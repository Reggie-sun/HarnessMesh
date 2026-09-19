import json

from agent_subagent_router.cli import main
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.smoke import run_smoke
from agent_subagent_router.api import inspect_task, run_contract
from agent_subagent_router.contracts import RouterError, TaskContract
from types import SimpleNamespace
import pytest


def fake_runtime():
    return SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})


def test_missing_credential_creates_recoverable_non_success_receipt(tmp_path):
    runtime = fake_runtime()
    store = ReceiptStore(tmp_path/'runs')
    receipt = run_smoke(runtime, 'worker', store, None)
    assert receipt['classification'] == 'CREDENTIAL_REQUIRED'
    assert receipt['process'] is None and receipt['wire_requests'] == 0
    assert store.read(receipt['invocation_id']) == receipt


def test_doctor_never_claims_containment_from_installed_binary(capsys, monkeypatch):
    monkeypatch.setattr('agent_subagent_router.cli.installed_runtime', fake_runtime)
    monkeypatch.setattr('agent_subagent_router.cli.probe_containment',
                        lambda: {'qualified': False, 'probe_exit': 0})
    monkeypatch.setattr('agent_subagent_router.cli.installed_sandbox',
                        lambda **_: (_ for _ in ()).throw(RouterError('BLOCKED_CAPABILITY')))
    assert main(['doctor']) == 2
    output = json.loads(capsys.readouterr().out)
    assert output['containment']['qualified'] is False
    assert output['project_routes'] == 'BLOCKED_CAPABILITY'


def test_cli_has_no_accept_revert_or_fallback_commands():
    for command in ('accept', 'revert', 'fallback'):
        with pytest.raises(SystemExit) as result:
            main([command])
        assert result.value.code == 2


def test_sealed_project_invocation_stays_blocked_and_cannot_override_route(tmp_path):
    root = tmp_path/'project'
    root.mkdir()
    (root/'a.py').write_text('VALUE = 1\n')
    task = TaskContract.from_dict(dict(parent_session_id='p', task_id='t', cwd=str(root),
         explicit_root=str(root), role='explorer', goal='map synthetic', read_paths=['a.py'],
         write_paths=[], permissions=['read'], selected_refs=[], active_documents='not_applicable',
         harness_refs=[], constitution_refs=[], skills=[], skill_roots=[], expected_evidence=['a.py'],
         backend='kimi', profile='worker', budgets=dict(wall_seconds=5,idle_seconds=5,request_limit=1,
                                                      output_bytes=10000,context_bytes=100000)))
    runtime = fake_runtime()
    manifest = inspect_task(task, tmp_path/'contracts', runtime)
    store = ReceiptStore(tmp_path/'runs')
    blocked = run_contract(manifest, 'kimi', 'worker', store, runtime)
    assert blocked['classification'] == 'BLOCKED_CAPABILITY' and blocked['wire_requests'] == 0
    assert blocked['process'] is None
    mismatch = run_contract(manifest, 'kimi', 'deep', store, runtime)
    assert mismatch['classification'] == 'SEALED_ROUTE_MISMATCH' and mismatch['process'] is None


def test_changed_credential_is_blocked_before_any_project_execution(tmp_path, monkeypatch):
    from agent_subagent_router.backends.kimi import profile
    from agent_subagent_router.transport.credentials import credential_fingerprint
    root = tmp_path/'project'
    root.mkdir()
    (root/'a.py').write_text('VALUE = 1\n')
    runtime = fake_runtime()
    sandbox = SimpleNamespace(verify=lambda: None, image='pinned', runtime_sha256='pinned')
    task = TaskContract.from_dict(dict(parent_session_id='p', task_id='t', cwd=str(root),
        explicit_root=str(root), role='explorer', goal='inspect', read_paths=['a.py'], write_paths=[],
        permissions=['read'], selected_refs=[], active_documents='not_applicable', harness_refs=[],
        constitution_refs=[], skills=[], skill_roots=[], expected_evidence=['a.py'],
        backend='kimi', profile='worker', budgets=dict(wall_seconds=5, idle_seconds=5,
        request_limit=1, output_bytes=10000, context_bytes=100000)))
    manifest = inspect_task(task, tmp_path/'contracts', runtime, sandbox=sandbox)
    qualified = {'classification': 'PARSED', 'evidence_kind': 'live',
        'profile': profile('worker').to_dict(), 'runtime': runtime.to_dict(),
        'credential_fingerprint': credential_fingerprint('kimi', 'key-A'),
        'observations': [{'classification': 'IDENTITY_VERIFIED', 'proof': 'authenticated_endpoint_declaration'}]}
    monkeypatch.setattr('agent_subagent_router.api.require_project_containment', lambda *_: {'qualified': True})
    monkeypatch.setattr('agent_subagent_router.route_qualification.read_qualification', lambda *_: (qualified, 'hash'))
    def forbidden(*args, **kwargs):
        raise AssertionError('must never spawn or send a request')
    monkeypatch.setattr('agent_subagent_router.project_run.execute_project', forbidden)
    key = tmp_path/'key'
    key.write_text('key-B')
    key.chmod(0o600)
    receipt = run_contract(manifest, 'kimi', 'worker', ReceiptStore(tmp_path/'runs'), runtime,
        sandbox=sandbox, qualification_id='qualification', credential_ref={'provider': 'kimi', 'file': str(key)})
    assert receipt['classification'] == 'QUALIFICATION_CREDENTIAL_MISMATCH'
    assert receipt['wire_requests'] == 0 and receipt['process'] is None


def test_gemini_dispatch_preserves_sealed_route_and_preflight_blocker(tmp_path, monkeypatch):
    root = tmp_path/'project'
    root.mkdir()
    (root/'a.py').write_text('VALUE = 1\n')
    runtime = fake_runtime()
    sandbox = SimpleNamespace(verify=lambda:None, image='pinned', runtime_sha256='pinned')
    task = TaskContract.from_dict(dict(parent_session_id='p', task_id='gemini', cwd=str(root),
        explicit_root=str(root), role='explorer', goal='inspect', read_paths=['a.py'], write_paths=[],
        permissions=['read'], selected_refs=[], active_documents='not_applicable', harness_refs=[],
        constitution_refs=[], skills=[], skill_roots=[], expected_evidence=['a.py'],
        backend='gemini', profile='worker', budgets=dict(wall_seconds=5,idle_seconds=5,
        request_limit=1,output_bytes=10000,context_bytes=100000)))
    manifest = inspect_task(task, tmp_path/'contracts', runtime, sandbox=sandbox)
    assert manifest['transport']['runtime'] == 'gemini-cli'
    monkeypatch.setattr('agent_subagent_router.permissions.gemini_qualification.qualify',
                        lambda *_: {'qualified':True})
    def ineligible(*args, **kwargs):
        raise RouterError('GEMINI_INELIGIBLE', 'UNSUPPORTED_CLIENT')
    monkeypatch.setattr('agent_subagent_router.gemini_run.execute_gemini', ineligible)
    store = ReceiptStore(tmp_path/'runs')
    receipt = run_contract(manifest, 'gemini', 'worker', store, runtime, sandbox=sandbox)
    assert receipt['classification'] == 'GEMINI_INELIGIBLE'
    assert receipt['reason'] == 'UNSUPPORTED_CLIENT' and receipt['wire_requests'] == 0
    assert store.read(receipt['invocation_id']) == receipt
    mismatch = run_contract(manifest, 'kimi', 'worker', store, runtime, sandbox=sandbox)
    assert mismatch['classification'] == 'SEALED_ROUTE_MISMATCH'
