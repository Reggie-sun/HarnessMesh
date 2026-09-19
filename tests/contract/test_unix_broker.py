import http.client
import socket

from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.transport.broker import Broker
from agent_subagent_router.contracts import canonical_bytes


def test_private_unix_broker_has_no_tcp_listener_and_removes_socket(tmp_path):
    path = tmp_path/'broker.sock'
    with Broker(profile('worker'), 'secret', request_limit=1, wall_seconds=5,
                socket_path=path) as broker:
        assert broker.url is None
        assert path.stat().st_mode & 0o777 == 0o600
        connection = http.client.HTTPConnection('localhost')
        connection.sock = socket.socket(socket.AF_UNIX)
        connection.sock.connect(str(path))
        connection.request('POST', '/v1/messages', body=b'{}')
        assert connection.getresponse().status == 403
        connection.close()
    assert not path.exists()


def test_upstream_rejection_preserves_sanitized_diagnostic():
    payload = {'model': 'k3', 'thinking': {'type': 'adaptive'},
               'output_config': {'effort': 'max'}}
    def upstream(*args):
        return 403, {}, canonical_bytes({'error': {'type': 'permission_error',
            'message': 'plan unavailable SENTINEL-KEY'}})
    with Broker(profile('deep'), 'SENTINEL-KEY', request_limit=1, wall_seconds=5,
                upstream=upstream) as broker:
        conn = http.client.HTTPConnection('127.0.0.1', broker._server.server_port)
        conn.request('POST', '/v1/messages', body=canonical_bytes(payload),
                     headers={'x-api-key': broker.capability})
        response = conn.getresponse()
        assert response.status == 502
        response.read()
        conn.close()
    observation = broker.observations[0]
    assert observation['upstream_error']['type'] == 'permission_error'
    assert 'plan unavailable' in observation['upstream_error']['message']
    assert 'SENTINEL-KEY' not in str(observation)
