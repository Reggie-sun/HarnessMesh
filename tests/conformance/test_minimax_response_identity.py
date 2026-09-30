import os
from pathlib import Path

import pytest

from agent_subagent_router.contracts import canonical_bytes, hash_bytes
from agent_subagent_router.image_conformance import native_conformance
from agent_subagent_router.image_probe import prepare_probe, read_probe
from agent_subagent_router.image_run import run_image_contract
from agent_subagent_router.receipts import ReceiptStore


@pytest.mark.native
@pytest.mark.containment
def test_real_container_binds_documented_body_identity_without_request_header(tmp_path):
    config = os.environ.get('ROUTER_IMAGE_MINIMAX_CONFIG')
    if not config:
        pytest.skip('requires explicit image-only config')
    root = Path(__file__).parents[2]
    refs = []
    for name in ['2026-09-29-image-only-route-design.md',
                 '2026-09-29-minimax-image-route-design.md',
                 '2026-09-30-image-unrestricted-spending.md',
                 '2026-10-01-minimax-response-identity.md']:
        path = root/'docs/superpowers/specs'/name
        refs.append({'path': str(path), 'sha256': hash_bytes(path.read_bytes()), 'accepted': True})
    store = ReceiptStore(tmp_path/'runs')
    probe = prepare_probe(store, backend='minimax', model='MiniMax-M3',
        profile='responses-bounded', effort='provider-default', refs=refs,
        sandbox_config=config, unrestricted=True)
    conformance = native_conformance(store, probe['invocation_id'], sandbox_config=config)
    assert conformance['classification'] == 'ENGINEERING_CONFORMANCE_COMPLETE'
    _, rubric = read_probe(store, probe['invocation_id'], probe['manifest'])
    response = {'id': 'minimax_documented_response', 'object': 'response', 'status': 'completed',
        'model': 'MiniMax-M3', 'store': False, 'output': [{'id': 'minimax_message',
            'type': 'message', 'role': 'assistant', 'status': 'completed',
            'content': [{'type': 'output_text', 'text': canonical_bytes(rubric).decode()}]}],
        'usage': {'input_tokens': 100, 'output_tokens': 100}}
    receipt = run_image_contract(probe['manifest'], store, sandbox_config=config,
        probe_id=probe['invocation_id'], upstream=lambda *args: (
            200, {'content-type': 'application/json'}, canonical_bytes(response)))
    assert receipt['classification'] == 'ENGINEERING_NATIVE_COMPLETE'
    assert receipt['container_removed'] is True and receipt['wire_requests'] == 1
    assert receipt['upstream'][0]['response_request_id_source'] == 'response-id'
    assert receipt['upstream'][0]['response_request_id'] == response['id']
    assert receipt['upstream'][0]['response_sha256'] == hash_bytes(canonical_bytes(response))
    assert receipt['authority'] == 'none' and receipt['eligible'] is False
