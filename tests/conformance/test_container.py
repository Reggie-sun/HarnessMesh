import json
import os

import pytest

from agent_subagent_router.contracts import Budgets
from agent_subagent_router.permissions.docker import DockerSandbox


pytestmark = pytest.mark.containment


@pytest.mark.skipif(not (os.environ.get('ROUTER_SANDBOX_IMAGE')
                         and os.environ.get('ROUTER_SANDBOX_RUNTIME_SHA256')),
                    reason='requires an explicitly built local containment image')
def test_synthetic_container_enforces_filesystem_network_ipc_capability_and_fd_boundaries(tmp_path):
    source = tmp_path / 'source'
    source.mkdir(mode=0o700)
    (source / 'input.txt').write_text('sealed')
    (source / 'input.txt').chmod(0o400)
    code = '''
import json, os, socket
checks = {}
try:
    open('/work/write-attempt', 'w').write('x')
    checks['work_readonly'] = False
except OSError:
    checks['work_readonly'] = True
try:
    socket.create_connection(('1.1.1.1', 53), .2)
    checks['network_none'] = False
except OSError:
    checks['network_none'] = True
checks['host_absent'] = not os.path.exists('/host')
checks['broker_absent'] = not os.path.exists('/broker.sock')
checks['caps_dropped'] = open('/proc/self/status').read().split('CapEff:\\t')[1].split('\\n')[0] == '0000000000000000'
checks['pid_namespace'] = os.readlink('/proc/1/root') == '/'
checks['no_unexpected_fds'] = len(os.listdir('/proc/self/fd')) <= 4
print(json.dumps(checks, sort_keys=True))
assert all(checks.values()), checks
'''
    sandbox = DockerSandbox(os.environ['ROUTER_SANDBOX_IMAGE'],
                            os.environ['ROUTER_SANDBOX_RUNTIME_SHA256'])
    result = sandbox.execute(('python3', '-c', code), {'PATH': '/usr/local/bin:/usr/bin:/bin',
                             'HOME': '/home/worker', 'TMPDIR': '/tmp'}, b'',
                             Budgets(10, 5, 1, 100000, 100000), source=source)
    assert result.exit_code == 0, result.stderr.decode(errors='replace')
    assert json.loads(result.stdout)['broker_absent']
