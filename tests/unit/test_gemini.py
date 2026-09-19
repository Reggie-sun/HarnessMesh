import json
import os

import pytest

from agent_subagent_router.contracts import Budgets, RouterError, hash_bytes


def report():
    return {'findings': ['found'], 'proposed_changes': [], 'evidence_refs': [],
            'uncertainties': [], 'questions': []}


def event(value):
    return json.dumps(value, separators=(',', ':')).encode()+b'\n'


def stream(*events):
    return b''.join(event(item) for item in events)


def test_gemini_stream_requires_single_final_terminal_and_report_schema():
    from agent_subagent_router.gemini_protocol import decode_gemini

    valid = stream(
        {'type': 'init', 'model': 'gemini-3.5-flash'},
        {'type': 'message', 'role': 'assistant', 'content': json.dumps(report()), 'delta': True},
        {'type': 'result', 'status': 'success'},
    )
    assert decode_gemini(valid).classification == 'PARSED'
    assert decode_gemini(b'').classification == 'TERMINAL_MISSING'
    assert decode_gemini(valid[:-1]).classification == 'PROTOCOL_ERROR'
    assert decode_gemini(valid+event({'type': 'message', 'role': 'assistant', 'content': '{}'})).classification == 'PROTOCOL_ERROR'
    assert decode_gemini(stream({'type': 'init', 'model': 'gemini-3.5-flash'},
                                {'type': 'result', 'status': 'success'})).classification == 'REPORT_SCHEMA_ERROR'


def test_gemini_stream_rejects_forbidden_tools_and_unobserved_evidence():
    from agent_subagent_router.gemini_protocol import decode_gemini

    forbidden = stream({'type': 'init', 'model': 'gemini-3.5-flash'},
                       {'type': 'tool_use', 'tool_name': 'run_shell', 'tool_id': '1', 'parameters': {}},
                       {'type': 'message', 'role': 'assistant', 'content': json.dumps(report())},
                       {'type': 'result', 'status': 'success'})
    assert decode_gemini(forbidden).classification == 'TOOL_POLICY_VIOLATION'
    evidence = report() | {'evidence_refs': [
        {'path': 'src/a.py', 'sha256': 'a'*64, 'start_line': 2, 'end_line': 3}
    ]}
    raw = stream({'type': 'init', 'model': 'gemini-3.5-flash'},
                 {'type': 'tool_use', 'tool_name': 'ReadFileTool', 'tool_id': '1', 'parameters': {}},
                 {'type': 'message', 'role': 'assistant', 'content': json.dumps(evidence)},
                 {'type': 'result', 'status': 'success'})
    parsed = decode_gemini(raw, required_evidence=['src/a.py'], source_hashes={'src/a.py': 'a'*64})
    assert parsed.classification == 'EVIDENCE_INCOMPLETE'
    assert parsed.tool_observations == ({'tool': 'read_file', 'id': '1', 'status': 'attempted'},)


def test_worker_profile_and_invocation_keep_secret_and_prompt_off_argv(tmp_path):
    from agent_subagent_router.adapters.gemini import SETTINGS, GeminiRuntime, build_invocation, tree_hash
    from agent_subagent_router.backends.gemini import profile

    node = tmp_path/'node'
    node.write_text("#!/bin/sh\nprintf '%s\\n' 0.60.0\n")
    node.chmod(0o500)
    package = tmp_path/'package'
    (package/'node_modules/@google/gemini-cli/bundle').mkdir(parents=True)
    (package/'node_modules/@google/gemini-cli/bundle/gemini.js').write_text('bundle')
    runtime = GeminiRuntime(str(node), hash_bytes(node.read_bytes()), package, '0.60.0', tree_hash(package))
    selected = profile('worker')
    invocation = build_invocation(runtime, selected, 'one-use-capability', b'secret prompt', Budgets(2, 1, 1, 4096, 4096))
    assert selected.client_model == selected.wire_model == 'gemini-3.5-flash'
    assert invocation.argv == ('/opt/node/bin/node', '/opt/gemini/node_modules/@google/gemini-cli/bundle/gemini.js',
                               '--output-format', 'stream-json', '--model', 'gemini-3.5-flash')
    assert b'secret prompt' == invocation.stdin
    assert all('one-use-capability' not in item and 'secret prompt' not in item for item in invocation.argv)
    assert invocation.env['GEMINI_API_KEY'] == 'one-use-capability'
    assert invocation.env['GOOGLE_GEMINI_BASE_URL'] == 'http://127.0.0.1:18765'
    assert 'GOOGLE_API_KEY' not in invocation.env
    assert SETTINGS['tools']['core'] == ['read_file', 'glob', 'list_directory']
    assert SETTINGS['mcpServers'] == {} and SETTINGS['admin']['extensions']['enabled'] is False
    assert SETTINGS['hooksConfig']['enabled'] is False
    assert SETTINGS['security']['auth'] == {'selectedType': 'gemini-api-key', 'useExternal': False}
    assert invocation.env['GEMINI_CLI_SYSTEM_SETTINGS_PATH'] == '/opt/gemini/router-settings.json'


def test_runtime_rejects_package_mutation_and_symlink(tmp_path):
    from agent_subagent_router.adapters.gemini import GeminiRuntime, tree_hash

    node = tmp_path/'node'
    node.write_text("#!/bin/sh\nprintf '%s\\n' 0.60.0\n")
    node.chmod(0o500)
    package = tmp_path/'package'
    package.mkdir()
    (package/'bundle.js').write_text('one')
    runtime = GeminiRuntime(str(node), hash_bytes(node.read_bytes()), package, '0.60.0', tree_hash(package))
    runtime.verify()
    (package/'bundle.js').write_text('two')
    with pytest.raises(RouterError, match='RUNTIME_CHANGED'):
        runtime.verify()
    package.joinpath('bundle.js').unlink()
    os.symlink(node, package/'bundle.js')
    with pytest.raises(RouterError, match='RUNTIME_CHANGED'):
        runtime.verify()


def test_projection_rejects_unqualified_selected_skills_and_native_settings(tmp_path, monkeypatch):
    from agent_subagent_router.adapters import gemini

    snapshot = tmp_path/'snapshot'
    snapshot.mkdir()
    asset = snapshot/'sources/skill/run.sh'
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b'#!/bin/sh\n')
    asset.chmod(0o500)
    source = {'path': '/project/skills/demo/run.sh', 'relative_path': 'skills/demo/run.sh',
              'snapshot_path': 'sources/skill/run.sh', 'sha256': hash_bytes(asset.read_bytes()),
              'size': asset.stat().st_size, 'mode': 0o500, 'category': 'skill',
              'selection_reason': 'selected_skill:/project/skills/demo'}
    manifest = {'snapshot_root': str(snapshot), 'project': {'root': '/project'}, 'seal': 'seal',
                'task': {'instruction_precedence': []}, 'sources': [source]}
    monkeypatch.setattr(gemini, 'verify', lambda value: None)
    with pytest.raises(RouterError, match='UNSUPPORTED_REQUIRED_CAPABILITY'):
        gemini.materialize_gemini_projection(manifest, tmp_path/'projection')
    source['path'] = '/outside/.gemini/settings.json'
    source['relative_path'] = '.gemini/settings.json'
    with pytest.raises(RouterError, match='UNSUPPORTED_REQUIRED_CAPABILITY'):
        gemini.materialize_gemini_projection(manifest, tmp_path/'invalid')


def test_native_context_sources_keep_distinct_exact_evidence_paths(tmp_path, monkeypatch):
    from agent_subagent_router.adapters import gemini
    sources = []
    snapshot = tmp_path/'snapshot'
    snapshot.mkdir()
    for index, relative in enumerate(('GEMINI.md', 'sub/GEMINI.md')):
        data = ('context '+str(index)+'\n').encode()
        (snapshot/str(index)).write_bytes(data)
        sources.append({'path':'/project/'+relative, 'relative_path':relative,
            'snapshot_path':str(index), 'sha256':hash_bytes(data), 'size':len(data),
            'mode':0o644, 'category':'instruction', 'selection_reason':'applicable_instruction'})
    manifest = {'snapshot_root':str(snapshot), 'project':{'root':'/project'}, 'seal':'seal',
                'task':{'instruction_precedence':[]}, 'sources':sources}
    monkeypatch.setattr(gemini, 'verify', lambda _:None)
    projection = gemini.materialize_gemini_projection(manifest, tmp_path/'projection')
    assert len({item['execution_path'] for item in projection['source_map']}) == 2
    for item in projection['source_map']:
        assert item['execution_path'] != 'GEMINI.md'
        assert hash_bytes((tmp_path/'projection'/item['execution_path']).read_bytes()) == item['sha256']
