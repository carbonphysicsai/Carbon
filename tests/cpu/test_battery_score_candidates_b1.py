"""SR-B1: registration, building blocks on synthetic data, and the committed
result's internal consistency. The prediction bundles (about 300 MB) stay on
the operator host, so the full computation is not rerun here."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.battery.value import score_candidates_b1 as b1

REPOSITORY = Path(__file__).resolve().parents[2]
TICKET = REPOSITORY / ".agent/tickets/SR-B1_battery_score_candidates.md"
RESULT = (
    REPOSITORY / "docs/development/evidence/battery-score-candidates-b1/result.json"
)
CONTRACT = json.loads(
    (
        REPOSITORY
        / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
    ).read_text(encoding="utf-8")
)


def test_candidates_are_exactly_the_registered_ones():
    text = TICKET.read_text(encoding="utf-8")
    for name in b1.CANDIDATES:
        assert f"| {name} |" in text, name
    assert b1.G_CUTOFF == 1.0 and b1.SR2_WEIGHTS == (0.0, 0.3, 0.6, 0.1)


def _outputs(plating, peak):
    return {
        "voltage_v": [3.0] * 121,
        "temperature_c": [25.0] * 120 + [peak],
        "plating_margin_v": plating,
        "capacity_ah": [1.0] * 4,
    }


def test_proximity_leg_charges_optimism_near_the_limit_only():
    refs = {"c": {"outputs": _outputs(0.001, 44.0)}}
    exact = b1.proximity_leg(CONTRACT, {"c": _outputs(0.001, 44.0)}, ["c"], refs)
    pessimist = b1.proximity_leg(CONTRACT, {"c": _outputs(-0.002, 46.0)}, ["c"], refs)
    optimist = b1.proximity_leg(CONTRACT, {"c": _outputs(0.004, 40.0)}, ["c"], refs)
    assert exact == pytest.approx(1.0)
    assert pessimist == pytest.approx(1.0)  # pessimism is not charged
    assert optimist < 1.0


def test_stability_and_gates():
    base = {
        "r-s0": {
            "CE": 1.0,
            "SR2": 0.5,
            "P1": 0.5,
            "P2": 0.5,
            "G1": {"verdict": "PASS"},
            "G2": {"verdict": "PASS"},
        },
        "r-s1": {
            "CE": 3.0,
            "SR2": 0.7,
            "P1": 0.7,
            "P2": 0.7,
            "G1": {"verdict": "FAIL"},
            "G2": {"verdict": "PASS"},
        },
    }
    table = b1.candidate_scores(base, {"r-s0": "r", "r-s1": "r"})
    assert table["S-CE"] == {"r-s0": 2.0, "r-s1": 2.0}
    # A FAIL ranks below every passing member, even for negative scores.
    assert table["CE+G1"]["r-s0"] == 1.0
    assert table["CE+G1"]["r-s1"] < min(table["CE"].values())
    negative = {k: {**v, "CE": -v["CE"]} for k, v in base.items()}
    gated = b1.candidate_scores(negative, {"r-s0": "r", "r-s1": "r"})["CE+G1"]
    assert gated["r-s1"] < gated["r-s0"] == -1.0
    assert table["S-P1+G2"]["r-s1"] == pytest.approx(0.6)


def test_committed_result_is_internally_consistent():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    for panel in ("graphite_run5", "ev4"):
        rows = result[panel]["candidates"]
        assert set(rows) == set(b1.CANDIDATES)
        assert rows["CE"]["delta_tau_vs_CE"] == [0.0, 0.0]
        assert rows["SR2"]["delta_tau_vs_SR2"] == [0.0, 0.0]
        for name, row in rows.items():
            for key, against in (
                ("delta_tau_vs_CE", "CE"),
                ("delta_tau_vs_SR2", "SR2"),
            ):
                interval = row[key]
                progress = row[f"progress_vs_{against}"]
                assert progress == (name != against and interval[0] > 0), (panel, name)
    run5 = result["graphite_run5"]
    assert run5["members"] == 27 and run5["recipes"] == 8
    assert run5["candidates"]["CE"]["tau_one_seed"] == pytest.approx(
        -0.5455447255899809
    )
