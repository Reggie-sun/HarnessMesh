import json
import time
from pathlib import Path

import pytest

from agent_subagent_router.adapters.project_claude import TOOLS, project_command
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import Budgets
from agent_subagent_router.permissions.docker import DockerSandbox
from agent_subagent_router.runtime_config import installed_runtime
from agent_subagent_router.transport.broker import Broker
from test_claude import fake_stream


def tool_stream(blocks):
    events = [{'type': 'message_start', 'message': {'id': 'msg_tool', 'type': 'message',
        'role': 'assistant', 'model': 'k3-256k', 'content': [], 'stop_reason': None,
        'usage': {'input_tokens': 2, 'output_tokens': 0}}}]
    for index, block in enumerate(blocks):
        events += [{'type': 'content_block_start', 'index': index, 'content_block': block | {'input': {}}},
                   {'type': 'content_block_delta', 'index': index,
                    'delta': {'type': 'input_json_delta', 'partial_json': json.dumps(block['input'])}},
                   {'type': 'content_block_stop', 'index': index}]
    events += [{'type': 'message_delta', 'delta': {'stop_reason': 'tool_use'},
                'usage': {'output_tokens': 2}}, {'type': 'message_stop'}]
    return ''.join(f'event: {event["type"]}\ndata: {json.dumps(event)}\n\n' for event in events).encode()


@pytest.mark.containment
def test_native_read_scope_and_forbidden_tools(tmp_path):
    config = json.loads((Path.home()/'.local/share/agent-subagent-router/sandbox.json').read_text())
    sandbox = DockerSandbox(config['image'], config['runtime_sha256'])
    source = tmp_path/'source'
    source.mkdir()
    (source/'a.py').write_text('VALUE = 42\n')
    tools = [
        ('Read', {'file_path': '/work/a.py'}),
        ('Read', {'file_path': '/proc/self/environ'}),
        ('Read', {'file_path': '/home/worker/config/.credentials.json'}),
        ('Bash', {'command': 'touch /tmp/forbidden-tool'}),
        ('Task', {'prompt': 'delegate', 'subagent_type': 'Explore', 'description': 'bad'}),
        ('mcp__evil__run', {})]
    seen = []
    def upstream(path, headers, body):
        seen.append(json.loads(body))
        if len(seen) == 1:
            time.sleep(10.1)  # Regression: the relay used to discard valid >10s generations.
        data = tool_stream([{'type': 'tool_use', 'id': f'tool_{i}', 'name': name, 'input': arguments}
                            for i, (name, arguments) in enumerate(tools)]) if len(seen) == 1 else fake_stream('k3-256k')
        return 200, {'content-type': 'text/event-stream'}, data
    budget = Budgets(30, 30, 2, 1000000, 2000000)
    # AF_UNIX paths are bounded by the kernel; use a short private parent-owned directory.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='rt-') as temporary:
        with Broker(profile('worker'), 'REAL-PROVIDER-SENTINEL', request_limit=2,
                    wall_seconds=30, upstream=upstream, allowed_tools=TOOLS,
                    socket_path=Path(temporary)/'b.sock') as broker:
            argv, env = project_command(installed_runtime(), profile('worker'), tmp_path/'runtime',
                                        broker.capability, budget)
            result = sandbox.execute(argv, env, b'Synthetic native permission check.', budget,
                                     source=source, broker_socket=Path(temporary)/'b.sock',
                                     on_stop=broker.revoke)
            capability = broker.capability
    assert result.exit_code == 0, result.stderr
    assert len(seen) == 2
    assert capability not in json.dumps(seen) and 'REAL-PROVIDER-SENTINEL' not in json.dumps(seen)
    results = {block['tool_use_id']: block for msg in seen[1]['messages']
               if msg['role'] == 'user' and isinstance(msg['content'], list)
               for block in msg['content'] if block.get('type') == 'tool_result'}
    assert 'VALUE = 42' in str(results['tool_0']) and not results['tool_0'].get('is_error')
    for index in range(1, len(tools)):
        assert results[f'tool_{index}'].get('is_error') is True, results[f'tool_{index}']


@pytest.mark.containment
def test_sealed_project_invocation_binds_native_read_report_and_receipt(tmp_path):
    from agent_subagent_router.api import inspect_task, run_contract
    from agent_subagent_router.contracts import TaskContract, hash_bytes
    from agent_subagent_router.receipts import ReceiptStore
    from agent_subagent_router.permissions.qualification import _stream
    config = json.loads((Path.home()/'.local/share/agent-subagent-router/sandbox.json').read_text())
    sandbox = DockerSandbox(config['image'], config['runtime_sha256'])
    runtime = installed_runtime()
    source = tmp_path/'project'
    source.mkdir()
    data = b'VALUE = 42\n'
    (source/'a.py').write_bytes(data)
    task = TaskContract.from_dict(dict(parent_session_id='p', task_id='t', cwd=str(source),
        explicit_root=str(source), role='reviewer', goal='Read a.py and report VALUE.',
        read_paths=['a.py'], write_paths=[], permissions=['read'], selected_refs=[],
        active_documents='not_applicable', harness_refs=[], constitution_refs=[], skills=[],
        skill_roots=[], expected_evidence=['a.py'], backend='kimi', profile='worker',
        budgets=dict(wall_seconds=30, idle_seconds=30, request_limit=2,
                     output_bytes=1000000, context_bytes=2000000)))
    sealed = inspect_task(task, tmp_path/'contracts', runtime, sandbox=sandbox)
    report = {'findings': ['VALUE is 42'], 'proposed_changes': [], 'uncertainties': [], 'questions': [],
              'evidence_refs': [{'path': str(source/'a.py'), 'sha256': hash_bytes(data),
                                 'start_line': 1, 'end_line': 1}]}
    calls = []
    def upstream(path, headers, body):
        calls.append(body)
        blocks = [{'type': 'tool_use', 'id': 'read_1', 'name': 'Read',
                   'input': {'file_path': '/work/a.py'}}] if len(calls) == 1 else [
                   {'type': 'text', 'text': json.dumps(report)}]
        return 200, {'content-type': 'text/event-stream'}, _stream(blocks, tools=len(calls) == 1)
    store = ReceiptStore(tmp_path/'runs')
    receipt = run_contract(sealed, 'kimi', 'worker', store, runtime, sandbox=sandbox, upstream=upstream)
    assert receipt['classification'] == 'PARSED', receipt
    assert receipt['wire_requests'] == 2 and receipt['observed_reads'][0]['start_line'] == 1
    assert receipt['parent_acceptance'] == 'NOT_EVALUATED'
    assert store.read(receipt['invocation_id']) == receipt
