import base64
from copy import deepcopy
import uuid

import pytest

from agent_subagent_router.contracts import RouterError, hash_bytes, canonical_bytes
from agent_subagent_router.image_wire import (
    validate_claude_image_request,
    environment_text,
    CLAUDE_NATIVE_IDENTITY,
)
from agent_subagent_router.adapters.image_claude import visible_text


def request_fixture():
    images = [b"first", b"middle", b"last", b"first"]
    task = {
        "model": "k3-256k",
        "effort": "high",
        "system_text": "Exact frozen system.",
        "task_text": "Review images.",
        "metadata": {"packet": 1},
        "images": [
            {
                "image_id": str(i),
                "sha256": hash_bytes(data),
                "byte_length": len(data),
                "width": 20,
                "height": 20,
            }
            for i, data in enumerate(images)
        ],
        "budgets": {"generation_tokens": 2048, "payload_bytes": 100000},
    }
    framing = {"day": "2026-09-28", "os_release": "7.0.0-34-generic"}
    body = {
        "model": "k3-256k",
        "output_config": {"effort": "high"},
        "tools": [],
        "thinking": {"type": "adaptive"},
        "max_tokens": 2048,
        "stream": True,
        "context_management": {"edits": [{"keep": "all", "type": "clear_thinking_20251015"}]},
        "system": [
            {
                "type": "text",
                "text": "x-anthropic-billing-header: cc_version=2.1.277.1be; cc_entrypoint=sdk-cli;",
            },
            {
                "type": "text",
                "text": CLAUDE_NATIVE_IDENTITY,
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": task["system_text"], "cache_control": {"type": "ephemeral"}},
        ],
        "metadata": {
            "user_id": canonical_bytes(
                {"device_id": "a" * 64, "account_uuid": "", "session_id": str(uuid.uuid4())}
            ).decode()
        },
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": visible_text(task)}]
                + [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(data).decode(),
                        },
                    }
                    for data in images
                ],
            },
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": environment_text(task, framing),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
        ],
    }
    return task, framing, body


def test_ordered_bytes_identity_and_duplicates_are_bound():
    task, framing, body = request_fixture()
    proof = validate_claude_image_request(task, body, framing)
    assert [x["image_id"] for x in proof["images"]] == ["0", "1", "2", "3"]
    assert proof["images"][0]["sha256"] == proof["images"][3]["sha256"]


@pytest.mark.parametrize(
    "attack",
    [
        "model",
        "tools",
        "effort",
        "generation",
        "system",
        "extra",
        "text",
        "first",
        "middle",
        "last",
        "reorder",
        "extra_image",
        "resize",
        "prior_context",
        "framing",
        "metadata",
        "base64",
        "payload",
    ],
)
def test_unsealed_image_requests_fail_before_wire(attack):
    task, framing, body = request_fixture()
    if attack == "model":
        body["model"] = "foreign"
    elif attack == "tools":
        body["tools"] = [{"name": "Read"}]
    elif attack == "effort":
        body["output_config"]["effort"] = "low"
    elif attack == "generation":
        body["max_tokens"] += 1
    elif attack == "system":
        body["system"][2]["text"] += "truth"
    elif attack == "extra":
        body["extra"] = "truth"
    elif attack == "text":
        body["messages"][0]["content"][0]["text"] += "truth"
    elif attack in ("first", "middle", "last"):
        body["messages"][0]["content"].pop({"first": 1, "middle": 2, "last": 3}[attack])
    elif attack == "reorder":
        body["messages"][0]["content"][1:3] = list(reversed(body["messages"][0]["content"][1:3]))
    elif attack == "extra_image":
        body["messages"][0]["content"].append(deepcopy(body["messages"][0]["content"][1]))
    elif attack == "resize":
        body["messages"][0]["content"][1]["source"]["data"] = base64.b64encode(b"changed").decode()
    elif attack == "prior_context":
        body["messages"].insert(0, {"role": "assistant", "content": "peer result"})
    elif attack == "framing":
        body["messages"][1]["content"][0]["text"] += "secret"
    elif attack == "metadata":
        body["metadata"]["user_id"] = '{"account_uuid":"secret"}'
    elif attack == "base64":
        body["messages"][0]["content"][1]["source"]["data"] = "invalid!"
    elif attack == "payload":
        task["budgets"]["payload_bytes"] = 10
    with pytest.raises(RouterError):
        validate_claude_image_request(task, body, framing)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"max_output_tokens": None},
        {"max_output_tokens": False},
        {"max_output_tokens": 2049},
        {"max_output_tokens": 0},
    ],
)
def test_missing_or_invalid_actual_generation_cap_cannot_be_local_config_proof(body):
    from agent_subagent_router.image_wire import require_native_generation_bound

    with pytest.raises(RouterError, match="IMAGE_GENERATION_BOUND_UNPROVEN"):
        require_native_generation_bound(body, 2048)


def test_actual_native_generation_cap_is_bounded():
    from agent_subagent_router.image_wire import require_native_generation_bound

    assert require_native_generation_bound({"max_output_tokens": 2048}, 2048) == 2048
