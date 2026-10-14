"""Named stress scenarios remain explicit, toy-only, and fail closed."""

import copy
import json
from pathlib import Path

import pytest

from scripts.dev.score_lab import campaign_stress
from scripts.dev.score_lab.core import LabRefused

ROOT = Path(__file__).parents[2] / "scripts/dev/score_lab"


def _inputs():
    base = json.loads((ROOT / "physics-example.json").read_text(encoding="utf-8"))
    spec = json.loads(
        (ROOT / "campaign-stress-example.json").read_text(encoding="utf-8")
    )
    base["questions_per_side"] = 3
    base["bootstrap"] = 2
    return base, spec


def test_named_stress_configs_are_valid_distinct_and_limited():
    base, spec = _inputs()
    configs = list(campaign_stress.configs(base, spec))
    assert len(configs) == 5
    assert {name for name, _limit, _config in configs} == {
        "ev4_like_small_grid",
        "tight_boundary_coupled",
        "large_operating_shift",
        "heavy_score_path_gamer",
        "tiny_question_bank",
    }
    assert all("not" in limit or "no " in limit for _name, limit, _config in configs)
    assert configs[-1][2]["questions_per_side"] == 3
    assert base["coverage"] == 1.0  # patches never mutate the registered base


def test_bad_stress_patches_refuse_before_evaluation():
    base, spec = _inputs()
    duplicate = copy.deepcopy(spec)
    duplicate["scenarios"][1]["id"] = duplicate["scenarios"][0]["id"]
    with pytest.raises(LabRefused, match="stress_scenario"):
        list(campaign_stress.configs(base, duplicate))
    wrong_path = copy.deepcopy(spec)
    wrong_path["scenarios"][0]["edits"] = {"hidden_case": "x"}
    with pytest.raises(LabRefused, match="sweep_axis_path"):
        list(campaign_stress.configs(base, wrong_path))


def test_named_stress_evaluation_reports_toy_rows_without_selection():
    base, spec = _inputs()
    spec["scenarios"] = spec["scenarios"][:1]

    def score_only(predictions, references, metadata):
        assert all(qid.startswith("S-") for qid in predictions)
        assert "value_questions" not in metadata
        return {"score": 1.0, "gate": "PASS"}

    report = campaign_stress.evaluate(
        base, spec, {"toy": {"rule": score_only}}, "toy-digest"
    )
    assert report["scope"] == "SYNTHETIC_DEVELOPMENT"
    assert report["selection"] is None
    assert report["rows"][0]["measured_rows"] > 0
    assert report["rows"][0]["limit"].startswith("One-dimensional toy")
