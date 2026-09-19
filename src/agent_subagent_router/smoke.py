"""Explicit M1 route-only smoke, separate from project access qualification."""
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import tempfile

from .adapters.claude import build_invocation
from .backends.kimi import profile
from .contracts import Budgets, RouterError, canonical_bytes, strict_json
from .protocol import decode_claude
from .receipts import ReceiptStore, atomic_json, redact
from .supervisor import supervise
from .transport.broker import Broker
from .transport.credentials import load_credential, credential_fingerprint


SMOKE_PROMPT = b'''Return only this JSON object, with no markdown or other content:
{"findings":["route smoke completed"],"proposed_changes":[],"evidence_refs":[],"uncertainties":[],"questions":[]}
Do not use tools. Do not describe your model identity.'''


def _reserve_live_smoke(state: Path, name: str, correction_reason: str | None = None):
    """One real generation per profile in the accepted two-smoke run set."""
    path = state/'m1-live-budget.json'
    fd = os.open(state/'.m1-live-budget.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        previous = strict_json(path.read_bytes()) if path.exists() else {'profiles': []}
        if correction_reason:
            corrections = previous.get('corrections', [])
            if name not in previous['profiles'] or len(corrections) >= 2:
                raise RouterError('LIVE_BUDGET_EXHAUSTED')
            previous['corrections'] = corrections + [{'profile': name, 'reason': correction_reason}]
            atomic_json(path, previous, exclusive=False)
            return
        if name in previous['profiles'] or len(previous['profiles']) >= 2:
            raise RouterError('LIVE_BUDGET_EXHAUSTED', 'new run set requires parent review')
        atomic_json(path, previous | {'profiles': previous['profiles']+[name]}, exclusive=False)
    finally:
        os.close(fd)


def run_smoke(runtime, name: str, store: ReceiptStore, credential_ref: dict | None, *,
              upstream=None, cancel=None, correction_reason=None) -> dict:
    route = profile(name)
    run = store.create('m1-parent', f'm1-smoke-{name}')
    base = {'kind': 'standalone-route-smoke', 'profile': route.to_dict(),
            'runtime': runtime.to_dict(), 'containment': 'NOT_EVALUATED',
            'project_access': False, 'deep_entitlement': 'NOT_EVALUATED',
            'trust_assumption': 'trusted pinned CLI in empty cwd; tools/hooks/MCP disabled',
            'evidence_kind': 'live' if upstream is None else 'native-loopback-synthetic',
            'actual_cost': None, 'parent_acceptance': 'NOT_EVALUATED'}
    if correction_reason:
        base['correction_reason'] = correction_reason
    try:
        runtime.verify()
        credential = load_credential('kimi', credential_ref) if upstream is None else 'SYNTHETIC-PROVIDER-SENTINEL'
        base['credential_fingerprint'] = credential_fingerprint('kimi', credential)
    except RouterError as exc:
        return store.finalize(run, base | {'classification': exc.code, 'process': None,
                              'observations': [], 'artifacts': [], 'wire_requests': 0})
    budget = Budgets(45, 45, 1, 1024*1024, 200000)
    try:
        if upstream is None:
            _reserve_live_smoke(store.root, name, correction_reason)
    except RouterError as exc:
        return store.finalize(run, base | {'classification': exc.code, 'process': None,
                              'observations': [], 'artifacts': [], 'wire_requests': 0})
    with tempfile.TemporaryDirectory(prefix='router-smoke-', dir='/tmp') as temporary:
        with Broker(route, credential, request_limit=budget.request_limit,
                    wall_seconds=budget.wall_seconds, upstream=upstream,
                    on_observation=lambda facts: store.observe(run, {'route': facts})) as broker:
            invocation = build_invocation(runtime, route, Path(temporary)/'runtime',
                                          broker.url, broker.capability, SMOKE_PROMPT, budget)
            process = supervise(invocation, cancel=cancel, on_stop=broker.revoke)
        # Broker is revoked, drained/frozen, and cannot publish after finalization.
        secrets = (credential.encode(), broker.capability.encode())
        stdout = b'[QUARANTINED: output limit]' if process.truncated else process.stdout
        stderr = b'[QUARANTINED: output limit]' if process.truncated else process.stderr
        artifacts = [store.artifact(run, 'stdout.jsonl', stdout, secrets=secrets,
                                   media_type='application/x-ndjson'),
                     store.artifact(run, 'stderr.txt', stderr, secrets=secrets)]
        parsed = decode_claude(process.stdout)
        classification = parsed.classification
        if process.reason != 'exited' or process.exit_code != 0:
            classification = 'PROCESS_'+process.reason.upper()
        if broker.rejections:
            classification = broker.rejections[0]
        if not broker.observations:
            classification = 'IDENTITY_UNVERIFIED' if not broker.rejections else broker.rejections[0]
        for observation in broker.observations:
            if observation['classification'] != 'IDENTITY_VERIFIED':
                classification = observation['classification']
        if classification == 'PARSED':
            artifacts.append(store.artifact(run, 'worker-report.json', canonical_bytes(parsed.report),
                                           secrets=secrets, media_type='application/json', producer='worker'))
        facts = {k: v for k, v in asdict(process).items() if k not in ('stdout', 'stderr')}
        final = base | {'classification': classification, 'process': facts,
                         'observations': broker.observations, 'rejections': broker.rejections,
                         'artifacts': artifacts, 'wire_requests': len(broker.observations),
                         'budgets': asdict(budget), 'orchestration_retries': 0,
                         'internal_retry_count': 'unknown', 'fallback': 'forbidden'}
        filtered, _ = redact(canonical_bytes(final), secrets)
        return store.finalize(run, strict_json(filtered))
