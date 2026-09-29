"""Independent strict JSON object output, never project report normalization."""

from .contracts import RouterError, canonical_bytes, strict_json, hash_bytes


def parse_image_text(raw: bytes, maximum: int) -> tuple[dict, bytes]:
    if len(raw) > maximum:
        raise RouterError("IMAGE_OUTPUT_LIMIT")
    value = strict_json(raw)
    if not isinstance(value, dict):
        raise RouterError("IMAGE_OUTPUT_PROTOCOL_ERROR")
    canonical = canonical_bytes(value)
    if len(canonical) > maximum:
        raise RouterError("IMAGE_OUTPUT_LIMIT")
    return value, canonical


def decode_image_minimax(stdout: bytes, maximum: int, *, task, observation, response_bytes) -> tuple[bytes, bytes]:
    from .minimax_image_wire import validate_minimax_image_response
    value = strict_json(stdout)
    if (not isinstance(value, dict) or set(value) != {'schema', 'status', 'request_sha256', 'response_sha256', 'response'}
            or value['schema'] != 'minimax-image-runtime/v1' or value['status'] != 'completed'):
        raise RouterError('IMAGE_TERMINAL_MISSING')
    if (value['request_sha256'] != observation['actual_request_sha256']
            or value['response_sha256'] != observation['response_sha256']
            or hash_bytes(response_bytes) != observation['response_sha256']
            or canonical_bytes(value['response']) != canonical_bytes(strict_json(response_bytes))):
        raise RouterError('IMAGE_NATIVE_ASSOCIATION_MISMATCH')
    proof = validate_minimax_image_response(task, {'content-type': 'application/json',
        'x-request-id': observation['response_request_id']}, response_bytes)
    raw = proof['text'].encode('utf-8')
    _, canonical = parse_image_text(raw, maximum)
    return raw, canonical


def decode_image_claude(stdout: bytes, maximum: int) -> tuple[bytes, bytes]:
    if not stdout or not stdout.endswith(b"\n"):
        raise RouterError("IMAGE_TERMINAL_MISSING")
    events = [strict_json(line) for line in stdout.splitlines() if line.strip()]
    if any(not isinstance(item, dict) for item in events):
        raise RouterError("IMAGE_OUTPUT_PROTOCOL_ERROR")
    for item in events:
        if item.get("subtype") == "init":
            if (
                item.get("tools") != []
                or item.get("mcp_servers") != []
                or item.get("plugins") != []
            ):
                raise RouterError("TOOL_POLICY_VIOLATION")
        for block in item.get("message", {}).get("content", []):
            if block.get("type") in ("tool_use", "server_tool_use"):
                raise RouterError("TOOL_POLICY_VIOLATION")
    terminals = [item for item in events if item.get("type") == "result"]
    if len(terminals) != 1 or events[-1] is not terminals[0]:
        raise RouterError("IMAGE_TERMINAL_MISSING")
    terminal = terminals[0]
    if (
        terminal.get("is_error") is not False
        or terminal.get("subtype") != "success"
        or not isinstance(terminal.get("result"), str)
    ):
        raise RouterError("IMAGE_OUTPUT_PROTOCOL_ERROR")
    raw = terminal["result"].encode("utf-8")
    _, canonical = parse_image_text(raw, maximum)
    return raw, canonical


def _validate_codex_user(task, item):
    import base64
    from .adapters.image_claude import visible_text
    from .contracts import hash_bytes
    if task is None or set(item) != {'type', 'id', 'clientId', 'content'} or item['clientId'] is not None:
        raise RouterError('IMAGE_NATIVE_ASSOCIATION_MISMATCH')
    content = item['content']
    if (not isinstance(content, list) or len(content) != len(task['images'])+1
            or content[0] != {'type': 'text', 'text': visible_text(task), 'text_elements': []}):
        raise RouterError('IMAGE_BINDING_MISMATCH')
    for block, descriptor in zip(content[1:], task['images'], strict=True):
        if (set(block) != {'type', 'detail', 'url'} or block['type'] != 'image'
                or block['detail'] != 'high' or not block['url'].startswith('data:image/png;base64,')):
            raise RouterError('IMAGE_BINDING_MISMATCH')
        raw = base64.b64decode(block['url'][22:], validate=True)
        if len(raw) != descriptor['byte_length'] or hash_bytes(raw) != descriptor['sha256']:
            raise RouterError('IMAGE_BINDING_MISMATCH')


def decode_image_codex(stdout: bytes, maximum: int, *, task=None) -> tuple[bytes, bytes]:
    value = strict_json(stdout)
    if (not isinstance(value, dict) or set(value) != {
            'schema', 'thread_id', 'turn_id', 'error', 'native_cleanup', 'rpc'}
            or value['schema'] != 'image-codex-native/v1' or value['error'] is not None
            or value['native_cleanup'] is not True or not isinstance(value['rpc'], list)
            or not isinstance(value['thread_id'], str) or not value['thread_id']
            or not isinstance(value['turn_id'], str) or not value['turn_id']):
        raise RouterError('IMAGE_TERMINAL_MISSING')
    thread, turn = value['thread_id'], value['turn_id']
    events = value['rpc']
    if any(not isinstance(item, dict) for item in events):
        raise RouterError('IMAGE_OUTPUT_PROTOCOL_ERROR')
    starts = [x for x in events if x.get('id') == 2]
    turns = [x for x in events if x.get('id') == 3]
    if (len(starts) != 1 or len(turns) != 1
            or starts[0].get('result', {}).get('thread', {}).get('id') != thread
            or turns[0].get('result', {}).get('turn', {}).get('id') != turn):
        raise RouterError('IMAGE_NATIVE_ASSOCIATION_MISMATCH')
    terminals = [x for x in events if x.get('method') == 'turn/completed']
    if len(terminals) != 1:
        raise RouterError('IMAGE_TERMINAL_MISSING')
    terminal = terminals[0].get('params', {})
    result = terminal.get('turn', {})
    if (terminal.get('threadId') != thread or result.get('id') != turn
            or result.get('status') != 'completed' or result.get('error') is not None
            or not isinstance(result.get('items'), list)):
        raise RouterError('IMAGE_NATIVE_ASSOCIATION_MISMATCH')
    completed = {}
    users = []
    for event in events:
        method = event.get('method', '')
        if 'error' in event or ('id' in event and method):
            raise RouterError('IMAGE_NATIVE_REQUEST_FORBIDDEN')
        if method in ('error', 'turn/error'):
            raise RouterError('IMAGE_OUTPUT_PROTOCOL_ERROR')
        if method in ('item/started', 'item/completed'):
            params = event.get('params', {})
            item = params.get('item', {})
            if (params.get('threadId') != thread or params.get('turnId') != turn
                    or item.get('type') not in ('agentMessage', 'reasoning', 'userMessage')):
                raise RouterError('TOOL_POLICY_VIOLATION')
            if item['type'] == 'userMessage':
                _validate_codex_user(task, item)
            if method == 'item/completed':
                if item['type'] == 'userMessage':
                    users.append(item)
                    continue
                if item.get('id') in completed:
                    raise RouterError('IMAGE_NATIVE_ASSOCIATION_MISMATCH')
                completed[item.get('id')] = item
    messages = []
    items = result['items']
    if result.get('itemsView') == 'notLoaded':
        if items:
            raise RouterError('IMAGE_NATIVE_ASSOCIATION_MISMATCH')
        items = list(completed.values())
    for item in items:
        if (not isinstance(item, dict) or item.get('type') not in ('agentMessage', 'reasoning', 'userMessage')
                or completed.get(item.get('id')) != item):
            raise RouterError('IMAGE_NATIVE_ASSOCIATION_MISMATCH')
        if item['type'] == 'agentMessage':
            if not isinstance(item.get('text'), str) or item.get('phase') not in (None, 'final_answer'):
                raise RouterError('IMAGE_OUTPUT_PROTOCOL_ERROR')
            messages.append(item['text'])
    if len(messages) != 1 or len(completed) != len(items) or (task is not None and len(users) != 1):
        raise RouterError('IMAGE_OUTPUT_PROTOCOL_ERROR')
    raw = messages[0].encode('utf-8')
    _, canonical = parse_image_text(raw, maximum)
    return raw, canonical
