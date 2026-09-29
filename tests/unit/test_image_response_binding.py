import pytest

from test_codex_image_broker import API_KEY, _post
from test_codex_image_wire import request_fixture, _sse_events, _sse_bytes
from agent_subagent_router.transport.codex_broker import CodexBroker
from agent_subagent_router.contracts import strict_json


@pytest.mark.parametrize('initial', ['added-summary', 'created-output', 'progress-output'])
@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
def test_initial_reasoning_state_cannot_bypass_terminal_binding(tmp_path, initial, secret_kind):
    from agent_subagent_router.receipts import ReceiptStore
    task, native, _ = request_fixture(tmp_path)
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('engineering-initial-state', 'codex-reasoning')
    artifacts, captured = [], []
    def upstream(*args):
        secret = API_KEY if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'normal-reasoning'
        cut = len(secret)//2
        events = _sse_events(task)
        item = {'id': 'rs_1', 'type': 'reasoning', 'summary': [{'type': 'summary_text', 'text': secret[cut:]}]}
        starting = dict(item, summary=[{'type': 'summary_text', 'text': secret[:cut]}])
        position = {'response_id': events[0]['response']['id'], 'item_id': item['id'], 'output_index': 0, 'summary_index': 0}
        events[-1]['response']['output'][0] = item
        if initial == 'created-output':
            events[0]['response']['output'] = [starting]
        elif initial == 'progress-output':
            events.insert(1, {'type': 'response.in_progress', 'response': dict(events[0]['response'], output=[starting])})
        at = 2 if initial == 'progress-output' else 1
        events[at:at] = [
            {'type': 'response.output_item.added', 'response_id': position['response_id'], 'output_index': 0,
             'item': starting if initial == 'added-summary' else dict(item, summary=[])},
            {'type': 'response.reasoning_summary_text.delta', **position, 'delta': secret[cut:]},
            {'type': 'response.reasoning_summary_text.done', **position, 'text': secret[cut:]},
            {'type': 'response.output_item.done', 'response_id': position['response_id'], 'output_index': 0, 'item': item}]
        raw = _sse_bytes(events)
        assert secret.encode() not in raw
        return 200, {'content-type': 'text/event-stream', 'x-request-id': 'req_safe'}, raw
    def exchange(phase, data):
        captured.append((phase, data))
        artifacts.append(store.artifact(run, 'wire/'+phase+'.bin', data,
            secrets=(API_KEY.encode(), broker.capability.encode()), producer='image-broker'))
    with CodexBroker(task, API_KEY, upstream=upstream, on_exchange=exchange) as broker:
        status, _ = _post(broker, native)
    assert status == 502 and broker._active is False
    assert broker.observations[0]['classification'] == 'UPSTREAM_PROTOCOL_ERROR'
    assert captured[-1][0] == 'response-quarantined'
    assert set(strict_json(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}
    if secret_kind != 'clean':
        secret = API_KEY if secret_kind == 'credential' else broker.capability
        cut = len(secret)//2
        for artifact in artifacts:
            saved = (run/artifact['path']).read_bytes()
            assert secret[:cut].encode() not in saved and secret[cut:].encode() not in saved


@pytest.mark.parametrize('case', ['unbound-summary', 'wrong-item'])
def test_reasoning_stream_requires_terminal_summary_binding(tmp_path, case):
    from agent_subagent_router.codex_image_wire import validate_codex_image_response
    from agent_subagent_router.contracts import RouterError
    task, _, _ = request_fixture(tmp_path)
    events = _sse_events(task)
    events.insert(3, {'type': 'response.reasoning_summary_text.delta',
        'response_id': events[0]['response']['id'], 'item_id': 'rs_1' if case == 'unbound-summary' else 'msg_answer',
        'output_index': 0, 'summary_index': 0, 'delta': 'safe reasoning'})
    with pytest.raises(RouterError):
        validate_codex_image_response(task, {'content-type': 'text/event-stream', 'x-request-id': 'req_safe'}, _sse_bytes(events))


@pytest.mark.parametrize('secret_kind', ['credential', 'capability'])
def test_http_failure_retains_only_metadata(tmp_path, secret_kind):
    from agent_subagent_router.transport.broker import Broker
    from agent_subagent_router.backends.kimi import profile
    from agent_subagent_router.contracts import canonical_bytes
    key = 'http-error-key-sentinel'
    captured = []
    def upstream(*args):
        secret = key if secret_kind == 'credential' else broker.capability
        return 503, {}, canonical_bytes({'error': {'code': secret[:9], 'message': 'X', 'type': secret[9:]}})
    with Broker(profile('worker'), key, request_limit=1, wall_seconds=5, upstream=upstream,
                on_exchange=lambda phase, data: captured.append((phase, data))) as broker:
        payload = {'model': 'k3-256k', 'thinking': {'type': 'enabled', 'budget_tokens': 8192},
                   'output_config': {'effort': 'high'}, 'messages': [{'role': 'user', 'content': 'OK'}],
                   'max_tokens': 100, 'tools': []}
        status, _ = _post(broker, payload, path='/v1/messages')
    assert status == 502
    assert 'upstream_error' not in broker.observations[0]
    assert captured[-1][0] == 'response-quarantined'
    assert set(strict_json(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}


@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
def test_interleaved_reasoning_secrets_are_quarantined(tmp_path, secret_kind):
    task, native, _ = request_fixture(tmp_path)
    captured = []
    def upstream(*args):
        secret = API_KEY if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'safe-reason'
        cut = len(secret)//2
        events = _sse_events(task)
        position = {'response_id': events[0]['response']['id'], 'item_id': 'rs_1', 'output_index': 0, 'summary_index': 0}
        events.insert(3, {'type': 'response.reasoning_summary_text.delta', **position, 'delta': secret[:cut]})
        events.insert(5, {'type': 'response.reasoning_summary_text.delta', **position, 'delta': secret[cut:]})
        if secret_kind == 'clean':
            item = {'id': 'rs_1', 'type': 'reasoning', 'summary': [{'type': 'summary_text', 'text': secret}]}
            events[-1]['response']['output'][0] = item
            events.insert(1, {'type': 'response.output_item.added', 'response_id': position['response_id'],
                             'output_index': 0, 'item': dict(item, summary=[])})
            events.insert(-1, {'type': 'response.reasoning_summary_text.done', **position, 'text': secret})
            events.insert(-1, {'type': 'response.output_item.done', 'response_id': position['response_id'],
                             'output_index': 0, 'item': item})
        raw = _sse_bytes(events)
        if secret_kind != 'clean':
            assert secret.encode() not in raw
        return 200, {'content-type': 'text/event-stream', 'x-request-id': 'req_safe'}, raw
    with CodexBroker(task, API_KEY, upstream=upstream, on_exchange=lambda phase, data: captured.append((phase, data))) as broker:
        status, _ = _post(broker, native)
    if secret_kind == 'clean':
        assert status == 200 and captured[-1][0] == 'response', broker.observations[0]['classification']
    else:
        assert status == 502 and broker._active is False
        assert broker.observations[0]['classification'] == 'UPSTREAM_SECRET_REFLECTION'
        assert captured[-1][0] == 'response-quarantined'
        assert set(strict_json(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}


@pytest.mark.parametrize('matching', [True, False])
def test_kimi_native_output_is_bound_to_authenticated_text(tmp_path, monkeypatch, matching):
    from types import SimpleNamespace
    from agent_subagent_router import image_run
    from agent_subagent_router.contracts import canonical_bytes, hash_bytes
    from agent_subagent_router.receipts import ReceiptStore
    from agent_subagent_router.transport import broker
    task, _, _ = request_fixture(tmp_path)
    task.update(backend='kimi', model='k3', profile='worker')
    text = '{"frames":[]}'
    data = [dict(type='system', subtype='init', session_id='session-1', skills=[], tools=[], mcp_servers=[], plugins=[]),
            dict(type='result', subtype='success', is_error=False, result=text)]
    class FakeBroker:
        capability = 'synthetic-capability'
        rejections = []
        observations = [{'classification': 'IDENTITY_VERIFIED', 'wire_started': True,
            'input_proof': {'session_id': 'session-1'},
            'response_output_sha256': hash_bytes(text.encode() if matching else b'{"frames":[1]}')}]
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def revoke(self): pass
        def last_activity(self): return 0
    class FakeSandbox:
        def execute(self, *a, **k):
            return SimpleNamespace(stdout=b''.join(canonical_bytes(x)+b'\n' for x in data), stderr=b'', reason='exited',
                                   exit_code=0, truncated=False, duration_seconds=0)
    sealed = {'task': task, 'pins': {}, 'images': [{'blob_path': x['path']} for x in task['images']]}
    manifest = tmp_path/'manifest.json'
    manifest.write_bytes(canonical_bytes(sealed))
    monkeypatch.setattr(image_run, 'verify_image_seal', lambda _: sealed)
    monkeypatch.setattr(image_run, 'image_runtime', lambda *a: (FakeSandbox(), {}))
    monkeypatch.setattr(image_run, '_invocation', lambda *a: ((), {}, b''))
    monkeypatch.setattr(broker, 'Broker', FakeBroker)
    receipt = image_run.run_image_contract(manifest, ReceiptStore(tmp_path/'runs'), sandbox_config=tmp_path/'config', upstream=lambda *a: None)
    assert receipt['classification'] == ('ENGINEERING_NATIVE_COMPLETE' if matching else 'IMAGE_NATIVE_ASSOCIATION_MISMATCH')
    if not matching:
        assert all(x['path'] not in ('model-raw.json', 'model-canonical.json') for x in receipt['artifacts'])
