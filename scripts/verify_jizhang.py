"""Parent-owned M7 native gates in a sealed, credential-free Docker test domain."""
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from agent_subagent_router.contracts import Budgets, RouterError, canonical_bytes, hash_bytes
from agent_subagent_router.permissions.docker import DockerSandbox, _run_docker
from agent_subagent_router.receipts import ReceiptStore, atomic_json


def snapshot(project, destination):
    selected = ['package.json', 'package-lock.json', 'server/package.json', 'server/tsconfig.json',
                'server/src', 'server/tests', 'web/package.json', 'web/tsconfig.json', 'web/src',
                'node_modules']
    records = []
    destination.mkdir(mode=0o700)
    for name in selected:
        source = project/name
        entries = sorted(source.rglob('*')) if source.is_dir() else [source]
        for entry in entries:
            relative = entry.relative_to(project)
            if any(part.startswith('.env') or part in ('.cache', '.vite', 'data', 'uploads') for part in relative.parts):
                continue
            target = destination/relative
            if entry.is_symlink():
                resolved = entry.resolve()
                if not resolved.is_relative_to(project):
                    raise RouterError('TEST_SOURCE_ESCAPE', str(relative))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(entry.readlink())
                records.append({'path': str(relative), 'symlink': str(entry.readlink())})
            elif entry.is_file():
                if entry.suffix in ('.db', '.sqlite', '.sqlite3'):
                    continue  # Native fake tests need no database bytes, including package templates.
                target.parent.mkdir(parents=True, exist_ok=True)
                data = entry.read_bytes()
                target.write_bytes(data)
                target.chmod(entry.stat().st_mode & 0o555)
                records.append({'path': str(relative), 'sha256': hash_bytes(data), 'size': len(data)})
    # Every copied link must resolve within the completed sealed closure.
    for link in destination.rglob('*'):
        if link.is_symlink() and (not link.resolve().is_relative_to(destination) or not link.exists()):
            raise RouterError('TEST_SOURCE_ESCAPE', str(link.relative_to(destination)))
    return records


def main():
    state = Path.home()/'.local/state/agent-subagent-router'
    config = json.loads((Path.home()/'.local/share/agent-subagent-router/sandbox.json').read_text())
    base_tag = 'router-local-'+config['image'].removeprefix('sha256:')[:16]+':sealed'
    _run_docker(('image', 'tag', config['image'], base_tag), timeout=10).check_returncode()
    node_root = Path.home()/'.nvm/versions/node/v22.21.0'
    with tempfile.TemporaryDirectory(prefix='router-test-image-') as folder:
        context = Path(folder)
        shutil.copyfile(node_root/'bin/node', context/'node')
        shutil.copytree(node_root/'lib/node_modules/npm', context/'npm', symlinks=True)
        (context/'Dockerfile').write_text(f'FROM {base_tag}\nUSER root\n'
            'COPY --chmod=0555 node /opt/node/bin/node\nCOPY npm /opt/node/lib/node_modules/npm\n'
            'RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /opt/node/bin/npm\n'
            'USER 1000:1000\nENTRYPOINT []\nCMD []\n')
        built = _run_docker(('build', '--network=none', '--pull=false', '--iidfile', str(context/'id'), str(context)), timeout=120)
        if built.returncode:
            raise RouterError('TEST_IMAGE_BUILD_FAILED', built.stderr.decode()[-2000:])
        image = (context/'id').read_text().strip()
    destination = state/'parent-tests'/str(uuid.uuid4())
    destination.mkdir(parents=True, mode=0o700)
    records = snapshot(Path.home()/'vscode_folder/jizhang', destination/'source')
    # Vitest writes cache after all tests. Redirect only that generated cache domain.
    cache = destination/'cache'
    cache.mkdir(mode=0o700)
    (destination/'source/server/node_modules').symlink_to('/candidate', target_is_directory=True)
    source_hash = hash_bytes(canonical_bytes(records))
    atomic_json(destination/'source-manifest.json', {'files': records, 'sha256': source_hash, 'image': image})
    sandbox = DockerSandbox(image, config['runtime_sha256'])
    store = ReceiptStore(state/'runs')
    for command in (('npm', '--workspace', 'server', 'test'), ('npm', 'run', 'lint')):
        run = store.create('m7-parent', 'jizhang-native-gate')
        result = sandbox.execute(command, {'PATH': '/opt/node/bin:/usr/bin:/bin', 'HOME': '/home/worker',
            'TMPDIR': '/tmp', 'npm_config_cache': '/tmp/npm-cache', 'CI': 'true'}, b'',
            Budgets(180, 180, 1, 2000000, 4096), source=destination/'source', candidate_directory=cache)
        artifacts = [store.artifact(run, 'stdout.txt', result.stdout), store.artifact(run, 'stderr.txt', result.stderr)]
        receipt = store.finalize(run, {'kind': 'parent-test', 'classification': 'PASS' if result.exit_code == 0 and result.reason == 'exited' else 'FAIL',
            'argv': command, 'source_sha256': source_hash, 'image': image, 'exit_code': result.exit_code,
            'reason': result.reason, 'duration_seconds': result.duration_seconds, 'broker': False,
            'network': False, 'artifacts': artifacts, 'node_sha256': hash_bytes((node_root/'bin/node').read_bytes())})
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
