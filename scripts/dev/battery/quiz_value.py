"""quiz-registry-v6: does Q3's decision regret catch over-caution?

    python -m scripts.dev.battery.quiz_value --dev-results ev4-dev-tuning-v1-results.json \
        --out RESULT.json

The near-limit-cautious control (`score_tuning.near_limit_cautious`) is
decided on EV4's verification scenarios under EV4's fixed rules, beside the
known-good members' committed decisions. Over the scenarios with a feasible
design (the v5 rule), value detection is the AUC of mean decision regret
(cautious against known-good) over draws of k scenarios. Over-caution is the
MISSED_OPPORTUNITY share. Registered at ccafd40a before this ran. Public
stand-in only.
"""

from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT = ROOT / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
REFS = ROOT / "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
CAUTIOUS = "control-near_limit_cautious"


def cautious_decisions():
    from carbon.battery.value import contract as ev
    from carbon.battery.value import score_tuning as st
    from carbon.battery.value import scoring as sc
    from carbon.battery.value.experiment import evaluate

    contract, _ = ev.load(CONTRACT)
    refs = {}
    for line in gzip.decompress(REFS.read_bytes()).decode().splitlines():
        if line.strip():
            record = json.loads(line)
            refs[record["case_id"]] = record
    store, ids, _ = sc.scoring_set(ROOT)
    predictions = {
        c: st.near_limit_cautious(r["outputs"])
        for c, r in refs.items()
        if r.get("status") == "OK" and r.get("outputs")
    }
    predictions |= {
        c: st.near_limit_cautious(store.refs[c]["outputs"])
        for c in ids
        if store.refs[c].get("outputs")
    }
    results = evaluate(
        contract,
        refs,
        {CAUTIOUS: {"predictions": predictions}},
        ROOT,
        controls=False,
        kinds_by_member={CAUTIOUS: "RECONSTRUCTED"},
    )
    return results["decisions"][CAUTIOUS]


def main(argv=None):
    from scripts.dev.battery import quiz_designs as qd

    parser = argparse.ArgumentParser(prog="quiz_value")
    parser.add_argument("--dev-results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    results = json.loads(args.dev_results.read_text())
    decisions = dict(results["decisions"])
    decisions[CAUTIOUS] = cautious_decisions()
    members = results["summary"]["members"]
    anyone = next(iter(results["decisions"]))
    scenarios = sorted(
        s
        for s, v in results["decisions"][anyone].items()
        if v["split"] == "verification"
        and v["outcome"].get("best_in_tested_set") is not None
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
    good = [m for m in (*qd.GOOD_CONTROLS, *best_quarter) if m in decisions]

    def regret(m, chosen):
        resolved = [
            decisions[m][s]["outcome"]
            for s in chosen
            if decisions[m][s]["outcome"]["decision_loss"] is not None
        ]
        if not resolved:
            return None, None
        return (
            statistics.fmean(o["decision_loss"] for o in resolved),
            sum(o["kind"] == "MISSED_OPPORTUNITY" for o in resolved) / len(resolved),
        )

    rng = np.random.default_rng(20261006)
    rows = {}
    for k in (1, 2, 3, 4, 6, 8):
        aucs = []
        for _ in range(1000):
            chosen = [
                scenarios[i] for i in rng.choice(len(scenarios), k, replace=False)
            ]
            bad_r = regret(CAUTIOUS, chosen)[0]
            good_r = [regret(m, chosen)[0] for m in good]
            good_r = [g for g in good_r if g is not None]
            if bad_r is not None and good_r:
                aucs.append(
                    sum((bad_r > g) + 0.5 * (bad_r == g) for g in good_r) / len(good_r)
                )
        rows[f"k{k}"] = {
            "mean": float(np.mean(aucs)),
            "p05": float(np.quantile(aucs, 0.05)),
        }
    full = {m: regret(m, scenarios) for m in (CAUTIOUS, *good)}
    document = {
        "schema": "carbon.battery.quiz-value-comparison.v1",
        "registry_commit": "ccafd40a",
        "source": "PUBLIC_STANDIN: EV4 verification scenarios with a feasible design",
        "scenarios": len(scenarios),
        "regret_auc_by_k": rows,
        "cautious": {"regret": full[CAUTIOUS][0], "over_caution": full[CAUTIOUS][1]},
        "good": {
            "regret_max": max(full[m][0] for m in good if full[m][0] is not None),
            "over_caution_mean": statistics.fmean(
                full[m][1] for m in good if full[m][1] is not None
            ),
        },
    }
    args.out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(json.dumps(document, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
