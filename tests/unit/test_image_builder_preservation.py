import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from agent_subagent_router.contracts import RouterError
import pytest


def builder():
    scripts = Path(__file__).parents[2]/'scripts'
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location('image_builder', scripts/'build_image_route_sandbox.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_untagged_base_is_preserved_without_image_rm(monkeypatch):
    module = builder()
    base = 'sha256:'+'a'*64
    calls = []
    def docker(args, **_):
        calls.append(args)
        data = json.dumps([{'Id': base}]).encode()
        return subprocess.CompletedProcess(args, 1 if len(calls)==1 else 0, data, b'')
    monkeypatch.setattr(module, '_run_docker', docker)
    tag = module.preserve_local_base(base)
    assert tag.endswith(':sealed')
    assert [x[:2] for x in calls] == [('image', 'inspect'), ('image', 'tag'), ('image', 'inspect')]
    assert not any('rm' in x for x in calls)


def test_conflicting_base_alias_is_never_overwritten(monkeypatch):
    module = builder()
    calls=[]
    def docker(args, **_):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, json.dumps([{'Id':'sha256:'+'b'*64}]).encode(), b'')
    monkeypatch.setattr(module, '_run_docker', docker)
    with pytest.raises(RouterError, match='IMAGE_BASE_CHANGED'):
        module.preserve_local_base('sha256:'+'a'*64)
    assert len(calls)==1
