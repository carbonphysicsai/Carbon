"""SCREENING-GRAIN-01, rule v3-bank-sched: the standard error of the
registered screening score, OWNER-BATTERY-SCORE-CANDIDATE-01's
G-FEAS/A-Q>@0.05 (higher is better), on public data only.

The live score (carbon/battery/daemon.py `_registered`): a = 1/(1 + E) with E
the mean per-case error on the pooled 294 scored cases; q = 1/(1 + R) with R
the mean Q3 decision regret over the active windows' design questions
(3 windows x k = 8 = 24, OWNER-BANK-SCHEDULED-ROTATION-01); score =
a^0.5 * q^0.5 (registry-v5 `A-Q`). The feasibility gate decides eligibility,
not the score's value, so it does not enter its SE.

Public stand-in: per-case errors on the EV4 public scoring set (as the v2
entry), and each member's per-scenario decision loss on EV4's verification
scenarios with a reference-feasible design (ev4-dev-tuning-v1 results), the
pool quiz_q3 uses. Bootstrap, per member: 294 cases without replacement, 24
questions with replacement from the member's scenarios; SE = sd(score) /
full-data score. The measured SE is the median over members; the grain is it
rounded UP to a 0.5 % step, floor 0.5 %.

    python grain_v3.py REPO OUT.json
"""

import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO, OUT = sys.argv[1], Path(sys.argv[2])
sys.path.insert(0, REPO)
from carbon.battery import exam
from carbon.battery.value import scoring as sc

HOME = Path("~carbon").expanduser()
DIRS = [
    HOME / "shared/evidence/srb1-ev4/experiment/predictions",
    HOME / "shared/evidence/graphite-run5-q1/predictions",
]
RESULTS = HOME / "shared/tuning-inputs/ev4-dev-tuning-v1-results.json"
POOLED = exam.DEVELOPMENT_RULE_V2["active_batches"] * (
    exam.DEVELOPMENT_RULE_V2["screening_batch_size"] - 2
)
QUESTIONS = 3 * 8
REPS = 4000
rng = np.random.default_rng(20261012)

store, ids, _ = sc.scoring_set(REPO)
err = {}
for d in DIRS:
    for p in sorted(Path(d).glob("*.json.gz")):
        b = json.loads(gzip.decompress(p.read_bytes()))
        rows, agg = exam.evaluate(b["predictions"], ids, store)
        if agg["eligible"]:
            err[b["member"]] = {
                r["case_id"]: r["error"] for r in rows if r["state"] == "SCORABLE"
            }
results = json.loads(RESULTS.read_text())
decisions = results["decisions"]
anyone = next(iter(decisions))
scenarios = sorted(
    s
    for s, v in decisions[anyone].items()
    if v["split"] == "verification"
    and v["outcome"].get("best_in_tested_set") is not None
)
loss = {}
for m in err:
    if m not in decisions:
        continue
    row = [decisions[m][s]["outcome"]["decision_loss"] for s in scenarios]
    if all(x is not None for x in row):
        loss[m] = np.array(row, dtype=float)
members = sorted(loss)
common = sorted(set.intersection(*(set(err[m]) for m in members)))
E = np.array([[err[m][c] for c in common] for m in members])
L = np.array([loss[m] for m in members])

full = np.sqrt((1 / (1 + E.mean(axis=1))) * (1 / (1 + L.mean(axis=1))))
scores = np.empty((len(members), REPS))
for r in range(REPS):
    cases = rng.choice(len(common), size=POOLED, replace=False)
    qs = rng.integers(len(scenarios), size=QUESTIONS)
    a = 1 / (1 + E[:, cases].mean(axis=1))
    q = 1 / (1 + L[:, qs].mean(axis=1))
    scores[:, r] = np.sqrt(a * q)
rel = scores.std(axis=1) / full
# Each leg's share, for the record.
a_rel = np.array(
    [
        (1 / (1 + E[i, rng.choice(len(common), size=(500, POOLED))].mean(axis=1))).std()
        * (1 + E[i].mean())
        for i in range(len(members))
    ]
)
q_rel = np.array(
    [
        (
            1
            / (
                1
                + L[i, rng.integers(len(scenarios), size=(500, QUESTIONS))].mean(axis=1)
            )
        ).std()
        * (1 + L[i].mean())
        for i in range(len(members))
    ]
)


def pct(x, p):
    return float(np.percentile(x, p))


se = float(np.median(rel))
grain = max(math.ceil(round(100 * se, 9) / 0.5) * 0.5, 0.5) / 100
out = {
    "schema": "carbon.battery.screening-grain-measurement.v1",
    "ticket": "SCREENING-GRAIN-01",
    "rule": "v3-bank-sched",
    "score": "registered G-FEAS/A-Q>@0.05 (OWNER-BATTERY-SCORE-CANDIDATE-01): a^0.5 q^0.5, higher is better",
    "data": "public EV4 scoring set + ev4-dev-tuning-v1 verification scenarios with a feasible design",
    "pooled_screening_cases": POOLED,
    "design_questions": QUESTIONS,
    "public_scenarios": len(scenarios),
    "members": len(members),
    "common_scorable_cases": len(common),
    "bootstrap_se": {
        "median": se,
        "p10": pct(rel, 10),
        "p90": pct(rel, 90),
        "reps": REPS,
    },
    "leg_relative_se_median": {
        "a": float(np.median(a_rel)),
        "q": float(np.median(q_rel)),
    },
    "measured_se": se,
    "grain": grain,
    "grain_if_p90_member": max(math.ceil(round(100 * pct(rel, 90), 9) / 0.5) * 0.5, 0.5)
    / 100,
    "caveat": (
        "q is resampled from only the public verification scenarios each member was "
        "scored on; live windows draw design questions from the sealed design bank. "
        "Remeasure from scored submissions after the cutover."
    ),
}
OUT.write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
