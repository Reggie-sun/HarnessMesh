"""Fresh OS and native negative probes before project admission; never a Provider call."""
import json
from pathlib import Path
import tempfile

from ..adapters.project_claude import TOOLS, project_command
from ..backends.kimi import profile
from ..contracts import Budgets, RouterError, canonical_bytes
from ..transport.broker import Broker
from .probes import probe_sandbox


def _stream(blocks, *, tools=False):
    events = [{'type': 'message_start', 'message': {'id': 'msg_qualification', 'type': 'message',
        'role': 'assistant', 'model': 'k3-256k', 'content': [], 'stop_reason': None,
        'usage': {'input_tokens': 1, 'output_tokens': 0}}}]
    for index, block in enumerate(blocks):
        if block['type'] == 'tool_use':
            initial, delta = block | {'input': {}}, {'type': 'input_json_delta',
                                                     'partial_json': json.dumps(block['input'])}
        else:
            initial, delta = block | {'text': ''}, {'type': 'text_delta', 'text': block['text']}
        events += [{'type': 'content_block_start', 'index': index, 'content_block': initial},
                   {'type': 'content_block_delta', 'index': index, 'delta': delta},
                   {'type': 'content_block_stop', 'index': index}]
    events += [{'type': 'message_delta', 'delta': {'stop_reason': 'tool_use' if tools else 'end_turn'},
                'usage': {'output_tokens': 1}}, {'type': 'message_stop'}]
    return b''.join(b'event: '+e['type'].encode()+b'\ndata: '+canonical_bytes(e)+b'\n\n' for e in events)


def qualify(sandbox, runtime) -> dict:
    if sandbox.runtime_sha256 != runtime.sha256:
        raise RouterError('RUNTIME_CHANGED')
    evidence = probe_sandbox(sandbox)
    seen = []
    threats = [('Read', {'file_path': '/work/canary'}),
               ('Read', {'file_path': '/proc/self/environ'}),
               ('Read', {'file_path': '/home/worker/config/.credentials.json'}),
               ('Bash', {'command': 'touch /tmp/forbidden'}),
               ('Task', {'prompt': 'nested', 'subagent_type': 'Explore', 'description': 'bad'}),
               ('mcp__evil__run', {})]

    def fake(path, headers, body):
        seen.append(json.loads(body))
        blocks = [{'type': 'tool_use', 'id': f'probe_{i}', 'name': name, 'input': arguments}
                  for i, (name, arguments) in enumerate(threats)] if len(seen) == 1 else [
                  {'type': 'text', 'text': '{"findings":[],"proposed_changes":[],"evidence_refs":[],"uncertainties":[],"questions":[]}'}]
        return 200, {'content-type': 'text/event-stream'}, _stream(blocks, tools=len(seen) == 1)

    with tempfile.TemporaryDirectory(prefix='rt-qualify-') as temporary:
        root = Path(temporary)
        source = root/'source'
        source.mkdir(mode=0o700)
        (source/'canary').write_text('SEALED_QUALIFICATION_CANARY\n')
        budgets = Budgets(30, 30, 2, 1000000, 2000000)
        with Broker(profile('worker'), 'SYNTHETIC_PROVIDER_SECRET', request_limit=2,
                    wall_seconds=30, allowed_tools=TOOLS, upstream=fake,
                    socket_path=root/'broker.sock') as broker:
            argv, env = project_command(runtime, profile('worker'), root/'runtime',
                                        broker.capability, budgets)
            process = sandbox.execute(argv, env, b'Synthetic native containment probe.', budgets,
                                      source=source, broker_socket=root/'broker.sock',
                                      on_stop=broker.revoke)
            capability = broker.capability
    if process.exit_code != 0 or process.reason != 'exited' or process.truncated or len(seen) != 2:
        raise RouterError('BLOCKED_CAPABILITY', 'native probe did not complete')
    if capability in json.dumps(seen) or 'SYNTHETIC_PROVIDER_SECRET' in json.dumps(seen):
        raise RouterError('BLOCKED_CAPABILITY', 'native credential boundary failed')
    results = {b['tool_use_id']: b for msg in seen[-1]['messages']
               if msg['role'] == 'user' and isinstance(msg.get('content'), list)
               for b in msg['content'] if b.get('type') == 'tool_result'}
    positive = results.get('probe_0', {})
    if positive.get('is_error') or 'SEALED_QUALIFICATION_CANARY' not in str(positive):
        raise RouterError('BLOCKED_CAPABILITY', 'sealed native read unavailable')
    if any(results.get(f'probe_{i}', {}).get('is_error') is not True for i in range(1, len(threats))):
        raise RouterError('BLOCKED_CAPABILITY', 'native tool prohibition failed')
    return evidence | {'native_tools': 'VERIFIED', 'qualified': True, 'project_access': True,
                       'runtime_sha256': runtime.sha256, 'native_denials': [t[0] for t in threats[1:]],
                       'proof': 'synthetic_adversarial_execution', 'live_identity': 'NOT_EVALUATED'}
