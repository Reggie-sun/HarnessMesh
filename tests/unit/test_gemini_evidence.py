import json

import pytest

from agent_subagent_router.contracts import RouterError, hash_bytes


def _fixture(tmp_path):
    data = b'one\ntwo\n'
    (tmp_path/'source').write_bytes(data)
    manifest = {'snapshot_root': str(tmp_path), 'sources': [{
        'path': '/project/a.py', 'snapshot_path': 'source', 'sha256': hash_bytes(data), 'size': len(data),
    }]}
    projection = {'source_map': [{
        'source_path': '/project/a.py', 'execution_path': 'a.py', 'sha256': hash_bytes(data),
    }]}
    response_id = 'read_file_1'
    raw = b'\n'.join(json.dumps(item).encode() for item in (
        {'type': 'tool_use', 'tool_name': 'read_file', 'tool_id': 'read_file__'+response_id,
         'parameters': {'file_path': '/work/a.py', 'start_line': 2, 'end_line': 2}},
        {'type': 'tool_result', 'tool_id': 'read_file__'+response_id, 'status': 'success', 'output': ''},
    ))+b'\n'
    wire = {'request': {'contents': [{'role': 'user', 'parts': [{'functionResponse': {
        'id': response_id, 'name': 'read_file', 'response': {'output': 'two\n'},
    }}]}]}}
    return manifest, projection, raw, [wire]


def test_native_gemini_read_is_bound_to_exact_projection_bytes_and_range(tmp_path):
    from agent_subagent_router.gemini_evidence import observed_gemini_reads

    manifest, projection, raw, wire = _fixture(tmp_path)
    assert observed_gemini_reads(raw, manifest, projection, wire) == [{
        'path': '/project/a.py', 'sha256': manifest['sources'][0]['sha256'], 'status': 'complete',
        'start_line': 2, 'end_line': 2, 'truncated': False, 'native_tool_use_id': 'read_file__read_file_1',
    }]


def test_native_glob_then_read_is_correlated_without_fabricating_read_evidence(tmp_path):
    from agent_subagent_router.gemini_evidence import observed_gemini_reads

    manifest, projection, raw, wire = _fixture(tmp_path)
    read_events = [json.loads(line) for line in raw.splitlines()]
    glob_id = 'glob_1'
    events = [
        {'type': 'tool_use', 'tool_name': 'glob', 'tool_id': 'glob__'+glob_id,
         'parameters': {'pattern': '*.py', 'dir_path': '/work'}},
        {'type': 'tool_result', 'tool_id': 'glob__'+glob_id, 'status': 'success', 'output': ''},
        *read_events,
    ]
    wire.insert(0, {'request': {'contents': [{'role': 'user', 'parts': [{'functionResponse': {
        'id': glob_id, 'name': 'glob', 'response': {'output': '/work/a.py'},
    }}]}]}})
    assert observed_gemini_reads(b'\n'.join(json.dumps(event).encode() for event in events)+b'\n',
                                 manifest, projection, wire)[0]['path'] == '/project/a.py'


@pytest.mark.parametrize('mutation', ('path', 'hash', 'truncated', 'forged_output'))
def test_native_gemini_forgery_cannot_become_evidence(tmp_path, mutation):
    from agent_subagent_router.gemini_evidence import observed_gemini_reads

    manifest, projection, raw, wire = _fixture(tmp_path)
    events = [json.loads(line) for line in raw.splitlines()]
    if mutation == 'path':
        events[0]['parameters']['file_path'] = '/work/elsewhere.py'
    elif mutation == 'hash':
        manifest['sources'][0]['sha256'] = '0'*64
    elif mutation == 'truncated':
        events[1]['truncated'] = True
    else:
        wire[0]['request']['contents'][0]['parts'][0]['functionResponse']['response']['output'] = 'forged'
    mutated = b'\n'.join(json.dumps(event).encode() for event in events)+b'\n'
    with pytest.raises(RouterError):
        observed_gemini_reads(mutated, manifest, projection, wire)


def test_spoofed_function_response_name_cannot_bind_another_native_tool(tmp_path):
    from agent_subagent_router.gemini_evidence import observed_gemini_reads

    manifest, projection, raw, wire = _fixture(tmp_path)
    wire[0]['request']['contents'][0]['parts'][0]['functionResponse']['name'] = 'glob'
    with pytest.raises(RouterError):
        observed_gemini_reads(raw, manifest, projection, wire)


def test_real_preflight_failure_consumes_no_contract_and_starts_no_generation(tmp_path, monkeypatch):
    import agent_subagent_router.gemini_run as gemini_run
    from agent_subagent_router.contracts import Budgets, TaskContract
    from agent_subagent_router.receipts import ReceiptStore

    task = TaskContract('parent', 'task', str(tmp_path), 'explorer', 'read', ['a.py'], [], ['read'], [],
                        'not_applicable', [], [], [], [], ['a.py'], 'gemini', 'worker',
                        Budgets(10, 5, 1, 1000, 1000), explicit_root=str(tmp_path),
                        instruction_precedence=['AGENTS.md'])
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('parent', 'task')
    calls = []
    monkeypatch.setattr(gemini_run, 'load_oauth_file', lambda *_args, **_kwargs: object())
    monkeypatch.setattr(gemini_run, 'access_token', lambda *_args, **_kwargs: 'token')
    monkeypatch.setattr(gemini_run, '_verify_pinned_oauth_bundle', lambda *_args, **_kwargs: None)

    def reject_preflight(*_args, **_kwargs):
        calls.append('preflight')
        raise RouterError('GEMINI_INELIGIBLE')

    monkeypatch.setattr(gemini_run, 'preflight_code_assist', reject_preflight)

    class Sandbox:
        def execute(self, *_args, **_kwargs):
            calls.append('generation')
            raise AssertionError('generation must not start')

    with pytest.raises(RouterError, match='GEMINI_INELIGIBLE'):
        gemini_run.execute_gemini({'task': task.to_dict(), 'project': {'root': str(tmp_path)}, 'seal': 'a'*64},
                                  object(), Sandbox(), store, run, {},
                                  {'provider': 'gemini', 'file': str(tmp_path/'oauth.json')})
    assert calls == ['preflight']
    assert not (store.root/'consumed-contracts'/(('a'*64)+'.json')).exists()
