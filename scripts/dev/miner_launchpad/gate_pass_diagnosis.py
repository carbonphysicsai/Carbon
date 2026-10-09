"""Summarize a miner's exported practice gate outcomes without trial details.

Run ``python -m scripts.dev.miner_launchpad.gate_pass_diagnosis EXPORT.json``.
The input is the Launchpad's own-research export. This reads existing public
PRACTICE feedback only; it does not train, predict, access an exam, or change a
gate. A score is descriptive even when the trial is ineligible.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from carbon.battery.scaffold import SCAFFOLD


def _default_mlp(recipe: object) -> bool:
    """Recognize the exact published scaffold, not merely an MLP family."""
    return type(recipe) is dict and recipe == SCAFFOLD


def _score(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def diagnose(export: object) -> dict:
    """Return aggregate evidence; absent or contradictory feedback is unknown."""
    if type(export) is not dict or type(export.get("experiments")) is not list:
        raise ValueError("expected a Launchpad export with an experiments list")

    gate_trials: Counter[str] = Counter()
    gate_cases: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    scaffold: Counter[str] = Counter()
    score_min: dict[str, float] = {}
    eligible_score_min: dict[str, float] = {}

    for trial in export["experiments"]:
        if type(trial) is not dict:
            counts["unreadable_trials"] += 1
            continue
        summary = trial.get("summary")
        if type(summary) is not dict:
            counts["missing_summaries"] += 1
            continue
        eligible = summary.get("eligible")
        failures = summary.get("gate_failures")
        scored = summary.get("n_scored")
        if (
            type(eligible) is not bool
            or type(failures) is not dict
            or type(scored) is not int
            or scored < 0
        ):
            counts["incomplete_summaries"] += 1
            continue
        if any(
            type(name) is not str or not name or type(n) is not int or n < 0
            for name, n in failures.items()
        ):
            counts["invalid_gate_counts"] += 1
            continue
        counts["checked_trials"] += 1
        contradictory = eligible and (any(failures.values()) or scored == 0)
        passed = eligible and not contradictory
        if passed:
            counts["eligible_trials"] += 1
        elif not eligible:
            counts["ineligible_trials"] += 1
        if contradictory:
            counts["contradictory_summaries"] += 1
        if not eligible and not any(failures.values()):
            counts["ineligible_without_reported_gate_failure"] += 1
        for name, n in failures.items():
            if n:
                gate_trials[name] += 1
                gate_cases[name] += n

        if _default_mlp(trial.get("recipe")):
            scaffold["checked_trials"] += 1
            if passed:
                scaffold["eligible_trials"] += 1
            elif not eligible:
                scaffold["ineligible_trials"] += 1
            else:
                scaffold["contradictory_summaries"] += 1
            if any(failures.values()):
                scaffold["trials_with_gate_failures"] += 1

        family = trial.get("backbone")
        score = _score(summary.get("score"))
        if type(family) is str and score is not None:
            score_min[family] = min(score, score_min.get(family, math.inf))
            if passed:
                eligible_score_min[family] = min(
                    score, eligible_score_min.get(family, math.inf)
                )

    return {
        "schema": "carbon.launchpad.gate-pass-diagnosis.v1",
        "basis": "Launchpad exported public PRACTICE summaries; score is descriptive",
        "exported_trials": len(export["experiments"]),
        "counts": {
            name: counts[name]
            for name in (
                "checked_trials",
                "eligible_trials",
                "ineligible_trials",
                "missing_summaries",
                "incomplete_summaries",
                "invalid_gate_counts",
                "unreadable_trials",
                "contradictory_summaries",
                "ineligible_without_reported_gate_failure",
            )
        },
        "gate_failures": {
            name: {
                "trials": gate_trials[name],
                "cases": gate_cases[name],
            }
            for name in sorted(gate_trials)
        },
        "published_default_mlp": {
            "checked_trials": scaffold["checked_trials"],
            "eligible_trials": scaffold["eligible_trials"],
            "ineligible_trials": scaffold["ineligible_trials"],
            "trials_with_gate_failures": scaffold["trials_with_gate_failures"],
            "contradictory_summaries": scaffold["contradictory_summaries"],
        },
        "lowest_descriptive_error_by_backbone": dict(sorted(score_min.items())),
        "lowest_eligible_error_by_backbone": dict(sorted(eligible_score_min.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path, help="Launchpad own-research export")
    args = parser.parse_args(argv)
    try:
        result = diagnose(json.loads(args.export.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
