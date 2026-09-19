"""Parent-only scoped candidate lifecycle; this module never runs project gates or workers."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from .contracts import RouterError, canonical_bytes, hash_bytes
from .resolver import verify
from .atomic_apply import exchange_owned_file


_SCHEMA_VERSION = 1


def prepare_candidate(manifest: dict, destination: Path) -> dict:
    """Copy the sealed baseline into a non-worktree candidate overlay with exact owned files."""
    root, records, owned = _derived_contract(manifest)
    _require_clean_tracked_targets(root, owned)
    candidate_root = Path(destination).absolute()
    if candidate_root.exists() or candidate_root.is_symlink():
        raise RouterError('CANDIDATE_EXISTS')
    candidate_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.candidate-', dir=candidate_root.parent))
    try:
        for source, record in zip(manifest['sources'], records, strict=True):
            relative = Path(record['relative'])
            target = _open_candidate_path(temporary, relative, create=True)
            data = (Path(manifest['snapshot_root']) / source['snapshot_path']).read_bytes()
            if hash_bytes(data) != source['sha256']:
                raise RouterError('SNAPSHOT_CHANGED', source['snapshot_path'])
            target.write_bytes(data)
            owned_path = record['owned']
            target.chmod(source['mode'] | stat.S_IWUSR if owned_path else source['mode'] & ~0o222)
        _lock_candidate_directories(temporary)
        temporary.rename(candidate_root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    result = {'schema_version': _SCHEMA_VERSION, 'candidate_root': str(candidate_root),
              'source_seal': manifest['seal'], 'source_manifest': manifest,
              'source_preimage': _source_preimage(records), 'files': records, 'owned_paths': sorted(owned)}
    result['seal'] = _seal(result)
    return result


def seal_candidate(candidate: dict) -> dict:
    """Freeze a complete candidate and prove that its nonowned baseline did not change."""
    _validate_candidate(candidate)
    _verify_candidate_seal(candidate)
    manifest = candidate['source_manifest']
    root = Path(candidate['candidate_root'])
    files = _validate_candidate_tree(root, candidate['files'])
    sealed_root = root.with_name(root.name + '.sealed')
    if sealed_root.exists() or sealed_root.is_symlink():
        raise RouterError('CANDIDATE_SEALED_EXISTS')
    _copy_immutable(root, sealed_root, files)
    _verify_immutable_tree(sealed_root, files)
    result = {'schema_version': _SCHEMA_VERSION, 'candidate_root': str(root),
              'sealed_root': str(sealed_root), 'source_seal': candidate['source_seal'],
              'source_manifest': manifest, 'source_preimage': candidate['source_preimage'],
              'files': files, 'owned_paths': candidate['owned_paths']}
    result['seal'] = _seal(result)
    return result


def apply_candidate(sealed: dict, *, verified_candidate_hash: str) -> dict:
    """Atomically replace only exact owned host files after an exact test-result binding."""
    _validate_sealed(sealed)
    if verified_candidate_hash != sealed['seal']:
        raise RouterError('TEST_BINDING_MISMATCH')
    _verify_candidate_seal(sealed)
    manifest = sealed['source_manifest']
    root, _records, owned = _derived_contract(manifest)
    if len(owned) != 1:
        raise RouterError('UNSUPPORTED_MULTIFILE_APPLY')
    _require_clean_tracked_targets(root, owned)
    _verify_immutable_tree(Path(sealed['sealed_root']), sealed['files'])
    applied = []
    for record in sealed['files']:
        if not record['owned']:
            continue
        data = _read_sealed_file(Path(sealed['sealed_root']), record)
        exchange = exchange_owned_file(root, record, data)
        if exchange['classification'] != 'APPLIED':
            return {'classification': exchange['classification'], 'exchange': exchange,
                    'candidate_seal': sealed['seal'], 'applied': []}
        applied.append({'path': record['source_path'], 'sha256': record['candidate_sha256']})
    receipt = {'schema_version': _SCHEMA_VERSION, 'source_seal': sealed['source_seal'],
               'candidate_seal': sealed['seal'], 'verified_candidate_hash': verified_candidate_hash,
               'classification': 'APPLIED', 'exchange': exchange, 'applied': applied}
    receipt['seal'] = _seal(receipt)
    return receipt


def _project_sources(manifest: dict, root: Path) -> dict[str, dict]:
    result = {}
    for source in manifest['sources']:
        path = Path(source['path'])
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if str(path) in result:
            raise RouterError('INVALID_CANDIDATE', 'duplicate project source')
        result[str(path)] = source
    return result


def _owned_sources(task: dict, root: Path, sources: dict[str, dict]) -> set[str]:
    owned = set()
    for raw in task['write_paths']:
        path = Path(raw)
        if not path.is_absolute():
            path = Path(task['cwd']) / path
        path = path.absolute()
        _reject_symlinks(path)
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise RouterError('WRITER_SCOPE_VIOLATION', str(path)) from exc
        if str(resolved) not in sources:
            raise RouterError('WRITER_SCOPE_VIOLATION', str(resolved))
        info = resolved.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise RouterError('WRITER_SCOPE_VIOLATION', str(resolved))
        owned.add(str(resolved))
    if not owned:
        raise RouterError('WRITER_SCOPE_VIOLATION', 'no exact owned target')
    return owned


def _require_clean_tracked_targets(root: Path, owned: set[str]) -> None:
    if not (root / '.git').exists():
        return
    relative = [str(Path(path).relative_to(root)) for path in sorted(owned)]
    for path in relative:
        tracked = subprocess.run(['git', '-C', str(root), 'ls-files', '--error-unmatch', '--', path],
                                 capture_output=True, check=False)
        if tracked.returncode:
            raise RouterError('WRITER_UNTRACKED_TARGET', path)
        status = subprocess.run(['git', '-C', str(root), 'status', '--porcelain=v1', '-z', '--', path],
                                capture_output=True, check=False)
        if status.returncode or status.stdout:
            raise RouterError('WRITER_DIRTY_TARGET', path)


def _relative_snapshot(source: dict) -> Path:
    relative = Path(source['snapshot_path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise RouterError('INVALID_CANDIDATE', 'snapshot path escapes candidate')
    return relative


def _record(source: dict, relative: Path, owned: bool) -> dict:
    return {'source_path': source['path'], 'relative': relative.as_posix(), 'owned': owned,
            'source_sha256': source['sha256'], 'source_size': source['size'],
            'source_mode': source['mode'], 'candidate_sha256': source['sha256'],
            'candidate_size': source['size'],
            'candidate_mode': source['mode'] | stat.S_IWUSR if owned else source['mode'] & ~0o222}


def _source_preimage(records: list[dict]) -> list[dict]:
    return [{'path': record['source_path'], 'sha256': record['source_sha256'],
             'size': record['source_size'], 'mode': record['source_mode']} for record in records]


def _derived_contract(manifest: dict) -> tuple[Path, list[dict], set[str]]:
    """Recreate all authority-bearing metadata from the resolver manifest alone."""
    verify(manifest)
    try:
        task, root = manifest['task'], Path(manifest['project']['root'])
        sources = manifest['sources']
    except (KeyError, TypeError) as exc:
        raise RouterError('INVALID_CANDIDATE') from exc
    if task.get('role') != 'implementer' or 'candidate-write' not in task.get('permissions', []):
        raise RouterError('AUTHORITY_VIOLATION', 'candidate writes require implementer authority')
    project_sources = _project_sources(manifest, root)
    owned = _owned_sources(task, root, project_sources)
    records, source_paths, relatives = [], set(), set()
    if not isinstance(sources, list):
        raise RouterError('INVALID_CANDIDATE')
    for source in sources:
        relative = _relative_snapshot(source)
        source_path = source.get('path') if isinstance(source, dict) else None
        if not isinstance(source_path, str) or source_path in source_paths or relative.as_posix() in relatives:
            raise RouterError('INVALID_CANDIDATE', 'duplicate or invalid source record')
        source_paths.add(source_path)
        relatives.add(relative.as_posix())
        records.append(_record(source, relative, source_path in owned))
    return root, records, owned


def _validate_candidate_tree(root: Path, records: list[dict]) -> list[dict]:
    _verify_expected_tree(root, records)
    final = []
    for record in records:
        path = root / record['relative']
        info = path.stat()
        data = path.read_bytes()
        digest = hash_bytes(data)
        mode = stat.S_IMODE(info.st_mode)
        if mode != record['candidate_mode']:
            raise RouterError('CANDIDATE_MODE_CHANGED', record['relative'])
        if not record['owned'] and (digest != record['source_sha256'] or len(data) != record['source_size']):
            raise RouterError('CANDIDATE_BASELINE_CHANGED', record['relative'])
        final.append(record | {'candidate_sha256': digest, 'candidate_size': len(data)})
    return final


def _copy_immutable(source_root: Path, sealed_root: Path, records: list[dict]) -> None:
    temporary = Path(tempfile.mkdtemp(prefix='.sealed-', dir=sealed_root.parent))
    try:
        for record in records:
            target = _open_candidate_path(temporary, Path(record['relative']), create=True)
            data = _read_candidate_file(source_root, record)
            target.write_bytes(data)
            target.chmod(record['candidate_mode'] & ~0o222)
        _lock_candidate_directories(temporary)
        temporary.rename(sealed_root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _verify_immutable_tree(root: Path, records: list[dict]) -> None:
    _verify_expected_tree(root, records)
    for record in records:
        path = root / record['relative']
        info = path.stat()
        if (hash_bytes(path.read_bytes()) != record['candidate_sha256']
                or info.st_size != record['candidate_size']
                or stat.S_IMODE(info.st_mode) != (record['candidate_mode'] & ~0o222)):
            raise RouterError('CANDIDATE_SNAPSHOT_CHANGED', record['relative'])


def _read_sealed_file(root: Path, record: dict) -> bytes:
    return _read_bound_file(root, record, record['candidate_mode'] & ~0o222,
                            'CANDIDATE_SNAPSHOT_CHANGED')


def _read_candidate_file(root: Path, record: dict) -> bytes:
    return _read_bound_file(root, record, record['candidate_mode'], 'CANDIDATE_SNAPSHOT_CHANGED')


def _read_bound_file(root: Path, record: dict, mode: int, error: str) -> bytes:
    parent_fd, name = _open_parent_dir(root, Path(record['relative']))
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != mode:
                raise RouterError(error, record['relative'])
            data = _read_exact(descriptor, record['candidate_size'])
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise RouterError(error, record['relative']) from exc
    finally:
        os.close(parent_fd)
    if len(data) != record['candidate_size'] or hash_bytes(data) != record['candidate_sha256']:
        raise RouterError(error, record['relative'])
    return data


def _verify_expected_tree(root: Path, records: list[dict]) -> None:
    if root.is_symlink() or not root.is_dir():
        raise RouterError('CANDIDATE_TREE_CHANGED')
    expected_files = {record['relative'] for record in records}
    expected_dirs = {'.'}
    for relative in expected_files:
        parent = Path(relative).parent
        while str(parent) != '.':
            expected_dirs.add(parent.as_posix())
            parent = parent.parent
    for item in root.rglob('*'):
        relative = item.relative_to(root).as_posix()
        if item.is_symlink() or (item.is_dir() and relative not in expected_dirs) or (
                item.is_file() and relative not in expected_files) or not (item.is_dir() or item.is_file()):
            raise RouterError('CANDIDATE_TREE_CHANGED', relative)
    for relative in expected_files:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise RouterError('CANDIDATE_TREE_CHANGED', relative)


def _open_parent_dir(root: Path, relative: Path) -> tuple[int, str]:
    if relative.is_absolute() or '..' in relative.parts or not relative.name:
        raise RouterError('WRITER_SCOPE_VIOLATION')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    try:
        for part in relative.parts[:-1]:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor, relative.name
    except Exception:
        os.close(descriptor)
        raise


def _read_exact(descriptor: int, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) <= size:
        chunk = os.read(descriptor, min(65536, size + 1 - len(chunks)))
        if not chunk:
            break
        chunks.extend(chunk)
    return bytes(chunks)


def _open_candidate_path(root: Path, relative: Path, *, create: bool) -> Path:
    path = root / relative
    if relative.is_absolute() or '..' in relative.parts:
        raise RouterError('INVALID_CANDIDATE')
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _lock_candidate_directories(root: Path) -> None:
    for directory in sorted((item for item in root.rglob('*') if item.is_dir()), reverse=True):
        directory.chmod(0o700)
    root.chmod(0o700)


def _reject_symlinks(path: Path) -> None:
    current = path
    while current != current.parent:
        if current.is_symlink():
            raise RouterError('SYMLINK_FORBIDDEN', str(current))
        current = current.parent


def _validate_candidate(candidate: dict) -> None:
    required = {'schema_version', 'candidate_root', 'source_seal', 'source_manifest', 'source_preimage',
                'files', 'owned_paths', 'seal'}
    if not isinstance(candidate, dict) or set(candidate) != required or candidate['schema_version'] != _SCHEMA_VERSION:
        raise RouterError('INVALID_CANDIDATE')
    _root, expected, owned = _derived_contract(candidate['source_manifest'])
    if (candidate['source_seal'] != candidate['source_manifest'].get('seal')
            or candidate['source_preimage'] != _source_preimage(expected)
            or candidate['owned_paths'] != sorted(owned)
            or candidate['files'] != expected):
        raise RouterError('INVALID_CANDIDATE')


def _validate_sealed(sealed: dict) -> None:
    required = {'schema_version', 'candidate_root', 'sealed_root', 'source_seal', 'source_manifest',
                'source_preimage', 'files', 'owned_paths', 'seal'}
    if not isinstance(sealed, dict) or set(sealed) != required or sealed['schema_version'] != _SCHEMA_VERSION:
        raise RouterError('INVALID_CANDIDATE')
    _root, expected, owned = _derived_contract(sealed['source_manifest'])
    if (sealed['source_seal'] != sealed['source_manifest'].get('seal')
            or sealed['source_preimage'] != _source_preimage(expected)
            or sealed['owned_paths'] != sorted(owned)
            or not _sealed_records_match(sealed['files'], expected)):
        raise RouterError('INVALID_CANDIDATE')


def _sealed_records_match(records: object, expected: list[dict]) -> bool:
    if not isinstance(records, list) or len(records) != len(expected):
        return False
    for actual, baseline in zip(records, expected, strict=True):
        if not isinstance(actual, dict) or set(actual) != set(baseline):
            return False
        for key, value in baseline.items():
            if key not in ('candidate_sha256', 'candidate_size') and actual[key] != value:
                return False
        if (not isinstance(actual['candidate_sha256'], str) or len(actual['candidate_sha256']) != 64
                or type(actual['candidate_size']) is not int or actual['candidate_size'] < 0):
            return False
        if not baseline['owned'] and (actual['candidate_sha256'] != baseline['source_sha256']
                                      or actual['candidate_size'] != baseline['source_size']):
            return False
    return True


def _verify_candidate_seal(candidate: dict) -> None:
    if candidate['seal'] != _seal({key: value for key, value in candidate.items() if key != 'seal'}):
        raise RouterError('INVALID_CANDIDATE_SEAL')


def _seal(value: dict) -> str:
    return hash_bytes(canonical_bytes(value))
