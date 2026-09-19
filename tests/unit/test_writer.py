import os
from pathlib import Path
import subprocess

import pytest

from agent_subagent_router.contracts import Budgets, RouterError, TaskContract, canonical_bytes, hash_bytes
from agent_subagent_router.resolver import resolve
from agent_subagent_router.writer import apply_candidate, prepare_candidate, seal_candidate


def write(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(mode)


def init_repo(root: Path) -> None:
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), 'config', 'user.email', 'writer@example.test'], check=True)
    subprocess.run(['git', '-C', str(root), 'config', 'user.name', 'Writer'], check=True)
    write(root / 'src' / 'owned.py', 'value = "before"\n')
    write(root / 'src' / 'other.py', 'other = "baseline"\n')
    write(root / 'unrelated.py', 'unrelated = "baseline"\n')
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), 'commit', '-qm', 'baseline'], check=True)


def task(root: Path, read_paths=None, write_paths=None) -> TaskContract:
    write_paths = write_paths or ['src/owned.py']
    return TaskContract(
        parent_session_id='parent', task_id='writer', cwd=str(root), role='implementer',
        goal='change one exact file', read_paths=read_paths or ['src'], write_paths=write_paths,
        permissions=['read', 'candidate-write'], selected_refs=[], active_documents='not_applicable',
        harness_refs=[], constitution_refs=[], skills=[], skill_roots=[], expected_evidence=['src/owned.py'],
        backend='kimi', profile='worker', budgets=Budgets(30, 10, 1, 100000, 100000),
        instruction_precedence=['AGENTS.md', 'CLAUDE.md'],
    )


def manifest(root: Path, tmp_path: Path, read_paths=None, write_paths=None) -> dict:
    return resolve(task(root, read_paths, write_paths), tmp_path / 'snapshot', {
        'backend': 'kimi', 'profile': 'worker', 'runtime': 'claude-code', 'capabilities': ['read'],
    })


def expect(call, code: str) -> None:
    with pytest.raises(RouterError) as raised:
        call()
    assert raised.value.code == code


def prepared(root: Path, tmp_path: Path, read_paths=None) -> dict:
    return prepare_candidate(manifest(root, tmp_path, read_paths), tmp_path / 'candidate')


def candidate_owned(candidate: dict) -> Path:
    return Path(candidate['candidate_root']) / 'project' / 'src' / 'owned.py'


def test_existing_dirty_owned_target_is_rejected_but_unrelated_dirty_is_not(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    init_repo(root)
    write(root / 'src' / 'owned.py', 'value = "dirty"\n')
    expect(lambda: prepare_candidate(manifest(root, tmp_path), tmp_path / 'candidate'), 'WRITER_DIRTY_TARGET')

    root = tmp_path / 'second-repo'
    init_repo(root)
    write(root / 'unrelated.py', 'unrelated = "dirty"\n')
    candidate = prepared(root, tmp_path / 'second')
    assert candidate_owned(candidate).read_text() == 'value = "before"\n'


def test_untracked_owned_target_is_not_a_clean_baseline(tmp_path):
    root = tmp_path/'repo'
    init_repo(root)
    subprocess.run(['git', '-C', str(root), 'rm', '--cached', 'src/owned.py'], check=True,
                   capture_output=True)
    expect(lambda: prepared(root, tmp_path), 'WRITER_UNTRACKED_TARGET')


def test_preimage_and_untouched_selected_source_drift_block_seal_or_apply(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    init_repo(root)
    candidate = prepared(root, tmp_path)
    candidate_owned(candidate).write_text('value = "candidate"\n')
    sealed = seal_candidate(candidate)
    write(root / 'src' / 'owned.py', 'value = "host drift"\n')
    expect(lambda: apply_candidate(sealed, verified_candidate_hash=sealed['seal']), 'SOURCE_CHANGED')

    root = tmp_path / 'second-repo'
    init_repo(root)
    candidate = prepared(root, tmp_path / 'second')
    write(root / 'src' / 'other.py', 'other = "host drift"\n')
    expect(lambda: seal_candidate(candidate), 'SOURCE_CHANGED')


@pytest.mark.parametrize('mutation', ['extra', 'symlink', 'mode', 'delete', 'rename'])
def test_candidate_rejects_scope_escape_and_baseline_shape_changes(tmp_path: Path, mutation: str) -> None:
    root = tmp_path / 'repo'
    init_repo(root)
    candidate = prepared(root, tmp_path)
    candidate_root = Path(candidate['candidate_root'])
    other = candidate_root / 'project' / 'src' / 'other.py'
    if mutation == 'extra':
        write(candidate_root / 'project' / 'src' / 'extra.py', 'extra\n')
    elif mutation == 'symlink':
        other.unlink()
        os.symlink(tmp_path / 'outside', other)
    elif mutation == 'mode':
        other.chmod(0o600)
    elif mutation == 'delete':
        other.unlink()
    else:
        other.rename(other.with_name('renamed.py'))
    expect(lambda: seal_candidate(candidate), 'CANDIDATE_TREE_CHANGED' if mutation != 'mode'
           else 'CANDIDATE_MODE_CHANGED')


def test_wrong_test_hash_is_rejected_and_clean_atomic_apply_preserves_unrelated_dirty(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    init_repo(root)
    candidate = prepared(root, tmp_path, ['src/owned.py'])
    candidate_owned(candidate).write_text('value = "candidate"\n')
    sealed = seal_candidate(candidate)
    expect(lambda: apply_candidate(sealed, verified_candidate_hash='0' * 64), 'TEST_BINDING_MISMATCH')

    write(root / 'unrelated.py', 'unrelated = "dirty"\n')
    receipt = apply_candidate(sealed, verified_candidate_hash=sealed['seal'])
    assert root.joinpath('src', 'owned.py').read_text() == 'value = "candidate"\n'
    assert root.joinpath('unrelated.py').read_text() == 'unrelated = "dirty"\n'
    assert receipt['applied'][0]['path'] == str((root / 'src' / 'owned.py').resolve())


def test_recomputed_candidate_seal_cannot_forge_derived_write_authority(tmp_path: Path) -> None:
    root = tmp_path/'repo'
    init_repo(root)
    candidate = prepared(root, tmp_path)
    other = next(record for record in candidate['files'] if record['source_path'].endswith('src/other.py'))
    other['owned'] = True
    other['candidate_mode'] |= 0o200
    candidate['owned_paths'].append(other['source_path'])
    candidate['source_preimage'] = [
        {'path': record['source_path'], 'sha256': record['source_sha256'],
         'size': record['source_size'], 'mode': record['source_mode']} for record in candidate['files']]
    candidate['seal'] = hash_bytes(canonical_bytes({key: value for key, value in candidate.items() if key != 'seal'}))
    expect(lambda: seal_candidate(candidate), 'INVALID_CANDIDATE')


def test_recomputed_seals_cannot_add_or_duplicate_bound_records(tmp_path: Path) -> None:
    root = tmp_path/'repo'
    init_repo(root)
    candidate = prepared(root, tmp_path)
    candidate['files'].append(dict(candidate['files'][0]))
    candidate['source_preimage'].append(dict(candidate['source_preimage'][0]))
    candidate['seal'] = hash_bytes(canonical_bytes({key: value for key, value in candidate.items() if key != 'seal'}))
    expect(lambda: seal_candidate(candidate), 'INVALID_CANDIDATE')

    candidate = prepared(root, tmp_path/'second')
    candidate_owned(candidate).write_text('value = "candidate"\n')
    sealed = seal_candidate(candidate)
    sealed['files'].append(dict(sealed['files'][0]))
    sealed['source_preimage'].append(dict(sealed['source_preimage'][0]))
    sealed['seal'] = hash_bytes(canonical_bytes({key: value for key, value in sealed.items() if key != 'seal'}))
    expect(lambda: apply_candidate(sealed, verified_candidate_hash=sealed['seal']), 'INVALID_CANDIDATE')


def test_candidate_seal_rejects_source_changed_between_hash_and_immutable_copy(tmp_path: Path, monkeypatch) -> None:
    import agent_subagent_router.writer as writer

    root = tmp_path/'repo'
    init_repo(root)
    candidate = prepared(root, tmp_path)
    candidate_owned(candidate).write_text('value = "candidate"\n')
    original = writer._copy_immutable

    def race(source_root, sealed_root, records):
        candidate_owned(candidate).write_text('value = "raced"\n')
        original(source_root, sealed_root, records)

    monkeypatch.setattr(writer, '_copy_immutable', race)
    expect(lambda: seal_candidate(candidate), 'CANDIDATE_SNAPSHOT_CHANGED')


def test_apply_restores_exact_source_mode_despite_umask(tmp_path: Path) -> None:
    root = tmp_path/'repo'
    init_repo(root)
    owned = root/'src'/'owned.py'
    owned.chmod(0o666)
    candidate = prepared(root, tmp_path)
    candidate_owned(candidate).write_text('value = "candidate"\n')
    sealed = seal_candidate(candidate)
    previous = os.umask(0o077)
    try:
        apply_candidate(sealed, verified_candidate_hash=sealed['seal'])
    finally:
        os.umask(previous)
    assert owned.stat().st_mode & 0o777 == 0o666


def test_multifile_candidate_apply_rejects_before_host_mutation(tmp_path: Path) -> None:
    root = tmp_path/'repo'
    init_repo(root)
    candidate = prepare_candidate(manifest(root, tmp_path, write_paths=['src/owned.py', 'src/other.py']),
                                  tmp_path/'candidate')
    candidate_root = Path(candidate['candidate_root'])/'project'/'src'
    candidate_root.joinpath('owned.py').write_text('value = "candidate"\n')
    candidate_root.joinpath('other.py').write_text('other = "candidate"\n')
    sealed = seal_candidate(candidate)
    before = {path: path.read_bytes() for path in (root/'src'/'owned.py', root/'src'/'other.py')}
    expect(lambda: apply_candidate(sealed, verified_candidate_hash=sealed['seal']), 'UNSUPPORTED_MULTIFILE_APPLY')
    assert {path: path.read_bytes() for path in before} == before


def test_resealed_nonowned_test_baseline_cannot_differ_from_host(tmp_path):
    from agent_subagent_router.contracts import hash_bytes
    from agent_subagent_router.writer import _seal
    root=tmp_path/'repo'
    init_repo(root)
    candidate=prepared(root,tmp_path)
    sealed=seal_candidate(candidate)
    other=next(item for item in sealed['files'] if item['source_path']==str(root/'src/other.py'))
    path=Path(sealed['sealed_root'])/other['relative']
    path.chmod(0o600)
    path.write_bytes(b'forged test baseline\n')
    path.chmod(other['candidate_mode'] & ~0o222)
    other.update(candidate_sha256=hash_bytes(path.read_bytes()),candidate_size=path.stat().st_size)
    sealed['seal']=_seal({k:v for k,v in sealed.items() if k!='seal'})
    expect(lambda:apply_candidate(sealed,verified_candidate_hash=sealed['seal']),'INVALID_CANDIDATE')
