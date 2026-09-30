from datetime import datetime, timezone

import pytest

from agent_subagent_router import subscription_account as account, image_budget
from agent_subagent_router.contracts import RouterError, canonical_bytes, strict_json
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.transport.credentials import CodexSubscriptionCredential
from test_image_unrestricted_spending import fixture


def test_model_only_observation_never_queries_quota_and_is_synthetic(tmp_path, monkeypatch):
    credential = CodexSubscriptionCredential('fixture-oauth', 'fixture-account',
        ('fixture-oauth', 'fixture-account'))
    monkeypatch.setattr(account, 'load_credential', lambda *a, **k: credential)
    calls = []
    def get(path, actual):
        calls.append(path)
        assert actual is credential
        return {'models': [{'slug': 'gpt-6.1-sol', 'input_modalities': ['text', 'image']}]}, 'a'*64
    store = ReceiptStore(tmp_path/'runs')
    record = account.observe_subscription_model(store, {}, 'gpt-6.1-sol', 'owned-probe', getter=get)
    assert calls == [account.MODELS_PATH]
    assert record['account_queries'] == 1 and record['provider_requests'] == 0
    assert record['classification'] == 'ENGINEERING_MODEL_READY'
    assert record['evidence_kind'] == 'synthetic-model-fixture'
    facts = strict_json((store.root/record['invocation_id']/'model-evidence.json').read_bytes())
    assert facts['matched_model_count'] == 1 and facts['input_modalities'] == ['text', 'image']
    task, _ = fixture(tmp_path, 'codex')
    with pytest.raises(RouterError, match='SUBSCRIPTION_MODEL_UNVERIFIED'):
        image_budget.require_probe_budget(store, record['invocation_id'], task, record['credential_fingerprint'])


def test_invalid_credential_model_verification_has_zero_queries(tmp_path, monkeypatch):
    def reject(*a, **k):
        raise RouterError('UNSAFE_CREDENTIAL')
    monkeypatch.setattr(account, 'load_credential', reject)
    calls = []
    record = account.observe_subscription_model(ReceiptStore(tmp_path/'runs'), {},
        'gpt-6.1-sol', 'owned-probe', getter=lambda *a: calls.append(a))
    assert record['classification'] == 'UNSAFE_CREDENTIAL'
    assert record['account_queries'] == 0 and not calls


def test_catalog_reservation_is_per_probe_and_survives_state_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(image_budget, 'probe_reservation_root', lambda: tmp_path/'host-ledger')
    image_budget.reserve_subscription_model_observation('first', 'owned-probe')
    with pytest.raises(RouterError, match='SUBSCRIPTION_MODEL_OBSERVATION_CONSUMED'):
        image_budget.reserve_subscription_model_observation('new-state', 'owned-probe')
    image_budget.reserve_subscription_model_observation('new-authorized', 'another-probe')


def evidence(store, task, **changes):
    facts = {'provider': 'codex-subscription', 'credential_fingerprint': 'current-fingerprint',
        'authenticated': True, 'model': task['model'], 'image_input_supported': True,
        'matched_model_count': 1, 'catalog_model_count': 1, 'input_modalities': ['text', 'image'],
        'catalog_source': 'https://chatgpt.com'+account.MODELS_PATH, 'catalog_sha256': 'a'*64,
        'observed_at': datetime.now(timezone.utc).isoformat()}
    facts.update(changes)
    run = store.create('router-image', 'subscription-model')
    artifact = store.artifact(run, 'model-evidence.json', canonical_bytes(facts),
        producer='subscription-model-observer')
    return store.finalize(run, {'kind': 'codex-subscription-model/v1',
        'classification': 'AUTHENTICATED_MODEL_READY', 'evidence_kind': 'authenticated-https-model',
        'model': facts['model'], 'credential_fingerprint': facts['credential_fingerprint'],
        'probe_id': 'owned-probe', 'account_queries': 1, 'provider_requests': 0, 'artifacts': [artifact]})


def test_catalog_only_canonical_evidence_satisfies_image_gate_without_quota(tmp_path):
    task, _ = fixture(tmp_path, 'codex')
    store = ReceiptStore(tmp_path/'runs')
    record = evidence(store, task)
    assert image_budget.require_probe_budget(store, record['invocation_id'], task,
        'current-fingerprint')['spending_policy'] == 'unrestricted'


@pytest.mark.parametrize('changes', [
    {'image_input_supported': False}, {'authenticated': False},
    {'credential_fingerprint': 'other'}, {'model': 'gpt-6-luna'},
    {'catalog_source': 'https://untrusted.invalid/models'}, {'catalog_sha256': 'bad'},
    {'observed_at': '2999-01-01T00:00:00+00:00'},
    {'matched_model_count': True}, {'matched_model_count': 2}, {'input_modalities': ['text']},
])
def test_catalog_only_invalid_evidence_cannot_authorize_images(tmp_path, changes):
    task, _ = fixture(tmp_path, 'codex')
    store = ReceiptStore(tmp_path/'runs')
    record = evidence(store, task, **changes)
    with pytest.raises(RouterError, match='SUBSCRIPTION_MODEL_UNVERIFIED'):
        image_budget.require_probe_budget(store, record['invocation_id'], task, 'current-fingerprint')


@pytest.mark.parametrize('models,count', [([], 0),
    ([{'slug': 'gpt-6.1-sol'}], 1),
    ([{'slug': 'gpt-6.1-sol', 'input_modalities': ['text']}], 1),
    ([{'slug': 'gpt-6.1-sol', 'input_modalities': ['image']}] * 2, 2)])
def test_catalog_failure_records_exact_presence_without_claiming_support(models, count):
    facts = account._model_facts({'models': models}, 'gpt-6.1-sol')
    assert facts['matched_model_count'] == count
    assert facts['image_input_supported'] is False


@pytest.mark.parametrize('accepted,legacy,recovery', [(False, False, False),
    (True, True, False), (True, False, True)])
def test_cli_model_verification_requires_new_policy_ref_and_excludes_recovery(
        tmp_path, monkeypatch, capsys, accepted, legacy, recovery):
    from agent_subagent_router import cli, image_probe, image_seal, image_runtime, image_conformance
    task, _ = fixture(tmp_path, 'codex')
    if accepted:
        task['selected_refs'].append({'path': '/tmp/model-spec.md',
            'sha256': image_budget.MODEL_VERIFICATION_SPEC_SHA, 'accepted': True})
    if legacy:
        task['metadata'].pop('spending_policy')
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
    calls = []
    monkeypatch.setattr(account, 'observe_subscription_model', lambda *a: calls.append(a))
    args = ['--state', str(tmp_path), '--sandbox-config', '/tmp/fixture-config.json',
        'observe-image-subscription', '--probe', 'owned-probe',
        '--credential-ref', '/tmp/missing-reference.json', '--verify-model']
    if recovery:
        args.append('--recover-account-projection')
    assert cli.main(args) != 0
    assert not calls
    assert 'SUBSCRIPTION_MODEL_VERIFICATION_ACCEPTANCE_REQUIRED' in capsys.readouterr().err
