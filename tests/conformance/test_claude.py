from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

import pytest

from agent_subagent_router.adapters.claude import Runtime, build_invocation
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import Budgets, hash_bytes
from agent_subagent_router.protocol import decode_claude
from agent_subagent_router.supervisor import supervise
from agent_subagent_router.transport.broker import Broker


NATIVE = Path.home()/'.local/share/agent-subagent-router/runtimes/claude-2.1.277/node_modules/@anthropic-ai/claude-code-linux-x64/claude'


def fake_stream(model):
    report = {'findings': ['synthetic route check'], 'proposed_changes': [],
              'evidence_refs': [], 'uncertainties': [], 'questions': []}
    events = [{'type': 'message_start', 'message': {'id': 'msg_fake', 'type': 'message',
               'role': 'assistant', 'model': model, 'content': [], 'stop_reason': None,
               'stop_sequence': None, 'usage': {'input_tokens': 3, 'output_tokens': 0}}},
              {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}},
              {'type': 'content_block_delta', 'index': 0,
               'delta': {'type': 'text_delta', 'text': json.dumps(report)}},
              {'type': 'content_block_stop', 'index': 0},
              {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None},
               'usage': {'output_tokens': 20}}, {'type': 'message_stop'}]
    return ''.join(f'event: {e["type"]}\ndata: {json.dumps(e)}\n\n' for e in events).encode()


@pytest.mark.native
@pytest.mark.parametrize('name', ['worker', 'deep'])
def test_real_cli_wire_profile_and_isolation(tmp_path, monkeypatch, name):
    monkeypatch.setenv('ANTHROPIC_BASE_URL', 'https://foreign.invalid')
    monkeypatch.setenv('ANTHROPIC_MODEL', 'MiniMax-M3')
    monkeypatch.setenv('ANTHROPIC_AUTH_TOKEN', 'HOST-SECRET-CANARY')
    route = profile(name)
    seen = []

    def fake(path, headers, body):
        seen.append(json.loads(body))
        assert b'Codex Home Workspace Rules' not in body and b'HOST-SECRET-CANARY' not in body
        return 200, {'content-type': 'text/event-stream'}, fake_stream(route.wire_model)

    runtime = Runtime(str(NATIVE), '2.1.277', hash_bytes(NATIVE.read_bytes()))
    with Broker(route, 'FAKE-PROVIDER-SENTINEL', request_limit=1, wall_seconds=8, upstream=fake) as broker:
        invocation = build_invocation(runtime, route, tmp_path/'runtime', broker.url,
                                      broker.capability, b'Return a small JSON report.', Budgets(8, 8, 1, 200000, 200000))
        assert b'Return a small' not in str(invocation.argv).encode()
        assert 'HOST-SECRET-CANARY' not in str(invocation.env)
        assert 'FAKE-PROVIDER-SENTINEL' not in str(invocation.env)
        result = supervise(invocation, on_stop=broker.revoke)
    assert result.exit_code == 0, result.stderr
    assert len(seen) == 1 and seen[0]['output_config']['effort'] == route.effort
    assert seen[0]['thinking']['type'] in ('enabled', 'adaptive')
    assert seen[0].get('tools', []) == []
    assert broker.observations[0]['classification'] == 'IDENTITY_VERIFIED'
    assert decode_claude(result.stdout).classification == 'PARSED'
    init = next(json.loads(line) for line in result.stdout.splitlines()
                if json.loads(line).get('subtype') == 'init')
    assert init['tools'] == [] and init['mcp_servers'] == [] and init['plugins'] == []


@pytest.mark.native
def test_api_timeout_env_controls_pinned_runtime_deadline(tmp_path):
    runtime = Runtime(str(NATIVE), '2.1.277', hash_bytes(NATIVE.read_bytes()))
    route = profile('deep')
    results = {}

    for name, timeout_ms in (('short', 1000), ('long', 5000)):
        response = fake_stream(route.wire_model)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                time.sleep(3)
                try:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Content-Length', str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                except (BrokenPipeError, ConnectionError, OSError):
                    pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        budgets = Budgets(10, 10, 1, 200000, 200000)
        invocation = build_invocation(runtime, route, tmp_path/name,
            f'http://127.0.0.1:{server.server_port}', 'synthetic-capability',
            b'Return a small JSON report.', budgets)
        env = dict(invocation.env)
        env['API_TIMEOUT_MS'] = str(timeout_ms)
        results[name] = supervise(replace(invocation, env=env))
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

    assert results['short'].exit_code == 1
    assert b'Request timed out' in results['short'].stdout + results['short'].stderr
    assert results['short'].duration_seconds < 2.5
    assert results['long'].exit_code == 0
    assert results['long'].duration_seconds >= 3
