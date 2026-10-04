"""The attack-family engine: one family's attacks, specimen and control.

Extracted from battery's Track A harness (`carbon/battery/track_a.py`) under
OWNER-GRAPHITE-ATTACKER-01, so every Challenge and every construction level
runs its families through the same detector logic. A family has:

- **attacks**, each run against the real boundary; each must be HELD;
- **a vulnerable specimen**: the same attack against a deliberately weakened
  boundary. The detector must fire there. A specimen that stays SILENT makes
  the family INCONCLUSIVE, never a pass;
- **a valid control**: a legitimate input against the real boundary. It must
  pass; a control the boundary refuses is a wrongful rejection.

A breached attack, or a control the real boundary wrongly refuses, is a
finding with the condition `FAILING_TRIGGER`, from the admission CONDITIONS
vocabulary (`carbon.challenge_readiness.admission`). Every finding is emitted;
none is suppressed.

A boundary that raises is never a pass either. `InfrastructureFailure` is
recorded FAILED_INFRA, `TimeoutError` TIMEOUT and any other exception CRASHED.
Each leaves the family INCONCLUSIVE, and none is a finding: infrastructure
failure is not a scientific result (invariant 7).

The attack budget is per family and counts attacks attempted. A specimen and
a control are detector diagnostics, not attempts. A budget smaller than the
family's attack set attempts the first attacks in order; the run records what
it attempted and what it left. Zero attempts is no evidence: INCONCLUSIVE.

The engine reads only trained controls. A held-out control passed to
`run_family` is refused (`HeldOutControlRefused`): held-out controls measure
wrongful rejection and are never tuned against.

No family state is an acceptance. A clean family is IN_PROGRESS: acceptance is
a reviewed LOCK (Challenge Admission §3.3), not a test result. The engine
never emits HELD as a family state; HELD is an attack's verdict.

Nothing here names a Challenge. Challenge-specific families come from an
adapter (`carbon.agent_campaign.attack.adapter`).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from carbon.challenge_readiness.admission import CHECKS, CONDITIONS, LEDGER_TRACK

ATTEMPT_SCHEMA = "carbon.attack.attempt.v1"

#: An attack's verdict against the real boundary.
HELD, BREACHED = "HELD", "BREACHED"
#: The specimen's verdict: the detector fired on the weakened boundary, or not.
FIRED, SILENT = "FIRED", "SILENT"
#: The control's verdict.
PASSED, REFUSED = "PASSED", "WRONGLY_REFUSED"
#: A boundary that did not answer. Never a pass, never a finding.
FAILED_INFRA, TIMEOUT, CRASHED = "FAILED_INFRA", "TIMEOUT", "CRASHED"
NO_ANSWER = frozenset({FAILED_INFRA, TIMEOUT, CRASHED})
ROLES = ("attack", "specimen", "control")
#: The family states the engine emits. None is an acceptance.
FAMILY_STATES = ("FINDING", "INCONCLUSIVE", "IN_PROGRESS")
#: The eight shared Track A checks a family may name.
TRACK_A_CHECKS = frozenset(CHECKS[LEDGER_TRACK])
FINDING_CONDITION = "FAILING_TRIGGER"
_NAME = re.compile(r"^[a-z][a-z0-9_]*\Z")


class InfrastructureFailure(Exception):
    """Raised by a boundary whose infrastructure failed. Recorded
    FAILED_INFRA: neither a pass nor a finding."""


class HeldOutControlRefused(ValueError):
    """The engine was handed a held-out control. It never reads them."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=repr)


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Family:
    """One attack family. `attacks()` returns `((name, input), ...)`;
    `boundary`, `specimen` take an input and return a result; `breached`
    takes a result and returns True when the attack got through; `control()`
    returns True when the valid control passes the real boundary."""

    name: str
    check: str
    boundary: Callable
    attacks: Callable
    specimen: Callable
    breached: Callable
    control: Callable
    #: What the family attacks, in the protocol's words.
    description: str = ""

    def __post_init__(self):
        if not (isinstance(self.name, str) and _NAME.match(self.name)):
            raise ValueError("family_name_is_a_lowercase_token")
        if self.check not in TRACK_A_CHECKS:
            raise ValueError("family_check_is_a_track_a_check: " + str(self.check))
        for part in ("boundary", "attacks", "specimen", "breached", "control"):
            if not callable(getattr(self, part)):
                raise TypeError("family_part_is_callable: " + part)

    @property
    def family_id(self):
        """The name, as battery's harness has always called it."""
        return self.name

    @property
    def protocol_family(self):
        return self.description


@dataclass(frozen=True)
class RunContext:
    """What every attempt record names besides the family: the Challenge, the
    construction profile (`level-N`) and the record schema."""

    challenge: str | None = None
    profile: str | None = None
    schema: str = ATTEMPT_SCHEMA


@dataclass(frozen=True)
class FamilyRun:
    """The attempt records of one family run, in order, with its budget."""

    family: str
    check: str
    records: tuple = field(repr=False)
    budget: int | None
    available: int
    attempted: int

    @property
    def exhausted(self):
        """True when the budget stopped the run before the attack set ended."""
        return self.attempted < self.available

    @property
    def not_attempted(self):
        return self.available - self.attempted


@dataclass(frozen=True)
class Finding:
    condition: str
    family: str
    attempt: str
    role: str
    evidence_digest: str

    def __post_init__(self):
        if self.condition not in CONDITIONS:
            raise ValueError(
                "finding_condition_outside_conditions: " + str(self.condition)
            )

    def as_dict(self):
        return {
            "condition": self.condition,
            "family": self.family,
            "attempt": self.attempt,
            "role": self.role,
            "evidence_digest": self.evidence_digest,
        }


def control_from(boundary, value_fn, breached):
    """A control that passes when the real boundary accepts `value_fn()`, or,
    for a boundary that does not say, when the result is not a breach."""

    def run():
        result = boundary(value_fn())
        return result.get("accepted", not breached(result))

    return run


def evaluate_control(family, control):
    """True when one control passes the family's real boundary. A control
    carries either its own `check()` or a `value` for the boundary, whose
    result must say whether it was `accepted`: a boundary that only reports
    breaches cannot show a wrongful refusal, so such a control raises and
    answers nothing. This only measures; it does not choose what the engine
    runs."""
    check = getattr(control, "check", None)
    if check is not None:
        return bool(check())
    result = family.boundary(control.value)
    if not (isinstance(result, dict) and isinstance(result.get("accepted"), bool)):
        raise TypeError("control_result_says_whether_it_was_accepted")
    return result["accepted"]


def answer(call, *args):
    """(result, None) or (evidence, verdict) when the call did not answer."""
    try:
        return call(*args), None
    except InfrastructureFailure as failed:
        return {"exception": type(failed).__name__}, FAILED_INFRA
    except TimeoutError as failed:
        return {"exception": type(failed).__name__}, TIMEOUT
    except Exception as failed:  # noqa: BLE001 - a crash is recorded, never a pass
        return {"exception": type(failed).__name__}, CRASHED


def _check_budget(budget):
    if budget is not None and (type(budget) is not int or budget < 0):
        raise ValueError("budget_is_a_non_negative_integer_or_none")


def run_family(family, *, budget=None, context=None, controls=None):
    """Run one family: each attack within the budget against the real
    boundary and its specimen, then the control. `controls`, when given, are
    trained controls (objects with `name`, `split` and `value` or `check`),
    each recorded under its own name; otherwise `family.control()` is recorded
    as `valid_control`. Returns a FamilyRun."""
    if type(family) is not Family:
        raise TypeError("an exact engine Family is required")
    _check_budget(budget)
    context = context or RunContext()
    if controls is not None:
        controls = tuple(controls)
        for control in controls:
            if getattr(control, "split", None) != "trained":
                raise HeldOutControlRefused(str(getattr(control, "name", control)))
    records = []

    def record(role, name, verdict, result):
        records.append(
            {
                "schema": context.schema,
                "challenge": context.challenge,
                "profile": context.profile,
                "family": family.name,
                "check": family.check,
                "role": role,
                "attempt": name,
                "verdict": verdict,
                "result_digest": digest(result),
            }
        )

    attacks = tuple(family.attacks())
    names = [name for name, _ in attacks]
    if len(names) != len(set(names)):
        raise ValueError("attack_names_are_unique")
    chosen = attacks if budget is None else attacks[:budget]
    for name, value in chosen:
        result, failed = answer(family.boundary, value)
        if failed is None:
            failed = BREACHED if family.breached(result) else HELD
        record("attack", name, failed, result)
        weak, silent = answer(family.specimen, value)
        if silent is None:
            silent = FIRED if family.breached(weak) else SILENT
        record("specimen", name, silent, weak)
    if controls is None:
        passed, failed = answer(family.control)
        record(
            "control",
            "valid_control",
            failed or (PASSED if passed else REFUSED),
            passed,
        )
    else:
        for control in controls:
            passed, failed = answer(evaluate_control, family, control)
            verdict = failed or (PASSED if passed else REFUSED)
            record("control", control.name, verdict, passed)
    return FamilyRun(
        family=family.name,
        check=family.check,
        records=tuple(records),
        budget=budget,
        available=len(attacks),
        attempted=len(chosen),
    )


def _rows(runs):
    for item in runs:
        if isinstance(item, FamilyRun):
            yield from item.records
        else:
            yield item


def findings(runs: Iterable):
    """Every condition the runs raise, as Findings. Takes FamilyRuns or
    attempt records. None is suppressed."""
    out = []
    for r in _rows(runs):
        if (r["role"], r["verdict"]) in (("attack", BREACHED), ("control", REFUSED)):
            out.append(
                Finding(
                    condition=FINDING_CONDITION,
                    family=r["family"],
                    attempt=r["attempt"],
                    role=r["role"],
                    evidence_digest=r["result_digest"],
                )
            )
    return out


def family_state(run, family_id=None):
    """FINDING when an attack was breached or a control wrongly refused;
    INCONCLUSIVE when there is no evidence (no attack, no control, a specimen
    that stayed silent or is missing, or a boundary that did not answer);
    otherwise IN_PROGRESS. Never an acceptance.

    Takes a FamilyRun, or attempt records and the family's id."""
    if isinstance(run, FamilyRun):
        rows = list(run.records)
    else:
        rows = [r for r in run if r["family"] == family_id]
    if any(r["verdict"] in (BREACHED, REFUSED) for r in rows):
        return "FINDING"
    attacks = [r for r in rows if r["role"] == "attack"]
    specimens = [r for r in rows if r["role"] == "specimen"]
    controls = [r for r in rows if r["role"] == "control"]
    if not attacks or not controls or len(specimens) != len(attacks):
        return "INCONCLUSIVE"  # no evidence is never a pass
    if any(r["verdict"] in NO_ANSWER for r in rows):
        return "INCONCLUSIVE"
    if any(r["verdict"] != FIRED for r in specimens):
        return "INCONCLUSIVE"  # the detector could not fire: no evidence
    return "IN_PROGRESS"
