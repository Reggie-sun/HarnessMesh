from pathlib import Path

import pytest

from agent_subagent_router.adapters.projection import materialize_projection
from agent_subagent_router.contracts import RouterError, TaskContract
from agent_subagent_router.contracts import hash_bytes
from agent_subagent_router.resolver import resolve


def manifest(tmp_path):
    project = tmp_path/'project'
    project.mkdir()
    (project/'a.py').write_text('VALUE = 3\n')
    (project/'AGENTS.md').write_text('BOUNDARY_SENTINEL: no shell')
    (project/'CLAUDE.md').write_text('NATIVE_SENTINEL: preserve this owner')
    skill = tmp_path/'skills'/'demo'
    (skill/'scripts').mkdir(parents=True)
    (skill/'SKILL.md').write_text('---\nname: demo\ndescription: synthetic demo\n---\nKeep asset bytes')
    (skill/'scripts'/'tool').write_bytes(b'#!/bin/sh\nexit 0\n')
    (skill/'scripts'/'tool').chmod(0o755)
    task = TaskContract.from_dict(dict(parent_session_id='p', task_id='t', cwd=str(project),
         explicit_root=str(project), role='reviewer', goal='Synthetic offline projection',
         read_paths=['a.py'], write_paths=[], permissions=['read'], selected_refs=[],
         active_documents='not_applicable', harness_refs=[], constitution_refs=[], skills=['demo'],
         skill_roots=[str(tmp_path/'skills')], expected_evidence=['a.py'], backend='kimi', profile='worker',
         instruction_precedence=['AGENTS.md','CLAUDE.md'],
         budgets=dict(wall_seconds=10, idle_seconds=10, request_limit=1, output_bytes=100000, context_bytes=100000)))
    return resolve(task, tmp_path/'snapshot', dict(backend='kimi', profile='worker', runtime='claude-code', capabilities=['read']))


def test_native_projection_preserves_owners_and_full_skill_bundle(tmp_path):
    sealed = manifest(tmp_path)
    result = materialize_projection(sealed, tmp_path/'native')
    root = Path(result['root'])
    assert (root/'CLAUDE.md').read_text() == 'NATIVE_SENTINEL: preserve this owner'
    assert 'BOUNDARY_SENTINEL' in (root/'.claude/rules/router-constitution.md').read_text()
    asset = root/'.claude/skills/demo/scripts/tool'
    assert asset.read_bytes() == b'#!/bin/sh\nexit 0\n' and asset.stat().st_mode & 0o100
    assert result['source_seal'] == sealed['seal']


def test_projection_refuses_overwriting_any_existing_destination(tmp_path):
    sealed = manifest(tmp_path)
    target = tmp_path/'native'
    target.mkdir()
    (target/'CLAUDE.md').write_text('user work')
    with pytest.raises(RouterError, match='PROJECTION_EXISTS'):
        materialize_projection(sealed, target)


def test_project_local_skill_json_assets_are_preserved(tmp_path):
    sealed = manifest(tmp_path)
    root = Path(sealed['project']['root'])
    skill = root/'.claude/skills/native-demo'
    (skill/'assets').mkdir(parents=True)
    (skill/'SKILL.md').write_text('---\nname: native-demo\ndescription: test\n---\nRead assets/schema.json')
    (skill/'assets/schema.json').write_bytes(b'{"type":"object"}\n')
    task = TaskContract.from_dict(sealed['task'] | {'skills':['native-demo'],
                                                   'skill_roots':[str(skill.parent)]})
    selected = resolve(task, tmp_path/'second-snapshot', sealed['transport'])
    output = materialize_projection(selected, tmp_path/'native')
    assert (Path(output['root'])/'.claude/skills/native-demo/assets/schema.json').read_bytes() == b'{"type":"object"}\n'


def test_external_accepted_spec_and_harness_are_in_execution_view(tmp_path):
    sealed = manifest(tmp_path)
    spec = tmp_path/'accepted-spec.md'
    spec.write_text('ACCEPTED_EXTERNAL_BOUNDARY')
    harness = tmp_path/'harness.md'
    harness.write_text('PARENT_VERIFICATION_ONLY')
    task = TaskContract.from_dict(sealed['task'] | {'active_documents':'accepted_refs',
        'selected_refs':[{'path':str(spec),'sha256':hash_bytes(spec.read_bytes()),'accepted':True}],
        'harness_refs':[str(harness)]})
    selected = resolve(task, tmp_path/'second-snapshot', sealed['transport'])
    output = materialize_projection(selected, tmp_path/'native')
    for origin in (spec,harness):
        mapped = next(item for item in output['source_map'] if item['source_path'] == str(origin))
        assert (Path(output['root'])/mapped['execution_path']).read_bytes() == origin.read_bytes()
