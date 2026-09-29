import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import signal
import sys
import threading

from . import __version__
from .api import inspect_task, run_contract
from .contracts import MIN_KIMI_LIVE_OUTPUT_BYTES, RouterError, TaskContract, strict_json
from .permissions.containment import probe_containment
from .receipts import ReceiptStore
from .runtime_config import installed_runtime, installed_sandbox, installed_backend_runtime
from .smoke import run_smoke


def default_state():
    return Path.home()/'.local/state/agent-subagent-router'


@contextmanager
def _image_cancellation():
    cancelled = threading.Event()
    previous = {sig: signal.signal(sig, lambda *_: cancelled.set())
                for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield cancelled
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='subagent')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--state', type=Path, default=default_state())
    parser.add_argument('--sandbox-config', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect', help='Seal exact local inputs; no provider calls')
    inspect.add_argument('--cwd', required=True)
    inspect.add_argument('--task', type=Path, required=True)
    images = commands.add_parser('inspect-images', help='Seal independent PNG inputs; no provider calls')
    images.add_argument('--task', type=Path, required=True)
    image_probe = commands.add_parser('prepare-image-probe', help='Freeze router-owned random images; no provider calls')
    image_probe.add_argument('--backend', choices=('kimi', 'codex', 'minimax'), required=True)
    image_probe.add_argument('--refs-json', type=Path, required=True)
    image_probe.add_argument('--model', required=True)
    image_probe.add_argument('--profile', required=True)
    image_probe.add_argument('--effort', required=True)
    image_qualify = commands.add_parser('qualify-image-route', help='Image capability gate, distinct from project routes')
    image_qualify.add_argument('--probe', required=True)
    image_mode = image_qualify.add_mutually_exclusive_group(required=True)
    image_mode.add_argument('--native-only', action='store_true')
    image_mode.add_argument('--live', action='store_true')
    image_qualify.add_argument('--credential-ref', type=Path)
    image_qualify.add_argument('--budget-receipt')
    image_run = commands.add_parser('run-images', help='Image execution; formal budget remains blocked')
    image_run.add_argument('--contract', type=Path, required=True)
    image_run.add_argument('--live', action='store_true', required=True)
    image_run.add_argument('--credential-ref', type=Path, required=True)
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
        elif args.command == 'inspect-images':
            from .image_inspect import inspect_images
            output = inspect_images(strict_json(args.task.read_bytes()), args.state/'image-contracts',
                                    sandbox_config=args.sandbox_config)
            code = 0
        elif args.command in ('prepare-image-probe', 'qualify-image-route', 'run-images'):
            if not args.sandbox_config:
                raise RouterError('IMAGE_RUNTIME_CONFIG_REQUIRED')
            store = ReceiptStore(args.state/'runs')
            from .transport.credentials import read_credential_reference
            if args.command == 'prepare-image-probe':
                from .image_probe import prepare_probe
                output = prepare_probe(store, backend=args.backend, model=args.model,
                    profile=args.profile, effort=args.effort,
                    refs=strict_json(args.refs_json.read_bytes()), sandbox_config=args.sandbox_config)
                code = 0
            elif args.command == 'qualify-image-route':
                if args.native_only:
                    from .image_conformance import native_conformance
                    with _image_cancellation() as cancelled:
                        output = native_conformance(store, args.probe, sandbox_config=args.sandbox_config,
                                                    cancel=cancelled)
                    code = 0 if output['classification'] == 'ENGINEERING_CONFORMANCE_COMPLETE' else 2
                else:
                    from .image_qualification import qualify_image_route
                    probe_task = store.read(args.probe)
                    # Probe input facts do not duplicate backend; read its sealed task.
                    from .image_seal import verify_image_seal
                    from .image_contract import IMAGE_PROVIDERS
                    provider = IMAGE_PROVIDERS[verify_image_seal(Path(probe_task['manifest']))['task']['backend']]
                    with _image_cancellation() as cancelled:
                        output = qualify_image_route(store, args.probe, sandbox_config=args.sandbox_config,
                            credential_ref=read_credential_reference(provider, args.credential_ref) if args.credential_ref else None,
                            budget_id=args.budget_receipt, cancel=cancelled)
                    code = 0 if output['classification'] == 'QUALIFIED' else 2
            else:
                from .image_run import run_image_contract
                from .image_seal import verify_image_seal
                from .image_contract import IMAGE_PROVIDERS
                provider = IMAGE_PROVIDERS[verify_image_seal(args.contract)['task']['backend']]
                with _image_cancellation() as cancelled:
                    output = run_image_contract(args.contract, store, sandbox_config=args.sandbox_config,
                        credential_ref=read_credential_reference(provider, args.credential_ref), cancel=cancelled)
                code = 0 if output['classification'] == 'IMAGE_NATIVE_COMPLETE' else 2
        elif args.command == 'inspect':
            task = TaskContract.from_dict(strict_json(args.task.read_bytes()))
            if Path(args.cwd).resolve() != Path(task.cwd).resolve():
                raise RouterError('CWD_MISMATCH')
            sealed = inspect_task(task, args.state/'contracts', installed_backend_runtime(task.backend),
                                  sandbox=installed_sandbox(task.backend, args.sandbox_config))
            output = {'seal': sealed['seal'], 'contract': str(Path(sealed['snapshot_root'])/'manifest.json'),
                      'source_count': len(sealed['sources']), 'project_access': 'SEALED_ONLY',
                      'frozen_source_paths': sorted(s['path'] for s in sealed['sources']),
                      'budgets': sealed['task']['budgets']}
            if 'resource_policy' in sealed['transport']:
                output['route'] = {'backend': sealed['task']['backend'],
                                   'profile': sealed['task']['profile'],
                                   'identity': sealed['transport']['profile_identity']}
                output['resource_policy'] = sealed['transport']['resource_policy']
            if (task.backend == 'kimi'
                    and sealed['task']['budgets']['output_bytes'] < MIN_KIMI_LIVE_OUTPUT_BYTES):
                output['warnings'] = [{'classification': 'OUTPUT_BUDGET_TOO_SMALL',
                                       'minimum_output_bytes': MIN_KIMI_LIVE_OUTPUT_BYTES,
                                       'live_execution': 'BLOCKED'}]
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
