"""Exact native projection guard before any authenticated image request."""

import base64
import binascii
import re
import uuid

from .adapters.image_claude import visible_text
from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json


WIRE_VERSION = "claude-image-wire/v1"
CLAUDE_NATIVE_IDENTITY = "You are a Claude agent, built on Anthropic's Claude Agent SDK."


def environment_text(task, framing):
    # Values must come from the parent-frozen native conformance tuple.
    if set(framing) not in ({"os_release", "day"}, {"os_release", "day", "cwd"}) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", framing["day"]
    ):
        raise RouterError("IMAGE_FRAMING_UNVERIFIED")
    if not re.fullmatch(r"[A-Za-z0-9_.+-]{1,100}", framing["os_release"]):
        raise RouterError("IMAGE_FRAMING_UNVERIFIED")
    cwd = framing.get('cwd', '/work')
    if cwd not in ('/work', '/home/worker'):
        raise RouterError('IMAGE_FRAMING_UNVERIFIED')
    return (
        "# Environment\nYou have been invoked in the following environment: \n"
        f" - Primary working directory: {cwd}\n - Is a git repository: false\n"
        " - Platform: linux\n - Shell: unknown\n"
        f" - OS Version: Linux {framing['os_release']}\n\n"
        f"You are powered by the model {task['model']}.\n\n"
        "<total_tokens>15000000 tokens left</total_tokens>\n\n"
        f"Today's date is {framing['day']}."
    )


def validate_claude_image_request(task: dict, body: dict, framing: dict) -> dict:
    allowed = {
        "model",
        "system",
        "messages",
        "tools",
        "metadata",
        "max_tokens",
        "stream",
        "thinking",
        "output_config",
        "context_management",
    }
    if not isinstance(body, dict) or set(body) != allowed:
        raise RouterError("IMAGE_PROJECTION_MISMATCH")
    wire_model = "k3" if task["model"] == "k3[1m]" else task["model"]
    if (
        body["model"] != wire_model
        or body["output_config"] != {"effort": task["effort"]}
        or body["thinking"] != {"type": "adaptive"}
        or body["tools"] != []
        or body["stream"] is not True
    ):
        raise RouterError("IMAGE_ROUTE_MISMATCH")
    if (
        type(body["max_tokens"]) is not int
        or body["max_tokens"] != task["budgets"]["generation_tokens"]
    ):
        raise RouterError("IMAGE_GENERATION_MISMATCH")
    if body["context_management"] != {
        "edits": [{"keep": "all", "type": "clear_thinking_20251015"}]
    }:
        raise RouterError("IMAGE_PROJECTION_MISMATCH")
    system = body["system"]
    if (
        not isinstance(system, list)
        or len(system) != 3
        or not isinstance(system[0], dict)
        or set(system[0]) != {"type", "text"}
        or system[0]["type"] != "text"
        or not isinstance(system[0]["text"], str)
        or not re.fullmatch(
            r"x-anthropic-billing-header: cc_version=2\.1\.277\.[0-9a-f]{3}; cc_entrypoint=sdk-cli;",
            system[0]["text"],
        )
        or system[1]
        != {"type": "text", "text": CLAUDE_NATIVE_IDENTITY, "cache_control": {"type": "ephemeral"}}
        or system[2]
        != {"type": "text", "text": task["system_text"], "cache_control": {"type": "ephemeral"}}
    ):
        raise RouterError("IMAGE_SYSTEM_MISMATCH")
    metadata = body["metadata"]
    if not isinstance(metadata, dict) or set(metadata) != {"user_id"}:
        raise RouterError("IMAGE_METADATA_MISMATCH")
    if not isinstance(metadata["user_id"], str):
        raise RouterError("IMAGE_METADATA_MISMATCH")
    identity = strict_json(metadata["user_id"])
    if (
        not isinstance(identity, dict)
        or set(identity) != {"device_id", "account_uuid", "session_id"}
        or identity["account_uuid"] != ""
        or not isinstance(identity["device_id"], str)
        or not re.fullmatch("[0-9a-f]{64}", identity["device_id"])
    ):
        raise RouterError("IMAGE_METADATA_MISMATCH")
    try:
        if str(uuid.UUID(identity["session_id"])) != identity["session_id"]:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise RouterError("IMAGE_METADATA_MISMATCH") from None
    messages = body["messages"]
    if (
        not isinstance(messages, list)
        or len(messages) != 2
        or messages[1]
        != {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": environment_text(task, framing),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
        or not isinstance(messages[0], dict)
        or set(messages[0]) != {"role", "content"}
        or messages[0]["role"] != "user"
        or not isinstance(messages[0]["content"], list)
    ):
        raise RouterError("IMAGE_CONTEXT_MISMATCH")
    content = messages[0]["content"]
    if len(content) != len(task["images"]) + 1 or content[0] != {
        "type": "text",
        "text": visible_text(task),
    }:
        raise RouterError("IMAGE_BINDING_MISMATCH")
    observations = []
    for descriptor, item in zip(task["images"], content[1:], strict=True):
        if (
            not isinstance(item, dict)
            or set(item) != {"type", "source"}
            or item["type"] != "image"
            or not isinstance(item["source"], dict)
            or set(item["source"]) != {"type", "media_type", "data"}
            or item["source"]["type"] != "base64"
            or item["source"]["media_type"] != "image/png"
        ):
            raise RouterError("IMAGE_BINDING_MISMATCH")
        try:
            data = base64.b64decode(item["source"]["data"], validate=True)
        except (ValueError, TypeError, binascii.Error):
            raise RouterError("IMAGE_BINDING_MISMATCH") from None
        if len(data) != descriptor["byte_length"] or hash_bytes(data) != descriptor["sha256"]:
            raise RouterError("IMAGE_BINDING_MISMATCH")
        observations.append(
            {
                key: descriptor[key]
                for key in ("image_id", "byte_length", "sha256", "width", "height")
            }
        )
    if len(canonical_bytes(body)) > task["budgets"]["payload_bytes"]:
        raise RouterError("IMAGE_PAYLOAD_LIMIT")
    return {
        "version": WIRE_VERSION,
        "images": observations,
        "session_id": identity["session_id"],
        "system_sha256": hash_bytes(canonical_bytes(system)),
        "task_sha256": hash_bytes(visible_text(task).encode()),
        "native_request_sha256": hash_bytes(canonical_bytes(body)),
    }


def require_native_generation_bound(body: dict, maximum: int) -> int:
    """A local config value or response-time check cannot prove a sending bound."""
    cap = body.get("max_output_tokens")
    if type(cap) is not int or not 0 < cap <= maximum:
        raise RouterError("IMAGE_GENERATION_BOUND_UNPROVEN")
    return cap


def _validate_semantic_block(block):
    if not isinstance(block, dict):
        raise RouterError('UPSTREAM_PROTOCOL_ERROR')
    fields = {'text': ('text',), 'thinking': ('thinking',), 'redacted_thinking': ('data',)}
    required = fields.get(block.get('type'))
    if required is None or any(not isinstance(block.get(field), str) for field in required):
        raise RouterError('UPSTREAM_PROTOCOL_ERROR')
    if block['type'] == 'thinking' and 'signature' in block and not isinstance(block['signature'], str):
        raise RouterError('UPSTREAM_PROTOCOL_ERROR')


def validate_claude_image_response(task, headers, raw):
    from .backends.kimi import profile
    from .transport.identity import validate_response
    proof = validate_response(profile(task['profile']), headers, raw, allow_tools=False)
    events = []
    if 'text/event-stream' in headers.get('content-type', ''):
        for block in raw.replace(b'\r\n', b'\n').split(b'\n\n'):
            data = b'\n'.join(line[5:].lstrip() for line in block.splitlines() if line.startswith(b'data:'))
            if data:
                events.append(strict_json(data))
        blocks, closed = {}, set()
        for event in events:
            kind = event.get('type')
            if kind == 'message_start' and event.get('message', {}).get('content') != []:
                raise RouterError('UPSTREAM_PROTOCOL_ERROR')
            if kind in ('content_block_start', 'content_block_delta', 'content_block_stop'):
                index = event.get('index')
                if type(index) is not int or index < 0:
                    raise RouterError('UPSTREAM_PROTOCOL_ERROR')
                if kind == 'content_block_start':
                    block = event.get('content_block', {})
                    _validate_semantic_block(block)
                    if index != len(blocks):
                        raise RouterError('UPSTREAM_PROTOCOL_ERROR')
                    blocks[index] = block['type']
                elif index not in blocks or index in closed:
                    raise RouterError('UPSTREAM_PROTOCOL_ERROR')
                elif kind == 'content_block_stop':
                    closed.add(index)
                else:
                    delta = event.get('delta', {})
                    fields = {'text_delta': ('text', 'text'), 'thinking_delta': ('thinking', 'thinking'),
                              'signature_delta': ('thinking', 'signature')}
                    expected = fields.get(delta.get('type'))
                    if expected is None or blocks[index] != expected[0] or not isinstance(delta.get(expected[1]), str):
                        raise RouterError('UPSTREAM_PROTOCOL_ERROR')
        if not events or events[-1].get('type') != 'message_stop' or closed != set(blocks):
            raise RouterError('UPSTREAM_PROTOCOL_ERROR')
        deltas = [x.get('delta', {}) for x in events if x.get('type') == 'message_delta']
        reason = next((x.get('stop_reason') for x in reversed(deltas) if x.get('stop_reason')), None)
    else:
        message = strict_json(raw)
        if not isinstance(message.get('content'), list):
            raise RouterError('UPSTREAM_PROTOCOL_ERROR')
        for block in message['content']:
            _validate_semantic_block(block)
        reason = message.get('stop_reason')
    if (reason != 'end_turn' or not {'input_tokens', 'output_tokens'}.issubset(proof['usage'])
            or proof['usage']['output_tokens'] > task['budgets']['generation_tokens']):
        raise RouterError('IMAGE_COMPLETION_UNPROVEN')
    return proof | {'stop_reason': reason}
