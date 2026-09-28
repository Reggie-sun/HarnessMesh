import hashlib
import os
from pathlib import Path
import struct
import zlib

import pytest

from agent_subagent_router.contracts import RouterError
from agent_subagent_router.image_contract import ImageTaskContract
from agent_subagent_router.image_seal import seal_images, verify_image_seal

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack('>I', len(payload)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)


def make_png():
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b'\x00\x10\x20\x30\xff')
    return PNG_SIGNATURE + chunk(b'IHDR', ihdr) + chunk(b'IDAT', pixels) + chunk(b'IEND', b'')


def descriptor(path, data, image_id):
    return {
        'image_id': image_id,
        'path': str(path),
        'byte_length': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'width': 1,
        'height': 1,
    }


def task_for(paths, data):
    images = [descriptor(path, data, f'image-{index}') for index, path in enumerate(paths, 1)]
    reference = Path(paths[0]).parent / 'accepted-plan.md'
    reference.write_text('accepted plan bytes', encoding='utf-8')
    refs = [{
        'path': str(reference),
        'sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
        'accepted': True,
    }]
    return ImageTaskContract.from_dict({
        'schema': 'image-task/v1',
        'parent_session_id': 'parent-1',
        'task_id': 'image-task-seal',
        'backend': 'codex',
        'model': 'codex-image-model',
        'profile': 'reviewer',
        'effort': 'high',
        'selected_refs': refs,
        'system_text': 'Inspect only these images.',
        'task_text': 'Return one JSON object.',
        'images': images,
        'metadata': {'phase': 'source-review'},
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
    })


PINS = {
    'adapter': {'sha256': 'a' * 64, 'version': 'image-adapter/v1'},
    'image': {'sha256': 'b' * 64, 'version': 'image-runtime/v1'},
    'protocol': {'sha256': 'c' * 64, 'version': 'JSON_OBJECT/v1'},
    'runtime': {'sha256': 'd' * 64, 'version': 'runtime/v1'},
}


def seal(tmp_path, *, pins=None, task=None):
    data = make_png()
    first = tmp_path / 'first.png'
    second = tmp_path / 'second.png'
    first.write_bytes(data)
    second.write_bytes(data)
    task = task or task_for([first, second], data)
    return seal_images(task, tmp_path / 'contracts', PINS if pins is None else pins)


def test_seal_preserves_order_and_duplicate_pixels_with_distinct_identity(tmp_path):
    sealed = seal(tmp_path)
    verified = verify_image_seal(sealed['manifest_path'])
    assert verified['task'] == sealed['task']
    assert verified['pins'] == PINS
    assert [image['image_id'] for image in verified['images']] == ['image-1', 'image-2']
    assert [image['sha256'] for image in verified['images']] == [
        image['sha256'] for image in verified['task']['images']
    ]
    assert len({image['blob_path'] for image in verified['images']}) == 2
    assert all(open(image['blob_path'], 'rb').read() == make_png() for image in verified['images'])
    assert os.stat(verified['manifest_path']).st_mode & 0o777 == 0o400
    assert os.stat(os.path.dirname(verified['manifest_path'])).st_mode & 0o777 == 0o500


def test_seal_is_independent_of_later_source_changes(tmp_path):
    sealed = seal(tmp_path)
    source = sealed['task']['images'][0]['path']
    with open(source, 'wb') as output:
        output.write(b'changed after sealing')
    verified = verify_image_seal(sealed['manifest_path'])
    assert open(verified['images'][0]['blob_path'], 'rb').read() == make_png()


def test_seal_rejects_changed_source_bytes_and_symlinks(tmp_path):
    data = make_png()
    source = tmp_path / 'image.png'
    source.write_bytes(data + b'extra')
    task = task_for([source], data)
    with pytest.raises(RouterError):
        seal_images(task, tmp_path / 'contracts', PINS)

    target = tmp_path / 'target.png'
    target.write_bytes(data)
    link = tmp_path / 'link.png'
    link.symlink_to(target)
    task = task_for([link], data)
    with pytest.raises(RouterError):
        seal_images(task, tmp_path / 'contracts-2', PINS)


@pytest.mark.parametrize('bad_pins', [{}, [], PINS | {'extra': object()}])
def test_seal_rejects_empty_or_non_json_pins(tmp_path, bad_pins):
    data = make_png()
    source = tmp_path / 'image.png'
    source.write_bytes(data)
    with pytest.raises(RouterError):
        seal_images(task_for([source], data), tmp_path / 'contracts', bad_pins)


def test_verify_rejects_manifest_byte_tampering(tmp_path):
    sealed = seal(tmp_path)
    path = sealed['manifest_path']
    os.chmod(path, 0o600)
    raw = bytearray(Path(path).read_bytes())
    raw[-1] ^= 1
    with open(path, 'wb') as output:
        output.write(raw)
    os.chmod(path, 0o400)
    with pytest.raises(RouterError):
        verify_image_seal(path)


def test_verify_rejects_blob_tampering_and_extra_blob_files(tmp_path):
    sealed = seal(tmp_path)
    blob = sealed['images'][0]['blob_path']
    os.chmod(blob, 0o600)
    changed = bytearray(make_png())
    changed[-1] ^= 1
    with open(blob, 'wb') as output:
        output.write(changed)
    os.chmod(blob, 0o400)
    with pytest.raises(RouterError):
        verify_image_seal(sealed['manifest_path'])



def test_verify_rejects_extra_blob_entries(tmp_path):
    sealed = seal(tmp_path)
    blobs = os.path.join(os.path.dirname(sealed['manifest_path']), 'blobs')
    os.chmod(blobs, 0o700)
    with open(os.path.join(blobs, 'extra.png'), 'wb') as output:
        output.write(make_png())
    os.chmod(blobs, 0o500)
    with pytest.raises(RouterError):
        verify_image_seal(sealed['manifest_path'])


def test_seal_binds_selected_ref_bytes_and_rechecks_them_on_verify(tmp_path):
    data = make_png()
    source = tmp_path / 'image.png'
    source.write_bytes(data)
    reference = tmp_path / 'accepted-plan.md'
    reference.write_text('accepted plan bytes', encoding='utf-8')
    task_data = task_for([source], data).to_dict()
    task_data['selected_refs'] = [{
        'path': str(reference),
        'sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
        'accepted': True,
    }]
    sealed = seal_images(ImageTaskContract.from_dict(task_data), tmp_path / 'contracts', PINS)
    assert sealed['task']['selected_refs'] == task_data['selected_refs']

    reference.write_text('changed after sealing', encoding='utf-8')
    with pytest.raises(RouterError):
        verify_image_seal(sealed['manifest_path'])


def test_seal_rejects_selected_ref_digest_mismatch_and_symlink(tmp_path):
    data = make_png()
    source = tmp_path / 'image.png'
    source.write_bytes(data)
    reference = tmp_path / 'accepted-plan.md'
    reference.write_text('accepted plan bytes', encoding='utf-8')
    task_data = task_for([source], data).to_dict()
    task_data['selected_refs'] = [{
        'path': str(reference),
        'sha256': '0' * 64,
        'accepted': True,
    }]
    with pytest.raises(RouterError):
        seal_images(ImageTaskContract.from_dict(task_data), tmp_path / 'contracts', PINS)

    link = tmp_path / 'accepted-link.md'
    link.symlink_to(reference)
    task_data['selected_refs'] = [{
        'path': str(link),
        'sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
        'accepted': True,
    }]
    with pytest.raises(RouterError):
        seal_images(ImageTaskContract.from_dict(task_data), tmp_path / 'contracts-2', PINS)


def test_seal_does_not_treat_empty_refs_as_acceptance(tmp_path):
    data = make_png()
    source = tmp_path / 'image.png'
    source.write_bytes(data)
    task_data = task_for([source], data).to_dict()
    task_data['selected_refs'] = []
    task = ImageTaskContract.from_dict(task_data)
    with pytest.raises(RouterError):
        seal_images(task, tmp_path / 'contracts', PINS)


def test_verify_rejects_extra_seal_entries(tmp_path):
    sealed = seal(tmp_path)
    directory = os.path.dirname(sealed['manifest_path'])
    os.chmod(directory, 0o700)
    with open(os.path.join(directory, 'unexpected.txt'), 'w', encoding='utf-8') as output:
        output.write('extra')
    os.chmod(directory, 0o500)
    with pytest.raises(RouterError):
        verify_image_seal(sealed['manifest_path'])
