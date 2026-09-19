from pathlib import Path
import sys
import threading
import time

from agent_subagent_router.contracts import Budgets
from agent_subagent_router.supervisor import Invocation, supervise


def run(tmp_path, code, *, wall=3, limit=2000000, cancel=None, stdin=b''):
    invocation = Invocation((sys.executable, '-c', code), tmp_path, {'PATH': '/usr/bin:/bin'},
                            stdin, Budgets(wall, wall, 1, limit, 10000))
    return supervise(invocation, cancel=cancel)


def test_concurrent_streams_and_stdin_no_secret_argv(tmp_path):
    result = run(tmp_path, "import sys;sys.stderr.write('E'*1000000);"
                 "x=sys.stdin.buffer.read();sys.stdout.buffer.write(x)", stdin=b'prompt-value')
    assert result.exit_code == 0 and result.reason == 'exited'
    assert result.stdout == b'prompt-value' and len(result.stderr) == 1000000


def test_output_budget_terminates_and_records_truncation(tmp_path):
    result = run(tmp_path, "import sys;sys.stdout.write('x'*2000000)", limit=100)
    assert result.reason == 'output_limit' and result.truncated
    assert len(result.stdout) + len(result.stderr) <= 100


def test_timeout_kills_process_group_including_grandchild(tmp_path):
    pidfile = tmp_path/'pid'
    code = ("import subprocess,time;from pathlib import Path;"
            "p=subprocess.Popen(['sleep','40']);Path('pid').write_text(str(p.pid));time.sleep(40)")
    result = run(tmp_path, code, wall=.3)
    assert result.reason == 'timeout' and result.exit_code is not None
    pid = int(pidfile.read_text())
    # A killed orphan may briefly be a zombie until the host init reaps it.
    stat = Path(f'/proc/{pid}/stat')
    try:
        assert stat.read_text().split()[2] == 'Z'
    except (FileNotFoundError, ProcessLookupError):
        # procfs can return ESRCH if init reaps the process between open and read.
        pass


def test_child_exit_does_not_leave_pipe_holding_descendant(tmp_path):
    result = run(tmp_path, "import subprocess;subprocess.Popen(['sleep','30'])", wall=.5)
    assert result.duration_seconds < 2
    assert result.descendants_terminated


def test_cancel_revokes_admission_before_process_cleanup(tmp_path):
    cancel = threading.Event()
    timer = threading.Timer(.1, cancel.set)
    timer.start()
    revoked = []
    inv = Invocation((sys.executable, '-c', 'import time;time.sleep(30)'), tmp_path, {}, b'',
                     Budgets(2, 2, 1, 10000, 10000))
    result = supervise(inv, cancel=cancel, on_stop=lambda: revoked.append(time.monotonic()))
    timer.join()
    assert result.reason == 'cancelled' and len(revoked) == 1


def test_spawn_failure_is_not_exit_zero(tmp_path):
    inv = Invocation(('/nonexistent/router-test-cli',), tmp_path, {}, b'',
                     Budgets(2, 2, 1, 10000, 10000))
    result = supervise(inv)
    assert result.reason == 'spawn_failed' and result.exit_code is None
