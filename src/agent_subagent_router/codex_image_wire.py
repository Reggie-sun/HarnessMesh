"""Pinned native Codex projection and strict Responses API identity checks."""

import base64
import binascii
import re
import uuid

from .adapters.image_claude import visible_text
from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .image_contract import ImageTaskContract, _validate_png_bytes


WIRE_VERSION = "codex-image-api-cap/v1"
MAX_CODEX_IMAGE_TOKENS = 2048
_NATIVE_FIELDS = {
    "model", "instructions", "input", "tools", "tool_choice", "parallel_tool_calls",
    "reasoning", "store", "stream", "include", "prompt_cache_key", "text",
    "client_metadata",
}
_REQUEST_FIELDS = _NATIVE_FIELDS | {"max_output_tokens"}
_ASTRA_LITE_FIELDS = {
    "model", "input", "tool_choice", "parallel_tool_calls", "reasoning", "store",
    "stream", "include", "prompt_cache_key", "text", "client_metadata",
}
_ASTRA_CONTROL_MESSAGE_SHA256 = (
    '47091490938505958b0c22ff42db6fd79b272a2af6923166f4c2cc53c4fe0df4',
    '6ded806e3cdbb35599ecaf8742574bc5274908472b1729090010c404c2151e8e',
)
_ASTRA_PROJECTION_VERSION = 'codex-responses-lite-astra/v1'
_CLIENT_METADATA_FIELDS = {
    "x-codex-turn-metadata", "x-codex-installation-id", "thread_id", "session_id",
    "x-codex-window-id", "turn_id", "root_turn_id",
}
_TURN_METADATA_FIELDS = {
    "installation_id", "session_id", "thread_id", "agent_name", "turn_id", "window_id",
    "window_number", "context_window_id", "request_kind", "root_turn_id", "sandbox",
    "sandbox_mode", "auto_review_enabled", "node_repl_auto_review_required",
    "node_repl_disabled", "turn_started_at_unix_ms",
}
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_MESSAGE_ID = re.compile(r"^msg_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")
_ADDITIONAL_TOOLS_ID = re.compile(r"^at_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")


def _fail(code="IMAGE_PROJECTION_MISMATCH", detail=""):
    raise RouterError(code, detail)


def _uuid(value, code="IMAGE_METADATA_MISMATCH", *, version=None):
    if not isinstance(value, str):
        _fail(code)
    try:
        parsed = uuid.UUID(value)
        if str(parsed) != value or (version is not None and parsed.version != version):
            raise ValueError()
    except (ValueError, AttributeError):
        _fail(code)
    return value


def _image_metadata(task, body):
    metadata = body["client_metadata"]
    if type(metadata) is not dict or set(metadata) != _CLIENT_METADATA_FIELDS:
        _fail("IMAGE_METADATA_MISMATCH")
    raw_turn = metadata["x-codex-turn-metadata"]
    if not isinstance(raw_turn, str) or len(raw_turn.encode("utf-8")) > 4096:
        _fail("IMAGE_METADATA_MISMATCH")
    turn = strict_json(raw_turn)
    if type(turn) is not dict or set(turn) != _TURN_METADATA_FIELDS:
        _fail("IMAGE_METADATA_MISMATCH")

    _uuid(turn["installation_id"], version=4)
    for field in (
        "session_id", "thread_id", "turn_id", "context_window_id", "root_turn_id",
    ):
        _uuid(turn[field], version=7)
    for field in ("installation_id", "session_id", "thread_id", "turn_id", "root_turn_id"):
        if metadata["x-codex-installation-id" if field == "installation_id" else field] != turn[field]:
            _fail("IMAGE_METADATA_MISMATCH")
    if (turn["agent_name"] != "/root" or turn["request_kind"] != "turn"
            or turn["sandbox"] != "seccomp" or turn["sandbox_mode"] != "read-only"
            or turn["auto_review_enabled"] is not False
            or turn["node_repl_auto_review_required"] is not False
            or turn["node_repl_disabled"] is not False):
        _fail("IMAGE_METADATA_MISMATCH")
    window_number = turn["window_number"]
    if type(window_number) is not int or not 0 <= window_number <= 2_147_483_647:
        _fail("IMAGE_METADATA_MISMATCH")
    expected_window_id = f'{turn["thread_id"]}:{window_number}'
    if turn["session_id"] != turn["thread_id"] or turn["turn_id"] != turn["root_turn_id"]:
        _fail("IMAGE_METADATA_MISMATCH")
    if turn["window_id"] != expected_window_id:
        _fail("IMAGE_METADATA_MISMATCH")
    timestamp = turn["turn_started_at_unix_ms"]
    if type(timestamp) is not int or not 1 <= timestamp <= 9_007_199_254_740_991:
        _fail("IMAGE_METADATA_MISMATCH")
    if metadata["x-codex-window-id"] != turn["window_id"]:
        _fail("IMAGE_METADATA_MISMATCH")
    if body["prompt_cache_key"] != turn["thread_id"]:
        _fail("IMAGE_METADATA_MISMATCH")
    return {
        "installation_id": turn["installation_id"],
        "session_id": turn["session_id"],
        "thread_id": turn["thread_id"],
        "turn_id": turn["turn_id"],
        "root_turn_id": turn["root_turn_id"],
        "window_id": turn["window_id"],
        "context_window_id": turn["context_window_id"],
    }


def _message_id(message, role):
    if (type(message) is not dict or set(message) != {"type", "id", "role", "content"}
            or message["type"] != "message" or message["role"] != role):
        _fail("IMAGE_CONTEXT_MISMATCH")
    matched = _MESSAGE_ID.fullmatch(message['id']) if isinstance(message['id'], str) else None
    if matched is None:
        _fail("IMAGE_METADATA_MISMATCH")
    _uuid(matched.group(1), code="IMAGE_METADATA_MISMATCH", version=7)
    return message['id']


def _single_input_text(message):
    content = message['content']
    if type(content) is not list or len(content) != 1:
        _fail("IMAGE_CONTEXT_MISMATCH")
    text = content[0]
    if type(text) is not dict or set(text) != {"type", "text"} or text.get('type') != 'input_text':
        _fail("IMAGE_CONTEXT_MISMATCH")
    if not isinstance(text.get('text'), str):
        _fail("IMAGE_CONTEXT_MISMATCH")
    return text['text']


def _validate_user_content(task, message, system_text):
    content = message['content']
    if type(content) is not list or len(content) != len(task["images"]) + 1:
        _fail("IMAGE_BINDING_MISMATCH")
    expected_text = visible_text(task)
    if type(content[0]) is not dict or set(content[0]) != {"type", "text"} or content[0] != {
        "type": "input_text", "text": expected_text,
    }:
        _fail("IMAGE_CONTEXT_MISMATCH")
    context_bytes = len(system_text.encode("utf-8")) + len(expected_text.encode("utf-8"))
    if context_bytes > task["budgets"]["context_bytes"]:
        _fail("IMAGE_CONTEXT_LIMIT")

    image_proof = []
    for descriptor, item in zip(task["images"], content[1:], strict=True):
        if (type(item) is not dict or set(item) != {"type", "image_url", "detail"}
                or item["type"] != "input_image" or item["detail"] != "high"
                or not isinstance(item["image_url"], str)
                or not item["image_url"].startswith("data:image/png;base64,")):
            _fail("IMAGE_BINDING_MISMATCH")
        try:
            data = base64.b64decode(item["image_url"].partition(",")[2], validate=True)
        except (ValueError, TypeError, binascii.Error):
            _fail("IMAGE_BINDING_MISMATCH")
        _validate_png_bytes(data, descriptor)
        image_proof.append({
            key: descriptor[key]
            for key in ("image_id", "byte_length", "sha256", "width", "height")
        })
    return image_proof, expected_text


def _validate_astra_lite_input(task, body):
    items = body['input']
    if type(items) is not list or len(items) != 5:
        _fail('IMAGE_CONTEXT_MISMATCH')

    additional = items[0]
    if (type(additional) is not dict or set(additional) != {'type', 'id', 'role', 'tools'}
            or additional['type'] != 'additional_tools' or additional['role'] != 'developer'
            or type(additional['tools']) is not list or additional['tools'] != []):
        _fail('IMAGE_CONTEXT_MISMATCH')
    additional_match = (_ADDITIONAL_TOOLS_ID.fullmatch(additional['id'])
        if isinstance(additional['id'], str) else None)
    if additional_match is None:
        _fail('IMAGE_METADATA_MISMATCH')
    _uuid(additional_match.group(1), code='IMAGE_METADATA_MISMATCH', version=7)

    system = items[1]
    system_id = _message_id(system, 'developer')
    if _single_input_text(system) != task['system_text']:
        _fail('IMAGE_CONTEXT_MISMATCH')

    removed = []
    for position, expected_hash, item in zip((2, 3), _ASTRA_CONTROL_MESSAGE_SHA256, items[2:4], strict=True):
        message_id = _message_id(item, 'developer')
        control_text = _single_input_text(item)
        try:
            digest = hash_bytes(control_text.encode('utf-8', 'strict'))
        except UnicodeError:
            _fail('IMAGE_CONTEXT_MISMATCH')
        if digest != expected_hash:
            _fail('IMAGE_CONTEXT_MISMATCH')
        removed.append({'position': position, 'id': message_id, 'sha256': digest})

    user = items[4]
    user_id = _message_id(user, 'user')
    ids = [additional['id'], system_id, *(item['id'] for item in items[2:4]), user_id]
    if len(ids) != len(set(ids)):
        _fail('IMAGE_METADATA_MISMATCH')
    images, text = _validate_user_content(task, user, task['system_text'])
    projection = {
        'removed_positions': (2, 3),
        'projection_version': _ASTRA_PROJECTION_VERSION,
        'removed_control_items': removed,
        'removed_control_item_count': len(removed),
        'native_additional_tools_id': additional['id'],
        'native_system_message_id': system_id,
    }
    return images, user_id, text, projection


def _validate_native_request(task, body):
    from .image_contract import selected_subscription_model
    astra_lite = task['profile'] == 'subscription-bounded' and selected_subscription_model(task)
    expected_parallel_tools = False if astra_lite else True
    if astra_lite:
        fields = (_ASTRA_LITE_FIELDS,)
        reasoning = {'effort': task['effort'], 'context': 'all_turns'}
    else:
        fields = (_NATIVE_FIELDS, _REQUEST_FIELDS)
        reasoning = {"effort": task["effort"]}
        if task['profile'] == 'subscription-bounded' and task['model'] in (
                'gpt-6.1-sol', 'gpt-6-sol', 'gpt-6-luna'):
            fields = (_NATIVE_FIELDS - {'text'}, _REQUEST_FIELDS - {'text'})
            reasoning['summary'] = 'auto'
    if type(body) is not dict or set(body) not in fields:
        _fail()
    if task["backend"] != "codex" or task["profile"] not in ("api-bounded", "subscription-bounded"):
        _fail("IMAGE_ROUTE_MISMATCH")
    if (body["model"] != task["model"]
            or (not astra_lite and (body["instructions"] != task["system_text"] or body["tools"] != []))
            or body["tool_choice"] != "auto"
            or body["parallel_tool_calls"] is not expected_parallel_tools or body["store"] is not False
            or body["stream"] is not True
            or body["reasoning"] != reasoning
            or body["include"] != ["reasoning.encrypted_content"]
            or ('text' in body and body["text"] != {"verbosity": "low"})):
        _fail("IMAGE_ROUTE_MISMATCH")
    cap = task["budgets"]["generation_tokens"]
    if cap is not None and cap > MAX_CODEX_IMAGE_TOKENS:
        _fail("IMAGE_GENERATION_LIMIT")
    if task['profile'] == 'subscription-bounded' and 'max_output_tokens' in body:
        _fail('IMAGE_GENERATION_MISMATCH')
    if "max_output_tokens" in body and (
        type(body["max_output_tokens"]) is not int or body["max_output_tokens"] != cap
    ):
        _fail("IMAGE_GENERATION_MISMATCH")

    projection = None
    if astra_lite:
        image_proof, message_id, expected_text, projection = _validate_astra_lite_input(task, body)
    else:
        input_value = body["input"]
        if type(input_value) is not list or len(input_value) != 1:
            _fail("IMAGE_CONTEXT_MISMATCH")
        message = input_value[0]
        message_id = _message_id(message, 'user')
        image_proof, expected_text = _validate_user_content(task, message, body['instructions'])
    return _image_metadata(task, body), image_proof, message_id, expected_text, projection


def map_codex_image_request(task: dict, body: dict) -> tuple[bytes, dict]:
    """Validate one pinned native request and mechanically add its sealed hard cap."""
    contract = ImageTaskContract.from_dict(task).to_dict()
    if contract["output_protocol"] != "JSON_OBJECT/v1":
        _fail("IMAGE_ROUTE_MISMATCH")
    identity, images, message_id, visible, projection = _validate_native_request(contract, body)
    try:
        native = canonical_bytes(body)
        mapped = dict(body)
        if projection is not None:
            removed_positions = set(projection['removed_positions'])
            mapped['input'] = [item for index, item in enumerate(body['input'])
                if index not in removed_positions]
        if contract['profile'] == 'api-bounded':
            mapped["max_output_tokens"] = contract["budgets"]["generation_tokens"]
        actual = canonical_bytes(mapped)
    except (TypeError, ValueError, UnicodeError):
        _fail()
    if len(native) > contract["budgets"]["payload_bytes"]:
        _fail("IMAGE_PAYLOAD_LIMIT")
    if len(actual) > contract["budgets"]["payload_bytes"]:
        _fail("IMAGE_PAYLOAD_LIMIT")
    proof = {
        "version": 'codex-image-subscription/v1' if contract['profile'] == 'subscription-bounded' else WIRE_VERSION,
        "images": images,
        "session_id": identity["session_id"],
        "thread_id": identity["thread_id"],
        "turn_id": identity["turn_id"],
        "root_turn_id": identity["root_turn_id"],
        "window_id": identity["window_id"],
        "native_message_id": message_id,
        "native_request_sha256": hash_bytes(native),
        "actual_request_sha256": hash_bytes(actual),
        "system_sha256": hash_bytes(contract["system_text"].encode("utf-8")),
        "visible_text_sha256": hash_bytes(visible.encode("utf-8")),
        "generation_tokens": contract["budgets"]["generation_tokens"],
    }
    if contract['profile'] == 'subscription-bounded':
        proof['observed_output_tokens_limit'] = contract['budgets']['observed_output_tokens_limit']
        proof['native_text_verbosity'] = body.get('text', {}).get('verbosity')
        if projection is None:
            proof['native_reasoning_summary'] = body['reasoning'].get('summary')
        else:
            proof['native_reasoning_context'] = body['reasoning'].get('context')
    if projection is not None:
        proof.update({key: projection[key] for key in (
            'projection_version', 'removed_control_items', 'removed_control_item_count',
            'native_additional_tools_id', 'native_system_message_id')})
    return actual, proof


def _response_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"resp_[A-Za-z0-9_-]{1,128}", value):
        _fail("IDENTITY_UNVERIFIED")
    return value


def _validate_reasoning_fields(item):
    """Use the same semantic shapes for initial, done and terminal items."""
    summary, content = item.get('summary'), item.get('content')
    if (not isinstance(summary, list) or any(
            not isinstance(part, dict) or part.get('type') != 'summary_text'
            or not isinstance(part.get('text'), str) for part in summary)
            or (content is not None and (not isinstance(content, list) or any(
                not isinstance(part, dict) or part.get('type') != 'reasoning_text'
                or not isinstance(part.get('text'), str) for part in content)))
            or (item.get('encrypted_content') is not None
                and not isinstance(item['encrypted_content'], str))):
        _fail('UPSTREAM_PROTOCOL_ERROR')


def _validate_response_object(task, response, request_id, response_id=None):
    if type(response) is not dict:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    actual_id = _response_id(response.get("id"))
    if response_id is not None and actual_id != response_id:
        _fail("IDENTITY_UNVERIFIED")
    if response.get("request_id") is not None and response["request_id"] != request_id:
        _fail("IDENTITY_UNVERIFIED")
    subscription = task['profile'] == 'subscription-bounded'
    cap_matches = (response.get('max_output_tokens') is None if subscription else
        type(response.get('max_output_tokens')) is int
        and response['max_output_tokens'] == task['budgets']['generation_tokens'])
    if (response.get("status") != "completed" or response.get("model") != task["model"] or not cap_matches):
        _fail("IDENTITY_UNVERIFIED")
    usage = response.get("usage")
    if type(usage) is not dict:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    cap = task['budgets']['observed_output_tokens_limit'] if subscription else task["budgets"]["generation_tokens"]
    if (type(input_tokens) is not int or input_tokens < 0 or type(output_tokens) is not int
            or output_tokens < 0 or (cap is not None and output_tokens > cap)):
        _fail("IMAGE_GENERATION_LIMIT")
    output = response.get("output")
    if type(output) is not list or not output:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    text_parts = []
    for item in output:
        if type(item) is not dict:
            _fail("UPSTREAM_PROTOCOL_ERROR")
        if not isinstance(item.get('id'), str) or not item['id']:
            _fail('IDENTITY_UNVERIFIED')
        if item.get("type") == "reasoning":
            _validate_reasoning_fields(item)
            continue
        if (item.get("type") != "message" or item.get("role") != "assistant"
                or item.get("status") not in (None, "completed")):
            _fail("TOOL_POLICY_VIOLATION")
        content = item.get("content")
        if type(content) is not list or not content:
            _fail("UPSTREAM_PROTOCOL_ERROR")
        for part in content:
            if (type(part) is not dict or part.get("type") != "output_text"
                    or not isinstance(part.get("text"), str)):
                _fail("TOOL_POLICY_VIOLATION")
            text_parts.append(part["text"])
    text = "".join(text_parts)
    if not text or len(text.encode("utf-8")) > task["budgets"]["output_bytes"]:
        _fail("UPSTREAM_OUTPUT_LIMIT")
    return {
        "text": text,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "request_id": request_id,
        "response_id": actual_id,
        "model": task["model"],
        "max_output_tokens": None if subscription else cap,
        **({'observed_output_tokens_limit': cap} if subscription else {}),
    }


def _parse_sse(data):
    if not data.endswith((b"\n\n", b"\r\n\r\n")):
        _fail("UPSTREAM_PROTOCOL_ERROR", "truncated event stream")
    normalized = data.replace(b"\r\n", b"\n")
    events = []
    event_name, data_lines = None, []
    for line in normalized.split(b"\n"):
        if not line:
            if event_name is None and not data_lines:
                continue
            if event_name is None or not data_lines:
                _fail("UPSTREAM_PROTOCOL_ERROR")
            value = strict_json(b"\n".join(data_lines))
            if type(value) is not dict or value.get("type") != event_name:
                _fail("UPSTREAM_PROTOCOL_ERROR")
            events.append(value)
            event_name, data_lines = None, []
            continue
        if line.startswith(b"event: ") and event_name is None and not data_lines:
            try:
                event_name = line[7:].decode("ascii")
            except UnicodeDecodeError:
                _fail("UPSTREAM_PROTOCOL_ERROR")
        elif line.startswith(b"data: ") and event_name is not None:
            data_lines.append(line[6:])
        else:
            _fail("UPSTREAM_PROTOCOL_ERROR")
    if event_name is not None or data_lines or not events:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    return events


def _validate_sse_output(events, output):
    """Bind every message delta/done/item to the authenticated terminal item."""
    opened, finished, parts, done = set(), set(), {}, set()
    summaries, summary_done = {}, set()
    for event in events:
        kind = event['type']
        if kind in ('response.reasoning_summary_text.delta', 'response.reasoning_summary_text.done'):
            index, summary_index = event.get('output_index'), event.get('summary_index')
            if (type(index) is not int or not 0 <= index < len(output)
                    or index not in opened or index in finished):
                _fail('UPSTREAM_PROTOCOL_ERROR')
            item = output[index]
            summary = item.get('summary')
            if (item['type'] != 'reasoning' or event.get('item_id') != item.get('id')
                    or type(summary) is not list or type(summary_index) is not int
                    or not 0 <= summary_index < len(summary)):
                _fail('IDENTITY_UNVERIFIED')
            expected = summary[summary_index]
            position = (index, summary_index)
            if (not isinstance(expected, dict) or expected.get('type') != 'summary_text'
                    or not isinstance(expected.get('text'), str) or position in summary_done):
                _fail('UPSTREAM_PROTOCOL_ERROR')
            if kind.endswith('.delta'):
                summaries[position] = summaries.get(position, '') + event['delta']
            elif event['text'] != summaries.get(position, '') or event['text'] != expected['text']:
                _fail('UPSTREAM_PROTOCOL_ERROR')
            else:
                summary_done.add(position)
            continue
        if kind not in ('response.output_item.added', 'response.output_item.done',
                        'response.content_part.added', 'response.content_part.done',
                        'response.output_text.delta', 'response.output_text.done'):
            continue
        index = event.get('output_index')
        if type(index) is not int or not 0 <= index < len(output):
            _fail('UPSTREAM_PROTOCOL_ERROR')
        item = output[index]
        if kind.startswith('response.output_item.'):
            actual = event['item']
            if actual.get('id') != item.get('id') or actual.get('type') != item.get('type'):
                _fail('IDENTITY_UNVERIFIED')
            if kind.endswith('.added'):
                if index in opened or index in finished:
                    _fail('UPSTREAM_PROTOCOL_ERROR')
                opened.add(index)
                if item['type'] == 'message' and (
                        actual.get('content') != [] or actual.get('status') != 'in_progress'):
                    _fail('UPSTREAM_PROTOCOL_ERROR')
                if item['type'] == 'reasoning' and (actual.get('summary') != []
                        or actual.get('content') not in (None, [])):
                    _fail('UPSTREAM_PROTOCOL_ERROR')
            else:
                if index not in opened or index in finished or actual != item:
                    _fail('UPSTREAM_PROTOCOL_ERROR')
                if item['type'] == 'message' and any(
                        (index, p) not in done for p in range(len(item['content']))):
                    _fail('UPSTREAM_PROTOCOL_ERROR')
                finished.add(index)
            continue
        part_index = event.get('content_index')
        if (item['type'] != 'message' or index not in opened or index in finished
                or event.get('item_id') != item.get('id') or type(part_index) is not int
                or not 0 <= part_index < len(item['content'])):
            _fail('IDENTITY_UNVERIFIED')
        position = (index, part_index)
        expected = item['content'][part_index]
        if kind == 'response.content_part.added':
            if position in parts or dict(event['part'], text=expected['text']) != expected or event['part'].get('text') != '':
                _fail('UPSTREAM_PROTOCOL_ERROR')
            parts[position] = ''
        elif kind == 'response.output_text.delta':
            if position not in parts or position in done:
                _fail('UPSTREAM_PROTOCOL_ERROR')
            parts[position] += event['delta']
        elif kind == 'response.output_text.done':
            if (position not in parts or position in done or event['text'] != parts[position]
                    or event['text'] != expected['text']):
                _fail('UPSTREAM_PROTOCOL_ERROR')
            done.add(position)
        elif position not in done or event['part'] != expected:
            _fail('UPSTREAM_PROTOCOL_ERROR')
    for index, item in enumerate(output):
        if (item['type'] == 'message' or index in opened) and index not in finished:
            _fail('UPSTREAM_PROTOCOL_ERROR')
    if any(position not in summary_done or position[0] not in finished for position in summaries):
        _fail('UPSTREAM_PROTOCOL_ERROR')


def _sse_response(task, data, request_id):
    events = _parse_sse(data)
    if events[0].get("type") != "response.created" or events[-1].get("type") != "response.completed":
        _fail("IDENTITY_UNVERIFIED")
    response_id = None
    terminal = False
    created = False
    item_ids = set()
    for index, event in enumerate(events):
        kind = event["type"]
        if terminal:
            _fail("UPSTREAM_PROTOCOL_ERROR")
        if kind in ("response.created", "response.in_progress", "response.completed"):
            response = event.get("response")
            if type(response) is not dict:
                _fail("UPSTREAM_PROTOCOL_ERROR")
            current = _response_id(response.get("id"))
            if response_id is None:
                if kind != "response.created" or created:
                    _fail("IDENTITY_UNVERIFIED")
                response_id = current
            elif current != response_id:
                _fail("IDENTITY_UNVERIFIED")
            elif kind == "response.created":
                _fail("IDENTITY_UNVERIFIED")
            if response.get("request_id") is not None and response["request_id"] != request_id:
                _fail("IDENTITY_UNVERIFIED")
            if response.get("model") is not None and response["model"] != task["model"]:
                _fail("IDENTITY_UNVERIFIED")
            if (response.get("max_output_tokens") is not None
                    and (type(response["max_output_tokens"]) is not int
                         or response["max_output_tokens"] != task["budgets"]["generation_tokens"])):
                _fail("IDENTITY_UNVERIFIED")
            if kind == "response.created":
                if (response.get("model") != task["model"]
                        or (task['profile'] != 'subscription-bounded'
                            and type(response.get("max_output_tokens")) is not int)
                        or response.get("status") not in ("queued", "in_progress")):
                    _fail("IDENTITY_UNVERIFIED")
                created = True
            elif kind == "response.in_progress" and response.get("status") != "in_progress":
                _fail("IDENTITY_UNVERIFIED")
            if kind in ("response.created", "response.in_progress") and response.get("output") != []:
                _fail("UPSTREAM_PROTOCOL_ERROR")
            if kind == "response.completed":
                for item in response.get("output", []) if isinstance(response.get("output"), list) else []:
                    if isinstance(item, dict) and isinstance(item.get("id"), str):
                        item_ids.add(item["id"])
                terminal = True
                if index != len(events) - 1:
                    _fail("UPSTREAM_PROTOCOL_ERROR")
        elif kind in ("response.output_text.delta", "response.output_text.done",
                      "response.reasoning_summary_text.delta", "response.reasoning_summary_text.done"):
            if response_id is None or _response_id(event.get("response_id")) != response_id:
                _fail("IDENTITY_UNVERIFIED")
            field = "delta" if kind.endswith(".delta") else "text"
            if not isinstance(event.get(field), str):
                _fail("UPSTREAM_PROTOCOL_ERROR")
            item_id = event.get("item_id")
            if item_id is not None:
                if not isinstance(item_id, str) or not item_id:
                    _fail("UPSTREAM_PROTOCOL_ERROR")
                item_ids.add(item_id)
        elif kind in ("response.output_item.added", "response.output_item.done"):
            if response_id is None or _response_id(event.get("response_id")) != response_id:
                _fail("IDENTITY_UNVERIFIED")
            item = event.get("item")
            if type(item) is not dict or item.get("type") not in ("reasoning", "message"):
                _fail("TOOL_POLICY_VIOLATION")
            if not isinstance(item.get('id'), str) or not item['id']:
                _fail('IDENTITY_UNVERIFIED')
            if item['type'] == 'reasoning':
                _validate_reasoning_fields(item)
            if item.get("type") == "message" and item.get("role") != "assistant":
                _fail("TOOL_POLICY_VIOLATION")
        elif kind in ("response.content_part.added", "response.content_part.done"):
            if response_id is None or _response_id(event.get("response_id")) != response_id:
                _fail("IDENTITY_UNVERIFIED")
            part = event.get("part")
            if type(part) is not dict or part.get("type") != "output_text":
                _fail("TOOL_POLICY_VIOLATION")
        else:
            _fail("UPSTREAM_PROTOCOL_ERROR")
    if not terminal or response_id is None:
        _fail("IDENTITY_UNVERIFIED")
    result = _validate_response_object(task, events[-1]["response"], request_id, response_id)
    _validate_sse_output(events, events[-1]['response']['output'])
    if item_ids:
        valid_item_ids = {
            item.get("id") for item in events[-1]["response"].get("output", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if not item_ids.issubset(valid_item_ids):
            _fail("IDENTITY_UNVERIFIED")
    return result


def validate_codex_image_response(task: dict, headers: dict, data: bytes) -> dict:
    """Require a complete authenticated response bound to this sealed task."""
    contract = ImageTaskContract.from_dict(task).to_dict()
    if contract["backend"] != "codex" or contract["profile"] not in ("api-bounded", "subscription-bounded"):
        _fail("IMAGE_ROUTE_MISMATCH")
    if not isinstance(headers, dict) or not isinstance(data, bytes):
        _fail("UPSTREAM_PROTOCOL_ERROR")
    lowered = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            _fail("UPSTREAM_PROTOCOL_ERROR")
        key = name.lower()
        if key in lowered:
            _fail("IDENTITY_UNVERIFIED")
        lowered[key] = value
    request_id = lowered.get("x-request-id") or lowered.get("request-id")
    if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
        _fail("IDENTITY_UNVERIFIED")
    if ("x-request-id" in lowered and "request-id" in lowered
            and lowered["x-request-id"] != lowered["request-id"]):
        _fail("IDENTITY_UNVERIFIED")
    if len(data) > contract["budgets"]["output_bytes"]:
        _fail("UPSTREAM_OUTPUT_LIMIT")
    content_type = lowered.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type == "application/json":
        response = strict_json(data)
        return _validate_response_object(contract, response, request_id)
    if content_type == "text/event-stream":
        return _sse_response(contract, data, request_id)
    _fail("UPSTREAM_PROTOCOL_ERROR")
