import os
from pathlib import Path

import pytest

from agent_subagent_router import atomic_apply
from agent_subagent_router.contracts import hash_bytes


def record(path):
    data = path.read_bytes()
    return {'source_path': str(path), 'source_sha256': hash_bytes(data), 'source_size': len(data),
            'source_mode': path.stat().st_mode & 0o777}


def test_exchange_preserves_mode_old_inode_and_late_writes_to_old_fd(tmp_path):
    path = tmp_path/'a.py'
    path.write_bytes(b'before')
    path.chmod(0o644)
    old = os.open(path, os.O_WRONLY)
    mask = os.umask(0o077)
    try:
        result = atomic_apply.exchange_owned_file(tmp_path, record(path), b'after')
    finally:
        os.umask(mask)
    assert result['classification'] == 'APPLIED'
    assert path.read_bytes() == b'after' and path.stat().st_mode & 0o777 == 0o644
    os.write(old, b'saved!')
    os.close(old)
    assert Path(result['retained_object']).read_bytes() == b'saved!'
    assert path.read_bytes() == b'after'
    assert (Path(result['recovery_path'])/'intent.json').is_file()


def test_edit_after_initial_preimage_check_is_preserved_and_conflict_recorded(tmp_path, monkeypatch):
    path = tmp_path/'a.py'
    path.write_bytes(b'before')
    original = atomic_apply._exchange
    def race(*args):
        path.write_bytes(b'user newer save')
        original(*args)
    monkeypatch.setattr(atomic_apply, '_exchange', race)
    result = atomic_apply.exchange_owned_file(tmp_path, record(path), b'candidate')
    assert result['classification'] == 'APPLY_CONFLICT'
    assert Path(result['retained_object']).read_bytes() == b'user newer save'
    assert path.read_bytes() == b'candidate'
    assert (Path(result['recovery_path'])/'outcome.json').is_file()


@pytest.mark.parametrize('failure', ['replace_after', 'fsync_after', 'receipt_after'])
def test_after_exchange_failures_return_recovery_not_false_no_effect(tmp_path, monkeypatch, failure):
    path = tmp_path/'a.py'
    path.write_bytes(b'before')
    original = atomic_apply._exchange
    def fault(*args):
        original(*args)
        if failure == 'replace_after':
            changed = tmp_path/'user-save'
            changed.write_bytes(b'new user file')
            os.replace(changed, path)
        if failure == 'fsync_after':
            monkeypatch.setattr(atomic_apply.os, 'fsync', lambda *_: (_ for _ in ()).throw(OSError('disk')))
        if failure == 'receipt_after':
            monkeypatch.setattr(atomic_apply, 'atomic_json', lambda *_: (_ for _ in ()).throw(OSError('disk')))
    monkeypatch.setattr(atomic_apply, '_exchange', fault)
    result = atomic_apply.exchange_owned_file(tmp_path, record(path), b'after')
    assert result['classification'] in ('APPLY_CONFLICT', 'APPLY_OUTCOME_UNKNOWN')
    assert Path(result['retained_object']).read_bytes() == b'before'
    assert (Path(result['recovery_path'])/'intent.json').is_file()
    if failure == 'replace_after':
        assert path.read_bytes() == b'new user file'


@pytest.mark.parametrize('timing', ['before','after'])
def test_canonical_parent_directory_replacement_is_never_applied_success(tmp_path, monkeypatch, timing):
    folder=tmp_path/'src'
    folder.mkdir()
    path=folder/'a.py'
    path.write_bytes(b'before')
    original=atomic_apply._facts if timing=='before' else atomic_apply._exchange
    moved=False
    def move_once():
        nonlocal moved
        if not moved:
            folder.rename(tmp_path/'moved')
            folder.mkdir()
            path.write_bytes(b'user new directory')
            moved=True
    def race(*args):
        result=original(*args)
        move_once()
        return result
    monkeypatch.setattr(atomic_apply,'_facts' if timing=='before' else '_exchange',race)
    if timing=='before':
        from agent_subagent_router.contracts import RouterError
        with pytest.raises(RouterError,match='SOURCE_CHANGED'):
            atomic_apply.exchange_owned_file(tmp_path,record(path),b'candidate')
        assert (tmp_path/'moved/a.py').read_bytes()==b'before'
    else:
        result=atomic_apply.exchange_owned_file(tmp_path,record(path),b'candidate')
        assert result['classification']=='APPLY_CONFLICT'
        assert Path(result['retained_object']).read_bytes()==b'before'
    assert path.read_bytes()==b'user new directory'
