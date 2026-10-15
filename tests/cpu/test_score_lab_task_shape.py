"""Optional analytic toy shape levers preserve the old default contract."""

import copy
import json
from itertools import pairwise
from pathlib import Path

import pytest

from scripts.dev.score_lab import physics
from scripts.dev.score_lab.core import LabRefused

EXAMPLE = Path(__file__).parents[2] / "scripts/dev/score_lab/physics-example.json"


def _config():
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    return config


def _objective(x, problem):
    return physics._toy_truth(x, 0.0, problem)["objective"]


def test_explicit_shape_defaults_preserve_old_analytic_panel():
    original = _config()
    original["problem"]["optima"] = "single"
    explicit = copy.deepcopy(original)
    explicit["problem"].update(
        optima_count=1,
        objective_kind="single",
        objective_weight=0.5,
        roughness=0.0,
        optimum_location="interior",
    )
    old, new = physics.build(original), physics.build(explicit)
    assert (
        old["assumption"]["physics_config_sha256"]
        != new["assumption"]["physics_config_sha256"]
    )
    del old["assumption"]["physics_config_sha256"]
    del new["assumption"]["physics_config_sha256"]
    assert old == new


def test_explicit_one_well_overrides_legacy_multi_shorthand():
    problem = _config()["problem"]
    problem["optima"] = "multi"
    old_mid = _objective(0.32, problem)
    problem["optima_count"] = 1
    assert _objective(0.32, problem) > old_mid


@pytest.mark.parametrize("count", [3, 10])
def test_well_count_is_a_real_analytic_objective_lever(count):
    problem = _config()["problem"]
    problem.update(optima_count=count, roughness=0.0)
    centers = [i / (count - 1) for i in range(count)]
    for center in centers:
        assert _objective(center, problem) == pytest.approx(0.0)
    for left, right in pairwise(centers):
        assert _objective((left + right) / 2, problem) > 0


def test_weighted_robust_rough_and_boundary_forms_change_truth():
    problem = _config()["problem"]
    problem.update(optima="single", optima_count=1)
    x = 0.125
    base = _objective(x, problem)
    problem.update(objective_kind="weighted", objective_weight=0.0)
    assert _objective(x, problem) == base
    problem["objective_weight"] = 1.0
    secondary = _objective(x, problem)
    problem["objective_kind"] = "robust"
    assert _objective(x, problem) == max(base, secondary)
    problem.update(objective_kind="single", roughness=0.1)
    assert _objective(x, problem) == pytest.approx(base - 0.1)
    problem.update(roughness=0.0, optimum_location="boundary")
    assert _objective(1.0, problem) < _objective(0.73, problem)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("optima_count", 2),
        ("objective_kind", "hidden"),
        ("objective_weight", 1.1),
        ("roughness", -0.1),
        ("optimum_location", "corner"),
    ],
)
def test_bad_shape_settings_refuse(field, value):
    config = _config()
    config["problem"][field] = value
    with pytest.raises(LabRefused, match="physics_problem_assumptions"):
        physics.validate_config(config)
