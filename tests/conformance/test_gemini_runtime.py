"""Native Gemini CLI containment evidence, enabled only with an explicit image."""

import json
import os
from pathlib import Path

import pytest

from agent_subagent_router.adapters.gemini import GeminiRuntime
from agent_subagent_router.permissions.docker import DockerSandbox
from agent_subagent_router.permissions.gemini_qualification import qualify


pytestmark = pytest.mark.containment


@pytest.mark.skipif(not (os.environ.get('ROUTER_GEMINI_SANDBOX_CONFIG')
                         and os.environ.get('ROUTER_GEMINI_RUNTIME_CONFIG')),
                    reason='requires explicitly built local Gemini containment image and runtime config')
def test_native_gemini_cli_uses_only_synthetic_local_broker_and_sealed_project():
    sandbox_config = json.loads(Path(os.environ['ROUTER_GEMINI_SANDBOX_CONFIG']).read_text())
    runtime_config = json.loads(Path(os.environ['ROUTER_GEMINI_RUNTIME_CONFIG']).read_text())
    runtime = GeminiRuntime(**{key: value for key, value in runtime_config.items() if key != 'sha256'})
    assert runtime.sha256 == runtime_config['sha256'] == sandbox_config['runtime_sha256']
    evidence = qualify(DockerSandbox(sandbox_config['image'], sandbox_config['runtime_sha256']), runtime)
    assert evidence['qualified'] is True
    assert evidence['project_access'] is True
    assert evidence['native_tools'] == 'VERIFIED'
    assert evidence['live_identity'] == 'NOT_EVALUATED'
    assert evidence['proof'] == 'synthetic_adversarial_execution'
    assert evidence['native_event_shape'][-1]['type'] == 'result'
    assert set(evidence['native_denials']) == {
        'read_file', 'run_shell_command', 'write_file', 'spawn_agent', 'mcp__evil__run'}
