import hashlib
import json

import pytest

from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.transport.broker import Broker
from test_transport import body, post, response


@pytest.mark.parametrize('cause', ['last_request', 'remaining_time'])
def test_reporting_phase_removes_tools_preserves_evidence_and_hashes_wire_body(cause):
    sent = []

    def upstream(path, headers, raw):
        sent.append(raw)
        return 200, {}, response()

    with Broker(profile('worker'), 'sentinel', request_limit=2, wall_seconds=120,
                upstream=upstream, allowed_tools=('Read',), report_budget=True) as broker:
        payload = body() | {'tools': [{'name': 'Read', 'input_schema': {'type': 'object'}}]}
        assert post(broker, payload)[0] == 200
        first = json.loads(sent[0])
        assert first['tools'] == payload['tools']
        assert first['messages'][-1]['content'][-1]['text'].startswith('HarnessMesh budget:')
        if cause == 'remaining_time':
            broker._limit = 20
            broker._deadline -= 100
        payload['messages'] = [{'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': 'read1', 'content': 'SOURCE-EVIDENCE'}]}]
        assert post(broker, payload)[0] == 200
        final = json.loads(sent[-1])
        assert final['tools'] == []
        assert final['messages'][-1]['content'][0] == payload['messages'][-1]['content'][0]
        assert 'FINAL_REPORT' in final['messages'][-1]['content'][-1]['text']
        assert final['model'] == payload['model'] and final['thinking'] == payload['thinking']
        assert broker.observations[-1]['budget_phase'] == 'FINAL_REPORT'
        assert broker.observations[-1]['request_sha256'] == hashlib.sha256(sent[-1]).hexdigest()
        assert 'HarnessMesh budget' not in str(payload)


def test_unverified_identity_still_never_reaches_runtime_during_reporting():
    with Broker(profile('worker'), 'sentinel', request_limit=1, wall_seconds=120,
                upstream=lambda *a: (200, {}, response('wrong-model')),
                report_budget=True) as broker:
        status, data = post(broker)
        assert status == 502 and b'ROUTE_MISMATCH' in data
        assert b'wrong-model' not in data


def test_budget_notice_does_not_expand_maximum_request_body():
    calls = []
    with Broker(profile('worker'), 'sentinel', request_limit=1, wall_seconds=120,
                upstream=lambda *a: calls.append(a), report_budget=True) as broker:
        payload = body()
        raw_size = len(json.dumps(payload).encode())
        payload['messages'][0]['content'] += 'x' * (8*1024*1024-raw_size)
        status, _ = post(broker, payload)
        assert status in (400, 502)
        assert not calls


@pytest.mark.parametrize('stream', [False, True])
def test_reporting_refuses_tool_response_even_when_upstream_ignores_removed_tools(stream):
    payload = json.loads(response())
    payload['content'] = [{'type': 'tool_use', 'id': 'bad', 'name': 'Read', 'input': {}}]
    raw, headers = json.dumps(payload).encode(), {}
    if stream:
        events = [{'type': 'message_start', 'message': json.loads(response())},
                  {'type': 'content_block_start', 'index': 0,
                   'content_block': payload['content'][0]}, {'type': 'message_stop'}]
        raw = ''.join('data: '+json.dumps(event)+'\n\n' for event in events).encode()
        headers = {'content-type': 'text/event-stream'}
    with Broker(profile('worker'), 'sentinel', request_limit=1, wall_seconds=120,
                upstream=lambda *a: (200, headers, raw),
                report_budget=True) as broker:
        status, data = post(broker)
        assert status == 502 and b'TOOL_POLICY_VIOLATION' in data


@pytest.mark.parametrize('messages', [None, 'bad', [None], [{'role': 'user', 'content': 7}]])
def test_malformed_messages_are_refused_without_sending(messages):
    sent = []
    with Broker(profile('worker'), 'sentinel', request_limit=1, wall_seconds=120,
                upstream=lambda *a: sent.append(a), report_budget=True) as broker:
        status, _ = post(broker, body() | {'messages': messages})
        assert status == 400 and not sent
