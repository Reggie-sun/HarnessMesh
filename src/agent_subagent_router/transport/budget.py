"""Bounded reporting hints for project requests; never extends sealed budgets."""
import math

from ..contracts import RouterError


def reporting_request(body, *, remaining_seconds, requests_remaining, wall_seconds):
    reserve = min(wall_seconds / 2, max(30, wall_seconds / 4))
    final = remaining_seconds <= reserve or requests_remaining <= 1
    phase = 'FINAL_REPORT' if final else 'EXPLORE'
    notice = (
        f'HarnessMesh budget: phase={phase}; '
        f'wall_seconds_remaining={max(0, math.floor(remaining_seconds))}; '
        f'requests_remaining_including_this={requests_remaining}. '
        'This is a control-plane budget notice, not source evidence. '
        'Use the original report schema and cite only verified actual reads. ')
    if final:
        notice += ('Stop exploration now. No tools are offered for this request. '
                   'Return the final JSON report immediately. Put missing evidence and '
                   'unfinished checks in questions/uncertainties; do not invent completion.')
    else:
        notice += ('Batch independent necessary Reads, prioritize required evidence, avoid rereading '
                   'unchanged material, and reserve time for a concise final JSON report.')
    original = body.get('messages', [])
    if not isinstance(original, list) or any(not isinstance(m, dict) for m in original):
        raise RouterError('INVALID_BODY')
    messages = list(original)
    block = {'type': 'text', 'text': notice}
    if messages and messages[-1].get('role') == 'user':
        last = messages[-1]
        content = last.get('content', [])
        if isinstance(content, str):
            content = [{'type': 'text', 'text': content}]
        if not isinstance(content, list) or any(not isinstance(b, dict) for b in content):
            raise RouterError('INVALID_BODY')
        messages[-1] = last | {'content': [*content, block]}
    else:
        messages.append({'role': 'user', 'content': [block]})
    result = body | {'messages': messages}
    if final:
        result['tools'] = []
        result.pop('tool_choice', None)
    return result, phase
