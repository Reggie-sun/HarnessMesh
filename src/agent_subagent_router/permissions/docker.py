"""Docker-backed execution with a sealed input envelope and no host-runtime mounts."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import threading
import tempfile
import uuid
from typing import Callable

from ..contracts import Budgets, RouterError, canonical_bytes, hash_bytes
from ..supervisor import Invocation, ProcessResult, supervise


_DIGEST = re.compile(r'^[0-9a-f]{64}$')
_ENV_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_ENTRY = Path(__file__).with_name('container_entry.py')


class DockerSandbox:
    """A local, immutable image invocation; image construction remains parent-owned."""

    def __init__(self, image: str, runtime_sha256: str):
        if not isinstance(image, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
            raise RouterError('INVALID_SANDBOX_IMAGE')
        if not isinstance(runtime_sha256, str) or not _DIGEST.fullmatch(runtime_sha256):
            raise RouterError('INVALID_RUNTIME_HASH')
        self.image = image
        self.runtime_sha256 = runtime_sha256

    def verify(self) -> None:
        """Require a local image ID and its build labels; ``image inspect`` never pulls."""
        result = _run_docker(('image', 'inspect', self.image), timeout=5)
        if result.returncode:
            raise RouterError('SANDBOX_IMAGE_UNAVAILABLE')
        try:
            payload = json.loads(result.stdout)
            image = payload[0]
            labels = image['Config']['Labels'] or {}
            entrypoint = image['Config'].get('Entrypoint')
            command = image['Config'].get('Cmd')
        except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RouterError('SANDBOX_IMAGE_INVALID') from exc
        if (not isinstance(image, dict) or not isinstance(labels, dict)
                or image.get('Id') != self.image
                or labels.get('org.agent-subagent-router.runtime-sha256') != self.runtime_sha256
                or labels.get('org.agent-subagent-router.entry-sha256') != hash_bytes(_ENTRY.read_bytes())
                or entrypoint not in (None, []) or command not in (None, [])):
            raise RouterError('SANDBOX_IMAGE_INVALID')

    def execute(self, argv: tuple[str, ...], env: dict[str, str], stdin: bytes, budgets: Budgets, *,
                source: Path | None = None, broker_socket: Path | None = None,
                candidate_directory: Path | None = None,
                cancel: threading.Event | None = None,
                on_stop: Callable[[], None] | None = None) -> ProcessResult:
        self.verify()
        _validate_execution(argv, env, stdin, budgets, source, broker_socket)
        if candidate_directory is not None:
            _require_directory(candidate_directory, 'INVALID_WRITER_OVERLAY')
            if (source is None or candidate_directory.resolve().is_relative_to(source.resolve())
                    or source.resolve().is_relative_to(candidate_directory.resolve())):
                raise RouterError('INVALID_WRITER_OVERLAY')
        envelope = canonical_bytes({
            'argv': list(argv), 'env': env, 'prompt_b64': base64.b64encode(stdin).decode('ascii'),
            'wall_seconds': budgets.wall_seconds,
        })
        if len(envelope) > budgets.context_bytes:
            raise RouterError('CONTRACT_TOO_LARGE', 'container envelope exceeds context budget')
        container_id = _create_container(self.image, source, broker_socket, budgets, candidate_directory)
        stopped = False

        def revoke_once() -> None:
            nonlocal stopped
            if not stopped:
                stopped = True
                if on_stop:
                    on_stop()

        try:
            with tempfile.TemporaryDirectory(prefix='router-docker-config-') as config:
                invocation = Invocation((*_docker_prefix(config), 'start', '-ai', container_id), Path('/'),
                                        {'PATH': '/usr/bin:/bin'}, envelope, budgets)
                return supervise(invocation, cancel=cancel, on_stop=revoke_once)
        finally:
            try:
                revoke_once()
            finally:
                _remove_container(container_id, budgets.wall_seconds)


def _validate_execution(argv: tuple[str, ...], env: dict[str, str], stdin: bytes, budgets: Budgets,
                        source: Path | None, broker_socket: Path | None) -> None:
    if (not isinstance(argv, tuple) or not argv
            or any(not isinstance(part, str) or not part for part in argv)):
        raise RouterError('INVALID_INVOCATION', 'argv must be a nonempty string tuple')
    if (not isinstance(env, dict)
            or any(not isinstance(key, str) or not _ENV_NAME.fullmatch(key)
                   or not isinstance(value, str) for key, value in env.items())):
        raise RouterError('INVALID_INVOCATION', 'invalid explicit environment')
    if not isinstance(stdin, bytes) or len(stdin) > budgets.context_bytes:
        raise RouterError('CONTRACT_TOO_LARGE', 'prompt exceeds context budget')
    if source is not None:
        _require_directory(source, 'INVALID_SOURCE_PROJECTION')
    if broker_socket is not None:
        _require_socket(broker_socket)
        urls = [env.get(name) for name in ('ANTHROPIC_BASE_URL', 'GOOGLE_GEMINI_BASE_URL') if name in env]
        if urls != ['http://127.0.0.1:18765']:
            raise RouterError('INVALID_INVOCATION', 'broker needs fixed loopback URL')


def _create_container(image: str, source: Path | None, broker_socket: Path | None,
                      budgets: Budgets, candidate_directory=None) -> str:
    uid, gid = os.getuid(), os.getgid()
    if uid == 0 or gid == 0:
        raise RouterError('UNSUPPORTED_REQUIRED_CAPABILITY', 'container requires non-root host identity')
    name = 'agent-subagent-router-'+uuid.uuid4().hex
    command = [
        'create', '-i', '--pull=never', '--network=none', '--ipc=none', '--cgroupns=private',
        '--name', name, '--label', f'org.agent-subagent-router.invocation={name}',
        '--read-only', '--user', f'{uid}:{gid}', '--cap-drop=ALL',
        '--security-opt=no-new-privileges', '--security-opt=apparmor=docker-default',
        '--pids-limit=128', '--cpus=2', '--memory=1g', '--log-driver=none',
        '--tmpfs', f'/tmp:rw,nosuid,nodev,noexec,size=64m,uid={uid},gid={gid},mode=700',
        '--tmpfs', f'/home/worker:rw,nosuid,nodev,noexec,size=64m,uid={uid},gid={gid},mode=700',
    ]
    if source is not None:
        command.extend(['--mount', f'type=bind,src={source.resolve()},dst=/work,readonly,bind-propagation=rprivate',
                        '--workdir', '/work'])
    else:
        command.extend(['--workdir', '/home/worker'])
    if broker_socket is not None:
        command.extend(['--mount', f'type=bind,src={broker_socket.resolve()},dst=/broker.sock,readonly,'
                        'bind-propagation=rprivate'])
    if candidate_directory is not None:
        command.extend(['--mount', f'type=bind,src={candidate_directory.resolve()},dst=/candidate,'
                        'bind-propagation=rprivate'])
    command.extend(['--entrypoint', 'python3', image, '/opt/router/container_entry.py'])
    try:
        result = _run_docker(tuple(command), timeout=_command_timeout(budgets.wall_seconds))
        identifier = result.stdout.decode(errors='replace').strip()
        if result.returncode or not re.fullmatch(r'[0-9a-f]{12,64}', identifier):
            raise RouterError('SANDBOX_CREATE_FAILED')
    except RouterError:
        _recover_created_container(name, image, budgets.wall_seconds)
        raise
    return identifier


def _recover_created_container(name: str, image: str, wall_seconds: float):
    result = _run_docker(('container', 'inspect', name), timeout=_command_timeout(wall_seconds))
    if result.returncode:
        return  # Creation did not reach the local daemon; no unrelated object can be removed.
    try:
        value, = json.loads(result.stdout)
        owned = value['Config']['Labels']['org.agent-subagent-router.invocation'] == name
        owned = owned and value['Config']['Image'] == image
        identifier = value['Id']
    except (TypeError, KeyError, ValueError) as exc:
        raise RouterError('SANDBOX_CLEANUP_FAILED') from exc
    if not owned:
        raise RouterError('SANDBOX_CLEANUP_FAILED', 'container ownership mismatch')
    _remove_container(identifier, wall_seconds)


def _remove_container(identifier: str, wall_seconds: float) -> None:
    if not re.fullmatch(r'[0-9a-f]{12,64}', identifier):
        raise RouterError('SANDBOX_CLEANUP_FAILED')
    result = _run_docker(('rm', '-f', identifier), timeout=_command_timeout(wall_seconds))
    if result.returncode:
        raise RouterError('SANDBOX_CLEANUP_FAILED')


def _run_docker(args: tuple[str, ...], *, timeout: float) -> subprocess.CompletedProcess:
    try:
        with tempfile.TemporaryDirectory(prefix='router-docker-config-') as config:
            return subprocess.run([*_docker_prefix(config), *args], capture_output=True, timeout=timeout,
                                  env={'PATH': '/usr/bin:/bin'}, close_fds=True, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RouterError('SANDBOX_DOCKER_UNAVAILABLE') from exc


def _docker_binary() -> str:
    binary = shutil.which('docker', path='/usr/bin:/bin')
    if not binary:
        raise RouterError('SANDBOX_DOCKER_UNAVAILABLE')
    return binary


def _docker_prefix(config: str) -> tuple[str, ...]:
    # Never consult the user's currentContext, plugins or a remote Docker endpoint.
    return (_docker_binary(), '--host=unix:///var/run/docker.sock', '--config', config)


def _command_timeout(wall_seconds: float) -> float:
    return max(1.0, min(10.0, wall_seconds))


def _require_directory(path: Path, code: str) -> None:
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise RouterError(code)


def _require_socket(path: Path) -> None:
    path = Path(path)
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise RouterError('INVALID_BROKER_SOCKET') from exc
    if path.is_symlink() or not stat.S_ISSOCK(mode):
        raise RouterError('INVALID_BROKER_SOCKET')
