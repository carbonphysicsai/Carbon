"""SCORE-PROOF-01 amendment 10: registry v9 is a small value-first family of
its own: simple legs, held-out decision outcomes, hard safety only."""

from __future__ import annotations

from pathlib import Path

from carbon.battery.value import score_tuning as st

REGISTRIES = (
    Path(__file__).resolve().parents[2]
    / "docs/development/evidence/battery-score-tuning"
)


def test_v9_is_the_small_registered_family():
    v9, _ = st.load_registry(REGISTRIES / "registry-v9.json")
    assert set(v9) == {
        "A", "R", "P", "ARP", "V3", "ARP-V3", "ENV/ARP", "ENV/ARP-V3",
        "A-Q", "G-FEAS/A-Q>@0.05",
    }  # fmt: skip
    v8, _ = st.load_registry(REGISTRIES / "registry-v8.json")
    # The controls are v8's, unchanged; v9's A weights accuracy as v8's does.
    for cid in ("A-Q", "G-FEAS/A-Q>@0.05"):
        assert v9[cid] == v8[cid]
    assert v9["A"].weights == v8["A"].weights


def test_no_q_led_rule_and_only_the_hard_safety_gate():
    v9, _ = st.load_registry(REGISTRIES / "registry-v9.json")
    for cid, c in v9.items():
        if cid in ("A-Q", "G-FEAS/A-Q>@0.05"):
            continue
        assert "q" not in c.weights
        assert all(g["measure"] == "envelope" and g["cutoff"] == 1.0 for g in c.gates)
    assert v9["ARP-V3"].weights == {"a": 0.25, "r": 0.25, "p": 0.25, "v3": 0.25}
    assert v9["ENV/ARP"].weights == v9["ARP"].weights
