from pathlib import Path
import subprocess
import sys

import pytest

from agent_subagent_router.contracts import RouterError
from agent_subagent_router.installation import install, rollback


SOURCE = Path(__file__).resolve().parents[2]


def test_managed_installation_is_bound_and_rollback_preserves_state(tmp_path):
    manifest = install(SOURCE, tmp_path, sys.executable)
    entry = tmp_path/'.local/bin/subagent'
    process = subprocess.run([str(entry), '--version'], capture_output=True, text=True)
    assert process.returncode == 0 and process.stdout.strip() == '0.1.0'
    assert manifest['source_hash'] and manifest['source_commit']
    assert (tmp_path/'.agents/skills/external-subagent/SKILL.md').is_file()
    assert str((tmp_path/'.agents/skills/external-subagent').resolve()).startswith(
        str(tmp_path/'.local/share/agent-subagent-router/installations'))
    receipt = tmp_path/'.local/state/agent-subagent-router/runs/keep'
    receipt.parent.mkdir(parents=True)
    receipt.write_text('retain')
    rollback(tmp_path)
    assert not entry.exists() and receipt.read_text() == 'retain'
    assert Path(manifest['package_root']).exists()


def test_unmanaged_entry_is_not_overwritten(tmp_path):
    entry = tmp_path/'.local/bin/subagent'
    entry.parent.mkdir(parents=True)
    entry.write_text('USER WORK')
    with pytest.raises(RouterError, match='UNMANAGED_INSTALLATION'):
        install(SOURCE, tmp_path, sys.executable)
    assert entry.read_text() == 'USER WORK'


def test_install_source_drift_and_rollback_drift_fail_closed(tmp_path):
    manifest = install(SOURCE, tmp_path, sys.executable)
    package = Path(manifest['package_root'])/'agent_subagent_router/__init__.py'
    package.write_text('tampered')
    entry = tmp_path/'.local/bin/subagent'
    process = subprocess.run([str(entry), '--version'], capture_output=True, text=True)
    assert process.returncode != 0 and 'INSTALLATION_DRIFT' in process.stderr
    entry.write_text('user changed wrapper')
    with pytest.raises(RouterError, match='INSTALLATION_DRIFT'):
        rollback(tmp_path)


def test_skill_snapshot_drift_blocks_cli_and_rollback(tmp_path):
    manifest = install(SOURCE, tmp_path, sys.executable)
    skill = Path(manifest['skill_target'])/'SKILL.md'
    skill.write_text('tampered authority')
    process = subprocess.run([str(tmp_path/'.local/bin/subagent'), '--version'], capture_output=True)
    assert process.returncode != 0 and b'INSTALLATION_DRIFT' in process.stderr
    with pytest.raises(RouterError, match='INSTALLATION_DRIFT'):
        rollback(tmp_path)


@pytest.mark.parametrize('existing', [False, True])
def test_failed_manifest_write_restores_only_owned_entries(tmp_path, monkeypatch, existing):
    import agent_subagent_router.installation as module
    entry = tmp_path/'.local/bin/subagent'
    if existing:
        install(SOURCE, tmp_path, sys.executable)
    before = entry.read_bytes() if entry.exists() else None

    def failed(*args, **kwargs):
        raise OSError('synthetic disk failure')

    monkeypatch.setattr(module, 'atomic_json', failed)
    with pytest.raises(OSError):
        install(SOURCE, tmp_path, sys.executable)
    if existing:
        assert entry.read_bytes() == before
        rollback(tmp_path)
    else:
        assert not entry.exists()
        assert not (tmp_path/'.agents/skills/external-subagent').exists()
