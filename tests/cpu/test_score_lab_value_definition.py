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


def test_robust_worst_case_value_uses_all_near_and_extrapolated_tasks():
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    panel = physics.build(config)
    robust = physics.value_view(panel, "robust_worst_case")
    assert set(robust["value_questions"]) == {"V-0", "V-1", "V-2"}
    assert all(value is None for value in robust["exact_oracle_losses"].values())
    for old, new in zip(panel["members"], robust["members"], strict=True):
        for qid, worst in new["value_losses"].items():
            related = [
                loss
                for name, loss in old["value_losses"].items()
                if name == qid or name.endswith("-" + qid.split("-")[-1])
            ]
            assert worst == max(related)
    # Value scope changes neither the score references nor the score side.
    assert robust["score_questions"] == panel["score_questions"]
    assert [m["score_predictions"] for m in robust["members"]] == [
        m["score_predictions"] for m in panel["members"]
    ]


def test_robust_cvar_value_averages_only_the_worst_declared_tail():
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    panel = physics.build(config)
    robust = physics.value_view(panel, "robust_cvar", tail_fraction=0.5)
    for old, new in zip(panel["members"], robust["members"], strict=True):
        for qid, observed in new["value_losses"].items():
            related = sorted(
                (
                    loss
                    for name, loss in old["value_losses"].items()
                    if name == qid or name.endswith("-" + qid.split("-")[-1])
                ),
                reverse=True,
            )
            assert observed == pytest.approx(
                sum(related[: (len(related) + 1) // 2]) / ((len(related) + 1) // 2)
            )
    assert all(value is None for value in robust["exact_oracle_losses"].values())
    assert robust["score_questions"] == panel["score_questions"]
    with pytest.raises(LabRefused, match="physics_cvar_tail_fraction"):
        physics.value_view(panel, "robust_cvar")
