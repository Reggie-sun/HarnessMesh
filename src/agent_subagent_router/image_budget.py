"""Read canonical parent-observed quota/cost evidence, and consume probe once."""
from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path

from .contracts import RouterError, canonical_bytes, hash_bytes
from .image_runtime import API_SPEC_SHA, SUBSCRIPTION_SPEC_SHA
from .receipts import atomic_json
from .image_contract import IMAGE_PROVIDERS
from .transport.credentials import owner_home

ACCOUNT_PROJECTION_SPEC_SHA = '7e96271ee259ba2f04d16d72b7d4766c8ef703f05c218fb9f6fca227b91a6d81'


def input_digest(task):
    from .adapters.image_claude import visible_text
    return hash_bytes(canonical_bytes({'backend': task['backend'], 'model': task['model'],
        'profile': task['profile'], 'effort': task['effort'], 'system': task['system_text'],
        'text': visible_text(task), 'images': [{k: x[k] for k in
            ('image_id', 'sha256', 'byte_length', 'width', 'height')} for x in task['images']],
        'budgets': task['budgets']}))


def require_probe_budget(store, identifier, task, fingerprint):
    if task.get('backend') == 'codex' and task.get('profile') == 'subscription-bounded':
        return _require_subscription_budget(store, identifier, task, fingerprint)
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


def _require_subscription_budget(store, identifier, task, fingerprint):
    if not identifier:
        raise RouterError('IMAGE_ACCOUNT_BUDGET_UNVERIFIED')
    from .contracts import strict_json
    try:
        record = store.read(identifier)
        account = record['authenticated_account_evidence']
        observed = datetime.fromisoformat(record['observed_at'].replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        required = {
            'kind': 'image-probe-budget/v1', 'classification': 'AUTHORIZED',
            'evidence_kind': 'parent-observed-authenticated-account',
            'spec_sha256': SUBSCRIPTION_SPEC_SHA, 'credential_fingerprint': fingerprint,
            'input_digest': input_digest(task), 'backend': 'codex',
            'profile': 'subscription-bounded', 'model': task['model'], 'effort': task['effort'],
            'request_limit': 1, 'generation_tokens': None, 'observed_output_tokens_limit': 2048,
            'cost_upper_bound_usd': None, 'billing_mode': 'existing-subscription-no-extra-purchase',
        }
        if any(type(record.get(k)) is not type(v) or record.get(k) != v for k, v in required.items()):
            raise ValueError()
        if not 0 <= age <= 300:
            raise ValueError()
        artifact = next(x for x in record['artifacts'] if x['path'] == 'account-evidence.json')
        if (artifact['producer'] != 'parent-account-observer'
                or strict_json((store.root/identifier/artifact['path']).read_bytes()) != account
                or account['credential_fingerprint'] != fingerprint
                or account['provider'] != 'codex-subscription'
                or account['authenticated'] is not True
                or account['source'] != 'https://chatgpt.com/backend-api/wham/usage'
                or account['quota_available'] is not True
                or account['model'] != task['model']
                or account['image_input_supported'] is not True
                or account['observed_at'] != record['observed_at']):
            raise ValueError()
        limits = {'wall_seconds': 180, 'idle_seconds': 90, 'request_limit': 1,
                  'max_images': 8, 'max_png_bytes': 1024 * 1024, 'payload_bytes': 65536,
                  'output_bytes': 1024 * 1024, 'context_bytes': 1024 * 1024}
        if any(task['budgets'][k] > v for k, v in limits.items()):
            raise ValueError()
        observation = store.read(account['observation_id'])
        fact = next(x for x in observation['artifacts'] if x['path'] == 'account-evidence.json')
        # The canonical observer signed facts must match, including quota/catalog bindings.
        facts = strict_json((store.root/account['observation_id']/fact['path']).read_bytes())
        if (observation['kind'] != 'codex-subscription-account/v1'
                or observation['classification'] != 'AUTHENTICATED_ACCOUNT_READY'
                or observation['evidence_kind'] != 'authenticated-https-account'
                or fact['producer'] != 'subscription-account-observer'
                or facts != {k: v for k, v in account.items() if k != 'observation_id'}):
            raise ValueError()
    except (KeyError, TypeError, ValueError, ArithmeticError, StopIteration, OSError):
        raise RouterError('IMAGE_ACCOUNT_BUDGET_UNVERIFIED') from None
    return record


def authorize_subscription_probe(store, probe_id, observation_id):
    """Freeze one observed subscription budget; no caller-provided account facts."""
    from .image_probe import read_probe
    from .image_seal import verify_image_seal
    from .image_conformance import require_conformance
    from .contracts import strict_json
    probe = store.read(probe_id)
    read_probe(store, probe_id, probe['manifest'])
    task = verify_image_seal(Path(probe['manifest']))['task']
    if task['backend'] != 'codex' or task['profile'] != 'subscription-bounded':
        raise RouterError('IMAGE_ROUTE_MISMATCH')
    require_conformance(store, probe, task)
    observation = store.read(observation_id)
    if (observation['kind'] != 'codex-subscription-account/v1'
            or observation['classification'] != 'AUTHENTICATED_ACCOUNT_READY'
            or observation['evidence_kind'] != 'authenticated-https-account'):
        raise RouterError('IMAGE_ACCOUNT_BUDGET_UNVERIFIED')
    account = strict_json((store.root/observation_id/'account-evidence.json').read_bytes())
    account['observation_id'] = observation_id
    if account['model'] != task['model']:
        raise RouterError('IMAGE_ACCOUNT_BUDGET_UNVERIFIED')
    run = store.create('router-image', 'subscription-probe-budget')
    artifact = store.artifact(run, 'account-evidence.json', canonical_bytes(account),
        media_type='application/json', producer='parent-account-observer')
    record = store.finalize(run, {'kind': 'image-probe-budget/v1', 'classification': 'AUTHORIZED',
        'evidence_kind': 'parent-observed-authenticated-account', 'spec_sha256': SUBSCRIPTION_SPEC_SHA,
        'credential_fingerprint': account['credential_fingerprint'], 'observed_at': account['observed_at'],
        'input_digest': input_digest(task), 'backend': task['backend'], 'profile': task['profile'],
        'model': task['model'], 'effort': task['effort'], 'request_limit': 1, 'generation_tokens': None,
        'observed_output_tokens_limit': 2048, 'cost_upper_bound_usd': None,
        'billing_mode': 'existing-subscription-no-extra-purchase',
        'authenticated_account_evidence': account, 'artifacts': [artifact], 'provider_requests': 0,
        'actual_cost_usd': None, 'authority': 'none', 'eligible': False})
    require_probe_budget(store, record['invocation_id'], task, account['credential_fingerprint'])
    return record


def reserve_subscription_account_observation(invocation_id, *, store=None,
        recover_projection=False, fingerprint=None, model=None):
    root = probe_reservation_root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or root.stat().st_mode & 0o077 or root.stat().st_uid != os.getuid():
        raise RouterError('UNSAFE_STATE')
    if recover_projection:
        from .contracts import strict_json
        try:
            original = strict_json((root/(SUBSCRIPTION_SPEC_SHA + '-account.json')).read_bytes())
            previous = store.read(original['invocation_id'])
            expected = {'kind': 'codex-subscription-account/v1',
                'classification': 'UPSTREAM_SECRET_REFLECTION', 'account_queries': 1,
                'provider_requests': 0, 'evidence_kind': 'authenticated-https-account',
                'credential_fingerprint': fingerprint, 'model': model}
            if (original['spec_sha256'] != SUBSCRIPTION_SPEC_SHA
                    or not fingerprint or not model
                    or any(type(previous.get(k)) is not type(v) or previous.get(k) != v
                           for k, v in expected.items())):
                raise ValueError()
        except (AttributeError, KeyError, OSError, TypeError, ValueError, RouterError):
            raise RouterError('SUBSCRIPTION_RECOVERY_NOT_AUTHORIZED') from None
        try:
            atomic_json(root/(ACCOUNT_PROJECTION_SPEC_SHA + '-account.json'), {
                'spec_sha256': ACCOUNT_PROJECTION_SPEC_SHA, 'invocation_id': invocation_id,
                'previous_invocation_id': previous['invocation_id'],
                'quota_query_limit': 1, 'catalog_query_limit': 1})
        except FileExistsError:
            raise RouterError('SUBSCRIPTION_ACCOUNT_OBSERVATION_CONSUMED') from None
        return
    try:
        atomic_json(root/(SUBSCRIPTION_SPEC_SHA + '-account.json'), {
            'spec_sha256': SUBSCRIPTION_SPEC_SHA, 'invocation_id': invocation_id,
            'quota_query_limit': 1, 'catalog_query_limit': 1})
    except FileExistsError:
        raise RouterError('SUBSCRIPTION_ACCOUNT_OBSERVATION_CONSUMED') from None


def probe_reservation_root():
    # CLI --state relocates evidence, never monetary authorization. One host
    # ledger prevents a fresh state directory from restoring consumed requests.
    return owner_home()/'.local/state/agent-subagent-router/image-probe-reservations'


def reserve_probe(store, backend, invocation_id, *, profile=None):
    # One durable reservation per approved amendment/backend, never per arbitrary
    # taskId. Recreating a fixture or run cannot restore consumed authorization.
    if backend not in ('kimi', 'codex'):
        raise RouterError('IMAGE_ROUTE_MISMATCH')
    root = probe_reservation_root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or root.stat().st_mode & 0o077 or root.stat().st_uid != os.getuid():
        raise RouterError('UNSAFE_STATE')
    spec = SUBSCRIPTION_SPEC_SHA if backend == 'codex' and profile == 'subscription-bounded' else API_SPEC_SHA
    path = root/(spec + '-' + backend + '.json')
    try:
        atomic_json(path, {'spec_sha256': spec, 'backend': backend,
                          'invocation_id': invocation_id, 'request_limit': 1})
    except FileExistsError:
        raise RouterError('IMAGE_PROBE_BUDGET_CONSUMED') from None
