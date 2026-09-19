"""Gemini 0.60 stream-json decoding without making identity assertions."""
from .contracts import RouterError, strict_json
from .protocol import ParsedOutput, validate_report


_TOOLS = {'read_file': 'read_file', 'ReadFileTool': 'read_file',
          'glob': 'glob', 'GlobTool': 'glob',
          'list_directory': 'list_directory', 'LSTool': 'list_directory'}


def _evidence_complete(report: dict, required_evidence, source_hashes, observed_reads) -> None:
    supported = set()
    for ref in report['evidence_refs']:
        ranges = sorted((item.get('start_line'), item.get('end_line')) for item in observed_reads
                        if item.get('path') == ref['path'] and item.get('sha256') == ref['sha256']
                        and item.get('status') == 'complete' and not item.get('truncated')
                        and type(item.get('start_line')) is int and type(item.get('end_line')) is int)
        cursor = ref['start_line']
        for start, end in ranges:
            if start <= cursor <= end:
                cursor = end+1
        if ref['sha256'] != source_hashes.get(ref['path']) or cursor <= ref['end_line']:
            raise RouterError('EVIDENCE_INCOMPLETE')
        supported.add(ref['path'])
    if set(required_evidence) - supported:
        raise RouterError('EVIDENCE_INCOMPLETE')


def decode_gemini(raw: bytes, *, required_evidence=(), source_hashes=None,
                  observed_reads=()) -> ParsedOutput:
    """Decode actual Gemini stream-json events.

    The init ``model`` is runtime-local configuration only.  Upstream identity
    remains exclusively a transport/broker responsibility.
    """
    observations = []
    try:
        if not isinstance(raw, bytes) or (raw and not raw.endswith(b'\n')):
            raise RouterError('PROTOCOL_ERROR', 'truncated JSONL')
        events = [strict_json(line) for line in raw.splitlines() if line.strip()]
        if any(not isinstance(item, dict) for item in events):
            raise RouterError('PROTOCOL_ERROR')
        terminals = [item for item in events if item.get('type') == 'result']
        if not terminals:
            raise RouterError('TERMINAL_MISSING')
        if len(terminals) != 1 or events[-1] is not terminals[0]:
            raise RouterError('PROTOCOL_ERROR', 'ambiguous terminal')
        initializers = [item for item in events if item.get('type') == 'init']
        if len(initializers) != 1 or not isinstance(initializers[0].get('model'), str):
            raise RouterError('PROTOCOL_ERROR', 'missing or ambiguous init')

        messages = []
        seen_tool_ids = set()
        for item in events:
            if item.get('type') == 'tool_use':
                name, identifier = item.get('tool_name'), item.get('tool_id')
                if not isinstance(name, str) or not isinstance(identifier, str):
                    raise RouterError('PROTOCOL_ERROR', 'invalid tool event')
                if identifier in seen_tool_ids:
                    raise RouterError('PROTOCOL_ERROR', 'duplicate tool_id')
                seen_tool_ids.add(identifier)
                normalized = _TOOLS.get(name)
                if normalized is None:
                    raise RouterError('TOOL_POLICY_VIOLATION')
                observations.append({'tool': normalized, 'id': identifier, 'status': 'attempted'})
            elif item.get('type') == 'message' and item.get('role') == 'assistant':
                content = item.get('content')
                if not isinstance(content, str):
                    raise RouterError('PROTOCOL_ERROR', 'invalid assistant content')
                messages.append(content)

        if terminals[0].get('status') != 'success':
            raise RouterError('RUNTIME_PROTOCOL_ERROR')
        if not messages:
            raise RouterError('REPORT_SCHEMA_ERROR')
        report = strict_json(''.join(messages))
        validate_report(report)
        _evidence_complete(report, required_evidence, source_hashes or {}, observed_reads)
        return ParsedOutput('PARSED', report, tuple(observations))
    except (RouterError, TypeError, KeyError, AttributeError) as exc:
        code = exc.code if isinstance(exc, RouterError) else 'PROTOCOL_ERROR'
        return ParsedOutput(code, None, tuple(observations))
