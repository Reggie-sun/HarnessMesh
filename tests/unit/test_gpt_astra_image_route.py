import copy

import pytest

from agent_subagent_router import image_contract as contract
from agent_subagent_router.contracts import RouterError, strict_json
from agent_subagent_router.codex_image_wire import map_codex_image_request
from test_image_unrestricted_spending import fixture


SPEC = '622c3ea8c119276b837fbfa9d9bbdcff25f73f52c8dec50d24b7380cc7684570'


def astra(tmp_path):
    task, body = fixture(tmp_path, 'codex')
    task['model'] = body['model'] = 'gpt-6-astra'
    task['selected_refs'].append({'path': '/tmp/astra-spec.md', 'sha256': SPEC, 'accepted': True})
    return task, body


def test_exact_astra_tuple_requires_new_accepted_contract(tmp_path):
    task, _ = astra(tmp_path)
    assert contract.selected_subscription_model(task)
    assert contract.ImageTaskContract.from_dict(task).to_dict()['model'] == 'gpt-6-astra'
    task['selected_refs'].pop()
    with pytest.raises(RouterError, match='IMAGE_ROUTE_MISMATCH'):
        contract.ImageTaskContract.from_dict(task)


@pytest.mark.parametrize('mutation', ['effort', 'profile', 'backend', 'model', 'ref', 'accepted'])
def test_new_reference_cannot_authorize_other_tuples(tmp_path, mutation):
    task, _ = astra(tmp_path)
    if mutation == 'effort': task['effort'] = 'max'
    elif mutation == 'profile': task['profile'] = 'api-bounded'
    elif mutation == 'backend': task['backend'] = 'minimax'
    elif mutation == 'model': task['model'] = 'gpt-6-astra-alias'
    elif mutation == 'ref': task['selected_refs'][-1]['sha256'] = 'f' * 64
    else: task['selected_refs'][-1]['accepted'] = False
    assert not contract.selected_subscription_model(task)
    with pytest.raises(RouterError): contract.ImageTaskContract.from_dict(task)


def test_astra_native_wire_keeps_exact_model_tools_and_reasoning(tmp_path):
    task, body = astra(tmp_path)
    wire, proof = map_codex_image_request(task, body)
    value = strict_json(wire)
    assert value['model'] == 'gpt-6-astra'
    assert value['reasoning'] == {'effort': 'high', 'summary': 'auto'}
    assert value['tools'] == [] and 'text' not in value
    assert 'max_output_tokens' not in value and proof['generation_tokens'] is None


@pytest.mark.parametrize('mutation', ['model', 'tools', 'summary', 'verbosity', 'effort'])
def test_astra_wire_rejects_native_drift(tmp_path, mutation):
    task, body = astra(tmp_path)
    if mutation == 'model': body['model'] = 'gpt-6.1-sol'
    elif mutation == 'tools': body['tools'] = [{'type': 'web_search'}]
    elif mutation == 'summary': body['reasoning'].pop('summary')
    elif mutation == 'verbosity': body['text'] = {'verbosity': 'low'}
    else: body['reasoning']['effort'] = 'max'
    with pytest.raises(RouterError): map_codex_image_request(task, body)


def test_legacy_tuple_and_model_gate_are_unchanged(tmp_path):
    task, body = fixture(tmp_path, 'codex')
    original = copy.deepcopy(task)
    assert not contract.selected_subscription_model(task)
    contract.ImageTaskContract.from_dict(task)
    map_codex_image_request(task, body)
    assert task == original


@pytest.mark.parametrize('metadata', [None, {}, {'spending_policy': 'unknown'}])
def test_astra_cannot_enter_legacy_spending_path(tmp_path, metadata):
    task, _ = astra(tmp_path)
    task['metadata'] = metadata
    assert not contract.selected_subscription_model(task)
    with pytest.raises(RouterError): contract.ImageTaskContract.from_dict(task)


def test_astra_still_requires_original_unrestricted_authorization(tmp_path):
    task, _ = astra(tmp_path)
    task['selected_refs'] = [ref for ref in task['selected_refs']
        if ref['sha256'] != contract.UNRESTRICTED_SPENDING_SPEC_SHA]
    with pytest.raises(RouterError, match='IMAGE_SPENDING_ACCEPTANCE_REQUIRED'):
        contract.ImageTaskContract.from_dict(task)
