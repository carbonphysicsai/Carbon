"""Battery's Level 0 attack adapter (OWNER-GRAPHITE-ATTACKER-01, slice AT-B).

Battery at construction Level 0 admits declarative recipes only: a miner sends
a `TrainingStrategy` document, and Carbon compiles, rebuilds and scores it
with its own code. This adapter gives the Challenge-neutral attack engine
everything battery-specific it needs at that level, and nothing else:

- **surface and contract**: the Level 0 permission inventory
  (`agent_campaign.study.permission_inventory`) and the live construction
  contract digest, read, never changed;
- **families**: the eight shared Track A checks
  (`challenge_readiness.admission.CHECKS`), each with attacks run against the
  real boundary, a deliberately weakened specimen that must fire (a silent
  specimen is INCONCLUSIVE, never a pass), an attack example and a valid
  control. Five families are `carbon.battery.track_a`'s, reused unchanged;
  four are added here (`permission_ablation`, `practice_disclosure`,
  `resource_accounting`, `rebuild_report`); `fresh_attack_confirmation` is a
  NOT_RUN seam;
- **controls**, split `trained` (the engine may see them) and `held_out` (only
  the report reads them, for the wrongful-rejection rate), versioned by
  `CONTROLS_VERSION`;
- **the oracle**: Carbon's own verdict on one attempt, from the real boundary
  (the compiler, `experiment.admit`, `FrozenRule.score`, the practice
  feedback and `exam.disclosure`, the canary scan, `rebuild_differences`);
- **rebuild**: `graphite.experiment.admit`, refused with a typed code when
  Carbon cannot rebuild a construction, which is then never scored;
- **level families**: what Level 0 cannot test (participant code) declared as
  NOT_RUN seams. Executing hostile code needs the security owner's isolation
  decision, which is reserved and not built here;
- **the session surface** a Graphite session needs (`attack.adapter.
  SessionSurface`): the permission inventory, the public identity, Carbon's
  admission refusals, the code-run wall allowance and a recipe the contract
  refuses.

It speaks the neutral core's interface (`attack.adapter`: `FamilyDef`,
`Control`, `OracleResult`, `Rebuilt`, `Unrebuildable`, `SeamFamily`;
`attack.engine.Family`) and registers itself in `attack.adapter.ADAPTERS`
from `attack.adapters`.

What it is not. Nothing here executes participant code, reads a hidden pool, a
seed, EV5 or any sealed or confirmation material, or changes the construction
contract (`carbon/reconstruction/capability_registry.py`). Every value it pins
is a copy of a battery value, checked against its source by a test, so a
change there moves this adapter's version. A held attack is evidence about
the boundary it called, nothing more; zero findings is attempted coverage,
never a bound; and no verdict here is security acceptance.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import math
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import SimpleNamespace

from carbon.challenge_readiness.admission import CHECKS, CONDITIONS

CHALLENGE_ID = "battery-fastcharge-ageing-development-v1"
LEVEL = 0
PROFILE = "level-0"
ADAPTER_VERSION = "carbon.attack.adapter.battery-l0.v1"
#: v2: the practice_disclosure and mandatory_failure held-out controls are
#: genuinely different valid inputs (v1's were key-reordered or JSON
#: round-tripped copies of the trained values, canonically identical).
CONTROLS_VERSION = "carbon.attack.controls.battery-l0.v2"
ORACLE_SCHEMA = "carbon.attack.oracle-result.battery-l0.v1"
TRACK = "construction_integrity"
SPLITS = ("trained", "held_out")
FAILING_TRIGGER, OTHER_SIGNAL = "FAILING_TRIGGER", "OTHER_SIGNAL"

#: The oracle's own reading of an attempt (`BatteryLevel0Adapter.assess`),
#: before it is put in the core's verdicts: a breach of the real boundary or a
#: path that accepted what Carbon refuses (BREACH), a path that refused what
#: Carbon would admit and run (WRONGFUL_REFUSAL), both FAILING_TRIGGER; or
#: protected material a path accepted or a result carried (EXPOSURE,
#: OTHER_SIGNAL). The core carries a condition only on BREACHED, so each of
#: these is BREACHED with its condition. An attempt that names protected
#: material but was refused or never sent is PROTECTED_WITHHELD: it is never
#: handed to a boundary, judged nothing (core NOT_RUN), and is no finding.
BREACH, EXPOSURE = "BREACH", "EXPOSURE"
WRONGFUL_REFUSAL, PROTECTED_WITHHELD = "WRONGFUL_REFUSAL", "PROTECTED_WITHHELD"
UNDETERMINED, NOT_APPLICABLE = "UNDETERMINED", "NOT_APPLICABLE"
CONDITION_OF = {
    BREACH: FAILING_TRIGGER,
    WRONGFUL_REFUSAL: FAILING_TRIGGER,
    EXPOSURE: OTHER_SIGNAL,
}

#: The wall allowance one code run may ask for: battery's practice worker
#: allowance (`carbon.battery.research.PRACTICE_SECONDS`), as the step-4
#: adapter pinned it (PROTO4-D6). A copy, checked against its source.
CODE_RUN_SECONDS = 600

#: What a miner's public practice feedback may carry
#: (`carbon.battery.practice.feedback`), and its aggregate summary
#: (`carbon.battery.exam.aggregate`). Copies, checked against their sources.
PRACTICE_FEEDBACK_FIELDS = frozenset(
    {
        "schema",
        "provenance",
        "challenge",
        "recipe_digest",
        "backbone",
        "summary",
        "fit",
        "backend",
        "worker",
        "adaptively_seen",
        "final_exam",
        "official_eligible",
        "scientific_qualification",
    }
)
PRACTICE_SUMMARY_FIELDS = frozenset(
    {
        "n_cases",
        "n_scored",
        "n_gate_failed",
        "n_reference_invalid",
        "n_failed_infra",
        "eligible",
        "score",
        "important_score",
        "n_important",
        "components",
        "gate_failures",
    }
)
#: The flags practice feedback must carry, by value.
PRACTICE_FLAGS = {
    "adaptively_seen": True,
    "final_exam": False,
    "official_eligible": False,
    "scientific_qualification": False,
}
#: Rule v2's miner-disclosure term (`exam.MINER_DISCLOSURE[2]`,
#: OWNER-BATTERY-3B-AND-EXPOSURE-01). A copy, checked against its source.
SEALED_DISCLOSURE = {
    "hidden_batch_results": "SEALED",
    "released_by": "CARBON_COMMIT_TO_TRAINING_POOL",
    "authority": "OWNER-BATTERY-3B-AND-EXPOSURE-01",
}
#: The fields Carbon compares between its own build and a reported one
#: (`graphite.experiment.REBUILT_FIELDS`). The tamper attacks are fixed here,
#: so dropping a field from the comparison is caught, not silently followed.
TAMPER_FIELDS = (
    "challenge",
    "contract_digest",
    "recipe",
    "recipe_digest",
    "strategy_hash",
    "plan_digest",
    "staged",
    "program",
    "seed",
)
#: Carbon's own refusal codes for a construction it cannot rebuild, each
#: mapped to the core's `Unrebuildable` code. The first five are
#: `graphite.experiment.admit`'s; the Carbon code leads the refusal's detail.
REFUSAL_CODES = {
    "strategy_not_an_object": "not_declarative",
    "strategy_not_json": "not_declarative",
    "not_the_battery_development_challenge": "unknown_construction",
    "seed_invalid": "unknown_construction",
    # Carbon's own contract record is not current: Carbon's side, never the
    # construction's, so Carbon can check nothing (`rebuild_failed_infra`).
    "construction_contract_unrecorded": "rebuild_failed_infra",
    "contract_refused": "refused_by_contract",
    "recipe_rejected": "refused_by_contract",
    "strategy_too_large": "refused_by_contract",
    "protected_material_named": "protected_material",
}
#: Contract issues that mean the construction needs a permission Level 0
#: withholds: refused as `outside_level`, not merely as malformed.
OUTSIDE_LEVEL_ISSUES = frozenset(
    {"parameter.not_rebuildable", "backbone.not_rebuildable"}
)
#: EV4 panel members (`carbon.battery.value.panel.PANELS["ev4"]`) used as
#: controls. EV4's panel only; nothing from EV5 is read.
TRAINED_PANEL = ("mlp",)
HELD_OUT_PANEL = ("knn", "deeponet", "mlp_t1500_w128_d2_f25")
#: The permission the registered Level 1 draft adds
#: (`carbon.battery.level1_draft.PERMISSION`); the climb ablates it.
DRAFT_PERMISSION = "objective.loss_expressions"
#: An interaction attack pairs the draft permission with this Level 0 one.
INTERACTION_PERMISSION = "architecture.width"
PROBE_BACKEND = {"kind": "ATTACK_PROBE", "worker": "none"}
#: Research tool names, without the miner SDK prefix, by the family whose
#: boundary they reach.
TOOL_FAMILIES = {
    "dry_validate": "recipe_surface",
    "compile_strategy": "recipe_surface",
    "inspect_resources": "recipe_surface",
    "forecast_resources": "resource_accounting",
    "get_research_result": "practice_disclosure",
    "get_challenge_info": "practice_disclosure",
    "get_interaction_manifest": "practice_disclosure",
    "cancel_research_task": "resource_accounting",
}
CODE_ACTIONS = ("run_python", "run_julia")
#: Workspace actions that read or write the session's own sandbox store and so
#: are judged against the carrier's isolation boundary, not left UNASSIGNED.
WORKSPACE_ISOLATION_ACTIONS = frozenset(
    {"read_file", "write_file", "inventory", "public_material", "notebook"}
)
#: The lanes whose code runs the code-run rule (`code_run_refusal`) binds: the
#: phase-4 Attacker dispatcher only. An observed attempt names its lane in a
#: `lane` field; without one, the rule does not judge it.
ATTACKER_LANE = "graphite_attacker"
CODE_RUN_RULE_LANES = frozenset({ATTACKER_LANE})


# -- the neutral core's shapes ---------------------------------------------------------------------
# The adapter returns the neutral core's own types (`attack.adapter`,
# `attack.engine`, slice AT-A). Where the core is not importable (this slice's
# branch before the core merges) it uses `_Shim`, a copy of the same shapes
# without their validation, so the adapter and its tests still run. Only an
# absent core falls back: a core that is present but fails to import raises,
# so the adapter never runs quietly on unvalidated shapes.
def _module_present(name):
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


if _module_present("carbon.agent_campaign.attack.adapter") or _module_present(
    "carbon.agent_campaign.attack.engine"
):
    from carbon.agent_campaign.attack import adapter as _core
    from carbon.agent_campaign.attack import engine as _engine
else:  # pragma: no cover - exercised only without the core
    _core = _engine = None


class _Shim:
    """The core's shapes, as the cross-slice interface states them."""

    HELD, BREACHED = "HELD", "BREACHED"
    FIRED, SILENT = "FIRED", "SILENT"
    FAILED_INFRA, TIMEOUT, CRASHED = "FAILED_INFRA", "TIMEOUT", "CRASHED"
    INCONCLUSIVE, NOT_RUN = "INCONCLUSIVE", "NOT_RUN"

    class InfrastructureFailure(Exception):
        pass

    @dataclass(frozen=True)
    class Family:
        name: str
        check: str
        boundary: object
        attacks: object
        specimen: object
        breached: object
        control: object
        description: str = ""

    @dataclass(frozen=True)
    class Control:
        name: str
        family: str
        split: str
        version: str
        value: object = None
        check: object = None
        input_digest: str | None = None

    @dataclass(frozen=True)
    class FamilyDef:
        name: str
        check: str
        boundary: str
        attack_example: object
        control_example: object
        family: object = None
        evidence: tuple = ()

    @dataclass(frozen=True)
    class SeamFamily:
        name: str
        check: str
        level: int
        reason: str
        state: str = "NOT_RUN"

    @dataclass(frozen=True)
    class AttackInput:
        name: str
        value: object

    @dataclass(frozen=True)
    class OracleResult:
        family: str
        attempt: str
        verdict: str
        evidence_digest: str
        condition: str | None = None
        specimen: str | None = None
        specimen_digest: str | None = None
        reading: str | None = None

        def __post_init__(self):
            if self.condition is not None and self.condition not in CONDITIONS:
                raise ValueError("oracle_condition_outside_conditions")
            if (self.verdict == "BREACHED") != (self.condition is not None):
                raise ValueError("only_a_breach_carries_a_condition")

    @dataclass(frozen=True)
    class Rebuilt:
        construction_digest: str
        rebuilt_digest: str
        detail: dict = field(default_factory=dict)

    @dataclass(frozen=True)
    class Unrebuildable:
        code: str
        detail: str = ""


#: Where each shape comes from: the core when present, else the shim.
_TYPES = _core or _Shim
_ENGINE = _engine or _Shim
Family = _ENGINE.Family
Control = _TYPES.Control
FamilyDef = _TYPES.FamilyDef
SeamFamily = _TYPES.SeamFamily
AttackInput = _TYPES.AttackInput
OracleResult = _TYPES.OracleResult
Rebuilt = _TYPES.Rebuilt
Unrebuildable = _TYPES.Unrebuildable
HELD, BREACHED = _ENGINE.HELD, _ENGINE.BREACHED
FIRED, SILENT = _ENGINE.FIRED, _ENGINE.SILENT
NO_ANSWER = frozenset({_ENGINE.FAILED_INFRA, _ENGINE.TIMEOUT, _ENGINE.CRASHED})
INCONCLUSIVE = getattr(_core, "INCONCLUSIVE", _Shim.INCONCLUSIVE)
NOT_RUN = getattr(_core, "NOT_RUN", _Shim.NOT_RUN)


def _answer(call, *args):
    """(result, None), or (evidence, verdict) when the call did not answer:
    the engine's own rule (`engine.answer`), so a crash is never a pass."""
    if _engine is not None:
        return _engine.answer(call, *args)
    try:
        return call(*args), None
    except _Shim.InfrastructureFailure as failed:
        return {"exception": type(failed).__name__}, _Shim.FAILED_INFRA
    except TimeoutError as failed:
        return {"exception": type(failed).__name__}, _Shim.TIMEOUT
    except Exception as failed:  # noqa: BLE001 - a crash is recorded, never a pass
        return {"exception": type(failed).__name__}, _Shim.CRASHED


@dataclass(frozen=True)
class FamilySpec:
    """One attack family at Level 0, as this adapter holds it: the real
    boundary, its attacks, its deliberately weakened specimen, its control
    check and Carbon's independent gate.

    `attacks()` returns `((name, input), ...)`; `boundary(input)` runs the
    real boundary; `specimen(input)` runs the weakened one; `breached(result)`
    is the detector; `control_check(value)` is True when a valid control
    passes; `admissible(value)` is Carbon's own gate for an observed session
    attempt (None when the family has none). `runnable(value)` is True when
    Carbon would both admit the input and run it on this path, so a path that
    refused it refused wrongly; None when the family cannot tell why a path
    refused (a refusal of an admissible input is then UNDETERMINED)."""

    name: str
    check: str
    protocol_family: str
    attacks: object
    boundary: object
    specimen: object
    breached: object
    control_check: object
    admissible: object
    attack_example: str
    reads: str
    runnable: object = None


@dataclass(frozen=True)
class ControlSpec:
    """A valid input the real boundary must accept. `make()` builds it."""

    family: str
    split: str
    label: str
    make: object
    version: str = CONTROLS_VERSION

    @property
    def name(self):
        """The control's name: a lowercase token, unique across splits."""
        return f"{self.family}_{self.split}_{self.label}"

    def value(self):
        return self.make()


@dataclass(frozen=True)
class SeamSpec:
    """A family this adapter declares and does not run."""

    name: str
    check: str
    level: int
    reason: str
    reserved_decision: str | None = None


@dataclass(frozen=True)
class Build:
    """Carbon's own rebuild of one construction, before it is mapped to the
    core's `Rebuilt` / `Unrebuildable`. `code` is None when Carbon rebuilt it."""

    strategy: object
    seed: object
    record: dict | None = None
    served: bool = False
    reason: str | None = None
    code: str | None = None
    issues: tuple = ()

    @property
    def rebuilt(self):
        return self.code is None


# -- helpers -----------------------------------------------------------------------------------
def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=repr)


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


def _track_a():
    from carbon.battery import track_a

    return track_a


def _protected(value):
    """Graphite's protected-material check (`graphite.tools.protected`)."""
    # `tools` and `literature` import each other; `literature` must load
    # first or a cold `import tools` fails part-way.
    from carbon.agent_campaign.graphite import literature, tools  # noqa: F401

    return tools.protected(value)


def _panel(label):
    from carbon.battery.value.panel import PANELS

    for name, strategy, _seeds in PANELS["ev4"]:
        if name == label:
            return copy.deepcopy(strategy)
    raise KeyError(label)


def _contract():
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE, contract

    return contract(BATTERY_CHALLENGE)


#: `_capability_index` by live contract digest, so a changed contract is never
#: read through a stale index in a long-lived process.
_INDEX_BY_CONTRACT = {}


def _capability_index():
    """Field and family names to capability ids, and the Level 0 permissions,
    from the live contract (read only), cached by the contract's digest."""
    live = _contract()
    index = _INDEX_BY_CONTRACT.get(live.digest)
    if index is None:
        index = _INDEX_BY_CONTRACT[live.digest] = _index_of(live)
    return index


def _index_of(live):
    from carbon.reconstruction.capability_registry import Dimension, Status

    families, fields, level0 = {}, {}, set()
    for c in live.capabilities:
        suffix = c.capability_id.partition(".")[2]
        if c.dimension is Dimension.MODEL_FAMILY:
            families[c.selector or suffix] = c.capability_id
            families.setdefault(suffix, c.capability_id)
        else:
            fields.setdefault(suffix, c.capability_id)
        if c.status is Status.REBUILDABLE_DEVELOPMENT:
            level0.add(c.capability_id)
    withheld = tuple(
        sorted(
            c.capability_id
            for c in live.capabilities
            if c.status is not Status.REBUILDABLE_DEVELOPMENT
        )
    )
    return families, fields, frozenset(level0), withheld, live.digest


def uses(strategy):
    """The capability ids a strategy uses; an unregistered name is
    `unregistered.<name>`, which no profile permits."""
    families, fields, *_ = _capability_index()
    if not isinstance(strategy, Mapping):
        return frozenset({"unregistered.strategy"})
    found = set()
    backbone = strategy.get("backbone")
    found.add(families.get(backbone, "unregistered.backbone." + str(backbone)))
    parameters = strategy.get("parameters")
    if isinstance(parameters, Mapping):
        for name in parameters:
            found.add(fields.get(name, "unregistered." + str(name)))
    else:
        found.add("unregistered.parameters")
    for key in strategy:
        if key not in ("schema_version", "challenge_id", "backbone", "parameters"):
            found.add("unregistered." + str(key))
    return frozenset(found)


def level0_permissions():
    return _capability_index()[2]


def _withheld_strategy(capability_id):
    """A strategy that uses one permission Level 0 withholds."""
    track_a = _track_a()
    dimension, _, suffix = capability_id.partition(".")
    if dimension == "model_family":
        return track_a._strategy(suffix)
    return track_a._strategy(**{suffix: True})


@functools.cache
def _control_recipe():
    from carbon.battery.compile import compile_recipe

    return compile_recipe(_track_a().RECIPE_CONTROL)[1]


@functools.cache
def _challenge_scoring():
    """Battery's exact scorer at the Challenge-neutral Graphite seam."""
    from carbon.challenge_validator.scoring import scoring_for

    return scoring_for(CHALLENGE_ID)


@functools.cache
def _frozen_rule():
    from carbon.agent_campaign.graphite.experiment import FrozenRule

    return FrozenRule(scoring=_challenge_scoring())


def _oracle_predictions():
    return _track_a().mandatory_control()


def _floats(value, convert):
    """`value` with every float passed through `convert` (dicts and lists
    walked; everything else kept)."""
    if isinstance(value, float):
        return convert(value)
    if isinstance(value, Mapping):
        return {key: _floats(item, convert) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_floats(item, convert) for item in value]
    return value


def _single_precision(value):
    """Every float as a single-precision (float32) model would emit it."""
    return _floats(value, lambda x: struct.unpack("<f", struct.pack("<f", x))[0])


def _rounded(value, places=6):
    """Every float rounded to `places` decimals."""
    return _floats(value, lambda x: round(x, places))


# -- the real boundaries this adapter adds -----------------------------------------------------
def gate(strategy):
    """The miner path's Level 0 admission: the battery construction contract,
    then the compiler (`challenge_contracts.compile_submission`).

    Only the gate's own typed refusals (`SubmissionRefused`,
    `RecipeRejected`) read as REFUSED. Any other exception is the gate
    failing, not refusing: it propagates, so the engine records CRASHED and a
    crash in Carbon's own gate is never read as a hold."""
    from carbon.development_session.research_catalog import RecipeRejected
    from carbon.reconstruction.challenge_contracts import (
        SubmissionRefused,
        compile_submission,
    )

    try:
        admitted = compile_submission(strategy)
    except SubmissionRefused as refused:
        return {
            "status": "REFUSED",
            "codes": sorted({(i.code, i.path) for i in refused.issues}),
        }
    except RecipeRejected as refused:
        return {
            "status": "REFUSED",
            "codes": sorted({(i.code, i.path) for i in refused.rejected.issues}),
        }
    return {"status": "OK", "recipe_digest": admitted.construction.recipe_digest}


def _ablation_item(strategy, label):
    used = uses(strategy)
    return {
        "item": label,
        "strategy": strategy,
        "uses": sorted(used),
        "expected_refusal": not used <= level0_permissions(),
    }


def ablation_boundary(item):
    """Run one item through the real gate under the Level 0 profile. A removed
    permission must come back REFUSED (`climb`'s rule)."""
    if item.get("climb"):
        report = climb_report()
        return {
            "kind": "climb",
            "status": report["status"],
            "findings": len(report["findings"]),
            "infrastructure_failures": report["infrastructure_failures"],
            "report_digest": _digest(report),
        }
    outcome = gate(item["strategy"])
    return {
        "kind": "item",
        "status": outcome["status"],
        "expected_refusal": item["expected_refusal"],
        "codes": outcome.get("codes", []),
    }


def ablation_specimen(item):
    """Vulnerable specimen: a gate that does not enforce the profile."""
    if item.get("climb"):
        report = climb_report(_unenforced_runners())
        return {
            "kind": "climb",
            "status": report["status"],
            "findings": len(report["findings"]),
            "infrastructure_failures": report["infrastructure_failures"],
            "report_digest": _digest(report),
        }
    return {
        "kind": "item",
        "status": "OK",
        "expected_refusal": item["expected_refusal"],
    }


def ablation_breached(result):
    if result["kind"] == "climb":
        return result["findings"] > 0
    return result["expected_refusal"] and result["status"] == "OK"


def _ablation_attacks():
    _, _, _, withheld, _ = _capability_index()
    items = [
        (
            "withheld_" + capability_id,
            _ablation_item(_withheld_strategy(capability_id), capability_id),
        )
        for capability_id in withheld
    ]
    items.append(("climb_ablation_of_the_level_1_draft", {"climb": True}))
    return tuple(items)


def _climb_items():
    """The climb's panel, attacks and combined attacks, as climb Items with
    their strategies."""
    from carbon.agent_campaign import climb

    track_a = _track_a()
    panel = {}
    for label in TRAINED_PANEL:
        strategy = _panel(label)
        panel["panel_" + label] = (
            climb.Item("panel_" + label, uses(strategy)),
            strategy,
        )
    attacks = {}
    for label, strategy in (
        ("loss_expressions_draft", track_a._strategy(loss_expressions=True)),
        ("pretrained_family", track_a._strategy("pretrained_weights")),
        ("submitted_datasets", track_a._strategy(submitted_datasets=["train-extra"])),
        ("label_method", track_a._strategy(label_method="reference_solver")),
    ):
        attacks["attack_" + label] = (
            climb.Item(
                "attack_" + label,
                uses(strategy),
                declared_violation="admitted with a permission Level 0 withholds",
            ),
            strategy,
        )
    combined = {}
    strategy = track_a._strategy(width=256, loss_expressions=True)
    combined["combined_width_and_loss_expressions"] = (
        climb.Item(
            "combined_width_and_loss_expressions",
            uses(strategy),
            declared_violation="admitted with a permission Level 0 withholds",
        ),
        strategy,
    )
    return panel, attacks, combined


def _gate_runners(strategies):
    from carbon.agent_campaign import climb

    def construct(_profile, item):
        outcome = gate(strategies[item.item_id])
        return {
            "status": outcome["status"],
            "artifact_digest": outcome.get("recipe_digest"),
            "result": _digest(outcome),
        }

    def attack(_profile, item):
        outcome = gate(strategies[item.item_id])
        return {
            "status": outcome["status"],
            "violation_reproduced": outcome["status"] == "OK",
            "evidence_digest": _digest(outcome),
        }

    def rebuild(run):
        first = build(strategies[run["item_id"]])
        second = build(strategies[run["item_id"]])
        if not (first.rebuilt and second.rebuilt):
            return {"status": "OK", "matches": False, "rebuilt_digest": None}
        return {
            "status": "OK",
            "matches": first.record == second.record,
            "rebuilt_digest": _digest(first.record),
        }

    return climb.Runners(construct=construct, attack=attack, rebuild=rebuild)


def _unenforced_runners():
    """Specimen runners: every construction and attack runs."""
    from carbon.agent_campaign import climb

    return climb.Runners(
        construct=lambda _p, item: {
            "status": "OK",
            "artifact_digest": None,
            "result": item.item_id,
        },
        attack=lambda _p, item: {
            "status": "OK",
            "violation_reproduced": True,
            "evidence_digest": item.item_id,
        },
        rebuild=lambda run: {"status": "OK", "matches": True, "rebuilt_digest": None},
    )


def climb_report(runners=None):
    """The climb harness (`agent_campaign.climb`), run as is over battery's
    registered Level 1 draft plan (`battery.level1_draft.climb_plan`). Its
    previous profile and its ablated profile are both exactly Level 0, so
    every attack under them checks that a permission Level 0 withholds comes
    back REFUSED from the live gate. Nothing is opened: the live gate is
    Level 0's whatever profile a run is labelled with."""
    from carbon.agent_campaign import climb
    from carbon.battery import level1_draft

    panel, attacks, combined = _climb_items()
    strategies = {
        key: strategy
        for group in (panel, attacks, combined)
        for key, (_item, strategy) in group.items()
    }
    plan = level1_draft.climb_plan(
        panel=[item for item, _ in panel.values()],
        attacks=[item for item, _ in attacks.values()],
        attack_budget=len(attacks),
        combined=[item for item, _ in combined.values()],
        promising=lambda run: run["item_id"] in panel,
    )
    return climb.climb(plan, runners or _gate_runners(strategies))


def code_run_seconds():
    """The wall allowance one code run may ask for (`CODE_RUN_SECONDS`)."""
    return CODE_RUN_SECONDS


def code_run_refusal(arguments):
    """Refused before dispatch: a code run must ask for a whole number of
    seconds between 1 and `code_run_seconds()`. Returns the refusal code, or
    None when it may be dispatched.

    It is the core's one code-run rule (`attack.adapter.code_run_refusal`) at
    battery's allowance, the rule the phase-4 Attacker dispatcher
    (`graphite.phase4.AttackerTools`) calls before dispatch, so the
    `resource_accounting` family attacks the dispatcher's rule itself. It
    binds only Carbon's Attacker sessions. It is not the miner lane's rule
    (`research_carrier`: any positive allowance or none, by owner direction)
    nor Carbon's own worker lane's (40 to 600 seconds)."""
    if _core is not None:
        return _core.code_run_refusal(arguments, seconds=code_run_seconds())
    if not isinstance(arguments, Mapping):  # pragma: no cover - no core
        return "code_run_arguments_unreadable"
    seconds = arguments.get("seconds")
    most = code_run_seconds()
    if type(seconds) is not int or not 1 <= seconds <= most:
        return "code_run_needs_seconds_up_to_" + str(most)
    return None


def track_a_baseline(root="."):
    """The battery harness's runs (`carbon.battery.track_a.run`), normalized:
    B2's deterministic side for battery Level 0 (`attack.benchmark.
    adapter_baseline` reaches it through `deterministic_baseline`)."""
    from carbon.agent_campaign.attack import report
    from carbon.battery import track_a

    records, _report, _divergence = track_a.run(root)
    return report.runs_from_records(records)


def _scoring(value):
    """A prediction set scored by the frozen rule (`FrozenRule.score`). For a
    partial set (`partial`), every case left without a prediction must be
    FAILED_INFRA, never a gate failure; a set with nothing scored is never
    eligible.

    This is the frozen rule's typing of a missing prediction only. How a pod
    run that timed out is typed is a different path (`experiment`'s pod
    outcome: stage `timeout` is CANDIDATE_FAILED, never scored); that question
    is the NOT_RUN seam `pod_timeout_typing`, not judged here."""
    _rows, summary = _frozen_rule().score(value["predictions"])
    return {
        "kind": "scoring",
        "partial": bool(value.get("partial")),
        "eligible": bool(summary["eligible"]),
        "n_cases": summary["n_cases"],
        "n_scored": summary["n_scored"],
        "n_failed_infra": summary["n_failed_infra"],
        "n_gate_failed": summary["n_gate_failed"],
    }


def _pod_attribution():
    """The construction-neutral pod-attribution attacks
    (`attack.pod_attribution`, GRAPHITE-POD-GPU-PROBE-01)."""
    from carbon.agent_campaign.attack import pod_attribution

    return pod_attribution


def resource_boundary(value):
    if value["kind"] == "code_run":
        refusal = code_run_refusal(value["arguments"])
        return {"kind": "code_run", "dispatched": refusal is None, "refusal": refusal}
    if value["kind"] == _pod_attribution().KIND:
        return _pod_attribution().boundary(value)
    return _scoring(value)


def resource_specimen(value):
    """Vulnerable specimen: a lifted allowance, an aggregate that counts an
    infrastructure failure as a pass, and a pod-outcome classifier that
    trusts a candidate-written `environment` claim."""
    if value["kind"] == "code_run":
        return {"kind": "code_run", "dispatched": True, "refusal": None}
    if value["kind"] == _pod_attribution().KIND:
        return _pod_attribution().specimen(value)
    result = _scoring(value)
    return {**result, "eligible": result["n_gate_failed"] == 0}


def resource_breached(result):
    if result["kind"] == "code_run":
        return result["dispatched"]
    if result["kind"] == _pod_attribution().KIND:
        # A construction's own failure bought an environment relaunch.
        return _pod_attribution().breached(result)
    if not result["partial"]:
        return False  # a complete set: its eligibility is the frozen rule's
    missing = result["n_cases"] - result["n_scored"]
    # Whether a set that omits some cases may still be eligible is not judged
    # here: `exam.aggregate` excludes a FAILED_INFRA case by design, a
    # scientific question recorded with the Level 5 seam. Only a set with
    # nothing scored is held to "never eligible".
    return (
        (result["n_scored"] == 0 and result["eligible"])
        or result["n_gate_failed"] > 0
        or result["n_failed_infra"] != missing
    )


def _resource_attacks():
    most = CODE_RUN_SECONDS

    def run(**arguments):
        return {"kind": "code_run", "arguments": arguments}

    return (
        ("seconds_just_over_the_allowance", run(seconds=most + 1)),
        ("seconds_one_hour", run(seconds=3600)),
        ("seconds_one_day", run(seconds=86400)),
        ("seconds_missing_unbounded", run()),
        ("seconds_zero", run(seconds=0)),
        ("seconds_negative", run(seconds=-1)),
        ("seconds_boolean", run(seconds=True)),
        ("seconds_float", run(seconds=float(most))),
        ("seconds_string", run(seconds=str(most))),
        ("seconds_nonfinite", run(seconds=math.inf)),
        ("arguments_not_an_object", {"kind": "code_run", "arguments": "seconds=1"}),
        (
            "no_predictions_scored",
            {"kind": "scoring", "predictions": {}, "partial": True},
        ),
        # A construction's own failure dressed as the GPU probe's
        # `environment` failure (pod-attribution-v2).
        *_pod_attribution().attacks(),
    )


def _half_predictions():
    oracle = _oracle_predictions()
    return {case: oracle[case] for case in sorted(oracle)[: len(oracle) // 2]}


def _resource_control(value):
    if value.get("kind") == _pod_attribution().KIND:
        return _pod_attribution().control_passes(value)
    result = resource_boundary(value)
    if result["kind"] == "code_run":
        return result["dispatched"]
    return result["eligible"] and not resource_breached(result)


def _resource_admissible(value):
    """The code-run rule judges only a run the Attacker's dispatcher handled
    (`lane` in `CODE_RUN_RULE_LANES`). A run on any other lane (the miner's
    own research, Carbon's worker lane) has its own rule, so this gate does
    not judge it (None: NOT_APPLICABLE), and it is never a finding."""
    if value.get("kind") != "code_run":
        return None
    if value.get("lane") not in CODE_RUN_RULE_LANES:
        return None
    return code_run_refusal(value.get("arguments")) is None


def _probe(predictions, feedback=None):
    """One practice probe: Carbon's own scoring and the public feedback a
    miner receives (`practice.score_practice`, `practice.feedback`)."""
    from carbon.battery import practice

    practice_set, material = _track_a()._Practice.get()
    _rows, summary = practice.score_practice(predictions, practice_set, material, ".")
    feedback = practice.feedback if feedback is None else feedback
    return feedback(
        summary, {}, recipe=_control_recipe(), backend=PROBE_BACKEND, worker={}
    )


def _rule_disclosure(rule_name):
    """What the intake tells a miner about results under a rule
    (`BatteryIntake._rule_facts`), against `exam.disclosure(rule)`."""
    from carbon.battery import exam
    from carbon.battery.intake import BatteryIntake

    rule = exam.RULES[rule_name]
    facts = BatteryIntake._rule_facts(SimpleNamespace(rule=rule), 0)
    return {
        "kind": "disclosure",
        "rule": rule_name,
        "shown": facts.get("results"),
        "expected": exam.disclosure(rule),
        "sealed": exam.sealed(rule),
    }


def _feedback_view(feedbacks, identical):
    return {
        "kind": "probe",
        "fields": sorted({k for fb in feedbacks for k in fb}),
        "summary_fields": sorted(
            {k for fb in feedbacks for k in fb.get("summary", {})}
        ),
        "flags": [{k: fb.get(k) for k in PRACTICE_FLAGS} for fb in feedbacks],
        "digests": [_digest(fb) for fb in feedbacks],
        "eligible": [bool(fb.get("summary", {}).get("eligible")) for fb in feedbacks],
        "identical": identical,
    }


def disclosure_boundary(value):
    if value["kind"] == "disclosure":
        return _rule_disclosure(value["rule"])
    feedbacks = [_probe(p) for p in value["probes"]]
    return _feedback_view(feedbacks, value.get("identical", False))


def _leaky_feedback():
    from carbon.battery import practice

    calls = []

    def leaky(summary, fit, **kwargs):
        calls.append(1)
        out = practice.feedback(summary, fit, **kwargs)
        return {**out, "screening": {"hidden_batch": True}, "probe_index": len(calls)}

    return leaky


def disclosure_specimen(value):
    """Vulnerable specimen: feedback that also carries a hidden-batch field
    and a probe counter, and a rule that discloses nothing sealed."""
    if value["kind"] == "disclosure":
        return {**_rule_disclosure(value["rule"]), "shown": None, "sealed": False}
    leaky = _leaky_feedback()
    feedbacks = [_probe(p, leaky) for p in value["probes"]]
    return _feedback_view(feedbacks, value.get("identical", False))


def disclosure_breached(result):
    if result["kind"] == "disclosure":
        return (
            result["shown"] != result["expected"]
            or not result["sealed"]
            or result["expected"] != SEALED_DISCLOSURE
        )
    return (
        set(result["fields"]) != PRACTICE_FEEDBACK_FIELDS
        or not set(result["summary_fields"]) <= PRACTICE_SUMMARY_FIELDS
        or any(flags != PRACTICE_FLAGS for flags in result["flags"])
        or (result["identical"] and len(set(result["digests"])) > 1)
    )


def _one_case(predictions, index):
    case = sorted(predictions)[index]
    return {case: predictions[case]}


def _disclosure_attacks():
    oracle = _oracle_predictions()
    return (
        ("repeated_identical_probes", {"probes": [oracle] * 3, "identical": True}),
        ("single_case_probe_first", {"probes": [_one_case(oracle, 0)]}),
        ("single_case_probe_last", {"probes": [_one_case(oracle, -1)]}),
        ("empty_probe", {"probes": [{}]}),
        ("sealed_rule_v2_disclosure", {"kind": "disclosure", "rule": "v2"}),
    )


def _with_kind(value):
    return value if "kind" in value else {**value, "kind": "probe"}


def _disclosure_control(value):
    result = disclosure_boundary(_with_kind(value))
    if result["kind"] == "disclosure":
        return not disclosure_breached(result)
    return not disclosure_breached(result) and all(result["eligible"])


def rebuild_report_boundary(value):
    """Carbon's independent rebuild check (`experiment.rebuild_differences`)
    on a build a pod reports: the declared tamper of one field, or a build an
    observed session reported."""
    from carbon.agent_campaign.graphite import experiment

    expected = _expected_build(_canonical(value["strategy"]), value.get("seed", 0))
    if "built" in value:
        built = value["built"]
    else:
        built = _tampered(expected, value["field"])
    return {
        "differences": experiment.rebuild_differences(expected, built),
        "tampered": value.get("field"),
    }


def rebuild_report_specimen(value):
    """Vulnerable specimen: a comparison that compares nothing."""
    return {"differences": [], "tampered": value.get("field")}


def rebuild_report_breached(result):
    if result["tampered"] is None:
        return bool(result["differences"])
    return result["tampered"] not in result["differences"]


@functools.lru_cache(maxsize=8)
def _expected_build_cached(strategy_json, seed, record):
    from carbon.agent_campaign.graphite import experiment

    return experiment.admit(
        json.loads(strategy_json), seed, scoring=_challenge_scoring()
    )


def _expected_build(strategy_json, seed):
    """Carbon's own admit record, cached by the recorded construction
    contract it was built under (`experiment.recorded_contract`), so a new
    contract record is never compared against a stale build."""
    from carbon.agent_campaign.graphite import experiment

    recorded = experiment.recorded_contract(_challenge_scoring())
    record = (recorded.get("contract_digest"), recorded.get("record_sequence"))
    return copy.deepcopy(_expected_build_cached(strategy_json, seed, record))


def clear_caches():
    """Drop every cached read (the contract index, Carbon's admit records,
    the frozen rule, the compiled control recipe), for a long-lived driver
    that starts a new session."""
    _INDEX_BY_CONTRACT.clear()
    _expected_build_cached.cache_clear()
    _frozen_rule.cache_clear()
    _control_recipe.cache_clear()


def _tampered(expected, field):
    built = copy.deepcopy(expected)
    value = built.get(field)
    if isinstance(value, dict):
        built[field] = {**value, "tampered": True}
    elif isinstance(value, bool):
        built[field] = not value
    elif isinstance(value, int):
        built[field] = value + 1
    elif isinstance(value, str):
        built[field] = value[:-1] + ("0" if value[-1:] != "0" else "1")
    else:
        built[field] = "tampered"
    return built


def _rebuild_report_attacks():
    strategy = _track_a().RECIPE_CONTROL
    return tuple(
        ("tampered_" + field, {"strategy": strategy, "seed": 7, "field": field})
        for field in TAMPER_FIELDS
    )


def _rebuild_report_control(value):
    """An untampered build is the build Carbon computes."""
    built = _expected_build(_canonical(value["strategy"]), value.get("seed", 0))
    return not rebuild_report_breached(
        rebuild_report_boundary({**value, "built": built})
    )


def _staged_names(strategy, seed):
    """The staged files for `strategy` while a hidden batch holding the
    canaries exists: names must be the published allow-list, and no canary
    may appear in any staged byte."""
    from carbon.battery import practice, worker
    from carbon.battery.compile import compile_recipe

    track_a = _track_a()
    _, recipe = compile_recipe(strategy)
    batch = track_a._hidden_batch()
    inputs = {c: row["inputs"] for c, row in batch.items()}
    practice_set, _ = track_a._Practice.get()
    staged = {
        "reconstruct": worker.reconstruct_files(".", recipe, seed),
        "infer": worker.infer_files(b"model-state", inputs),
        "practice": practice.staged_files(".", practice_set, recipe, seed),
    }
    code = set(practice.STAGED_MODULES)
    expected = {
        "reconstruct": code | {"train-v1.jsonl.gz", "ocv-table.json", "recipe.json"},
        "infer": code | {"state.npz", "query.json"},
        "practice": code
        | {
            "train-v1.jsonl.gz",
            "ocv-table.json",
            "practice-inputs.json",
            "recipe.json",
        },
    }
    names_ok = all(set(staged[k]) == expected[k] for k in expected)
    return names_ok and not track_a.staged_canaries(staged)["found"]


def _rebuild_identity_control(strategy):
    track_a = _track_a()
    reordered = json.loads(json.dumps(strategy))
    reordered["parameters"] = dict(reversed(list(reordered["parameters"].items())))
    reordered = dict(reversed(list(reordered.items())))
    a, b = track_a.compile_boundary(strategy), track_a.compile_boundary(reordered)
    return a["accepted"] and a == b


def _forge_control(strategy):
    from carbon.battery.compile import BatteryRecipe, compile_recipe

    _, recipe = compile_recipe(strategy)
    return type(recipe) is BatteryRecipe


def build(construction, seed=0):
    """Carbon's rebuild of a construction (`graphite.experiment.admit`).

    `construction` is a strategy, or `{"strategy": ..., "seed": ...}`. A
    backend the phase-3 pods do not serve is still rebuilt (`served=False`,
    Carbon's own `pod_phase.built_record`) and is never run on those pods.
    Anything Carbon cannot rebuild carries a code from `REFUSAL_CODES`."""
    from carbon.agent_campaign.graphite import experiment

    strategy = construction
    if isinstance(construction, Mapping) and "strategy" in construction:
        strategy = construction["strategy"]
        seed = construction.get("seed", seed)

    def refused(code, issues=()):
        return Build(strategy, seed, code=code, issues=tuple(tuple(i) for i in issues))

    if _protected(strategy):
        return refused("protected_material_named")
    if type(seed) is not int or seed < 0:
        return refused("seed_invalid")
    try:
        size = len(json.dumps(strategy).encode())
    except (TypeError, ValueError):
        return refused("strategy_not_json")
    if size > experiment.MAX_STRATEGY_BYTES:
        return refused("strategy_too_large")
    try:
        record = experiment.admit(strategy, seed, scoring=_challenge_scoring())
    except experiment.Unrebuildable as error:
        return refused(error.code, error.issues)
    except experiment.NotServed as error:
        from carbon.agent_campaign.graphite.pod_phase import built_record

        contract = experiment.recorded_contract(_challenge_scoring())
        record, _files, _program = built_record(
            strategy, contract["contract_digest"], seed, experiment.REPOSITORY
        )
        record = {**record, "record_sequence": contract["record_sequence"]}
        return Build(strategy, seed, record, served=False, reason=str(error))
    return Build(strategy, seed, record, served=True)


def carbon_admits(strategy):
    """Would Carbon accept this construction? Exactly the authoritative chain,
    on the same input: the validator door's strict parse
    (`strict_json.parse_strategy`), the contract compile
    (`compile_submission`), then Graphite's admission (`experiment.admit`,
    through `build`). Nothing weaker: `validate_for_challenge` alone accepts
    out-of-domain values such as a kNN `neighbours: -5` that the compiler and
    admission both refuse (OWNER-GRAPHITE triage; independently confirmed by
    the Carbon Validator on main 83839718). A FAILING_TRIGGER for an
    AUTHORITATIVE path rests on this judgement."""
    from carbon.agent_campaign.graphite import experiment
    from carbon.challenge_validator import strict_json
    from carbon.reconstruction.challenge_contracts import compile_submission

    try:
        strict_json.parse_strategy(
            json.dumps(strategy, allow_nan=True),
            max_bytes=experiment.MAX_STRATEGY_BYTES,
        )
    except Exception:  # noqa: BLE001 - any door refusal means Carbon would not accept
        return False
    try:
        compile_submission(strategy)
    except Exception:  # noqa: BLE001 - any contract/compiler refusal: not accepted
        return False
    return build(strategy).rebuilt


def _recipe_admissible(strategy):
    """Carbon's own admission of a recipe, independent of the path: the full
    authoritative chain (`carbon_admits`)."""
    return carbon_admits(strategy)


def _recipe_runnable(strategy):
    """Carbon admits the recipe (the full chain) and the phase-3 pods serve
    its backend: a path that refused it refused a construction Carbon would
    have run."""
    if not carbon_admits(strategy):
        return False
    return build(strategy).served


def _ablation_admissible(item):
    strategy = item["strategy"]
    return uses(strategy) <= level0_permissions() and _recipe_admissible(strategy)


def _ablation_runnable(item):
    strategy = item["strategy"]
    return uses(strategy) <= level0_permissions() and _recipe_runnable(strategy)


def _mandatory_admissible(predictions):
    _rows, summary = _frozen_rule().score(predictions)
    return bool(summary["eligible"])


def _mandatory_boundary(predictions):
    """The frozen rule's gates and aggregate (`experiment.FrozenRule.score`)."""
    _rows, summary = _frozen_rule().score(predictions)
    return {
        "eligible": bool(summary["eligible"]),
        "score": summary["score"],
        "n_gate_failed": summary["n_gate_failed"],
        "gate_failures": summary["gate_failures"],
    }


# -- the families ------------------------------------------------------------------------------
def _protocol(family_id):
    """`track_a`'s own description of one of its families: its
    `protocol_family` (a track_a family) or `description` (an engine
    `Family`). A family with neither, or whose text is only its name, is a
    defect, raised rather than silently replaced by the bare name."""
    for family in _track_a().FAMILIES:
        name = getattr(family, "family_id", None) or getattr(family, "name", None)
        if name != family_id:
            continue
        text = getattr(family, "protocol_family", None) or getattr(
            family, "description", None
        )
        if not isinstance(text, str) or not text.strip() or text == family_id:
            raise LookupError("track_a_family_has_no_protocol_text: " + family_id)
        return text
    raise KeyError(family_id)


@functools.cache
def _families():
    t = _track_a  # resolved at call time, so a weakened boundary is seen

    return (
        FamilySpec(
            name="permission_ablation",
            check="baseline_and_permission_ablation",
            protocol_family="the Level 0 baseline panel under the live gate; every "
            "permission Level 0 withholds, and the registered draft's permission "
            "ablated by the climb harness, must come back REFUSED",
            attacks=_ablation_attacks,
            boundary=ablation_boundary,
            specimen=ablation_specimen,
            breached=ablation_breached,
            control_check=lambda s: (
                uses(s) <= level0_permissions() and gate(s)["status"] == "OK"
            ),
            admissible=_ablation_admissible,
            attack_example="withheld_" + DRAFT_PERMISSION,
            reads="the live construction contract (read only) and panel recipes",
            runnable=_ablation_runnable,
        ),
        FamilySpec(
            name="recipe_surface",
            check="artifact_and_dependency_attacks",
            protocol_family=_protocol("recipe_surface"),
            attacks=lambda: t().RECIPE_ATTACKS,
            boundary=lambda s: t().compile_boundary(s),
            specimen=lambda s: t().unchecked_compiler(s),
            breached=lambda r: t().recipe_breached(r),
            control_check=lambda s: t().compile_boundary(s)["accepted"],
            admissible=_recipe_admissible,
            attack_example="pretrained_weights_field",
            reads="recipes only",
            runnable=_recipe_runnable,
        ),
        FamilySpec(
            name="recipe_forgery",
            check="artifact_and_dependency_attacks",
            protocol_family=_protocol("recipe_forgery"),
            attacks=lambda: t()._forged_recipe_inputs(),
            boundary=lambda f: t().forge_boundary(f),
            specimen=lambda f: t().unsealed_recipe(f),
            breached=lambda r: r["accepted"],
            control_check=_forge_control,
            admissible=None,
            attack_example="raw_recipe_without_token",
            reads="recipes only",
        ),
        FamilySpec(
            name="practice_disclosure",
            check="adaptive_feedback_and_state_attacks",
            protocol_family="function-level PRACTICE probes and the sealed rule's "
            "disclosure: repeated identical probes through practice.feedback give "
            "identical feedback with the published allow-list only, and the "
            "intake's rule facts tell a miner exactly exam.disclosure(rule)",
            attacks=_disclosure_attacks,
            boundary=lambda v: disclosure_boundary(_with_kind(v)),
            specimen=lambda v: disclosure_specimen(_with_kind(v)),
            breached=disclosure_breached,
            control_check=_disclosure_control,
            admissible=None,
            attack_example="repeated_identical_probes",
            reads="public PRACTICE references and the rule table",
        ),
        FamilySpec(
            name="mandatory_failure",
            check="score_exploitation_and_tail_failures",
            protocol_family=_protocol("mandatory_failure"),
            attacks=lambda: t().mandatory_inputs(),
            boundary=_mandatory_boundary,
            specimen=lambda p: t().averaging_scorer(p),
            breached=lambda r: t().mandatory_breached(r),
            control_check=lambda p: _mandatory_boundary(p)["eligible"],
            admissible=_mandatory_admissible,
            attack_example="nan_voltage",
            reads="public PRACTICE references",
            runnable=_mandatory_admissible,
        ),
        FamilySpec(
            name="resource_accounting",
            check="resource_and_failure_accounting",
            protocol_family="the Attacker code-run rule this adapter defines: a wall "
            "allowance above code_run_seconds is refused before dispatch; and the "
            "frozen rule types every case a partial prediction set leaves out as "
            "FAILED_INFRA, never a gate failure, and a set with nothing scored is "
            "never eligible; and a construction's own failure never buys the GPU "
            "probe's environment relaunch under the registered pod attribution "
            "policy",
            attacks=_resource_attacks,
            boundary=resource_boundary,
            specimen=resource_specimen,
            breached=resource_breached,
            control_check=_resource_control,
            admissible=_resource_admissible,
            attack_example="seconds_just_over_the_allowance",
            reads="public PRACTICE references",
        ),
        FamilySpec(
            name="staged_bytes",
            check="construction_evaluation_isolation",
            protocol_family=_protocol("staged_bytes"),
            attacks=lambda: (("stage_with_private_state_present", None),),
            boundary=lambda _: t().staged_canaries(t()._stage_all(t().real_stager)),
            specimen=lambda _: t().staged_canaries(t()._stage_all(t().leaky_stager)),
            breached=lambda r: bool(r["found"]),
            control_check=lambda v: _staged_names(v["strategy"], v["seed"]),
            admissible=None,
            attack_example="stage_with_private_state_present",
            reads="synthetic canaries and public material",
        ),
        FamilySpec(
            name="rebuild_identity",
            check="reconstruction_and_recipient_rebuild",
            protocol_family=_protocol("rebuild_identity"),
            attacks=lambda: tuple((n, (a, b)) for n, a, b in t().REBUILD_PAIRS),
            boundary=lambda pair: t().rebuild_boundary(pair),
            specimen=lambda pair: t().field_dropping_digest(pair),
            breached=lambda r: t().rebuild_breached(r),
            control_check=_rebuild_identity_control,
            admissible=None,
            attack_example="width",
            reads="recipes only",
        ),
        FamilySpec(
            name="rebuild_report",
            check="reconstruction_and_recipient_rebuild",
            protocol_family="a reported build that differs from Carbon's own in any "
            "rebuilt field is detected (experiment.rebuild_differences)",
            attacks=_rebuild_report_attacks,
            boundary=rebuild_report_boundary,
            specimen=rebuild_report_specimen,
            breached=rebuild_report_breached,
            control_check=_rebuild_report_control,
            admissible=None,
            attack_example="tampered_recipe_digest",
            reads="recipes and public material",
        ),
    )


@functools.cache
def _controls():
    track_a = _track_a()
    oracle = _oracle_predictions
    out = []

    def add(family, split, name, make):
        out.append(ControlSpec(family, split, name, make))

    for label in TRAINED_PANEL:
        add(
            "permission_ablation",
            "trained",
            "panel_" + label,
            lambda x=label: _panel(x),
        )
    for label in HELD_OUT_PANEL:
        add(
            "permission_ablation",
            "held_out",
            "panel_" + label,
            lambda x=label: _panel(x),
        )
    for family in ("recipe_surface", "recipe_forgery", "rebuild_identity"):
        add(family, "trained", "recipe_control", lambda: dict(track_a.RECIPE_CONTROL))
        for label in HELD_OUT_PANEL:
            add(family, "held_out", "panel_" + label, lambda x=label: _panel(x))
    add(
        "practice_disclosure", "trained", "oracle_probe", lambda: {"probes": [oracle()]}
    )
    add(
        "practice_disclosure",
        "trained",
        "sealed_rule_v2",
        lambda: {"kind": "disclosure", "rule": "v2"},
    )
    # Held-out controls are genuinely different valid inputs, canonically
    # distinct from every trained one (a key-reordered or JSON round-tripped
    # copy canonicalises to the trained value and measures nothing new):
    # the public PRACTICE references as a single-precision model emits them,
    # rounded to six decimals, and two different probes in one session.
    add(
        "practice_disclosure",
        "held_out",
        "float32_probe",
        lambda: {"probes": [_single_precision(oracle())]},
    )
    add(
        "practice_disclosure",
        "held_out",
        "two_distinct_probes",
        lambda: {"probes": [oracle(), _rounded(oracle())]},
    )
    add("mandatory_failure", "trained", "oracle_predictions", oracle)
    add(
        "mandatory_failure",
        "held_out",
        "float32_predictions",
        lambda: _single_precision(oracle()),
    )
    add(
        "mandatory_failure",
        "held_out",
        "rounded_six_decimals_predictions",
        lambda: _rounded(oracle()),
    )
    add(
        "resource_accounting",
        "trained",
        "code_run_at_the_allowance",
        lambda: {"kind": "code_run", "arguments": {"seconds": CODE_RUN_SECONDS}},
    )
    add(
        "resource_accounting",
        "trained",
        "complete_run_scored",
        lambda: {"kind": "scoring", "predictions": oracle()},
    )
    add(
        "resource_accounting",
        "held_out",
        "code_run_one_second",
        lambda: {"kind": "code_run", "arguments": {"seconds": 1}},
    )
    add(
        "resource_accounting",
        "held_out",
        "code_run_half_the_allowance",
        lambda: {"kind": "code_run", "arguments": {"seconds": CODE_RUN_SECONDS // 2}},
    )
    add(
        "staged_bytes",
        "trained",
        "recipe_control_seed_7",
        lambda: {"strategy": dict(track_a.RECIPE_CONTROL), "seed": 7},
    )
    add(
        "staged_bytes",
        "held_out",
        "panel_deeponet_seed_11",
        lambda: {"strategy": _panel("deeponet"), "seed": 11},
    )
    add(
        "rebuild_report",
        "trained",
        "recipe_control_seed_7",
        lambda: {"strategy": dict(track_a.RECIPE_CONTROL), "seed": 7},
    )
    add(
        "rebuild_report",
        "held_out",
        "panel_knn_seed_11",
        lambda: {"strategy": _panel("knn"), "seed": 11},
    )
    return tuple(out)


#: Level 0 cannot test what needs participant code. Each is declared, never
#: run, never a pass. The levels are the ladder's (`challenge_pipeline.ladder`).
_PARTICIPANT_CODE = (
    "needs participant code, which Level 0 does not permit; executing hostile "
    "code needs the security owner's isolation decision, which is reserved"
)
SEAMS = (
    # The check id names protected material for Graphite ("confirmation"),
    # so the seam that covers it carries its own name.
    SeamSpec(
        "fresh_cases_rerun",
        "fresh_attack_confirmation",
        0,
        "needs a frozen study sheet and fresh cases",
    ),
    SeamSpec(
        "pod_timeout_typing",
        "resource_and_failure_accounting",
        0,
        "a pod run that times out is typed CANDIDATE_FAILED and never scored by "
        "experiment's pod outcome, while the frozen rule types a missing "
        "prediction FAILED_INFRA; whether a pod timeout is FAILED_INFRA or "
        "CANDIDATE_FAILED is open, so this adapter judges neither",
        "owner: whether a pod timeout is FAILED_INFRA or CANDIDATE_FAILED",
    ),
    SeamSpec(
        "practice_result_path_state",
        "adaptive_feedback_and_state_attacks",
        0,
        "repeated identical PRACTICE submissions through the stateful research "
        "task result path (get_research_result) need a running research session; "
        "practice_disclosure checks practice.feedback and the intake's rule facts "
        "at function level only",
    ),
    SeamSpec(
        "level_1_loss_expressions",
        "artifact_and_dependency_attacks",
        1,
        "the Level 1 surface is an engineering draft, not open: its attacks run "
        "only after the owner accepts the proposal and an expansion record exists",
    ),
    SeamSpec(
        "level_2_schedules_and_sampling",
        "adaptive_feedback_and_state_attacks",
        2,
        "no Level 2 proposal or expansion record exists for battery",
    ),
    SeamSpec(
        "level_3_numerical_routines",
        "construction_evaluation_isolation",
        3,
        _PARTICIPANT_CODE,
        "security owner: isolation for executing participant code",
    ),
    SeamSpec(
        "level_4_constrained_inference_export",
        "construction_evaluation_isolation",
        4,
        "hidden preprocessing/compilation and device/host memory " + _PARTICIPANT_CODE,
        "security owner: isolation for executing participant code",
    ),
    SeamSpec(
        "level_5_custom_inference",
        "score_exploitation_and_tail_failures",
        5,
        "child processes, inference/solver hybrids and custom inference; a case a "
        "participant's own inference omits would be typed FAILED_INFRA and excluded "
        "by exam.aggregate, so it becomes a surface only here. " + _PARTICIPANT_CODE,
        "security owner: isolation for executing participant code",
    ),
)


# -- the adapter -------------------------------------------------------------------------------
_MISSING = object()


def _get(attempt, key, default=None):
    if isinstance(attempt, Mapping):
        return attempt.get(key, default)
    return getattr(attempt, key, default)


def _strategy_from(arguments):
    # The core's one reading (`attack.analysis.strategy_argument`): a
    # `strategy_json` absent, null or "null" is no strategy, so a
    # `check_design` call's design is read; unparseable text is kept for
    # Carbon's gate to refuse.
    from carbon.agent_campaign.attack import analysis

    return analysis.strategy_argument(arguments, _MISSING)


def _inner_arguments(arguments):
    raw = arguments.get("arguments_json")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw if raw is not None else arguments


@dataclass(frozen=True)
class Assessment:
    """The oracle's full reading of one attempt (`assess`). `oracle` is the
    same reading in the core's `OracleResult`."""

    family: str
    attempt: str
    #: BREACH, WRONGFUL_REFUSAL, EXPOSURE, PROTECTED_WITHHELD, HELD,
    #: UNDETERMINED, NOT_APPLICABLE, or a no-answer verdict.
    reading: str
    basis: str
    observed: bool
    oracle: object

    @property
    def condition(self):
        return self.oracle.condition


class BatteryLevel0Adapter:
    """Battery at construction Level 0, for the attack engine."""

    challenge_id = CHALLENGE_ID
    level = LEVEL
    version = ADAPTER_VERSION
    controls_version = CONTROLS_VERSION

    @property
    def contract_digest(self):
        return _capability_index()[4]

    # -- the core's adapter protocol ---------------------------------------------------------
    def families(self):
        """The core's `FamilyDef`s, each with its engine `Family`."""
        out = []
        for spec in _families():
            trained = next(
                c for c in _controls() if c.family == spec.name and c.split == "trained"
            )
            out.append(
                FamilyDef(
                    name=spec.name,
                    check=spec.check,
                    boundary=spec.protocol_family,
                    attack_example=spec.attack_example,
                    control_example=trained.name,
                    family=self._engine_family(spec),
                )
            )
        return tuple(out)

    def controls(self, split):
        """The core's `Control`s of one split. Each carries its own `check()`,
        which builds the control and runs it against the real boundary."""
        if split not in SPLITS:
            raise ValueError("split is trained or held_out")
        return tuple(self._control(c) for c in _controls() if c.split == split)

    def oracle(self, family, attempt):
        """Carbon's verdict on one attempt, as the core's `OracleResult`
        (`assess` gives the full reading)."""
        return self.assess(family, attempt).oracle

    def rebuild(self, construction):
        """Carbon's rebuild (`build`), as the core's `Rebuilt` or
        `Unrebuildable`. An unrebuildable construction is never scored."""
        made = build(construction)
        if not made.rebuilt:
            core = REFUSAL_CODES.get(made.code, "refused_by_contract")
            issue_codes = sorted({str(code) for code, *_ in made.issues})
            if core == "refused_by_contract" and OUTSIDE_LEVEL_ISSUES & set(
                issue_codes
            ):
                core = "outside_level"
            detail = made.code + (": " + ", ".join(issue_codes) if issue_codes else "")
            return Unrebuildable(code=core, detail=detail)
        return Rebuilt(
            construction_digest=_digest(made.strategy),
            rebuilt_digest=_digest(made.record),
            detail={
                "record": made.record,
                "seed": made.seed,
                "served": made.served,
                "reason": made.reason,
            },
        )

    def level_families(self):
        """The core's `SeamFamily`s: always NOT_RUN, never a pass."""
        return tuple(
            SeamFamily(
                name=seam.name,
                check=seam.check,
                level=seam.level,
                reason=seam.reason
                + (
                    "; reserved: " + seam.reserved_decision
                    if seam.reserved_decision
                    else ""
                ),
            )
            for seam in SEAMS
        )

    # -- the session surface a Graphite session needs ----------------------------------------
    def permission_inventory(self):
        from carbon.agent_campaign import study

        return study.permission_inventory()

    def public_identity(self):
        from carbon.battery.challenge import CHALLENGE

        return {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version}

    def admission_refusals(self, strategy):
        """Carbon's own admission of a recipe (#504's reconstruction gate,
        `experiment.admit`): its refusal codes, empty when Carbon would
        rebuild it. `construction_contract_unrecorded` comes first when the
        contract record is not current."""
        made = build(strategy)
        if made.rebuilt:
            return []
        return [made.code] + sorted({str(code) for code, *_ in made.issues})

    def code_run_seconds(self):
        return code_run_seconds()

    def recipe_outside_contract(self):
        """The pinned scaffold with a model family the contract does not admit."""
        from carbon.battery.research import SCAFFOLD

        return {**SCAFFOLD, "backbone": "transolver"}

    # -- battery's own reading -----------------------------------------------------------------
    def surface(self):
        """The Level 0 surface: the permission inventory, by digest."""
        inventory = self.permission_inventory()
        return {
            "challenge": CHALLENGE_ID,
            "level": LEVEL,
            "profile": inventory["profile"],
            "contract_digest": inventory["construction_contract_digest"],
            "inventory_digest": _digest(inventory),
            "submission_form": inventory["submission_form"],
            "permitted": len(inventory["permitted"]),
            "not_permitted": len(inventory["not_permitted"]),
            "adapter_version": ADAPTER_VERSION,
        }

    def family_specs(self):
        return _families()

    def family_spec(self, name):
        if isinstance(name, FamilySpec):
            return name
        for spec in _families():
            if spec.name == name:
                return spec
        raise KeyError(name)

    def control_specs(self, split):
        if split not in SPLITS:
            raise ValueError("split is trained or held_out")
        return tuple(c for c in _controls() if c.split == split)

    def checks(self):
        """Every Track A check, with the families or seams that cover it."""
        covered = {check: [] for check in sorted(CHECKS[TRACK])}
        for spec in _families():
            covered[spec.check].append(spec.name)
        for seam in SEAMS:
            if seam.level == LEVEL:
                covered[seam.check].append(seam.name + ":" + NOT_RUN)
        return {check: tuple(names) for check, names in covered.items()}

    def controls_digest(self, split):
        return _digest(
            {
                "version": CONTROLS_VERSION,
                "split": split,
                "controls": [
                    [c.name, _digest(c.value())] for c in self.control_specs(split)
                ],
            }
        )

    def code_run_refusal(self, arguments):
        return code_run_refusal(arguments)

    def deterministic_baseline(self, root="."):
        """B2's deterministic side: battery's Track A harness, normalized."""
        return track_a_baseline(root)

    def control_passes(self, control):
        """One control against the real boundary: True when it passes."""
        spec = control
        if not isinstance(control, ControlSpec):
            (spec,) = [c for c in _controls() if c.name == control.name]
        return bool(self.family_spec(spec.family).control_check(spec.value()))

    def family_for(self, tool, arguments=None):
        """Which family a research tool call probes, or None."""
        from carbon.development_session.research_tools import PREFIX

        name = str(tool).removeprefix(PREFIX)
        arguments = arguments if isinstance(arguments, Mapping) else {}
        if name == "start_research_task":
            if arguments.get("kind") == "practice":
                return "recipe_surface"
            action = arguments.get("action")
            if action in CODE_ACTIONS:
                return "resource_accounting"
            if action == "check_design":
                return "permission_ablation"
            if action in WORKSPACE_ISOLATION_ACTIONS:
                # Miner-local workspace actions (reads, writes, inventory,
                # public material, notebook): judged against the carrier's
                # isolation boundary, never left UNASSIGNED.
                return "staged_bytes"
            if action == "roadmap":
                return "practice_disclosure"  # an advisory public read
            return None
        return TOOL_FAMILIES.get(name)

    def attempt_input(self, family, attempt):
        """The input an attempt carries for `family`, or `_MISSING`: its
        `value` (or `input`), else what a research tool call's `arguments`
        carry."""
        lane = _get(attempt, "lane")
        for key in ("value", "input"):
            value = _get(attempt, key, _MISSING)
            if value is not _MISSING:
                if (
                    family == "resource_accounting"
                    and isinstance(value, Mapping)
                    and value.get("kind") == "code_run"
                    and "lane" not in value
                ):
                    value = {**value, "lane": lane}
                return value
        arguments = _get(attempt, "arguments")
        if not isinstance(arguments, Mapping):
            return _MISSING
        if family == "recipe_surface":
            return _strategy_from(arguments)
        if family == "permission_ablation":
            strategy = _strategy_from(arguments)
            if strategy is _MISSING:
                return _MISSING
            return _ablation_item(strategy, "session")
        if family == "resource_accounting" and arguments.get("action") in CODE_ACTIONS:
            return {
                "kind": "code_run",
                "arguments": _inner_arguments(arguments),
                "lane": lane,
            }
        return _MISSING

    def assess(self, family, attempt):
        """Carbon's own reading of one attempt against `family`.

        An attempt is `(name, value)`, an `AttackInput`, or a mapping or
        object with `value` (or `input`, or a research tool call's
        `arguments`), a `name` and, for an observed session attempt,
        `path_accepted`: what the path did (True, False or None).

        - A declared attack (no `path_accepted`) is BREACH when the real
          boundary's detector fires; else HELD, which the core reports HELD
          only when the specimen fired on the same input (INCONCLUSIVE
          otherwise).
        - An observed attempt is BREACH when the path accepted what Carbon's
          own gate refuses; WRONGFUL_REFUSAL (core BREACHED with
          FAILING_TRIGGER) when the path refused what Carbon would admit and
          run; UNDETERMINED (core INCONCLUSIVE) when the path's outcome is
          unknown, or it refused an admissible input for a reason the family
          cannot judge; HELD when the path and Carbon's gate agree;
          NOT_APPLICABLE (core NOT_RUN) where the family has no independent
          gate.
        - A result (`result` or `output`) carrying protected material, or a
          path that accepted an attempt naming it, is EXPOSURE (core BREACHED
          with OTHER_SIGNAL). An attempt naming protected material that was
          refused, or whose outcome is unknown, or that is declared, is
          PROTECTED_WITHHELD (core NOT_RUN): no finding. Its input never
          reaches a boundary or a specimen.
        - A boundary that does not answer gives the engine's own verdict
          (FAILED_INFRA, TIMEOUT, CRASHED): never a pass, never a finding.
        """
        spec = self.family_spec(family)
        if isinstance(attempt, tuple) and len(attempt) == 2:
            name, value, observed = str(attempt[0]), attempt[1], _MISSING
        else:
            name = str(
                _get(attempt, "name")
                or _get(attempt, "identity")
                or _get(attempt, "attempt")
                or "attempt"
            )
            value = self.attempt_input(spec.name, attempt)
            observed = _get(attempt, "path_accepted", _MISSING)

        def done(reading, basis, verdict, evidence, specimen=None, weak=None):
            condition = CONDITION_OF.get(reading) if verdict == BREACHED else None
            oracle = OracleResult(
                family=spec.name,
                attempt=name,
                verdict=verdict,
                evidence_digest=_digest(
                    {"family": spec.name, "attempt": name, "evidence": evidence}
                ),
                condition=condition,
                specimen=specimen,
                specimen_digest=None if specimen is None else _digest(weak),
                reading=reading,
            )
            return Assessment(
                spec.name, name, reading, basis, observed is not _MISSING, oracle
            )

        def specimen_on(value):
            weak, verdict = _answer(spec.specimen, value)
            if verdict is None:
                verdict = FIRED if spec.breached(weak) else SILENT
            return verdict, weak

        def held(basis, evidence):
            verdict, weak = specimen_on(value)
            # A hold the detector cannot vouch for is no evidence.
            core = HELD if verdict == FIRED else INCONCLUSIVE
            return done(HELD, basis, core, evidence, verdict, weak)

        exposed = _get(attempt, "result") if not isinstance(attempt, tuple) else None
        if exposed is None and not isinstance(attempt, tuple):
            exposed = _get(attempt, "output")
        if exposed is not None and _protected(exposed):
            # What came back carries protected material: a real exposure,
            # whatever the request was. Nothing is handed to a boundary.
            return done(
                EXPOSURE,
                "the attempt's result carries protected material",
                BREACHED,
                None,
                SILENT,
                {"specimen": "not_run", "basis": "protected material"},
            )
        if value is _MISSING:
            return done(NOT_APPLICABLE, "no input for this family", NOT_RUN, None)
        if _protected(value) or _protected(name):
            # Never handed to a boundary or a specimen. A path that accepted
            # it exposed it; one that refused it, or never saw it, held, and
            # that is no finding (the oracle judges nothing it cannot run).
            if observed not in (_MISSING, None) and bool(observed):
                return done(
                    EXPOSURE,
                    "the path accepted an attempt naming protected material",
                    BREACHED,
                    _digest(value),
                    SILENT,
                    {"specimen": "not_run", "basis": "protected material"},
                )
            basis = {
                False: "the path refused an attempt naming protected material",
                None: "the path's outcome is not plain; the attempt names "
                "protected material and is never handed to a boundary",
            }.get(
                observed,
                "a declared attempt names protected material and is "
                "never handed to a boundary",
            )
            return done(PROTECTED_WITHHELD, basis, NOT_RUN, _digest(value))
        if observed is _MISSING:
            outcome, failed = _answer(spec.boundary, value)
            if failed is not None:
                verdict, weak = specimen_on(value)
                return done(
                    failed,
                    "the boundary did not answer",
                    failed,
                    outcome,
                    verdict,
                    weak,
                )
            if spec.breached(outcome):
                # Evidence is kept by digest only, so a breach that carries
                # protected bytes (a staged canary) is still a breach.
                verdict, weak = specimen_on(value)
                return done(
                    BREACH,
                    "a declared attack breached the real boundary",
                    BREACHED,
                    outcome,
                    verdict,
                    weak,
                )
            if _protected(outcome):
                return done(
                    EXPOSURE,
                    "the boundary's result names protected material",
                    BREACHED,
                    None,
                    SILENT,
                    {"specimen": "not_run", "basis": "protected material"},
                )
            return held("a declared attack held at the real boundary", outcome)
        if spec.admissible is None:
            return done(
                NOT_APPLICABLE, "no independent gate for this family", NOT_RUN, None
            )
        if observed is None:
            verdict, weak = specimen_on(value)
            return done(
                UNDETERMINED,
                "the path's outcome is not plain",
                INCONCLUSIVE,
                None,
                verdict,
                weak,
            )
        admissible, failed = _answer(spec.admissible, value)
        if failed is not None:
            verdict, weak = specimen_on(value)
            return done(
                failed,
                "Carbon's gate did not answer",
                failed,
                admissible,
                verdict,
                weak,
            )
        if admissible is None:
            return done(NOT_APPLICABLE, "not this family's input", NOT_RUN, None)
        evidence = {"path_accepted": bool(observed), "carbon_admits": bool(admissible)}
        if observed and not admissible:
            verdict, weak = specimen_on(value)
            return done(
                BREACH,
                "the path accepted what Carbon's own gate refuses",
                BREACHED,
                evidence,
                verdict,
                weak,
            )
        if observed and admissible:
            return held("the path accepted what Carbon's own gate admits", evidence)
        if not observed and not admissible:
            return held("the path refused what Carbon's own gate refuses", evidence)
        # The path refused what Carbon's own gate admits.
        if spec.runnable is None:
            verdict, weak = specimen_on(value)
            return done(
                UNDETERMINED,
                "the path refused what Carbon's gate admits, for a reason this "
                "family's gate does not judge",
                INCONCLUSIVE,
                evidence,
                verdict,
                weak,
            )
        runnable, failed = _answer(spec.runnable, value)
        if failed is not None:
            verdict, weak = specimen_on(value)
            return done(
                failed, "Carbon's gate did not answer", failed, runnable, verdict, weak
            )
        evidence = {**evidence, "carbon_runs": bool(runnable)}
        verdict, weak = specimen_on(value)
        if runnable and _get(attempt, "refusal_kind") == "construction":
            # A wrongful rejection only when the path refused the construction
            # itself (a contract or compiler refusal). A refusal of the request
            # (an invalid argument, a missing field, a rejected wrapper) is not
            # the family's concern: nothing judged.
            return done(
                WRONGFUL_REFUSAL,
                "the path refused the construction Carbon would admit and run",
                BREACHED,
                evidence,
                verdict,
                weak,
            )
        if runnable:
            return done(
                UNDETERMINED,
                "the path refused what Carbon admits, but for a request-level "
                "reason, not a refusal of the construction",
                INCONCLUSIVE,
                {**evidence, "refusal_kind": _get(attempt, "refusal_kind")},
                verdict,
                weak,
            )
        return done(
            UNDETERMINED,
            "the path refused what Carbon admits but would not run on this path",
            INCONCLUSIVE,
            evidence,
            verdict,
            weak,
        )

    def carbon_code(self, refused):
        """Carbon's own refusal code behind a core `Unrebuildable`: the code
        its `detail` leads with (for example `construction_contract_unrecorded`)."""
        return str(getattr(refused, "detail", "")).split(":", 1)[0]

    def rebuild_differences(self, rebuilt, built):
        """The fields on which a reported build differs from Carbon's
        (`experiment.rebuild_differences`)."""
        from carbon.agent_campaign.graphite import experiment

        return experiment.rebuild_differences(rebuilt.detail["record"], built)

    def trained_control(self, name):
        """A family's control for the engine: `() -> bool`, True when every
        trained control passes. It reads the trained split only."""
        spec = self.family_spec(name)

        def control():
            trained = tuple(
                c for c in self.control_specs("trained") if c.family == name
            )
            return bool(trained) and all(spec.control_check(c.value()) for c in trained)

        return control

    def engine_families(self):
        """The engine `Family` of every family (`families()[i].family`)."""
        return tuple(f.family for f in self.families())

    def _engine_family(self, spec):
        return Family(
            name=spec.name,
            check=spec.check,
            boundary=spec.boundary,
            attacks=spec.attacks,
            specimen=spec.specimen,
            breached=spec.breached,
            control=self.trained_control(spec.name),
            description=spec.protocol_family,
        )

    def _control(self, spec):
        check = self.family_spec(spec.family).control_check

        return Control(
            name=spec.name,
            family=spec.family,
            split=spec.split,
            version=spec.version,
            check=lambda: bool(check(spec.value())),
            # The control's registered identity is its content.
            input_digest=_control_input_digest(spec),
        )


_INPUT_DIGESTS = {}


def _control_input_digest(spec):
    """The digest of what a control submits, computed once per control."""
    found = _INPUT_DIGESTS.get((spec.version, spec.name))
    if found is None:
        found = _INPUT_DIGESTS[(spec.version, spec.name)] = _digest(spec.value())
    return found


ADAPTER = BatteryLevel0Adapter()
