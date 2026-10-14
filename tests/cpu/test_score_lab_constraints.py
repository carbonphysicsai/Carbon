"""Zero to five toy hard limits remain explicit in references and proxies."""

import json
from pathlib import Path

import pytest

from scripts.dev.score_lab import candidates, physics
from scripts.dev.score_lab.core import LabRefused

EXAMPLE = Path(__file__).parents[2] / "scripts/dev/score_lab/physics-example.json"


def _config(count):
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    config["problem"].update(constraint_count=count, constraint_offset=0.0)
    config["coverage"] = 1.0
    return config


@pytest.mark.parametrize("count", range(6))
def test_reference_prediction_and_candidate_margin_grammar_match(count):
    panel = physics.build(_config(count))
    question = panel["score_questions"]["S-0"]
    assert all(len(ref["margins"]) == count for ref in question["actions"].values())
    assert all(
        len(pred["margins"]) == count
        for member in panel["members"]
        for pred in member["score_predictions"]["S-0"].values()
    )
    proxy, refs, metadata = candidates.adapt_synthetic(panel, panel["members"][0])
    assert len(metadata["scale"]) == count + 1
    assert all(
        len(ref["margins"]) == count for row in refs.values() for ref in row.values()
    )
    assert all(
        len(pred["margins"]) == count for row in proxy.values() for pred in row.values()
    )
    if count == 0:
        assert all(ref["status"] == "FEASIBLE" for ref in question["actions"].values())


def test_constraint_offset_changes_feasible_share_without_changing_objective():
    config = _config(2)
    config["problem"]["constraint_offset"] = -0.2
    tight = physics._question("S-0", 0.06, config["problem"])
    config["problem"]["constraint_offset"] = 0.2
    loose = physics._question("S-0", 0.06, config["problem"])
    assert [row["objective"] for row in tight["actions"].values()] == [
        row["objective"] for row in loose["actions"].values()
    ]
    assert sum(row["status"] == "FEASIBLE" for row in tight["actions"].values()) < sum(
        row["status"] == "FEASIBLE" for row in loose["actions"].values()
    )


def test_zero_constraint_incomplete_coverage_refuses():
    config = _config(0)
    config["coverage"] = 0.75
    with pytest.raises(LabRefused, match="physics_coverage_or_bootstrap"):
        physics.validate_config(config)


def test_candidate_adapter_refuses_inconsistent_margin_count():
    panel = physics.build(_config(3))
    member = panel["members"][0]
    first_action = next(iter(member["score_predictions"]["S-0"]))
    member["score_predictions"]["S-0"][first_action]["margins"] = (0.1, 0.2)
    with pytest.raises(LabRefused, match="candidate_margin_grammar"):
        candidates.adapt_synthetic(panel, member)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("constraint_count", -1),
        ("constraint_count", 6),
        ("constraint_offset", -0.4),
        ("constraint_offset", 0.4),
    ],
)
def test_invalid_constraint_settings_refuse(field, value):
    config = _config(2)
    config["problem"][field] = value
    with pytest.raises(LabRefused, match="physics_problem_assumptions"):
        physics.validate_config(config)
