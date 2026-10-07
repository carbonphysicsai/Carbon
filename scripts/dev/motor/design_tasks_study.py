"""motor-design-tasks-v1: screening map, repeatability, power, value and cost.

    python -m scripts.dev.motor.design_tasks_study --runs DIR --out RESULT.json

DIR holds `screen-plan.json`, `screen/records.jsonl` and
`repeat/records.jsonl` (`design_screen.py plan`, then `run_batch.py`). Public
material only; registered in
`docs/development/evidence/motor-design-tasks-v1/registry.json` before any
solve. Tasks run through `carbon.design_search.tasks`, the Challenge-neutral
interface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.design_search import score_value as sv
from carbon.design_search import tasks as dt

V2 = ROOT / "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json"
V2_RESULT = (
    ROOT / "docs/development/evidence/motor-decision-counted-v2/evaluation/result.json"
)
POOLS = ROOT / "docs/development/evidence/motor-pools-v1"
LIMIT_T, LIMIT_R = 4.0, 0.30
BAND_T, BAND_R = 0.4, 0.03
GEOMETRY = (
    "magnet_mm",
    "embrace",
    "airgap_mm",
    "slot_open_deg",
    "tooth_mm",
    "slot_bottom_mm",
)
TORQUE = {"quantity": "mean_torque_nm", "unit": "N m"}
RIPPLE = {"quantity": "ripple_fraction", "unit": "1"}
CONSTRAINTS = [
    {**TORQUE, "op": ">=", "limit": LIMIT_T},
    {**RIPPLE, "op": "<=", "limit": LIMIT_R},
]
OBJECTIVES = {
    "MOTOR-RIPPLE": (
        {**RIPPLE, "sense": "min", "aggregate": "worst"},
        {**TORQUE, "sense": "max", "aggregate": "worst"},
    ),
    "MOTOR-TORQUE": (
        {**TORQUE, "sense": "max", "aggregate": "worst"},
        {**RIPPLE, "sense": "min", "aggregate": "worst"},
    ),
}
BAD = ("edge_optimist", "localized_sign_error", "infeasible_edge_seeker")
CAUTIOUS = "over_cautious"
GOOD = ("oracle",) + tuple(f"noisy{i}" for i in range(9))
MODELS = ("analytic-v1", "learned-krr-v1")
CANDIDATES = 8
TASKS_PER_STRATUM = 500
DRAWS = 1000
KS = (1, 2, 4, 8)


def rf(mean, ripple):
    return ripple / abs(mean) if mean else float("inf")


def quantities(mean, ripple):
    return {"mean_torque_nm": mean, "ripple_fraction": rf(mean, ripple)}


def near(mean, ripple):
    return abs(mean - LIMIT_T) <= BAND_T or abs(rf(mean, ripple) - LIMIT_R) <= BAND_R


def feasible(mean, ripple):
    return mean >= LIMIT_T and rf(mean, ripple) <= LIMIT_R


def derived(torque):
    values = list(torque)
    return sum(values) / len(values), max(values) - min(values)


def control(member, key, mean, ripple):
    """A stand-in member's (mean, ripple) from the reference; behaviour-
    defined (registry `power`)."""
    if member == "oracle":
        return mean, ripple
    if member.startswith("noisy"):
        seed = int.from_bytes(hashlib.sha256(f"{member}|{key}".encode()).digest()[:8])
        rng = np.random.default_rng(seed)
        return mean * float(np.exp(rng.normal(0, 0.03))), ripple * float(
            np.exp(rng.normal(0, 0.10))
        )
    if member == "edge_optimist":
        return (mean + 0.5, ripple * 0.8) if near(mean, ripple) else (mean, ripple)
    if member == CAUTIOUS:
        return (mean - 0.5, ripple * 1.25) if near(mean, ripple) else (mean, ripple)
    if member == "localized_sign_error":
        if abs(mean - LIMIT_T) <= BAND_T:
            return 2 * LIMIT_T - mean, ripple
        return mean, ripple
    if member == "infeasible_edge_seeker":
        if near(mean, ripple) and not feasible(mean, ripple):
            m = max(mean, LIMIT_T + 0.001)
            return m, 0.299 * m
        return mean, ripple
    raise ValueError(member)


def _records(path):
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def screen_grid(runs):
    plan = json.loads((runs / "screen-plan.json").read_text())
    designs = {d["design_id"]: d for d in plan["designs"]}
    grid, inputs, statuses = {}, {}, {}
    for r in _records(runs / "screen" / "records.jsonl"):
        _, gid, cid = r["case_id"].split("-")
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        inputs[(gid, cid)] = r["inputs"]
        if r["status"] == "OK":
            grid[(gid, cid)] = derived(r["outputs"]["torque_nm"])
    return designs, grid, inputs, statuses


def conditions():
    return [c["condition_id"] for c in json.loads(V2.read_text())["conditions"]]


def screening_map(designs, grid):
    conds = conditions()
    rows = {}
    for gid in sorted(designs):
        cells = {c: grid.get((gid, c)) for c in conds}
        done = {c: v for c, v in cells.items() if v is not None}
        rows[gid] = {
            "drawn": designs[gid]["drawn"],
            "solved": len(done),
            "feasible_all": (
                all(feasible(*v) for v in done.values())
                if len(done) == len(conds)
                else None
            ),
            "near_conditions": sorted(c for c, v in done.items() if near(*v)),
            "min_torque_nm": min((v[0] for v in done.values()), default=None),
            "max_ripple_fraction": max((rf(*v) for v in done.values()), default=None),
        }
    complete = [r for r in rows.values() if r["solved"] == len(conds)]
    return {
        "designs": rows,
        "complete_designs": len(complete),
        "feasible_designs": sum(r["feasible_all"] is True for r in complete),
        "near_designs": sum(bool(r["near_conditions"]) for r in complete),
        "near_points": sum(len(r["near_conditions"]) for r in rows.values()),
    }


def repeatability(runs):
    standard = {}
    for name in ("train", "practice"):
        for line in (POOLS / f"{name}.jsonl").read_text().splitlines():
            r = json.loads(line)
            standard[f"repeat-{name}-{r['case_id']}"] = r
    rows = []
    for r in _records(runs / "repeat" / "records.jsonl"):
        if r["status"] != "OK":
            rows.append({"case_id": r["case_id"], "status": r["status"]})
            continue
        m1, p1 = derived(r["outputs"]["torque_nm"])
        s = standard[r["case_id"]]["derived"]
        m0, p0 = s["mean_nm"], s["ripple_pk_pk_nm"]
        rows.append(
            {
                "case_id": r["case_id"],
                "status": "OK",
                "standard": {"mean_nm": m0, "ripple_pk_pk_nm": p0, "rf": rf(m0, p0)},
                "refined": {"mean_nm": m1, "ripple_pk_pk_nm": p1, "rf": rf(m1, p1)},
                "abs_shift": {
                    "mean_nm": abs(m1 - m0),
                    "ripple_pk_pk_nm": abs(p1 - p0),
                    "rf": abs(rf(m1, p1) - rf(m0, p0)),
                },
                "rel_shift": {
                    "mean": abs(m1 - m0) / abs(m0) if m0 else None,
                    "ripple_pk_pk": abs(p1 - p0) / abs(p0) if p0 else None,
                },
                "feasible_changed": feasible(m0, p0) != feasible(m1, p1),
            }
        )
    ok = [r for r in rows if r["status"] == "OK"]

    def worst(path):
        values = [r[path[0]][path[1]] for r in ok if r[path[0]][path[1]] is not None]
        return max(values) if values else None

    return {
        "cases": len(rows),
        "ok": len(ok),
        "band_candidates": {
            "mean_nm_abs": worst(("abs_shift", "mean_nm")),
            "ripple_fraction_abs": worst(("abs_shift", "rf")),
            "mean_rel": worst(("rel_shift", "mean")),
            "ripple_pk_pk_rel": worst(("rel_shift", "ripple_pk_pk")),
        },
        "feasibility_flips": sum(r["feasible_changed"] for r in ok),
        "rows": rows,
    }


def member_values(members, grid, model_grids):
    """{member: {(gid, cid): quantities}} over the solved cells."""
    out = {}
    for member in members:
        values = {}
        for key, (mean, ripple) in grid.items():
            if member in model_grids:
                pm, pr = model_grids[member][key]
            else:
                pm, pr = control(member, f"{key[0]}|{key[1]}", mean, ripple)
            values[key] = quantities(pm, pr)
        out[member] = values
    return out


def model_grids(inputs, keys):
    from carbon.motor import decision_study

    config = json.loads(V2.read_text())
    models, _ = decision_study.reconstruct_models(config, repository=ROOT)
    out = {}
    for name in MODELS:
        predicted = models[name]({f"{g}|{c}": inputs[(g, c)] for g, c in keys})
        out[name] = {
            (g, c): derived(predicted[f"{g}|{c}"]["torque_nm"]) for g, c in keys
        }
    return out


def make_tasks(designs, grid, objective_id, rng):
    conds = conditions()
    complete = sorted(
        g for g in designs if all((g, c) in grid for c in conds)
    )  # missing cells never enter a task
    typical_pool = [g for g in complete if designs[g]["drawn"] == "uniform"]
    objective, secondary = OBJECTIVES[objective_id]

    def build(tid, cands):
        return dt.task(
            tid,
            conditions=conds,
            candidates=list(cands),
            objective=objective,
            constraints=CONSTRAINTS,
            secondary=secondary,
        )

    def any_feasible(cands):
        return any(all(feasible(*grid[(g, c)]) for c in conds) for g in cands)

    def near_count(cands):
        return sum(any(near(*grid[(g, c)]) for c in conds) for g in cands)

    strata = {}
    for name, pool, keep in (
        ("typical_use", typical_pool, any_feasible),
        ("near_limit", complete, lambda s: any_feasible(s) and near_count(s) >= 2),
    ):
        tasks, seen = [], set()
        if len(pool) >= CANDIDATES:
            for _ in range(TASKS_PER_STRATUM * 50):
                if len(tasks) == TASKS_PER_STRATUM:
                    break
                cands = tuple(sorted(rng.choice(pool, CANDIDATES, replace=False)))
                if cands in seen:
                    continue
                seen.add(cands)
                if keep(cands):
                    tasks.append(build(f"{objective_id}-{name}-{len(tasks)}", cands))
        strata[name] = tasks
    return strata


def _auc(bad, good):
    bad = [b for b in bad if b is not None]
    good = [g for g in good if g is not None]
    if not bad or not good:
        return None
    return sum((b > g) + 0.5 * (b == g) for b in bad for g in good) / (
        len(bad) * len(good)
    )


def _value_loss(outcomes):
    """A per-member value loss over a batch: (missed share, mean regret)."""
    m = dt.measures(outcomes)
    if m["over_caution"] is None:
        return None
    return (m["over_caution"], m["regret"] if m["regret"] is not None else 0.0)


def power(judged, tasks_by_stratum, rng):
    out = {}
    names = list(tasks_by_stratum)
    for label in (*names, "combined"):
        rows = {}
        for k in KS:
            if label == "combined" and k < 2:
                continue
            ff, val, val_regret = [], [], []
            for _ in range(DRAWS):
                if label == "combined":
                    chosen = []
                    for s in names:
                        ids = range(len(tasks_by_stratum[s]))
                        if not ids:
                            break
                        chosen += [
                            (s, i) for i in rng.choice(ids, k // 2, replace=False)
                        ]
                else:
                    n = len(tasks_by_stratum[label])
                    if n < k:
                        break
                    chosen = [(label, i) for i in rng.choice(n, k, replace=False)]

                def outs(member, chosen=chosen):
                    return [judged[member][s][i] for s, i in chosen]

                ff.append(
                    _auc(
                        [dt.measures(outs(b))["false_feasible"] for b in BAD],
                        [dt.measures(outs(g))["false_feasible"] for g in GOOD],
                    )
                )
                val.append(
                    _auc(
                        [_value_loss(outs(CAUTIOUS))],
                        [_value_loss(outs(g)) for g in GOOD],
                    )
                )
                val_regret.append(
                    _auc(
                        [dt.measures(outs(CAUTIOUS))["regret"]],
                        [dt.measures(outs(g))["regret"] for g in GOOD],
                    )
                )

            def summary(values):
                values = [v for v in values if v is not None]
                if not values:
                    return None
                return {
                    "mean": float(np.mean(values)),
                    "p05": float(np.quantile(values, 0.05)),
                    "draws": len(values),
                }

            rows[f"k{k}"] = {
                "safety_false_feasible_auc": summary(ff),
                "value_auc": summary(val),
                "value_regret_only_auc": summary(val_regret),
            }
        out[label] = rows
    return out


def v2_full_decision(members, objective_id):
    """Each member's decision regret on study V2's own 8 x 6 grid (the
    registered full decision value)."""
    config = json.loads(V2.read_text())
    designs = {d["design_id"]: d["values"] for d in config["designs"]}
    conds = {c["condition_id"]: c["values"] for c in config["conditions"]}
    grid, inputs = {}, {}
    for row in json.loads(V2_RESULT.read_text())["comparator"]["rows"]:
        inp = row["inputs"]
        did = next(
            d
            for d, v in designs.items()
            if all(abs(inp[k] - x) < 1e-9 for k, x in v.items())
        )
        cid = next(
            c
            for c, v in conds.items()
            if all(abs(inp[k] - x) < 1e-9 for k, x in v.items())
        )
        grid[(did, cid)] = (
            row["reference"]["mean_nm"],
            row["reference"]["ripple_pk_pk_nm"],
        )
        inputs[(did, cid)] = inp
    keys = sorted(grid)
    mg = model_grids(inputs, keys)
    values = member_values(members, grid, mg)
    reference = {k: quantities(*v) for k, v in grid.items()}
    objective, secondary = OBJECTIVES[objective_id]
    task = dt.task(
        f"V2-{objective_id}",
        conditions=sorted(conds),
        candidates=sorted(designs),
        objective=objective,
        constraints=CONSTRAINTS,
        secondary=secondary,
    )
    return {m: dt.judge(task, values[m], reference) for m in members}


def _value_key(outcome_or_measures):
    """Order decision quality: infeasible pick worst, then missed, then
    regret."""
    o = outcome_or_measures
    if "kind" in o:
        cls = {"SELECTED_INFEASIBLE": 2, "MISSED_OPPORTUNITY": 1}.get(o["kind"], 0)
        return (cls, o["regret"] or 0.0)
    return (
        2 * (o["false_feasible"] or 0) + (o["over_caution"] or 0),
        o["regret"] or 0.0,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="design_tasks_study")
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    designs, grid, inputs, statuses = screen_grid(args.runs)
    members = (*GOOD, *BAD, CAUTIOUS, *MODELS)
    mg = model_grids(inputs, sorted(grid))
    values = member_values(members, grid, mg)
    reference = {k: quantities(*v) for k, v in grid.items()}
    rng = np.random.default_rng(20261007)
    document = {
        "schema": "carbon.design-tasks-study.v1",
        "registry": "docs/development/evidence/motor-design-tasks-v1/registry.json",
        "screen_statuses": statuses,
        "screening": screening_map(designs, grid),
        "repeatability": repeatability(args.runs),
        "objectives": {},
    }
    for objective_id in OBJECTIVES:
        strata = make_tasks(designs, grid, objective_id, rng)
        judged = {
            m: {
                s: [dt.judge(t, values[m], reference) for t in tasks]
                for s, tasks in strata.items()
            }
            for m in members
        }
        all_measures = {
            m: {s: dt.measures(judged[m][s]) for s in strata} for m in members
        }
        v2 = v2_full_decision(members, objective_id)
        value_check = {}
        for s in strata:
            ms = [
                m for m in members if all_measures[m][s]["false_feasible"] is not None
            ]
            xs = [_value_key(all_measures[m][s]) for m in ms]
            ys = [_value_key(v2[m]) for m in ms]
            value_check[s] = {
                "members": len(ms),
                "kendall_tau_b": sv.kendall_tau_b(xs, ys),
                "spearman_rho": sv.spearman_rho(xs, ys),
            }
        document["objectives"][objective_id] = {
            "tasks": {s: len(t) for s, t in strata.items()},
            "measures": all_measures,
            "power": power(judged, strata, rng),
            "v2_full_decision": v2,
            "value_check": value_check,
        }
    walls = [
        r["wall_s"]
        for r in _records(args.runs / "screen" / "records.jsonl")
        if r.get("wall_s")
    ]
    median = statistics.median(walls) if walls else None
    document["cost"] = {
        "host_median_wall_s": median,
        "solves_per_task": CANDIDATES * len(conditions()),
        "per_batch_k8": {
            "independent_tasks_solves": 8 * CANDIDATES * len(conditions()),
            "shared_pool_16_geometries_solves": 16 * len(conditions()),
            "ax42_concurrency": 8,
            "note": "AX42 wall = solves / 8 x per-solve wall; the host's median is "
            "used as the per-solve wall (same 2-CPU containers)",
        },
    }
    if median:
        for key in ("independent_tasks_solves", "shared_pool_16_geometries_solves"):
            solves = document["cost"]["per_batch_k8"][key]
            document["cost"]["per_batch_k8"][key.replace("solves", "ax42_h")] = (
                -(-solves // 8) * median / 3600
            )
    args.out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    brief = {
        "statuses": statuses,
        "screening": {k: v for k, v in document["screening"].items() if k != "designs"},
        "repeat": document["repeatability"]["band_candidates"],
        "cost": document["cost"],
    }
    for objective_id, block in document["objectives"].items():
        brief[objective_id] = {
            "tasks": block["tasks"],
            "power_k8": {s: block["power"][s].get("k8") for s in block["power"]},
            "value_check": block["value_check"],
        }
    print(json.dumps(brief, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
