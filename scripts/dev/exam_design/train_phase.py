"""Reconstruction phase: train recipes on TRAIN v1, freeze, then predict.

Data boundary, enforced by what is loaded and when:

1. Only the TRAIN reference file is read before training. It carries inputs and
   reference outputs for TRAIN v1 cases, nothing else.
2. After each fit, the parameter digest is recorded (``frozen``) *before* any
   non-TRAIN input is read.
3. Predictions are made from the **inputs-only** file: screening, final and
   verification inputs never arrive with their references, and the pod never
   holds a non-TRAIN reference. Scoring happens off the pod.

Each run records compile, train and per-role inference seconds, so the cost of a
reconstruction and of inferring a stored model on an incoming batch can be read
separately.
"""

from __future__ import annotations

import gzip
import json
import os
import time

import numpy as np

from scripts.dev.exam_design import recipes


def _load_jsonl_gz(path: str) -> list[dict]:
    with gzip.open(path, "rt") as f:
        return [json.loads(l) for l in f if l.strip()]


def run(cfg: dict, out: str) -> int:
    t_start = time.time()
    train_all = _load_jsonl_gz(cfg["train_file"])
    ocv = json.load(open(cfg["ocv_table"]))
    structure = recipes.Structure(ocv["soc"], ocv["ocv_v"])
    important = set(cfg.get("important_train_ids", []))
    runs = cfg["runs"]
    frozen = []
    models = []
    progress = {"phase": "train", "total": len(runs), "done": 0}
    stop_at = float(cfg.get("stop_admitting_epoch", 0)) or None
    for i, r in enumerate(runs):
        if stop_at and time.time() >= stop_at:
            frozen.append({"tag": r["tag"], "status": "NOT_ADMITTED"})
            continue
        recs = [x for x in train_all if x["case_id"] in set(r["train_ids"])] if "train_ids" in r else train_all[: r["train_n"]]
        d = recipes.Data.from_records(recs, important_fn=lambda rec: rec["case_id"] in important)
        m = recipes.make(r["recipe"])
        t0 = time.perf_counter()
        stats = m.fit(d, structure, seed=r["seed"])
        stats["fit_wall_s"] = time.perf_counter() - t0
        rec = {"tag": r["tag"], "recipe": r["recipe"], "seed": r["seed"], "n_train": len(recs), "status": "FROZEN",
               "config": m.config() if hasattr(m, "config") else {"name": m.name, "k": getattr(m, "k", None)}} | stats
        frozen.append(rec)
        models.append((r, m))
        progress["done"] = i + 1
        json.dump(progress, open(os.path.join(out, "progress.json"), "w"))
        json.dump(frozen, open(os.path.join(out, "frozen.json"), "w"), indent=1)
    # Only now are non-TRAIN inputs read.
    inputs = json.load(open(cfg["inputs_file"]))
    by_role: dict[str, list[dict]] = {}
    for c in inputs["cases"]:
        by_role.setdefault(c["role"], []).append(c)
    if cfg.get("private_blob"):
        # Private roles arrive encrypted; hidden duplicates are rebuilt from the public slot list so each
        # duplicate is predicted as its own request (the paired-repeat probe), never copied.
        from scripts.dev.exam_design import private_cases

        jobs = private_cases.unseal(open(cfg["private_blob"], "rb").read(), os.environ["PRIVATE_KEY"])
        by_id = {}
        for j in jobs:
            c = dict(j["case"], role=j["role"])
            by_id[c["case_id"]] = c
        slots = json.load(open(cfg["private_slots"]))
        for role, entries in slots.items():
            for e in entries:
                src = by_id[e.get("duplicate_of", e["case_id"])]
                by_role.setdefault(role, []).append(dict(src, case_id=e["case_id"], role=role))
    timing = []
    for r, m in models:
        preds = {}
        for role in r["predict_roles"]:
            cases = by_role.get(role, [])
            if not cases:
                continue
            x = np.array([[c[k] for k in ("c1", "c2", "t_amb_c", "soc0")] for c in cases], float)
            t0 = time.perf_counter()
            o = m.predict(x)
            t1 = time.perf_counter()
            # A second pass measures steady-state inference (the first includes compilation).
            m.predict(x)
            t2 = time.perf_counter()
            timing.append({"tag": r["tag"], "role": role, "n": len(cases), "first_s": t1 - t0, "steady_s": t2 - t1})
            preds |= recipes.to_preds(o, [c["case_id"] for c in cases])
        with gzip.open(os.path.join(out, f"pred_{r['tag']}.json.gz"), "wt") as f:
            json.dump(preds, f)
    json.dump(timing, open(os.path.join(out, "inference_timing.json"), "w"), indent=1)
    json.dump({"elapsed_s": time.time() - t_start, "runs": len(runs)}, open(os.path.join(out, "DONE.json"), "w"))
    return 0
