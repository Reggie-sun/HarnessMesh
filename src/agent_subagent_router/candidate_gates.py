"""Canonical candidate -> contained parent test -> explicit parent apply boundary."""
from pathlib import Path

from .contracts import Budgets, RouterError, canonical_bytes, hash_bytes, strict_json
from .writer import _validate_sealed, _verify_candidate_seal, _verify_immutable_tree, apply_candidate


def candidate_from_receipt(store, identifier):
    receipt = store.read(identifier)
    if receipt.get('kind') != 'candidate-invocation' or receipt.get('classification') != 'PARSED':
        raise RouterError('CANDIDATE_NOT_QUALIFIED')
    if not any(a['path'] == 'candidate-manifest.json' for a in receipt['artifacts']):
        raise RouterError('CANDIDATE_NOT_QUALIFIED')
    sealed = strict_json((store.root/identifier/'candidate-manifest.json').read_bytes())
    _validate_sealed(sealed)
    _verify_candidate_seal(sealed)
    if receipt.get('candidate_seal') != sealed['seal']:
        raise RouterError('CANDIDATE_BINDING_MISMATCH')
    _verify_immutable_tree(Path(sealed['sealed_root']), sealed['files'])
    return sealed


def test_candidate(store, identifier, sandbox, argv, *, budgets=None):
    sealed = candidate_from_receipt(store, identifier)
    if (not isinstance(argv, tuple) or len(argv) < 2
            or argv[0] not in ('/usr/local/bin/python3', '/opt/node/bin/node', '/opt/node/bin/npm')
            or any(not isinstance(a, str) or not a for a in argv)
            or any(a in ('-c','--eval','-e',';','&&','||','|') for a in argv)):
        raise RouterError('INVALID_TEST_COMMAND')
    budget = budgets or Budgets(120, 120, 1, 2000000, 100000)
    run = store.create('parent-test', 'candidate-gate')
    process = sandbox.execute(argv, {'PATH': '/usr/local/bin:/opt/node/bin:/usr/bin:/bin',
        'HOME': '/home/worker', 'TMPDIR': '/tmp', 'PYTHONPATH': '/work/src',
        'PYTHONDONTWRITEBYTECODE': '1', 'CI': 'true'}, b'', budget,
        source=Path(sealed['sealed_root'])/'project')
    _verify_immutable_tree(Path(sealed['sealed_root']), sealed['files'])
    artifacts = [store.artifact(run, 'stdout.txt', process.stdout), store.artifact(run, 'stderr.txt', process.stderr)]
    return store.finalize(run, {'kind': 'candidate-test', 'classification': 'PASS' if process.exit_code == 0
        and process.reason == 'exited' and not process.truncated else 'FAIL',
        'candidate_invocation_id': identifier, 'candidate_seal': sealed['seal'],
        'image': sandbox.image, 'argv': list(argv), 'exit_code': process.exit_code,
        'reason': process.reason, 'broker': False, 'network': False, 'artifacts': artifacts})


def apply_tested_candidate(store, identifier, test_id):
    sealed = candidate_from_receipt(store, identifier)
    test = store.read(test_id)
    if (test.get('kind') != 'candidate-test' or test.get('classification') != 'PASS'
            or test.get('candidate_invocation_id') != identifier or test.get('candidate_seal') != sealed['seal']
            or test.get('broker') is not False or test.get('network') is not False):
        raise RouterError('TEST_BINDING_MISMATCH')
    run = store.create('parent-apply', 'candidate-apply')
    binding = {'candidate_invocation_id': identifier, 'candidate_seal': sealed['seal'],
               'test_invocation_id': test_id, 'test_sha256': hash_bytes(canonical_bytes(test))}
    store.observe(run, {'phase': 'before-apply', **binding})
    result = apply_candidate(sealed, verified_candidate_hash=test['candidate_seal'])
    store.observe(run, {'phase': 'after-apply', **binding, 'application': result})
    return store.finalize(run, {'kind': 'candidate-apply', 'candidate_invocation_id': identifier,
        'test_invocation_id': test_id, 'test_sha256': hash_bytes(canonical_bytes(test)),
        'classification': result['classification'], 'application': result,
        'project_native_post_apply': 'NOT_EVALUATED', 'artifacts': []})
