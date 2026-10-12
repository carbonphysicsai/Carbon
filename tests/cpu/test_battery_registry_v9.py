"""SCORE-PROOF-01 amendment 10: registry v9 keeps v8 and adds the value-first
family, with accuracy only as a tiebreak."""

from __future__ import annotations

from pathlib import Path

import pytest

from carbon.battery.value import score_tuning as st

REGISTRIES = (
    Path(__file__).resolve().parents[2]
    / "docs/development/evidence/battery-score-tuning"
)
GRID = ("0.005", "0.01", "0.02", "0.05", "1.01")


def test_v9_keeps_every_v8_candidate_and_adds_the_value_first_family():
    v8, _ = st.load_registry(REGISTRIES / "registry-v8.json")
    v9, _ = st.load_registry(REGISTRIES / "registry-v9.json")
    assert {k: v for k, v in v9.items() if k in v8} == v8
    assert set(v9) - set(v8) == {
        "VERIFY-R-k3+tb-a",
        "D+tb-a",
        *(f"G-FEAS+ENV/VERIFY-R-k3+tb-a@{c}" for c in GRID),
        *(f"G-FEAS+ENV/D+tb-a@{c}" for c in GRID),
    }
    assert len(v9) == len(v8) + 12


@pytest.mark.parametrize("rule,lead", [("VERIFY-R-k3+tb-a", "v3"), ("D+tb-a", "q")])
def test_accuracy_only_breaks_near_ties(rule, lead):
    v9, _ = st.load_registry(REGISTRIES / "registry-v9.json")
    c = v9[rule]
    assert c.weights == {lead: 0.99, "a": 0.01}

    def score(lead_value, a):
        return st.score_member(
            c, {"eligible": True, "E": 0.1, "legs": {lead: lead_value, "a": a}}
        )

    # A better lead leg wins whatever the accuracy; equal leads go to accuracy.
    assert score(0.80, 0.10) > score(0.78, 0.99)
    assert score(0.80, 0.90) > score(0.80, 0.50)
    gated = v9[f"G-FEAS+ENV/{rule}@0.01"]
    assert gated.weights == c.weights
    assert [g["measure"] for g in gated.gates] == ["feasibility", "envelope"]
