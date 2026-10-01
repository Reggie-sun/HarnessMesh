"""Strict image-only task contract and PNG byte validation."""
from bisect import bisect_left
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import PurePosixPath
import re
import stat
import struct
import zlib
from types import MappingProxyType
from typing import Any, Mapping

from .contracts import RouterError

IMAGE_TASK_SCHEMA = 'image-task/v1'
IMAGE_OUTPUT_PROTOCOL = 'JSON_OBJECT/v1'
IMAGE_CONTEXT_POLICY = 'FRESH_SEALED_INPUT/v1'
IMAGE_PROVIDERS = MappingProxyType({'kimi': 'kimi', 'codex': 'openai', 'minimax': 'minimax'})
UNRESTRICTED_SPENDING_SPEC_SHA = 'f96a2fa0ed47e96810c46cda8c221694690badc64689661dbabe4826e0b345eb'
SELECTED_SUBSCRIPTION_MODEL_SPEC_SHA = '622c3ea8c119276b837fbfa9d9bbdcff25f73f52c8dec50d24b7380cc7684570'


def selected_subscription_model(task) -> bool:
    """Only the account-verified, explicitly frozen Astra tuple; no aliases."""
    return (isinstance(task, dict)
        and tuple(task.get(key) for key in ('backend', 'profile', 'model', 'effort'))
            == ('codex', 'subscription-bounded', 'gpt-6-astra', 'high')
        and isinstance(task.get('metadata'), dict)
        and task['metadata'].get('spending_policy') == 'unrestricted'
        and isinstance(task.get('selected_refs'), list)
        and any(isinstance(ref, dict) and ref.get('sha256') == SELECTED_SUBSCRIPTION_MODEL_SPEC_SHA
            and ref.get('accepted') is True for ref in task['selected_refs']))


def unrestricted_spending(task) -> bool:
    policy = task.get('metadata', {}).get('spending_policy')
    if policy is None:
        return False
    if policy != 'unrestricted':
        raise RouterError('IMAGE_SPENDING_POLICY_INVALID')
    route = (task['backend'], task['profile'], task['model'], task['effort'])
    if route not in (('minimax', 'responses-bounded', 'MiniMax-M3', 'provider-default'),
            ('codex', 'subscription-bounded', 'gpt-6.1-sol', 'high'),
            ('codex', 'subscription-bounded', 'gpt-6-luna', 'high')) and not selected_subscription_model(task):
        raise RouterError('IMAGE_ROUTE_MISMATCH')
    if not any(ref['sha256'] == UNRESTRICTED_SPENDING_SPEC_SHA and ref['accepted'] is True
               for ref in task['selected_refs']):
        raise RouterError('IMAGE_SPENDING_ACCEPTANCE_REQUIRED')
    return True


def image_provider(task) -> str:
    if task['backend'] == 'codex' and task['profile'] == 'subscription-bounded':
        return 'codex-subscription'
    return IMAGE_PROVIDERS[task['backend']]


MAX_IMAGES = 1024
MAX_PNG_BYTES = 24 * 1024 * 1024
MAX_NATIVE_PAYLOAD_BYTES = 32 * 1024 * 1024
MAX_IMAGE_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PROMPT_BYTES = 256 * 1024
MAX_IMAGE_DIMENSION = 4096
MAX_CONTEXT_BYTES = 32 * 1024 * 1024
MAX_GENERATION_TOKENS = 32000
MAX_WALL_SECONDS = 3600
MAX_REQUESTS = 64
_MAX_CHUNKS = 100_000
_MAX_PATH_BYTES = 4096
_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
_HEX_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_IDENTIFIER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
_METADATA_KEY = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
_METADATA_VALUE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,31}$')
_METADATA_SENSITIVE = re.compile(
    r'(?:^|_)(?:path|file|token|secret|credential|auth|account|url|uri|prompt|text|'
    r'content|cookie|session|password|api|key|id)(?:_|$)', re.IGNORECASE,
)
_SECRET_PREFIX = (
    'sk-', 'sk_', 'pk-', 'pk_', 'ghp_', 'gho_', 'github_pat_', 'xox',
    'bearer-', 'bearer_', 'token-', 'token_', 'api-', 'api_',
)
_TOP_FIELDS = {
    'schema', 'parent_session_id', 'task_id', 'backend', 'model', 'profile', 'effort',
    'selected_refs', 'system_text', 'task_text', 'images', 'metadata', 'output_protocol',
    'context_policy', 'budgets',
}
_IMAGE_FIELDS = {'image_id', 'path', 'byte_length', 'sha256', 'width', 'height'}
_BUDGET_FIELDS = {
    'max_images', 'max_png_bytes', 'payload_bytes', 'output_bytes', 'context_bytes',
    'generation_tokens', 'wall_seconds', 'idle_seconds', 'request_limit',
}
_REF_FIELDS = {'path', 'sha256', 'accepted'}


def _fail(code: str, detail: str = ''):
    raise RouterError(code, detail)


def _is_int(value: Any) -> bool:
    return type(value) is int


def _bounded_string(value: Any, name: str, maximum: int, *, trim: bool = True) -> str:
    if not isinstance(value, str) or not value or '\x00' in value:
        _fail('INVALID_CONTRACT', f'invalid {name}')
    try:
        encoded = value.encode('utf-8', 'strict')
    except UnicodeError as exc:
        raise RouterError('INVALID_CONTRACT', f'invalid {name}') from exc
    if len(encoded) > maximum or (trim and value != value.strip()):
        _fail('INVALID_CONTRACT', f'invalid {name}')
    return value


def _safe_path(value: Any, name: str, *, absolute: bool) -> str:
    value = _bounded_string(value, name, _MAX_PATH_BYTES)
    if absolute and not os.path.isabs(value):
        _fail('INVALID_CONTRACT', f'{name} must be absolute')
    if absolute and '..' in PurePosixPath(value).parts:
        _fail('INVALID_CONTRACT', f'{name} must not traverse parent paths')
    return value


def _safe_metadata(value: Any) -> dict[str, str]:
    if type(value) is not dict or len(value) > 64:
        _fail('INVALID_CONTRACT', 'metadata must be a flat object of anonymous labels')
    result: dict[str, str] = {}
    for key, item in value.items():
        if (not isinstance(key, str) or not _METADATA_KEY.fullmatch(key)
                or _METADATA_SENSITIVE.search(key)):
            _fail('INVALID_CONTRACT', 'metadata keys must be nonsensitive labels')
        if not isinstance(item, str) or not _METADATA_VALUE.fullmatch(item):
            _fail('INVALID_CONTRACT', 'metadata values must be short ASCII labels')
        lowered = item.lower()
        if lowered.startswith(_SECRET_PREFIX) or (len(item) >= 24 and len(set(item)) >= 12):
            _fail('INVALID_CONTRACT', 'metadata value looks like a credential or opaque token')
        result[key] = item
    return result


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _validate_descriptor(value: Any) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _IMAGE_FIELDS:
        _fail('INVALID_CONTRACT', 'image descriptor has missing or unknown fields')
    image_id = _bounded_string(value['image_id'], 'image_id', 128)
    if not _IDENTIFIER.fullmatch(image_id):
        _fail('INVALID_CONTRACT', 'invalid image_id')
    path = _safe_path(value['path'], 'image path', absolute=True)
    byte_length = value['byte_length']
    width = value['width']
    height = value['height']
    if not _is_int(byte_length) or not 1 <= byte_length <= MAX_PNG_BYTES:
        _fail('INVALID_CONTRACT', 'invalid image byte_length')
    if (not _is_int(width) or not _is_int(height)
            or not 1 <= width <= MAX_IMAGE_DIMENSION
            or not 1 <= height <= MAX_IMAGE_DIMENSION):
        _fail('INVALID_CONTRACT', 'invalid image dimensions')
    sha256 = value['sha256']
    if not isinstance(sha256, str) or not _HEX_SHA256.fullmatch(sha256):
        _fail('INVALID_CONTRACT', 'invalid image sha256')
    return {
        'image_id': image_id,
        'path': path,
        'byte_length': byte_length,
        'sha256': sha256,
        'width': width,
        'height': height,
    }


def _validate_refs(value: Any) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) > MAX_IMAGES:
        _fail('INVALID_CONTRACT', 'selected_refs must be a bounded list')
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for ref in value:
        if type(ref) is not dict or set(ref) != _REF_FIELDS:
            _fail('INVALID_CONTRACT', 'accepted ref has missing or unknown fields')
        path = _safe_path(ref['path'], 'selected ref path', absolute=True)
        digest = ref['sha256']
        if (ref['accepted'] is not True or not isinstance(digest, str)
                or not _HEX_SHA256.fullmatch(digest)):
            _fail('INVALID_CONTRACT', 'selected ref must be accepted and sha256-bound')
        key = (path, digest)
        if key in seen:
            _fail('INVALID_CONTRACT', 'duplicate selected ref')
        seen.add(key)
        refs.append({'path': path, 'sha256': digest, 'accepted': True})
    return refs


def _validate_budgets(
    value: Any, images: list[dict[str, Any]], prompt_bytes: int, *, subscription: bool = False,
    unrestricted: bool = False,
) -> dict[str, Any]:
    fields = _BUDGET_FIELDS | {'observed_output_tokens_limit'} if subscription else _BUDGET_FIELDS
    if type(value) is not dict or set(value) != fields:
        _fail('INVALID_CONTRACT', 'image budgets have missing or unknown fields')
    observed = None if unrestricted else 2048
    if subscription and (value['generation_tokens'] is not None
            or type(value['observed_output_tokens_limit']) is not type(observed)
            or value['observed_output_tokens_limit'] != observed):
        _fail('INVALID_CONTRACT', 'subscription hard generation cap must be null')
    if unrestricted and (value['generation_tokens'] is not None or value['request_limit'] != 1
            or type(value['request_limit']) is not int):
        _fail('INVALID_CONTRACT', 'unrestricted spending keeps single-submission protocol')

    integer_limits = {
        'max_images': (1, MAX_IMAGES),
        'max_png_bytes': (1, MAX_PNG_BYTES),
        'payload_bytes': (1, MAX_NATIVE_PAYLOAD_BYTES),
        'output_bytes': (1, MAX_IMAGE_OUTPUT_BYTES),
        'context_bytes': (1, MAX_CONTEXT_BYTES),
        'generation_tokens': (1, MAX_GENERATION_TOKENS),
        'request_limit': (1, MAX_REQUESTS),
    }
    budgets = dict(value)
    for name, (minimum, maximum) in integer_limits.items():
        if (subscription or unrestricted) and name == 'generation_tokens':
            continue
        item = budgets[name]
        if not _is_int(item) or not minimum <= item <= maximum:
            _fail('INVALID_CONTRACT', f'invalid image budget {name}')

    for name in ('wall_seconds', 'idle_seconds'):
        item = budgets[name]
        if (type(item) not in (int, float) or not math.isfinite(item)
                or not 0 < item <= MAX_WALL_SECONDS):
            _fail('INVALID_CONTRACT', f'invalid image budget {name}')
    if budgets['idle_seconds'] > budgets['wall_seconds']:
        _fail('INVALID_CONTRACT', 'idle_seconds exceeds wall_seconds')

    if len(images) > budgets['max_images']:
        _fail('INVALID_CONTRACT', 'image count exceeds max_images')
    total_png = sum(image['byte_length'] for image in images)
    if total_png > budgets['max_png_bytes']:
        _fail('INVALID_CONTRACT', 'declared PNG bytes exceed max_png_bytes')
    base64_bytes = sum(4 * ((image['byte_length'] + 2) // 3) for image in images)
    if base64_bytes > budgets['payload_bytes']:
        _fail('INVALID_CONTRACT', 'encoded PNG bytes exceed payload_bytes')
    if prompt_bytes > budgets['context_bytes']:
        _fail('INVALID_CONTRACT', 'prompt text exceeds context_bytes')
    return budgets


@dataclass(frozen=True)
class ImageTaskContract:
    schema: str
    parent_session_id: str
    task_id: str
    backend: str
    model: str
    profile: str
    effort: str
    selected_refs: tuple[Mapping[str, Any], ...]
    system_text: str
    task_text: str
    images: tuple[Mapping[str, Any], ...]
    metadata: Mapping[str, str]
    output_protocol: str
    context_policy: str
    budgets: Mapping[str, Any]

    @classmethod
    def from_dict(cls, data: dict) -> 'ImageTaskContract':
        if type(data) is not dict or set(data) != _TOP_FIELDS:
            _fail('INVALID_CONTRACT', 'image task has missing or unknown fields')
        if data['schema'] != IMAGE_TASK_SCHEMA:
            _fail('INVALID_CONTRACT', 'unsupported image task schema')

        parent_session_id = _bounded_string(data['parent_session_id'], 'parent_session_id', 128)
        task_id = _bounded_string(data['task_id'], 'task_id', 128)
        if not _IDENTIFIER.fullmatch(parent_session_id) or not _IDENTIFIER.fullmatch(task_id):
            _fail('INVALID_CONTRACT', 'invalid task identity')
        backend = data['backend']
        if backend not in IMAGE_PROVIDERS:
            _fail('INVALID_CONTRACT', 'image backend must be explicit kimi, codex or minimax')
        model = _bounded_string(data['model'], 'model', 256)
        profile = _bounded_string(data['profile'], 'profile', 128)
        effort = _bounded_string(data['effort'], 'effort', 64)
        if backend == 'minimax' and (model, profile, effort) != ('MiniMax-M3', 'responses-bounded', 'provider-default'):
            _fail('IMAGE_ROUTE_MISMATCH')
        if data['output_protocol'] != IMAGE_OUTPUT_PROTOCOL:
            _fail('INVALID_CONTRACT', 'unsupported output protocol')
        if data['context_policy'] != IMAGE_CONTEXT_POLICY:
            _fail('INVALID_CONTRACT', 'unsupported image context policy')

        system_text = _bounded_string(
            data['system_text'], 'system_text', MAX_IMAGE_PROMPT_BYTES, trim=False)
        task_text = _bounded_string(
            data['task_text'], 'task_text', MAX_IMAGE_PROMPT_BYTES, trim=False)
        for name, text in (('system_text', system_text), ('task_text', task_text)):
            if any(ord(char) < 32 and char not in '\n\r\t' for char in text):
                _fail('INVALID_CONTRACT', f'invalid control character in {name}')
        prompt_bytes = len(system_text.encode('utf-8')) + len(task_text.encode('utf-8'))
        if prompt_bytes > MAX_IMAGE_PROMPT_BYTES:
            _fail('INVALID_CONTRACT', 'combined prompt text exceeds 256 KiB')

        raw_images = data['images']
        if type(raw_images) is not list or not 1 <= len(raw_images) <= MAX_IMAGES:
            _fail('INVALID_CONTRACT', 'images must contain 1..1024 descriptors')
        images = [_validate_descriptor(image) for image in raw_images]
        ids = [image['image_id'] for image in images]
        if len(ids) != len(set(ids)):
            _fail('INVALID_CONTRACT', 'duplicate image_id')

        refs = _validate_refs(data['selected_refs'])
        metadata = _safe_metadata(data['metadata'])
        if model == 'gpt-6-astra' and not selected_subscription_model(data | {'metadata': metadata, 'selected_refs': refs}):
            _fail('IMAGE_ROUTE_MISMATCH')
        budgets = _validate_budgets(data['budgets'], images, prompt_bytes,
            subscription=backend == 'codex' and profile == 'subscription-bounded',
            unrestricted=unrestricted_spending(data | {'metadata': metadata, 'selected_refs': refs}))
        return cls(
            schema=IMAGE_TASK_SCHEMA,
            parent_session_id=parent_session_id,
            task_id=task_id,
            backend=backend,
            model=model,
            profile=profile,
            effort=effort,
            selected_refs=tuple(_freeze(ref) for ref in refs),
            system_text=system_text,
            task_text=task_text,
            images=tuple(_freeze(image) for image in images),
            metadata=_freeze(metadata),
            output_protocol=IMAGE_OUTPUT_PROTOCOL,
            context_policy=IMAGE_CONTEXT_POLICY,
            budgets=_freeze(budgets),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'schema': self.schema,
            'parent_session_id': self.parent_session_id,
            'task_id': self.task_id,
            'backend': self.backend,
            'model': self.model,
            'profile': self.profile,
            'effort': self.effort,
            'selected_refs': _thaw(self.selected_refs),
            'system_text': self.system_text,
            'task_text': self.task_text,
            'images': _thaw(self.images),
            'metadata': _thaw(self.metadata),
            'output_protocol': self.output_protocol,
            'context_policy': self.context_policy,
            'budgets': _thaw(self.budgets),
        }


def _read_open_file(fd: int, expected_length: int) -> bytes:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_size != expected_length:
        _fail('INVALID_IMAGE', 'image is not a regular file of the declared length')
    data = bytearray()
    while len(data) <= expected_length:
        block = os.read(fd, min(64 * 1024, expected_length + 1 - len(data)))
        if not block:
            break
        data.extend(block)
        if len(data) > expected_length:
            _fail('INVALID_IMAGE', 'image grew while being read')
    after = os.fstat(fd)
    if (len(data) != expected_length or before.st_dev != after.st_dev
            or before.st_ino != after.st_ino or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns or before.st_ctime_ns != after.st_ctime_ns):
        _fail('INVALID_IMAGE', 'image changed while being read')
    return bytes(data)


def _open_absolute_file_nofollow(path: str) -> int:
    if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        _fail(
            'UNSUPPORTED_REQUIRED_CAPABILITY',
            'descriptor-based no-follow file access is unavailable',
        )
    if not os.path.isabs(path) or '\x00' in path:
        _fail('INVALID_IMAGE', 'image path must be absolute')
    components = path.split('/')
    if '..' in components:
        _fail('INVALID_IMAGE', 'image path must not traverse parent paths')
    parts = [part for part in components if part not in ('', '.')]
    if not parts:
        _fail('INVALID_IMAGE', 'image path is not a file')

    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in parts[:-1]:
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                 dir_fd=directory)
            os.close(directory)
            directory = following
        return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                       dir_fd=directory)
    except OSError as exc:
        raise RouterError(
            'INVALID_IMAGE', 'image path could not be opened without following links',
        ) from exc
    finally:
        os.close(directory)


def _validate_png_bytes(data: bytes, descriptor: Mapping[str, Any]) -> None:
    if len(data) != descriptor['byte_length']:
        _fail('INVALID_IMAGE', 'PNG length does not match descriptor')
    if hashlib.sha256(data).hexdigest() != descriptor['sha256']:
        _fail('INVALID_IMAGE', 'PNG digest does not match descriptor')
    if len(data) > MAX_PNG_BYTES or not data.startswith(_PNG_SIGNATURE):
        _fail('INVALID_IMAGE', 'invalid PNG signature or size')

    offset = len(_PNG_SIGNATURE)
    chunk_count = 0
    ihdr = None
    palette_entries = 0
    seen_plte = False
    seen_trns = False
    seen_bkgd = False
    seen_hist = False
    seen_idat = False
    idat_closed = False
    seen_iend = False
    unique_chunks: set[bytes] = set()
    decompressor = None
    inflated_bytes = 0
    filter_positions: list[int] = []
    expected_inflated = 0

    def consume_inflated(output: bytes) -> None:
        nonlocal inflated_bytes
        if not output:
            return
        start = inflated_bytes
        end = start + len(output)
        if end > expected_inflated:
            _fail('INVALID_IMAGE', 'PNG pixel stream expands beyond declared dimensions')
        index = bisect_left(filter_positions, start)
        while index < len(filter_positions) and filter_positions[index] < end:
            filter_offset = filter_positions[index]
            if output[filter_offset - start] > 4:
                _fail('INVALID_IMAGE', 'PNG scanline has an invalid filter')
            index += 1
        inflated_bytes = end

    while offset < len(data):
        chunk_count += 1
        if chunk_count > _MAX_CHUNKS or len(data) - offset < 12:
            _fail('INVALID_IMAGE', 'truncated or excessive PNG chunks')
        length = struct.unpack_from('>I', data, offset)[0]
        kind_start = offset + 4
        kind = data[kind_start:kind_start + 4]
        payload_start = kind_start + 4
        payload_end = payload_start + length
        chunk_end = payload_end + 4
        if payload_end < payload_start or chunk_end > len(data):
            _fail('INVALID_IMAGE', 'PNG chunk length exceeds file')
        if (len(kind) != 4 or any(not (65 <= byte <= 90 or 97 <= byte <= 122) for byte in kind)
                or kind[2] & 0x20):
            _fail('INVALID_IMAGE', 'invalid PNG chunk type')
        actual_crc = zlib.crc32(memoryview(data)[kind_start:payload_end]) & 0xffffffff
        expected_crc = struct.unpack_from('>I', data, payload_end)[0]
        if actual_crc != expected_crc:
            _fail('INVALID_IMAGE', 'PNG chunk CRC mismatch')
        payload = memoryview(data)[payload_start:payload_end]
        if kind in (b'acTL', b'fcTL', b'fdAT'):
            _fail('INVALID_IMAGE', 'animated PNG is not accepted')

        if ihdr is None:
            if kind != b'IHDR' or length != 13:
                _fail('INVALID_IMAGE', 'IHDR must be the first PNG chunk')
            (width, height, bit_depth, color_type, compression, filtering, interlace
             ) = struct.unpack('>IIBBBBB', payload)
            allowed_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if (not 1 <= width <= MAX_IMAGE_DIMENSION or not 1 <= height <= MAX_IMAGE_DIMENSION
                    or color_type not in allowed_depths
                    or bit_depth not in allowed_depths[color_type]
                    or compression != 0 or filtering != 0 or interlace not in (0, 1)):
                _fail('INVALID_IMAGE', 'invalid PNG IHDR values')
            if width != descriptor['width'] or height != descriptor['height']:
                _fail('INVALID_IMAGE', 'PNG dimensions do not match descriptor')
            channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
            bits_per_pixel = channels * bit_depth
            passes = ((0, 0, 1, 1),) if interlace == 0 else (
                (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
                (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
            )
            for x_start, y_start, x_step, y_step in passes:
                pass_width = max(0, (width - x_start + x_step - 1) // x_step)
                pass_height = max(0, (height - y_start + y_step - 1) // y_step)
                if pass_width == 0 or pass_height == 0:
                    continue
                row_stride = (pass_width * bits_per_pixel + 7) // 8 + 1
                for _ in range(pass_height):
                    filter_positions.append(expected_inflated)
                    expected_inflated += row_stride
            ihdr = (width, height, bit_depth, color_type, interlace)
            offset = chunk_end
            continue
        if kind == b'IHDR':
            _fail('INVALID_IMAGE', 'PNG contains multiple IHDR chunks')
        if seen_iend:
            _fail('INVALID_IMAGE', 'PNG contains bytes after IEND')
        if seen_idat and kind != b'IDAT':
            idat_closed = True
        if kind == b'IDAT':
            if idat_closed:
                _fail('INVALID_IMAGE', 'PNG IDAT chunks must be consecutive')
            if not seen_idat:
                color_type = ihdr[3]
                if color_type == 3 and not seen_plte:
                    _fail('INVALID_IMAGE', 'indexed PNG is missing PLTE')
                decompressor = zlib.decompressobj()
                seen_idat = True
            if length:
                pending = payload
                while pending:
                    allowance = min(64 * 1024, expected_inflated - inflated_bytes + 1)
                    try:
                        output = decompressor.decompress(pending, allowance)
                    except zlib.error as exc:
                        raise RouterError(
                            'INVALID_IMAGE', 'PNG pixel stream is not valid zlib data',
                        ) from exc
                    consume_inflated(output)
                    if decompressor.unused_data:
                        _fail('INVALID_IMAGE', 'PNG IDAT has trailing compressed data')
                    following = decompressor.unconsumed_tail
                    if following and following == pending and not output:
                        _fail('INVALID_IMAGE', 'PNG decompression made no progress')
                    pending = following
            offset = chunk_end
            continue

        if kind == b'PLTE':
            color_type = ihdr[3]
            bit_depth = ihdr[2]
            if (seen_plte or seen_trns or seen_bkgd or seen_hist or seen_idat
                    or color_type in (0, 4) or not 3 <= length <= 768 or length % 3):
                _fail('INVALID_IMAGE', 'invalid or misplaced PLTE')
            palette_entries = length // 3
            if color_type == 3 and palette_entries > (1 << bit_depth):
                _fail('INVALID_IMAGE', 'PLTE has too many entries for indexed PNG')
            seen_plte = True
        elif kind == b'tRNS':
            color_type = ihdr[3]
            if seen_trns or seen_idat:
                _fail('INVALID_IMAGE', 'invalid or misplaced tRNS')
            if color_type == 0 and length != 2:
                _fail('INVALID_IMAGE', 'invalid grayscale tRNS')
            if color_type == 2 and length != 6:
                _fail('INVALID_IMAGE', 'invalid truecolor tRNS')
            if color_type == 3 and (not seen_plte or not 1 <= length <= palette_entries):
                _fail('INVALID_IMAGE', 'invalid indexed tRNS')
            if color_type in (4, 6):
                _fail('INVALID_IMAGE', 'tRNS is forbidden with alpha channels')
            seen_trns = True
        elif kind == b'bKGD':
            color_type = ihdr[3]
            required = 1 if color_type == 3 else (2 if color_type in (0, 4) else 6)
            if seen_bkgd or seen_idat or length != required:
                _fail('INVALID_IMAGE', 'invalid or misplaced bKGD')
            if color_type == 3 and (not seen_plte or payload[0] >= palette_entries):
                _fail('INVALID_IMAGE', 'indexed bKGD references an invalid palette entry')
            seen_bkgd = True
        elif kind == b'hIST':
            if (seen_hist or seen_idat or ihdr[3] != 3 or not seen_plte
                    or length != 2 * palette_entries):
                _fail('INVALID_IMAGE', 'invalid or misplaced hIST')
            seen_hist = True
        elif kind in (b'cHRM', b'gAMA', b'iCCP', b'sBIT', b'sRGB', b'pHYs', b'eXIf', b'sPLT',
                      b'tEXt', b'zTXt', b'iTXt', b'tIME'):
            if (kind in (b'cHRM', b'gAMA', b'iCCP', b'sBIT', b'sRGB', b'eXIf', b'pHYs', b'sPLT')
                    and seen_idat):
                _fail('INVALID_IMAGE', 'PNG ancillary chunk is misplaced after IDAT')
            if kind in (b'cHRM', b'gAMA', b'iCCP', b'sBIT', b'sRGB', b'eXIf') and seen_plte:
                _fail('INVALID_IMAGE', 'PNG color metadata must precede PLTE')
            if kind in (b'cHRM', b'gAMA', b'iCCP', b'sBIT', b'sRGB', b'pHYs', b'eXIf', b'tIME'):
                if kind in unique_chunks:
                    _fail('INVALID_IMAGE', 'duplicate unique PNG ancillary chunk')
                unique_chunks.add(kind)
            if kind == b'cHRM' and length != 32:
                _fail('INVALID_IMAGE', 'invalid cHRM length')
            if kind == b'gAMA' and (length != 4 or struct.unpack('>I', payload)[0] == 0):
                _fail('INVALID_IMAGE', 'invalid gAMA data')
            if kind == b'sRGB' and (length != 1 or payload[0] > 3):
                _fail('INVALID_IMAGE', 'invalid sRGB data')
            if kind == b'pHYs' and (length != 9 or payload[8] > 1):
                _fail('INVALID_IMAGE', 'invalid pHYs data')
            if kind == b'tIME' and length != 7:
                _fail('INVALID_IMAGE', 'invalid tIME length')
            if kind == b'sBIT':
                required = {0: 1, 2: 3, 3: 3, 4: 2, 6: 4}[ihdr[3]]
                maximum = 8 if ihdr[3] == 3 else ihdr[2]
                if length != required or any(not 1 <= bit <= maximum for bit in payload):
                    _fail('INVALID_IMAGE', 'invalid sBIT data')
            if kind in (b'tEXt', b'zTXt', b'iTXt') and not length:
                _fail('INVALID_IMAGE', 'empty PNG text chunk')
        elif kind == b'IEND':
            if length != 0 or not seen_idat:
                _fail('INVALID_IMAGE', 'invalid or misplaced IEND')
            seen_iend = True
            if chunk_end != len(data):
                _fail('INVALID_IMAGE', 'PNG contains trailing bytes after IEND')
        elif kind == b'IDAT':
            _fail('INVALID_IMAGE', 'invalid IDAT sequence')
        else:
            if kind[0] & 0x20 == 0:
                _fail('INVALID_IMAGE', 'unknown critical PNG chunk')
            # Unknown ancillary chunks are safe to skip but must still obey the
            # PNG rule that image data remains a single consecutive run.

        offset = chunk_end

    if not seen_iend or not seen_idat or decompressor is None:
        _fail('INVALID_IMAGE', 'PNG is missing image data or IEND')
    try:
        while inflated_bytes <= expected_inflated:
            output = decompressor.decompress(
                b'', min(64 * 1024, expected_inflated - inflated_bytes + 1),
            )
            if not output:
                break
            consume_inflated(output)
    except zlib.error as exc:
        raise RouterError('INVALID_IMAGE', 'PNG pixel stream is incomplete') from exc
    if (not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail
            or inflated_bytes != expected_inflated):
        _fail('INVALID_IMAGE', 'PNG pixel stream is incomplete or has extra data')


def read_png(descriptor: dict) -> bytes:
    """Read and validate a bound local PNG using no-follow file descriptors."""
    image = _validate_descriptor(descriptor)
    if image['byte_length'] > MAX_PNG_BYTES:
        _fail('INVALID_IMAGE', 'PNG exceeds byte limit')
    fd = _open_absolute_file_nofollow(image['path'])
    try:
        data = _read_open_file(fd, image['byte_length'])
    except OSError as exc:
        raise RouterError('INVALID_IMAGE', 'image could not be read safely') from exc
    finally:
        os.close(fd)
    _validate_png_bytes(data, image)
    return data
