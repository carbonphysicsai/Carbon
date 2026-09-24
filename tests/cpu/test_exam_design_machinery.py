"""Exam-design campaign machinery: gates, typed case states, pools, comparison, controls.

Numpy-only: no PyBaMM, fdtdx or GPU. The references here are synthetic records
shaped like the battery challenge's, built so each gate's boundary is known.
"""

from __future__ import annotations

import numpy as np
import pytest

from scripts.dev.exam_design import controls, exam, gates, scoring, simulate

G = 121
SHAPES = {"voltage_v": (G,), "temperature_c": (G,), "plating_margin_v": (), "capacity_ah": (3,)}


def _ref(cid: str, soc: float, t_amb: float, eta: float, t_max: float, rng) -> dict:
    ocv = 3.3 + 0.9 * soc
    v = np.minimum(ocv + np.linspace(0, 1.2, G) + rng.normal(0, 1e-3, G), 4.2)
    v[0] = ocv
    t = t_amb + np.linspace(0, t_max - t_amb, G)
    t[0] = t_amb
    return {"case_id": cid, "status": "OK", "inputs": {"c1": 1.0, "c2": 0.5, "t_amb_c": t_amb, "soc0": soc},
            "outputs": {"voltage_v": v.tolist(), "temperature_c": t.tolist(), "plating_margin_v": eta,
                        "capacity_ah": [4.9 + 0.001 * t_amb, 4.89 + 0.0011 * t_amb, 4.88 + 0.0009 * t_amb]},
            "diagnostics": {"t_max_c": t_max}}


@pytest.fixture()
def store():
    rng = np.random.default_rng(0)
    refs = {}
    for i in range(40):
        eta = -0.03 if i % 5 == 0 else 0.05  # every fifth case reaches plating conditions
        refs[f"c{i:03d}"] = _ref(f"c{i:03d}", 0.1 + 0.01 * i, 5 + i * 0.8, eta, 30 + i * 0.5, rng)
    refs["c001"] = refs["c000"] | {"case_id": "c001"}  # hidden duplicate: same inputs, same reference
    refs["c-bad"] = {"case_id": "c-bad", "status": "REFERENCE_SOLVER_FAILED", "inputs": {"t_amb_c": 20.0}}
    ocv = {c: 3.3 + 0.9 * r["inputs"]["soc0"] for c, r in refs.items() if r["status"] == "OK"}
    ok = [r for r in refs.values() if r["status"] == "OK"]
    tol = gates.calibrate(ok, ocv, q_bound=5.8)
    return exam.CaseStore(refs, ocv, tol, scoring.scales_from_train(ok), SHAPES, twins={"c001": "c000"})


def _ids(store):
    return sorted(store.refs)


def test_oracle_passes_every_gate_including_unsafe_and_important_cases(store):
    ids = [c for c in _ids(store) if c != "c-bad"]
    preds = controls.oracle(store.refs, ids)
    rows, agg = exam.evaluate(preds, ids, store)
    assert agg["eligible"] and agg["n_gate_failed"] == 0
    assert agg["score"] == pytest.approx(0.0, abs=1e-12)
    # Plating-onset cases are scored, never gated, and counted as important.
    assert agg["n_important"] >= 8


@pytest.mark.parametrize("kind,gate", [(k, g) for k, g in controls.FAULTS.items() if g and g != "paired_repeat"])
def test_each_authored_fault_fires_its_own_gate(store, kind, gate):
    ids = [c for c in _ids(store) if c != "c-bad"]
    bad = controls.fault(kind, controls.oracle(store.refs, ids), q_bound=store.tol.q_bound)
    _, agg = exam.evaluate(bad, ids, store)
    assert not agg["eligible"]
    assert gate in agg["gate_failures"]


def test_nondeterminism_fires_paired_repeat_only_where_a_twin_exists(store):
    ids = ["c000", "c001", "c002"]
    base = controls.oracle(store.refs, ids)
    bad = controls.fault("nondeterministic", base, q_bound=store.tol.q_bound, seed=3)
    rows, agg = exam.evaluate(bad, ids, store)
    by = {r["case_id"]: r for r in rows}
    assert by["c000"]["gates"]["paired_repeat"] == "FAIL"
    assert by["c002"]["gates"]["paired_repeat"] == "NOT_APPLICABLE"


def test_time_shift_passes_gates_but_scores_worse(store):
    ids = [c for c in _ids(store) if c not in ("c-bad", "c001")]
    good = controls.oracle(store.refs, ids)
    shifted = controls.fault("time_shift", good, q_bound=store.tol.q_bound)
    _, agg = exam.evaluate(shifted, ids, store)
    assert agg["eligible"] and agg["score"] > 0


def test_reference_failure_and_infra_are_never_charged_to_the_model(store):
    ids = ["c002", "c003", "c-bad"]
    preds = controls.oracle(store.refs, ["c002"])
    rows, agg = exam.evaluate(preds, ids, store, infra_failed={"c003"})
    states = {r["case_id"]: r["state"] for r in rows}
    assert states == {"c002": "SCORABLE", "c003": "FAILED_INFRA", "c-bad": "REFERENCE_INVALID"}
    assert agg["eligible"] and agg["n_reference_invalid"] == 1 and agg["n_failed_infra"] == 1


def test_sub_ambient_temperature_and_negative_heat_are_not_gated(store):
    ids = ["c010"]
    p = controls.oracle(store.refs, ids)
    t = np.asarray(p["c010"]["temperature_c"])
    t[5:10] = t[0] - 0.2  # entropic cooling below ambient after t = 0
    p["c010"]["temperature_c"] = t.tolist()
    _, agg = exam.evaluate(p, ids, store)
    assert agg["eligible"]


def test_tolerances_come_from_reference_evidence_with_a_float32_floor(store):
    tol = store.tol
    assert tol.tau_v0 >= gates.ULP_FACTOR * gates.F32_EPS * 4.2
    assert tol.evidence["n_references"] == 40


def test_pool_rotates_after_n_admitted_and_reuses_stored_predictions(store):
    ids = [c for c in _ids(store) if c not in ("c-bad", "c001")]
    batches = [ids[i:i + 6] for i in range(0, 36, 6)]
    calls = []

    def predictor(cids):
        calls.append(len(cids))
        return controls.oracle(store.refs, cids)

    bank = exam.PredictionBank({"m": predictor})
    pool = exam.ScreeningPool(batches=batches, rotate_after=2)
    versions = [pool.score("m", bank, store)["pool_version"] for _ in range(6)]
    assert versions == [0, 0, 1, 1, 2, 2]
    assert pool.retired == [0, 1, 2]
    # First call infers the initial pool; each rotation infers only the incoming batch.
    assert calls[0] == 18 and all(c == 6 for c in calls[1:])


def test_nested_batch_prefix_uses_the_same_cases(store):
    ids = [c for c in _ids(store) if c not in ("c-bad", "c001")]
    batches = [ids[i:i + 10] for i in range(0, 30, 10)]
    small = exam.ScreeningPool(batches=batches, rotate_after=99, batch_size=4)
    assert set(small.active_case_ids()) <= set(exam.ScreeningPool(batches=batches, rotate_after=99).active_case_ids())


def test_train_changes_only_by_named_version(store):
    tv = exam.TrainVersions("train-v1", ["a", "b"])
    tv.publish("train-v2", ["c"], reason="retired screening batch B00")
    assert tv.versions["train-v1"] == ["a", "b"] and tv.versions["train-v2"] == ["a", "b", "c"]
    with pytest.raises(ValueError):
        tv.publish("train-v2", ["d"], reason="duplicate")


def _cmp(delta, n=200, imp_every=4, seed=1, margin=0.02):
    rng = np.random.default_rng(seed)
    inc = {f"k{i}": 1.0 + rng.normal(0, 0.05) for i in range(n)}
    chal = {k: v + delta(i) + rng.normal(0, 0.01) for i, (k, v) in enumerate(inc.items())}
    imp = {k: i % imp_every == 0 for i, k in enumerate(inc)}
    return exam.final_compare(inc, chal, imp, exam.ComparisonRule(equivalence_margin=margin))


def test_final_comparison_allows_every_outcome():
    assert _cmp(lambda i: -0.1)["outcome"] == exam.IMPROVEMENT
    assert _cmp(lambda i: +0.1)["outcome"] == exam.REGRESSION
    assert _cmp(lambda i: 0.0)["outcome"] == exam.NO_IMPROVEMENT
    assert _cmp(lambda i: -0.1 if i % 4 else +0.1)["outcome"] == exam.TRADE_OFF
    assert _cmp(lambda i: -0.02 if i % 4 else +0.2)["outcome"] == exam.REGRESSION
    few = exam.final_compare({"a": 1.0}, {"a": 0.5}, {"a": True}, exam.ComparisonRule(equivalence_margin=0.02))
    assert few["outcome"] == exam.INSUFFICIENT


def test_gate_failure_on_final_cases_is_a_regression_not_a_tradeoff():
    r = exam.final_compare({"a": 1.0}, {"a": 0.1}, {}, exam.ComparisonRule(equivalence_margin=0.02),
                           chal_eligible=False)
    assert r["outcome"] == exam.REGRESSION


def test_seed_mixing_attack_gain_shrinks_with_faster_rotation():
    rng = np.random.default_rng(0)
    e1 = rng.gamma(4, 0.05, 4000)
    e2 = rng.gamma(4, 0.05, 4000)
    slow = simulate.seed_mixing_attack(e1, e2, batch_size=50, rotate_after=10, submissions=30, reps=60)
    fast = simulate.seed_mixing_attack(e1, e2, batch_size=50, rotate_after=1, submissions=30, reps=60)
    assert slow["mean_gain"] > fast["mean_gain"] > 0 or fast["mean_gain"] <= 0.5 * slow["mean_gain"]


def test_ranking_reliability_improves_with_batch_size():
    rng = np.random.default_rng(0)
    a = rng.gamma(4, 0.05, 3000)
    b = a + 0.01 + rng.normal(0, 0.05, 3000)
    r = simulate.ranking_reliability(a, b, [50, 200, 600], margin=0.004, reps=800)
    s = r["sizes"]
    assert s[50]["same_order_as_full"] < s[600]["same_order_as_full"]


def test_adaptive_agent_extension_refuses_without_an_authorized_budget(monkeypatch):
    from scripts.dev.exam_design import adaptive_agent

    monkeypatch.delenv("CARBON_EXAM_AGENT_BUDGET_USD", raising=False)
    monkeypatch.delenv("CARBON_EXAM_AGENT_AUTHORITY", raising=False)
    with pytest.raises(adaptive_agent.NotAuthorized):
        adaptive_agent.authorize()
    fb = adaptive_agent.feedback({"eligible": True, "score": 0.1, "pool_version": 2, "gate_failures": {},
                                  "components": {"voltage": 0.1}})
    assert set(fb) == {"eligible", "score", "pool_version", "failed_gates"}
    with pytest.raises(ValueError):
        adaptive_agent.validate_submission({"recipe": "mlp", "case_ids": ["x"]})


def test_regional_regression_blocks_promotion_even_with_an_overall_gain():
    r = _cmp(lambda i: -0.1 if i % 4 else +0.1)
    assert r["outcome"] == exam.TRADE_OFF and not r["promotable"] and r["regional_block"]
    assert _cmp(lambda i: -0.1)["promotable"]


def test_screening_nomination_refuses_regional_regression():
    inc = {"eligible": True, "score": 1.0, "important_score": 1.0, "pool_version": 3}
    better_but_regional = {"eligible": True, "score": 0.8, "important_score": 1.2, "pool_version": 3}
    assert exam.nominate(better_but_regional, inc, 0.02) == (False, "important-region regression beyond the margin")
    assert exam.nominate(dict(better_but_regional, important_score=0.9), inc, 0.02)[0]
    assert not exam.nominate(dict(better_but_regional, pool_version=2), inc, 0.02)[0]
