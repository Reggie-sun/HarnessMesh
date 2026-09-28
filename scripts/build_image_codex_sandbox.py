"""Build a separate pinned Codex diagnostic image from existing local bytes only."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from agent_subagent_router.contracts import RouterError, hash_bytes
from agent_subagent_router.permissions import container_entry
from agent_subagent_router.permissions.docker import _run_docker

CODEX_VERSION = "0.154.0"
CODEX_SHA256 = "3188814c35471432d4123203e0eb38e5bddc60226e3d7ddf0e59e649ea140022"
BASE = "sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-source", type=Path, required=True)
    parser.add_argument("--config-out", type=Path, required=True)
    args = parser.parse_args()
    path = args.runtime_source
    if path.is_symlink() or not path.is_file() or hash_bytes(path.read_bytes()) != CODEX_SHA256:
        raise RouterError("RUNTIME_CHANGED")
    version = subprocess.run(
        [str(path), "--version"],
        capture_output=True,
        timeout=5,
        env={"PATH": "/usr/bin:/bin"},
        check=True,
    )
    if version.stdout.strip() != b"codex-cli 0.154.0":
        raise RouterError("RUNTIME_VERSION_MISMATCH")
    _run_docker(("image", "inspect", BASE), timeout=10).check_returncode()
    entry = Path(container_entry.__file__).read_bytes()
    helper = Path(__file__).parents[1] / "src/agent_subagent_router/adapters/codex_image_rpc.py"
    helper_bytes = helper.read_bytes()
    with tempfile.TemporaryDirectory(prefix="router-image-codex-") as folder:
        root = Path(folder)
        shutil.copyfile(path, root / "codex")
        if hash_bytes((root / "codex").read_bytes()) != CODEX_SHA256:
            raise RouterError("RUNTIME_CHANGED")
        (root / "container_entry.py").write_bytes(entry)
        (root / "codex_image_rpc.py").write_bytes(helper_bytes)
        (root / "Dockerfile").write_text(
            f"FROM python@{BASE}\n"
            "COPY --chmod=0555 codex /opt/runtime/codex\n"
            "COPY --chmod=0555 container_entry.py /opt/router/container_entry.py\n"
            "COPY --chmod=0555 codex_image_rpc.py /opt/router/codex_image_rpc.py\n"
            f'LABEL org.agent-subagent-router.runtime-sha256="{CODEX_SHA256}"\n'
            f'LABEL org.agent-subagent-router.entry-sha256="{hash_bytes(entry)}"\n'
            f'LABEL org.agent-subagent-router.image-helper-sha256="{hash_bytes(helper_bytes)}"\n'
            "USER 1000:1000\nWORKDIR /work\nENTRYPOINT []\nCMD []\n"
        )
        result = _run_docker(
            (
                "build",
                "--network=none",
                "--pull=false",
                "--iidfile",
                str(root / "image-id"),
                str(root),
            ),
            timeout=120,
        )
        result.check_returncode()
        image = (root / "image-id").read_text().strip()
    config = {
        "image": image,
        "runtime_sha256": CODEX_SHA256,
        "runtime_version": CODEX_VERSION,
        "entry_sha256": hash_bytes(entry),
        "helper_sha256": hash_bytes(helper_bytes),
        "base_image": BASE,
        "purpose": "OFFLINE_NATIVE_DIAGNOSTIC_ONLY",
    }
    # An explicit new config never replaces an existing qualified route configuration.
    args.config_out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with args.config_out.open("x") as stream:
        json.dump(config, stream)
    args.config_out.chmod(0o600)
    print(json.dumps(config))


if __name__ == "__main__":
    main()
