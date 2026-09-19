"""One sealed Gemini invocation with parent-held OAuth and frozen-read evidence."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import tempfile

from .adapters.gemini import build_invocation, materialize_gemini_projection
from .backends.gemini import profile
from .contracts import RouterError, TaskContract, canonical_bytes, strict_json
from .gemini_evidence import observed_gemini_reads
from .gemini_protocol import decode_gemini
from .receipts import atomic_json, redact
from .resolver import verify
from .transport.gemini_broker import GeminiBroker
from .transport.gemini_oauth import (
    access_token,
    load_oauth_file,
    preflight_code_assist,
    verify_pinned_client_constants,
)


_SYNTHETIC_TOKEN = 'SYNTHETIC_GEMINI_SENTINEL'


def _credential_reference(reference) -> Path:
    if (not isinstance(reference, dict) or set(reference) != {'provider', 'file'}
            or reference.get('provider') != 'gemini' or not isinstance(reference.get('file'), str)):
        raise RouterError('INVALID_CONTRACT', 'Gemini credential reference requires provider and file')
    return Path(reference['file'])


def _verify_pinned_oauth_bundle(runtime) -> None:
    """Bind refresh constants to the same immutable Gemini runtime used for execution."""
    runtime.verify()
    bundle = Path(runtime.package_root)/'node_modules/@google/gemini-cli/bundle/chunk-M6NSK26M.js'
    verify_pinned_client_constants(bundle)


def _consume(store, run: Path, seal: str) -> None:
    consumed = store.root/'consumed-contracts'
    consumed.mkdir(mode=0o700, exist_ok=True)
    try:
        atomic_json(consumed/(seal+'.json'), {'invocation_id': run.name})
    except FileExistsError as exc:
        raise RouterError('CONTRACT_ALREADY_CONSUMED') from exc


def _prompt(task: TaskContract, projection: dict) -> bytes:
    source_map = projection.get('source_map')
    if not isinstance(source_map, list):
        raise RouterError('PROJECTION_SCHEMA_ERROR')
    execution = []
    for item in source_map:
        if not isinstance(item, dict) or set(item) != {'source_path', 'execution_path', 'sha256'}:
            raise RouterError('PROJECTION_SCHEMA_ERROR')
        execution.append({'path': item['source_path'], 'sha256': item['sha256'],
                          'execution_path': '/work/'+item['execution_path']})
    value = {
        'goal': task.goal,
        'instructions': ('Use only read_file, glob, and list_directory. Read evidence through the listed absolute '
                         '/work execution paths. Return only one compact JSON object: no Markdown fences and no '
                         'prose outside that object. It must have exactly the five fields in report_schema. '
                         'evidence_refs must cite original source paths and frozen SHA-256 values; do not claim '
                         'reads not made.'),
        'report_schema': {
            'findings': ['string'],
            'proposed_changes': [{'path': 'original absolute source path', 'summary': 'string'}],
            'evidence_refs': [{'path': 'original absolute source path', 'sha256': '64 lowercase hex',
                               'start_line': 'positive integer', 'end_line': 'positive integer'}],
            'uncertainties': ['string'],
            'questions': ['string'],
        },
        'source_map': execution,
    }
    prompt = canonical_bytes(value)
    if len(prompt) > task.budgets.context_bytes:
        raise RouterError('CONTRACT_TOO_LARGE')
    return prompt


def execute_gemini(manifest, runtime, sandbox, store, run, facts, credential_ref, *, upstream=None, cancel=None):
    """Run exactly one preflighted Gemini invocation; synthetic mode never reads OAuth."""
    task = TaskContract.from_dict(manifest['task'])
    if task.backend != 'gemini':
        raise RouterError('ROUTE_MISMATCH', 'Gemini execution requires Gemini backend')
    route = profile(task.profile)
    if upstream is None:
        _verify_pinned_oauth_bundle(runtime)
        credential = load_oauth_file(_credential_reference(credential_ref),
                                     project_root=Path(manifest['project']['root']))
        token = access_token(credential)
        preflight = preflight_code_assist(token, project=None)
        evidence_kind = 'live'
    else:
        token = _SYNTHETIC_TOKEN
        preflight = {'project': 'synthetic-project', 'tier': 'synthetic', 'proof': 'synthetic_bypass'}
        evidence_kind = 'native-loopback-synthetic'
    verify(manifest)
    if upstream is None:
        _consume(store, run, manifest['seal'])
    with tempfile.TemporaryDirectory(prefix='gemini-project-') as directory:
        root = Path(directory)
        projection = materialize_gemini_projection(manifest, root/'projection')
        prompt = _prompt(task, projection)
        requests = []
        def persist(_):
            store.observe(run, {'route':broker.observations, 'rejections':list(broker.rejections)})
        with GeminiBroker(token, preflight['project'], request_limit=task.budgets.request_limit,
                          wall_seconds=task.budgets.wall_seconds, socket_path=root/'broker.sock',
                          upstream=upstream, on_request=requests.append,
                          on_observation=persist, on_rejection=persist) as broker:
            invocation = build_invocation(runtime, route, broker.capability, prompt, task.budgets)
            process = sandbox.execute(invocation.argv, invocation.env, invocation.stdin, task.budgets,
                                      source=root/'projection', broker_socket=root/'broker.sock',
                                      cancel=cancel, on_stop=broker.revoke)
        secrets = (token.encode(), broker.capability.encode())
        artifacts = [
            store.artifact(run, 'execution-view.json', canonical_bytes(projection), secrets=secrets,
                           media_type='application/json'),
            store.artifact(run, 'stdout.jsonl', b'[QUARANTINED]' if process.truncated else process.stdout,
                           secrets=secrets, media_type='application/x-ndjson'),
            store.artifact(run, 'stderr.txt', b'[QUARANTINED]' if process.truncated else process.stderr,
                           secrets=secrets),
            store.artifact(run, 'broker-observations.json', canonical_bytes(broker.observations), secrets=secrets,
                           media_type='application/json'),
        ]
        reads = []
        try:
            reads = observed_gemini_reads(process.stdout, manifest, projection, requests)
            required = [str(Path(manifest['project']['root'])/path) for path in task.expected_evidence]
            parsed = decode_gemini(process.stdout, required_evidence=required,
                                   source_hashes={source['path']: source['sha256'] for source in manifest['sources']},
                                   observed_reads=reads)
            classification = parsed.classification
            if classification == 'PARSED':
                artifacts.append(store.artifact(run, 'worker-report.json', canonical_bytes(parsed.report),
                                                secrets=secrets, media_type='application/json', producer='worker'))
        except (RouterError, TypeError, KeyError, AttributeError) as exc:
            classification = exc.code if isinstance(exc, RouterError) else 'PROTOCOL_ERROR'
        if process.reason != 'exited' or process.exit_code != 0 or process.truncated:
            classification = 'PROCESS_'+process.reason.upper()
        if not broker.observations:
            classification = 'IDENTITY_UNVERIFIED'
        for observation in broker.observations:
            if observation.get('classification') != 'IDENTITY_VERIFIED':
                classification = observation.get('classification', 'OUTCOME_UNKNOWN')
        if broker.rejections:
            classification = broker.rejections[0]
        result = facts | {
            'kind': 'gemini-invocation', 'classification': classification, 'evidence_kind': evidence_kind,
            'profile': route.to_dict(), 'runtime': runtime.to_dict(), 'preflight': preflight,
            'process': {key: value for key, value in asdict(process).items() if key not in ('stdout', 'stderr')},
            'observations': broker.observations, 'rejections':list(broker.rejections),
            'observed_reads': reads, 'artifacts': artifacts,
            'wire_requests': sum(item.get('wire_started') is True for item in broker.observations),
            'budgets': asdict(task.budgets),
            'parent_acceptance': 'NOT_EVALUATED', 'fallback': 'forbidden', 'orchestration_retries': 0,
            'internal_retry_count': 'unknown',
        }
        filtered, _ = redact(canonical_bytes(result), secrets)
        return store.finalize(run, strict_json(filtered))
