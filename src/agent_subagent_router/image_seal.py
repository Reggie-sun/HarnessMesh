"""Private immutable storage for image-task/v1 PNG inputs."""
import hashlib
import math
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any

from .contracts import RouterError, canonical_bytes, strict_json
from .image_contract import (
    MAX_CONTEXT_BYTES,
    ImageTaskContract,
    _open_absolute_file_nofollow,
    _read_open_file,
    _validate_png_bytes,
    read_png,
)

_SEAL_SCHEMA = 'image-seal/v1'
_MANIFEST_NAME = re.compile(r'^manifest-([0-9a-f]{64})\.json$')
_SEAL_DIR_NAME = re.compile(r'^seal-[0-9a-f]{32}$')
_MAX_MANIFEST_BYTES = 16 * 1024 * 1024
_REQUIRED_PIN_GROUPS = {'adapter', 'image', 'protocol', 'runtime'}
_READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _fail(detail: str):
    raise RouterError('INVALID_IMAGE_SEAL', detail)


def _path_components(value: str) -> list[str]:
    if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        _fail('descriptor-based no-follow storage is unavailable')
    if type(value) is not str or not os.path.isabs(value) or '\x00' in value:
        _fail('seal paths must be absolute')
    components = value.split('/')
    if '..' in components:
        _fail('seal paths must not traverse parent paths')
    return [component for component in components if component not in ('', '.')]


def _open_directory(path: str) -> int:
    parts = _path_components(path)
    descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in parts:
            following = os.open(component, _DIR_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = following
        result = descriptor
        descriptor = -1
        return result
    except OSError as exc:
        raise RouterError(
            'INVALID_IMAGE_SEAL', 'seal directory could not be opened safely',
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _open_or_create_private_root(path: str) -> tuple[int, str]:
    parts = _path_components(path)
    descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    normalized = '/' + '/'.join(parts)
    try:
        for component in parts:
            try:
                following = os.open(component, _DIR_FLAGS, dir_fd=descriptor)
            except FileNotFoundError:
                os.mkdir(component, 0o700, dir_fd=descriptor)
                following = os.open(component, _DIR_FLAGS, dir_fd=descriptor)
                os.fchmod(following, 0o700)
            os.close(descriptor)
            descriptor = following
        info = os.fstat(descriptor)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            _fail('store_root must be an owner-only 0700 directory owned by this user')
        result = descriptor
        descriptor = -1
        return result, normalized
    except OSError as exc:
        raise RouterError(
            'INVALID_IMAGE_SEAL', 'store_root could not be opened or created safely',
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _owner_mode(info: os.stat_result, mode: int, *, directory: bool) -> bool:
    return (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) and (
        info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == mode
    )


def _validate_json(value: Any, *, depth: int = 0) -> None:
    if depth > 12:
        _fail('pins exceed the supported JSON nesting depth')
    if value is None or type(value) in (bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            _fail('pins contain a non-finite number')
        return
    if type(value) is str:
        try:
            if len(value.encode('utf-8', 'strict')) > 4096:
                _fail('pin string exceeds the supported length')
        except UnicodeError as exc:
            raise RouterError('INVALID_IMAGE_SEAL', 'pins contain invalid Unicode') from exc
        return
    if type(value) is list:
        if len(value) > 4096:
            _fail('pin array exceeds the supported length')
        for item in value:
            _validate_json(item, depth=depth + 1)
        return
    if type(value) is dict:
        if len(value) > 256 or any(type(key) is not str or not key for key in value):
            _fail('pins must use bounded string keys')
        for key, item in value.items():
            _validate_json(key, depth=depth + 1)
            _validate_json(item, depth=depth + 1)
        return
    _fail('pins must be a strict JSON object')


def _validate_pins(pins: Any) -> dict[str, Any]:
    if type(pins) is not dict or not pins:
        _fail('pins must be a non-empty JSON object')
    if not _REQUIRED_PIN_GROUPS.issubset(pins):
        _fail('pins must bind runtime, adapter, image, and protocol fingerprints')
    copied: dict[str, Any] = {}
    for name, value in pins.items():
        if type(name) is not str or not name or len(name) > 128:
            _fail('pin group names must be bounded strings')
        if type(value) is not dict or not value:
            _fail('each pin group must be a non-empty JSON object')
        fingerprint = value.get('sha256')
        if (not isinstance(fingerprint, str) or len(fingerprint) != 64
                or any(char not in '0123456789abcdef' for char in fingerprint)):
            _fail('each pin group must include a lowercase sha256 fingerprint')
        _validate_json(value)
        copied[name] = value
    try:
        canonical_bytes(copied)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise RouterError('INVALID_IMAGE_SEAL', 'pins are not canonical JSON') from exc
    return strict_json(canonical_bytes(copied))


def _verify_selected_refs(task_data: dict[str, Any]) -> None:
    """Bind every declared accepted ref to current regular-file bytes without following links."""
    if not task_data['selected_refs']:
        _fail('image task seal requires at least one accepted ref')
    prompt_bytes = (len(task_data['system_text'].encode('utf-8'))
                    + len(task_data['task_text'].encode('utf-8')))
    total_bytes = prompt_bytes
    context_limit = task_data['budgets']['context_bytes']
    for ref in task_data['selected_refs']:
        try:
            descriptor = _open_absolute_file_nofollow(ref['path'])
        except RouterError as exc:
            if exc.code == 'UNSUPPORTED_REQUIRED_CAPABILITY':
                raise
            raise RouterError(
                'INVALID_IMAGE_SEAL', 'selected ref path is not safely readable',
            ) from exc
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_CONTEXT_BYTES:
                _fail('selected ref is not a bounded regular file')
            total_bytes += info.st_size
            if total_bytes > context_limit:
                _fail('selected refs and prompt exceed context_bytes')
            content = _read_open_file(descriptor, info.st_size)
        except OSError as exc:
            raise RouterError(
                'INVALID_IMAGE_SEAL', 'selected ref could not be read safely',
            ) from exc
        finally:
            os.close(descriptor)
        if hashlib.sha256(content).hexdigest() != ref['sha256']:
            _fail('selected ref bytes do not match the accepted digest')


def _write_file_at(directory_fd: int, name: str, data: bytes) -> None:
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=directory_fd)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                _fail('short write while sealing image bytes')
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _create_dir_at(parent_fd: int, name: str, mode: int) -> int:
    os.mkdir(name, mode, dir_fd=parent_fd)
    try:
        descriptor = os.open(name, _DIR_FLAGS, dir_fd=parent_fd)
        os.fchmod(descriptor, mode)
        return descriptor
    except Exception:
        try:
            os.rmdir(name, dir_fd=parent_fd)
        except OSError:
            pass
        raise


def _remove_new_seal(root_fd: int, seal_name: str, seal_fd: int, blobs_fd: int | None,
                     file_names: list[str]) -> None:
    if blobs_fd is None:
        try:
            blobs_fd = os.open('blobs', _DIR_FLAGS, dir_fd=seal_fd)
        except OSError:
            pass
    if blobs_fd is not None:
        try:
            os.fchmod(blobs_fd, 0o700)
            for name in os.listdir(blobs_fd):
                try:
                    os.unlink(name, dir_fd=blobs_fd)
                except OSError:
                    pass
        finally:
            os.close(blobs_fd)
        try:
            os.rmdir('blobs', dir_fd=seal_fd)
        except OSError:
            pass
    for name in file_names:
        try:
            os.unlink(name, dir_fd=seal_fd)
        except OSError:
            pass
    try:
        os.fchmod(seal_fd, 0o700)
    except OSError:
        pass
    try:
        os.close(seal_fd)
    except OSError:
        pass
    try:
        os.rmdir(seal_name, dir_fd=root_fd)
    except OSError:
        pass


def _view(manifest: dict[str, Any], manifest_path: str) -> dict[str, Any]:
    result = strict_json(canonical_bytes(manifest))
    result['manifest_path'] = manifest_path
    seal_directory = os.path.dirname(manifest_path)
    for image in result['images']:
        image['blob_path'] = os.path.join(seal_directory, image['blob'])
    return result


def seal_images(task: ImageTaskContract, store_root: Path, pins: dict) -> dict:
    """Freeze validated PNG bytes and their exact task/pin bindings in a private store."""
    if isinstance(task, ImageTaskContract):
        contract = ImageTaskContract.from_dict(task.to_dict())
    elif type(task) is dict:
        contract = ImageTaskContract.from_dict(task)
    else:
        _fail('task must be an ImageTaskContract or image-task/v1 object')
    task_data = contract.to_dict()
    pin_data = _validate_pins(pins)
    _verify_selected_refs(task_data)
    task_bytes = canonical_bytes(task_data)
    pin_bytes = canonical_bytes(pin_data)
    if len(task_bytes) + len(pin_bytes) > _MAX_MANIFEST_BYTES // 2:
        _fail('task and pins exceed the supported manifest size')

    image_bytes: list[bytes] = []
    total_png = 0
    total_payload = 0
    for descriptor in task_data['images']:
        data = read_png(descriptor)
        total_png += len(data)
        total_payload += 4 * ((len(data) + 2) // 3)
        image_bytes.append(data)
    if total_png > task_data['budgets']['max_png_bytes']:
        _fail('actual PNG bytes exceed max_png_bytes')
    if total_payload > task_data['budgets']['payload_bytes']:
        _fail('base64 PNG bytes exceed payload_bytes')
    if len(image_bytes) > task_data['budgets']['max_images']:
        _fail('image count exceeds max_images')

    try:
        root_path = os.fspath(store_root)
    except TypeError as exc:
        raise RouterError('INVALID_IMAGE_SEAL', 'store_root must be a filesystem path') from exc
    if type(root_path) is not str:
        _fail('store_root must use a text filesystem path')
    root_fd, normalized_root = _open_or_create_private_root(root_path)
    seal_name = 'seal-' + secrets.token_hex(16)
    seal_fd = None
    blobs_fd = None
    created_files: list[str] = []
    verified = None
    try:
        seal_fd = _create_dir_at(root_fd, seal_name, 0o700)
        blobs_fd = _create_dir_at(seal_fd, 'blobs', 0o700)
        images = []
        for index, (descriptor, data) in enumerate(
            zip(task_data['images'], image_bytes, strict=True),
        ):
            blob_name = f'{index:04d}-{descriptor["sha256"]}.png'
            _write_file_at(blobs_fd, blob_name, data)
            image = {
                'image_id': descriptor['image_id'],
                'blob': f'blobs/{blob_name}',
                'byte_length': descriptor['byte_length'],
                'sha256': descriptor['sha256'],
                'width': descriptor['width'],
                'height': descriptor['height'],
            }
            images.append(image)
        manifest = {
            'schema': _SEAL_SCHEMA,
            'task': task_data,
            'task_sha256': hashlib.sha256(task_bytes).hexdigest(),
            'pins': pin_data,
            'pins_sha256': hashlib.sha256(pin_bytes).hexdigest(),
            'images': images,
        }
        manifest_bytes = canonical_bytes(manifest)
        if len(manifest_bytes) > _MAX_MANIFEST_BYTES:
            _fail('manifest exceeds the supported size')
        manifest_name = f'manifest-{hashlib.sha256(manifest_bytes).hexdigest()}.json'
        created_files.append(manifest_name)
        _write_file_at(seal_fd, manifest_name, manifest_bytes)
        os.fsync(blobs_fd)
        os.fchmod(blobs_fd, 0o500)
        os.fsync(blobs_fd)
        os.fsync(seal_fd)
        os.fchmod(seal_fd, 0o500)
        os.fsync(seal_fd)
        os.fsync(root_fd)
        manifest_path = os.path.join(normalized_root, seal_name, manifest_name)
        verified = verify_image_seal(manifest_path)
    except Exception:
        if seal_fd is not None:
            _remove_new_seal(root_fd, seal_name, seal_fd, blobs_fd, created_files)
            seal_fd = None
            blobs_fd = None
        raise
    finally:
        if blobs_fd is not None:
            os.close(blobs_fd)
        if seal_fd is not None:
            os.close(seal_fd)
        os.close(root_fd)
    return verified


def _read_at(directory_fd: int, name: str, maximum: int, expected_mode: int) -> bytes:
    descriptor = os.open(name, _READ_FLAGS, dir_fd=directory_fd)
    try:
        info = os.fstat(descriptor)
        if (not _owner_mode(info, expected_mode, directory=False)
                or not 1 <= info.st_size <= maximum):
            _fail('sealed file has unsafe type, owner, mode, or length')
        return _read_open_file(descriptor, info.st_size)
    except OSError as exc:
        raise RouterError('INVALID_IMAGE_SEAL', 'sealed file could not be read safely') from exc
    finally:
        os.close(descriptor)


def _canonical_digest(value: Any, name: str) -> str:
    digest = value.get(name)
    if (not isinstance(digest, str) or len(digest) != 64
            or any(char not in '0123456789abcdef' for char in digest)):
        _fail(f'invalid {name} in manifest')
    return digest


def verify_image_seal(manifest_path: Path) -> dict:
    """Validate the immutable manifest and every ordered PNG blob before returning paths."""
    try:
        path = os.fspath(manifest_path)
    except TypeError as exc:
        raise RouterError('INVALID_IMAGE_SEAL', 'manifest_path must be a filesystem path') from exc
    if type(path) is not str:
        _fail('manifest_path must use a text filesystem path')
    parts = _path_components(path)
    if len(parts) < 3:
        _fail('manifest_path is outside a private seal directory')
    manifest_name = parts[-1]
    named_digest = _MANIFEST_NAME.fullmatch(manifest_name)
    seal_name = parts[-2]
    if not named_digest or not _SEAL_DIR_NAME.fullmatch(seal_name):
        _fail('manifest path does not carry a seal digest identity')
    normalized = '/' + '/'.join(parts)
    seal_path = os.path.dirname(normalized)
    root_path = os.path.dirname(seal_path)
    root_fd = _open_directory(root_path)
    seal_fd = None
    blobs_fd = None
    try:
        root_info = os.fstat(root_fd)
        if not _owner_mode(root_info, 0o700, directory=True):
            _fail('contract store root is not private')
        seal_fd = os.open(seal_name, _DIR_FLAGS, dir_fd=root_fd)
        seal_info = os.fstat(seal_fd)
        if not _owner_mode(seal_info, 0o500, directory=True):
            _fail('seal directory is not immutable and owner-only')
        if set(os.listdir(seal_fd)) != {manifest_name, 'blobs'}:
            _fail('seal directory contains missing or extra entries')
        manifest_bytes = _read_at(seal_fd, manifest_name, _MAX_MANIFEST_BYTES, 0o400)
        if hashlib.sha256(manifest_bytes).hexdigest() != named_digest.group(1):
            _fail('manifest bytes do not match their immutable name')
        try:
            manifest = strict_json(manifest_bytes)
        except RouterError as exc:
            raise RouterError('INVALID_IMAGE_SEAL', 'manifest is not strict JSON') from exc
        if type(manifest) is not dict or set(manifest) != {
                'schema', 'task', 'task_sha256', 'pins', 'pins_sha256', 'images'}:
            _fail('manifest has missing or unknown fields')
        if manifest['schema'] != _SEAL_SCHEMA:
            _fail('unsupported seal schema')
        if canonical_bytes(manifest) != manifest_bytes:
            _fail('manifest is not in canonical serialization')

        contract = ImageTaskContract.from_dict(manifest['task'])
        task_data = contract.to_dict()
        if (hashlib.sha256(canonical_bytes(task_data)).hexdigest()
                != _canonical_digest(manifest, 'task_sha256')):
            _fail('task digest does not match manifest')
        _verify_selected_refs(task_data)
        pins = _validate_pins(manifest['pins'])
        if (hashlib.sha256(canonical_bytes(pins)).hexdigest()
                != _canonical_digest(manifest, 'pins_sha256')):
            _fail('pin digest does not match manifest')
        if (type(manifest['images']) is not list
                or len(manifest['images']) != len(task_data['images'])):
            _fail('manifest image list does not match task')

        blobs_fd = os.open('blobs', _DIR_FLAGS, dir_fd=seal_fd)
        blobs_info = os.fstat(blobs_fd)
        if not _owner_mode(blobs_info, 0o500, directory=True):
            _fail('blob directory is not immutable and owner-only')
        expected_entries: set[str] = set()
        for index, (item, source) in enumerate(
            zip(manifest['images'], task_data['images'], strict=True),
        ):
            if type(item) is not dict or set(item) != {
                    'image_id', 'blob', 'byte_length', 'sha256', 'width', 'height'}:
                _fail('manifest image record has missing or unknown fields')
            expected_blob = f'blobs/{index:04d}-{source["sha256"]}.png'
            expected_record = {
                'image_id': source['image_id'],
                'blob': expected_blob,
                'byte_length': source['byte_length'],
                'sha256': source['sha256'],
                'width': source['width'],
                'height': source['height'],
            }
            if item != expected_record:
                _fail('manifest image binding does not match task descriptor')
            blob_name = expected_blob.split('/', 1)[1]
            expected_entries.add(blob_name)
            blob_fd = os.open(blob_name, _READ_FLAGS, dir_fd=blobs_fd)
            try:
                blob_info = os.fstat(blob_fd)
                if not _owner_mode(blob_info, 0o400, directory=False):
                    _fail('PNG blob is not immutable and owner-only')
                blob = _read_open_file(blob_fd, source['byte_length'])
            except OSError as exc:
                raise RouterError(
                    'INVALID_IMAGE_SEAL', 'PNG blob could not be read safely',
                ) from exc
            finally:
                os.close(blob_fd)
            _validate_png_bytes(blob, source)
        if set(os.listdir(blobs_fd)) != expected_entries:
            _fail('blob directory contains missing or extra files')
        return _view(manifest, normalized)
    except OSError as exc:
        raise RouterError('INVALID_IMAGE_SEAL', 'seal path could not be opened safely') from exc
    finally:
        if blobs_fd is not None:
            os.close(blobs_fd)
        if seal_fd is not None:
            os.close(seal_fd)
        os.close(root_fd)
