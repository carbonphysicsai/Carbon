"""Carbon's verdict on one attack attempt, from Carbon's own checks.

Challenge-neutral (OWNER-GRAPHITE-ATTACKER-01 §1, §3). An attempt's claims are
data; Carbon re-checks each one outside the agent:

1. **Exposure.** A result that named protected material (`analysis`
   withheld it) is an exposure: `BREACHED`, condition `OTHER_SIGNAL`. A
   loop-local echo of the agent's own protected words is the same finding
   with its own reason (`protected_named_by_agent`): a development finding
   that names a protected case is itself `OTHER_SIGNAL`.
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
   is a `FAILING_TRIGGER` and the attempt is not scored. A pod-scored
   attempt whose build record was not supplied is `UNDETERMINED`
   (`pod_build_record_not_supplied`): Carbon's own evidence is missing, which
   is neither a breach nor a score. A crash in the comparison is `INFRA`.
6. **Oracle.** Only then does the adapter's oracle judge the attempt
   (`HELD`/`BREACHED`, a near miss, a condition). It is handed an
   `OracleAttempt` view: `name`, `arguments`, `tool`, `path_accepted` (what
   the path did) and, unless the adapter derives its own input per family
   (`attempt_input`), `value` (the construction, else the arguments).
   An oracle `EXPOSURE` is `BREACHED` with `OTHER_SIGNAL`; one that did not
   answer (`FAILED_INFRA`, `TIMEOUT`, `CRASHED`) is `INFRA`; `NOT_RUN` (a
   seam) is `NOT_APPLICABLE`; `INCONCLUSIVE` (a hold the detector cannot
   vouch for, or a path answer that is not plain) is `UNDETERMINED`. A
   `HELD` counts only with the family specimen's `FIRED` verdict on the same
   input: an oracle result that says it held without that specimen check
   (`{"held": True}`) is `UNDETERMINED` (`oracle_hold_without_specimen`). The
   view says whether Carbon rebuilt a construction (`rebuilt`); the generic
   oracle (`attack.adapter.family_oracle`) judges nothing without one, which
   reads `UNDETERMINED` (`oracle_needs_a_rebuilt_construction`). Only a
   `HELD` or `BREACHED` judgement is scored.
7. **Specimen.** A breached attempt with a rebuilt construction is bundled
   and re-checked from the bundle alone (`delivery.clean_rebuild`, or the
   adapter's own); a mismatch adds `FAILING_TRIGGER`.
8. **Agreed admissible** (verdict v2, GRAPHITE-ORACLE-AGREED-ADMISSIBLE-01).
   An ADVISORY tool accepted a construction and the oracle could not vouch for
   the agreement (`oracle_inconclusive`: the family's detector does not fire
   on a valid design). When Carbon rebuilt that construction, the adapter's
   `agreement(family, attempt)` says Carbon's AUTHORITATIVE chain accepts it
   (never `validate_for_challenge` alone) AND it is within the level's
   contract, on the same construction, and nothing else was found (no
   breach, usability record, canary or isolation hit, or authoritative
   refusal), the verdict is `AGREED_ADMISSIBLE`: no breach and no usability
   defect. It is never scored, never a hold and never a finding; for closure
   it counts like `NOT_APPLICABLE`. An adapter with no `agreement` hook
   never yields it.

9. **Advisory exposure** (verdict v2). An oracle `EXPOSURE` (BREACHED with
   `OTHER_SIGNAL`) is a finding whatever the tool's authority: authority
   decides only whether *acceptance* is a breach, and an exposure of
   protected material is a disclosure failure an advisory tool hands the
   agent directly. It is never a usability record and never
   `AGREED_ADMISSIBLE`.

Versions. `carbon.attack.verdict.v1` records carry five outcomes; v2 adds
`AGREED_ADMISSIBLE` and reads an advisory exposure as a finding. A v1 record
keeps its meaning (invariant 10): its `UNDETERMINED` stays `UNDETERMINED`
and is never re-read as agreed, and a v1 advisory usability record stays a
usability record, never re-read as a finding (`outcome_of`).

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
from carbon.challenge_readiness.admission import CONDITIONS
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

#: v2: the `AGREED_ADMISSIBLE` outcome (module docstring, step 8).
SCHEMA = "carbon.attack.verdict.v2"
SCHEMA_V1 = "carbon.attack.verdict.v1"
FINDING_SCHEMA = "carbon.attack.finding.v1"
REBUILT, UNREBUILDABLE, NO_CONSTRUCTION = "REBUILT", "UNREBUILDABLE", "NO_CONSTRUCTION"
HELD, BREACHED, UNDETERMINED = "HELD", "BREACHED", "UNDETERMINED"
INFRA, NOT_APPLICABLE = "INFRA", "NOT_APPLICABLE"
#: An ADVISORY tool and Carbon's AUTHORITATIVE chain both accept a valid,
#: in-contract construction: no breach, no usability defect, nothing scored.
AGREED_ADMISSIBLE = "AGREED_ADMISSIBLE"
AGREED_ADMISSIBLE_REASON = "advisory_and_authoritative_agree_admissible"
OUTCOMES_V1 = frozenset({HELD, BREACHED, UNDETERMINED, INFRA, NOT_APPLICABLE})
OUTCOMES = OUTCOMES_V1 | {AGREED_ADMISSIBLE}
#: Each verdict schema's outcome vocabulary: a record is read under its own.
OUTCOMES_BY_SCHEMA = {SCHEMA_V1: OUTCOMES_V1, SCHEMA: OUTCOMES}
#: Outcomes that close an attempt as nothing to judge, never a hold or a pass.
CLOSED_UNJUDGED = frozenset({NOT_APPLICABLE, AGREED_ADMISSIBLE})
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
#: Oracle verdicts that answered nothing (the engine's NO_ANSWER): INFRA.
ORACLE_NO_ANSWER = frozenset({"FAILED_INFRA", "TIMEOUT", "CRASHED"})
#: An oracle's exposure verdict: BREACHED with OTHER_SIGNAL.
ORACLE_EXPOSURE = "EXPOSURE"
ORACLE_EXPOSURE_REASON = "oracle_exposure"
#: A seam's oracle verdict: nothing judged.
ORACLE_NOT_RUN = "NOT_RUN"
#: A hold the oracle's detector cannot vouch for (its specimen did not fire),
#: or a path answer that is not plain: no evidence, UNDETERMINED.
ORACLE_INCONCLUSIVE = "INCONCLUSIVE"
ORACLE_INCONCLUSIVE_REASON = "oracle_inconclusive"
#: An adapter's reading for an attempt it withheld because it names protected
#: material (battery's PROTECTED_WITHHELD, core NOT_RUN): NOT_APPLICABLE with
#: its own reason, so the report shows it NOT COVERED, never held.
ORACLE_PROTECTED_WITHHELD = "PROTECTED_WITHHELD"
PROTECTED_WITHHELD_REASON = "oracle_protected_withheld"
#: A path that refused a construction Carbon cannot rebuild: never scored,
#: and never a hold for its family (the family's attack never ran).
REFUSED_AT_REBUILD_REASON = "path_refused"
#: The specimen verdict that makes an oracle's HELD evidence: the family's
#: detector fired on the same input (`attack.engine.FIRED`).
SPECIMEN_FIRED = "FIRED"
#: An oracle that said HELD without a specimen that fired: never scored.
HOLD_WITHOUT_SPECIMEN_REASON = "oracle_hold_without_specimen"
#: The generic oracle's reading for an attempt with no rebuilt construction
#: (`attack.adapter.NO_REBUILT_CONSTRUCTION`), and its verdict's reason.
ORACLE_NO_REBUILT_CONSTRUCTION = "NO_REBUILT_CONSTRUCTION"
NO_REBUILT_CONSTRUCTION_REASON = "oracle_needs_a_rebuilt_construction"


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
    authority: str | None = None
    evidence: dict = field(default_factory=dict, compare=False)
    specimen: dict | None = field(default=None, compare=False)
    #: An advisory tool that accepted what Carbon's own boundary refuses: a
    #: usability record (`{attempt, operation, kind, reason}`), never a finding.
    usability: dict | None = field(default=None, compare=False)

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
        if self.outcome == AGREED_ADMISSIBLE and (
            self.scored
            or self.usability is not None
            or self.rebuild != REBUILT
            or self.authority != analysis.ADVISORY
        ):
            # Structural: never scored, never beside a usability record, only
            # on a construction Carbon rebuilt, only for an ADVISORY tool.
            raise ValueError("verdict_agreed_admissible_outside_its_guard")

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
            "authority": self.authority,
            "evidence": dict(self.evidence),
            "specimen": self.specimen,
            "usability": self.usability,
        }


def outcome_of(record):
    """A verdict record's outcome, read under its own schema's vocabulary
    (`OUTCOMES_BY_SCHEMA`). A v1 record keeps its v1 meaning: nothing is
    re-read under a later vocabulary (invariant 10). An unknown schema, or an
    outcome its schema does not carry, is refused."""
    schema = record.get("schema")
    vocabulary = OUTCOMES_BY_SCHEMA.get(schema)
    if vocabulary is None:
        raise ValueError("verdict_schema_unknown: " + str(schema))
    outcome = record.get("outcome")
    if outcome not in vocabulary:
        raise ValueError(
            "verdict_outcome_outside_its_schema: " + str(schema) + " " + str(outcome)
        )
    return outcome


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
#: A digest-only `Rebuilt` (the engine adapter's): its digests and `detail`.
DIGEST_FIELDS = ("construction_digest", "rebuilt_digest")


def record_of(rebuilt):
    """Carbon's rebuilt record, as a dict, from what an adapter's `rebuild`
    returned: a mapping; an object whose `record`, `built` or `expected` is
    one; the engine adapter's `Rebuilt(construction_digest, rebuilt_digest,
    detail)` whose `detail["record"]` is one (battery's); or, without such a
    record, that `Rebuilt` read as its digests plus its detail. Anything else
    is a TypeError (a crash)."""
    if isinstance(rebuilt, Mapping):
        return dict(rebuilt)
    for name in RECORD_FIELDS:
        record = getattr(rebuilt, name, None)
        if isinstance(record, Mapping):
            return dict(record)
    detail = getattr(rebuilt, "detail", None)
    detail = dict(detail) if isinstance(detail, Mapping) else {}
    if isinstance(detail.get("record"), Mapping):
        return dict(detail["record"])
    digests = {name: getattr(rebuilt, name, None) for name in DIGEST_FIELDS}
    if all(type(value) is str for value in digests.values()):
        return {**detail, **digests}
    raise TypeError("adapter_rebuild_returned_no_record")


def _rebuild(adapter, construction):
    """`(rebuilt, record, code, issues)`: what the adapter returned and
    Carbon's rebuilt record, or the typed code it cannot rebuild under. Any
    other failure propagates as a crash."""
    if construction is analysis.UNPARSEABLE:
        return None, None, CONSTRUCTION_UNPARSEABLE, ()
    try:
        out = adapter.rebuild(construction)
    except Exception as refused:
        if is_unrebuildable(refused):
            return (
                None,
                None,
                str(getattr(refused, "code", "unrebuildable")),
                _issues(refused),
            )
        raise
    if is_unrebuildable(out):
        return None, None, str(getattr(out, "code", "unrebuildable")), _issues(out)
    return out, record_of(out), None, ()


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


def _differences(adapter, rebuilt, record, built):
    """The fields on which a pod's build differs from Carbon's. An adapter's
    own `rebuild_differences(rebuilt, built)` is handed exactly what its
    `rebuild` returned; the default (`experiment.rebuild_differences`)
    compares Carbon's rebuilt record."""
    own = getattr(adapter, "rebuild_differences", None)
    if callable(own):
        return list(own(rebuilt, built))
    from carbon.agent_campaign.graphite.experiment import rebuild_differences

    return rebuild_differences(record, built)


#: An `OracleAttempt` carrying no `value`: the adapter derives its own input.
NO_VALUE = object()


@dataclass(frozen=True)
class OracleAttempt:
    """What the adapter's oracle is handed for one session attempt.

    `name` is the journal identity; `arguments` and `tool` the call;
    `path_accepted` what the path did (True, False, or None when its answer is
    not plain). `value` is the input the attempt submits (its construction
    when it carries one, else its arguments), for an oracle that re-runs it
    against the real boundary (`attack.adapter.family_oracle`). For an adapter
    that derives its own input per family (`attempt_input(family, attempt)`,
    battery's) the view carries no `value` at all, so the adapter's own
    derivation is never overridden. The attempt's content was already checked
    for protected material."""

    name: str
    arguments: dict = field(compare=False)
    tool: str
    path_accepted: bool | None
    refused_by: str | None = None
    given: object = field(default=NO_VALUE, compare=False, repr=False)
    #: Whether Carbon rebuilt a construction for this attempt (False when it
    #: carried none or none Carbon could rebuild). The generic oracle
    #: (`attack.adapter.family_oracle`) never scores an attempt without one.
    rebuilt: bool | None = None
    #: The tool's authority class (`analysis.AUTHORITATIVE/ADVISORY/
    #: MINER_LOCAL`), and, when the path refused, what it refused
    #: (`analysis.Attempt.refusal_kind`: `construction`, `request` or None).
    #: Only a `construction` refusal can be a wrongful rejection.
    authority: str | None = None
    refusal_kind: str | None = None

    @property
    def value(self):
        if self.given is NO_VALUE:
            raise AttributeError("value")  # `hasattr`/`getattr` read: absent
        return self.given

    @property
    def identity(self):
        return self.name

    @property
    def operation(self):
        return self.tool.removeprefix(analysis.PREFIX)


def oracle_attempt(
    attempt, construction=None, *, adapter=None, rebuilt=None, authority=None
):
    """The `OracleAttempt` view of an `analysis.Attempt` (see the class)."""
    if callable(getattr(adapter, "attempt_input", None)):
        given = NO_VALUE
    elif construction is not None:
        given = construction
    else:
        given = dict(attempt.arguments)
    return OracleAttempt(
        name=attempt.identity,
        arguments=dict(attempt.arguments),
        tool=attempt.tool,
        path_accepted=attempt.accepted,
        refused_by=attempt.refused_by,
        given=given,
        rebuilt=rebuilt,
        authority=authority,
        refusal_kind=attempt.refusal_kind,
    )


def _oracle(adapter, family, attempt):
    """`(outcome, condition, near_miss, evidence, reason)` from the adapter's
    oracle result, an object or a mapping (module docstring, step 6)."""
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
    condition = get("condition")
    condition = getattr(condition, "value", condition)
    evidence = get("evidence", get("evidence_digest"))
    reason = None
    reading = get("reading")
    reading = getattr(reading, "value", reading)
    if outcome == ORACLE_EXPOSURE:
        outcome, condition = BREACHED, condition or OTHER_SIGNAL
        reason = ORACLE_EXPOSURE_REASON
    elif outcome in ORACLE_NO_ANSWER:
        outcome, condition, reason = INFRA, None, "oracle_no_answer:" + outcome
    elif outcome == ORACLE_NOT_RUN and reading == ORACLE_NO_REBUILT_CONSTRUCTION:
        # The generic oracle refused to judge an attempt Carbon rebuilt no
        # construction for: no evidence, never scored.
        outcome, condition = UNDETERMINED, None
        reason = NO_REBUILT_CONSTRUCTION_REASON
    elif outcome == ORACLE_NOT_RUN:
        reason = (
            PROTECTED_WITHHELD_REASON
            if reading == ORACLE_PROTECTED_WITHHELD
            else "oracle_not_run"
        )
        outcome, condition = NOT_APPLICABLE, None
    elif outcome == ORACLE_INCONCLUSIVE:
        outcome, condition, reason = UNDETERMINED, None, ORACLE_INCONCLUSIVE_REASON
    elif outcome == HELD:
        # A hold is evidence only when the family's detector fired on the
        # same input (`attack.adapter.OracleResult`'s rule). A result that
        # says it held without that specimen check, such as a bare
        # `{"held": True}`, judged nothing: UNDETERMINED, never scored.
        specimen = get("specimen")
        specimen = getattr(specimen, "value", specimen)
        if specimen != SPECIMEN_FIRED:
            outcome, condition = UNDETERMINED, None
            reason = HOLD_WITHOUT_SPECIMEN_REASON
    if outcome not in (HELD, BREACHED, UNDETERMINED, NOT_APPLICABLE, INFRA):
        raise ValueError("oracle_outcome_unknown: " + str(outcome))
    return outcome, condition, bool(get("near_miss", False)), evidence, reason


def _usability(attempt, kind, reason):
    """A usability record: an advisory tool diverged from Carbon's own
    boundary. Never a finding."""
    return {
        "attempt": attempt.identity,
        "operation": attempt.operation,
        "kind": kind,
        "reason": reason,
    }


def is_exposure(condition, reason):
    """An oracle breach that is an exposure of protected material (its
    `OTHER_SIGNAL` condition, or the oracle's own `EXPOSURE` verdict). A
    disclosure failure whichever tool emits it: never a usability record."""
    return condition == OTHER_SIGNAL or reason == ORACLE_EXPOSURE_REASON


def agreement_may_apply(outcome, reason):
    """Only an oracle that judged nothing because its detector could not
    vouch for the path's answer (`oracle_inconclusive`) may be read as an
    agreement. A breach, a hold, a seam, a no-answer or any other
    undetermined reading never is."""
    return outcome == UNDETERMINED and reason == ORACLE_INCONCLUSIVE_REASON


def authoritative_accepts(said):
    """The adapter says Carbon's AUTHORITATIVE chain accepts the
    construction (battery: `carbon_admits`, strict parse ->
    `compile_submission` -> `experiment.admit`). Only a plain True counts."""
    return said.get("authoritative_accepts") is True


def within_contract(said):
    """The adapter says the construction is within the level's contract
    (battery: every capability it uses is one the level permits). Only a
    plain True counts."""
    return said.get("within_contract") is True


def agreed_admissible(
    adapter,
    family,
    attempt,
    view,
    construction,
    rebuild,
    authority,
    *,
    canaries=(),
    carrier=None,
    evidence=None,
):
    """Whether an attempt is `AGREED_ADMISSIBLE` (module docstring, step 8).
    Every guard must hold; anything else, including an adapter with no
    `agreement` hook or one that raises, fails closed (False)."""
    if authority != analysis.ADVISORY:
        return False  # only an advisory tool's agreement; never MINER_LOCAL
    if attempt.withheld is not None or attempt.infra is not None:
        return False
    if attempt.refused_by != "path" or attempt.accepted is not True:
        return False  # the advisory tool must have answered and accepted
    if rebuild != REBUILT or construction is None:
        return False  # Carbon rebuilt the construction under its contract
    if analysis.isolation_breach(attempt, canaries=canaries, carrier=carrier):
        return False  # a canary or isolation hit is never an agreement
    hook = getattr(adapter, "agreement", None)
    if not callable(hook):
        return False
    try:
        said = hook(family, view)
    except Exception:  # noqa: BLE001 - Carbon could not say: fail closed
        return False
    if not isinstance(said, Mapping):
        return False
    if not authoritative_accepts(said):
        return False
    if not within_contract(said):
        return False
    if _digest_of(said.get("construction")) != _digest_of(construction):
        return False  # the agreement must be on the construction Carbon rebuilt
    if evidence is not None:
        evidence["agreement"] = _digest_of(
            {
                "authoritative_accepts": True,
                "within_contract": True,
                "construction": _digest_of(construction),
            }
        )
    return True


def verify(
    attempt,
    adapter,
    *,
    pods=None,
    family=None,
    specimen_dir=None,
    canaries=(),
    carrier=None,
):
    """Carbon's `Verdict` on one `analysis.Attempt` (module docstring).

    `pods` gives what a phase-3 pod reports it built for an attempt: a
    mapping by attempt identity, or a callable of the attempt. `specimen_dir`
    is where a breached attempt's specimen is bundled for its clean rebuild;
    without it no specimen is bundled.

    A FAILING_TRIGGER is raised only when an AUTHORITATIVE tool accepted what
    Carbon refuses. An ADVISORY tool's divergence (it accepted what Carbon
    refuses) is a usability record, never a finding; an exposure of protected
    material (OTHER_SIGNAL) is a finding whatever the tool's authority. A MINER_LOCAL action is
    judged against the carrier's isolation boundary (`analysis.
    isolation_breach`) from its own result and the operator's canary registry
    (`canaries`) and carrier evidence (`carrier`); reading its own sandbox and
    staged files is not a finding."""
    family = family or analysis.family_of(attempt, adapter)
    evidence = {"intent": attempt.intent_digest, "result": attempt.result_digest}
    authority = None

    def verdict(outcome, rebuild=NO_CONSTRUCTION, conditions=(), **rest):
        rest.setdefault("authority", authority)
        return Verdict(
            attempt=attempt.identity,
            family=family,
            rebuild=rebuild,
            outcome=outcome,
            conditions=tuple(conditions),
            evidence=evidence,
            **rest,
        )

    if attempt.withheld == analysis.WITHHELD_ECHO:
        return verdict(
            BREACHED, conditions=(OTHER_SIGNAL,), reason="protected_named_by_agent"
        )
    if attempt.withheld in (analysis.WITHHELD_RESULT, analysis.WITHHELD_JOURNAL):
        return verdict(
            BREACHED, conditions=(OTHER_SIGNAL,), reason="exposure:" + attempt.withheld
        )
    if attempt.withheld == analysis.WITHHELD_TARGET:
        # The path answered with an attack target Graphite withheld from the
        # agent: no exposure, and nothing Carbon can judge.
        return verdict(
            UNDETERMINED, reason="result_withheld_attack_target", refused_by="path"
        )
    if attempt.refused_by == "graphite":
        return verdict(HELD, refused_by="graphite", reason="refused_by_graphite")
    if attempt.infra is not None:
        return verdict(INFRA, reason="infra:" + attempt.infra)
    # An attempt no family takes never becomes a breach (exposure is caught
    # above): judged ahead of any rebuild or oracle.
    if family == analysis.UNASSIGNED:
        return verdict(NOT_APPLICABLE, reason="no_family_takes_this_attempt")
    # The tool's authority. Unknown fails closed: never authoritative, and
    # nothing judged (UNDETERMINED), never a pass and never a finding.
    try:
        authority = analysis.authority_of(attempt, adapter)
    except analysis.UnknownTool:
        return verdict(
            UNDETERMINED, reason="tool_authority_unknown", refused_by=attempt.refused_by
        )
    if authority == analysis.MINER_LOCAL:
        breach = analysis.isolation_breach(attempt, canaries=canaries, carrier=carrier)
        if breach is None:
            # It stayed inside its own sandbox and staged files.
            return verdict(
                NOT_APPLICABLE,
                reason="miner_local_within_sandbox",
                refused_by=attempt.refused_by,
            )
        evidence["isolation"] = breach["detail_digest"]
        return verdict(
            BREACHED,
            NO_CONSTRUCTION,
            (FAILING_TRIGGER,),
            reason="miner_local_isolation_breach:" + ",".join(breach["reasons"]),
            refused_by=attempt.refused_by,
        )
    advisory = authority == analysis.ADVISORY
    rebuild = NO_CONSTRUCTION
    construction = _construction(adapter, attempt)
    if construction is not None:
        evidence["construction"] = _digest_of(construction)
        try:
            rebuilt, record, code, issues = _rebuild(adapter, construction)
        except Exception as crashed:  # noqa: BLE001 - Carbon failed: never a pass
            return verdict(INFRA, reason="rebuild_crashed:" + type(crashed).__name__)
        if code is not None:
            return _unrebuildable(verdict, attempt, code, issues, evidence, advisory)
        rebuild = REBUILT
        evidence["rebuilt"] = _digest_of(record)
        built = _pod_built(pods, attempt)
        if built is None and _pod_scored(attempt.result):
            # The pod scored it and Carbon was not handed its build record:
            # Carbon's own evidence is missing. Neither a breach nor a score.
            return verdict(
                UNDETERMINED,
                rebuild,
                reason="pod_build_record_not_supplied",
                refused_by=attempt.refused_by,
            )
        if built is not None:
            evidence["pod_built"] = _digest_of(built)
            try:
                differences = _differences(adapter, rebuilt, record, built)
            except Exception as crashed:  # noqa: BLE001 - Carbon failed: never a pass
                return verdict(
                    INFRA,
                    rebuild,
                    reason="rebuild_compare_crashed:" + type(crashed).__name__,
                )
            if differences:
                # A pod built something other than Carbon's own rebuild: an
                # integrity finding, from Carbon's comparison, not from the
                # tool's authority (only a pod-scored attempt reaches here).
                evidence["differences"] = list(differences)
                return verdict(
                    BREACHED,
                    rebuild,
                    (FAILING_TRIGGER,),
                    reason="rebuild_mismatch",
                    refused_by=attempt.refused_by,
                )
    view = oracle_attempt(
        attempt,
        construction,
        adapter=adapter,
        rebuilt=rebuild == REBUILT,
        authority=authority,
    )
    try:
        outcome, condition, near_miss, said, why = _oracle(adapter, family, view)
    except Exception as crashed:  # noqa: BLE001 - Carbon failed: never a pass
        return verdict(
            INFRA, rebuild, reason="oracle_crashed:" + type(crashed).__name__
        )
    evidence["oracle"] = _digest_of(said)
    if agreement_may_apply(outcome, why) and agreed_admissible(
        adapter,
        family,
        attempt,
        view,
        construction,
        rebuild,
        authority,
        canaries=canaries,
        carrier=carrier,
        evidence=evidence,
    ):
        # Step 8: the advisory tool and Carbon's authoritative chain agree on
        # a valid, in-contract construction. Never scored, never a hold.
        return verdict(
            AGREED_ADMISSIBLE,
            rebuild,
            reason=AGREED_ADMISSIBLE_REASON,
            refused_by=attempt.refused_by,
        )
    if outcome in (INFRA, NOT_APPLICABLE, UNDETERMINED):
        # The oracle answered nothing, judged nothing, or the family is a
        # seam: never scored. Only HELD or BREACHED is a scored judgement.
        return verdict(outcome, rebuild, reason=why, refused_by=attempt.refused_by)
    if outcome == BREACHED and advisory and not is_exposure(condition, why):
        # An advisory tool accepted what Carbon's own boundary refuses: a
        # usability record, never a finding. An exposure is not acceptance:
        # it falls through to a finding whatever the tool's authority.
        return verdict(
            UNDETERMINED,
            rebuild,
            reason="advisory_boundary_divergence",
            refused_by=attempt.refused_by,
            usability=_usability(
                attempt, "oracle_divergence", why or "advisory_boundary_divergence"
            ),
        )
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
        reason=why,
        specimen=specimen,
    )


def _unrebuildable(verdict, attempt, code, issues, evidence, advisory=False):
    """Never scored. An AUTHORITATIVE path that accepted an unrebuildable
    construction is a fail-open (FAILING_TRIGGER); an ADVISORY tool that
    accepted it is a usability record, never a finding."""
    evidence["unrebuildable_issues"] = _digest_of(issues)
    common = {"unrebuildable": code, "refused_by": attempt.refused_by}
    if code == CONTRACT_UNRECORDED:
        return verdict(
            UNDETERMINED, UNREBUILDABLE, reason="carbon_contract_unrecorded", **common
        )
    accepted = attempt.accepted
    if accepted is True:
        if advisory:
            return verdict(
                UNDETERMINED,
                UNREBUILDABLE,
                reason="advisory_accepted_unrebuildable",
                usability=_usability(
                    attempt,
                    "accepted_unrebuildable",
                    "advisory_accepted_unrebuildable",
                ),
                **common,
            )
        return verdict(
            BREACHED,
            UNREBUILDABLE,
            (FAILING_TRIGGER,),
            reason="path_accepted_an_unrebuildable_construction",
            **common,
        )
    if accepted is False:
        # The path and Carbon both refused it, but the family's attack never
        # ran: the report counts it refused at rebuild, never as held.
        return verdict(HELD, UNREBUILDABLE, reason=REFUSED_AT_REBUILD_REASON, **common)
    return verdict(UNDETERMINED, UNREBUILDABLE, reason="path_answer_unclear", **common)


# -- specimens ------------------------------------------------------------------------------
def _specimen(adapter, attempt, family, construction, record, directory):
    """Bundle a breached attempt's construction and re-check it from the
    bundle alone. `REBUILD_MISMATCH` is a finding; a bundle Carbon could not
    write or check is reported, never a pass."""
    from carbon.agent_campaign.attack import knowledge

    key = digest((family + "/" + attempt.identity).encode())[7:23]
    folder = Path(directory) / ("specimen-" + key)
    # The store's material rule (registered sealed identities and protected
    # markers), not the checkout deny list: a breach that names an attack
    # target such as a `.env` path keeps its specimen, bundled operator-side.
    if knowledge.sealed(construction) or knowledge.held_out(construction):
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
def names_protected(value):
    """The redaction rule for finding evidence: the attack-knowledge store's
    narrowed protected rule (`attack.knowledge.protected`: Graphite's
    protected markers and the deny fragments that name sealed or confirmation
    material) or a registered sealed identity. Not the live session's broad
    request filter (`graphite.tools.protected`), which also refuses the attack
    targets `.env`, `secret`, `credential` and repository paths: a finding
    naming one is a breach to keep, not material to redact."""
    from carbon.agent_campaign.attack import knowledge

    return knowledge.protected(value) or knowledge.sealed_identity(value) is not None


def finding_body(verdict, condition):
    """The evidence bytes a finding binds: the verdict record, or, if it
    would name protected material (`names_protected`), its digest alone
    (redacted, never suppressed)."""
    body = {
        "schema": FINDING_SCHEMA,
        "condition": condition,
        "verdict": verdict.record(),
    }
    if names_protected(body):
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


def _record_body(controller, condition, body, tag):
    check_conditions((condition,))
    if names_protected(body):
        body = {
            "schema": FINDING_SCHEMA,
            "condition": condition,
            "redacted": "protected_material",
            "body_digest": _digest_of(body),
        }
    payload = canonical(body)
    finding_id = "attack-{}-{}-{}".format(
        condition.lower().replace("_", "-"), digest(payload)[7:23], tag
    )
    controller.record_finding(finding_id, condition, payload)
    return finding_id


def record_control(
    controller, *, family, control, split, identity, input_digest, outcome, source
):
    """Record a valid control the boundary wrongly refused as a
    `FAILING_TRIGGER` finding on the campaign controller, bound to the
    control's registered identity, its input digest and its outcome; returns
    the finding id. Held-out and trained controls, from the report or a
    deterministic run, go through this one path, so each stops expansion
    (`admission_expansion_after_finding`)."""
    if outcome != "WRONGLY_REFUSED":
        raise ValueError("only_a_wrongly_refused_control_is_a_finding")
    for value in (identity, input_digest):
        if value is not None and not (
            type(value) is str and value.startswith("sha256:")
        ):
            raise ValueError("control_evidence_is_digest_bound")
    if identity is None:
        raise ValueError("control_evidence_is_digest_bound")
    body = {
        "schema": FINDING_SCHEMA,
        "condition": FAILING_TRIGGER,
        "source": source,
        "role": split + "_control",
        "family": family,
        "control": control,
        "control_identity": identity,
        "input_digest": input_digest,
        "outcome": outcome,
    }
    return _record_body(controller, FAILING_TRIGGER, body, "c")


def record_engine_findings(runs, controller, *, source="deterministic_baseline"):
    """Record every finding a deterministic engine run raises (a breached
    attack or a wrongly refused trained control, `engine.findings`) on the
    campaign controller, each bound to its digest evidence; returns the ids."""
    from carbon.agent_campaign.attack import engine

    ids = []
    for found in engine.findings(runs):
        body = {
            "schema": FINDING_SCHEMA,
            "condition": found.condition,
            "source": source,
            **found.as_dict(),
        }
        ids.append(_record_body(controller, found.condition, body, "e"))
    return ids


def verify_all(
    found, adapter, *, pods=None, specimen_dir=None, canaries=(), carrier=None
):
    """Verdicts for every attempt, in run order."""
    return [
        verify(
            attempt,
            adapter,
            pods=pods,
            specimen_dir=specimen_dir,
            canaries=canaries,
            carrier=carrier,
        )
        for attempt in found
    ]
