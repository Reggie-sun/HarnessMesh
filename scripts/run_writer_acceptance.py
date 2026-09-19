"""One explicitly bounded M8 real candidate on a clean router-owned code target."""
import argparse
import json
from pathlib import Path

from agent_subagent_router.api import inspect_task, run_contract
from agent_subagent_router.contracts import TaskContract
from agent_subagent_router.receipts import ReceiptStore, atomic_json
from agent_subagent_router.runtime_config import installed_runtime, installed_sandbox


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',required=True,action='store_true')
    parser.add_argument('--correction',action='store_true')
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    state=Path.home()/'.local/state/agent-subagent-router'
    runtime,sandbox=installed_runtime(),installed_sandbox()
    routes=json.loads((state/'qualified-routes.json').read_text())
    readonly=json.loads((state/'readonly-qualified.json').read_text())['invocation_id']
    credential=json.loads((Path.home()/'.config/agent-subagent-router/kimi-credential.json').read_text())
    target='src/agent_subagent_router/gemini_protocol.py'
    task_id='m8-gemini-duplicate-tool-id'+('-correction-1' if args.correction else '')
    task=TaskContract.from_dict(dict(parent_session_id='m8-parent',task_id=task_id,
        cwd=str(repo),role='implementer',goal='Fix decode_gemini to reject repeated native tool_id with PROTOCOL_ERROR. '
        'Track seen IDs for tool_use events before appending observations; distinct IDs must remain accepted. '
        'Make the minimum change only in the owned gemini_protocol.py candidate. The selected stdlib parent gate '
        'tests/writer_duplicate_check.py currently fails and must pass after the change. Do not execute tests yourself.',
        read_paths=[target,'src/agent_subagent_router/__init__.py','src/agent_subagent_router/contracts.py',
                    'src/agent_subagent_router/protocol.py','tests/writer_duplicate_check.py'],
        write_paths=[target],permissions=['read','candidate-write'],selected_refs=[],active_documents='not_applicable',
        harness_refs=[],constitution_refs=[],skills=[],skill_roots=[],expected_evidence=[target,'tests/writer_duplicate_check.py'],
        instruction_precedence=['AGENTS.override.md','AGENTS.md','CLAUDE.md'],backend='kimi',profile='worker',
        budgets=dict(wall_seconds=180,idle_seconds=180,request_limit=8,output_bytes=1000000,context_bytes=1000000)))
    manifest=inspect_task(task,state/'m8-contracts',runtime,sandbox=sandbox)
    # A separate, explicit parent correction for the recorded prompt defect; never an automatic retry.
    attempt_name='m8-correction-1' if args.correction else 'm8'
    reason=None
    if args.correction:
        original=ReceiptStore(state/'runs').read('731ee220-37d6-40c1-b47b-fa5504550c12')
        if original['classification']!='PROTOCOL_ERROR' or original['host_project_modified'] is not False:
            raise RuntimeError('M8 correction precondition changed')
        reason='Writer prompt replaced strict output instructions; restore JSON-only and object-valued proposed_changes.'
    atomic_json(state/(attempt_name+'-attempt.json'),{'contract_seal':manifest['seal'],
        'task_limit':1,'state':'submitted_or_unknown','reason':reason})
    receipt=run_contract(manifest,'kimi','worker',ReceiptStore(state/'runs'),runtime,sandbox=sandbox,
        credential_ref=credential,qualification_id=routes['worker'],readonly_qualification_id=readonly)
    atomic_json(state/(attempt_name+'-result.json'),receipt)
    print(json.dumps({'invocation_id':receipt['invocation_id'],'classification':receipt['classification'],
                      'wire_requests':receipt['wire_requests']}))


if __name__=='__main__':
    main()
