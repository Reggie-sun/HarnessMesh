import pytest
from test_codex_image_broker import _post
from agent_subagent_router.contracts import canonical_bytes, strict_json
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.image_wire import validate_claude_image_response
from agent_subagent_router.transport.broker import Broker


@pytest.mark.parametrize('secret_kind', ['credential', 'capability', 'clean'])
@pytest.mark.parametrize('mode', ['start-delta', 'unverified-id', 'nested-field', 'signature-field', 'json-field', 'initial-message', 'unknown-index'])
def test_kimi_start_and_delta_share_block_identity(tmp_path, secret_kind, mode):
    from agent_subagent_router.receipts import ReceiptStore
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('engineering-fragment-test', 'kimi-block')
    artifacts = []
    key = 'kimi-block-key-sentinel'
    captured = []
    task = {'profile': 'worker', 'budgets': {'generation_tokens': 2048}}
    def upstream(*args):
        secret = key if secret_kind == 'credential' else broker.capability if secret_kind == 'capability' else 'normal-thinking'
        cut = len(secret)//2
        events = [
            {'type': 'message_start', 'message': {'id': 'msg_safe', 'model': 'k3-256k', 'content': [], 'usage': {'input_tokens': 1}}},
            {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'thinking', 'thinking': secret[:cut]}},
            {'type': 'content_block_start', 'index': 1, 'content_block': {'type': 'thinking', 'thinking': 'X'}},
            {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'thinking_delta', 'thinking': secret[cut:]}},
            {'type': 'content_block_stop', 'index': 0},
            {'type': 'content_block_stop', 'index': 1},
            {'type': 'content_block_start', 'index': 2, 'content_block': {'type': 'text', 'text': '{}'}},
            {'type': 'content_block_stop', 'index': 2},
            {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 1}},
            {'type': 'message_stop'}]
        if mode == 'unverified-id':
            events[1]['content_block']['thinking'] = ''
            events.insert(2, {'type': 'content_block_delta', 'index': 0, 'response_id': 'unverified-a',
                             'delta': {'type': 'thinking_delta', 'thinking': secret[:cut]}})
            events[4]['response_id'] = 'unverified-b'
        elif mode == 'unknown-index':
            events[3]['index'] = 2
        elif mode == 'nested-field':
            events[1]['content_block']['thinking'] = ''
            events.insert(2, {'type': 'content_block_delta', 'index': 0,
                             'delta': {'type': 'thinking_delta', 'thinking': secret[:cut]}})
            events[4]['aux'] = {'thinking': 'X'}
        elif mode == 'signature-field':
            events[1]['content_block']['thinking'] = ''
            events.insert(2, {'type': 'content_block_delta', 'index': 0,
                             'delta': {'type': 'thinking_delta', 'thinking': secret[:cut]}})
            events.insert(3, {'type': 'content_block_delta', 'index': 0,
                             'delta': {'type': 'signature_delta', 'signature': 'safe-signature', 'thinking': 'X'}})
        elif mode == 'json-field':
            message = dict(events[0]['message'], stop_reason='end_turn', usage={'input_tokens': 1, 'output_tokens': 1},
                content=[{'type': 'thinking', 'thinking': secret[:cut]},
                         {'type': 'text', 'text': '{}', 'thinking': 'X'},
                         {'type': 'thinking', 'thinking': secret[cut:]}])
            raw = canonical_bytes(message)
            assert secret.encode() not in raw
            return 200, {'content-type': 'application/json'}, raw
        elif mode == 'initial-message':
            events[0]['message']['content'] = [{'type': 'thinking', 'thinking': secret[:cut]}]
            events[1]['content_block']['thinking'] = ''
        raw = b''.join(b'data: '+canonical_bytes(x)+b'\n\n' for x in events)
        assert secret.encode() not in raw
        return 200, {'content-type': 'text/event-stream'}, raw
    def exchange(phase, data):
        captured.append((phase, data))
        artifacts.append(store.artifact(run, 'wire/'+phase+'.bin', data,
            secrets=(key.encode(), broker.capability.encode()), producer='image-broker'))
    with Broker(profile('worker'), key, request_limit=1, wall_seconds=5, upstream=upstream,
                allow_response_tools=False, response_validator=lambda h,d: validate_claude_image_response(task,h,d),
                on_exchange=exchange) as broker:
        request = {'model': 'k3-256k', 'thinking': {'type': 'enabled', 'budget_tokens': 8192},
                   'output_config': {'effort': 'high'}, 'messages': [{'role': 'user', 'content': 'OK'}],
                   'max_tokens': 100, 'tools': []}
        status, _ = _post(broker, request, path='/v1/messages')
    if secret_kind == 'clean' and mode not in ('unknown-index', 'initial-message'):
        assert status == 200 and captured[-1][0] == 'response'
    else:
        assert status == 502
        assert broker.observations[0]['classification'] in ('UPSTREAM_SECRET_REFLECTION', 'UPSTREAM_PROTOCOL_ERROR')
        assert captured[-1][0] == 'response-quarantined'
        assert set(strict_json(captured[-1][1])) == {'classification', 'sha256', 'byte_length'}
        secret = key if secret_kind == 'credential' else broker.capability
        cut = len(secret)//2
        for artifact in artifacts:
            saved = (run/artifact['path']).read_bytes()
            assert secret[:cut].encode() not in saved and secret[cut:].encode() not in saved
