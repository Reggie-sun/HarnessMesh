import os
from pathlib import Path

import pytest

from agent_subagent_router.contracts import hash_bytes, strict_json
from agent_subagent_router.image_conformance import native_conformance
from agent_subagent_router.image_probe import prepare_probe
from agent_subagent_router.receipts import ReceiptStore


@pytest.mark.native
@pytest.mark.containment
@pytest.mark.parametrize('model', ['gpt-6.1-sol', 'gpt-6-sol', 'gpt-6-luna'])
def test_subscription_model_has_real_docker_isolation_and_uncapped_native_input(tmp_path, model):
    config = os.environ.get('ROUTER_IMAGE_CODEX_CONFIG')
    if not config:
        pytest.skip('requires explicit image-only config')
    root = Path(__file__).parents[2]
    refs = []
    for name in ['docs/superpowers/specs/2026-09-29-image-only-route-design.md',
                 'docs/superpowers/specs/2026-09-30-codex-subscription-image-design.md',
                 'docs/superpowers/plans/2026-09-29-image-only-routes.md']:
        path = root / name
        refs.append({'path': str(path), 'sha256': hash_bytes(path.read_bytes()), 'accepted': True})
    store = ReceiptStore(tmp_path / 'runs')
    probe = prepare_probe(store, backend='codex', model=model, profile='subscription-bounded',
        effort='high', refs=refs, sandbox_config=config)
    receipt = native_conformance(store, probe['invocation_id'], sandbox_config=config)
    assert receipt['classification'] == 'ENGINEERING_CONFORMANCE_COMPLETE', receipt
    assert receipt['provider_requests'] == 0 and all(receipt['checks'].values())
    native = store.read(receipt['native_invocation_id'])
    assert native['container_removed'] is True
    assert native['classification'] == 'ENGINEERING_NATIVE_COMPLETE'
    observation = native['upstream'][0]
    assert observation['upstream_host'] == 'chatgpt.com'
    assert observation['upstream_path'] == '/backend-api/codex/responses'
    assert observation['generation_tokens'] is None
    assert observation['response_max_output_tokens'] is None
    assert observation['wire_proof']['observed_output_tokens_limit'] == 2048
    request = next(x for x in native['artifacts'] if x['path'].startswith('wire/request-'))
    payload = strict_json((store.root/native['invocation_id']/request['path']).read_bytes())
    assert payload['tools'] == [] and 'max_output_tokens' not in payload
    assert payload['model'] == model
    assert native['authority'] == 'none' and native['eligible'] is False
