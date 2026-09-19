"""One sealed read-only invocation. Parent qualification and acceptance remain separate."""
from dataclasses import asdict
from pathlib import Path
import tempfile

from .adapters.project_claude import TOOLS, project_command, project_prompt
from .adapters.projection import materialize_projection
from .backends.kimi import profile
from .contracts import RouterError, TaskContract, canonical_bytes, strict_json
from .evidence import observed_reads
from .protocol import decode_claude
from .receipts import atomic_json, redact
from .resolver import verify
from .transport.broker import Broker
from .transport.credentials import credential_fingerprint


def verify_smoke(receipt, route, runtime, credential=None):
    if (receipt.get('classification') != 'PARSED' or receipt.get('evidence_kind') != 'live'
            or receipt.get('profile') != route.to_dict() or receipt.get('runtime') != runtime.to_dict()
            or not receipt.get('observations')
            or any(o.get('classification') != 'IDENTITY_VERIFIED'
                   or o.get('proof') != 'authenticated_endpoint_declaration'
                   for o in receipt['observations'])):
        raise RouterError('ROUTE_NOT_QUALIFIED', 'matching live M1 route receipt required')
    if route.name == 'deep' and receipt.get('deep_entitlement') != 'VERIFIED':
        raise RouterError('ENTITLEMENT_UNVERIFIED', 'account-specific 1M entitlement required')
    if route.name == 'deep':
        from .route_qualification import validate_entitlement
        validate_entitlement(receipt.get('account_entitlement'))
    if credential is not None and receipt.get('credential_fingerprint') != credential_fingerprint('kimi', credential):
        raise RouterError('QUALIFICATION_CREDENTIAL_MISMATCH')


def execute_project(manifest, runtime, sandbox, store, run, facts, credential,
                    *, upstream=None, cancel=None):
    task = TaskContract.from_dict(manifest['task'])
    route = profile(task.profile)
    if upstream is None:
        consumed = store.root/'consumed-contracts'
        consumed.mkdir(mode=0o700, exist_ok=True)
        try:
            atomic_json(consumed/(manifest['seal']+'.json'), {'invocation_id': run.name})
        except FileExistsError as exc:
            raise RouterError('CONTRACT_ALREADY_CONSUMED') from exc
    with tempfile.TemporaryDirectory(prefix='rt-project-') as temporary:
        root = Path(temporary)
        projection = materialize_projection(manifest, root/'projection')
        prompt = project_prompt(manifest, projection)
        if len(prompt) > task.budgets.context_bytes:
            raise RouterError('CONTRACT_TOO_LARGE')
        with Broker(route, credential, request_limit=task.budgets.request_limit,
                    wall_seconds=task.budgets.wall_seconds, upstream=upstream,
                    allowed_tools=TOOLS, socket_path=root/'broker.sock',
                    on_observation=lambda observed: store.observe(run, {'route': observed})) as broker:
            argv, env = project_command(runtime, route, root/'runtime', broker.capability, task.budgets)
            process = sandbox.execute(argv, env, prompt, task.budgets,
                                      source=root/'projection', broker_socket=root/'broker.sock',
                                      cancel=cancel, on_stop=broker.revoke)
        secrets = (credential.encode(), broker.capability.encode())
        artifacts = [store.artifact(run, 'execution-view.json', canonical_bytes(projection),
                                   media_type='application/json'),
                     store.artifact(run, 'stdout.jsonl', b'[QUARANTINED]' if process.truncated else process.stdout,
                                    secrets=secrets, media_type='application/x-ndjson'),
                     store.artifact(run, 'stderr.txt', b'[QUARANTINED]' if process.truncated else process.stderr,
                                    secrets=secrets)]
        reads = []
        try:
            verify(manifest)
            reads = observed_reads(process.stdout, manifest, projection)
            required = [str(Path(manifest['project']['root'])/path) for path in task.expected_evidence]
            parsed = decode_claude(process.stdout, required_evidence=required,
                source_hashes={s['path']: s['sha256'] for s in manifest['sources']},
                allowed_tools=TOOLS, observed_reads=reads)
            classification = parsed.classification
            if classification == 'PARSED':
                artifacts.append(store.artifact(run, 'worker-report.json', canonical_bytes(parsed.report),
                    secrets=secrets, media_type='application/json', producer='worker'))
        except (RouterError, TypeError, AttributeError, KeyError) as exc:
            classification = exc.code if isinstance(exc, RouterError) else 'PROTOCOL_ERROR'
        if process.reason != 'exited' or process.exit_code != 0:
            classification = 'PROCESS_'+process.reason.upper()
        if broker.rejections:
            classification = broker.rejections[0]
        if not broker.observations:
            classification = 'IDENTITY_UNVERIFIED'
        for observation in broker.observations:
            if observation['classification'] != 'IDENTITY_VERIFIED':
                classification = observation['classification']
        final = facts | {'classification': classification,
            'evidence_kind': 'live' if upstream is None else 'native-loopback-synthetic',
            'process': {k: v for k, v in asdict(process).items() if k not in ('stdout', 'stderr')},
            'observations': broker.observations, 'observed_reads': reads, 'artifacts': artifacts,
            'wire_requests': len(broker.observations), 'budgets': asdict(task.budgets),
            'fallback': 'forbidden', 'orchestration_retries': 0, 'internal_retry_count': 'unknown'}
        filtered, _ = redact(canonical_bytes(final), secrets)
        return store.finalize(run, strict_json(filtered))
