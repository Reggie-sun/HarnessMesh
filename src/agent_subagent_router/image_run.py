"""Image-only execution owner. Project task qualifications cannot admit images."""
import base64
from datetime import datetime, timezone
import platform
from pathlib import Path
import tempfile

from .adapters.image_claude import build_image_invocation, docker_projection, visible_text
from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .image_budget import require_probe_budget, reserve_probe
from .image_output import decode_image_claude, decode_image_codex
from .image_probe import read_probe
from .image_process import ImageProcessBudgets
from .image_runtime import image_runtime
from .image_seal import verify_image_seal
from .receipts import redact_known_secrets
from .transport.credentials import credential_fingerprint, load_credential


def require_live_admission(store, task, manifest, probe_id, budget_id, fingerprint):
    # This amendment authorizes one router-owned capability probe per backend.
    # Formal/project requests still have no monetary authorization.
    if not probe_id:
        raise RouterError('IMAGE_FORMAL_BUDGET_NOT_AUTHORIZED')
    probe, _ = read_probe(store, probe_id, manifest)
    from .image_conformance import require_conformance
    require_conformance(store, probe, task)
    return require_probe_budget(store, budget_id, task, fingerprint)


def _invocation(task, pngs, capability, directory):
    budgets = ImageProcessBudgets.from_task(task)
    if task['backend'] == 'kimi':
        from .backends.kimi import profile
        from .runtime_config import installed_runtime
        invocation = build_image_invocation(installed_runtime(), profile(task['profile']),
            directory/'native', 'http://127.0.0.1:18765', capability, task, pngs, budgets)
        argv, env = docker_projection(invocation)
        return argv, env, invocation.stdin
    prompt = canonical_bytes({'model': task['model'], 'effort': task['effort'],
        'system_text': task['system_text'], 'task_text': visible_text(task),
        'png_b64': [base64.b64encode(raw).decode('ascii') for raw in pngs],
        'wall_seconds': budgets.wall_seconds, 'output_bytes': budgets.output_bytes})
    if len(prompt) > task['budgets']['payload_bytes']:
        raise RouterError('IMAGE_PAYLOAD_LIMIT')
    return ('/usr/local/bin/python3', '/opt/router/image_codex.py'), {
        'PATH': '/usr/bin:/bin', 'HOME': '/home/worker', 'CODEX_HOME': '/home/worker/codex',
        'TMPDIR': '/tmp', 'LANG': 'C.UTF-8', 'OPENAI_BASE_URL': 'http://127.0.0.1:18765',
        'IMAGE_ROUTE_CAPABILITY': capability}, prompt


def run_image_contract(manifest, store, *, sandbox_config, credential_ref=None,
                       probe_id=None, budget_id=None, upstream=None, cancel=None):
    run = store.create('router-image', 'image-invocation')
    artifacts, observations, rejections = [], [], []
    process = None
    removed = False
    wire = 0
    task = None
    pins = None
    broker = None
    credential = ''
    fingerprint = None
    raw = canonical = None
    classification = 'INCOMPLETE'
    try:
        sealed = verify_image_seal(Path(manifest))
        task = sealed['task']
        sandbox, pins = image_runtime(task, sandbox_config)
        if pins != sealed['pins']:
            raise RouterError('IMAGE_ROUTE_PIN_DRIFT')
        if cancel is not None and cancel.is_set():
            raise RouterError('IMAGE_CANCELLED')
        if upstream is None:
            provider = 'openai' if task['backend'] == 'codex' else 'kimi'
            credential = load_credential(provider, credential_ref, project_root=Path(__file__).resolve().parents[2])
            fingerprint = credential_fingerprint(provider, credential)
            require_live_admission(store, task, manifest, probe_id, budget_id, fingerprint)
        else:
            credential = 'sk-offline-image-test-only' if task['backend'] == 'codex' else 'offline-image-test-only'
        pngs = [Path(item['blob_path']).read_bytes() for item in sealed['images']]
        verify_image_seal(Path(manifest))
        artifacts.append(store.artifact(run, 'sealed-input.json', Path(manifest).read_bytes(),
                                        media_type='application/json'))
        budgets = ImageProcessBudgets.from_task(task)

        def observe(value):
            store.observe(run, {'kind': 'image-invocation/v1', 'upstream': value})

        def exchange(phase, data):
            index = sum(x['path'].startswith('wire/'+phase+'-') for x in artifacts)
            artifacts.append(store.artifact(run, f'wire/{phase}-{index:03d}.bin', data,
                secrets=(credential.encode(), broker.capability.encode()),
                media_type='application/octet-stream', producer='image-broker'))

        def before_request():
            if cancel is not None and cancel.is_set():
                raise RouterError('IMAGE_CANCELLED')
            if verify_image_seal(Path(manifest)) != sealed:
                raise RouterError('IMAGE_SEAL_CHANGED')
            _, current_pins = image_runtime(task, sandbox_config)
            if current_pins != pins:
                raise RouterError('IMAGE_ROUTE_PIN_DRIFT')
            if upstream is None:
                require_live_admission(store, task, manifest, probe_id, budget_id, fingerprint)
                reserve_probe(store, task['backend'], run.name)

        with tempfile.TemporaryDirectory(prefix='router-image-run-') as temporary:
            directory = Path(temporary)
            if task['backend'] == 'codex':
                from .transport.codex_broker import CodexBroker
                broker = CodexBroker(task, credential, upstream=upstream,
                    socket_path=directory/'broker.sock', before_request=before_request,
                    on_observation=observe, on_exchange=exchange)
            else:
                from .backends.kimi import profile
                from .image_wire import validate_claude_image_request, validate_claude_image_response
                from .transport.broker import Broker
                framing = {'os_release': platform.release(),
                    'day': datetime.now(timezone.utc).date().isoformat(), 'cwd': '/home/worker'}
                broker = Broker(profile(task['profile']), credential,
                    request_limit=budgets.request_limit, wall_seconds=budgets.wall_seconds,
                    generation_tokens=budgets.generation_tokens, allowed_tools=(),
                    allow_response_tools=False, upstream=upstream, socket_path=directory/'broker.sock',
                    before_request=before_request, on_observation=observe, on_exchange=exchange,
                    request_validator=lambda body: validate_claude_image_request(task, body, framing),
                    response_validator=lambda headers, data: validate_claude_image_response(task, headers, data),
                    max_request_bytes=task['budgets']['payload_bytes'])
            with broker:
                argv, env, prompt = _invocation(task, pngs, broker.capability, directory)
                process = sandbox.execute(argv, env, prompt, budgets, source=None,
                    broker_socket=directory/'broker.sock', cancel=cancel,
                    on_stop=broker.revoke, last_activity=broker.last_activity)
                removed = True  # execute returned only after owned Docker rm succeeded.
        observations, rejections = broker.observations, broker.rejections
        wire = sum(x.get('wire_started', False) for x in observations)
        for name, data in [('native-stdout.bin', process.stdout), ('native-stderr.bin', process.stderr)]:
            artifacts.append(store.artifact(run, name, data,
                secrets=(credential.encode(), broker.capability.encode()), producer='native-runtime'))
        if (process.reason != 'exited' or process.exit_code != 0 or process.truncated
                or not removed or rejections or len(observations) != 1
                or observations[0]['classification'] != 'IDENTITY_VERIFIED'):
            raise RouterError('IMAGE_NATIVE_EXECUTION_INCOMPLETE')
        if image_runtime(task, sandbox_config)[1] != pins or verify_image_seal(Path(manifest)) != sealed:
            raise RouterError('IMAGE_ROUTE_PIN_DRIFT')
        if task['backend'] == 'codex':
            raw, canonical = decode_image_codex(process.stdout, budgets.output_bytes, task=task)
        else:
            raw, canonical = decode_image_claude(process.stdout, budgets.output_bytes)
        if task['backend'] == 'codex':
            native = strict_json(process.stdout)
            proof = observations[0]['wire_proof']
            if (native['thread_id'] != proof['thread_id'] or native['turn_id'] != proof['turn_id']):
                raise RouterError('IMAGE_NATIVE_ASSOCIATION_MISMATCH')
        else:
            events = [strict_json(line) for line in process.stdout.splitlines() if line.strip()]
            inits = [x for x in events if x.get('subtype') == 'init']
            if (len(inits) != 1 or inits[0].get('session_id') != observations[0]['input_proof']['session_id']
                    or inits[0].get('skills') != []):
                raise RouterError('IMAGE_NATIVE_ASSOCIATION_MISMATCH')
        if hash_bytes(raw) != observations[0].get('response_output_sha256'):
            raise RouterError('IMAGE_NATIVE_ASSOCIATION_MISMATCH')
        secrets = (credential.encode(), broker.capability.encode())
        if any(redact_known_secrets(data, secrets)[1] for data in (raw, canonical)):
            raise RouterError('UPSTREAM_SECRET_REFLECTION')
        artifacts.append(store.artifact(run, 'model-raw.json', raw, media_type='application/json', secrets=secrets))
        artifacts.append(store.artifact(run, 'model-canonical.json', canonical, media_type='application/json', secrets=secrets))
        classification = 'ENGINEERING_NATIVE_COMPLETE' if upstream is not None else 'IMAGE_NATIVE_COMPLETE'
    except (RouterError, OSError, ValueError, KeyError, TypeError) as exc:
        classification = exc.code if isinstance(exc, RouterError) else 'IMAGE_LOCAL_INPUT_ERROR'
        if classification == 'OBSERVATION_DRAIN_TIMEOUT':
            return store.recover(run.name) | {'kind': 'image-invocation/v1',
                'classification': 'INCOMPLETE', 'cause': classification}
        if broker is not None:
            observations, rejections = broker.observations, broker.rejections
            wire = sum(x.get('wire_started', False) for x in observations)
    return store.finalize(run, {'kind': 'image-invocation/v1', 'classification': classification,
        'evidence_kind': 'synthetic-upstream' if upstream is not None else 'authenticated-endpoint',
        'manifest': str(manifest), 'pins': pins, 'backend': task['backend'] if task else None,
        'model': task['model'] if task else None, 'profile': task['profile'] if task else None,
        'effort': task['effort'] if task else None, 'wire_requests': wire,
        'credential_fingerprint': fingerprint if upstream is None and credential else None,
        'probe_id': probe_id, 'budget_id': budget_id, 'upstream': observations, 'rejections': rejections,
        'container_removed': removed, 'native': {'exit_code': process.exit_code,
            'reason': process.reason, 'duration_seconds': process.duration_seconds,
            'truncated': process.truncated} if process else None,
        'artifacts': artifacts, 'actual_cost_usd': None, 'semantic_metrics': None,
        'source_semantic': 'NOT_EVALUATED', 'authority': 'none', 'eligible': False})
