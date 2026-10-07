"""Answer-key leak detection, operator-side and Challenge-neutral (owner,
2026-10-07, routed by the Test Lead).

A leaked hidden batch shows up as a hotkey scoring **anomalously better on
the batches it was scored on** than the same model scores on batches it
could not have seen:
- **fresh:** the next rotation's, imported but not yet live;
- **retired** or **published:** windows that have ended.

The gap is measured beyond the seed band.

For each scored submission, a Challenge's adapter supplies a **profile**:
its retained model's score on every batch it holds, each classed as
`current` (the score's active batches), `fresh`, `retired` or `published`.
The detector reports, per submission:
- `advantage`: the median score on the other batches minus the median on
  the current ones, signed so that positive means better on the current
  batches. A Challenge's `lower_is_better` gives the direction.
- `in_seed_band`: the advantage over the seed band, when one is given. That
  is the Challenge's measured seed-to-seed spread of one recipe, measured,
  not chosen here.
- `in_batch_spread`: the advantage over this model's own spread across the
  non-current batches (median absolute deviation), a band that needs no
  outside value.

Thresholds are HUMAN_INPUT. The report gives, for a sweep of cutoffs, how
many submissions each band would flag, as a curve the owner reads. **It never
gates, ranks, settles or reaches a miner.** It is descriptive operator
evidence, and nothing in the validator or weights reads it.

    python -m carbon.challenge_validator.leak_detection report --config DEPLOYMENT.json \\
        [--seed-band X] --out REPORT.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
SCHEMA = "carbon.challenge-validator.leak-detection.v1"
CLASSES = ("current", "fresh", "retired", "published")
#: The cutoffs a report sweeps, in band units. An engineering grid for the
#: curve, never a chosen threshold (HUMAN_INPUT).
SWEEP = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0)


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def _mad(values):
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return None
    centre = statistics.median(values)
    return statistics.median(abs(v - centre) for v in values)


def assess(profile, *, lower_is_better, seed_band=None):
    """One submission's leak measures from its `profile`
    (`{"hotkey", "submission_id", "batches": {fingerprint: {"class", "score"}}}`).
    Public values only: counts, medians and ratios."""
    by_class = {c: [] for c in CLASSES}
    for entry in profile["batches"].values():
        if entry["class"] in by_class and entry.get("score") is not None:
            by_class[entry["class"]].append(float(entry["score"]))
    current = _median(by_class["current"])
    unseen = by_class["fresh"] + by_class["retired"] + by_class["published"]
    other = _median(unseen)
    advantage = None
    if current is not None and other is not None:
        advantage = (other - current) if lower_is_better else (current - other)
    spread = _mad(unseen)

    def ratio(band):
        if advantage is None or band is None or band <= 0:
            return None
        return advantage / band

    return {
        "hotkey": profile["hotkey"],
        "submission_id": profile["submission_id"],
        "n": {c: len(v) for c, v in by_class.items()},
        "current_median": current,
        "unseen_median": other,
        "advantage": advantage,
        "in_seed_band": ratio(seed_band),
        "in_batch_spread": ratio(spread),
    }


def report(profiles, *, lower_is_better, seed_band=None, sweep=SWEEP):
    """The descriptive report over every profiled submission: each one's
    measures, and per band the count above each cutoff of the sweep."""
    rows = [
        assess(p, lower_is_better=lower_is_better, seed_band=seed_band)
        for p in profiles
    ]

    def curve(key):
        values = [r[key] for r in rows if r[key] is not None]
        return [
            {"cutoff": cutoff, "above": sum(v > cutoff for v in values)}
            for cutoff in sweep
        ]

    return {
        "schema": SCHEMA,
        "descriptive_only": True,
        "gates": "NONE",
        "threshold": "HUMAN_INPUT",
        "seed_band": seed_band,
        "lower_is_better": lower_is_better,
        "submissions": len(rows),
        "rows": sorted(
            rows,
            key=lambda r: (
                r["advantage"] is None,
                -(r["advantage"] or 0.0),
                r["submission_id"],
            ),
        ),
        "curves": {
            "in_seed_band": curve("in_seed_band"),
            "in_batch_spread": curve("in_batch_spread"),
        },
    }


def _write_private(path, value):
    path = Path(path)
    resolved = path.resolve()
    if resolved == REPOSITORY.resolve() or REPOSITORY.resolve() in resolved.parents:
        raise SystemExit("leak_report_inside_repository")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True, indent=1)
        handle.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.leak_detection")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("report")
    run.add_argument("--config", required=True)
    run.add_argument("--seed-band", type=float)
    run.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    from .battery import BatteryAdapter

    adapter = BatteryAdapter.from_deployment(args.config, repository=REPOSITORY)
    profiles = adapter.leak_profiles()
    result = report(
        profiles, lower_is_better=adapter.lower_is_better, seed_band=args.seed_band
    )
    _write_private(args.out, result)
    print(json.dumps({"submissions": result["submissions"], "out": args.out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
