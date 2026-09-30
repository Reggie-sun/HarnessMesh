"""Check decoded response fragments before protocol validation or persistence."""
from collections import defaultdict
from itertools import permutations

from ..contracts import RouterError, canonical_bytes, strict_json
from ..receipts import redact_known_secrets


def validate_response_secrets(headers, body, secrets):
    def check(data):
        if redact_known_secrets(data, secrets)[1]:
            raise RouterError('UPSTREAM_SECRET_REFLECTION')

    # Only these three upstream fields can enter image identity receipts. Scan
    # their values together before validation/capture, independent of wire order.
    header_values = [value.encode() for name, value in headers.items()
                     if isinstance(name, str) and isinstance(value, str)
                     and name.lower() in ('content-type', 'x-request-id', 'request-id')]
    if len(header_values) > 3:
        raise RouterError('UPSTREAM_PROTOCOL_ERROR')
    for value in header_values:
        check(value)
    for count in range(2, len(header_values) + 1):
        for values in permutations(header_values, count):
            check(b''.join(values))
    check(body)
    if 'text/event-stream' in headers.get('content-type', ''):
        documents = [b'\n'.join(line[5:].lstrip() for line in block.splitlines()
                               if line.startswith(b'data:'))
                     for block in body.replace(b'\r\n', b'\n').split(b'\n\n')]
    else:
        documents = [body]
    fragments = defaultdict(list)
    for document in documents:
        if not document:
            continue
        value = strict_json(document)
        stream = None
        payload = None
        if isinstance(value, dict):
            kind = value.get('type', '')
            # Use only the identity fields validated by the corresponding protocol.
            # Kimi start/delta describe the same block, without Codex response IDs.
            if kind in ('content_block_start', 'content_block_delta', 'content_block_stop'):
                stream = canonical_bytes({'family': 'kimi-block', 'index': value.get('index')})
                payload = value.get('content_block' if kind == 'content_block_start' else 'delta')
                if isinstance(payload, dict):
                    fields = {'text': ('text',), 'thinking': ('thinking', 'signature'),
                              'redacted_thinking': ('data',), 'text_delta': ('text',),
                              'thinking_delta': ('thinking',), 'signature_delta': ('signature',)}
                    payload = {field: payload.get(field) for field in fields.get(payload.get('type'), ())}
            elif kind in ('response.output_text.delta', 'response.output_text.done',
                          'response.reasoning_summary_text.delta', 'response.reasoning_summary_text.done'):
                part = 'summary_index' if 'reasoning_summary_text' in kind else 'content_index'
                stream = canonical_bytes({'family': kind.rsplit('.', 1)[0],
                    **{key: value.get(key) for key in ('response_id', 'item_id', 'output_index', part)}})
                payload = {'text': value.get('delta' if kind.endswith('.delta') else 'text')}
            elif kind in ('response.output_item.added', 'response.output_item.done'):
                item = value.get('item')
                if isinstance(item, dict) and item.get('type') == 'reasoning':
                    stream = canonical_bytes({'family': 'codex-reasoning-item',
                        'response_id': value.get('response_id'), 'output_index': value.get('output_index'),
                        'item_id': item.get('id')})
                    payload = {'encrypted_content': item.get('encrypted_content')}
        # Reconstruct the actual protocol payload independently of auxiliary fields.
        # Full paths below keep nested same-name metadata out of these streams.
        if isinstance(payload, dict):
            for field in ('text', 'thinking', 'signature', 'data', 'encrypted_content'):
                piece = payload.get(field)
                if isinstance(piece, str):
                    fragments[(stream, 'protocol', field)].append(piece)
        pending = [((), value)]
        while pending:
            path, value = pending.pop()
            if isinstance(value, str):
                check(value.encode())
                fragments[path].append(value)
                if stream is not None:
                    fragments[(stream, path)].append(value)
            elif isinstance(value, dict):
                for key in value:
                    check(key.encode())
                # JSON content arrays also carry typed parts; unused fields on a
                # different part type must not interrupt a semantic field stream.
                if isinstance(value.get('type'), str):
                    path += (('@type', value['type']),)
                pending.extend((path+(key,), item) for key, item in reversed(list(value.items())))
            elif isinstance(value, list):
                pending.extend((path+(('item',),), item) for item in reversed(value))
    # Protocol status/terminal errors must not bypass checking earlier fragments.
    # Group by protocol payload or full path, never just a leaf field name.
    for pieces in fragments.values():
        check(''.join(pieces).encode())
