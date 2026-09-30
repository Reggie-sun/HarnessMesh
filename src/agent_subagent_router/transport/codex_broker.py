"""Owned Responses relay for explicit bounded Codex and MiniMax image routes."""

import hmac
import http.client
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import socket
import socketserver
import ssl
import threading
import time
import uuid

from ..codex_image_wire import (
    MAX_CODEX_IMAGE_TOKENS,
    map_codex_image_request,
    validate_codex_image_response,
)
from ..contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from ..image_contract import ImageTaskContract
from ..receipts import redact, redact_known_secrets
from .broker import _BoundedHandlers
from .response_secrets import validate_response_secrets
from .credentials import CodexSubscriptionCredential


_ENDPOINT_PATH = "/v1/responses"
_API_HOST = "api.openai.com"


class _BrokerFailure(RouterError):
    def __init__(self, code, status):
        super().__init__(code)
        self.http_status = status


class _UnixServer(_BoundedHandlers, socketserver.ThreadingUnixStreamServer):
    pass


class _TCPServer(_BoundedHandlers, http.server.ThreadingHTTPServer):
    pass


class _CodexUpstream:
    """Fixed HTTPS transport with no redirect, proxy, or retry behavior."""

    def __init__(self, timeout, response_limit, *, deadline=None, on_activity=None, backend='codex', profile='api-bounded'):
        if backend not in ('codex', 'minimax'):
            raise RouterError('IMAGE_ROUTE_MISMATCH')
        self.host = 'api.minimaxi.com' if backend == 'minimax' else _API_HOST
        self.path = _ENDPOINT_PATH
        if backend == 'codex' and profile == 'subscription-bounded':
            self.host, self.path = 'chatgpt.com', '/backend-api/codex/responses'
        self.timeout = timeout
        self.response_limit = response_limit
        self.deadline = deadline
        self._connection = None
        self._socket = None
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._on_activity = on_activity

    def __call__(self, path, headers, body):
        if path != self.path:
            raise RouterError("FORBIDDEN_UPSTREAM_PATH")
        try:
            timeout = self._remaining_timeout()
            connection = http.client.HTTPSConnection(
                self.host, timeout=timeout, context=ssl.create_default_context()
            )
        except RouterError:
            raise
        except Exception as exc:
            raise RouterError("TLS_SETUP_FAILED") from exc
        with self._lock:
            if self._closed.is_set():
                raise RouterError("CAPABILITY_REVOKED")
            self._connection = connection
        phase = "CONNECT"
        response = None
        try:
            connection.connect()
            connection.auto_open = 0
            with self._lock:
                if self._closed.is_set():
                    raise RouterError("CAPABILITY_REVOKED")
                transport = self._socket = connection.sock
            transport.settimeout(self._remaining_timeout())
            phase = "REQUEST_SEND"
            connection.request("POST", self.path, body=body, headers=headers)
            transport.settimeout(self._remaining_timeout())
            phase = "RESPONSE_HEADERS"
            response = connection.getresponse()
            if self._on_activity:
                self._on_activity(0)
            phase = "RESPONSE_BODY"
            data = bytearray()
            while True:
                if self._closed.is_set():
                    raise RouterError("CAPABILITY_REVOKED")
                transport.settimeout(self._remaining_timeout())
                chunk = response.read1(min(65536, self.response_limit + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if self._on_activity:
                    self._on_activity(len(chunk))
                if len(data) > self.response_limit:
                    raise RouterError("UPSTREAM_OUTPUT_LIMIT")
            kept = {}
            for key, value in response.getheaders():
                name = key.lower()
                if name not in ("content-type", "request-id", "x-request-id"):
                    continue
                if name in kept:
                    raise RouterError("IDENTITY_UNVERIFIED")
                kept[name] = value
            return response.status, kept, bytes(data)
        except RouterError:
            raise
        except Exception as exc:
            raise RouterError("OUTCOME_UNKNOWN", phase) from exc
        finally:
            if response is not None:
                response.close()
            connection.close()
            with self._lock:
                self._connection = None
                self._socket = None

    def close(self):
        self._closed.set()
        with self._lock:
            connection = self._connection
            transport = self._socket or (connection.sock if connection else None)
        if connection is not None:
            if transport is not None:
                try:
                    transport.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            connection.close()

    def _remaining_timeout(self):
        if self.deadline is None:
            return self.timeout
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RouterError("WALL_TIME_LIMIT")
        return min(self.timeout, remaining)


class CodexBroker:
    """One invocation, one capability, exact bounded request/response binding."""

    def __init__(self, task: dict, credential: str, *, upstream=None, socket_path=None,
                 before_request=None, on_observation=None, on_exchange=None):
        contract = ImageTaskContract.from_dict(task).to_dict()
        if (contract["backend"], contract["profile"]) not in (
                ('codex', 'api-bounded'), ('codex', 'subscription-bounded'), ('minimax', 'responses-bounded')):
            raise RouterError("IMAGE_ROUTE_MISMATCH")
        if not contract["selected_refs"]:
            raise RouterError("IMAGE_REF_REQUIRED")
        subscription = contract['profile'] == 'subscription-bounded'
        if subscription:
            if not isinstance(credential, CodexSubscriptionCredential):
                raise RouterError('UNSAFE_CREDENTIAL')
            self._account_id = credential.account_id
            self._credential_secrets = tuple(x.encode() for x in credential.secret_values)
            credential = credential.access_token
        else:
            if isinstance(credential, CodexSubscriptionCredential):
                raise RouterError('UNSAFE_CREDENTIAL')
            self._account_id = None
            self._credential_secrets = (credential.encode(),) if isinstance(credential, str) else ()
        if (not isinstance(credential, str) or not credential
                or (contract['backend'] == 'codex' and not subscription and (not credential.startswith('sk-') or len(credential) < 20))
                or any(ord(char) < 33 or ord(char) > 126 for char in credential)):
            raise RouterError("UNSAFE_CREDENTIAL", "provider-specific API key required")
        if upstream is None and before_request is None:
            raise RouterError("IMAGE_SEAL_RECHECK_REQUIRED")
        self.task = contract
        self._api_host = 'api.minimaxi.com' if contract['backend'] == 'minimax' else _API_HOST
        self._endpoint_path = _ENDPOINT_PATH
        if subscription:
            self._api_host, self._endpoint_path = 'chatgpt.com', '/backend-api/codex/responses'
        budgets = contract["budgets"]
        if budgets["generation_tokens"] is not None and budgets["generation_tokens"] > MAX_CODEX_IMAGE_TOKENS:
            raise RouterError("IMAGE_GENERATION_LIMIT")
        self._credential = credential
        self.capability = secrets.token_urlsafe(32)
        self._request_limit = budgets["request_limit"]
        self._payload_limit = budgets["payload_bytes"]
        self._output_limit = budgets["output_bytes"]
        self._deadline = time.monotonic() + budgets["wall_seconds"]
        self._idle_seconds = budgets["idle_seconds"]
        self._last_activity = time.monotonic()
        self._active = True
        self._inflight = False
        self._lock = threading.Lock()
        self._delivery_lock = threading.RLock()
        self._publication_lock = threading.RLock()
        self._publish_enabled = True
        self._idle = threading.Event()
        self._idle.set()
        self._observations = []
        self._frozen_observations = None
        self.rejections = []
        self._on_observation = on_observation
        self._on_exchange = on_exchange
        self._before_request = before_request
        self._upstream = upstream if upstream is not None else _CodexUpstream(
            min(budgets["wall_seconds"], budgets["idle_seconds"]),
            budgets["output_bytes"], deadline=self._deadline,
            on_activity=self._record_activity,
            backend=contract['backend'],
            profile=contract['profile'],
        )
        self._proof = "synthetic_upstream" if upstream is not None else "authenticated_endpoint_declaration"

        self._socket_path = Path(socket_path) if socket_path is not None else None
        if self._socket_path is None:
            self._server = _TCPServer(("127.0.0.1", 0), self._handler())
            self.url = f"http://127.0.0.1:{self._server.server_port}"
        else:
            self._validate_socket_path(self._socket_path)
            self._server = _UnixServer(str(self._socket_path), self._handler())
            self._socket_path.chmod(0o600)
            self.url = None
        self._server.daemon_threads = True
        self._server.handler_slots = threading.BoundedSemaphore(8)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.025},
            daemon=True,
        )

    @property
    def secret_values(self):
        return self._credential_secrets + (self.capability.encode(),)

    @staticmethod
    def _validate_socket_path(path):
        if path.exists() or path.is_symlink():
            raise RouterError("BROKER_SOCKET_EXISTS")
        try:
            parent = path.parent.lstat()
        except OSError as exc:
            raise RouterError("BROKER_SOCKET_UNSAFE") from exc
        if (path.parent.is_symlink() or not path.parent.is_dir() or parent.st_uid != os.getuid()
                or parent.st_mode & 0o077):
            raise RouterError("BROKER_SOCKET_UNSAFE")

    def _handler(self):
        broker = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def setup(self):
                super().setup()
                remaining = max(0.1, broker._deadline - time.monotonic())
                self.connection.settimeout(min(remaining, broker._idle_seconds, 10))

            def _reply(self, status, data, content_type="application/json"):
                with broker._delivery_lock:
                    if status == 200:
                        with broker._lock:
                            if not broker._active or time.monotonic() >= broker._deadline:
                                status, data = 502, b'{"error":"CAPABILITY_REVOKED"}'
                                content_type = "application/json"
                    try:
                        self.send_response(status)
                        self.send_header("Content-Type", content_type)
                        self.send_header("Content-Length", str(len(data)))
                        self.send_header("Connection", "close")
                        self.end_headers()
                        self.wfile.write(data)
                    except (BrokenPipeError, ConnectionError, OSError):
                        pass

            def do_POST(self):
                if self.path != _ENDPOINT_PATH:
                    broker._record_rejection("FORBIDDEN_PATH")
                    self._reply(404, b'{"error":"FORBIDDEN_PATH"}')
                    return
                authenticated = False
                try:
                    broker._authenticate(self.headers)
                    authenticated = True
                    if (self.headers.get("Transfer-Encoding")
                            or len(self.headers.get_all("Content-Length", [])) != 1
                            or len(self.headers.get_all("Authorization", [])) != 1
                            or len(self.headers.get_all("Content-Type", [])) != 1):
                        raise RouterError("INVALID_BODY")
                    allowed = {
                        "host", "authorization", "content-type", "content-length", "accept",
                        "accept-encoding", "connection",
                    }
                    if set(key.lower() for key in self.headers.keys()) - allowed:
                        raise RouterError("FORBIDDEN_REQUEST_HEADER")
                    content_type = self.headers.get("Content-Type", "").lower()
                    if content_type != "application/json":
                        raise RouterError("INVALID_BODY")
                    raw_length = self.headers.get("Content-Length", "")
                    if not re.fullmatch(r"[0-9]{1,10}", raw_length):
                        raise RouterError("INVALID_BODY")
                    length = int(raw_length)
                    if length < 1 or length > broker._payload_limit:
                        raise RouterError("IMAGE_PAYLOAD_LIMIT")
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise RouterError("INVALID_BODY")
                    status, headers, data = broker._forward(raw)
                    self._reply(status, data, headers.get("content-type", "application/json"))
                except RouterError as exc:
                    broker._record_rejection(exc.code)
                    if authenticated:
                        broker.revoke()
                    status = getattr(exc, "http_status", None)
                    if status is None:
                        status = 403 if exc.code == "CAPABILITY_REVOKED" else (
                            429 if exc.code == "REQUEST_BUDGET_EXHAUSTED" else (
                                413 if exc.code in ("IMAGE_PAYLOAD_LIMIT", "UPSTREAM_OUTPUT_LIMIT")
                                else 400
                            )
                        )
                    self._reply(status, canonical_bytes({"error": exc.code}))

            def do_GET(self):
                broker._record_rejection("FORBIDDEN_METHOD")
                self._reply(405, b'{"error":"FORBIDDEN_METHOD"}')

            def do_PUT(self):
                self.do_GET()

            def do_DELETE(self):
                self.do_GET()

        return Handler

    def _authenticate(self, headers):
        auth_values = headers.get_all("Authorization", [])
        if len(auth_values) != 1 or not hmac.compare_digest(
            auth_values[0], "Bearer " + self.capability
        ):
            raise RouterError("CAPABILITY_DENIED")

    def _record_activity(self, received_bytes):
        with self._lock:
            if self._active:
                self._last_activity = time.monotonic()
                if self._observations:
                    observation = self._observations[-1]
                    observation["upstream_bytes_received"] = (
                        observation.get("upstream_bytes_received", 0) + received_bytes
                    )

    def last_activity(self):
        with self._lock:
            return self._last_activity

    @property
    def observations(self):
        with self._lock:
            source = (self._frozen_observations if self._frozen_observations is not None
                      else self._observations)
            raw, _ = redact(
                canonical_bytes(source),
                self.secret_values,
            )
            return strict_json(raw)

    def _record_rejection(self, code):
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z0-9_]{1,64}", code):
            code = "REQUEST_REJECTED"
        with self._lock:
            if len(self.rejections) < 64:
                self.rejections.append(code)

    def _publish(self):
        with self._publication_lock:
            if self._on_observation is not None and self._publish_enabled:
                try:
                    self._on_observation(self.observations)
                except Exception as exc:
                    raise RouterError("OBSERVATION_WRITE_FAILED") from exc

    def _exchange(self, phase, data):
        if self._on_exchange is not None:
            try:
                self._on_exchange(phase, data)
            except Exception as exc:
                raise RouterError("EXCHANGE_RECORD_FAILED") from exc

    def _forward(self, raw):
        if not isinstance(raw, bytes) or not raw or len(raw) > self._payload_limit:
            raise RouterError("IMAGE_PAYLOAD_LIMIT")
        try:
            body = strict_json(raw)
            if type(body) is not dict:
                raise RouterError("IMAGE_PROJECTION_MISMATCH")
            if self.task['backend'] == 'minimax':
                from ..minimax_image_wire import map_minimax_image_request
                actual, proof = map_minimax_image_request(self.task, body)
            else:
                actual, proof = map_codex_image_request(self.task, body)
        except RouterError as exc:
            self._exchange('native-request-quarantined', canonical_bytes({
                'classification': exc.code, 'sha256': hash_bytes(raw), 'byte_length': len(raw)}))
            raise
        if len(actual) > self._payload_limit:
            raise RouterError("IMAGE_PAYLOAD_LIMIT")
        with self._lock:
            if not self._active or time.monotonic() >= self._deadline:
                raise RouterError("CAPABILITY_REVOKED")
            if self._inflight or len(self._observations) >= self._request_limit:
                raise RouterError("REQUEST_BUDGET_EXHAUSTED")
            self._inflight = True
            self._idle.clear()
            self._last_activity = admitted_at = time.monotonic()
            observation = {
                "attempt_id": str(uuid.uuid4()),
                "request_number": len(self._observations) + 1,
                "upstream_host": self._api_host,
                "upstream_path": self._endpoint_path,
                "model": self.task["model"],
                "effort": self.task["effort"],
                "generation_tokens": self.task["budgets"]["generation_tokens"],
                "native_wire_sha256": hash_bytes(raw),
                "native_canonical_sha256": proof["native_request_sha256"],
                "actual_request_sha256": hash_bytes(actual),
                "wire_proof": proof,
                "classification": "OUTCOME_UNKNOWN",
            }
            self._observations.append(observation)
        try:
            self._publish()
            if self._before_request is not None:
                try:
                    self._before_request()
                except RouterError as exc:
                    raise _BrokerFailure(exc.code, 409) from exc
                except Exception as exc:
                    raise _BrokerFailure("SOURCE_CHECK_FAILED", 409) from exc
            with self._lock:
                if not self._active or time.monotonic() >= self._deadline:
                    raise RouterError("CAPABILITY_REVOKED")
            self._exchange("native-request", raw)
            self._exchange("request", actual)
            upstream_headers = {
                "Authorization": "Bearer " + self._credential,
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            if self._account_id is not None:
                upstream_headers['ChatGPT-Account-ID'] = self._account_id
            with self._lock:
                if not self._active or time.monotonic() >= self._deadline:
                    raise RouterError("CAPABILITY_REVOKED")
                observation["wire_started"] = True
            status, response_headers, response = self._upstream(
                self._endpoint_path, upstream_headers, actual
            )
            observation["http_status"] = status
            if not isinstance(response, bytes) or len(response) > self._output_limit:
                raise RouterError("UPSTREAM_OUTPUT_LIMIT")
            try:
                if 300 <= status < 400:
                    raise RouterError('UPSTREAM_REDIRECT')
                if status != 200:
                    code = 'CREDENTIAL_OR_ENTITLEMENT_REJECTED' if status in (401, 403) else 'UPSTREAM_HTTP_ERROR'
                    raise RouterError(code)
                response_secrets = self.secret_values
                validate_response_secrets(response_headers, response, response_secrets)
                if status == 200:
                    if self.task['backend'] == 'minimax':
                        from ..minimax_image_wire import validate_minimax_image_response
                        response_proof = validate_minimax_image_response(self.task, response_headers, response)
                    else:
                        response_proof = validate_codex_image_response(self.task, response_headers, response)
                    _, reflected = redact_known_secrets(response_proof['text'].encode(), response_secrets)
                    if reflected:
                        raise RouterError('UPSTREAM_SECRET_REFLECTION')
            except RouterError as exc:
                diagnostic = {}
                if self.task['backend'] == 'minimax':
                    from ..minimax_image_wire import RESPONSE_ISSUES
                    if type(exc.detail) is str and exc.detail in RESPONSE_ISSUES:
                        diagnostic['response_issue'] = exc.detail
                        with self._lock:
                            observation.update(diagnostic)
                self._exchange('response-quarantined', canonical_bytes({
                    'classification': exc.code, 'sha256': hash_bytes(response),
                    'byte_length': len(response), **diagnostic}))
                raise
            self._exchange('response', response)
            with self._lock:
                if not self._active or time.monotonic() >= self._deadline:
                    raise RouterError("CAPABILITY_REVOKED")
            if 300 <= status < 400:
                raise RouterError("UPSTREAM_REDIRECT")
            if status != 200:
                code = "CREDENTIAL_OR_ENTITLEMENT_REJECTED" if status in (401, 403) else "UPSTREAM_HTTP_ERROR"
                raise RouterError(code)
            with self._lock:
                if not self._active or time.monotonic() >= self._deadline:
                    raise RouterError("CAPABILITY_REVOKED")
                observation.update({
                    "classification": "IDENTITY_VERIFIED",
                    "response_sha256": hash_bytes(response),
                    "response_output_sha256": hash_bytes(response_proof['text'].encode('utf-8')),
                    "response_request_id": response_proof["request_id"],
                    "response_id": response_proof["response_id"],
                    "response_model": response_proof["model"],
                    "response_max_output_tokens": response_proof["max_output_tokens"],
                    "usage": response_proof["usage"],
                    "duration_seconds": time.monotonic() - admitted_at,
                })
                from ..minimax_image_wire import RESPONSE_IDENTITY_SPEC_SHA
                if self.task['backend'] == 'minimax' and any(
                        ref['sha256'] == RESPONSE_IDENTITY_SPEC_SHA
                        for ref in self.task['selected_refs']):
                    observation['response_request_id_source'] = response_proof.get('request_id_source', 'header')
                    observation['response_identity_headers'] = {
                        name.lower(): (value.split(';', 1)[0].strip().lower()
                                       if name.lower() == 'content-type' else value)
                        for name, value in response_headers.items()
                        if name.lower() in ('content-type', 'x-request-id', 'request-id')}
            self._publish()
            return 200, {"content-type": response_headers.get("content-type", "application/json")}, response
        except RouterError as exc:
            with self._lock:
                observation["classification"] = exc.code
                observation["duration_seconds"] = time.monotonic() - admitted_at
            self.revoke()
            try:
                self._publish()
            except RouterError:
                pass
            if isinstance(exc, _BrokerFailure):
                raise
            if observation.get("wire_started"):
                raise _BrokerFailure(exc.code, 502) from exc
            raise
        except Exception as exc:
            with self._lock:
                observation["classification"] = "OUTCOME_UNKNOWN"
                observation["duration_seconds"] = time.monotonic() - admitted_at
            self.revoke()
            try:
                self._publish()
            except RouterError:
                pass
            raise _BrokerFailure("OUTCOME_UNKNOWN", 502) from exc
        finally:
            with self._lock:
                self._inflight = False
            self._idle.set()

    def __enter__(self):
        self._thread.start()
        return self

    def revoke(self):
        with self._delivery_lock:
            with self._lock:
                self._active = False
        if hasattr(self._upstream, "close"):
            self._upstream.close()

    def __exit__(self, *_args):
        self.revoke()
        self._server.shutdown()
        self._server.server_close()
        if self._socket_path is not None:
            self._socket_path.unlink(missing_ok=True)
        self._thread.join(timeout=1)
        self._idle.wait(0.5)
        if not self._publication_lock.acquire(timeout=0.25):
            raise RouterError("OBSERVATION_DRAIN_TIMEOUT", "receipt must remain incomplete")
        try:
            self._publish_enabled = False
            with self._lock:
                self._frozen_observations = json.loads(json.dumps(self._observations))
                if self._inflight:
                    for observation in self._frozen_observations:
                        observation["classification"] = "OUTCOME_UNKNOWN"
        finally:
            self._publication_lock.release()
