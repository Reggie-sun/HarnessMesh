import pytest

from agent_subagent_router.contracts import RouterError, canonical_bytes
from agent_subagent_router.image_budget import reserve_probe, require_probe_budget
from agent_subagent_router.image_probe import _png, compare_probe
from agent_subagent_router.receipts import ReceiptStore


def test_probe_reservation_cannot_be_recreated_with_new_task(tmp_path, monkeypatch):
    from agent_subagent_router import image_budget
    monkeypatch.setattr(image_budget, 'probe_reservation_root', lambda: tmp_path/'reservations')
    store = ReceiptStore(tmp_path/'runs')
    reserve_probe(store, 'codex', 'first')
    with pytest.raises(RouterError, match='IMAGE_PROBE_BUDGET_CONSUMED'):
        reserve_probe(store, 'codex', 'second')
    reserve_probe(store, 'kimi', 'other-backend')
    with pytest.raises(RouterError, match='IMAGE_PROBE_BUDGET_CONSUMED'):
        reserve_probe(ReceiptStore(tmp_path/'other-state'/'runs'), 'codex', 'new-state')


def test_missing_account_evidence_never_becomes_zero_cost(tmp_path):
    with pytest.raises(RouterError, match='IMAGE_ACCOUNT_BUDGET_UNVERIFIED'):
        require_probe_budget(ReceiptStore(tmp_path/'runs'), None, {}, 'fingerprint')


def test_strict_probe_requires_all_images_and_order():
    rubric = {'images': [{'image_id': 'a', 'shape': 'circle', 'color': 'red', 'position': 0},
        {'image_id': 'b', 'shape': 'square', 'color': 'blue', 'position': 8}]}
    assert compare_probe(canonical_bytes(rubric), rubric)
    assert not compare_probe(canonical_bytes({'images': rubric['images'][::-1]}), rubric)
    assert not compare_probe(canonical_bytes({'images': rubric['images'][:1]}), rubric)
    assert _png('circle', 'red', 0) != _png('circle', 'red', 8)
