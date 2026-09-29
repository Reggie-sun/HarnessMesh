import base64
import copy
import hashlib
import struct
import zlib

import pytest

from agent_subagent_router.adapters.image_claude import visible_text
from agent_subagent_router.contracts import RouterError, canonical_bytes, hash_bytes
from agent_subagent_router.image_contract import ImageTaskContract
from agent_subagent_router.minimax_image_wire import (
    map_minimax_image_request,
    validate_minimax_image_response,
)
from test_codex_image_wire import request_fixture


_REQUEST_ID = "mm-request-18"


def _request(task, pngs):
    content = [{"type": "input_text", "text": visible_text(task)}]
    content.extend(
        {
            "type": "input_image",
            "image_url": "data:image/png;base64," + base64.b64encode(raw).decode("ascii"),
            "detail": "high",
        }
        for raw in pngs
    )
    return {
        "model": task["model"],
        "instructions": task["system_text"],
        "input": [{"role": "user", "content": content}],
        "tools": [],
        "tool_choice": "none",
        "stream": False,
        "store": False,
        "max_output_tokens": task["budgets"]["generation_tokens"],
    }


def _task_and_request(tmp_path):
    task, _, pngs = request_fixture(tmp_path, payload_bytes=32 * 1024 * 1024)
    task.update(
        backend="minimax",
        model="MiniMax-M3",
        profile="responses-bounded",
        effort="provider-default",
    )
    task = ImageTaskContract.from_dict(task).to_dict()
    return task, pngs, _request(task, pngs)


def _response(task, *, response_id="minimax.reply-18"):
    return {
        "id": response_id,
        "object": "response",
        "status": "completed",
        "model": task["model"],
        "store": False,
        "output": [
            {
                "id": "reasoning-1",
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "Check each image."}],
                "content": [{"type": "reasoning_text", "text": "Keep source order."}],
            },
            {
                "id": "message-1",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": '{"same":true}', "annotations": []}
                ],
            },
        ],
        "usage": {"input_tokens": 120, "output_tokens": 24},
    }


def _headers(request_id=_REQUEST_ID):
    return {"content-type": "application/json; charset=utf-8", "x-request-id": request_id}


def test_maps_exact_sealed_request_and_all_full_pngs(tmp_path):
    task, pngs, body = _task_and_request(tmp_path)

    mapped, proof = map_minimax_image_request(task, body)

    assert mapped == canonical_bytes(body)
    assert set(proof) == {
        "version",
        "images",
        "native_request_sha256",
        "actual_request_sha256",
        "system_sha256",
        "visible_text_sha256",
        "generation_tokens",
    }
    assert proof["version"] == "minimax-image-responses/v1"
    assert proof["native_request_sha256"] == hash_bytes(canonical_bytes(body))
    assert proof["actual_request_sha256"] == hash_bytes(mapped)
    assert proof["system_sha256"] == hash_bytes(task["system_text"].encode())
    assert proof["visible_text_sha256"] == hash_bytes(visible_text(task).encode())
    assert proof["generation_tokens"] == 2048
    assert [item["image_id"] for item in proof["images"]] == [
        item["image_id"] for item in task["images"]
    ]
    assert [item["sha256"] for item in proof["images"]] == [
        hashlib.sha256(raw).hexdigest() for raw in pngs
    ]
    assert b"path" not in canonical_bytes(proof)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tools", [{"type": "function", "name": "search"}]),
        ("tool_choice", "auto"),
        ("stream", True),
        ("store", True),
        ("previous_response_id", "old-response"),
    ],
)
def test_rejects_tools_streaming_storage_and_unknown_request_fields(tmp_path, field, value):
    task, pngs, body = _task_and_request(tmp_path)
    body[field] = value

    with pytest.raises(RouterError):
        map_minimax_image_request(task, body)


@pytest.mark.parametrize("change", ["history", "wrong-role", "wrong-text", "wrong-order", "extra-part"])
def test_rejects_history_context_and_image_binding_changes(tmp_path, change):
    task, pngs, body = _task_and_request(tmp_path)
    body = copy.deepcopy(body)
    message = body["input"][0]
    if change == "history":
        body["input"].append(copy.deepcopy(message))
    elif change == "wrong-role":
        message["role"] = "system"
    elif change == "wrong-text":
        message["content"][0]["text"] += " extra"
    elif change == "wrong-order":
        message["content"][1], message["content"][2] = (
            message["content"][2], message["content"][1]
        )
    else:
        message["content"].append({"type": "input_text", "text": "extra"})

    with pytest.raises(RouterError):
        map_minimax_image_request(task, body)


def test_generation_cap_is_sealed_and_limited_to_2048(tmp_path):
    task, pngs, body = _task_and_request(tmp_path)
    task["budgets"]["generation_tokens"] = 2049
    body["max_output_tokens"] = 2049

    with pytest.raises(RouterError):
        map_minimax_image_request(task, body)


def _chunk(kind, payload):
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _png_larger_than(limit):
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    idat = _chunk(b"IDAT", zlib.compress(bytes((0, 1, 2, 3, 255))))
    iend = _chunk(b"IEND", b"")
    payload_size = limit + 1 - len(signature + ihdr + idat + iend) - 12
    raw = signature + ihdr + _chunk(b"tEXt", b"k\0" + b"x" * (payload_size - 2)) + idat + iend
    assert len(raw) == limit + 1
    return raw


def test_rejects_png_over_ten_mib_before_mapping(tmp_path):
    task, pngs, body = _task_and_request(tmp_path)
    raw = _png_larger_than(10 * 1024 * 1024)
    image_path = tmp_path / "large.png"
    image_path.write_bytes(raw)
    descriptor = dict(task["images"][0])
    descriptor.update(
        path=str(image_path),
        byte_length=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
    task["images"] = [descriptor]
    task["budgets"].update(
        max_images=1,
        max_png_bytes=20 * 1024 * 1024,
        payload_bytes=32 * 1024 * 1024,
    )
    task = ImageTaskContract.from_dict(task).to_dict()

    with pytest.raises(RouterError):
        map_minimax_image_request(task, _request(task, [raw]))


def test_validates_completed_response_without_assuming_codex_id_or_cap_echo(tmp_path):
    task, _, _ = _task_and_request(tmp_path)
    response = _response(task)

    result = validate_minimax_image_response(task, _headers(), canonical_bytes(response))

    assert result == {
        "text": '{"same":true}',
        "usage": {"input_tokens": 120, "output_tokens": 24},
        "request_id": _REQUEST_ID,
        "response_id": "minimax.reply-18",
        "model": "MiniMax-M3",
        "max_output_tokens": None,
    }


def test_checks_optional_cap_echo_and_output_text_convenience(tmp_path):
    task, _, _ = _task_and_request(tmp_path)
    response = _response(task)
    response["max_output_tokens"] = 2048
    response["output_text"] = '{"same":true}'

    result = validate_minimax_image_response(task, _headers(), canonical_bytes(response))

    assert result["max_output_tokens"] == 2048
    response["output_text"] = "different"
    with pytest.raises(RouterError):
        validate_minimax_image_response(task, _headers(), canonical_bytes(response))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("object", "message"),
        ("status", "incomplete"),
        ("model", "another-model"),
        ("store", True),
        ("error", {"message": "failed"}),
        ("incomplete_details", {"reason": "max_output_tokens"}),
    ],
)
def test_rejects_nonterminal_or_mismatched_response(tmp_path, field, value):
    task, _, _ = _task_and_request(tmp_path)
    response = _response(task)
    response[field] = value

    with pytest.raises(RouterError):
        validate_minimax_image_response(task, _headers(), canonical_bytes(response))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("input_tokens", True),
        ("input_tokens", -1),
        ("output_tokens", True),
        ("output_tokens", 2049),
    ],
)
def test_rejects_invalid_usage_types_and_generation_over_cap(tmp_path, field, value):
    task, _, _ = _task_and_request(tmp_path)
    response = _response(task)
    response["usage"][field] = value

    with pytest.raises(RouterError):
        validate_minimax_image_response(task, _headers(), canonical_bytes(response))


@pytest.mark.parametrize("change", ["tool", "wrong-role", "incomplete-message", "nontext", "bad-reasoning"])
def test_rejects_tools_nonassistant_messages_and_invalid_reasoning(tmp_path, change):
    task, _, _ = _task_and_request(tmp_path)
    response = _response(task)
    if change == "tool":
        response["output"].append({"id": "call-1", "type": "function_call", "name": "search"})
    elif change == "wrong-role":
        response["output"][1]["role"] = "user"
    elif change == "incomplete-message":
        response["output"][1]["status"] = "in_progress"
    elif change == "nontext":
        response["output"][1]["content"][0] = {"type": "refusal", "refusal": "no"}
    else:
        response["output"][0]["summary"] = [{"type": "function_call", "text": "bad"}]

    with pytest.raises(RouterError):
        validate_minimax_image_response(task, _headers(), canonical_bytes(response))


def test_requires_json_authenticated_safe_request_id_and_strict_json(tmp_path):
    task, _, _ = _task_and_request(tmp_path)
    response = canonical_bytes(_response(task))

    for headers, data in [
        ({"content-type": "text/event-stream", "x-request-id": _REQUEST_ID}, response),
        ({"content-type": "application/json"}, response),
        (_headers("contains space"), response),
        (_headers(), b'{"id":"first","id":"duplicate"}'),
    ]:
        with pytest.raises(RouterError):
            validate_minimax_image_response(task, headers, data)


def test_checks_response_request_identity_and_bounded_ascii_response_id(tmp_path):
    task, _, _ = _task_and_request(tmp_path)
    response = _response(task)
    response["request_id"] = "other-request"
    with pytest.raises(RouterError):
        validate_minimax_image_response(task, _headers(), canonical_bytes(response))

    for identifier in ("", "has space", "réponse", "r" * 257):
        response = _response(task, response_id=identifier)
        with pytest.raises(RouterError):
            validate_minimax_image_response(task, _headers(), canonical_bytes(response))
