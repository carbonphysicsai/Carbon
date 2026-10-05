"""Motor's Level 0 attack adapter (OWNER-GRAPHITE-ATTACKER-01; the Graphite
test wave's motor row, approved by the owner on 2026-10-04 with battery and
cooling).

Motor (`electric-motor-magnetics`) at construction Level 0 admits declarative
recipes only: a miner sends a kernel-ridge `TrainingStrategy` choosing a
kernel length and a ridge from the published grid, and Carbon compiles,
rebuilds and scores it with its own code (CHALLENGE-MOTOR-02). This adapter
gives the Challenge-neutral attack engine everything motor-specific it needs
at that level, in the shape of cooling's adapter (`adapters/cooling.py`):

- **surface and contract**: the Level 0 permission inventory
  (`agent_campaign.study.permission_inventory`) and the live construction
  contract digest, read, never changed;
- **families**: the eight shared Track A checks
  (`challenge_readiness.admission.CHECKS`), each with attacks run against the
  real boundary, a deliberately weakened specimen that must fire (a silent
  specimen is INCONCLUSIVE, never a pass), an attack example and a valid
  control. The Test Lead's motor vectors (`MOTOR_VECTORS`) run in five
  families: a flat curve with the right mean, a phase-shifted ripple, a
  flipped period or orientation, saturation-blind linear iron and a ripple
  scaled to game the normalised error;
- **controls**, split `trained` (the engine may see them) and `held_out` (only
  the report reads them, for the wrongful-rejection rate), versioned by
  `CONTROLS_VERSION`; every held-out control is a genuinely different valid
  input, canonically distinct from every trained one;
- **the oracle**: Carbon's own verdict on one attempt, from the real boundary
  (the construction contract gate, the motor compiler, motor's public
  PRACTICE rule `carbon.motor.practice.score_practice` with its exam gates and
  aggregate, the practice feedback, the worker staging, the population screen,
  the public-material digests and the shared rebuild comparison);
- **rebuild**: Carbon's own typed rebuild record for a strategy (the contract
  gate and motor's compiler, staging and practice program, under the newest
  expansion record), refused with a typed code when Carbon cannot rebuild a
  construction, which is then never scored;
- **seams**: what Level 0 cannot test, and every vector that needs an owner
  value no record holds (a tolerance, a phase allowance, a duplicate-case
  design), declared NOT_RUN with the missing value named. No threshold is
  invented here.

What motor does not have yet. No `ChallengeScoring` is registered for motor
(`challenge_validator.scoring.scoring_for` refuses it with
`challenge_scoring_not_registered`), so Graphite's pods do not serve it and
the phase-4 runner refuses a motor run before anything starts. The adapter
therefore scores with motor's own public PRACTICE rule, the rule the motor
practice provider uses, and its rebuild record is Carbon's alone: there is no
pod build to compare (`pod_scoring_not_registered`, a seam). Official
evaluation stays the typed `motor_validator_not_served` refusal.

What it is not. Nothing here executes participant code, or reads counted
GetDP material, the decision study or its references, the private 60-case
pool or its commitment, or any sealed material; only the public TRAIN and
PRACTICE records (and the public calibration document their loader checks)
are read. Nothing changes the construction contract
(`carbon/reconstruction/capability_registry.py`), motor's behaviour or the
design-search code. Every value pinned here is a copy of a motor value,
checked against its source by a test. A held attack is evidence about the
boundary it called, nothing more; zero findings is attempted coverage, never
a bound; and no verdict here is security acceptance or scientific
qualification.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import math
import shutil
import struct
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean

from carbon.agent_campaign.attack import adapter as _core
from carbon.agent_campaign.attack import engine as _engine
from carbon.challenge_readiness.admission import CHECKS, LEDGER_TRACK

CHALLENGE_ID = "electric-motor-magnetics"
LEVEL = 0
PROFILE = "level-0"
ADAPTER_VERSION = "carbon.attack.adapter.motor-l0.v1"
CONTROLS_VERSION = "carbon.attack.controls.motor-l0.v1"
BUILD_SCHEMA = "carbon.attack.motor-l0-carbon-build.v1"
TRACK = LEDGER_TRACK
SPLITS = _core.SPLITS
FAILING_TRIGGER, OTHER_SIGNAL = "FAILING_TRIGGER", "OTHER_SIGNAL"
REPOSITORY = Path(__file__).resolve().parents[4]

#: The oracle's own reading of an attempt (`assess`), as cooling's adapter
#: reads it: BREACH and WRONGFUL_REFUSAL are FAILING_TRIGGER, EXPOSURE is
#: OTHER_SIGNAL (each core BREACHED); PROTECTED_WITHHELD is never handed to a
#: boundary and is no finding (core NOT_RUN).
BREACH, EXPOSURE = "BREACH", "EXPOSURE"
WRONGFUL_REFUSAL, PROTECTED_WITHHELD = "WRONGFUL_REFUSAL", "PROTECTED_WITHHELD"
UNDETERMINED, NOT_APPLICABLE = "UNDETERMINED", "NOT_APPLICABLE"
CONDITION_OF = {
    BREACH: FAILING_TRIGGER,
    WRONGFUL_REFUSAL: FAILING_TRIGGER,
    EXPOSURE: OTHER_SIGNAL,
}

Family = _engine.Family
Control = _core.Control
FamilyDef = _core.FamilyDef
SeamFamily = _core.SeamFamily
AttackInput = _core.AttackInput
OracleResult = _core.OracleResult
Rebuilt = _core.Rebuilt
Unrebuildable = _core.Unrebuildable
HELD, BREACHED = _engine.HELD, _engine.BREACHED
FIRED, SILENT = _engine.FIRED, _engine.SILENT
INCONCLUSIVE, NOT_RUN = _core.INCONCLUSIVE, _core.NOT_RUN

# -- pinned copies of motor values (each checked against its source by a test) ----------------
#: The wall allowance one code run may ask for: motor's practice worker
#: allowance (`carbon.motor.research.PRACTICE_SECONDS`).
CODE_RUN_SECONDS = 600
#: Torque samples per rotor period (`carbon.motor.domain.ANGLE_STEPS`), used
#: here only to shape attacks (a quarter-period shift, a short curve).
ANGLE_STEPS = 60
#: The important group's current-density floor (`exam.J_IMPORTANT`, a
#: provisional DEVELOPMENT value), used here only to choose which cases an
#: attack degrades; the exam types the group itself.
J_IMPORTANT = 10.0
#: What a miner's public practice feedback may carry
#: (`carbon.motor.practice.feedback`) and its aggregate summary
#: (`carbon.motor.exam.aggregate`).
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
        "components",
        "important_score",
        "n_important",
        "important_mean_bias_nm",
        "gate_failures",
    }
)
PRACTICE_FLAGS = {
    "adaptively_seen": True,
    "final_exam": False,
    "official_eligible": False,
    "scientific_qualification": False,
}
#: The files a practice worker is staged with (`practice.staged_files`):
#: Carbon's recipe modules, the public TRAIN bytes, the PRACTICE inputs (never
#: their labels) and the compiled recipe.
STAGED_NAMES = frozenset(
    {
        "learned-baseline.py",
        "motor-domain.py",
        "motor-recipes.py",
        "train-v1.jsonl",
        "practice-inputs.json",
        "recipe.json",
    }
)
#: The fields Carbon compares between its own build and a reported one
#: (`challenge_validator.scoring.REBUILT_FIELDS`).
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
#: mapped to the core's `Unrebuildable` code. The Carbon code leads the
#: refusal's detail.
REFUSAL_CODES = {
    "strategy_not_an_object": "not_declarative",
    "strategy_not_json": "not_declarative",
    "not_the_motor_development_challenge": "unknown_construction",
    "seed_invalid": "unknown_construction",
    # Carbon's own records or material are not current: Carbon's side, never
    # the construction's.
    "construction_contract_unrecorded": "rebuild_failed_infra",
    "public_material_mismatch": "rebuild_failed_infra",
    "contract_refused": "refused_by_contract",
    "recipe_rejected": "refused_by_contract",
    "strategy_too_large": "refused_by_contract",
    "protected_material_named": "protected_material",
}
OUTSIDE_LEVEL_ISSUES = frozenset(
    {"parameter.not_rebuildable", "backbone.not_rebuildable"}
)
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
#: Workspace actions judged against the carrier's isolation boundary, so they
#: are never left UNASSIGNED.
WORKSPACE_ISOLATION_ACTIONS = frozenset(
    {"read_file", "write_file", "inventory", "public_material", "notebook"}
)
ATTACKER_LANE = "graphite_attacker"
CODE_RUN_RULE_LANES = frozenset({ATTACKER_LANE})
#: Synthetic markers the isolation family plants (never real material).
LABEL_MARKER = "motor-attack-label-marker-v1"
FILE_MARKER = "motor-attack-file-marker-v1"

#: What every vector's attack example and control read: the attack HELD at
#: the real boundary and FIRED on the vulnerable specimen; the control PASSED.
VECTOR_EXPECTED = {
    "real_boundary": "HELD",
    "vulnerable_specimen": "FIRED",
    "control": "PASSED",
}
#: The Test Lead's motor vectors: the families that run each where a
#: registered boundary exists (the first is the vector's own), its attack
#: example and trained control, the further attacks it maps to in the other
#: families, and the NOT_RUN seam that names the owner value it still needs
#: (None where the registered gates and score cover the vector whole).
MOTOR_VECTORS = {
    "flat_curve_right_mean": {
        "check": "score_exploitation_and_tail_failures",
        "families": ("ripple_omission",),
        "attack": "flat_curve_at_the_reference_mean",
        "control": "ripple_omission_trained_exact_predictions",
        "also": {},
        "seam": "ripple_amplitude_bias_tolerance",
        "expected": VECTOR_EXPECTED,
    },
    "phase_shifted_ripple": {
        "check": "score_exploitation_and_tail_failures",
        "families": ("ripple_phase",),
        "attack": "ripple_shifted_a_quarter_period",
        "control": "ripple_phase_trained_exact_predictions",
        "also": {},
        "seam": "ripple_phase_tolerance",
        "expected": VECTOR_EXPECTED,
    },
    "flipped_period_or_orientation": {
        "check": "score_exploitation_and_tail_failures",
        "families": ("ripple_phase", "mandatory_failure", "population_screen"),
        "attack": "angle_order_reversed",
        "control": "ripple_phase_trained_exact_predictions",
        "also": {
            "mandatory_failure": "torque_sign_flipped_on_every_case",
            "population_screen": "generating_quadrant_current_angle",
        },
        "seam": None,
        "expected": VECTOR_EXPECTED,
    },
    "saturation_blind_linear_iron": {
        "check": "score_exploitation_and_tail_failures",
        "families": ("saturation_optimism", "population_screen"),
        "attack": "important_mean_linear_in_current",
        "control": "saturation_optimism_trained_exact_predictions",
        "also": {
            "population_screen": "benchmark_nominal_current_density_beyond_the_box",
        },
        "seam": "saturation_bias_tolerance",
        "expected": VECTOR_EXPECTED,
    },
    "ripple_scaled_to_game_normalised_error": {
        "check": "score_exploitation_and_tail_failures",
        "families": ("ripple_scaling",),
        "attack": "ripple_halved_shape_kept",
        "control": "ripple_scaling_trained_exact_predictions",
        "also": {},
        "seam": "ripple_amplitude_bias_tolerance",
        "expected": VECTOR_EXPECTED,
    },
}


@dataclass(frozen=True)
class FamilySpec:
    """One attack family at Level 0 (cooling's `FamilySpec` shape): the real
    boundary, its attacks, its weakened specimen, its control check and, for
    an observed session attempt, Carbon's independent gate (`admissible`) and
    whether Carbon would also run it (`runnable`)."""

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
    code: str | None = None
    issues: tuple = ()

    @property
    def rebuilt(self):
        return self.code is None


class _Refused(ValueError):
    """A typed refusal inside Carbon's motor rebuild."""

    def __init__(self, code, issues=()):
        super().__init__(code)
        self.code, self.issues = code, tuple(issues)


# -- helpers -----------------------------------------------------------------------------------
def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=repr)


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


def _protected(value):
    """Graphite's protected-material check (`graphite.tools.protected`)."""
    from carbon.agent_campaign.graphite import literature, tools  # noqa: F401

    return tools.protected(value)


def _answer(call, *args):
    """(result, None), or (evidence, verdict) when the call did not answer."""
    return _engine.answer(call, *args)


@functools.cache
def _material():
    """Motor's verified public material (TRAIN, PRACTICE and calibration)."""
    from carbon.motor.challenge import PublicMaterial

    return PublicMaterial.load(REPOSITORY)


@functools.cache
def _practice():
    from carbon.motor.practice import PracticeSet

    return PracticeSet.load(REPOSITORY)


def _records():
    return _practice().records


def _scaffold():
    from carbon.motor.research import SCAFFOLD

    return copy.deepcopy(SCAFFOLD)


def _strategy(length=None, ridge=None, **extra):
    """The scaffold with its grid choices replaced and `extra` parameters."""
    strategy = _scaffold()
    if length is not None:
        strategy["parameters"]["length"] = length
    if ridge is not None:
        strategy["parameters"]["ridge"] = ridge
    strategy["parameters"].update(extra)
    return strategy


def _contract():
    from carbon.reconstruction.capability_registry import MOTOR_CHALLENGE, contract

    return contract(MOTOR_CHALLENGE)


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
    found = {families.get(strategy.get("backbone"), "unregistered.backbone")}
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
    dimension, _, suffix = capability_id.partition(".")
    if dimension == "model_family":
        return {**_scaffold(), "backbone": suffix}
    return _strategy(**{suffix: True})


@functools.cache
def _control_recipe():
    from carbon.motor.compile import compile_recipe

    return compile_recipe(_scaffold())[1]


def _floats(value, convert):
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
    return _floats(value, lambda x: round(x, places))


def _same(a, b):
    """Equal up to floating round-off (a numerical comparison, never a
    physics tolerance)."""
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)


# -- predictions built from the public PRACTICE references -------------------------------------
def _oracle_predictions():
    """The public PRACTICE references as predictions (exact: score 0)."""
    return {
        r["case_id"]: {"torque_nm": list(r["outputs"]["torque_nm"])} for r in _records()
    }


def _current_density():
    return {r["case_id"]: r["inputs"]["current_density_a_mm2"] for r in _records()}


def _important_ids():
    """Cases at or above the important current density (`J_IMPORTANT`)."""
    return frozenset(case for case, j in _current_density().items() if j >= J_IMPORTANT)


def _chosen(where):
    """The case ids an attack edits: `all`, `important` or `representative`."""
    every = {r["case_id"] for r in _records()}
    hot = _important_ids()
    return {"all": every, "important": hot, "representative": every - hot}[where]


def _split(curve):
    mean = fmean(curve)
    return mean, [t - mean for t in curve]


def _edited(edit, where="all"):
    """The exact references with every chosen case's curve changed by
    `edit(curve, case_id)`."""
    out, ids = _oracle_predictions(), _chosen(where)
    for case in ids:
        out[case]["torque_nm"] = edit(out[case]["torque_nm"], case)
    return out


def _flat(where="all"):
    """Each chosen curve replaced by its own period mean: the right mean
    torque, no ripple (the textbook constant-torque answer)."""
    return _edited(lambda curve, _case: [fmean(curve)] * len(curve), where)


def _rolled(steps, where="all"):
    """Each chosen curve shifted along the rotor angle by `steps` samples
    (periodic): the same mean and ripple values, the wrong phase."""
    return _edited(lambda curve, _case: curve[-steps:] + curve[:-steps], where)


def _reversed(where="all"):
    """Each chosen curve with its angle order reversed: the period swept the
    other way, the same mean and ripple values."""
    return _edited(lambda curve, _case: list(reversed(curve)), where)


def _negated(where="all"):
    """Each chosen curve with its sign flipped (the torque's orientation)."""
    return _edited(lambda curve, _case: [-t for t in curve], where)


def _ripple_scaled(factor, where="all"):
    """Each chosen curve's ripple (the curve less its mean) multiplied by
    `factor` with the mean kept: the shape kept, the amplitude changed."""

    def edit(curve, _case):
        mean, rest = _split(curve)
        return [mean + factor * r for r in rest]

    return _edited(edit, where)


def _mean_scaled(factor_of, where="all"):
    """Each chosen curve's period mean multiplied by `factor_of(case)` with
    its ripple kept."""

    def edit(curve, case):
        mean, rest = _split(curve)
        return [mean * factor_of(case) + r for r in rest]

    return _edited(edit, where)


def _linear_in_current():
    """Saturation-blind linear iron: on the important cases (where
    saturation acts) the period-mean torque grows in proportion to the
    current density above the important floor, as an unsaturated iron model
    would extrapolate it; the ripple is kept."""
    density = _current_density()
    return _mean_scaled(lambda case: density[case] / J_IMPORTANT, "important")


def _corrupt(case_index, edit):
    """The exact references with one case's prediction changed by `edit`."""
    out = _oracle_predictions()
    case = sorted(out)[case_index]
    out[case] = edit(copy.deepcopy(out[case]))
    return out


# -- motor's public PRACTICE rule as each scoring family reads it ------------------------------
def _score(predictions):
    """Rows and summary from motor's public PRACTICE rule
    (`practice.score_practice`: the exam's typing, gates, components and
    aggregate over the public PRACTICE cases, normalised by public TRAIN)."""
    from carbon.motor import practice

    if not isinstance(predictions, Mapping):
        predictions = {}
    return practice.score_practice(predictions, _practice(), _material())


def _predictions_of(value):
    if isinstance(value, Mapping) and "predictions" in value:
        return value["predictions"]
    return value


def score_view(value):
    """The rule's summary of a prediction set, with the attack's tags.
    `value` is `{"predictions": ..., ...tags}` or a bare prediction set."""
    _rows, s = _score(_predictions_of(value))
    where = value.get("where", "all") if isinstance(value, Mapping) else "all"
    return {
        "eligible": bool(s["eligible"]),
        "score": s["score"],
        "components": s["components"],
        "n_cases": s["n_cases"],
        "n_scored": s["n_scored"],
        "n_gate_failed": s["n_gate_failed"],
        "n_failed_infra": s["n_failed_infra"],
        "gate_failures": s["gate_failures"],
        "important_score": s["important_score"],
        "n_important": s["n_important"],
        "important_mean_bias_nm": s["important_mean_bias_nm"],
        "where": where,
    }


def _eligible_control(value):
    return score_view(value)["eligible"]


def _scored_rows(value):
    rows, _summary = _score(_predictions_of(value))
    references = {r["case_id"]: r for r in _records()}
    return [
        (row, _predictions_of(value)[row["case_id"]], references[row["case_id"]])
        for row in rows
        if row.get("state") == "SCORABLE"
    ]


def _ripple_by(compare, value):
    """The view with its ripple component replaced by a specimen's own
    per-case ripple comparison (`compare(predicted_rest, reference_rest)`),
    normalised by the same public TRAIN scale; the score recomputed."""
    from carbon.motor import exam

    view = score_view(value)
    scale = exam.scales_from_train(_material().train)["s_ripple"]
    errors = []
    for _row, prediction, reference in _scored_rows(value):
        _pm, p_rest = _split([float(t) for t in prediction["torque_nm"]])
        _rm, r_rest = _split(reference["outputs"]["torque_nm"])
        errors.append(compare(p_rest, r_rest) / scale)
    components = dict(view["components"] or {})
    if errors:
        components["ripple"] = fmean(errors)
    kept = [components.get(k) for k in ("mean", "ripple")]
    score = fmean(kept) if all(v is not None for v in kept) else view["score"]
    return {**view, "components": components, "score": score}


def _rms(values):
    return math.sqrt(fmean(v * v for v in values)) if values else 0.0


def ripple_uncharged(result):
    """An eligible set whose ripple is wrong (missing, shifted, reversed or
    rescaled; every gate passed) must still cost ripple error: the rule
    scores the ripple's shape sample by sample, separately from the mean."""
    if not result["eligible"]:
        return False  # a gate caught it: never compensated
    components = result["components"] or {}
    ripple = components.get("ripple")
    return (
        ripple is None or ripple <= 0 or result["score"] is None or result["score"] <= 0
    )


# mandatory failure: a gate failure is never compensated by score ----------------------------
def _mandatory_inputs():
    def at(index, edit):
        return _corrupt(index, edit)

    def nan_value(p):
        return {"torque_nm": [math.nan, *p["torque_nm"][1:]]}

    def infinite_value(p):
        return {"torque_nm": [*p["torque_nm"][:-1], math.inf]}

    def short_curve(p):
        return {"torque_nm": p["torque_nm"][:-1]}

    def long_curve(p):
        return {"torque_nm": [*p["torque_nm"], p["torque_nm"][0]]}

    def missing_torque(_p):
        return {"torque_curve": "omitted"}

    def scalar_torque(p):
        return {"torque_nm": fmean(p["torque_nm"])}

    def boolean_sample(p):
        return {"torque_nm": [True, *p["torque_nm"][1:]]}

    def string_sample(p):
        return {"torque_nm": [str(p["torque_nm"][0]), *p["torque_nm"][1:]]}

    def mapping_curve(p):
        return {"torque_nm": dict(enumerate(p["torque_nm"]))}

    def negated(p):
        return {"torque_nm": [-t for t in p["torque_nm"]]}

    loaded = max(_current_density().items(), key=lambda item: item[1])[0]
    loaded_index = sorted(_oracle_predictions()).index(loaded)
    return (
        ("nan_torque_sample", at(0, nan_value)),
        ("infinite_torque_sample", at(1, infinite_value)),
        ("curve_one_sample_short", at(2, short_curve)),
        ("curve_one_sample_long", at(3, long_curve)),
        ("torque_field_missing", at(4, missing_torque)),
        ("scalar_torque_instead_of_a_curve", at(5, scalar_torque)),
        ("boolean_torque_sample", at(6, boolean_sample)),
        ("string_torque_sample", at(7, string_sample)),
        ("curve_as_a_mapping", at(8, mapping_curve)),
        ("torque_sign_flipped_on_the_most_loaded_case", at(loaded_index, negated)),
        (
            "torque_sign_flipped_on_every_case",
            {"predictions": _negated(), "where": "all"},
        ),
    )


def mandatory_breached(result):
    """Every attack set carries a gate failure: any eligible result, or one
    that counts no gate failure, compensated it."""
    return result["eligible"] or result["n_gate_failed"] == 0


def averaging_scorer(value):
    """Vulnerable specimen: eligibility by the soft score alone, gates ignored."""
    view = score_view(value)
    return {**view, "eligible": view["n_scored"] > 0, "n_gate_failed": 0}


# a flat curve with the right mean ------------------------------------------------------------
def _omission_attacks():
    return (
        (
            "flat_curve_at_the_reference_mean",
            {"predictions": _flat(), "where": "all"},
        ),
        (
            "important_group_flat_rest_exact",
            {"predictions": _flat("important"), "where": "important"},
        ),
        (
            "representative_group_flat_rest_exact",
            {"predictions": _flat("representative"), "where": "representative"},
        ),
    )


def mean_only_scorer(value):
    """Vulnerable specimen: the curve graded by its period mean alone, so a
    flat curve at the right mean costs nothing."""
    view = score_view(value)
    components = dict(view["components"] or {})
    components["ripple"] = 0.0
    mean = components.get("mean")
    return {
        **view,
        "components": components,
        "score": None if mean is None else fmean([mean, 0.0]),
    }


# a phase-shifted ripple, and the period swept the other way -----------------------------------
def _phase_attacks():
    quarter = ANGLE_STEPS // 4
    return (
        (
            "ripple_shifted_a_quarter_period",
            {"predictions": _rolled(quarter), "where": "all"},
        ),
        (
            "ripple_shifted_one_angle_step",
            {"predictions": _rolled(1), "where": "all"},
        ),
        (
            "important_group_shifted_half_a_period",
            {
                "predictions": _rolled(ANGLE_STEPS // 2, "important"),
                "where": "important",
            },
        ),
        ("angle_order_reversed", {"predictions": _reversed(), "where": "all"}),
    )


def phase_blind_ripple_scorer(value):
    """Vulnerable specimen: the ripple graded by its distribution of values
    (sorted), blind to where in the rotor period each value falls, so a
    shifted or reversed ripple costs nothing."""

    def compare(p_rest, r_rest):
        pairs = list(zip(sorted(p_rest), sorted(r_rest)))
        if len(p_rest) != len(r_rest) or all(_same(a, b) for a, b in pairs):
            return 0.0
        return _rms([a - b for a, b in pairs])

    return _ripple_by(compare, value)


# a ripple rescaled to game the normalised error ----------------------------------------------
def _scaling_attacks():
    return (
        ("ripple_halved_shape_kept", {"predictions": _ripple_scaled(0.5)}),
        ("ripple_doubled_shape_kept", {"predictions": _ripple_scaled(2.0)}),
        ("ripple_tenfold_shape_kept", {"predictions": _ripple_scaled(10.0)}),
        (
            "important_group_ripple_a_tenth_rest_exact",
            {"predictions": _ripple_scaled(0.1, "important"), "where": "important"},
        ),
    )


def shape_normalised_ripple_scorer(value):
    """Vulnerable specimen: each ripple normalised by its own amplitude
    before it is compared, so a ripple of the right shape scores zero at any
    amplitude (an error a submission can game by rescaling)."""

    def compare(p_rest, r_rest):
        p_scale, r_scale = _rms(p_rest), _rms(r_rest)
        if len(p_rest) != len(r_rest) or p_scale == 0 or r_scale == 0:
            return _rms([a - b for a, b in zip(p_rest, r_rest)])
        diff = [a / p_scale - b / r_scale for a, b in zip(p_rest, r_rest)]
        return 0.0 if all(_same(d, 0.0) for d in diff) else _rms(diff)

    return _ripple_by(compare, value)


# saturation-blind linear iron: torque promised where saturation acts -------------------------
def _saturation_attacks():
    density = _current_density()

    def linear_everywhere(case):
        # Linear in the current above the floor, and five percent high below
        # it: optimism on every case, growing where saturation acts.
        if density[case] < J_IMPORTANT:
            return 1.05
        return density[case] / J_IMPORTANT

    return (
        (
            "important_mean_linear_in_current",
            {"predictions": _linear_in_current(), "where": "important"},
        ),
        (
            "important_mean_ten_percent_high",
            {
                "predictions": _mean_scaled(lambda _c: 1.1, "important"),
                "where": "important",
            },
        ),
        (
            "every_mean_five_percent_high",
            {"predictions": _mean_scaled(lambda _c: 1.05), "where": "all"},
        ),
        (
            "representative_mean_ten_percent_high",
            {
                "predictions": _mean_scaled(lambda _c: 1.1, "representative"),
                "where": "representative",
            },
        ),
        (
            "every_mean_linear_in_current_above_the_floor",
            {"predictions": _mean_scaled(linear_everywhere), "where": "all"},
        ),
    )


def saturation_breached(result):
    """A set that promises more torque than the reference (every gate passed)
    must score worse than the exact references (score above 0), and, where it
    over-predicts on the important group, the rule must report that group's
    mean-torque bias as positive (`important_mean_bias_nm`)."""
    if not result["eligible"]:
        return False
    score = result["score"]
    if score is None or score <= 0:
        return True
    if result["where"] in ("all", "important"):
        bias = result["important_mean_bias_nm"]
        return bias is None or bias <= 0
    return False


def signed_torque_scorer(value):
    """Vulnerable specimen: a score that rewards promised torque (the negated
    mean signed error), with the important group's bias dropped."""
    view = score_view(value)
    rows, _summary = _score(_predictions_of(value))
    signed = [r["mean_signed_error_nm"] for r in rows if "mean_signed_error_nm" in r]
    return {
        **view,
        "score": -fmean(signed) if signed else None,
        "important_mean_bias_nm": None,
    }


def _saturation_control(value):
    """An exact or conservative set is eligible and shows no over-prediction
    on the important group."""
    view = score_view(value)
    bias = view["important_mean_bias_nm"]
    return view["eligible"] and bias is not None and bias <= 0


# the population screen: outside the box, unbuildable, or the other quadrant -----------------
#: An input-box corner whose geometry cannot be built (the slot opening is
#: wider than the slot behind it), found by searching the box's corners with
#: the public `domain.validity`.
UNBUILDABLE_CORNER = {
    "magnet_mm": 1.5,
    "embrace": 0.55,
    "airgap_mm": 0.3,
    "slot_open_deg": 6.0,
    "tooth_mm": 5.0,
    "slot_bottom_mm": 34.0,
    "current_density_a_mm2": 0.0,
    "current_angle_deg": 0.0,
}


def _nominal():
    from carbon.motor.domain import NOMINAL

    return dict(NOMINAL)


def _membership(value, admitted_by):
    """A case's screen verdict, beside its membership read independently:
    inside the input box (`domain.check_inputs`) and buildable
    (`domain.validity`)."""
    from carbon.motor import domain

    case = value["case"]
    try:
        domain.check_inputs(case)
        in_box = True
    except ValueError:
        in_box = False
    buildable = in_box and not domain.validity(case)
    try:
        admitted = bool(admitted_by(case))
    except ValueError:
        admitted = False
    return {"admitted": admitted, "in_box": in_box, "buildable": buildable}


def screen_boundary(value):
    """The population screen (`population.admitted`): a case is a member
    only inside the input box with a buildable geometry. A case outside the
    box is refused by `domain.check_inputs` (a ValueError), typed here."""
    from carbon.motor import population

    return _membership(value, population.admitted)


def box_blind_screen(value):
    """Vulnerable specimen: every finite case admitted."""
    return _membership(value, lambda _case: True)


def screen_breached(result):
    """A member outside the input box, or with an unbuildable geometry, got
    through."""
    return result["admitted"] and not (result["in_box"] and result["buildable"])


def _screen_attacks():
    nominal = _nominal()
    return (
        ("unbuildable_slot_opening_inside_the_box", {"case": dict(UNBUILDABLE_CORNER)}),
        (
            # The benchmark machine's own density (domain.NOMINAL notes it lies
            # above this Challenge's range): deeper into saturation.
            "benchmark_nominal_current_density_beyond_the_box",
            {"case": {**nominal, "current_density_a_mm2": 20.3}},
        ),
        (
            "generating_quadrant_current_angle",
            {"case": {**nominal, "current_angle_deg": -30.0}},
        ),
        (
            "current_angle_beyond_sixty_degrees",
            {"case": {**nominal, "current_angle_deg": 90.0}},
        ),
        (
            "reversed_current_direction",
            {"case": {**nominal, "current_density_a_mm2": -5.0}},
        ),
        ("airgap_below_the_box", {"case": {**nominal, "airgap_mm": 0.1}}),
    )


def _screen_control(value):
    result = screen_boundary(value)
    return result["admitted"] and not screen_breached(result)


# practice feedback ---------------------------------------------------------------------------
def _probe(predictions, feedback=None):
    """One practice probe: Carbon's own scoring and the public feedback a
    miner receives (`practice.score_practice`, `practice.feedback`)."""
    from carbon.motor import practice

    _rows, summary = _score(predictions)
    feedback = practice.feedback if feedback is None else feedback
    return feedback(
        summary, {}, recipe=_control_recipe(), backend=PROBE_BACKEND, worker={}
    )


def _feedback_view(feedbacks, identical):
    case_ids = {r["case_id"] for r in _records()}
    return {
        "fields": sorted({k for fb in feedbacks for k in fb}),
        "summary_fields": sorted(
            {k for fb in feedbacks for k in (fb.get("summary") or {})}
        ),
        "flags": [{k: fb.get(k) for k in PRACTICE_FLAGS} for fb in feedbacks],
        "digests": [_digest(fb) for fb in feedbacks],
        "eligible": [
            bool((fb.get("summary") or {}).get("eligible")) for fb in feedbacks
        ],
        "case_detail": any(
            case in _canonical(fb) for fb in feedbacks for case in case_ids
        ),
        "identical": identical,
    }


def disclosure_boundary(value):
    feedbacks = [_probe(p) for p in value["probes"]]
    return _feedback_view(feedbacks, value.get("identical", False))


def _leaky_feedback():
    from carbon.motor import practice

    calls = []

    def leaky(summary, fit, **kwargs):
        calls.append(1)
        out = practice.feedback(summary, fit, **kwargs)
        rows = sorted(r["case_id"] for r in _records())[:3]
        return {**out, "screening": {"cases": rows}, "probe_index": len(calls)}

    return leaky


def disclosure_specimen(value):
    """Vulnerable specimen: feedback that also carries per-case detail and a
    probe counter."""
    leaky = _leaky_feedback()
    feedbacks = [_probe(p, leaky) for p in value["probes"]]
    return _feedback_view(feedbacks, value.get("identical", False))


def disclosure_breached(result):
    return (
        set(result["fields"]) != PRACTICE_FEEDBACK_FIELDS
        or not set(result["summary_fields"]) <= PRACTICE_SUMMARY_FIELDS
        or any(flags != PRACTICE_FLAGS for flags in result["flags"])
        or (result["identical"] and len(set(result["digests"])) > 1)
        or result["case_detail"]
    )


def _disclosure_attacks():
    oracle = _oracle_predictions()
    first, last = min(oracle), max(oracle)
    with_reference_fields = {
        case: {
            **p,
            "reference_outputs": "echo",
            "counted_getdp_torque_nm": p["torque_nm"],
        }
        for case, p in oracle.items()
    }
    train_keyed = {f"train-{i:04d}": p for i, p in enumerate(oracle.values()) if i < 5}
    return (
        ("repeated_identical_probes", {"probes": [oracle] * 3, "identical": True}),
        ("single_case_probe_first", {"probes": [{first: oracle[first]}]}),
        ("single_case_probe_last", {"probes": [{last: oracle[last]}]}),
        ("empty_probe", {"probes": [{}]}),
        ("probe_carrying_reference_fields", {"probes": [with_reference_fields]}),
        ("probe_keyed_by_train_cases", {"probes": [train_keyed]}),
    )


def _disclosure_control(value):
    result = disclosure_boundary(value)
    return not disclosure_breached(result) and all(result["eligible"])


# resource accounting -------------------------------------------------------------------------
def code_run_seconds():
    return CODE_RUN_SECONDS


def code_run_refusal(arguments):
    """Refused before dispatch: a code run must ask for a whole number of
    seconds between 1 and `code_run_seconds()`. Returns the refusal code, or
    None. It is the core's one code-run rule (`attack.adapter.
    code_run_refusal`) at motor's allowance, the rule the phase-4 Attacker
    dispatcher applies, and binds Carbon's Attacker lane only."""
    return _core.code_run_refusal(arguments, seconds=code_run_seconds())


def _scoring_accounting(value):
    """A prediction set scored by the rule. For a partial set, every case
    left without a prediction must be FAILED_INFRA, never a gate failure; a
    set with nothing scored is never eligible."""
    view = score_view(value["predictions"])
    return {
        "kind": "scoring",
        "partial": bool(value.get("partial")),
        "eligible": view["eligible"],
        "n_cases": view["n_cases"],
        "n_scored": view["n_scored"],
        "n_failed_infra": view["n_failed_infra"],
        "n_gate_failed": view["n_gate_failed"],
    }


def resource_boundary(value):
    if value["kind"] == "code_run":
        refusal = code_run_refusal(value["arguments"])
        return {"kind": "code_run", "dispatched": refusal is None, "refusal": refusal}
    return _scoring_accounting(value)


def resource_specimen(value):
    """Vulnerable specimen: a lifted allowance, and an aggregate that counts
    an infrastructure failure as a pass."""
    if value["kind"] == "code_run":
        return {"kind": "code_run", "dispatched": True, "refusal": None}
    result = _scoring_accounting(value)
    return {**result, "eligible": result["n_gate_failed"] == 0}


def resource_breached(result):
    if result["kind"] == "code_run":
        return result["dispatched"]
    if not result["partial"]:
        return False
    missing = result["n_cases"] - result["n_scored"]
    return (
        (result["n_scored"] == 0 and result["eligible"])
        or result["n_gate_failed"] > 0
        or result["n_failed_infra"] != missing
    )


def _half_predictions():
    """Half the cases predicted: a partial set whose missing half must be
    typed FAILED_INFRA (checked by a test; whether such a set may be eligible
    is not judged here, as for battery and cooling: `exam.aggregate` excludes
    a FAILED_INFRA case by design)."""
    oracle = _oracle_predictions()
    return {case: oracle[case] for case in sorted(oracle)[: len(oracle) // 2]}


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
    )


def _resource_control(value):
    result = resource_boundary(value)
    if result["kind"] == "code_run":
        return result["dispatched"]
    return result["eligible"] and not resource_breached(result)


def _resource_admissible(value):
    """The code-run rule judges only a run the Attacker's dispatcher handled
    (`lane` in `CODE_RUN_RULE_LANES`); any other is NOT_APPLICABLE."""
    if value.get("kind") != "code_run":
        return None
    if value.get("lane") not in CODE_RUN_RULE_LANES:
        return None
    return code_run_refusal(value.get("arguments")) is None


# construction-evaluation isolation: staged bytes ---------------------------------------------
def _labelled_practice():
    """The public PRACTICE set with a synthetic marker in every label: a
    worker staged from it must never receive one."""
    from carbon.motor.practice import PracticeSet

    practice = _practice()
    records = tuple(
        {**r, "outputs": {**r["outputs"], "label_marker": LABEL_MARKER}}
        for r in practice.records
    )
    return PracticeSet(records, practice.source_sha256)


def _staging_root(directory):
    """A repository root holding the public TRAIN bytes and, beside them, a
    synthetic marker file outside the public allow-list."""
    from carbon.motor.challenge import TRAIN_PATH

    root = Path(directory)
    target = root / TRAIN_PATH
    target.parent.mkdir(parents=True)
    shutil.copyfile(REPOSITORY / TRAIN_PATH, target)
    beside = target.parent / "beside-train-marker.jsonl"
    beside.write_text(json.dumps({"marker": FILE_MARKER}) + "\n", encoding="utf-8")
    return root, beside


def _stage(strategy, leaky=False):
    from carbon.motor import practice
    from carbon.motor.compile import compile_recipe

    _compiled, recipe = compile_recipe(strategy)
    labelled = _labelled_practice()
    with tempfile.TemporaryDirectory(prefix="motor-attack-stage-") as directory:
        root, beside = _staging_root(directory)
        files = practice.staged_files(root, labelled, recipe)
        if leaky:
            files = {
                **files,
                "practice.jsonl": labelled.public_bytes(),
                beside.name: beside.read_bytes(),
            }
    found = sorted(
        {
            marker
            for body in files.values()
            for marker in (LABEL_MARKER, FILE_MARKER)
            if marker.encode() in body
        }
    )
    return {"names": sorted(files), "found": found}


def staged_boundary(value):
    return _stage(value["strategy"])


def leaky_stager(value):
    """Vulnerable specimen: the worker also gets the labelled PRACTICE records
    and the file beside the pool."""
    return _stage(value["strategy"], leaky=True)


def staged_breached(result):
    return bool(result["found"]) or set(result["names"]) != STAGED_NAMES


# reconstruction: rebuild identity, a reported build and the delivered package ---------------
def _recipe_digest(strategy):
    from carbon.motor import compile as motor_compile

    return motor_compile.compile_recipe(strategy)[1].recipe_digest


def rebuild_identity_boundary(pair):
    a, b = pair
    return {"same": _recipe_digest(a) == _recipe_digest(b), "expect_same": False}


def family_only_digest(pair):
    """Vulnerable specimen: a recipe identity that drops the settings."""
    a, b = pair
    return {"same": a.get("backbone") == b.get("backbone"), "expect_same": False}


def rebuild_identity_breached(result):
    return result["same"] != result["expect_same"]


def _rebuild_pairs():
    base = _scaffold()
    return (
        ("length_changed", (base, _strategy(length="length_8"))),
        ("ridge_changed", (base, _strategy(ridge="ridge_1e_6"))),
        ("both_changed", (base, _strategy(length="length_16", ridge="ridge_1"))),
        (
            "neighbouring_grid_points",
            (_strategy(length="length_0p25"), _strategy(length="length_0p5")),
        ),
    )


def _rebuild_identity_control(strategy):
    """A key-reordered copy of a valid strategy is the same recipe."""
    reordered = json.loads(json.dumps(strategy))
    reordered["parameters"] = dict(reversed(list(reordered["parameters"].items())))
    reordered = dict(reversed(list(reordered.items())))
    return _recipe_digest(strategy) == _recipe_digest(reordered)


def _recorded_contract():
    """The motor contract in force, only if its newest expansion record pins
    it (`reconstruction.expansion_record`), as every Challenge's scoring reads
    it: construction stays inside the recorded contract, nothing wider."""
    from carbon.reconstruction import expansion_record

    history = expansion_record.records(CHALLENGE_ID)
    live = _contract().digest
    if not history or history[-1]["contract_digest"] != live:
        raise _Refused("construction_contract_unrecorded")
    return {
        "challenge": CHALLENGE_ID,
        "contract_digest": live,
        "record_sequence": history[-1]["sequence"],
    }


def carbon_build_record(strategy, seed):
    """Carbon's own build of a motor strategy: the contract gate and motor's
    compiler (`challenge_contracts.compile_submission`), motor's worker
    staging and practice program, under the newest expansion record. It
    carries every field the shared rebuild comparison reads
    (`challenge_validator.scoring.REBUILT_FIELDS`). It is not a pod record:
    no `ChallengeScoring` serves motor's pods."""
    from carbon.development_session.research_catalog import RecipeRejected
    from carbon.motor.contracts import digest
    from carbon.motor.practice import PROGRAM, staged_files
    from carbon.reconstruction.challenge_contracts import (
        SubmissionRefused,
        compile_submission,
    )

    recorded = _recorded_contract()
    try:
        admitted = compile_submission(
            strategy, contract_digest=recorded["contract_digest"]
        )
    except SubmissionRefused as refused:
        raise _Refused(
            "contract_refused", [(i.code, i.path) for i in refused.issues]
        ) from None
    except RecipeRejected as refused:
        raise _Refused(
            "recipe_rejected", [(i.code, i.path) for i in refused.rejected.issues]
        ) from None
    recipe = admitted.construction
    plan = admitted.compiled.construction_plan
    files = staged_files(REPOSITORY, _practice(), recipe)
    return {
        "schema": BUILD_SCHEMA,
        "challenge": recipe.document()["challenge"],
        "contract_digest": admitted.contract_digest,
        "recipe": recipe.document(),
        "recipe_digest": recipe.recipe_digest,
        "strategy_hash": plan.strategy_hash.value,
        "plan_digest": plan.to_ref().content_digest,
        "staged": {name: digest(body) for name, body in sorted(files.items())},
        "program": digest(PROGRAM.encode()),
        "seed": seed,
        "record_sequence": recorded["record_sequence"],
    }


@functools.lru_cache(maxsize=8)
def _expected_build_cached(strategy_json, seed, record):
    return carbon_build_record(json.loads(strategy_json), seed)


def _expected_build(strategy_json, seed):
    """Carbon's own build record, cached by the recorded contract it was
    built under, so a new contract record is never compared with a stale
    build."""
    recorded = _recorded_contract()
    record = (recorded.get("contract_digest"), recorded.get("record_sequence"))
    return copy.deepcopy(_expected_build_cached(strategy_json, seed, record))


def _rebuild_differences(expected, built):
    """The shared, Challenge-neutral comparison
    (`challenge_validator.scoring.rebuild_differences`)."""
    from carbon.challenge_validator import scoring

    return scoring.rebuild_differences(expected, built)


def _tampered(expected, field_name):
    built = copy.deepcopy(expected)
    value = built.get(field_name)
    if isinstance(value, dict):
        built[field_name] = {**value, "tampered": True}
    elif isinstance(value, bool):
        built[field_name] = not value
    elif isinstance(value, int):
        built[field_name] = value + 1
    elif isinstance(value, str):
        built[field_name] = value[:-1] + ("0" if value[-1:] != "0" else "1")
    else:
        built[field_name] = "tampered"
    return built


def rebuild_report_boundary(value):
    """Carbon's independent rebuild check on a reported build: the declared
    tamper of one field, or a build an observed session reported."""
    expected = _expected_build(_canonical(value["strategy"]), value.get("seed", 0))
    if "built" in value:
        built = value["built"]
    else:
        built = _tampered(expected, value["field"])
    return {
        "differences": _rebuild_differences(expected, built),
        "tampered": value.get("field"),
    }


def rebuild_report_specimen(value):
    """Vulnerable specimen: a comparison that compares nothing."""
    return {"differences": [], "tampered": value.get("field")}


def rebuild_report_breached(result):
    if result["tampered"] is None:
        return bool(result["differences"])
    return result["tampered"] not in result["differences"]


def _rebuild_report_attacks():
    strategy = _scaffold()
    return tuple(
        ("tampered_" + name, {"strategy": strategy, "seed": 7, "field": name})
        for name in TAMPER_FIELDS
    )


def _rebuild_report_control(value):
    built = _expected_build(_canonical(value["strategy"]), value.get("seed", 0))
    return not rebuild_report_breached(
        rebuild_report_boundary({**value, "built": built})
    )


#: Edits a delivery package's TRAIN bytes may carry. `none` and
#: `crlf_line_endings` are valid (a Windows checkout's line endings are
#: normalised before the digest check); every other edit must be refused.
PACKAGE_EDITS = (
    "none",
    "crlf_line_endings",
    "one_value_changed",
    "last_record_dropped",
    "last_record_repeated",
    "truncated_mid_record",
)


def _edited_train(edit):
    from carbon.motor.challenge import TRAIN_PATH

    body = (REPOSITORY / TRAIN_PATH).read_bytes().replace(b"\r\n", b"\n")
    lines = body.splitlines(keepends=True)
    if edit == "none":
        return body
    if edit == "crlf_line_endings":
        return body.replace(b"\n", b"\r\n")
    if edit == "one_value_changed":
        record = json.loads(lines[0])
        record["outputs"]["torque_nm"][0] += 0.5
        return json.dumps(record).encode() + b"\n" + b"".join(lines[1:])
    if edit == "last_record_dropped":
        return b"".join(lines[:-1])
    if edit == "last_record_repeated":
        return body + lines[-1]
    if edit == "truncated_mid_record":
        return body[: len(body) - len(lines[-1]) // 2]
    raise ValueError("unknown package edit: " + str(edit))


def _package_root(directory, edit):
    from carbon.motor.challenge import CALIBRATION_PATH, PRACTICE_PATH, TRAIN_PATH

    root = Path(directory)
    for relative in (PRACTICE_PATH, CALIBRATION_PATH):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / relative, target)
    (root / TRAIN_PATH).write_bytes(_edited_train(edit))
    return root


def package_boundary(value):
    """A recipient loads the delivered public material
    (`challenge.PublicMaterial.load`): a TRAIN file that is not its pinned
    bytes is refused (`MaterialMismatch`), so the rebuild fails closed."""
    from carbon.motor import challenge

    with tempfile.TemporaryDirectory(prefix="motor-attack-package-") as directory:
        root = _package_root(directory, value["edit"])
        try:
            challenge.PublicMaterial.load(root)
        except challenge.MaterialMismatch:
            return {"accepted": False, "edit": value["edit"]}
    return {"accepted": True, "edit": value["edit"]}


def trusting_loader(value):
    """Vulnerable specimen: a recipient that trusts the delivered bytes."""
    return {"accepted": True, "edit": value["edit"]}


def package_breached(result):
    return result["accepted"] and result["edit"] not in ("none", "crlf_line_endings")


# recipe forgery ------------------------------------------------------------------------------
def forge_boundary(forged):
    """A `MotorRecipe` comes only from `compile_recipe`, and the rebuild takes
    only a compiled one: a forged or foreign recipe is refused with a
    TypeError before anything is fitted."""
    from carbon.motor import compile as motor_compile

    fields = {
        "family": forged.get("family", "kernel_ridge"),
        "values": tuple(sorted(forged.get("settings", {}).items())),
        "supplied": frozenset(forged.get("settings", {})),
        "strategy_hash": forged.get("strategy_hash", "sha256:" + "0" * 64),
        "plan_digest": forged.get("plan_digest", "sha256:" + "0" * 64),
    }
    try:
        if forged["kind"] == "construct":
            if forged.get("token"):
                motor_compile.MotorRecipe(**fields, token=object())
            else:
                motor_compile.MotorRecipe(**fields)
        else:
            motor_compile.rebuild(dict(fields), material=object())
    except TypeError:
        return {"accepted": False}
    return {"accepted": True}


def unsealed_recipe(_forged):
    """Vulnerable specimen: a recipe type anyone may construct."""
    return {"accepted": True}


def _forged_inputs():
    settings = {"length": 4.0, "ridge": 1e-4}
    return (
        ("raw_recipe_without_token", {"kind": "construct", "settings": settings}),
        (
            "recipe_with_a_made_up_token",
            {"kind": "construct", "settings": settings, "token": True},
        ),
        (
            "off_grid_settings_without_token",
            {"kind": "construct", "settings": {"length": 3.0, "ridge": 0.0}},
        ),
        ("mapping_handed_to_the_rebuild", {"kind": "rebuild", "settings": settings}),
    )


def _forge_control(strategy):
    from carbon.motor import compile as motor_compile

    _, recipe = motor_compile.compile_recipe(strategy)
    return type(recipe) is motor_compile.MotorRecipe


# the construction gate -----------------------------------------------------------------------
def gate(strategy):
    """The miner path's Level 0 admission: the motor construction contract,
    then the compiler (`challenge_contracts.compile_submission`). Only the
    gate's own typed refusals read as REFUSED; anything else propagates, so a
    crash in Carbon's own gate is never read as a hold."""
    from carbon.development_session.research_catalog import RecipeRejected
    from carbon.reconstruction import challenge_contracts

    try:
        admitted = challenge_contracts.compile_submission(strategy)
    except challenge_contracts.SubmissionRefused as refused:
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
    """One item through the real gate under the Level 0 profile: a withheld
    permission must come back REFUSED."""
    outcome = gate(item["strategy"])
    return {
        "status": outcome["status"],
        "expected_refusal": item["expected_refusal"],
        "codes": outcome.get("codes", []),
    }


def ablation_specimen(item):
    """Vulnerable specimen: a gate that does not enforce the profile."""
    return {"status": "OK", "expected_refusal": item["expected_refusal"]}


def ablation_breached(result):
    return result["expected_refusal"] and result["status"] == "OK"


def _ablation_attacks():
    withheld = _capability_index()[3]
    items = [
        (
            "withheld_" + capability_id,
            _ablation_item(_withheld_strategy(capability_id), capability_id),
        )
        for capability_id in withheld
    ]
    combined = _strategy(length="length_8", loss_expressions=True)
    items.append(
        (
            "combined_length_and_loss_expressions",
            _ablation_item(combined, "combined"),
        )
    )
    return tuple(items)


def recipe_boundary(strategy):
    outcome = gate(strategy)
    return {"accepted": outcome["status"] == "OK", "codes": outcome.get("codes", [])}


def unchecked_compiler(_strategy):
    """Vulnerable specimen: a compiler that checks nothing."""
    return {"accepted": True, "codes": []}


def _recipe_attacks():
    scaffold = _scaffold()
    return (
        ("unknown_weights_field", _strategy(weights="pretrained.npz")),
        ("undeclared_iron_curve_parameter", _strategy(iron_bh_curve="linear")),
        ("undeclared_skew_angle_parameter", _strategy(skew_deg=7.5)),
        ("off_grid_length", _strategy(length="length_3")),
        ("numeric_length_instead_of_a_grid_token", _strategy(length=4.0)),
        ("nonfinite_ridge", _strategy(ridge=math.nan)),
        ("top_level_loader", {**scaffold, "loader": "pickle"}),
        ("top_level_dependencies", {**scaffold, "dependencies": ["torch"]}),
        ("strategy_as_json_text", json.dumps(scaffold)),
        ("parameters_as_a_list", {**scaffold, "parameters": [["length", "length_4"]]}),
        ("future_schema_version", {**scaffold, "schema_version": "2.0"}),
        (
            # Battery registers no kernel-ridge family. Cooling would admit this
            # exact recipe as its own (the same grid tokens), which is no
            # breach: the gate compiles a recipe under the Challenge it names.
            "another_challenges_id",
            {**scaffold, "challenge_id": "battery-fastcharge-ageing-development-v1"},
        ),
        (
            "unregistered_motor_version_id",
            {**scaffold, "challenge_id": CHALLENGE_ID + "-v2"},
        ),
        ("family_outside_the_contract", {**scaffold, "backbone": "transolver"}),
    )


def build(construction, seed=0):
    """Carbon's typed rebuild of a construction (`carbon_build_record`).
    `construction` is a strategy, or `{"strategy": ..., "seed": ...}`.
    Anything Carbon cannot rebuild carries a code from `REFUSAL_CODES`."""
    from carbon.agent_campaign.graphite import experiment
    from carbon.motor.challenge import MaterialMismatch

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
        size = len(json.dumps(strategy, allow_nan=False).encode())
    except (TypeError, ValueError):
        return refused("strategy_not_json")
    if size > experiment.MAX_STRATEGY_BYTES:
        return refused("strategy_too_large")
    if type(strategy) is not dict:
        return refused("strategy_not_an_object")
    if strategy.get("challenge_id") != CHALLENGE_ID:
        return refused("not_the_motor_development_challenge")
    try:
        record = carbon_build_record(strategy, seed)
    except _Refused as error:
        return refused(error.code, error.issues)
    except MaterialMismatch:
        return refused("public_material_mismatch")
    return Build(strategy, seed, record)


def _recipe_admissible(strategy):
    return build(strategy).rebuilt


def _ablation_admissible(item):
    strategy = item["strategy"]
    return uses(strategy) <= level0_permissions() and _recipe_admissible(strategy)


def pod_scoring_code():
    """Why Graphite's pods do not serve motor: the scoring registry's own
    refusal code, or None once a motor `ChallengeScoring` is registered."""
    from carbon.challenge_validator import scoring

    try:
        scoring.scoring_for(CHALLENGE_ID)
    except scoring.ScoringUnavailable as refused:
        return refused.code
    return None


def clear_caches():
    """Drop every cached read, for a long-lived driver that starts a new
    session."""
    _INDEX_BY_CONTRACT.clear()
    _expected_build_cached.cache_clear()
    _material.cache_clear()
    _practice.cache_clear()
    _control_recipe.cache_clear()


# -- the families ------------------------------------------------------------------------------
SCORE_CHECK = "score_exploitation_and_tail_failures"
_PRACTICE_READS = "public PRACTICE references, normalised by public TRAIN"


@functools.cache
def _families():
    return (
        FamilySpec(
            name="permission_ablation",
            check="baseline_and_permission_ablation",
            protocol_family="the Level 0 baseline under the live gate: every "
            "permission the motor contract withholds (a neural-operator or "
            "pretrained family, loss expressions, a learned optimizer, reusing "
            "the reference solver), alone and combined with a permitted change, "
            "must come back REFUSED",
            attacks=_ablation_attacks,
            boundary=ablation_boundary,
            specimen=ablation_specimen,
            breached=ablation_breached,
            control_check=lambda s: (
                uses(s) <= level0_permissions() and gate(s)["status"] == "OK"
            ),
            admissible=_ablation_admissible,
            attack_example="withheld_objective.loss_expressions",
            reads="the live construction contract (read only) and grid recipes",
            runnable=_ablation_admissible,
        ),
        FamilySpec(
            name="recipe_surface",
            check="artifact_and_dependency_attacks",
            protocol_family="the construction gate refuses an undeclared field "
            "(weights, an iron B-H curve, a skew angle), an off-grid or numeric "
            "choice, a nonfinite value, a top-level loader or dependency list, "
            "text instead of an object, another Challenge's id and a family "
            "outside the contract",
            attacks=_recipe_attacks,
            boundary=recipe_boundary,
            specimen=unchecked_compiler,
            breached=lambda r: r["accepted"],
            control_check=lambda s: recipe_boundary(s)["accepted"],
            admissible=_recipe_admissible,
            attack_example="undeclared_iron_curve_parameter",
            reads="recipes only",
            runnable=_recipe_admissible,
        ),
        FamilySpec(
            name="recipe_forgery",
            check="artifact_and_dependency_attacks",
            protocol_family="a motor recipe comes only from the compiler and the "
            "rebuild takes only a compiled one: a recipe built without the "
            "compiler's token, with a made-up token or as a plain mapping is "
            "refused before anything is fitted",
            attacks=_forged_inputs,
            boundary=forge_boundary,
            specimen=unsealed_recipe,
            breached=lambda r: r["accepted"],
            control_check=_forge_control,
            admissible=None,
            attack_example="raw_recipe_without_token",
            reads="recipes only",
        ),
        FamilySpec(
            name="practice_disclosure",
            check="adaptive_feedback_and_state_attacks",
            protocol_family="function-level public PRACTICE probes: repeated "
            "identical probes give identical feedback, and every probe, however "
            "shaped, gets the published allow-list only, with aggregate figures "
            "and no per-case detail",
            attacks=_disclosure_attacks,
            boundary=disclosure_boundary,
            specimen=disclosure_specimen,
            breached=disclosure_breached,
            control_check=_disclosure_control,
            admissible=None,
            attack_example="repeated_identical_probes",
            reads=_PRACTICE_READS,
        ),
        FamilySpec(
            name="mandatory_failure",
            check=SCORE_CHECK,
            protocol_family="one prediction that breaks a validity gate (a "
            "nonfinite or malformed torque curve, a curve of the wrong length, "
            "or a torque whose sign is flipped so its period mean leaves the "
            "motoring quadrant) makes the whole set ineligible; the soft score "
            "never compensates it",
            attacks=_mandatory_inputs,
            boundary=score_view,
            specimen=averaging_scorer,
            breached=mandatory_breached,
            control_check=_eligible_control,
            admissible=None,
            attack_example="torque_sign_flipped_on_every_case",
            reads=_PRACTICE_READS,
        ),
        FamilySpec(
            name="ripple_omission",
            check=SCORE_CHECK,
            protocol_family="a flat torque curve at the right period mean (the "
            "constant-torque answer) passes every gate and costs ripple error: "
            "the rule scores the ripple apart from the mean",
            attacks=_omission_attacks,
            boundary=score_view,
            specimen=mean_only_scorer,
            breached=ripple_uncharged,
            control_check=_eligible_control,
            admissible=None,
            attack_example="flat_curve_at_the_reference_mean",
            reads=_PRACTICE_READS,
        ),
        FamilySpec(
            name="ripple_phase",
            check=SCORE_CHECK,
            protocol_family="a ripple with the right values at the wrong rotor "
            "angles (shifted along the period, or the period swept the other "
            "way) costs ripple error: the rule compares the ripple angle by "
            "angle",
            attacks=_phase_attacks,
            boundary=score_view,
            specimen=phase_blind_ripple_scorer,
            breached=ripple_uncharged,
            control_check=_eligible_control,
            admissible=None,
            attack_example="ripple_shifted_a_quarter_period",
            reads=_PRACTICE_READS,
        ),
        FamilySpec(
            name="ripple_scaling",
            check=SCORE_CHECK,
            protocol_family="a ripple of the right shape at the wrong amplitude "
            "costs ripple error: the rule normalises by a fixed public TRAIN "
            "scale, never by the submission's own amplitude, so rescaling the "
            "ripple cannot game the normalised error",
            attacks=_scaling_attacks,
            boundary=score_view,
            specimen=shape_normalised_ripple_scorer,
            breached=ripple_uncharged,
            control_check=_eligible_control,
            admissible=None,
            attack_example="ripple_halved_shape_kept",
            reads=_PRACTICE_READS,
        ),
        FamilySpec(
            name="saturation_optimism",
            check=SCORE_CHECK,
            protocol_family="saturation-blind linear iron: a period-mean torque "
            "that grows with the current where saturation acts (more torque than "
            "the reference, every gate passed) scores worse than the exact "
            "references, and over-prediction on the important group is reported "
            "as a positive mean-torque bias",
            attacks=_saturation_attacks,
            boundary=score_view,
            specimen=signed_torque_scorer,
            breached=saturation_breached,
            control_check=_saturation_control,
            admissible=None,
            attack_example="important_mean_linear_in_current",
            reads=_PRACTICE_READS,
        ),
        FamilySpec(
            name="population_screen",
            check=SCORE_CHECK,
            protocol_family="a case outside the input box (a current density "
            "beyond the range, a generating-quadrant or over-advanced current "
            "angle, a reversed current, an airgap below the box) or with an "
            "unbuildable geometry is never a member of the population that "
            "cases are drawn from",
            attacks=_screen_attacks,
            boundary=screen_boundary,
            specimen=box_blind_screen,
            breached=screen_breached,
            control_check=_screen_control,
            admissible=None,
            attack_example="generating_quadrant_current_angle",
            reads="public input box, geometry rule and PRACTICE inputs",
        ),
        FamilySpec(
            name="resource_accounting",
            check="resource_and_failure_accounting",
            protocol_family="the Attacker code-run rule this adapter defines: a "
            "wall allowance above code_run_seconds is refused before dispatch; "
            "and the rule types every case a partial prediction set leaves out "
            "as FAILED_INFRA, never a gate failure, and a set with nothing "
            "scored is never eligible",
            attacks=_resource_attacks,
            boundary=resource_boundary,
            specimen=resource_specimen,
            breached=resource_breached,
            control_check=_resource_control,
            admissible=_resource_admissible,
            attack_example="seconds_just_over_the_allowance",
            reads=_PRACTICE_READS,
        ),
        FamilySpec(
            name="staged_bytes",
            check="construction_evaluation_isolation",
            protocol_family="a practice worker is staged with Carbon's recipe "
            "modules, the public TRAIN bytes, the PRACTICE inputs and the "
            "compiled recipe only: never a PRACTICE label, and never a file "
            "lying beside the public pool",
            attacks=lambda: (
                (
                    "stage_with_labels_and_a_file_beside_the_pool",
                    {"strategy": _scaffold()},
                ),
                (
                    "stage_another_grid_point_with_labels_present",
                    {"strategy": _strategy(length="length_1", ridge="ridge_1e_8")},
                ),
            ),
            boundary=staged_boundary,
            specimen=leaky_stager,
            breached=staged_breached,
            control_check=lambda v: not staged_breached(staged_boundary(v)),
            admissible=None,
            attack_example="stage_with_labels_and_a_file_beside_the_pool",
            reads="synthetic markers and public material",
        ),
        FamilySpec(
            name="rebuild_identity",
            check="reconstruction_and_recipient_rebuild",
            protocol_family="two recipes that differ in any registered choice "
            "have different recipe digests, and a key-reordered copy is the same "
            "recipe",
            attacks=_rebuild_pairs,
            boundary=rebuild_identity_boundary,
            specimen=family_only_digest,
            breached=rebuild_identity_breached,
            control_check=_rebuild_identity_control,
            admissible=None,
            attack_example="length_changed",
            reads="recipes only",
        ),
        FamilySpec(
            name="rebuild_report",
            check="reconstruction_and_recipient_rebuild",
            protocol_family="a reported build that differs from Carbon's own "
            "build record in any rebuilt field is detected by the shared "
            "rebuild comparison",
            attacks=_rebuild_report_attacks,
            boundary=rebuild_report_boundary,
            specimen=rebuild_report_specimen,
            breached=rebuild_report_breached,
            control_check=_rebuild_report_control,
            admissible=None,
            attack_example="tampered_recipe_digest",
            reads="recipes and public material",
        ),
        FamilySpec(
            name="package_integrity",
            check="reconstruction_and_recipient_rebuild",
            protocol_family="a delivery package whose public TRAIN bytes were "
            "changed, cut short, extended or truncated is refused by the "
            "recipient's digest check, so the rebuild fails closed",
            attacks=lambda: tuple((edit, {"edit": edit}) for edit in PACKAGE_EDITS[2:]),
            boundary=package_boundary,
            specimen=trusting_loader,
            breached=package_breached,
            control_check=lambda v: package_boundary(v)["accepted"],
            admissible=None,
            attack_example="one_value_changed",
            reads="public TRAIN, PRACTICE and calibration bytes",
        ),
    )


@functools.cache
def _controls():
    oracle = _oracle_predictions
    out = []

    def add(family, split, label, make):
        out.append(ControlSpec(family, split, label, make))

    add("permission_ablation", "trained", "scaffold", _scaffold)
    add(
        "permission_ablation",
        "held_out",
        "length_8_ridge_1e_6",
        lambda: _strategy(length="length_8", ridge="ridge_1e_6"),
    )
    add(
        "permission_ablation",
        "held_out",
        "registered_defaults",
        lambda: {**_scaffold(), "parameters": {}},
    )
    for family in ("recipe_surface", "recipe_forgery", "rebuild_identity"):
        add(family, "trained", "scaffold", _scaffold)
        add(
            family,
            "held_out",
            "length_16_ridge_1",
            lambda: _strategy(length="length_16", ridge="ridge_1"),
        )
        add(
            family,
            "held_out",
            "length_0p5_ridge_1e_2",
            lambda: _strategy(length="length_0p5", ridge="ridge_1e_2"),
        )
    add("practice_disclosure", "trained", "exact_probe", lambda: {"probes": [oracle()]})
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
    for family in (
        "mandatory_failure",
        "ripple_omission",
        "ripple_phase",
        "ripple_scaling",
    ):
        add(family, "trained", "exact_predictions", lambda: {"predictions": oracle()})
        add(
            family,
            "held_out",
            "float32_predictions",
            lambda: {"predictions": _single_precision(oracle())},
        )
        add(
            family,
            "held_out",
            "rounded_six_decimals_predictions",
            lambda: {"predictions": _rounded(oracle())},
        )
    add(
        "saturation_optimism",
        "trained",
        "exact_predictions",
        lambda: {"predictions": oracle()},
    )
    add(
        "saturation_optimism",
        "held_out",
        "conservative_mean_two_percent_low",
        lambda: {"predictions": _mean_scaled(lambda _c: 0.98)},
    )
    add(
        "saturation_optimism",
        "held_out",
        "conservative_important_mean_one_percent_low",
        lambda: {"predictions": _mean_scaled(lambda _c: 0.99, "important")},
    )
    records = _records
    add(
        "population_screen",
        "trained",
        "first_practice_inputs",
        lambda: {"case": dict(records()[0]["inputs"])},
    )
    add(
        "population_screen",
        "held_out",
        "last_practice_inputs",
        lambda: {"case": dict(records()[-1]["inputs"])},
    )
    add(
        "population_screen",
        "held_out",
        "benchmark_nominal_design",
        lambda: {"case": _nominal()},
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
    add("staged_bytes", "trained", "scaffold", lambda: {"strategy": _scaffold()})
    add(
        "staged_bytes",
        "held_out",
        "length_2_ridge_1e_1",
        lambda: {"strategy": _strategy(length="length_2", ridge="ridge_1e_1")},
    )
    add(
        "rebuild_report",
        "trained",
        "scaffold_seed_7",
        lambda: {"strategy": _scaffold(), "seed": 7},
    )
    add(
        "rebuild_report",
        "held_out",
        "length_8_seed_11",
        lambda: {"strategy": _strategy(length="length_8"), "seed": 11},
    )
    add("package_integrity", "trained", "pinned_bytes", lambda: {"edit": "none"})
    add(
        "package_integrity",
        "held_out",
        "crlf_line_endings",
        lambda: {"edit": "crlf_line_endings"},
    )
    return tuple(out)


#: What needs participant code: Level 0 does not permit it, and executing
#: hostile code needs the security owner's isolation decision, which is
#: reserved.
_PARTICIPANT_CODE = (
    "needs participant code, which Level 0 does not permit; executing hostile "
    "code needs the security owner's isolation decision, which is reserved"
)
SEAMS = (
    SeamSpec(
        "fresh_cases_rerun",
        "fresh_attack_confirmation",
        0,
        "re-running found attacks needs a fresh motor case set held by the "
        "evaluator custodian; none exists (the admission study pins its "
        "population as None and its attack budget as None)",
        "owner: the size and sampling law of motor's fresh evaluator-held case "
        "set, and the attack budget",
    ),
    SeamSpec(
        "pod_scoring_not_registered",
        "reconstruction_and_recipient_rebuild",
        0,
        "no ChallengeScoring is registered for motor "
        "(challenge_validator.scoring refuses it as "
        "challenge_scoring_not_registered), so Graphite's pods do not serve it, "
        "the phase-4 runner refuses a motor run, and there is no pod build to "
        "compare with Carbon's own build record; official evaluation stays "
        "motor_validator_not_served",
        "owner: a registered motor ChallengeScoring (the separate motor "
        "validator and scoring ticket)",
    ),
    SeamSpec(
        "ripple_amplitude_bias_tolerance",
        SCORE_CHECK,
        0,
        "a flat or rescaled ripple that passes every gate is only scored, never "
        "refused: the rule penalises ripple error symmetrically and reports no "
        "signed ripple-amplitude bias, while an under-predicted ripple makes a "
        "design look feasible under a ripple limit; no record says how much "
        "missing ripple makes a set ineligible",
        "owner (science): a one-sided ripple-amplitude tolerance, or the "
        "decision that none applies",
    ),
    SeamSpec(
        "ripple_phase_tolerance",
        SCORE_CHECK,
        0,
        "a ripple at the wrong rotor angles is only scored, never refused, and "
        "no record states how far a model's angle origin may drift from the "
        "reference's",
        "owner (science): a rotor-angle phase tolerance, or the decision that "
        "none applies",
    ),
    SeamSpec(
        "saturation_bias_tolerance",
        SCORE_CHECK,
        0,
        "over-predicted torque where saturation acts that passes every gate is "
        "only scored: the exam reports the important group's signed mean-torque "
        "bias beside the score, not in it, and no record says how much promised "
        "torque makes a set ineligible; no reference outside the current range "
        "exists to judge a deeper-saturation query",
        "owner (science): a tolerance on the important group's signed mean-"
        "torque bias, or the decision that none applies",
    ),
    SeamSpec(
        "paired_repeat_gate",
        SCORE_CHECK,
        0,
        "the exam's paired_repeat gate needs a duplicated case the evaluator "
        "holds; public PRACTICE has none (the gate reads NOT_APPLICABLE), so a "
        "prediction that is not a function of its inputs is not tested here",
        "owner: the evaluator's duplicate-case design",
    ),
    SeamSpec(
        "pod_timeout_typing",
        "resource_and_failure_accounting",
        0,
        "a pod run that times out would be typed by experiment's pod outcome, "
        "while the rule types a missing prediction FAILED_INFRA; whether a pod "
        "timeout is FAILED_INFRA or CANDIDATE_FAILED is open, and motor has no "
        "pod scoring yet, so this adapter judges neither",
        "owner: whether a pod timeout is FAILED_INFRA or CANDIDATE_FAILED",
    ),
    SeamSpec(
        "practice_result_path_state",
        "adaptive_feedback_and_state_attacks",
        0,
        "repeated identical PRACTICE submissions through the stateful research "
        "task result path (get_research_result) need a running research session; "
        "practice_disclosure checks practice.feedback at function level only",
    ),
    SeamSpec(
        "level_1_physical_structure_and_objective",
        "baseline_and_permission_ablation",
        1,
        "no Level 1 proposal or expansion record exists for motor (the "
        "admission study plans physical structure and the objective at Level 1), "
        "so there is no draft permission to ablate",
    ),
    SeamSpec(
        "level_2_schedules_sampling_and_data",
        "adaptive_feedback_and_state_attacks",
        2,
        "no Level 2 proposal or expansion record exists for motor (batching, "
        "optimizer, schedule, stages and training data are planned at Level 2)",
    ),
    SeamSpec(
        "level_3_numerical_routines",
        "construction_evaluation_isolation",
        3,
        _PARTICIPANT_CODE,
        "security owner: isolation for executing participant code",
    ),
    SeamSpec(
        "level_4_hybrid_and_prediction",
        "construction_evaluation_isolation",
        4,
        "hybrids and prediction stages " + _PARTICIPANT_CODE,
        "security owner: isolation for executing participant code",
    ),
    SeamSpec(
        "level_5_custom_inference",
        SCORE_CHECK,
        5,
        "custom inference; a case a participant's own inference omits would be "
        "typed FAILED_INFRA and excluded by exam.aggregate, so it becomes a "
        "surface only here. " + _PARTICIPANT_CODE,
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
    raw = arguments.get("strategy_json")
    if raw is None:
        # A `check_design` call carries its construction in its design
        # (`attack.analysis.design_of`, the core's one reading of it).
        from carbon.agent_campaign.attack import analysis

        design = analysis.design_of(dict(arguments))
        return _MISSING if design is None else design
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


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
    """The oracle's full reading of one attempt (`assess`)."""

    family: str
    attempt: str
    reading: str
    basis: str
    observed: bool
    oracle: object

    @property
    def condition(self):
        return self.oracle.condition


class MotorLevel0Adapter:
    """Motor (`electric-motor-magnetics`) at construction Level 0, for the
    attack engine."""

    challenge_id = CHALLENGE_ID
    level = LEVEL
    version = ADAPTER_VERSION
    controls_version = CONTROLS_VERSION

    @property
    def contract_digest(self):
        return _capability_index()[4]

    # -- the core's adapter protocol ---------------------------------------------------------
    def families(self):
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
        if split not in SPLITS:
            raise ValueError("split is trained or held_out")
        return tuple(self._control(c) for c in _controls() if c.split == split)

    def oracle(self, family, attempt):
        """Carbon's verdict on one attempt (`assess`); a declared seam's is
        NOT_RUN, whatever the attempt (`attack.adapter.seam_oracle`)."""
        for seam in self.level_families():
            if seam.name == family:
                return _core.seam_oracle(seam, attempt)
        return self.assess(family, attempt).oracle

    def rebuild(self, construction):
        """Carbon's rebuild (`build`), as the core's `Rebuilt` or
        `Unrebuildable`. An unrebuildable construction is never scored. A
        rebuilt one is not served by Graphite's pods while no motor
        `ChallengeScoring` is registered (`served` False, with the registry's
        refusal code)."""
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
        refusal = pod_scoring_code()
        return Rebuilt(
            construction_digest=_digest(made.strategy),
            rebuilt_digest=_digest(made.record),
            detail={
                "record": made.record,
                "seed": made.seed,
                "served": refusal is None,
                "pod_scoring": refusal,
            },
        )

    def level_families(self):
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

    # -- the session surface ---------------------------------------------------------------
    def permission_inventory(self):
        from carbon.agent_campaign import study

        return study.permission_inventory(CHALLENGE_ID)

    def public_identity(self):
        from carbon.motor.challenge import CHALLENGE

        return {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version}

    def admission_refusals(self, strategy):
        made = build(strategy)
        if made.rebuilt:
            return []
        return [made.code] + sorted({str(code) for code, *_ in made.issues})

    def code_run_seconds(self):
        return code_run_seconds()

    def recipe_outside_contract(self):
        """A recipe motor's contract refuses (a family it does not register),
        declared here because no motor `ChallengeScoring` declares one."""
        return {**_scaffold(), "backbone": "transolver"}

    # -- motor's own reading ----------------------------------------------------------------
    def surface(self):
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

    def vectors(self):
        """The Test Lead's motor vectors, each with its check, the families
        that run it and the seam naming the owner value it still needs."""
        return copy.deepcopy(MOTOR_VECTORS)

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

    def control_passes(self, control):
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
                return "staged_bytes"
            if action == "roadmap":
                return "practice_disclosure"
            return None
        return TOOL_FAMILIES.get(name)

    def attempt_input(self, family, attempt):
        """The input an attempt carries for `family`, or `_MISSING`."""
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
        """Carbon's own reading of one attempt against `family`, by cooling's
        and battery's rule: a declared attack is BREACH when the real
        boundary's detector fires, else HELD (core HELD only when the specimen
        fired, INCONCLUSIVE otherwise); an observed attempt is BREACH when the
        path accepted what Carbon's gate refuses, WRONGFUL_REFUSAL when it
        refused what Carbon would admit and run, UNDETERMINED when its outcome
        is unknown, HELD when they agree and NOT_APPLICABLE where the family
        has no independent gate; protected material is EXPOSURE when it got
        through and PROTECTED_WITHHELD (no finding) otherwise; a boundary that
        does not answer gives the engine's own verdict."""
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
            core = HELD if verdict == FIRED else INCONCLUSIVE
            return done(HELD, basis, core, evidence, verdict, weak)

        def withheld_specimen():
            return {"specimen": "not_run", "basis": "protected material"}

        exposed = _get(attempt, "result") if not isinstance(attempt, tuple) else None
        if exposed is None and not isinstance(attempt, tuple):
            exposed = _get(attempt, "output")
        if exposed is not None and _protected(exposed):
            return done(
                EXPOSURE,
                "the attempt's result carries protected material",
                BREACHED,
                None,
                SILENT,
                withheld_specimen(),
            )
        if value is _MISSING:
            return done(NOT_APPLICABLE, "no input for this family", NOT_RUN, None)
        if _protected(value) or _protected(name):
            if observed not in (_MISSING, None) and bool(observed):
                return done(
                    EXPOSURE,
                    "the path accepted an attempt naming protected material",
                    BREACHED,
                    _digest(value),
                    SILENT,
                    withheld_specimen(),
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
                    withheld_specimen(),
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
        if runnable:
            return done(
                WRONGFUL_REFUSAL,
                "the path refused what Carbon would admit and run",
                BREACHED,
                evidence,
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
        return str(getattr(refused, "detail", "")).split(":", 1)[0]

    def rebuild_differences(self, rebuilt, built):
        return _rebuild_differences(rebuilt.detail["record"], built)

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
            input_digest=_control_input_digest(spec),
        )


_INPUT_DIGESTS = {}


def _control_input_digest(spec):
    found = _INPUT_DIGESTS.get((spec.version, spec.name))
    if found is None:
        found = _INPUT_DIGESTS[(spec.version, spec.name)] = _digest(spec.value())
    return found


ADAPTER = MotorLevel0Adapter()
