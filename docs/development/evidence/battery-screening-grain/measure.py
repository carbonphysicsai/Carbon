"""SCREENING-GRAIN-01: battery's screening-score standard error, for the
ladder grain (OWNER-BATTERY-CHAMPIONSHIP-03 §1; the owner, 2026-10-12: "the
grain is the Test Engineer's measured screening standard error, rounded up to
the nearest 0.5% (minimum 0.5%)").

Public data only: the EV4 public scoring set and the public stored
predictions (srb1-ev4, graphite-run5-q1). The pooled screening score is the
mean per-case error over the pooled screening set: 3 active batches x 98
scored cases = 294 cases (DEVELOPMENT_RULE_V2 / _V2_BANK in carbon/battery/exam.py).

SE (relative) of one member's pooled score, two ways:
- analytic: sd(per-case error) / mean(per-case error) / sqrt(294);
- bootstrap: draw 294 cases (without replacement) from the common scorable
  cases, 4,000 times; sd of the member's mean / its full-set mean.
The measured SE is the median over the eligible members, the larger of the
two estimators. The grain is that SE rounded UP to a 0.5 % step, floor 0.5 %.

    python grain.py REPO OUT.json
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

DIRS = [
    "/home/carbon/shared/evidence/srb1-ev4/experiment/predictions",
    "/home/carbon/shared/evidence/graphite-run5-q1/predictions",
]
POOLED = exam.DEVELOPMENT_RULE_V2["active_batches"] * (
    exam.DEVELOPMENT_RULE_V2["screening_batch_size"] - 2
)
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
common = sorted(set.intersection(*(set(e) for e in err.values())))
E = np.array([[err[m][c] for c in common] for m in sorted(err)])
analytic = E.std(axis=1) / E.mean(axis=1) / math.sqrt(POOLED)
boot = np.empty((len(E), REPS))
for r in range(REPS):
    idx = rng.choice(len(common), size=POOLED, replace=False)
    boot[:, r] = E[:, idx].mean(axis=1)
bootstrap = boot.std(axis=1) / E.mean(axis=1)


def q(x, p):
    return float(np.percentile(x, p))


se = max(float(np.median(analytic)), float(np.median(bootstrap)))
grain = max(math.ceil(round(100 * se, 9) / 0.5) * 0.5, 0.5) / 100
out = {
    "schema": "carbon.battery.screening-grain-measurement.v1",
    "ticket": "SCREENING-GRAIN-01",
    "data": "public EV4 scoring set; public stored predictions (srb1-ev4, graphite-run5-q1)",
    "pooled_screening_cases": POOLED,
    "members": len(E),
    "common_scorable_cases": len(common),
    "analytic_se": {
        "median": float(np.median(analytic)),
        "p10": q(analytic, 10),
        "p90": q(analytic, 90),
    },
    "bootstrap_se": {
        "median": float(np.median(bootstrap)),
        "p10": q(bootstrap, 10),
        "p90": q(bootstrap, 90),
        "reps": REPS,
    },
    "measured_se": se,
    "rule": "measured SE = median over members of the larger estimator; grain = SE rounded UP to a 0.5 % step, floor 0.5 % (owner, 2026-10-12)",
    "grain": grain,
    "grain_if_p90_member": max(
        math.ceil(round(100 * max(q(analytic, 90), q(bootstrap, 90)), 9) / 0.5) * 0.5,
        0.5,
    )
    / 100,
}
OUT.write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
