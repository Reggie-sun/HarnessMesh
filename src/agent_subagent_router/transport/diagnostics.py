"""Bounded transport diagnostics without exception text, bodies or credentials."""
import http.client
import re
import socket
import ssl

from ..contracts import RouterError, strict_json


def stream_progress(body: bytes | bytearray) -> dict | None:
    """Count complete SSE control frames on failure, never expose their payloads."""
    known = {'message_start', 'message_delta', 'message_stop', 'content_block_start',
             'content_block_delta', 'content_block_stop', 'ping', 'error'}
    result = {'complete_events': 0, 'message_start_count': 0, 'message_stop_count': 0,
              'error_count': 0, 'invalid_events': 0, 'last_event': 'none'}
    offset = 0
    for separator in re.finditer(rb'(?:\r?\n){2}', body):
        block = body[offset:separator.start()]
        offset = separator.end()
        data = b'\n'.join(line[5:].lstrip() for line in block.splitlines()
                          if line.startswith(b'data:'))
        if not data:
            continue
        result['complete_events'] += 1
        try:
            event = strict_json(data)
            kind = event.get('type') if isinstance(event, dict) else None
        except (RouterError, RecursionError):
            kind = None
            result['invalid_events'] += 1
        result['last_event'] = kind if isinstance(kind, str) and kind in known else 'unknown'
        if kind in ('message_start', 'message_stop', 'error'):
            result[kind+'_count'] += 1
    tail = body[offset:]
    result['trailing_bytes'] = len(tail)
    if result['complete_events'] or tail.startswith((b'data:', b'event:')):
        return result
    return None


def failure_diagnostic(phase: str, error: Exception) -> dict:
    if isinstance(error, socket.gaierror):
        kind = 'DNS_ERROR'
    elif isinstance(error, ssl.SSLError):
        kind = 'TLS_ERROR'
    elif isinstance(error, TimeoutError):
        kind = 'TIMEOUT'
    elif isinstance(error, ConnectionError):
        kind = 'CONNECTION_ERROR'
    elif isinstance(error, http.client.IncompleteRead):
        kind = 'INCOMPLETE_RESPONSE'
    elif isinstance(error, http.client.HTTPException):
        kind = 'HTTP_PROTOCOL_ERROR'
    elif isinstance(error, OSError):
        kind = 'OS_ERROR'
    else:
        kind = 'UNEXPECTED_ERROR'
    diagnostic = {'phase': phase, 'kind': kind}
    for error_type, detail in (
        (http.client.RemoteDisconnected, 'REMOTE_DISCONNECTED'),
        (ConnectionResetError, 'CONNECTION_RESET'),
        (ConnectionAbortedError, 'CONNECTION_ABORTED'),
        (BrokenPipeError, 'BROKEN_PIPE'),
    ):
        if isinstance(error, error_type):
            diagnostic['detail'] = detail
            break
    return diagnostic


class UpstreamFailure(RouterError):
    def __init__(self, phase: str, error: Exception, http_status: int | None = None):
        self.diagnostic = failure_diagnostic(phase, error)
        self.http_status = http_status
        super().__init__('OUTCOME_UNKNOWN')
