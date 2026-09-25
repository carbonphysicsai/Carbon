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
import base64
import glob
import gzip
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np

from scripts.dev.exam_design import exam, gates, plans, recipes, scoring

EVID = "docs/development/evidence/exam-design-2026-09-24"
SHAPES = lambda k: {
    "voltage_v": (121,),
    "temperature_c": (121,),
    "plating_margin_v": (),
    "capacity_ah": (k,),
}


def _jsonl(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt") as f:
        return [json.loads(l) for l in f if l.strip()]


def _write_jsonl_gz(path, rows):
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_refs(pattern: str) -> tuple[dict, dict, list]:
    """Normal references by case id, refined references by case id, and every record (failures kept).

    ``pattern`` names a pod export prefix such as ``refs-a*``; single-phase exports keep records at
    ``out/records.jsonl`` and multi-phase ones at ``out/battery_refs/records.jsonl``. A later OK record
    for a case supersedes an earlier failure; every record is still returned in ``every``.
    """
    normal, refined, every = {}, {}, []
    paths = sorted(
        set(glob.glob(f"{EVID}/{pattern}/out/battery_refs/records.jsonl"))
        | set(glob.glob(f"{EVID}/{pattern}/out/records.jsonl"))
    )
    for path in paths:
        for r in _jsonl(path):
            every.append(r)
            bucket = refined if r.get("refined") else normal
            if r.get("status") == "OK" or r["case_id"] not in bucket:
                bucket[r["case_id"]] = r
    return normal, refined, every


def private_slots() -> dict:
    return json.loads(Path(f"{EVID}/plans/private-slots.json").read_text())


def with_twins(refs: dict) -> tuple[dict, dict]:
    """Add hidden-duplicate case ids; each carries its original's reference unchanged."""
    twins = {}
    for slots in private_slots().values():
        for c in slots:
            if "duplicate_of" in c and c["duplicate_of"] in refs:
                refs[c["case_id"]] = dict(
                    refs[c["duplicate_of"]],
                    case_id=c["case_id"],
                    duplicate_of=c["duplicate_of"],
                )
                twins[c["case_id"]] = c["duplicate_of"]
    return refs, twins


def ocv_map(refs: dict, table: dict) -> dict:
    return {
        cid: float(np.interp(r["inputs"]["soc0"], table["soc"], table["ocv_v"]))
        for cid, r in refs.items()
        if r.get("inputs")
    }


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


def raw_uncertainty_floors(normal: dict, refined: dict) -> dict:
    """Median coarse-vs-refined disagreement per output, in output units (the scale floors)."""
    dv, dt, de, dq, df = [], [], [], [], []
    for cid, f in refined.items():
        c = normal.get(cid)
        if not c or c.get("status") != "OK" or f.get("status") != "OK":
            continue
        a, b = c["outputs"], f["outputs"]
        dv.append(
            float(
                np.sqrt(
                    np.mean((np.array(a["voltage_v"]) - np.array(b["voltage_v"])) ** 2)
                )
            )
        )
        dt.append(
            float(
                np.sqrt(
                    np.mean(
                        (np.array(a["temperature_c"]) - np.array(b["temperature_c"]))
                        ** 2
                    )
                )
            )
        )
        de.append(abs(a["plating_margin_v"] - b["plating_margin_v"]))
        qa, qb = np.array(a["capacity_ah"]), np.array(b["capacity_ah"])
        dq.append(abs(float(qa[0] - qb[0])))
        df.append(float(np.sqrt(np.mean(((qa[0] - qa[1:]) - (qb[0] - qb[1:])) ** 2))))
    if not dv:
        return {}
    return {
        "s_v": float(np.median(dv)),
        "s_t": float(np.median(dt)),
        "s_eta": float(np.median(de)),
        "s_q1": float(np.median(dq)),
        "s_fade": float(np.median(df)),
        "n_pairs": len(dv),
    }


def reference_uncertainty(normal: dict, refined: dict, scales: dict) -> dict:
    """Coarse-vs-refined disagreement per output, raw and in score units."""
    rows = []
    for cid, f in refined.items():
        c = normal.get(cid)
        if not c or c.get("status") != "OK" or f.get("status") != "OK":
            continue
        comp = scoring.case_components(c["outputs"], f, scales)
        rows.append(
            {
                "case_id": cid,
                "components": comp,
                "case_error": scoring.case_error(comp),
                "fade_last_mAh": {
                    "coarse": 1000
                    * (
                        c["outputs"]["capacity_ah"][0] - c["outputs"]["capacity_ah"][-1]
                    ),
                    "refined": 1000
                    * (
                        f["outputs"]["capacity_ah"][0] - f["outputs"]["capacity_ah"][-1]
                    ),
                },
                "plating_margin_diff_v": f["outputs"]["plating_margin_v"]
                - c["outputs"]["plating_margin_v"],
            }
        )
    errs = np.array([r["case_error"] for r in rows]) if rows else np.array([np.nan])
    return {
        "n": len(rows),
        "case_error_median": float(np.median(errs)),
        "case_error_max": float(np.max(errs)),
        "components_median": (
            {
                k: float(np.median([r["components"][k] for r in rows]))
                for k in scoring.COMPONENTS
            }
            if rows
            else None
        ),
        "rows": rows,
    }


def cmd_prepare(a) -> None:
    normal, refined, every = load_refs("refs-a*")
    table = json.loads(Path(f"{EVID}/ocv_table.json").read_text())
    k = len(plans.MAIN_CHECKPOINTS)
    shapes = SHAPES(k)
    by_role: dict[str, list] = {}
    for r in normal.values():
        by_role.setdefault(r["role"], []).append(r)
    train_ok = [
        r
        for r in sorted(by_role["train"], key=lambda r: r["case_id"])
        if r["status"] == "OK"
    ]
    practice_ok = [r for r in by_role.get("practice", []) if r["status"] == "OK"]
    ocv = ocv_map(normal, table)
    tol = gates.calibrate(
        train_ok + practice_ok, ocv, table["capacity_bounds"]["bound_ah"]
    )
    scales = scoring.scales_from_train(
        train_ok, floors=raw_uncertainty_floors(normal, refined)
    )
    self_bad = reference_self_check(normal, tol, ocv, shapes)
    unc = reference_uncertainty(normal, refined, scales)
    os.makedirs(f"{EVID}/datasets", exist_ok=True)
    train_sha = _write_jsonl_gz(
        f"{EVID}/datasets/train-v1-candidates.jsonl.gz", train_ok
    )
    verify = [r for r in by_role.get("verify", [])]
    sealed = hashlib.sha256(
        json.dumps(sorted(verify, key=lambda r: r["case_id"]), sort_keys=True).encode()
    ).hexdigest()
    Path(f"{EVID}/datasets/inputs.json").write_text(json.dumps(plans.inputs_manifest()))
    status = {}
    for r in every:
        key = f'{r.get("role")}{"/refined" if r.get("refined") else ""}'
        status.setdefault(key, {}).setdefault(r["status"], 0)
        status[key][r["status"]] += 1
    walls = [r["wall_total_s"] for r in normal.values() if r["status"] == "OK"]
    out = {
        "prepared_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status_counts": status,
        "tolerances": tol.as_dict(),
        "scales": scales,
        "reference_self_check_failures": self_bad,
        "reference_uncertainty": {k2: v for k2, v in unc.items() if k2 != "rows"},
        "reference_uncertainty_rows": unc["rows"],
        "wall_s": {
            "median": float(np.median(walls)),
            "p90": float(np.quantile(walls, 0.9)),
            "max": float(np.max(walls)),
        },
        "train_candidates_sha256": train_sha,
        "n_train_ok": len(train_ok),
        "verify_sealed": {
            "n": len(verify),
            "sha256": sealed,
            "note": "verification references are not read until the freeze record is committed",
        },
    }
    Path(f"{EVID}/prepare.json").write_text(json.dumps(out, indent=1))
    print(
        json.dumps(
            {
                k2: out[k2]
                for k2 in (
                    "status_counts",
                    "tolerances",
                    "wall_s",
                    "n_train_ok",
                    "verify_sealed",
                )
            },
            indent=1,
        )
    )
    print("reference uncertainty", json.dumps(out["reference_uncertainty"]))


def _structure():
    t = json.loads(Path(f"{EVID}/ocv_table.json").read_text())
    return recipes.Structure(t["soc"], t["ocv_v"])


def _store(refs, twins, prep, k):
    table = json.loads(Path(f"{EVID}/ocv_table.json").read_text())
    tol = gates.Tolerances(
        **{
            x: prep["tolerances"][x]
            for x in (
                "tau_v0",
                "tau_t0",
                "tau_vmax",
                "tau_vmin",
                "q_bound",
                "v_max",
                "v_min",
            )
        }
    )
    return exam.CaseStore(
        refs, ocv_map(refs, table), tol, prep["scales"], SHAPES(k), twins
    )


def cmd_learning_curve(a) -> None:
    """Local CPU study on PRACTICE (public): how much TRAIN is a useful starting point?"""
    prep = json.loads(Path(f"{EVID}/prepare.json").read_text())
    normal, _, _ = load_refs("refs-a*")
    train = _jsonl(f"{EVID}/datasets/train-v1-candidates.jsonl.gz")
    practice = sorted(
        [r for r in normal.values() if r["role"] == "practice" and r["status"] == "OK"],
        key=lambda r: r["case_id"],
    )
    store = _store(normal, {}, prep, len(plans.MAIN_CHECKPOINTS))
    x = np.array(
        [[r["inputs"][k] for k in ("c1", "c2", "t_amb_c", "soc0")] for r in practice]
    )
    ids = [r["case_id"] for r in practice]
    rows = []
    for n in a.sizes:
        d = recipes.Data.from_records(train[:n], scoring.is_important)
        for name in a.recipes:
            for seed in (range(a.seeds) if name != "knn" else [0]):
                m = recipes.make(name)
                t0 = time.perf_counter()
                m.fit(d, _structure(), seed=seed)
                preds = recipes.to_preds(m.predict(x), ids)
                _, agg = exam.evaluate(preds, ids, store)
                rows.append(
                    {
                        "recipe": name,
                        "n_train": n,
                        "seed": seed,
                        "fit_s": time.perf_counter() - t0,
                        "score": agg["score"],
                        "important_score": agg["important_score"],
                        "eligible": agg["eligible"],
                        "gate_failures": agg["gate_failures"],
                        "components": agg["components"],
                    }
                )
                print(json.dumps(rows[-1]), flush=True)
    Path(f"{EVID}/learning_curve.json").write_text(
        json.dumps(
            {
                "host": "development container (CPU); diagnostic, not A40 evidence",
                "practice_n": len(ids),
                "rows": rows,
            },
            indent=1,
        )
    )


def cmd_train_plan(a) -> None:
    train = _jsonl(f"{EVID}/datasets/train-v1-candidates.jsonl.gz")[: a.n]
    sha = _write_jsonl_gz(f"{EVID}/datasets/train-v1.jsonl.gz", train)
    important = [r["case_id"] for r in train if scoring.is_important(r)]
    # Public-seed roles are offline development evidence; exam roles are private (carbon.seeding root).
    roles = (
        ["train", "practice", "final", "verify"]
        + [f"pscreen-B{b:02d}" for b in range(plans.SCREEN_BATCHES)]
        + ["pfinal", "pverify"]
    )
    runs = [
        {
            "tag": "knn",
            "recipe": "knn",
            "seed": 0,
            "train_n": a.n,
            "predict_roles": roles,
        }
    ]
    for rec in ("mlp_half", "mlp", "mlp_ens3", "mlp_plus", "mlp_localized"):
        for s in range(3):
            runs.append(
                {
                    "tag": f"{rec}-s{s}",
                    "recipe": rec,
                    "seed": s,
                    "train_n": a.n,
                    "predict_roles": roles,
                }
            )
    for rec in ("mlp", "mlp_plus"):
        runs.append(
            {
                "tag": f"{rec}-s0-repeat",
                "recipe": rec,
                "seed": 0,
                "train_n": a.n,
                "predict_roles": roles,
            }
        )
    # Unconstrained voltage head: measures what the voltage_ceiling gate rejects (not a candidate).
    runs.append(
        {
            "tag": "mlp_raw-s0",
            "recipe": "mlp_raw",
            "seed": 0,
            "train_n": a.n,
            "predict_roles": roles,
        }
    )
    plan = {
        "plan": "battery-reconstruct-v1",
        "train_file": f"{EVID}/datasets/train-v1.jsonl.gz",
        "train_sha256": sha,
        "ocv_table": f"{EVID}/ocv_table.json",
        "inputs_file": f"{EVID}/datasets/inputs.json",
        "important_train_ids": important,
        "runs": runs,
        "private_blob": "scripts/dev/exam_design/private/refs-b-v1.bin",
        "private_slots": f"{EVID}/plans/private-slots.json",
    }
    Path(f"{EVID}/plans/reconstruct-v1.json").write_text(json.dumps(plan, indent=1))
    print(
        json.dumps(
            {
                "n_train": a.n,
                "runs": len(runs),
                "train_sha256": sha,
                "important": len(important),
            }
        )
    )


# --------------------------------------------------------------------------- analysis

SCREEN_SIZES = (50, 100, 200)
SCHEDULES = (1, 3, 10)


def _all_refs():
    normal, refined, every = load_refs("refs-*")
    return with_twins(normal) + (refined, every)


def load_predictions(pattern: str | None = None) -> dict:
    out = {}
    for path in sorted(glob.glob(pattern or f"{EVID}/refs-b/out/train/pred_*.json.gz")):
        tag = os.path.basename(path)[len("pred_") : -len(".json.gz")]
        with gzip.open(path, "rt") as f:
            out[tag] = json.load(f)
    return out


def _role_ids(refs: dict, role: str) -> list:
    return sorted(
        c for c, r in refs.items() if r.get("role") == role and not r.get("refined")
    )


def _batch_ids() -> list[list[str]]:
    """Private screening batches (pscreen-B00..), in entry order, including their hidden duplicates."""
    sl = private_slots()
    return [
        [c["case_id"] for c in sl[f"pscreen-B{b:02d}"]]
        for b in range(plans.SCREEN_BATCHES)
    ]


def _case_errors(preds: dict, ids: list, store) -> tuple[dict, dict, dict]:
    rows, agg = exam.evaluate(preds, ids, store)
    err = {r["case_id"]: r["error"] for r in rows if r["state"] == gates.SCORABLE}
    comp = {r["case_id"]: r["components"] for r in rows if r["state"] == gates.SCORABLE}
    return err, comp, agg


def _seed_avg(errs: list[dict]) -> dict:
    common = set.intersection(*[set(e) for e in errs])
    return {c: float(np.mean([e[c] for e in errs])) for c in common}


def _kendall(a: list, b: list) -> float | None:
    keep = [i for i in range(len(a)) if a[i] is not None and b[i] is not None]
    a, b = [a[i] for i in keep], [b[i] for i in keep]
    if len(a) < 3:
        return None
    n, s = len(a), 0
    for i in range(n):
        for j in range(i + 1, n):
            s += np.sign(a[i] - a[j]) * np.sign(b[i] - b[j])
    return float(s / (n * (n - 1) / 2))


REAL = [
    "knn",
    "mlp_half-s0",
    "mlp_half-s1",
    "mlp_half-s2",
    "mlp-s0",
    "mlp-s1",
    "mlp-s2",
    "mlp_ens3-s0",
    "mlp_ens3-s1",
    "mlp_ens3-s2",
    "mlp_plus-s0",
    "mlp_plus-s1",
    "mlp_plus-s2",
    "mlp_localized-s0",
    "mlp_localized-s1",
    "mlp_localized-s2",
]
ORDER = [
    "knn",
    "mlp_half-s0",
    "mlp-s0",
    "mlp_plus-s0",
    "LEAK",
    "mlp_ens3-s0",
    "mlp_localized-s0",
    "mlp_half-s1",
    "mlp-s1",
    "LEAK",
    "mlp_plus-s1",
    "mlp_ens3-s1",
    "mlp_localized-s1",
    "mlp-s2",
    "mlp_ens3-s2",
    "LEAK",
    "mlp_plus-s2",
    "mlp_localized-s2",
]


def _truth(per_err: dict, a: str, b: str, ids: list, margin_rel: float) -> dict:
    """Large-sample truth for 'b vs a' on ids (mean paired difference; positive = b worse)."""
    common = [c for c in ids if c in per_err[a] and c in per_err[b]]
    d = np.array([per_err[b][c] - per_err[a][c] for c in common])
    base = float(np.mean([per_err[a][c] for c in common]))
    se = float(d.std(ddof=1) / np.sqrt(d.size))
    m = margin_rel * base
    lab = (
        "better"
        if d.mean() < -m and d.mean() + 2 * se < 0
        else (
            "worse"
            if d.mean() > m and d.mean() - 2 * se > 0
            else "equivalent" if abs(d.mean()) + 2 * se <= m else "unclear"
        )
    )
    return {
        "mean_delta": float(d.mean()),
        "se": se,
        "rel": float(d.mean() / base),
        "label": lab,
        "n": len(common),
    }


def cmd_analyze(a) -> None:
    from scripts.dev.exam_design import controls, simulate

    prep = json.loads(Path(f"{EVID}/prepare.json").read_text())
    refs, twins, _refined, _every = _all_refs()
    k = len(plans.MAIN_CHECKPOINTS)
    store = _store(refs, twins, prep, k)
    reference_self_check(refs, store.tol, store.ocv, SHAPES(k))
    preds = load_predictions()
    frozen = json.loads(Path(f"{EVID}/refs-b/out/train/frozen.json").read_text())
    timing = json.loads(
        Path(f"{EVID}/refs-b/out/train/inference_timing.json").read_text()
    )
    batches = _batch_ids()
    ids = {
        r: _role_ids(refs, r)
        for r in ("train", "practice", "final", "verify", "pfinal")
    }
    screen_all = [c for bt in batches for c in bt if c not in twins]
    truth_ids = (
        ids["practice"] + ids["final"] + ids["verify"] + screen_all
    )  # never pfinal / pverify
    res: dict = {
        "analyzed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "models": {},
    }

    # 1. Every model on every development role, gates and scores from the same stored predictions.
    per_err, per_comp = {}, {}
    everything = sorted(
        set(
            truth_ids + ids["pfinal"] + ids["train"] + [c for bt in batches for c in bt]
        )
    )
    for tag, p in preds.items():
        rows, _ = exam.evaluate(p, everything, store)
        per_err[tag] = {
            r["case_id"]: r["error"] for r in rows if r["state"] == gates.SCORABLE
        }
        per_comp[tag] = {
            r["case_id"]: r["components"] for r in rows if r["state"] == gates.SCORABLE
        }
        res["models"][tag] = {}
        for role, rid in (
            ("train", ids["train"]),
            ("practice", ids["practice"]),
            ("dev_final", ids["final"]),
            ("pfinal", ids["pfinal"]),
            ("pool0_200", [c for bt in batches[:3] for c in bt]),
        ):
            res["models"][tag][role] = exam.evaluate(p, rid, store)[1]
    # 2. Reconstruction variability.
    var = {}
    fz = {f["tag"]: f for f in frozen}
    for rec in ("mlp_half", "mlp", "mlp_ens3", "mlp_plus", "mlp_localized"):
        tags = [f"{rec}-s{i}" for i in range(3) if f"{rec}-s{i}" in preds]
        truth_scores = [
            float(np.mean([per_err[t][c] for c in truth_ids if c in per_err[t]]))
            for t in tags
        ]
        var[rec] = {
            "tags": tags,
            "truth_scores": truth_scores,
            "sd": float(np.std(truth_scores, ddof=1)),
            "rel_sd": float(np.std(truth_scores, ddof=1) / np.mean(truth_scores)),
            "fit_s": [fz[t].get("fit_wall_s") for t in tags],
        }
        rep = f"{rec}-s0-repeat"
        if rep in preds:
            var[rec]["same_seed_repeat"] = {
                "params_identical": fz[rep]["params_sha256"]
                == fz[f"{rec}-s0"]["params_sha256"],
                "predictions_identical": all(
                    preds[rep][c] == preds[f"{rec}-s0"][c] for c in preds[rep]
                ),
            }
    res["reconstruction_variability"] = var
    margin = 2 * max(v["rel_sd"] for v in var.values())
    res["equivalence_margin"] = {
        "relative": margin,
        "rule": "2 x the largest seed-to-seed relative SD of the "
        "large-sample score among the reconstructed recipes",
    }
    # 3. Large-sample truth for the decisions the exam must make (development roles only).
    pairs = [
        ("mlp_half-s0", "mlp-s0"),
        ("mlp-s0", "mlp_ens3-s0"),
        ("mlp-s0", "mlp_plus-s0"),
        ("mlp-s0", "mlp_localized-s0"),
        ("mlp-s0", "mlp-s1"),
        ("knn", "mlp-s0"),
    ]
    imp_truth = [c for c in truth_ids if store.important(c)]
    res["truth"] = {
        f"{b} vs {a_}": {
            "overall": _truth(per_err, a_, b, truth_ids, margin),
            "important": _truth(per_err, a_, b, imp_truth, margin),
        }
        for a_, b in pairs
    }
    # 4. Screening vs fresh agreement across real models (rank correlation), per batch size.
    for size in (50, 100, 200):
        pool = [c for bt in batches[:3] for c in bt[:size]]
        sc = [exam.evaluate(preds[t], pool, store)[1]["score"] for t in REAL]
        fr = [
            float(np.mean([per_err[t][c] for c in ids["pfinal"] if c in per_err[t]]))
            for t in REAL
        ]
        tr = [
            float(np.mean([per_err[t][c] for c in truth_ids if c in per_err[t]]))
            for t in REAL
        ]
        res.setdefault("screen_vs_fresh", {})[size] = {
            "kendall_screen_vs_pfinal": _kendall(sc, fr),
            "kendall_screen_vs_truth": _kendall(sc, tr),
            "screen": dict(zip(REAL, sc)),
            "pfinal": dict(zip(REAL, fr)),
        }
    # 5. Controls: gates on authored faults, oracle, pool leak, unconstrained head.
    pool0 = [c for bt in batches[:3] for c in bt]
    ctrl = {"oracle": exam.evaluate(controls.oracle(refs, pool0), pool0, store)[1]}
    for f, g in controls.FAULTS.items():
        ctrl[f] = exam.evaluate(
            controls.fault(f, preds["mlp-s0"], store.tol.q_bound, seed=7), pool0, store
        )[1] | {"expected_gate": g}
    if "mlp_raw-s0" in preds:
        ctrl["mlp_raw"] = exam.evaluate(preds["mlp_raw-s0"], pool0, store)[1]
    res["controls"] = ctrl
    # 6. The exam loop, replayed: screening -> nomination -> frozen final comparison -> promotion.
    rule = exam.ComparisonRule(equivalence_margin=margin)
    loops = []
    for size in (50, 100, 200):
        for kk in (1, 3, 10):
            bank = exam.PredictionBank()
            for t in REAL:
                bank.add(t, preds[t])
            pool = exam.ScreeningPool(batches=batches, rotate_after=kk, batch_size=size)
            incumbent, events, n_leak = None, [], 0
            for t in ORDER:
                if t == "LEAK":
                    n_leak += 1
                    t = f"pool_leak-{n_leak}"
                    base = incumbent or "mlp-s0"
                    bank.add(
                        t,
                        controls.pool_leak(
                            preds[base], refs, set(pool.active_case_ids())
                        ),
                    )
                    per_err.setdefault(
                        t, per_err[base]
                    )  # fresh-case truth = its base model (it learned nothing)
                pv = pool.pool_version
                rec = pool.score(t, bank, store)
                inc_rec = None
                if incumbent:
                    ids_now = (
                        pool.active_case_ids() if pool.pool_version == pv else None
                    )
                    ids_now = [
                        c
                        for bt in [pool.batches[b] for b in rec["active_batches"]]
                        for c in (bt[:size])
                    ]
                    _, inc_agg = exam.evaluate(
                        bank.ensure(incumbent, ids_now), ids_now, store
                    )
                    inc_rec = {**inc_agg, "pool_version": rec["pool_version"]}
                ok, why = exam.nominate(rec, inc_rec, margin)
                ev = {
                    "submission": t,
                    "pool_version": rec["pool_version"],
                    "score": rec["score"],
                    "eligible": rec["eligible"],
                    "nominated": ok,
                    "why": why,
                }
                if ok and incumbent is None:
                    incumbent = t
                    ev["promoted"] = "first eligible incumbent"
                elif ok:
                    fin = exam.final_compare(
                        {
                            c: e
                            for c, e in per_err[incumbent].items()
                            if c in ids["pfinal"]
                        },
                        {
                            c: e
                            for c, e in (
                                per_err[t]
                                if not t.startswith("pool_leak")
                                else _case_errors(bank.preds[t], ids["pfinal"], store)[
                                    0
                                ]
                            ).items()
                            if c in ids["pfinal"]
                        },
                        {c: store.important(c) for c in ids["pfinal"]},
                        rule,
                    )
                    ev["final"] = {
                        x: fin.get(x)
                        for x in (
                            "outcome",
                            "reason",
                            "promotable",
                            "mean_delta",
                            "ci",
                            "important",
                            "overall",
                        )
                    }
                    base_t = t if not t.startswith("pool_leak") else incumbent
                    ev["truth_vs_incumbent"] = _truth(
                        per_err, incumbent, base_t, truth_ids, margin
                    )["label"]
                    if fin["promotable"]:
                        ev["promoted"] = f"replaces {incumbent}"
                        incumbent = t
                events.append(ev)
            loops.append(
                {
                    "batch_size": size,
                    "rotate_after": kk,
                    "rotations": pool.pool_version,
                    "events": events,
                    "final_incumbent": incumbent,
                }
            )
    res["exam_loop"] = loops
    # 7. Detection power and false promotion on real paired errors + authored controlled improvements.
    base_ids = [
        c for c in screen_all if c in per_err["mlp-s0"] and c in per_err["mlp-s1"]
    ]
    e0 = np.array([per_err["mlp-s0"][c] for c in base_ids])
    e1 = np.array([per_err["mlp-s1"][c] for c in base_ids])
    res["ranking_reliability"] = {
        "equal_quality_seeds": simulate.ranking_reliability(
            e0, e1, [150, 300, 600], margin * float(e0.mean())
        ),
        "real_improvement_half_to_full": simulate.ranking_reliability(
            np.array([per_err["mlp_half-s0"][c] for c in base_ids]),
            e0,
            [150, 300, 600],
            margin * float(e0.mean()),
        ),
        "authored_improvements": {
            str(alpha): simulate.ranking_reliability(
                e0, (1 - alpha) * e0, [150, 300, 600], margin * float(e0.mean())
            )
            for alpha in (0.02, 0.05, 0.1, 0.2)
        },
        "note": "pool sizes are 3 x batch size; authored improvements scale the incumbent's per-case error by (1-alpha): "
        "synthetic controls with a known true effect, not trained models",
    }
    res["seed_mixing_attack"] = [
        simulate.seed_mixing_attack(e0, e1, n, kk, 30, reps=300)
        for n in (50, 100, 200)
        for kk in (1, 3, 10)
    ]
    # 8. Costs (measured).
    t0 = time.perf_counter()
    exam.evaluate(preds["mlp-s0"], pool0, store)
    res["cost_inputs"] = {
        "frozen": frozen,
        "inference": timing,
        "gate_and_score_600_cases_s_local": time.perf_counter() - t0,
    }
    Path(f"{EVID}/analysis.json").write_text(json.dumps(res, indent=1, default=float))
    print(
        json.dumps(
            {
                "variability": {
                    r: {k2: v[k2] for k2 in ("truth_scores", "rel_sd")}
                    for r, v in var.items()
                },
                "margin": margin,
                "truth": {
                    k2: (
                        v["overall"]["label"],
                        round(v["overall"]["rel"], 3),
                        v["important"]["label"],
                    )
                    for k2, v in res["truth"].items()
                },
                "screen_vs_fresh": {
                    s2: round(v["kendall_screen_vs_pfinal"], 3)
                    for s2, v in res["screen_vs_fresh"].items()
                },
            },
            indent=1,
            default=float,
        )
    )


def cmd_photonic(a) -> None:
    """Feasibility summary for the photonic pilot: cost, passivity, reciprocity, refinement."""
    recs = []
    for path in sorted(glob.glob(f"{EVID}/refs-a/out/photonic_refs/records.jsonl")):
        recs += _jsonl(path)
    from scripts.dev.exam_design import photonic_reference as pr

    wls = [str(w) for w in pr.SPEC["wavelengths_um"]]
    rows = []
    for r in recs:
        row = {
            k: r.get(k)
            for k in (
                "case_id",
                "refined",
                "status",
                "wall_total_s",
                "cells",
                "sim_time_fs",
                "resolution_nm",
                "gpu_peak_bytes",
                "error",
            )
        }
        row["inputs"] = r.get("inputs")
        if r.get("status") == "OK":
            ch = pr.checks(r["S"], wls)
            row["passivity_max_sum"] = max(
                max(v["sum_power_from_p1"], v["sum_power_from_p3"]) for v in ch.values()
            )
            row["passivity_min_sum"] = min(
                min(v["sum_power_from_p1"], v["sum_power_from_p3"]) for v in ch.values()
            )
            row["reciprocity_max_abs"] = max(
                v["reciprocity_31_13"] for v in ch.values()
            )
            s31 = [abs(complex(*r["S"]["p3<-p1"][w])) for w in wls]
            row["reciprocity_max_rel"] = max(
                v["reciprocity_31_13"] / max(s, 1e-9) for v, s in zip(ch.values(), s31)
            )
            runs = r.get("runs", [])
            row["run_s"] = [x["run_s"] for x in runs]
            row["setup_s"] = [x["setup_s"] for x in runs]
        rows.append(row)
    ref = {}
    for r in recs:
        if r.get("status") == "OK":
            ref.setdefault(r["case_id"], {})[
                "refined" if r.get("refined") else "normal"
            ] = r
    refinement = []
    for cid, d in ref.items():
        if "normal" in d and "refined" in d:
            diffs = []
            for key in d["normal"]["S"]:
                for w in wls:
                    a1 = complex(*d["normal"]["S"][key][w])
                    a2 = complex(
                        *d["refined"]["S"].get(key, {}).get(w, [np.nan, np.nan])
                    )
                    diffs.append(abs(a1 - a2))
            t31 = [abs(complex(*d["refined"]["S"]["p3<-p1"][w])) ** 2 for w in wls]
            refinement.append(
                {
                    "case_id": cid,
                    "max_abs_S_diff": float(np.nanmax(diffs)),
                    "median_abs_S_diff": float(np.nanmedian(diffs)),
                    "refined_T31": t31,
                }
            )
    ok = [r for r in rows if r["status"] == "OK" and not r["refined"]]
    out = {
        "rows": rows,
        "refinement": refinement,
        "summary": {
            "n_ok": len(ok),
            "n_total": len(rows),
            "statuses": {
                s: sum(r["status"] == s for r in rows)
                for s in {r["status"] for r in rows}
            },
            "wall_s_median_normal": (
                float(np.median([r["wall_total_s"] for r in ok])) if ok else None
            ),
            "passivity_max_sum": max(
                (r["passivity_max_sum"] for r in rows if "passivity_max_sum" in r),
                default=None,
            ),
            "reciprocity_max_abs": max(
                (r["reciprocity_max_abs"] for r in rows if "reciprocity_max_abs" in r),
                default=None,
            ),
        },
    }
    Path(f"{EVID}/photonic_pilot.json").write_text(
        json.dumps(out, indent=1, default=float)
    )
    print(json.dumps(out["summary"], indent=1), json.dumps(refinement, indent=1)[:2000])


FREEZE = f"{EVID}/freeze.json"
CRITERIA = [
    {
        "id": "V1",
        "comparison": ["mlp-s0", "mlp-s1"],
        "expect_not_promotable": True,
        "text": "equal-quality control (another seed of the incumbent recipe) is not promoted",
    },
    {
        "id": "V2",
        "faults": True,
        "text": "every authored fault fires its expected gate on the verification cases",
    },
    {
        "id": "V3",
        "comparison": ["mlp_half-s0", "mlp-s0"],
        "expect_outcome": "IMPROVEMENT",
        "text": "the real improvement (full-TRAIN recipe over the half-TRAIN recipe) is promoted",
    },
    {
        "id": "V4",
        "comparison": ["mlp-s0", "mlp_plus-s0"],
        "expect_outcome": "REGRESSION",
        "text": "the intended improvement that regressed in development is classified as a regression",
    },
    {
        "id": "V5",
        "comparison": ["mlp-s0", "mlp_localized-s0"],
        "expect_not_promotable": True,
        "text": "the localized-regression control is not promoted",
    },
    {
        "id": "V6",
        "leak": True,
        "expect_not_promotable": True,
        "text": "a candidate that memorized screening references is not promoted on fresh verification cases",
    },
    {
        "id": "V7",
        "oracle": True,
        "text": "the reference itself passes every gate on every valid verification case",
    },
    {
        "id": "R1",
        "comparison": ["mlp-s0", "mlp_ens3-s0"],
        "report_only": True,
        "text": "small candidate (3-ensemble): outcome reported, no pass criterion",
    },
]


def _write_once(path: str, obj) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=1, default=float)


def cmd_freeze(a) -> None:
    """Record the exam rule and verification criteria BEFORE the private verification set is read."""
    an = json.loads(Path(f"{EVID}/analysis.json").read_text())
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    code = {
        p: digest(p)
        for p in (
            "scripts/dev/exam_design/gates.py",
            "scripts/dev/exam_design/scoring.py",
            "scripts/dev/exam_design/exam.py",
            "scripts/dev/exam_design/controls.py",
        )
    }
    rec = {
        "schema": "carbon.exam-design.freeze.v1",
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "settings": {
            "batch_size": a.batch_size,
            "rotate_after": a.rotate_after,
            "active_batches": 3,
            "train_v1_n": 400,
            "equivalence_margin_rel": an["equivalence_margin"]["relative"],
            "comparison_rule": {
                "n_min": 30,
                "n_boot": 4000,
                "alpha": 0.05,
                "important_min": 10,
            },
            "important_region": {
                "plating_band_v": scoring.PLATING_BAND_V,
                "t_important_c": scoring.T_IMPORTANT_C,
            },
            "reconstruction": "single reconstruction per side (seed 0), matched budget, pinned XLA",
        },
        "rationale": a.rationale,
        "code_sha256": code,
        "prepare_sha256": digest(f"{EVID}/prepare.json"),
        "analysis_sha256": digest(f"{EVID}/analysis.json"),
        "criteria": CRITERIA,
        "verification_set": {
            "role": "pverify",
            "source": "private (carbon.seeding root; see private_commitment.json)",
            "rule_change_policy": "if any setting or criterion changes after verification opens, this "
            "verification becomes development evidence and a fresh set is required",
        },
    }
    _write_once(FREEZE, rec)
    print(json.dumps(rec["settings"], indent=1))


def _freeze_committed() -> dict:
    ok = (
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", FREEZE],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    clean = (
        subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", FREEZE], check=False
        ).returncode
        == 0
    )
    if not (ok and clean):
        raise SystemExit(
            "refusing: the freeze record must be committed, unmodified, before verification opens"
        )
    return json.loads(Path(FREEZE).read_text())


def cmd_verify(a) -> None:
    from scripts.dev.exam_design import controls

    fr = _freeze_committed()
    prep = json.loads(Path(f"{EVID}/prepare.json").read_text())
    refs, twins, _, _ = _all_refs()
    store = _store(refs, twins, prep, len(plans.MAIN_CHECKPOINTS))
    preds = load_predictions()
    vids = _role_ids(refs, "pverify")
    rule = exam.ComparisonRule(
        equivalence_margin=fr["settings"]["equivalence_margin_rel"]
    )
    imp = {c: store.important(c) for c in vids}
    errs = {t: _case_errors(p, vids, store) for t, p in preds.items()}
    out = {
        "verified_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_cases": len(vids),
        "freeze_sha256": hashlib.sha256(Path(FREEZE).read_bytes()).hexdigest(),
        "results": [],
    }
    for crit in fr["criteria"]:
        r = {"id": crit["id"], "text": crit["text"]}
        if "comparison" in crit:
            inc, ch = crit["comparison"]
            fin = exam.final_compare(
                errs[inc][0],
                errs[ch][0],
                imp,
                rule,
                chal_eligible=errs[ch][2]["eligible"],
                inc_components=errs[inc][1],
                chal_components=errs[ch][1],
            )
            r["outcome"] = {
                x: fin.get(x)
                for x in (
                    "outcome",
                    "reason",
                    "promotable",
                    "mean_delta",
                    "ci",
                    "overall",
                    "important",
                    "important_ci",
                    "n_important",
                    "components",
                )
            }
            if "expect_outcome" in crit:
                r["pass"] = fin["outcome"] == crit["expect_outcome"]
            elif crit.get("expect_not_promotable"):
                r["pass"] = not fin["promotable"]
            else:
                r["pass"] = None
        elif crit.get("faults"):
            fired = {}
            for f, g in controls.FAULTS.items():
                agg = exam.evaluate(
                    controls.fault(f, preds["mlp-s0"], store.tol.q_bound, seed=11),
                    vids,
                    store,
                )[1]
                fired[f] = {
                    "expected": g,
                    "gate_failures": agg["gate_failures"],
                    "eligible": agg["eligible"],
                }
            # nondeterminism needs a hidden duplicate; the verification set has none, so it is NOT_APPLICABLE here.
            r["faults"] = fired
            r["pass"] = all(
                (
                    (v["expected"] in v["gate_failures"])
                    if v["expected"] and v["expected"] != "paired_repeat"
                    else True
                )
                for v in fired.values()
            )
        elif crit.get("leak"):
            leak = controls.pool_leak(
                preds["mlp-s0"], refs, {c for bt in _batch_ids() for c in bt}
            )
            le = _case_errors(leak, vids, store)
            fin = exam.final_compare(errs["mlp-s0"][0], le[0], imp, rule)
            r["outcome"] = {
                x: fin.get(x) for x in ("outcome", "promotable", "mean_delta")
            }
            r["pass"] = not fin["promotable"]
        elif crit.get("oracle"):
            agg = exam.evaluate(controls.oracle(refs, vids), vids, store)[1]
            r["gate_failures"] = agg["gate_failures"]
            r["pass"] = agg["n_gate_failed"] == 0
        out["results"].append(r)
    Path(f"{EVID}/verification.json").write_text(
        json.dumps(out, indent=1, default=float)
    )
    print(
        json.dumps(
            [
                {k: v for k, v in r.items() if k in ("id", "pass")}
                | ({"outcome": r["outcome"]["outcome"]} if "outcome" in r else {})
                for r in out["results"]
            ],
            indent=1,
        )
    )


DECISION_MODELS = [
    "knn",
    "mlp_half-s0",
    "mlp-s0",
    "mlp-s1",
    "mlp_ens3-s0",
    "mlp_plus-s0",
    "mlp_localized-s0",
    "mlp_raw-s0",
]


RETAINED_FORMAT = "carbon-exam-design-f32-v1"
RETAINED_ARRAYS = ("voltage_v", "temperature_c", "plating_margin_v", "capacity_ah")


def write_retained(path: str, case_ids: list[str], arrays: dict) -> None:
    """Write float32 arrays losslessly as base64 little-endian bytes in deterministic gzip JSON.

    The repository forbids committed NumPy payloads, so retained predictions use this plain format.
    """
    doc = {
        "format": RETAINED_FORMAT,
        "case_ids": list(case_ids),
        "arrays": {
            k: {
                "shape": list(v.shape),
                "le_f32_b64": base64.b64encode(
                    np.ascontiguousarray(v, dtype="<f4").tobytes()
                ).decode("ascii"),
            }
            for k, v in arrays.items()
        },
    }
    with (
        open(path, "wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as f,
    ):
        f.write(json.dumps(doc, sort_keys=True).encode())


def read_retained(path: str) -> tuple[list[str], dict]:
    """Inverse of ``write_retained``: case ids and float32 arrays, bit-exact."""
    with gzip.open(path, "rt") as f:
        doc = json.load(f)
    if doc.get("format") != RETAINED_FORMAT:
        raise ValueError(f"unsupported retained prediction format: {doc.get('format')}")
    arrays = {
        k: np.frombuffer(base64.b64decode(v["le_f32_b64"]), dtype="<f4").reshape(
            v["shape"]
        )
        for k, v in doc["arrays"].items()
    }
    return doc["case_ids"], arrays


def cmd_retain(a) -> None:
    """Retain predictions compactly: full float32 arrays for decision models, a per-case score table for all.

    Every prediction is regenerable bit-for-bit (same-seed reconstruction under the pinned configuration was
    measured identical), so the repository keeps what a reviewer needs to check decisions without the
    regenerable bulk; the original export digests are recorded.
    """
    src = f"{EVID}/refs-b/out/train"
    dst = f"{EVID}/predictions"
    os.makedirs(dst, exist_ok=True)
    prep = json.loads(Path(f"{EVID}/prepare.json").read_text())
    refs, twins, _, _ = _all_refs()
    store = _store(refs, twins, prep, len(plans.MAIN_CHECKPOINTS))
    manifest, table = {}, {}
    for path in sorted(glob.glob(f"{src}/pred_*.json.gz")):
        tag = os.path.basename(path)[len("pred_") : -len(".json.gz")]
        with gzip.open(path, "rt") as f:
            d = json.load(f)
        ids = sorted(d)
        manifest[tag] = {
            "export_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "n": len(ids),
            "full_predictions_retained": tag in DECISION_MODELS,
        }
        if tag in DECISION_MODELS:
            arr = lambda k, d=d, ids=ids: np.array(
                [d[c][k] for c in ids], dtype=np.float32
            )
            write_retained(
                f"{dst}/{tag}.f32.json.gz",
                ids,
                {k: arr(k) for k in RETAINED_ARRAYS},
            )
        rows, _ = exam.evaluate(d, [c for c in ids if c in refs], store)
        table[tag] = {
            r["case_id"]: [
                r["state"],
                round(r.get("error", float("nan")), 6),
                [g for g, v in r.get("gates", {}).items() if v == "FAIL"],
            ]
            for r in rows
        }
    Path(f"{dst}/manifest.json").write_text(json.dumps(manifest, indent=1))
    with gzip.open(f"{dst}/case_scores.json.gz", "wt") as f:
        json.dump(table, f)
    print(json.dumps({t: m["full_predictions_retained"] for t, m in manifest.items()}))


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
    fz = sub.add_parser("freeze")
    fz.add_argument("--batch-size", type=int, required=True)
    fz.add_argument("--rotate-after", type=int, required=True)
    fz.add_argument("--rationale", required=True)
    sub.add_parser("verify")
    sub.add_parser("retain")
    a = ap.parse_args(argv)
    {
        "prepare": cmd_prepare,
        "learning-curve": cmd_learning_curve,
        "train-plan": cmd_train_plan,
        "analyze": cmd_analyze,
        "photonic": cmd_photonic,
        "freeze": cmd_freeze,
        "verify": cmd_verify,
        "retain": cmd_retain,
    }[a.cmd](a)


if __name__ == "__main__":
    main()
