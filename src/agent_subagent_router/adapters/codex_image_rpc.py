"""Baked bounded native RPC diagnostic; synthetic upstream only, no credentials."""

import http.server
import json
import os
import queue
import base64
import subprocess
import sys
import threading
import time


DISABLED_FEATURES = (
    "default_mode_request_user_input",
    "shell_tool",
    "unified_exec",
    "shell_snapshot",
    "web_search_cached",
    "web_search_request",
    "multi_agent",
    "multi_agent_v2",
    "apps",
    "skill_search",
    "skill_mcp_dependency_install",
    "code_mode",
    "code_mode_only",
    "code_mode_host",
    "current_time_reminder",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "computer_use",
    "in_app_browser",
    "image_generation",
    "view_image",
    "sleep_tool",
    "goals",
    "plugins",
    "remote_plugin",
    "workspace_dependencies",
    "request_permissions_tool",
    "tool_suggest",
    "tool_call_mcp_elicitation",
    "enable_request_compression",
    "unbounded_connection_retries",
)


def main():
    task = json.load(sys.stdin)
    if set(task) != {"model", "effort", "system_text", "task_text", "png_b64", "wall_seconds"}:
        raise ValueError("invalid diagnostic task")
    pngs = task["png_b64"]
    if not isinstance(pngs, list) or not 1 <= len(pngs) <= 8:
        raise ValueError("diagnostic PNG count must be 1..8")
    for png in pngs:
        raw = base64.b64decode(png, validate=True)
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) > 1024 * 1024:
            raise ValueError("invalid diagnostic PNG")
    if type(task["wall_seconds"]) not in (int, float) or not 0 < task["wall_seconds"] <= 30:
        raise ValueError("invalid diagnostic deadline")
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(min(int(self.headers.get("Content-Length", "0")), 1024 * 1024))
            seen.append({"path": self.path, "request": json.loads(raw)})
            data = b'{"error":{"message":"Synthetic diagnostic terminal; no upstream call"}}'
            self.send_response(403)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 18765), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    argv = ["/opt/runtime/codex", "app-server", "--enable", "skip_host_skill_discovery"]
    for feature in DISABLED_FEATURES:
        argv.extend(["--disable", feature])
    for key, value in {
        "model_provider": '"sealed_image"',
        "model": '"' + task["model"] + '"',
        "model_providers.sealed_image.name": '"sealed_image"',
        "model_providers.sealed_image.base_url": '"http://127.0.0.1:18765/v1"',
        "model_providers.sealed_image.env_key": '"IMAGE_DIAGNOSTIC_CAPABILITY"',
        "model_providers.sealed_image.wire_api": '"responses"',
        "model_providers.sealed_image.request_max_retries": "0",
        "model_providers.sealed_image.stream_max_retries": "0",
        "orchestrator.skills.enabled": "false",
        "orchestrator.mcp.enabled": "false",
        "agents.enabled": "false",
        "skills.include_instructions": "false",
        "include_environment_context": "false",
        "include_permissions_instructions": "false",
        "include_apps_instructions": "false",
        "include_collaboration_mode_instructions": "false",
        "model_max_output_tokens": "2048",
        "tools.experimental_request_user_input.enabled": "false",
        "tools.update_plan.enabled": "false",
        "web_search": '"disabled"',
        "approval_policy": '"never"',
        "sandbox_mode": '"read-only"',
        "project_doc_max_bytes": "0",
        "mcp_servers": "{}",
        "shell_environment_policy.inherit": '"none"',
        "suppress_unstable_features_warning": "true",
    }.items():
        argv.extend(["-c", key + "=" + value])
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/worker",
        "CODEX_HOME": "/home/worker/codex",
        "TMPDIR": "/tmp",
        "LANG": "C.UTF-8",
        "IMAGE_DIAGNOSTIC_CAPABILITY": "SYNTHETIC-NONCREDENTIAL",
    }
    os.makedirs(env["CODEX_HOME"], mode=0o700, exist_ok=False)
    process = subprocess.Popen(
        argv, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    lines = queue.Queue()
    errors = []

    def read(stream, target):
        for line in stream:
            target(line)

    threading.Thread(
        target=read, args=(process.stdout, lambda x: lines.put(json.loads(x))), daemon=True
    ).start()
    threading.Thread(
        target=read,
        args=(process.stderr, lambda x: errors.append(x.decode(errors="replace"))),
        daemon=True,
    ).start()
    deadline = time.monotonic() + task["wall_seconds"]
    observations = []

    def send(i, method, params=None):
        msg = {"method": method}
        if i is not None:
            msg["id"] = i
        if params is not None:
            msg["params"] = params
        process.stdin.write(json.dumps(msg).encode() + b"\n")
        process.stdin.flush()

    def response(i):
        while time.monotonic() < deadline:
            item = lines.get(timeout=max(0.01, deadline - time.monotonic()))
            observations.append(item)
            if item.get("id") == i:
                return item

    diagnostic_error = None
    try:
        send(
            1,
            "initialize",
            {
                "clientInfo": {"name": "sealed_image_probe", "version": "1"},
                "capabilities": {"experimentalApi": True},
            },
        )
        response(1)
        send(None, "initialized")
        send(4, "config/read", {"includeLayers": False})
        response(4)
        send(
            2,
            "thread/start",
            {
                "model": task["model"],
                "modelProvider": "sealed_image",
                "cwd": "/home/worker",
                "ephemeral": True,
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "environments": [],
                "baseInstructions": task["system_text"],
                "developerInstructions": "",
                "dynamicTools": [],
                "runtimeWorkspaceRoots": [],
                "selectedCapabilityRoots": [],
            },
        )
        started = response(2)
        if "result" in started:
            thread_id = started["result"]["thread"]["id"]
            send(
                3,
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": [
                        {"type": "text", "text": task["task_text"]},
                    ]
                    + [{"type": "image", "url": "data:image/png;base64," + png} for png in pngs],
                    "environments": [],
                    "approvalPolicy": "never",
                    "effort": task["effort"],
                    "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
                },
            )
            response(3)
            while time.monotonic() < deadline and not seen:
                try:
                    observations.append(lines.get(timeout=0.1))
                except queue.Empty:
                    pass
    except (queue.Empty, BrokenPipeError, KeyError, TypeError) as exc:
        diagnostic_error = type(exc).__name__
    finally:
        process.terminate()
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=2)
        server.shutdown()
        server.server_close()
    print(
        json.dumps(
            {
                "purpose": "OFFLINE_NATIVE_DIAGNOSTIC_ONLY",
                "requests": seen,
                "diagnostic_error": diagnostic_error,
                "rpc": observations,
                "stderr": errors,
                "real_upstream_requests": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
