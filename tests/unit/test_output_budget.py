import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_subagent_router.api import inspect_task, run_contract
from agent_subagent_router.cli import main
from agent_subagent_router.contracts import RouterError, TaskContract
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.supervisor import Invocation, supervise


def task_data(root):
    return dict(parent_session_id='budget-parent', task_id='budget-task', cwd=str(root),
        explicit_root=str(root), role='explorer', goal='Read the selected source.',
        read_paths=['a.py'], write_paths=[], permissions=['read'], selected_refs=[],
        active_documents='not_applicable', harness_refs=[], constitution_refs=[],
        skills=[], skill_roots=[], expected_evidence=['a.py'], backend='kimi', profile='worker',
        budgets=dict(wall_seconds=5, idle_seconds=5, request_limit=1, context_bytes=100000))


def test_default_is_sealed_and_captures_large_event_stream(tmp_path):
    root = tmp_path/'project'
    root.mkdir()
    (root/'a.py').write_text('VALUE = 1\n')
    task = TaskContract.from_dict(task_data(root))
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    sealed = inspect_task(task, tmp_path/'contracts', runtime)
    restored = TaskContract.from_dict(sealed['task'])
    assert restored.budgets.output_bytes == 8388608
    # Representative native progress overhead alone can exhaust a 1 MiB cap.
    stream = tmp_path/'events.jsonl'
    terminal = b'{"type":"result","subtype":"success","result":"done"}\n'
    stream.write_bytes(b'{"type":"system","subtype":"thinking_tokens","estimated_tokens":1}\n'
                       * 20000 + terminal)
    result = supervise(Invocation(('/bin/cat', str(stream)), Path('/tmp'), {}, b'',
                                  restored.budgets))
    assert result.reason == 'exited' and not result.truncated
    assert result.stdout.endswith(terminal)


@pytest.mark.parametrize('cap', [32000, 1048576, 2097151, 2097152, 16777216])
@pytest.mark.parametrize('profile', ['worker', 'deep'])
def test_live_budget_refusal_precedes_execution_and_preserves_seal(tmp_path, cap, profile):
    root = tmp_path/'project'
    root.mkdir()
    (root/'a.py').write_text('VALUE = 1\n')
    data = task_data(root)
    data['profile'] = profile
    data['budgets']['output_bytes'] = cap
    task = TaskContract.from_dict(data)
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    sealed = inspect_task(task, tmp_path/'contracts', runtime)
    store = ReceiptStore(tmp_path/'runs')
    receipt = run_contract(sealed, 'kimi', profile, store, runtime)
    expected = 'OUTPUT_BUDGET_TOO_SMALL' if cap < 2097152 else 'BLOCKED_CAPABILITY'
    assert receipt['classification'] == expected
    assert receipt['process'] is None and receipt['wire_requests'] == 0
    assert store.read(receipt['invocation_id']) == receipt
    assert sealed['task']['budgets']['output_bytes'] == cap
    assert not (store.root/'consumed-contracts').exists()


@pytest.mark.parametrize('cap', [None, 0, True, 16777217])
def test_explicit_invalid_budget_is_not_replaced_by_default(tmp_path, cap):
    data = task_data(tmp_path)
    data['budgets']['output_bytes'] = cap
    with pytest.raises(RouterError, match='INVALID_CONTRACT'):
        TaskContract.from_dict(data)


def test_gemini_does_not_inherit_kimi_default(tmp_path):
    data = task_data(tmp_path)
    data['backend'] = 'gemini'
    with pytest.raises(RouterError, match='INVALID_CONTRACT'):
        TaskContract.from_dict(data)


@pytest.mark.parametrize('cap', [None, 32000, 2097152])
def test_inspect_exposes_sealed_budget_and_live_warning(tmp_path, monkeypatch, capsys, cap):
    root = tmp_path/'project'
    root.mkdir()
    (root/'a.py').write_text('VALUE = 1\n')
    data = task_data(root)
    if cap is not None:
        data['budgets']['output_bytes'] = cap
    task_file = tmp_path/'task.json'
    task_file.write_text(json.dumps(data))
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    sandbox = SimpleNamespace(verify=lambda: None, image='pinned', runtime_sha256='pinned')
    monkeypatch.setattr('agent_subagent_router.cli.installed_backend_runtime', lambda _: runtime)
    monkeypatch.setattr('agent_subagent_router.cli.installed_sandbox', lambda *_: sandbox)
    assert main(['--state', str(tmp_path/'state'), 'inspect', '--cwd', str(root),
                 '--task', str(task_file)]) == 0
    output = json.loads(capsys.readouterr().out)
    sealed = json.loads(Path(output['contract']).read_text())
    assert output['budgets'] == sealed['task']['budgets']
    assert output['frozen_source_paths'] == sorted(s['path'] for s in sealed['sources'])
    assert output['budgets']['output_bytes'] == (8388608 if cap is None else cap)
    if cap == 32000:
        assert output['warnings'][0]['classification'] == 'OUTPUT_BUDGET_TOO_SMALL'
        assert output['warnings'][0]['live_execution'] == 'BLOCKED'
    else:
        assert 'warnings' not in output
