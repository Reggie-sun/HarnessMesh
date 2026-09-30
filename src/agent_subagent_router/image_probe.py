"""Router-owned random visual probes, isolated from project data and truth."""
from pathlib import Path
import secrets
import struct
import uuid
import zlib

from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .image_inspect import inspect_images
from .image_seal import verify_image_seal

PROBE_VERSION = 'random-shapes-eight/v1'
SIDE = 128
SYSTEM = 'Inspect every original image independently. Return only one JSON object.'
TASK = ('Return {"images":[{"image_id":string,"shape":string,"color":string,"position":integer}]} '
        'in supplied order, including duplicate pixels under their separate image_id. '
        'Each image has one colored shape on white. Shape is circle, square or triangle; '
        'color is red, green or blue. Position is its cell in a 3 by 3 grid, '
        'numbered 0..8 left to right, top to bottom. Use the image_ids in the sealed metadata.')


def _png(shape, color, position):
    colors = {'red': (230, 20, 20), 'green': (0, 175, 0), 'blue': (20, 30, 230)}
    cx, cy = 22 + position % 3 * 42, 22 + position // 3 * 42
    rows = bytearray()
    for y in range(SIDE):
        rows.append(0)
        for x in range(SIDE):
            dx, dy = x - cx, y - cy
            inside = (dx * dx + dy * dy <= 13 * 13 if shape == 'circle' else
                      abs(dx) <= 12 and abs(dy) <= 12 if shape == 'square' else
                      -13 <= dy <= 13 and abs(dx) <= (dy + 13) / 2)
            rows.extend(colors[color] if inside else (255, 255, 255))
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', SIDE, SIDE, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def prepare_probe(store, *, backend, model, profile, effort, refs, sandbox_config):
    run = store.create('router-image-capability', 'prepare-' + backend)
    images, rubric, artifacts = [], [], []
    first = None
    for index in range(8):
        identity = 'image-' + uuid.uuid4().hex
        if index == 7:
            raw, shape, color, position = first
        else:
            shape = secrets.choice(('circle', 'square', 'triangle'))
            color = secrets.choice(('red', 'green', 'blue'))
            position = secrets.randbelow(9)
            raw = _png(shape, color, position)
            if index == 0:
                first = raw, shape, color, position
        name = 'inputs/' + identity + '.png'
        artifacts.append(store.artifact(run, name, raw, media_type='image/png'))
        images.append({'image_id': identity, 'path': str(run/name), 'width': SIDE, 'height': SIDE,
                       'sha256': hash_bytes(raw), 'byte_length': len(raw)})
        rubric.append({'image_id': identity, 'shape': shape, 'color': color, 'position': position})
    task = {'schema': 'image-task/v1', 'parent_session_id': 'router-image-capability',
            'task_id': 'probe-' + run.name, 'backend': backend, 'model': model,
            'profile': profile, 'effort': effort, 'selected_refs': refs,
            'system_text': SYSTEM, 'task_text': TASK, 'metadata': {'purpose': 'capability'},
            'images': images, 'output_protocol': 'JSON_OBJECT/v1',
            'context_policy': 'FRESH_SEALED_INPUT/v1',
            'budgets': {'wall_seconds': 180, 'idle_seconds': 90, 'request_limit': 1,
                        'max_images': 8, 'max_png_bytes': 1024 * 1024,
                        'payload_bytes': 65536, 'output_bytes': 1024 * 1024,
                        'context_bytes': 1024 * 1024, 'generation_tokens': 2048}}
    if backend == 'codex' and profile == 'subscription-bounded':
        task['budgets'].update(generation_tokens=None, observed_output_tokens_limit=2048)
    inspected = inspect_images(task, store.root.parent/'image-contracts', sandbox_config=sandbox_config)
    path = Path(inspected['manifest'])
    artifacts.append(store.artifact(run, 'rubric.json', canonical_bytes({'images': rubric}),
                                    media_type='application/json'))
    artifacts.append(store.artifact(run, 'sealed-input.json', path.read_bytes(),
                                    media_type='application/json'))
    return store.finalize(run, {'kind': 'image-probe-input/v1', 'classification': 'FROZEN',
        'probe_version': PROBE_VERSION, 'manifest': str(path), 'manifest_sha256': hash_bytes(path.read_bytes()),
        'pins': inspected['pins'], 'artifacts': artifacts, 'wire_requests': 0,
        'authority': 'none', 'eligible': False, 'source_semantic': 'NOT_EVALUATED'})


def read_probe(store, identifier, manifest_path):
    record = store.read(identifier)
    path = Path(manifest_path)
    if (record.get('kind') != 'image-probe-input/v1' or record.get('classification') != 'FROZEN'
            or record.get('probe_version') != PROBE_VERSION
            or record.get('manifest') != str(path)
            or record.get('manifest_sha256') != hash_bytes(path.read_bytes())
            or (store.root/identifier/'sealed-input.json').read_bytes() != path.read_bytes()):
        raise RouterError('IMAGE_PROBE_BINDING_MISMATCH')
    sealed = verify_image_seal(path)
    task = sealed['task']
    generation = None if task['backend'] == 'codex' and task['profile'] == 'subscription-bounded' else 2048
    if (task['system_text'] != SYSTEM or task['task_text'] != TASK
            or task['metadata'] != {'purpose': 'capability'} or len(task['images']) != 8
            or task['budgets']['generation_tokens'] != generation or task['budgets']['request_limit'] != 1):
        raise RouterError('IMAGE_PROBE_BINDING_MISMATCH')
    rubric = strict_json((store.root/identifier/'rubric.json').read_bytes())
    if not isinstance(rubric, dict) or set(rubric) != {'images'} or len(rubric['images']) != 8:
        raise RouterError('IMAGE_PROBE_BINDING_MISMATCH')
    for descriptor, expected in zip(task['images'], rubric['images'], strict=True):
        if (not isinstance(expected, dict) or set(expected) != {'image_id', 'shape', 'color', 'position'}
                or expected['shape'] not in ('circle', 'square', 'triangle')
                or expected['color'] not in ('red', 'green', 'blue')
                or type(expected['position']) is not int or not 0 <= expected['position'] <= 8):
            raise RouterError('IMAGE_PROBE_BINDING_MISMATCH')
        if (descriptor['image_id'] != expected['image_id'] or descriptor['width'] != SIDE
                or descriptor['height'] != SIDE
                or hash_bytes(_png(expected['shape'], expected['color'], expected['position'])) != descriptor['sha256']):
            raise RouterError('IMAGE_PROBE_BINDING_MISMATCH')
    return record, rubric


def compare_probe(raw, rubric):
    value = strict_json(raw)
    return canonical_bytes(value) == canonical_bytes(rubric)
