"""Benchmark B2: the Attacker against the deterministic harness, per family.

OWNER-GRAPHITE-ATTACKER-01 §4. For each family, the Attacker's runs and the
deterministic harness's runs (the adapter's own, `adapter_baseline`) are
compared at an **equal attempt budget**: each side's first `budget`
attempts, in the order they ran, and nothing after. Each side reports what
`report.summarize` reports (attempts, budget used, verified findings, near
misses, timeouts and crashes, NOT_RUN, wrongful rejection on held-out
controls), so a timeout is never a pass and no finding reads as attempted
coverage, never as a bound.

B2 is recorded per attack-knowledge store snapshot: the store digest the
Attacker ran under is part of the record, so a later store is a later B2. A
record made without one says `store_snapshot_missing`. An engine side's family
state is recomputed from its records within the budget; controls are engine
diagnostics, never budgeted. A comparison, never a grade: which side found
more is descriptive.

**Distinct by the rebuilt artifact (OWNER-GRAPHITE-TEST-WAVE-04 §1).** The
equal budget is an attempt budget: what each side spent, reworded copies
included. What each side *found* is counted by construction identity
(`attack.identity.distinct`): `verified_difference` is the difference in
distinct verified findings (distinct rebuilt artifacts, plus distinct
behaviours of breaches that have none), so a reworded copy of a construction
already found adds nothing. The per-attempt difference is kept as
`verified_attempts_difference`, a diagnostic.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from carbon.agent_campaign.attack import identity, report

#: v2: `verified_difference` by distinct construction identity (§1);
#: `verified_attempts_difference` per attempt, a diagnostic.
SCHEMA = "carbon.attack.b2.v2"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
#: Whether a B2 record names the attack-knowledge store snapshot it ran under.
SNAPSHOT_PINNED, SNAPSHOT_MISSING = "PINNED", "store_snapshot_missing"


def _budget_for(budget, family):
    value = budget.get(family) if isinstance(budget, Mapping) else budget
    if type(value) is not int or value < 0:
        raise ValueError("b2_budget_is_a_non_negative_integer_per_family: " + family)
    return value


def _within(run, budget):
    """The run with only its first `budget` attempts: the equal budget.

    For an engine run the family state is recomputed from the records left:
    the cut attacks and their specimens. Controls are kept whole: in the
    engine a control is a detector diagnostic, not an attempt, so it is never
    budgeted (`attack.engine.run_family`), and a wrongly refused control is a
    finding at any budget. An attacker run has no engine state."""
    if run is None:
        return None
    taken = run["attempts"][:budget]
    out = {**run, "attempts": taken, "budget_used": len(taken)}
    if run.get("not_attempted") is not None:
        # What the cut leaves is unattempted too.
        out["not_attempted"] = run["not_attempted"] + len(run["attempts"]) - len(taken)
    records = run.get("records")
    if records is not None:
        names = {a["attempt"] for a in taken}
        kept = [r for r in records if r["role"] == "control" or r["attempt"] in names]
        out["records"] = kept
        out["engine_state"] = report.engine_state(kept)
    return out


def found(line):
    """What one side found, for the comparison: its distinct verified
    findings (`identity.distinct`), never its breached attempts (§1)."""
    return line["distinct"]["verified"]


def _side(run, budget, held_out, not_run, check=None, family=None):
    line = report.summarize(_within(run, budget), held_out, not_run, check, family)
    line["budget"] = budget
    return line


def b2(
    attacker_runs,
    baseline_runs,
    *,
    budget,
    store_snapshot=None,
    controls_held_out=(),
    seams=(),
):
    """B2 per family at an equal attempt budget (module docstring).

    `budget` is one attempt budget for every family, or `{family: budget}`
    covering each one. `store_snapshot` is the attack-knowledge store digest
    the Attacker ran under."""
    if store_snapshot is not None and (
        type(store_snapshot) is not str or not _DIGEST.fullmatch(store_snapshot)
    ):
        raise ValueError("b2_store_snapshot_is_a_sha256_digest")
    attacker = _by_family(attacker_runs)
    baseline = _by_family(baseline_runs)
    held_out = report.held_out_controls(controls_held_out)
    seam = report.seam_names(seams)
    seam_check = report.seam_checks(seams)
    names = [*attacker, *(n for n in baseline if n not in attacker)]
    names += [n for n in seam if n not in names]
    families = {}
    for name in names:
        n = _budget_for(budget, name)
        controls = held_out.get(name, ())
        check = seam_check.get(name)
        mine = _side(attacker.get(name), n, controls, seam.get(name), check, name)
        theirs = _side(baseline.get(name), n, controls, seam.get(name), check, name)
        families[name] = {
            "check": mine["check"] or theirs["check"],
            "budget": n,
            "attacker": mine,
            "baseline": theirs,
            # Distinct constructions found, never reworded copies (§1).
            "verified_difference": found(mine) - found(theirs),
            "verified_attempts_difference": mine["verified"] - theirs["verified"],
        }
    return {
        "schema": SCHEMA,
        "store_snapshot": store_snapshot,
        # B2 is recorded per store snapshot; one without it says so plainly.
        "store_snapshot_status": (
            SNAPSHOT_MISSING if store_snapshot is None else SNAPSHOT_PINNED
        ),
        "budget": budget if isinstance(budget, int) else dict(budget),
        "identity_rule": identity.RULE,
        "families": families,
        "checks": report.checks_view(families),
        "zero_findings_reads_as": report.ATTEMPTED_COVERAGE,
        "claims": {**report.CLAIMS, "comparison_is_descriptive": True},
    }


def _by_family(runs):
    out = {}
    for run in runs:
        run = report.normalize(run)
        if run["family"] in out:
            raise ValueError("two_runs_for_one_family: " + run["family"])
        out[run["family"]] = run
    return out


def adapter_baseline(adapter, root="."):
    """B2's deterministic side for one adapter: its own deterministic harness
    when it has one (`adapter.deterministic_baseline(root)`, already
    normalized runs), else its engine runs (`attack.adapter.run_adapter`).
    The neutral core names no Challenge: a Challenge's harness is reached
    only through its adapter."""
    own = getattr(adapter, "deterministic_baseline", None)
    if callable(own):
        return list(own(root))
    from carbon.agent_campaign.attack import adapter as core

    return list(core.run_adapter(adapter))
