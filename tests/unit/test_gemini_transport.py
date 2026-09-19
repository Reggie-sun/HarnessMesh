import json
import os
import socket

import pytest

from agent_subagent_router.contracts import RouterError, canonical_bytes


def test_oauth_reader_rejects_public_project_and_preserves_credential_file(tmp_path):
    from agent_subagent_router.transport.gemini_oauth import load_oauth_file

    project = tmp_path/'project'
    project.mkdir()
    credential = project/'oauth.json'
    credential.write_text(json.dumps({'access_token': 'token', 'refresh_token': 'refresh', 'expiry_date': 9_999_999_999_999}))
    credential.chmod(0o600)
    with pytest.raises(RouterError, match='UNSAFE_CREDENTIAL'):
        load_oauth_file(credential, project_root=project)
    credential = tmp_path/'oauth.json'
    raw = json.dumps({'access_token': 'token', 'refresh_token': 'refresh', 'expiry_date': 9_999_999_999_999}).encode()
    credential.write_bytes(raw)
    credential.chmod(0o600)
    loaded = load_oauth_file(credential, project_root=project)
    assert loaded.access_token == 'token'
    assert credential.read_bytes() == raw
    credential.chmod(0o644)
    with pytest.raises(RouterError, match='UNSAFE_CREDENTIAL'):
        load_oauth_file(credential, project_root=project)
    credential.chmod(0o600)
    os.symlink(credential, tmp_path/'link.json')
    with pytest.raises(RouterError, match='UNSAFE_CREDENTIAL'):
        load_oauth_file(tmp_path/'link.json', project_root=project)


def test_oauth_refresh_and_code_assist_preflight_are_fixed_and_typed():
    from agent_subagent_router.transport.gemini_oauth import OAuthCredential, access_token, preflight_code_assist

    credential = OAuthCredential('old', 'refresh', 1)
    seen = {}

    def refresh(form):
        seen.update(form)
        return {'access_token': 'new', 'expires_in': 3600}

    assert access_token(credential, now=100, refresher=refresh) == 'new'
    assert seen['grant_type'] == 'refresh_token' and seen['refresh_token'] == 'refresh'
    request = {}

    def upstream(path, headers, body):
        request.update(path=path, headers=headers, body=json.loads(body))
        return 200, {}, canonical_bytes({'currentTier': {'id': 'STANDARD'}, 'cloudaicompanionProject': 'approved-project'})

    result = preflight_code_assist('bearer', 'approved-project', upstream=upstream)
    assert result == {'project': 'approved-project', 'tier': 'STANDARD', 'proof': 'synthetic_upstream'}
    assert request['path'] == '/v1internal:loadCodeAssist'
    assert request['headers']['authorization'] == 'Bearer bearer'
    with pytest.raises(RouterError, match='GEMINI_INELIGIBLE'):
        preflight_code_assist('bearer', 'approved-project', upstream=lambda *_: (200, {}, b'{}'))
    discovered = preflight_code_assist('bearer', upstream=upstream)
    assert discovered['project'] == 'approved-project'
    assert 'cloudaicompanionProject' not in request['body']


def test_broker_rejects_wrong_path_model_tools_and_revoked_capability(tmp_path):
    from agent_subagent_router.transport.gemini_broker import GeminiBroker, REST_PATH

    response = {'traceId': 'parent-token', 'response': {'candidates': [{'finishReason': 'STOP'}],
                                                    'usageMetadata': {}, 'modelVersion': 'gemini-3.5-flash'}}
    published = []

    def upstream(*_args):
        assert published and published[-1][0]['classification'] == 'OUTCOME_UNKNOWN'
        return 200, {'content-type': 'text/event-stream'}, b'data: '+canonical_bytes(response)+b'\n\n'

    broker = GeminiBroker('parent-token', 'project', request_limit=1, wall_seconds=10,
                          socket_path=tmp_path/'broker.sock', upstream=upstream, on_observation=published.append)
    valid = canonical_bytes({'contents': [{'role': 'user', 'parts': [{'text': 'hello'}]}],
                             'tools': [{'functionDeclarations': [{'name': 'read_file'}]}]})
    headers = {'x-goog-api-key': broker.capability, 'content-type': 'application/json'}
    with pytest.raises(RouterError, match='FORBIDDEN_PATH'):
        broker.forward('/v1beta/models/other:streamGenerateContent?alt=sse', headers, valid)
    with pytest.raises(RouterError, match='ROUTE_MISMATCH'):
        broker.forward(REST_PATH, headers, canonical_bytes({'contents': [], 'model': 'gemini-1.5-pro'}))
    with pytest.raises(RouterError, match='TOOL_POLICY_VIOLATION'):
        broker.forward(REST_PATH, headers, canonical_bytes({'contents': [], 'tools': [{'functionDeclarations': [{'name': 'shell'}]}]}))
    with pytest.raises(RouterError, match='TOOL_POLICY_VIOLATION'):
        broker.forward(REST_PATH, headers, canonical_bytes({'contents': [], 'tools': [
            {'functionDeclarations': [{'name': 'read_file'}], 'googleSearch': {}}]}))
    status, _headers, data = broker.forward(REST_PATH, headers, valid)
    assert status == 200 and b'"modelVersion":"gemini-3.5-flash"' in data
    assert b'parent-token' not in data
    assert broker.observations[0]['proof'] == 'synthetic_upstream'
    assert 'parent-token' not in repr(broker.observations)
    broker.revoke()
    with pytest.raises(RouterError, match='CAPABILITY_REVOKED'):
        broker.forward(REST_PATH, headers, valid)


def test_broker_enforces_cap_budget_and_authenticated_model_identity(tmp_path):
    from agent_subagent_router.transport.gemini_broker import GeminiBroker, REST_PATH

    class Upstream:
        closed = False

        def __call__(self, _path, _headers, _body):
            response = {'traceId': 'trace-1', 'response': {'candidates': [{'finishReason': 'STOP'}],
                                                            'usageMetadata': {}, 'modelVersion': 'wrong'}}
            return 200, {'content-type': 'text/event-stream'}, b'data: '+canonical_bytes(response)+b'\n\n'

        def close(self):
            self.closed = True

    upstream = Upstream()
    broker = GeminiBroker('parent-token', 'project', request_limit=1, wall_seconds=10,
                          socket_path=tmp_path/'broker.sock', upstream=upstream)
    body = canonical_bytes({'contents': []})
    with pytest.raises(RouterError, match='IDENTITY_UNVERIFIED'):
        broker.forward(REST_PATH, {'authorization': 'Bearer '+broker.capability,
                                   'content-type': 'application/json'}, body)
    with pytest.raises(RouterError, match='REQUEST_BUDGET_EXHAUSTED'):
        broker.forward(REST_PATH, {'authorization': 'Bearer '+broker.capability,
                                   'content-type': 'application/json'}, body)
    broker.revoke()
    assert upstream.closed


def test_broker_socket_bounds_truncated_body_and_freezes_late_publication(tmp_path):
    from agent_subagent_router.transport.gemini_broker import GeminiBroker, REST_PATH

    publications = []
    response = {'traceId': 'trace-1', 'response': {'candidates': [{'finishReason': 'STOP'}],
                                                    'modelVersion': 'gemini-3.5-flash'}}
    broker = GeminiBroker('parent-token', 'project', request_limit=1, wall_seconds=1,
                          socket_path=tmp_path/'broker.sock', on_observation=publications.append,
                          upstream=lambda *_: (200, {'content-type': 'text/event-stream'},
                                                   b'data: '+canonical_bytes(response)+b'\n\n'))
    with broker:
        assert (tmp_path/'broker.sock').stat().st_mode & 0o777 == 0o600
        client = socket.socket(socket.AF_UNIX)
        client.settimeout(1)
        client.connect(str(tmp_path/'broker.sock'))
        client.sendall((f'POST {REST_PATH} HTTP/1.1\r\nHost: local\r\n'
                        f'x-goog-api-key: {broker.capability}\r\nContent-Type: application/json\r\n'
                        'Content-Length: 9\r\n\r\n{}').encode())
        client.shutdown(socket.SHUT_WR)
        assert b'400' in client.recv(4096)
        client.close()
        body = canonical_bytes({'contents': []})
        client = socket.socket(socket.AF_UNIX)
        client.settimeout(1)
        client.connect(str(tmp_path/'broker.sock'))
        client.sendall((f'POST {REST_PATH} HTTP/1.1\r\nHost: local\r\n'
                        f'x-goog-api-key: {broker.capability}\r\nContent-Type: application/json\r\n'
                        f'Content-Length: {len(body)}\r\n\r\n').encode()+body)
        assert b'200' in client.recv(4096)
        client.close()
    count = len(publications)
    broker._publish()
    assert len(publications) == count


@pytest.mark.parametrize('stop', ['revoke', 'deadline'])
def test_broker_rechecks_admission_after_durable_observation(tmp_path, stop):
    from agent_subagent_router.transport.gemini_broker import GeminiBroker, REST_PATH
    calls = []
    def publish(_):
        if stop == 'revoke':
            broker.revoke()
        else:
            broker._deadline = 0
    broker = GeminiBroker('secret', 'project', request_limit=1, wall_seconds=10,
        socket_path=tmp_path/'broker.sock', on_observation=publish,
        upstream=lambda *args: calls.append(args))
    with broker, pytest.raises(RouterError, match='CAPABILITY_REVOKED'):
        broker.forward(REST_PATH, {'x-goog-api-key': broker.capability,
            'content-type': 'application/json'}, canonical_bytes({'contents': []}))
    assert calls == []


def test_rejected_route_stays_observable_after_later_valid_request(tmp_path):
    from agent_subagent_router.transport.gemini_broker import GeminiBroker, REST_PATH
    publications, requests = [], []
    response = {'traceId':'trace', 'response':{'modelVersion':'gemini-3.5-flash',
                                            'candidates':[{'finishReason':'STOP'}]}}
    with GeminiBroker('secret', 'project', request_limit=1, wall_seconds=5,
        socket_path=tmp_path/'broker.sock', on_rejection=publications.append,
        on_request=requests.append, upstream=lambda *_:(200, {'content-type':'text/event-stream'},
            b'data: '+canonical_bytes(response)+b'\n\n')) as broker:
        headers = {'x-goog-api-key':broker.capability, 'content-type':'application/json'}
        with pytest.raises(RouterError, match='FORBIDDEN_PATH'):
            broker.forward('/alternate-model', headers, canonical_bytes({'contents':[]}))
        assert publications == [['FORBIDDEN_PATH']] and not requests
        broker.forward(REST_PATH, headers, canonical_bytes({'contents':[]}))
    assert broker.rejections == ['FORBIDDEN_PATH']
    assert len(requests) == 1 and broker.observations[0]['proof'] == 'synthetic_upstream'
