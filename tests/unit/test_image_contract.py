import hashlib
import struct
import zlib

import pytest

from agent_subagent_router.contracts import RouterError, TaskContract
from agent_subagent_router.image_contract import ImageTaskContract, read_png

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack('>I', len(payload)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)


def make_png(*, width=1, height=1, pixel_rows=None, extra_before_idat=(), idat_data=None):
    raw = pixel_rows if pixel_rows is not None else b'\x00\x10\x20\x30\xff' * height
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    compressed = zlib.compress(raw) if idat_data is None else idat_data
    return (PNG_SIGNATURE + png_chunk(b'IHDR', ihdr) + b''.join(extra_before_idat)
            + png_chunk(b'IDAT', compressed) + png_chunk(b'IEND', b''))


def descriptor(path='/tmp/image.png', data=None, *, image_id='image-1', width=1, height=1):
    data = make_png() if data is None else data
    return {
        'image_id': image_id,
        'path': path,
        'byte_length': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'width': width,
        'height': height,
    }


def task_dict(images=None):
    return {
        'schema': 'image-task/v1',
        'parent_session_id': 'parent-1',
        'task_id': 'image-task-1',
        'backend': 'kimi',
        'model': 'kimi-image-model',
        'profile': 'worker',
        'effort': 'high',
        'selected_refs': [],
        'system_text': 'Inspect only the supplied images.',
        'task_text': 'Return a strict JSON object.',
        'images': [descriptor()] if images is None else images,
        'metadata': {'phase': 'source-review', 'packet': 'first'},
        'output_protocol': 'JSON_OBJECT/v1',
        'context_policy': 'FRESH_SEALED_INPUT/v1',
        'budgets': {
            'max_images': 4,
            'max_png_bytes': 1_000_000,
            'payload_bytes': 1_400_000,
            'output_bytes': 1_000_000,
            'context_bytes': 2_000_000,
            'generation_tokens': 2048,
            'wall_seconds': 180,
            'idle_seconds': 90,
            'request_limit': 1,
        },
    }


def test_image_task_round_trip_is_strict_and_detached_from_caller_mutations():
    source = task_dict()
    task = ImageTaskContract.from_dict(source)
    expected = task.to_dict()
    source['images'][0]['image_id'] = 'mutated'
    source['metadata']['phase'] = 'mutated'
    assert task.to_dict() == expected
    returned = task.to_dict()
    returned['images'][0]['image_id'] = 'mutated-again'
    assert task.to_dict() == expected


def test_unknown_fields_and_wrong_nested_shapes_are_rejected():
    changes = [
        lambda data: data.update({'read_paths': []}),
        lambda data: data['budgets'].update({'legacy_budget': 10}),
        lambda data: data['images'][0].update({'detail': 'original'}),
        lambda data: data.update({'metadata': {'nested': {'value': 'unsafe'}}}),
        lambda data: data.update({'selected_refs': [{'path': 'plan.md', 'sha256': '0' * 64}]}),
    ]
    for change in changes:
        value = task_dict()
        change(value)
        with pytest.raises(RouterError):
            ImageTaskContract.from_dict(value)


@pytest.mark.parametrize(('field', 'value'), [
    ('backend', 'gemini'),
    ('output_protocol', 'JSON_OBJECT/v2'),
    ('context_policy', 'restored-session'),
    ('schema', 'task/v1'),
])
def test_only_explicit_image_route_protocol_values_are_accepted(field, value):
    value_dict = task_dict()
    value_dict[field] = value
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(value_dict)


def test_selected_ref_paths_must_be_explicit_absolute_paths():
    value = task_dict()
    value['selected_refs'] = [{'path': 'docs/accepted.md', 'sha256': 'a' * 64, 'accepted': True}]
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(value)


def test_accepted_refs_require_explicit_approval_and_exact_digest():
    value = task_dict()
    value['selected_refs'] = [{
        'path': '/workspace/docs/accepted.md',
        'sha256': 'a' * 64,
        'accepted': True,
    }]
    assert (ImageTaskContract.from_dict(value).to_dict()['selected_refs']
            == value['selected_refs'])
    value['selected_refs'][0]['accepted'] = False
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(value)


@pytest.mark.parametrize('metadata', [
    {'source_path': 'tmp/input.png'},
    {'api_token': 'sk-live-abc123'},
    {'phase': '/home/user/file.png'},
    {'opaque': 'aBcDef0123456789fEdCbA9876543210'},
    {'nested': {'label': 'safe'}},
])
def test_metadata_accepts_only_short_anonymous_labels(metadata):
    value = task_dict()
    value['metadata'] = metadata
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(value)


def test_metadata_accepts_flat_bounded_labels():
    value = task_dict()
    value['metadata'] = {'phase': 'source-review', 'packet': 'first', 'rapid': 'safe'}
    assert ImageTaskContract.from_dict(value).to_dict()['metadata'] == value['metadata']


@pytest.mark.parametrize(('budget', 'value'), [
    ('max_images', 1025),
    ('max_png_bytes', 24 * 1024 * 1024 + 1),
    ('payload_bytes', 32 * 1024 * 1024 + 1),
    ('output_bytes', 8 * 1024 * 1024 + 1),
    ('generation_tokens', 0),
    ('request_limit', True),
    ('wall_seconds', float('inf')),
    ('idle_seconds', 181),
])
def test_image_budgets_are_finite_typed_and_capped(budget, value):
    data = task_dict()
    data['budgets'][budget] = value
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(data)


def test_declared_image_and_encoded_payload_must_fit_task_budgets():
    data = task_dict()
    data['budgets']['max_images'] = 0
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(data)

    data = task_dict()
    data['budgets']['max_png_bytes'] = data['images'][0]['byte_length'] - 1
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(data)

    data = task_dict()
    data['budgets']['payload_bytes'] = 1
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(data)


def test_prompt_cap_counts_utf8_bytes():
    data = task_dict()
    data['system_text'] = '界' * (256 * 1024 // 3 + 1)
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(data)


def test_duplicate_image_ids_and_invalid_dimensions_are_rejected():
    one = descriptor(image_id='same')
    two = descriptor(image_id='same')
    data = task_dict([one, two])
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(data)

    one = descriptor(width=4097)
    with pytest.raises(RouterError):
        ImageTaskContract.from_dict(task_dict([one]))


def test_read_png_binds_exact_bytes_dimensions_and_rejects_bad_crc_or_apng(tmp_path):
    data = make_png()
    path = tmp_path / 'image.png'
    path.write_bytes(data)
    assert read_png(descriptor(str(path), data)) == data

    bad_crc = data[:-1] + bytes([data[-1] ^ 1])
    path.write_bytes(bad_crc)
    with pytest.raises(RouterError):
        read_png(descriptor(str(path), bad_crc))

    apng = make_png(extra_before_idat=(png_chunk(b'acTL', struct.pack('>II', 1, 0)),))
    path.write_bytes(apng)
    with pytest.raises(RouterError):
        read_png(descriptor(str(path), apng))

    path.write_bytes(data)
    with pytest.raises(RouterError):
        read_png(descriptor(str(path), data, width=2))


def test_read_png_rejects_incomplete_inflate_bad_filter_and_symlink(tmp_path):
    raw = b'\x00\x10\x20\x30'  # One byte short for a 1x1 RGBA scanline.
    truncated = make_png(idat_data=zlib.compress(raw))
    path = tmp_path / 'image.png'
    path.write_bytes(truncated)
    with pytest.raises(RouterError):
        read_png(descriptor(str(path), truncated))

    invalid_filter = make_png(pixel_rows=b'\x05\x10\x20\x30\xff')
    path.write_bytes(invalid_filter)
    with pytest.raises(RouterError):
        read_png(descriptor(str(path), invalid_filter))

    target = tmp_path / 'target.png'
    target.write_bytes(make_png())
    link = tmp_path / 'link.png'
    link.symlink_to(target)
    with pytest.raises(RouterError):
        read_png(descriptor(str(link), target.read_bytes()))

    directory = tmp_path / 'real-dir'
    directory.mkdir()
    nested = directory / 'nested.png'
    nested.write_bytes(make_png())
    directory_link = tmp_path / 'linked-dir'
    directory_link.symlink_to(directory, target_is_directory=True)
    with pytest.raises(RouterError):
        read_png(descriptor(str(directory_link / 'nested.png'), nested.read_bytes()))


def test_legacy_task_contract_still_rejects_image_task_fields():
    with pytest.raises(RouterError):
        TaskContract.from_dict(task_dict())


def test_read_png_checks_chunk_order_and_contiguous_idat_chunks(tmp_path):
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)
    compressed = zlib.compress(b'\x00\x10\x20\x30\xff')
    wrong_first_chunk = (PNG_SIGNATURE + png_chunk(b'IDAT', compressed)
                         + png_chunk(b'IHDR', ihdr) + png_chunk(b'IEND', b''))
    split_idat = (PNG_SIGNATURE + png_chunk(b'IHDR', ihdr)
                  + png_chunk(b'IDAT', compressed[:2])
                  + png_chunk(b'tEXt', b'Comment\x00split')
                  + png_chunk(b'IDAT', compressed[2:]) + png_chunk(b'IEND', b''))
    path = tmp_path / 'invalid-order.png'
    for data in (wrong_first_chunk, split_idat):
        path.write_bytes(data)
        with pytest.raises(RouterError):
            read_png(descriptor(str(path), data))


def test_read_png_inflates_complete_adam7_passes(tmp_path):
    ihdr = struct.pack('>IIBBBBB', 2, 2, 8, 6, 0, 0, 1)
    first_pixel = b'\x00\x10\x20\x30\xff'
    second_pixel = b'\x00\x40\x50\x60\xff'
    final_row = b'\x00\x70\x80\x90\xff\xa0\xb0\xc0\xff'
    raw = first_pixel + second_pixel + final_row
    data = (PNG_SIGNATURE + png_chunk(b'IHDR', ihdr)
            + png_chunk(b'IDAT', zlib.compress(raw)) + png_chunk(b'IEND', b''))
    path = tmp_path / 'interlaced.png'
    path.write_bytes(data)
    assert read_png(descriptor(str(path), data, width=2, height=2)) == data

    truncated = (PNG_SIGNATURE + png_chunk(b'IHDR', ihdr)
                 + png_chunk(b'IDAT', zlib.compress(raw[:-1])) + png_chunk(b'IEND', b''))
    path.write_bytes(truncated)
    with pytest.raises(RouterError):
        read_png(descriptor(str(path), truncated, width=2, height=2))
