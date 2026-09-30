import os
from pathlib import Path

import pytest

from agent_subagent_router.contracts import hash_bytes, strict_json
from agent_subagent_router.image_conformance import native_conformance
from agent_subagent_router.image_probe import prepare_probe, read_probe
from agent_subagent_router.receipts import ReceiptStore


@pytest.mark.native
@pytest.mark.containment
@pytest.mark.parametrize('backend,model', [
    ('minimax', 'MiniMax-M3'), ('codex', 'gpt-6.1-sol'), ('codex', 'gpt-6-luna'),
])
def test_unrestricted_spending_keeps_real_os_native_images_and_receipts(tmp_path, backend, model):
    config = os.environ.get('ROUTER_IMAGE_'+backend.upper()+'_CONFIG')
    if not config:
        pytest.skip('requires explicit image-only config')
    root = Path(__file__).parents[2]
    paths = [root/'docs/superpowers/specs'/name for name in (
        '2026-09-29-image-only-route-design.md', '2026-09-29-minimax-image-route-design.md',
        '2026-09-30-codex-subscription-image-design.md', '2026-09-30-image-unrestricted-spending.md')]
    refs = [{'path': str(p), 'sha256': hash_bytes(p.read_bytes()), 'accepted': True} for p in paths]
    store = ReceiptStore(tmp_path/'runs')
    probe = prepare_probe(store, backend=backend, model=model,
        profile='responses-bounded' if backend == 'minimax' else 'subscription-bounded',
        effort='provider-default' if backend == 'minimax' else 'high',
        refs=refs, sandbox_config=config, unrestricted=True)
    read_probe(store, probe['invocation_id'], probe['manifest'])
    receipt = native_conformance(store, probe['invocation_id'], sandbox_config=config)
    assert receipt['classification'] == 'ENGINEERING_CONFORMANCE_COMPLETE', receipt
    assert len(receipt['checks']) == 14 and all(receipt['checks'].values())
    native = store.read(receipt['native_invocation_id'])
    assert native['classification'] == 'ENGINEERING_NATIVE_COMPLETE'
    assert native['container_removed'] is True and native['spending_policy'] == 'unrestricted'
    assert native['wire_requests'] == 1 and receipt['provider_requests'] == 0
    request = next(x for x in native['artifacts'] if x['path'].startswith('wire/request-'))
    body = strict_json((store.root/native['invocation_id']/request['path']).read_bytes())
    assert 'max_output_tokens' not in body and body['tools'] == []
    assert native['upstream'][0]['generation_tokens'] is None
    assert native['authority'] == 'none' and native['eligible'] is False
