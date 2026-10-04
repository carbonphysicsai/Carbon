"""What one Challenge at one construction level supplies to the attack engine.

OWNER-GRAPHITE-ATTACKER-01 item 1: one adapter per Challenge and per
construction level. An adapter supplies:

- `challenge_id`, `level` (0-5, `carbon.challenge_pipeline.ladder.LEVELS`)
  and `contract_digest`, the construction contract it attacks;
- `families()`: its families (`FamilyDef`). Each names one of the eight
  shared Track A checks (`challenge_readiness.admission` CHECKS), what it
  attacks, an attack example and a valid control example, and, when Carbon
  runs it deterministically, its engine `Family`. A family whose evidence is
  elsewhere cites it in `evidence` instead;
- `controls(split)`: valid controls, split `trained` (the engine runs them)
  and `held_out` (they only measure wrongful rejection, never tuning), each
  versioned;
- `oracle(family, attempt)`: Carbon's own verdict on one attempt, re-run
  against the real boundary (`OracleResult`);
- `rebuild(construction)`: Carbon's rebuild of an attack construction, or a
  typed refusal (`Rebuilt` or `Unrebuildable`). An unrebuildable construction
  is never scored;
- `level_families()`: families that need a level or material this adapter
  does not have, such as participant code, child processes or solver hybrids.
  Each is a `SeamFamily`, always NOT_RUN, never a pass.

Every one of the eight checks must be supplied, by a family or by a seam, or
the adapter is refused (`check_not_supplied`).

A Graphite session also needs the Challenge's session surface
(`SessionSurface`): the permission inventory, the public identity, Carbon's
admission refusals, the wall allowance for one sandbox code run and a recipe
its contract refuses. An adapter that drives Graphite provides it.

`ADAPTERS[(challenge_id, level)]` is the registry. Built-in adapters register
themselves from `carbon.agent_campaign.attack.adapters` the first time the
registry is read. A test registers its own and removes it after.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from carbon.challenge_pipeline.ladder import LEVELS
from carbon.challenge_readiness.admission import CHECKS, CONDITIONS, LEDGER_TRACK

from . import engine

#: The eight shared Track A checks, in the order admission lists them.
TRACK_A_CHECKS = (
    "baseline_and_permission_ablation",
    "artifact_and_dependency_attacks",
    "adaptive_feedback_and_state_attacks",
    "score_exploitation_and_tail_failures",
    "resource_and_failure_accounting",
    "construction_evaluation_isolation",
    "reconstruction_and_recipient_rebuild",
    "fresh_attack_confirmation",
)
if set(TRACK_A_CHECKS) != CHECKS[LEDGER_TRACK]:  # pragma: no cover - drift guard
    raise ImportError("TRACK_A_CHECKS no longer matches admission CHECKS")
SPLITS = ("trained", "held_out")
NOT_RUN = "NOT_RUN"
#: Why Carbon cannot rebuild an attack construction. Never scored.
UNREBUILDABLE_CODES = frozenset(
    {
        "not_declarative",
        "refused_by_contract",
        "outside_level",
        "protected_material",
        "unknown_construction",
        "rebuild_failed_infra",
    }
)
#: The oracle's verdict when the boundary held but the family's specimen did
#: not fire on the attempt: the detector is blind to it. Never a pass.
INCONCLUSIVE = "INCONCLUSIVE"
#: An oracle's verdicts: the engine's attack verdicts, INCONCLUSIVE for a hold
#: the detector cannot vouch for, and NOT_RUN for a seam.
ORACLE_VERDICTS = frozenset(
    {engine.HELD, engine.BREACHED, *engine.NO_ANSWER, INCONCLUSIVE, NOT_RUN}
)
#: The specimen's verdicts an oracle result may carry.
SPECIMEN_VERDICTS = frozenset({engine.FIRED, engine.SILENT, *engine.NO_ANSWER})
SESSION_FUNCTIONS = (
    "permission_inventory",
    "public_identity",
    "admission_refusals",
    "code_run_seconds",
    "recipe_outside_contract",
)
BUILTIN_PACKAGE = "carbon.agent_campaign.attack.adapters"
_TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*\Z")
_NAME = re.compile(r"^[a-z][a-z0-9_]*\Z")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}\Z")


class AdapterError(ValueError):
    """An adapter the engine refuses; `code` names why."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _text(value):
    return isinstance(value, str) and value.strip() != ""


def level_profile(level):
    """The construction profile name a level's attempt records carry."""
    return f"level-{level}"


@dataclass(frozen=True)
class Control:
    """One valid control. `split` is `trained` or `held_out`. A control
    carries a `value` for the family's boundary, or its own `check()`; a
    check-only control declares the digest of the input it submits
    (`input_digest`), so its registered identity is its content.

    `identity` (`engine.control_identity`) is the family and the input's
    digest: never the name, version or split, so a held-out control
    relabelled `trained` keeps its identity and is still refused."""

    name: str
    family: str
    split: str
    version: str
    value: object = None
    check: Callable | None = None
    input_digest: str | None = None

    def __post_init__(self):
        if not (isinstance(self.name, str) and _NAME.match(self.name)):
            raise AdapterError("control_name_is_a_lowercase_token", str(self.name))
        if self.split not in SPLITS:
            raise AdapterError("control_split_is_trained_or_held_out", self.name)
        if not _text(self.version):
            raise AdapterError("control_is_versioned", self.name)
        if self.check is not None and not callable(self.check):
            raise AdapterError("control_check_is_callable", self.name)
        if self.input_digest is not None and not (
            isinstance(self.input_digest, str) and _DIGEST.match(self.input_digest)
        ):
            raise AdapterError("control_input_digest_is_sha256", self.name)

    @property
    def identity(self):
        return engine.control_identity(self)

    @property
    def submitted_digest(self):
        """The digest of what this control submits, or None."""
        return engine.control_input_digest(self)


@dataclass(frozen=True)
class FamilyDef:
    """One family an adapter supplies, under one Track A check."""

    name: str
    check: str
    #: The boundary it attacks, in words.
    boundary: str
    attack_example: object
    control_example: object
    #: The deterministic engine family, when Carbon runs one.
    family: engine.Family | None = None
    #: Reused evidence (test node ids) when the family is not run here.
    evidence: tuple = ()

    def __post_init__(self):
        if not (isinstance(self.name, str) and _NAME.match(self.name)):
            raise AdapterError("family_name_is_a_lowercase_token", str(self.name))
        if self.check not in TRACK_A_CHECKS:
            raise AdapterError("family_check_is_a_track_a_check", self.name)
        if not _text(self.boundary):
            raise AdapterError("family_names_its_boundary", self.name)
        if self.attack_example is None or self.control_example is None:
            raise AdapterError("family_has_an_attack_and_a_control_example", self.name)
        if self.family is None and not self.evidence:
            raise AdapterError("family_is_run_here_or_cites_evidence", self.name)
        if self.family is not None and (
            type(self.family) is not engine.Family
            or self.family.name != self.name
            or self.family.check != self.check
        ):
            raise AdapterError("engine_family_matches_its_definition", self.name)
        if not all(_text(e) for e in self.evidence):
            raise AdapterError("evidence_is_named", self.name)


@dataclass(frozen=True)
class SeamFamily:
    """A family declared and not run: NOT_RUN, never a pass."""

    name: str
    check: str
    #: The construction level from which it would apply.
    level: int
    reason: str
    state: str = NOT_RUN

    def __post_init__(self):
        if not (isinstance(self.name, str) and _NAME.match(self.name)):
            raise AdapterError("seam_name_is_a_lowercase_token", str(self.name))
        if self.check not in TRACK_A_CHECKS:
            raise AdapterError("seam_check_is_a_track_a_check", self.name)
        if type(self.level) is not int or self.level not in LEVELS:
            raise AdapterError("seam_level_is_a_ladder_level", self.name)
        if not _text(self.reason):
            raise AdapterError("seam_states_why_it_is_not_run", self.name)
        if self.state != NOT_RUN:
            raise AdapterError("a_seam_is_not_run", self.name)


@dataclass(frozen=True)
class AttackInput:
    """One attempt for the oracle: its name and the input it submits."""

    name: str
    value: object


@dataclass(frozen=True)
class OracleResult:
    family: str
    attempt: str
    verdict: str
    evidence_digest: str
    #: FAILING_TRIGGER for a breach; None otherwise.
    condition: str | None = None
    #: The family specimen's verdict on the same attempt (FIRED, SILENT or a
    #: no-answer verdict); None for a seam, which runs nothing.
    specimen: str | None = None
    specimen_digest: str | None = None
    #: The adapter's own reading behind the verdict, when it has one (for
    #: example battery's PROTECTED_WITHHELD behind a NOT_RUN): reported, so a
    #: withheld attempt is shown as not covered, never as held.
    reading: str | None = None

    def __post_init__(self):
        if self.verdict not in ORACLE_VERDICTS:
            raise AdapterError("oracle_verdict_unknown", str(self.verdict))
        if self.condition is not None and self.condition not in CONDITIONS:
            raise AdapterError("oracle_condition_outside_conditions", self.condition)
        if (self.verdict == engine.BREACHED) != (self.condition is not None):
            raise AdapterError("only_a_breach_carries_a_condition", self.attempt)
        if self.specimen is not None and self.specimen not in SPECIMEN_VERDICTS:
            raise AdapterError("oracle_specimen_verdict_unknown", str(self.specimen))
        if (self.verdict == NOT_RUN) != (self.specimen is None):
            raise AdapterError("only_a_seam_runs_no_specimen", self.attempt)
        if self.verdict == engine.HELD and self.specimen != engine.FIRED:
            raise AdapterError("a_hold_needs_a_specimen_that_fired", self.attempt)


@dataclass(frozen=True)
class Rebuilt:
    """Carbon rebuilt the construction: the digest it was given and the
    digest of what Carbon built from it."""

    construction_digest: str
    rebuilt_digest: str
    detail: Mapping = field(default_factory=dict)

    def __post_init__(self):
        for value in (self.construction_digest, self.rebuilt_digest):
            if not (isinstance(value, str) and _DIGEST.match(value)):
                raise AdapterError("rebuilt_digests_are_sha256")


@dataclass(frozen=True)
class Unrebuildable:
    """Carbon cannot rebuild the construction; it is never scored."""

    code: str
    detail: str = ""

    def __post_init__(self):
        if self.code not in UNREBUILDABLE_CODES:
            raise AdapterError("unrebuildable_code_unknown", str(self.code))


@runtime_checkable
class Adapter(Protocol):
    challenge_id: str
    level: int
    contract_digest: str

    def families(self) -> tuple: ...

    def controls(self, split: str) -> tuple: ...

    def oracle(self, family: str, attempt) -> OracleResult: ...

    def rebuild(self, construction) -> Rebuilt | Unrebuildable: ...

    def level_families(self) -> tuple: ...


@runtime_checkable
class SessionSurface(Protocol):
    """What a Graphite session needs from a Challenge (graphite/challenge.py)."""

    def permission_inventory(self) -> dict: ...

    def public_identity(self) -> dict: ...

    def admission_refusals(self, strategy) -> list: ...

    def code_run_seconds(self) -> int: ...

    def recipe_outside_contract(self) -> dict: ...


def family_oracle(family, attempt):
    """Carbon's verdict on one attempt, by the engine's rule for one attack:
    the attempt is re-run against the family's real boundary and against its
    vulnerable specimen. `attempt` has a `name` and a `value`.

    BREACHED (FAILING_TRIGGER) when the real boundary let it through. HELD
    only when the boundary held and the detector fired on the specimen. A
    boundary that held while the specimen stayed SILENT, or did not answer,
    is INCONCLUSIVE: the detector is blind to this attempt, so the hold is no
    evidence, never a pass. A boundary that did not answer gives its own
    verdict (FAILED_INFRA, TIMEOUT, CRASHED)."""
    if type(family) is not engine.Family:
        raise TypeError("an exact engine Family is required")
    if not (hasattr(attempt, "name") and hasattr(attempt, "value")):
        raise TypeError("an attempt has a name and a value")
    result, verdict = engine.answer(family.boundary, attempt.value)
    if verdict is None:
        verdict = engine.BREACHED if family.breached(result) else engine.HELD
    weak, specimen = engine.answer(family.specimen, attempt.value)
    if specimen is None:
        specimen = engine.FIRED if family.breached(weak) else engine.SILENT
    if verdict == engine.HELD and specimen != engine.FIRED:
        verdict = INCONCLUSIVE
    return OracleResult(
        family=family.name,
        attempt=str(attempt.name),
        verdict=verdict,
        evidence_digest=engine.digest(result),
        condition=engine.FINDING_CONDITION if verdict == engine.BREACHED else None,
        specimen=specimen,
        specimen_digest=engine.digest(weak),
    )


def seam_oracle(seam, attempt):
    """A seam's verdict: NOT_RUN, whatever the attempt."""
    return OracleResult(
        family=seam.name,
        attempt=str(getattr(attempt, "name", "attempt")),
        verdict=NOT_RUN,
        evidence_digest=engine.digest({"not_run": seam.reason}),
    )


def _controls(adapter, split):
    out = tuple(adapter.controls(split))
    if not all(type(c) is Control and c.split == split for c in out):
        raise AdapterError("controls_are_of_the_split_asked_for", split)
    return out


def validate(adapter, *, held_out=True):
    """The adapter, or AdapterError naming what is missing. `held_out=False`
    checks everything but the held-out split's shape."""
    if not isinstance(adapter, Adapter):
        raise AdapterError("adapter_protocol_not_met")
    if not (
        isinstance(adapter.challenge_id, str) and _TOKEN.match(adapter.challenge_id)
    ):
        raise AdapterError("challenge_id_is_a_contract_token")
    if type(adapter.level) is not int or adapter.level not in LEVELS:
        raise AdapterError("level_is_a_ladder_level")
    if not (
        isinstance(adapter.contract_digest, str)
        and _DIGEST.match(adapter.contract_digest)
    ):
        raise AdapterError("contract_digest_is_sha256")
    families = tuple(adapter.families())
    seams = tuple(adapter.level_families())
    if not all(type(f) is FamilyDef for f in families):
        raise AdapterError("families_are_family_defs")
    if not all(type(s) is SeamFamily for s in seams):
        raise AdapterError("level_families_are_seams")
    names = [f.name for f in families] + [s.name for s in seams]
    if len(names) != len(set(names)):
        raise AdapterError("family_names_are_unique")
    supplied = {f.check for f in families} | {s.check for s in seams}
    missing = [c for c in TRACK_A_CHECKS if c not in supplied]
    if missing:
        raise AdapterError("check_not_supplied", ", ".join(missing))
    splits = {"trained": _controls(adapter, "trained")}
    if held_out:
        splits["held_out"] = _controls(adapter, "held_out")
    run = {f.name for f in families if f.family is not None}
    seen = {}
    for split, controls in splits.items():
        for control in controls:
            if control.family not in {f.name for f in families}:
                raise AdapterError("control_for_an_unknown_family", control.name)
            if control.name in seen:
                raise AdapterError(
                    "control_names_are_unique_across_splits", control.name
                )
            seen[control.name] = split
        for name in sorted(run):
            if not any(c.family == name for c in controls):
                raise AdapterError(f"family_has_a_{split}_control", name)
    if held_out:
        # A held-out control canonically identical to a trained one measures
        # nothing the trained run did not already see, and its identity
        # would refuse the trained control too.
        trained = {c.identity: c.name for c in splits["trained"]}
        for control in splits["held_out"]:
            if control.identity in trained:
                raise AdapterError(
                    "held_out_control_is_canonically_a_trained_one",
                    f"{control.name} = {trained[control.identity]}",
                )
        engine.register_held_out(splits["held_out"])
    return adapter


def register_held_out_identities(adapter):
    """Register the adapter's held-out controls by identity with the engine,
    so `run_family` refuses any of them whatever split label it carries. Only
    identities are computed; no held-out control is run here."""
    return engine.register_held_out(_controls(adapter, "held_out"))


def coverage(adapter):
    """Each of the eight checks: the families that supply it and the seams
    declared NOT_RUN for it."""
    families = tuple(adapter.families())
    seams = tuple(adapter.level_families())
    return {
        check: {
            "run": [f.name for f in families if f.check == check and f.family],
            "evidence": [f.name for f in families if f.check == check and not f.family],
            "not_run": [s.name for s in seams if s.check == check],
        }
        for check in TRACK_A_CHECKS
    }


def run_adapter(adapter, *, budget=None):
    """Run every family the adapter runs deterministically, with its trained
    controls only. Returns a tuple of engine FamilyRuns. Held-out controls are
    never read here."""
    context = engine.RunContext(
        challenge=adapter.challenge_id, profile=level_profile(adapter.level)
    )
    # Held-out identities are registered when the adapter is validated
    # (`register`) or measured (`held_out_outcomes`), never read here.
    trained = _controls(adapter, "trained")
    runs = []
    for definition in adapter.families():
        if definition.family is None:
            continue
        runs.append(
            engine.run_family(
                definition.family,
                budget=budget,
                context=context,
                controls=tuple(c for c in trained if c.family == definition.name),
            )
        )
    return tuple(runs)


#: A wrongful-rejection rate with nothing to measure: no held-out control, or
#: none that ran (its family only cites evidence elsewhere). Never a zero rate.
NOT_MEASURED = "NOT_MEASURED"
MEASURED = "MEASURED"


def held_out_outcomes(adapter):
    """Each held-out control against its family's real boundary, for the
    wrongful-rejection rate. A measurement only: nothing here feeds a run.
    Each row binds the control's registered identity and input digest. A
    control whose family only cites evidence elsewhere (no engine family
    here) is `NOT_MEASURED`, never skipped."""
    families = {f.name: f.family for f in adapter.families()}
    engine.register_held_out(_controls(adapter, "held_out"))
    out = {}
    for control in _controls(adapter, "held_out"):
        family = families.get(control.family)
        if family is None:
            outcome = NOT_MEASURED
        else:
            passed, failed = engine.answer(engine.evaluate_control, family, control)
            outcome = failed or (engine.PASSED if passed else engine.REFUSED)
        out.setdefault(control.family, []).append(
            {
                "control": control.name,
                "version": control.version,
                "identity": control.identity,
                "input_digest": control.submitted_digest,
                "outcome": outcome,
            }
        )
    return out


def wrongful_rejection(outcomes, families=()):
    """`{family: {status, refused, total, no_answer, not_measured, rate}}`
    from `held_out_outcomes`, for every family in `outcomes` and every name
    in `families` (an adapter's `families()`). A control that did not answer,
    or that could not be run, counts in neither the numerator nor the
    denominator. A family with no held-out control that ran is
    `NOT_MEASURED` with rate None: never a zero rate."""
    names = list(outcomes)
    for family in families:
        name = getattr(family, "name", family)
        if name not in names:
            names.append(name)
    out = {}
    for family in names:
        rows = outcomes.get(family, ())
        answered = [r for r in rows if r["outcome"] in (engine.PASSED, engine.REFUSED)]
        refused = sum(r["outcome"] == engine.REFUSED for r in answered)
        out[family] = {
            "status": MEASURED if answered else NOT_MEASURED,
            "refused": refused,
            "total": len(answered),
            "no_answer": sum(r["outcome"] in engine.NO_ANSWER for r in rows),
            "not_measured": sum(r["outcome"] == NOT_MEASURED for r in rows),
            "rate": (refused / len(answered)) if answered else None,
        }
    return out


def ablation_family(plan, runners, specimen_runners, *, name="permission_ablation"):
    """The baseline_and_permission_ablation family over the climb harness
    (`carbon.agent_campaign.climb`), reused as it is.

    Each attack is one panel construction or attack that uses a new
    permission, run under the expanded profile without that permission
    (`ClimbPlan.ablated`). The oracle is the climb's rule: a removed
    permission must come back REFUSED; one that runs is breached. A run that
    fails on infrastructure answers nothing. The specimen is the same item
    under `specimen_runners`, a boundary that does not enforce the profile.
    The default control: every panel construction runs under the expanded
    profile.

    Every panel member is therefore an attack input and the default control,
    so a panel member is a trained control at most. A held-out control for
    this family must be a construction outside `plan.panel` and
    `plan.attacks`; it runs as a construction (`runners.construct`)."""
    from carbon.agent_campaign import climb

    if type(plan) is not climb.ClimbPlan or type(runners) is not climb.Runners:
        raise TypeError("exact ClimbPlan and Runners required")
    if type(specimen_runners) is not climb.Runners:
        raise TypeError("exact specimen Runners required")
    attack_ids = {item.item_id for item in plan.attacks}

    def attacks():
        out = []
        for permission in sorted(plan.new_permissions):
            ablated = plan.ablated(permission)
            for item in (*plan.panel, *plan.attacks):
                if permission in item.uses:
                    out.append((f"{permission}:{item.item_id}", (ablated, item)))
        return tuple(out)

    def under(chosen):
        def run(value):
            profile, item = value
            call = chosen.attack if item.item_id in attack_ids else chosen.construct
            outcome = call(profile, item)
            status = outcome.get("status")
            if status == "FAILED_INFRA":
                raise engine.InfrastructureFailure(item.item_id)
            if status not in climb.RUN_STATUSES:
                raise climb.ClimbError("runner_status_unknown", str(status))
            return {
                "accepted": status == "OK",
                "status": status,
                "expected_refusal": not item.uses <= profile.permissions,
                "profile": profile.name,
                "profile_digest": profile.digest,
                "item_id": item.item_id,
            }

        return run

    def breached(result):
        return result["expected_refusal"] and result["status"] == "OK"

    def control():
        for item in plan.panel:
            status = runners.construct(plan.expanded, item).get("status")
            if status == "FAILED_INFRA":
                raise engine.InfrastructureFailure(item.item_id)
            if status != "OK":
                return False
        return True

    return engine.Family(
        name=name,
        check="baseline_and_permission_ablation",
        boundary=under(runners),
        attacks=attacks,
        specimen=under(specimen_runners),
        breached=breached,
        control=control,
        description="a removed permission must come back REFUSED",
    )


@dataclass(frozen=True)
class DeclaredAdapter:
    """An adapter built from declared parts. A Challenge may implement the
    protocol any way it likes; this is the common shape."""

    challenge_id: str
    level: int
    contract_digest: str
    family_defs: tuple
    control_set: tuple
    seams: tuple = ()
    rebuilder: Callable | None = None
    session: object = None

    def families(self):
        return tuple(self.family_defs)

    def controls(self, split):
        if split not in SPLITS:
            raise AdapterError("control_split_is_trained_or_held_out", str(split))
        return tuple(c for c in self.control_set if c.split == split)

    def level_families(self):
        return tuple(self.seams)

    def oracle(self, family, attempt):
        for definition in self.family_defs:
            if definition.name == family and definition.family is not None:
                return family_oracle(definition.family, attempt)
        for seam in self.seams:
            if seam.name == family:
                return seam_oracle(seam, attempt)
        raise AdapterError("oracle_for_an_unknown_or_unrun_family", str(family))

    def rebuild(self, construction):
        if self.rebuilder is None:
            return Unrebuildable("not_declarative", "this adapter rebuilds nothing")
        rebuilt = self.rebuilder(construction)
        if type(rebuilt) not in (Rebuilt, Unrebuildable):
            raise AdapterError("rebuild_returns_rebuilt_or_unrebuildable")
        return rebuilt

    def __getattr__(self, name):
        # The session surface, when this adapter carries one.
        if name in SESSION_FUNCTIONS and self.session is not None:
            return getattr(self.session, name)
        raise AttributeError(name)


class _Registry(Mapping):
    """`ADAPTERS[(challenge_id, level)]`. Built-in adapters load on first read."""

    def __init__(self):
        self._entries = {}
        self._loaded = False
        self._loading = False

    def _load(self):
        """Import the built-in adapters once. A built-in package that fails
        to import is never hidden: every read raises AdapterError
        `builtin_adapters_failed_to_import` (chained to the import error)
        until an import succeeds, rather than reading as an empty registry."""
        if self._loaded or self._loading:
            return  # the package's own register() calls arrive while loading
        self._loading = True
        before = dict(self._entries)
        try:
            if importlib.util.find_spec(BUILTIN_PACKAGE) is not None:
                importlib.import_module(BUILTIN_PACKAGE)
        except Exception as failed:
            # Roll back what the failed import registered, so the next read
            # retries cleanly and reports the same failure.
            self._entries = before
            raise AdapterError(
                "builtin_adapters_failed_to_import",
                f"{BUILTIN_PACKAGE}: {type(failed).__name__}: {failed}",
            ) from failed
        finally:
            self._loading = False
        self._loaded = True

    def __getitem__(self, key):
        self._load()
        return self._entries[key]

    def __iter__(self):
        self._load()
        return iter(dict(self._entries))

    def __len__(self):
        self._load()
        return len(self._entries)

    def register(self, adapter, *, replace=False):
        self._load()  # built-ins first, so a clash is refused here
        validate(adapter)
        key = (adapter.challenge_id, adapter.level)
        if key in self._entries and not replace:
            raise AdapterError("adapter_already_registered", f"{key[0]} level {key[1]}")
        self._entries[key] = adapter
        return key

    def unregister(self, challenge_id, level):
        self._entries.pop((challenge_id, level), None)


ADAPTERS = _Registry()


def register(adapter, *, replace=False):
    """Register an adapter under (challenge_id, level); returns the key."""
    return ADAPTERS.register(adapter, replace=replace)


def unregister(challenge_id, level):
    ADAPTERS.unregister(challenge_id, level)


def get(challenge_id, level):
    """The registered adapter, or AdapterError `adapter_not_registered`."""
    try:
        return ADAPTERS[(challenge_id, level)]
    except KeyError:
        raise AdapterError(
            "adapter_not_registered", f"{challenge_id} level {level}"
        ) from None
