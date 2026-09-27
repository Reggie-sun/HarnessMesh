from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import pytest

from agent_subagent_router.adapters.claude import build_invocation
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import Budgets
from agent_subagent_router.protocol import decode_claude
from agent_subagent_router.runtime_config import installed_runtime
from agent_subagent_router.supervisor import supervise
from agent_subagent_router.transport.broker import Broker
from test_claude import fake_stream


@pytest.mark.native
@pytest.mark.parametrize('progress,wrong_model', [(True, False), (False, False), (True, True)])
def test_buffered_upstream_activity_reaches_supervisor_without_bypassing_identity(
        tmp_path, monkeypatch, progress, wrong_model):
    response = fake_stream('wrong-model' if wrong_model else 'k3-256k')
    ping = b'event: ping\ndata: {"type":"ping"}\n\n'
    finished = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Content-Length', str(len(ping)*12+len(response)))
                self.end_headers()
                for _ in range(12):
                    self.wfile.write(ping)
                    self.wfile.flush()
                    time.sleep(.18 if progress else 1.5)
                self.wfile.write(response)
            except (BrokenPipeError, ConnectionError, OSError):
                pass
            finally:
                finished.set()

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Exercise the real bounded upstream reader against a local fake transport.
    monkeypatch.setattr('http.client.HTTPSConnection',
        lambda *a, **k: HTTPConnection('127.0.0.1', server.server_port, timeout=5))
    try:
        with Broker(profile('worker'), 'FAKE-KEY', request_limit=1, wall_seconds=8) as broker:
            invocation = build_invocation(installed_runtime(), profile('worker'), tmp_path/'runtime',
                broker.url, broker.capability, b'Return the JSON report.', Budgets(8, 1, 1, 200000, 100000))
            result = supervise(invocation, on_stop=broker.revoke, last_activity=broker.last_activity)
        observed = broker.observations[0]
        assert observed['upstream_bytes_received'] > 0
        if not progress:
            assert result.reason == 'idle_timeout'
            assert observed['classification'] != 'IDENTITY_VERIFIED'
        elif wrong_model:
            assert observed['classification'] == 'ROUTE_MISMATCH'
            assert decode_claude(result.stdout).classification != 'PARSED'
        else:
            assert result.reason == 'exited' and result.exit_code == 0
            assert decode_claude(result.stdout).classification == 'PARSED'
            assert result.duration_seconds > 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(1)
        finished.wait(2)
