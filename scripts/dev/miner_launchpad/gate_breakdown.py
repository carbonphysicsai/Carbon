"""Local public-PRACTICE gate counts for the shared Launchpad campaign view.

The counting rules mirror GATE-PASS-DIAGNOSIS-01. Only names from the public
Challenge contract leave this function; recipe and trial fields never do.
"""

from __future__ import annotations

from collections import Counter

SCHEMA = "carbon.launchpad.practice-gate-breakdown.v1"


def summarize(experiments, public_gates):
    """Count failures across all local trials, including ones outside the UI feed."""
    if type(experiments) is not list:
        experiments = []
    names = (
        tuple(dict.fromkeys(public_gates))
        if type(public_gates) is list
        and 0 < len(public_gates) <= 64
        and all(type(name) is str and 0 < len(name) <= 100 for name in public_gates)
        else ()
    )
    if not names:
        return {
            "schema": SCHEMA,
            "status": "UNAVAILABLE_PUBLIC_GATE_LIST",
            "basis": "No registered public gate list for this campaign",
            "exported_trials": len(experiments),
            "checked_trials": 0,
            "unverified_trial_summaries": len(experiments),
            "trials_passing_all_gates": 0,
            "gate_failures": {},
            "unrecognized_gate_names": 0,
        }

    gate_trials = Counter()
    gate_cases = Counter()
    unknown = set()
    checked = passed = 0
    allowed = set(names)
    for trial in experiments:
        if type(trial) is not dict or type(trial.get("summary")) is not dict:
            continue
        summary = trial["summary"]
        eligible = summary.get("eligible")
        failures = summary.get("gate_failures")
        scored = summary.get("n_scored")
        if (
            type(eligible) is not bool
            or type(failures) is not dict
            or type(scored) is not int
            or scored < 0
            or any(
                type(name) is not str or not name or type(n) is not int or n < 0
                for name, n in failures.items()
            )
        ):
            continue
        contradictory = eligible and (any(failures.values()) or scored == 0)
        if not contradictory:
            checked += 1
        if eligible and not contradictory:
            passed += 1
        for name, count in failures.items():
            if not count:
                continue
            if name in allowed:
                gate_trials[name] += 1
                gate_cases[name] += count
            else:
                unknown.add(name)

    return {
        "schema": SCHEMA,
        "status": (
            "NO_TRIALS"
            if not experiments
            else "INSUFFICIENT_VERIFIED_SUMMARIES" if checked == 0 else "AVAILABLE"
        ),
        "basis": "Local public PRACTICE summaries; gate counts are descriptive",
        "exported_trials": len(experiments),
        "checked_trials": checked,
        "unverified_trial_summaries": len(experiments) - checked,
        "trials_passing_all_gates": passed,
        "gate_failures": {
            name: {"trials": gate_trials[name], "cases": gate_cases[name]}
            for name in names
        },
        "unrecognized_gate_names": len(unknown),
    }
