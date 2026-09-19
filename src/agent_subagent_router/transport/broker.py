"""Invocation-local admission, fixed TLS upstream, no routing or fallback."""
import hashlib
import hmac
import http.client
import http.server
import json
import math
from pathlib import Path
import secrets
import socket
import socketserver
import ssl
import threading
import time
import uuid

from ..contracts import RouterError, canonical_bytes, strict_json
from ..receipts import redact
from .identity import validate_request, validate_response


class _BoundedHandlers:
    """Bound pre-authentication connections as well as generation admissions."""
    def process_request(self, request, address):
        if not self.handler_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.handler_slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.handler_slots.release()


class _UnixServer(_BoundedHandlers, socketserver.ThreadingUnixStreamServer):
    pass


class _TCPServer(_BoundedHandlers, http.server.ThreadingHTTPServer):
    pass


class KimiUpstream:
    """No redirects, environment proxies, arbitrary host/path or SDK retries."""
    def __init__(self, timeout: float, response_limit: int = 16*1024*1024):
        self.timeout = timeout
        self.response_limit = response_limit
        self._connection = None
        self._lock = threading.Lock()
        self._closed = threading.Event()

    def __call__(self, path, headers, body):
        if path not in ('/v1/messages', '/v1/messages?beta=true'):
            raise RouterError('FORBIDDEN_UPSTREAM_PATH')
        connection = http.client.HTTPSConnection('api.kimi.ai', timeout=self.timeout,
                                                 context=ssl.create_default_context())
        with self._lock:
            if self._closed.is_set():
                raise RouterError('CAPABILITY_REVOKED')
            self._connection = connection
        try:
            connection.connect()
            # Never reconnect automatically if cancellation closes the connected socket.
            connection.auto_open = 0
            if self._closed.is_set():
                raise RouterError('CAPABILITY_REVOKED')
            connection.request('POST', '/coding'+path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read(self.response_limit+1)
            if len(data) > self.response_limit:
                raise RouterError('UPSTREAM_OUTPUT_LIMIT')
            kept = {name: value for name, value in response.getheaders()
                    if name.lower() in ('content-type', 'request-id', 'x-request-id')}
            return response.status, {k.lower(): v for k, v in kept.items()}, data
        finally:
            connection.close()
            with self._lock:
                self._connection = None

    def close(self):
        self._closed.set()
        connection = self._connection
        if connection is not None:
            if connection.sock:
                try:
                    connection.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            connection.close()


class Broker:
    def __init__(self, profile, credential: str, *, request_limit: int, wall_seconds: float,
                 upstream=None, allowed_tools=(), on_observation=None, socket_path=None):
        if request_limit < 1 or wall_seconds <= 0:
            raise RouterError('INVALID_BUDGET')
        self.profile = profile
        self._credential = credential
        self.capability = secrets.token_urlsafe(32)
        self._limit = request_limit
        self._deadline = time.monotonic()+wall_seconds
        self._upstream = upstream if upstream is not None else KimiUpstream(wall_seconds)
        self._proof = 'synthetic_upstream' if upstream is not None else 'authenticated_endpoint_declaration'
        self.allowed_tools = tuple(allowed_tools)
        self._active = True
        self._inflight = False
        self._lock = threading.Lock()
        self._observations = []
        self._frozen_observations = None
        self._publication_lock = threading.RLock()
        self._publish_enabled = True
        self._idle = threading.Event()
        self._idle.set()
        self._on_observation = on_observation
        broker = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def setup(self):
                super().setup()
                self.connection.settimeout(min(wall_seconds, 10))

            def reply(self, status, data, content_type='application/json'):
                try:
                    self.send_response(status)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionError, OSError):
                    pass

            def do_POST(self):
                if self.path not in ('/v1/messages', '/v1/messages?beta=true'):
                    self.reply(404, b'{"error":"FORBIDDEN_PATH"}')
                    return
                auth = self.headers.get('Authorization', '')
                key = self.headers.get('x-api-key', '')
                if not (hmac.compare_digest(auth, 'Bearer '+broker.capability)
                        or hmac.compare_digest(key, broker.capability)):
                    self.reply(403, b'{"error":"CAPABILITY_DENIED"}')
                    return
                if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                    self.reply(400, b'{"error":"INVALID_BODY"}')
                    return
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 8*1024*1024:
                        raise ValueError()
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise ValueError()
                    body = strict_json(raw)
                    validate_request(broker.profile, body, allowed_tools=broker.allowed_tools)
                except (ValueError, OSError, RouterError) as exc:
                    code = exc.code if isinstance(exc, RouterError) else 'INVALID_BODY'
                    broker._record_rejection(code)
                    self.reply(400, canonical_bytes({'error': code}))
                    return
                with broker._lock:
                    if not broker._active or time.monotonic() >= broker._deadline:
                        self.reply(403, b'{"error":"CAPABILITY_REVOKED"}')
                        return
                    if broker._inflight or len(broker._observations) >= broker._limit:
                        self.reply(429, b'{"error":"REQUEST_BUDGET_EXHAUSTED"}')
                        return
                    broker._inflight = True
                    broker._idle.clear()
                    observation = {'attempt_id': str(uuid.uuid4()),
                                   'request_number': len(broker._observations)+1,
                                   'upstream_host': 'api.kimi.ai',
                                   'request_model': body['model'], 'thinking': body['thinking'],
                                   'effort': body['output_config']['effort'],
                                   'request_sha256': hashlib.sha256(raw).hexdigest(),
                                   'classification': 'OUTCOME_UNKNOWN'}
                    broker._observations.append(observation)
                try:
                    broker._publish()
                    with broker._lock:
                        if not broker._active or time.monotonic() >= broker._deadline:
                            raise RouterError('CAPABILITY_REVOKED')
                    remaining_seconds = max(1, math.ceil(broker._deadline-time.monotonic()))
                    headers = {'x-api-key': broker._credential, 'content-type': 'application/json',
                               'anthropic-version': '2023-06-01', 'accept': 'text/event-stream',
                               'x-stainless-timeout': str(remaining_seconds)}
                    # Beta features are explicit profile policy, never arbitrary forwarded headers.
                    status, upstream_headers, data = broker._upstream(self.path, headers, raw)
                    observation['http_status'] = status
                    if status != 200:
                        try:
                            error = strict_json(data).get('error', {})
                            if isinstance(error, dict):
                                diagnostic = {key: value for key in ('type', 'code', 'message')
                                              if isinstance(value := error.get(key), str)}
                                # Redact before truncation so partial secrets cannot escape.
                                safe, _ = redact(canonical_bytes(diagnostic),
                                    (broker._credential.encode(), broker.capability.encode()))
                                observation['upstream_error'] = {
                                    key: value[:1024] for key, value in strict_json(safe).items()}
                        except (RouterError, AttributeError):
                            pass
                    if 300 <= status < 400:
                        raise RouterError('UPSTREAM_REDIRECT')
                    if status in (401, 403):
                        raise RouterError('CREDENTIAL_OR_ENTITLEMENT_REJECTED')
                    if status != 200:
                        raise RouterError('UPSTREAM_HTTP_ERROR')
                    observation.update(validate_response(broker.profile, upstream_headers, data))
                    observation['proof'] = broker._proof
                    with broker._lock:
                        active = broker._active and time.monotonic() < broker._deadline
                    if not active:
                        raise RouterError('OUTCOME_UNKNOWN', 'revoked before delivery')
                    self.reply(200, data, upstream_headers.get('content-type', 'application/json'))
                except RouterError as exc:
                    observation['classification'] = exc.code
                    self.reply(502, canonical_bytes({'error': exc.code}))
                except Exception:
                    observation['classification'] = 'OUTCOME_UNKNOWN'
                    self.reply(502, b'{"error":"OUTCOME_UNKNOWN"}')
                finally:
                    with broker._lock:
                        broker._inflight = False
                    try:
                        broker._publish()
                    finally:
                        broker._idle.set()

        self._socket_path = Path(socket_path) if socket_path is not None else None
        if self._socket_path is not None:
            if self._socket_path.exists() or self._socket_path.is_symlink():
                raise RouterError('BROKER_SOCKET_EXISTS')
            self._server = _UnixServer(str(self._socket_path), Handler)
            self._socket_path.chmod(0o600)
            self.url = None
        else:
            self._server = _TCPServer(('127.0.0.1', 0), Handler)
            self.url = f'http://127.0.0.1:{self._server.server_port}'
        self._server.daemon_threads = True
        self._server.handler_slots = threading.BoundedSemaphore(8)
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        kwargs={'poll_interval': .025}, daemon=True)
        self.rejections = []

    def _record_rejection(self, code):
        with self._lock:
            if len(self.rejections) < 64:
                self.rejections.append(code)

    def _publish(self):
        with self._publication_lock:
            if self._on_observation and self._publish_enabled:
                data, _ = redact(canonical_bytes(self.observations),
                                 (self._credential.encode(), self.capability.encode()))
                self._on_observation(strict_json(data))

    @property
    def observations(self):
        with self._lock:
            source = self._frozen_observations if self._frozen_observations is not None else self._observations
            return json.loads(json.dumps(source))

    def __enter__(self):
        self._thread.start()
        return self

    def revoke(self):
        with self._lock:
            self._active = False
        if hasattr(self._upstream, 'close'):
            self._upstream.close()

    def __exit__(self, *args):
        self.revoke()
        self._server.shutdown()
        self._server.server_close()
        if self._socket_path is not None:
            self._socket_path.unlink(missing_ok=True)
        self._thread.join(timeout=1)
        self._idle.wait(.5)
        if not self._publication_lock.acquire(timeout=.25):
            raise RouterError('OBSERVATION_DRAIN_TIMEOUT', 'receipt must remain incomplete')
        try:
            self._publish_enabled = False
            with self._lock:
                self._frozen_observations = json.loads(json.dumps(self._observations))
                if self._inflight:
                    for observation in self._frozen_observations:
                        observation['classification'] = 'OUTCOME_UNKNOWN'
        finally:
            self._publication_lock.release()
