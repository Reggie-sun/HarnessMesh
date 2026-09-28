"""Codex request evidence only; this diagnostic cannot issue live qualification."""

import base64
import os
from pathlib import Path

import pytest

from agent_subagent_router.contracts import (
    Budgets,
    RouterError,
    canonical_bytes,
    hash_bytes,
    strict_json,
)
from agent_subagent_router.image_wire import require_native_generation_bound
from agent_subagent_router.permissions.docker import DockerSandbox, _run_docker
from agent_subagent_router.adapters import codex_image_rpc
from test_image_claude import png


@pytest.mark.native
@pytest.mark.containment
def test_codex_images_empty_tools_and_unproven_generation_bound():
    selected = os.environ.get("ROUTER_IMAGE_CODEX_DIAGNOSTIC_CONFIG")
    if not selected:
        pytest.skip("requires explicit local diagnostic image config; no host fallback")
    config = strict_json(Path(selected).read_bytes())
    helper_sha = hash_bytes(Path(codex_image_rpc.__file__).read_bytes())
    assert config["helper_sha256"] == helper_sha
    sandbox = DockerSandbox(config["image"], config["runtime_sha256"])
    sandbox.verify()
    checked = _run_docker(("image", "inspect", sandbox.image), timeout=5)
    assert checked.returncode == 0
    assert (
        strict_json(checked.stdout)[0]["Config"]["Labels"][
            "org.agent-subagent-router.image-helper-sha256"
        ]
        == helper_sha
    )
    images = [png((i * 20, 100, 200)) for i in range(7)]
    images.append(images[0])
    task = {
        "model": "gpt-5.4",
        "effort": "high",
        "system_text": "Return one JSON object.",
        "task_text": "Describe all eight images in order.",
        "png_b64": [base64.b64encode(data).decode() for data in images],
        "wall_seconds": 10,
    }
    result = sandbox.execute(
        ("/usr/local/bin/python3", "/opt/router/codex_image_rpc.py"),
        {"PATH": "/usr/bin:/bin", "HOME": "/home/worker"},
        canonical_bytes(task),
        Budgets(15, 12, 1, 500000, 500000),
        source=None,
    )
    assert result.exit_code == 0 and result.reason == "exited", (result.stdout, result.stderr)
    observed = strict_json(result.stdout)
    assert observed["diagnostic_error"] is None and len(observed["requests"]) == 1
    assert observed["real_upstream_requests"] == 0
    body = observed["requests"][0]["request"]
    assert body["model"] == "gpt-5.4" and body["reasoning"]["effort"] == "high"
    assert body["tools"] == [] and body["instructions"] == task["system_text"]
    assert len(body["input"]) == 1 and body["input"][0]["role"] == "user"
    blocks = body["input"][0]["content"]
    assert blocks[0] == {"type": "input_text", "text": task["task_text"]}
    actual = [
        base64.b64decode(item["image_url"].removeprefix("data:image/png;base64,"), validate=True)
        for item in blocks[1:]
    ]
    assert [hash_bytes(data) for data in actual] == [hash_bytes(data) for data in images]
    assert len(actual) == 8 and actual[0] == actual[7]
    with pytest.raises(RouterError, match="IMAGE_GENERATION_BOUND_UNPROVEN"):
        require_native_generation_bound(body, 2048)
    # Turn termination/successful generation is deliberately not evidenced by this 403 fake.
    assert not any(
        item.get("method") == "turn/completed" and item["params"]["turn"]["status"] == "completed"
        for item in observed["rpc"]
    )
