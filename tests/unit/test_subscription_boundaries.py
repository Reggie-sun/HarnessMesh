"""Reproduce real host/environment and HTTP-close boundaries without providers."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_subagent_router import image_budget, subscription_account
from agent_subagent_router.contracts import RouterError, hash_bytes
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.transport import codex_broker, credentials
from test_codex_subscription_credentials import _auth, _reference


@pytest.mark.parametrize('kind', ['account', 'subscription', 'api'])
def test_changed_HOME_cannot_restore_consumed_authorization(tmp_path, monkeypatch, kind):
    import pwd
    monkeypatch.setattr(pwd, 'getpwuid', lambda uid: SimpleNamespace(pw_dir=str(tmp_path)))
    monkeypatch.setenv('HOME', str(tmp_path/'first-home'))
    store = ReceiptStore(tmp_path/'fixed-state'/'runs')

    def reserve(identifier):
        if kind == 'account':
            image_budget.reserve_subscription_account_observation(identifier)
        else:
            image_budget.reserve_probe(store, 'codex', identifier,
                profile='subscription-bounded' if kind == 'subscription' else 'api-bounded')

    reserve('first')
    original = image_budget.probe_reservation_root()
    monkeypatch.setenv('HOME', str(tmp_path/'second-home'))
    with pytest.raises(RouterError, match='CONSUMED'):
        reserve('second')
    assert image_budget.probe_reservation_root() == original


def test_auth_suffix_outside_application_rejected_before_read(tmp_path, monkeypatch):
    path = _auth(tmp_path/'project'/'jianji'/'codex'/'auth.json')
    opened = []
    real_open = credentials.os.open

    def track(path, *args, **kwargs):
        opened.append(str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(credentials.os, 'open', track)
    with pytest.raises(RouterError, match='UNSAFE_CREDENTIAL'):
        credentials.load_credential('codex-subscription', _reference(path),
            project_root=Path(credentials.__file__).resolve().parents[2])
    assert opened == []


def _closing_transport(monkeypatch, module, *, on_read=None):
    seen = {'timeouts': [], 'shutdowns': [], 'response_closed': False}

    class Socket:
        def settimeout(self, timeout):
            seen['timeouts'].append(timeout)

        def shutdown(self, how):
            seen['shutdowns'].append(how)

    class Response:
        status = 200

        def __init__(self):
            self.parts = [b'{}', b'']

        def read1(self, size):
            if on_read:
                on_read()
            return self.parts.pop(0)

        def getheaders(self):
            return [('Content-Type', 'application/json')]

        def close(self):
            seen['response_closed'] = True

    class Connection:
        def __init__(self, host, **kwargs):
            self.sock = Socket()

        def connect(self):
            pass

        def request(self, method, path, **kwargs):
            seen['method'], seen['path'] = method, path

        def getresponse(self):
            # HTTPConnection detaches its socket for Connection: close; the
            # HTTPResponse file still holds that transport until body close.
            self.sock = None
            return Response()

        def close(self):
            seen['connection_closed'] = True

    monkeypatch.setattr(module.http.client, 'HTTPSConnection', Connection)
    return seen


def test_complete_close_response_accepted_by_account_get(tmp_path, monkeypatch):
    seen = _closing_transport(monkeypatch, subscription_account)
    credential = credentials.CodexSubscriptionCredential('synthetic-oauth', 'synthetic-account',
        ('synthetic-oauth', 'synthetic-account'))
    value, digest = subscription_account._get(subscription_account.QUOTA_PATH, credential)
    assert value == {} and digest == hash_bytes(b'{}')
    assert seen['method'] == 'GET'
    assert seen['response_closed'] and seen['connection_closed']


def test_account_deadline_expires_before_request_after_connect(monkeypatch):
    seen = _closing_transport(monkeypatch, subscription_account)
    times = iter([100, 131])
    monkeypatch.setattr(subscription_account.time, 'monotonic', lambda: next(times))
    credential = credentials.CodexSubscriptionCredential('synthetic-oauth', 'synthetic-account',
        ('synthetic-oauth', 'synthetic-account'))
    with pytest.raises(RouterError, match='SUBSCRIPTION_ACCOUNT_UNVERIFIED'):
        subscription_account._get(subscription_account.QUOTA_PATH, credential)
    assert 'method' not in seen and seen['connection_closed']


def test_account_deadline_stops_body_and_closes_detached_response(monkeypatch):
    clock = [100]
    seen = _closing_transport(monkeypatch, subscription_account, on_read=lambda: clock.__setitem__(0, 131))
    monkeypatch.setattr(subscription_account.time, 'monotonic', lambda: clock[0])
    credential = credentials.CodexSubscriptionCredential('synthetic-oauth', 'synthetic-account',
        ('synthetic-oauth', 'synthetic-account'))
    with pytest.raises(RouterError, match='SUBSCRIPTION_ACCOUNT_UNVERIFIED'):
        subscription_account._get(subscription_account.QUOTA_PATH, credential)
    assert seen['response_closed'] and seen['connection_closed']


@pytest.mark.parametrize('backend,profile,path', [
    ('codex', 'subscription-bounded', '/backend-api/codex/responses'),
    ('codex', 'api-bounded', '/v1/responses'),
    ('minimax', 'responses-bounded', '/v1/responses'),
])
def test_complete_close_response_accepted_by_shared_upstream(monkeypatch, backend, profile, path):
    seen = _closing_transport(monkeypatch, codex_broker)
    upstream = codex_broker._CodexUpstream(5, 1024, backend=backend, profile=profile)
    assert upstream(path, {}, b'{}') == (200, {'content-type': 'application/json'}, b'{}')
    assert seen['method'] == 'POST'
    assert seen['response_closed'] and seen['connection_closed']
    assert upstream._connection is None


def test_revoke_interrupts_response_held_socket_after_connection_detaches(monkeypatch):
    holder = {}
    seen = _closing_transport(monkeypatch, codex_broker, on_read=lambda: holder['upstream'].close())
    upstream = holder['upstream'] = codex_broker._CodexUpstream(5, 1024,
        profile='subscription-bounded')
    with pytest.raises(RouterError, match='CAPABILITY_REVOKED'):
        upstream('/backend-api/codex/responses', {}, b'{}')
    assert seen['shutdowns']
    assert seen['response_closed'] and seen['connection_closed']
    assert upstream._connection is None
