import copy
import hashlib
import http.client
import json
from urllib.parse import urlsplit

import pytest

import agent_subagent_router.transport.codex_broker as codex_broker
from agent_subagent_router.contracts import RouterError, canonical_bytes, strict_json
from agent_subagent_router.transport.codex_broker import CodexBroker, _CodexUpstream
from test_codex_image_wire import _completed, _sse_bytes, _sse_events, request_fixture


API_KEY = "sk-proj-" + "P" * 32


@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('secret_kind', ['credential', 'capability'])
@pytest.mark.parametrize('escaped', [False, True])
def test_response_body_secret_is_quarantined_before_delivery(tmp_path, stream, secret_kind, escaped):
    task, native, _ = request_fixture(tmp_path)
    def upstream(*args):
        secret = API_KEY if secret_kind == 'credential' else broker.capability
        text = json.dumps({'value': secret})
        def wire(raw):
            return raw.replace(secret.encode(), ''.join(f'\\u{ord(c):04x}' for c in secret).encode()) if escaped else raw
        if not stream:
            response = _completed(task)
            response['output'][1]['content'][0]['text'] = text
            return 200, {'content-type': 'application/json', 'x-request-id': 'req_safe'}, wire(canonical_bytes(response))
        events = _sse_events(task)
        for event in events:
            if event['type'].endswith('output_text.delta'):
                event['delta'] = text
            if event['type'].endswith('output_text.done'):
                event['text'] = text
            if 'part' in event and event['type'].endswith('.done'):
                event['part']['text'] = text
            if 'item' in event and event['type'].endswith('.done'):
                event['item']['content'][0]['text'] = text
        events[-1]['response']['output'][1]['content'][0]['text'] = text
        return 200, {'content-type': 'text/event-stream', 'x-request-id': 'req_safe'}, wire(_sse_bytes(events))
    with CodexBroker(task, API_KEY, upstream=upstream) as broker:
        status, payload = _post(broker, native)
    assert status == 502
    assert API_KEY.encode() not in payload and broker.capability.encode() not in payload
    assert broker._active is False
    assert broker.observations[0]['classification'] == 'UPSTREAM_SECRET_REFLECTION'


@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
def test_split_response_parts_are_checked_before_delivery_and_capture(tmp_path, stream, secret_kind):
    task, native, _ = request_fixture(tmp_path)
    captured = []
    def upstream(*args):
        secret = API_KEY if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'safe-value'
        cut = len(secret) // 2
        pieces = ['{"value":"' + secret[:cut], secret[cut:] + '"}']
        response = _completed(task)
        item = response['output'][1]
        item['content'] = [{'type': 'output_text', 'text': text} for text in pieces]
        if not stream:
            raw = canonical_bytes(response)
            headers = {'content-type': 'application/json', 'x-request-id': 'req_safe'}
        else:
            rid = response['id']
            events = [{'type': 'response.created', 'response': dict(response, status='in_progress', output=[])},
                      {'type': 'response.output_item.added', 'response_id': rid, 'output_index': 1,
                       'item': dict(item, status='in_progress', content=[])}]
            for index, part in enumerate(item['content']):
                pos = {'response_id': rid, 'item_id': item['id'], 'output_index': 1, 'content_index': index}
                events += [{'type': 'response.content_part.added', **pos, 'part': dict(part, text='')},
                           {'type': 'response.output_text.delta', **pos, 'delta': part['text']},
                           {'type': 'response.output_text.done', **pos, 'text': part['text']},
                           {'type': 'response.content_part.done', **pos, 'part': part}]
            events += [{'type': 'response.output_item.done', 'response_id': rid, 'output_index': 1, 'item': item},
                       {'type': 'response.completed', 'response': response}]
            raw = _sse_bytes(events)
            headers = {'content-type': 'text/event-stream', 'x-request-id': 'req_safe'}
        assert secret.encode() not in raw
        return 200, headers, raw
    with CodexBroker(task, API_KEY, upstream=upstream,
                     on_exchange=lambda phase, data: captured.append((phase, data))) as broker:
        status, payload = _post(broker, native)
    if secret_kind == 'clean':
        assert status == 200 and captured[-1][0] == 'response'
    else:
        assert status == 502 and broker._active is False
        assert broker.observations[0]['classification'] == 'UPSTREAM_SECRET_REFLECTION'
        assert captured[-1][0] == 'response-quarantined'
        assert set(strict_json(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}
        assert API_KEY.encode() not in payload and broker.capability.encode() not in payload


@pytest.mark.parametrize('ending', ['incomplete', 'error', 'truncated', 'http-error'])
def test_partial_response_secrets_never_enter_artifacts(tmp_path, ending):
    task, native, _ = request_fixture(tmp_path)
    captured = []
    def upstream(*args):
        cut = len(API_KEY)//2
        response = _completed(task)
        response['output'][1]['content'] = [{'type': 'output_text', 'text': piece}
                                           for piece in (API_KEY[:cut], API_KEY[cut:])]
        if ending in ('incomplete', 'http-error'):
            response['status'] = 'incomplete'
            raw = canonical_bytes(response)
            content_type = 'application/json'
        else:
            events = _sse_events(task)[:1]
            events += [{'type': 'response.output_text.delta', 'response_id': response['id'], 'delta': piece}
                       for piece in (API_KEY[:cut], API_KEY[cut:])]
            if ending == 'error':
                events += [{'type': 'error', 'code': 'server_error'}]
            raw = _sse_bytes(events)
            content_type = 'text/event-stream'
        assert API_KEY.encode() not in raw
        return 503 if ending == 'http-error' else 200, {'content-type': content_type, 'x-request-id': 'req_safe'}, raw
    with CodexBroker(task, API_KEY, upstream=upstream,
                     on_exchange=lambda phase, data: captured.append((phase, data))) as broker:
        status, payload = _post(broker, native)
    assert status == 502 and broker._active is False
    assert broker.observations[0]['classification'] == (
        'UPSTREAM_HTTP_ERROR' if ending == 'http-error' else 'UPSTREAM_SECRET_REFLECTION')
    assert captured[-1][0] == 'response-quarantined'
    assert set(strict_json(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}
    assert API_KEY.encode() not in payload


def _post(broker, value, *, path="/v1/responses", capability=None):
    address = urlsplit(broker.url)
    connection = http.client.HTTPConnection(address.hostname, address.port, timeout=3)
    raw = value if isinstance(value, bytes) else canonical_bytes(value)
    connection.request(
        "POST",
        path,
        body=raw,
        headers={
            "Authorization": "Bearer " + (capability or broker.capability),
            "Content-Type": "application/json",
        },
    )
    response = connection.getresponse()
    status, data = response.status, response.read()
    connection.close()
    return status, data


def _response(task):
    return canonical_bytes(_completed(task))


def _task_with_budget(task, **changes):
    value = copy.deepcopy(task)
    value["budgets"].update(changes)
    return value


def test_broker_sends_exact_mapped_body_and_keeps_key_out_of_observations(tmp_path):
    task, native, _ = request_fixture(tmp_path)
    upstream_calls, exchanges, published, before = [], [], [], []

    def upstream(path, headers, body):
        upstream_calls.append((path, headers, body))
        return 200, {"content-type": "application/json", "x-request-id": "req_broker"}, _response(task)

    def before_request():
        before.append(True)

    with CodexBroker(
        task,
        API_KEY,
        upstream=upstream,
        before_request=before_request,
        on_observation=lambda value: published.append(value),
        on_exchange=lambda phase, data: exchanges.append((phase, data)),
    ) as broker:
        raw = canonical_bytes(native)
        status, data = _post(broker, raw)
        capability = broker.capability

    assert status == 200
    assert strict_json(data)["status"] == "completed"
    assert before == [True]
    assert len(upstream_calls) == 1
    path, headers, actual_raw = upstream_calls[0]
    assert path == "/v1/responses"
    assert headers["Authorization"] == "Bearer " + API_KEY
    assert strict_json(actual_raw)["max_output_tokens"] == 2048
    assert [phase for phase, _ in exchanges] == ["native-request", "request", "response"]
    assert exchanges[0][1] == raw
    assert exchanges[1][1] == actual_raw
    assert exchanges[2][1] == _response(task)
    observation_json = json.dumps(broker.observations) + json.dumps(published)
    assert API_KEY not in observation_json
    assert capability not in observation_json
    observation = broker.observations[0]
    assert observation["classification"] == "IDENTITY_VERIFIED"
    assert observation["native_wire_sha256"] == hashlib.sha256(raw).hexdigest()
    assert observation["actual_request_sha256"] == hashlib.sha256(actual_raw).hexdigest()
    assert observation["response_request_id"] == "req_broker"


def test_invalid_native_request_never_reaches_authenticated_upstream(tmp_path):
    task, native, _ = request_fixture(tmp_path)
    native["tools"] = [{"type": "function", "name": "read_file"}]
    calls, exchanges = [], []

    with CodexBroker(
        task,
        API_KEY,
        upstream=lambda *args: calls.append(args),
        on_exchange=lambda phase, data: exchanges.append((phase, data)),
    ) as broker:
        status, _ = _post(broker, native)
        capability = broker.capability

    assert status == 400
    assert calls == []
    assert len(exchanges) == 1 and exchanges[0][0] == 'native-request-quarantined'
    assert set(strict_json(exchanges[0][1])) == {'classification', 'sha256', 'byte_length'}
    assert "IMAGE_ROUTE_MISMATCH" in broker.rejections
    assert capability not in json.dumps(broker.observations)


@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
def test_rejected_native_input_persists_only_metadata(tmp_path, secret_kind):
    from agent_subagent_router.receipts import ReceiptStore
    task, native, _ = request_fixture(tmp_path)
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('engineering-input-capture', 'invalid-input')
    calls, artifacts = [], []
    def capture(phase, data):
        artifacts.append(store.artifact(run, 'wire/'+phase+'.bin', data,
                                       secrets=(API_KEY.encode(), broker.capability.encode()), producer='image-broker'))
    with CodexBroker(task, API_KEY, upstream=lambda *args: calls.append(args), on_exchange=capture) as broker:
        secret = API_KEY if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'ordinary-invalid-input'
        cut = len(secret)//2
        native['instructions'] = secret[:cut]
        native['input'][0]['content'][0]['text'] = secret[cut:]
        status, _ = _post(broker, native)
    assert status == 400 and calls == []
    assert len(artifacts) == 1 and artifacts[0]['path'] == 'wire/native-request-quarantined.bin'
    saved = (run/artifacts[0]['path']).read_bytes()
    assert set(strict_json(saved)) == {'classification', 'sha256', 'byte_length'}
    assert secret[:cut].encode() not in saved and secret[cut:].encode() not in saved


def test_preflight_failure_does_not_capture_native_input(tmp_path):
    task, native, _ = request_fixture(tmp_path)
    calls, captures = [], []
    def deny():
        raise RouterError('IMAGE_ACCOUNT_BUDGET_UNVERIFIED')
    with CodexBroker(task, API_KEY, upstream=lambda *args: calls.append(args), before_request=deny,
                     on_exchange=lambda phase, data: captures.append((phase, data))) as broker:
        status, _ = _post(broker, native)
    assert status == 409 and not calls and not captures


def test_seal_is_reverified_before_upstream_and_failure_revokes_capability(tmp_path):
    task, native, _ = request_fixture(tmp_path)
    calls = []
    checks = []

    def changed_seal():
        checks.append(True)
        raise RouterError("IMAGE_SEAL_CHANGED")

    with CodexBroker(task, API_KEY, upstream=lambda *args: calls.append(args),
                     before_request=changed_seal) as broker:
        status, body = _post(broker, native)

    assert status == 409
    assert strict_json(body)["error"] == "IMAGE_SEAL_CHANGED"
    assert checks == [True]
    assert calls == []
    assert broker.observations[0]["classification"] == "IMAGE_SEAL_CHANGED"


@pytest.mark.parametrize("failure", ["redirect", "wrong-model", "wrong-request-id"])
def test_failed_upstream_response_is_not_delivered_and_revokes_route(tmp_path, failure):
    task, native, _ = request_fixture(tmp_path)
    calls = []

    def upstream(path, headers, body):
        calls.append((path, headers, body))
        if failure == "redirect":
            return 302, {"location": "https://evil.invalid/"}, b"redirect body"
        response = _completed(task)
        if failure == "wrong-model":
            response["model"] = "gpt-5.4-foreign"
        request_id = "" if failure == "wrong-request-id" else "req_upstream"
        return 200, {"content-type": "application/json", "x-request-id": request_id}, canonical_bytes(response)

    with CodexBroker(task, API_KEY, upstream=upstream) as broker:
        status, response = _post(broker, native)
        second_status, _ = _post(broker, native)

    assert status == 502
    assert b"redirect body" not in response
    assert second_status in (403, 429)
    assert len(calls) == 1
    assert broker.observations[0]["classification"] in {
        "UPSTREAM_REDIRECT", "IDENTITY_UNVERIFIED", "CAPABILITY_REVOKED"
    }


def test_late_response_after_revoke_is_observed_but_never_delivered(tmp_path):
    task, native, _ = request_fixture(tmp_path)
    holder, exchanges = {}, []
    response = _response(task)

    def upstream(*_args):
        holder["broker"].revoke()
        return 200, {"content-type": "application/json", "x-request-id": "req_late"}, response

    with CodexBroker(
        task,
        API_KEY,
        upstream=upstream,
        on_exchange=lambda phase, data: exchanges.append((phase, data)),
    ) as broker:
        holder["broker"] = broker
        status, delivered = _post(broker, native)

    assert status == 502
    assert b'"status":"completed"' not in delivered
    assert exchanges[-1] == ("response", response)
    assert broker.observations[0]["classification"] == "CAPABILITY_REVOKED"


def test_native_and_mapped_body_limits_are_enforced_before_upstream(tmp_path):
    task, native, _ = request_fixture(tmp_path)
    native_limit = len(canonical_bytes(native)) - 1
    bounded_task = _task_with_budget(task, payload_bytes=native_limit)
    calls = []

    with CodexBroker(bounded_task, API_KEY, upstream=lambda *args: calls.append(args)) as broker:
        status, _ = _post(broker, native)

    assert status == 413
    assert calls == []
    assert broker.rejections


def test_route_count_is_finite_and_endpoint_is_exact(tmp_path):
    task, native, _ = request_fixture(tmp_path)
    calls = []

    def upstream(path, headers, body):
        calls.append(path)
        return 200, {"content-type": "application/json", "x-request-id": f"req_{len(calls)}"}, _response(task)

    with CodexBroker(task, API_KEY, upstream=upstream) as broker:
        accepted, _ = _post(broker, native)
        wrong_path, _ = _post(broker, native, path="/v1/responses?stream=false")

    assert accepted == 200
    assert wrong_path == 404
    assert calls == ["/v1/responses"]


def test_default_upstream_uses_only_fixed_verified_tls_destination(monkeypatch):
    seen = {}

    class FakeResponse:
        status = 200

        def __init__(self):
            self._chunks = [b'{"body":"ok"}', b""]

        def getheaders(self):
            return [("Content-Type", "application/json"), ("X-Request-Id", "req_tls_fake")]

        def read1(self, _size):
            return self._chunks.pop(0)

    class FakeConnection:
        def __init__(self, host, *, timeout, context):
            seen["host"] = host
            seen["timeout"] = timeout
            seen["verify_mode"] = context.verify_mode
            self.sock = FakeSocket()

        def connect(self):
            seen["connected"] = True

        def request(self, method, path, *, body, headers):
            seen["method"] = method
            seen["path"] = path
            seen["body"] = body
            seen["headers"] = headers

        def getresponse(self):
            return FakeResponse()

        def close(self):
            seen["closed"] = True

    class FakeSocket:
        def settimeout(self, value):
            seen["socket_timeout"] = value

    monkeypatch.setattr(codex_broker.http.client, "HTTPSConnection", FakeConnection)
    upstream = _CodexUpstream(30, 1024)
    status, headers, data = upstream(
        "/v1/responses",
        {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"},
        b"{}",
    )

    assert seen["host"] == "api.openai.com"
    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/responses"
    assert seen["verify_mode"] != 0
    assert "organization" not in json.dumps(seen["headers"]).lower()
    assert status == 200
    assert headers == {"content-type": "application/json", "x-request-id": "req_tls_fake"}
    assert data == b'{"body":"ok"}'
    assert seen["closed"] is True


def test_default_upstream_rejects_alternate_path_before_tls_setup(monkeypatch):
    def forbidden_connection(*_args, **_kwargs):
        pytest.fail("alternate endpoint must be rejected before network setup")

    monkeypatch.setattr(codex_broker.http.client, "HTTPSConnection", forbidden_connection)
    upstream = _CodexUpstream(30, 1024)

    with pytest.raises(RouterError, match="FORBIDDEN_UPSTREAM_PATH"):
        upstream("/v1/responses?redirect=1", {}, b"{}")


def test_default_upstream_rejects_duplicate_response_identity_headers(monkeypatch):
    class FakeResponse:
        status = 200

        def __init__(self):
            self.read = False

        def getheaders(self):
            return [
                ("Content-Type", "application/json"),
                ("X-Request-Id", "req_one"),
                ("X-Request-Id", "req_two"),
            ]

        def read1(self, _size):
            if self.read:
                return b""
            self.read = True
            return b"{}"

    class FakeConnection:
        def __init__(self, *_args, **_kwargs):
            self.sock = self

        def connect(self):
            pass

        def settimeout(self, _value):
            pass

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            return FakeResponse()

        def close(self):
            pass

    monkeypatch.setattr(codex_broker.http.client, "HTTPSConnection", FakeConnection)
    upstream = _CodexUpstream(30, 1024)

    with pytest.raises(RouterError, match="IDENTITY_UNVERIFIED"):
        upstream("/v1/responses", {"Authorization": "Bearer " + API_KEY}, b"{}")


def test_authenticated_endpoint_cannot_start_without_per_request_seal_recheck(tmp_path):
    task, _, _ = request_fixture(tmp_path)

    with pytest.raises(RouterError, match="IMAGE_SEAL_RECHECK_REQUIRED"):
        CodexBroker(task, API_KEY)


def test_broker_rejects_task_cap_above_approved_api_maximum_before_listening(tmp_path):
    task, _, _ = request_fixture(tmp_path)
    task["budgets"]["generation_tokens"] = 2049

    with pytest.raises(RouterError, match="IMAGE_GENERATION_LIMIT"):
        CodexBroker(task, API_KEY, upstream=lambda *_args: None)


def test_default_upstream_refuses_to_connect_after_wall_deadline(monkeypatch):
    import time

    def forbidden_connection(*_args, **_kwargs):
        pytest.fail("expired invocation must stop before TLS setup")

    monkeypatch.setattr(codex_broker.http.client, "HTTPSConnection", forbidden_connection)
    upstream = _CodexUpstream(30, 1024, deadline=time.monotonic() - 1)

    with pytest.raises(RouterError, match="WALL_TIME_LIMIT"):
        upstream("/v1/responses", {}, b"{}")
