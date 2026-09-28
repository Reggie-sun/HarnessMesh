import pytest

from agent_subagent_router.api import inspect_task, run_contract
from agent_subagent_router.contracts import RouterError, TaskContract
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.resolver import resolve
from test_output_budget import task_data
from types import SimpleNamespace


@pytest.mark.parametrize('limit', [None, 2048, 8192])
def test_new_kimi_seal_binds_generation_limit(tmp_path, limit):
    (tmp_path/'a.py').write_text('VALUE = 1\n')
    data = task_data(tmp_path)
    if limit is not None:
        data['budgets']['generation_tokens'] = limit
    task = TaskContract.from_dict(data)
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    manifest = inspect_task(task, tmp_path/'contracts', runtime)
    assert manifest['task']['budgets']['generation_tokens'] == 32000
    assert manifest['transport']['resource_policy']['requested_budgets'].get('generation_tokens') == limit


@pytest.mark.parametrize('limit', [None, True, 0, 1023, 32001, 2048.5])
def test_invalid_explicit_generation_limit_is_not_silently_defaulted(tmp_path, limit):
    data = task_data(tmp_path)
    data['budgets']['generation_tokens'] = limit
    with pytest.raises(RouterError, match='INVALID_CONTRACT'):
        TaskContract.from_dict(data)


def test_generation_cap_is_not_silently_ignored_on_gemini(tmp_path):
    data = task_data(tmp_path)
    data['backend'] = 'gemini'
    data['budgets'].update(generation_tokens=4096, output_bytes=8388608)
    with pytest.raises(RouterError, match='INVALID_CONTRACT'):
        TaskContract.from_dict(data)


def test_legacy_seal_is_not_rewritten_or_sent_live(tmp_path):
    from agent_subagent_router.backends.kimi import profile
    root = tmp_path/'source'
    root.mkdir()
    (root/'a.py').write_text('VALUE = 1\n')
    task = TaskContract.from_dict(task_data(root))
    runtime = SimpleNamespace(verify=lambda: None, to_dict=lambda: {'version': 'synthetic'})
    manifest = resolve(task, tmp_path/'legacy', {'backend': 'kimi', 'profile': 'worker',
        'runtime': 'claude-code', 'runtime_identity': runtime.to_dict(),
        'profile_identity': profile('worker').to_dict(), 'capabilities': ['read']})
    old_seal = manifest['seal']
    assert 'generation_tokens' not in manifest['task']['budgets']
    receipt = run_contract(manifest, 'kimi', 'worker', ReceiptStore(tmp_path/'runs'), runtime)
    assert receipt['classification'] == 'GENERATION_BUDGET_REQUIRED'
    assert receipt['wire_requests'] == 0 and receipt['process'] is None
    assert manifest['seal'] == old_seal
