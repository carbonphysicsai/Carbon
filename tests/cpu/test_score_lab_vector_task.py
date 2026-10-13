"""Two-to-eight dimensional toy decisions use bounded offered action sets."""

import copy
import json
from pathlib import Path

import pytest

from scripts.dev.score_lab import physics
from scripts.dev.score_lab.core import LabRefused

EXAMPLE = Path(__file__).parents[2] / "scripts/dev/score_lab/physics-example.json"


def _config(dimension=2, space="small-grid"):
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    config["problem"].update(
        dimension=dimension,
        action_count=17,
        space=space,
        constraint_coupling=1.0,
    )
    return config


@pytest.mark.parametrize("dimension,space", [(2, "small-grid"), (8, "continuous")])
def test_offered_vector_panel_is_deterministic_and_truth_is_enumerated(
    dimension, space
):
    config = _config(dimension, space)
    panel = physics.build(config)
    assert panel == physics.build(config)
    question = panel["score_questions"]["S-0"]
    assert len(question["actions"]) == 17
    assert question["fallback"] in question["actions"]
    assert question["actions"][question["fallback"]]["status"] == "FEASIBLE"
    assert all(len(aid[2:].split(",")) == dimension for aid in question["actions"])
    feasible = [
        row["objective"]
        for row in question["actions"].values()
        if row["status"] == "FEASIBLE"
    ]
    assert question["exact_best_objective"] == min(feasible)
    assert all(
        set(member["score_predictions"]["S-0"]) == set(question["actions"])
        for member in panel["members"]
    )


def test_second_coordinate_changes_objective_and_coupled_margins():
    config = _config()
    problem = config["problem"]
    first = physics._toy_truth((0.2, 0.2), 0.0, problem)
    second = physics._toy_truth((0.2, 0.8), 0.0, problem)
    assert first["objective"] != second["objective"]
    assert all(a > b for a, b in zip(first["margins"], second["margins"], strict=True))
    uncoupled = copy.deepcopy(problem)
    uncoupled["constraint_coupling"] = 0.0
    a = physics._toy_truth((0.2, 0.2), 0.0, uncoupled)
    b = physics._toy_truth((0.2, 0.8), 0.0, uncoupled)
    assert a["margins"] == b["margins"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dimension", 0),
        ("dimension", 9),
        ("action_count", 3),
        ("action_count", 257),
        ("constraint_coupling", -0.1),
        ("constraint_coupling", 1.1),
    ],
)
def test_bad_vector_settings_refuse(field, value):
    config = _config()
    config["problem"][field] = value
    with pytest.raises(LabRefused, match="physics_problem_assumptions"):
        physics.validate_config(config)
