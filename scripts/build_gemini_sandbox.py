"""Build the Gemini sandbox from locally pinned bytes only."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

from agent_subagent_router.adapters.gemini import SETTINGS, GeminiRuntime, tree_hash
from agent_subagent_router.contracts import RouterError, canonical_bytes, hash_bytes
from agent_subagent_router.permissions import container_entry
from agent_subagent_router.permissions.docker import _run_docker


VERSION = '0.60.0'
BASE_IMAGE = 'sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff'
RUNTIME_ROOT = Path.home()/'.local/share/agent-subagent-router/runtimes'/f'gemini-{VERSION}'
PACKAGE_SOURCE = RUNTIME_ROOT/'node_modules/@google/gemini-cli'
SEALED_PACKAGE = RUNTIME_ROOT/'sealed-package'
NODE = Path.home()/'.nvm/versions/node/v22.21.0/bin/node'
CONFIG_ROOT = Path.home()/'.local/share/agent-subagent-router'


def _regular_tree(source: Path) -> None:
    """Reject links and special entries before copying a runtime package."""
    try:
        root_mode = source.lstat().st_mode
    except OSError as exc:
        raise RouterError('RUNTIME_MISSING', 'Gemini CLI package missing') from exc
    if not stat.S_ISDIR(root_mode) or stat.S_ISLNK(root_mode):
        raise RouterError('RUNTIME_CHANGED', 'Gemini CLI package root is unsafe')
    for parent, directories, files in os.walk(source, topdown=True, followlinks=False):
        current = Path(parent)
        if stat.S_ISLNK(current.lstat().st_mode):
            raise RouterError('RUNTIME_CHANGED', 'Gemini CLI package contains a symlink')
        for name in [*directories, *files]:
            mode = (current/name).lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise RouterError('RUNTIME_CHANGED', 'Gemini CLI package contains unsupported entry')


def _copy_package(destination: Path) -> None:
    """Copy only the self-contained CLI package into the sealed tree layout."""
    _regular_tree(PACKAGE_SOURCE)
    target = destination/'node_modules/@google/gemini-cli'
    target.parent.mkdir(parents=True, mode=0o700)
    shutil.copytree(PACKAGE_SOURCE, target, copy_function=shutil.copy2)
    _regular_tree(destination)
    if not (target/'bundle/gemini.js').is_file():
        raise RouterError('RUNTIME_MISSING', 'Gemini bundle is absent')


def seal_package() -> Path:
    """Materialize a symlink-free package once, refusing to replace a changed seal."""
    with tempfile.TemporaryDirectory(prefix='gemini-package-', dir=RUNTIME_ROOT) as folder:
        staged = Path(folder)/'sealed-package'
        _copy_package(staged)
        staged_hash = tree_hash(staged)
        if SEALED_PACKAGE.exists():
            if SEALED_PACKAGE.is_symlink() or tree_hash(SEALED_PACKAGE) != staged_hash:
                raise RouterError('RUNTIME_CHANGED', 'existing Gemini package seal differs')
            return SEALED_PACKAGE
        SEALED_PACKAGE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        staged.rename(SEALED_PACKAGE)
    return SEALED_PACKAGE


def installed_runtime() -> GeminiRuntime:
    package = seal_package().absolute()
    try:
        node_mode = NODE.lstat().st_mode
    except OSError as exc:
        raise RouterError('RUNTIME_MISSING', 'pinned Node 22 binary missing') from exc
    if NODE.is_symlink() or not stat.S_ISREG(node_mode):
        raise RouterError('RUNTIME_CHANGED', 'pinned Node 22 binary is unsafe')
    runtime = GeminiRuntime(str(NODE), hash_bytes(NODE.read_bytes()), package, VERSION, tree_hash(package))
    runtime.verify()
    return runtime


def _write_private_json(target: Path, value: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_suffix(target.suffix+'.tmp')
    try:
        temporary.write_bytes(canonical_bytes(value)+b'\n')
        temporary.chmod(0o600)
        os.replace(temporary, target)
        target.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def build() -> dict:
    """Build locally with Docker network disabled and persist exact local identities."""
    runtime = installed_runtime()
    inspected = _run_docker(('image', 'inspect', BASE_IMAGE), timeout=10)
    if inspected.returncode:
        raise RouterError('SANDBOX_BASE_MISSING', 'pinned local Python base is absent')
    entry = Path(container_entry.__file__).read_bytes()
    settings = canonical_bytes(SETTINGS)
    with tempfile.TemporaryDirectory(prefix='gemini-image-') as folder:
        root = Path(folder)
        shutil.copyfile(NODE, root/'node')
        (root/'node').chmod(0o555)
        _copy_package(root/'gemini')
        (root/'container_entry.py').write_bytes(entry)
        (root/'router-settings.json').write_bytes(settings)
        if (hash_bytes((root/'node').read_bytes()) != runtime.node_sha256
                or tree_hash(root/'gemini') != runtime.package_sha256
                or hash_bytes((root/'container_entry.py').read_bytes()) != hash_bytes(entry)
                or (root/'router-settings.json').read_bytes() != settings):
            raise RouterError('RUNTIME_CHANGED', 'image inputs changed while copying')
        (root/'Dockerfile').write_text(
            f'FROM python@{BASE_IMAGE}\n'
            'COPY --chmod=0555 node /opt/node/bin/node\n'
            'COPY gemini/node_modules/@google/gemini-cli /opt/gemini/node_modules/@google/gemini-cli\n'
            'COPY --chmod=0444 router-settings.json /opt/gemini/router-settings.json\n'
            'COPY --chmod=0555 container_entry.py /opt/router/container_entry.py\n'
            f'LABEL org.agent-subagent-router.runtime-sha256="{runtime.sha256}"\n'
            f'LABEL org.agent-subagent-router.entry-sha256="{hash_bytes(entry)}"\n'
            'USER 1000:1000\nWORKDIR /work\nENTRYPOINT []\nCMD []\n')
        result = _run_docker(('build', '--network=none', '--pull=false', '--iidfile', str(root/'image-id'),
                              str(root)), timeout=180)
        if result.returncode:
            raise RouterError('SANDBOX_BUILD_FAILED', result.stderr.decode('utf-8', 'replace')[-500:])
        image = (root/'image-id').read_text().strip()
    if not image.startswith('sha256:') or len(image) != 71:
        raise RouterError('SANDBOX_BUILD_FAILED', 'Docker did not return an immutable image id')
    sandbox = {'image': image, 'runtime_sha256': runtime.sha256,
               'entry_sha256': hash_bytes(entry), 'base_image': BASE_IMAGE}
    runtime_config = runtime.to_dict() | {'sha256': runtime.sha256}
    _write_private_json(CONFIG_ROOT/'gemini-sandbox.json', sandbox)
    _write_private_json(CONFIG_ROOT/'gemini-runtime.json', runtime_config)
    return sandbox


def main() -> None:
    print(json.dumps(build(), sort_keys=True))


if __name__ == '__main__':
    main()
