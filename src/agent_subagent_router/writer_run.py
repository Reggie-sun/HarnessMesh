"""Native scoped candidate generation; the host project is never mounted writable."""
from dataclasses import asdict
from pathlib import Path
import stat
import tempfile

from .adapters.project_claude import project_command, project_prompt
from .adapters.projection import materialize_projection
from .backends.kimi import profile
from .contracts import RouterError, TaskContract, canonical_bytes, strict_json
from .evidence import observed_reads
from .protocol import decode_claude
from .receipts import atomic_json, redact
from .transport.broker import Broker
from .writer import prepare_candidate, seal_candidate


TOOLS = ('Read','Glob','Grep','Edit')


def execute_writer(manifest, runtime, sandbox, store, run, facts, credential, *, upstream=None, cancel=None):
    task = TaskContract.from_dict(manifest['task'])
    if len(task.write_paths) != 1:
        raise RouterError('UNSUPPORTED_MULTIFILE_APPLY')
    candidate = prepare_candidate(manifest, run/'candidate')
    record, = [entry for entry in candidate['files'] if entry['owned']]
    if upstream is None:
        consumed = store.root/'consumed-contracts'
        consumed.mkdir(mode=0o700, exist_ok=True)
        try:
            atomic_json(consumed/(manifest['seal']+'.json'), {'invocation_id': run.name})
        except FileExistsError as exc:
            raise RouterError('CONTRACT_ALREADY_CONSUMED') from exc
    overlay = run/'overlay'
    overlay.mkdir(mode=0o700)
    overlay_file = overlay/'owned'
    initial = Path(candidate['candidate_root'])/record['relative']
    overlay_file.write_bytes(initial.read_bytes())
    overlay_file.chmod(record['candidate_mode'])
    route = profile(task.profile)
    with tempfile.TemporaryDirectory(prefix='rt-write-') as folder:
        root = Path(folder)
        projection = materialize_projection(manifest, root/'projection')
        prompt = strict_json(project_prompt(manifest, projection))
        prompt['instructions'] = (
            'Read immutable /work sources for evidence before editing. Read /candidate/owned, then use Edit '
            'only on /candidate/owned to implement the goal. This single file corresponds to '+record['source_path']+'. '
            'Return exactly one JSON object, without prose, markdown or code fences. '
            'findings, uncertainties and questions are arrays of strings; proposed_changes is an array of '
            'objects (for example {"path":"original source_path","description":"change"}), never strings. '
            'Return the exact report_schema JSON object; evidence_refs cite original baseline source_path/hash '
            'from actual Read /work results, never candidate bytes. No Bash, Task, Write, Agent, MCP, network, '
            'nested delegation, host apply, tests, commit, KEEP or claims of parent acceptance. '
            'No other candidate paths, creation/deletion/rename or mode changes are authorized.')
        prompt['candidate'] = {'execution_path': '/candidate/owned', 'source_path': record['source_path']}
        with Broker(route, credential, request_limit=task.budgets.request_limit,
                    wall_seconds=task.budgets.wall_seconds, upstream=upstream, allowed_tools=TOOLS,
                    socket_path=root/'broker.sock',
                    on_observation=lambda observed: store.observe(run, {'route': observed})) as broker:
            argv, env = project_command(runtime, route, root/'runtime', broker.capability, task.budgets)
            argv = list(argv)
            argv[argv.index('--tools')+1] = ','.join(TOOLS)
            argv += ['Read(//candidate/owned)', 'Edit(//candidate/owned)']
            process = sandbox.execute(tuple(argv), env, canonical_bytes(prompt), task.budgets,
                source=root/'projection', broker_socket=root/'broker.sock', candidate_directory=overlay,
                cancel=cancel, on_stop=broker.revoke)
        secrets = (credential.encode(), broker.capability.encode())
        artifacts = [store.artifact(run, 'stdout.jsonl', b'[QUARANTINED]' if process.truncated else process.stdout, secrets=secrets),
                     store.artifact(run, 'stderr.txt', b'[QUARANTINED]' if process.truncated else process.stderr, secrets=secrets),
                     store.artifact(run, 'execution-view.json', canonical_bytes(projection))]
        classification = 'OUTCOME_UNKNOWN'
        sealed = None
        try:
            reads = observed_reads(process.stdout, manifest, projection, ignored_execution_paths=('/candidate/owned',))
            parsed = decode_claude(process.stdout,
                required_evidence=[str(Path(manifest['project']['root'])/p) for p in task.expected_evidence],
                source_hashes={s['path']: s['sha256'] for s in manifest['sources']},
                allowed_tools=TOOLS, observed_reads=reads)
            classification = parsed.classification
            if list(overlay.iterdir()) != [overlay_file] or overlay_file.is_symlink() or not overlay_file.is_file():
                raise RouterError('CANDIDATE_TREE_CHANGED')
            if (stat.S_IMODE(overlay_file.stat().st_mode) != record['candidate_mode']
                    or overlay_file.stat().st_size > task.budgets.context_bytes):
                raise RouterError('CANDIDATE_MODE_OR_SIZE_CHANGED')
            initial.write_bytes(overlay_file.read_bytes())
            sealed = seal_candidate(candidate)
            if classification == 'PARSED':
                artifacts.append(store.artifact(run, 'worker-report.json', canonical_bytes(parsed.report), secrets=secrets, producer='worker'))
        except RouterError as exc:
            classification = exc.code
        if process.reason != 'exited' or process.exit_code != 0 or process.truncated:
            classification = 'PROCESS_'+process.reason.upper()
        if broker.rejections:
            classification = broker.rejections[0]
        if not broker.observations:
            classification = 'IDENTITY_UNVERIFIED'
        for observation in broker.observations:
            if observation['classification'] != 'IDENTITY_VERIFIED':
                classification = observation['classification']
        if sealed is not None:
            artifacts.append(store.artifact(run, 'candidate-manifest.json', canonical_bytes(sealed)))
        result = facts | {'kind': 'candidate-invocation', 'classification': classification,
            'candidate_seal': sealed['seal'] if sealed else None, 'host_project_modified': False,
            'evidence_kind': 'live' if upstream is None else 'native-loopback-synthetic',
            'observations': broker.observations, 'wire_requests': len(broker.observations),
            'artifacts': artifacts, 'process': {k:v for k,v in asdict(process).items() if k not in ('stdout','stderr')},
            'parent_acceptance': 'NOT_EVALUATED', 'fallback': 'forbidden'}
        filtered, _ = redact(canonical_bytes(result), secrets)
        return store.finalize(run, strict_json(filtered))
