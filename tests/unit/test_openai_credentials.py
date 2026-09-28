from pathlib import Path

import pytest

import agent_subagent_router.transport.credentials as credentials
from agent_subagent_router.contracts import RouterError
from agent_subagent_router.transport.credentials import load_credential


def _private_file(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


def test_openai_accepts_only_explicit_private_api_key_file(tmp_path):
    key = _private_file(tmp_path / "openai-key", "sk-proj-" + "A" * 32)

    assert load_credential("openai", {"provider": "openai", "file": str(key)}) == (
        "sk-proj-" + "A" * 32
    )


@pytest.mark.parametrize("value", [
    "oauth-access-token-not-an-api-key",
    "sk-short",
    "sk-contains spaces and is long enough",
    "sk-" + "A" * 20 + "\nsecond-line",
])
def test_openai_rejects_oauth_malformed_or_nonprintable_values_without_echoing_them(
    tmp_path, value
):
    key = _private_file(tmp_path / "openai-key", value)

    with pytest.raises(RouterError) as error:
        load_credential("openai", {"provider": "openai", "file": str(key)})

    assert error.value.code == "UNSAFE_CREDENTIAL"
    assert value not in str(error.value)


def test_openai_rejects_global_codex_path_before_opening_it(tmp_path, monkeypatch):
    global_auth = _private_file(tmp_path / ".codex" / "auth.json", "sk-" + "A" * 32)
    original_open = credentials.os.open
    attempted = []

    def track_open(path, *args, **kwargs):
        attempted.append(str(path))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(credentials.os, "open", track_open)
    with pytest.raises(RouterError) as error:
        load_credential("openai", {"provider": "openai", "file": str(global_auth)})

    assert error.value.code == "UNSAFE_CREDENTIAL"
    assert str(global_auth) not in attempted


def test_openai_rejects_symlink_and_group_readable_files(tmp_path):
    target = _private_file(tmp_path / "key", "sk-" + "A" * 32)
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(RouterError, match="UNSAFE_CREDENTIAL"):
        load_credential("openai", {"provider": "openai", "file": str(link)})

    target.chmod(0o640)
    with pytest.raises(RouterError, match="UNSAFE_CREDENTIAL"):
        load_credential("openai", {"provider": "openai", "file": str(target)})


def test_openai_credential_must_stay_outside_project(tmp_path):
    project = tmp_path / "project"
    key = _private_file(project / "key", "sk-" + "A" * 32)

    with pytest.raises(RouterError, match="UNSAFE_CREDENTIAL"):
        load_credential(
            "openai", {"provider": "openai", "file": str(key)}, project_root=project
        )


def test_existing_kimi_credential_values_keep_their_original_contract(tmp_path):
    key = _private_file(tmp_path / "kimi-key", "legacy-kimi-private-value")

    assert load_credential("kimi", {"provider": "kimi", "file": str(key)}) == (
        "legacy-kimi-private-value"
    )
