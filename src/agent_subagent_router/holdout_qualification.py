"""Parent assessment binding for the frozen paired read-only experiment."""
from pathlib import Path
from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .resolver import verify


def _validate_assessments(store, runset, assessments, parent_gate_ids):
    if hash_bytes(canonical_bytes({k: v for k, v in runset.items() if k != 'sha256'})) != runset.get('sha256'):
        raise RouterError('RUN_SET_CHANGED')
    expected = {item['task_id']: item for item in runset['runs']}
    if len(expected) != 8 or len(assessments) != 8 or {a['task_id'] for a in assessments} != set(expected):
        raise RouterError('HOLDOUT_INCOMPLETE')
    sources = []
    pairs = {}
    for assessment in assessments:
        task = expected[assessment['task_id']]
        baseline = strict_json(Path(task['contract']).read_bytes())
        verify(baseline, check_host=False)
        if (baseline['seal'] != task['contract_seal'] or baseline['task']['task_id'] != task['task_id']
                or baseline['task']['profile'] != task['profile']
                or Path(baseline['project']['root']).name != task['project']):
            raise RouterError('HOLDOUT_BINDING_MISMATCH')
        if (assessment.get('usable') is not True or assessment.get('blocking_questions')
                or not assessment.get('verified_claims') or 'unsupported_claims' not in assessment):
            raise RouterError('HOLDOUT_NOT_USABLE')
        receipt = store.read(assessment['receipt_id'])
        if (receipt.get('classification') != 'PARSED' or receipt.get('evidence_kind') != 'live'
                or receipt.get('kind') != 'project-invocation' or not receipt.get('route_qualification')
                or not any(a['path'] == 'worker-report.json' for a in receipt['artifacts'])):
            raise RouterError('HOLDOUT_NOT_QUALIFIED')
        # An explicitly reserved correction has a new task ID/seal, never overwrites the first receipt.
        if receipt['task_id'] != task['task_id']:
            if (receipt['task_id'] != task['task_id']+'-correction'
                    or not assessment.get('correction_of')):
                raise RouterError('HOLDOUT_BINDING_MISMATCH')
            original = store.read(assessment['correction_of'])
            if original['task_id'] != task['task_id'] or original['contract_seal'] != task['contract_seal']:
                raise RouterError('HOLDOUT_BINDING_MISMATCH')
            corrected = assessment.get('correction_manifest')
            if not isinstance(corrected, dict):
                raise RouterError('CORRECTION_BINDING_MISMATCH')
            verify(corrected, check_host=False)
            if (baseline['seal'] != task['contract_seal'] or corrected['seal'] != receipt['contract_seal']
                    or corrected['task'] != baseline['task'] | {'task_id': receipt['task_id']}
                    or any(corrected[k] != baseline[k] for k in ('sources','project','transport'))
                    or original['route_qualification'] != receipt['route_qualification']):
                raise RouterError('CORRECTION_BINDING_MISMATCH')
        elif receipt['contract_seal'] != task['contract_seal']:
            raise RouterError('HOLDOUT_BINDING_MISMATCH')
        pairs.setdefault(baseline['project']['root'], []).append(baseline['task']['profile'])
        sources.append({'task_id': task['task_id'], 'invocation_id': receipt['invocation_id'],
                        'sha256': hash_bytes(canonical_bytes(receipt)),
                        'route_qualification': receipt['route_qualification']})
    if len(pairs) != 2 or any(sorted(v) != ['deep','deep','worker','worker'] for v in pairs.values()):
        raise RouterError('HOLDOUT_INCOMPLETE')
    gates = []
    for identifier in parent_gate_ids:
        gate = store.read(identifier)
        if gate.get('kind') != 'parent-test' or gate.get('classification') != 'PASS' or gate.get('broker') is not False:
            raise RouterError('PARENT_TEST_FAILED')
        gates.append({'invocation_id': identifier, 'sha256': hash_bytes(canonical_bytes(gate))})
    if not gates:
        raise RouterError('PARENT_TEST_REQUIRED')
    return sources, gates


def qualify_holdouts(store, runset, assessments, parent_gate_ids):
    sources, gates = _validate_assessments(store, runset, assessments, parent_gate_ids)
    run = store.create('parent-acceptance', 'paired-readonly-qualification')
    artifacts = [store.artifact(run, 'run-set.json', canonical_bytes(runset), media_type='application/json'),
                 store.artifact(run, 'parent-assessment.json', canonical_bytes(assessments), media_type='application/json')]
    return store.finalize(run, {'kind': 'readonly-qualification', 'classification': 'QUALIFIED',
        'policy_version': 2, 'profiles': ['worker','deep'], 'run_set_sha256': runset['sha256'], 'sources': sources,
        'parent_gates': gates, 'artifacts': artifacts, 'scope': 'frozen eight-task experiment only'})


def require_readonly_qualification(store, identifier, route_qualification_id):
    if not isinstance(identifier, str):
        raise RouterError('READONLY_NOT_QUALIFIED')
    receipt = store.read(identifier)
    if (receipt.get('kind') != 'readonly-qualification' or receipt.get('classification') != 'QUALIFIED'
            or receipt.get('policy_version') != 2):
        raise RouterError('READONLY_NOT_QUALIFIED')
    runset = strict_json((store.root/identifier/'run-set.json').read_bytes())
    assessments = strict_json((store.root/identifier/'parent-assessment.json').read_bytes())
    sources, gates = _validate_assessments(store, runset, assessments,
                                         [g['invocation_id'] for g in receipt['parent_gates']])
    if sources != receipt['sources'] or gates != receipt['parent_gates']:
        raise RouterError('READONLY_NOT_QUALIFIED')
    route_ids = set()
    if len(receipt.get('sources', [])) != 8:
        raise RouterError('READONLY_NOT_QUALIFIED')
    for source in receipt['sources']:
        original = store.read(source['invocation_id'])
        if hash_bytes(canonical_bytes(original)) != source['sha256'] or original['classification'] != 'PARSED':
            raise RouterError('READONLY_NOT_QUALIFIED')
        route_ids.add(source['route_qualification']['invocation_id'])
    if route_qualification_id not in route_ids:
        raise RouterError('READONLY_ROUTE_MISMATCH')
    return receipt
