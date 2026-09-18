import math

import pytest

from agent_subagent_router.contracts import Budgets, RouterError, TaskContract, strict_json


def task_dict():
    return dict(parent_session_id='parent-1', task_id='task-1', cwd='/tmp/project',
                role='explorer', goal='Map the owner with file evidence',
                read_paths=['src/main.py'], write_paths=[], permissions=['read'],
                selected_refs=[], active_documents='not_applicable',
                harness_refs=[], constitution_refs=[], skills=[], skill_roots=[],
                expected_evidence=['src/main.py'], backend='kimi', profile='worker',
                budgets=dict(wall_seconds=20, idle_seconds=10, request_limit=1,
                             output_bytes=100000, context_bytes=200000))


def test_task_round_trip_and_explicit_route():
    task = TaskContract.from_dict(task_dict())
    assert task.to_dict() == task_dict()
    data = task_dict()
    del data['backend']
    with pytest.raises(RouterError, match='INVALID_CONTRACT'):
        TaskContract.from_dict(data)


@pytest.mark.parametrize('key,value', [('wall_seconds', 0), ('wall_seconds', math.inf),
                                    ('idle_seconds', math.nan), ('request_limit', True),
                                    ('output_bytes', -1)])
def test_budgets_are_positive_and_finite(key, value):
    data = task_dict()['budgets']
    data[key] = value
    with pytest.raises(RouterError, match='INVALID_CONTRACT'):
        Budgets(**data)


@pytest.mark.parametrize('change', [{'permissions': ['Bash']}, {'write_paths': ['a']},
                                 {'role': 'boss'}, {'acceptance': 'KEEP'},
                                 {'selected_refs': [{'path': 'plan.md', 'accepted': False}]}])
def test_authority_is_not_inferred(change):
    data = task_dict() | change
    with pytest.raises(RouterError):
        TaskContract.from_dict(data)


@pytest.mark.parametrize('raw', ['{"x":1,"x":2}', '{"x":NaN}', '{} trailing'])
def test_strict_json_rejects_ambiguous_representation(raw):
    with pytest.raises(RouterError):
        strict_json(raw)
