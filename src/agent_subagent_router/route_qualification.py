"""Parent-owned route qualification combines immutable smoke and account evidence."""
from datetime import datetime, timezone

from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .transport.credentials import credential_fingerprint, load_credential


def qualify_route(store, smoke_id: str, credential_ref: dict, *, entitlement: dict | None = None):
    smoke = store.read(smoke_id)
    if (smoke.get('kind') != 'standalone-route-smoke' or smoke.get('classification') != 'PARSED'
            or smoke.get('evidence_kind') != 'live' or not smoke.get('observations')
            or any(o.get('classification') != 'IDENTITY_VERIFIED'
                   or o.get('proof') != 'authenticated_endpoint_declaration' for o in smoke['observations'])):
        raise RouterError('ROUTE_NOT_QUALIFIED')
    is_deep = smoke['profile']['name'] == 'deep'
    fingerprint = credential_fingerprint('kimi', load_credential('kimi', credential_ref))
    if is_deep:
        validate_entitlement(entitlement)
        if entitlement.get('credential_fingerprint') != fingerprint:
            raise RouterError('ENTITLEMENT_CREDENTIAL_MISMATCH')
    run = store.create('parent-route-qualification', 'qualify-'+smoke['profile']['name'])
    artifacts = [store.artifact(run, 'source-smoke.json', canonical_bytes(smoke),
                               media_type='application/json')]
    if is_deep:
        artifacts.append(store.artifact(run, 'account-entitlement.json', canonical_bytes(entitlement),
                                        media_type='application/json'))
    return store.finalize(run, {'kind': 'route-qualification', 'classification': 'PARSED',
        'evidence_kind': 'live', 'source_smoke_id': smoke_id, 'profile': smoke['profile'],
        'runtime': smoke['runtime'], 'observations': smoke['observations'],
        'credential_fingerprint': fingerprint,
        'deep_entitlement': 'VERIFIED' if is_deep else 'NOT_APPLICABLE',
        'account_entitlement': entitlement if is_deep else None, 'artifacts': artifacts,
        'wire_requests': 0, 'actual_context_consumption': 'small smoke only',
        'parent_acceptance': 'ROUTE_ONLY', 'project_acceptance': 'NOT_EVALUATED'})


def validate_entitlement(entitlement):
    try:
        fresh = datetime.fromisoformat(entitlement['observed_at'].replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc)-fresh).total_seconds()
        valid = (entitlement['kind'] == 'account-entitlement-observation'
                 and entitlement['source'] == 'https://www.kimi.com/code/console'
                 and entitlement['credential_match'] is True
                 and entitlement['tier'] in ('Pro', 'Max', 'Allegretto', 'Allegro', 'Vivace')
                 and entitlement['entitled_context_tokens'] >= 1048576 and 0 <= age <= 86400)
    except (KeyError, TypeError, ValueError, AttributeError):
        valid = False
    if not valid:
        raise RouterError('ENTITLEMENT_UNVERIFIED', 'fresh parent-observed account evidence required')


def read_qualification(store, identifier):
    if not isinstance(identifier, str):
        raise RouterError('ROUTE_NOT_QUALIFIED', 'immutable qualification ID required')
    value = store.read(identifier)
    if value.get('kind') != 'route-qualification':
        raise RouterError('ROUTE_NOT_QUALIFIED')
    source = store.read(value['source_smoke_id'])
    artifact = strict_json((store.root/identifier/'source-smoke.json').read_bytes())
    if artifact != source or any(value.get(k) != source.get(k) for k in ('profile', 'runtime', 'observations')):
        raise RouterError('QUALIFICATION_BINDING_MISMATCH')
    if value['profile']['name'] == 'deep':
        account = strict_json((store.root/identifier/'account-entitlement.json').read_bytes())
        if (account != value.get('account_entitlement')
                or account.get('credential_fingerprint') != value.get('credential_fingerprint')):
            raise RouterError('QUALIFICATION_BINDING_MISMATCH')
    return value, hash_bytes(canonical_bytes(value))
