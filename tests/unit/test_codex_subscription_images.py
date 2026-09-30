import copy

import pytest

from agent_subagent_router.contracts import RouterError, canonical_bytes, strict_json
from agent_subagent_router.codex_image_wire import map_codex_image_request, validate_codex_image_response
from agent_subagent_router.image_contract import ImageTaskContract
from agent_subagent_router.image_process import ImageProcessBudgets
from agent_subagent_router.image_budget import reserve_probe, require_probe_budget
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.transport.credentials import CodexSubscriptionCredential
from agent_subagent_router.transport.codex_broker import CodexBroker, _CodexUpstream
from test_codex_image_broker import _post
from test_codex_image_wire import request_fixture, _completed, _sse_events, _sse_bytes


def subscription_fixture(tmp_path):
    task, native, images = request_fixture(tmp_path)
    task.update(profile='subscription-bounded', model='gpt-6-sol')
    task['budgets'].update(generation_tokens=None, observed_output_tokens_limit=2048)
    native['model'] = task['model']
    native.pop('text')
    native['reasoning']['summary'] = 'auto'
    return task, native, images


@pytest.mark.parametrize('model', ['gpt-6.1-sol', 'gpt-6-sol', 'gpt-6-luna'])
def test_subscription_has_no_preflight_cap_and_keeps_native_bytes(tmp_path, model):
    task, native, _ = subscription_fixture(tmp_path)
    task['model'] = native['model'] = model
    parsed = ImageTaskContract.from_dict(task).to_dict()
    budgets = ImageProcessBudgets.from_task(parsed)
    assert budgets.generation_tokens is None
    actual, proof = map_codex_image_request(parsed, native)
    assert actual == canonical_bytes(native)
    assert 'max_output_tokens' not in strict_json(actual)
    assert proof['version'] == 'codex-image-subscription/v1'
    assert proof['generation_tokens'] is None
    assert proof['observed_output_tokens_limit'] == 2048
    assert proof['native_text_verbosity'] is None
    assert proof['native_reasoning_summary'] == 'auto'


@pytest.mark.parametrize('backend,profile', [('codex', 'api-bounded'), ('kimi', 'worker'), ('minimax', 'responses-bounded')])
def test_null_generation_is_exclusive_to_subscription(tmp_path, backend, profile):
    task, _, _ = subscription_fixture(tmp_path)
    task.update(backend=backend, profile=profile)
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(task)


@pytest.mark.parametrize('value', [None, True, 0, 2049])
def test_subscription_observed_limit_is_fixed(tmp_path, value):
    task, _, _ = subscription_fixture(tmp_path)
    task['budgets']['observed_output_tokens_limit'] = value
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(task)


def test_subscription_rejects_native_cap_injection(tmp_path):
    task, native, _ = subscription_fixture(tmp_path)
    native['max_output_tokens'] = 2048
    with pytest.raises(RouterError, match='IMAGE_GENERATION_MISMATCH'):
        map_codex_image_request(task, native)


@pytest.mark.parametrize('stream', [False, True])
def test_subscription_complete_response_records_null_hard_cap(tmp_path, stream):
    task, _, _ = subscription_fixture(tmp_path)
    if stream:
        events = _sse_events(task)
        for event in events:
            if 'response' in event:
                event['response'].pop('max_output_tokens', None)
        data, content = _sse_bytes(events), 'text/event-stream'
    else:
        response = _completed(task)
        response.pop('max_output_tokens', None)
        data, content = canonical_bytes(response), 'application/json'
    result = validate_codex_image_response(task, {'content-type': content, 'x-request-id': 'req_subscription'}, data)
    assert result['max_output_tokens'] is None
    assert result['observed_output_tokens_limit'] == 2048


@pytest.mark.parametrize('count', [True, -1, 2049, None])
def test_subscription_usage_must_be_observed_and_bounded(tmp_path, count):
    task, _, _ = subscription_fixture(tmp_path)
    response = _completed(task)
    response.pop('max_output_tokens', None)
    response['usage']['output_tokens'] = count
    with pytest.raises(RouterError):
        validate_codex_image_response(task, {'content-type': 'application/json', 'x-request-id': 'req_sub'}, canonical_bytes(response))


def test_api_still_requires_real_cap(tmp_path):
    task, native, _ = request_fixture(tmp_path)
    actual, proof = map_codex_image_request(task, native)
    assert strict_json(actual)['max_output_tokens'] == 2048
    assert proof['version'] == 'codex-image-api-cap/v1'
    response = copy.deepcopy(_completed(task))
    response.pop('max_output_tokens')
    with pytest.raises(RouterError):
        validate_codex_image_response(task, {'content-type': 'application/json', 'x-request-id': 'req_api'}, canonical_bytes(response))


def test_subscription_missing_account_budget_is_zero_admission(tmp_path):
    task, _, _ = subscription_fixture(tmp_path)
    with pytest.raises(RouterError, match='IMAGE_ACCOUNT_BUDGET_UNVERIFIED'):
        require_probe_budget(ReceiptStore(tmp_path/'runs'), None, task, 'fingerprint')


def test_subscription_once_ledger_is_independent_but_not_reset_by_state(tmp_path, monkeypatch):
    from agent_subagent_router import image_budget
    monkeypatch.setattr(image_budget, 'probe_reservation_root', lambda: tmp_path/'ledger')
    one, two = ReceiptStore(tmp_path/'one'), ReceiptStore(tmp_path/'two')
    reserve_probe(one, 'codex', 'api-historical')
    reserve_probe(one, 'codex', 'subscription-first', profile='subscription-bounded')
    with pytest.raises(RouterError, match='IMAGE_PROBE_BUDGET_CONSUMED'):
        reserve_probe(two, 'codex', 'subscription-new-context', profile='subscription-bounded')


def test_subscription_broker_uses_host_oauth_account_and_original_body(tmp_path):
    task, native, _ = subscription_fixture(tmp_path)
    credential = CodexSubscriptionCredential('oauth-test-only', 'account-test-only',
        ('oauth-test-only', 'account-test-only', 'refresh-test-only'))
    seen = []
    def upstream(path, headers, raw):
        seen.append((path, headers, raw))
        response = _completed(task)
        response.pop('max_output_tokens')
        return 200, {'content-type': 'application/json', 'x-request-id': 'req_subscription'}, canonical_bytes(response)
    with CodexBroker(task, credential, upstream=upstream) as broker:
        status, _ = _post(broker, native)
    assert status == 200
    path, headers, raw = seen[0]
    assert path == '/backend-api/codex/responses'
    assert headers['Authorization'] == 'Bearer oauth-test-only'
    assert headers['ChatGPT-Account-ID'] == 'account-test-only'
    assert raw == canonical_bytes(native)
    assert broker.observations[0]['generation_tokens'] is None
    transport = _CodexUpstream(5, 65536, profile='subscription-bounded')
    assert transport.host == 'chatgpt.com' and transport.path == path


@pytest.mark.parametrize('secret', ['account-test-only', 'refresh-test-only'])
def test_subscription_all_projected_auth_secrets_are_quarantined(tmp_path, secret):
    task, native, _ = subscription_fixture(tmp_path)
    credential = CodexSubscriptionCredential('oauth-test-only', 'account-test-only',
        ('oauth-test-only', 'account-test-only', 'refresh-test-only'))
    capture = []
    def upstream(*args):
        response = _completed(task)
        response.pop('max_output_tokens')
        response['output'][1]['content'][0]['text'] = '{"value":"' + secret + '"}'
        return 200, {'content-type': 'application/json', 'x-request-id': 'req_subscription'}, canonical_bytes(response)
    with CodexBroker(task, credential, upstream=upstream,
            on_exchange=lambda phase, raw: capture.append((phase, raw))) as broker:
        status, raw = _post(broker, native)
    assert status == 502 and secret.encode() not in raw
    assert capture[-1][0] == 'response-quarantined'
    assert broker.observations[0]['classification'] == 'UPSTREAM_SECRET_REFLECTION'
    assert all(secret.encode() not in item for _, item in capture)


def test_subscription_api_credential_cannot_cross_profiles(tmp_path):
    task, _, _ = subscription_fixture(tmp_path)
    with pytest.raises(RouterError, match='UNSAFE_CREDENTIAL'):
        CodexBroker(task, 'sk-project-api-key-only', upstream=lambda *a: None)
