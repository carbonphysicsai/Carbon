"""SCORE-CEILING-01: the τ-ceiling line score_proof prints (synthetic losses)."""

from __future__ import annotations

import numpy as np

from carbon.battery.value import score_proof as sp


def losses(members, questions, member_sd, noise_sd, seed=0):
    rng = np.random.default_rng(seed)
    skill = rng.normal(0, member_sd, size=(members, 1))
    return skill + rng.normal(0, noise_sd, size=(members, questions))


def test_a_consistent_value_has_a_high_ceiling_and_noise_has_none():
    strong = sp.value_ceiling(losses(80, 24, 1.0, 0.5))
    noise = sp.value_ceiling(losses(80, 24, 0.0, 1.0))
    assert strong["status"] == noise["status"] == "MEASURED"
    assert strong["tau_ceiling"] > 0.85 and strong["reliability"] > 0.95
    assert noise["tau_ceiling"] < 0.35
    lo, hi = strong["tau_ceiling_ci95"]
    assert lo <= strong["tau_ceiling"] <= hi


def test_more_questions_raise_the_ceiling():
    few = sp.value_ceiling(losses(80, 6, 0.5, 1.0, seed=1))
    many = sp.value_ceiling(losses(80, 60, 0.5, 1.0, seed=1))
    assert many["tau_ceiling"] > few["tau_ceiling"]


def test_constant_questions_are_left_out_and_too_few_is_not_measurable():
    L = losses(30, 4, 1.0, 0.5)
    L[:, 1] = 2.0  # every member scores the same here
    c = sp.value_ceiling(L)
    assert c["resolved_questions"] == 4 and c["informative_questions"] == 3
    one = np.zeros((30, 3))
    one[:, 0] = np.arange(30)
    assert sp.value_ceiling(one)["status"] == "NOT_MEASURABLE"
    assert sp.value_ceiling([[1.0, 2.0]])["status"] == "NOT_MEASURABLE"


def test_the_observed_tau_is_reported_as_a_share_of_the_ceiling():
    c = sp.value_ceiling(losses(80, 24, 1.0, 0.5), observed_tau=0.3)
    assert c["observed_tau"] == 0.3
    assert abs(c["share_of_ceiling"] - 0.3 / c["tau_ceiling"]) < 1e-12
    # Deterministic: the same losses give the same interval.
    again = sp.value_ceiling(losses(80, 24, 1.0, 0.5), observed_tau=0.3)
    assert again == c


def test_the_line_prints_the_ceiling_and_the_share():
    from scripts.dev.battery import score_proof as script

    c = {
        "rule": "G-FEAS/A-Q>@0.05",
        **sp.value_ceiling(losses(80, 24, 1.0, 0.5), observed_tau=0.3),
    }
    line = script.ceiling_line(c)
    assert line.startswith(
        "**τ ceiling (SCORE-CEILING-01):** 24 informative of 24 resolved"
    )
    assert "% of the ceiling" in line and "G-FEAS/A-Q>@0.05" in line
    assert "not measurable" in script.ceiling_line(
        {"status": "NOT_MEASURABLE", "resolved_questions": 1}
    )
