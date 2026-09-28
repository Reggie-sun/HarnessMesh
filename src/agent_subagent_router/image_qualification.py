"""Capability verdict from actual owned probe receipts; no source-review authority."""
from .image_probe import compare_probe, read_probe
from .image_run import run_image_contract


def qualify_image_route(store, probe_id, *, sandbox_config, credential_ref=None, budget_id=None,
                        cancel=None):
    probe = store.read(probe_id)
    _, rubric = read_probe(store, probe_id, probe['manifest'])
    run = store.create('router-image', 'image-qualification')
    invocation = run_image_contract(probe['manifest'], store, sandbox_config=sandbox_config,
        credential_ref=credential_ref, probe_id=probe_id, budget_id=budget_id, cancel=cancel)
    classification = 'INCOMPLETE'
    cause = invocation['classification']
    if cause == 'IMAGE_NATIVE_COMPLETE':
        raw = (store.root/invocation['invocation_id']/'model-raw.json').read_bytes()
        classification = 'QUALIFIED' if compare_probe(raw, rubric) else 'NOT_QUALIFIED'
        cause = 'VISUAL_PROBE_MATCH' if classification == 'QUALIFIED' else 'VISUAL_PROBE_MISMATCH'
    return store.finalize(run, {'kind': 'image-route-qualification/v1',
        'classification': classification, 'cause': cause, 'probe_id': probe_id,
        'native_invocation_id': invocation['invocation_id'], 'pins': probe['pins'],
        'backend': invocation['backend'], 'model': invocation['model'],
        'profile': invocation['profile'], 'effort': invocation['effort'],
        'credential_fingerprint': invocation['credential_fingerprint'],
        'envelope': {'images': 8, 'width': 128, 'height': 128,
            'generation_tokens': 2048, 'context': 'owned-probe-only'},
        'provider_requests': invocation['wire_requests'], 'actual_cost_usd': None,
        'artifacts': [], 'source_semantic': 'NOT_EVALUATED',
        'source_review_qualification': 'NOT_EVALUATED', 'authority': 'none', 'eligible': False})
