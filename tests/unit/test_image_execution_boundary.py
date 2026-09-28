import copy
import io
import json
from pathlib import Path

import pytest

from agent_subagent_router.contracts import Budgets, RouterError, canonical_bytes
from agent_subagent_router.image_output import decode_image_codex
from agent_subagent_router.image_process import ImageProcessBudgets
from agent_subagent_router.permissions import container_entry, image_container_entry


def native_result():
    item = {'id': 'message-1', 'type': 'agentMessage', 'text': '{"frames":[]}',
            'phase': 'final_answer'}
    turn = {'id': 'turn-1', 'status': 'completed', 'error': None, 'items': [item]}
    return {'schema': 'image-codex-native/v1', 'thread_id': 'thread-1', 'turn_id': 'turn-1',
            'error': None, 'native_cleanup': True,
            'rpc': [{'id': 2, 'result': {'thread': {'id': 'thread-1'}}},
                    {'id': 3, 'result': {'turn': {'id': 'turn-1'}}},
                    {'method': 'item/completed', 'params': {'threadId': 'thread-1',
                     'turnId': 'turn-1', 'item': item}},
                    {'method': 'turn/completed', 'params': {'threadId': 'thread-1',
                     'turn': turn}}]}


def test_codex_delivery_requires_complete_matching_native_turn():
    assert decode_image_codex(canonical_bytes(native_result()) + b'\n', 10000)[0] == b'{"frames":[]}'


@pytest.mark.parametrize('case', ['missing', 'wrong_thread', 'wrong_turn', 'tool', 'partial',
                                  'unmatched_item', 'cleanup', 'extra_terminal'])
def test_codex_capture_or_mismatched_terminal_cannot_deliver(case):
    data = json.loads(json.dumps(native_result()))
    terminal = data['rpc'][-1]
    if case == 'missing':
        data['rpc'].pop()
    elif case == 'wrong_thread':
        terminal['params']['threadId'] = 'other'
    elif case == 'wrong_turn':
        terminal['params']['turn']['id'] = 'other'
    elif case == 'tool':
        terminal['params']['turn']['items'].append({'id': 'evil', 'type': 'commandExecution'})
    elif case == 'partial':
        terminal['params']['turn']['status'] = 'failed'
    elif case == 'unmatched_item':
        data['rpc'][2]['params']['item']['id'] = 'other'
    elif case == 'cleanup':
        data['native_cleanup'] = False
    else:
        data['rpc'].append(copy.deepcopy(terminal))
    with pytest.raises(RouterError):
        decode_image_codex(canonical_bytes(data) + b'\n', 10000)


def test_image_process_budget_does_not_widen_project_schema():
    value = {'wall_seconds': 10, 'idle_seconds': 5, 'request_limit': 1,
             'output_bytes': 1024, 'context_bytes': 32 * 1024 * 1024,
             'generation_tokens': 2048}
    assert ImageProcessBudgets(**value).context_bytes == value['context_bytes']
    with pytest.raises(RouterError):
        Budgets(**value)


def test_image_relay_limits_are_explicit_and_original_entry_unchanged():
    assert container_entry._MAX_BODY == 8 * 1024 * 1024
    assert '/v1/responses' not in container_entry._ALLOWED_PATHS
    assert image_container_entry.IMAGE_BODY_BYTES == 32 * 1024 * 1024
    assert Path(image_container_entry.__file__).read_bytes()


def test_image_envelope_rejects_project_and_auth_environment(monkeypatch):
    data = {'argv': ['/opt/runtime/codex'], 'env': {'HOME': '/home/reggie'},
            'prompt_b64': '', 'wall_seconds': 10}
    monkeypatch.setattr(container_entry.sys, 'stdin', io.TextIOWrapper(io.BytesIO(json.dumps(data).encode())))
    with pytest.raises(ValueError):
        image_container_entry.read_image_envelope()


def test_native_summary_preserves_sealed_user_images_and_matching_output(tmp_path):
    import base64
    from test_codex_image_wire import request_fixture
    from agent_subagent_router.adapters.image_claude import visible_text
    task, _, pngs = request_fixture(tmp_path)
    data = json.loads(json.dumps(native_result()))
    user = {'type': 'userMessage', 'id': 'native-user', 'clientId': None,
        'content': [{'type': 'text', 'text': visible_text(task), 'text_elements': []}] + [
            {'type': 'image', 'detail': 'high', 'url': 'data:image/png;base64,'+base64.b64encode(raw).decode()}
            for raw in pngs]}
    data['rpc'].insert(2, {'method': 'item/completed', 'params': {
        'threadId': 'thread-1', 'turnId': 'turn-1', 'item': user}})
    data['rpc'][-1]['params']['turn']['itemsView'] = 'summary'
    assert decode_image_codex(canonical_bytes(data), 10000, task=task)[0] == b'{"frames":[]}'
    user['content'][1]['url'] = user['content'][2]['url']
    with pytest.raises(RouterError, match='IMAGE_BINDING_MISMATCH'):
        decode_image_codex(canonical_bytes(data), 10000, task=task)
