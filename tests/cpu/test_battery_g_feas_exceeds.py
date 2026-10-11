"""G-FEAS's comparison at its cutoff (#961; OWNER-BATTERY-SCORE-RULE-01).

The record says a submission is ineligible when its false-feasible rate
**exceeds** 0.05. Registry v5's `G-FEAS/A-Q>@0.05` fails only above 0.05;
every earlier candidate, and the pinned `admissibility.verdict` (EV5), keep
failing at or above their cutoff, unchanged.
"""

from __future__ import annotations

from pathlib import Path

from carbon.battery.value import admissibility, score_tuning

REPOSITORY = Path(__file__).resolve().parents[2]
REGISTRIES = REPOSITORY / "docs/development/evidence/battery-score-tuning"


def row(rate):
    return {"gates": {"feasibility": rate}}


def test_at_exactly_005_the_strict_gate_passes_and_the_pinned_one_fails():
    candidates, _ = score_tuning.load_registry(REGISTRIES / "registry-v5.json")
    strict = candidates["G-FEAS/A-Q>@0.05"]
    pinned = candidates["G-FEAS/A-Q@0.05"]
    assert strict.gate == {
        "measure": "feasibility",
        "cutoff": 0.05,
        "comparison": "exceeds",
    }
    assert score_tuning.gate_verdict(strict, row(1 / 20)) == admissibility.PASS
    assert score_tuning.gate_verdict(strict, row(0.05000001)) == admissibility.FAIL
    assert score_tuning.gate_verdict(strict, row(1 / 21)) == admissibility.PASS
    assert score_tuning.gate_verdict(strict, row(None)) == admissibility.FAIL
    # Registry v4's candidate and the pinned helper are unchanged.
    assert score_tuning.gate_verdict(pinned, row(1 / 20)) == admissibility.FAIL
    assert admissibility.verdict(0.05, threshold=0.05) == admissibility.FAIL


def test_v5_keeps_every_v4_candidate_exactly():
    v4, _ = score_tuning.load_registry(REGISTRIES / "registry-v4.json")
    v5, _ = score_tuning.load_registry(REGISTRIES / "registry-v5.json")
    assert {k: v for k, v in v5.items() if k in v4} == v4
    assert set(v5) - set(v4) == {"G-FEAS/A-Q>@0.05"}
    assert all("comparison" not in (c.gate or {}) for c in v4.values())


def test_v6_keeps_every_v5_candidate_and_adds_1059s_selection_candidates():
    v5, _ = score_tuning.load_registry(REGISTRIES / "registry-v5.json")
    v6, _ = score_tuning.load_registry(REGISTRIES / "registry-v6.json")
    assert {k: v for k, v in v6.items() if k in v5} == v5
    assert len(v5) == 130 and len(v6) == 149
    grid = ("0.005", "0.01", "0.02", "0.025", "0.05", "0.1", "1.01")
    expected = {
        *(f"G-PLATE/A-Q@{c}" for c in grid),
        *(f"G-PLATE/A-Q>@{c}" for c in grid),
        "G-FEAS-T/A-Q@0.025",
        *(f"G-FEAS-T/A-Q>@{c}" for c in ("0.005", "0.01", "0.02", "0.025")),
    }
    assert set(v6) - set(v5) == expected
    at, above = v6["G-PLATE/A-Q@0.01"], v6["G-PLATE/A-Q>@0.01"]
    assert at.weights == above.weights == v6["A-Q"].weights
    rate = {"gates": {"plating_fa": 0.01}}
    assert score_tuning.gate_verdict(at, rate) == admissibility.FAIL
    assert score_tuning.gate_verdict(above, rate) == admissibility.PASS
    tight = v6["G-FEAS-T/A-Q>@0.02"]
    assert tight.gate == {
        "measure": "feasibility",
        "cutoff": 0.02,
        "comparison": "exceeds",
    }
    assert score_tuning.gate_verdict(tight, row(0.021)) == admissibility.FAIL


def test_the_score_proof_reads_registry_v6():
    from scripts.dev.battery import score_proof

    assert score_proof.REGISTRY.name == "registry-v6.json"


def test_an_unknown_comparison_is_refused():
    import pytest

    entry = {
        "id": "x",
        "kind": "gate_sweep",
        "measure": "feasibility",
        "grid": [0.05],
        "base": "A-Q",
        "comparison": "below",
    }
    with pytest.raises(score_tuning.TuningError) as refused:
        score_tuning.expand_sweep(entry, {"A-Q": score_tuning.Candidate("A-Q")})
    assert refused.value.code == "sweep_comparison"
