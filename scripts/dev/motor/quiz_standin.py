"""Motor quiz power on the public stand-in (registry-v1, commit ed095dd7).

    python -m scripts.dev.motor.quiz_standin --out RESULT.json

Works on derived quantities only (mean torque and ripple peak-to-peak), from
public references: the 180 TRAIN and PRACTICE cases for Q2, and study V2's
complete 8-design x 6-condition grid for Q3's pseudo-scenarios. No hidden
material and no new solve.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
LIMIT_T, LIMIT_R = 4.0, 0.30
BAND_T, BAND_R = 0.4, 0.03
POOLS = ROOT / "docs/development/evidence/motor-pools-v1"
V2 = ROOT / "docs/development/evidence/motor-decision-counted-v2/evaluation/result.json"


def rf(mean, ripple):
    return ripple / abs(mean) if mean else float("inf")


def feasible(mean, ripple):
    return mean >= LIMIT_T and rf(mean, ripple) <= LIMIT_R


def near(mean, ripple):
    return abs(mean - LIMIT_T) <= BAND_T or abs(rf(mean, ripple) - LIMIT_R) <= BAND_R


def control(kind, mean, ripple, seed=None):
    """A member's prediction (mean, ripple) from the reference."""
    if kind == "oracle":
        return mean, ripple
    if kind.startswith("noisy"):
        rng = np.random.default_rng(seed)
        return mean * float(np.exp(rng.normal(0, 0.03))), ripple * float(
            np.exp(rng.normal(0, 0.10))
        )
    if kind == "boundary_optimist":
        return (mean + 0.5, ripple * 0.8) if near(mean, ripple) else (mean, ripple)
    if kind == "localized_sign_error":
        return (
            (2 * LIMIT_T - mean, ripple)
            if abs(mean - LIMIT_T) <= BAND_T
            else (mean, ripple)
        )
    if kind == "infeasible_edge_seeker":
        if near(mean, ripple) and not feasible(mean, ripple):
            m = max(mean, LIMIT_T + 0.001)
            return m, 0.299 * m
        return mean, ripple
    if kind == "near_limit_cautious":
        return (mean - 0.5, ripple * 1.25) if near(mean, ripple) else (mean, ripple)
    raise ValueError(kind)


BAD = ("boundary_optimist", "localized_sign_error", "infeasible_edge_seeker")
GOOD = ("oracle",) + tuple(f"noisy{i}" for i in range(9))


def predict(member, case_key, mean, ripple):
    seed = None
    if member.startswith("noisy"):
        seed = int(member[5:]) * 1_000_003 + (abs(hash(case_key)) % 1_000_003)
    return control(
        "noisy" if member.startswith("noisy") else member, mean, ripple, seed
    )


def _auc(bad, good):
    bad = [b for b in bad if b is not None]
    good = [g for g in good if g is not None]
    if not bad or not good:
        return None
    return sum((b > g) + 0.5 * (b == g) for b in bad for g in good) / (
        len(bad) * len(good)
    )


def q2(rng, draws=1000):
    cases = []
    for name in ("train.jsonl", "practice.jsonl"):
        for line in (POOLS / name).read_text().splitlines():
            r = json.loads(line)
            if r.get("status") == "OK":
                cases.append(
                    (
                        r["case_id"] + name,
                        r["derived"]["mean_nm"],
                        r["derived"]["ripple_pk_pk_nm"],
                    )
                )
    near_ids = [i for i, (_k, m, rp) in enumerate(cases) if near(m, rp)]
    out = {
        "pool": len(cases),
        "near_band_cases": len(near_ids),
        "infeasible_near": sum(
            not feasible(cases[i][1], cases[i][2]) for i in near_ids
        ),
    }
    for label, n, half in [(f"n{n}", n, True) for n in (12, 24, 48)] + [
        (f"pooled_n{n}", n, False) for n in (12, 24, 32)
    ]:
        aucs, short = [], 0
        for _ in range(draws):
            # Pooled: a hotkey's quiz cases over W batches, drawn from the whole
            # public near band (the proxy for cross-rotation pooling).
            size = len(cases) // 2 if half else len(cases)
            batch = set(rng.choice(len(cases), size, replace=False).tolist())
            pool = [i for i in near_ids if i in batch]
            if len(pool) < n:
                short += 1
                continue
            chosen = rng.choice(pool, n, replace=False)

            def ff(member, chosen=chosen):
                infeasible = accepted = 0
                for i in chosen:
                    key, m, rp = cases[i]
                    if not feasible(m, rp):
                        infeasible += 1
                        pm, pr = predict(member, key, m, rp)
                        accepted += feasible(pm, pr)
                return accepted / infeasible if infeasible else None

            value = _auc([ff(b) for b in BAD], [ff(g) for g in GOOD])
            if value is not None:
                aucs.append(value)
        out[label] = {
            "draws_short": short,
            **(
                {}
                if not aucs
                else {
                    "mean": float(np.mean(aucs)),
                    "p05": float(np.quantile(aucs, 0.05)),
                }
            ),
        }
    return out


def _v2_grid():
    r = json.loads(V2.read_text())
    rows = r["comparator"]["rows"]
    designs = {
        d["design_id"]: d
        for d in json.loads(
            (
                ROOT / "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json"
            ).read_text()
        )["designs"]
    }
    conds = {
        c["condition_id"]: c
        for c in json.loads(
            (
                ROOT / "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json"
            ).read_text()
        )["conditions"]
    }
    grid = {}
    for row in rows:
        inp = row["inputs"]
        did = next(
            d
            for d, v in designs.items()
            if all(abs(inp[k] - x) < 1e-9 for k, x in v["values"].items())
        )
        cid = next(
            c
            for c, v in conds.items()
            if all(abs(inp[k] - x) < 1e-9 for k, x in v["values"].items())
        )
        grid[(did, cid)] = (
            row["reference"]["mean_nm"],
            row["reference"]["ripple_pk_pk_nm"],
        )
    return grid, sorted(designs), sorted(conds)


def q3(rng, draws=1000):
    grid, designs, conds = _v2_grid()

    def decide(member, subset):
        def assess(values):
            ok = all(feasible(m, rp) for m, rp in values)
            worst = max(rf(m, rp) for m, rp in values)
            return ok, worst, min(m for m, _ in values)

        truth = {d: assess([grid[(d, c)] for c in conds]) for d in subset}
        pred = {
            d: assess([predict(member, f"{d}{c}", *grid[(d, c)]) for c in conds])
            for d in subset
        }
        cands = [d for d in subset if pred[d][0]]
        best_true = [d for d in subset if truth[d][0]]
        if not cands:
            return "MISSED_OPPORTUNITY" if best_true else "CORRECT_ABSTENTION"
        pick = min(cands, key=lambda d: (pred[d][1], -pred[d][2], d))
        return "SELECTED_FEASIBLE" if truth[pick][0] else "SELECTED_INFEASIBLE"

    subsets = [
        s
        for s in itertools.combinations(designs, 4)
        if any(all(feasible(*grid[(d, c)]) for c in conds) for d in s)
    ]
    outcomes = {m: {s: decide(m, s) for s in subsets} for m in (*BAD, *GOOD)}
    out = {
        "pseudo_scenarios": len(subsets),
        "designs": len(designs),
        "conditions": len(conds),
    }
    for k in (1, 2, 4, 8):
        aucs = []
        for _ in range(draws):
            chosen = [subsets[i] for i in rng.choice(len(subsets), k, replace=False)]

            def ffr(member, chosen=chosen, k=k):
                return (
                    sum(outcomes[member][s] == "SELECTED_INFEASIBLE" for s in chosen)
                    / k
                )

            value = _auc([ffr(b) for b in BAD], [ffr(g) for g in GOOD])
            if value is not None:
                aucs.append(value)
        out[f"k{k}"] = {
            "mean": float(np.mean(aucs)),
            "p05": float(np.quantile(aucs, 0.05)),
        }
    out["false_feasible_all"] = {
        m: sum(v == "SELECTED_INFEASIBLE" for v in outcomes[m].values()) / len(subsets)
        for m in (*BAD, *GOOD)
    }
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="quiz_standin")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    rng = np.random.default_rng(20261007)
    document = {
        "schema": "carbon.motor.quiz-standin.v1",
        "registry_commit": "ed095dd7",
        "q2": q2(rng),
        "q3": q3(rng),
    }
    args.out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(json.dumps(document, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
