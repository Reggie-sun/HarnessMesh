import json

import pytest

from agent_subagent_router.contracts import RouterError, hash_bytes
from agent_subagent_router.evidence import observed_reads


def fixture(tmp_path):
    raw = b'one\ntwo\n'
    (tmp_path/'source').write_bytes(raw)
    source = {'path': '/host/a', 'snapshot_path': 'source', 'sha256': hash_bytes(raw)}
    manifest = {'snapshot_root': str(tmp_path), 'sources': [source]}
    projection = {'source_map': [{'source_path': '/host/a', 'execution_path': 'a'}]}
    events = [{'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'r1',
        'name': 'Read', 'input': {'file_path': '/work/a'}}]}},
        {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'r1'}]},
         'tool_use_result': {'type': 'text', 'file': {'filePath': '/work/a', 'content': 'two',
             'numLines': 1, 'startLine': 2, 'totalLines': 3}}}]
    return manifest, projection, events


def encode(events):
    return b'\n'.join(json.dumps(e).encode() for e in events)+b'\n'


def test_observed_ranges_are_bound_to_successful_native_read_and_exact_bytes(tmp_path):
    manifest, projection, events = fixture(tmp_path)
    read, = observed_reads(encode(events), manifest, projection)
    assert read['start_line'] == read['end_line'] == 2
    assert read['path'] == '/host/a'


@pytest.mark.parametrize('mutation', ['content', 'path', 'request', 'nested', 'duplicate'])
def test_forged_and_unassociated_reads_cannot_support_citations(tmp_path, mutation):
    manifest, projection, events = fixture(tmp_path)
    if mutation == 'content':
        events[1]['tool_use_result']['file']['content'] = 'invented'
    elif mutation == 'path':
        events[1]['tool_use_result']['file']['filePath'] = '/etc/passwd'
    elif mutation == 'request':
        events.pop(0)
    elif mutation == 'nested':
        events[1]['parent_tool_use_id'] = 'nested'
    else:
        events.append(events[1])
    with pytest.raises(RouterError):
        observed_reads(encode(events), manifest, projection)
