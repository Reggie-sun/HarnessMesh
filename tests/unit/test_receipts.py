import os

import pytest

from agent_subagent_router.contracts import RouterError, hash_bytes
from agent_subagent_router.receipts import ReceiptStore, redact


@pytest.mark.parametrize('mode', ['lower', 'upper', 'mixed'])
def test_known_secret_json_unicode_escapes_are_redacted(tmp_path, mode):
    secret = b'body-key-SENTINEL'
    encoded = b''.join((bytes([c]) if mode == 'mixed' and i % 2 else
                       f'\\u{c:04X}'.encode() if mode == 'upper' else f'\\u{c:04x}'.encode())
                      for i, c in enumerate(secret))
    raw = b'{"value":"' + encoded + b'"}'
    safe, count = redact(raw, (secret,))
    assert safe == b'{"value":"[REDACTED]"}' and count == 1
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('p', 't')
    artifact = store.artifact(run, 'wire.json', raw, secrets=(secret,))
    assert (run/'wire.json').read_bytes() == safe
    assert artifact['representation'] == 'redacted'


def test_private_atomic_receipt_and_redacted_hashes(tmp_path):
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('parent', 'task')
    artifact = store.artifact(run, 'stdout.txt', b'test SENTINEL secret', secrets=[b'SENTINEL'])
    receipt = store.finalize(run, {'process': {'exit_code': 0}, 'artifacts': [artifact]})
    assert b'SENTINEL' not in (run/'stdout.txt').read_bytes()
    assert artifact['sha256'] == hash_bytes((run/'stdout.txt').read_bytes())
    assert artifact['representation'] == 'redacted' and artifact['redaction_count'] == 1
    assert os.stat(run).st_mode & 0o777 == 0o700
    assert os.stat(run/'stdout.txt').st_mode & 0o777 == 0o600
    assert store.read(run.name) == receipt
    with pytest.raises(RouterError, match='RECEIPT_FINALIZED'):
        store.finalize(run, {})
    with pytest.raises(RouterError, match='RECEIPT_FINALIZED'):
        store.artifact(run, 'stdout.txt', b'x')


@pytest.mark.parametrize('path', ['../outside', '/tmp/outside', 'a/../../outside'])
def test_artifact_escape_rejected(tmp_path, path):
    store = ReceiptStore(tmp_path)
    run = store.create('p', 't')
    with pytest.raises(RouterError):
        store.artifact(run, path, b'no')


def test_artifact_tamper_and_invocation_mismatch_rejected(tmp_path):
    store = ReceiptStore(tmp_path)
    run = store.create('p', 't')
    item = store.artifact(run, 'x', b'one')
    store.finalize(run, {'artifacts': [item]})
    (run/'x').write_bytes(b'two')
    with pytest.raises(RouterError, match='ARTIFACT_MISMATCH'):
        store.read(run.name)


def test_interrupted_run_keeps_unknown_outcome(tmp_path):
    store = ReceiptStore(tmp_path)
    run = store.create('p', 't')
    recovery = store.recover(run.name)
    assert recovery['outcome'] == 'unknown'
    assert recovery['replay_allowed'] is False
    assert not (run/'invocation-receipt.json').exists()


def test_same_uuid_in_foreign_directory_cannot_escape_store(tmp_path):
    store = ReceiptStore(tmp_path/'runs')
    run = store.create('p', 't')
    foreign = tmp_path/'foreign'/run.name
    foreign.mkdir(parents=True)
    with pytest.raises(RouterError, match='ARTIFACT_ESCAPE'):
        store.artifact(foreign, 'escaped.txt', b'no')
    assert not (foreign/'escaped.txt').exists()
