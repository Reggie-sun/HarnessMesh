"""Parent entrypoints; only the parent can decide project acceptance."""
from pathlib import Path
import uuid

from .backends.kimi import profile
from .contracts import RouterError, TaskContract, strict_json
from .permissions.containment import require_project_containment
from .receipts import ReceiptStore
from .resolver import resolve, verify


def inspect_task(task: TaskContract, state: Path, runtime, *, sandbox=None) -> dict:
    if task.backend == 'gemini':
        from .backends.gemini import profile as gemini_profile
        selected = gemini_profile(task.profile)
        if task.skills:
            raise RouterError('UNSUPPORTED_REQUIRED_CAPABILITY', 'Gemini selected Skills are not qualified')
        if task.role == 'implementer':
            raise RouterError('WRITER_NOT_QUALIFIED')
    elif task.backend == 'kimi':
        selected = profile(task.profile)
    else:
        raise RouterError('BACKEND_NOT_QUALIFIED')
    runtime.verify()
    state = Path(state)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    transport = {'backend': task.backend, 'profile': task.profile,
                 'runtime': 'gemini-cli' if task.backend == 'gemini' else 'claude-code',
                 'runtime_identity': runtime.to_dict(), 'profile_identity': selected.to_dict(),
                 'capabilities': ['read']}
    if sandbox is not None:
        sandbox.verify()
        transport['containment'] = {'image': sandbox.image, 'runtime_sha256': sandbox.runtime_sha256}
    destination = state/str(uuid.uuid4())
    return resolve(task, destination, transport)


def run_contract(manifest: dict, backend: str, name: str, store: ReceiptStore, runtime, *,
                 sandbox=None, credential_ref=None, qualification_id=None, readonly_qualification_id=None,
                 upstream=None, cancel=None) -> dict:
    task = TaskContract.from_dict(manifest.get('task'))
    run = store.create(task.parent_session_id, task.task_id)
    facts = {'kind': 'project-invocation', 'contract_seal': manifest.get('seal'),
             'process': None, 'observations': [], 'artifacts': [], 'wire_requests': 0,
             'parent_acceptance': 'NOT_EVALUATED'}
    try:
        verify(manifest)
        if backend != task.backend or name != task.profile:
            raise RouterError('SEALED_ROUTE_MISMATCH')
        if backend == 'gemini':
            from .backends.gemini import profile as selected_profile
        elif backend == 'kimi':
            selected_profile = profile
        else:
            raise RouterError('BACKEND_NOT_QUALIFIED')
        if (manifest['transport']['profile_identity'] != selected_profile(name).to_dict()
                or manifest['transport']['runtime_identity'] != runtime.to_dict()):
            raise RouterError('SEALED_ROUTE_MISMATCH')
        runtime.verify()
        if task.role == 'implementer' and readonly_qualification_id is None:
            raise RouterError('WRITER_NOT_QUALIFIED', 'M8 requires qualified read-only route')
        if backend == 'gemini':
            if task.role == 'implementer':
                raise RouterError('WRITER_NOT_QUALIFIED')
            if sandbox is None:
                raise RouterError('BLOCKED_CAPABILITY', 'Gemini containment is required')
            from .permissions.gemini_qualification import qualify
            containment = qualify(sandbox, runtime)
        else:
            containment = require_project_containment(sandbox, runtime)
        if manifest['transport'].get('containment') != {
                'image': sandbox.image, 'runtime_sha256': sandbox.runtime_sha256}:
            raise RouterError('SEALED_ROUTE_MISMATCH', 'containment image changed')
        facts['containment'] = containment
        if backend == 'gemini':
            from .gemini_run import execute_gemini
            return execute_gemini(manifest, runtime, sandbox, store, run, facts, credential_ref,
                                  upstream=upstream, cancel=cancel)
        from .project_run import execute_project, verify_smoke
        credential = 'SYNTHETIC_PROVIDER_SECRET'
        if upstream is None:
            from .transport.credentials import load_credential
            from .route_qualification import read_qualification
            qualified, qualification_hash = read_qualification(store, qualification_id)
            facts['route_qualification'] = {'invocation_id': qualification_id, 'sha256': qualification_hash}
            credential = load_credential('kimi', credential_ref, project_root=Path(manifest['project']['root']))
            verify_smoke(qualified, profile(name), runtime, credential)
        if task.role == 'implementer':
            from .holdout_qualification import require_readonly_qualification
            from .writer_run import execute_writer
            require_readonly_qualification(store, readonly_qualification_id, qualification_id)
            facts['readonly_qualification_id'] = readonly_qualification_id
            return execute_writer(manifest, runtime, sandbox, store, run, facts, credential,
                                  upstream=upstream, cancel=cancel)
        return execute_project(manifest, runtime, sandbox, store, run, facts, credential,
                               upstream=upstream, cancel=cancel)
    except RouterError as exc:
        observation = run/'observations.json'
        if observation.exists():
            durable = strict_json(observation.read_bytes())
            observed = durable.get('route', [])
            wires = sum(item.get('wire_started') is True for item in observed) if backend == 'gemini' else len(observed)
            facts.update(observations=observed, wire_requests=wires, outcome='unknown',
                         rejections=durable.get('rejections', []))
        return store.finalize(run, facts | {'classification': exc.code, 'reason': exc.detail})
