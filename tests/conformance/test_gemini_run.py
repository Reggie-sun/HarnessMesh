import json
from pathlib import Path
import subprocess

import pytest

from agent_subagent_router.contracts import Budgets, RouterError, TaskContract, canonical_bytes, hash_bytes
from agent_subagent_router.gemini_run import execute_gemini
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.resolver import resolve
from agent_subagent_router.runtime_config import installed_gemini_runtime, installed_sandbox


pytestmark = pytest.mark.containment


def _init(repo: Path) -> None:
    subprocess.run(('git', 'init', '-q', str(repo)), check=True)
    subprocess.run(('git', '-C', str(repo), 'config', 'user.email', 'test@example.com'), check=True)
    subprocess.run(('git', '-C', str(repo), 'config', 'user.name', 'Test'), check=True)
    repo.joinpath('a.py').write_text('VALUE = 42\n')
    subprocess.run(('git', '-C', str(repo), 'add', 'a.py'), check=True)
    subprocess.run(('git', '-C', str(repo), 'commit', '-qm', 'initial'), check=True)


def _sse(response: dict) -> bytes:
    return b'data: '+canonical_bytes({'traceId': 'synthetic-trace', 'response': response})+b'\n\n'


def test_native_gemini_read_report_and_receipt_are_bound_to_frozen_source(tmp_path):
    try:
        runtime, sandbox = installed_gemini_runtime(), installed_sandbox('gemini')
    except RouterError as exc:
        pytest.skip(str(exc))
    repo = tmp_path/'project'
    repo.mkdir()
    _init(repo)
    data = b'VALUE = 42\n'
    task = TaskContract('parent', 'gemini-task', str(repo), 'explorer', 'read a.py', ['a.py'], [], ['read'], [],
                        'not_applicable', [], [], [], [], ['a.py'], 'gemini', 'worker',
                        Budgets(30, 15, 3, 1_000_000, 1_000_000), instruction_precedence=['AGENTS.md', 'CLAUDE.md'])
    manifest = resolve(task, tmp_path/'snapshot', {
        'backend': 'gemini', 'profile': 'worker', 'runtime': 'gemini-cli', 'capabilities': ['read'],
    })
    report = {'findings': ['VALUE is 42'], 'proposed_changes': [], 'uncertainties': [], 'questions': [],
              'evidence_refs': [{'path': str(repo/'a.py'), 'sha256': hash_bytes(data),
                                 'start_line': 1, 'end_line': 1}]}
    calls = []

    def upstream(_path, _headers, body):
        calls.append(json.loads(body))
        if len(calls) == 1:
            response = {'modelVersion': 'gemini-3.5-flash', 'candidates': [{
                'content': {'role': 'model', 'parts': [{'functionCall': {
                    'name': 'glob', 'args': {'pattern': '*.py', 'dir_path': '/work'},
                }}]}, 'finishReason': 'STOP'}]}
        elif len(calls) == 2:
            response = {'modelVersion': 'gemini-3.5-flash', 'candidates': [{
                'content': {'role': 'model', 'parts': [{'functionCall': {
                    'name': 'read_file', 'args': {'file_path': '/work/a.py'},
                }}]}, 'finishReason': 'STOP'}]}
        else:
            response = {'modelVersion': 'gemini-3.5-flash', 'candidates': [{
                'content': {'role': 'model', 'parts': [{'text': json.dumps(report)}]}, 'finishReason': 'STOP'}]}
        return 200, {'content-type': 'text/event-stream'}, _sse(response)

    store = ReceiptStore(tmp_path/'runs')
    run = store.create('parent', 'gemini-task')
    receipt = execute_gemini(manifest, runtime, sandbox, store, run, {}, None, upstream=upstream)
    assert receipt['classification'] == 'PARSED', receipt
    assert receipt['evidence_kind'] == 'native-loopback-synthetic'
    assert receipt['wire_requests'] == 3
    assert receipt['observed_reads'][0]['path'] == str(repo/'a.py')
    assert {item['path'] for item in receipt['artifacts']} >= {
        'execution-view.json', 'stdout.jsonl', 'stderr.txt', 'broker-observations.json', 'worker-report.json',
    }
    assert store.read(receipt['invocation_id']) == receipt
    assert b'SYNTHETIC_GEMINI_SENTINEL' not in (run/'stdout.jsonl').read_bytes()
