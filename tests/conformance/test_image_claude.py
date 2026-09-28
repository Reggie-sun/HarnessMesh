"""Actual pinned runtime in source=None Docker against only synthetic upstream."""

import json
import platform
import struct
import zlib
from datetime import datetime, timezone

import pytest

from agent_subagent_router.adapters.image_claude import build_image_invocation, docker_projection
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import Budgets, hash_bytes
from agent_subagent_router.image_output import decode_image_claude
from agent_subagent_router.image_wire import validate_claude_image_request
from agent_subagent_router.runtime_config import installed_runtime, installed_sandbox
from agent_subagent_router.transport.broker import Broker


def png(color):
    def chunk(name, data):
        return (
            struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 32, 32, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + bytes(color) * 32) * 32))
        + chunk(b"IEND", b"")
    )


def stream(model, tool):
    block = (
        {
            "type": "tool_use",
            "id": "tool_fake",
            "name": "Bash",
            "input": {"command": "touch /tmp/escaped"},
        }
        if tool
        else {"type": "text", "text": ""}
    )
    events = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_fake_image",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "usage": {"input_tokens": 10, "output_tokens": 0},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": block},
    ]
    if not tool:
        events.append(
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": '{"frames":[]}'},
            }
        )
    events.extend(
        [
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use" if tool else "end_turn"},
                "usage": {"output_tokens": 5},
            },
            {"type": "message_stop"},
        ]
    )
    return "".join(
        "event: " + item["type"] + "\ndata: " + json.dumps(item) + "\n\n" for item in events
    ).encode()


@pytest.mark.native
@pytest.mark.containment
@pytest.mark.parametrize("route_name", ["worker", "deep"])
@pytest.mark.parametrize("tool_response", [False, True])
def test_image_native_docker_exact_bytes_and_no_tools(tmp_path, route_name, tool_response):
    route = profile(route_name)
    images = [png((i * 20, 100, 200)) for i in range(7)]
    images.append(images[0])
    task = {
        "backend": "kimi",
        "model": route.client_model,
        "profile": route_name,
        "effort": route.effort,
        "system_text": "Return one JSON object describing all supplied images.",
        "task_text": "Describe each image.",
        "metadata": {"packet": 1},
        "images": [
            {
                "image_id": "opaque-" + str(i),
                "sha256": hash_bytes(raw),
                "byte_length": len(raw),
                "width": 32,
                "height": 32,
            }
            for i, raw in enumerate(images)
        ],
        "budgets": {"payload_bytes": 200000, "generation_tokens": 2048},
    }
    framing = {
        "os_release": platform.release(),
        "day": datetime.now(timezone.utc).date().isoformat(),
    }
    seen = []

    def fake(path, headers, body):
        seen.append(json.loads(body))
        return 200, {"content-type": "text/event-stream"}, stream(route.wire_model, tool_response)

    with Broker(
        route,
        "SYNTHETIC-NONCREDENTIAL",
        upstream=fake,
        request_limit=1,
        wall_seconds=20,
        socket_path=tmp_path / "broker.sock",
        generation_tokens=2048,
        request_validator=lambda body: validate_claude_image_request(task, body, framing),
        allow_response_tools=False,
    ) as broker:
        invocation = build_image_invocation(
            installed_runtime(),
            route,
            tmp_path / "runtime",
            "http://127.0.0.1:18765",
            broker.capability,
            task,
            images,
            Budgets(20, 15, 1, 500000, 500000),
        )
        argv, env = docker_projection(invocation)
        result = installed_sandbox().execute(
            argv,
            env,
            invocation.stdin,
            invocation.budgets,
            source=None,
            broker_socket=tmp_path / "broker.sock",
            on_stop=broker.revoke,
        )
    assert len(seen) == 1, (broker.rejections, result.stdout, result.stderr)
    observation = broker.observations[0]
    assert len(observation["input_proof"]["images"]) == 8
    assert [x["image_id"] for x in observation["input_proof"]["images"]] == [
        "opaque-" + str(i) for i in range(8)
    ]
    assert (
        observation["proof"] == "synthetic_upstream"
        if not tool_response
        else observation["classification"] == "TOOL_POLICY_VIOLATION"
    )
    if tool_response:
        assert observation["classification"] == "TOOL_POLICY_VIOLATION"
        assert result.exit_code != 0
    else:
        assert result.exit_code == 0, (result.stdout, result.stderr)
        assert decode_image_claude(result.stdout, 10000) == (b'{"frames":[]}', b'{"frames":[]}')
        init = next(
            json.loads(line)
            for line in result.stdout.splitlines()
            if json.loads(line).get("subtype") == "init"
        )
        assert (
            init["tools"] == []
            and init["skills"] == []
            and init["plugins"] == []
            and init["mcp_servers"] == []
        )
        assert init["session_id"] == observation["input_proof"]["session_id"]
    assert b"/home/reggie" not in json.dumps(seen).encode()
