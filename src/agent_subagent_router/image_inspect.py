"""Offline image seal entrypoint. A seal is never route or semantic qualification."""
from pathlib import Path

from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .image_contract import ImageTaskContract
from .image_seal import seal_images
from .receipts import implementation_identity
from .runtime_config import installed_runtime, installed_sandbox


SPEC_SHA = 'c1169a61ba8573a2c4ce442b321683a65b800230d3e8620e069e388a6d97c0f1'
CODEX_SHA = '3188814c35471432d4123203e0eb38e5bddc60226e3d7ddf0e59e649ea140022'


def inspect_images(data: dict, store_root: Path, *, sandbox_config: Path | None = None):
    task = ImageTaskContract.from_dict(data)
    value = task.to_dict()
    if (len(value['selected_refs']) < 2 or not any(
            ref['sha256'] == SPEC_SHA for ref in value['selected_refs'])):
        raise RouterError('IMAGE_ACCEPTED_REFS_REQUIRED')
    # The CLI constructs actual pins. The task cannot provide its own runtime/image proof.
    from .adapters import image_claude, codex_image_rpc
    from . import image_wire, image_output
    if sandbox_config is not None:
        configured = strict_json(Path(sandbox_config).read_bytes())
        if configured.get('purpose') == 'ISOLATED_IMAGE_ROUTE/v1':
            from .image_runtime import image_runtime
            sandbox, pins = image_runtime(value, sandbox_config)
            sealed = seal_images(task, store_root, pins)
            return {'schema': 'image-inspect/v1', 'manifest': sealed['manifest_path'],
                    'image_count': len(sealed['images']), 'pins': pins,
                    'capability_status': 'ENGINEERING_ROUTE_NOT_LIVE_QUALIFIED',
                    'qualified_route': None, 'formal_execution': 'BLOCKED',
                    'semantic_qualification': 'NOT_EVALUATED', 'authority': 'none', 'eligible': False}
    if task.backend == 'kimi':
        runtime = installed_runtime()
        runtime.verify()
        sandbox = installed_sandbox('kimi', sandbox_config)
        sandbox.verify()
        runtime_pin = runtime.to_dict()
        adapter = Path(image_claude.__file__).read_bytes()
        status = 'NATIVE_FAKE_ONLY_NOT_LIVE_QUALIFIED'
    else:
        if sandbox_config is None:
            raise RouterError('IMAGE_SANDBOX_CONFIG_REQUIRED')
        config = strict_json(Path(sandbox_config).read_bytes())
        from .permissions.docker import DockerSandbox, _run_docker
        if (config.get('purpose') != 'OFFLINE_NATIVE_DIAGNOSTIC_ONLY'
                or config.get('runtime_sha256') != CODEX_SHA
                or config.get('runtime_version') != '0.154.0'
                or config.get('helper_sha256') != hash_bytes(Path(codex_image_rpc.__file__).read_bytes())):
            raise RouterError('IMAGE_DIAGNOSTIC_PIN_MISMATCH')
        sandbox = DockerSandbox(config['image'], CODEX_SHA)
        sandbox.verify()
        inspected = _run_docker(('image', 'inspect', sandbox.image), timeout=5)
        if inspected.returncode:
            raise RouterError('SANDBOX_IMAGE_UNAVAILABLE')
        labels = strict_json(inspected.stdout)[0]['Config']['Labels']
        if labels.get('org.agent-subagent-router.image-helper-sha256') != config['helper_sha256']:
            raise RouterError('IMAGE_DIAGNOSTIC_PIN_MISMATCH')
        runtime_pin = {'sha256': CODEX_SHA, 'version': '0.154.0'}
        adapter = Path(codex_image_rpc.__file__).read_bytes()
        status = 'INCOMPLETE_GENERATION_BOUND'
    pins = {'runtime': runtime_pin, 'adapter': {'sha256': hash_bytes(adapter)},
            'image': {'sha256': sandbox.image.removeprefix('sha256:')},
            'protocol': {'sha256': hash_bytes(canonical_bytes({
                'output': hash_bytes(Path(image_output.__file__).read_bytes()),
                'wire': hash_bytes(Path(image_wire.__file__).read_bytes()),
                'version': 'image-input/v1'}))},
            'implementation': {'sha256': implementation_identity()['source_sha256']}}
    sealed = seal_images(task, store_root, pins)
    return {'schema': 'image-inspect/v1', 'manifest': sealed['manifest_path'],
            'image_count': len(sealed['images']), 'pins': pins,
            'capability_status': status, 'qualified_route': None,
            'formal_execution': 'BLOCKED', 'semantic_qualification': 'NOT_EVALUATED',
            'authority': 'none', 'eligible': False}
