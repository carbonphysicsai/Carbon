"""The near-limit optimism gate (TRACK-B-STUCK-01 review outcome).

The claims tested: with no cutoff the gate is inactive and changes nothing;
with a cutoff, a model at or above it is inadmissible and scores 0, so
ranking cannot compensate; an unmeasured model fails a set gate; the
shipped cutoff is OWNER-GATE-CUTOFF-01's 2.0 bands; and on the retained
evidence it fails the boundary optimist, passes the oracle, fails fewer than
half the real members, and fails ones that decide worse than those it passes.
"""

import json
from pathlib import Path

from carbon.battery.value import admissibility as gate

REPO = Path(__file__).resolve().parents[2]


def test_the_shipped_cutoff_is_the_recorded_one(monkeypatch):
    assert gate.THRESHOLD_BANDS == 2.0
    assert gate.verdict(2.0) == gate.FAIL and gate.verdict(1.99) == gate.PASS
    # Specimen: with no cutoff the gate is inactive and changes nothing.
    monkeypatch.setattr(gate, "THRESHOLD_BANDS", None)
    assert gate.verdict(9.9) == gate.INACTIVE
    assert gate.gated(0.8, 9.9) == 0.8


def test_a_set_cutoff_fails_at_or_above_it_and_zeroes_the_score():
    assert gate.verdict(1.0, threshold=2.0) == gate.PASS
    assert gate.verdict(2.0, threshold=2.0) == gate.FAIL
    assert gate.gated(0.95, 2.5, threshold=2.0) == 0.0
    assert gate.gated(0.95, 1.5, threshold=2.0) == 0.95


def test_an_unmeasured_model_fails_a_set_gate():
    assert gate.verdict(None, threshold=2.0) == gate.FAIL


def test_near_optimism_is_srs_measure_over_the_important_region():
    contract = json.loads(
        (
            REPO
            / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
        ).read_text()
    )
    band = contract["reference"]["uncertainty"]["bands"]["plating_margin_v"]

    def outputs(margin):
        return {
            "voltage_v": [3.5] * 121,
            "temperature_c": [25.0] * 121,
            "plating_margin_v": margin,
            "capacity_ah": [4.9] * 4,
        }

    refs = {
        "near": {"outputs": outputs(0.001), "diagnostics": {"t_max_c": 30.0}},
        "far": {"outputs": outputs(0.05), "diagnostics": {"t_max_c": 30.0}},
    }
    predictions = {"near": outputs(0.001 + 4 * band), "far": outputs(0.05 + 40 * band)}
    # Only the near case counts; over two constraints, 4 bands average to 2.
    assert (
        abs(gate.near_optimism(contract, predictions, ["near", "far"], refs) - 2.0)
        < 1e-9
    )


def test_the_retained_evidence_matches_what_it_reports():
    report = json.loads(
        (
            REPO
            / "docs/development/evidence/admissibility-optimism-2026-10-03/optimism.json"
        ).read_text()
    )
    assert report["threshold_bands"] == gate.THRESHOLD_BANDS
    assert report["state"] == "ACTIVE"
    for dataset in report["datasets"].values():
        at = dataset["at_cutoff"]
        assert at["controls"]["control-boundary_optimist"] == gate.FAIL
        assert at["controls"]["control-oracle"] == gate.PASS
        assert len(at["real_members_failed"]) * 2 < dataset["real_members"]
        assert (
            at["mean_verification_loss_failed"] > at["mean_verification_loss_passed"]
        )
    ev4 = report["datasets"]["ev4-2026-10-01"]
    optimist = ev4["at_control_levels"]["control-boundary_optimist"]
    assert ev4["real_members"] == 99
    assert ev4["controls"]["control-boundary_optimist"] > ev4["real_median"]
    assert optimist["real_members_at_or_above"] == sum(
        v >= optimist["level_bands"] for v in ev4["real"].values()
    )
    assert (
        optimist["mean_verification_loss_at_or_above"]
        > optimist["mean_verification_loss_below"]
    )
