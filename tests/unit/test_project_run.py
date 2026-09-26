from datetime import datetime as NativeDateTime, timezone
from types import SimpleNamespace

import pytest

from agent_subagent_router import route_qualification
from agent_subagent_router.backends.kimi import profile
from agent_subagent_router.contracts import RouterError
from agent_subagent_router.project_run import verify_smoke
from agent_subagent_router.transport.credentials import credential_fingerprint


def test_small_deep_smoke_is_not_account_specific_one_million_entitlement():
    runtime = SimpleNamespace(to_dict=lambda: {'pinned': True})
    route = profile('deep')
    receipt = {'classification': 'PARSED', 'evidence_kind': 'live', 'profile': route.to_dict(),
        'runtime': runtime.to_dict(), 'observations': [{'classification': 'IDENTITY_VERIFIED',
        'proof': 'authenticated_endpoint_declaration'}], 'deep_entitlement': 'NOT_EVALUATED'}
    with pytest.raises(RouterError, match='ENTITLEMENT_UNVERIFIED'):
        verify_smoke(receipt, route, runtime)


def test_qualified_credential_cannot_be_replaced_before_project_admission():
    runtime = SimpleNamespace(to_dict=lambda: {'pinned': True})
    receipt = {'classification': 'PARSED', 'evidence_kind': 'live', 'profile': profile('worker').to_dict(),
        'runtime': runtime.to_dict(), 'observations': [{'classification': 'IDENTITY_VERIFIED',
        'proof': 'authenticated_endpoint_declaration'}],
        'credential_fingerprint': credential_fingerprint('kimi', 'key-A')}
    verify_smoke(receipt, profile('worker'), runtime, 'key-A')
    with pytest.raises(RouterError, match='QUALIFICATION_CREDENTIAL_MISMATCH'):
        verify_smoke(receipt, profile('worker'), runtime, 'key-B')


def test_deep_project_admission_accepts_seven_day_old_entitlement(monkeypatch):
    class FrozenDateTime(NativeDateTime):
        @classmethod
        def now(cls, tz=None):
            value = NativeDateTime(2026, 9, 26, 12, tzinfo=timezone.utc)
            return value if tz is None else value.astimezone(tz)

    monkeypatch.setattr(route_qualification, 'datetime', FrozenDateTime)
    runtime = SimpleNamespace(to_dict=lambda: {'pinned': True})
    route = profile('deep')
    receipt = {'classification': 'PARSED', 'evidence_kind': 'live',
        'profile': route.to_dict(), 'runtime': runtime.to_dict(),
        'observations': [{'classification': 'IDENTITY_VERIFIED',
            'proof': 'authenticated_endpoint_declaration'}],
        'deep_entitlement': 'VERIFIED',
        'account_entitlement': {'kind': 'account-entitlement-observation',
            'source': 'https://www.kimi.com/code/console', 'credential_match': True,
            'tier': 'Pro', 'entitled_context_tokens': 1048576,
            'observed_at': '2026-09-19T12:00:00Z'}}

    verify_smoke(receipt, route, runtime)
