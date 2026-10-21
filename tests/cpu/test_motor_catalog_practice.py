"""Motor catalog practice (OWNER-BACKBONE-CATALOG-01): the recipe is expanded to
its Carbon bundle and rebuilt by the receiver's own call with the receiver's
inputs; PRACTICE is scored with Motor's scorer. The C-03 build is injected
here; its custody is the bundle worker's own tests'."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from test_lp_prod_research_tools import ledger

from carbon.challenge_registry.motor import catalog_recipe
from carbon.development_session import bundle_construction_worker as worker
from carbon.motor import catalog_practice


@pytest.fixture
def practice(tmp_path, monkeypatch):
    calls = []

    def fake(ledger_, **kwargs):
        calls.append(kwargs)
        reference = kwargs["inputs"]
        rows = np.full((len(reference), 60), 1.0).tolist()
        state = "sha256:" + "5" * 64
        return SimpleNamespace(
            build=SimpleNamespace(state_digest=state),
            inference=SimpleNamespace(state_digest=state, predictions=rows),
        )

    monkeypatch.setattr(worker, "reconstruct_and_infer_public", fake)
    meter = ledger(tmp_path / "ledger")
    parent = SimpleNamespace(image_id="sha256:" + "7" * 64)
    resolved = []
    item = catalog_practice.MotorCatalogPractice(
        ledger=meter,
        owner="alice",
        parent=parent,
        cache_root=tmp_path / "cache",
        root=".",
        resolver=lambda ref: resolved.append(ref) or SimpleNamespace(bundle_ref=ref),
        parents=SimpleNamespace(for_bundle=lambda _ref: parent),
    )
    return item, calls, resolved


def test_a_catalog_recipe_runs_as_its_bundle_with_the_receivers_inputs(practice):
    item, calls, resolved = practice
    result = item("motor-catalog-0001", catalog_recipe("neuralop.FNO"))
    (call,) = calls
    assert call["seed"] == 0 and call["recipe"].to_dict()["source"]["kind"] == "bundle"
    assert (
        call["inference_image"] is item.parent
        and call["construction_parent"] is item.parent
    )
    assert (
        resolved[0].bundle_digest
        == call["recipe"].to_dict()["source"]["bundle_ref"]["bundle_digest"]
    )
    assert result["provenance"] == "MOTOR_PUBLIC_PRACTICE"
    assert result["catalog_id"] == "neuralop.FNO"
    assert result["recipe"] == catalog_recipe("neuralop.FNO")
    assert result["summary"]  # Motor's practice scorer ran on PRACTICE


def test_an_uninstalled_entry_is_not_served_here_before_anything_runs(tmp_path):
    meter = ledger(tmp_path / "ledger")

    def missing(ref):
        raise FileNotFoundError("verified child missing")

    item = catalog_practice.MotorCatalogPractice(
        ledger=meter,
        owner="alice",
        parent=SimpleNamespace(image_id="sha256:" + "7" * 64),
        cache_root=tmp_path / "cache",
        resolver=missing,
        parents=SimpleNamespace(for_bundle=lambda _ref: None),
    )
    assert item.backend_refusal(catalog_recipe("neuralop.FNO")) == ()


def test_a_level0_strategy_is_not_a_catalog_recipe(practice):
    item, calls, _ = practice
    strategy = {
        "schema_version": "1.0",
        "challenge_id": "electric-motor-magnetics",
        "backbone": "kernel_ridge",
        "parameters": {},
    }
    with pytest.raises(ValueError):
        item("motor-catalog-0002", strategy)
    assert calls == []


# --- two CPU parents: each entry builds on its own runtime's parent -----------


def _two_parent_practice(tmp_path, monkeypatch, parents):
    from test_direct_parents import torch_image

    calls = []

    def fake(ledger_, **kwargs):
        calls.append(kwargs)
        rows = np.full((len(kwargs["inputs"]), 60), 1.0).tolist()
        state = "sha256:" + "5" * 64
        return SimpleNamespace(
            build=SimpleNamespace(state_digest=state),
            inference=SimpleNamespace(state_digest=state, predictions=rows),
        )

    monkeypatch.setattr(worker, "reconstruct_and_infer_public", fake)
    item = catalog_practice.MotorCatalogPractice(
        ledger=ledger(tmp_path / "ledger"),
        owner="alice",
        parent=torch_image(),
        cache_root=tmp_path / "cache",
        root=".",
        version="1.3",  # the jNO entries are offered on Motor 1.3
        resolver=lambda ref: SimpleNamespace(bundle_ref=ref),
        parents=parents,
    )
    return item, calls


def test_a_jno_entry_builds_on_the_cpu_parent_and_infers_on_torch(
    tmp_path, monkeypatch
):
    from test_direct_parents import torch_image

    from carbon.development_session.gpu_practice import DirectParents

    parents = DirectParents.from_torch(torch_image())
    item, calls = _two_parent_practice(tmp_path, monkeypatch, parents)
    result = item("motor-catalog-0003", catalog_recipe("jno.fno1d", version="1.3"))
    (call,) = calls
    assert call["construction_parent"] == parents.for_runtime("python-cpu-py311")
    assert call["inference_image"] == torch_image()
    assert result["backend"]["parent"] == torch_image().base_image_digest
    item("motor-catalog-0004", catalog_recipe("neuralop.FNO", version="1.3"))
    assert calls[1]["construction_parent"] == torch_image()


def test_without_the_cpu_parent_a_jno_entry_is_not_served(tmp_path, monkeypatch):
    from test_direct_parents import torch_image

    from carbon.development_session.gpu_practice import DirectParents

    parents = DirectParents({"torch-cpu-py311": torch_image()})
    item, calls = _two_parent_practice(tmp_path, monkeypatch, parents)
    installed = item.backend_refusal(catalog_recipe("jno.fno1d", version="1.3"))
    assert installed and not [i for i in installed if i.startswith("jno.")]
    assert item.backend_refusal(catalog_recipe("neuralop.FNO", version="1.3")) is None
    assert calls == []


@pytest.mark.parametrize("eligible", [True, False])
def test_the_cpu_parent_is_served_only_when_docker_finds_it(
    tmp_path, monkeypatch, eligible
):
    from test_direct_parents import torch_image

    from carbon.reconstruction.worker import docker_runtime

    seen = []

    def doctor(*, image_id, image_identity):
        seen.append(image_id)
        return SimpleNamespace(eligible=eligible)

    monkeypatch.setattr(docker_runtime, "doctor", doctor)
    item, _ = _two_parent_practice(tmp_path, monkeypatch, None)
    assert item.parents().runtimes() == (
        ("python-cpu-py311", "torch-cpu-py311") if eligible else ("torch-cpu-py311",)
    )
    assert seen == [torch_image().base_image_digest]


def test_a_not_served_entry_is_corrected_with_the_installed_catalog_ids():
    # A catalog practice refuses an uninstalled entry by listing the entries
    # installed here; those are Carbon's public catalog ids, so the correction
    # must accept them (it raised TypeError when only Level 0 backends were
    # listable). A value outside Carbon's lists is still refused.
    from carbon.backbone_catalog import listing
    from carbon.development_session.research_tools import TaskContractMismatch

    installed = tuple(e["catalog_id"] for e in listing.entries())[:3]
    refusal = TaskContractMismatch("backend_not_served", "strategy_json", installed)
    assert refusal.choices == installed
    with pytest.raises(TypeError):
        TaskContractMismatch("backend_not_served", "strategy_json", ("miner.Own",))


@pytest.mark.parametrize("practice_module", ["motor", "cooling"])
def test_the_practice_binding_is_the_one_the_bundle_worker_accepts(
    tmp_path, monkeypatch, practice_module
):
    # The bundle worker refuses any binding but its exact five fields
    # (`_checked_binding`); catalog practice passed the kit's own `id`/`version`
    # keys, so every real catalog practice was refused
    # `bundle_challenge_binding_invalid` while stubbed tests passed.
    from carbon.development_session.bundle_construction_worker import _checked_binding
    from carbon.development_session.construction_recipe import ConstructionRecipe

    seen = {}

    def worker_stand_in(ledger_, **kwargs):
        seen.update(kwargs)
        _checked_binding(kwargs["recipe"], kwargs["challenge_binding"])
        raise RuntimeError("stop after the binding check")

    monkeypatch.setattr(worker, "reconstruct_and_infer_public", worker_stand_in)
    if practice_module == "motor":
        item = catalog_practice.MotorCatalogPractice(
            ledger=ledger(tmp_path / "ledger"),
            owner="alice",
            parent=SimpleNamespace(image_id="sha256:" + "7" * 64),
            cache_root=tmp_path / "cache",
            resolver=lambda ref: SimpleNamespace(bundle_ref=ref),
            parents=SimpleNamespace(for_bundle=lambda _ref: None),
        )
        recipe = catalog_recipe("neuralop.FNO")
    else:
        from carbon.challenge_registry.cold_plate import (
            catalog_recipe as cooling_recipe,
        )
        from carbon.cold_plate import catalog_practice as cooling_practice

        item = cooling_practice.CoolingCatalogPractice(
            ledger=ledger(tmp_path / "ledger"),
            owner="alice",
            parent=SimpleNamespace(image_id="sha256:" + "7" * 64),
            cache_root=tmp_path / "cache",
            version="1.2",
            resolver=lambda ref: SimpleNamespace(bundle_ref=ref),
            parents=SimpleNamespace(for_bundle=lambda _ref: None),
        )
        recipe = cooling_recipe("cooling.neuralop.FNO", version="1.2")
    with pytest.raises(RuntimeError, match="stop after the binding check"):
        item("motor-catalog-binding", recipe)
    assert set(seen["challenge_binding"]) == {
        "challenge_id",
        "challenge_version",
        "train_digest",
        "interface_digest",
        "construction_limits_digest",
    }
    assert isinstance(seen["recipe"], ConstructionRecipe)
