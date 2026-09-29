from concurrent.futures import ThreadPoolExecutor
import json
import threading
import urllib.error
import urllib.request

import pytest

from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import RouterError
from agent_subagent_router.transport.broker import Broker
from agent_subagent_router.transport.identity import validate_request, validate_response


def body(model='k3-256k', effort='high'):
    return {'model': model, 'thinking': {'type': 'enabled', 'budget_tokens': 8192},
            'output_config': {'effort': effort}, 'messages': [{'role': 'user', 'content': 'OK'}],
            'max_tokens': 100, 'tools': []}


def response(model='k3-256k'):
    return json.dumps({'id': 'msg_fake', 'type': 'message', 'model': model,
                       'content': [{'type': 'text', 'text': 'OK'}],
                       'usage': {'input_tokens': 1, 'output_tokens': 1}}).encode()


@pytest.mark.parametrize('change', [{'model': 'claude-opus-4-6'}, {'model': 'MiniMax-M3'},
                                 {'model': 'kimi-for-coding'}, {'thinking': {'type': 'disabled'}},
                                 {'output_config': {'effort': 'low'}},
                                 {'tools': [{'name': 'Task'}]}])
def test_request_route_must_match_every_field(change):
    with pytest.raises(RouterError):
        validate_request(profile('worker'), body() | change, allowed_tools=[])


@pytest.mark.parametrize('model', ['claude-opus-4-6', 'MiniMax-M3', 'kimi-for-coding', 'k3[1m]'])
def test_response_identity_is_upstream_not_cli(model):
    with pytest.raises(RouterError, match='ROUTE_MISMATCH'):
        validate_response(profile('worker'), {}, response(model))


def test_missing_model_or_request_id_is_unverified():
    with pytest.raises(RouterError, match='IDENTITY_UNVERIFIED'):
        validate_response(profile('worker'), {}, b'{"type":"message","content":[]}')


def post(broker, payload=None, path='/v1/messages', token=None):
    request = urllib.request.Request(broker.url+path, data=json.dumps(payload or body()).encode(),
                                     headers={'Authorization': 'Bearer '+(token or broker.capability),
                                              'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=3) as stream:
            return stream.status, stream.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def test_broker_injects_parent_secret_and_remaining_provider_timeout():
    calls = []

    def upstream(path, headers, payload):
        calls.append((path, headers, payload))
        return 200, {}, response('MiniMax-M3')

    with Broker(profile('worker'), 'SECRET-SENTINEL', request_limit=1, wall_seconds=1200,
                upstream=upstream) as broker:
        status, data = post(broker)
        assert status == 502 and b'ROUTE_MISMATCH' in data
        assert calls[0][1]['x-api-key'] == 'SECRET-SENTINEL'
        assert 1199 <= int(calls[0][1]['x-stainless-timeout']) <= 1200
        assert set(calls[0][1]) == {'x-api-key', 'content-type', 'anthropic-version', 'accept',
                                    'x-stainless-timeout'}
        assert broker.capability not in str(calls)
        assert 'SECRET-SENTINEL' not in json.dumps(broker.observations)


@pytest.mark.parametrize('identity_field', ['request-id', 'message-id'])
def test_upstream_secret_reflection_cannot_enter_final_receipt(tmp_path, identity_field):
    from agent_subagent_router.receipts import ReceiptStore
    secret = 'PROVIDER-SECRET-SENTINEL'
    saved = []
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('parent', 'reflection')
    artifacts = []
    def exchange(phase, data):
        artifacts.append(store.artifact(run, 'wire/'+phase+'.bin', data,
                         secrets=(secret.encode(), broker.capability.encode())))
    def upstream(path, headers, payload):
        value = json.loads(response())
        identity = 'msg_' + headers['x-api-key']
        response_headers = {'request-id': identity if identity_field == 'request-id' else 'req_safe'}
        value['id'] = identity if identity_field == 'message-id' else 'msg_safe'
        return 200, response_headers, json.dumps(value).encode()
    with Broker(profile('worker'), secret, request_limit=1, wall_seconds=5,
                upstream=upstream, on_observation=saved.append, on_exchange=exchange) as broker:
        status, payload = post(broker)
    receipt = store.finalize(run, {'upstream': broker.observations, 'artifacts': artifacts})
    assert secret not in json.dumps(receipt) + json.dumps(saved) + payload.decode()
    assert secret.encode() not in (run/'invocation-receipt.json').read_bytes()
    assert status == 502
    assert broker.observations[0]['classification'] == 'UPSTREAM_SECRET_REFLECTION'
    assert all(secret.encode() not in (run/a['path']).read_bytes() for a in artifacts)
    assert broker._active is False


@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('secret_kind', ['credential', 'capability'])
@pytest.mark.parametrize('escaped', [False, True])
def test_response_body_secret_is_quarantined_before_delivery(stream, secret_kind, escaped):
    key = 'body-key-sentinel'
    def upstream(*args):
        secret = key if secret_kind == 'credential' else broker.capability
        message = json.loads(response())
        message['id'] = 'msg_safe'
        message['content'][0]['text'] = json.dumps({'value': secret})
        def wire(value):
            raw = json.dumps(value).encode()
            return raw.replace(secret.encode(), ''.join(f'\\u{ord(c):04x}' for c in secret).encode()) if escaped else raw
        if not stream:
            return 200, {}, wire(message)
        events = [{'type': 'message_start', 'message': dict(message, content=[])},
                  {'type': 'content_block_start', 'index': 0, 'content_block': message['content'][0]},
                  {'type': 'content_block_stop', 'index': 0},
                  {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 1}},
                  {'type': 'message_stop'}]
        return 200, {'content-type': 'text/event-stream'}, b''.join(
            b'data: '+wire(x)+b'\n\n' for x in events)
    with Broker(profile('worker'), key, request_limit=1, wall_seconds=5, upstream=upstream) as broker:
        status, payload = post(broker)
    assert status == 502
    assert key.encode() not in payload and broker.capability.encode() not in payload
    assert broker._active is False
    assert broker.observations[0]['classification'] == 'UPSTREAM_SECRET_REFLECTION'


@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
def test_split_response_text_is_checked_before_delivery_and_capture(stream, secret_kind):
    key = 'split-key-sentinel'
    captured = []
    def upstream(*args):
        secret = key if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'safe-value'
        cut = len(secret) // 2
        pieces = ['{"value":"' + secret[:cut], secret[cut:] + '"}']
        message = json.loads(response())
        message['content'] = [{'type': 'text', 'text': text} for text in pieces]
        if not stream:
            raw = json.dumps(message).encode()
            headers = {}
        else:
            events = [{'type': 'message_start', 'message': dict(message, content=[])},
                      {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}},
                      *[{'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': text}}
                        for text in pieces],
                      {'type': 'content_block_stop', 'index': 0},
                      {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 1}},
                      {'type': 'message_stop'}]
            raw = b''.join(b'data: '+json.dumps(x).encode()+b'\n\n' for x in events)
            headers = {'content-type': 'text/event-stream'}
        assert secret.encode() not in raw
        return 200, headers, raw
    with Broker(profile('worker'), key, request_limit=1, wall_seconds=5, upstream=upstream,
                on_exchange=lambda phase, data: captured.append((phase, data))) as broker:
        status, payload = post(broker)
    if secret_kind == 'clean':
        assert status == 200 and captured[-1][0] == 'response'
    else:
        assert status == 502 and broker._active is False
        assert broker.observations[0]['classification'] == 'UPSTREAM_SECRET_REFLECTION'
        assert captured[-1][0] == 'response-quarantined'
        assert set(json.loads(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}
        assert key.encode() not in payload and broker.capability.encode() not in payload


@pytest.mark.parametrize('ending', ['complete', 'error', 'truncated', 'http-error'])
@pytest.mark.parametrize('field', ['text', 'thinking'])
def test_partial_and_thinking_secrets_never_enter_response_artifacts(ending, field):
    key = 'partial-key-sentinel'
    captured = []
    def upstream(*args):
        pieces = [key[:len(key)//2], key[len(key)//2:]]
        message = json.loads(response())
        events = [{'type': 'message_start', 'message': dict(message, content=[])},
                  {'type': 'content_block_start', 'index': 0, 'content_block': {'type': field, field: ''}},
                  *[{'type': 'content_block_delta', 'index': 0,
                     'delta': {'type': field+'_delta', field: piece}} for piece in pieces],
                  {'type': 'content_block_stop', 'index': 0}]
        if ending == 'complete':
            events += [{'type': 'content_block_start', 'index': 1, 'content_block': {'type': 'text', 'text': '{}'}},
                       {'type': 'content_block_stop', 'index': 1},
                       {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 1}},
                       {'type': 'message_stop'}]
        elif ending == 'error':
            events += [{'type': 'error', 'error': {'type': 'api_error'}}]
        raw = b''.join(b'data: '+json.dumps(event).encode()+b'\n\n' for event in events)
        assert key.encode() not in raw
        return 503 if ending == 'http-error' else 200, {'content-type': 'text/event-stream'}, raw
    with Broker(profile('worker'), key, request_limit=1, wall_seconds=5, upstream=upstream,
                on_exchange=lambda phase, data: captured.append((phase, data))) as broker:
        status, payload = post(broker)
    assert status == 502 and broker._active is False
    assert broker.observations[0]['classification'] == (
        'UPSTREAM_HTTP_ERROR' if ending == 'http-error' else 'UPSTREAM_SECRET_REFLECTION')
    assert captured[-1][0] == 'response-quarantined'
    assert set(json.loads(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}
    assert key.encode() not in payload


@pytest.mark.parametrize('stop', ['revoke', 'deadline'])
def test_stop_between_validation_and_reply_cannot_deliver_success(monkeypatch, stop):
    import time
    entered, release = threading.Event(), threading.Event()
    with Broker(profile('worker'), 'sentinel', request_limit=1, wall_seconds=5,
                upstream=lambda *a: (200, {}, response())) as broker:
        handler = broker._server.RequestHandlerClass
        original = handler.reply
        def paused(self, status, data, content_type='application/json'):
            if status == 200:
                entered.set()
                assert release.wait(2)
            return original(self, status, data, content_type)
        monkeypatch.setattr(handler, 'reply', paused)
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(post, broker)
            assert entered.wait(1)
            if stop == 'revoke':
                broker.revoke()
            else:
                broker._deadline = time.monotonic() - 1
            release.set()
            status, payload = future.result(timeout=3)
    assert status == 502
    assert b'"text": "OK"' not in payload
    assert broker.observations[0]['classification'] == 'OUTCOME_UNKNOWN'


def test_atomic_budget_and_revocation_prevent_extra_requests():
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def upstream(*args):
        calls.append(1)
        entered.set()
        release.wait(2)
        return 200, {}, response()

    with Broker(profile('worker'), 'sentinel', request_limit=1, wall_seconds=5,
                upstream=upstream) as broker:
        with ThreadPoolExecutor(3) as pool:
            first = pool.submit(post, broker)
            assert entered.wait(1)
            assert post(broker)[0] == 429
            broker.revoke()
            release.set()
            first.result()
        assert post(broker)[0] == 403
        assert len(calls) == 1


@pytest.mark.parametrize('path', ['/proxy?url=https://evil.test', '//evil.test/v1/messages',
                                '/v1/messages/../admin', '/v1/messages?url=evil'])
def test_broker_is_not_an_arbitrary_proxy(path):
    calls = []
    with Broker(profile('worker'), 'sentinel', request_limit=1, wall_seconds=2,
                upstream=lambda *args: calls.append(args)) as broker:
        assert post(broker, path=path)[0] in (400, 404)
        assert not calls


def test_foreign_redirect_is_rejected():
    with Broker(profile('worker'), 'sentinel', request_limit=1, wall_seconds=2,
                upstream=lambda *args: (302, {'location': 'https://evil.test'}, b'')) as broker:
        assert post(broker)[0] == 502
        assert broker.observations[0]['classification'] == 'UPSTREAM_REDIRECT'


def test_cancel_during_durable_admission_does_not_dispatch():
    calls = []
    with Broker(profile('worker'), 'sentinel', request_limit=1, wall_seconds=2,
                upstream=lambda *args: calls.append(args),
                on_observation=lambda _: broker.revoke()) as broker:
        assert post(broker)[0] == 502
        assert not calls


def test_secret_cannot_enter_durable_observation_through_thinking():
    saved = []
    with Broker(profile('worker'), 'PROVIDER-SECRET', request_limit=1, wall_seconds=2,
                upstream=lambda *args: (200, {}, response()), on_observation=saved.append) as broker:
        value = body()
        value['thinking']['extra'] = broker.capability
        post(broker, value)
        assert broker.capability not in json.dumps(saved)


def test_sse_final_usage_is_provider_reported_final_usage():
    events = [{'type': 'message_start', 'message': {'id': 'msg_fake', 'model': 'k3-256k',
               'usage': {'input_tokens': 3, 'output_tokens': 0}}},
              {'type': 'message_delta', 'usage': {'output_tokens': 987}},
              {'type': 'message_stop'}]
    raw = ''.join(f'data: {json.dumps(event)}\n\n' for event in events).encode()
    observed = validate_response(profile('worker'), {'content-type': 'text/event-stream'}, raw)
    assert observed['usage']['output_tokens'] == 987


def test_late_handler_cannot_mutate_frozen_receipt_observations():
    entered, release = threading.Event(), threading.Event()
    saved = []

    def upstream(*args):
        entered.set()
        release.wait(2)
        return 200, {}, response()

    with ThreadPoolExecutor(1) as pool:
        with Broker(profile('worker'), 'sentinel', request_limit=1, wall_seconds=3,
                    upstream=upstream, on_observation=saved.append) as broker:
            future = pool.submit(post, broker)
            assert entered.wait(1)
        frozen = broker.observations
        callbacks = len(saved)
        assert frozen[0]['classification'] == 'OUTCOME_UNKNOWN'
        release.set()
        future.result()
        assert broker.observations == frozen and len(saved) == callbacks
