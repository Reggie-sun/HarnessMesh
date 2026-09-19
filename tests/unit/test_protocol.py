import json

import pytest

from agent_subagent_router.protocol import decode_claude


def report():
    return dict(findings=['owner located'], proposed_changes=[], evidence_refs=[],
                uncertainties=[], questions=[])


def terminal(value=None, **extras):
    return (json.dumps(dict(type='result', subtype='success', is_error=False,
                            result=json.dumps(report() if value is None else value)) | extras)+'\n').encode()


def test_one_terminal_is_reviewable_but_not_acceptance():
    result = decode_claude(terminal())
    assert result.classification == 'PARSED'
    assert result.report == report()
    assert not hasattr(result, 'accepted')


@pytest.mark.parametrize('raw,expected', [(b'', 'TERMINAL_MISSING'),
                        (terminal()+terminal(), 'PROTOCOL_ERROR'),
                        (terminal()[:-2], 'PROTOCOL_ERROR'),
                        (terminal()+b'garbage\n', 'PROTOCOL_ERROR'),
                        (terminal(report() | {'status': 'KEEP'}), 'REPORT_SCHEMA_ERROR'),
                        (terminal(subtype='error_max_structured_output_retries'), 'STRUCTURED_OUTPUT_EXHAUSTED')])
def test_invalid_output_never_becomes_success(raw, expected):
    parsed = decode_claude(raw)
    assert parsed.classification == expected and parsed.report is None


def test_questions_and_uncertainties_can_coexist():
    value = report() | {'questions': ['Which owner?'], 'uncertainties': ['cannot infer']}
    assert decode_claude(terminal(value)).classification == 'PARSED'


def test_claimed_evidence_without_observed_read_is_incomplete():
    value = report() | {'evidence_refs': [{'path': 'a.py', 'sha256': 'f'*64,
                                         'start_line': 1, 'end_line': 3}]}
    parsed = decode_claude(terminal(value), required_evidence=['a.py'], source_hashes={'a.py': 'f'*64})
    assert parsed.classification == 'EVIDENCE_INCOMPLETE' and parsed.report is None


def test_forbidden_delegation_event_is_not_hidden_by_success():
    event = {'type': 'assistant', 'message': {'content': [
        {'type': 'tool_use', 'id': 'tool1', 'name': 'Task', 'input': {}}]}}
    parsed = decode_claude(json.dumps(event).encode()+b'\n'+terminal())
    assert parsed.classification == 'TOOL_POLICY_VIOLATION'


def test_read_range_must_support_claimed_evidence_lines():
    value = report() | {'evidence_refs': [{'path': 'a.py', 'sha256': 'f'*64,
                                         'start_line': 500, 'end_line': 600}]}
    parsed = decode_claude(terminal(value), required_evidence=['a.py'], source_hashes={'a.py': 'f'*64},
                          observed_reads=[{'path': 'a.py', 'sha256': 'f'*64, 'status': 'complete',
                                           'start_line': 1, 'end_line': 1, 'truncated': False}])
    assert parsed.classification == 'EVIDENCE_INCOMPLETE'
