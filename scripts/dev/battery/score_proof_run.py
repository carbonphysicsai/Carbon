"""The owner's one sitting for SCORE-PROOF-01, on the operator host.

    python -m scripts.dev.battery.score_proof_run --work W --quiz Q \
        --dev-results RESULTS --out W/proof [--estimate-only]

1. **Estimate.** It prints the expected CPU time for the registered proof
   members' rebuilds, from each recipe's steps and ensemble size, before
   anything runs.
2. **Rebuild on free host CPU.** The registered Level 0 proof members
   (`carbon/battery/value/panels/proof-panel-l0-v1.json`: stage A's 5
   bundles, minerH's and minerI's 6 submissions) predict the sealed tuning
   set and the quiz (`challenge_validator.tuning predict`). `score` then
   rewrites the scores and `q3-regret.json` for every member.
3. **Selection.** `score_proof --phase selection` compares every registered
   rule on the selection fold and writes `W/proof/selection.md`.

The confirmation phase is the second, short command, run after the owner
picks a rule from `selection.md` (`SCORE_PROOF_OWNER_SHEET.md`).

`--dev-results` is the proof contract's development decision results
(`ev4-dev-proof-v1`), computed off the sealed set from public EV4
references (`tuning_dev_panel --contract ev4-dev-proof-v1`). The sealed
cases never leave `W`; only aggregates are written to `--out`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: Planning constants, not measurements: CPU seconds per 1,000 training steps
#: of one member of a default-width MLP on one operator core, and per KNN fit.
#: The printed estimate is only a guide; the run records the real times.
MLP_S_PER_1000_STEPS = 40.0
KNN_S = 5.0


def panel_members():
    from carbon.battery.value import panel as pn

    return [
        {
            "member": f"{label}-s{seed}",
            "kind": "RECONSTRUCTED",
            "strategy": strategy,
            "seed": seed,
        }
        for label, strategy, seeds in pn.PROOF_L0
        for seed in seeds
    ]


def estimate_seconds(strategy):
    """A planning estimate of one rebuild's CPU seconds."""
    if strategy["backbone"] == "knn":
        return KNN_S
    p = strategy.get("parameters", {})
    steps = p.get("steps", 6000)
    width = p.get("width", 256)
    return (
        MLP_S_PER_1000_STEPS
        * steps
        / 1000
        * max(1, p.get("ensemble_members", 1))
        * (width / 256)
    )


def estimate(members, quiz=True):
    per = {m["member"]: estimate_seconds(m["strategy"]) for m in members}
    # One rebuild serves the tuning set and the quiz together (`tuning.predict`).
    return {"members": len(per), "rebuild_cpu_s": sum(per.values()), "per_member": per}


def _run(args):
    started = time.monotonic()
    subprocess.run([sys.executable, "-m", *args], cwd=ROOT, check=True)
    return time.monotonic() - started


def main(argv=None):
    parser = argparse.ArgumentParser(prog="score_proof_run")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--quiz", type=Path, required=True)
    parser.add_argument("--dev-results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--estimate-only", action="store_true")
    args = parser.parse_args(argv)
    members = panel_members()
    plan = estimate(members)
    hours = plan["rebuild_cpu_s"] / 3600
    print(
        json.dumps(
            {
                "step": "estimate",
                "proof_members": plan["members"],
                "rebuild_cpu_hours": round(hours, 2),
                "then": "score (minutes) and the selection report (about 10 minutes)",
                "note": "a planning estimate from recipe sizes, not a measurement",
            }
        ),
        flush=True,
    )
    if args.estimate_only:
        return 0
    panel_path = args.work / "proof-panel.json"
    fd = os.open(panel_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(
            {
                "schema": "carbon.challenge-validator.tuning-panel.v1",
                "members": members,
            },
            handle,
        )
    timings = {}
    timings["predict_s"] = _run(
        [
            "carbon.challenge_validator.tuning",
            "predict",
            "--work",
            str(args.work),
            "--panel",
            str(panel_path),
            "--quiz",
            str(args.quiz),
        ]
    )
    timings["score_s"] = _run(
        [
            "carbon.challenge_validator.tuning",
            "score",
            "--work",
            str(args.work),
            "--quiz",
            str(args.quiz),
        ]
    )
    timings["selection_s"] = _run(
        [
            "scripts.dev.battery.score_proof",
            "--phase",
            "selection",
            "--work",
            str(args.work),
            "--dev-results",
            str(args.dev_results),
            "--q3-regret",
            str(args.work / "q3-regret.json"),
            "--out",
            str(args.out),
        ]
    )
    print(
        json.dumps(
            {
                "step": "done",
                "timings_s": timings,
                "read": str(args.out / "selection.md"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
