import json

import pytest

from agent_subagent_router import subscription_account as account
from agent_subagent_router import image_budget
from agent_subagent_router.contracts import RouterError, hash_bytes
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.transport.credentials import CodexSubscriptionCredential


def response_fixture(monkeypatch, value):
    raw = json.dumps(value).encode()

    class Socket:
        def settimeout(self, value):
            pass

    class Response:
        status = 200
        parts = [raw, b'']

        def read1(self, limit):
            return self.parts.pop(0)

        def close(self):
            pass

    class Connection:
        sock = Socket()

        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(account.http.client, 'HTTPSConnection', Connection)
    return raw


def credential():
    return CodexSubscriptionCredential('oauth-synthetic', 'account-synthetic',
        ('oauth-synthetic', 'account-synthetic', 'refresh-synthetic'))


def test_matching_quota_account_is_checked_removed_and_never_returned(monkeypatch):
    raw = response_fixture(monkeypatch, {'account_id': 'account-synthetic', 'rate_limit': {}})
    parsed, digest = account._get(account.QUOTA_PATH, credential())
    assert parsed == {'rate_limit': {}} and digest == hash_bytes(raw)
    assert 'account-synthetic' not in json.dumps(parsed)


@pytest.mark.parametrize('value', ['wrong-account', None, 1, True])
def test_wrong_quota_identity_rejected(monkeypatch, value):
    response_fixture(monkeypatch, {'account_id': value})
    with pytest.raises(RouterError, match='SUBSCRIPTION_ACCOUNT_UNVERIFIED'):
        account._get(account.QUOTA_PATH, credential())


@pytest.mark.parametrize('path,extra', [
    (account.MODELS_PATH, {}),
    (account.QUOTA_PATH, {'other': 'account-synthetic'}),
    (account.QUOTA_PATH, {'other': 'oauth-synthetic'}),
    (account.QUOTA_PATH, {'other': 'refresh-synthetic'}),
])
def test_projection_does_not_exempt_catalog_or_other_secret_locations(monkeypatch, path, extra):
    response_fixture(monkeypatch, {'account_id': 'account-synthetic', **extra})
    with pytest.raises(RouterError, match='UPSTREAM_SECRET_REFLECTION'):
        account._get(path, credential())


def prior_observation(tmp_path, monkeypatch, **changes):
    ledger = tmp_path / 'ledger'
    monkeypatch.setattr(image_budget, 'probe_reservation_root', lambda: ledger)
    store = ReceiptStore(tmp_path / 'runs')
    run = store.create('router-image', 'subscription-account')
    image_budget.reserve_subscription_account_observation(run.name)
    facts = {'kind': 'codex-subscription-account/v1',
        'classification': 'UPSTREAM_SECRET_REFLECTION', 'account_queries': 1,
        'provider_requests': 0, 'evidence_kind': 'authenticated-https-account',
        'credential_fingerprint': 'fingerprint', 'model': 'gpt-6.1-sol', 'artifacts': []}
    facts.update(changes)
    store.finalize(run, facts)
    return store, ledger


def test_explicit_recovery_is_once_and_does_not_restore_default_or_new_state(tmp_path, monkeypatch):
    store, ledger = prior_observation(tmp_path, monkeypatch)
    original = (ledger / (image_budget.SUBSCRIPTION_SPEC_SHA + '-account.json')).read_bytes()
    with pytest.raises(RouterError, match='CONSUMED'):
        image_budget.reserve_subscription_account_observation('default-again')
    with pytest.raises(RouterError, match='RECOVERY_NOT_AUTHORIZED'):
        image_budget.reserve_subscription_account_observation('new-state',
            store=ReceiptStore(tmp_path / 'other'), recover_projection=True,
            fingerprint='fingerprint', model='gpt-6.1-sol')
    image_budget.reserve_subscription_account_observation('recovery', store=store,
        recover_projection=True, fingerprint='fingerprint', model='gpt-6.1-sol')
    with pytest.raises(RouterError, match='CONSUMED'):
        image_budget.reserve_subscription_account_observation('recovery-again', store=store,
            recover_projection=True, fingerprint='fingerprint', model='gpt-6.1-sol')
    assert (ledger / (image_budget.SUBSCRIPTION_SPEC_SHA + '-account.json')).read_bytes() == original


@pytest.mark.parametrize('changes', [
    {'classification': 'OUTCOME_UNKNOWN'}, {'classification': 'UNSAFE_CREDENTIAL'},
    {'account_queries': 2}, {'account_queries': True}, {'provider_requests': False},
    {'credential_fingerprint': 'different'}, {'model': 'gpt-6-luna'},
    {'evidence_kind': 'synthetic-account-fixture'},
])
def test_recovery_rejects_unknown_second_endpoint_wrong_identity_or_synthetic(tmp_path, monkeypatch, changes):
    store, ledger = prior_observation(tmp_path, monkeypatch, **changes)
    with pytest.raises(RouterError, match='RECOVERY_NOT_AUTHORIZED'):
        image_budget.reserve_subscription_account_observation('recovery', store=store,
            recover_projection=True, fingerprint='fingerprint', model='gpt-6.1-sol')
    assert not (ledger / (image_budget.ACCOUNT_PROJECTION_SPEC_SHA + '-account.json')).exists()


def test_recovery_cannot_bootstrap_without_consumed_original(tmp_path, monkeypatch):
    monkeypatch.setattr(image_budget, 'probe_reservation_root', lambda: tmp_path / 'ledger')
    with pytest.raises(RouterError, match='RECOVERY_NOT_AUTHORIZED'):
        image_budget.reserve_subscription_account_observation('recovery',
            store=ReceiptStore(tmp_path / 'runs'), recover_projection=True,
            fingerprint='fingerprint', model='gpt-6.1-sol')
