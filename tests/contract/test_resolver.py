import copy
import os
import subprocess
from pathlib import Path

import pytest

import agent_subagent_router.resolver as resolver_module
from agent_subagent_router.contracts import Budgets, RouterError, TaskContract, hash_bytes
from agent_subagent_router.resolver import resolve, verify


def write(path: Path, text: str, mode: int = 0o644) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return path


def task(repo: Path, **changes) -> TaskContract:
    data = {
        'parent_session_id': 'parent', 'task_id': 'task', 'cwd': str(repo),
        'role': 'explorer', 'goal': 'map a bounded source set',
        'read_paths': ['src'], 'write_paths': [], 'permissions': ['read'],
        'selected_refs': [], 'active_documents': 'not_applicable',
        'harness_refs': [], 'constitution_refs': [], 'skills': [], 'skill_roots': [],
        'expected_evidence': ['src/main.py'], 'backend': 'kimi', 'profile': 'worker',
        'budgets': Budgets(60, 10, 1, 1024, 1024 * 1024),
        'instruction_precedence': ['AGENTS.md', 'CLAUDE.md'],
    }
    data.update(changes)
    return TaskContract(**data)


def transport(**changes) -> dict:
    data = {'backend': 'kimi', 'profile': 'worker', 'runtime': 'claude-code',
            'capabilities': ['read']}
    data.update(changes)
    return data


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def init_git(repo: Path) -> None:
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'user.email', 'test@example.com'], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'user.name', 'Test'], check=True)
    write(repo / 'src' / 'main.py', 'answer = 42\n')
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'initial'], check=True)


def error_code(call, code: str) -> None:
    with pytest.raises(RouterError) as raised:
        call()
    assert raised.value.code == code


def test_seals_ancestor_and_nested_rules_into_frozen_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    write(repo / 'AGENTS.md', 'root rule\n')
    write(repo / 'src' / 'AGENTS.override.md', 'nested rule\n')
    manifest = resolve(task(repo), tmp_path / 'snapshot', transport())

    assert manifest['schema_version'] == 1
    assert manifest['project']['root'] == str(repo.resolve())
    paths = {item['relative_path'] for item in manifest['sources']}
    assert {'AGENTS.md', 'src/AGENTS.override.md', 'src/main.py'} <= paths
    for item in manifest['sources']:
        assert (Path(manifest['snapshot_root']) / item['snapshot_path']).is_file()
    verify(manifest)


def test_seals_named_constitution_ancestors_above_the_git_root(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    parent_rule = write(tmp_path / 'AGENTS.md', 'host ancestor rule\n')
    manifest = resolve(task(repo), tmp_path / 'snapshot', transport())
    assert str(parent_rule) in {item['path'] for item in manifest['sources']}
    assert manifest['instruction_precedence'] == ['AGENTS.md', 'CLAUDE.md']


def test_new_named_ancestor_rule_invalidates_the_host_preimage(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    manifest = resolve(task(repo), tmp_path / 'snapshot', transport())
    write(tmp_path / 'AGENTS.md', 'arrived after seal\n')
    error_code(lambda: verify(manifest), 'INSTRUCTION_CHANGED')


def test_instruction_created_during_sealing_is_not_left_unbound(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    original = resolver_module._coalesce

    def inject_rule(candidates, root):
        sources = original(candidates, root)
        write(repo / 'src' / 'AGENTS.md', 'late nested rule\n')
        return sources

    monkeypatch.setattr(resolver_module, '_coalesce', inject_rule)
    error_code(lambda: resolve(task(repo), tmp_path / 'snapshot', transport()), 'INSTRUCTION_CHANGED')


def test_git_identity_uses_submodule_root_and_non_git_requires_explicit_root(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    manifest = resolve(task(repo), tmp_path / 'git-snapshot', transport())
    assert manifest['project']['head'] == git(repo, 'rev-parse', 'HEAD')
    assert Path(manifest['project']['gitdir']) == repo / '.git'

    plain = tmp_path / 'plain'
    write(plain / 'src' / 'main.py', 'plain\n')
    error_code(lambda: resolve(task(plain), tmp_path / 'none', transport()), 'ROOT_REQUIRED')
    manifest = resolve(task(plain, explicit_root=str(plain)), tmp_path / 'plain-snapshot', transport())
    assert manifest['project']['head'] is None


def test_git_worktree_identity_is_taken_from_the_selected_worktree(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    linked = tmp_path / 'linked-worktree'
    subprocess.run(['git', '-C', str(repo), 'worktree', 'add', '-qb', 'linked', str(linked)], check=True)
    manifest = resolve(task(linked), tmp_path / 'snapshot', transport())
    assert manifest['project']['root'] == str(linked.resolve())
    assert manifest['project']['head'] == git(linked, 'rev-parse', 'HEAD')


def test_unborn_and_submodule_git_identities_are_explicit(tmp_path: Path) -> None:
    unborn = tmp_path / 'unborn'
    subprocess.run(['git', 'init', '-q', str(unborn)], check=True)
    write(unborn / 'src' / 'main.py', 'unborn\n')
    manifest = resolve(task(unborn), tmp_path / 'unborn-snapshot', transport())
    assert manifest['project']['head'] is None

    child = tmp_path / 'child'
    init_git(child)
    parent = tmp_path / 'parent'
    init_git(parent)
    subprocess.run(['git', '-C', str(parent), '-c', 'protocol.file.allow=always', 'submodule', 'add',
                    '-q', str(child), 'vendor/child'], check=True)
    subprocess.run(['git', '-C', str(parent), 'commit', '-qm', 'add child'], check=True)
    submanifest = resolve(task(parent / 'vendor' / 'child'), tmp_path / 'sub-snapshot', transport())
    assert submanifest['project']['root'] == str((parent / 'vendor' / 'child').resolve())
    assert submanifest['project']['superproject_root'] == str(parent.resolve())


def test_differing_instruction_formats_need_explicit_precedence(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    write(repo / 'AGENTS.md', 'agents rule\n')
    write(repo / 'CLAUDE.md', 'claude rule\n')
    error_code(lambda: resolve(task(repo, instruction_precedence=None), tmp_path / 'snapshot', transport()),
               'CONTRACT_CONFLICT')


def test_write_scope_contributes_its_applicable_instruction_closure(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    write(repo / 'policies' / 'AGENTS.md', 'writer rule\n')
    writer = task(repo, role='implementer', permissions=['read', 'candidate-write'],
                  write_paths=['policies/result.py'])
    manifest = resolve(writer, tmp_path / 'snapshot', transport())
    assert 'policies/AGENTS.md' in {item['relative_path'] for item in manifest['sources']}


def test_accepted_reference_hash_and_required_capability_fail_closed(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    spec = write(repo / 'docs' / 'spec.md', 'accepted\n')
    selected = {'path': str(spec), 'sha256': hash_bytes(spec.read_bytes()), 'accepted': True}
    good = task(repo, selected_refs=[selected], active_documents='accepted_refs')
    resolve(good, tmp_path / 'snapshot', transport())
    write(spec, 'drifted\n')
    error_code(lambda: resolve(good, tmp_path / 'stale', transport()), 'STALE_ACCEPTED_REF')
    error_code(lambda: resolve(task(repo, required_capabilities=['hooks']), tmp_path / 'hook', transport()),
               'UNSUPPORTED_REQUIRED_CAPABILITY')


def test_verify_rejects_changed_source_and_new_nested_instruction(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    manifest = resolve(task(repo), tmp_path / 'snapshot', transport())
    write(repo / 'src' / 'main.py', 'changed\n')
    error_code(lambda: verify(manifest), 'SOURCE_CHANGED')

    manifest = resolve(task(repo), tmp_path / 'snapshot-two', transport())
    write(repo / 'src' / 'AGENTS.md', 'new rule\n')
    error_code(lambda: verify(manifest), 'INSTRUCTION_CHANGED')
    (repo / 'src' / 'AGENTS.md').unlink()
    manifest = resolve(task(repo), tmp_path / 'snapshot-three', transport())
    os.symlink(tmp_path / 'outside-rule', repo / 'src' / 'AGENTS.md')
    error_code(lambda: verify(manifest), 'INSTRUCTION_CHANGED')


def test_directory_closure_excludes_sensitive_content_and_rejects_symlinks(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    write(repo / 'src' / 'data' / 'ledger.json', '{}')
    write(repo / 'src' / '.env', 'secret')
    manifest = resolve(task(repo), tmp_path / 'snapshot', transport())
    paths = {item['relative_path'] for item in manifest['sources']}
    assert 'src/data/ledger.json' not in paths
    assert 'src/.env' not in paths
    os.symlink(tmp_path / 'outside.txt', repo / 'src' / 'escape')
    error_code(lambda: resolve(task(repo), tmp_path / 'link', transport()), 'SYMLINK_FORBIDDEN')
    error_code(lambda: resolve(task(repo, read_paths=['src/escape']), tmp_path / 'direct-link', transport()),
               'SYMLINK_FORBIDDEN')


def test_directory_closure_does_not_grant_files_added_after_seal(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    manifest = resolve(task(repo), tmp_path / 'snapshot', transport())
    write(repo / 'src' / 'later.py', 'later\n')
    verify(manifest)
    assert 'src/later.py' not in {item['relative_path'] for item in manifest['sources']}


def test_context_budget_rejects_the_complete_input_instead_of_truncating(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    write(repo / 'src' / 'large.py', 'x' * 32)
    constrained = task(repo, budgets=Budgets(60, 10, 1, 1024, 16))
    error_code(lambda: resolve(constrained, tmp_path / 'snapshot', transport()), 'CONTRACT_TOO_LARGE')
    metadata_only = task(repo, budgets=Budgets(60, 10, 1, 1024, 1))
    error_code(lambda: resolve(metadata_only, tmp_path / 'metadata', transport()), 'CONTRACT_TOO_LARGE')


def test_evidence_must_be_bound_to_a_frozen_source(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    error_code(lambda: resolve(task(repo, expected_evidence=['unbound-output']), tmp_path / 'snapshot', transport()),
               'UNFROZEN_EVIDENCE')


def test_skill_selection_copies_binary_assets_and_modes_and_rejects_name_collision(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    root_a, root_b = tmp_path / 'skills-a', tmp_path / 'skills-b'
    write(root_a / 'demo' / 'SKILL.md', 'A\n')
    asset = root_a / 'demo' / 'scripts' / 'run.bin'
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(b'\x00binary')
    asset.chmod(0o755)
    write(root_b / 'demo' / 'SKILL.md', 'B\n')
    base = task(repo, skills=['demo'], skill_roots=[str(root_a), str(root_b)])
    error_code(lambda: resolve(base, tmp_path / 'ambiguous', transport()), 'AMBIGUOUS_SKILL')

    manifest = resolve(task(repo, skills=[str(root_a / 'demo')], skill_roots=[str(root_a), str(root_b)]),
                       tmp_path / 'snapshot', transport())
    record = next(item for item in manifest['sources'] if item['path'] == str(asset.resolve()))
    assert record['mode'] & 0o111
    assert (Path(manifest['snapshot_root']) / record['snapshot_path']).read_bytes() == b'\x00binary'


def test_snapshot_and_host_mode_drift_or_unexpected_snapshot_file_fail_closed(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    manifest = resolve(task(repo), tmp_path / 'snapshot', transport())
    record = next(item for item in manifest['sources'] if item['relative_path'] == 'src/main.py')
    snapshot_file = Path(manifest['snapshot_root']) / record['snapshot_path']
    assert snapshot_file.stat().st_mode & 0o777 == 0o400
    snapshot_file.chmod(0o500)
    error_code(lambda: verify(manifest), 'SNAPSHOT_CHANGED')

    manifest = resolve(task(repo), tmp_path / 'snapshot-two', transport())
    Path(manifest['snapshot_root']).chmod(0o700)
    write(Path(manifest['snapshot_root']) / 'extra.txt', 'unexpected\n')
    error_code(lambda: verify(manifest), 'SNAPSHOT_CHANGED')

    manifest = resolve(task(repo), tmp_path / 'snapshot-three', transport())
    (repo / 'src' / 'main.py').chmod(0o600)
    error_code(lambda: verify(manifest), 'SOURCE_CHANGED')

    manifest = resolve(task(repo), tmp_path / 'snapshot-four', transport())
    snapshot_root = Path(manifest['snapshot_root'])
    snapshot_root.chmod(0o700)
    (snapshot_root / 'extra').mkdir()
    error_code(lambda: verify(manifest), 'SNAPSHOT_CHANGED')

    manifest = resolve(task(repo), tmp_path / 'snapshot-five', transport())
    snapshot_root = Path(manifest['snapshot_root'])
    snapshot_root.chmod(0o700)
    os.symlink(tmp_path / 'outside', snapshot_root / 'link')
    error_code(lambda: verify(manifest), 'SNAPSHOT_CHANGED')


def test_secret_paths_and_symlinked_skill_roots_are_rejected_before_reading(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    write(repo / 'src' / '.ssh' / 'id.pem', 'private')
    manifest = resolve(task(repo), tmp_path / 'snapshot', transport())
    assert 'src/.ssh/id.pem' not in {item['relative_path'] for item in manifest['sources']}
    error_code(lambda: resolve(task(repo, read_paths=['src/.ssh/id.pem']), tmp_path / 'secret', transport()),
               'SENSITIVE_SOURCE')

    skill_root = tmp_path / 'skill-root'
    write(skill_root / 'demo' / 'SKILL.md', 'demo\n')
    linked_root = tmp_path / 'linked-skills'
    os.symlink(skill_root, linked_root)
    selected = task(repo, skills=['demo'], skill_roots=[str(linked_root)])
    error_code(lambda: resolve(selected, tmp_path / 'skill-snapshot', transport()), 'SYMLINK_FORBIDDEN')


@pytest.mark.parametrize('mutate', [
    lambda manifest: manifest.update(sources=None),
    lambda manifest: manifest.update(sources=[None]),
    lambda manifest: manifest.update(sources=['not-a-source']),
    lambda manifest: manifest['sources'][0].update(size='not-an-int'),
    lambda manifest: manifest.update(task=None),
    lambda manifest: manifest.update(project=None),
    lambda manifest: manifest.update(transport=None),
    lambda manifest: manifest.update(instruction_observations=None),
    lambda manifest: manifest.update(instruction_observations=[None]),
])
def test_malformed_manifest_fields_always_raise_typed_router_errors(tmp_path: Path, mutate) -> None:
    repo = tmp_path / 'repo'
    init_git(repo)
    manifest = copy.deepcopy(resolve(task(repo), tmp_path / 'snapshot', transport()))
    mutate(manifest)
    with pytest.raises(RouterError):
        verify(manifest)
