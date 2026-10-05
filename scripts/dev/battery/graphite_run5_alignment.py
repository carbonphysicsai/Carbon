"""Q1 score-to-value on Graphite run 5's battery panel (TRACK-B-HARNESS-01).

    python -m scripts.dev.battery.graphite_run5_alignment predict --out DIR [--only MEMBER ...]
    python -m scripts.dev.battery.graphite_run5_alignment analyse --out DIR

Does Graphite's practice score rank the run-5 constructions by decision
quality? The Test Lead approved this plan on 2026-10-05: CPU only, no spend.

**Members.** `PANELS["graphite-run5"]`: the baseline and eight scored DeepONet
proposals, each rebuilt by Carbon on CPU (`worker.DirectBackend`).
- Seeds: the seed each was scored with, plus two declared extra seeds.
- No weights from the pod are used.

**Same artifact for score and decision** (OWNER-GRAPHITE-TEST-WAVE-04 §1).
Each rebuilt member:
- is scored on the public PRACTICE set with battery rule v2's practice
  scoring, in-process (`frozen_rule(...).score`), which is the primary score;
- predicts EV4's decision and scoring inputs from the same trained state.

The pod's original practice scores are reported as a secondary line, with a
rank-drift table.

**Decisions.** The EV4 charge-protocol contract, reused as
`graphite-run5-charge-protocol-selection.v1.json`: panel `graphite-run5`, EV4's
case ids, and EV4's committed reference-scored grid
(`docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz`).
- No PyBaMM solves.
- **EV4 development conditions (previously used)** only: development
  evidence, no confirmation claim.
- EV5's conditions, plan and sealed batch, and graphite-confirmation-v1, are
  never read.

**Reference failures** are never a candidate penalty. Every member is scored on
the common resolved-case mask, and the mask is reported.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.battery.value import panel as value_panel

PANEL = "graphite-run5"
CHALLENGE_ID = "battery-fastcharge-ageing-development-v1"
CONTRACT = (
    ROOT
    / "carbon/battery/value/contracts/graphite-run5-charge-protocol-selection.v1.json"
)
EV4_REFERENCES = (
    ROOT / "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
)


class _CachedBackend:
    """DirectBackend that keeps each member's trained state so one rebuild
    serves both its practice scoring and its decision predictions."""

    def __init__(self, backend):
        self.backend = backend
        self.identity = backend.identity
        self.state = None

    def reconstruct(self, identity, recipe, seed):
        self.state, stats = self.backend.reconstruct(identity, recipe, seed)
        return self.state, stats

    def infer(self, identity, state, inputs):
        return self.backend.infer(identity, state, inputs)


def _practice():
    from carbon.agent_campaign.graphite.experiment import frozen_rule
    from carbon.battery.practice import INPUTS
    from carbon.challenge_validator.scoring import scoring_for

    rule = frozen_rule(ROOT, scoring=scoring_for(CHALLENGE_ID))
    inputs = {
        r["case_id"]: {k: r["inputs"][k] for k in INPUTS} for r in rule.practice.records
    }
    return rule, inputs


def predict(out, only=None):
    from carbon.battery.value import experiment as ev
    from carbon.battery.value.contract import load as load_contract
    from carbon.battery.worker import DirectBackend

    out = Path(out)
    (out / "predictions").mkdir(parents=True, exist_ok=True)
    (out / "practice").mkdir(parents=True, exist_ok=True)
    contract, _ = load_contract(CONTRACT)
    inputs = ev.panel_inputs(contract, ROOT)
    rule, practice_inputs = _practice()
    backend = _CachedBackend(DirectBackend(ROOT))
    done = []
    for member, _label, strategy, seed in value_panel.members(PANEL):
        if only and member not in only:
            continue
        target = out / "predictions" / f"{member}.json.gz"
        if target.exists():
            continue
        started = time.monotonic()
        bundle, state = ev.member_bundle(backend, member, strategy, seed, inputs)
        practice_predictions = backend.infer(
            f"practice-{member}", state, practice_inputs
        )
        rows, summary = rule.score(practice_predictions)
        practice = {
            "member": member,
            "recipe_digest": bundle["recipe_digest"],
            "seed": seed,
            "rule": rule.identity,
            "summary": summary,
            "rows": rows,
        }
        (out / "practice" / f"{member}.json").write_text(
            json.dumps(practice, indent=2, sort_keys=True) + "\n"
        )
        target.write_bytes(ev.bundle_bytes(bundle))
        done.append(member)
        print(
            json.dumps(
                {
                    "member": member,
                    "practice_score": summary.get("score"),
                    "seconds": round(time.monotonic() - started, 1),
                }
            ),
            flush=True,
        )
    return done


#: Recipes whose rebuilt artifact is identical to an earlier recipe's at the
#: same seed (identity by rebuilt artifact, OWNER-GRAPHITE-TEST-WAVE-04 §1).
#: Each pair is checked by `alias-check`; the analysis treats an alias as
#: extra seeds of its target.
ALIAS_CANDIDATES = (
    # Differ only by capacity_fade_head, which the rebuild ignores.
    ("graphite-run5-p-fa70c075f903", "graphite-run5-p-69268f1b74ec"),
    # Differ by basis_functions (20 vs 30): expected distinct, checked anyway.
    ("graphite-run5-p-4fd7fb870d2b", "graphite-run5-p-1d4aaff5d292"),
)


def alias_check(out):
    """Rebuild each candidate at its partner's first seed and compare the
    predictions byte for byte against the partner's bundle."""
    import gzip
    import hashlib

    from carbon.battery.value import experiment as ev
    from carbon.battery.value.contract import load as load_contract
    from carbon.battery.worker import DirectBackend

    out = Path(out)
    contract, _ = load_contract(CONTRACT)
    inputs = ev.panel_inputs(contract, ROOT)
    rows = {
        label: (strategy, seeds) for label, strategy, seeds in value_panel.PANELS[PANEL]
    }
    backend = DirectBackend(ROOT)

    def digest(predictions):
        text = json.dumps(predictions, sort_keys=True).encode()
        return "sha256:" + hashlib.sha256(text).hexdigest()

    results = []
    for alias, target in ALIAS_CANDIDATES:
        strategy, _ = rows[alias]
        _, seeds = rows[target]
        bundle, _ = ev.member_bundle(
            backend, f"alias-{alias}", strategy, seeds[0], inputs
        )
        reference = json.loads(
            gzip.decompress(
                (out / "predictions" / f"{target}-s{seeds[0]}.json.gz").read_bytes()
            )
        )
        results.append(
            {
                "alias": alias,
                "target": target,
                "seed": seeds[0],
                "alias_recipe_digest": bundle["recipe_digest"],
                "target_recipe_digest": reference["recipe_digest"],
                "alias_prediction_digest": digest(bundle["predictions"]),
                "target_prediction_digest": digest(reference["predictions"]),
                "identical_predictions": bundle["predictions"]
                == reference["predictions"],
            }
        )
    text = json.dumps(results, indent=2, sort_keys=True)
    (out / "aliasing.json").write_text(text + chr(10))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("predict")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--only", nargs="*")
    a = sub.add_parser("analyse")
    a.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("alias-check")
    c.add_argument("--out", type=Path, required=True)
    f = sub.add_parser("followup")
    f.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "predict":
        predict(args.out, args.only)
        return 0
    if args.command == "followup":
        from scripts.dev.battery import graphite_run5_followup

        return graphite_run5_followup.main(args.out)
    if args.command == "alias-check":
        print(json.dumps(alias_check(args.out), indent=1))
        return 0
    from scripts.dev.battery import graphite_run5_analysis

    return graphite_run5_analysis.main(args.out)


if __name__ == "__main__":
    sys.exit(main())
