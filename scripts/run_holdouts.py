"""Explicit bounded M7 execution. Default tests never import or invoke this script."""
import argparse
import json
from pathlib import Path

from agent_subagent_router.api import inspect_task, run_contract
from agent_subagent_router.contracts import RouterError, TaskContract, canonical_bytes, hash_bytes
from agent_subagent_router.permissions.docker import DockerSandbox
from agent_subagent_router.receipts import ReceiptStore, atomic_json
from agent_subagent_router.runtime_config import installed_runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_set', type=Path)
    parser.add_argument('--live', required=True, action='store_true')
    parser.add_argument('--task', help='One sealed task ID, or all unconsumed tasks')
    parser.add_argument('--correction-reason', help='One explicitly classified correction; requires --task')
    args = parser.parse_args()
    if args.correction_reason and not args.task:
        parser.error('--correction-reason requires --task')
    runset = json.loads(args.run_set.read_text())
    body = {k: v for k, v in runset.items() if k != 'sha256'}
    if hash_bytes(canonical_bytes(body)) != runset['sha256'] or len(runset['runs']) != 8:
        raise RouterError('RUN_SET_CHANGED')
    state = Path.home()/'.local/state/agent-subagent-router'
    store = ReceiptStore(state/'runs')
    routes = json.loads((state/'qualified-routes.json').read_text())
    reference = json.loads((Path.home()/'.config/agent-subagent-router/kimi-credential.json').read_text())
    config = json.loads((Path.home()/'.local/share/agent-subagent-router/sandbox.json').read_text())
    sandbox = DockerSandbox(config['image'], config['runtime_sha256'])
    for item in runset['runs']:
        if args.task and item['task_id'] != args.task:
            continue
        suffix = '.correction' if args.correction_reason else ''
        path = args.run_set.parent/(item['task_id']+suffix+'.attempt.json')
        if path.exists():
            continue  # No retries; the existing invocation remains authoritative.
        manifest = json.loads(Path(item['contract']).read_text())
        if manifest['seal'] != item['contract_seal']:
            raise RouterError('RUN_SET_CHANGED')
        if args.correction_reason:
            previous = args.run_set.parent/(item['task_id']+'.result.json')
            if not previous.is_file() or json.loads(previous.read_text())['classification'] == 'PARSED':
                raise RouterError('CORRECTION_NOT_APPLICABLE')
            task = TaskContract.from_dict(manifest['task'] | {'task_id': item['task_id']+'-correction'})
            corrected = inspect_task(task, args.run_set.parent/'corrections', installed_runtime(), sandbox=sandbox)
            if corrected['sources'] != manifest['sources']:
                raise RouterError('CORRECTION_SOURCE_CHANGED')
            manifest = corrected
            from agent_subagent_router.smoke import _reserve_live_smoke
            _reserve_live_smoke(store.root, item['profile'], args.correction_reason)
        atomic_json(path, {'run_set_sha256': runset['sha256'], 'task_id': item['task_id'],
                           'state': 'submitted_or_unknown', 'contract_seal': manifest['seal'],
                           'correction_reason': args.correction_reason})
        receipt = run_contract(manifest, 'kimi', item['profile'], store, installed_runtime(),
            sandbox=sandbox, credential_ref=reference, qualification_id=routes[item['profile']])
        atomic_json(args.run_set.parent/(item['task_id']+suffix+'.result.json'), receipt)
        print(json.dumps({'task': item['task_id'], 'classification': receipt['classification'],
                          'invocation_id': receipt['invocation_id'],
                          'wire_requests': receipt['wire_requests']}), flush=True)


if __name__ == '__main__':
    main()
