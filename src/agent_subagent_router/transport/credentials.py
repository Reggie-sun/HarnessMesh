import os
from pathlib import Path
import stat

from ..contracts import RouterError, hash_bytes


def credential_fingerprint(provider: str, credential: str) -> str:
    return hash_bytes((provider+'\0'+credential).encode())


def load_credential(provider: str, reference: dict | None, *, project_root: Path | None = None) -> str:
    if not reference:
        raise RouterError('CREDENTIAL_REQUIRED', f'configure private {provider} credential locally')
    if set(reference) != {'provider', 'file'} or reference['provider'] != provider:
        raise RouterError('UNSAFE_CREDENTIAL', 'provider-specific reference required')
    path = Path(reference['file'])
    if not path.is_absolute() or path.is_symlink():
        raise RouterError('UNSAFE_CREDENTIAL', 'private absolute file required')
    if project_root is not None and path.resolve().is_relative_to(project_root.resolve()):
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
        value = os.read(fd, 8193).decode('utf-8').strip()
        if not value or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise RouterError('UNSAFE_CREDENTIAL', 'invalid credential encoding')
        return value
    finally:
        os.close(fd)
