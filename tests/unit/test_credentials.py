
import pytest

from agent_subagent_router.contracts import RouterError
from agent_subagent_router.transport.credentials import load_credential


def test_explicit_private_file_only(tmp_path, monkeypatch):
    monkeypatch.setenv('CLI_API_KEY', 'foreign-sentinel')
    with pytest.raises(RouterError, match='CREDENTIAL_REQUIRED'):
        load_credential('kimi', None)
    secret = tmp_path/'key'
    secret.write_text('private-sentinel')
    secret.chmod(0o600)
    assert load_credential('kimi', {'provider': 'kimi', 'file': str(secret)}) == 'private-sentinel'
    secret.chmod(0o644)
    with pytest.raises(RouterError, match='UNSAFE_CREDENTIAL'):
        load_credential('kimi', {'provider': 'kimi', 'file': str(secret)})


def test_foreign_provider_and_symlink_never_fallback(tmp_path):
    key = tmp_path/'key'
    key.write_text('sentinel')
    key.chmod(0o600)
    link = tmp_path/'link'
    link.symlink_to(key)
    for ref in ({'provider': 'minimax', 'file': str(key)},
                {'provider': 'kimi', 'file': str(link)}):
        with pytest.raises(RouterError):
            load_credential('kimi', ref)
