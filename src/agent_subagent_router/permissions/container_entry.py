"""Baked container entrypoint; it deliberately imports no mutable router package code."""

from __future__ import annotations

import base64
import http.server
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time


_MAX_ENVELOPE = 8 * 1024 * 1024
_MAX_BODY = 8 * 1024 * 1024
_BROKER_SOCKET = '/broker.sock'
_ALLOWED_PATHS = {'/v1/messages', '/v1/messages?beta=true',
                  '/v1beta/models/gemini-3.5-flash:streamGenerateContent?alt=sse'}
_FORWARDED_HEADERS = {'authorization', 'x-api-key', 'x-goog-api-key', 'content-type', 'anthropic-version', 'accept'}


def main() -> int:
    try:
        envelope = _read_envelope()
        relay = _start_relay(envelope['wall_seconds']) if Path(_BROKER_SOCKET).exists() else None
        try:
            cwd = '/work' if Path('/work').is_dir() else '/home/worker'
            process = subprocess.Popen(envelope['argv'], cwd=cwd, env=envelope['env'], stdin=subprocess.PIPE,
                                       stdout=None, stderr=None, shell=False, close_fds=True)
            process.communicate(envelope['prompt'])
            return process.returncode
        finally:
            if relay:
                relay.shutdown()
                relay.server_close()
    except (ValueError, OSError, json.JSONDecodeError):
        sys.stderr.write('{"error":"INVALID_CONTAINER_ENVELOPE"}\n')
        return 126


def _read_envelope() -> dict:
    raw = sys.stdin.buffer.read(_MAX_ENVELOPE + 1)
    if len(raw) > _MAX_ENVELOPE:
        raise ValueError()
    data = json.loads(raw, object_pairs_hook=_no_duplicates)
    if not isinstance(data, dict) or set(data) != {'argv', 'env', 'prompt_b64', 'wall_seconds'}:
        raise ValueError()
    argv, env, prompt_b64 = data['argv'], data['env'], data['prompt_b64']
    if (not isinstance(argv, list) or not argv
            or any(not isinstance(item, str) or not item for item in argv)
            or not isinstance(env, dict)
            or any(not isinstance(key, str) or not isinstance(value, str) for key, value in env.items())
            or not isinstance(prompt_b64, str)):
        raise ValueError()
    prompt = base64.b64decode(prompt_b64, validate=True)
    wall = data['wall_seconds']
    if type(wall) not in (int, float) or not math.isfinite(wall) or not 0 < wall <= 3600:
        raise ValueError()
    if len(prompt) > _MAX_BODY:
        raise ValueError()
    return {'argv': argv, 'env': env, 'prompt': prompt, 'wall_seconds': wall}


def _no_duplicates(items):
    data = {}
    for key, value in items:
        if key in data:
            raise ValueError()
        data[key] = value
    return data


def _start_relay(wall_seconds):
    deadline = time.monotonic()+wall_seconds
    class Relay(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_args):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(max(.001, deadline-time.monotonic()))

        def do_CONNECT(self):
            self.send_error(405)

        def do_GET(self):
            self.send_error(405)

        def do_POST(self):
            if self.path not in _ALLOWED_PATHS or self.headers.get('Transfer-Encoding'):
                self.send_error(403)
                return
            lengths = self.headers.get_all('Content-Length', [])
            try:
                length = int(lengths[0])
                if len(lengths) != 1 or not 0 < length <= _MAX_BODY:
                    raise ValueError()
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError()
            except (ValueError, OSError):
                self.send_error(400)
                return
            headers = []
            for name, value in self.headers.items():
                if name.lower() in _FORWARDED_HEADERS:
                    if '\r' in value or '\n' in value:
                        self.send_error(400)
                        return
                    headers.append((name, value))
            request = [f'POST {self.path} HTTP/1.1', 'Host: broker', f'Content-Length: {len(body)}']
            request.extend(f'{name}: {value}' for name, value in headers)
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as upstream:
                    upstream.settimeout(max(.001, deadline-time.monotonic()))
                    upstream.connect(_BROKER_SOCKET)
                    upstream.sendall(('\r\n'.join(request)+'\r\n\r\n').encode()+body)
                    while True:
                        chunk = upstream.recv(65536)
                        if not chunk:
                            break
                        self.connection.sendall(chunk)
            except OSError:
                try:
                    self.send_error(502)
                except OSError:
                    pass
            self.close_connection = True

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 18765), Relay)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    return server


if __name__ == '__main__':
    raise SystemExit(main())
