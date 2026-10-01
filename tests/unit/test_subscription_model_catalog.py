import hashlib
from pathlib import Path

import pytest

from agent_subagent_router import cli, image_budget, image_contract, subscription_account as account
from agent_subagent_router.contracts import RouterError, strict_json
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.transport.credentials import CodexSubscriptionCredential
from test_image_unrestricted_spending import fixture


def test_catalog_projection_lists_only_safe_gpt_facts():
    catalog = {
        'account_id': 'must-not-be-projected',
        'display_name': 'must-not-be-projected',
        'models': [
            {'slug': 'claude-3-7-sonnet', 'input_modalities': ['image']},
            {'slug': 'gpt-6.1-sol', 'input_modalities': ['image', 'audio', 'text'],
             'instructions': 'must-not-be-projected'},
            {'slug': 'gpt-5.4', 'input_modalities': ['text']},
        ],
    }

    assert account._project_model_catalog(catalog) == [
        {'slug': 'gpt-5.4', 'matched_model_count': 1,
         'input_modalities': ['text'], 'image_input_supported': False},
        {'slug': 'gpt-6.1-sol', 'matched_model_count': 1,
         'input_modalities': ['text', 'image'], 'image_input_supported': True},
    ]


def test_duplicate_gpt_slug_is_visible_but_never_claims_image_support():
    catalog = {'models': [
        {'slug': 'gpt-6.1-sol', 'input_modalities': ['image']},
        {'slug': 'gpt-6.1-sol', 'input_modalities': ['text', 'image']},
    ]}

    assert account._project_model_catalog(catalog) == [{
        'slug': 'gpt-6.1-sol', 'matched_model_count': 2,
        'input_modalities': [], 'image_input_supported': False,
    }]


@pytest.mark.parametrize('catalog', [
    {}, {'models': None}, {'models': {}}, {'models': [None]},
    {'models': [{'slug': None}]}, {'models': [{'slug': 'gpt-猫'}]},
    {'models': [{'slug': 'gpt-'}]}, {'models': [{'slug': 'gpt-6.1-sol\n'}]},
    {'models': [{'slug': 'gpt-' + 'a' * 77}]},
    {'models': [{'slug': 'unsafe/slug'}]},
])
def test_invalid_model_catalog_or_slug_fails_closed(catalog):
    with pytest.raises(RouterError, match='SUBSCRIPTION_MODEL_CATALOG_INVALID'):
        account._project_model_catalog(catalog)


def test_model_catalog_is_bounded_and_safe_non_gpt_entries_are_omitted():
    safe_non_gpt = {'slug': 'claude-sonnet-4', 'input_modalities': ['image']}
    assert account._project_model_catalog({'models': [safe_non_gpt]}) == []
    slug_at_limit = 'gpt-' + 'a' * 76
    assert len(slug_at_limit) == 80
    assert account._project_model_catalog({'models': [{'slug': slug_at_limit}]})[0]['slug'] == slug_at_limit

    with pytest.raises(RouterError, match='SUBSCRIPTION_MODEL_CATALOG_INVALID'):
        account._project_model_catalog({'models': [safe_non_gpt] * 129})


def test_discovery_projection_is_opt_in_and_uses_one_catalog_get(tmp_path, monkeypatch):
    credential = CodexSubscriptionCredential('fixture-oauth', 'fixture-account',
        ('fixture-oauth', 'fixture-account'))
    monkeypatch.setattr(account, 'load_credential', lambda *a, **k: credential)
    calls = []

    def get(path, actual):
        calls.append(path)
        assert actual is credential
        return {'account_id': 'private', 'models': [
            {'slug': 'gpt-6.1-sol', 'input_modalities': ['text']},
            {'slug': 'gpt-6.2', 'input_modalities': ['image']},
        ]}, 'a' * 64

    store = ReceiptStore(tmp_path / 'runs')
    default = account.observe_subscription_model(store, {}, 'gpt-6.1-sol', 'old-probe', getter=get)
    default_facts = strict_json((store.root / default['invocation_id'] / 'model-evidence.json').read_bytes())
    assert set(default_facts) == {
        'provider', 'credential_fingerprint', 'authenticated', 'model', 'catalog_source',
        'catalog_sha256', 'observed_at', 'catalog_model_count', 'matched_model_count',
        'input_modalities', 'image_input_supported',
    }

    discovered = account.observe_subscription_model(store, {}, 'gpt-6.1-sol', 'new-probe',
        getter=get, discover_models=True)
    facts = strict_json((store.root / discovered['invocation_id'] / 'model-evidence.json').read_bytes())
    assert calls == [account.MODELS_PATH, account.MODELS_PATH]
    assert facts['model'] == 'gpt-6.1-sol'
    assert discovered['classification'] == 'INCOMPLETE'
    assert facts['catalog_models'] == [
        {'slug': 'gpt-6.1-sol', 'matched_model_count': 1,
         'input_modalities': ['text'], 'image_input_supported': False},
        {'slug': 'gpt-6.2', 'matched_model_count': 1,
         'input_modalities': ['image'], 'image_input_supported': True},
    ]
    assert set(facts['catalog_models'][0]) == {
        'slug', 'matched_model_count', 'input_modalities', 'image_input_supported'}
    assert 'account_id' not in facts and 'instructions' not in facts
    assert discovered['provider_requests'] == 0 and discovered['account_queries'] == 1
    assert discovered['authority'] == 'none' and discovered['eligible'] is False


def test_invalid_discovery_catalog_is_not_written_to_canonical_receipt(tmp_path, monkeypatch):
    credential = CodexSubscriptionCredential('fixture-oauth', 'fixture-account',
        ('fixture-oauth', 'fixture-account'))
    monkeypatch.setattr(account, 'load_credential', lambda *a, **k: credential)
    calls = []

    def get(path, actual):
        calls.append(path)
        return {'models': [{'slug': 'gpt-6.1-sol', 'input_modalities': 'image'}]}, 'b' * 64

    store = ReceiptStore(tmp_path / 'runs')
    record = account.observe_subscription_model(store, {}, 'gpt-6.1-sol', 'invalid-catalog',
        getter=get, discover_models=True)

    assert calls == [account.MODELS_PATH]
    assert record['classification'] == 'SUBSCRIPTION_MODEL_CATALOG_INVALID'
    assert record['account_queries'] == 1 and record['provider_requests'] == 0
    assert record['artifacts'] == []


def _astra_task(tmp_path):
    task, _ = fixture(tmp_path, 'codex')
    task['model'] = 'gpt-6-astra'
    task['selected_refs'].append({'path': '/tmp/astra-spec.md',
        'sha256': image_contract.SELECTED_SUBSCRIPTION_MODEL_SPEC_SHA, 'accepted': True})
    return task


@pytest.mark.parametrize('invalid', ['missing-task', 'wrong-model', 'missing-astra-ref', 'missing-unrestricted-ref'])
def test_astra_model_observation_requires_bound_task_before_credential_or_catalog(
        tmp_path, monkeypatch, invalid):
    credential_reads, catalog_reads = [], []
    monkeypatch.setattr(account, 'load_credential',
        lambda *a, **k: credential_reads.append((a, k)))
    task = _astra_task(tmp_path)
    if invalid == 'missing-task':
        task = None
    elif invalid == 'wrong-model':
        task['model'] = 'gpt-6-astra-alias'
    elif invalid == 'missing-astra-ref':
        task['selected_refs'].pop()
    else:
        task['selected_refs'] = [ref for ref in task['selected_refs']
            if ref['sha256'] != image_contract.UNRESTRICTED_SPENDING_SPEC_SHA]

    record = account.observe_subscription_model(ReceiptStore(tmp_path / 'runs'), {},
        'gpt-6-astra', 'owned-probe', getter=lambda *a: catalog_reads.append(a), task=task)

    assert record['classification'] == 'SUBSCRIPTION_MODEL_UNVERIFIED'
    assert record['account_queries'] == 0 and record['provider_requests'] == 0
    assert credential_reads == [] and catalog_reads == []


def test_astra_model_observation_uses_only_original_catalog_and_has_no_authority(tmp_path, monkeypatch):
    credential = CodexSubscriptionCredential('fixture-oauth', 'fixture-account',
        ('fixture-oauth', 'fixture-account'))
    monkeypatch.setattr(account, 'load_credential', lambda *a, **k: credential)
    calls = []

    def get(path, actual):
        calls.append(path)
        assert actual is credential
        return {'models': [{'slug': 'gpt-6-astra', 'input_modalities': ['text', 'image']}]}, 'c' * 64

    store = ReceiptStore(tmp_path / 'runs')
    record = account.observe_subscription_model(store, {}, 'gpt-6-astra', 'owned-probe',
        getter=get, task=_astra_task(tmp_path))
    facts = strict_json((store.root / record['invocation_id'] / 'model-evidence.json').read_bytes())

    assert calls == [account.MODELS_PATH]
    assert record['classification'] == 'ENGINEERING_MODEL_READY'
    assert record['account_queries'] == 1 and record['provider_requests'] == 0
    assert record['authority'] == 'none' and record['eligible'] is False
    assert facts['model'] == 'gpt-6-astra' and facts['image_input_supported'] is True


def test_cli_passes_sealed_task_to_astra_observer_only(tmp_path, monkeypatch, capsys):
    task = _astra_task(tmp_path)
    task['selected_refs'].append({'path': '/tmp/model-spec.md',
        'sha256': image_budget.MODEL_VERIFICATION_SPEC_SHA, 'accepted': True})
    _mock_cli_preflight(monkeypatch, tmp_path, task)
    credential_reads, catalog_reads = [], []
    monkeypatch.setattr('agent_subagent_router.transport.credentials.read_credential_reference',
        lambda *a, **k: credential_reads.append((a, k)) or {'safe': 'reference'})
    monkeypatch.setattr(account, 'observe_subscription_model',
        lambda *a, **k: catalog_reads.append((a, k)) or {'classification': 'AUTHENTICATED_MODEL_READY'})
    args = ['--state', str(tmp_path), '--sandbox-config', '/tmp/fixture-config.json',
        'observe-image-subscription', '--probe', 'owned-probe', '--credential-ref', '/tmp/ref.json',
        '--verify-model']

    assert cli.main(args) == 0
    capsys.readouterr()
    assert len(credential_reads) == 1 and len(catalog_reads) == 1
    assert catalog_reads[0][0][2:4] == ('gpt-6-astra', 'owned-probe')
    assert catalog_reads[0][1] == {'task': task}


def test_cli_legacy_model_verification_keeps_observer_call_shape(tmp_path, monkeypatch, capsys):
    task, _ = fixture(tmp_path, 'codex')
    task['selected_refs'].append({'path': '/tmp/model-spec.md',
        'sha256': image_budget.MODEL_VERIFICATION_SPEC_SHA, 'accepted': True})
    _mock_cli_preflight(monkeypatch, tmp_path, task)
    monkeypatch.setattr('agent_subagent_router.transport.credentials.read_credential_reference',
        lambda *a, **k: {'safe': 'reference'})
    catalog_calls = []
    monkeypatch.setattr(account, 'observe_subscription_model',
        lambda *a: catalog_calls.append(a) or {'classification': 'AUTHENTICATED_MODEL_READY'})
    args = ['--state', str(tmp_path), '--sandbox-config', '/tmp/fixture-config.json',
        'observe-image-subscription', '--probe', 'owned-probe', '--credential-ref', '/tmp/ref.json',
        '--verify-model']

    assert cli.main(args) == 0
    capsys.readouterr()
    assert len(catalog_calls) == 1 and len(catalog_calls[0]) == 4
    assert catalog_calls[0][2:] == ('gpt-6.1-sol', 'owned-probe')


def _mock_cli_preflight(monkeypatch, tmp_path, task):
    from agent_subagent_router import image_probe, image_seal, image_runtime, image_conformance

    class Store:
        def __init__(self, path):
            pass

        def read(self, identifier):
            return {'manifest': '/tmp/fixture-manifest.json', 'pins': {'fixture': True}}

    monkeypatch.setattr(cli, 'ReceiptStore', Store)
    monkeypatch.setattr(image_probe, 'read_probe', lambda *a: None)
    monkeypatch.setattr(image_seal, 'verify_image_seal', lambda *a: {'task': task})
    monkeypatch.setattr(image_runtime, 'image_runtime', lambda *a: ({}, {'fixture': True}))
    monkeypatch.setattr(image_conformance, 'require_conformance', lambda *a: None)


@pytest.mark.parametrize('verify,recovery,refs,unrestricted', [
    (False, False, 'both', True),
    (True, True, 'both', True),
    (True, False, 'none', True),
    (True, False, 'old', True),
    (True, False, 'new', True),
    (True, False, 'both', False),
])
def test_cli_discovery_rejects_invalid_gates_before_credential_or_catalog_access(
        tmp_path, monkeypatch, capsys, verify, recovery, refs, unrestricted):
    task, _ = fixture(tmp_path, 'codex')
    if refs in ('old', 'both'):
        task['selected_refs'].append({'path': '/tmp/model-spec.md',
            'sha256': image_budget.MODEL_VERIFICATION_SPEC_SHA, 'accepted': True})
    if refs in ('new', 'both'):
        task['selected_refs'].append({'path': '/tmp/catalog-spec.md',
            'sha256': cli.MODEL_CATALOG_DISCOVERY_SPEC_SHA, 'accepted': True})
    if not unrestricted:
        task['metadata'].pop('spending_policy', None)
    _mock_cli_preflight(monkeypatch, tmp_path, task)

    credential_reads, catalog_reads = [], []
    monkeypatch.setattr('agent_subagent_router.transport.credentials.read_credential_reference',
        lambda *a, **k: credential_reads.append((a, k)))
    monkeypatch.setattr(account, 'observe_subscription_model',
        lambda *a, **k: catalog_reads.append((a, k)))
    args = ['--state', str(tmp_path), '--sandbox-config', '/tmp/fixture-config.json',
        'observe-image-subscription', '--probe', 'owned-probe',
        '--credential-ref', '/tmp/missing-reference.json', '--discover-models']
    if verify:
        args.append('--verify-model')
    if recovery:
        args.append('--recover-account-projection')

    assert cli.main(args) != 0
    error = capsys.readouterr().err
    if not verify:
        assert 'SUBSCRIPTION_MODEL_DISCOVERY_REQUIRES_MODEL_VERIFICATION' in error
    else:
        assert 'SUBSCRIPTION_MODEL_VERIFICATION_ACCEPTANCE_REQUIRED' in error
    assert credential_reads == []
    assert catalog_reads == []


def test_cli_accepts_both_exact_model_and_discovery_specs_then_forwards_mode(
        tmp_path, monkeypatch, capsys):
    task, _ = fixture(tmp_path, 'codex')
    task['selected_refs'].extend([
        {'path': '/tmp/model-spec.md', 'sha256': image_budget.MODEL_VERIFICATION_SPEC_SHA,
         'accepted': True},
        {'path': '/tmp/catalog-spec.md', 'sha256': cli.MODEL_CATALOG_DISCOVERY_SPEC_SHA,
         'accepted': True},
    ])
    _mock_cli_preflight(monkeypatch, tmp_path, task)
    assert cli.MODEL_CATALOG_DISCOVERY_SPEC_SHA == hashlib.sha256(
        Path('docs/superpowers/specs/2026-10-01-image-model-catalog-selection.md').read_bytes()
    ).hexdigest()

    credential_reads, catalog_reads = [], []
    monkeypatch.setattr('agent_subagent_router.transport.credentials.read_credential_reference',
        lambda *a, **k: credential_reads.append((a, k)) or {'safe': 'reference'})
    monkeypatch.setattr(account, 'observe_subscription_model',
        lambda *a, **k: catalog_reads.append((a, k)) or {'classification': 'AUTHENTICATED_MODEL_READY'})
    args = ['--state', str(tmp_path), '--sandbox-config', '/tmp/fixture-config.json',
        'observe-image-subscription', '--probe', 'owned-probe', '--credential-ref', '/tmp/ref.json',
        '--verify-model', '--discover-models']

    assert cli.main(args) == 0
    capsys.readouterr()
    assert len(credential_reads) == 1
    assert len(catalog_reads) == 1
    assert catalog_reads[0][0][2:] == ('gpt-6.1-sol', 'owned-probe')
    assert catalog_reads[0][1] == {'discover_models': True}
