"""Native image stdin projection; no project adapter or file tools."""

import base64
from dataclasses import replace
from pathlib import Path

from .claude import build_invocation
from ..contracts import RouterError, canonical_bytes


ADAPTER_VERSION = "claude-image-input/v1"


def visible_text(task: dict) -> str:
    # JSON framing makes image identity/order and anonymous metadata explicit.
    return canonical_bytes(
        {
            "task": task["task_text"],
            "metadata": task["metadata"],
            "image_ids": [item["image_id"] for item in task["images"]],
        }
    ).decode()


def native_input(task: dict, pngs: list[bytes]) -> bytes:
    if len(pngs) != len(task["images"]):
        raise RouterError("IMAGE_BINDING_MISMATCH")
    content = [{"type": "text", "text": visible_text(task)}]
    content.extend(
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(raw).decode("ascii"),
            },
        }
        for raw in pngs
    )
    return (
        canonical_bytes({"type": "user", "message": {"role": "user", "content": content}}) + b"\n"
    )


def build_image_invocation(
    runtime,
    profile,
    directory: Path,
    broker_url: str,
    capability: str,
    task: dict,
    pngs: list[bytes],
    budgets,
):
    if (
        task["backend"] != "kimi"
        or task["model"] != profile.client_model
        or task["profile"] != profile.name
        or task["effort"] != profile.effort
    ):
        raise RouterError("ROUTE_MISMATCH")
    prompt = native_input(task, pngs)
    if len(prompt) > task["budgets"]["payload_bytes"]:
        raise RouterError("IMAGE_PAYLOAD_LIMIT")
    invocation = build_invocation(
        runtime, profile, directory, broker_url, capability, prompt, budgets
    )
    argv = list(invocation.argv)
    # Docker rejects empty argv entries. Equals syntax is native CLI syntax.
    for option in ("--tools", "--setting-sources"):
        index = argv.index(option)
        argv[index : index + 2] = [option + "="]
    argv.extend(["--input-format", "stream-json", "--system-prompt=" + task["system_text"]])
    env = dict(invocation.env)
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(task["budgets"]["generation_tokens"])
    return replace(invocation, argv=tuple(argv), env=env)


def docker_projection(invocation):
    argv = list(invocation.argv)
    argv[0] = "/opt/runtime/claude"
    settings = argv.index("--settings") + 1
    argv[settings] = Path(argv[settings]).read_text()
    env = dict(invocation.env)
    for key, value in [
        ("HOME", "/home/worker"),
        ("TMPDIR", "/tmp"),
        ("CLAUDE_CONFIG_DIR", "/home/worker/config"),
    ]:
        env[key] = value
    return tuple(argv), env
