"""The per-family attack report (OWNER-GRAPHITE-ATTACKER-01 §3).

Challenge-neutral. A *run* is one family's evidence from either side:

- the deterministic engine's family run (`attack.engine.run_family`, or the
  battery harness `carbon.battery.track_a`): its attempt records
  (`role` attack / specimen / control, `verdict` HELD / BREACHED / FIRED /
  SILENT / PASSED / WRONGLY_REFUSED);
- the Attacker's verdicts (`verify.Verdict`), grouped by `attacker_runs`;
- or an already normalized run: `{"family", "check", "attempts": [...]}`.

For each family the report states the attempts, the attempt budget used,
the verified findings, the near misses, the timeouts and crashes, whether it
was NOT_RUN, and the wrongful-rejection count on **held-out** valid controls
(the engine never reads those; only this report does). The rules:

- a timeout or crash (`INFRA`) is never a pass: it is counted apart and never
  as an attempt that completed or held;
- a family with no finding is `ATTEMPTED_COVERAGE`: what was tried, never an
  exploit-free bound;
- a higher-level family declared a seam is `NOT_RUN`, never a pass;
- findings use only the admission `CONDITIONS` vocabulary: a breached attempt
  carries its condition, and a valid control the boundary wrongly refused is a
  `FAILING_TRIGGER`. Any other condition is refused.

A report; grading stays with the technical owner, and nothing here is
security acceptance.
"""

from __future__ import annotations

from collections.abc import Mapping

from carbon.agent_campaign.attack import analysis, verify

SCHEMA = "carbon.attack.family-report.v1"
FINDING, ATTEMPTED_COVERAGE, NOT_RUN = "FINDING", "ATTEMPTED_COVERAGE", "NOT_RUN"
HELD, BREACHED, INFRA = verify.HELD, verify.BREACHED, verify.INFRA
#: Outcomes that did not complete an attempt: never a pass.
NOT_COMPLETED = frozenset({INFRA})
#: Engine record verdicts (`carbon.battery.track_a`).
_ENGINE_ATTACK = {"HELD": HELD, "BREACHED": BREACHED}
_CONTROL_PASSED, _CONTROL_REFUSED = "PASSED", "WRONGLY_REFUSED"
CLAIMS = {
    "exploit_free_bound": False,
    "security_acceptance": False,
    "graded": False,
    "timeouts_counted_as_pass": False,
}


def _get(item, name, default=None):
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


# -- normalising runs -------------------------------------------------------------------------
def attacker_runs(verdicts, *, families=()):
    """The Attacker's verdicts as normalized runs, one per family, in the
    order families are given then first seen. `families` (an adapter's
    `families()`) supplies each family's check."""
    checks = {analysis.family_name(f): analysis.family_check(f) for f in families}
    runs = {name: _run(name, checks[name]) for name in checks}
    for v in verdicts:
        run = runs.setdefault(v.family, _run(v.family, checks.get(v.family)))
        run["attempts"].append(
            {
                "attempt": v.attempt,
                "outcome": v.outcome,
                "conditions": list(v.conditions),
                "near_miss": v.near_miss,
                "evidence": v.evidence.get("result"),
            }
        )
    return list(runs.values())


def _run(name, check, source="attacker"):
    return {
        "family": name,
        "check": check,
        "source": source,
        "attempts": [],
        "controls": [],
    }


def runs_from_records(records):
    """Engine attempt records (track_a format) as normalized runs, one per
    family, in record order."""
    grouped = {}
    for r in records:
        grouped.setdefault(r["family"], []).append(r)
    return [normalize({"records": rows}) for rows in grouped.values()]


def _engine_state(records):
    """The engine's own family state: a silent specimen is INCONCLUSIVE
    (the detector could not fire), never a pass."""
    if any(r["verdict"] in ("BREACHED", _CONTROL_REFUSED) for r in records):
        return "FINDING"
    if any(r["role"] == "specimen" and r["verdict"] == "SILENT" for r in records):
        return "INCONCLUSIVE"
    return "IN_PROGRESS"


def normalize(run):
    """One run as `{"family", "check", "source", "attempts", "controls",
    "budget_used", "not_run", "engine_state"}`."""
    records = _get(run, "records")
    if records is not None:
        records = list(records)
        family = _get(run, "family") or _first(records, "family")
        check = (
            _get(run, "check")
            or (None if type(family) is str else analysis.family_check(family))
            or _first(records, "check")
        )
        out = _run(analysis.family_name(family), check, "engine")
        for r in records:
            if r["role"] == "attack":
                outcome = _ENGINE_ATTACK.get(r["verdict"])
                if outcome is None:
                    raise ValueError(
                        "engine_attack_verdict_unknown: " + str(r["verdict"])
                    )
                out["attempts"].append(
                    {
                        "attempt": r["attempt"],
                        "outcome": outcome,
                        "conditions": (
                            [verify.FAILING_TRIGGER] if outcome == BREACHED else []
                        ),
                        "near_miss": False,
                        "evidence": r.get("result_digest"),
                    }
                )
            elif r["role"] == "control":
                out["controls"].append(
                    {
                        "control": r["attempt"],
                        "split": "trained",
                        "outcome": _control_outcome(r["verdict"]),
                    }
                )
        out["engine_state"] = _engine_state(records)
    else:
        name = analysis.family_name(_get(run, "family"))
        out = _run(name, _get(run, "check"), _get(run, "source", "attacker"))
        out["attempts"] = [dict(a) for a in _get(run, "attempts", ())]
        out["controls"] = [dict(c) for c in _get(run, "controls", ())]
        out["engine_state"] = _get(run, "engine_state")
    for attempt in out["attempts"]:
        if attempt["outcome"] not in verify.OUTCOMES:
            raise ValueError("attempt_outcome_unknown: " + str(attempt["outcome"]))
        verify.check_conditions(attempt.get("conditions") or ())
    used = _get(run, "budget_used")
    out["budget_used"] = len(out["attempts"]) if used is None else used
    out["not_run"] = _get(run, "not_run")
    return out


def _first(records, key):
    return records[0].get(key) if records else None


def _control_outcome(value):
    if value is True or value == _CONTROL_PASSED:
        return _CONTROL_PASSED
    if value is False or value == _CONTROL_REFUSED:
        return _CONTROL_REFUSED
    if value == INFRA:
        return INFRA
    raise ValueError("control_outcome_unknown: " + str(value))


def held_out_controls(controls):
    """Held-out control results as `{family: [{"control", "outcome"}]}`.
    Each is a mapping with `family`, `control` and `passed` (bool) or
    `outcome` (PASSED / WRONGLY_REFUSED / INFRA), or a `(family, control,
    passed)` triple."""
    out = {}
    for item in controls:
        if isinstance(item, tuple):
            family, control, passed = item
            outcome = _control_outcome(passed)
        else:
            family, control = item["family"], item["control"]
            outcome = _control_outcome(
                item["passed"] if "passed" in item else item["outcome"]
            )
        out.setdefault(analysis.family_name(family), []).append(
            {"control": control, "split": "held_out", "outcome": outcome}
        )
    return out


def seam_names(seams):
    """`{name: reason}` for the adapter's NOT_RUN seam families."""
    out = {}
    for seam in seams:
        reason = _get(seam, "reason") or _get(seam, "why") or "declared seam: NOT_RUN"
        out[analysis.family_name(seam)] = reason
    return out


# -- the report -------------------------------------------------------------------------------
def _rejection(controls):
    done = [c for c in controls if c["outcome"] != INFRA]
    return {
        "controls": len(controls),
        "completed": len(done),
        "wrongly_refused": sum(c["outcome"] == _CONTROL_REFUSED for c in done),
    }


def summarize(run, held_out=(), not_run=None):
    """One family's line of the report, from a normalized run."""
    attempts = run["attempts"] if run is not None else []
    trained = run["controls"] if run is not None else []
    findings = [
        {"attempt": a["attempt"], "condition": c, "role": "attack"}
        for a in attempts
        if a["outcome"] == BREACHED
        for c in a["conditions"]
    ]
    for control in [*trained, *held_out]:
        if control["outcome"] == _CONTROL_REFUSED:
            findings.append(
                {
                    "attempt": control["control"],
                    "condition": verify.FAILING_TRIGGER,
                    "role": control["split"] + "_control",
                }
            )
    verify.check_conditions(f["condition"] for f in findings)
    completed = [a for a in attempts if a["outcome"] not in NOT_COMPLETED]
    not_run = not_run or (run or {}).get("not_run")
    if not_run is None and not attempts:
        not_run = "no_attempts_recorded"
    if findings:
        status = FINDING
    elif not_run is not None:
        status = NOT_RUN
    else:
        status = ATTEMPTED_COVERAGE
    return {
        "check": (run or {}).get("check"),
        "status": status,
        "attempts": len(attempts),
        "budget_used": (run or {}).get("budget_used", 0),
        "completed": len(completed),
        "held": sum(a["outcome"] == HELD for a in completed),
        "undetermined": sum(a["outcome"] == verify.UNDETERMINED for a in completed),
        "verified": sum(a["outcome"] == BREACHED for a in attempts),
        "findings": findings,
        "near_misses": sum(bool(a.get("near_miss")) for a in attempts),
        "timeouts_crashes": sum(a["outcome"] in NOT_COMPLETED for a in attempts),
        "not_run": not_run,
        "wrongful_rejection_trained": _rejection(trained),
        "wrongful_rejection_held_out": _rejection(list(held_out)),
        "engine_state": (run or {}).get("engine_state"),
        "bound": None,
    }


def family_report(runs, *, controls_held_out, seams=()):
    """The per-family report (module docstring). `controls_held_out` is
    required: a report without the held-out wrongful-rejection measure is not
    one. `seams` are the adapter's `level_families()`, each NOT_RUN."""
    normalized = {}
    for run in runs:
        run = normalize(run)
        if run["family"] in normalized:
            raise ValueError("two_runs_for_one_family: " + run["family"])
        normalized[run["family"]] = run
    held_out = held_out_controls(controls_held_out)
    seam = seam_names(seams)
    names = [*normalized, *(n for n in held_out if n not in normalized)]
    names += [n for n in seam if n not in names]
    families = {
        name: summarize(normalized.get(name), held_out.get(name, ()), seam.get(name))
        for name in names
    }
    findings = [
        {"family": name, **f}
        for name, line in families.items()
        for f in line["findings"]
    ]
    return {
        "schema": SCHEMA,
        "families": families,
        "findings": findings,
        "totals": {
            key: sum(line[key] for line in families.values())
            for key in (
                "attempts",
                "completed",
                "verified",
                "near_misses",
                "timeouts_crashes",
            )
        },
        "not_run": sorted(
            n for n, line in families.items() if line["status"] == NOT_RUN
        ),
        "zero_findings_reads_as": ATTEMPTED_COVERAGE,
        "claims": dict(CLAIMS),
    }
