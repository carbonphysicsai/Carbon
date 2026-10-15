"""Optional synthetic error levers change predictions without changing truth."""

import copy
import json
import math
from pathlib import Path

import pytest

from scripts.dev.score_lab import physics, synthetic
from scripts.dev.score_lab.core import LabRefused

EXAMPLE = Path(__file__).parents[2] / "scripts/dev/score_lab/physics-error-example.json"
OPTIONAL = (
    "heteroscedasticity",
    "error_region",
    "cross_design_correlation",
    "tail_rate",
    "tail_size",
    "sigma_scale",
)


def _inputs():
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    member = config["population"][0]
    question = synthetic._question("S-0", 0.06, config["problem"])
    return config, member, question


def _predict(member, question, aid):
    return physics._predict(
        member,
        "S-0",
        aid,
        question,
        base_question=question,
        horizon=0.0,
        perturbation=0.0,
    )


def test_optional_defaults_reproduce_legacy_toy_panel_exactly():
    config, _, _ = _inputs()
    legacy = copy.deepcopy(config)
    for key in OPTIONAL:
        del legacy["population"][0][key]
    current_panel, legacy_panel = physics.build(config), physics.build(legacy)
    assert (
        current_panel["assumption"]["physics_config_sha256"]
        != legacy_panel["assumption"]["physics_config_sha256"]
    )
    del current_panel["assumption"]["physics_config_sha256"]
    del legacy_panel["assumption"]["physics_config_sha256"]
    assert current_panel == legacy_panel


def test_cross_design_correlation_is_shared_within_question():
    _, member, question = _inputs()
    member.update(
        noise=0.1,
        transfer=1.0,
        rollout_drift=0.0,
        robustness=0.0,
        cross_design_correlation=1.0,
    )
    first, second = list(question["actions"])[:2]
    shared = [
        _predict(member, question, aid)["objective"]
        - question["actions"][aid]["objective"]
        for aid in (first, second)
    ]
    assert shared[0] == pytest.approx(shared[1])
    member["cross_design_correlation"] = 0.0
    independent = [
        _predict(member, question, aid)["objective"]
        - question["actions"][aid]["objective"]
        for aid in (first, second)
    ]
    assert not math.isclose(independent[0], independent[1], abs_tol=1e-9)


def test_locality_tails_and_uncertainty_scale_have_separate_effects():
    _, member, question = _inputs()
    member.update(noise=0.05, transfer=1.0, rollout_drift=0.0, robustness=0.0)
    actions = question["actions"]
    boundary = sorted(
        actions, key=lambda aid: min(abs(v) for v in actions[aid]["margins"])
    )
    member.update(heteroscedasticity=2.0, error_region="boundary")
    assert (
        _predict(member, question, boundary[0])["sigma"]
        > _predict(member, question, boundary[-1])["sigma"]
    )
    optimum = sorted(actions, key=lambda aid: actions[aid]["objective"])
    member["error_region"] = "optimum"
    assert (
        _predict(member, question, optimum[0])["sigma"]
        > _predict(member, question, optimum[-1])["sigma"]
    )

    member.update(noise=0.0, heteroscedasticity=0.0, tail_rate=0.0)
    aid = optimum[0]
    ordinary = _predict(member, question, aid)
    member.update(tail_rate=1.0, tail_size=0.4)
    tailed = _predict(member, question, aid)
    assert abs(tailed["objective"] - ordinary["objective"]) == pytest.approx(0.4)
    assert abs(tailed["margins"][0] - ordinary["margins"][0]) == pytest.approx(0.4)

    member.update(noise=0.05, tail_rate=0.0, sigma_scale=1.0)
    calibrated = _predict(member, question, aid)
    member["sigma_scale"] = 2.0
    wider = _predict(member, question, aid)
    assert wider["objective"] == calibrated["objective"]
    assert wider["margins"] == calibrated["margins"]
    assert wider["sigma"] == 2 * calibrated["sigma"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("error_region", "unknown"),
        ("heteroscedasticity", -1),
        ("cross_design_correlation", 1.1),
        ("tail_rate", 1.1),
        ("tail_size", -0.1),
        ("sigma_scale", 0),
    ],
)
def test_invalid_error_settings_refuse(key, value):
    config, _, _ = _inputs()
    config["population"][0][key] = value
    with pytest.raises(LabRefused, match="physics_member_traits"):
        physics.validate_config(config)
