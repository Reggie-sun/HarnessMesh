"""Strict MiniMax Responses projection and completed-response validation."""

import base64
import binascii
import re

from .adapters.image_claude import visible_text
from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .image_contract import ImageTaskContract, _validate_png_bytes


WIRE_VERSION = "minimax-image-responses/v1"
MAX_MINIMAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_MINIMAX_IMAGE_TOKENS = 2048
_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}", re.ASCII)
_OPAQUE_ID = re.compile(r"[!-~]{1,256}", re.ASCII)
_REQUEST_FIELDS = {
    "model",
    "instructions",
    "input",
    "tools",
    "tool_choice",
    "stream",
    "store",
    "max_output_tokens",
}


def _fail(code="IMAGE_PROJECTION_MISMATCH"):
    raise RouterError(code)


def _validate_minimax_request(task, body):
    if type(body) is not dict or set(body) != _REQUEST_FIELDS:
        _fail()
    if (
        task["backend"] != "minimax"
        or task["model"] != "MiniMax-M3"
        or task["profile"] != "responses-bounded"
        or task["effort"] != "provider-default"
        or task["output_protocol"] != "JSON_OBJECT/v1"
    ):
        _fail("IMAGE_ROUTE_MISMATCH")
    cap = task["budgets"]["generation_tokens"]
    if cap > MAX_MINIMAX_IMAGE_TOKENS:
        _fail("IMAGE_GENERATION_LIMIT")
    if (
        body["model"] != task["model"]
        or body["instructions"] != task["system_text"]
        or type(body["tools"]) is not list
        or body["tools"] != []
        or body["tool_choice"] != "none"
        or body["stream"] is not False
        or body["store"] is not False
        or type(body["max_output_tokens"]) is not int
        or body["max_output_tokens"] != cap
    ):
        _fail("IMAGE_ROUTE_MISMATCH")

    inputs = body["input"]
    if type(inputs) is not list or len(inputs) != 1:
        _fail("IMAGE_CONTEXT_MISMATCH")
    message = inputs[0]
    if (
        type(message) is not dict
        or set(message) != {"role", "content"}
        or message["role"] != "user"
    ):
        _fail("IMAGE_CONTEXT_MISMATCH")
    content = message["content"]
    if type(content) is not list or len(content) != len(task["images"]) + 1:
        _fail("IMAGE_BINDING_MISMATCH")

    visible = visible_text(task)
    first = content[0]
    if type(first) is not dict or set(first) != {"type", "text"} or first != {
        "type": "input_text",
        "text": visible,
    }:
        _fail("IMAGE_CONTEXT_MISMATCH")
    context_bytes = len(body["instructions"].encode("utf-8")) + len(visible.encode("utf-8"))
    if context_bytes > task["budgets"]["context_bytes"]:
        _fail("IMAGE_CONTEXT_LIMIT")

    images = []
    for descriptor, item in zip(task["images"], content[1:], strict=True):
        if (
            descriptor["byte_length"] > MAX_MINIMAX_IMAGE_BYTES
            or type(item) is not dict
            or set(item) != {"type", "image_url", "detail"}
            or item["type"] != "input_image"
            or item["detail"] != "high"
            or not isinstance(item["image_url"], str)
            or not item["image_url"].startswith("data:image/png;base64,")
        ):
            _fail("IMAGE_BINDING_MISMATCH")
        encoded = item["image_url"][len("data:image/png;base64,") :]
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError, binascii.Error):
            _fail("IMAGE_BINDING_MISMATCH")
        if len(raw) > MAX_MINIMAX_IMAGE_BYTES:
            _fail("IMAGE_BINDING_MISMATCH")
        _validate_png_bytes(raw, descriptor)
        images.append(
            {
                key: descriptor[key]
                for key in ("image_id", "byte_length", "sha256", "width", "height")
            }
        )
    return images, visible


def map_minimax_image_request(task: dict, body: dict) -> tuple[bytes, dict]:
    """Validate one fresh user request and preserve its canonical wire bytes."""
    contract = ImageTaskContract.from_dict(task).to_dict()
    images, visible = _validate_minimax_request(contract, body)
    try:
        actual = canonical_bytes(body)
    except (TypeError, ValueError, UnicodeError):
        _fail()
    if len(actual) > contract["budgets"]["payload_bytes"]:
        _fail("IMAGE_PAYLOAD_LIMIT")
    proof = {
        "version": WIRE_VERSION,
        "images": images,
        "native_request_sha256": hash_bytes(actual),
        "actual_request_sha256": hash_bytes(actual),
        "system_sha256": hash_bytes(contract["system_text"].encode("utf-8")),
        "visible_text_sha256": hash_bytes(visible.encode("utf-8")),
        "generation_tokens": contract["budgets"]["generation_tokens"],
    }
    return actual, proof


def _headers(headers):
    if type(headers) is not dict:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    lowered = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            _fail("UPSTREAM_PROTOCOL_ERROR")
        key = name.lower()
        if key in lowered:
            _fail("IDENTITY_UNVERIFIED")
        lowered[key] = value
    request_ids = [lowered[name] for name in ("x-request-id", "request-id") if name in lowered]
    if (
        not request_ids
        or len(set(request_ids)) != 1
        or not _REQUEST_ID.fullmatch(request_ids[0])
    ):
        _fail("IDENTITY_UNVERIFIED")
    content_type = lowered.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        _fail("UPSTREAM_PROTOCOL_ERROR")
    return request_ids[0]


def _opaque_id(value):
    return isinstance(value, str) and _OPAQUE_ID.fullmatch(value) is not None


def _validate_reasoning(item):
    if set(item) - {"id", "type", "summary", "content"}:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    summary = item.get("summary")
    content = item.get("content", [])
    if type(summary) is not list or type(content) is not list:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    for part, kind in [(part, "summary_text") for part in summary] + [
        (part, "reasoning_text") for part in content
    ]:
        if (
            type(part) is not dict
            or set(part) != {"type", "text"}
            or part["type"] != kind
            or not isinstance(part["text"], str)
        ):
            _fail("UPSTREAM_PROTOCOL_ERROR")


def _validate_message(item):
    if (
        set(item) != {"id", "type", "role", "status", "content"}
        or item["role"] != "assistant"
        or item["status"] != "completed"
        or type(item["content"]) is not list
        or not item["content"]
    ):
        _fail("TOOL_POLICY_VIOLATION")
    parts = []
    for part in item["content"]:
        if (
            type(part) is not dict
            or set(part) not in ({"type", "text"}, {"type", "text", "annotations"})
            or part["type"] != "output_text"
            or not isinstance(part["text"], str)
            or ("annotations" in part and part["annotations"] != [])
        ):
            _fail("TOOL_POLICY_VIOLATION")
        parts.append(part["text"])
    return parts


def validate_minimax_image_response(task: dict, headers: dict, data: bytes) -> dict:
    """Validate a complete non-streamed MiniMax response and bind it to its request."""
    contract = ImageTaskContract.from_dict(task).to_dict()
    if (
        contract["backend"] != "minimax"
        or contract["model"] != "MiniMax-M3"
        or contract["profile"] != "responses-bounded"
        or contract["effort"] != "provider-default"
    ):
        _fail("IMAGE_ROUTE_MISMATCH")
    if type(data) is not bytes:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    if len(data) > contract["budgets"]["output_bytes"]:
        _fail("UPSTREAM_OUTPUT_LIMIT")
    request_id = _headers(headers)
    try:
        data.decode("utf-8", "strict")
    except UnicodeDecodeError:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    response = strict_json(data)
    if type(response) is not dict:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    response_id = response.get("id")
    if not _opaque_id(response_id):
        _fail("IDENTITY_UNVERIFIED")
    if response.get("request_id") is not None and response["request_id"] != request_id:
        _fail("IDENTITY_UNVERIFIED")
    if (
        response.get("object") != "response"
        or response.get("status") != "completed"
        or response.get("model") != contract["model"]
        or response.get("store") is not False
        or response.get("error") is not None
        or response.get("incomplete_details") is not None
    ):
        _fail("IDENTITY_UNVERIFIED")
    cap = contract["budgets"]["generation_tokens"]
    echoed_cap = response.get("max_output_tokens")
    if "max_output_tokens" in response and (type(echoed_cap) is not int or echoed_cap != cap):
        _fail("IMAGE_GENERATION_LIMIT")

    usage = response.get("usage")
    if type(usage) is not dict:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if (
        type(input_tokens) is not int
        or input_tokens < 0
        or type(output_tokens) is not int
        or output_tokens < 0
        or output_tokens > cap
    ):
        _fail("IMAGE_GENERATION_LIMIT")

    output = response.get("output")
    if type(output) is not list or not output:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    text_parts = []
    for item in output:
        if type(item) is not dict or not _opaque_id(item.get("id")):
            _fail("IDENTITY_UNVERIFIED")
        if item.get("type") == "reasoning":
            _validate_reasoning(item)
        elif item.get("type") == "message":
            text_parts.extend(_validate_message(item))
        else:
            _fail("TOOL_POLICY_VIOLATION")
    text = "".join(text_parts)
    if not text or len(text.encode("utf-8")) > contract["budgets"]["output_bytes"]:
        _fail("UPSTREAM_OUTPUT_LIMIT")
    if "output_text" in response and response["output_text"] != text:
        _fail("UPSTREAM_PROTOCOL_ERROR")
    return {
        "text": text,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "request_id": request_id,
        "response_id": response_id,
        "model": contract["model"],
        "max_output_tokens": echoed_cap if "max_output_tokens" in response else None,
    }
