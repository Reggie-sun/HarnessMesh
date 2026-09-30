import copy
import http.client
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from agent_subagent_router.contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from agent_subagent_router.image_run import _invocation
from agent_subagent_router.image_output import decode_image_minimax
from agent_subagent_router.transport.codex_broker import CodexBroker, _CodexUpstream
from test_image_contract import make_png, task_dict


KEY = 'private-minimax-test-key-0123456789'


def fixture(tmp_path):
    task = task_dict()
    task.update(backend='minimax', profile='responses-bounded', model='MiniMax-M3', effort='provider-default')
    task['selected_refs'] = [{'path': '/tmp/accepted.md', 'sha256': 'a'*64, 'accepted': True}]
    _, env, payload = _invocation(task, [make_png()], 'opaque', tmp_path)
    assert 'CODEX_HOME' not in env and KEY not in str(env)
    return task, strict_json(payload)


def response(task, text='{"ok":true}'):
    return {'id': 'mini_response_1', 'object': 'response', 'model': task['model'], 'status': 'completed',
        'store': False, 'output': [{'id': 'mini_message_1', 'type': 'message', 'role': 'assistant',
            'status': 'completed', 'content': [{'type': 'output_text', 'text': text}]}],
        'usage': {'input_tokens': 10, 'output_tokens': 10, 'total_tokens': 20}}


def post(broker, body):
    parsed = urlsplit(broker.url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        connection.request('POST', '/v1/responses', canonical_bytes(body),
            {'Authorization': 'Bearer '+broker.capability, 'Content-Type': 'application/json'})
        result = connection.getresponse()
        return result.status, result.read()
    finally:
        connection.close()


def test_minimax_exact_request_and_receipt_identity_are_separate_from_codex(tmp_path):
    task, body = fixture(tmp_path)
    captured = []
    def upstream(path, headers, raw):
        captured.append((path, raw))
        return 200, {'content-type': 'application/json', 'x-request-id': 'req_minimax'}, canonical_bytes(response(task))
    with CodexBroker(task, KEY, upstream=upstream) as broker:
        status, raw = post(broker, body)
    assert status == 200 and strict_json(raw)['model'] == 'MiniMax-M3'
    assert captured == [('/v1/responses', canonical_bytes(body))]
    observation = broker.observations[0]
    assert observation['upstream_host'] == 'api.minimaxi.com'
    assert observation['generation_tokens'] == 2048
    assert observation['response_max_output_tokens'] is None
    assert 'thread_id' not in observation['wire_proof']
    assert observation['classification'] == 'IDENTITY_VERIFIED'


@pytest.mark.parametrize('field,value', [('max_output_tokens', 2049), ('tools', [{'type': 'function'}]),
    ('store', True), ('input', []), ('model', 'gpt-5.4')])
def test_minimax_projection_tampering_is_zero_wire(tmp_path, field, value):
    task, body = fixture(tmp_path)
    body[field] = value
    calls = []
    with CodexBroker(task, KEY, upstream=lambda *a: calls.append(a)) as broker:
        status, _ = post(broker, body)
    assert status == 400 and calls == []


@pytest.mark.parametrize('secret_kind', ['credential', 'capability'])
def test_minimax_split_escaped_secret_is_quarantined_before_capture(tmp_path, secret_kind):
    task, body = fixture(tmp_path)
    captures = []
    def upstream(*args):
        secret = KEY if secret_kind == 'credential' else broker.capability
        cut = len(secret)//2
        value = response(task)
        value['output'][0]['content'] = [{'type': 'output_text', 'text': secret[:cut]}, {'type': 'output_text', 'text': secret[cut:]}]
        raw = canonical_bytes(value)
        for piece in (secret[:cut], secret[cut:]):
            raw = raw.replace(piece.encode(), ''.join('\\u%04x'%ord(c) for c in piece).encode())
        return 200, {'content-type': 'application/json', 'x-request-id': 'req_minimax'}, raw
    with CodexBroker(task, KEY, upstream=upstream, on_exchange=lambda phase, raw: captures.append((phase, raw))) as broker:
        status, output = post(broker, body)
    assert status == 502 and KEY.encode() not in output
    assert broker.observations[0]['classification'] == 'UPSTREAM_SECRET_REFLECTION'
    assert not any(phase == 'response' for phase, _ in captures)
    assert any(phase == 'response-quarantined' for phase, _ in captures)


def test_minimax_fixed_tls_host_is_used_without_provider_fallback(monkeypatch):
    calls = []
    def connection(host, **kwargs):
        calls.append(host)
        raise OSError('test stops before TLS')
    monkeypatch.setattr(http.client, 'HTTPSConnection', connection)
    with pytest.raises(RouterError, match='TLS_SETUP_FAILED'):
        _CodexUpstream(1, 1000, backend='minimax')('/v1/responses', {}, b'{}')
    assert calls == ['api.minimaxi.com']
    with pytest.raises(RouterError, match='IMAGE_ROUTE_MISMATCH'):
        _CodexUpstream(1, 1000, backend='other')


def test_minimax_failure_receipt_projects_only_static_issue(tmp_path):
    task, body = fixture(tmp_path)
    captures = []
    with CodexBroker(task, KEY, upstream=lambda *args: (
        200, {'content-type': 'application/json'}, canonical_bytes(response(task))),
            on_exchange=lambda phase, raw: captures.append((phase, raw))) as broker:
        status, raw = post(broker, body)
    assert status == 502 and strict_json(raw) == {'error': 'IDENTITY_UNVERIFIED'}
    assert broker.observations[0]['response_issue'] == 'REQUEST_ID_MISSING'
    quarantined = [strict_json(raw) for phase, raw in captures if phase == 'response-quarantined']
    assert quarantined[0]['response_issue'] == 'REQUEST_ID_MISSING'
    assert not any(phase == 'response' for phase, _ in captures)


def test_minimax_arbitrary_exception_detail_is_not_projected(tmp_path, monkeypatch):
    from agent_subagent_router import minimax_image_wire
    task, body = fixture(tmp_path)
    captures = []
    def reject(*args):
        raise RouterError('IDENTITY_UNVERIFIED', 'private-provider-data')
    monkeypatch.setattr(minimax_image_wire, 'validate_minimax_image_response', reject)
    with CodexBroker(task, KEY, upstream=lambda *args: (
        200, {'content-type': 'application/json', 'x-request-id': 'safe-id'},
        canonical_bytes(response(task))),
            on_exchange=lambda phase, raw: captures.append((phase, raw))) as broker:
        status, _ = post(broker, body)
    assert status == 502
    assert 'response_issue' not in broker.observations[0]
    assert b'private-provider-data' not in canonical_bytes(broker.observations)
    assert all(b'private-provider-data' not in raw for _, raw in captures)


@pytest.mark.parametrize('field,value,issue', [
    ('max_output_tokens', None, 'CAP_ECHO_NULL'),
    ('max_output_tokens', False, 'CAP_ECHO_INVALID'),
    ('max_output_tokens', 4096, 'CAP_ECHO_MISMATCH'),
    ('input_tokens', None, 'INPUT_USAGE_INVALID'),
    ('output_tokens', None, 'OUTPUT_USAGE_INVALID'),
    ('output_tokens', 2049, 'OUTPUT_OVER_CAP'),
])
def test_generation_diagnostic_is_static_and_response_remains_quarantined(tmp_path, field, value, issue):
    task, body = fixture(tmp_path)
    value_response = response(task)
    if field == 'max_output_tokens':
        value_response[field] = value
    else:
        value_response['usage'][field] = value
    captures = []
    with CodexBroker(task, KEY, upstream=lambda *args: (
            200, {'content-type': 'application/json', 'x-request-id': 'actual-request'},
            canonical_bytes(value_response)),
            on_exchange=lambda phase, raw: captures.append((phase, raw))) as broker:
        status, raw = post(broker, body)
    assert status == 502 and strict_json(raw) == {'error': 'IMAGE_GENERATION_LIMIT'}
    assert broker.observations[0]['response_issue'] == issue
    quarantined = [strict_json(raw) for phase, raw in captures if phase == 'response-quarantined']
    assert quarantined[0]['response_issue'] == issue
    assert set(quarantined[0]) == {'classification', 'sha256', 'byte_length', 'response_issue'}
    assert not any(phase == 'response' for phase, _ in captures)


def test_new_body_identity_is_bound_in_broker_and_native_decoder(tmp_path):
    from test_minimax_image_wire import allow_response_identity
    task, body = fixture(tmp_path)
    allow_response_identity(task)
    actual = canonical_bytes(response(task))
    with CodexBroker(task, KEY, upstream=lambda *args: (
            200, {'content-type': 'application/json'}, actual)) as broker:
        status, raw = post(broker, body)
    assert status == 200 and raw == actual
    observation = broker.observations[0]
    assert observation['response_request_id_source'] == 'response-id'
    assert observation['response_request_id'] == 'mini_response_1'
    packet = {'schema': 'minimax-image-runtime/v1', 'status': 'completed',
              'request_sha256': hash_bytes(canonical_bytes(body)),
              'response_sha256': hash_bytes(actual), 'response': response(task)}
    original, canonical = decode_image_minimax(canonical_bytes(packet), 1000000,
        task=task, observation=observation, response_bytes=actual)
    assert original == canonical == b'{"ok":true}'
    for field, value in [('response_request_id_source', 'caller'),
                         ('response_request_id_source', 'header'),
                         ('response_request_id', 'borrowed-response')]:
        altered = {**observation, field: value}
        with pytest.raises(RouterError):
            decode_image_minimax(canonical_bytes(packet), 1000000, task=task,
                                 observation=altered, response_bytes=actual)
    for field in ['response_request_id_source', 'response_identity_headers']:
        altered = dict(observation)
        altered.pop(field, None)
        altered['response_request_id'] = 'borrowed_other_run'
        with pytest.raises(RouterError):
            decode_image_minimax(canonical_bytes(packet), 1000000, task=task,
                                 observation=altered, response_bytes=actual)


def test_new_header_identity_records_actual_headers_and_explicit_source(tmp_path):
    from test_minimax_image_wire import allow_response_identity
    task, body = fixture(tmp_path)
    allow_response_identity(task)
    actual = canonical_bytes(response(task))
    headers = {'Content-Type': 'application/json; charset=utf-8', 'Request-ID': 'actual-request'}
    with CodexBroker(task, KEY, upstream=lambda *args: (200, headers, actual)) as broker:
        status, _ = post(broker, body)
    assert status == 200
    observation = broker.observations[0]
    assert observation['response_request_id_source'] == 'header'
    assert observation['response_identity_headers'] == {
        'content-type': 'application/json', 'request-id': 'actual-request'}
    packet = {'schema': 'minimax-image-runtime/v1', 'status': 'completed',
              'request_sha256': hash_bytes(canonical_bytes(body)),
              'response_sha256': hash_bytes(actual), 'response': response(task)}
    assert decode_image_minimax(canonical_bytes(packet), 1000000, task=task,
        observation=observation, response_bytes=actual)[1] == b'{"ok":true}'


@pytest.mark.parametrize('secret_kind', ['credential', 'capability'])
@pytest.mark.parametrize('reverse', [False, True])
def test_new_identity_headers_reject_split_secrets_before_any_publication(tmp_path, secret_kind, reverse):
    from test_minimax_image_wire import allow_response_identity
    task, body = fixture(tmp_path)
    allow_response_identity(task)
    persisted = []
    captures = []
    pieces = []
    def upstream(*args):
        secret = KEY if secret_kind == 'credential' else broker.capability
        cut = len(secret)//2
        pieces.extend([secret[:cut], secret[cut:]])
        headers = {'content-type': 'application/json; marker='+pieces[0],
                   'request-id': pieces[1]}
        if reverse:
            headers = dict(reversed(list(headers.items())))
        return 200, headers, canonical_bytes(response(task))
    with CodexBroker(task, KEY, upstream=upstream,
            on_observation=lambda value: persisted.append(canonical_bytes(value)),
            on_exchange=lambda phase, raw: captures.append((phase, raw))) as broker:
        status, _ = post(broker, body)
    assert status == 502
    assert broker.observations[0]['classification'] == 'UPSTREAM_SECRET_REFLECTION'
    assert 'response_identity_headers' not in broker.observations[0]
    assert not any(phase == 'response' for phase, _ in captures)
    for raw in persisted + [raw for _, raw in captures]:
        assert all(piece.encode() not in raw for piece in pieces)


@pytest.mark.parametrize('tamper', ['request', 'response_hash', 'response_object', 'store_type'])
def test_minimax_native_envelope_must_match_independent_wire_bytes(tmp_path, tamper):
    task, body = fixture(tmp_path)
    raw_response = canonical_bytes(response(task))
    request_sha = hash_bytes(canonical_bytes(body))
    observation = {'actual_request_sha256': request_sha, 'response_sha256': hash_bytes(raw_response), 'response_request_id': 'req_minimax'}
    packet = {'schema': 'minimax-image-runtime/v1', 'status': 'completed', 'request_sha256': request_sha,
        'response_sha256': hash_bytes(raw_response), 'response': response(task)}
    original, canonical = decode_image_minimax(canonical_bytes(packet), 1000000, task=task,
        observation=observation, response_bytes=raw_response)
    assert strict_json(original) == strict_json(canonical) == {'ok': True}
    broken = copy.deepcopy(packet)
    if tamper == 'response_object':
        broken['response']['output'][0]['content'][0]['text'] = '{"other":true}'
    elif tamper == 'store_type':
        broken['response']['store'] = 0
    else:
        broken['request_sha256' if tamper == 'request' else 'response_sha256'] = '0'*64
    with pytest.raises(RouterError, match='IMAGE_NATIVE_ASSOCIATION_MISMATCH'):
        decode_image_minimax(canonical_bytes(broken), 1000000, task=task, observation=observation, response_bytes=raw_response)


def test_minimax_binding_uses_original_wire_not_filtered_receipt_artifact(tmp_path, monkeypatch):
    from agent_subagent_router import image_run
    from agent_subagent_router.receipts import ReceiptStore
    task, _ = fixture(tmp_path)
    png_path = tmp_path/'image.png'
    png_path.write_bytes(make_png())
    task['images'][0]['path'] = str(png_path)
    sealed = {'task': task, 'pins': {}, 'images': [{'blob_path': item['path']} for item in task['images']]}
    manifest = tmp_path/'manifest.json'
    manifest.write_bytes(canonical_bytes(sealed))
    text = '{"note":"authorization: safe"}'

    class SyntheticRuntime:
        def execute(self, argv, env, stdin, budgets, **kwargs):
            connection = http.client.HTTPConnection('broker', timeout=5)
            connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.sock.connect(str(kwargs['broker_socket']))
            try:
                connection.request('POST', '/v1/responses', stdin,
                    {'Authorization': 'Bearer '+env['IMAGE_ROUTE_CAPABILITY'], 'Content-Type': 'application/json'})
                upstream = connection.getresponse()
                raw = upstream.read()
                assert upstream.status == 200
            finally:
                connection.close()
            packet = {'schema': 'minimax-image-runtime/v1', 'status': 'completed',
                'request_sha256': hash_bytes(stdin), 'response_sha256': hash_bytes(raw), 'response': strict_json(raw)}
            return SimpleNamespace(stdout=canonical_bytes(packet)+b'\n', stderr=b'',
                exit_code=0, reason='exited', truncated=False, duration_seconds=0)

    monkeypatch.setattr(image_run, 'verify_image_seal', lambda _: sealed)
    monkeypatch.setattr(image_run, 'image_runtime', lambda *a: (SyntheticRuntime(), {}))
    store = ReceiptStore(tmp_path/'runs')
    receipt = image_run.run_image_contract(manifest, store, sandbox_config=tmp_path/'config',
        upstream=lambda *a: (200, {'content-type': 'application/json', 'x-request-id': 'req_minimax'},
            canonical_bytes(response(task, text))))
    assert receipt['classification'] == 'ENGINEERING_NATIVE_COMPLETE'
    wire = next(item for item in receipt['artifacts'] if item['path'] == 'wire/response-000.bin')
    assert wire['redaction_count'] == 1
    assert wire['sha256'] != receipt['upstream'][0]['response_sha256']
    assert store.read(receipt['invocation_id']) == receipt
