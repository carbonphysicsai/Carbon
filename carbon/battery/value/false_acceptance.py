"""Battery near-limit false acceptance: a localized measurement, descriptive.

The owner commissioned this on 2026-10-03 (OWNER-EXEC-APPROVALS-01) for the
named gap in `docs/development/evidence/real-divergence-2026-10-03/`: the
localized sign-error control outranks almost every real model under every
tested rule, and the mean near-limit optimism gate
(`admissibility.py`) cannot catch it, because averaging over the whole
important region dilutes an error confined to one band.

**Measured quantity.** On the published important region
(`near.near_cases`, `domain.is_important`), for each of the two constraints
with a continuous margin (no plating onset, peak temperature):
- the reference's verdict, with the decision contract's uncertainty bands
  (`decision.check`; within a band is UNRESOLVED and is not counted);
- the model's verdict, without bands, as the selector reads it
  (`decision.assess_predicted`);
- the false-acceptance rate: of the cases the reference resolves as FAIL, the
  share the model calls PASS.

The localized figure is the worst constraint's rate. A model wrong only in
one band is not averaged away by the cases it gets right. The contract
supplies the verdicts, constraints and bands; nothing new is chosen.

**Not a gate.** No cutoff exists here and no score changes. Making it a gate
needs a cutoff, which is a science value (HUMAN_INPUT). It is proposed as
EV5's H3 measurement and reported per member.

    python -m carbon.battery.value.false_acceptance --out DIR
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import decision as d
from . import panel as pn
from .margins import CONSTRAINTS

SCHEMA = "carbon.battery.near-false-acceptance.v1"
CONTRACT = "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"


def component(contract, predictions, case_ids, refs):
    """A member's per-constraint verdict counts on `case_ids`, and its worst
    false-acceptance rate.

    None when any case's prediction or reference is missing: an unmeasured
    model is never reported as clean. The worst rate is None when the
    reference resolves no case as FAIL on any constraint.
    """
    bands = contract["reference"]["uncertainty"]["bands"]
    counts = {
        c: {
            "reference_fail": 0,
            "false_acceptance": 0,
            "reference_pass": 0,
            "false_rejection": 0,
        }
        for c in CONSTRAINTS
    }
    for case_id in case_ids:
        outputs, reference = predictions.get(case_id), refs[case_id].get("outputs")
        if outputs is None or reference is None:
            return None
        truth = d.check(contract, d.measure(contract, reference), bands)
        said = d.check(contract, d.measure(contract, outputs))
        for constraint in CONSTRAINTS:
            row = counts[constraint]
            if truth[constraint] == d.FAIL:
                row["reference_fail"] += 1
                row["false_acceptance"] += said[constraint] == d.PASS
            elif truth[constraint] == d.PASS:
                row["reference_pass"] += 1
                row["false_rejection"] += said[constraint] == d.FAIL
    rates = {}
    for constraint, row in counts.items():
        rate = (
            row["false_acceptance"] / row["reference_fail"]
            if row["reference_fail"]
            else None
        )
        row["false_acceptance_rate"] = rate
        if rate is not None:
            rates[constraint] = rate
    worst = max(rates, key=lambda c: (rates[c], c)) if rates else None
    return {
        "constraints": counts,
        "worst_constraint": worst,
        "worst_false_acceptance_rate": None if worst is None else rates[worst],
    }


def controls(root="."):
    """The measurement for each constructed control on the scoring set's
    important region. Controls are built from committed references, so this
    needs no member predictions."""
    from . import scoring as sc
    from .near import near_cases

    root = Path(root)
    contract = json.loads((root / CONTRACT).read_text())
    store, case_ids, identity = sc.scoring_set(root)
    near = near_cases(store, case_ids)
    return {
        "schema": SCHEMA,
        "contract": CONTRACT,
        "scoring_set": identity,
        "scoring_cases": len(case_ids),
        "important_cases": len(near),
        "cutoff": None,
        "state": "DESCRIPTIVE",
        "controls": {
            "control-"
            + kind: component(
                contract, pn.control_predictions(kind, store.refs), near, store.refs
            )
            for kind in pn.CONTROLS
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.battery.value.false_acceptance"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = controls(".")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "controls.json").write_text(
        json.dumps(report, sort_keys=True, indent=1) + "\n"
    )
    print(
        json.dumps(
            {k: v["worst_false_acceptance_rate"] for k, v in report["controls"].items()}
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
