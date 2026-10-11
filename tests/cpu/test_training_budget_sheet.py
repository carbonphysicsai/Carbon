"""TRAINING-BUDGET-01 slice 1: the sheet and the adapter registry.

- A missing sheet value is HUMAN_INPUT and blocks the phases that use it.
- The study seed root is never in a sheet: only where it is held and its
  commitment (it lives on the producer host).
- The image is a released worker image by registry digest.
- Every Challenge with a construction contract has an adapter or a named gap.
- The shared modules hold no Challenge-specific literal.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from carbon.reconstruction import capability_registry
from carbon.training_budget import adapter, sheet

REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE = "example-challenge-v1"
COMMITMENT = "sha256:" + "ab" * 32
IMAGE = "ghcr.io/carbonphysicsai/carbon-c03-worker@sha256:" + "cd" * 32


def complete(**changes):
    document = {
        "schema": sheet.SCHEMA,
        "challenge_id": CHALLENGE,
        "challenge_version": "v1",
        "gpu_model": "example-gpu",
        "image_digest": IMAGE,
        "spend_ceiling": 10,
        "study_seed_root": {"held_by": "producer", "commitment": COMMITMENT},
        "study_contract_ranges": {"steps": [16, 40000]},
        "rebuild_time_target": 600,
        "memory_ceiling": 8_000_000_000,
        "study_time_limit": 3600,
        "seeds_per_setting": 3,
        "study_recipes": [{"width": 64}],
        "generation_ceiling": 3200,
        "minimum_panel_size": 20,
        "target_utilization": 0.5,
        "gpu_ceiling": 8,
        "expected_participation": 32,
        "study_eval_size": 200,
        "confirmation_size": 120,
    }
    document.update(changes)
    return document


def test_a_challenge_without_a_sheet_blocks_every_phase():
    empty = sheet.load(CHALLENGE, root=REPOSITORY / "does-not-exist")
    for phase in sheet.PHASES:
        with pytest.raises(sheet.SheetIncomplete) as refused:
            empty.require(phase)
        assert "challenge_id" in refused.value.fields


def test_a_complete_sheet_opens_every_phase():
    full = sheet.parse(complete(), CHALLENGE)
    for phase in sheet.PHASES:
        assert full.require(phase) is full
    assert full.get("train_size_ladder") == list(sheet.DEFAULT_TRAIN_SIZE_LADDER)


@pytest.mark.parametrize("unset", [None, sheet.HUMAN_INPUT])
def test_an_unset_value_blocks_only_the_phases_that_use_it(unset):
    partial = sheet.parse(complete(gpu_ceiling=unset), CHALLENGE)
    with pytest.raises(sheet.SheetIncomplete) as refused:
        partial.require("R11")
    assert refused.value.fields == ("gpu_ceiling",)
    partial.require("G")


@pytest.mark.parametrize(
    "root",
    [
        "0123456789abcdef",
        12345,
        {"held_by": "producer", "commitment": "0123"},
        {"held_by": "producer", "commitment": COMMITMENT, "root": "0123"},
        {"commitment": COMMITMENT},
    ],
)
def test_a_sheet_never_holds_the_study_seed_root(root):
    with pytest.raises(sheet.SheetInvalid) as refused:
        sheet.parse(complete(study_seed_root=root), CHALLENGE)
    assert refused.value.field == "study_seed_root"


@pytest.mark.parametrize(
    "image",
    [
        "carbon-c03-worker:latest",
        "ghcr.io/carbonphysicsai/carbon-c03-worker:worker-images-v1",
        "docker.io/library/carbon-c03-worker@sha256:" + "cd" * 32,
        "ghcr.io/someone/carbon-c03-worker@sha256:" + "cd" * 32,
    ],
)
def test_the_image_is_a_released_digest(image):
    with pytest.raises(sheet.SheetInvalid):
        sheet.parse(complete(image_digest=image), CHALLENGE)


@pytest.mark.parametrize(
    "changes",
    [
        {"seeds_per_setting": 2},
        {"target_utilization": 1.5},
        {"study_contract_ranges": {"steps": [40000, 16]}},
        {"train_size_ladder": [1, -2]},
        {"unknown_field": 1},
        {"challenge_id": "another-challenge"},
        {"schema": "carbon.training-budget.sheet.v0"},
    ],
)
def test_a_malformed_sheet_is_refused_not_read_as_unset(changes):
    with pytest.raises(sheet.SheetInvalid):
        sheet.parse(complete(**changes), CHALLENGE)


def test_a_sheet_file_is_loaded_by_challenge(tmp_path):
    (tmp_path / f"{CHALLENGE}.json").write_text(json.dumps(complete()))
    assert sheet.load(CHALLENGE, root=tmp_path).get("gpu_ceiling") == 8


def test_the_battery_sheet_is_for_testing_and_explains_every_value():
    """OWNER-BATTERY-STUDY-SHEET-01: team-proposed, owner-approved for testing,
    never production; every set value carries its reason. Its study seed root
    stays unset until the producer records the commitment, so every phase is
    blocked until then. Its image stays unset until worker-images-v3 is
    released (OWNER-BATTERY-STUDY-4090-01, #826), which blocks every phase and
    rule."""
    battery = capability_registry.BATTERY_CHALLENGE
    loaded = sheet.load(battery)
    assert loaded.status == "TEAM_PROPOSED_OWNER_APPROVED_FOR_TESTING"
    document = json.loads((sheet.SHEETS / f"{battery}.json").read_text())
    assert set(loaded.values) - {"challenge_id"} <= set(document["rationale"])
    assert loaded.get("study_seed_root") is None
    assert loaded.get("image_digest") is None
    for phase in "ABCDEFGH":
        with pytest.raises(sheet.SheetIncomplete) as refused:
            loaded.require(phase)
        assert refused.value.fields == ("image_digest", "study_seed_root")
    for phase in ("R3", "R9", "R11", "stop"):
        with pytest.raises(sheet.SheetIncomplete) as refused:
            loaded.require(phase)
        assert refused.value.fields == ("image_digest",)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "PRODUCTION"},
        {"status": "TEAM_PROPOSED_OWNER_APPROVED_FOR_TESTING", "rationale": {}},
        {"rationale": {"not_a_field": "x"}},
    ],
)
def test_a_sheet_status_and_rationale_are_checked(changes):
    with pytest.raises(sheet.SheetInvalid):
        sheet.parse(complete(**changes), CHALLENGE)


def test_every_contract_has_an_adapter_or_a_named_gap():
    adapters, gaps = set(adapter.registered()), adapter.gaps()
    assert adapters | set(gaps) == set(capability_registry.CONTRACTS)
    assert not adapters & set(gaps)
    assert all(reason.strip() for reason in gaps.values())
    for challenge in gaps:
        with pytest.raises(adapter.NoAdapter):
            adapter.adapter_for(challenge)


def test_the_battery_adapter_names_its_records():
    battery = adapter.adapter_for(capability_registry.BATTERY_CHALLENGE)
    assert battery.train_cases() == 400
    assert set(battery.backends()) == {"jax", "pytorch"}
    for item in adapter.RECORD_ITEMS:
        assert adapter.record(battery, item) is not None


def test_shared_modules_hold_no_challenge_literal():
    """Battery is the first instance, never the design."""
    tokens = set(capability_registry.CONTRACTS) | {
        "battery",
        "burgers",
        "cold-plate",
        "motor",
    }
    pattern = re.compile("|".join(re.escape(t) for t in sorted(tokens)), re.IGNORECASE)
    shared = sorted((REPOSITORY / "carbon" / "training_budget").glob("*.py"))
    assert shared
    for path in shared:
        assert not pattern.search(path.read_text()), path.name
