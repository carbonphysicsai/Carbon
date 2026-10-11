"""SCORE-VALUE-ALIGNMENT-01: committed evidence and toy report logic only."""

import math

import pytest

from scripts.dev.battery import score_value_alignment_report as report


def test_one_seed_replays_recorded_v2_and_keeps_v3_unmeasured():
    rows = report.audit(draws=12)["panels"]
    one_seed = next(
        row
        for row in rows
        if row["panel"] == "graphite-run5-q1" and row["split"] == "one_seed"
    )
    assert one_seed["score_rule"] == "v2_public_PRACTICE"
    assert one_seed["metrics"]["tau"] == pytest.approx(-0.47280542884465016)
    assert one_seed["metrics"]["rho"] == pytest.approx(-0.5389318178609666)
    assert len(one_seed["divergent_members_v2"]) == 6
    assert one_seed["v3"]["status"] == "UNCOMPUTABLE_FROM_COMMITTED_PANEL"
    assert one_seed["v3"]["tau"] is None
    assert set(one_seed["v3"]["term_contributions"]) == {
        "a",
        "q",
        "G-FEAS@0.05",
    }


def test_historical_ev_panels_are_not_relabelled_as_v2():
    rows = report.audit(draws=12)["panels"]
    ev = [row for row in rows if row["panel"].startswith("ev")]
    assert len(ev) == 4
    assert all(row["score_rule"] == "control-exam-v1_not_v2" for row in ev)
    assert all(row["v2"]["tau"] is None for row in ev)
    assert all(row["v3"]["rho"] is None for row in ev)


def test_cluster_bootstrap_is_deterministic_and_retains_seed_group():
    groups = {
        "recipe-a": [(0.8, 0.1), (0.7, 0.2)],
        "recipe-b": [(0.4, 0.5), (0.3, 0.6)],
        "recipe-c": [(0.2, 0.7), (0.1, 0.8)],
    }
    first = report._bootstrap(groups, seed=7, draws=50)
    assert first == report._bootstrap(groups, seed=7, draws=50)
    assert first["tau"]["defined_draws"] == 50
    assert math.isfinite(first["tau"]["low"])
    assert first["tau"]["low"] <= first["tau"]["high"]


def test_no_negative_or_empty_bootstrap():
    with pytest.raises(ValueError, match="draws_must_be_positive"):
        report.audit(draws=0)
