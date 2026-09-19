import copy
import json
from types import SimpleNamespace

import pytest

from agent_subagent_router import holdout_qualification as qualification
from agent_subagent_router.contracts import RouterError, canonical_bytes, hash_bytes


def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(qualification, 'verify', lambda _, **__: None)
    receipts, runs, assessments = {}, [], []
    for index in range(8):
        name='task-'+str(index)
        profile='worker' if index%2==0 else 'deep'
        manifest={'seal':name, 'task':{'task_id':name, 'profile':profile, 'expected_evidence':['a.py']},
                  'sources':[{'sha256':'a'*64}], 'project':{'root':'p'+str(index//4)},
                  'transport':{'profile':profile}}
        path=tmp_path/(name+'.json')
        path.write_text(json.dumps(manifest))
        runs.append({'task_id':name,'profile':profile,'project':'p'+str(index//4),
                     'contract':str(path),'contract_seal':name})
        receipt={'invocation_id':name,'task_id':name,'contract_seal':name,'classification':'PARSED',
                 'kind':'project-invocation','evidence_kind':'live',
                 'route_qualification':{'invocation_id':profile,'sha256':profile},
                 'artifacts':[{'path':'worker-report.json'}]}
        receipts[name]=receipt
        assessments.append({'task_id':name,'receipt_id':name,'usable':True,
                            'verified_claims':['source checked'],'unsupported_claims':[],'blocking_questions':[]})
    baseline=json.loads((tmp_path/'task-1.json').read_text())
    correction=copy.deepcopy(baseline)
    correction['task']['task_id']='task-1-correction'
    correction['seal']='correction-seal'
    receipts['corrected']=receipts['task-1']|{'invocation_id':'corrected','task_id':'task-1-correction','contract_seal':'correction-seal'}
    receipts['task-1']['classification']='REPORT_SCHEMA_ERROR'
    assessments[1].update(receipt_id='corrected',correction_of='task-1',correction_manifest=correction)
    receipts['gate']={'kind':'parent-test','classification':'PASS','broker':False}
    runset={'runs':runs}
    runset['sha256']=hash_bytes(canonical_bytes(runset))
    return SimpleNamespace(read=lambda name:receipts[name]),runset,assessments,receipts


def test_exact_correction_keeps_pair_and_source_contract(tmp_path,monkeypatch):
    store,runset,assessments,_=fixture(tmp_path,monkeypatch)
    sources,gates=qualification._validate_assessments(store,runset,assessments,['gate'])
    assert len(sources)==8 and len(gates)==1


@pytest.mark.parametrize('mutation',['profile','sources','evidence','route','seal'])
def test_same_correction_task_name_cannot_replace_scope_or_profile(tmp_path,monkeypatch,mutation):
    store,runset,assessments,receipts=fixture(tmp_path,monkeypatch)
    changed=assessments[1]['correction_manifest']
    if mutation=='profile':
        changed['transport']['profile']='worker'
    elif mutation=='sources':
        changed['sources'][0]['sha256']='b'*64
    elif mutation=='evidence':
        changed['task']['expected_evidence']=[]
    elif mutation=='route':
        receipts['corrected']['route_qualification']={'invocation_id':'worker','sha256':'worker'}
    else:
        changed['seal']='unapproved'
    with pytest.raises(RouterError,match='CORRECTION_BINDING_MISMATCH'):
        qualification._validate_assessments(store,runset,assessments,['gate'])


def test_swapping_runset_profile_labels_cannot_relabel_actual_contracts(tmp_path,monkeypatch):
    store,runset,assessments,_=fixture(tmp_path,monkeypatch)
    for task in runset['runs']:
        task['profile']='deep' if task['profile']=='worker' else 'worker'
    runset['sha256']=hash_bytes(canonical_bytes({k:v for k,v in runset.items() if k!='sha256'}))
    with pytest.raises(RouterError,match='HOLDOUT_BINDING_MISMATCH'):
        qualification._validate_assessments(store,runset,assessments,['gate'])
