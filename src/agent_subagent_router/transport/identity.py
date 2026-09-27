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


def validate_response(profile, headers: dict, body: bytes, *, allow_tools=True) -> dict:
    is_stream = 'text/event-stream' in headers.get('content-type', '')
    if is_stream:
        starts = []
        final_usage = {}
        stop_reason = None
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
            if (not allow_tools and event.get('type') == 'content_block_start'
                    and event.get('content_block', {}).get('type') in ('tool_use', 'server_tool_use')):
                raise RouterError('TOOL_POLICY_VIOLATION', 'reporting request cannot call tools')
            if event.get('type') == 'message_stop':
                stopped = True
            if event.get('type') == 'message_delta' and isinstance(event.get('usage'), dict):
                final_usage.update(event['usage'])
            if event.get('type') == 'message_delta':
                stop_reason = event.get('delta', {}).get('stop_reason', stop_reason)
        if len(starts) != 1 or not stopped:
            raise RouterError('IDENTITY_UNVERIFIED', 'missing or ambiguous message identity')
        message = starts[0]
        if isinstance(message, dict):
            message = message | {'usage': (message.get('usage', {}) | final_usage), 'stop_reason': stop_reason}
    else:
        message = strict_json(body)
    if not isinstance(message, dict) or not message.get('model'):
        raise RouterError('IDENTITY_UNVERIFIED', 'response model absent')
    if message['model'] != profile.wire_model:
        raise RouterError('ROUTE_MISMATCH', 'upstream response model')
    if message.get('stop_reason') == 'max_tokens':
        raise RouterError('UPSTREAM_GENERATION_LIMIT')
    if (not allow_tools and any(block.get('type') in ('tool_use', 'server_tool_use')
                               for block in message.get('content', []))):
        raise RouterError('TOOL_POLICY_VIOLATION', 'reporting request cannot call tools')
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
