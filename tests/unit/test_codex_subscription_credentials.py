import base64
from dataclasses import FrozenInstanceError
import json

import pytest

import agent_subagent_router.transport.credentials as credentials
from agent_subagent_router.contracts import RouterError, hash_bytes
from agent_subagent_router.transport.credentials import (
    CodexSubscriptionCredential,
    credential_fingerprint,
    load_credential,
    read_credential_reference,
)

_DEFAULT_ACCESS_TOKEN = object()


@pytest.fixture(autouse=True)
def synthetic_application_home(tmp_path, monkeypatch):
    monkeypatch.setattr(credentials, 'owner_home', lambda: tmp_path)


def _jwt(*, exp=4_102_444_800, nbf=None, iat=None, account="account-synthetic"):
    header = {"alg": "none", "typ": "JWT"}
    payload = {"exp": exp, "https://api.openai.com/auth": {"chatgpt_account_id": account}}
    if nbf is not None:
        payload["nbf"] = nbf
    if iat is not None:
        payload["iat"] = iat

    def encode(value):
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{encode(header)}.{encode(payload)}.synthetic-signature"


def _auth(path, *, access_token=_DEFAULT_ACCESS_TOKEN, account_id="account-synthetic", mode="chatgpt",
          api_key=None, extra=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "auth_mode": mode,
        "tokens": {
            "id_token": "id-token-synthetic",
            "refresh_token": "refresh-token-synthetic",
            "account_id": account_id,
        },
        "last_refresh": "2026-09-30T00:00:00Z",
    }
    if access_token is _DEFAULT_ACCESS_TOKEN:
        value["tokens"]["access_token"] = _jwt()
    elif access_token is not None:
        value["tokens"]["access_token"] = access_token
    if api_key is not None:
        value["OPENAI_API_KEY"] = api_key
    if extra:
        value.update(extra)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)
    return path


def _app_auth_path(tmp_path):
    return tmp_path / ".config" / "jianji" / "codex" / "auth.json"


def _reference(path):
    return {"provider": "codex-subscription", "file": str(path)}


def test_loads_only_synthetic_private_app_auth_and_keeps_every_token_for_scanning(tmp_path):
    auth = _auth(_app_auth_path(tmp_path))

    loaded = load_credential("codex-subscription", _reference(auth))

    assert isinstance(loaded, CodexSubscriptionCredential)
    assert loaded.access_token == _jwt()
    assert loaded.account_id == "account-synthetic"
    assert loaded.secret_values == (
        _jwt(),
        "id-token-synthetic",
        "refresh-token-synthetic",
        "account-synthetic",
    )
    with pytest.raises(FrozenInstanceError):
        loaded.account_id = "changed"


def test_subscription_reference_rejects_global_codex_path_before_opening(tmp_path, monkeypatch):
    reference = tmp_path / ".codex" / "credential-reference.json"
    reference.parent.mkdir()
    reference.write_text("{}", encoding="utf-8")
    attempted = []
    real_open = credentials.os.open

    def track_open(path, *args, **kwargs):
        attempted.append(str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(credentials.os, "open", track_open)
    with pytest.raises(RouterError) as error:
        read_credential_reference("codex-subscription", reference)

    assert error.value.code == "UNSAFE_CREDENTIAL"
    assert attempted == []


@pytest.mark.parametrize("kind", ["wrong-app", "global-codex", "project", "file-symlink", "parent-symlink"])
def test_subscription_auth_rejects_wrong_or_linked_locations(tmp_path, kind):
    project = tmp_path / "project"
    if kind == "wrong-app":
        path = _auth(tmp_path / "user-data" / "codex" / "auth.json")
    elif kind == "global-codex":
        path = _auth(tmp_path / ".codex" / "jianji" / "codex" / "auth.json")
    elif kind == "project":
        path = _auth(project / "jianji" / "codex" / "auth.json")
    elif kind == "file-symlink":
        real = _auth(_app_auth_path(tmp_path))
        path = real.parent / "linked-auth.json"
        path.symlink_to(real)
    else:
        real_root = tmp_path / "real-user-data"
        real = _auth(real_root / "jianji" / "codex" / "auth.json")
        link_root = tmp_path / "linked-user-data"
        link_root.symlink_to(real_root, target_is_directory=True)
        path = link_root / "jianji" / "codex" / "auth.json"

    with pytest.raises(RouterError) as error:
        load_credential("codex-subscription", _reference(path), project_root=project)

    assert error.value.code == "UNSAFE_CREDENTIAL"


@pytest.mark.parametrize("auth_change", [
    {"mode": "apiKey"},
    {"api_key": "sk-synthetic-api-key"},
    {"access_token": None},
    {"account_id": ""},
    {"extra": {"unexpected": "untracked-secret"}},
])
def test_subscription_auth_rejects_api_mode_key_or_missing_fields_without_echo(tmp_path, auth_change):
    options = dict(auth_change)
    auth = _auth(_app_auth_path(tmp_path), **options)

    with pytest.raises(RouterError) as error:
        load_credential("codex-subscription", _reference(auth))

    assert error.value.code == "UNSAFE_CREDENTIAL"
    assert "sk-synthetic-api-key" not in str(error.value)
    assert "untracked-secret" not in str(error.value)


@pytest.mark.parametrize("token", [
    _jwt(exp=1),
    _jwt(nbf=4_102_444_800),
    _jwt(iat=4_102_444_800),
    "not-a-jwt",
    _jwt(exp=True),
    "eyJhbGciOiJub25lIn0.%%%bad%%%.signature",
])
def test_subscription_loader_rejects_expired_future_invalid_or_malformed_jwt(tmp_path, token):
    auth = _auth(_app_auth_path(tmp_path), access_token=token)

    with pytest.raises(RouterError) as error:
        load_credential("codex-subscription", _reference(auth))

    assert error.value.code == "UNSAFE_CREDENTIAL"
    assert token not in str(error.value)


@pytest.mark.parametrize("claim", ["different-account", None, "", True, 17])
def test_subscription_loader_rejects_unassociated_account_before_observation(tmp_path, claim):
    from agent_subagent_router.subscription_account import observe_subscription_account
    from agent_subagent_router.receipts import ReceiptStore

    auth = _auth(_app_auth_path(tmp_path), access_token=_jwt(account=claim))
    calls = []
    record = observe_subscription_account(ReceiptStore(tmp_path / "runs"), _reference(auth),
        "gpt-6-sol", getter=lambda *args: calls.append(args))

    assert record["classification"] == "UNSAFE_CREDENTIAL"
    assert record["account_queries"] == 0 and record["provider_requests"] == 0
    assert calls == [] and record["artifacts"] == []


def test_subscription_loader_rejects_oversized_or_non_private_auth(tmp_path):
    oversized = _auth(_app_auth_path(tmp_path), extra={"last_refresh": "x" * 9000})
    with pytest.raises(RouterError, match="UNSAFE_CREDENTIAL"):
        load_credential("codex-subscription", _reference(oversized))

    oversized.chmod(0o644)
    with pytest.raises(RouterError, match="UNSAFE_CREDENTIAL"):
        load_credential("codex-subscription", _reference(oversized))


@pytest.mark.parametrize("field,value", [
    ("access_token", "unsafe\r\nInjected: yes"),
    ("account_id", "unsafe\nInjected"),
    ("secret_values", ("valid-secret", "bad\u00e9-secret")),
    ("access_token", "sk-" + "A" * 24),
])
def test_typed_subscription_credential_rejects_header_injection_and_api_keys(field, value):
    args = {
        "access_token": "oauth-synthetic-token",
        "account_id": "account-synthetic",
        "secret_values": ("oauth-synthetic-token", "account-synthetic"),
    }
    args[field] = value

    with pytest.raises(RouterError):
        CodexSubscriptionCredential(**args)


def test_typed_credential_repr_is_secret_free_and_fingerprint_binds_account():
    access = "oauth-access-sentinel"
    account_a = "account-a-sentinel"
    credential_a = CodexSubscriptionCredential(
        access_token=access,
        account_id=account_a,
        secret_values=(access, "id-sentinel", "refresh-sentinel", account_a),
    )
    credential_b = CodexSubscriptionCredential(
        access_token=access,
        account_id="account-b-sentinel",
        secret_values=(access, "id-sentinel", "refresh-sentinel", "account-b-sentinel"),
    )

    assert access not in repr(credential_a)
    assert "id-sentinel" not in repr(credential_a)
    assert "refresh-sentinel" not in repr(credential_a)
    assert account_a not in repr(credential_a)
    first = credential_fingerprint("codex-subscription", credential_a)
    assert first == credential_fingerprint("codex-subscription", credential_a)
    assert first != credential_fingerprint("codex-subscription", credential_b)
    with pytest.raises(RouterError):
        credential_fingerprint("openai", credential_a)


def test_existing_api_and_string_fingerprint_behavior_are_unchanged(tmp_path):
    key = tmp_path / "api-key"
    key.write_text("sk-project-" + "A" * 32, encoding="utf-8")
    key.chmod(0o600)

    assert load_credential("openai", {"provider": "openai", "file": str(key)}) == (
        "sk-project-" + "A" * 32
    )
    assert credential_fingerprint("kimi", "legacy-key") == hash_bytes(
        b"kimi\0legacy-key"
    )
