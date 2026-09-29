import json

import pytest

from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.transport.broker import Broker
from test_transport import body, post, response


def adaptive_body(max_tokens=32000):
    return body() | {'max_tokens': max_tokens, 'thinking': {'type': 'adaptive'}}


@pytest.mark.parametrize('requested,expected', [(32000, 4096), (2048, 2048)])
def test_wire_generation_cap_preserves_model_and_effort(requested, expected):
    sent = []
    def upstream(path, headers, raw):
        sent.append(json.loads(raw))
        return 200, {}, response()
    with Broker(profile('worker'), 'generation-key-sentinel', request_limit=2, wall_seconds=30,
                upstream=upstream, generation_tokens=4096) as broker:
        payload = adaptive_body(requested)
        assert post(broker, payload)[0] == 200
        assert sent[0]['max_tokens'] == expected
        assert sent[0]['thinking'] == payload['thinking']
        assert sent[0]['output_config'] == payload['output_config']
        assert sent[0]['model'] == payload['model']
        assert broker.observations[0]['request_max_tokens'] == expected
        assert broker.observations[0]['generation_token_limit'] == 4096


@pytest.mark.parametrize('stream', [False, True])
def test_truncated_generation_never_delivered_or_continued(stream):
    sent = []
    message = json.loads(response()) | {'stop_reason': 'max_tokens'}
    raw, headers = json.dumps(message).encode(), {}
    if stream:
        events = [{'type': 'message_start', 'message': json.loads(response())},
                  {'type': 'message_delta', 'delta': {'stop_reason': 'max_tokens'},
                   'usage': {'output_tokens': 4096}}, {'type': 'message_stop'}]
        raw = ''.join('data: '+json.dumps(e)+'\n\n' for e in events).encode()
        headers = {'content-type': 'text/event-stream'}
    def upstream(*args):
        sent.append(args)
        return 200, headers, raw
    with Broker(profile('worker'), 'generation-key-sentinel', request_limit=4, wall_seconds=30,
                upstream=upstream, generation_tokens=4096) as broker:
        status, data = post(broker, adaptive_body())
        assert status == 502 and b'UPSTREAM_GENERATION_LIMIT' in data
        assert post(broker, adaptive_body())[0] == 403
        assert len(sent) == 1


def test_manual_thinking_is_not_silently_reduced_to_fit_cap():
    sent = []
    with Broker(profile('worker'), 'fake', request_limit=2, wall_seconds=30,
                upstream=lambda *args: sent.append(args), generation_tokens=4096) as broker:
        status, data = post(broker, body() | {'max_tokens': 32000})
        assert status == 400 and b'GENERATION_BUDGET_INCOMPATIBLE' in data
        assert not sent


@pytest.mark.parametrize('limit', [None, True, 0, '4096'])
def test_invalid_runtime_max_tokens_never_reaches_upstream(limit):
    sent = []
    with Broker(profile('worker'), 'fake', request_limit=2, wall_seconds=30,
                upstream=lambda *args: sent.append(args), generation_tokens=4096) as broker:
        status, data = post(broker, adaptive_body(limit))
        assert status == 400 and b'INVALID_GENERATION_BUDGET' in data
        assert not sent


def test_upstream_cannot_claim_usage_above_cap_and_still_deliver():
    sent = []
    message = json.loads(response()) | {'usage': {'output_tokens': 4097}, 'stop_reason': 'end_turn'}
    def upstream(*args):
        sent.append(args)
        return 200, {}, json.dumps(message).encode()
    with Broker(profile('worker'), 'generation-key-sentinel', request_limit=3, wall_seconds=30,
                upstream=upstream, generation_tokens=4096) as broker:
        status, data = post(broker, adaptive_body())
        assert status == 502 and b'UPSTREAM_GENERATION_LIMIT' in data
        assert post(broker, adaptive_body())[0] == 403
        assert len(sent) == 1
