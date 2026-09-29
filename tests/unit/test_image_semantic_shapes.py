import pytest
from test_codex_image_broker import API_KEY, _post
from test_codex_image_wire import request_fixture, _sse_events, _sse_bytes
from agent_subagent_router.contracts import canonical_bytes, strict_json
from agent_subagent_router.transport.codex_broker import CodexBroker
from agent_subagent_router.transport.broker import Broker
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.image_wire import validate_claude_image_response
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.contracts import RouterError


@pytest.mark.parametrize('encoding', ['sse', 'json'])
@pytest.mark.parametrize('kind,field', [('text', 'text'), ('thinking', 'thinking'),
                                     ('thinking', 'signature'), ('redacted_thinking', 'data')])
@pytest.mark.parametrize('malformed', [True, False])
def test_all_kimi_semantic_block_fields_have_string_shape(encoding, kind, field, malformed):
    block = {'type': kind, 'thinking': ''} if kind == 'thinking' else {'type': kind}
    block[field] = ['ordinary-content'] if malformed else 'ordinary-content'
    message = {'id': 'msg_safe', 'model': 'k3-256k', 'content': [block, {'type': 'text', 'text': '{}'}],
               'stop_reason': 'end_turn', 'usage': {'input_tokens': 1, 'output_tokens': 1}}
    if encoding == 'json':
        raw = canonical_bytes(message)
    else:
        events = [{'type': 'message_start', 'message': dict(message, content=[])},
                  {'type': 'content_block_start', 'index': 0, 'content_block': block},
                  {'type': 'content_block_stop', 'index': 0},
                  {'type': 'content_block_start', 'index': 1, 'content_block': {'type': 'text', 'text': '{}'}},
                  {'type': 'content_block_stop', 'index': 1},
                  {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 1}},
                  {'type': 'message_stop'}]
        raw = b''.join(b'data: '+canonical_bytes(event)+b'\n\n' for event in events)
    task = {'profile': 'worker', 'budgets': {'generation_tokens': 2048}}
    headers = {'content-type': 'application/json' if encoding == 'json' else 'text/event-stream'}
    if malformed:
        with pytest.raises(RouterError, match='UPSTREAM_PROTOCOL_ERROR'):
            validate_claude_image_response(task, headers, raw)
    else:
        assert validate_claude_image_response(task, headers, raw)['classification'] == 'IDENTITY_VERIFIED'


@pytest.mark.parametrize('encoding', ['sse', 'json'])
@pytest.mark.parametrize('shape', ['array', 'object', 'string'])
@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
def test_terminal_reasoning_requires_string_summary(tmp_path, encoding, shape, secret_kind):
    task, native, _ = request_fixture(tmp_path)
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('engineering-semantic-shape', 'codex-summary')
    artifacts, captured = [], []
    def upstream(*args):
        secret = API_KEY if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'normal-reasoning'
        cut = len(secret)//2
        prefix = [secret[:cut]] if shape == 'array' else {'value': secret[:cut]} if shape == 'object' else secret[:cut]
        events = _sse_events(task)
        response = events[-1]['response']
        response['output'][0]['summary'] = [{'type': 'summary_text', 'text': prefix}, {'type': 'summary_text', 'text': secret[cut:]}]
        raw = _sse_bytes(events) if encoding == 'sse' else canonical_bytes(response)
        assert secret.encode() not in raw
        return 200, {'content-type': 'text/event-stream' if encoding == 'sse' else 'application/json', 'x-request-id': 'req_safe'}, raw
    def exchange(phase, data):
        captured.append((phase, data))
        artifacts.append(store.artifact(run, 'wire/'+phase+'.bin', data, secrets=(API_KEY.encode(), broker.capability.encode()), producer='image-broker'))
    with CodexBroker(task, API_KEY, upstream=upstream, on_exchange=exchange) as broker:
        status, _ = _post(broker, native)
    if shape == 'string' and secret_kind == 'clean':
        assert status == 200 and captured[-1][0] == 'response'
    else:
        assert status == 502 and broker._active is False
        assert broker.observations[0]['classification'] in ('UPSTREAM_SECRET_REFLECTION', 'UPSTREAM_PROTOCOL_ERROR')
        assert captured[-1][0] == 'response-quarantined'
        assert set(strict_json(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}
        if secret_kind != 'clean':
            secret = API_KEY if secret_kind == 'credential' else broker.capability
            cut = len(secret)//2
            for artifact in artifacts:
                saved = (run/artifact['path']).read_bytes()
                assert secret[:cut].encode() not in saved and secret[cut:].encode() not in saved


@pytest.mark.parametrize('mode', ['thinking-start', 'signature-start', 'json-thinking'])
@pytest.mark.parametrize('shape', ['array', 'object', 'string'])
@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
def test_kimi_semantic_fields_require_strings(tmp_path, mode, shape, secret_kind):
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('engineering-semantic-shape', 'kimi-content')
    artifacts, captured = [], []
    key = 'kimi-semantic-key-sentinel'
    task = {'profile': 'worker', 'budgets': {'generation_tokens': 2048}}
    def upstream(*args):
        secret = key if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'normal-thinking'
        cut = len(secret)//2
        prefix = [secret[:cut]] if shape == 'array' else {'value': secret[:cut]} if shape == 'object' else secret[:cut]
        field = 'signature' if mode == 'signature-start' else 'thinking'
        start = {'type': 'thinking', 'thinking': '', field: prefix}
        message = {'id': 'msg_safe', 'model': 'k3-256k', 'content': [], 'usage': {'input_tokens': 1}}
        if mode == 'json-thinking':
            message.update(content=[start, {'type': 'thinking', 'thinking': secret[cut:]}, {'type': 'text', 'text': '{}'}],
                           stop_reason='end_turn', usage={'input_tokens': 1, 'output_tokens': 1})
            raw = canonical_bytes(message)
        else:
            events = [
                {'type': 'message_start', 'message': message},
                {'type': 'content_block_start', 'index': 0, 'content_block': start},
                {'type': 'content_block_delta', 'index': 0, 'delta': {'type': field+'_delta', field: secret[cut:]}},
                {'type': 'content_block_stop', 'index': 0},
                {'type': 'content_block_start', 'index': 1, 'content_block': {'type': 'text', 'text': '{}'}},
                {'type': 'content_block_stop', 'index': 1},
                {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 1}},
                {'type': 'message_stop'}]
            raw = b''.join(b'data: '+canonical_bytes(event)+b'\n\n' for event in events)
        assert secret.encode() not in raw
        return 200, {'content-type': 'application/json' if mode == 'json-thinking' else 'text/event-stream'}, raw
    def exchange(phase, data):
        captured.append((phase, data))
        artifacts.append(store.artifact(run, 'wire/'+phase+'.bin', data, secrets=(key.encode(), broker.capability.encode()), producer='image-broker'))
    with Broker(profile('worker'), key, request_limit=1, wall_seconds=5, upstream=upstream,
                allow_response_tools=False, response_validator=lambda h,d: validate_claude_image_response(task,h,d), on_exchange=exchange) as broker:
        request = {'model': 'k3-256k', 'thinking': {'type': 'enabled', 'budget_tokens': 8192}, 'output_config': {'effort': 'high'},
                   'messages': [{'role': 'user', 'content': 'OK'}], 'max_tokens': 100, 'tools': []}
        status, _ = _post(broker, request, path='/v1/messages')
    if shape == 'string' and secret_kind == 'clean':
        assert status == 200 and captured[-1][0] == 'response'
    else:
        assert status == 502
        assert broker.observations[0]['classification'] in ('UPSTREAM_SECRET_REFLECTION', 'UPSTREAM_PROTOCOL_ERROR')
        assert captured[-1][0] == 'response-quarantined'
        assert set(strict_json(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}
        if secret_kind != 'clean':
            secret = key if secret_kind == 'credential' else broker.capability
            cut = len(secret)//2
            for artifact in artifacts:
                saved = (run/artifact['path']).read_bytes()
                assert secret[:cut].encode() not in saved and secret[cut:].encode() not in saved


@pytest.mark.parametrize('encoding', ['sse', 'json'])
@pytest.mark.parametrize('shape', ['array', 'object', 'string'])
@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
def test_terminal_reasoning_content_requires_string_text(tmp_path, encoding, shape, secret_kind):
    task, native, _ = request_fixture(tmp_path)
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('engineering-semantic-shape', 'codex-summary')
    artifacts, captured = [], []
    def upstream(*args):
        secret = API_KEY if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'normal-reasoning'
        cut = len(secret)//2
        prefix = [secret[:cut]] if shape == 'array' else {'value': secret[:cut]} if shape == 'object' else secret[:cut]
        events = _sse_events(task)
        response = events[-1]['response']
        response['output'][0]['summary'] = []
        response['output'][0]['content'] = [{'type': 'reasoning_text', 'text': prefix}, {'type': 'reasoning_text', 'text': secret[cut:]}]
        raw = _sse_bytes(events) if encoding == 'sse' else canonical_bytes(response)
        assert secret.encode() not in raw
        return 200, {'content-type': 'text/event-stream' if encoding == 'sse' else 'application/json', 'x-request-id': 'req_safe'}, raw
    def exchange(phase, data):
        captured.append((phase, data))
        artifacts.append(store.artifact(run, 'wire/'+phase+'.bin', data, secrets=(API_KEY.encode(), broker.capability.encode()), producer='image-broker'))
    with CodexBroker(task, API_KEY, upstream=upstream, on_exchange=exchange) as broker:
        status, _ = _post(broker, native)
    if shape == 'string' and secret_kind == 'clean':
        assert status == 200 and captured[-1][0] == 'response'
    else:
        assert status == 502 and broker._active is False
        assert broker.observations[0]['classification'] in ('UPSTREAM_SECRET_REFLECTION', 'UPSTREAM_PROTOCOL_ERROR')
        assert captured[-1][0] == 'response-quarantined'
        assert set(strict_json(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}
        if secret_kind != 'clean':
            secret = API_KEY if secret_kind == 'credential' else broker.capability
            cut = len(secret)//2
            for artifact in artifacts:
                saved = (run/artifact['path']).read_bytes()
                assert secret[:cut].encode() not in saved and secret[cut:].encode() not in saved



@pytest.mark.parametrize('encoding', ['sse', 'json'])
def test_null_encrypted_reasoning_is_compatible(tmp_path, encoding):
    task, native, _ = request_fixture(tmp_path)
    def upstream(*args):
        events = _sse_events(task)
        response = events[-1]['response']
        response['output'][0]['encrypted_content'] = None
        raw = _sse_bytes(events) if encoding == 'sse' else canonical_bytes(response)
        return 200, {'content-type': 'text/event-stream' if encoding == 'sse' else 'application/json', 'x-request-id': 'req_safe'}, raw
    with CodexBroker(task, API_KEY, upstream=upstream) as broker:
        status, _ = _post(broker, native)
    assert status == 200, broker.observations[0]['classification']

@pytest.mark.parametrize('field', ['content', 'encrypted_content'])
@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
@pytest.mark.parametrize('finished', [True, False])
def test_initial_reasoning_payload_cannot_leak_fragments(tmp_path, field, secret_kind, finished):
    task, native, _ = request_fixture(tmp_path)
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('engineering-initial-reasoning', 'initial-field')
    artifacts, captured = [], []
    def upstream(*args):
        secret = API_KEY if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'normal-encrypted-data'
        cut = len(secret)//2
        events = _sse_events(task)
        item = dict(events[-1]['response']['output'][0])
        def value(piece):
            return [{'type': 'reasoning_text', 'text': piece}] if field == 'content' else piece
        starting = dict(item, **{field: value(secret[:cut])})
        item[field] = value(secret[cut:])
        events[-1]['response']['output'][0] = item
        events.insert(1, {'type': 'response.output_item.added', 'response_id': events[0]['response']['id'], 'output_index': 0, 'item': starting})
        if finished:
            events.insert(-1, {'type': 'response.output_item.done', 'response_id': events[0]['response']['id'], 'output_index': 0, 'item': item})
        raw = _sse_bytes(events)
        assert secret.encode() not in raw
        return 200, {'content-type': 'text/event-stream', 'x-request-id': 'req_safe'}, raw
    def exchange(phase,data):
        captured.append((phase,data))
        artifacts.append(store.artifact(run,'wire/'+phase+'.bin',data,secrets=(API_KEY.encode(),broker.capability.encode()),producer='image-broker'))
    with CodexBroker(task,API_KEY,upstream=upstream,on_exchange=exchange) as broker:
        status,_ = _post(broker,native)
    if field == 'encrypted_content' and secret_kind == 'clean' and finished:
        assert status == 200
    else:
        assert status == 502
        assert broker.observations[0]['classification'] in ('UPSTREAM_PROTOCOL_ERROR','UPSTREAM_SECRET_REFLECTION')
        assert captured[-1][0]=='response-quarantined'
        if secret_kind != 'clean':
            secret = API_KEY if secret_kind == 'credential' else broker.capability
            cut = len(secret)//2
            for artifact in artifacts:
                saved=(run/artifact['path']).read_bytes()
                assert secret[:cut].encode() not in saved and secret[cut:].encode() not in saved


@pytest.mark.parametrize('encoding', ['sse', 'json'])
@pytest.mark.parametrize('shape', ['absent', 'null', 'string', 'array', 'object'])
def test_encrypted_reasoning_metadata_nullable_contract(tmp_path, encoding, shape):
    task, native, _ = request_fixture(tmp_path)
    def upstream(*args):
        events = _sse_events(task)
        response = events[-1]['response']
        if shape != 'absent':
            response['output'][0]['encrypted_content'] = {'null': None, 'string': 'opaque-data',
                                                         'array': ['opaque-data'], 'object': {'text': 'opaque-data'}}[shape]
        raw = _sse_bytes(events) if encoding == 'sse' else canonical_bytes(response)
        return 200, {'content-type': 'text/event-stream' if encoding == 'sse' else 'application/json', 'x-request-id': 'req_safe'}, raw
    with CodexBroker(task, API_KEY, upstream=upstream) as broker:
        status, _ = _post(broker, native)
    assert status == (200 if shape in ('absent', 'null', 'string') else 502)


@pytest.mark.parametrize('shape', ['array', 'object', 'boolean-id'])
@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
def test_initial_reasoning_shape_and_identity_before_capture(tmp_path, shape, secret_kind):
    task, native, _ = request_fixture(tmp_path)
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('engineering-initial-reasoning', 'initial-shape')
    artifacts, captured = [], []
    def upstream(*args):
        secret = API_KEY if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'ordinary-encrypted-data'
        cut = len(secret)//2
        events = _sse_events(task)
        item = dict(events[-1]['response']['output'][0], encrypted_content=secret[cut:])
        starting = dict(item, encrypted_content=secret[:cut])
        if shape == 'array':
            starting['encrypted_content'] = [secret[:cut]]
        elif shape == 'object':
            starting['encrypted_content'] = {'text': secret[:cut]}
        else:
            starting['id'], item['id'] = True, 1
        events[-1]['response']['output'][0] = item
        events.insert(1, {'type': 'response.output_item.added', 'response_id': events[0]['response']['id'],
                          'output_index': 0, 'item': starting})
        events.insert(-1, {'type': 'response.output_item.done', 'response_id': events[0]['response']['id'],
                           'output_index': 0, 'item': item})
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
    assert broker.observations[0]['classification'] in ('UPSTREAM_PROTOCOL_ERROR', 'IDENTITY_UNVERIFIED', 'UPSTREAM_SECRET_REFLECTION')
    assert captured[-1][0] == 'response-quarantined'
    assert set(strict_json(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}
    if secret_kind != 'clean':
        secret = API_KEY if secret_kind == 'credential' else broker.capability
        cut = len(secret)//2
        for artifact in artifacts:
            saved = (run/artifact['path']).read_bytes()
            assert secret[:cut].encode() not in saved and secret[cut:].encode() not in saved


@pytest.mark.parametrize('encoding', ['sse', 'json'])
@pytest.mark.parametrize('identity', [True, 1, None, ''])
def test_terminal_reasoning_identity_requires_nonempty_string(tmp_path, encoding, identity):
    task, native, _ = request_fixture(tmp_path)
    def upstream(*args):
        events = _sse_events(task)
        response = events[-1]['response']
        response['output'][0]['id'] = identity
        raw = _sse_bytes(events) if encoding == 'sse' else canonical_bytes(response)
        return 200, {'content-type': 'text/event-stream' if encoding == 'sse' else 'application/json', 'x-request-id': 'req_safe'}, raw
    with CodexBroker(task, API_KEY, upstream=upstream) as broker:
        status, _ = _post(broker, native)
    assert status == 502


@pytest.mark.parametrize('shape', ['absent', 'null', 'string'])
def test_initial_reasoning_nullable_metadata_remains_compatible(tmp_path, shape):
    task, native, _ = request_fixture(tmp_path)
    def upstream(*args):
        events = _sse_events(task)
        item = dict(events[-1]['response']['output'][0])
        if shape != 'absent':
            item['encrypted_content'] = None if shape == 'null' else 'ordinary-opaque-data'
        events[-1]['response']['output'][0] = item
        events.insert(1, {'type': 'response.output_item.added', 'response_id': events[0]['response']['id'],
                          'output_index': 0, 'item': dict(item)})
        events.insert(-1, {'type': 'response.output_item.done', 'response_id': events[0]['response']['id'],
                           'output_index': 0, 'item': dict(item)})
        return 200, {'content-type': 'text/event-stream', 'x-request-id': 'req_safe'}, _sse_bytes(events)
    with CodexBroker(task, API_KEY, upstream=upstream) as broker:
        status, _ = _post(broker, native)
    assert status == 200
