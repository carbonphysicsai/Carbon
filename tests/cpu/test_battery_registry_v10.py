"""Registry v10: a pre-registered contingency, scored only if no v9 rule is
pickable. Its leg v3s and gate measure sign are registrable now and fail
closed (withheld, never scored) until a panel computes them."""

from __future__ import annotations

from pathlib import Path

from carbon.battery.value import score_tuning as st

REGISTRIES = (
    Path(__file__).resolve().parents[2]
    / "docs/development/evidence/battery-score-tuning"
)


def test_v10_is_the_small_contingency_family_scored_only_after_v9():
    import json

    v10, _ = st.load_registry(REGISTRIES / "registry-v10.json")
    assert set(v10) == {
        "V3S", "ARP-V3S", "ENV/ARP-V3S", "SIGN/V3S", "SIGN/ARP-V3S",
        "SIGN+ENV/ARP-V3S", "A-Q", "G-FEAS/A-Q>@0.05",
    }  # fmt: skip
    v9, _ = st.load_registry(REGISTRIES / "registry-v9.json")
    for cid in ("A-Q", "G-FEAS/A-Q>@0.05"):
        assert v10[cid] == v9[cid]
    for cid, c in v10.items():
        if cid in ("A-Q", "G-FEAS/A-Q>@0.05"):
            continue
        assert "v3s" in c.weights and "q" not in c.weights
        assert {g["measure"] for g in (c.gates or (c.gate,)) if g} <= {
            "envelope",
            "sign",
        }
    raw = json.loads((REGISTRIES / "registry-v10.json").read_text())
    assert "ONLY IF no v9 rule is pickable" in raw["order"]
    assert "PICKABLE-02" in raw["pickability"] and "unchanged" in raw["pickability"]


def row(gates=None, **legs):
    return {
        "eligible": True,
        "E": 0.1,
        "legs": {"a": 0.5, "r": 0.5, "p": 0.5, **legs},
        "gates": {"envelope": 0.0, **(gates or {})},
    }


def test_an_uncomputed_leg_or_measure_withholds_never_scores():
    v10, _ = st.load_registry(REGISTRIES / "registry-v10.json")
    v9, _ = st.load_registry(REGISTRIES / "registry-v9.json")
    # No v3s leg and no sign measure on this panel: every v10 rule withheld.
    for cid in ("V3S", "ARP-V3S", "ENV/ARP-V3S", "SIGN/ARP-V3S", "SIGN+ENV/ARP-V3S"):
        assert st.score_member(v10[cid], row()) is None, cid
    # The sign gate alone withholds, even with v3s present.
    assert st.score_member(v10["SIGN/ARP-V3S"], row(v3s=0.5)) is None
    assert st.score_member(v10["ARP-V3S"], row(v3s=0.5)) is not None
    measured = row({"sign": 0.0}, v3s=0.5)
    assert st.score_member(v10["SIGN+ENV/ARP-V3S"], measured) is not None
    assert st.gate_verdict(v10["SIGN/ARP-V3S"], row({"sign": 0.01}, v3s=0.5)) == "FAIL"
    assert st.gate_verdict(v10["SIGN/ARP-V3S"], measured) == "PASS"
    # v9's rules score exactly as before on a panel without the new keys.
    assert st.score_member(v9["ARP"], row()) is not None
    assert st.score_member(v9["ENV/ARP"], row()) is not None
