"""Parent-only Gemini OAuth and Code Assist preflight; never writes credentials."""
from dataclasses import dataclass
import http.client
import os
from pathlib import Path
import ssl
import stat
import time
from urllib.parse import urlencode

from ..contracts import RouterError, canonical_bytes, strict_json


_TOKEN_HOST = 'oauth2.googleapis.com'
_TOKEN_PATH = '/token'
_CODE_ASSIST_HOST = 'cloudcode-pa.googleapis.com'
_MAX_CREDENTIAL_BYTES = 32*1024


def _client_constants(*, required: bool = True) -> tuple[str, str]:
    """Read public OAuth client settings from the local runtime, never source control."""
    client_id = os.environ.get('AGENT_ROUTER_GEMINI_OAUTH_CLIENT_ID', '')
    client_secret = os.environ.get('AGENT_ROUTER_GEMINI_OAUTH_CLIENT_SECRET', '')
    if required and (not client_id or not client_secret):
        raise RouterError('OAUTH_CLIENT_CONFIG_REQUIRED', 'configure Gemini OAuth constants locally')
    return client_id, client_secret


@dataclass(frozen=True)
class OAuthCredential:
    access_token: str
    refresh_token: str
    expiry_date: int


def verify_pinned_client_constants(bundle: Path) -> None:
    """Bind public OAuth client constants to the pinned bundle without emitting them."""
    bundle = Path(bundle)
    try:
        if not bundle.is_absolute() or bundle.is_symlink() or not bundle.is_file():
            raise OSError()
        source = bundle.read_bytes()
    except OSError as exc:
        raise RouterError('RUNTIME_CHANGED', 'Gemini OAuth source unavailable') from exc
    client_id, client_secret = _client_constants()
    required = (b'var OAUTH_CLIENT_ID = "'+client_id.encode()+b'";',
                b'var OAUTH_CLIENT_SECRET = "'+client_secret.encode()+b'";')
    if not all(marker in source for marker in required):
        raise RouterError('RUNTIME_CHANGED', 'Gemini OAuth constants changed')


def _token(value) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 8192 and not any(ord(char) < 33 for char in value)


def load_oauth_file(path: Path, *, project_root: Path | None = None) -> OAuthCredential:
    """Read an existing owner-private OAuth record without onboarding or mutation."""
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise RouterError('UNSAFE_CREDENTIAL', 'private absolute regular file required')
    if project_root is not None and path.resolve().is_relative_to(Path(project_root).resolve()):
        raise RouterError('UNSAFE_CREDENTIAL', 'OAuth file cannot be in the project')
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise RouterError('CREDENTIAL_REQUIRED', 'configured OAuth file unavailable') from exc
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077
                or info.st_size <= 0 or info.st_size > _MAX_CREDENTIAL_BYTES):
            raise RouterError('UNSAFE_CREDENTIAL', 'OAuth file permissions or type invalid')
        raw = os.read(descriptor, _MAX_CREDENTIAL_BYTES+1)
        if len(raw) != info.st_size or len(raw) > _MAX_CREDENTIAL_BYTES:
            raise RouterError('UNSAFE_CREDENTIAL', 'OAuth file changed while reading')
    finally:
        os.close(descriptor)
    value = strict_json(raw)
    allowed = {'access_token', 'refresh_token', 'expiry_date', 'token_type', 'scope', 'id_token'}
    if not isinstance(value, dict) or set(value) - allowed or not _token(value.get('access_token')):
        raise RouterError('UNSAFE_CREDENTIAL', 'invalid OAuth record')
    if not _token(value.get('refresh_token')) or type(value.get('expiry_date')) is not int or value['expiry_date'] < 0:
        raise RouterError('UNSAFE_CREDENTIAL', 'OAuth refresh record required')
    return OAuthCredential(value['access_token'], value['refresh_token'], value['expiry_date'])


def _refresh_request(form: dict[str, str]) -> dict:
    connection = http.client.HTTPSConnection(_TOKEN_HOST, timeout=10, context=ssl.create_default_context())
    try:
        connection.connect()
        connection.auto_open = 0
        payload = urlencode(form).encode()
        connection.request('POST', _TOKEN_PATH, body=payload,
                           headers={'content-type': 'application/x-www-form-urlencoded',
                                    'content-length': str(len(payload))})
        response = connection.getresponse()
        raw = response.read(64*1024+1)
        if response.status != 200 or len(raw) > 64*1024:
            raise RouterError('CREDENTIAL_OR_ENTITLEMENT_REJECTED')
        value = strict_json(raw)
        if not isinstance(value, dict):
            raise RouterError('CREDENTIAL_OR_ENTITLEMENT_REJECTED')
        return value
    except (OSError, http.client.HTTPException) as exc:
        raise RouterError('OAUTH_REFRESH_FAILED') from exc
    finally:
        connection.close()


def access_token(credential: OAuthCredential, *, now: int | None = None, refresher=None) -> str:
    now = int(time.time()*1000) if now is None else now
    if type(now) is not int:
        raise RouterError('INVALID_CONTRACT', 'OAuth clock')
    if credential.expiry_date > now+60_000:
        return credential.access_token
    client_id, client_secret = _client_constants(required=refresher is None)
    form = {'client_id': client_id, 'client_secret': client_secret,
            'refresh_token': credential.refresh_token, 'grant_type': 'refresh_token'}
    value = (refresher or _refresh_request)(form)
    if (not isinstance(value, dict) or not _token(value.get('access_token'))
            or type(value.get('expires_in')) is not int or value['expires_in'] <= 0):
        raise RouterError('OAUTH_REFRESH_FAILED')
    return value['access_token']


def _code_assist_request(path: str, headers: dict, body: bytes):
    if path != '/v1internal:loadCodeAssist':
        raise RouterError('FORBIDDEN_UPSTREAM_PATH')
    connection = http.client.HTTPSConnection(_CODE_ASSIST_HOST, timeout=10, context=ssl.create_default_context())
    try:
        connection.connect()
        connection.auto_open = 0
        connection.request('POST', path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(256*1024+1)
        if len(raw) > 256*1024:
            raise RouterError('UPSTREAM_OUTPUT_LIMIT')
        return response.status, {key.lower(): value for key, value in response.getheaders()}, raw
    except (OSError, http.client.HTTPException) as exc:
        raise RouterError('OAUTH_PREFLIGHT_FAILED') from exc
    finally:
        connection.close()


def preflight_code_assist(token: str, project: str | None = None, *, upstream=None) -> dict:
    """Read-only entitlement preflight. Validation/onboarding responses stay blockers."""
    if not _token(token) or (project is not None and (not isinstance(project, str) or not project)):
        raise RouterError('INVALID_CONTRACT', 'Code Assist preflight')
    metadata = {'ideType': 'IDE_UNSPECIFIED', 'platform': 'PLATFORM_UNSPECIFIED', 'pluginType': 'GEMINI'}
    body_value = {'metadata': metadata}
    if project is not None:
        body_value['cloudaicompanionProject'] = project
        metadata['duetProject'] = project
    body = canonical_bytes(body_value)
    status, _headers, raw = (upstream or _code_assist_request)(
        '/v1internal:loadCodeAssist', {'authorization': 'Bearer '+token, 'content-type': 'application/json'}, body)
    if status in (401, 403):
        raise RouterError('CREDENTIAL_OR_ENTITLEMENT_REJECTED')
    if status != 200:
        raise RouterError('OAUTH_PREFLIGHT_FAILED')
    value = strict_json(raw)
    if not isinstance(value, dict):
        raise RouterError('GEMINI_INELIGIBLE')
    if value.get('validationInfo') or value.get('validationRequired'):
        raise RouterError('GEMINI_VALIDATION_REQUIRED')
    tier, approved_project = value.get('currentTier'), value.get('cloudaicompanionProject')
    if (not isinstance(tier, dict) or not isinstance(tier.get('id'), str) or not tier['id']
            or not isinstance(approved_project, str) or not approved_project):
        reasons = value.get('ineligibleTiers', [])
        unsupported = isinstance(reasons, list) and any(isinstance(item, dict)
            and item.get('reasonCode') == 'UNSUPPORTED_CLIENT' for item in reasons)
        raise RouterError('GEMINI_INELIGIBLE', 'UNSUPPORTED_CLIENT' if unsupported else 'No approved tier/project')
    return {'project': approved_project, 'tier': tier['id'],
            'proof': 'synthetic_upstream' if upstream is not None else 'authenticated_endpoint_declaration'}
