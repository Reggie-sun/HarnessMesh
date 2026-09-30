import copy

import pytest

from agent_subagent_router.contracts import RouterError, canonical_bytes, strict_json
from agent_subagent_router.image_budget import require_probe_budget, reserve_probe
from agent_subagent_router.image_contract import ImageTaskContract
from agent_subagent_router.image_process import ImageProcessBudgets
from agent_subagent_router.codex_image_wire import map_codex_image_request, validate_codex_image_response
from agent_subagent_router.minimax_image_wire import map_minimax_image_request, validate_minimax_image_response
from agent_subagent_router.receipts import ReceiptStore
from test_codex_subscription_images import subscription_fixture
from test_codex_image_wire import _completed
from test_minimax_image_wire import _task_and_request, _response


SPEC = 'f96a2fa0ed47e96810c46cda8c221694690badc64689661dbabe4826e0b345eb'


def unrestricted(task):
    task = copy.deepcopy(task)
    task['metadata']['spending_policy'] = 'unrestricted'
    task['selected_refs'].append({'path': '/tmp/unrestricted-spec.md', 'sha256': SPEC, 'accepted': True})
    task['budgets']['generation_tokens'] = None
    if task['backend'] == 'codex':
        task['model'] = 'gpt-6.1-sol'
        task['budgets']['observed_output_tokens_limit'] = None
    return task


def fixture(tmp_path, backend):
    if backend == 'minimax':
        task, _, body = _task_and_request(tmp_path)
        body.pop('max_output_tokens')
    else:
        task, body, _ = subscription_fixture(tmp_path)
        body['model'] = 'gpt-6.1-sol'
    task = unrestricted(task)
    from agent_subagent_router.adapters.image_claude import visible_text
    body['input'][0]['content'][0]['text'] = visible_text(task)
    return task, body


@pytest.mark.parametrize('backend', ['minimax', 'codex'])
def test_new_policy_removes_preflight_and_observed_token_cap(tmp_path, backend):
    task, body = fixture(tmp_path, backend)
    parsed = ImageTaskContract.from_dict(task).to_dict()
    budgets = ImageProcessBudgets.from_task(parsed)
    assert budgets.generation_tokens is None
    assert budgets.observed_output_tokens_limit is None
    mapper = map_minimax_image_request if backend == 'minimax' else map_codex_image_request
    wire, proof = mapper(parsed, body)
    assert 'max_output_tokens' not in strict_json(wire)
    assert proof['generation_tokens'] is None


def test_minimax_does_not_need_balance_accounting_or_budget_receipt(tmp_path):
    task, _ = fixture(tmp_path, 'minimax')
    result = require_probe_budget(ReceiptStore(tmp_path/'runs'), None, task, 'current-fingerprint')
    assert result['spending_policy'] == 'unrestricted'


@pytest.mark.parametrize('backend', ['minimax', 'codex'])
def test_complete_usage_above_old_cap_is_evidence_not_financial_refusal(tmp_path, backend):
    task, _ = fixture(tmp_path, backend)
    response = _response(task) if backend == 'minimax' else _completed(task)
    response.pop('max_output_tokens', None)
    response['usage']['output_tokens'] = 90000
    validate = validate_minimax_image_response if backend == 'minimax' else validate_codex_image_response
    result = validate(task, {'content-type': 'application/json', 'x-request-id': 'request-unmetered'}, canonical_bytes(response))
    assert result['usage']['output_tokens'] == 90000


@pytest.mark.parametrize('backend', ['minimax', 'codex'])
@pytest.mark.parametrize('count', [True, -1, None])
def test_no_token_cap_still_requires_typed_nonnegative_usage(tmp_path, backend, count):
    task, _ = fixture(tmp_path, backend)
    response = _response(task) if backend == 'minimax' else _completed(task)
    response.pop('max_output_tokens', None)
    response['usage']['output_tokens'] = count
    validate = validate_minimax_image_response if backend == 'minimax' else validate_codex_image_response
    with pytest.raises(RouterError):
        validate(task, {'content-type': 'application/json', 'x-request-id': 'request-unmetered'}, canonical_bytes(response))


def test_unrestricted_policy_requires_exact_accepted_ref(tmp_path):
    task, _ = fixture(tmp_path, 'minimax')
    task['selected_refs'].pop()
    with pytest.raises(RouterError, match='IMAGE_SPENDING_ACCEPTANCE_REQUIRED'):
        ImageTaskContract.from_dict(task)


def test_codex_without_image_permission_is_not_called_a_budget_failure(tmp_path):
    task, _ = fixture(tmp_path, 'codex')
    with pytest.raises(RouterError, match='SUBSCRIPTION_MODEL_UNVERIFIED'):
        require_probe_budget(ReceiptStore(tmp_path/'runs'), None, task, 'current-fingerprint')


def test_new_owned_probes_have_no_task_total_cap_but_same_probe_cannot_replay(tmp_path, monkeypatch):
    from agent_subagent_router import image_budget
    monkeypatch.setattr(image_budget, 'probe_reservation_root', lambda: tmp_path/'host-ledger')
    task, _ = fixture(tmp_path, 'minimax')
    store = ReceiptStore(tmp_path/'runs')
    reserve_probe(store, 'minimax', 'attempt-one', task=task, probe_id='owned-probe-one')
    reserve_probe(store, 'minimax', 'attempt-two', task=task, probe_id='owned-probe-two')
    with pytest.raises(RouterError, match='IMAGE_PROBE_ALREADY_SUBMITTED'):
        reserve_probe(store, 'minimax', 'attempt-three', task=task, probe_id='owned-probe-one')


def test_old_minimax_budget_gate_still_applies_to_old_seal(tmp_path):
    task, _, _ = _task_and_request(tmp_path)
    with pytest.raises(RouterError, match='IMAGE_MINIMAX_BUDGET_NOT_AUTHORIZED'):
        require_probe_budget(ReceiptStore(tmp_path/'runs'), None, task, 'fingerprint')


@pytest.mark.parametrize('mutation', ['policy', 'backend', 'cap', 'requests'])
def test_new_policy_is_scoped_and_not_a_general_safety_bypass(tmp_path, mutation):
    task, _ = fixture(tmp_path, 'minimax')
    if mutation == 'policy':
        task['metadata']['spending_policy'] = 'unknown'
    elif mutation == 'backend':
        task.update(backend='codex', profile='api-bounded')
    elif mutation == 'cap':
        task['budgets']['generation_tokens'] = 2048
    else:
        task['budgets']['request_limit'] = 2
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(task)


def model_evidence(store, task, **changes):
    from datetime import datetime, timezone
    facts = {'provider': 'codex-subscription', 'credential_fingerprint': 'current-fingerprint',
        'authenticated': True, 'source': 'https://chatgpt.com/backend-api/wham/usage',
        'catalog_source': 'https://chatgpt.com/backend-api/codex/models?client_version=0.154.0',
        'quota_sha256': 'a'*64, 'catalog_sha256': 'b'*64, 'quota_available': False,
        'model': task['model'], 'image_input_supported': True,
        'observed_at': datetime.now(timezone.utc).isoformat()}
    facts.update(changes)
    run = store.create('router-image', 'subscription-account')
    artifact = store.artifact(run, 'account-evidence.json', canonical_bytes(facts),
        producer='subscription-account-observer')
    return store.finalize(run, {'kind': 'codex-subscription-account/v1',
        'classification': 'INCOMPLETE', 'evidence_kind': 'authenticated-https-account',
        'model': facts['model'], 'credential_fingerprint': facts['credential_fingerprint'],
        'account_queries': 2, 'provider_requests': 0, 'artifacts': [artifact]})


def test_codex_image_permission_does_not_require_available_quota(tmp_path):
    task, _ = fixture(tmp_path, 'codex')
    store = ReceiptStore(tmp_path/'runs')
    evidence = model_evidence(store, task)
    result = require_probe_budget(store, evidence['invocation_id'], task, 'current-fingerprint')
    assert result['spending_policy'] == 'unrestricted'


@pytest.mark.parametrize('changes', [
    {'image_input_supported': False}, {'authenticated': False},
    {'credential_fingerprint': 'other-credential'}, {'model': 'gpt-6-luna'},
    {'catalog_source': 'https://untrusted.invalid/models'}, {'catalog_sha256': 'z'*64},
    {'observed_at': '2999-01-01T00:00:00+00:00'},
])
def test_unrestricted_spending_does_not_forge_model_image_evidence(tmp_path, changes):
    task, _ = fixture(tmp_path, 'codex')
    store = ReceiptStore(tmp_path/'runs')
    evidence = model_evidence(store, task, **changes)
    with pytest.raises(RouterError, match='SUBSCRIPTION_MODEL_UNVERIFIED'):
        require_probe_budget(store, evidence['invocation_id'], task, 'current-fingerprint')


def test_missing_formal_owner_is_an_execution_gap_not_financial_cap(tmp_path):
    from agent_subagent_router.image_run import require_live_admission
    task, _ = fixture(tmp_path, 'minimax')
    with pytest.raises(RouterError, match='IMAGE_FORMAL_EXECUTION_UNAVAILABLE'):
        require_live_admission(ReceiptStore(tmp_path/'runs'), task, None, None, None, 'fingerprint')
