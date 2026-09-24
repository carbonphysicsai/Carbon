"""Campaign assembly and analysis (runs off the pod, on retained evidence).

    python -m scripts.dev.exam_design.campaign prepare          # after reference pod A
    python -m scripts.dev.exam_design.campaign learning-curve   # local CPU, PRACTICE only
    python -m scripts.dev.exam_design.campaign train-plan --n N # writes the A40 reconstruction plan
    python -m scripts.dev.exam_design.campaign analyze          # after reference pod B + reconstruction
    python -m scripts.dev.exam_design.campaign verify           # only after the freeze record exists

``prepare`` writes the public artifacts a prediction worker may receive (TRAIN
v1 references, the OCV table, the inputs manifest) and **seals** the
verification references: their digest is recorded and nothing reads their
outputs until ``verify`` runs against a committed freeze record.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import json
import os
import time

import numpy as np

from scripts.dev.exam_design import exam, gates, plans, recipes, scoring

EVID = "docs/development/evidence/exam-design-2026-09-24"
SHAPES = lambda k: {"voltage_v": (121,), "temperature_c": (121,), "plating_margin_v": (), "capacity_ah": (k,)}  # noqa: E731


def _jsonl(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt") as f:
        return [json.loads(l) for l in f if l.strip()]


def _write_jsonl_gz(path, rows):
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_refs(pattern: str) -> tuple[dict, dict, list]:
    """Normal references by case id, refined references by case id, and every record (failures kept)."""
    normal, refined, every = {}, {}, []
    for path in sorted(glob.glob(pattern)):
        for r in _jsonl(path):
            every.append(r)
            (refined if r.get("refined") else normal)[r["case_id"]] = r
    return normal, refined, every


def with_twins(refs: dict) -> tuple[dict, dict]:
    """Add hidden-duplicate case ids; each carries its original's reference unchanged."""
    twins = {}
    for slots in plans.screen_batches():
        for c in slots:
            if "duplicate_of" in c and c["duplicate_of"] in refs:
                refs[c["case_id"]] = dict(refs[c["duplicate_of"]], case_id=c["case_id"], duplicate_of=c["duplicate_of"])
                twins[c["case_id"]] = c["duplicate_of"]
    return refs, twins


def ocv_map(refs: dict, table: dict) -> dict:
    return {cid: float(np.interp(r["inputs"]["soc0"], table["soc"], table["ocv_v"])) for cid, r in refs.items()
            if r.get("inputs")}


def reference_self_check(refs: dict, tol: gates.Tolerances, ocv: dict, shapes) -> dict:
    """A reference must pass the gates it anchors; a failing reference is REFERENCE_INVALID."""
    bad = {}
    for cid, r in refs.items():
        if r.get("status") != "OK":
            continue
        row = gates.evaluate_case(r["outputs"], r, r["inputs"], ocv[cid], tol, shapes)
        if row["state"] != gates.SCORABLE:
            r["reference_valid"] = False
            bad[cid] = [g for g, v in row["gates"].items() if v == "FAIL"]
    return bad


def reference_uncertainty(normal: dict, refined: dict, scales: dict) -> dict:
    """Coarse-vs-refined disagreement per output, raw and in score units."""
    rows = []
    for cid, f in refined.items():
        c = normal.get(cid)
        if not c or c.get("status") != "OK" or f.get("status") != "OK":
            continue
        comp = scoring.case_components(c["outputs"], f, scales)
        rows.append({"case_id": cid, "components": comp, "case_error": scoring.case_error(comp),
                     "fade_last_mAh": {"coarse": 1000 * (c["outputs"]["capacity_ah"][0] - c["outputs"]["capacity_ah"][-1]),
                                       "refined": 1000 * (f["outputs"]["capacity_ah"][0] - f["outputs"]["capacity_ah"][-1])},
                     "plating_margin_diff_v": f["outputs"]["plating_margin_v"] - c["outputs"]["plating_margin_v"]})
    errs = np.array([r["case_error"] for r in rows]) if rows else np.array([np.nan])
    return {"n": len(rows), "case_error_median": float(np.median(errs)), "case_error_max": float(np.max(errs)),
            "components_median": {k: float(np.median([r["components"][k] for r in rows])) for k in scoring.COMPONENTS}
            if rows else None, "rows": rows}


def cmd_prepare(a) -> None:
    normal, refined, every = load_refs(f"{EVID}/refs-a/out/battery_refs/records.jsonl")
    table = json.load(open(f"{EVID}/ocv_table.json"))
    k = len(plans.MAIN_CHECKPOINTS)
    shapes = SHAPES(k)
    by_role: dict[str, list] = {}
    for r in normal.values():
        by_role.setdefault(r["role"], []).append(r)
    train_ok = [r for r in sorted(by_role["train"], key=lambda r: r["case_id"]) if r["status"] == "OK"]
    practice_ok = [r for r in by_role["practice"] if r["status"] == "OK"]
    ocv = ocv_map(normal, table)
    tol = gates.calibrate(train_ok + practice_ok, ocv, table["capacity_bounds"]["bound_ah"])
    scales = scoring.scales_from_train(train_ok)
    self_bad = reference_self_check(normal, tol, ocv, shapes)
    unc = reference_uncertainty(normal, refined, scales)
    os.makedirs(f"{EVID}/datasets", exist_ok=True)
    train_sha = _write_jsonl_gz(f"{EVID}/datasets/train-v1-candidates.jsonl.gz", train_ok)
    verify = [r for r in by_role.get("verify", [])]
    sealed = hashlib.sha256(json.dumps(sorted(verify, key=lambda r: r["case_id"]), sort_keys=True).encode()).hexdigest()
    json.dump(plans.inputs_manifest(), open(f"{EVID}/datasets/inputs.json", "w"))
    status = {}
    for r in every:
        key = f'{r.get("role")}{"/refined" if r.get("refined") else ""}'
        status.setdefault(key, {}).setdefault(r["status"], 0)
        status[key][r["status"]] += 1
    walls = [r["wall_total_s"] for r in normal.values() if r["status"] == "OK"]
    out = {"prepared_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status_counts": status,
           "tolerances": tol.as_dict(), "scales": scales, "reference_self_check_failures": self_bad,
           "reference_uncertainty": {k2: v for k2, v in unc.items() if k2 != "rows"},
           "reference_uncertainty_rows": unc["rows"],
           "wall_s": {"median": float(np.median(walls)), "p90": float(np.quantile(walls, 0.9)), "max": float(np.max(walls))},
           "train_candidates_sha256": train_sha, "n_train_ok": len(train_ok),
           "verify_sealed": {"n": len(verify), "sha256": sealed,
                             "note": "verification references are not read until the freeze record is committed"}}
    json.dump(out, open(f"{EVID}/prepare.json", "w"), indent=1)
    print(json.dumps({k2: out[k2] for k2 in ("status_counts", "tolerances", "wall_s", "n_train_ok", "verify_sealed")}, indent=1))
    print("reference uncertainty", json.dumps(out["reference_uncertainty"]))


def _structure():
    t = json.load(open(f"{EVID}/ocv_table.json"))
    return recipes.Structure(t["soc"], t["ocv_v"])


def _store(refs, twins, prep, k):
    table = json.load(open(f"{EVID}/ocv_table.json"))
    tol = gates.Tolerances(**{x: prep["tolerances"][x] for x in ("tau_v0", "tau_t0", "tau_vmax", "tau_vmin", "q_bound",
                                                                 "v_max", "v_min")})
    return exam.CaseStore(refs, ocv_map(refs, table), tol, prep["scales"], SHAPES(k), twins)


def cmd_learning_curve(a) -> None:
    """Local CPU study on PRACTICE (public): how much TRAIN is a useful starting point?"""
    prep = json.load(open(f"{EVID}/prepare.json"))
    normal, _, _ = load_refs(f"{EVID}/refs-a/out/battery_refs/records.jsonl")
    train = _jsonl(f"{EVID}/datasets/train-v1-candidates.jsonl.gz")
    practice = sorted([r for r in normal.values() if r["role"] == "practice" and r["status"] == "OK"],
                      key=lambda r: r["case_id"])
    store = _store(normal, {}, prep, len(plans.MAIN_CHECKPOINTS))
    x = np.array([[r["inputs"][k] for k in ("c1", "c2", "t_amb_c", "soc0")] for r in practice])
    ids = [r["case_id"] for r in practice]
    rows = []
    for n in a.sizes:
        d = recipes.Data.from_records(train[:n], scoring.is_important)
        for name in a.recipes:
            for seed in (range(a.seeds) if name != "knn" else [0]):
                m = recipes.make(name)
                t0 = time.perf_counter()
                st = m.fit(d, _structure(), seed=seed)
                preds = recipes.to_preds(m.predict(x), ids)
                _, agg = exam.evaluate(preds, ids, store)
                rows.append({"recipe": name, "n_train": n, "seed": seed, "fit_s": time.perf_counter() - t0,
                             "score": agg["score"], "important_score": agg["important_score"],
                             "eligible": agg["eligible"], "gate_failures": agg["gate_failures"],
                             "components": agg["components"]})
                print(json.dumps(rows[-1]), flush=True)
    json.dump({"host": "development container (CPU); diagnostic, not A40 evidence", "practice_n": len(ids),
               "rows": rows}, open(f"{EVID}/learning_curve.json", "w"), indent=1)


def cmd_train_plan(a) -> None:
    train = _jsonl(f"{EVID}/datasets/train-v1-candidates.jsonl.gz")[: a.n]
    sha = _write_jsonl_gz(f"{EVID}/datasets/train-v1.jsonl.gz", train)
    important = [r["case_id"] for r in train if scoring.is_important(r)]
    roles = ["train", "practice", "final", "verify"] + [f"screen-B{b:02d}" for b in range(plans.SCREEN_BATCHES)]
    runs = [{"tag": "knn", "recipe": "knn", "seed": 0, "train_n": a.n, "predict_roles": roles}]
    for rec in ("mlp", "mlp_plus", "mlp_plus_localized"):
        for s in range(3):
            runs.append({"tag": f"{rec}-s{s}", "recipe": rec, "seed": s, "train_n": a.n, "predict_roles": roles})
    for rec in ("mlp", "mlp_plus"):
        runs.append({"tag": f"{rec}-s0-repeat", "recipe": rec, "seed": 0, "train_n": a.n, "predict_roles": roles})
    plan = {"plan": "battery-reconstruct-v1", "train_file": f"{EVID}/datasets/train-v1.jsonl.gz",
            "train_sha256": sha, "ocv_table": f"{EVID}/ocv_table.json", "inputs_file": f"{EVID}/datasets/inputs.json",
            "important_train_ids": important, "runs": runs}
    json.dump(plan, open(f"{EVID}/plans/reconstruct-v1.json", "w"), indent=1)
    print(json.dumps({"n_train": a.n, "runs": len(runs), "train_sha256": sha, "important": len(important)}))


# --------------------------------------------------------------------------- analysis

SCREEN_SIZES = (50, 100, 200)
SCHEDULES = (1, 3, 10)


def _all_refs():
    normal, refined, every = load_refs(f"{EVID}/refs-*/out/battery_refs/records.jsonl")
    return with_twins(normal) + (refined, every)


def load_predictions(pattern=f"{EVID}/refs-b/out/train/pred_*.json.gz") -> dict:
    out = {}
    for path in sorted(glob.glob(pattern, recursive=True)):
        tag = os.path.basename(path)[len("pred_"):-len(".json.gz")]
        with gzip.open(path, "rt") as f:
            out[tag] = json.load(f)
    return out


def _role_ids(refs: dict, role: str) -> list:
    return sorted(c for c, r in refs.items() if r.get("role") == role and not r.get("refined"))


def _batch_ids() -> list[list[str]]:
    return [[c["case_id"] for c in slots] for slots in plans.screen_batches()]


def _case_errors(preds: dict, ids: list, store) -> tuple[dict, dict, dict]:
    rows, agg = exam.evaluate(preds, ids, store)
    err = {r["case_id"]: r["error"] for r in rows if r["state"] == gates.SCORABLE}
    comp = {r["case_id"]: r["components"] for r in rows if r["state"] == gates.SCORABLE}
    return err, comp, agg


def _seed_avg(errs: list[dict]) -> dict:
    common = set.intersection(*[set(e) for e in errs])
    return {c: float(np.mean([e[c] for e in errs])) for c in common}


def _kendall(a: list, b: list) -> float:
    n, s = len(a), 0
    for i in range(n):
        for j in range(i + 1, n):
            s += np.sign(a[i] - a[j]) * np.sign(b[i] - b[j])
    return float(s / (n * (n - 1) / 2))


def cmd_analyze(a) -> None:
    from scripts.dev.exam_design import controls, simulate

    prep = json.load(open(f"{EVID}/prepare.json"))
    refs, twins, refined, every = _all_refs()
    k = len(plans.MAIN_CHECKPOINTS)
    store = _store(refs, twins, prep, k)
    reference_self_check(refs, store.tol, store.ocv, SHAPES(k))
    preds = load_predictions()
    frozen = []
    for path in glob.glob(f"{EVID}/refs-b/out/train/frozen.json"):
        frozen += json.load(open(path))
    timing = []
    for path in glob.glob(f"{EVID}/refs-b/out/train/inference_timing.json"):
        timing += json.load(open(path))
    batches = _batch_ids()
    final_ids = _role_ids(refs, "final")
    practice_ids = _role_ids(refs, "practice")
    train_ids = _role_ids(refs, "train")
    res: dict = {"analyzed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "models": {}}

    # 1. Every stored model on every development role (verification stays sealed).
    per = {}
    for tag, p in preds.items():
        per[tag] = {}
        for role, ids in (("train", train_ids), ("practice", practice_ids), ("final", final_ids),
                          *[(f"screen-B{b:02d}", batches[b]) for b in range(len(batches))]):
            err, comp, agg = _case_errors(p, ids, store)
            per[tag][role] = {"err": err, "comp": comp, "agg": agg}
        res["models"][tag] = {role: v["agg"] for role, v in per[tag].items()}

    # 2. Reconstruction variability: seeds and same-seed repeats.
    var = {}
    for rec in ("mlp", "mlp_plus", "mlp_plus_localized"):
        tags = [f"{rec}-s{s}" for s in range(3) if f"{rec}-s{s}" in per]
        if len(tags) < 2:
            continue
        fs = [per[t]["final"]["agg"]["score"] for t in tags]
        pool0 = [float(np.mean([per[t][f"screen-B{b:02d}"]["agg"]["score"] for b in range(3)])) for t in tags]
        var[rec] = {"seeds": tags, "final_scores": fs, "final_sd": float(np.std(fs, ddof=1)),
                    "final_rel_sd": float(np.std(fs, ddof=1) / np.mean(fs)), "pool0_scores": pool0}
        rep = f"{rec}-s0-repeat"
        if rep in preds:
            fz = {f["tag"]: f for f in frozen}
            same = all(preds[rep][c] == preds[f"{rec}-s0"][c] for c in final_ids)
            var[rec]["same_seed_repeat"] = {"params_identical": fz.get(rep, {}).get("params_sha256") ==
                                            fz.get(f"{rec}-s0", {}).get("params_sha256"),
                                            "final_predictions_identical": same}
    res["reconstruction_variability"] = var
    margin = max([v["final_rel_sd"] for v in var.values()] + [0.0]) * 2
    res["equivalence_margin_from_seed_sd"] = margin

    # 3. Screening vs fresh: rank agreement across real trained models.
    real = [t for t in per if not t.endswith("-repeat")]
    for size in SCREEN_SIZES:
        pool = [c for b in batches[:3] for c in b[:size]]
        sc = [exam.evaluate(preds[t], pool, store)[1]["score"] for t in real]
        fr = [per[t]["final"]["agg"]["score"] for t in real]
        res.setdefault("screen_vs_fresh", {})[size] = {"models": real, "screen": sc, "final": fr,
                                                      "kendall_tau": _kendall(sc, fr)}

    # 4. Batch-size reliability for the decision that matters: candidate vs competent baseline, and
    #    equal-quality seeds (which the screen should *not* separate beyond the margin).
    screen_all = [c for b in batches for c in b if c not in twins]
    def errs(tag):
        return exam.evaluate(preds[tag], screen_all, store)[0]
    def vec(rows, ids):
        m = {r["case_id"]: r.get("error") for r in rows}
        return np.array([m[c] for c in ids])
    if all(t in preds for t in ("mlp-s0", "mlp-s1", "mlp_plus-s0")):
        e = {t: errs(t) for t in ("mlp-s0", "mlp-s1", "mlp_plus-s0", "mlp_plus-s1")}
        ok_ids = [c for c in screen_all if all(dict((r["case_id"], r["state"]) for r in e[t])[c] == gates.SCORABLE
                                               for t in e)]
        base = vec(e["mlp-s0"], ok_ids)
        pool_sizes = [3 * s for s in SCREEN_SIZES]
        res["ranking_reliability"] = {
            "candidate_vs_competent": simulate.ranking_reliability(base, vec(e["mlp_plus-s0"], ok_ids), pool_sizes,
                                                                   margin * float(base.mean())),
            "equal_quality_seeds": simulate.ranking_reliability(base, vec(e["mlp-s1"], ok_ids), pool_sizes,
                                                                margin * float(base.mean())),
            "assumption": "pool of 3 x batch size; cases resampled from the 1188 screening cases",
        }
        res["seed_mixing_attack"] = [simulate.seed_mixing_attack(vec(e["mlp_plus-s0"], ok_ids),
                                                                  vec(e["mlp_plus-s1"], ok_ids), n, kk, 30, reps=300)
                                     for n in SCREEN_SIZES for kk in SCHEDULES]

    # 5. Pool replay with rotation: scripted submissions, stored-model inference, pool versions.
    order = ["knn", "mlp-s0", "mlp_plus-s0", "mlp_plus_localized-s0", "LEAK", "mlp-s1", "mlp_plus-s1",
             "mlp_plus_localized-s1", "LEAK", "mlp-s2", "mlp_plus-s2", "mlp_plus_localized-s2"]
    replays = []
    for size in SCREEN_SIZES:
        for kk in SCHEDULES:
            bank = exam.PredictionBank()
            for t in real:
                bank.add(t, preds[t])
            pool = exam.ScreeningPool(batches=batches, rotate_after=kk, batch_size=size)
            n_leak = 0
            for t in order:
                if t == "LEAK":
                    # Authored overfitting control: memorizes the references of the pool it is scored on.
                    n_leak += 1
                    tag = f"pool_leak-{n_leak}"
                    exposed = set(pool.active_case_ids())
                    bank.add(tag, controls.pool_leak(preds["mlp-s0"], refs, exposed))
                    t = tag
                if t not in bank.preds:
                    continue
                pool.score(t, bank, store)
            best = min((h for h in pool.history if h["eligible"]), key=lambda h: h["score"])
            replays.append({"batch_size": size, "rotate_after": kk, "rotations": pool.pool_version,
                            "retired": pool.retired,
                            "history": [{x: h[x] for x in ("model_id", "pool_version", "score", "eligible",
                                                            "important_score")} for h in pool.history],
                            "screen_leader": best["model_id"], "leader_pool_version": best["pool_version"]})
    res["pool_replay"] = replays

    # 6. Controls on the screening pool and on fresh cases.
    ctrl = {}
    pool0 = [c for b in batches[:3] for c in b]
    oracle = controls.oracle(refs, pool0 + final_ids)
    ctrl["oracle"] = exam.evaluate(oracle, pool0, store)[1]
    for f in controls.FAULTS:
        ctrl[f] = exam.evaluate(controls.fault(f, preds["mlp_plus-s0"], store.tol.q_bound, seed=7), pool0, store)[1]
    leak = controls.pool_leak(preds["mlp-s0"], refs, set(pool0))
    ctrl["pool_leak_on_screen"] = exam.evaluate(leak, pool0, store)[1]
    ctrl["pool_leak_on_final"] = exam.evaluate(leak, final_ids, store)[1]
    res["controls"] = ctrl

    # 7. Final comparisons on fresh cases under the development rule (margin from seed variability).
    rule = exam.ComparisonRule(equivalence_margin=margin)
    def avg(rec, role="final"):
        tags = [f"{rec}-s{s}" for s in range(3) if f"{rec}-s{s}" in per]
        return _seed_avg([per[t][role]["err"] for t in tags]), tags
    fin = {}
    inc, _ = avg("mlp")
    imp = {c: store.important(c) for c in final_ids}
    for name, (chal, elig) in {
        "mlp_plus vs mlp": (avg("mlp_plus")[0], True),
        "mlp_plus_localized vs mlp": (avg("mlp_plus_localized")[0], True),
        "knn vs mlp": (per["knn"]["final"]["err"], per["knn"]["final"]["agg"]["eligible"]),
        "mlp seed1 vs mlp seed0 (equal quality)": (per["mlp-s1"]["final"]["err"], True),
        "pool_leak vs mlp (overfitting control)": ({c: e for c, e in _case_errors(leak, final_ids, store)[0].items()},
                                                   True),
    }.items():
        base = per["mlp-s0"]["final"]["err"] if "equal quality" in name or "pool_leak" in name else inc
        fin[name] = exam.final_compare(base, chal, imp, rule, chal_eligible=elig)
    res["final_comparisons_development"] = fin

    # 8. Costs.
    res["timing"] = {"frozen": frozen, "inference": timing}
    t0 = time.perf_counter()
    exam.evaluate(preds["mlp_plus-s0"], pool0, store)
    res["timing"]["gate_and_score_600_cases_s_local"] = time.perf_counter() - t0
    json.dump(res, open(f"{EVID}/analysis.json", "w"), indent=1, default=float)
    print(json.dumps({"models": {t: {r: round(v["score"], 4) if v["score"] else None for r, v in m.items()
                                     if r in ("practice", "final")} for t, m in res["models"].items()},
                      "variability": var, "margin": margin, "final": {n: v["outcome"] for n, v in fin.items()}},
                     indent=1, default=float))


def cmd_photonic(a) -> None:
    """Feasibility summary for the photonic pilot: cost, passivity, reciprocity, refinement."""
    recs = []
    for path in sorted(glob.glob(f"{EVID}/refs-a/out/photonic_refs/records.jsonl")):
        recs += _jsonl(path)
    from scripts.dev.exam_design import photonic_reference as pr

    wls = [str(w) for w in pr.SPEC["wavelengths_um"]]
    rows = []
    for r in recs:
        row = {k: r.get(k) for k in ("case_id", "refined", "status", "wall_total_s", "cells", "sim_time_fs",
                                     "resolution_nm", "gpu_peak_bytes", "error")}
        row["inputs"] = r.get("inputs")
        if r.get("status") == "OK":
            ch = pr.checks(r["S"], wls)
            row["passivity_max_sum"] = max(max(v["sum_power_from_p1"], v["sum_power_from_p3"]) for v in ch.values())
            row["passivity_min_sum"] = min(min(v["sum_power_from_p1"], v["sum_power_from_p3"]) for v in ch.values())
            row["reciprocity_max_abs"] = max(v["reciprocity_31_13"] for v in ch.values())
            s31 = [abs(complex(*r["S"]["p3<-p1"][w])) for w in wls]
            row["reciprocity_max_rel"] = max(v["reciprocity_31_13"] / max(s, 1e-9) for v, s in zip(ch.values(), s31))
            runs = r.get("runs", [])
            row["run_s"] = [x["run_s"] for x in runs]
            row["setup_s"] = [x["setup_s"] for x in runs]
        rows.append(row)
    ref = {}
    for r in recs:
        if r.get("status") == "OK":
            ref.setdefault(r["case_id"], {})["refined" if r.get("refined") else "normal"] = r
    refinement = []
    for cid, d in ref.items():
        if "normal" in d and "refined" in d:
            diffs = []
            for key in d["normal"]["S"]:
                for w in wls:
                    a1 = complex(*d["normal"]["S"][key][w])
                    a2 = complex(*d["refined"]["S"].get(key, {}).get(w, [np.nan, np.nan]))
                    diffs.append(abs(a1 - a2))
            t31 = [abs(complex(*d["refined"]["S"]["p3<-p1"][w])) ** 2 for w in wls]
            refinement.append({"case_id": cid, "max_abs_S_diff": float(np.nanmax(diffs)),
                               "median_abs_S_diff": float(np.nanmedian(diffs)), "refined_T31": t31})
    ok = [r for r in rows if r["status"] == "OK" and not r["refined"]]
    out = {"rows": rows, "refinement": refinement,
           "summary": {"n_ok": len(ok), "n_total": len(rows),
                       "statuses": {s: sum(r["status"] == s for r in rows) for s in {r["status"] for r in rows}},
                       "wall_s_median_normal": float(np.median([r["wall_total_s"] for r in ok])) if ok else None,
                       "passivity_max_sum": max((r["passivity_max_sum"] for r in rows if "passivity_max_sum" in r),
                                                default=None),
                       "reciprocity_max_abs": max((r["reciprocity_max_abs"] for r in rows if "reciprocity_max_abs" in r),
                                                  default=None)}}
    json.dump(out, open(f"{EVID}/photonic_pilot.json", "w"), indent=1, default=float)
    print(json.dumps(out["summary"], indent=1), json.dumps(refinement, indent=1)[:2000])


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    lc = sub.add_parser("learning-curve")
    lc.add_argument("--sizes", type=int, nargs="+", default=[25, 50, 100, 200, 400])
    lc.add_argument("--recipes", nargs="+", default=["knn", "mlp", "mlp_plus"])
    lc.add_argument("--seeds", type=int, default=1)
    tp = sub.add_parser("train-plan")
    tp.add_argument("--n", type=int, required=True)
    sub.add_parser("analyze")
    sub.add_parser("photonic")
    a = ap.parse_args(argv)
    {"prepare": cmd_prepare, "learning-curve": cmd_learning_curve, "train-plan": cmd_train_plan,
     "analyze": cmd_analyze, "photonic": cmd_photonic}[a.cmd](a)


if __name__ == "__main__":
    main()
