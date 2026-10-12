"""VERIFY-R on the public development questions' LEG half, and the selection's
decision results on their VALUE half (PUBLIC-DEV-DECISIONS-01; SCORE-PROOF-01
amendment 10).

    python -m scripts.dev.battery.verify_r_public --work W --out DIR

`W` is the public run's work directory (`public_dev_questions evaluate` has
run: `experiment/` holds the members' predictions and the references,
`records.jsonl` the solved and refined records). The registered split
(`public-dev-split-v1.json`) puts each question on exactly one side:
- `DIR/verify-r-public.json`: VERIFY-R's legs (v1, v3, v5) over the LEG
  questions only, each question's 35 solved EV4 actions its bank, the panel's
  synthetic controls added (as `verify_r_quiz`);
- `DIR/results-value.json`: the evaluate results with each member's decisions
  kept on the VALUE questions only, for `score_proof --dev-results`.
Everything here is public. Prints the counts and the diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SPLIT = ROOT / "docs/development/evidence/battery-score-tuning/public-dev-split-v1.json"
SCHEMA = "carbon.battery.verify-r-public.v1"


def side(split, scenario_id):
    """LEG or VALUE, by the registered rule."""
    h = hashlib.sha256(f"{split['salt']}:question:{scenario_id}".encode()).hexdigest()
    return "LEG" if int(h[:8], 16) / 2**32 < split["leg_share"] else "VALUE"


def value_results(results, value_ids):
    """The results with every member's decisions on VALUE questions only."""
    return {
        **results,
        "decisions": {
            m: {s: v for s, v in d.items() if s in value_ids}
            for m, d in results["decisions"].items()
        },
        "value_split": {"questions": sorted(value_ids), "rule": "public-dev-split-v1"},
    }


def legs_from(contract, scenarios, predictions, refs, receipt_id):
    """VERIFY-R legs over `scenarios`, the contract's actions as each bank."""
    from carbon.battery.value import contract as ev
    from carbon.battery.value import panel as pn
    from carbon.battery.value import verify_quiz as vq

    members = dict(predictions)
    for kind in pn.CONTROLS:
        members["control-" + kind] = pn.control_predictions(kind, refs)
    for kind in pn.SCREEN_CONTROLS:  # SCORE-PROOF-01 amendment 13
        members["control-" + kind] = pn.screen_control_predictions(kind, refs)
    return vq.member_scores(
        contract,
        scenarios,
        members,
        refs,
        receipt_id,
        candidates=ev.candidates(contract),
    )


def run(work, split_path=SPLIT):
    from carbon.battery.value import contract as ev
    from carbon.battery.value import reference_policy
    from carbon.battery.value.experiment import Experiment

    work = Path(work)
    split = json.loads(Path(split_path).read_text())
    experiment = Experiment(work / "experiment", repository=ROOT)
    contract = experiment.contract()
    refs = reference_policy.overlay(
        experiment.reference_map(), reference_policy.settled(work / "records.jsonl")
    )
    scenarios = ev.scenarios(contract, "development")
    leg = [s for s in scenarios if side(split, s["id"]) == "LEG"]
    value_ids = {s["id"] for s in scenarios if side(split, s["id"]) == "VALUE"}
    predictions = {}
    for member, *_ in experiment._members():
        bundle = experiment._member_predictions(member)
        if bundle is not None:
            predictions[member] = bundle["predictions"]
    by_leg, diagnostics = legs_from(
        contract, leg, predictions, refs, ev.digest(contract)
    )
    results = json.loads((work / "experiment/results/results.json").read_text())
    return (
        {
            "schema": SCHEMA,
            "contract_digest": ev.digest(contract),
            "split": split["salt"],
            "leg_questions": [s["id"] for s in leg],
            "legs": by_leg,
            "diagnostics": diagnostics,
            "state": "DEVELOPMENT (public)",
        },
        value_results(results, value_ids),
    )


def main(argv=None):
    ap = argparse.ArgumentParser(prog="verify_r_public")
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--split", type=Path, default=SPLIT)
    args = ap.parse_args(argv)
    legs, results = run(args.work, args.split)
    # Owner-only: the same script splits the fresh sealed questions on the
    # operator host (SCORE-PROOF-01 amendment 10), where nothing is world-readable.
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, value in (
        ("verify-r-public.json", legs),
        ("results-value.json", results),
    ):
        path = args.out / name
        if path.exists():
            path.unlink()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(json.dumps(value, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "leg_questions": len(legs["leg_questions"]),
                "value_questions": len(results["value_split"]["questions"]),
                "members": len(next(iter(legs["legs"].values()))),
                "diagnostics": legs["diagnostics"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
