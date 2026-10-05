"""Bounded transport diagnostics without exception text, bodies or credentials."""
import http.client
import socket
import ssl

from ..contracts import RouterError


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
