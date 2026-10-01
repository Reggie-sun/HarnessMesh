"""Read-only ChatGPT quota/catalog evidence; no login, refresh or generation."""
from datetime import datetime, timezone
import http.client
import re
import ssl
import time
from pathlib import Path

from .contracts import RouterError, canonical_bytes, hash_bytes, strict_json
from .receipts import redact_known_secrets
from .transport.credentials import load_credential, credential_fingerprint

QUOTA_PATH = '/backend-api/wham/usage'
MODELS_PATH = '/backend-api/codex/models?client_version=0.154.0'
_SAFE_MODEL_SLUG = re.compile(r'[a-z0-9][a-z0-9.-]*', re.ASCII)
_GPT_MODEL_SLUG = re.compile(r'gpt-[a-z0-9][a-z0-9.-]*', re.ASCII)
_MAX_CATALOG_MODELS = 128
_MAX_MODEL_SLUG_LENGTH = 80


def _get(path, credential):
    if path not in (QUOTA_PATH, MODELS_PATH):
        raise RouterError('FORBIDDEN_UPSTREAM_PATH')
    connection = http.client.HTTPSConnection('chatgpt.com', timeout=15,
        context=ssl.create_default_context())
    deadline = time.monotonic() + 30
    response = None

    def timeout():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RouterError('SUBSCRIPTION_ACCOUNT_UNVERIFIED')
        return min(15, remaining)

    try:
        connection.connect()
        connection.auto_open = 0
        transport = connection.sock
        transport.settimeout(timeout())
        connection.request('GET', path, headers={
            'Authorization': 'Bearer ' + credential.access_token,
            'ChatGPT-Account-Id': credential.account_id,
            'User-Agent': 'codex_cli_rs/0.154.0', 'Accept': 'application/json'})
        transport.settimeout(timeout())
        response = connection.getresponse()
        raw = bytearray()
        while len(raw) <= 1024 * 1024:
            transport.settimeout(timeout())
            part = response.read1(min(65536, 1024 * 1024 + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        raw = bytes(raw)
        if response.status != 200 or len(raw) > 1024 * 1024:
            raise RouterError('SUBSCRIPTION_ACCOUNT_UNVERIFIED')
        value = strict_json(raw)
        if path == QUOTA_PATH and isinstance(value, dict) and 'account_id' in value:
            if type(value['account_id']) is not str or value['account_id'] != credential.account_id:
                raise RouterError('SUBSCRIPTION_ACCOUNT_UNVERIFIED')
            value = {k: v for k, v in value.items() if k != 'account_id'}
        if redact_known_secrets(canonical_bytes(value), tuple(x.encode() for x in credential.secret_values))[1]:
            raise RouterError('UPSTREAM_SECRET_REFLECTION')
        return value, hash_bytes(raw)
    except RouterError:
        raise
    except Exception:
        raise RouterError('SUBSCRIPTION_ACCOUNT_UNVERIFIED') from None
    finally:
        if response is not None:
            response.close()
        connection.close()


def observe_subscription_account(store, reference, model, *, getter=None, recover_projection=False):
    """At most one GET per fixed endpoint; public facts omit all account secrets."""
    run = store.create('router-image', 'subscription-account')
    facts, artifacts, queries, fingerprint = None, [], 0, None
    classification = 'INCOMPLETE'
    try:
        if model not in ('gpt-6.1-sol', 'gpt-6-sol', 'gpt-6-luna'):
            raise RouterError('SUBSCRIPTION_MODEL_UNVERIFIED')
        credential = load_credential('codex-subscription', reference,
            project_root=Path(__file__).resolve().parents[2])
        fingerprint = credential_fingerprint('codex-subscription', credential)
        get = getter or _get
        if getter is None:
            from .image_budget import reserve_subscription_account_observation
            reserve_subscription_account_observation(run.name, store=store,
                recover_projection=recover_projection, fingerprint=fingerprint, model=model)
        queries += 1
        quota, quota_hash = get(QUOTA_PATH, credential)
        queries += 1
        catalog, catalog_hash = get(MODELS_PATH, credential)
        quota_available = _quota_available(quota)
        supports_image = _model_supports_image(catalog, model)
        facts = {'provider': 'codex-subscription', 'credential_fingerprint': fingerprint,
            'authenticated': True, 'source': 'https://chatgpt.com' + QUOTA_PATH,
            'catalog_source': 'https://chatgpt.com' + MODELS_PATH,
            'quota_sha256': quota_hash, 'catalog_sha256': catalog_hash,
            'quota_available': quota_available, 'model': model,
            'image_input_supported': supports_image,
            'observed_at': datetime.now(timezone.utc).isoformat()}
        artifacts.append(store.artifact(run, 'account-evidence.json', canonical_bytes(facts),
            media_type='application/json', producer='subscription-account-observer'))
        classification = ('AUTHENTICATED_ACCOUNT_READY' if getter is None else 'ENGINEERING_ACCOUNT_READY') if quota_available and supports_image else 'INCOMPLETE'
    except (RouterError, KeyError, TypeError, ValueError, OSError) as exc:
        classification = exc.code if isinstance(exc, RouterError) else 'SUBSCRIPTION_ACCOUNT_UNVERIFIED'
    return store.finalize(run, {'kind': 'codex-subscription-account/v1',
        'classification': classification, 'credential_fingerprint': fingerprint,
        'evidence_kind': 'authenticated-https-account' if getter is None else 'synthetic-account-fixture',
        'account_queries': queries, 'provider_requests': 0, 'actual_cost_usd': None,
        'model': model, 'artifacts': artifacts, 'source_semantic': 'NOT_EVALUATED',
        'authority': 'none', 'eligible': False})


def observe_subscription_model(store, reference, model, probe_id, *, getter=None,
        discover_models=False, task=None):
    """Explicit catalog-only observation; old account/recovery ledgers are untouched."""
    run = store.create('router-image', 'subscription-model')
    artifacts, queries, fingerprint = [], 0, None
    classification = 'INCOMPLETE'
    try:
        if model not in ('gpt-6.1-sol', 'gpt-6-luna', 'gpt-6-astra'):
            raise RouterError('SUBSCRIPTION_MODEL_UNVERIFIED')
        if model == 'gpt-6-astra':
            if not isinstance(task, dict) or task.get('model') != model:
                raise RouterError('SUBSCRIPTION_MODEL_UNVERIFIED')
            from .image_contract import ImageTaskContract
            try:
                ImageTaskContract.from_dict(task)
            except (RouterError, KeyError, TypeError, ValueError):
                raise RouterError('SUBSCRIPTION_MODEL_UNVERIFIED') from None
        credential = load_credential('codex-subscription', reference,
            project_root=Path(__file__).resolve().parents[2])
        fingerprint = credential_fingerprint('codex-subscription', credential)
        if getter is None:
            from .image_budget import reserve_subscription_model_observation
            reserve_subscription_model_observation(run.name, probe_id)
        queries += 1
        catalog, catalog_hash = (getter or _get)(MODELS_PATH, credential)
        facts = {'provider': 'codex-subscription', 'credential_fingerprint': fingerprint,
            'authenticated': True, 'model': model,
            'catalog_source': 'https://chatgpt.com' + MODELS_PATH,
            'catalog_sha256': catalog_hash, 'observed_at': datetime.now(timezone.utc).isoformat(),
            **_model_facts(catalog, model)}
        if discover_models:
            facts['catalog_models'] = _project_model_catalog(catalog)
        artifacts.append(store.artifact(run, 'model-evidence.json', canonical_bytes(facts),
            media_type='application/json', producer='subscription-model-observer'))
        if facts['image_input_supported']:
            classification = 'AUTHENTICATED_MODEL_READY' if getter is None else 'ENGINEERING_MODEL_READY'
    except (RouterError, KeyError, TypeError, ValueError, OSError) as exc:
        classification = exc.code if isinstance(exc, RouterError) else 'SUBSCRIPTION_MODEL_UNVERIFIED'
    return store.finalize(run, {'kind': 'codex-subscription-model/v1',
        'classification': classification, 'credential_fingerprint': fingerprint,
        'evidence_kind': 'authenticated-https-model' if getter is None else 'synthetic-model-fixture',
        'probe_id': probe_id, 'account_queries': queries, 'provider_requests': 0,
        'model': model, 'artifacts': artifacts, 'actual_cost_usd': None,
        'source_semantic': 'NOT_EVALUATED', 'authority': 'none', 'eligible': False})


def _project_model_catalog(value):
    models = value.get('models') if isinstance(value, dict) else None
    if not isinstance(models, list) or len(models) > _MAX_CATALOG_MODELS:
        raise RouterError('SUBSCRIPTION_MODEL_CATALOG_INVALID')

    grouped = {}
    for item in models:
        if not isinstance(item, dict):
            raise RouterError('SUBSCRIPTION_MODEL_CATALOG_INVALID')
        slug = item.get('slug')
        if (type(slug) is not str or not slug.isascii() or len(slug) > _MAX_MODEL_SLUG_LENGTH
                or not _SAFE_MODEL_SLUG.fullmatch(slug)):
            raise RouterError('SUBSCRIPTION_MODEL_CATALOG_INVALID')
        if not _GPT_MODEL_SLUG.fullmatch(slug):
            if slug.startswith('gpt-'):
                raise RouterError('SUBSCRIPTION_MODEL_CATALOG_INVALID')
            continue

        modalities = item.get('input_modalities', [])
        if not isinstance(modalities, list) or any(type(modality) is not str for modality in modalities):
            raise RouterError('SUBSCRIPTION_MODEL_CATALOG_INVALID')
        explicit_modalities = {modality for modality in modalities if modality in ('text', 'image')}
        grouped.setdefault(slug, []).append(explicit_modalities)

    projection = []
    for slug in sorted(grouped):
        matches = grouped[slug]
        modalities = sorted(matches[0], key=('text', 'image').index) if len(matches) == 1 else []
        projection.append({'slug': slug, 'matched_model_count': len(matches),
            'input_modalities': modalities,
            'image_input_supported': len(matches) == 1 and 'image' in modalities})
    return projection


def _model_facts(value, model):
    models = value.get('models') if isinstance(value, dict) else None
    matches = [m for m in models if isinstance(m, dict) and m.get('slug') == model] if isinstance(models, list) else []
    modalities = matches[0].get('input_modalities') if len(matches) == 1 else None
    return {'catalog_model_count': len(models) if isinstance(models, list) else None,
        'matched_model_count': len(matches),
        'input_modalities': [x for x in ('text', 'image') if isinstance(modalities, list) and x in modalities],
        'image_input_supported': _model_supports_image(value, model)}


def _quota_available(value):
    rate = value.get('rate_limit') if isinstance(value, dict) else None
    if not isinstance(rate, dict) or rate.get('allowed') is not True or rate.get('limit_reached') is not False:
        return False
    windows = [rate.get('primary_window'), rate.get('secondary_window')]
    present = [w for w in windows if w is not None]
    return bool(present) and all(isinstance(w, dict)
        and type(w.get('used_percent')) in (int, float) and 0 <= w['used_percent'] < 100
        and type(w.get('reset_at')) is int and w['reset_at'] > 0 for w in present)


def _model_supports_image(value, model):
    models = value.get('models') if isinstance(value, dict) else None
    if not isinstance(models, list):
        return False
    matches = [m for m in models if isinstance(m, dict) and m.get('slug') == model]
    return len(matches) == 1 and isinstance(matches[0].get('input_modalities'), list) and 'image' in matches[0]['input_modalities']
