from dataclasses import replace
import json
from pathlib import Path

import pytest

from agent_subagent_router.adapters.claude import Runtime, build_invocation
from agent_subagent_router.adapters.projection import materialize_projection
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import Budgets, TaskContract, hash_bytes
from agent_subagent_router.resolver import resolve
from agent_subagent_router.supervisor import supervise
from agent_subagent_router.transport.broker import Broker
from test_claude import NATIVE, fake_stream


@pytest.mark.native
def test_native_loader_finds_sealed_rules_and_skill(tmp_path):
    project = tmp_path/'synthetic'
    project.mkdir()
    (project/'a.py').write_text('VALUE = 1\n')
    (project/'AGENTS.md').write_text('SEALED_CONSTITUTION_987654: parent owns acceptance.')
    skill = tmp_path/'skills'/'sealed-demo'
    skill.mkdir(parents=True)
    (skill/'SKILL.md').write_text('---\nname: sealed-demo\ndescription: synthetic demo evidence\n---\nUse only synthetic facts.\n')
    task = TaskContract.from_dict(dict(parent_session_id='p', task_id='t', cwd=str(project),
        explicit_root=str(project), role='explorer', goal='synthetic', read_paths=['a.py'], write_paths=[],
        permissions=['read'], selected_refs=[], active_documents='not_applicable', harness_refs=[],
        constitution_refs=[], skills=['sealed-demo'], skill_roots=[str(tmp_path/'skills')],
        expected_evidence=[], backend='kimi', profile='worker',
        budgets=dict(wall_seconds=8, idle_seconds=8, request_limit=1, output_bytes=200000, context_bytes=300000)))
    sealed = resolve(task, tmp_path/'snapshot', {'backend':'kimi','profile':'worker','runtime':'claude-code','capabilities':['read']})
    projection = materialize_projection(sealed, tmp_path/'projection')
    seen = []

    def upstream(path, headers, body):
        seen.append(body)
        return 200, {'content-type':'text/event-stream'}, fake_stream('k3-256k')

    runtime = Runtime(str(NATIVE), '2.1.277', hash_bytes(NATIVE.read_bytes()))
    with Broker(profile('worker'), 'SYNTHETIC', request_limit=1, wall_seconds=8, upstream=upstream) as broker:
        invocation = build_invocation(runtime, profile('worker'), tmp_path/'runtime', broker.url,
            broker.capability, b'Synthetic loader check only.', Budgets(8,8,1,200000,300000))
        # This conformance-only mode uses synthetic files and local fake upstream, never a live route.
        env = dict(invocation.env)
        del env['CLAUDE_CODE_DISABLE_CLAUDE_MDS']
        argv = list(invocation.argv)
        argv.remove('--disable-slash-commands')
        argv[argv.index('--setting-sources')+1] = 'project'
        result = supervise(replace(invocation, argv=tuple(argv), cwd=Path(projection['root']), env=env),
                           on_stop=broker.revoke)
    assert result.exit_code == 0, result.stderr
    assert len(seen) == 1 and b'SEALED_CONSTITUTION_987654' in seen[0]
    init = next(json.loads(line) for line in result.stdout.splitlines() if json.loads(line).get('subtype') == 'init')
    assert 'sealed-demo' in init['skills']
