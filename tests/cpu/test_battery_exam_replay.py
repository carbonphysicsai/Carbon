"""The promoted battery exam replays the exam-design campaign (M2, OD-2).

Claims tested, against the campaign's retained evidence:
- on the same inputs, `carbon.battery.exam` returns exactly what the research
  modules returned: every gate, typed state, case error, aggregate and final
  comparison, for all eight retained decision models on all 2,600 cases;
- every recorded verification decision (V1-V7, R1) is reproduced from the
  retained predictions. The retained predictions are float32, so recorded
  mean differences are reproduced to 1e-5, not bit for bit; decisions,
  labels and which gates fire are identical (one fault's count moves by 2 of
  200 at the float32 ceiling boundary);
- tolerances and scales recomputed from references equal the frozen ones;
- the OD-2 rule constants equal the committed freeze record.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import exam as ours
from scripts.dev.exam_design import campaign as C
from scripts.dev.exam_design import controls, gates, plans, scoring
from scripts.dev.exam_design import exam as research

EVID = C.EVID
MODELS = C.DECISION_MODELS


@pytest.fixture(scope="module")
def evidence():
    refs, twins, refined, _ = C._all_refs()
    prep = json.loads(Path(f"{EVID}/prepare.json").read_text())
    theirs = C._store(refs, twins, prep, len(plans.MAIN_CHECKPOINTS))
    mine = ours.CaseStore(
        refs,
        theirs.ocv,
        ours.Tolerances(
            **{
                k: getattr(theirs.tol, k)
                for k in theirs.tol.as_dict()
                if k != "evidence"
            }
        ),
        theirs.scales,
        theirs.shapes,
        twins,
    )
    preds = {}
    for tag in MODELS:
        ids, arrays = C.read_retained(f"{EVID}/predictions/{tag}.f32.json.gz")
        preds[tag] = {
            c: {
                k: (a[i].tolist() if a.ndim > 1 else float(a[i]))
                for k, a in arrays.items()
            }
            for i, c in enumerate(ids)
        }
    return {
        "refs": refs,
        "refined": refined,
        "prep": prep,
        "theirs": theirs,
        "mine": mine,
        "preds": preds,
        "freeze": json.loads(Path(C.FREEZE).read_text()),
        "verification": json.loads(Path(f"{EVID}/verification.json").read_text()),
    }


def test_every_case_is_gated_and_scored_identically(evidence):
    ids = sorted(evidence["refs"])
    assert len(ids) == 2600 and len(MODELS) == 8
    for tag in MODELS:
        preds = evidence["preds"][tag]
        mine = ours.evaluate(preds, ids, evidence["mine"])
        theirs = research.evaluate(preds, ids, evidence["theirs"])
        assert mine == theirs, tag
    # Specimen: the raw control really fails a gate, so equality is not vacuous.
    agg = ours.evaluate(evidence["preds"]["mlp_raw-s0"], ids, evidence["mine"])[1]
    assert agg["gate_failures"] and not agg["eligible"]


def _errors(module, preds, ids, store):
    rows, agg = module.evaluate(preds, ids, store)
    err = {r["case_id"]: r["error"] for r in rows if r["state"] == ours.SCORABLE}
    comp = {r["case_id"]: r["components"] for r in rows if r["state"] == ours.SCORABLE}
    return err, comp, agg


def test_the_frozen_rule_reproduces_every_verification_decision(evidence):
    fr, ver = evidence["freeze"], evidence["verification"]
    recorded = {r["id"]: r for r in ver["results"]}
    vids = C._role_ids(evidence["refs"], "pverify")
    assert len(vids) == ver["n_cases"] == 200
    rule = ours.ComparisonRule(
        equivalence_margin=ours.DEVELOPMENT_RULE["equivalence_margin_rel"]
    )
    store = evidence["mine"]
    imp = {c: store.important(c) for c in vids}
    errs = {t: _errors(ours, p, vids, store) for t, p in evidence["preds"].items()}
    checked = []
    for crit in fr["criteria"]:
        got = recorded[crit["id"]]
        if "comparison" in crit:
            inc, ch = crit["comparison"]
            args = (errs[inc][0], errs[ch][0], imp, rule)
            kw = {
                "chal_eligible": errs[ch][2]["eligible"],
                "inc_components": errs[inc][1],
                "chal_components": errs[ch][1],
            }
            fin = ours.final_compare(*args, **kw)
            # Identical to the research module on identical inputs.
            assert fin == research.final_compare(
                *args,
                **kw,
            ) | {"rule": fin["rule"]}
            want = got["outcome"]
            for key in ("outcome", "promotable", "overall", "important", "components"):
                assert fin[key] == want[key], (crit["id"], key)
            assert fin["n_important"] == want["n_important"]
            assert fin["mean_delta"] == pytest.approx(want["mean_delta"], abs=1e-5)
        elif crit.get("faults"):
            for name in controls.FAULTS:
                faulty = controls.fault(
                    name, evidence["preds"]["mlp-s0"], store.tol.q_bound, seed=11
                )
                agg = ours.evaluate(faulty, vids, store)[1]
                assert agg == research.evaluate(faulty, vids, evidence["theirs"])[1]
                recorded_fault = got["faults"][name]
                # The same gates fire and eligibility matches. Counts are
                # exact except where noise straddles the 4.2 V ceiling on
                # float32-retained predictions (the nondeterminism fault).
                assert set(agg["gate_failures"]) == set(recorded_fault["gate_failures"])
                assert agg["eligible"] == recorded_fault["eligible"]
                if name != "nondeterministic":
                    assert agg["gate_failures"] == recorded_fault["gate_failures"]
        elif crit.get("leak"):
            leak = controls.pool_leak(
                evidence["preds"]["mlp-s0"],
                evidence["refs"],
                {c for batch in C._batch_ids() for c in batch},
            )
            fin = ours.final_compare(
                errs["mlp-s0"][0], _errors(ours, leak, vids, store)[0], imp, rule
            )
            assert fin["outcome"] == got["outcome"]["outcome"]
            assert fin["promotable"] is False
        elif crit.get("oracle"):
            agg = ours.evaluate(controls.oracle(evidence["refs"], vids), vids, store)[1]
            assert agg["n_gate_failed"] == 0 and got["pass"]
        checked.append(crit["id"])
    assert checked == ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "R1"]


def test_the_rule_is_the_committed_freeze(evidence):
    settings = evidence["freeze"]["settings"]
    rule = ours.DEVELOPMENT_RULE
    assert rule["equivalence_margin_rel"] == settings["equivalence_margin_rel"]
    assert rule["screening_batch_size"] == settings["batch_size"]
    assert rule["rotate_after_admitted"] == settings["rotate_after"]
    assert rule["active_batches"] == settings["active_batches"]
    assert rule["train_v1_cases"] == settings["train_v1_n"]
    assert rule["comparison"] == settings["comparison_rule"]
    assert rule["important_region"] == settings["important_region"]
    assert rule["status"] == "PROVISIONAL_DEVELOPMENT_NON_PAYING"
    defaults = ours.ComparisonRule(equivalence_margin=0.0)
    assert {k: getattr(defaults, k) for k in settings["comparison_rule"]} == (
        settings["comparison_rule"]
    )


def test_tolerances_and_scales_are_recomputed_from_references(evidence):
    refs, prep = evidence["refs"], evidence["prep"]
    table = json.loads(Path(f"{EVID}/ocv_table.json").read_text())
    calibration = [
        r
        for r in refs.values()
        if r.get("role") in ("train", "practice") and r.get("status") == "OK"
    ]
    ocv = C.ocv_map(refs, table)
    mine = ours.calibrate(calibration, ocv, table["capacity_bounds"]["bound_ah"])
    theirs = gates.calibrate(calibration, ocv, table["capacity_bounds"]["bound_ah"])
    assert mine.as_dict() == theirs.as_dict()
    train = [r for r in refs.values() if r.get("role") == "train"]
    floors = prep["scales"]["floors"]
    assert ours.scales_from_train(train, floors) == scoring.scales_from_train(
        train, floors
    )
    for key in ("s_v", "s_t", "s_eta", "s_q1", "s_fade"):
        assert ours.scales_from_train(train, floors)[key] == prep["scales"][key]


def test_screening_pool_rotation_matches_the_research_pool(evidence):
    batches = C._batch_ids()
    bank_a, bank_b = ours.PredictionBank(), research.PredictionBank()
    for tag in ("mlp-s0", "mlp-s1", "mlp_half-s0", "knn"):
        bank_a.add(tag, evidence["preds"][tag])
        bank_b.add(tag, evidence["preds"][tag])
    rule = ours.DEVELOPMENT_RULE
    pool_a = ours.ScreeningPool(
        batches,
        rule["rotate_after_admitted"],
        rule["active_batches"],
        rule["screening_batch_size"],
    )
    pool_b = research.ScreeningPool(batches, 3, 3, 100)
    for tag in ("mlp-s0", "mlp-s1", "mlp_half-s0", "knn", "mlp-s0"):
        assert pool_a.score(tag, bank_a, evidence["mine"]) == pool_b.score(
            tag, bank_b, evidence["theirs"]
        )
    assert pool_a.pool_version == pool_b.pool_version == 1
    assert pool_a.retired == [0]
    assert np.isfinite(pool_a.history[-1]["score"])
