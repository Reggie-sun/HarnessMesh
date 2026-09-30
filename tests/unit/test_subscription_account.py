import pytest

from agent_subagent_router import subscription_account as account
from agent_subagent_router.contracts import RouterError
from agent_subagent_router.image_budget import reserve_subscription_account_observation
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.transport.credentials import CodexSubscriptionCredential


def test_quota_requires_included_rate_limit_not_credits_guess():
    quota = {'rate_limit': {'allowed': True, 'limit_reached': False,
        'primary_window': {'used_percent': 5, 'reset_at': 1790660000}, 'secondary_window': None}}
    assert account._quota_available(quota)
    quota['rate_limit']['primary_window']['used_percent'] = 100
    assert not account._quota_available(quota)
    assert not account._quota_available({'credits': {'balance': 1000}})
    assert not account._quota_available({'rate_limit': {'allowed': 1, 'limit_reached': 0}})


@pytest.mark.parametrize('models', [[], [{'slug': 'gpt-6-sol', 'input_modalities': ['text']}],
    [{'slug': 'gpt-6-luna', 'input_modalities': ['image']}],
    [{'slug': 'gpt-6-sol', 'input_modalities': ['image']}] * 2])
def test_catalog_requires_unique_exact_model_with_image_input(models):
    assert not account._model_supports_image({'models': models}, 'gpt-6-sol')


def test_exact_image_model_is_supported():
    assert account._model_supports_image({'models': [
        {'slug': 'gpt-6-sol', 'input_modalities': ['text', 'image']}]}, 'gpt-6-sol')


def test_account_observation_ledger_survives_new_state(tmp_path, monkeypatch):
    from agent_subagent_router import image_budget
    monkeypatch.setattr(image_budget, 'probe_reservation_root', lambda: tmp_path/'ledger')
    reserve_subscription_account_observation('first')
    with pytest.raises(RouterError, match='SUBSCRIPTION_ACCOUNT_OBSERVATION_CONSUMED'):
        reserve_subscription_account_observation('new-state')


def test_rejected_auth_never_queries_account(tmp_path, monkeypatch):
    def reject(*args, **kwargs):
        raise RouterError('UNSAFE_CREDENTIAL')
    monkeypatch.setattr(account, 'load_credential', reject)
    calls = []
    record = account.observe_subscription_account(ReceiptStore(tmp_path/'runs'), {}, 'gpt-6-sol',
        getter=lambda *args: calls.append(args))
    assert record['classification'] == 'UNSAFE_CREDENTIAL'
    assert record['account_queries'] == 0 and record['provider_requests'] == 0
    assert calls == [] and record['artifacts'] == []


@pytest.mark.parametrize('model', ['gpt-6.1-sol', 'gpt-6-sol', 'gpt-6-luna'])
def test_synthetic_account_observer_cannot_claim_live_authentication(tmp_path, monkeypatch, model):
    credential = CodexSubscriptionCredential('test-oauth-only', 'test-account-only',
        ('test-oauth-only', 'test-account-only'))
    monkeypatch.setattr(account, 'load_credential', lambda *args, **kwargs: credential)
    calls = []
    def get(path, projected):
        calls.append(path)
        assert projected is credential
        if path == account.QUOTA_PATH:
            return {'rate_limit': {'allowed': True, 'limit_reached': False,
                'primary_window': {'used_percent': 5, 'reset_at': 1790660000}}}, 'a'*64
        return {'models': [{'slug': model, 'input_modalities': ['image']}]}, 'b'*64
    record = account.observe_subscription_account(ReceiptStore(tmp_path/'runs'), {}, model, getter=get)
    assert calls == [account.QUOTA_PATH, account.MODELS_PATH]
    assert record['classification'] == 'ENGINEERING_ACCOUNT_READY'
    assert record['evidence_kind'] == 'synthetic-account-fixture'
    assert record['provider_requests'] == 0
