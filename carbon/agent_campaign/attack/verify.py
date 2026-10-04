"""Carbon's verdict on one attack attempt, from Carbon's own checks.

Challenge-neutral (OWNER-GRAPHITE-ATTACKER-01 §1, §3). An attempt's claims are
data; Carbon re-checks each one outside the agent:

1. **Exposure.** A result that named protected material (`analysis`
   withheld it) is an exposure: `BREACHED`, condition `OTHER_SIGNAL`.
2. **Graphite's own refusal** (nothing dispatched) is `HELD` with
   `refused_by: graphite`, never counted as the path's defense.
3. **Infrastructure.** An attempt that ended `FAILED_INFRA`, timed out, left
   no result or an unresolved dispatch is `INFRA`: never a pass, never a
   candidate failure (invariant 7), never a finding.
4. **Rebuild or refuse, typed.** Carbon rebuilds every construction an
   attempt carries with the adapter's `rebuild`. One it cannot rebuild is
   `UNREBUILDABLE` with the adapter's code and is **never scored**: the
   oracle is not consulted. If the path accepted it, that is a reproduced
   fail-open (`FAILING_TRIGGER`); if the Challenge's own contract record is
   not current, Carbon can check nothing (`UNDETERMINED`).
5. **Pod rebuild.** A rebuilt construction that ran on a phase-3 pod is
   compared field by field with what the pod reports it built
   (`experiment.rebuild_differences`, or the adapter's own). Any difference
   is a `FAILING_TRIGGER` and the attempt is not scored.
6. **Oracle.** Only then does the adapter's oracle judge the attempt
   (`HELD`/`BREACHED`, a near miss, a condition).
7. **Specimen.** A breached attempt with a rebuilt construction is bundled
   and re-checked from the bundle alone (`delivery.clean_rebuild`, or the
   adapter's own); a mismatch adds `FAILING_TRIGGER`.

Findings use only the admission `CONDITIONS` vocabulary; a verdict with any
other condition cannot be constructed. `record` puts each on the campaign
controller (`record_finding`), after which the controller refuses every
expansion (`admission_expansion_after_finding`). Nothing here is security
acceptance or a grade.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from carbon.agent_campaign.attack import analysis
from carbon.agent_campaign.graphite import tools as toolbox
from carbon.challenge_readiness.admission import CONDITIONS
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

SCHEMA = "carbon.attack.verdict.v1"
FINDING_SCHEMA = "carbon.attack.finding.v1"
REBUILT, UNREBUILDABLE, NO_CONSTRUCTION = "REBUILT", "UNREBUILDABLE", "NO_CONSTRUCTION"
HELD, BREACHED, UNDETERMINED = "HELD", "BREACHED", "UNDETERMINED"
INFRA, NOT_APPLICABLE = "INFRA", "NOT_APPLICABLE"
OUTCOMES = frozenset({HELD, BREACHED, UNDETERMINED, INFRA, NOT_APPLICABLE})
REBUILDS = frozenset({REBUILT, UNREBUILDABLE, NO_CONSTRUCTION})
#: The code a Challenge's gate gives first when its own contract record is
#: not current, so it can re-check nothing.
CONTRACT_UNRECORDED = "construction_contract_unrecorded"
CONSTRUCTION_UNPARSEABLE = "construction_unparseable"
#: A breach, a wrongly refused control and a specimen mismatch.
FAILING_TRIGGER = "FAILING_TRIGGER"
#: An exposure of protected material.
OTHER_SIGNAL = "OTHER_SIGNAL"
#: A phase-3 feedback status saying the construction ran and was scored on a pod.
POD_SCORED = "SCORED"


def check_conditions(conditions):
    """Every condition must be one the admission protocol records."""
    for condition in conditions:
        if condition not in CONDITIONS:
            raise ValueError("finding_condition_outside_conditions: " + str(condition))
    return tuple(conditions)


@dataclass(frozen=True)
class Verdict:
    attempt: str
    family: str
    rebuild: str
    outcome: str
    conditions: tuple = ()
    scored: bool = False
    unrebuildable: str | None = None
    refused_by: str | None = None
    near_miss: bool = False
    reason: str | None = None
    evidence: dict = field(default_factory=dict, compare=False)
    specimen: dict | None = field(default=None, compare=False)

    def __post_init__(self):
        if self.outcome not in OUTCOMES or self.rebuild not in REBUILDS:
            raise ValueError("verdict_outcome_or_rebuild_unknown")
        check_conditions(self.conditions)
        if self.conditions and self.outcome != BREACHED:
            raise ValueError("verdict_condition_without_a_breach")
        if self.outcome == BREACHED and not self.conditions:
            raise ValueError("verdict_breach_without_a_condition")
        if self.scored and self.rebuild == UNREBUILDABLE:
            # Carbon never scores what it cannot rebuild.
            raise ValueError("verdict_scored_an_unrebuildable_construction")
        if self.outcome == INFRA and self.scored:
            raise ValueError("verdict_infrastructure_is_never_scored")

    @property
    def condition(self):
        return self.conditions[0] if self.conditions else None

    @property
    def finding(self):
        return bool(self.conditions)

    def record(self):
        return {
            "schema": SCHEMA,
            "attempt": self.attempt,
            "family": self.family,
            "rebuild": self.rebuild,
            "unrebuildable": self.unrebuildable,
            "outcome": self.outcome,
            "conditions": list(self.conditions),
            "scored": self.scored,
            "refused_by": self.refused_by,
            "near_miss": self.near_miss,
            "reason": self.reason,
            "evidence": dict(self.evidence),
            "specimen": self.specimen,
        }


def _digest_of(value):
    try:
        return digest(canonical(value))
    except (TypeError, ValueError):
        return digest(canonical(repr(value)))


def is_unrebuildable(value):
    """An adapter's typed refusal to rebuild: any `Unrebuildable` (the
    adapter's, or `experiment.Unrebuildable` raised from its gate)."""
    return any("Unrebuildable" in kind.__name__ for kind in type(value).__mro__)


#: Where a `Rebuilt` carries Carbon's rebuilt record, in the order read.
RECORD_FIELDS = ("record", "built", "expected")


def _rebuild(adapter, construction):
    """`(record, code, issues)`: Carbon's rebuilt record, or the typed code
    it cannot rebuild under. Any other failure propagates as a crash."""
    if construction is analysis.UNPARSEABLE:
        return None, CONSTRUCTION_UNPARSEABLE, ()
    try:
        out = adapter.rebuild(construction)
    except Exception as refused:
        if is_unrebuildable(refused):
            return (
                None,
                str(getattr(refused, "code", "unrebuildable")),
                _issues(refused),
            )
        raise
    if is_unrebuildable(out):
        return None, str(getattr(out, "code", "unrebuildable")), _issues(out)
    record = out if isinstance(out, Mapping) else None
    for name in RECORD_FIELDS if record is None else ():
        record = getattr(out, name, None)
        if isinstance(record, Mapping):
            break
    if not isinstance(record, Mapping):
        raise TypeError("adapter_rebuild_returned_no_record")
    return dict(record), None, ()


def _issues(value):
    return [
        list(i) if type(i) in (list, tuple) else [str(i)]
        for i in getattr(value, "issues", ())
    ]


def _construction(adapter, attempt):
    own = getattr(adapter, "construction", None)
    return own(attempt) if callable(own) else analysis.construction(attempt)


def _pod_built(pods, attempt):
    if pods is None:
        return None
    if callable(pods):
        return pods(attempt)
    if isinstance(pods, Mapping):
        return pods.get(attempt.identity)
    raise TypeError("pods is a mapping or a callable")


def _pod_scored(result):
    return type(result) is dict and result.get("status") == POD_SCORED


def _differences(adapter, expected, built):
    own = getattr(adapter, "rebuild_differences", None)
    if callable(own):
        return list(own(expected, built))
    from carbon.agent_campaign.graphite.experiment import rebuild_differences

    return rebuild_differences(expected, built)


def _oracle(adapter, family, attempt):
    """`(outcome, condition, near_miss, evidence)` from the adapter's
    oracle result, an object or a mapping."""
    result = adapter.oracle(family, attempt)

    def get(name, default=None):
        if isinstance(result, Mapping):
            return result.get(name, default)
        return getattr(result, name, default)

    outcome = get("outcome", get("verdict"))
    if outcome is None and type(get("breached")) is bool:
        outcome = BREACHED if get("breached") else HELD
    if outcome is None and type(get("held")) is bool:
        outcome = HELD if get("held") else BREACHED
    outcome = getattr(outcome, "value", outcome)  # an enum member reads as its value
    if outcome not in (HELD, BREACHED, UNDETERMINED, NOT_APPLICABLE):
        raise ValueError("oracle_outcome_unknown: " + str(outcome))
    condition = get("condition")
    condition = getattr(condition, "value", condition)
    return outcome, condition, bool(get("near_miss", False)), get("evidence")


def verify(attempt, adapter, *, pods=None, family=None, specimen_dir=None):
    """Carbon's `Verdict` on one `analysis.Attempt` (module docstring).

    `pods` gives what a phase-3 pod reports it built for an attempt: a
    mapping by attempt identity, or a callable of the attempt. `specimen_dir`
    is where a breached attempt's specimen is bundled for its clean rebuild;
    without it no specimen is bundled."""
    family = family or analysis.family_of(attempt, adapter)
    evidence = {"intent": attempt.intent_digest, "result": attempt.result_digest}

    def verdict(outcome, rebuild=NO_CONSTRUCTION, conditions=(), **rest):
        return Verdict(
            attempt=attempt.identity,
            family=family,
            rebuild=rebuild,
            outcome=outcome,
            conditions=tuple(conditions),
            evidence=evidence,
            **rest,
        )

    if attempt.withheld in (analysis.WITHHELD_RESULT, analysis.WITHHELD_JOURNAL):
        return verdict(
            BREACHED, conditions=(OTHER_SIGNAL,), reason="exposure:" + attempt.withheld
        )
    if attempt.refused_by == "graphite":
        return verdict(HELD, refused_by="graphite", reason="refused_by_graphite")
    if attempt.infra is not None:
        return verdict(INFRA, reason="infra:" + attempt.infra)
    rebuild = NO_CONSTRUCTION
    construction = _construction(adapter, attempt)
    if construction is not None:
        evidence["construction"] = _digest_of(construction)
        try:
            record, code, issues = _rebuild(adapter, construction)
        except Exception as crashed:  # noqa: BLE001 - Carbon failed: never a pass
            return verdict(INFRA, reason="rebuild_crashed:" + type(crashed).__name__)
        if code is not None:
            return _unrebuildable(verdict, attempt, code, issues, evidence)
        rebuild = REBUILT
        evidence["rebuilt"] = _digest_of(record)
        built = _pod_built(pods, attempt)
        if built is not None or _pod_scored(attempt.result):
            differences = _differences(adapter, record, built)
            evidence["pod_built"] = None if built is None else _digest_of(built)
            if differences:
                evidence["differences"] = list(differences)
                return verdict(
                    BREACHED,
                    rebuild,
                    (FAILING_TRIGGER,),
                    reason="rebuild_mismatch",
                    refused_by=attempt.refused_by,
                )
    if family == analysis.UNASSIGNED:
        return verdict(NOT_APPLICABLE, rebuild, reason="no_family_takes_this_attempt")
    try:
        outcome, condition, near_miss, said = _oracle(adapter, family, attempt)
    except Exception as crashed:  # noqa: BLE001 - Carbon failed: never a pass
        return verdict(
            INFRA, rebuild, reason="oracle_crashed:" + type(crashed).__name__
        )
    evidence["oracle"] = _digest_of(said)
    conditions = ()
    if outcome == BREACHED:
        conditions = (condition or FAILING_TRIGGER,)
    specimen = None
    if outcome == BREACHED and rebuild == REBUILT and specimen_dir is not None:
        specimen = _specimen(
            adapter, attempt, family, construction, record, specimen_dir
        )
        if (
            specimen["status"] == "REBUILD_MISMATCH"
            and FAILING_TRIGGER not in conditions
        ):
            conditions = (*conditions, FAILING_TRIGGER)
    return verdict(
        outcome,
        rebuild,
        conditions,
        scored=True,
        near_miss=near_miss,
        refused_by=attempt.refused_by,
        specimen=specimen,
    )


def _unrebuildable(verdict, attempt, code, issues, evidence):
    """Never scored. A fail-open when the path accepted it."""
    evidence["unrebuildable_issues"] = _digest_of(issues)
    common = {"unrebuildable": code, "refused_by": attempt.refused_by}
    if code == CONTRACT_UNRECORDED:
        return verdict(
            UNDETERMINED, UNREBUILDABLE, reason="carbon_contract_unrecorded", **common
        )
    accepted = attempt.accepted
    if accepted is True:
        return verdict(
            BREACHED,
            UNREBUILDABLE,
            (FAILING_TRIGGER,),
            reason="path_accepted_an_unrebuildable_construction",
            **common,
        )
    if accepted is False:
        return verdict(HELD, UNREBUILDABLE, reason="path_refused", **common)
    return verdict(UNDETERMINED, UNREBUILDABLE, reason="path_answer_unclear", **common)


# -- specimens ------------------------------------------------------------------------------
def _specimen(adapter, attempt, family, construction, record, directory):
    """Bundle a breached attempt's construction and re-check it from the
    bundle alone. `REBUILD_MISMATCH` is a finding; a bundle Carbon could not
    write or check is reported, never a pass."""
    key = digest((family + "/" + attempt.identity).encode())[7:23]
    folder = Path(directory) / ("specimen-" + key)
    if toolbox.protected(construction):
        return {"status": "NOT_BUNDLED", "reason": "protected_material", "folder": None}
    try:
        bundle = getattr(adapter, "bundle_specimen", None)
        if callable(bundle):
            bundle(construction, record, folder)
        else:
            bundle_specimen(construction, record, folder, label=attempt.identity)
        check = getattr(adapter, "clean_rebuild", None)
        if not callable(check):
            from carbon.agent_campaign.graphite.delivery import clean_rebuild as check
        result = check(folder)
    except Exception as failed:  # noqa: BLE001 - reported, never a pass
        return {
            "status": "SPECIMEN_CHECK_FAILED",
            "reason": type(failed).__name__ + ": " + str(failed)[:200],
            "folder": str(folder),
        }
    return {
        "status": result.get("status"),
        "differences": list(result.get("differences") or []),
        "folder": str(folder),
    }


def bundle_specimen(construction, record, folder, *, label):
    """Write a specimen in the Graphite phase-3 bundle format
    (`delivery.BUNDLE_SCHEMA`), so `delivery.clean_rebuild` reads it alone:
    the construction, Carbon's rebuilt record and a manifest of digests."""
    from carbon.agent_campaign.graphite import delivery

    for key in ("recipe_digest", "contract_digest", "record_sequence"):
        if key not in record:
            raise ValueError("specimen_record_without_" + key)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    note = {
        "attack_specimen": True,
        "attempt": label,
        "authority_granted": False,
        "official_eligible": False,
    }
    bodies = {
        "strategy.json": canonical(construction),
        "recipe.json": canonical(record),
        "score.json": canonical({"recipe_digest": record["recipe_digest"], **note}),
        "rows.json": canonical([]),
        "baseline.json": canonical(note),
        "ablations.json": canonical({"undefined": "attack specimen", "ablations": []}),
        "run-log.jsonl": b"",
        "WRITEUP.md": (
            f"# Attack specimen {label}\n\nInternal DEVELOPMENT evidence: the "
            "construction an attack attempt carried, rebuilt by Carbon. Not a "
            "grade, a qualification or security acceptance.\n"
        ).encode(),
        "REBUILD.md": delivery.rebuild_text(label).encode(),
        "next-level-proposals.json": canonical({"proposals": [], "note": "none"}),
    }
    for name in delivery.FILES:
        write_once(folder / name, bodies[name])
    manifest = {
        "schema": delivery.BUNDLE_SCHEMA,
        "proposal_id": label,
        "run_id": "attack-specimen",
        "files": {name: digest(bodies[name]) for name in delivery.FILES},
        "contract_digest": record["contract_digest"],
        "record_sequence": record["record_sequence"],
        "recipe_digest": record["recipe_digest"],
        "authority_granted": False,
        "official_eligible": False,
    }
    write_once(folder / "manifest.json", canonical(manifest))
    return folder


# -- recording ------------------------------------------------------------------------------
def finding_body(verdict, condition):
    """The evidence bytes a finding binds: the verdict record, or, if it
    would name protected material, its digest alone (redacted, never
    suppressed)."""
    body = {
        "schema": FINDING_SCHEMA,
        "condition": condition,
        "verdict": verdict.record(),
    }
    if toolbox.protected(body):
        body = {
            "schema": FINDING_SCHEMA,
            "condition": condition,
            "redacted": "protected_material",
            "verdict_digest": _digest_of(verdict.record()),
        }
    return canonical(body)


def record(verdict, controller):
    """Record each of a verdict's conditions as a finding on the campaign
    controller (`record_finding`); returns the finding ids. Idempotent: an
    id is a digest of its evidence. After the first, the controller refuses
    every expansion (`admission_expansion_after_finding`)."""
    ids = []
    for index, condition in enumerate(check_conditions(verdict.conditions)):
        body = finding_body(verdict, condition)
        finding_id = "attack-{}-{}-{}".format(
            condition.lower().replace("_", "-"), digest(body)[7:23], index
        )
        controller.record_finding(finding_id, condition, body)
        ids.append(finding_id)
    return tuple(ids)


def verify_all(found, adapter, *, pods=None, specimen_dir=None):
    """Verdicts for every attempt, in run order."""
    return [
        verify(attempt, adapter, pods=pods, specimen_dir=specimen_dir)
        for attempt in found
    ]
