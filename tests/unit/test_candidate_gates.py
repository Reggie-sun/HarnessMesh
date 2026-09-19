import pytest

from agent_subagent_router import candidate_gates
from agent_subagent_router.contracts import RouterError
from agent_subagent_router.receipts import ReceiptStore


def bound_test(store):
    run = store.create('parent-test', 'candidate-gate')
    return store.finalize(run, {'kind': 'candidate-test', 'classification': 'PASS',
        'candidate_invocation_id': 'candidate', 'candidate_seal': 'seal',
        'broker': False, 'network': False, 'artifacts': []})


@pytest.mark.parametrize('field,value', [('kind','other'), ('classification','FAIL'),
    ('candidate_invocation_id','other'), ('candidate_seal','other'), ('broker',True), ('network',True)])
def test_wrong_test_binding_never_reaches_apply(tmp_path, monkeypatch, field, value):
    store = ReceiptStore(tmp_path/'runs')
    receipt = bound_test(store)
    receipt[field] = value
    monkeypatch.setattr(store, 'read', lambda _: receipt)
    monkeypatch.setattr(candidate_gates, 'candidate_from_receipt', lambda *_: {'seal': 'seal'})
    def forbidden(*args, **kwargs):
        raise AssertionError('must not apply')
    monkeypatch.setattr(candidate_gates, 'apply_candidate', forbidden)
    with pytest.raises(RouterError, match='TEST_BINDING_MISMATCH'):
        candidate_gates.apply_tested_candidate(store, 'candidate', receipt['invocation_id'])


def test_finalization_failure_retains_durable_apply_association(tmp_path, monkeypatch):
    store = ReceiptStore(tmp_path/'runs')
    receipt = bound_test(store)
    monkeypatch.setattr(candidate_gates, 'candidate_from_receipt', lambda *_: {'seal':'seal'})
    def apply(*args, **kwargs):
        run = next(p for p in store.root.iterdir() if p.name != receipt['invocation_id'])
        observed = store.recover(run.name)['last_observations']
        assert observed['phase'] == 'before-apply'
        assert observed['candidate_invocation_id'] == 'candidate'
        assert observed['test_invocation_id'] == receipt['invocation_id']
        return {'classification':'APPLIED', 'recovery_path':'retained-object'}
    monkeypatch.setattr(candidate_gates, 'apply_candidate', apply)
    def fail(*_):
        raise OSError('final receipt write fault')
    monkeypatch.setattr(store, 'finalize', fail)
    with pytest.raises(OSError):
        candidate_gates.apply_tested_candidate(store, 'candidate', receipt['invocation_id'])
    run = next(p for p in store.root.iterdir() if p.name != receipt['invocation_id'])
    recovered = store.recover(run.name)
    assert recovered['outcome'] == 'unknown' and recovered['replay_allowed'] is False
    assert recovered['last_observations']['phase'] == 'after-apply'
    assert recovered['last_observations']['application']['recovery_path'] == 'retained-object'
