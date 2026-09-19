"""Fixed Gemini REST admission translated to Code Assist streaming requests."""
import hashlib
import hmac
import http.client
import http.server
import json
import os
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
from .broker import _BoundedHandlers


MODEL = 'gemini-3.5-flash'
REST_PATH = '/v1beta/models/gemini-3.5-flash:streamGenerateContent?alt=sse'
_CODE_ASSIST_PATH = '/v1internal:streamGenerateContent?alt=sse'
_ALLOWED_TOOLS = {'read_file', 'glob', 'list_directory'}


class _UnixServer(_BoundedHandlers, socketserver.ThreadingUnixStreamServer):
    pass


class GeminiUpstream:
    def __init__(self, timeout: float, response_limit: int = 16*1024*1024):
        self.timeout, self.response_limit = timeout, response_limit
        self._connection = None
        self._closed = threading.Event()
        self._lock = threading.Lock()

    def __call__(self, path: str, headers: dict, body: bytes):
        if path != _CODE_ASSIST_PATH:
            raise RouterError('FORBIDDEN_UPSTREAM_PATH')
        connection = http.client.HTTPSConnection('cloudcode-pa.googleapis.com', timeout=self.timeout,
                                                 context=ssl.create_default_context())
        with self._lock:
            if self._closed.is_set():
                raise RouterError('CAPABILITY_REVOKED')
            self._connection = connection
        try:
            connection.connect()
            connection.auto_open = 0
            if self._closed.is_set():
                raise RouterError('CAPABILITY_REVOKED')
            connection.request('POST', path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(self.response_limit+1)
            if len(raw) > self.response_limit:
                raise RouterError('UPSTREAM_OUTPUT_LIMIT')
            return response.status, {key.lower(): value for key, value in response.getheaders()}, raw
        except (OSError, http.client.HTTPException) as exc:
            raise RouterError('UPSTREAM_TRANSPORT_ERROR') from exc
        finally:
            connection.close()
            with self._lock:
                self._connection = None

    def close(self) -> None:
        self._closed.set()
        connection = self._connection
        if connection is not None and connection.sock:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()


def _validate_request(value) -> dict:
    allowed = {'contents', 'systemInstruction', 'tools', 'toolConfig', 'safetySettings', 'generationConfig'}
    if not isinstance(value, dict) or set(value) - allowed or not isinstance(value.get('contents'), list):
        raise RouterError('ROUTE_MISMATCH', 'fixed Gemini request schema')
    tools = value.get('tools', [])
    if not isinstance(tools, list):
        raise RouterError('TOOL_POLICY_VIOLATION')
    for tool in tools:
        if not isinstance(tool, dict) or set(tool) != {'functionDeclarations'}:
            raise RouterError('TOOL_POLICY_VIOLATION')
        declarations = tool.get('functionDeclarations')
        if not isinstance(declarations, list):
            raise RouterError('TOOL_POLICY_VIOLATION')
        for declaration in declarations:
            if not isinstance(declaration, dict) or declaration.get('name') not in _ALLOWED_TOOLS:
                raise RouterError('TOOL_POLICY_VIOLATION')
    def prohibited(node):
        if isinstance(node, dict):
            if {'fileData', 'inlineData', 'googleSearch', 'urlContext', 'codeExecution'} & set(node):
                return True
            return any(prohibited(item) for item in node.values())
        return isinstance(node, list) and any(prohibited(item) for item in node)
    if prohibited(value):
        raise RouterError('TOOL_POLICY_VIOLATION')
    return value


def _sse_events(raw: bytes) -> list[dict]:
    events, lines = [], []
    for line in raw.replace(b'\r\n', b'\n').split(b'\n'):
        if line.startswith(b'data:'):
            lines.append(line[5:].lstrip())
        elif not line:
            if lines:
                value = strict_json(b'\n'.join(lines))
                if not isinstance(value, dict):
                    raise RouterError('UPSTREAM_PROTOCOL_ERROR')
                events.append(value)
                lines = []
        else:
            raise RouterError('UPSTREAM_PROTOCOL_ERROR')
    if lines:
        raise RouterError('UPSTREAM_PROTOCOL_ERROR', 'truncated SSE')
    if not events:
        raise RouterError('IDENTITY_UNVERIFIED')
    return events


def _to_rest(raw: bytes) -> tuple[bytes, str, str]:
    outputs, trace, model, terminal = [], None, None, False
    for event in _sse_events(raw):
        current_trace, response = event.get('traceId'), event.get('response')
        if not isinstance(response, dict):
            raise RouterError('UPSTREAM_PROTOCOL_ERROR')
        if current_trace is not None:
            if not isinstance(current_trace, str) or not current_trace or trace not in (None, current_trace):
                raise RouterError('IDENTITY_UNVERIFIED', 'Code Assist trace')
            trace = current_trace
        current_model = response.get('modelVersion')
        if current_model is not None:
            if not isinstance(current_model, str) or current_model != MODEL or model not in (None, current_model):
                raise RouterError('IDENTITY_UNVERIFIED', 'Code Assist model version')
            model = current_model
        candidates = response.get('candidates')
        if candidates is not None:
            if not isinstance(candidates, list) or any(not isinstance(item, dict) for item in candidates):
                raise RouterError('UPSTREAM_PROTOCOL_ERROR')
            terminal = terminal or any(isinstance(item.get('finishReason'), str) and item['finishReason']
                                       for item in candidates)
        mapped = {key: response[key] for key in ('candidates', 'automaticFunctionCallingHistory', 'usageMetadata',
                                                  'modelVersion', 'promptFeedback')
                  if key in response}
        if current_trace is not None:
            mapped['responseId'] = current_trace
        outputs.append(b'data: '+canonical_bytes(mapped)+b'\n\n')
    if trace is None or model is None or not terminal:
        raise RouterError('IDENTITY_UNVERIFIED', 'incomplete Code Assist terminal identity')
    return b''.join(outputs), trace, model


class GeminiBroker:
    """One capability, one in-flight request, fixed REST and Code Assist routes."""
    def __init__(self, credential: str, project: str, *, request_limit: int, wall_seconds: float,
                 socket_path: Path, upstream=None, on_observation=None, on_request=None, on_rejection=None):
        if not isinstance(credential, str) or not credential or not isinstance(project, str) or not project:
            raise RouterError('INVALID_CONTRACT')
        if type(request_limit) is not int or request_limit < 1 or wall_seconds <= 0:
            raise RouterError('INVALID_BUDGET')
        self.capability = secrets.token_urlsafe(32)
        self._credential, self._project = credential, project
        self._deadline, self._limit = time.monotonic()+wall_seconds, request_limit
        self._socket_timeout = min(max(wall_seconds, .1), 10)
        self._upstream = upstream if upstream is not None else GeminiUpstream(wall_seconds)
        self._proof = 'synthetic_upstream' if upstream is not None else 'authenticated_endpoint_declaration'
        self._active, self._inflight = True, False
        self._lock = threading.Lock()
        self._observations, self._on_observation = [], on_observation
        self._on_request = on_request
        self.rejections, self._on_rejection = [], on_rejection
        self._frozen_observations = None
        self._publication_lock = threading.RLock()
        self._publish_enabled = True
        self._idle = threading.Event()
        self._idle.set()
        self._socket_path = Path(socket_path)
        try:
            parent_info = self._socket_path.parent.lstat()
        except OSError as exc:
            raise RouterError('BROKER_SOCKET_UNSAFE') from exc
        if (self._socket_path.parent.is_symlink() or not self._socket_path.parent.is_dir()
                or parent_info.st_uid != os.getuid() or parent_info.st_mode & 0o077):
            raise RouterError('BROKER_SOCKET_UNSAFE')
        if self._socket_path.exists() or self._socket_path.is_symlink():
            raise RouterError('BROKER_SOCKET_EXISTS')
        self._server = _UnixServer(str(self._socket_path), self._handler())
        self._socket_path.chmod(0o600)
        self._server.handler_slots = threading.BoundedSemaphore(8)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        kwargs={'poll_interval': .025}, daemon=True)

    def _handler(self):
        broker = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def setup(self):
                super().setup()
                self.connection.settimeout(broker._socket_timeout)

            def _read_body(self, length):
                chunks, remaining = [], length
                try:
                    while remaining:
                        chunk = self.rfile.read(remaining)
                        if not chunk:
                            raise RouterError('INVALID_BODY', 'truncated body')
                        chunks.append(chunk)
                        remaining -= len(chunk)
                except OSError as exc:
                    raise RouterError('INVALID_BODY', 'body read failed') from exc
                return b''.join(chunks)

            def do_POST(self):
                try:
                    if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                        raise RouterError('INVALID_BODY')
                    if any(len(self.headers.get_all(name, [])) > 1
                           for name in ('Authorization', 'x-goog-api-key', 'Content-Type')):
                        raise RouterError('FORBIDDEN_REQUEST_HEADER')
                    length = int(self.headers.get('Content-Length', '0'))
                    if length < 1 or length > 8*1024*1024:
                        raise RouterError('INVALID_BODY')
                    status, headers, data = broker.forward(self.path, dict(self.headers.items()), self._read_body(length))
                    self.send_response(status)
                    for key, value in headers.items():
                        self.send_header(key, value)
                    self.send_header('content-length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except RouterError as exc:
                    broker._record_rejection(exc.code)
                    data = canonical_bytes({'error': exc.code})
                    self.send_response(403 if exc.code == 'CAPABILITY_REVOKED' else 400)
                    self.send_header('content-type', 'application/json')
                    self.send_header('content-length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

        return Handler

    @property
    def observations(self):
        with self._lock:
            source = self._frozen_observations if self._frozen_observations is not None else self._observations
            raw, _ = redact(canonical_bytes(source), (self._credential.encode(), self.capability.encode()))
            return strict_json(raw)

    def _publish(self) -> None:
        with self._publication_lock:
            if self._on_observation and self._publish_enabled:
                self._on_observation(self.observations)

    def _record_rejection(self, code):
        with self._publication_lock:
            if not self._publish_enabled:
                return
            with self._lock:
                if len(self.rejections) < 64:
                    self.rejections.append(code)
            if self._on_rejection is not None:
                self._on_rejection(list(self.rejections))

    def _authenticate(self, headers: dict) -> None:
        normalized = {str(key).lower(): str(value) for key, value in headers.items()}
        allowed = {'host', 'content-type', 'content-length', 'x-goog-api-key', 'authorization', 'accept'}
        if set(normalized) - allowed:
            raise RouterError('FORBIDDEN_REQUEST_HEADER')
        bearer = normalized.get('authorization', '')
        api_key = normalized.get('x-goog-api-key', '')
        valid = ((not api_key and hmac.compare_digest(bearer, 'Bearer '+self.capability))
                 or (not bearer and hmac.compare_digest(api_key, self.capability)))
        if not valid or normalized.get('content-type') != 'application/json':
            raise RouterError('CAPABILITY_DENIED')

    def forward(self, path: str, headers: dict, raw: bytes) -> tuple[int, dict, bytes]:
        try:
            return self._forward(path, headers, raw)
        except RouterError as exc:
            self._record_rejection(exc.code)
            raise

    def _forward(self, path: str, headers: dict, raw: bytes) -> tuple[int, dict, bytes]:
        if path != REST_PATH:
            raise RouterError('FORBIDDEN_PATH')
        self._authenticate(headers)
        if not isinstance(raw, bytes) or not raw or len(raw) > 8*1024*1024:
            raise RouterError('INVALID_BODY')
        body = _validate_request(strict_json(raw))
        with self._lock:
            if not self._active or time.monotonic() >= self._deadline:
                raise RouterError('CAPABILITY_REVOKED')
            if self._inflight or len(self._observations) >= self._limit:
                raise RouterError('REQUEST_BUDGET_EXHAUSTED')
            self._inflight = True
            self._idle.clear()
            observation = {'attempt_id': str(uuid.uuid4()), 'request_number': len(self._observations)+1,
                           'request_model': MODEL, 'request_sha256': hashlib.sha256(raw).hexdigest(),
                           'upstream_host': 'cloudcode-pa.googleapis.com', 'proof': self._proof,
                           'classification': 'OUTCOME_UNKNOWN', 'wire_started': False}
            self._observations.append(observation)
        try:
            self._publish()
            with self._lock:
                if not self._active or time.monotonic() >= self._deadline:
                    raise RouterError('CAPABILITY_REVOKED')
            envelope = {'model': MODEL, 'project': self._project, 'user_prompt_id': str(uuid.uuid4()),
                        'request': body | {'session_id': str(uuid.uuid4())}, 'enabled_credit_types': []}
            upstream_headers = {'authorization': 'Bearer '+self._credential, 'content-type': 'application/json',
                                'accept': 'text/event-stream'}
            payload = canonical_bytes(envelope)
            if self._on_request is not None:
                self._on_request(strict_json(payload))
            with self._lock:
                if not self._active or time.monotonic() >= self._deadline:
                    raise RouterError('CAPABILITY_REVOKED')
                observation['wire_started'] = True
            status, response_headers, response = self._upstream(_CODE_ASSIST_PATH, upstream_headers, payload)
            observation['http_status'] = status
            if 300 <= status < 400:
                raise RouterError('UPSTREAM_REDIRECT')
            if status != 200:
                raise RouterError('CREDENTIAL_OR_ENTITLEMENT_REJECTED' if status in (401, 403) else 'UPSTREAM_HTTP_ERROR')
            if 'text/event-stream' not in response_headers.get('content-type', ''):
                raise RouterError('UPSTREAM_PROTOCOL_ERROR')
            if not isinstance(response, bytes) or len(response) > 16*1024*1024:
                raise RouterError('UPSTREAM_OUTPUT_LIMIT')
            mapped, trace, model = _to_rest(response)
            mapped, _ = redact(mapped, (self._credential.encode(), self.capability.encode()))
            with self._lock:
                if not self._active or time.monotonic() >= self._deadline:
                    raise RouterError('CAPABILITY_REVOKED')
            observation.update({'classification': 'IDENTITY_VERIFIED', 'response_model': model,
                                'upstream_trace_id': trace, 'proof': self._proof})
            return 200, {'content-type': 'text/event-stream'}, mapped
        except RouterError as exc:
            observation['classification'] = exc.code
            raise
        except Exception as exc:
            observation['classification'] = 'OUTCOME_UNKNOWN'
            raise RouterError('OUTCOME_UNKNOWN') from exc
        finally:
            with self._lock:
                self._inflight = False
            try:
                self._publish()
            finally:
                self._idle.set()

    def __enter__(self):
        self._thread.start()
        return self

    def revoke(self) -> None:
        with self._lock:
            self._active = False
        if hasattr(self._upstream, 'close'):
            self._upstream.close()

    def __exit__(self, *_args) -> None:
        self.revoke()
        self._server.shutdown()
        self._server.server_close()
        self._socket_path.unlink(missing_ok=True)
        self._thread.join(timeout=1)
        self._idle.wait(.5)
        if not self._publication_lock.acquire(timeout=.25):
            raise RouterError('OBSERVATION_DRAIN_TIMEOUT')
        try:
            self._publish_enabled = False
            with self._lock:
                self._frozen_observations = json.loads(json.dumps(self._observations))
                if self._inflight:
                    for observation in self._frozen_observations:
                        observation['classification'] = 'OUTCOME_UNKNOWN'
        finally:
            self._publication_lock.release()
