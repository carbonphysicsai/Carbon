"""Q3 (quiz-registry-v4): the decision-scenario quiz, on the public stand-in.

    python -m scripts.dev.battery.quiz_q3 --dev-results ev4-dev-tuning-v1-results.json \
        --b4-records RECORDS.jsonl --out RESULT.json

The stand-in pool is EV4's 12 verification scenarios, decided by every
ev4-dev-tuning-v1 member under EV4's fixed decision rules against committed
reference grids. ev4-dev-tuning-v1 measures value on the development split
only, so the pool is disjoint from it. Each draw takes k scenarios. The gate
is the decision-level false-feasible rate (picks the reference shows
infeasible); regret and over-caution are reported beside it. Registered at
fa865e57 before this ran.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REGISTRY = ROOT / "docs/development/evidence/battery-quiz-designs/quiz-registry-v4.json"


def _auc(bad, good):
    bad = [b for b in bad if b is not None]
    good = [g for g in good if g is not None]
    if not bad or not good:
        return None
    return sum((b > g) + 0.5 * (b == g) for b in bad for g in good) / (
        len(bad) * len(good)
    )


def main(argv=None):
    from scripts.dev.battery import quiz_designs as qd

    parser = argparse.ArgumentParser(prog="quiz_q3")
    parser.add_argument("--dev-results", type=Path, required=True)
    parser.add_argument("--b4-records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    registry = json.loads(REGISTRY.read_text())
    design = registry["designs"][0]
    results = json.loads(args.dev_results.read_text())
    decisions = results["decisions"]
    members = results["summary"]["members"]
    scenarios = sorted(
        {
            s
            for m in decisions
            for s, v in decisions[m].items()
            if v["split"] == "verification"
        }
    )
    ev4 = [
        m
        for m, row in members.items()
        if row["kind"] == "RECONSTRUCTED" and not m.startswith("graphite-")
    ]
    values = {
        m: members[m]["loss_development"]
        for m in ev4
        if members[m]["loss_development"] is not None
    }
    best_quarter = sorted(values, key=lambda m: (values[m], m))[
        : max(1, len(values) // 4)
    ]
    bad = [m for m in (*qd.TRACK_A_BAD, qd.WINNER) if m in decisions]
    good = [m for m in (*qd.GOOD_CONTROLS, *best_quarter) if m in decisions]
    outcome = {
        m: {s: decisions[m][s]["outcome"] for s in scenarios} for m in (*bad, *good)
    }

    def gate(m, chosen):
        resolved = [
            outcome[m][s] for s in chosen if outcome[m][s]["decision_loss"] is not None
        ]
        if not resolved:
            return None, None, None
        infeasible = sum(o["kind"] == "SELECTED_INFEASIBLE" for o in resolved) / len(
            resolved
        )
        regret = statistics.fmean(o["decision_loss"] for o in resolved)
        caution = sum(o["kind"] == "MISSED_OPPORTUNITY" for o in resolved) / len(
            resolved
        )
        return infeasible, regret, caution

    rng = np.random.default_rng(20261006)
    rows = {}
    for k in design["k"]:
        aucs, regret_bad, regret_good, caution_good = [], [], [], []
        for _ in range(registry["metric"]["draws"]):
            chosen = [
                scenarios[i] for i in rng.choice(len(scenarios), k, replace=False)
            ]
            b = [gate(m, chosen) for m in bad]
            g = [gate(m, chosen) for m in good]
            value = _auc([x[0] for x in b], [x[0] for x in g])
            if value is not None:
                aucs.append(value)
            regret_bad += [x[1] for x in b if x[1] is not None]
            regret_good += [x[1] for x in g if x[1] is not None]
            caution_good += [x[2] for x in g if x[2] is not None]
        rows[f"Q3/k{k}"] = {
            "k": k,
            "auc_decision_false_feasible": (
                None
                if not aucs
                else {
                    "mean": float(np.mean(aucs)),
                    "p05": float(np.quantile(aucs, 0.05)),
                }
            ),
            "regret_bad_mean": statistics.fmean(regret_bad) if regret_bad else None,
            "regret_good_mean": statistics.fmean(regret_good) if regret_good else None,
            "over_caution_good_mean": (
                statistics.fmean(caution_good) if caution_good else None
            ),
        }
    per_member = {m: gate(m, scenarios)[0] for m in (*bad, *good)}
    walls = [
        json.loads(line)["wall_s"]
        for line in args.b4_records.read_text().splitlines()
        if line.strip() and json.loads(line).get("wall_s")
    ]
    document = {
        "schema": "carbon.battery.quiz-q3-comparison.v1",
        "registry_commit": "fa865e57",
        "source": "PUBLIC_STANDIN: EV4 verification scenarios; not a hidden batch",
        "scenarios": len(scenarios),
        "known_bad": bad,
        "known_good": {
            "controls": list(qd.GOOD_CONTROLS),
            "best_quarter": len(best_quarter),
        },
        "all_12_false_feasible": {
            "bad": {m: per_member[m] for m in bad},
            "good_max": max(
                (per_member[m] for m in good if per_member[m] is not None), default=None
            ),
        },
        "results": rows,
        "producer_cost_per_scenario": {
            "reference_solves": 35,
            "cpu_seconds_per_solve_median": statistics.median(walls),
            "cpu_hours_per_scenario": 35 * statistics.median(walls) / 3600,
            "basis": "the B4 practice set's 210 host solves (pinned truth image)",
        },
    }
    args.out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v["auc_decision_false_feasible"] for k, v in rows.items()}))
    print(json.dumps(document["all_12_false_feasible"]))
    print(json.dumps(document["producer_cost_per_scenario"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
