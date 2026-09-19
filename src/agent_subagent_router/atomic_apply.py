"""Single-file Linux exchange with durable intent and retained displaced inode.

This is not a filesystem compare-and-swap. A conflict can be observed after the
exchange; both objects remain available and no automatic rollback is attempted.
"""
import ctypes
import errno
import os
from pathlib import Path
import stat
import uuid

from .contracts import RouterError, hash_bytes
from .receipts import atomic_json


def _exchange(source_fd, source_name, target_fd, target_name):
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None:
        raise OSError(errno.ENOSYS, 'renameat2 unavailable')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source_fd, os.fsencode(source_name), target_fd, os.fsencode(target_name), 2):
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def _facts(directory, name, limit):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise RouterError('SOURCE_CHANGED')
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(descriptor, min(65536, limit+1-len(data)))
            if not chunk:
                break
            data.extend(chunk)
        return {'sha256': hash_bytes(bytes(data)), 'size': len(data),
                'mode': stat.S_IMODE(info.st_mode), 'device': info.st_dev, 'inode': info.st_ino}
    finally:
        os.close(descriptor)


def _open_parent(root, relative):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    try:
        for part in relative.parts[:-1]:
            following = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = following
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _canonical_parent_matches(root, relative, expected_root, expected_parent):
    try:
        root_info = root.stat()
        if (root_info.st_dev, root_info.st_ino) != expected_root:
            return False
        descriptor = _open_parent(root, relative)
        try:
            current = os.fstat(descriptor)
            return (current.st_dev, current.st_ino) == expected_parent
        finally:
            os.close(descriptor)
    except OSError:
        return False


def exchange_owned_file(root: Path, record: dict, data: bytes) -> dict:
    relative = Path(record['source_path']).relative_to(root)
    if '..' in relative.parts or not relative.name:
        raise RouterError('WRITER_SCOPE_VIOLATION')
    parent_fd = _open_parent(root, relative)
    root_info, parent_info = root.stat(), os.fstat(parent_fd)
    root_identity = (root_info.st_dev, root_info.st_ino)
    parent_identity = (parent_info.st_dev, parent_info.st_ino)
    recovery_fd = None
    recovery = None
    exchanged = False
    expected = {'sha256': record['source_sha256'], 'size': record['source_size'], 'mode': record['source_mode']}
    after = {'sha256': hash_bytes(data), 'size': len(data), 'mode': record['source_mode']}
    limit = max(len(data), record['source_size']) + 1024*1024
    try:
        before = _facts(parent_fd, relative.name, limit)
        if any(before[k] != value for k, value in expected.items()):
            raise RouterError('SOURCE_CHANGED', str(relative))
        # Same filesystem, private parent-owned storage; never unlinked after exchange.
        recovery_name = '.router-recovery-'+uuid.uuid4().hex
        os.mkdir(recovery_name, 0o700, dir_fd=parent_fd)
        recovery_fd = os.open(recovery_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        recovery = Path(os.readlink(f'/proc/self/fd/{recovery_fd}'))
        descriptor = os.open('displaced', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=recovery_fd)
        try:
            os.fchmod(descriptor, record['source_mode'])
            offset = 0
            while offset < len(data):
                offset += os.write(descriptor, data[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        staged = _facts(recovery_fd, 'displaced', limit)
        if any(staged[k] != value for k, value in after.items()):
            raise RouterError('CANDIDATE_SNAPSHOT_CHANGED')
        intent = {'schema_version': 1, 'kind': 'single-file-exchange', 'state': 'PREPARED',
                  'target': str(root/relative), 'recovery_path': str(recovery),
                  'retained_object': str(recovery/'displaced'), 'preimage': before,
                  'candidate': staged, 'automatic_rollback': False}
        atomic_json(recovery/'intent.json', intent)
        os.fsync(recovery_fd)
        os.fsync(parent_fd)
        if not _canonical_parent_matches(root, relative, root_identity, parent_identity):
            raise RouterError('SOURCE_CHANGED', 'canonical parent directory changed; recovery '+str(recovery))
        _exchange(recovery_fd, 'displaced', parent_fd, relative.name)
        exchanged = True
        recovery = Path(os.readlink(f'/proc/self/fd/{recovery_fd}'))
        intent.update(recovery_path=str(recovery), retained_object=str(recovery/'displaced'))
        result = intent | {'state': 'EXCHANGED', 'classification': 'APPLY_OUTCOME_UNKNOWN'}
        try:
            displaced = _facts(recovery_fd, 'displaced', limit)
            current = _facts(parent_fd, relative.name, limit)
            result.update(displaced=displaced, current=current)
            original_matches = all(displaced[k] == value for k, value in expected.items())
            candidate_matches = current == staged and _canonical_parent_matches(root, relative, root_identity, parent_identity)
            result['classification'] = 'APPLIED' if original_matches and candidate_matches else 'APPLY_CONFLICT'
            os.fsync(recovery_fd)
            os.fsync(parent_fd)
            atomic_json(recovery/'outcome.json', result)
        except (OSError, RouterError) as exc:
            result.update(classification='APPLY_OUTCOME_UNKNOWN', error=type(exc).__name__)
            try:
                atomic_json(recovery/'unknown.json', result)
            except OSError:
                pass  # Durable intent still identifies both objects; never claim not applied.
        return result
    except (OSError, RouterError) as exc:
        if exchanged:
            return {'classification': 'APPLY_OUTCOME_UNKNOWN', 'recovery_path': str(recovery),
                    'target': str(root/relative), 'error': type(exc).__name__}
        if isinstance(exc, RouterError):
            raise
        raise RouterError('WRITER_APPLY_NOT_STARTED', str(recovery) if recovery else str(relative)) from exc
    finally:
        if recovery_fd is not None:
            os.close(recovery_fd)
        os.close(parent_fd)
