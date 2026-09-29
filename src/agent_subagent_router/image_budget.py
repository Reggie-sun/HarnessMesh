"""Read canonical parent-observed quota/cost evidence, and consume probe once."""
from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path

from .contracts import RouterError, canonical_bytes, hash_bytes
from .image_runtime import API_SPEC_SHA
from .receipts import atomic_json
from .image_contract import IMAGE_PROVIDERS


def input_digest(task):
    from .adapters.image_claude import visible_text
    return hash_bytes(canonical_bytes({'backend': task['backend'], 'model': task['model'],
        'profile': task['profile'], 'effort': task['effort'], 'system': task['system_text'],
        'text': visible_text(task), 'images': [{k: x[k] for k in
            ('image_id', 'sha256', 'byte_length', 'width', 'height')} for x in task['images']],
        'budgets': task['budgets']}))


def require_probe_budget(store, identifier, task, fingerprint):
    # MiniMax engineering is authorized; its authenticated accounting/budget is not yet frozen.
    if task.get('backend') == 'minimax':
        raise RouterError('IMAGE_MINIMAX_BUDGET_NOT_AUTHORIZED')
    if not identifier:
        raise RouterError('IMAGE_ACCOUNT_BUDGET_UNVERIFIED')
    record = store.read(identifier)
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(
            record['observed_at'].replace('Z', '+00:00'))).total_seconds()
        account = record['authenticated_account_evidence']
        valid = (record['kind'] == 'image-probe-budget/v1'
            and record['classification'] == 'AUTHORIZED'
            and record['evidence_kind'] == 'parent-observed-authenticated-account'
            and record['spec_sha256'] == API_SPEC_SHA
            and record['credential_fingerprint'] == fingerprint
            and record['input_digest'] == input_digest(task)
            and record['backend'] == task['backend'] and record['model'] == task['model']
            and record['profile'] == task['profile'] and record['effort'] == task['effort']
            and record['request_limit'] == 1 and record['generation_tokens'] == 2048
            and 0 <= age <= 86400
            and account['credential_fingerprint'] == fingerprint
            and account['provider'] == IMAGE_PROVIDERS[task['backend']]
            and account['authenticated'] is True
            and isinstance(account['source'], str) and account['source'].startswith('https://')
            and bool(record['artifacts']))
        if not valid:
            raise ValueError()
        # ReceiptStore verifies saved bytes; require the parent-observed facts to
        # be the exact artifact, rather than a standalone caller assertion.
        from .contracts import strict_json
        artifact = next(x for x in record['artifacts'] if x['path'] == 'account-evidence.json')
        if (artifact['producer'] != 'parent-account-observer'
                or strict_json((store.root/identifier/artifact['path']).read_bytes()) != account):
            raise ValueError()
        if task['backend'] == 'codex':
            bound = Decimal(str(record['cost_upper_bound_usd']))
            if not bound.is_finite() or not 0 < bound <= Decimal('1'):
                raise ValueError()
            if Decimal(str(account['available_usd'])) < bound:
                raise ValueError()
            accounting = record['frozen_accounting']
            # The parent must freeze actual image/token accounting and price sources;
            # no model request or token-counting call is used to discover a bound.
            if (accounting['model'] != task['model']
                    or accounting['input_digest'] != input_digest(task)
                    or accounting['generation_tokens'] != 2048
                    or type(accounting['input_tokens_upper']) is not int
                    or accounting['input_tokens_upper'] < 1
                    or not accounting['pricing_source'].startswith('https://developers.openai.com/')
                    or not accounting['image_accounting_source'].startswith('https://developers.openai.com/')):
                raise ValueError()
            artifact = next(x for x in record['artifacts'] if x['path'] == 'frozen-accounting.json')
            from .adapters.image_claude import visible_text
            text_upper = len(task['system_text'].encode()) + len(visible_text(task).encode())
            if (artifact['producer'] != 'parent-account-observer'
                    or strict_json((store.root/identifier/artifact['path']).read_bytes()) != accounting
                    or type(accounting['text_tokens_upper']) is not int
                    or accounting['text_tokens_upper'] < text_upper
                    or type(accounting['image_tokens_upper']) is not int
                    or accounting['image_tokens_upper'] < len(task['images'])*4096
                    or accounting['input_tokens_upper'] < accounting['text_tokens_upper'] + accounting['image_tokens_upper']):
                raise ValueError()
            computed = (Decimal(accounting['input_tokens_upper']) * Decimal(str(accounting['input_usd_per_million']))
                + Decimal(2048) * Decimal(str(accounting['output_usd_per_million']))) / Decimal(1000000)
            if not computed.is_finite() or not 0 < computed <= bound:
                raise ValueError()
        elif (type(account['available_tokens']) is not int
                or type(record['required_tokens_upper']) is not int
                or record['required_tokens_upper'] < 2048
                or account['available_tokens'] < record['required_tokens_upper']):
            raise ValueError()
    except (KeyError, TypeError, ValueError, ArithmeticError, StopIteration, OSError):
        raise RouterError('IMAGE_ACCOUNT_BUDGET_UNVERIFIED') from None
    return record


def probe_reservation_root():
    # CLI --state relocates evidence, never monetary authorization. One host
    # ledger prevents a fresh state directory from restoring consumed requests.
    return Path.home()/'.local/state/agent-subagent-router/image-probe-reservations'


def reserve_probe(store, backend, invocation_id):
    # One durable reservation per approved amendment/backend, never per arbitrary
    # taskId. Recreating a fixture or run cannot restore consumed authorization.
    if backend not in ('kimi', 'codex'):
        raise RouterError('IMAGE_ROUTE_MISMATCH')
    root = probe_reservation_root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or root.stat().st_mode & 0o077 or root.stat().st_uid != os.getuid():
        raise RouterError('UNSAFE_STATE')
    path = root/(API_SPEC_SHA + '-' + backend + '.json')
    try:
        atomic_json(path, {'spec_sha256': API_SPEC_SHA, 'backend': backend,
                          'invocation_id': invocation_id, 'request_limit': 1})
    except FileExistsError:
        raise RouterError('IMAGE_PROBE_BUDGET_CONSUMED') from None
