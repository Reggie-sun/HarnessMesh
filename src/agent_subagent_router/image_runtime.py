"""Exact local image tuple; caller route claims never supply runtime proof."""
from pathlib import Path

from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .permissions.docker import DockerSandbox, _run_docker
from .receipts import implementation_identity

PURPOSE = 'ISOLATED_IMAGE_ROUTE/v1'
API_SPEC_SHA = '14e10cad0f3afc44f0f3796c2ae86c45e161c8a17ab2d54801c8c261a81df272'
SUBSCRIPTION_SPEC_SHA = '94a290b26e496831024dd19d4fdbb1e0d29e5e23f680c26df09105c68e8b729a'
MINIMAX_SPEC_SHA = '24bc75a73bf32bde768f6aec13d333b215785fade08cb9b3c81134c9668031ed'
MINIMAX_BASE = 'sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff'


def image_runtime(task, config_path):
    from .adapters import image_claude, image_codex, codex_image_rpc
    from . import image_wire, image_output
    from .permissions import container_entry, image_container_entry
    from .runtime_config import CLAUDE_SHA256, CLAUDE_VERSION
    from .image_inspect import CODEX_SHA
    config = strict_json(Path(config_path).read_bytes())
    if (not isinstance(config, dict) or set(config) != {'purpose', 'backend', 'image',
            'runtime_sha256', 'runtime_version', 'entry_sha256', 'image_entry_sha256',
            'helpers', 'base_image'} or config['purpose'] != PURPOSE
            or config['backend'] != task['backend']):
        raise RouterError('IMAGE_RUNTIME_CONFIG_MISMATCH')
    helpers = {}
    if task['backend'] == 'kimi':
        from .backends.kimi import profile
        route = profile(task['profile'])
        if task['model'] != route.client_model or task['effort'] != route.effort:
            raise RouterError('IMAGE_ROUTE_MISMATCH')
        runtime_sha, version = CLAUDE_SHA256, CLAUDE_VERSION
        adapter = Path(image_claude.__file__)
    elif task['backend'] == 'codex':
        spec = {'api-bounded': API_SPEC_SHA, 'subscription-bounded': SUBSCRIPTION_SPEC_SHA}.get(task['profile'])
        if spec is None or not any(ref['sha256'] == spec for ref in task['selected_refs']):
            raise RouterError('IMAGE_API_ACCEPTANCE_REQUIRED')
        runtime_sha, version = CODEX_SHA, '0.154.0'
        adapter = Path(image_codex.__file__)
        helpers = {'image_codex.py': hash_bytes(adapter.read_bytes()),
                   'codex_image_rpc.py': hash_bytes(Path(codex_image_rpc.__file__).read_bytes())}
    elif task['backend'] == 'minimax':
        from .adapters import image_minimax
        if ((task['model'], task['profile'], task['effort']) != ('MiniMax-M3', 'responses-bounded', 'provider-default')
                or not any(ref['sha256'] == MINIMAX_SPEC_SHA for ref in task['selected_refs'])
                or config['base_image'] != MINIMAX_BASE):
            raise RouterError('IMAGE_MINIMAX_ACCEPTANCE_REQUIRED')
        adapter = Path(image_minimax.__file__)
        runtime_sha, version = hash_bytes(adapter.read_bytes()), 'minimax-responses/v1'
        helpers = {'image_minimax.py': runtime_sha}
    else:
        raise RouterError('IMAGE_ROUTE_MISMATCH')
    if (config['runtime_sha256'] != runtime_sha or config['runtime_version'] != version
            or config['entry_sha256'] != hash_bytes(Path(container_entry.__file__).read_bytes())
            or config['image_entry_sha256'] != hash_bytes(Path(image_container_entry.__file__).read_bytes())
            or config['helpers'] != helpers):
        raise RouterError('IMAGE_RUNTIME_CONFIG_MISMATCH')
    sandbox = DockerSandbox(config['image'], runtime_sha, image_entry=True)
    sandbox.verify()
    result = _run_docker(('image', 'inspect', sandbox.image), timeout=5)
    if result.returncode:
        raise RouterError('SANDBOX_IMAGE_UNAVAILABLE')
    labels = strict_json(result.stdout)[0]['Config']['Labels']
    if labels.get('org.agent-subagent-router.image-helpers-sha256') != hash_bytes(canonical_bytes(helpers)):
        raise RouterError('IMAGE_RUNTIME_CONFIG_MISMATCH')
    from .transport import broker
    from . import image_process
    modules = [image_wire, image_output, image_process, broker]
    if task['backend'] in ('codex', 'minimax'):
        from . import codex_image_wire
        from .transport import codex_broker
        modules.extend([codex_image_wire, codex_broker])
        if task['backend'] == 'minimax':
            from . import minimax_image_wire
            modules.append(minimax_image_wire)
    policy = {Path(module.__file__).name: hash_bytes(Path(module.__file__).read_bytes()) for module in modules}
    policy['image_entry'] = config['image_entry_sha256']
    policy['image_helpers'] = helpers
    return sandbox, {
        'runtime': {'sha256': runtime_sha, 'version': version},
        'image': {'sha256': sandbox.image.removeprefix('sha256:')},
        'adapter': {'sha256': hash_bytes(adapter.read_bytes())},
        'protocol': {'sha256': hash_bytes(canonical_bytes(policy)), 'version': 'image-route/v1'},
        'implementation': {'sha256': implementation_identity()['source_sha256']},
        'configuration': {'sha256': hash_bytes(canonical_bytes(config))},
    }
