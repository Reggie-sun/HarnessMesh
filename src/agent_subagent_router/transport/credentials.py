import base64
from dataclasses import dataclass, field
import os
from pathlib import Path
import pwd
import re
import stat
import time

from ..contracts import RouterError, canonical_bytes, hash_bytes, strict_json


@dataclass(frozen=True)
class CodexSubscriptionCredential:
    access_token: str = field(repr=False)
    account_id: str = field(repr=False)
    secret_values: tuple[str, ...] = field(repr=False)

    def __post_init__(self):
        if (not _header_value(self.access_token) or self.access_token.startswith('sk-')
                or not _header_value(self.account_id) or type(self.secret_values) is not tuple
                or not self.secret_values or len(self.secret_values) > 4
                or any(not _header_value(secret) for secret in self.secret_values)
                or self.access_token not in self.secret_values
                or self.account_id not in self.secret_values):
            raise RouterError('UNSAFE_CREDENTIAL', 'invalid Codex subscription credential')


def credential_fingerprint(provider: str, credential: str | CodexSubscriptionCredential) -> str:
    if isinstance(credential, CodexSubscriptionCredential):
        if provider != 'codex-subscription':
            raise RouterError('UNSAFE_CREDENTIAL', 'provider-specific credential required')
        return hash_bytes(canonical_bytes({
            'kind': 'codex-subscription-credential/v1',
            'provider': provider,
            'access_token': credential.access_token,
            'account_id': credential.account_id,
        }))
    return hash_bytes((provider+'\0'+credential).encode())


def _header_value(value: object) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= 8192
            and all(33 <= ord(character) <= 126 for character in value))


def _has_symlink_component(path: Path) -> bool:
    try:
        return any(stat.S_ISLNK(component.lstat().st_mode) for component in (path, *path.parents))
    except OSError:
        return True


def owner_home() -> Path:
    """Host UID authority, independent of invocation-controlled HOME/XDG."""
    try:
        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, OSError, TypeError):
        raise RouterError('UNSAFE_STATE') from None
    if not home.is_absolute() or '..' in home.parts:
        raise RouterError('UNSAFE_STATE')
    return home


def _validate_subscription_path(path: Path, project_root: Path | None) -> None:
    if (not path.is_absolute() or '..' in path.parts or _is_global_codex_path(path)
            or path != owner_home()/'.config/jianji/codex/auth.json'
            or _has_symlink_component(path)):
        raise RouterError('UNSAFE_CREDENTIAL', 'private application authentication file required')
    if project_root is not None:
        try:
            if path.resolve().is_relative_to(project_root.resolve()):
                raise RouterError('UNSAFE_CREDENTIAL', 'credential must be outside project')
        except (OSError, RuntimeError):
            raise RouterError('UNSAFE_CREDENTIAL', 'invalid credential path') from None


def _jwt_payload(token: str) -> dict:
    parts = token.split('.')
    if len(parts) != 3 or any(not re.fullmatch(r'[A-Za-z0-9_-]+', part) for part in parts):
        raise RouterError('UNSAFE_CREDENTIAL', 'invalid Codex subscription credential')

    def decode(part: str) -> dict:
        encoded = part.encode('ascii')
        raw = base64.b64decode(encoded + b'=' * (-len(encoded) % 4), altchars=b'-_', validate=True)
        value = strict_json(raw)
        if not isinstance(value, dict):
            raise ValueError('JWT component')
        return value

    try:
        decode(parts[0])
        payload = decode(parts[1])
    except (ValueError, UnicodeError, RouterError):
        raise RouterError('UNSAFE_CREDENTIAL', 'invalid Codex subscription credential') from None
    now = time.time()
    expiry = payload.get('exp')
    if type(expiry) is not int or expiry <= now:
        raise RouterError('UNSAFE_CREDENTIAL', 'invalid Codex subscription credential')
    for claim in ('nbf', 'iat'):
        value = payload.get(claim)
        if claim in payload and (type(value) is not int or value > now):
            raise RouterError('UNSAFE_CREDENTIAL', 'invalid Codex subscription credential')
    return payload


def _codex_subscription_credential(raw: bytes) -> CodexSubscriptionCredential:
    try:
        value = strict_json(raw)
        allowed = {'auth_mode', 'OPENAI_API_KEY', 'tokens', 'last_refresh'}
        if (not isinstance(value, dict) or set(value) - allowed
                or value.get('auth_mode') != 'chatgpt'
                or value.get('OPENAI_API_KEY') is not None):
            raise ValueError('auth mode')
        if ('last_refresh' in value and
                (not isinstance(value['last_refresh'], str) or len(value['last_refresh']) > 128)):
            raise ValueError('refresh metadata')
        tokens = value.get('tokens')
        token_fields = {'access_token', 'account_id', 'id_token', 'refresh_token'}
        if not isinstance(tokens, dict) or set(tokens) - token_fields:
            raise ValueError('token fields')
        access_token = tokens.get('access_token')
        account_id = tokens.get('account_id')
        if not _header_value(access_token) or not _header_value(account_id) or access_token.startswith('sk-'):
            raise ValueError('required token')
        payload = _jwt_payload(access_token)
        auth_claim = payload.get('https://api.openai.com/auth')
        if (not isinstance(auth_claim, dict)
                or not _header_value(auth_claim.get('chatgpt_account_id'))
                or auth_claim['chatgpt_account_id'] != account_id):
            raise ValueError('account association')
        secrets = [access_token]
        for name in ('id_token', 'refresh_token'):
            secret = tokens.get(name)
            if name in tokens and secret is not None:
                if not _header_value(secret):
                    raise ValueError('optional token')
                secrets.append(secret)
        secrets.append(account_id)
        return CodexSubscriptionCredential(access_token, account_id, tuple(secrets))
    except (RouterError, UnicodeError, ValueError, TypeError, KeyError):
        raise RouterError('UNSAFE_CREDENTIAL', 'invalid Codex subscription credential') from None


def _is_global_codex_path(path: Path) -> bool:
    normalized = Path(os.path.normpath(str(path)))
    if '.codex' in normalized.parts:
        return True
    global_root = (owner_home()/'.codex').resolve(strict=False)
    try:
        return normalized.resolve(strict=False).is_relative_to(global_root)
    except (OSError, RuntimeError):
        return True


def read_credential_reference(provider: str, path: Path) -> dict:
    """New image CLI reference admission, before reading any reference bytes."""
    path = Path(path)
    if (not path.is_absolute() or path.is_symlink()
            or (provider in ('openai', 'minimax', 'codex-subscription')
                and _is_global_codex_path(path))):
        raise RouterError('UNSAFE_CREDENTIAL', 'private application reference required')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise RouterError('CREDENTIAL_REQUIRED') from None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > 8192):
            raise RouterError('UNSAFE_CREDENTIAL')
        value = strict_json(os.read(fd, 8193))
        if not isinstance(value, dict) or set(value) != {'provider', 'file'} or value['provider'] != provider:
            raise RouterError('UNSAFE_CREDENTIAL')
        return value
    finally:
        os.close(fd)


def load_credential(
    provider: str, reference: dict | None, *, project_root: Path | None = None
) -> str | CodexSubscriptionCredential:
    if not reference:
        raise RouterError('CREDENTIAL_REQUIRED', f'configure private {provider} credential locally')
    if provider == 'codex-subscription' and not isinstance(reference, dict):
        raise RouterError('UNSAFE_CREDENTIAL', 'provider-specific reference required')
    if set(reference) != {'provider', 'file'} or reference['provider'] != provider:
        raise RouterError('UNSAFE_CREDENTIAL', 'provider-specific reference required')
    path = Path(reference['file'])
    if not path.is_absolute():
        raise RouterError('UNSAFE_CREDENTIAL', 'private absolute file required')
    if provider in ('openai', 'minimax', 'codex-subscription') and _is_global_codex_path(path):
        raise RouterError('UNSAFE_CREDENTIAL', 'global Codex credentials are not accepted')
    if provider == 'codex-subscription':
        _validate_subscription_path(path, project_root)
    if path.is_symlink():
        raise RouterError('UNSAFE_CREDENTIAL', 'private absolute file required')
    if (provider != 'codex-subscription' and project_root is not None
            and path.resolve().is_relative_to(project_root.resolve())):
        raise RouterError('UNSAFE_CREDENTIAL', 'credential must be outside project')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise RouterError('CREDENTIAL_REQUIRED', 'configured credential file unavailable') from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > 8192):
            raise RouterError('UNSAFE_CREDENTIAL', 'credential permissions or type invalid')
        if provider == 'codex-subscription':
            return _codex_subscription_credential(os.read(fd, 8193))
        value = os.read(fd, 8193).decode('utf-8').strip()
        if not value or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise RouterError('UNSAFE_CREDENTIAL', 'invalid credential encoding')
        if provider == 'openai' and (not value.startswith('sk-') or len(value) < 20):
            raise RouterError('UNSAFE_CREDENTIAL', 'OpenAI API key required')
        return value
    finally:
        os.close(fd)
