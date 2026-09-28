from pathlib import Path

import pytest

from agent_subagent_router.contracts import RouterError, hash_bytes
from agent_subagent_router.image_inspect import inspect_images
from agent_subagent_router.image_seal import verify_image_seal
from test_image_contract import task_dict, descriptor, make_png


def test_missing_accepted_image_refs_is_zero_runtime_work(tmp_path, monkeypatch):
    def forbidden():
        raise AssertionError("runtime was consulted before accepted-ref admission")

    monkeypatch.setattr("agent_subagent_router.image_inspect.installed_runtime", forbidden)
    with pytest.raises(RouterError, match="IMAGE_ACCEPTED_REFS_REQUIRED"):
        inspect_images(task_dict(), tmp_path / "contracts")
    assert not (tmp_path / "contracts").exists()


def test_image_inspection_creates_only_private_seal_not_qualification(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from agent_subagent_router import image_inspect

    image = tmp_path / "anon.png"
    png = make_png()
    image.write_bytes(png)
    root = Path(__file__).parents[2]
    spec = root / "docs/superpowers/specs/2026-09-29-image-only-route-design.md"
    plan = root / "docs/superpowers/plans/2026-09-29-image-only-routes.md"
    value = task_dict([descriptor(str(image), png)])
    value["selected_refs"] = [
        {"path": str(p), "sha256": hash_bytes(p.read_bytes()), "accepted": True}
        for p in (spec, plan)
    ]
    monkeypatch.setattr(
        image_inspect,
        "installed_runtime",
        lambda: SimpleNamespace(
            verify=lambda: None, to_dict=lambda: {"sha256": "1" * 64, "version": "SYNTHETIC"}
        ),
    )
    monkeypatch.setattr(
        image_inspect,
        "installed_sandbox",
        lambda *args: SimpleNamespace(verify=lambda: None, image="sha256:" + "2" * 64),
    )
    result = inspect_images(value, tmp_path / "contracts")
    sealed = verify_image_seal(Path(result["manifest"]))
    assert sealed["task"]["images"][0]["sha256"] == hash_bytes(png)
    assert result["qualified_route"] is None and result["formal_execution"] == "BLOCKED"
    assert result["semantic_qualification"] == "NOT_EVALUATED"
    assert not (tmp_path / "runs").exists()
