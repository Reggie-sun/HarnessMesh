import os
from pathlib import Path

import pytest

from agent_subagent_router.contracts import hash_bytes
from agent_subagent_router.image_conformance import native_conformance
from agent_subagent_router.image_probe import prepare_probe
from agent_subagent_router.receipts import ReceiptStore


@pytest.mark.native
@pytest.mark.containment
@pytest.mark.parametrize('backend', ['codex', 'kimi'])
def test_actual_image_execution_has_os_and_completed_native_receipts(tmp_path, backend):
    config = os.environ.get('ROUTER_IMAGE_'+backend.upper()+'_CONFIG')
    if not config:
        pytest.skip('requires explicit image-only config')
    root=Path(__file__).parents[2]
    refs=[]
    for name in ['docs/superpowers/specs/2026-09-29-image-only-route-design.md',
                 'docs/superpowers/specs/2026-09-29-codex-image-api-budget-design.md',
                 'docs/superpowers/plans/2026-09-29-image-only-routes.md']:
        path=root/name
        refs.append({'path':str(path),'sha256':hash_bytes(path.read_bytes()),'accepted':True})
    store=ReceiptStore(tmp_path/'runs')
    probe=prepare_probe(store, backend=backend, model='gpt-5.4' if backend=='codex' else 'k3[1m]',
        profile='api-bounded' if backend=='codex' else 'deep', effort='high' if backend=='codex' else 'max',
        refs=refs,sandbox_config=config)
    receipt=native_conformance(store,probe['invocation_id'],sandbox_config=config)
    assert receipt['classification']=='ENGINEERING_CONFORMANCE_COMPLETE', receipt
    assert receipt['provider_requests']==0
    invocation=store.read(receipt['native_invocation_id'])
    assert invocation['container_removed'] is True
    assert invocation['classification']=='ENGINEERING_NATIVE_COMPLETE'
    assert len(invocation['upstream'])==1
    assert invocation['source_semantic']=='NOT_EVALUATED'
    assert invocation['authority']=='none' and invocation['eligible'] is False
