"""SCORE-PROOF-01 amendment 7: two-gate candidates (registry v7) and the two
pickability criteria reported at selection. Synthetic rows only."""

from __future__ import annotations

from pathlib import Path

import pytest

from carbon.battery.value import admissibility
from carbon.battery.value import score_proof as sp
from carbon.battery.value import score_tuning as st

ROOT = Path(__file__).resolve().parents[2]
REGISTRIES = ROOT / "docs/development/evidence/battery-score-tuning"
BASES = ("A-Q", "D", "A", "CE", "SR2", "G-N", "R-G-N", "N-heavy")
FEAS = ("0.005", "0.01", "0.02", "0.05", "0.1", "1.01")
PLATE = ("0.005", "0.01", "0.02", "0.025", "0.05", "0.1", "1.01")
ENV = {"measure": "envelope", "cutoff": 1.0}


def gates_row(feasibility=0.0, plating_fa=0.0, envelope=0.0):
    return {
        "gates": {
            "near": 0.0,
            "envelope": envelope,
            "feasibility": feasibility,
            "plating_fa": plating_fa,
            "error": 0.1,
        }
    }


#: Run 5's unsafe member on the scoring set: inside the feasibility and
#: plating bands (both measures 0), outside the decision envelope.
RUN5_UNSAFE = gates_row(envelope=1.5)


@pytest.fixture(scope="module")
def v7():
    return st.load_registry(REGISTRIES / "registry-v7.json")[0]


def test_v7_keeps_every_v6_candidate_and_adds_the_two_gate_sweeps(v7):
    v6, _ = st.load_registry(REGISTRIES / "registry-v6.json")
    assert {k: v for k, v in v7.items() if k in v6} == v6
    expected = {
        *(f"G-FEAS+ENV/{b}@{c}" for b in BASES for c in FEAS),
        *(f"G-PLATE+ENV/{b}@{c}" for b in BASES for c in PLATE),
        "G-FEAS+ENV/A-Q>@0.05",
    }
    assert set(v7) - set(v6) == expected
    assert len(v6) == 150 and len(v7) == 255
    for cid in expected:
        candidate = v7[cid]
        base = cid.split("/", 1)[1].split("@")[0].rstrip(">")
        assert candidate.weights == v7[base].weights
        assert candidate.kind == v7[base].kind
        assert candidate.gates[1:] == (ENV,)
        assert candidate.gates[0] == candidate.gate
    assert v7["G-FEAS+ENV/A-Q>@0.05"].gate == {
        "measure": "feasibility",
        "cutoff": 0.05,
        "comparison": "exceeds",
    }


def test_v7_catches_run_5s_unsafe_member_that_the_one_gate_rules_miss(v7):
    two_gate = [c for c in v7 if "+ENV/" in c]
    assert two_gate
    for cid in two_gate:
        assert st.gate_verdict(v7[cid], RUN5_UNSAFE) == admissibility.FAIL, cid
    # The one-gate FEAS and PLATE rules see feasibility and plating 0: PASS.
    for cid in ("G-FEAS/A-Q>@0.05", "G-FEAS/SR2@0.01", "G-PLATE/A-Q@0.01"):
        assert st.gate_verdict(v7[cid], RUN5_UNSAFE) == admissibility.PASS
    # A member inside every band passes both gates; one outside either fails.
    rule = v7["G-FEAS+ENV/SR2@0.01"]
    assert st.gate_verdict(rule, gates_row(envelope=0.5)) == admissibility.PASS
    assert (
        st.gate_verdict(rule, gates_row(feasibility=0.02, envelope=0.5))
        == admissibility.FAIL
    )
    assert (
        st.gate_verdict(rule, {"gates": {**RUN5_UNSAFE["gates"], "envelope": None}})
        == admissibility.FAIL
    )


def test_the_unsafe_member_scores_below_every_passing_member(v7):
    legs = {
        "unsafe": {
            **RUN5_UNSAFE,
            "legs": dict.fromkeys("argmnpq", 0.9),
            "E": 0.01,
            "eligible": True,
        },
        "safe": {
            **gates_row(),
            "legs": dict.fromkeys("argmnpq", 0.1),
            "E": 0.5,
            "eligible": True,
        },
    }
    scores, verdicts = st.candidate_scores(
        v7["G-FEAS+ENV/A-Q@0.05"], legs, {"unsafe": "u", "safe": "s"}
    )
    assert verdicts == {"unsafe": admissibility.FAIL, "safe": admissibility.PASS}
    assert scores["unsafe"] < scores["safe"]


def test_gate_check_passes_a_two_gate_rule_and_names_each_gates_catching_cutoff():
    legs = {"run5": RUN5_UNSAFE}
    feas = {"measure": "feasibility", "cutoff": 0.05}
    caught = st.parse_candidate(
        {"id": "x", "weights": {"a": 1.0}, "gates": [feas, ENV]}
    )
    assert sp.gate_check(caught, legs, ["run5"]) == {"status": "PASS"}
    loose = st.parse_candidate(
        {
            "id": "y",
            "weights": {"a": 1.0},
            "gates": [feas, {"measure": "envelope", "cutoff": 9.0}],
        }
    )
    check = sp.gate_check(loose, legs, ["run5"])
    assert check["status"] == "FAIL" and check["missed"] == ["run5"]
    assert check["and_gates"] == [
        {
            "gate": {"measure": "envelope", "cutoff": 9.0},
            "catching_cutoff": {"measure": "envelope", "cutoff_at_or_below": 1.5},
        }
    ]
    one = st.parse_candidate({"id": "z", "weights": {"a": 1.0}, "gate": feas})
    assert "and_gates" not in sp.gate_check(one, legs, ["run5"])


@pytest.mark.parametrize(
    "entry",
    [
        {"id": "x", "weights": {"a": 1.0}, "gates": [ENV]},
        {"id": "x", "weights": {"a": 1.0}, "gate": ENV, "gates": [ENV, ENV]},
        {
            "id": "x",
            "weights": {"a": 1.0},
            "gates": [ENV, {"measure": "nope", "cutoff": 1}],
        },
        {"id": "x", "weights": {"a": 1.0}, "gates": ENV},
    ],
)
def test_a_malformed_gates_list_is_refused(entry):
    with pytest.raises(st.TuningError):
        st.parse_candidate(entry)


@pytest.mark.parametrize(
    "and_gates",
    [
        [],
        [{"measure": "envelope"}],
        [{"measure": "envelope", "cutoff": 1.0, "x": 1}],
        ENV,
    ],
)
def test_a_malformed_sweep_and_gates_is_refused(and_gates):
    base = st.parse_candidate({"id": "A", "weights": {"a": 1.0}})
    entry = {
        "id": "S",
        "kind": "gate_sweep",
        "measure": "feasibility",
        "grid": [0.05],
        "base": "A",
        "and_gates": and_gates,
    }
    with pytest.raises(st.TuningError):
        st.expand_sweep(entry, {"A": base})


def test_a_one_gate_candidate_is_unchanged():
    candidate = st.parse_candidate(
        {"id": "x", "weights": {"a": 1.0}, "gate": {"measure": "near", "cutoff": 2.0}}
    )
    assert candidate.gates == (candidate.gate,)
    assert st.parse_candidate({"id": "y", "weights": {"a": 1.0}}).gates == ()


def pooled(**overrides):
    r = {
        "members": 20,
        "status": "COMPLETE",
        "known_bad_in_top_half": [],
        "adversarial_in_top_half": [],
        "unsafe_ranks": {},
        "deployment": "TOP1",
        "top1_regret": 0.0,
        "value_noise_band": 0.1,
        "adversarial_divergence": [],
        "tau": 0.3,
        "tau_ci95": [0.1, 0.4],
    }
    return {**r, **overrides}


def test_both_pickability_criteria_are_computed_and_divergence_is_in_force():
    report = {
        "gate_recall_check": {},
        "candidates": {
            # The selection's case: adversarial members placed high, no divergence.
            "HIGH": {"pooled": pooled(adversarial_in_top_half=["adv"])},
            "DIVERGES": {"pooled": pooled(adversarial_divergence=["adv"])},
            "BAD": {"pooled": pooled(known_bad_in_top_half=["control"])},
        },
    }
    # PICKABLE-02: the owner's correction, selection only.
    assert sp.PICKABILITY_IN_FORCE == "divergence"
    assert sp.pickable(report, "HIGH") == (True, [])
    assert sp.pickable(report, "HIGH", criterion="placement") == (
        False,
        ["pooled: adversarial member in the top half"],
    )
    assert sp.pickable(report, "DIVERGES") == (
        False,
        ["pooled: adversarial divergence"],
    )
    assert sp.pickable(report, "DIVERGES", criterion="placement") == (True, [])
    for criterion in sp.PICKABILITY_CRITERIA:
        assert not sp.pickable(report, "BAD", criterion=criterion)[0]


def test_selection_md_lists_both_criteria_and_marks_the_one_in_force():
    from scripts.dev.battery import score_proof as script

    report = {
        "gate_recall_check": {"HIGH": {"status": "PASS"}},
        "candidates": {
            "HIGH": {"pooled": pooled(adversarial_in_top_half=["adv"])},
            "OK": {"pooled": pooled(tau=0.1)},
        },
    }
    report["pickable_by_criterion"] = {
        c: {
            cid: dict(
                zip(("pickable", "failed"), sp.pickable(report, cid, criterion=c))
            )
            for cid in report["candidates"]
        }
        for c in sp.PICKABILITY_CRITERIA
    }
    text = script.criteria_lines(report)
    assert "### placement (superseded, reported only)" in text
    assert "1 of 2 pickable" in text
    assert "### divergence (in force)" in text and "2 of 2" in text
    proposed = text.split("### divergence", 1)[1]
    assert proposed.index("**HIGH**") < proposed.index("**OK**")  # best tau first
    assert "gate recall PASS" in proposed
