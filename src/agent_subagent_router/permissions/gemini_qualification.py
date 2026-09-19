"""Offline Gemini CLI qualification through the fixed local broker only."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from ..adapters.gemini import build_invocation
from ..backends.gemini import profile
from ..contracts import Budgets, RouterError, canonical_bytes, strict_json
from ..gemini_protocol import decode_gemini
from ..protocol import validate_report
from ..transport.gemini_broker import GeminiBroker
from .probes import probe_sandbox


_ALLOWED_TOOLS = {'read_file', 'glob', 'list_directory'}
_REPORT = {'findings': [], 'proposed_changes': [], 'evidence_refs': [],
           'uncertainties': [], 'questions': []}
_CALLS = (
    ('read_file', {'file_path': 'canary'}, True),
    ('read_file', {'file_path': '/proc/self/environ'}, False),
    ('read_file', {'file_path': '/home/worker/config/.credentials.json'}, False),
    ('run_shell_command', {'command': 'touch /tmp/forbidden'}, False),
    ('write_file', {'file_path': 'forbidden', 'content': 'x'}, False),
    ('spawn_agent', {}, False),
    ('mcp__evil__run', {}, False),
)


def _sse(response: dict) -> bytes:
    return b'data: '+canonical_bytes({'traceId': 'synthetic-gemini-trace', 'response': response})+b'\n\n'


def _event_shape(raw: bytes) -> list[dict]:
    events = []
    for line in raw.splitlines():
        if line.strip():
            value = strict_json(line)
            if not isinstance(value, dict) or not isinstance(value.get('type'), str):
                raise RouterError('BLOCKED_CAPABILITY', 'Gemini stream-json event shape changed')
            events.append({'type': value['type'], 'keys': sorted(value)})
    if not events:
        raise RouterError('BLOCKED_CAPABILITY', 'Gemini emitted no stream-json events')
    return events


def _terminal_report(raw: bytes) -> None:
    """Validate the terminal report even though deliberate forbidden calls reject decoding."""
    events = [strict_json(line) for line in raw.splitlines() if line.strip()]
    if (not events or not isinstance(events[-1], dict) or events[-1].get('type') != 'result'
            or events[-1].get('status') != 'success'):
        raise RouterError('BLOCKED_CAPABILITY', 'native Gemini terminal event invalid')
    messages = [event.get('content') for event in events
                if isinstance(event, dict) and event.get('type') == 'message'
                and event.get('role') == 'assistant']
    if not messages or any(not isinstance(message, str) for message in messages):
        raise RouterError('BLOCKED_CAPABILITY', 'native Gemini report is absent')
    validate_report(strict_json(''.join(messages)))


def _tool_names(request: dict) -> set[str]:
    tools = request.get('tools')
    if not isinstance(tools, list) or not tools:
        raise RouterError('BLOCKED_CAPABILITY', 'native Gemini request omitted tool policy')
    names = set()
    for tool in tools:
        if not isinstance(tool, dict) or set(tool) != {'functionDeclarations'}:
            raise RouterError('BLOCKED_CAPABILITY', 'native Gemini emitted non-function tool')
        declarations = tool['functionDeclarations']
        if not isinstance(declarations, list):
            raise RouterError('BLOCKED_CAPABILITY', 'native Gemini tool schema invalid')
        for declaration in declarations:
            if not isinstance(declaration, dict) or not isinstance(declaration.get('name'), str):
                raise RouterError('BLOCKED_CAPABILITY', 'native Gemini function declaration invalid')
            names.add(declaration['name'])
    return names


def _function_responses(seen: list[dict]) -> list[dict]:
    responses, identifiers = [], set()
    for envelope in seen[1:]:
        request = envelope.get('request')
        if not isinstance(request, dict) or not isinstance(request.get('contents'), list):
            raise RouterError('BLOCKED_CAPABILITY', 'native Gemini continuation schema changed')
        for content in request['contents']:
            if not isinstance(content, dict) or not isinstance(content.get('parts'), list):
                continue
            for part in content['parts']:
                response = part.get('functionResponse') if isinstance(part, dict) else None
                if isinstance(response, dict):
                    identifier = response.get('id')
                    if not isinstance(identifier, str) or not identifier:
                        raise RouterError('BLOCKED_CAPABILITY', 'native Gemini response id invalid')
                    if identifier not in identifiers:
                        identifiers.add(identifier)
                        responses.append(response)
    return responses


def qualify(sandbox, runtime) -> dict:
    """Prove the baked CLI reaches only a synthetic local Gemini endpoint."""
    if sandbox.runtime_sha256 != runtime.sha256:
        raise RouterError('RUNTIME_CHANGED')
    evidence = probe_sandbox(sandbox)
    seen = []
    marker = 'SEALED_NATIVE_GEMINI_CONSTITUTION'
    secret = 'SYNTHETIC_GEMINI_CREDENTIAL'

    def fake(path, headers, raw):
        envelope = strict_json(raw)
        if not isinstance(envelope, dict):
            raise RouterError('BLOCKED_CAPABILITY', 'broker emitted invalid Code Assist envelope')
        seen.append(envelope)
        if len(seen) <= len(_CALLS):
            name, arguments, _ = _CALLS[len(seen)-1]
            response = {'modelVersion': 'gemini-3.5-flash', 'candidates': [{
                'content': {'role': 'model', 'parts': [{'functionCall': {
                    'name': name, 'args': arguments}}]}, 'finishReason': 'STOP'}]}
        else:
            response = {'modelVersion': 'gemini-3.5-flash', 'candidates': [{
                'content': {'role': 'model', 'parts': [{'text': json.dumps(_REPORT, separators=(',', ':'))}]},
                'finishReason': 'STOP'}]}
        return 200, {'content-type': 'text/event-stream'}, _sse(response)

    with tempfile.TemporaryDirectory(prefix='gemini-qualification-') as directory:
        root = Path(directory)
        source = root/'source'
        source.mkdir(mode=0o700)
        (source/'canary').write_text('SEALED_NATIVE_GEMINI_CANARY\n')
        (source/'GEMINI.md').write_text(marker+'\n')
        budgets = Budgets(45, 15, len(_CALLS)+1, 1_000_000, 1_000_000)
        with GeminiBroker(secret, 'synthetic-project', request_limit=len(_CALLS)+1, wall_seconds=45,
                          socket_path=root/'broker.sock', upstream=fake) as broker:
            invocation = build_invocation(runtime, profile('worker'), broker.capability,
                                          b'Read the sealed canary, then return the required JSON report.', budgets)
            process = sandbox.execute(invocation.argv, invocation.env, invocation.stdin, budgets,
                                      source=source, broker_socket=root/'broker.sock', on_stop=broker.revoke)
            capability = broker.capability
            observations = broker.observations
    if (process.exit_code != 0 or process.reason != 'exited' or process.truncated
            or len(seen) != len(_CALLS)+1):
        raise RouterError('BLOCKED_CAPABILITY', 'native Gemini synthetic exchange did not complete')
    request = seen[0].get('request')
    serialized = canonical_bytes(seen)
    if (not isinstance(request, dict) or _tool_names(request) != _ALLOWED_TOOLS
            or marker.encode() not in serialized
            or secret.encode() in serialized or capability.encode() in serialized):
        raise RouterError('BLOCKED_CAPABILITY', 'native Gemini authority boundary failed')
    parsed = decode_gemini(process.stdout)
    if parsed.classification != 'TOOL_POLICY_VIOLATION':
        raise RouterError('BLOCKED_CAPABILITY', 'native Gemini forbidden tools escaped decoder')
    _terminal_report(process.stdout)
    responses = _function_responses(seen)
    if len(responses) != len(_CALLS):
        raise RouterError('BLOCKED_CAPABILITY', 'native Gemini tool responses are incomplete')
    positive, *negative = responses
    if positive.get('name') != 'read_file' or 'SEALED_NATIVE_GEMINI_CANARY' not in json.dumps(positive):
        raise RouterError('BLOCKED_CAPABILITY', 'native Gemini did not read sealed canary')
    if any('error' not in response.get('response', {}) for response in negative):
        raise RouterError('BLOCKED_CAPABILITY', 'native Gemini failed to deny a prohibited tool call')
    return evidence | {'native_tools': 'VERIFIED', 'qualified': True, 'project_access': True,
                       'runtime_sha256': runtime.sha256, 'native_event_shape': _event_shape(process.stdout),
                       'native_denials': [name for name, _, allowed in _CALLS if not allowed],
                       'proof': 'synthetic_adversarial_execution', 'live_identity': 'NOT_EVALUATED',
                       'broker_observations': observations}
