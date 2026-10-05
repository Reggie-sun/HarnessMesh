import http.client
import io
import json
import socket
import ssl
from email.message import Message
from types import SimpleNamespace

import pytest

from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import RouterError, canonical_bytes
from agent_subagent_router.transport.broker import Broker, KimiUpstream
from agent_subagent_router.transport.diagnostics import failure_diagnostic


def failing_connection(monkeypatch, operation, error, status=200):
    calls = []

    def step(name, result=None):
        def run(*args, **kwargs):
            calls.append(name)
            if name == operation:
                raise error
            return result
        return run

    response = SimpleNamespace(status=status, read1=step('read1', b''),
                               getheaders=step('getheaders', []))
    connection = SimpleNamespace(connect=step('connect'), request=step('request'),
        getresponse=step('getresponse', response), close=step('close'))
    monkeypatch.setattr(http.client, 'HTTPSConnection', lambda *a, **k: connection)
    return calls


@pytest.mark.parametrize('operation,phase', [
    ('connect', 'CONNECT'), ('request', 'REQUEST_SEND'),
    ('getresponse', 'RESPONSE_HEADERS'), ('read1', 'RESPONSE_BODY'),
])
@pytest.mark.parametrize('error,kind', [
    (socket.gaierror(-2, 'secret-host'), 'DNS_ERROR'),
    (ssl.SSLError('private-key'), 'TLS_ERROR'),
    (TimeoutError('private-key'), 'TIMEOUT'),
    (ConnectionResetError('private-key'), 'CONNECTION_ERROR'),
    (http.client.IncompleteRead(b'private-response', 100), 'INCOMPLETE_RESPONSE'),
    (RuntimeError('private-key request-body /host/secret'), 'UNEXPECTED_ERROR'),
])
def test_upstream_errors_have_safe_phase_and_kind(monkeypatch, operation, phase, error, kind):
    calls = failing_connection(monkeypatch, operation, error)
    with pytest.raises(RouterError, match='OUTCOME_UNKNOWN') as caught:
        KimiUpstream(5)('/v1/messages', {'x-api-key': 'private-key'}, b'private-body')
    failure = caught.value
    assert {key: failure.diagnostic[key] for key in ('phase', 'kind')} == {
        'phase': phase, 'kind': kind}
    assert ('response_progress' in failure.diagnostic) == (operation == 'read1')
    assert failure.http_status == (200 if operation == 'read1' else None)
    assert 'private' not in str(failure) + str(failure.diagnostic)
    assert calls[-1] == 'close'
    assert calls.count(operation) == 1


def test_tls_setup_failure_is_recorded_without_paths(monkeypatch):
    def context():
        raise OSError('private-key /host/certificates')

    monkeypatch.setattr(ssl, 'create_default_context', context)
    with pytest.raises(RouterError, match='OUTCOME_UNKNOWN') as caught:
        KimiUpstream(5)('/v1/messages', {}, b'{}')
    assert caught.value.diagnostic == {'phase': 'TLS_SETUP', 'kind': 'OS_ERROR'}
    assert caught.value.http_status is None


def test_exception_text_is_never_evaluated(monkeypatch):
    class UnsafeError(RuntimeError):
        def __str__(self):
            raise AssertionError('exception text must not be accessed')

    failing_connection(monkeypatch, 'connect', UnsafeError())
    with pytest.raises(RouterError, match='OUTCOME_UNKNOWN') as caught:
        KimiUpstream(5)('/v1/messages', {}, b'{}')
    assert caught.value.diagnostic == {'phase': 'CONNECT', 'kind': 'UNEXPECTED_ERROR'}


def test_known_control_error_preserves_classification(monkeypatch):
    calls = failing_connection(monkeypatch, 'read1', RouterError('CAPABILITY_REVOKED'))
    with pytest.raises(RouterError, match='CAPABILITY_REVOKED') as caught:
        KimiUpstream(5)('/v1/messages', {}, b'{}')
    assert not hasattr(caught.value, 'diagnostic')
    assert calls[-1] == 'close'


def dispatch_without_socket(monkeypatch, upstream, on_observation=None):
    # Exercise the actual HTTP handler/admission/publication path without a listener.
    def server(address, handler):
        return SimpleNamespace(server_port=18765, handler=handler,
                               serve_forever=lambda **kwargs: None)

    monkeypatch.setattr('agent_subagent_router.transport.broker._TCPServer', server)
    broker = Broker(profile('worker'), 'private-key', request_limit=1, wall_seconds=5,
                    upstream=upstream, on_observation=on_observation)
    raw = canonical_bytes({'model': 'k3-256k', 'thinking': {'type': 'adaptive'},
                           'output_config': {'effort': 'high'}, 'messages': [], 'tools': []})
    handler = object.__new__(broker._server.handler)
    handler.path = '/v1/messages'
    handler.headers = Message()
    handler.headers['x-api-key'] = broker.capability
    handler.headers['Content-Length'] = str(len(raw))
    handler.rfile = io.BytesIO(raw)
    replies = []
    handler.reply = lambda status, data, *args: replies.append((status, data))
    handler.do_POST()
    return broker, replies


def test_partial_response_preserves_upstream_status_in_published_failure(monkeypatch):
    failing_connection(monkeypatch, 'read1', http.client.IncompleteRead(b'private-key', 100), 503)
    published = []
    broker, replies = dispatch_without_socket(monkeypatch, KimiUpstream(5), published.append)
    assert replies == [(502, b'{"error":"OUTCOME_UNKNOWN"}')]
    observed = broker.observations[0]
    assert observed['http_status'] == 503
    assert observed['transport_error']['phase'] == 'RESPONSE_BODY'
    assert observed['transport_error']['kind'] == 'INCOMPLETE_RESPONSE'
    assert observed['transport_error']['response_progress']['received_bytes'] == 0
    assert observed['classification'] == 'OUTCOME_UNKNOWN'
    assert 'proof' not in observed and 'usage' not in observed
    assert published[-1][0] == observed
    assert 'private-key' not in json.dumps(published)


def test_broker_internal_error_is_distinct_and_never_dispatches(monkeypatch):
    published, calls = [], []

    def publish(value):
        published.append(value)
        if len(published) == 1:
            raise RuntimeError('private-key /host/secret')

    broker, replies = dispatch_without_socket(monkeypatch, lambda *a: calls.append(a), publish)
    assert not calls
    assert replies == [(502, b'{"error":"OUTCOME_UNKNOWN"}')]
    assert broker._active is False
    assert broker.observations[0]['broker_error'] == {
        'phase': 'ADMISSION_RECORD', 'kind': 'UNEXPECTED_ERROR'}
    assert 'http_status' not in broker.observations[0]
    assert 'private-key' not in json.dumps(published)


def test_real_http_failure_is_distinct_from_broker_generated_502(monkeypatch):
    calls = []

    def upstream(*args):
        calls.append(1)
        return 502, {}, canonical_bytes({'error': {'type': 'server_error',
                                                  'message': 'private-key'}})

    broker, replies = dispatch_without_socket(monkeypatch, upstream)
    observed = broker.observations[0]
    assert replies == [(502, b'{"error":"UPSTREAM_HTTP_ERROR"}')]
    assert observed['classification'] == 'UPSTREAM_HTTP_ERROR'
    assert observed['http_status'] == 502
    assert 'transport_error' not in observed and 'broker_error' not in observed
    assert 'private-key' not in json.dumps(observed)
    assert calls == [1]


@pytest.mark.parametrize('error,detail', [
    (ConnectionResetError('private-key'), 'CONNECTION_RESET'),
    (ConnectionAbortedError('private-key'), 'CONNECTION_ABORTED'),
    (BrokenPipeError('private-key'), 'BROKEN_PIPE'),
    (http.client.RemoteDisconnected('private-key'), 'REMOTE_DISCONNECTED'),
])
def test_connection_failure_detail_is_fixed_not_exception_text(error, detail):
    diagnostic = failure_diagnostic('RESPONSE_BODY', error)
    assert diagnostic == {'phase': 'RESPONSE_BODY', 'kind': 'CONNECTION_ERROR',
                          'detail': detail}
    assert 'private-key' not in json.dumps(diagnostic)


def test_body_reset_records_received_progress_without_releasing_partial_bytes(monkeypatch):
    now = [0.0]
    monkeypatch.setattr('agent_subagent_router.transport.broker.time.monotonic', lambda: now[0])
    chunks = iter([b'private-response', b'more-private-response'])

    def read1(_limit):
        try:
            chunk = next(chunks)
        except StopIteration:
            now[0] += 300
            raise ConnectionResetError('private-key')
        now[0] += 2
        return chunk

    def getresponse():
        now[0] += 25
        return SimpleNamespace(status=200, read1=read1, getheaders=lambda: [])

    connection = SimpleNamespace(connect=lambda: None, request=lambda *a, **k: None,
                                 getresponse=getresponse, close=lambda: None)
    monkeypatch.setattr(http.client, 'HTTPSConnection', lambda *a, **k: connection)
    with pytest.raises(RouterError, match='OUTCOME_UNKNOWN') as caught:
        KimiUpstream(3600)('/v1/messages', {'x-api-key': 'private-key'}, b'private-body')
    assert caught.value.diagnostic == {
        'phase': 'RESPONSE_BODY', 'kind': 'CONNECTION_ERROR', 'detail': 'CONNECTION_RESET',
        'response_progress': {'headers_seconds': 25.0, 'body_seconds': 304.0,
                              'received_bytes': 37, 'chunks_received': 2,
                              'last_byte_age_seconds': 300.0, 'max_read_wait_seconds': 300.0}}
    assert 'private' not in json.dumps(caught.value.diagnostic)
