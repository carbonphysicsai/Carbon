"""The battery score-tuning harness: known-answer fixtures (no real data)."""

from __future__ import annotations

import json
import subprocess

import pytest

from carbon.battery.value import score_tuning as st

SCEN = ("D1", "D2", "D3")


def _legs(n=6):
    """Members r0..r5 (two seeds each of three recipes). Leg `a` tracks decision
    quality; the deciding rule (−E) prefers the worst decider, `r5`."""
    legs, values, recipe_of = {}, {}, {}
    for i in range(n):
        m = f"rec{i // 2}-s{i % 2}"
        quality = 1.0 - i / (2 * n)  # higher is better
        legs[m] = {
            "eligible": True,
            "E": 0.1 * (n - i),  # −E is best for the last member
            "legs": {
                "a": quality,
                "r": 0.5,
                "g": 0.5,
                "m": 0.5,
                "n": 0.5,
                "p": 0.5,
            },
            "gates": {"near": 0.5 if i < n - 1 else 3.0, "envelope": 0.5},
        }
        values[m] = float(i)  # decision loss, lower is better
        recipe_of[m] = f"rec{i // 2}"
    return legs, values, recipe_of


def _outcomes(members, unsafe):
    return {
        m: {s: (st.INFEASIBLE if m in unsafe else "SELECTED_FEASIBLE") for s in SCEN}
        for m in members
    }


REGISTRY = {
    "schema": st.REGISTRY_SCHEMA,
    "candidates": [
        {"id": "CE", "kind": "deciding", "basis": "the deciding rule"},
        {"id": "A", "weights": {"a": 1.0}, "basis": "accuracy only"},
        {
            "id": "CE+gate",
            "kind": "deciding",
            "gate": {"measure": "near", "cutoff": 2.0},
            "basis": "deciding plus the gate",
        },
    ],
}


def _registry(tmp_path, document=REGISTRY, commit=True):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(document))
    if commit:
        subprocess.run(["git", "-C", str(tmp_path), "add", "registry.json"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(tmp_path),
                "-c",
                "user.email=t@t",
                "-c",
                "user.name=t",
                "commit",
                "-qm",
                "register",
            ],
            check=True,
        )
    return path


def test_registration_must_be_committed_before_computing(tmp_path):
    path = _registry(tmp_path, commit=False)
    with pytest.raises(st.TuningError, match="registry_not_committed"):
        st.load_registry(path, repository=tmp_path)


def test_a_modified_registry_is_refused(tmp_path):
    path = _registry(tmp_path)
    candidates, identity = st.load_registry(path, repository=tmp_path)
    assert set(candidates) == {"CE", "A", "CE+gate"} and identity["commit"]
    path.write_text(path.read_text() + " ")
    with pytest.raises(st.TuningError, match="registry_not_committed"):
        st.load_registry(path, repository=tmp_path)


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "x", "weights": {"zz": 1.0}},
        {"id": "x", "weights": {"a": 0.5}},
        {"id": "x", "weights": {"a": -1.0, "r": 2.0}},
        {"id": "x", "kind": "deciding", "gate": {"measure": "other", "cutoff": 1}},
    ],
)
def test_malformed_candidates_are_refused(tmp_path, bad):
    document = {"schema": st.REGISTRY_SCHEMA, "candidates": [bad]}
    path = tmp_path / "r.json"
    path.write_text(json.dumps(document))
    with pytest.raises(st.TuningError):
        st.load_registry(path)


def test_known_answers_alignment_regret_and_the_unsafe_pick(tmp_path):
    legs, values, recipe_of = _legs()
    members = sorted(legs)
    one_seed = [m for m in members if m.endswith("-s0")]
    unsafe = ["rec2-s1"]
    registry = st.load_registry(_registry(tmp_path), repository=tmp_path)
    result = st.evaluate_all(
        registry,
        legs,
        values,
        _outcomes(members, unsafe),
        recipe_of,
        members,
        one_seed,
        unsafe=unsafe,
    )
    a, ce, gated = (result["candidates"][k] for k in ("A", "CE", "CE+gate"))
    assert result["registry"]["commit"]
    # Leg a tracks decision value exactly: τ = 1, top choice is the best, no regret.
    assert a["tau_all"] == pytest.approx(1.0) and a["regret"] == 0.0
    assert a["divergence_count"] == 0 and not a["picks_unsafe"]
    # The deciding rule prefers the worst decider (the unsafe one) first.
    assert ce["tau_all"] == pytest.approx(-1.0)
    assert ce["unsafe_ranks"]["rec2-s1"][0] == 1
    assert ce["divergence_count"] > 0
    # The gate fails the unsafe member, which then ranks strictly last.
    assert gated["gate_failures"] == ["rec2-s1"]
    assert gated["unsafe_ranks"]["rec2-s1"] == (len(members), len(members))
    assert a["progress_vs_baseline"] and not ce["progress_vs_baseline"]


def test_an_unregistered_candidate_is_refused(tmp_path):
    legs, values, recipe_of = _legs()
    members = sorted(legs)
    registry = st.load_registry(_registry(tmp_path), repository=tmp_path)
    with pytest.raises(st.TuningError, match="candidate_not_registered"):
        st.evaluate_all(
            registry, legs, values, {}, recipe_of, members, members, ids=["B"]
        )


def test_stability_averages_a_recipe_s_seeds():
    legs, _values, recipe_of = _legs()
    candidate = st.Candidate("S", weights={"a": 1.0}, stable=True)
    scores, _ = st.candidate_scores(candidate, legs, recipe_of)
    assert scores["rec0-s0"] == scores["rec0-s1"]


def test_ineligible_members_score_zero_and_an_unmeasured_leg_is_none():
    legs, _values, recipe_of = _legs()
    legs["rec0-s0"]["eligible"] = False
    legs["rec0-s1"]["legs"]["a"] = None
    scores, _ = st.candidate_scores(
        st.Candidate("A", weights={"a": 1.0}), legs, recipe_of
    )
    assert scores["rec0-s0"] == 0.0 and scores["rec0-s1"] is None


def test_diagnosis_finds_sensitive_scenarios_and_leg_alignment():
    legs, values, _ = _legs()
    members = sorted(legs)
    results = {
        "decisions": {
            m: {
                "D1": {
                    "split": "development",
                    "outcome": {"decision_loss": values[m], "kind": "X", "selected": m},
                },
                "D2": {
                    "split": "development",
                    "outcome": {"decision_loss": 0.0, "kind": "X", "selected": "same"},
                },
            }
            for m in members
        }
    }
    report = st.diagnosis(results, members, legs, values, ["D1", "D2"])
    assert report["most_sensitive"][0] == "D1"
    assert report["scenarios"]["D2"]["distinct_selections"] == 1
    assert report["leg_alignment"]["a"]["rho_with_decision_value"] == pytest.approx(1.0)


def test_decision_values_use_the_common_resolved_mask():
    results = {
        "decisions": {
            "x": {
                "D1": {
                    "split": "development",
                    "outcome": {"decision_loss": 1.0, "kind": "K"},
                },
                "D2": {
                    "split": "development",
                    "outcome": {"decision_loss": None, "kind": "U"},
                },
            },
            "y": {
                "D1": {
                    "split": "development",
                    "outcome": {"decision_loss": 3.0, "kind": "K"},
                },
                "D2": {
                    "split": "development",
                    "outcome": {"decision_loss": 2.0, "kind": "K"},
                },
            },
        }
    }
    values, mask, outcomes = st.decision_values(results, ["x", "y"])
    assert mask == ["D1"] and values == {"x": 1.0, "y": 3.0}
    assert outcomes["x"] == {"D1": "K"}


def test_chain_mappings_pay_and_count_weight_on_unsafe():
    scores = {"m1": 3.0, "m2": 2.0, "m3": 1.0, "m4": 0.0}
    values = {"m1": 5.0, "m2": 1.0, "m3": 0.0, "m4": 9.0}
    out = st.chain_mappings(scores, values, list(scores), k=2, unsafe=["m1"])
    assert out["winner_take_all"]["weights"] == {"m1": 1.0}
    assert out["winner_take_all"]["weighted_loss"] == 5.0
    assert out["winner_take_all"]["best_possible_loss"] == 0.0
    assert out["winner_take_all"]["weight_on_unsafe"] == 1.0
    assert out["top_k_equal"]["weighted_loss"] == pytest.approx(3.0)
    assert out["top_k_rank"]["weights"]["m1"] == pytest.approx(2 / 3)


def test_the_public_api_is_what_candidate_scores_uses():
    """VALIDATOR-09 wraps a registry entry verbatim and scores through
    parse_candidate and score_member: the same floats as the panel path."""
    legs, _values, recipe_of = _legs()
    entry = {"id": "A", "weights": {"a": 0.6, "r": 0.4}, "basis": "x"}
    candidate = st.parse_candidate(entry)
    panel, _ = st.candidate_scores(candidate, legs, recipe_of)
    single = {m: st.score_member(candidate, row) for m, row in legs.items()}
    assert json.dumps(panel, sort_keys=True) == json.dumps(single, sort_keys=True)
    gated = st.parse_candidate(
        {"id": "G", "weights": {"a": 1.0}, "gate": {"measure": "near", "cutoff": 2.0}}
    )
    assert st.gate_verdict(gated, legs["rec2-s1"]) == "FAIL"
    assert st.gate_verdict(candidate, legs["rec2-s1"]) is None


def test_adversarial_members_must_leave_the_top_half_without_good_deciders():
    legs, values, recipe_of = _legs()
    members = sorted(legs)
    adversary = "rec2-s1"  # the worst decider, which -E ranks first
    ce = st.evaluate(
        st.candidate_scores(st.Candidate("CE", kind="deciding"), legs, recipe_of)[0],
        values,
        {},
        recipe_of,
        members,
        members,
        adversarial=[adversary],
    )[0]
    a = st.evaluate(
        st.candidate_scores(st.Candidate("A", weights={"a": 1.0}), legs, recipe_of)[0],
        values,
        {},
        recipe_of,
        members,
        members,
        adversarial=[adversary],
    )[0]
    assert ce["adversarial_in_top_half"] == [adversary]
    assert ce["good_deciders_top_half_share"] == 0.0
    assert a["adversarial_in_top_half"] == []
    assert a["good_deciders_top_half_share"] == 1.0


def test_a_gate_sweep_expands_and_reports_its_curve(tmp_path):
    legs, values, recipe_of = _legs()
    for i, m in enumerate(sorted(legs)):
        legs[m]["gates"]["feasibility"] = (
            0.1 * i
        )  # the worst decider is the most false-feasible
    members = sorted(legs)
    document = {
        "schema": st.REGISTRY_SCHEMA,
        "candidates": [
            {"id": "CE", "kind": "deciding"},
            {"id": "A", "weights": {"a": 1.0}},
            {
                "id": "G-FEAS/CE",
                "kind": "gate_sweep",
                "measure": "feasibility",
                "grid": [0.25, 1.01],
                "base": "CE",
            },
        ],
    }
    path = _registry(tmp_path, document)
    registry = st.load_registry(path, repository=tmp_path)
    assert registry[1]["sweeps"] == {"G-FEAS/CE": ["G-FEAS/CE@0.25", "G-FEAS/CE@1.01"]}
    result = st.evaluate_all(registry, legs, values, {}, recipe_of, members, members)
    curve = result["sweep_curves"]["G-FEAS/CE"]
    assert [p["cutoff"] for p in curve] == [0.25, 1.01]
    assert curve[0]["gate_failures"] > 0 and curve[1]["gate_failures"] == 0
    assert curve[0]["tau_all"] > curve[1]["tau_all"]
    assert result["threshold"].startswith("HUMAN_INPUT")


@pytest.mark.parametrize(
    "bad",
    [
        {
            "id": "s",
            "kind": "gate_sweep",
            "measure": "nope",
            "grid": [0.1],
            "base": "CE",
        },
        {
            "id": "s",
            "kind": "gate_sweep",
            "measure": "feasibility",
            "grid": [0.2, 0.1],
            "base": "CE",
        },
        {
            "id": "s",
            "kind": "gate_sweep",
            "measure": "feasibility",
            "grid": [0.1],
            "base": "missing",
        },
    ],
)
def test_malformed_sweeps_are_refused(tmp_path, bad):
    document = {
        "schema": st.REGISTRY_SCHEMA,
        "candidates": [{"id": "CE", "kind": "deciding"}, bad],
    }
    path = tmp_path / "r.json"
    path.write_text(json.dumps(document))
    with pytest.raises(st.TuningError):
        st.load_registry(path)


def test_the_committed_registries_load():
    for name in ("registry-v1.json", "registry-v2.json"):
        candidates, identity = st.load_registry(
            st.Path(__file__).resolve().parents[2]
            / "docs/development/evidence/battery-score-tuning"
            / name
        )
        assert "CE" in candidates
    assert len(identity["sweeps"]) == 10 and len(candidates) == 12 + 80
    v3, identity3 = st.load_registry(
        st.Path(__file__).resolve().parents[2]
        / "docs/development/evidence/battery-score-tuning/registry-v3.json"
    )
    assert set(candidates) < set(v3) and "A-Q" in v3 and len(identity3["sweeps"]) == 11


def test_false_infeasible_and_near_limit_on_real_references():
    from carbon.battery.value import scoring as sc
    from carbon.battery.value.contract import load

    contract, _ = load(
        st.Path(__file__).resolve().parents[2]
        / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
    )
    store, ids, _ = sc.scoring_set(st.Path(__file__).resolve().parents[2])
    ids = ids[:200]
    oracle = {c: store.refs[c]["outputs"] for c in ids}
    assert st.false_infeasible_rate(contract, oracle, ids, store.refs) == 0.0
    assert st.false_feasible_rate(contract, oracle, ids, store.refs) in (0.0, None)
    near = [c for c in ids if st.near_limit(contract, store.refs[c]["outputs"], 1.0)]
    wider = [c for c in ids if st.near_limit(contract, store.refs[c]["outputs"], 4.0)]
    assert set(near) <= set(wider)
    assert st.false_infeasible_rate(contract, {}, ids, store.refs) is None


def test_leg_q_and_the_cautious_control():
    legs, values, recipe_of = _legs()
    for i, m in enumerate(sorted(legs)):
        legs[m]["legs"]["q"] = 1.0 / (1.0 + i)  # regret i: the worst decider has most
    scores, _ = st.candidate_scores(
        st.parse_candidate({"id": "A-Q", "weights": {"a": 0.5, "q": 0.5}}),
        legs,
        recipe_of,
    )
    assert max(scores, key=scores.get) == min(values, key=values.get)
    outputs = {"plating_margin_v": 0.002, "temperature_c": [25.0, 40.0, 44.0]}
    cautious = st.near_limit_cautious(outputs)
    assert cautious["plating_margin_v"] < 0 and max(cautious["temperature_c"]) > 45
    far = {"plating_margin_v": 0.05, "temperature_c": [25.0, 30.0]}
    assert st.near_limit_cautious(far) == far
