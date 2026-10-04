"""Cooling Level-0 contract, compiler, public-material and study boundaries."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from carbon.agent_campaign import study
from carbon.challenge_readiness import admission
from carbon.cold_plate import admission_study, challenge, practice
from carbon.cold_plate.compile import ColdPlateRecipe, compile_recipe, rebuild
from carbon.development_session.research_catalog import RecipeRejected
from carbon.reconstruction import capability_registry as registry
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    compile_submission,
    validate_for_challenge,
)

REPOSITORY = Path(__file__).resolve().parents[2]
TOKEN = registry.COLD_PLATE_CHALLENGE


def strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": TOKEN,
        "backbone": "kernel_ridge",
        "parameters": parameters,
    }


def test_contract_is_exactly_the_published_krr_surface():
    from carbon import learned_baseline

    assert dict(registry.rebuildable_families(TOKEN)) == {
        "kernel_ridge": "cold_plate_kernel_ridge"
    }
    surfaces = registry.catalog_surfaces(TOKEN)
    assert tuple(registry.COLD_PLATE_LENGTHS) == tuple(learned_baseline.LENGTHS)
    assert tuple(registry.COLD_PLATE_RIDGES) == tuple(learned_baseline.RIDGES)
    assert surfaces["length"][2] == registry.COLD_PLATE_LENGTH_CHOICES
    assert surfaces["ridge"][2] == registry.COLD_PLATE_RIDGE_CHOICES
    envelope = registry.contract(TOKEN).document()["envelope"]
    assert envelope["worker_cpu"] == 2 and envelope["precision"] == "float64"

    from carbon.cold_plate.research import implementation_files

    assert "learned_baseline.py" in {path.name for path in implementation_files()}


def test_compiler_returns_only_the_guarded_recipe_and_defaults():
    compiled, recipe = compile_recipe(strategy())
    assert compiled.construction_plan.challenge_key == challenge.CHALLENGE
    assert isinstance(recipe, ColdPlateRecipe)
    assert recipe.family == "kernel_ridge"
    assert recipe.settings == {"length": 8.0, "ridge": 1e-6}
    with pytest.raises(TypeError):
        ColdPlateRecipe("kernel_ridge", (), frozenset(), "x", "y")


def test_submission_dispatches_by_challenge_and_refuses_cross_challenge():
    compiled = compile_submission(strategy(length="length_4", ridge="ridge_1e_4"))
    assert compiled.challenge == TOKEN
    assert isinstance(compiled.construction, ColdPlateRecipe)
    wrong = strategy(length="length_4", ridge="ridge_1e_4")
    wrong["backbone"] = "mlp"
    assert {
        (issue.code, issue.path) for issue in validate_for_challenge(wrong).errors
    } == {("backbone.not_in_contract", "/backbone")}
    with pytest.raises(SubmissionRefused):
        compile_submission(wrong)


@pytest.mark.parametrize(
    "value",
    [
        strategy(length="length_3"),
        strategy(ridge="ridge_3e_3"),
        strategy(length="length_4", mystery=1),
    ],
)
def test_off_grid_or_unknown_settings_fail_closed(value):
    with pytest.raises((RecipeRejected, SubmissionRefused)):
        compile_submission(value)


def test_public_material_is_digest_pinned_and_rebuild_is_deterministic(tmp_path):
    material = challenge.PublicMaterial.load(REPOSITORY)
    assert len(material.train) == 400 and len(material.practice) == 100
    _, recipe = compile_recipe(strategy(length="length_8", ridge="ridge_1e_6"))
    model_a = rebuild(recipe, material)
    model_b = rebuild(recipe, material)
    case = material.practice[0]["inputs"]
    assert model_a.predict(case) == model_b.predict(case)
    changed = tmp_path / "train.jsonl"
    changed.write_bytes(
        (REPOSITORY / challenge.TRAIN_PATH)
        .read_bytes()
        .replace(b"train-0000", b"train-x000", 1)
    )
    with pytest.raises(challenge.MaterialMismatch):
        challenge.canonical_text(changed, challenge.TRAIN_SHA256, "train")


def test_worker_staging_contains_public_train_and_inputs_but_no_practice_labels():
    material = challenge.PublicMaterial.load(REPOSITORY)
    public_practice = practice.PracticeSet.load(REPOSITORY)
    _, recipe = compile_recipe(strategy())
    staged = practice.staged_files(REPOSITORY, public_practice, recipe)
    assert set(staged) == {
        "learned-baseline.py",
        "cold-plate-domain.py",
        "cold-plate-recipes.py",
        "train-v1.jsonl",
        "practice-inputs.json",
        "recipe.json",
    }
    inputs = json.loads(staged["practice-inputs.json"])
    assert len(inputs["cases"]) == 100
    assert all(set(case) == {"case_id", "inputs"} for case in inputs["cases"])
    assert b'"outputs"' not in staged["practice-inputs.json"]
    assert material.practice[0]["outputs"]


def test_study_places_every_dimension_and_remains_unfreezable():
    adapter, contract = study.study_for(TOKEN)
    assert adapter is admission_study.STUDY
    assert {capability.dimension.value for capability in contract.capabilities} <= set(
        adapter.ladder
    )
    assert {specimen["check"] for specimen in adapter.specimens} == set(
        admission.CHECKS[admission.LEDGER_TRACK]
    )
    sheet = study.study_sheet(REPOSITORY, TOKEN)
    assert sheet["unpinned"] == ["budget", "population"]
    assert sheet["freezable"] is False and sheet["executed"] is False


@pytest.mark.skipif(os.name == "nt", reason="campaign controller is POSIX-only")
def test_evaluation_stays_typed_and_fail_closed_until_validator_adapter():
    from carbon.cold_plate import campaign
    from carbon.development_session.research_campaign import OperationRefused

    with pytest.raises(OperationRefused) as refused:
        asyncio.run(campaign.evaluate_frozen(None, 1, strategy()))
    assert refused.value.code == "cooling_validator_not_served"


def test_research_uses_the_public_measurement_authoring_surface():
    source = (REPOSITORY / "carbon" / "cold_plate" / "research.py").read_text(
        encoding="utf-8"
    )
    assert "carbon.evaluation" not in source
    assert "m.ReferencePolicyRef(" in source
