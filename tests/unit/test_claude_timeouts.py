from agent_subagent_router.adapters.claude import Runtime, build_invocation
from agent_subagent_router.adapters.project_claude import project_command
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import Budgets


def test_kimi_request_timeouts_follow_task_budgets(tmp_path, monkeypatch):
    monkeypatch.setattr(Runtime, 'verify', lambda self: None)
    budgets = Budgets(wall_seconds=1200, idle_seconds=900, request_limit=4,
                      output_bytes=1000000, context_bytes=8000000)

    invocation = build_invocation(
        Runtime('/unused/claude', 'test', '0' * 64), profile('deep'),
        tmp_path/'runtime', 'http://127.0.0.1:18765', 'capability', b'prompt', budgets)

    assert invocation.env['API_TIMEOUT_MS'] == '1200000'
    assert invocation.env['CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS'] == '900000'
    assert invocation.env['CLAUDE_STREAM_IDLE_TIMEOUT_MS'] == '900000'

    _, project_env = project_command(
        Runtime('/unused/claude', 'test', '0' * 64), profile('deep'),
        tmp_path/'project-runtime', 'capability', budgets)

    assert project_env['API_TIMEOUT_MS'] == '1200000'
    assert project_env['CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS'] == '900000'
    assert project_env['CLAUDE_STREAM_IDLE_TIMEOUT_MS'] == '900000'
