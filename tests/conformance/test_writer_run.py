import json
from pathlib import Path

import pytest

from agent_subagent_router.api import inspect_task
from agent_subagent_router.candidate_gates import apply_tested_candidate, test_candidate as run_candidate_test
from agent_subagent_router.contracts import TaskContract, hash_bytes
from agent_subagent_router.permissions.docker import DockerSandbox
from agent_subagent_router.permissions.qualification import _stream
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.runtime_config import installed_runtime
from agent_subagent_router.writer_run import execute_writer


@pytest.mark.containment
def test_native_candidate_test_and_parent_apply_bind_exact_bytes(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    data = b'VALUE = 1\nassert VALUE == 2\n'
    target = source/'a.py'
    target.write_bytes(data)
    config = json.loads((Path.home()/'.local/share/agent-subagent-router/sandbox.json').read_text())
    sandbox = DockerSandbox(config['image'], config['runtime_sha256'])
    runtime = installed_runtime()
    task = TaskContract.from_dict(dict(parent_session_id='p', task_id='w', cwd=str(source),
        explicit_root=str(source), role='implementer', goal='Change VALUE from 1 to 2.',
        read_paths=['a.py'], write_paths=['a.py'], permissions=['read','candidate-write'],
        selected_refs=[], active_documents='not_applicable', harness_refs=[], constitution_refs=[],
        skills=[], skill_roots=[], expected_evidence=['a.py'], backend='kimi', profile='worker',
        budgets=dict(wall_seconds=30,idle_seconds=30,request_limit=3,output_bytes=1000000,context_bytes=2000000)))
    manifest = inspect_task(task, tmp_path/'contracts', runtime, sandbox=sandbox)
    calls=[]
    report = {'findings':['changed VALUE'],'proposed_changes':[],'uncertainties':[],'questions':[],
        'evidence_refs':[{'path':str(target),'sha256':hash_bytes(data),'start_line':1,'end_line':2}]}
    def fake(path,headers,body):
        calls.append(body)
        if len(calls)==1:
            blocks=[{'type':'tool_use','name':'Read','id':'r'+str(i),'input':{'file_path':p}}
                    for i,p in enumerate(['/work/a.py','/candidate/owned'])]
        elif len(calls)==2:
            blocks=[{'type':'tool_use','name':'Edit','id':'e','input':{'file_path':'/candidate/owned',
                       'old_string':'VALUE = 1','new_string':'VALUE = 2'}}]
        else:
            blocks=[{'type':'text','text':json.dumps(report)}]
        return 200,{'content-type':'text/event-stream'},_stream(blocks,tools=len(calls)<3)
    store=ReceiptStore(tmp_path/'runs')
    run=store.create('p','w')
    receipt=execute_writer(manifest,runtime,sandbox,store,run,{'contract_seal':manifest['seal']},'SENTINEL',upstream=fake)
    assert receipt['classification']=='PARSED',receipt
    assert target.read_bytes()==data
    gate=run_candidate_test(store,run.name,sandbox,('/usr/local/bin/python3','/work/a.py'))
    assert gate['classification']=='PASS',gate
    applied=apply_tested_candidate(store,run.name,gate['invocation_id'])
    assert applied['classification']=='APPLIED',applied
    assert target.read_bytes()==b'VALUE = 2\nassert VALUE == 2\n'
    assert Path(applied['application']['exchange']['retained_object']).read_bytes()==data
