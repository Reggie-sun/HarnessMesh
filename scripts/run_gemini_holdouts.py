"""Two explicit M9 attempts reusing M7 task scope; no retry or onboarding."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from agent_subagent_router.api import inspect_task, run_contract
from agent_subagent_router.contracts import Budgets, TaskContract, strict_json
from agent_subagent_router.receipts import ReceiptStore, atomic_json
from agent_subagent_router.runtime_config import installed_gemini_runtime, installed_sandbox


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', required=True, action='store_true')
    parser.add_argument('--run-set', type=Path, required=True)
    parser.add_argument('--project', choices=('AI-VIDEO', 'jizhang'), required=True)
    parser.add_argument('--credential-ref', type=Path, required=True)
    args = parser.parse_args()
    state = Path.home()/'.local/state/agent-subagent-router'
    source = strict_json(args.run_set.read_bytes())
    name = 'ai-owner-worker' if args.project == 'AI-VIDEO' else 'jizhang-rules-worker'
    item, = [entry for entry in source['runs'] if entry['task_id'] == name]
    baseline = strict_json(Path(item['contract']).read_bytes())
    if baseline['seal'] != item['contract_seal']:
        raise ValueError('Run-set binding mismatch')
    task = replace(TaskContract.from_dict(baseline['task']), backend='gemini', profile='worker',
        task_id='m9-'+name, parent_session_id='m9-parent',
        budgets=Budgets(180, 180, 6, 1_000_000, 2_000_000))
    runtime, sandbox = installed_gemini_runtime(), installed_sandbox('gemini')
    manifest = inspect_task(task, state/'m9-contracts', runtime, sandbox=sandbox)
    atomic_json(state/('m9-'+name+'-attempt.json'), {'contract_seal':manifest['seal'],
        'task_limit':1, 'generation_request_limit':6, 'state':'submitted_or_unknown',
        'onboarding':False, 'retry':False})
    receipt = run_contract(manifest, 'gemini', 'worker', ReceiptStore(state/'runs'), runtime,
        sandbox=sandbox, credential_ref=strict_json(args.credential_ref.read_bytes()))
    atomic_json(state/('m9-'+name+'-result.json'), receipt)
    print(json.dumps({key:receipt.get(key) for key in
        ('invocation_id','classification','reason','wire_requests')}))


if __name__ == '__main__':
    main()
