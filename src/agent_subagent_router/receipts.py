"""Private supervisor-owned artifacts; hashes describe saved, filtered bytes."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import re
import tempfile
import uuid

from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from . import __version__


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def implementation_identity() -> dict:
    root = Path(__file__).parent
    files = {str(path.relative_to(root)): hash_bytes(path.read_bytes())
             for path in sorted(root.rglob('*.py'))}
    return {'version': __version__, 'source_sha256': hash_bytes(canonical_bytes(files))}


def atomic_json(path: Path, value: dict, *, exclusive: bool = True):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def redact(data: bytes, secrets=()) -> tuple[bytes, int]:
    count = 0
    for secret in sorted(set(secrets), key=len, reverse=True):
        if not secret:
            continue
        count += data.count(secret)
        data = data.replace(secret, b'[REDACTED]')
    data, generic = re.subn(rb'(?i)(authorization["\s:]+(?:bearer\s+)?)[^\s"\\]+',
                            rb'\1[REDACTED]', data)
    return data, count+generic


class ReceiptStore:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()
        if self.root.is_symlink():
            raise RouterError('ARTIFACT_ESCAPE', 'state root is a symlink')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.stat().st_uid != os.getuid() or self.root.stat().st_mode & 0o077:
            raise RouterError('UNSAFE_STATE', 'state directory must be private and owned')

    def _run(self, run_id: str) -> Path:
        try:
            if str(uuid.UUID(run_id)) != run_id:
                raise ValueError()
        except ValueError as exc:
            raise RouterError('INVALID_RECEIPT_ID') from exc
        run = self.root/run_id
        if run.is_symlink() or not run.is_dir() or run.resolve().parent != self.root.resolve():
            raise RouterError('ARTIFACT_ESCAPE')
        return run

    def create(self, parent_session_id: str, task_id: str) -> Path:
        run = self.root/str(uuid.uuid4())
        run.mkdir(mode=0o700)
        atomic_json(run/'pending.json', {'schema_version': 1, 'invocation_id': run.name,
                    'attempt_id': str(uuid.uuid4()), 'parent_session_id': parent_session_id,
                    'task_id': task_id, 'started_at': utc_now(), 'router': implementation_identity()})
        return run

    @contextmanager
    def _locked(self, run: Path):
        canonical = self._run(run.name)
        if Path(run).absolute() != canonical:
            raise RouterError('ARTIFACT_ESCAPE', 'run path is outside its owning store')
        run = canonical
        fd = os.open(run/'.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            if (run/'invocation-receipt.json').exists():
                raise RouterError('RECEIPT_FINALIZED')
            yield
        finally:
            os.close(fd)

    def _path(self, run: Path, name: str) -> Path:
        path = Path(name)
        if (path.is_absolute() or not path.parts or '..' in path.parts
                or any(part.startswith('.') for part in path.parts)):
            raise RouterError('ARTIFACT_ESCAPE')
        current = run
        for part in path.parts:
            current = current/part
            if current.is_symlink():
                raise RouterError('ARTIFACT_ESCAPE')
        if not current.resolve().is_relative_to(run.resolve()):
            raise RouterError('ARTIFACT_ESCAPE')
        return current

    def artifact(self, run: Path, name: str, data: bytes, *, secrets=(),
                 media_type='text/plain', producer='supervisor') -> dict:
        with self._locked(run):
            path = self._path(run, name)
            if name in ('pending.json', 'invocation-receipt.json'):
                raise RouterError('ARTIFACT_ESCAPE', 'reserved name')
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            data, count = redact(data, secrets)
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            return {'path': name, 'sha256': hash_bytes(data), 'size': len(data),
                    'media_type': media_type, 'producer': producer,
                    'representation': 'redacted' if count else 'filtered',
                    'redaction_version': 1, 'redaction_count': count}

    def finalize(self, run: Path, facts: dict) -> dict:
        with self._locked(run):
            pending = strict_json(self._path(run, 'pending.json').read_bytes())
            if set(pending) & set(facts):
                raise RouterError('RECEIPT_ASSOCIATION_MISMATCH')
            value = pending | facts | {'finalized_at': utc_now()}
            self._verify_artifacts(run, value)
            atomic_json(run/'invocation-receipt.json', value)
            return value

    def observe(self, run: Path, facts: dict):
        """Last durable supervisor observations; recovery never invents completion."""
        with self._locked(run):
            atomic_json(run/'observations.json', facts, exclusive=False)

    def _verify_artifacts(self, run: Path, receipt: dict):
        seen = set()
        for item in receipt.get('artifacts', []):
            path = self._path(run, item['path'])
            if item['path'] in seen:
                raise RouterError('ARTIFACT_MISMATCH', 'duplicate artifact')
            seen.add(item['path'])
            if (not path.is_file() or path.stat().st_size != item['size']
                    or hash_bytes(path.read_bytes()) != item['sha256']):
                raise RouterError('ARTIFACT_MISMATCH')

    def read(self, run_id: str) -> dict:
        run = self._run(run_id)
        receipt_path = self._path(run, 'invocation-receipt.json')
        if not receipt_path.exists():
            raise RouterError('INCOMPLETE_RECEIPT')
        value = strict_json(receipt_path.read_bytes())
        pending = strict_json(self._path(run, 'pending.json').read_bytes())
        if value.get('invocation_id') != run_id or any(value.get(k) != v for k, v in pending.items()):
            raise RouterError('RECEIPT_ASSOCIATION_MISMATCH')
        self._verify_artifacts(run, value)
        return value

    def recover(self, run_id: str) -> dict:
        run = self._run(run_id)
        if (run/'invocation-receipt.json').exists():
            return self.read(run_id)
        pending = strict_json(self._path(run, 'pending.json').read_bytes())
        observation = run/'observations.json'
        facts = strict_json(self._path(run, 'observations.json').read_bytes()) if observation.exists() else {}
        return pending | {'outcome': 'unknown', 'replay_allowed': False, 'last_observations': facts}
