import hashlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_subagent_router.contracts import canonical_bytes, strict_json


_ADAPTER = Path(__file__).parents[2] / "src/agent_subagent_router/adapters/image_minimax.py"
_SPEC = importlib.util.spec_from_file_location("image_minimax_standalone", _ADAPTER)
_RUNNER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_RUNNER)


class _FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    def read(self, *args):
        return self.body


class _FakeConnection:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.closed = False

    def request(self, method, path, *, body, headers):
        self.calls.append((method, path, body, headers))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


def _invoke(monkeypatch, request, fake):
    stdout = io.BytesIO()
    stderr = io.StringIO()
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:18765")
    monkeypatch.setenv("IMAGE_ROUTE_CAPABILITY", "opaque-local-capability")
    monkeypatch.setattr(_RUNNER.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(request)))
    monkeypatch.setattr(_RUNNER.sys, "stdout", SimpleNamespace(buffer=stdout))
    monkeypatch.setattr(_RUNNER.sys, "stderr", stderr)
    monkeypatch.setattr(_RUNNER.http.client, "HTTPConnection", fake)
    return stdout, stderr


def test_runner_posts_once_to_fixed_loopback_and_emits_hash_bound_envelope(monkeypatch):
    request = canonical_bytes({"model": "MiniMax-M3", "input": []})
    response = canonical_bytes({"object": "response", "status": "completed"})
    connections = []

    def connection(host, port, *, timeout):
        instance = _FakeConnection(_FakeResponse(200, response))
        connections.append((host, port, timeout, instance))
        return instance

    stdout, stderr = _invoke(monkeypatch, request, connection)

    assert _RUNNER.main() == 0
    assert stderr.getvalue() == ""
    assert len(connections) == 1
    host, port, timeout, fake = connections[0]
    assert (host, port, timeout) == ("127.0.0.1", 18765, 180)
    assert len(fake.calls) == 1
    method, path, body, headers = fake.calls[0]
    assert (method, path, body) == ("POST", "/v1/responses", request)
    assert headers["Authorization"] == "Bearer opaque-local-capability"
    assert fake.closed
    assert strict_json(stdout.getvalue()) == {
        "schema": "minimax-image-runtime/v1",
        "status": "completed",
        "request_sha256": hashlib.sha256(request).hexdigest(),
        "response_sha256": hashlib.sha256(response).hexdigest(),
        "response": strict_json(response),
    }


@pytest.mark.parametrize(
    ("http_status", "response"),
    [
        (503, {"status": "completed", "error": {"message": "secret body"}}),
        (200, {"status": "incomplete", "error": None}),
    ],
)
def test_runner_fails_once_without_printing_upstream_body(monkeypatch, http_status, response):
    request = canonical_bytes({"model": "MiniMax-M3"})
    raw_response = canonical_bytes(response)
    instances = []

    def connection(*args, **kwargs):
        instance = _FakeConnection(_FakeResponse(http_status, raw_response))
        instances.append(instance)
        return instance

    stdout, stderr = _invoke(monkeypatch, request, connection)

    assert _RUNNER.main() == 1
    assert len(instances) == 1 and len(instances[0].calls) == 1
    assert stdout.getvalue() == b""
    assert b"secret body" not in stderr.getvalue().encode()
    assert "failed" in stderr.getvalue().lower()
    assert instances[0].closed


def test_runner_rejects_wrong_base_url_before_network(monkeypatch):
    request = canonical_bytes({"model": "MiniMax-M3"})
    stdout = io.BytesIO()
    stderr = io.StringIO()
    calls = []
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:18765/v1")
    monkeypatch.setenv("IMAGE_ROUTE_CAPABILITY", "opaque-local-capability")
    monkeypatch.setattr(_RUNNER.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(request)))
    monkeypatch.setattr(_RUNNER.sys, "stdout", SimpleNamespace(buffer=stdout))
    monkeypatch.setattr(_RUNNER.sys, "stderr", stderr)
    monkeypatch.setattr(_RUNNER.http.client, "HTTPConnection", lambda *a, **k: calls.append(a))

    assert _RUNNER.main() == 1
    assert calls == [] and stdout.getvalue() == b""
    assert "failed" in stderr.getvalue().lower()
