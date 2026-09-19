"""Seal the accepted eight-task experiment before model evaluation. No live calls."""
import json
from pathlib import Path
import uuid

from agent_subagent_router.api import inspect_task
from agent_subagent_router.contracts import TaskContract, canonical_bytes, hash_bytes
from agent_subagent_router.permissions.docker import DockerSandbox
from agent_subagent_router.receipts import atomic_json
from agent_subagent_router.runtime_config import installed_runtime


def main():
    repo = Path(__file__).resolve().parents[1]
    tasks = json.loads((repo/'tests/holdout/tasks.json').read_text())
    config = json.loads((Path.home()/'.local/share/agent-subagent-router/sandbox.json').read_text())
    sandbox = DockerSandbox(config['image'], config['runtime_sha256'])
    runtime = installed_runtime()
    destination = Path.home()/'.local/state/agent-subagent-router/holdouts'/str(uuid.uuid4())
    destination.mkdir(parents=True, mode=0o700)
    runs = []
    for item in tasks:
        project = Path.home()/'vscode_folder'/item['project']
        for profile in ('worker', 'deep'):
            task = TaskContract.from_dict(dict(parent_session_id='m7-readonly',
                task_id=item['id']+'-'+profile, cwd=str(project), role=item['role'],
                goal=item['goal'], read_paths=item['paths'], write_paths=[], permissions=['read'],
                selected_refs=[], active_documents='not_applicable', harness_refs=item['refs'],
                constitution_refs=[], skills=[], skill_roots=[], expected_evidence=item['paths'],
                instruction_precedence=['AGENTS.override.md', 'AGENTS.md', 'CLAUDE.md'],
                backend='kimi', profile=profile, budgets=dict(wall_seconds=240, idle_seconds=240,
                request_limit=16, output_bytes=2000000, context_bytes=2000000)))
            manifest = inspect_task(task, destination/'contracts', runtime, sandbox=sandbox)
            runs.append({'task_id': task.task_id, 'profile': profile, 'project': item['project'],
                         'contract': str(Path(manifest['snapshot_root'])/'manifest.json'),
                         'contract_seal': manifest['seal'], 'rubric': item['rubric']})
    runset = {'schema_version': 1, 'task_invocation_limit': 8, 'runs': runs,
              'correction_limit': 2, 'corrections_shared_with_m1': True,
              'rubric_sha256': hash_bytes(canonical_bytes(tasks)),
              'actual_cost': None, 'provider_media_actions': False}
    runset['sha256'] = hash_bytes(canonical_bytes(runset))
    atomic_json(destination/'run-set.json', runset)
    print(destination/'run-set.json')


if __name__ == '__main__':
    main()
