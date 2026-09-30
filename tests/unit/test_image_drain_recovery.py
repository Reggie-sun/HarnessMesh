import threading
from types import SimpleNamespace

import pytest

from agent_subagent_router import image_qualification, image_run
from agent_subagent_router.contracts import RouterError, canonical_bytes
from agent_subagent_router.receipts import ReceiptStore
from agent_subagent_router.transport import codex_broker
from test_codex_subscription_images import subscription_fixture
from test_codex_image_wire import request_fixture
from test_codex_image_broker import API_KEY, _post, _completed


def test_real_broker_drain_timeout_after_fake_wire_revokes_without_replay(tmp_path):
    task, native, _ = request_fixture(tmp_path)
    blocked, release = threading.Event(), threading.Event()
    calls, client_errors = [], []

    def upstream(*args):
        calls.append(args)
        return 200, {'content-type': 'application/json', 'x-request-id': 'req_stalled'}, canonical_bytes(_completed(task))

    def observe(value):
        if any(item.get('wire_started') for item in value):
            blocked.set()
            release.wait(5)

    broker = codex_broker.CodexBroker(task, API_KEY, upstream=upstream, on_observation=observe)
    broker.__enter__()

    def post():
        try:
            _post(broker, native)
        except Exception as exc:
            client_errors.append(type(exc).__name__)

    client = threading.Thread(target=post)
    client.start()
    try:
        assert blocked.wait(2)
        with pytest.raises(RouterError, match='OBSERVATION_DRAIN_TIMEOUT'):
            broker.__exit__(None, None, None)
        assert len(calls) == 1 and broker._active is False
    finally:
        release.set()
        client.join(3)
    assert not client.is_alive() and len(calls) == 1


@pytest.mark.parametrize('backend,profile,model', [
    ('codex', 'subscription-bounded', 'gpt-6.1-sol'),
    ('codex', 'api-bounded', 'gpt-5.4'),
    ('minimax', 'responses-bounded', 'MiniMax-M3'),
])
def test_drain_timeout_preserves_qualification_id_and_unknown_nonreplayable_invocation(
        tmp_path, monkeypatch, backend, profile, model):
    fixture = subscription_fixture if profile == 'subscription-bounded' else request_fixture
    task, _, _ = fixture(tmp_path)
    task.update(backend=backend, profile=profile, model=model)
    if backend == 'minimax':
        task['effort'] = 'provider-default'

    class StalledBroker:
        capability = 'synthetic-capability'

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            raise RouterError('OBSERVATION_DRAIN_TIMEOUT')

        def revoke(self):
            pass

        def last_activity(self):
            return 0

    class Sandbox:
        def execute(self, *args, **kwargs):
            return SimpleNamespace(stdout=b'', stderr=b'', reason='exited', exit_code=0,
                truncated=False, duration_seconds=0)

    sealed = {'task': task, 'pins': {},
        'images': [{'blob_path': item['path']} for item in task['images']]}
    manifest = tmp_path / 'manifest.json'
    manifest.write_bytes(canonical_bytes(sealed))
    store = ReceiptStore(tmp_path / 'runs')
    probe = store.create('parent', 'probe')
    store.finalize(probe, {'manifest': str(manifest), 'pins': {}, 'artifacts': []})
    monkeypatch.setattr(image_run, 'verify_image_seal', lambda _: sealed)
    monkeypatch.setattr(image_run, 'image_runtime', lambda *args: (Sandbox(), {}))
    monkeypatch.setattr(codex_broker, 'CodexBroker', StalledBroker)
    monkeypatch.setattr(image_qualification, 'verify_image_seal', lambda _: sealed)
    monkeypatch.setattr(image_qualification, 'read_probe', lambda *args: (None, {}))
    monkeypatch.setattr(image_qualification, 'run_image_contract',
        lambda manifest, store, **kwargs: image_run.run_image_contract(manifest, store,
            sandbox_config=kwargs['sandbox_config'], upstream=lambda *args: None))

    receipt = image_qualification.qualify_image_route(store, probe.name,
        sandbox_config=tmp_path / 'config')

    assert store.read(receipt['invocation_id']) == receipt
    assert receipt['classification'] == 'INCOMPLETE'
    assert receipt['cause'] == 'OBSERVATION_DRAIN_TIMEOUT'
    assert (receipt['backend'], receipt['profile'], receipt['model']) == (backend, profile, model)
    assert receipt['provider_requests'] is None and receipt['actual_cost_usd'] is None
    assert receipt['authority'] == 'none' and receipt['eligible'] is False
    pending = store.recover(receipt['native_invocation_id'])
    assert pending['outcome'] == 'unknown' and pending['replay_allowed'] is False
    with pytest.raises(RouterError, match='INCOMPLETE_RECEIPT'):
        store.read(receipt['native_invocation_id'])
    # A late durable observation cannot upgrade the already finalized qualification.
    store.observe(store.root / receipt['native_invocation_id'], {'late': True})
    assert store.read(receipt['invocation_id']) == receipt
