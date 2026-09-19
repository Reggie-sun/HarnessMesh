"""Finite, shell-free subprocess execution with concurrent pipe drainage."""
from dataclasses import dataclass
import os
from pathlib import Path
import selectors
import signal
import subprocess
import threading
import time
from typing import Callable

from .contracts import Budgets


@dataclass(frozen=True)
class Invocation:
    argv: tuple[str, ...]
    cwd: Path
    env: dict[str, str]
    stdin: bytes
    budgets: Budgets


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int | None
    reason: str
    stdout: bytes
    stderr: bytes
    truncated: bool
    duration_seconds: float
    descendants_terminated: bool
    stdout_observed_bytes: int = 0
    stderr_observed_bytes: int = 0


def _signal_group(pid: int, sig: int) -> bool:
    try:
        os.killpg(pid, sig)
        return True
    except ProcessLookupError:
        return False


def supervise(invocation: Invocation, *, cancel: threading.Event | None = None,
              on_stop: Callable[[], None] | None = None) -> ProcessResult:
    start = last_activity = time.monotonic()
    try:
        child = subprocess.Popen(invocation.argv, cwd=invocation.cwd, env=invocation.env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, shell=False, close_fds=True,
                                 start_new_session=True)
    except OSError:
        if on_stop:
            on_stop()
        return ProcessResult(None, 'spawn_failed', b'', b'', False,
                             time.monotonic()-start, False)
    selector = selectors.DefaultSelector()
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    observed = {'stdout': 0, 'stderr': 0}
    input_offset = 0
    reason = 'exited'
    truncated = descendants = stopped = False
    stop_time = None

    def stop():
        nonlocal stopped, stop_time
        if not stopped:
            stopped = True
            stop_time = time.monotonic()
            try:
                if on_stop:
                    on_stop()
            finally:
                _signal_group(child.pid, signal.SIGTERM)

    try:
        for name in ('stdout', 'stderr'):
            stream = getattr(child, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        if invocation.stdin:
            os.set_blocking(child.stdin.fileno(), False)
            selector.register(child.stdin, selectors.EVENT_WRITE, 'stdin')
        else:
            child.stdin.close()
        while selector.get_map() or child.poll() is None:
            now = time.monotonic()
            if not stopped:
                if cancel is not None and cancel.is_set():
                    reason = 'cancelled'
                    stop()
                elif now-start >= invocation.budgets.wall_seconds:
                    reason = 'timeout'
                    stop()
                elif now-last_activity >= invocation.budgets.idle_seconds:
                    reason = 'idle_timeout'
                    stop()
                elif child.poll() is not None:
                    descendants = _signal_group(child.pid, 0)
                    stop()
            if stopped and now-stop_time >= .15:
                _signal_group(child.pid, signal.SIGKILL)
            if stopped and now-stop_time >= 1:
                break  # escaped pipe holder cannot defeat the finite wall deadline
            for key, _ in selector.select(.025):
                stream, name = key.fileobj, key.data
                if name == 'stdin':
                    try:
                        sent = os.write(stream.fileno(), invocation.stdin[input_offset:input_offset+65536])
                        input_offset += sent
                    except (BrokenPipeError, OSError):
                        input_offset = len(invocation.stdin)
                    if input_offset == len(invocation.stdin):
                        selector.unregister(stream)
                        stream.close()
                    continue
                try:
                    chunk = os.read(stream.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(stream)
                    stream.close()
                    continue
                last_activity = time.monotonic()
                observed[name] += len(chunk)
                remaining = invocation.budgets.output_bytes - sum(map(len, buffers.values()))
                buffers[name].extend(chunk[:max(remaining, 0)])
                if len(chunk) > remaining:
                    truncated = True
                    reason = 'output_limit'
                    stop()
        # Reap the leader; kill even on natural exit to clean remaining group members.
        if not stopped:
            descendants = _signal_group(child.pid, 0) and child.poll() is not None
        stop()
        if child.poll() is None:
            try:
                child.wait(timeout=.15)
            except subprocess.TimeoutExpired:
                _signal_group(child.pid, signal.SIGKILL)
        _signal_group(child.pid, signal.SIGKILL)
        child.wait(timeout=1)
    finally:
        try:
            stop()
        finally:
            _signal_group(child.pid, signal.SIGKILL)
            child.wait(timeout=1)
            selector.close()
            for stream in (child.stdin, child.stdout, child.stderr):
                stream.close()
    return ProcessResult(child.returncode, reason, bytes(buffers['stdout']),
                         bytes(buffers['stderr']), truncated, time.monotonic()-start,
                         descendants, observed['stdout'], observed['stderr'])
