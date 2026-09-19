import socket
import subprocess
from pathlib import Path

import pytest

from agent_subagent_router.contracts import Budgets, RouterError, hash_bytes
from agent_subagent_router.permissions import docker
from agent_subagent_router.supervisor import ProcessResult


IMAGE = 'sha256:' + 'a' * 64
RUNTIME = 'b' * 64


def budgets():
    return Budgets(3, 2, 1, 10000, 10000)


def test_verify_requires_local_immutable_image_and_baked_entry_label(monkeypatch):
    calls = []
    expected_entry = hash_bytes(Path(docker.__file__).with_name('container_entry.py').read_bytes())

    def run(args, *, timeout):
        calls.append(args)
        image = {'Id': IMAGE, 'Config': {'Labels': {
            'org.agent-subagent-router.runtime-sha256': RUNTIME,
            'org.agent-subagent-router.entry-sha256': expected_entry,
        }, 'Entrypoint': None, 'Cmd': None}}
        return subprocess.CompletedProcess(['docker'], 0, __import__('json').dumps([image]).encode(), b'')

    monkeypatch.setattr(docker, '_run_docker', run)
    docker.DockerSandbox(IMAGE, RUNTIME).verify()
    assert calls == [('image', 'inspect', IMAGE)]


def test_create_uses_only_exact_readonly_mounts_and_never_places_secrets_in_docker_argv(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    broker_path = tmp_path / 'broker.sock'
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(broker_path))
    seen = []

    def run(args, *, timeout):
        seen.append(args)
        return subprocess.CompletedProcess(['docker'], 0, b'0123456789ab\n', b'')

    monkeypatch.setattr(docker, '_run_docker', run)
    monkeypatch.setattr(docker.os, 'getuid', lambda: 1000)
    monkeypatch.setattr(docker.os, 'getgid', lambda: 1000)
    try:
        identifier = docker._create_container(IMAGE, source, broker_path, budgets())
    finally:
        listener.close()
    command = seen[0]
    assert identifier == '0123456789ab'
    assert '--network=none' in command and '--read-only' in command and '--cap-drop=ALL' in command
    assert '--env' not in command and '-e' not in command and 'HOST-SECRET' not in ' '.join(command)
    mounts = [command[index + 1] for index, value in enumerate(command) if value == '--mount']
    assert len(mounts) == 2 and any('dst=/work,readonly' in mount for mount in mounts)
    assert any('dst=/broker.sock,readonly' in mount for mount in mounts)
    assert all('docker.sock' not in mount and str(tmp_path) in mount for mount in mounts)


def test_execute_revokes_before_removing_only_the_created_container(monkeypatch):
    sandbox = docker.DockerSandbox(IMAGE, RUNTIME)
    monkeypatch.setattr(sandbox, 'verify', lambda: None)
    monkeypatch.setattr(docker, '_create_container', lambda *_args: '0123456789ab')
    monkeypatch.setattr(docker, '_docker_binary', lambda: '/usr/bin/docker')
    events = []

    def supervised(invocation, *, cancel, on_stop):
        assert 'HOST-SECRET' not in ' '.join(invocation.argv)
        assert '--host=unix:///var/run/docker.sock' in invocation.argv
        assert '--config' in invocation.argv
        assert invocation.env == {'PATH': '/usr/bin:/bin'}
        on_stop()
        return ProcessResult(0, 'exited', b'', b'', False, .01, False)

    monkeypatch.setattr(docker, 'supervise', supervised)
    monkeypatch.setattr(docker, '_remove_container', lambda identifier, _wall: events.append(('remove', identifier)))
    result = sandbox.execute(('python3', '-c', 'print(1)'), {'TOKEN': 'HOST-SECRET'}, b'prompt-secret', budgets(),
                             on_stop=lambda: events.append(('revoke', None)))
    assert result.exit_code == 0
    assert events == [('revoke', None), ('remove', '0123456789ab')]


@pytest.mark.parametrize('image, runtime', [('latest', RUNTIME), (IMAGE, 'short')])
def test_constructor_rejects_mutable_or_unbound_images(image, runtime):
    with pytest.raises(RouterError):
        docker.DockerSandbox(image, runtime)


def test_lost_create_response_cleans_only_preallocated_owned_name(monkeypatch):
    seen = []
    owned = {}
    def run(args, *, timeout):
        seen.append(args)
        if args[0] == 'create':
            owned['name'] = args[args.index('--name')+1]
            raise RouterError('SANDBOX_DOCKER_UNAVAILABLE')
        if args[:2] == ('container', 'inspect'):
            assert args[2] == owned['name']
            data = [{'Id': 'a'*64, 'Config': {'Image': IMAGE, 'Labels': {
                'org.agent-subagent-router.invocation': owned['name']}}}]
            return subprocess.CompletedProcess([], 0, __import__('json').dumps(data).encode(), b'')
        assert args == ('rm', '-f', 'a'*64)
        return subprocess.CompletedProcess([], 0, b'', b'')
    monkeypatch.setattr(docker, '_run_docker', run)
    with pytest.raises(RouterError, match='SANDBOX_DOCKER_UNAVAILABLE'):
        docker._create_container(IMAGE, None, None, budgets())
    assert seen[-1] == ('rm', '-f', 'a'*64)


@pytest.mark.parametrize('direction',['parent','child'])
def test_candidate_and_immutable_source_cannot_overlap_either_direction(tmp_path,monkeypatch,direction):
    root=tmp_path/'root'
    child=root/'child'
    child.mkdir(parents=True)
    source,candidate=(child,root) if direction=='parent' else (root,child)
    sandbox=docker.DockerSandbox(IMAGE,RUNTIME)
    monkeypatch.setattr(sandbox,'verify',lambda:None)
    with pytest.raises(RouterError,match='INVALID_WRITER_OVERLAY'):
        sandbox.execute(('/usr/local/bin/python3','--version'),{},b'',budgets(),source=source,candidate_directory=candidate)
