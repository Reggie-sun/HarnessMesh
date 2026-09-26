from datetime import datetime as NativeDateTime, timezone

import pytest

from agent_subagent_router import route_qualification
from agent_subagent_router.contracts import RouterError


class FrozenDateTime(NativeDateTime):
    @classmethod
    def now(cls, tz=None):
        value = NativeDateTime(2026, 9, 26, 12, tzinfo=timezone.utc)
        return value if tz is None else value.astimezone(tz)


def entitlement(observed_at='2026-09-19T12:00:00Z'):
    return {
        'kind': 'account-entitlement-observation',
        'source': 'https://www.kimi.com/code/console',
        'credential_match': True,
        'tier': 'Pro',
        'entitled_context_tokens': 1048576,
        'observed_at': observed_at,
    }


@pytest.mark.parametrize('observed_at', [
    '2026-09-19T12:00:00Z',
    '2016-09-26T12:00:00Z',
])
def test_old_account_entitlement_observations_remain_valid(monkeypatch, observed_at):
    monkeypatch.setattr(route_qualification, 'datetime', FrozenDateTime)

    route_qualification.validate_entitlement(entitlement(observed_at))


@pytest.mark.parametrize('observed_at', [
    '2026-09-26T12:00:01Z',
    'not-a-date',
    '2026-09-19T12:00:00',
])
def test_future_invalid_and_timezone_naive_observations_are_rejected(monkeypatch, observed_at):
    monkeypatch.setattr(route_qualification, 'datetime', FrozenDateTime)

    with pytest.raises(RouterError, match='ENTITLEMENT_UNVERIFIED'):
        route_qualification.validate_entitlement(entitlement(observed_at))


@pytest.mark.parametrize("field", [
    'kind',
    'source',
    'credential_match',
    'tier',
    'entitled_context_tokens',
    'observed_at',
])
def test_missing_entitlement_fields_are_rejected(monkeypatch, field):
    monkeypatch.setattr(route_qualification, 'datetime', FrozenDateTime)
    evidence = entitlement()
    del evidence[field]

    with pytest.raises(RouterError, match='ENTITLEMENT_UNVERIFIED'):
        route_qualification.validate_entitlement(evidence)


@pytest.mark.parametrize(('field', 'value'), [
    ('kind', 'other-observation'),
    ('source', 'https://example.com/account'),
    ('credential_match', False),
    ('tier', 'Basic'),
    ('entitled_context_tokens', 1048575),
])
def test_invalid_entitlement_fields_are_rejected(monkeypatch, field, value):
    monkeypatch.setattr(route_qualification, 'datetime', FrozenDateTime)
    evidence = entitlement()
    evidence[field] = value

    with pytest.raises(RouterError, match='ENTITLEMENT_UNVERIFIED'):
        route_qualification.validate_entitlement(evidence)


def test_missing_entitlement_is_rejected():
    with pytest.raises(RouterError, match='ENTITLEMENT_UNVERIFIED'):
        route_qualification.validate_entitlement(None)
