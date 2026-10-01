"""The score-value divergence detector fires as an emitted condition.

OWNER-CHALLENGE-ADMISSION-01 (amended 2026-10-01) §3.2-§3.4 and §4.2. The
worked example is EV2's boundary-optimist control; specimens show the detector
both firing and staying quiet, so a silent run is evidence, not an accident.
"""

import copy
import json
from pathlib import Path

from carbon.battery.value import divergence as d

REPOSITORY = Path(__file__).resolve().parents[2]
EVIDENCE = REPOSITORY / "docs/development/evidence"


def results(name):
    return json.loads((EVIDENCE / name / "results.json").read_text())


def fired(conditions, member, split=None):
    return [
        c
        for c in conditions
        if c["member"] == member
        and c["condition"] == "SCORE_VALUE_DIVERGENCE"
        and (split is None or c["split"] == split)
    ]


def test_ev2_boundary_optimist_is_the_worked_example():
    ev2 = results("ev2-2026-10-01")
    conditions = d.conditions(ev2)
    real = {
        m
        for m, row in ev2["summary"]["members"].items()
        if row["kind"] == "RECONSTRUCTED" and row["eligible"] is True
    }
    assert len(real) == 14
    for split in d.SPLITS:
        (hit,) = fired(conditions, "control-boundary_optimist", split)
        # It scores at or above every eligible real member while deciding
        # worse than each of them by more than the seed noise band.
        assert real <= set(hit["scored_at_or_above"])
        assert hit["review_state"] == d.REVIEW_STATE


def test_a_member_that_decides_best_never_fires():
    conditions = d.conditions(results("ev2-2026-10-01"))
    assert fired(conditions, "control-oracle") == []


def test_ineligible_members_emit_a_gate_anomaly():
    conditions = d.conditions(results("ev2-2026-10-01"))
    anomalies = [c["member"] for c in conditions if c["condition"] == "GATE_ANOMALY"]
    assert anomalies == ["mlp_raw-s0"]


def synthetic(scores, losses, spread=0.0):
    """A minimal result: score order and loss order chosen by the test."""
    members = {
        m: {
            "kind": "RECONSTRUCTED",
            "eligible": True,
            "loss_development": losses[m],
            "loss_verification": losses[m],
        }
        for m in scores
    }
    return {
        "schema": "carbon.engineering-value-results.v1",
        "summary": {"members": members},
        "rule_scores": {m: {d.DECIDING_RULE: s} for m, s in scores.items()},
        "seed_variation": {
            "r": {
                s: {"max": spread, "min": 0.0, "mean": spread / 2, "seeds": 2}
                for s in d.SPLITS
            }
        },
    }


def test_agreeing_score_and_value_emit_nothing_and_a_flip_fires():
    agree = synthetic({"a": 3.0, "b": 2.0, "c": 1.0}, {"a": 0.0, "b": 1.0, "c": 2.0})
    assert d.conditions(agree) == []
    flipped = copy.deepcopy(agree)
    flipped["rule_scores"]["c"][d.DECIDING_RULE] = 4.0
    hits = fired(d.conditions(flipped), "c")
    assert [h["split"] for h in hits] == list(d.SPLITS)
    assert all(h["scored_at_or_above"] == ["a", "b"] for h in hits)


def test_a_gap_inside_the_seed_noise_band_does_not_fire():
    within = synthetic({"a": 1.0, "b": 2.0}, {"a": 0.0, "b": 0.5}, spread=1.0)
    assert d.conditions(within) == []
    beyond = synthetic({"a": 1.0, "b": 2.0}, {"a": 0.0, "b": 1.5}, spread=1.0)
    assert fired(d.conditions(beyond), "b")


def test_noise_bands_are_derived_from_retained_seed_repeats():
    ev2 = results("ev2-2026-10-01")
    spreads = [
        row["verification"]["max"] - row["verification"]["min"]
        for row in ev2["seed_variation"].values()
        if row["verification"]["seeds"] >= 2
    ]
    assert d.loss_noise_band(ev2, "verification") == max(spreads)
    tau = d.tau_noise_band(ev2)
    assert tau["panels"] == 24  # deeponet 2 x mlp 3 x mlp_half 2 x mlp_localized 2
    assert tau["band"] == tau["tau_max"] - tau["tau_min"]
    assert abs(tau["band"] - 0.2598507678293194) < 1e-12


def test_retained_condition_files_are_what_the_detector_emits():
    base = EVIDENCE / "admission-pressure-2026-10-01"
    for name, source in (("ev1", "ev1-2026-09-25"), ("ev2", "ev2-2026-10-01")):
        retained = json.loads((base / f"{name}-conditions.json").read_text())
        assert retained["conditions"] == d.conditions(results(source))
        assert retained["tau_noise_band"] == d.tau_noise_band(results(source))
