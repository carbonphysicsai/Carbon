"""Toy controls for a miner who sees only rounded public score feedback."""

import pytest

from scripts.dev.score_lab.core import LabRefused
from scripts.dev.score_lab.feedback import add_value_outcome, climb, sweep


def _run(*, grain="aggregate", decimals=2, probes=2):
    seen = []

    def public_score(params, public_grain):
        seen.append((dict(params), public_grain))
        return (
            params["edge_bias"]
            if public_grain == "aggregate"
            else 0.4 * params["edge_bias"]
        )

    result = climb(
        public_score,
        initial={"edge_bias": 0.0},
        bounds={"edge_bias": (-1.0, 1.0)},
        step={"edge_bias": 0.25},
        grain=grain,
        decimals=decimals,
        probes_per_epoch=probes,
        epochs=4,
    )
    return result, seen


def test_feedback_gamer_hill_climbs_public_score_then_value_is_measured():
    result, seen = _run()
    assert result["calls"] == 1 + 4 * 2 == len(seen)
    assert {grain for _params, grain in seen} == {"aggregate"}
    assert result["final_parameters"]["edge_bias"] == 1.0
    assert result["final_score"] > result["initial_score"]
    measured = add_value_outcome(result, lambda params: params["edge_bias"] ** 2)
    assert measured["score_gain"] > 0
    assert measured["value_gain"] < 0  # Goodhart: worse held-out buyer loss


def test_disclosure_grain_rounding_and_probe_allowance_change_visible_gain():
    aggregate, _ = _run(grain="aggregate", decimals=2, probes=2)
    coarse, _ = _run(grain="coarse", decimals=0, probes=1)
    assert aggregate["final_score"] > aggregate["initial_score"]
    assert coarse["final_score"] == coarse["initial_score"]
    assert coarse["calls"] == 5
    assert coarse["final_parameters"] == coarse["initial_parameters"]


def test_feedback_ties_keep_prior_and_bad_inputs_fail_closed():
    tied = climb(
        lambda _params, _grain: 0.5,
        initial={"bias": 0.0},
        bounds={"bias": (-1.0, 1.0)},
        step={"bias": 0.1},
        grain="aggregate",
        decimals=1,
        probes_per_epoch=1,
        epochs=3,
    )
    assert tied["final_parameters"] == {"bias": 0.0}
    with pytest.raises(LabRefused, match="feedback_configuration"):
        climb(
            lambda _params, _grain: 1.0,
            initial={"bias": 0.0},
            bounds={"bias": (-1.0, 1.0)},
            step={"bias": 0.1},
            grain="aggregate",
            decimals=13,
            probes_per_epoch=1,
            epochs=1,
        )
    with pytest.raises(LabRefused, match="feedback_score_nonfinite"):
        climb(
            lambda _params, _grain: float("nan"),
            initial={"bias": 0.0},
            bounds={"bias": (-1.0, 1.0)},
            step={"bias": 0.1},
            grain="aggregate",
            decimals=1,
            probes_per_epoch=1,
            epochs=1,
        )


def test_sweep_accounts_for_each_disclosure_setting_and_defers_value():
    rows = sweep(
        lambda params, grain: params["bias"] * (1 if grain == "aggregate" else 0.4),
        lambda params: params["bias"] ** 2,
        initial={"bias": 0.0},
        bounds={"bias": (-1.0, 1.0)},
        step={"bias": 0.25},
        grains=["aggregate", "coarse"],
        roundings=[0, 2],
        probe_allowances=[1, 2],
        epochs=4,
    )
    assert len(rows) == 8
    assert {row["grain"] for row in rows} == {"aggregate", "coarse"}
    assert {row["calls"] for row in rows} == {5, 9}
    assert any(row["score_gain"] > 0 and row["value_gain"] < 0 for row in rows)
    assert any(row["score_gain"] == row["value_gain"] == 0 for row in rows)
