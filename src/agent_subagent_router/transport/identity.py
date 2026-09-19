"""Mechanical endpoint declarations, never a model's self-description."""
import re

from ..contracts import RouterError, strict_json


def validate_request(profile, body: dict, *, allowed_tools=()):
    if not isinstance(body, dict) or body.get('model') != profile.wire_model:
        raise RouterError('ROUTE_MISMATCH', 'request model')
    thinking = body.get('thinking', {})
    if (not isinstance(thinking, dict) or thinking.get('type') not in ('enabled', 'adaptive')
            or (thinking.get('type') == 'enabled'
                and (type(thinking.get('budget_tokens')) is not int or thinking['budget_tokens'] <= 0))):
        raise RouterError('ROUTE_MISMATCH', 'thinking must be enabled')
    if set(thinking) - {'type', 'budget_tokens'}:
        raise RouterError('ROUTE_MISMATCH', 'unrecognized thinking fields')
    if not isinstance(body.get('output_config'), dict) or body['output_config'].get('effort') != profile.effort:
        raise RouterError('ROUTE_MISMATCH', 'request effort')
    tools = body.get('tools', [])
    if not isinstance(tools, list) or any(not isinstance(t, dict) or t.get('name') not in allowed_tools for t in tools):
        raise RouterError('TOOL_POLICY_VIOLATION')


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', value)


def validate_response(profile, headers: dict, body: bytes) -> dict:
    is_stream = 'text/event-stream' in headers.get('content-type', '')
    if is_stream:
        starts = []
        final_usage = {}
        stopped = False
        for block in body.replace(b'\r\n', b'\n').split(b'\n\n'):
            data = b'\n'.join(line[5:].lstrip() for line in block.splitlines() if line.startswith(b'data:'))
            if not data:
                continue
            event = strict_json(data)
            if not isinstance(event, dict) or stopped:
                raise RouterError('PROTOCOL_ERROR', 'invalid upstream stream ordering')
            if event.get('type') == 'message_start':
                starts.append(event.get('message', {}))
            elif not starts and event.get('type') != 'ping':
                raise RouterError('IDENTITY_UNVERIFIED', 'content precedes identity')
            if event.get('type') == 'error':
                raise RouterError('UPSTREAM_PROTOCOL_ERROR')
            if event.get('type') == 'message_stop':
                stopped = True
            if event.get('type') == 'message_delta' and isinstance(event.get('usage'), dict):
                final_usage.update(event['usage'])
        if len(starts) != 1 or not stopped:
            raise RouterError('IDENTITY_UNVERIFIED', 'missing or ambiguous message identity')
        message = starts[0]
        if isinstance(message, dict):
            message = message | {'usage': (message.get('usage', {}) | final_usage)}
    else:
        message = strict_json(body)
    if not isinstance(message, dict) or not message.get('model'):
        raise RouterError('IDENTITY_UNVERIFIED', 'response model absent')
    if message['model'] != profile.wire_model:
        raise RouterError('ROUTE_MISMATCH', 'upstream response model')
    request_id = headers.get('request-id') or headers.get('x-request-id') or message.get('id')
    if not _identifier(request_id) or not _identifier(message.get('id')):
        raise RouterError('IDENTITY_UNVERIFIED', 'response association absent')
    usage = message.get('usage', {})
    if not isinstance(usage, dict):
        raise RouterError('UPSTREAM_PROTOCOL_ERROR')
    return {'classification': 'IDENTITY_VERIFIED', 'response_model': message['model'],
            'upstream_request_id': request_id, 'message_id': message['id'],
            'usage': {k: v for k, v in usage.items() if k in
                      ('input_tokens', 'output_tokens', 'cache_creation_input_tokens',
                       'cache_read_input_tokens') and type(v) is int and v >= 0},
            'proof': 'authenticated_endpoint_declaration', 'actual_cost': None}
