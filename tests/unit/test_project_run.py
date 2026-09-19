from types import SimpleNamespace

import pytest

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
