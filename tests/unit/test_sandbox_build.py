import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_subagent_router.contracts import RouterError, hash_bytes


def test_changed_runtime_cannot_receive_the_original_image_label(tmp_path):
    spec = importlib.util.spec_from_file_location('builder', Path(__file__).parents[2]/'scripts/build_sandbox.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    binary = tmp_path/'runtime'
    binary.write_bytes(b'original')
    runtime = SimpleNamespace(executable=str(binary), sha256=hash_bytes(b'original'),
                              verify=lambda: binary.write_bytes(b'changed-after-verification'))
    with pytest.raises(RouterError, match='RUNTIME_CHANGED'):
        builder.copy_runtime(runtime, tmp_path/'build-copy')
