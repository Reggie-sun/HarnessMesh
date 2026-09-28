import json
from types import SimpleNamespace

import pytest

from agent_subagent_router.api import inspect_task, run_contract
from agent_subagent_router.adapters.project_claude import project_command
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.cli import main
from agent_subagent_router.contracts import RouterError, TaskContract
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.resolver import resolve, verify
from test_output_budget import task_data


MAXIMUM = dict(wall_seconds=3600, idle_seconds=1800, request_limit=64,
               output_bytes=16777216, context_bytes=8388608, generation_tokens=32000)


@pytest.mark.parametrize('requested_profile', ['worker', 'deep'])
@pytest.mark.parametrize('generation', [None, 8192, 32000])
def test_new_seal_applies_global_maximum_without_changing_scope(tmp_path, requested_profile, generation):
    (tmp_path/'a.py').write_text('VALUE = 1\n')
    data = task_data(tmp_path)
    data['profile'] = requested_profile
    if generation is not None:
        data['budgets']['generation_tokens'] = generation
    task = TaskContract.from_dict(data)
    requested = task.to_dict()
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})

    sealed = inspect_task(task, tmp_path/'contracts', runtime)

    assert sealed['task']['budgets'] == MAXIMUM
    assert sealed['task']['profile'] == sealed['transport']['profile'] == 'deep'
    route = sealed['transport']['profile_identity']
    assert (route['client_model'], route['wire_model'], route['effort'], route['context_tokens']) == (
        'k3[1m]', 'k3', 'max', 1048576)
    assert sealed['transport']['resource_policy'] == {
        'name': 'kimi-maximum-v1', 'requested_profile': requested_profile,
        'requested_budgets': requested['budgets']}
    assert task.to_dict() == requested
    assert {k: v for k, v in sealed['task'].items() if k not in ('budgets', 'profile')} == {
        k: v for k, v in requested.items() if k not in ('budgets', 'profile')}
    verify(sealed)


def test_cli_exposes_effective_route_and_requested_resource_policy(tmp_path, monkeypatch, capsys):
    (tmp_path/'a.py').write_text('VALUE = 1\n')
    data = task_data(tmp_path)
    data['budgets']['generation_tokens'] = 8192
    task_file = tmp_path/'task.json'
    task_file.write_text(json.dumps(data))
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    sandbox = SimpleNamespace(verify=lambda: None, image='pinned', runtime_sha256='pinned')
    monkeypatch.setattr('agent_subagent_router.cli.installed_backend_runtime', lambda _: runtime)
    monkeypatch.setattr('agent_subagent_router.cli.installed_sandbox', lambda *_: sandbox)

    assert main(['--state', str(tmp_path/'state'), 'inspect', '--cwd', str(tmp_path),
                 '--task', str(task_file)]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result['budgets'] == MAXIMUM
    assert result['route']['profile'] == 'deep'
    assert result['resource_policy']['requested_profile'] == 'worker'
    assert result['resource_policy']['requested_budgets']['generation_tokens'] == 8192
    assert 'warnings' not in result


def test_existing_lower_seal_keeps_original_route_and_limits(tmp_path):
    (tmp_path/'a.py').write_text('VALUE = 1\n')
    data = task_data(tmp_path)
    data['budgets'].update(generation_tokens=8192, output_bytes=8388608)
    task = TaskContract.from_dict(data)
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    sealed = resolve(task, tmp_path/'old-seal', {
        'backend': 'kimi', 'profile': 'worker', 'runtime': 'claude-code',
        'runtime_identity': runtime.to_dict(), 'profile_identity': profile('worker').to_dict(),
        'capabilities': ['read']})
    original = json.dumps(sealed, sort_keys=True)
    store = ReceiptStore(tmp_path/'runs')

    blocked = run_contract(sealed, 'kimi', 'worker', store, runtime)
    mismatch = run_contract(sealed, 'kimi', 'deep', store, runtime)

    assert blocked['classification'] == 'BLOCKED_CAPABILITY'
    assert mismatch['classification'] == 'SEALED_ROUTE_MISMATCH'
    assert blocked['wire_requests'] == mismatch['wire_requests'] == 0
    assert json.dumps(sealed, sort_keys=True) == original
    assert sealed['task']['budgets']['generation_tokens'] == 8192
    verify(sealed)


def test_maximum_policy_does_not_repair_unknown_profile(tmp_path):
    data = task_data(tmp_path)
    data['profile'] = 'unknown'
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    with pytest.raises(RouterError, match='UNKNOWN_PROFILE'):
        inspect_task(TaskContract.from_dict(data), tmp_path/'contracts', runtime)


def test_gemini_seal_keeps_parent_budgets_and_profile(tmp_path):
    (tmp_path/'a.py').write_text('VALUE = 1\n')
    data = task_data(tmp_path)
    data.update(backend='gemini', profile='worker')
    data['budgets']['output_bytes'] = 10000
    task = TaskContract.from_dict(data)
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    sealed = inspect_task(task, tmp_path/'contracts', runtime)
    assert sealed['task'] == task.to_dict()
    assert 'resource_policy' not in sealed['transport']


def test_maximum_seal_reaches_native_runtime_without_lower_generation_cap(tmp_path):
    (tmp_path/'a.py').write_text('VALUE = 1\n')
    task = TaskContract.from_dict(task_data(tmp_path))
    runtime = SimpleNamespace(verify=lambda: None, executable='/bin/true',
                              to_dict=lambda: {'version': 'synthetic'})
    sealed = inspect_task(task, tmp_path/'contracts', runtime)
    frozen = TaskContract.from_dict(sealed['task'])

    argv, env = project_command(runtime, profile(frozen.profile), tmp_path/'runtime',
                                'synthetic-capability', frozen.budgets)

    assert argv[argv.index('--model')+1] == 'k3[1m]'
    assert argv[argv.index('--effort')+1] == 'max'
    assert env['CLAUDE_CODE_MAX_OUTPUT_TOKENS'] == '32000'
    assert env['CLAUDE_CODE_MAX_CONTEXT_TOKENS'] == '1048576'
    assert env['API_TIMEOUT_MS'] == '3600000'
    assert env['CLAUDE_CODE_MAX_RETRIES'] == '0'


@pytest.mark.parametrize('field,value', [
    ('wall_seconds', 0), ('wall_seconds', 3601), ('wall_seconds', float('nan')),
    ('idle_seconds', 1801), ('request_limit', 65), ('request_limit', True),
    ('output_bytes', 16777217), ('context_bytes', 8388609), ('generation_tokens', 32001)])
def test_invalid_input_is_rejected_before_maximum_normalization(tmp_path, field, value):
    data = task_data(tmp_path)
    data['budgets'][field] = value
    with pytest.raises(RouterError, match='INVALID_CONTRACT'):
        TaskContract.from_dict(data)


def test_maximum_policy_keeps_finite_source_context_boundary(tmp_path):
    (tmp_path/'a.py').write_bytes(b'A' * 8388609)
    task = TaskContract.from_dict(task_data(tmp_path))
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    with pytest.raises(RouterError, match='CONTRACT_TOO_LARGE'):
        inspect_task(task, tmp_path/'contracts', runtime)
