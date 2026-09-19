"""Synthetic OS boundary probes. No host project bytes or provider calls."""
import os
from pathlib import Path
import tempfile

from ..contracts import Budgets, RouterError, canonical_bytes, strict_json


PROBE = r'''
import json, os, pathlib, socket
p = pathlib.Path
request = json.loads(input())
checks = {}
checks['non_root'] = os.getuid() != 0
status = dict(line.split(':', 1) for line in p('/proc/self/status').read_text().splitlines() if ':' in line)
checks['capabilities_dropped'] = int(status['CapEff'], 16) == 0
checks['no_new_privileges'] = status['NoNewPrivs'].strip() == '1'
checks['seccomp'] = status['Seccomp'].strip() == '2'
checks['apparmor'] = p('/proc/self/attr/current').read_text().strip() == 'docker-default (enforce)'
checks['sealed_read'] = p('/work/canary').read_text() == 'selected snapshot'
for name, action in {
    'source_write_denied': lambda: p('/work/canary').write_text('changed'),
    'source_chmod_denied': lambda: p('/work/canary').chmod(0o777),
    'root_write_denied': lambda: p('/etc/router-escape').write_text('changed'),
    'host_secret_denied': lambda: p(request['secret_path']).read_bytes(),
    'symlink_escape_denied': lambda: p('/work/outside').read_bytes(),
    'host_proc_denied': lambda: p('/proc/'+str(request['host_pid'])+'/environ').read_bytes(),
    'host_home_denied': lambda: list(p(request['host_home']).iterdir()),
    'docker_socket_denied': lambda: socket.socket(socket.AF_UNIX).connect('/var/run/docker.sock'),
    'external_network_denied': lambda: socket.create_connection(('1.1.1.1', 443), timeout=.2),
    'host_ipc_denied': lambda: socket.socket(socket.AF_UNIX).connect(request['host_socket']),
    'no_broker_in_test_domain': lambda: socket.socket(socket.AF_UNIX).connect('/broker.sock'),
}.items():
    try:
        action()
        checks[name] = False
    except OSError:
        checks[name] = True
checks['clean_environment'] = 'ROUTER_HOST_SECRET' not in os.environ
checks['private_processes'] = len([x for x in p('/proc').iterdir() if x.name.isdigit()]) <= 4
checks['scratch_writable'] = p('/tmp/scratch').write_text('scratch') == 7
print(json.dumps(checks))
'''


def probe_sandbox(sandbox) -> dict:
    sandbox.verify()
    with tempfile.TemporaryDirectory(prefix='router-containment-') as temporary:
        root = Path(temporary)
        source = root/'snapshot'
        source.mkdir(mode=0o700)
        (source/'canary').write_text('selected snapshot')
        (root/'secret').write_text('synthetic host-only secret')
        (source/'outside').symlink_to(root/'secret')
        # Real host IPC canary, not merely a path that never existed.
        import socket
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(root/'host.sock'))
            listener.listen(1)
            process = sandbox.execute(('/usr/local/bin/python3', '-c', PROBE),
                {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/home/worker'},
                canonical_bytes({'secret_path': str(root/'secret'), 'host_pid': os.getpid(),
                                 'host_home': str(Path.home()), 'host_socket': str(root/'host.sock')})+b'\n',
                Budgets(15, 15, 1, 32000, 100000), source=source)
    if process.exit_code != 0 or process.reason != 'exited' or process.truncated:
        raise RouterError('BLOCKED_CAPABILITY', 'container probe did not complete')
    checks = strict_json(process.stdout)
    if not isinstance(checks, dict) or len(checks) != 20 or any(v is not True for v in checks.values()):
        raise RouterError('BLOCKED_CAPABILITY', 'container negative probe failed: '+str(checks))
    return {'primitive': 'docker', 'image': sandbox.image, 'checks': checks,
            'os_boundary_verified': True, 'native_tools': 'NOT_EVALUATED',
            'qualified': False, 'project_access': False}
