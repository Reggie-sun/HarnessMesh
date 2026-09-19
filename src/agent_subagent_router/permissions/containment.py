import shutil
import subprocess

from ..contracts import RouterError


def probe_containment() -> dict:
    binary = shutil.which('bwrap', path='/usr/bin:/bin')
    result = {'primitive': 'bubblewrap', 'qualified': False, 'project_access': False,
              'classification': 'BLOCKED_CAPABILITY'}
    if not binary:
        return result | {'reason': 'bubblewrap_missing'}
    try:
        process = subprocess.run([binary, '--unshare-user', '--unshare-pid', '--ro-bind',
                                  '/', '/', '--', '/usr/bin/true'], capture_output=True,
                                 timeout=5, env={'PATH': '/usr/bin:/bin'}, close_fds=True)
    except (OSError, subprocess.TimeoutExpired):
        return result | {'reason': 'namespace_probe_failed'}
    return result | {'probe_exit': process.returncode,
                     'reason': ('namespace_unavailable' if process.returncode else
                                'adversarial_containment_not_qualified'),
                     'diagnostic': process.stderr.decode(errors='replace')[:512]}


def require_project_containment(sandbox=None, runtime=None) -> dict:
    if sandbox is None or runtime is None:
        evidence = probe_containment()
        raise RouterError('BLOCKED_CAPABILITY', evidence['reason'])
    from .qualification import qualify
    return qualify(sandbox, runtime)
