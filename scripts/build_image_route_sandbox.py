"""Build explicit image routes from pinned local bytes; never mutate old config."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from agent_subagent_router.contracts import RouterError, canonical_bytes, hash_bytes
from agent_subagent_router.permissions import container_entry, image_container_entry
from agent_subagent_router.permissions.docker import _run_docker
from agent_subagent_router.runtime_config import installed_sandbox, CLAUDE_SHA256, CLAUDE_VERSION
from agent_subagent_router.adapters import image_codex, codex_image_rpc
from build_image_codex_sandbox import BASE, CODEX_SHA256, CODEX_VERSION
from agent_subagent_router.image_runtime import MINIMAX_BASE


def preserve_local_base(base):
    # Removing the last tag can delete an otherwise untagged base image. Keep
    # this deterministic alias; never delete image metadata as build cleanup.
    local_tag = 'router-image-base-' + base.removeprefix('sha256:') + ':sealed'
    previous = _run_docker(('image', 'inspect', local_tag), timeout=5)
    if previous.returncode == 0:
        if json.loads(previous.stdout)[0]['Id'] != base:
            raise RouterError('IMAGE_BASE_CHANGED')
    else:
        _run_docker(('image', 'tag', base, local_tag), timeout=5).check_returncode()
    tagged = json.loads(_run_docker(('image', 'inspect', local_tag), timeout=5).stdout)[0]
    if tagged['Id'] != base:
        raise RouterError('IMAGE_BASE_CHANGED')
    return local_tag


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=('kimi', 'codex', 'minimax'), required=True)
    parser.add_argument('--runtime-source', type=Path)
    parser.add_argument('--config-out', type=Path, required=True)
    args = parser.parse_args()
    if args.config_out.exists() or args.config_out.is_symlink():
        raise RouterError('IMAGE_CONFIG_EXISTS')
    helpers = {}
    if args.backend == 'kimi':
        previous = installed_sandbox()
        previous.verify()
        base = previous.image
        runtime_sha, version = CLAUDE_SHA256, CLAUDE_VERSION
        if args.runtime_source is not None:
            raise RouterError('INVALID_RUNTIME_SOURCE')
    elif args.backend == 'codex':
        path = args.runtime_source
        if path is None or path.is_symlink() or not path.is_file() or hash_bytes(path.read_bytes()) != CODEX_SHA256:
            raise RouterError('RUNTIME_CHANGED')
        base, runtime_sha, version = BASE, CODEX_SHA256, CODEX_VERSION
        helpers = {Path(module.__file__).name: Path(module.__file__).read_bytes()
                   for module in (image_codex, codex_image_rpc)}
    else:
        from agent_subagent_router.adapters import image_minimax
        if args.runtime_source is not None:
            raise RouterError('INVALID_RUNTIME_SOURCE')
        base = MINIMAX_BASE
        content = Path(image_minimax.__file__).read_bytes()
        runtime_sha, version = hash_bytes(content), 'minimax-responses/v1'
        helpers = {'image_minimax.py': content}
    _run_docker(('image', 'inspect', base), timeout=5).check_returncode()
    entry = Path(container_entry.__file__).read_bytes()
    wrapper = Path(image_container_entry.__file__).read_bytes()
    helper_hashes = {name: hash_bytes(raw) for name, raw in helpers.items()}
    with tempfile.TemporaryDirectory(prefix='router-image-route-') as temporary:
        root = Path(temporary)
        # BuildKit treats a bare sha256 ID as a registry name. The verified local
        # alias resolves metadata locally and preserves untagged original images.
        local_tag = preserve_local_base(base)
        dockerfile = [f'FROM {local_tag}']
        if args.backend == 'kimi':
            # The old project's WORKDIR created an empty /work in its image.
            # Image routes have no project path, and the original entry selects
            # /home/worker only when that inherited directory is absent.
            dockerfile.extend(['USER 0', 'RUN rmdir /work'])
        if args.backend == 'codex':
            shutil.copyfile(path, root/'codex')
            if hash_bytes((root/'codex').read_bytes()) != runtime_sha:
                raise RouterError('RUNTIME_CHANGED')
            dockerfile.append('COPY --chmod=0555 codex /opt/runtime/codex')
        for name, content in {'container_entry.py': entry, 'image_container_entry.py': wrapper, **helpers}.items():
            (root/name).write_bytes(content)
            dockerfile.append(f'COPY --chmod=0555 {name} /opt/router/{name}')
        labels = {'runtime-sha256': runtime_sha, 'entry-sha256': hash_bytes(entry),
                  'image-entry-sha256': hash_bytes(wrapper),
                  'image-helpers-sha256': hash_bytes(canonical_bytes(helper_hashes))}
        dockerfile.extend(f'LABEL org.agent-subagent-router.{name}="{value}"' for name, value in labels.items())
        dockerfile.extend(['USER 1000:1000', 'WORKDIR /home/worker', 'ENTRYPOINT []', 'CMD []'])
        (root/'Dockerfile').write_text('\n'.join(dockerfile)+'\n')
        built = _run_docker(('build', '--network=none', '--pull=false', '--iidfile', str(root/'image-id'),
                             str(root)), timeout=120)
        if built.returncode:
            # Build inputs are local public bytes, without credentials or user media.
            print(built.stderr.decode(errors='replace'))
            print(built.stdout.decode(errors='replace'))
            raise RouterError('IMAGE_BUILD_FAILED')
        image = (root/'image-id').read_text().strip()
    config = {'purpose': 'ISOLATED_IMAGE_ROUTE/v1', 'backend': args.backend, 'image': image,
              'runtime_sha256': runtime_sha, 'runtime_version': version,
              'entry_sha256': hash_bytes(entry), 'image_entry_sha256': hash_bytes(wrapper),
              'helpers': helper_hashes, 'base_image': base}
    args.config_out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with args.config_out.open('x') as stream:
        json.dump(config, stream)
    args.config_out.chmod(0o600)
    print(json.dumps(config))


if __name__ == '__main__':
    main()
