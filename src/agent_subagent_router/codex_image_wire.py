"""Pinned native Codex projection and strict Responses API identity checks."""

import base64
import binascii
import re
import uuid

from .adapters.image_claude import visible_text
from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .image_contract import ImageTaskContract, read_png


WIRE_VERSION = "codex-image-api-cap/v1"
MAX_CODEX_IMAGE_TOKENS = 2048
_NATIVE_FIELDS = {
    "model", "instructions", "input", "tools", "tool_choice", "parallel_tool_calls",
    "reasoning", "store", "stream", "include", "prompt_cache_key", "text",
    "client_metadata",
}
_REQUEST_FIELDS = _NATIVE_FIELDS | {"max_output_tokens"}
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


def _validate_native_request(task, body):
    if type(body) is not dict or set(body) not in (_NATIVE_FIELDS, _REQUEST_FIELDS):
        _fail()
    if task["backend"] != "codex" or task["profile"] != "api-bounded":
        _fail("IMAGE_ROUTE_MISMATCH")
    if (body["model"] != task["model"] or body["instructions"] != task["system_text"]
            or body["tools"] != [] or body["tool_choice"] != "auto"
            or body["parallel_tool_calls"] is not True or body["store"] is not False
            or body["stream"] is not True
            or body["reasoning"] != {"effort": task["effort"]}
            or body["include"] != ["reasoning.encrypted_content"]
            or body["text"] != {"verbosity": "low"}):
        _fail("IMAGE_ROUTE_MISMATCH")
    cap = task["budgets"]["generation_tokens"]
    if cap > MAX_CODEX_IMAGE_TOKENS:
        _fail("IMAGE_GENERATION_LIMIT")
    if "max_output_tokens" in body and (
        type(body["max_output_tokens"]) is not int or body["max_output_tokens"] != cap
    ):
        _fail("IMAGE_GENERATION_MISMATCH")

    input_value = body["input"]
    if type(input_value) is not list or len(input_value) != 1:
        _fail("IMAGE_CONTEXT_MISMATCH")
    message = input_value[0]
    if (type(message) is not dict or set(message) != {"type", "id", "role", "content"}
            or message["type"] != "message" or message["role"] != "user"):
        _fail("IMAGE_CONTEXT_MISMATCH")
    message_match = _MESSAGE_ID.fullmatch(message["id"]) if isinstance(message["id"], str) else None
    if message_match is None:
        _fail("IMAGE_METADATA_MISMATCH")
    _uuid(message_match.group(1), version=7)

    content = message["content"]
    if type(content) is not list or len(content) != len(task["images"]) + 1:
        _fail("IMAGE_BINDING_MISMATCH")
    expected_text = visible_text(task)
    first = content[0]
    if type(first) is not dict or set(first) != {"type", "text"} or first != {
        "type": "input_text", "text": expected_text,
    }:
        _fail("IMAGE_CONTEXT_MISMATCH")
    context_bytes = len(body["instructions"].encode("utf-8")) + len(expected_text.encode("utf-8"))
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
        if (len(data) != descriptor["byte_length"] or hash_bytes(data) != descriptor["sha256"]
                or read_png(descriptor) != data):
            _fail("IMAGE_BINDING_MISMATCH")
        image_proof.append({
            key: descriptor[key]
            for key in ("image_id", "byte_length", "sha256", "width", "height")
        })
    return _image_metadata(task, body), image_proof, message["id"], expected_text


def map_codex_image_request(task: dict, body: dict) -> tuple[bytes, dict]:
    """Validate one pinned native request and mechanically add its sealed hard cap."""
    contract = ImageTaskContract.from_dict(task).to_dict()
    if contract["output_protocol"] != "JSON_OBJECT/v1":
        _fail("IMAGE_ROUTE_MISMATCH")
    identity, images, message_id, visible = _validate_native_request(contract, body)
    try:
        native = canonical_bytes(body)
        mapped = dict(body)
        mapped["max_output_tokens"] = contract["budgets"]["generation_tokens"]
        actual = canonical_bytes(mapped)
    except (TypeError, ValueError, UnicodeError):
        _fail()
    if len(native) > contract["budgets"]["payload_bytes"]:
        _fail("IMAGE_PAYLOAD_LIMIT")
    if len(actual) > contract["budgets"]["payload_bytes"]:
        _fail("IMAGE_PAYLOAD_LIMIT")
    proof = {
        "version": WIRE_VERSION,
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
    return actual, proof


def _response_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"resp_[A-Za-z0-9_-]{1,128}", value):
        _fail("IDENTITY_UNVERIFIED")
    return value


def _validate_response_object(task, response, request_id, response_id=None):
    if type(response) is not dict:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    actual_id = _response_id(response.get("id"))
    if response_id is not None and actual_id != response_id:
        _fail("IDENTITY_UNVERIFIED")
    if response.get("request_id") is not None and response["request_id"] != request_id:
        _fail("IDENTITY_UNVERIFIED")
    if (response.get("status") != "completed" or response.get("model") != task["model"]
            or type(response.get("max_output_tokens")) is not int
            or response["max_output_tokens"] != task["budgets"]["generation_tokens"]):
        _fail("IDENTITY_UNVERIFIED")
    usage = response.get("usage")
    if type(usage) is not dict:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    cap = task["budgets"]["generation_tokens"]
    if (type(input_tokens) is not int or input_tokens < 0 or type(output_tokens) is not int
            or output_tokens < 0 or output_tokens > cap):
        _fail("IMAGE_GENERATION_LIMIT")
    output = response.get("output")
    if type(output) is not list or not output:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    text_parts = []
    for item in output:
        if type(item) is not dict:
            _fail("UPSTREAM_PROTOCOL_ERROR")
        if item.get("type") == "reasoning":
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
        "max_output_tokens": cap,
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
                        or type(response.get("max_output_tokens")) is not int
                        or response.get("status") not in ("queued", "in_progress")):
                    _fail("IDENTITY_UNVERIFIED")
                created = True
            elif kind == "response.in_progress" and response.get("status") != "in_progress":
                _fail("IDENTITY_UNVERIFIED")
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
    if contract["backend"] != "codex" or contract["profile"] != "api-bounded":
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
