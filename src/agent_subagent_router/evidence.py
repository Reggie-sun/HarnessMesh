"""Bind native successful Read results to exact sealed bytes, not model citations."""
from pathlib import Path, PurePosixPath

from .contracts import RouterError, hash_bytes, strict_json


def observed_reads(raw: bytes, manifest: dict, projection: dict, *, ignored_execution_paths=()) -> list[dict]:
    sources = {item['path']: item for item in manifest['sources']}
    mapping = {'/work/'+item['execution_path']: item for item in projection['source_map']}
    requests = {}
    completed = set()
    reads = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        event = strict_json(line)
        if not isinstance(event, dict) or event.get('parent_tool_use_id') is not None:
            raise RouterError('TOOL_POLICY_VIOLATION')
        content = event.get('message', {}).get('content', [])
        if event.get('type') == 'assistant':
            for block in content:
                if block.get('type') == 'tool_use':
                    if block.get('id') in requests:
                        raise RouterError('PROTOCOL_ERROR', 'duplicate native tool ID')
                    requests[block.get('id')] = block
        if event.get('type') != 'user':
            continue
        successful = [b for b in content if b.get('type') == 'tool_result' and not b.get('is_error')]
        result = event.get('tool_use_result', {})
        if not isinstance(result, dict) or result.get('type') != 'text':
            continue
        file = result.get('file', {})
        if len(successful) != 1 or not isinstance(file, dict):
            raise RouterError('EVIDENCE_INCOMPLETE')
        identifier = successful[0].get('tool_use_id')
        request = requests.get(identifier, {})
        if request.get('name') != 'Read' or identifier in completed:
            raise RouterError('EVIDENCE_INCOMPLETE')
        path = file.get('filePath')
        if path in ignored_execution_paths:
            continue  # Candidate reads cannot establish immutable baseline evidence.
        origin = mapping.get(path)
        argument = request.get('input', {}).get('file_path', '')
        logical = str(PurePosixPath('/work')/argument)
        if origin is None or logical != path:
            raise RouterError('EVIDENCE_INCOMPLETE', 'Read is outside exact projection')
        source = sources[origin['source_path']]
        data = (Path(manifest['snapshot_root'])/source['snapshot_path']).read_bytes()
        if hash_bytes(data) != source['sha256']:
            raise RouterError('SNAPSHOT_CHANGED')
        try:
            lines = data.decode('utf-8').split('\n')
        except UnicodeError as exc:
            raise RouterError('EVIDENCE_INCOMPLETE') from exc
        start, count = file.get('startLine'), file.get('numLines')
        if (type(start) is not int or type(count) is not int or start < 1 or count < 1
                or start+count-1 > len(lines) or file.get('totalLines') != len(lines)
                or '\n'.join(lines[start-1:start+count-1]) != file.get('content')):
            raise RouterError('EVIDENCE_INCOMPLETE', 'native Read differs from sealed lines')
        completed.add(identifier)
        reads.append({'path': source['path'], 'sha256': source['sha256'], 'status': 'complete',
                      'start_line': start, 'end_line': start+count-1,
                      'truncated': False, 'native_tool_use_id': identifier})
    return reads
