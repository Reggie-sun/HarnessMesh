import pytest

from agent_subagent_router.contracts import RouterError
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.image_run import require_live_admission


def test_arbitrary_image_contract_cannot_bootstrap_live(tmp_path):
    store = ReceiptStore(tmp_path/'runs')
    with pytest.raises(RouterError, match='IMAGE_FORMAL_BUDGET_NOT_AUTHORIZED'):
        require_live_admission(store, {}, None, None, None, None)


def test_text_qualification_cannot_admit_image_probe(tmp_path):
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('parent', 'old-text')
    record = store.finalize(run, {'kind': 'route-qualification/v1',
        'classification': 'QUALIFIED', 'artifacts': []})
    with pytest.raises(RouterError, match='IMAGE_PROBE_BINDING_MISMATCH'):
        require_live_admission(store, {}, tmp_path/'absent', record['invocation_id'], None, None)


def test_reference_admission_rejects_global_codex_before_open(monkeypatch, tmp_path):
    from agent_subagent_router.transport import credentials
    called=[]
    monkeypatch.setattr(credentials.os, 'open', lambda *a: called.append(a))
    with pytest.raises(RouterError, match='UNSAFE_CREDENTIAL'):
        credentials.read_credential_reference('openai', tmp_path/'.codex'/'auth.json')
    assert called==[]


def test_missing_credential_records_null_unassessed_metrics_without_execution(tmp_path, monkeypatch):
    from agent_subagent_router import image_run
    task={'backend':'codex','model':'gpt-5.4','profile':'api-bounded','effort':'high'}
    monkeypatch.setattr(image_run, 'verify_image_seal', lambda _: {'task':task,'pins':{},'images':[]})
    monkeypatch.setattr(image_run, 'image_runtime', lambda *a: (object(),{}))
    store=ReceiptStore(tmp_path/'runs')
    receipt=image_run.run_image_contract(tmp_path/'manifest',store,sandbox_config=tmp_path/'config')
    assert receipt['classification']=='CREDENTIAL_REQUIRED'
    assert receipt['wire_requests']==0 and receipt['native'] is None
    assert receipt['semantic_metrics'] is None and receipt['actual_cost_usd'] is None
    assert receipt['authority']=='none' and receipt['eligible'] is False
    assert store.read(receipt['invocation_id'])==receipt


def test_cancelled_image_run_never_reads_credentials(tmp_path, monkeypatch):
    import threading
    from agent_subagent_router import image_run
    task={'backend':'codex','model':'gpt-5.4','profile':'api-bounded','effort':'high'}
    monkeypatch.setattr(image_run, 'verify_image_seal', lambda _: {'task':task,'pins':{},'images':[]})
    monkeypatch.setattr(image_run, 'image_runtime', lambda *a: (object(),{}))
    called=[]
    monkeypatch.setattr(image_run, 'load_credential', lambda *a, **k: called.append(a))
    cancel=threading.Event()
    cancel.set()
    receipt=image_run.run_image_contract(tmp_path/'manifest',ReceiptStore(tmp_path/'runs'),
        sandbox_config=tmp_path/'config',cancel=cancel)
    assert receipt['classification']=='IMAGE_CANCELLED'
    assert receipt['wire_requests']==0 and called==[]
