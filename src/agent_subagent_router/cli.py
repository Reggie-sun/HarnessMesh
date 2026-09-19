import argparse
import json
from pathlib import Path
import signal
import sys
import threading

from . import __version__
from .api import inspect_task, run_contract
from .contracts import RouterError, TaskContract, strict_json
from .permissions.containment import probe_containment
from .receipts import ReceiptStore
from .runtime_config import installed_runtime, installed_sandbox, installed_backend_runtime
from .smoke import run_smoke


def default_state():
    return Path.home()/'.local/state/agent-subagent-router'


def main(argv=None):
    parser = argparse.ArgumentParser(prog='subagent')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--state', type=Path, default=default_state())
    parser.add_argument('--sandbox-config', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect', help='Seal exact local inputs; no provider calls')
    inspect.add_argument('--cwd', required=True)
    inspect.add_argument('--task', type=Path, required=True)
    run = commands.add_parser('run', help='Run only a qualified sealed route')
    run.add_argument('--contract', type=Path, required=True)
    run.add_argument('--backend', required=True)
    run.add_argument('--profile', required=True)
    run.add_argument('--live', required=True, action='store_true')
    run.add_argument('--credential-ref', type=Path, required=True)
    run.add_argument('--qualification', help='Required canonical route qualification for Kimi')
    run.add_argument('--readonly-qualification')
    receipt = commands.add_parser('receipt')
    receipt.add_argument('invocation_id')
    smoke = commands.add_parser('smoke', help='M1 fixed-input route smoke; requires explicit --live')
    smoke.add_argument('--profile', choices=('worker', 'deep'), required=True)
    smoke.add_argument('--live', action='store_true', required=True)
    smoke.add_argument('--credential-ref', type=Path)
    qualify = commands.add_parser('qualify-route', help='Bind canonical smoke to current credential and entitlement')
    qualify.add_argument('--smoke', required=True)
    qualify.add_argument('--credential-ref', type=Path, required=True)
    qualify.add_argument('--entitlement', type=Path)
    test = commands.add_parser('candidate-test')
    test.add_argument('--invocation', required=True)
    test.add_argument('--argv-json', type=Path, required=True)
    apply = commands.add_parser('candidate-apply')
    apply.add_argument('--invocation', required=True)
    apply.add_argument('--test', required=True)
    doctor = commands.add_parser('doctor', help='Local capabilities, no credential values or model calls')
    doctor.add_argument('--backend', choices=('kimi', 'gemini'), default='kimi')
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            evidence = probe_containment()
            runtime = None
            try:
                runtime = installed_runtime() if args.backend == 'kimi' else installed_backend_runtime(args.backend)
                runtime.verify()
                runtime_data = runtime.to_dict()
            except RouterError as exc:
                runtime_data = {'classification': exc.code}
            try:
                from .permissions.containment import require_project_containment
                if runtime is None:
                    raise RouterError('RUNTIME_MISSING')
                sandbox = installed_sandbox(backend=args.backend, config=args.sandbox_config)
                if args.backend == 'gemini':
                    from .permissions.gemini_qualification import qualify
                    evidence = qualify(sandbox, runtime)
                else:
                    evidence = require_project_containment(sandbox, runtime)
            except RouterError as exc:
                evidence = evidence | {'qualified': False, 'docker_classification': exc.code}
            output = {'backend': args.backend, 'runtime': runtime_data, 'containment': evidence,
                      'project_routes': 'CONTAINMENT_QUALIFIED' if evidence['qualified'] else 'BLOCKED_CAPABILITY',
                      'writer': 'REQUIRES_READONLY_QUALIFICATION_AND_PARENT_TEST',
                      'second_backend': 'REQUIRES_INDEPENDENT_QUALIFICATION'}
            code = 0 if evidence['qualified'] else 2
        elif args.command == 'inspect':
            task = TaskContract.from_dict(strict_json(args.task.read_bytes()))
            if Path(args.cwd).resolve() != Path(task.cwd).resolve():
                raise RouterError('CWD_MISMATCH')
            sealed = inspect_task(task, args.state/'contracts', installed_backend_runtime(task.backend),
                                  sandbox=installed_sandbox(task.backend, args.sandbox_config))
            output = {'seal': sealed['seal'], 'contract': str(Path(sealed['snapshot_root'])/'manifest.json'),
                      'source_count': len(sealed['sources']), 'project_access': 'SEALED_ONLY'}
            code = 0
        else:
            store = ReceiptStore(args.state/'runs')
            if args.command == 'receipt':
                output = store.read(args.invocation_id)
                code = 0
            elif args.command == 'run':
                cancelled = threading.Event()
                previous = {sig: signal.signal(sig, lambda *_: cancelled.set())
                            for sig in (signal.SIGINT, signal.SIGTERM)}
                try:
                    output = run_contract(strict_json(args.contract.read_bytes()), args.backend,
                                          args.profile, store, installed_backend_runtime(args.backend),
                                          sandbox=installed_sandbox(args.backend, args.sandbox_config),
                                          credential_ref=strict_json(args.credential_ref.read_bytes()),
                                          qualification_id=args.qualification,
                                          readonly_qualification_id=args.readonly_qualification, cancel=cancelled)
                finally:
                    for sig, handler in previous.items():
                        signal.signal(sig, handler)
                code = 0 if output['classification'] == 'PARSED' else 2
            elif args.command == 'qualify-route':
                from .route_qualification import qualify_route
                output = qualify_route(store, args.smoke, strict_json(args.credential_ref.read_bytes()),
                    entitlement=strict_json(args.entitlement.read_bytes()) if args.entitlement else None)
                code = 0
            elif args.command == 'candidate-test':
                from .candidate_gates import test_candidate
                output = test_candidate(store, args.invocation, installed_sandbox(config=args.sandbox_config),
                                        tuple(strict_json(args.argv_json.read_bytes())))
                code = 0 if output['classification'] == 'PASS' else 2
            elif args.command == 'candidate-apply':
                from .candidate_gates import apply_tested_candidate
                output = apply_tested_candidate(store, args.invocation, args.test)
                code = 0 if output['classification'] == 'APPLIED' else 2
            else:
                ref = strict_json(args.credential_ref.read_bytes()) if args.credential_ref else None
                cancelled = threading.Event()
                previous = {sig: signal.signal(sig, lambda *_: cancelled.set())
                            for sig in (signal.SIGINT, signal.SIGTERM)}
                try:
                    output = run_smoke(installed_runtime(), args.profile, store, ref, cancel=cancelled)
                finally:
                    for sig, handler in previous.items():
                        signal.signal(sig, handler)
                code = 0 if output['classification'] == 'PARSED' else 2
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return code
    except RouterError as exc:
        print(json.dumps({'classification': exc.code, 'detail': exc.detail}), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'classification': 'LOCAL_INPUT_ERROR', 'type': type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
