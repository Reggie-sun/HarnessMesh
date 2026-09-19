import json
from pathlib import Path
import tempfile

import pytest

from agent_subagent_router.adapters.project_claude import project_command
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import Budgets
from agent_subagent_router.permissions.docker import DockerSandbox
from agent_subagent_router.permissions.qualification import _stream
from agent_subagent_router.runtime_config import installed_runtime
from agent_subagent_router.transport.broker import Broker


def sandbox():
    config = json.loads((Path.home()/'.local/share/agent-subagent-router/sandbox.json').read_text())
    return DockerSandbox(config['image'], config['runtime_sha256'])


@pytest.mark.containment
def test_candidate_domain_cannot_write_immutable_baseline(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    (source/'owned.py').write_text('before\n')
    (source/'other.py').write_text('protected\n')
    candidate = tmp_path/'candidate'
    candidate.mkdir()
    overlay = candidate/'owned.py'
    overlay.write_text('before\n')
    probe = '''from pathlib import Path
p=Path('/work')
Path('/candidate/owned.py').write_text('after\\n')
for name in ('other.py','new.py'):
 try: p.joinpath(name).write_text('escape'); raise AssertionError(name)
 except OSError: pass
print('OVERLAY_ONLY')
'''
    result = sandbox().execute(('/usr/local/bin/python3', '-c', probe), {'PATH': '/usr/bin:/bin'}, b'',
        Budgets(15, 15, 1, 100000, 100000), source=source,
        candidate_directory=candidate)
    assert result.exit_code == 0, result.stderr
    assert overlay.read_text() == 'after\n'
    assert (source/'owned.py').read_text() == 'before\n'
    assert (source/'other.py').read_text() == 'protected\n'
    assert not (source/'new.py').exists()


@pytest.mark.containment
def test_native_edit_only_exact_owned_overlay(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    (source/'owned.py').write_text('VALUE = 1\n')
    (source/'other.py').write_text('VALUE = 1\n')
    candidate = tmp_path/'candidate'
    candidate.mkdir()
    overlay = candidate/'owned.py'
    overlay.write_text('VALUE = 1\n')
    seen = []
    def upstream(path, headers, body):
        seen.append(json.loads(body))
        if len(seen) == 1:
            blocks = [{'type': 'tool_use', 'id': f'read_{i}', 'name': 'Read',
                'input': {'file_path': ('/candidate/' if name == 'owned.py' else '/work/')+name}} for i, name in enumerate(('owned.py', 'other.py'))]
        elif len(seen) == 2:
            blocks = [{'type': 'tool_use', 'id': f'edit_{i}', 'name': 'Edit',
                'input': {'file_path': '/candidate/'+name, 'old_string': 'VALUE = 1',
                          'new_string': 'VALUE = 2'}} for i, name in enumerate(('owned.py', 'other.py'))]
        else:
            blocks = [{'type': 'text', 'text': '{}'}]
        return 200, {'content-type': 'text/event-stream'}, _stream(blocks, tools=len(seen) < 3)
    budget = Budgets(30, 30, 3, 1000000, 2000000)
    with tempfile.TemporaryDirectory(prefix='rt-w-') as folder:
        socket = Path(folder)/'b.sock'
        with Broker(profile('worker'), 'PROVIDER-SECRET', request_limit=3, wall_seconds=30,
                    upstream=upstream, allowed_tools=('Read','Glob','Grep','Edit'), socket_path=socket) as broker:
            argv, env = project_command(installed_runtime(), profile('worker'), tmp_path/'runtime', broker.capability, budget)
            argv = list(argv)
            argv[argv.index('--tools')+1] = 'Read,Glob,Grep,Edit'
            argv += ['Read(//candidate/owned.py)', 'Edit(//candidate/owned.py)']
            result = sandbox().execute(tuple(argv), env, b'Perform the requested bounded edits.', budget,
                source=source, broker_socket=socket, candidate_directory=candidate, on_stop=broker.revoke)
    assert result.exit_code == 0, result.stderr
    assert len(seen) == 3
    responses = [b for m in seen[-1]['messages'] if m['role'] == 'user' and isinstance(m['content'], list)
                 for b in m['content'] if b.get('type') == 'tool_result']
    assert overlay.read_text() == 'VALUE = 2\n', json.dumps(responses)
    assert (source/'owned.py').read_text() == 'VALUE = 1\n'
    assert (source/'other.py').read_text() == 'VALUE = 1\n'
    results = [block for msg in seen[-1]['messages'] if msg['role'] == 'user' and isinstance(msg['content'], list)
               for block in msg['content'] if block.get('tool_use_id') == 'edit_1']
    assert len(results) == 1 and results[0].get('is_error') is True
