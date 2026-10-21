"""One direct-candidate record for a miner's freeze and Graphite's SELECT
(OWNER-BACKBONE-CATALOG-01): Graphite could select no direct recipe, since its
record wanted a Level 0 challenge_id. A catalog recipe is recorded as written,
with the Carbon bundle it stands for as its construction source."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from carbon.backbone_catalog import pipeline
from carbon.challenge_kit import physical_public
from carbon.challenge_registry.motor import catalog_recipe
from carbon.development_session.research_campaign import (
    OperationRefused,
    direct_candidate_record,
)

MOTOR = "electric-motor-magnetics"


def prepared(tmp_path):
    campaign = SimpleNamespace(
        construction_kit=lambda: physical_public.construction_kit(MOTOR, "1.2"),
        construction_reconstruct=lambda *a, **k: None,
    )
    return SimpleNamespace(
        ledger=SimpleNamespace(root=tmp_path), owner="alice", campaign=campaign
    )


def test_a_catalog_recipe_is_recorded_with_its_bundle_as_source(tmp_path):
    recipe = catalog_recipe("transolver")
    record, envelope = direct_candidate_record(
        prepared(tmp_path), recipe, "best practice", True
    )
    assert envelope is None
    assert record["schema"] == "carbon.direct-selected-recipe.v2"
    assert record["strategy"] == recipe
    assert (
        record["construction_source_digest"]
        == pipeline.entry("transolver")["bundle_ref"]["bundle_digest"]
    )
    assert record["catalog"]["catalog_id"] == "transolver"


def test_a_refused_catalog_setting_is_refused_by_its_code(tmp_path):
    recipe = copy.deepcopy(catalog_recipe("neuralop.FNO"))
    recipe["procedure"]["train_use"] = {"steps": 0}
    with pytest.raises(OperationRefused, match="catalog_setting_invalid"):
        direct_candidate_record(prepared(tmp_path), recipe, "x", False)


def test_a_campaign_without_construction_hooks_serves_no_direct_selection(tmp_path):
    bare = SimpleNamespace(
        ledger=SimpleNamespace(root=tmp_path), owner="alice", campaign=SimpleNamespace()
    )
    with pytest.raises(OperationRefused, match="construction_reconstruction_unserved"):
        direct_candidate_record(bare, catalog_recipe(), "x", False)
