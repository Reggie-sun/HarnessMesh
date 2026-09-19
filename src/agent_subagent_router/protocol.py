"""Worker assertions are separate from supervisor facts and parent acceptance."""
from dataclasses import dataclass

from .contracts import RouterError, strict_json


@dataclass(frozen=True)
class ParsedOutput:
    classification: str
    report: dict | None
    tool_observations: tuple[dict, ...] = ()


def validate_report(report: dict) -> None:
    expected = {'findings', 'proposed_changes', 'evidence_refs', 'uncertainties', 'questions'}
    if not isinstance(report, dict) or set(report) != expected:
        raise RouterError('REPORT_SCHEMA_ERROR')
    for key in ('findings', 'uncertainties', 'questions'):
        if not isinstance(report[key], list) or any(not isinstance(x, str) for x in report[key]):
            raise RouterError('REPORT_SCHEMA_ERROR')
    if not isinstance(report['proposed_changes'], list) or any(not isinstance(x, dict) for x in report['proposed_changes']):
        raise RouterError('REPORT_SCHEMA_ERROR')
    if not isinstance(report['evidence_refs'], list):
        raise RouterError('REPORT_SCHEMA_ERROR')
    for ref in report['evidence_refs']:
        if (not isinstance(ref, dict) or set(ref) != {'path', 'sha256', 'start_line', 'end_line'}
                or not isinstance(ref['path'], str) or not isinstance(ref['sha256'], str)
                or len(ref['sha256']) != 64 or type(ref['start_line']) is not int
                or type(ref['end_line']) is not int or not 1 <= ref['start_line'] <= ref['end_line']):
            raise RouterError('REPORT_SCHEMA_ERROR')


def decode_claude(raw: bytes, *, required_evidence=(), source_hashes=None,
                  allowed_tools=(), observed_reads=()) -> ParsedOutput:
    observations = []
    try:
        if raw and not raw.endswith(b'\n'):
            raise RouterError('PROTOCOL_ERROR', 'truncated JSONL')
        events = [strict_json(line) for line in raw.splitlines() if line.strip()]
        if any(not isinstance(event, dict) for event in events):
            raise RouterError('PROTOCOL_ERROR')
        terminals = [event for event in events if event.get('type') == 'result']
        for event in events:
            if event.get('type') == 'assistant':
                for block in event.get('message', {}).get('content', []):
                    if block.get('type') != 'tool_use':
                        continue
                    observation = {'tool': block.get('name'), 'id': block.get('id'),
                                   'status': 'attempted'}
                    observations.append(observation)
                    if block.get('name') not in allowed_tools:
                        raise RouterError('TOOL_POLICY_VIOLATION')
        if not terminals:
            raise RouterError('TERMINAL_MISSING')
        if len(terminals) != 1 or events[-1] is not terminals[0]:
            raise RouterError('PROTOCOL_ERROR', 'ambiguous terminal')
        terminal = terminals[0]
        if terminal.get('subtype') == 'error_max_structured_output_retries':
            raise RouterError('STRUCTURED_OUTPUT_EXHAUSTED')
        if terminal.get('is_error') is not False or terminal.get('subtype') != 'success':
            raise RouterError('RUNTIME_PROTOCOL_ERROR')
        if not isinstance(terminal.get('result'), str):
            raise RouterError('REPORT_SCHEMA_ERROR')
        report = strict_json(terminal['result'])
        validate_report(report)
        hashes = source_hashes or {}
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
            if ref['sha256'] != hashes.get(ref['path']) or cursor <= ref['end_line']:
                raise RouterError('EVIDENCE_INCOMPLETE')
            supported.add(ref['path'])
        if set(required_evidence) - supported:
            raise RouterError('EVIDENCE_INCOMPLETE')
        return ParsedOutput('PARSED', report, tuple(observations))
    except (RouterError, TypeError, KeyError, AttributeError) as exc:
        code = exc.code if isinstance(exc, RouterError) else 'PROTOCOL_ERROR'
        return ParsedOutput(code, None, tuple(observations))
