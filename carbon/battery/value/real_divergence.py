"""Score-value divergence split by who diverges: a prospective view.

TRACK-B-STUCK-01 found that the pre-registered SCORE_VALUE_DIVERGENCE count
(`divergence.conditions`) mixes three things:
- constructed controls;
- members of one model family ordering among themselves;
- real models of different families.

So the count cannot show a real-model gain. This report splits each
condition's pairs (X scores at or above Y although Y decides better by more
than the loss band) into:

- `control`: X or Y is a constructed control;
- `within_family`: X and Y are real members of the same family;
- `across_families`: X and Y are real members of different families.

A condition is classed by its worst pair, in the order across_families,
within_family, control.

**Prospective only.** Every frozen study keeps its pre-registered outcome;
nothing here rescores or reinterprets it. The rule scores are those the
studies already define, recomputed from components committed in the retained
evidence; no prediction is reread. Future studies report these classes
alongside the count.

    python -m carbon.battery.value.real_divergence --out DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from . import divergence, margins, near, ratios

SCHEMA = "carbon.battery.real-divergence.v1"
CLASSES = ("across_families", "within_family", "control")
EVIDENCE = "docs/development/evidence"
#: Per dataset: the engineering-value result, and the SR-2 / SR-3 results that
#: hold its committed margin and near-limit components.
DATASETS = {
    "ev2-2026-10-01": {
        "sr2": "sr2-2026-10-02/results.json",
        "sr3": "sr3-2026-10-02/results.json",
    },
    "ev4-2026-10-01": {
        "sr2": "sr-ev4-2026-10-02/sr2/results.json",
        "sr3": "sr-ev4-2026-10-02/sr3/results.json",
    },
}
#: The candidates each study chose on EV4 development: the ones EV5 would
#: compare against the deciding rule.
CANDIDATES = {
    "sr1": "sr1-2026-10-02/results.json",
    "sr2": "sr-ev4-2026-10-02/sr2/results.json",
    "sr3": "sr-ev4-2026-10-02/sr3/results.json",
}


def family(member, kind):
    """`control`, or a real member's model family (its name's leading word)."""
    if kind != "RECONSTRUCTED":
        return "control"
    return re.match(r"[a-z]+", member).group(0)


def pair_class(x, y, members):
    fx = family(x, members[x]["kind"])
    fy = family(y, members[y]["kind"])
    if "control" in (fx, fy):
        return "control"
    return "within_family" if fx == fy else "across_families"


def classified(results, rule):
    """Each SCORE_VALUE_DIVERGENCE condition under `rule`, with its pairs
    classed, and the counts per split and class."""
    members = results["summary"]["members"]
    rows = []
    counts = {s: {c: 0 for c in CLASSES} for s in divergence.SPLITS}
    for condition in divergence.conditions(results, rule=rule):
        if condition["condition"] != "SCORE_VALUE_DIVERGENCE":
            continue
        x = condition["member"]
        pairs = {c: [] for c in CLASSES}
        for y in condition["scored_at_or_above"]:
            pairs[pair_class(x, y, members)].append(y)
        worst = next(c for c in CLASSES if pairs[c])
        counts[condition["split"]][worst] += 1
        rows.append(
            {
                "member": x,
                "split": condition["split"],
                "class": worst,
                "pairs": {c: v for c, v in pairs.items() if v},
            }
        )
    return {"counts": counts, "conditions": rows}


def with_candidates(results, sr2, sr3, candidates):
    """`results` with each candidate rule's scores added, from the committed
    components (SR-1 legs; SR-2 margin; SR-3 near-limit margin)."""
    out = json.loads(json.dumps(results))
    for member, component in results["components"].items():
        full = {
            **component,
            "margin": sr2["margin_component"].get(member),
            "near": sr3["near_component"].get(member),
        }
        scores = out["rule_scores"][member]
        for study, (rule, weights) in candidates.items():
            scorer = {"sr1": ratios.score, "sr2": margins.score, "sr3": near.score}
            scores[rule] = scorer[study](full, tuple(weights))
    return out


def report(root="."):
    root = Path(root)
    candidates = {}
    for study, path in CANDIDATES.items():
        chosen = json.loads((root / EVIDENCE / path).read_text())
        candidates[study] = (chosen["chosen"], chosen["chosen_weights"])
    datasets = {}
    for dataset, sources in DATASETS.items():
        path = root / EVIDENCE / dataset / "results.json"
        results = json.loads(path.read_text())
        sr2 = json.loads((root / EVIDENCE / sources["sr2"]).read_text())
        sr3 = json.loads((root / EVIDENCE / sources["sr3"]).read_text())
        scored = with_candidates(results, sr2, sr3, candidates)
        rules = [divergence.DECIDING_RULE] + [r for r, _ in candidates.values()]
        datasets[dataset] = {
            "results_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rules": {rule: classified(scored, rule) for rule in rules},
        }
    return {
        "schema": SCHEMA,
        "candidates": {
            s: {"rule": r, "weights": w} for s, (r, w) in candidates.items()
        },
        "datasets": datasets,
        "claims": {
            "prospective_only": True,
            "frozen_outcomes_changed": False,
            "testnet_rule_changed": False,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.battery.value.real_divergence"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    out = report(".")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(out, sort_keys=True, indent=1))
    print(
        json.dumps(
            {
                d: {r: v["counts"]["verification"] for r, v in body["rules"].items()}
                for d, body in out["datasets"].items()
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
