"""Test Runner 2, row 4 (23:00Z): Motor 1.4's and Cooling 1.4's served example recipes used the
LEGACY entries (neuralop.FNO, cooling13.neuralop.FNO), so an agent that edited the example hit
the old Carbon limits. The example is now a v2.* entry on every version that offers one, the
legacy entries say so, and the refusal tells the miner to move to a v2.* entry."""

from __future__ import annotations

import json

import pytest

from carbon.backbone_catalog import listing
from carbon.challenge_registry import cold_plate, direct, motor
from carbon.direct_campaign.spec import SPECS
from carbon.development_session import research_service, research_tools

MOTOR, COOLING = "electric-motor-magnetics", "chip-cold-plate"
F08, F02 = "f08-ribbed-bracket", "f02"


def _example_id(challenge, version):
    if challenge == MOTOR:
        return motor.catalog_recipe(version=version)["source"]["catalog_id"]
    if challenge == COOLING:
        return cold_plate.catalog_recipe(version=version)["source"]["catalog_id"]
    return direct.catalog_recipe(SPECS[challenge], version=version)["source"]["catalog_id"]


@pytest.mark.parametrize(
    ("challenge", "version"),
    [(MOTOR, "1.4"), (COOLING, "1.4"), (F08, "1.5"), (F02, "2.4")],
)
def test_the_served_example_is_a_v2_entry_where_a_version_offers_them(challenge, version):
    assert listing.preferred(challenge, version) is not None
    assert _example_id(challenge, version).startswith("v2.")


def test_a_version_with_no_v2_entries_keeps_its_old_default():
    assert listing.preferred(MOTOR, "1.3") is None
    assert motor.catalog_recipe(version="1.3")["source"]["catalog_id"] == "neuralop.FNO"


def test_the_legacy_entries_are_labelled_and_the_v2_ones_are_not():
    legacy = [e for e in listing.entries(MOTOR, "1.4") if not e["catalog_id"].startswith("v2.")]
    modern = [e for e in listing.entries(MOTOR, "1.4") if e["catalog_id"].startswith("v2.")]
    assert legacy and modern
    for e in legacy:
        assert listing.is_legacy(e["catalog_id"], MOTOR, "1.4")
        assert "legacy entry" in listing.summary(e["catalog_id"], e["backbone"], MOTOR, "1.4")
    for e in modern:
        assert not listing.is_legacy(e["catalog_id"], MOTOR, "1.4")
        assert "legacy" not in listing.summary(e["catalog_id"], e["backbone"], MOTOR, "1.4")
    # A version that offers no v2 entries has no legacy ones.
    assert not listing.is_legacy("neuralop.FNO", MOTOR, "1.3")


def test_the_describe_text_labels_legacy_entries():
    shown = motor.describe_catalog("1.4")["models"]["rebuildable"]
    by_id = {item["selector"]: item["summary"] for item in shown}
    assert "legacy entry" in by_id["neuralop.FNO"]
    assert all("legacy" not in text for sel, text in by_id.items() if sel.startswith("v2."))


def test_the_picker_flags_legacy_entries():
    from scripts.dev.miner_launchpad import toolbox

    rows = toolbox.catalog_recipes(MOTOR, "1.4")
    flagged = {r["catalog_id"] for r in rows if "legacy" in r}
    assert "neuralop.FNO" in flagged
    assert not any(c.startswith("v2.") for c in flagged)


def test_the_refusal_for_a_legacy_setting_says_which_entries_take_more():
    assert "v2.*" in research_tools.TASK_CORRECTIONS["catalog_setting_unknown"]
    assert "legacy" in research_tools.TASK_CORRECTIONS["catalog_setting_unknown"]
    assert "v2.*" in research_service.RECIPE_ISSUE_TEXT["catalog_setting_unknown"]


def test_a_legacy_entry_refuses_a_v2_only_setting_and_lists_what_it_takes():
    import types

    recipe = motor.catalog_recipe("neuralop.FNO", version="1.4")
    recipe["procedure"]["train_use"] = {"optimizer": "nadam"}
    key = types.SimpleNamespace(challenge_id=MOTOR, version="1.4")
    issues = research_service.construction_recipe_issues(recipe, key)
    assert issues[0].code == "catalog_setting_unknown"
    assert issues[0].allowed  # what the entry DOES take is named
    # The same setting on the example (a v2.* entry) is accepted.
    example = motor.catalog_recipe(version="1.4")
    example["procedure"]["train_use"] = {"optimizer": "nadam"}
    assert not research_service.construction_recipe_issues(example, key)
    json.dumps(example)
