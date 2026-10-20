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
