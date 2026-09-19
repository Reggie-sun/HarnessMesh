"""Bind Gemini native read responses to frozen projection bytes."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from .contracts import RouterError, hash_bytes, strict_json


_ALLOWED_TOOLS = frozenset(('read_file', 'glob', 'list_directory'))


def _source_map(manifest: dict, projection: dict) -> dict[str, dict]:
    try:
        sources = manifest['sources']
        source_map = projection['source_map']
    except (KeyError, TypeError) as exc:
        raise RouterError('EVIDENCE_INCOMPLETE', 'source map missing') from exc
    if not isinstance(sources, list) or not isinstance(source_map, list):
        raise RouterError('EVIDENCE_INCOMPLETE', 'source map schema')
    source_by_path = {}
    for source in sources:
        if (not isinstance(source, dict) or not isinstance(source.get('path'), str)
                or not isinstance(source.get('snapshot_path'), str)
                or not isinstance(source.get('sha256'), str)):
            raise RouterError('EVIDENCE_INCOMPLETE', 'source schema')
        source_by_path[source['path']] = source
    mapped = {}
    for item in source_map:
        if (not isinstance(item, dict) or set(item) != {'source_path', 'execution_path', 'sha256'}
                or not all(isinstance(item.get(key), str) and item[key]
                           for key in ('source_path', 'execution_path', 'sha256'))):
            raise RouterError('EVIDENCE_INCOMPLETE', 'projection source map schema')
        execution = PurePosixPath(item['execution_path'])
        source = source_by_path.get(item['source_path'])
        if (execution.is_absolute() or '..' in execution.parts or str(execution) == '.'
                or source is None or source['sha256'] != item['sha256']
                or str(execution) in mapped):
            raise RouterError('EVIDENCE_INCOMPLETE', 'projection source map mismatch')
        mapped[str(execution)] = source
    return mapped


def _responses(wire_requests) -> dict[str, dict]:
    if not isinstance(wire_requests, list):
        raise RouterError('EVIDENCE_INCOMPLETE', 'wire request capture missing')
    responses = {}
    for envelope in wire_requests:
        try:
            contents = envelope['request']['contents']
        except (KeyError, TypeError) as exc:
            raise RouterError('EVIDENCE_INCOMPLETE', 'wire request schema') from exc
        if not isinstance(contents, list):
            raise RouterError('EVIDENCE_INCOMPLETE', 'wire contents schema')
        for content in contents:
            if not isinstance(content, dict) or not isinstance(content.get('parts'), list):
                raise RouterError('EVIDENCE_INCOMPLETE', 'wire part schema')
            for part in content['parts']:
                response = part.get('functionResponse') if isinstance(part, dict) else None
                if response is None:
                    continue
                if (not isinstance(response, dict) or set(response) != {'id', 'name', 'response'}
                        or not isinstance(response['id'], str) or not response['id']
                        or response['name'] not in _ALLOWED_TOOLS
                        or not isinstance(response['response'], dict)):
                    raise RouterError('EVIDENCE_INCOMPLETE', 'tool response schema')
                if (response['name'] == 'read_file'
                        and (set(response['response']) != {'output'}
                             or not isinstance(response['response']['output'], str))):
                    raise RouterError('EVIDENCE_INCOMPLETE', 'read response schema')
                previous = responses.get(response['id'])
                if previous is not None and previous != response:
                    raise RouterError('EVIDENCE_INCOMPLETE', 'conflicting tool response')
                responses[response['id']] = response
    return responses


def _frozen_lines(manifest: dict, source: dict) -> list[str]:
    try:
        data = (Path(manifest['snapshot_root'])/source['snapshot_path']).read_bytes()
    except (KeyError, OSError, TypeError) as exc:
        raise RouterError('SNAPSHOT_CHANGED') from exc
    if hash_bytes(data) != source['sha256']:
        raise RouterError('SNAPSHOT_CHANGED')
    try:
        return data.decode('utf-8').split('\n')
    except UnicodeError as exc:
        raise RouterError('EVIDENCE_INCOMPLETE', 'native read was not text') from exc


def observed_gemini_reads(raw: bytes, manifest: dict, projection: dict, wire_requests: list[dict]) -> list[dict]:
    """Accept only successful /work read_file calls whose returned text matches frozen bytes."""
    if not isinstance(raw, bytes) or (raw and not raw.endswith(b'\n')):
        raise RouterError('PROTOCOL_ERROR', 'truncated native JSONL')
    mapped, responses = _source_map(manifest, projection), _responses(wire_requests)
    requests, completed, reads = {}, set(), []
    for line in raw.splitlines():
        if not line.strip():
            continue
        event = strict_json(line)
        if not isinstance(event, dict):
            raise RouterError('PROTOCOL_ERROR')
        if event.get('type') == 'tool_use':
            name, identifier, parameters = event.get('tool_name'), event.get('tool_id'), event.get('parameters')
            if (name not in _ALLOWED_TOOLS or not isinstance(identifier, str)
                    or not identifier.startswith(name+'__') or identifier == name+'__'
                    or not isinstance(parameters, dict)):
                raise RouterError('EVIDENCE_INCOMPLETE', 'native tool request schema')
            if (name == 'read_file'
                    and (set(parameters) - {'file_path', 'start_line', 'end_line'}
                         or not isinstance(parameters.get('file_path'), str))):
                raise RouterError('EVIDENCE_INCOMPLETE', 'native read request schema')
            if identifier in requests:
                raise RouterError('PROTOCOL_ERROR', 'duplicate native tool id')
            requests[identifier] = (name, parameters)
        elif event.get('type') == 'tool_result' and event.get('status') == 'success':
            identifier = event.get('tool_id')
            if identifier not in requests or identifier in completed or event.get('truncated'):
                raise RouterError('EVIDENCE_INCOMPLETE', 'native tool completion')
            name, parameters = requests[identifier]
            response_id = identifier.removeprefix(name+'__')
            response = responses.get(response_id)
            if response is None or response['name'] != name:
                raise RouterError('EVIDENCE_INCOMPLETE', 'missing correlated tool response')
            completed.add(identifier)
            if name != 'read_file':
                continue
            execution = parameters['file_path'].removeprefix('/work/')
            source = mapped.get(execution)
            if parameters['file_path'] != '/work/'+execution or source is None:
                raise RouterError('EVIDENCE_INCOMPLETE', 'read outside exact /work projection')
            lines = _frozen_lines(manifest, source)
            start, end = parameters.get('start_line', 1), parameters.get('end_line', len(lines))
            if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
                raise RouterError('EVIDENCE_INCOMPLETE', 'native read range')
            expected = '\n'.join(lines[start-1:end])
            if end < len(lines):
                expected += '\n'
            if response['response']['output'] != expected:
                raise RouterError('EVIDENCE_INCOMPLETE', 'native read differs from frozen range')
            reads.append({'path': source['path'], 'sha256': source['sha256'], 'status': 'complete',
                          'start_line': start, 'end_line': end, 'truncated': False,
                          'native_tool_use_id': identifier})
    expected = {identifier.removeprefix(name+'__'): name for identifier, (name, _parameters) in requests.items()}
    if any(expected.get(identifier) != response['name'] for identifier, response in responses.items()):
        raise RouterError('EVIDENCE_INCOMPLETE', 'uncorrelated or spoofed tool response')
    return reads
