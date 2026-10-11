"""SCORE-PROOF-01: the score proof's metrics on a synthetic panel (no
predictions, references or tuning data)."""

from __future__ import annotations

import random

import numpy as np
import pytest

from carbon.battery.value import admissibility
from carbon.battery.value import score_proof as sp
from carbon.battery.value import score_tuning as st
from carbon.design_search import score_value


def row(error, *, gate=0.0, legs=None):
    return {
        "eligible": True,
        "E": error,
        "legs": legs or {"a": 0.5, "r": 0.5, "g": 0.5, "m": 0.5, "n": 0.5, "p": 0.5, "q": None},
        "gates": {"near": gate, "envelope": gate, "feasibility": 0.0, "plating_fa": 0.0, "error": error},
    }  # fmt: skip


def registry():
    entries = [
        {"id": "CE", "kind": "deciding"},
        {
            "id": "CE+near1",
            "kind": "deciding",
            "gate": {"measure": "near", "cutoff": 1.0},
        },
        {"id": "INVERTED", "weights": {"a": 1.0}},
    ]
    return {e["id"]: st.parse_candidate(e) for e in entries}, {"commit": "fixture"}


def panel():
    """Six recipes, two seeds each: value tracks error, except the gamed
    member (low error, bad value) and the unsafe one (gate measure high)."""
    legs, values, recipe_of = {}, {}, {}
    for r in range(6):
        for s in range(2):
            name = f"r{r}-s{s}"
            legs[name] = row(0.1 * (r + 1) + 0.01 * s, legs={
                "a": 1.0 - 0.1 * r, "r": 0.5, "g": 0.5, "m": 0.5, "n": 0.5, "p": 0.5, "q": None})  # fmt: skip
            values[name] = 1.0 * (r + 1) + 0.05 * s
            recipe_of[name] = f"r{r}"
    legs["gamed-s0"], values["gamed-s0"], recipe_of["gamed-s0"] = (
        row(0.01),
        9.0,
        "gamed",
    )
    legs["unsafe-s0"], values["unsafe-s0"] = row(0.05, gate=5.0), 8.0
    recipe_of["unsafe-s0"] = "unsafe"
    legs["control-bad"], values["control-bad"] = row(0.02), 10.0
    recipe_of["control-bad"] = "control-bad"
    levels = {m: (1 if m.startswith("r5") else 0) for m in legs}
    levels["control-bad"] = None
    return legs, values, recipe_of, levels


def test_the_vectorized_tau_is_the_reference_tau():
    rng = random.Random(3)
    for _ in range(20):
        x = [rng.choice((0, 1, 2, 3)) for _ in range(15)]
        y = [rng.choice((0, 1, 2)) for _ in range(15)]
        ref = score_value.kendall_tau_b(x, y)
        got = sp.tau_b(np.asarray(x, float), np.asarray(y, float))
        assert (ref is None and got is None) or got == pytest.approx(ref)


def test_the_proof_reports_every_metric_per_level_and_pooled():
    legs, values, recipe_of, levels = panel()
    report = sp.prove(
        registry(),
        legs,
        values,
        recipe_of,
        levels,
        known_bad=["control-bad"],
        adversarial=["gamed-s0"],
        unsafe=["unsafe-s0"],
        n_bootstrap=200,
    )
    assert set(report["levels"]) == {"L0", "L1", "pooled"}
    # The level-agnostic control joins every level's pool.
    assert report["levels"]["L1"] == 3 and report["levels"]["pooled"] == 15
    ce = report["candidates"]["CE"]["pooled"]
    # -E ranks the gamed member and the bad control on top: the proof says so.
    assert ce["known_bad_in_top_half"] == ["control-bad"]
    assert ce["adversarial_in_top_half"] == ["gamed-s0"]
    assert ce["adversarial_divergence"]["gamed-s0"] > 0
    # The gamed member and the bad control are probes, never deployed: top-1
    # is the best-scoring real recipe, here the unsafe one (value 8).
    assert ce["primary_members"] == 13 and ce["deployment"] == "TOP1"
    assert ce["top1_regret"] == pytest.approx(8.0 - 1.0)
    assert ce["bootstrap"]["undefined_fraction"] == 0.0
    assert set(ce["tau_sensitivity"]) == {"recipe_only", "question_only"}
    assert ce["ties"]["usable_members"] == 13
    assert ce["gate_recall_unsafe"] is None  # no gate
    lo, hi = ce["tau_ci95"]
    assert lo <= ce["tau"] <= hi
    assert ce["delta_tau_vs_rule_in_force_ci95"] == [0.0, 0.0]
    gated = report["candidates"]["CE+near1"]["pooled"]
    assert gated["gate_recall_unsafe"] == 1.0
    assert gated["unsafe_ranks"]["unsafe-s0"][0] == 15  # a failure ranks last
    assert report["targets"]["gate_recall_unsafe"] == 1.0
    assert report["threshold"].startswith("HUMAN_INPUT")


def test_fold_stability_comes_from_scenario_and_case_folds():
    legs, values, recipe_of, levels = panel()
    decisions = {
        m: {
            f"s{k}": {"split": "development", "outcome": {"decision_loss": values[m] + k, "kind": "OK"}}
            for k in range(10)
        }
        for m in legs
    }  # fmt: skip
    report = sp.prove(
        registry(),
        legs,
        values,
        recipe_of,
        levels,
        results={"decisions": decisions},
        fold_legs=[legs, legs],
        ids=["CE"],
        folds=5,
        n_bootstrap=50,
    )
    folds = report["candidates"]["CE"]["pooled"]["fold_stability"]
    assert len(folds["scenario_folds"]["values"]) == 5
    assert folds["case_folds"]["sd"] == 0.0  # identical folds: no spread


def test_an_unregistered_candidate_is_refused():
    legs, values, recipe_of, levels = panel()
    with pytest.raises(st.TuningError):
        sp.prove(registry(), legs, values, recipe_of, levels, ids=["NEW"])


def test_a_gate_failure_counts_toward_recall():
    candidate = registry()[0]["CE+near1"]
    assert st.gate_verdict(candidate, row(0.1, gate=5.0)) == admissibility.FAIL
    assert st.gate_verdict(candidate, row(0.1, gate=0.0)) == admissibility.PASS


def test_a_rule_whose_legs_are_missing_is_withheld_not_ranked():
    legs, values, recipe_of, levels = panel()
    candidates, identity = registry()
    candidates["Q"] = st.parse_candidate(
        {"id": "Q", "weights": {"q": 1.0}, "gate": {"measure": "near", "cutoff": 1.0}}
    )
    report = sp.prove(
        (candidates, identity), legs, values, recipe_of, levels,
        unsafe=["unsafe-s0"], ids=["Q"], n_bootstrap=20,
    )  # fmt: skip
    q = report["candidates"]["Q"]["pooled"]
    # Every q leg is missing: only the gate's failure would carry a score.
    assert q["status"] == "INCOMPLETE_LEGS" and q["unscored"] == 15
    assert "tau" not in q and q["gate_recall_unsafe"] == 1.0
    assert report["candidates"]["CE"]["pooled"]["status"] == "COMPLETE"


def test_a_gate_that_misses_an_unsafe_member_fails_and_names_the_catching_cutoff():
    legs, values, recipe_of, levels = panel()
    candidates, identity = registry()
    candidates["CE+near9"] = st.parse_candidate(
        {
            "id": "CE+near9",
            "kind": "deciding",
            "gate": {"measure": "near", "cutoff": 9.0},
        }
    )
    report = sp.prove(
        (candidates, identity), legs, values, recipe_of, levels,
        unsafe=["unsafe-s0"], n_bootstrap=20,
    )  # fmt: skip
    checks = report["gate_recall_check"]
    assert checks["CE"] == {"status": "NO_GATE"}
    assert checks["CE+near1"] == {"status": "PASS"}
    missed = checks["CE+near9"]
    assert missed["status"] == "FAIL" and missed["missed"] == ["unsafe-s0"]
    # The unsafe member measures 5.0: any cutoff at or below it would catch it.
    assert missed["catching_cutoff"] == {"measure": "near", "cutoff_at_or_below": 5.0}
    exceeds = sp.catching_cutoff(
        {"measure": "feasibility", "comparison": "exceeds"}, [0.03, None]
    )
    assert exceeds == {"measure": "feasibility", "cutoff_below": 0.03}


def split_doc():
    return {"salt": "fixture-salt", "minimum_recipes": 3, "minimum_level_members": 3}


def test_the_split_is_registered_disjoint_and_keeps_seeds_and_anchors_together():
    legs, _values, recipe_of, levels = panel()
    split = split_doc()
    cases = [f"case-{i}" for i in range(200)]
    selection = sp.split_cases(split, cases, sp.SELECTION)
    confirmation = sp.split_cases(split, cases, sp.CONFIRMATION)
    assert set(selection).isdisjoint(confirmation)
    assert sorted(selection + confirmation) == sorted(cases)
    assert 60 < len(selection) < 140  # roughly half, by the registered hash
    anchors = {"control-bad", "gamed-s0", "unsafe-s0"}
    picked = {
        phase: sp.split_members(split, list(legs), recipe_of, levels, anchors, phase)
        for phase in (sp.SELECTION, sp.CONFIRMATION)
    }
    (sel, split_levels), (con, _) = picked[sp.SELECTION], picked[sp.CONFIRMATION]
    assert split_levels == [0]  # level 1 has one recipe: all its members kept
    assert anchors <= set(sel) & set(con)
    assert {"r5-s0", "r5-s1"} <= set(sel) & set(con)
    for r in range(5):  # a recipe's seeds stay on one side
        assert ({f"r{r}-s0", f"r{r}-s1"} <= set(sel)) != (
            {f"r{r}-s0", f"r{r}-s1"} <= set(con)
        )


def test_confirmation_gives_a_verdict_naming_each_failed_criterion():
    legs, values, recipe_of, levels = panel()
    report = sp.prove(
        registry(), legs, values, recipe_of, levels,
        known_bad=["control-bad"], adversarial=["gamed-s0"], unsafe=["unsafe-s0"],
        ids=["CE"], n_bootstrap=50,
    )  # fmt: skip
    verdict = sp.verdict(report, "CE", minimum_level_members=10)
    assert verdict["verdict"] == sp.UNPROVEN
    assert "pooled: known-bad member in the top half" in verdict["failed"]
    assert "pooled: adversarial divergence" in verdict["failed"]
    assert not any(f.startswith("L1:") for f in verdict["failed"])  # too few members


def test_a_gate_that_fails_every_real_recipe_deploys_nothing():
    legs, values, recipe_of, levels = panel()
    candidates, identity = registry()
    candidates["CE+near0"] = st.parse_candidate(
        {
            "id": "CE+near0",
            "kind": "deciding",
            "gate": {"measure": "near", "cutoff": 0.0},
        }
    )
    report = sp.prove(
        (candidates, identity), legs, values, recipe_of, levels,
        ids=["CE+near0"], n_bootstrap=20,
    )  # fmt: skip
    pooled = report["candidates"]["CE+near0"]["pooled"]
    assert pooled["deployment"] == "NONE_ELIGIBLE" and pooled["top1_regret"] is None


def test_the_crossed_bootstrap_resamples_questions_as_well_as_recipes():
    scores = {f"m{i}": float(i) for i in range(8)}
    recipe_of = {m: m for m in scores}
    losses = {f"m{i}": [8 - i, 8 - i + (i % 2)] for i in range(8)}
    out = sp.bootstrap(scores, scores, losses, recipe_of, list(scores), n=200)
    assert out["questions"] == 2 and out["joint"][1] <= 1.0
    assert out["delta_joint"] == [0.0, 0.0]  # the same rule against itself
    assert out["question_only"] is not None and out["recipe_only"] is not None
