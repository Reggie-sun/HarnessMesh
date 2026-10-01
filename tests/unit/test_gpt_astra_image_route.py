import base64
import copy
import hashlib
from pathlib import Path

import pytest

from agent_subagent_router import image_contract as contract
from agent_subagent_router.contracts import RouterError, canonical_bytes, strict_json
from agent_subagent_router import codex_image_wire as wire
from agent_subagent_router.codex_image_wire import map_codex_image_request
from test_image_unrestricted_spending import fixture


SPEC = '0b58e1963b73037c1b13a18f01ed671cfb07558ee5e2af2cf68c6a44718ef3ac'
CONTROLLED_CONTROL_ONE = 'CONTROLLED TEST FIXTURE ONLY: synthetic world-state text.'
CONTROLLED_CONTROL_TWO = 'CONTROLLED TEST FIXTURE ONLY: synthetic agent policy text.'
CONTROLLED_CONTROL_HASHES = tuple(hashlib.sha256(text.encode()).hexdigest()
    for text in (CONTROLLED_CONTROL_ONE, CONTROLLED_CONTROL_TWO))


def _uuid(index):
    return f'0190f3e4-7a00-7000-8000-{index:012x}'


def _message(identifier, role, text):
    return {'type': 'message', 'id': f'msg_{identifier}', 'role': role,
        'content': [{'type': 'input_text', 'text': text}]}


def astra(tmp_path):
    task, classic = fixture(tmp_path, 'codex')
    task['model'] = classic['model'] = 'gpt-6-astra'
    classic['parallel_tool_calls'] = False
    task['selected_refs'].append({'path': '/tmp/astra-spec.md', 'sha256': SPEC, 'accepted': True})
    system = classic.pop('instructions')
    classic.pop('tools')
    classic['text'] = {'verbosity': 'low'}
    classic['reasoning'] = {'effort': 'high', 'context': 'all_turns'}
    user = copy.deepcopy(classic['input'][0])
    user['id'] = f'msg_{_uuid(5)}'
    classic['input'] = [
        {'type': 'additional_tools', 'id': f'at_{_uuid(1)}', 'role': 'developer', 'tools': []},
        _message(_uuid(2), 'developer', system),
        _message(_uuid(3), 'developer', CONTROLLED_CONTROL_ONE),
        _message(_uuid(4), 'developer', CONTROLLED_CONTROL_TWO),
        user,
    ]
    return task, classic


def controlled_astra(tmp_path, monkeypatch):
    task, body = astra(tmp_path)
    # The authentic role text is runtime-specific and intentionally absent from this fixture.
    # These hashes qualify only the two explicitly synthetic strings above.
    monkeypatch.setattr(wire, '_ASTRA_CONTROL_MESSAGE_SHA256', CONTROLLED_CONTROL_HASHES)
    return task, body


def test_exact_astra_tuple_requires_new_accepted_contract(tmp_path):
    assert hashlib.sha256(Path('docs/superpowers/specs/2026-10-01-gpt-astra-image-route.md').read_bytes()).hexdigest() == SPEC
    task, _ = astra(tmp_path)
    assert contract.selected_subscription_model(task)
    assert contract.ImageTaskContract.from_dict(task).to_dict()['model'] == 'gpt-6-astra'
    task['selected_refs'].pop()
    with pytest.raises(RouterError, match='IMAGE_ROUTE_MISMATCH'):
        contract.ImageTaskContract.from_dict(task)


@pytest.mark.parametrize('mutation', ['effort', 'profile', 'backend', 'model', 'ref', 'accepted'])
def test_new_reference_cannot_authorize_other_tuples(tmp_path, mutation):
    task, _ = astra(tmp_path)
    if mutation == 'effort': task['effort'] = 'max'
    elif mutation == 'profile': task['profile'] = 'api-bounded'
    elif mutation == 'backend': task['backend'] = 'minimax'
    elif mutation == 'model': task['model'] = 'gpt-6-astra-alias'
    elif mutation == 'ref': task['selected_refs'][-1]['sha256'] = 'f' * 64
    else: task['selected_refs'][-1]['accepted'] = False
    assert not contract.selected_subscription_model(task)
    with pytest.raises(RouterError): contract.ImageTaskContract.from_dict(task)


def test_runtime_control_hashes_are_exact_literals():
    assert wire._ASTRA_CONTROL_MESSAGE_SHA256 == (
        '47091490938505958b0c22ff42db6fd79b272a2af6923166f4c2cc53c4fe0df4',
        '6ded806e3cdbb35599ecaf8742574bc5274908472b1729090010c404c2151e8e',
    )


def test_astra_lite_projects_only_two_pinned_controls_and_preserves_sealed_inputs(tmp_path, monkeypatch):
    task, body = controlled_astra(tmp_path, monkeypatch)
    frozen_body = copy.deepcopy(body)
    native_bytes = canonical_bytes(body)

    actual_bytes, proof = map_codex_image_request(task, body)
    actual = strict_json(actual_bytes)

    assert set(actual) == {
        'model', 'input', 'tool_choice', 'parallel_tool_calls', 'reasoning', 'store',
        'stream', 'include', 'prompt_cache_key', 'text', 'client_metadata',
    }
    assert actual['reasoning'] == {'effort': 'high', 'context': 'all_turns'}
    assert actual['text'] == {'verbosity': 'low'}
    assert actual['input'] == body['input'][:2] + body['input'][4:]
    assert actual['input'][0] == frozen_body['input'][0]
    assert actual['input'][1] == frozen_body['input'][1]
    assert actual['input'][2] == frozen_body['input'][4]
    assert CONTROLLED_CONTROL_ONE not in actual_bytes.decode()
    assert CONTROLLED_CONTROL_TWO not in actual_bytes.decode()
    assert body == frozen_body
    assert proof['projection_version'] == 'codex-responses-lite-astra/v1'
    assert proof['native_request_sha256'] == hashlib.sha256(native_bytes).hexdigest()
    assert proof['actual_request_sha256'] == hashlib.sha256(actual_bytes).hexdigest()
    assert proof['removed_control_items'] == [
        {'position': 2, 'id': body['input'][2]['id'], 'sha256': CONTROLLED_CONTROL_HASHES[0]},
        {'position': 3, 'id': body['input'][3]['id'], 'sha256': CONTROLLED_CONTROL_HASHES[1]},
    ]
    assert proof['removed_control_item_count'] == 2
    assert proof['native_additional_tools_id'] == body['input'][0]['id']
    assert proof['native_system_message_id'] == body['input'][1]['id']
    assert proof['native_message_id'] == body['input'][4]['id']
    assert proof['system_sha256'] == hashlib.sha256(task['system_text'].encode()).hexdigest()
    assert proof['visible_text_sha256'] == hashlib.sha256(
        wire.visible_text(task).encode()).hexdigest()
    assert proof['images'] == [{key: descriptor[key] for key in
        ('image_id', 'byte_length', 'sha256', 'width', 'height')} for descriptor in task['images']]
    assert proof['generation_tokens'] is None


@pytest.mark.parametrize('mutation', [
    'control-byte', 'control-order', 'duplicate-id', 'duplicate-control', 'extra-input',
    'nonempty-additional-tools', 'top-level-tools', 'classic-shape', 'reasoning-context',
    'lite-parallel-enabled', 'wrong-model', 'wrong-ref', 'bad-id', 'wrong-role', 'system-drift', 'user-text-drift',
    'png-drift', 'context-limit',
])
def test_astra_lite_rejects_unsealed_or_unexpected_input_drift(tmp_path, monkeypatch, mutation):
    task, body = controlled_astra(tmp_path, monkeypatch)
    if mutation == 'control-byte':
        body['input'][2]['content'][0]['text'] += 'x'
    elif mutation == 'control-order':
        body['input'][2], body['input'][3] = body['input'][3], body['input'][2]
    elif mutation == 'duplicate-id':
        body['input'][3]['id'] = body['input'][2]['id']
    elif mutation == 'duplicate-control':
        body['input'][3] = copy.deepcopy(body['input'][2])
    elif mutation == 'extra-input':
        body['input'].append(copy.deepcopy(body['input'][4]))
    elif mutation == 'nonempty-additional-tools':
        body['input'][0]['tools'] = [{'type': 'web_search'}]
    elif mutation == 'top-level-tools':
        body['tools'] = []
    elif mutation == 'classic-shape':
        body['instructions'] = task['system_text']
    elif mutation == 'reasoning-context':
        body['reasoning']['context'] = 'current_turn'
    elif mutation == 'lite-parallel-enabled':
        body['parallel_tool_calls'] = True
    elif mutation == 'wrong-model':
        task['model'] = body['model'] = 'gpt-6.1-sol'
    elif mutation == 'wrong-ref':
        task['selected_refs'].pop()
    elif mutation == 'bad-id':
        body['input'][0]['id'] = 'at_0190f3e4-7a00-4000-8000-000000000001'
    elif mutation == 'wrong-role':
        body['input'][2]['role'] = 'user'
    elif mutation == 'system-drift':
        body['input'][1]['content'][0]['text'] += 'x'
    elif mutation == 'user-text-drift':
        body['input'][4]['content'][0]['text'] += 'x'
    elif mutation == 'png-drift':
        item = body['input'][4]['content'][1]
        image = bytearray(base64.b64decode(item['image_url'].partition(',')[2]))
        image[-8] ^= 1
        item['image_url'] = 'data:image/png;base64,' + base64.b64encode(image).decode()
    else:
        task['budgets']['context_bytes'] = 1

    with pytest.raises(RouterError):
        map_codex_image_request(task, body)


def test_legacy_tuple_and_model_gate_are_unchanged(tmp_path):
    task, body = fixture(tmp_path, 'codex')
    original = copy.deepcopy(task)
    assert not contract.selected_subscription_model(task)
    contract.ImageTaskContract.from_dict(task)
    map_codex_image_request(task, body)
    assert task == original


def test_legacy_classic_wire_still_requires_parallel_tools_true(tmp_path):
    task, body = fixture(tmp_path, 'codex')
    body['parallel_tool_calls'] = False
    with pytest.raises(RouterError, match='IMAGE_ROUTE_MISMATCH'):
        map_codex_image_request(task, body)


@pytest.mark.parametrize('metadata', [None, {}, {'spending_policy': 'unknown'}])
def test_astra_cannot_enter_legacy_spending_path(tmp_path, metadata):
    task, _ = astra(tmp_path)
    task['metadata'] = metadata
    assert not contract.selected_subscription_model(task)
    with pytest.raises(RouterError): contract.ImageTaskContract.from_dict(task)


def test_astra_still_requires_original_unrestricted_authorization(tmp_path):
    task, _ = astra(tmp_path)
    task['selected_refs'] = [ref for ref in task['selected_refs']
        if ref['sha256'] != contract.UNRESTRICTED_SPENDING_SPEC_SHA]
    with pytest.raises(RouterError, match='IMAGE_SPENDING_ACCEPTANCE_REQUIRED'):
        contract.ImageTaskContract.from_dict(task)
