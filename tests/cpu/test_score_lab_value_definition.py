"""Toy buyer-value definition is a prospective analysis lever."""

import copy
import json
from pathlib import Path

import pytest

from scripts.dev.score_lab import physics
from scripts.dev.score_lab.core import LabRefused

EXAMPLE = Path(__file__).parents[2] / "scripts/dev/score_lab/physics-example.json"


def test_legacy_one_pick_changes_value_without_changing_score_questions():
    base = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    base["questions_per_side"] = 3
    shortlist = physics.build(base)
    legacy_config = copy.deepcopy(base)
    legacy_config["value_definition"] = "legacy_one_pick"
    legacy = physics.build(legacy_config)
    assert shortlist["score_questions"] == legacy["score_questions"]
    assert [m["score_predictions"] for m in shortlist["members"]] == [
        m["score_predictions"] for m in legacy["members"]
    ]
    assert any(
        a["value_losses"] != b["value_losses"]
        for a, b in zip(shortlist["members"], legacy["members"], strict=True)
    )


def test_unknown_value_definition_refuses():
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["value_definition"] = "hidden_exam"
    with pytest.raises(LabRefused, match="physics_value_definition"):
        physics.validate_config(config)


def test_legacy_one_pick_does_not_gain_extra_verification_slots():
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    config["value_definition"] = "legacy_one_pick"
    config["decision"]["k"] = 1
    one = physics.build(config)
    config["decision"]["k"] = 5
    five = physics.build(config)
    assert [m["value_losses"] for m in one["members"]] == [
        m["value_losses"] for m in five["members"]
    ]
    assert one["exact_oracle_losses"] == five["exact_oracle_losses"]
