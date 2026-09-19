"""Build from pinned local bytes only. No pull, network install, host policy changes."""
import json
from pathlib import Path
import shutil
import tempfile

from agent_subagent_router.contracts import RouterError, hash_bytes
from agent_subagent_router.runtime_config import installed_runtime
from agent_subagent_router.permissions import container_entry
from agent_subagent_router.permissions.docker import _run_docker


def copy_runtime(runtime, destination):
    runtime.verify()
    shutil.copyfile(runtime.executable, destination)
    if hash_bytes(destination.read_bytes()) != runtime.sha256:
        raise RouterError('RUNTIME_CHANGED', 'copied runtime differs from verified identity')
    destination.chmod(0o555)


def main():
    runtime = installed_runtime()
    base = 'sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff'
    _run_docker(('image', 'inspect', base), timeout=10).check_returncode()
    entry = Path(container_entry.__file__).read_bytes()
    with tempfile.TemporaryDirectory(prefix='router-image-') as folder:
        root = Path(folder)
        copy_runtime(runtime, root/'claude')
        (root/'container_entry.py').write_bytes(entry)
        (root/'Dockerfile').write_text(
            f'FROM python@{base}\n'
            'COPY --chmod=0555 claude /opt/runtime/claude\n'
            'COPY --chmod=0555 container_entry.py /opt/router/container_entry.py\n'
            f'LABEL org.agent-subagent-router.runtime-sha256="{runtime.sha256}"\n'
            f'LABEL org.agent-subagent-router.entry-sha256="{hash_bytes(entry)}"\n'
            'USER 1000:1000\nWORKDIR /work\nENTRYPOINT []\nCMD []\n')
        result = _run_docker(('build', '--network=none', '--pull=false',
                             '--iidfile', str(root/'image-id'), str(root)), timeout=120)
        print(result.stderr.decode(errors='replace'))
        result.check_returncode()
        image = (root/'image-id').read_text().strip()
    config = {'image': image, 'runtime_sha256': runtime.sha256,
              'entry_sha256': hash_bytes(entry), 'base_image': base}
    target = Path.home()/'.local/share/agent-subagent-router/sandbox.json'
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.write_text(json.dumps(config, indent=2)+'\n')
    target.chmod(0o600)
    print(json.dumps(config))


if __name__ == '__main__':
    main()
