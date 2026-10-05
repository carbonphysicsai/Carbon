"""Cooling's Level 0 attack adapter (OWNER-GRAPHITE-ATTACKER-01; the Graphite
test wave's cooling row, OWNER-GRAPHITE-TEST-WAVE-01..03).

Cooling (`chip-cold-plate`) at construction Level 0 admits declarative recipes
only: a miner sends a kernel-ridge `TrainingStrategy` choosing a kernel length
and a ridge from the published grid, and Carbon compiles, rebuilds and scores
it with its own code. This adapter gives the Challenge-neutral attack engine
everything cooling-specific it needs at that level, in the shape of battery's
adapter (`adapters/battery.py`):

- **surface and contract**: the Level 0 permission inventory
  (`agent_campaign.study.permission_inventory`) and the live construction
  contract digest, read, never changed;
- **families**: the eight shared Track A checks
  (`challenge_readiness.admission.CHECKS`), each with attacks run against the
  real boundary, a deliberately weakened specimen that must fire (a silent
  specimen is INCONCLUSIVE, never a pass), an attack example and a valid
  control. Five families carry the Test Lead's cooling vectors
  (`COOLING_VECTORS`): false cooling optimism, a flow imbalance masked behind
  a correct mean, an under-predicted pressure drop, sacrificing the hot group
  for the representative one, and an out-of-regime Reynolds number;
- **controls**, split `trained` (the engine may see them) and `held_out` (only
  the report reads them, for the wrongful-rejection rate), versioned by
  `CONTROLS_VERSION`; every held-out control is a genuinely different valid
  input, canonically distinct from every trained one;
- **the oracle**: Carbon's own verdict on one attempt, from the real boundary
  (the construction contract gate, the cold-plate compiler, the frozen public
  PRACTICE rule through cooling's `ChallengeScoring`, the practice feedback,
  the worker staging, the population screen, the public-material digests and
  `rebuild_differences`);
- **rebuild**: `graphite.experiment.admit` with cooling's `ChallengeScoring`,
  refused with a typed code when Carbon cannot rebuild a construction, which
  is then never scored;
- **seams**: what Level 0 cannot test, and every vector that needs an owner
  value no record holds (a tolerance, a weighting, a maldistribution
  reference), declared NOT_RUN with the missing value named. No threshold is
  invented here;
- **the session surface** a Graphite session needs (`attack.adapter.
  SessionSurface`).

What it is not. Nothing here executes participant code, or reads counted CFD,
the decision study's own cases, a pool other than the public TRAIN and
PRACTICE records, or any sealed or confirmation material; the cooling
decision study's registered identities (`attack.knowledge.SEALED_IDENTITIES`)
are never named. Nothing changes the construction contract
(`carbon/reconstruction/capability_registry.py`) or the design-search code.
Every value pinned here is a copy of a cooling value, checked against its
source by a test. A held attack is evidence about the boundary it called,
nothing more; zero findings is attempted coverage, never a bound; and no
verdict here is security acceptance or scientific qualification.
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

CHALLENGE_ID = "chip-cold-plate"
LEVEL = 0
PROFILE = "level-0"
ADAPTER_VERSION = "carbon.attack.adapter.cooling-l0.v1"
CONTROLS_VERSION = "carbon.attack.controls.cooling-l0.v1"
TRACK = LEDGER_TRACK
SPLITS = _core.SPLITS
FAILING_TRIGGER, OTHER_SIGNAL = "FAILING_TRIGGER", "OTHER_SIGNAL"
REPOSITORY = Path(__file__).resolve().parents[4]

#: The oracle's own reading of an attempt (`assess`), as battery's adapter
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

# -- pinned copies of cooling values (each checked against its source by a test) --------------
#: The wall allowance one code run may ask for: cooling's practice worker
#: allowance (`carbon.cold_plate.research.PRACTICE_SECONDS`).
CODE_RUN_SECONDS = 600
#: What a miner's public practice feedback may carry
#: (`carbon.cold_plate.practice.feedback`) and its aggregate summary
#: (`carbon.cold_plate.exam.aggregate`).
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
        "important_peak_bias_k",
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
        "cold-plate-domain.py",
        "cold-plate-recipes.py",
        "train-v1.jsonl",
        "practice-inputs.json",
        "recipe.json",
    }
)
#: The laminar bound the population screen holds every case to
#: (`domain.RE_LAMINAR_MAX`, `population.SCREEN["re_max"]`). The breach test
#: reads this copy, so a screen whose bound was lifted is caught.
RE_LAMINAR_MAX = 2000.0
#: The important group's reference-peak floor (`exam.T_IMPORTANT_C`, a
#: provisional DEVELOPMENT value), used here only to choose which cases an
#: attack degrades; the frozen rule types the group itself.
T_IMPORTANT_C = 85.0
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
    "not_the_cold_plate_development_challenge": "unknown_construction",
    "seed_invalid": "unknown_construction",
    # Carbon's own records or material are not current: Carbon's side, never
    # the construction's.
    "construction_contract_unrecorded": "rebuild_failed_infra",
    "public_material_mismatch": "rebuild_failed_infra",
    "backend_not_served": "rebuild_failed_infra",
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
ATTACKER_LANE = "graphite_attacker"
CODE_RUN_RULE_LANES = frozenset({ATTACKER_LANE})
#: Synthetic markers the isolation family plants (never real material).
LABEL_MARKER = "cold-plate-attack-label-marker-v1"
FILE_MARKER = "cold-plate-attack-file-marker-v1"

#: What every vector's attack example and control read: the attack HELD at
#: the real boundary and FIRED on the vulnerable specimen; the control PASSED.
VECTOR_EXPECTED = {
    "real_boundary": "HELD",
    "vulnerable_specimen": "FIRED",
    "control": "PASSED",
}
#: The Test Lead's cooling vectors (TEST_WAVE_MATRIX.md §3, "Constructed
#: controls"): the families that run each where a registered boundary exists
#: (the first is the vector's own), its attack example and trained control,
#: and the NOT_RUN seam that names the owner value it still needs.
COOLING_VECTORS = {
    "false_cooling_optimism": {
        "check": "score_exploitation_and_tail_failures",
        "families": ("cooling_optimism", "mandatory_failure"),
        "attack": "hot_group_rise_twenty_percent_low",
        "control": "cooling_optimism_trained_exact_predictions",
        "seam": "optimism_bias_tolerance",
        "expected": VECTOR_EXPECTED,
    },
    "hidden_flow_imbalance": {
        "check": "score_exploitation_and_tail_failures",
        "families": ("flow_imbalance_masking", "recipe_surface"),
        "attack": "profile_tilted_mean_kept",
        "control": "flow_imbalance_masking_trained_exact_predictions",
        "seam": "channel_maldistribution",
        "expected": VECTOR_EXPECTED,
    },
    "under_predicted_pressure_drop": {
        "check": "score_exploitation_and_tail_failures",
        "families": ("pressure_underprediction", "mandatory_failure"),
        "attack": "every_pressure_drop_halved",
        "control": "pressure_underprediction_trained_exact_predictions",
        "seam": "pressure_bias_and_hydraulic_limit",
        "expected": VECTOR_EXPECTED,
    },
    "group_sacrifice": {
        "check": "score_exploitation_and_tail_failures",
        "families": ("group_sacrifice",),
        "attack": "hot_group_rise_twenty_percent_low_rest_exact",
        "control": "group_sacrifice_trained_exact_predictions",
        "seam": "group_weighting",
        "expected": VECTOR_EXPECTED,
    },
    "out_of_regime_reynolds": {
        "check": "score_exploitation_and_tail_failures",
        "families": ("regime_screen",),
        "attack": "box_corner_beyond_the_laminar_bound",
        "control": "regime_screen_trained_first_practice_inputs",
        "seam": "regime_applicability",
        "expected": VECTOR_EXPECTED,
    },
}


@dataclass(frozen=True)
class FamilySpec:
    """One attack family at Level 0 (battery's `FamilySpec` shape): the real
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
def _scoring():
    """Cooling's `ChallengeScoring` (CHALLENGE-AI-COOLING-07), named exactly."""
    from carbon.challenge_validator.scoring import scoring_for

    return scoring_for(CHALLENGE_ID)


@functools.cache
def _frozen_rule():
    """The frozen public PRACTICE rule, as Graphite scores with it."""
    from carbon.agent_campaign.graphite.experiment import FrozenRule

    return FrozenRule(REPOSITORY, scoring=_scoring())


def _records():
    return _frozen_rule().practice.records


def _scaffold():
    from carbon.cold_plate.research import SCAFFOLD

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
    from carbon.reconstruction.capability_registry import COLD_PLATE_CHALLENGE, contract

    return contract(COLD_PLATE_CHALLENGE)


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
    from carbon.cold_plate.compile import compile_recipe

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


# -- predictions built from the public PRACTICE references -------------------------------------
def _oracle_predictions():
    """The public PRACTICE references as predictions (exact: score 0)."""
    return {
        r["case_id"]: {
            "peak_c": r["outputs"]["peak_c"],
            "profile_c": list(r["outputs"]["profile_c"]),
            "pressure_drop_pa": r["outputs"]["pressure_drop_pa"],
        }
        for r in _records()
    }


def _inlets():
    return {r["case_id"]: r["inputs"]["inlet_c"] for r in _records()}


def _important_ids():
    """Cases whose reference peak is in the important group (`T_IMPORTANT_C`)."""
    return frozenset(
        r["case_id"] for r in _records() if r["outputs"]["peak_c"] >= T_IMPORTANT_C
    )


def _chosen(where):
    """The case ids an attack edits: `all`, `important` or `representative`."""
    every = {r["case_id"] for r in _records()}
    hot = _important_ids()
    return {"all": every, "important": hot, "representative": every - hot}[where]


def _rise_scaled(factor, where="all"):
    """Every temperature's rise above the inlet multiplied by `factor` on the
    chosen cases: below 1 is optimism (a cooler plate than the reference),
    above 1 conservatism. Gates still pass (the face stays above the inlet and
    the peak bounds the profile)."""
    out, inlets, ids = _oracle_predictions(), _inlets(), _chosen(where)
    for case in ids:
        t_in, p = inlets[case], out[case]
        p["peak_c"] = t_in + factor * (p["peak_c"] - t_in)
        p["profile_c"] = [t_in + factor * (t - t_in) for t in p["profile_c"]]
    return out


def _shifted(kelvin, where="all"):
    out, ids = _oracle_predictions(), _chosen(where)
    for case in ids:
        p = out[case]
        p["peak_c"] += kelvin
        p["profile_c"] = [t + kelvin for t in p["profile_c"]]
    return out


def _pressure_scaled(factor, where="all", base=None):
    out, ids = base or _oracle_predictions(), _chosen(where)
    for case in ids:
        out[case]["pressure_drop_pa"] *= factor
    return out


def _redistributed(fraction, where="all"):
    """Each chosen profile tilted along the flow with its segment mean kept:
    the inlet end cooler, the outlet end hotter by `fraction` of the smallest
    rise. A mean-preserving redistribution, as a flow imbalance would move
    heat between regions without changing the plate's total."""
    out, inlets, ids = _oracle_predictions(), _inlets(), _chosen(where)
    for case in ids:
        p, t_in = out[case], inlets[case]
        n = len(p["profile_c"])
        middle = (n - 1) / 2
        amplitude = fraction * (min(p["profile_c"]) - t_in)
        p["profile_c"] = [
            t + amplitude * (i - middle) / middle for i, t in enumerate(p["profile_c"])
        ]
        p["peak_c"] = max(p["peak_c"], max(p["profile_c"]))
    return out


def _reversed_profiles(where="all"):
    """Each chosen profile mirrored along the flow: the same values and mean,
    the hot end moved to the other side."""
    out, ids = _oracle_predictions(), _chosen(where)
    for case in ids:
        out[case]["profile_c"] = list(reversed(out[case]["profile_c"]))
    return out


def _corrupt(case_index, edit):
    """The exact references with one case's prediction changed by `edit`."""
    out = _oracle_predictions()
    case = sorted(out)[case_index]
    out[case] = edit(copy.deepcopy(out[case]), _inlets()[case])
    return out


# -- the frozen rule as each scoring family reads it -------------------------------------------
def _score(predictions):
    """Rows and summary from the frozen public PRACTICE rule."""
    return _frozen_rule().score(predictions)


def score_view(value):
    """The frozen rule's summary of a prediction set, with the attack's tags.
    `value` is `{"predictions": ..., ...tags}` or a bare prediction set."""
    if not (isinstance(value, Mapping) and "predictions" in value):
        value = {"predictions": value}
    _rows, s = _score(value["predictions"])
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
        "important_peak_bias_k": s["important_peak_bias_k"],
        "where": value.get("where", "all"),
    }


def _eligible_control(value):
    return score_view(value)["eligible"]


# mandatory failure: a gate failure is never compensated by score ----------------------------
def _mandatory_inputs():
    def at(index, edit):
        return _corrupt(index, edit)

    def nan_peak(p, _t):
        return {**p, "peak_c": math.nan}

    def inf_pressure(p, _t):
        return {**p, "pressure_drop_pa": math.inf}

    def short_profile(p, _t):
        return {**p, "profile_c": p["profile_c"][:-1]}

    def face_at_inlet(p, t_in):
        # Total cooling optimism: the heated face no warmer than the coolant.
        return {**p, "profile_c": [t_in] * len(p["profile_c"]), "peak_c": t_in}

    def peak_below_profile(p, _t):
        return {**p, "peak_c": max(p["profile_c"]) - 1.0}

    def zero_pressure(p, _t):
        return {**p, "pressure_drop_pa": 0.0}

    def negative_pressure(p, _t):
        return {**p, "pressure_drop_pa": -p["pressure_drop_pa"]}

    def boolean_peak(p, _t):
        return {**p, "peak_c": True}

    def string_pressure(p, _t):
        return {**p, "pressure_drop_pa": str(p["pressure_drop_pa"])}

    def missing_profile(p, _t):
        return {k: v for k, v in p.items() if k != "profile_c"}

    def scalar_profile(p, _t):
        return {**p, "profile_c": p["profile_c"][0]}

    def list_peak(p, _t):
        return {**p, "peak_c": [p["peak_c"]]}

    hot = sorted(_important_ids())
    hot_index = sorted(_oracle_predictions()).index(hot[0])
    return (
        ("nan_peak", at(0, nan_peak)),
        ("infinite_pressure_drop", at(1, inf_pressure)),
        ("short_profile", at(2, short_profile)),
        ("face_at_inlet_on_a_hot_case", at(hot_index, face_at_inlet)),
        ("peak_below_profile", at(3, peak_below_profile)),
        ("zero_pressure_drop", at(4, zero_pressure)),
        ("negative_pressure_drop", at(5, negative_pressure)),
        ("boolean_peak", at(6, boolean_peak)),
        ("string_pressure_drop", at(7, string_pressure)),
        ("missing_profile", at(8, missing_profile)),
        ("scalar_profile", at(9, scalar_profile)),
        ("list_peak", at(10, list_peak)),
    )


def mandatory_breached(result):
    """Every attack set carries one gate failure: any eligible result, or one
    that counts no gate failure, compensated it."""
    return result["eligible"] or result["n_gate_failed"] == 0


def averaging_scorer(value):
    """Vulnerable specimen: eligibility by the soft score alone, gates ignored."""
    view = score_view(value)
    return {**view, "eligible": view["n_scored"] > 0, "n_gate_failed": 0}


# false cooling optimism ----------------------------------------------------------------------
def _optimism_attacks():
    return (
        (
            "every_rise_ten_percent_low",
            {"predictions": _rise_scaled(0.9), "where": "all"},
        ),
        (
            "hot_group_rise_twenty_percent_low",
            {"predictions": _rise_scaled(0.8, "important"), "where": "important"},
        ),
        (
            "representative_rise_ten_percent_low",
            {
                "predictions": _rise_scaled(0.9, "representative"),
                "where": "representative",
            },
        ),
        (
            "every_case_one_kelvin_cool",
            {"predictions": _shifted(-1.0), "where": "all"},
        ),
    )


def optimism_breached(result):
    """An optimistic set (cooler than the reference, every gate passed) must
    score worse than the exact references (score above 0), and, where it is
    optimistic on the hot group, the frozen rule must report that group's
    peak bias as negative (`important_peak_bias_k`)."""
    if not result["eligible"]:
        return False  # a gate caught it: never compensated
    score = result["score"]
    if score is None or score <= 0:
        return True
    if result["where"] in ("all", "important"):
        bias = result["important_peak_bias_k"]
        return bias is None or bias >= 0
    return False


def signed_scorer(value):
    """Vulnerable specimen: a score of the mean signed peak error, which
    rewards under-predicting temperature, with the hot group's bias dropped."""
    view = score_view(value)
    if not (isinstance(value, Mapping) and "predictions" in value):
        value = {"predictions": value}
    rows, _summary = _score(value["predictions"])
    signed = [r["peak_signed_error"] for r in rows if "peak_signed_error" in r]
    return {
        **view,
        "score": fmean(signed) if signed else None,
        "important_peak_bias_k": None,
    }


def _optimism_control(value):
    """An exact or conservative set is eligible and shows no optimism."""
    view = score_view(value)
    bias = view["important_peak_bias_k"]
    return view["eligible"] and bias is not None and bias >= 0


# a flow imbalance masked behind a correct mean -----------------------------------------------
def _imbalance_attacks():
    return (
        (
            "profile_tilted_mean_kept",
            {"predictions": _redistributed(0.3), "where": "all"},
        ),
        (
            "hot_group_profile_tilted_mean_kept",
            {"predictions": _redistributed(0.5, "important"), "where": "important"},
        ),
        (
            "profile_mirrored_along_the_flow",
            {"predictions": _reversed_profiles(), "where": "all"},
        ),
    )


def imbalance_breached(result):
    """A redistributed profile with its mean kept must still cost profile
    error: the frozen rule scores the profile segment by segment."""
    if not result["eligible"]:
        return False
    components = result["components"] or {}
    profile = components.get("profile")
    return profile is None or profile <= 0 or result["score"] <= 0


def mean_only_profile_scorer(value):
    """Vulnerable specimen: the profile graded by its segment mean alone, so a
    redistribution that keeps the mean costs nothing. Means equal to floating
    round-off read as equal (a numerical comparison, not a physics value)."""
    from carbon.cold_plate import exam

    view = score_view(value)
    if not (isinstance(value, Mapping) and "predictions" in value):
        value = {"predictions": value}
    scale = exam.scales_from_train(_frozen_rule().material.train)["s_profile"]
    errors = []
    for record in _records():
        p = value["predictions"].get(record["case_id"])
        try:
            got = fmean(p["profile_c"])
        except (TypeError, KeyError, ValueError):
            continue
        want = fmean(record["outputs"]["profile_c"])
        same = math.isclose(got, want, rel_tol=1e-12, abs_tol=1e-9)
        errors.append(0.0 if same else abs(got - want) / scale)
    components = dict(view["components"] or {})
    components["profile"] = fmean(errors) if errors else None
    return {**view, "components": components}


# an under-predicted pressure drop ------------------------------------------------------------
def _pressure_attacks():
    return (
        (
            "every_pressure_drop_halved",
            {"predictions": _pressure_scaled(0.5), "where": "all"},
        ),
        (
            "hot_group_pressure_drop_ten_percent_low",
            {"predictions": _pressure_scaled(0.9, "important"), "where": "important"},
        ),
        (
            "every_pressure_drop_a_tenth",
            {"predictions": _pressure_scaled(0.1), "where": "all"},
        ),
    )


def pressure_breached(result):
    """An under-predicted pressure drop (positive, so the gate passes) must
    cost pressure error in the frozen rule."""
    if not result["eligible"]:
        return False
    components = result["components"] or {}
    pressure = components.get("pressure")
    return pressure is None or pressure <= 0 or result["score"] <= 0


def temperature_only_scorer(value):
    """Vulnerable specimen: pressure left out of the score."""
    view = score_view(value)
    components = dict(view["components"] or {})
    components["pressure"] = 0.0
    kept = [components.get(k) for k in ("peak", "profile")]
    score = fmean(kept) if all(v is not None for v in kept) else view["score"]
    return {**view, "components": components, "score": score}


# sacrificing the hot group to favour the representative one ---------------------------------
def _group_attacks():
    return (
        (
            "hot_group_rise_twenty_percent_low_rest_exact",
            {"predictions": _rise_scaled(0.8, "important"), "where": "important"},
        ),
        (
            "hot_group_rise_quarter_high_rest_exact",
            {"predictions": _rise_scaled(1.25, "important"), "where": "important"},
        ),
        (
            "hot_group_pressure_tripled_rest_exact",
            {"predictions": _pressure_scaled(3.0, "important"), "where": "important"},
        ),
        (
            "hot_group_profile_mirrored_rest_exact",
            {"predictions": _reversed_profiles("important"), "where": "important"},
        ),
    )


def group_breached(result):
    """With the representative cases exact and the hot group degraded (every
    gate passed), the frozen rule must report the hot group apart and worse
    than the diluted overall score."""
    if not result["eligible"]:
        return False
    hot = result["important_score"]
    return (
        hot is None
        or not result["n_important"]
        or result["score"] is None
        or hot <= result["score"]
    )


def pooled_group_scorer(value):
    """Vulnerable specimen: the hot group not reported apart (its score is
    the pooled score)."""
    view = score_view(value)
    return {**view, "important_score": view["score"]}


def _group_control(value):
    view = score_view(value)
    return bool(
        view["eligible"] and view["important_score"] is not None and view["n_important"]
    )


# an out-of-regime Reynolds number ------------------------------------------------------------
#: The input-box corner with the largest closed-form Reynolds number (about
#: 2,200, above the laminar bound). A grid search of the box with the public
#: closed-form screen found no case above the laminar bound whose hottest wall
#: stays inside the coolant model, so inside the box the wall rule also
#: refuses every out-of-regime case; the attacks therefore pair this corner
#: with cases outside the box.
REGIME_CORNER_CASE = {
    "channel_width_mm": 0.5,
    "fin_width_mm": 0.5,
    "channel_depth_mm": 1.0,
    "flow_lpm_per_kw": 2.0,
    "inlet_c": 45.0,
    "heat_load_w": 1500.0,
    "hotspot_ratio": 3.0,
    "hotspot_center_mm": 3.0,
    "hotspot_width_mm": 3.5,
}


def regime_boundary(value):
    """The population screen (`population.screen`): a case is a member only
    inside the input box, with its closed-form hottest wall inside the coolant
    model and its Reynolds number laminar. A case outside the box is refused
    by `domain.check_inputs` (a ValueError), typed here."""
    from carbon.cold_plate import population

    try:
        admitted, _reasons, diagnostics = population.screen(value["case"])
    except ValueError:
        return {"admitted": False, "re_max": None, "in_box": False}
    return {
        "admitted": bool(admitted),
        "re_max": diagnostics["re_max"],
        "in_box": True,
    }


def box_only_screen(value):
    """Vulnerable specimen: membership by the input box alone."""
    from carbon.cold_plate import analytic

    try:
        re_max = analytic.predict(value["case"])["diagnostics"]["re_max"]
        in_box = True
    except ValueError:
        re_max, in_box = None, False
    return {"admitted": True, "re_max": re_max, "in_box": in_box}


def regime_breached(result):
    """A member out of the box, or above the laminar bound (`RE_LAMINAR_MAX`,
    this adapter's pinned copy), got through."""
    if not result["admitted"]:
        return False
    return (
        not result["in_box"]
        or result["re_max"] is None
        or result["re_max"] > RE_LAMINAR_MAX
    )


def _regime_attacks():
    return (
        ("box_corner_beyond_the_laminar_bound", {"case": dict(REGIME_CORNER_CASE)}),
        (
            "flow_rate_beyond_the_box",
            {"case": {**REGIME_CORNER_CASE, "flow_lpm_per_kw": 4.0}},
        ),
        (
            "channel_depth_below_the_box",
            {"case": {**REGIME_CORNER_CASE, "channel_depth_mm": 0.5}},
        ),
        (
            "coolant_inlet_beyond_the_box",
            {"case": {**REGIME_CORNER_CASE, "inlet_c": 60.0}},
        ),
    )


def _regime_control(value):
    result = regime_boundary(value)
    return result["admitted"] and not regime_breached(result)


# practice feedback ---------------------------------------------------------------------------
def _probe(predictions, feedback=None):
    """One practice probe: Carbon's own scoring and the public feedback a
    miner receives (`practice.score_practice`, `practice.feedback`)."""
    from carbon.cold_plate import practice

    rule = _frozen_rule()
    _rows, summary = practice.score_practice(predictions, rule.practice, rule.material)
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
    from carbon.cold_plate import practice

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
        case: {**p, "reference_outputs": "echo", "counted_cfd_peak_c": p["peak_c"]}
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
    None. As battery's rule, it binds Carbon's Attacker lane only."""
    if not isinstance(arguments, Mapping):
        return "code_run_arguments_unreadable"
    seconds = arguments.get("seconds")
    most = code_run_seconds()
    if type(seconds) is not int or not 1 <= seconds <= most:
        return "code_run_needs_seconds_up_to_" + str(most)
    return None


def _scoring_accounting(value):
    """A prediction set scored by the frozen rule. For a partial set, every
    case left without a prediction must be FAILED_INFRA, never a gate
    failure; a set with nothing scored is never eligible."""
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
    is not judged here, as for battery: `exam.aggregate` excludes a
    FAILED_INFRA case by design)."""
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
    from carbon.cold_plate.practice import PracticeSet

    rule = _frozen_rule()
    records = tuple(
        {**r, "outputs": {**r["outputs"], "label_marker": LABEL_MARKER}}
        for r in rule.practice.records
    )
    return PracticeSet(records, rule.practice.source_sha256)


def _staging_root(directory):
    """A repository root holding the public TRAIN bytes and, beside them, a
    synthetic marker file outside the public allow-list."""
    from carbon.cold_plate.challenge import TRAIN_PATH

    root = Path(directory)
    target = root / TRAIN_PATH
    target.parent.mkdir(parents=True)
    shutil.copyfile(REPOSITORY / TRAIN_PATH, target)
    beside = target.parent / "beside-train-marker.jsonl"
    beside.write_text(json.dumps({"marker": FILE_MARKER}) + "\n", encoding="utf-8")
    return root, beside


def _stage(strategy, leaky=False):
    from carbon.cold_plate import practice
    from carbon.cold_plate.compile import compile_recipe

    _compiled, recipe = compile_recipe(strategy)
    labelled = _labelled_practice()
    with tempfile.TemporaryDirectory(prefix="cooling-attack-stage-") as directory:
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
    from carbon.cold_plate import compile as cold_compile

    return cold_compile.compile_recipe(strategy)[1].recipe_digest


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
        ("length_changed", (base, _strategy(length="length_4"))),
        ("ridge_changed", (base, _strategy(ridge="ridge_1e_4"))),
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


@functools.lru_cache(maxsize=8)
def _expected_build_cached(strategy_json, seed, record):
    from carbon.agent_campaign.graphite import experiment

    return experiment.admit(
        json.loads(strategy_json), seed, REPOSITORY, scoring=_scoring()
    )


def _expected_build(strategy_json, seed):
    """Carbon's own admit record, cached by the recorded contract it was
    built under, so a new contract record is never compared with a stale
    build."""
    from carbon.agent_campaign.graphite import experiment

    recorded = experiment.recorded_contract(_scoring())
    record = (recorded.get("contract_digest"), recorded.get("record_sequence"))
    return copy.deepcopy(_expected_build_cached(strategy_json, seed, record))


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
    from carbon.cold_plate.challenge import TRAIN_PATH

    body = (REPOSITORY / TRAIN_PATH).read_bytes().replace(b"\r\n", b"\n")
    lines = body.splitlines(keepends=True)
    if edit == "none":
        return body
    if edit == "crlf_line_endings":
        return body.replace(b"\n", b"\r\n")
    if edit == "one_value_changed":
        record = json.loads(lines[0])
        record["outputs"]["peak_c"] += 0.5
        return json.dumps(record).encode() + b"\n" + b"".join(lines[1:])
    if edit == "last_record_dropped":
        return b"".join(lines[:-1])
    if edit == "last_record_repeated":
        return body + lines[-1]
    if edit == "truncated_mid_record":
        return body[: len(body) - len(lines[-1]) // 2]
    raise ValueError("unknown package edit: " + str(edit))


def _package_root(directory, edit):
    from carbon.cold_plate.challenge import CALIBRATION_PATH, PRACTICE_PATH, TRAIN_PATH

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
    from carbon.cold_plate import challenge

    with tempfile.TemporaryDirectory(prefix="cooling-attack-package-") as directory:
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
    """A `ColdPlateRecipe` comes only from `compile_recipe`, and the rebuild
    takes only a compiled one: a forged or foreign recipe is refused with a
    TypeError before anything is fitted."""
    from carbon.cold_plate import compile as cold_compile

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
                cold_compile.ColdPlateRecipe(**fields, token=object())
            else:
                cold_compile.ColdPlateRecipe(**fields)
        else:
            cold_compile.rebuild(dict(fields), material=object())
    except TypeError:
        return {"accepted": False}
    return {"accepted": True}


def unsealed_recipe(_forged):
    """Vulnerable specimen: a recipe type anyone may construct."""
    return {"accepted": True}


def _forged_inputs():
    settings = {"length": 8.0, "ridge": 1e-6}
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
    from carbon.cold_plate import compile as cold_compile

    _, recipe = cold_compile.compile_recipe(strategy)
    return type(recipe) is cold_compile.ColdPlateRecipe


# the construction gate -----------------------------------------------------------------------
def gate(strategy):
    """The miner path's Level 0 admission: the cooling construction contract,
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
    combined = _strategy(length="length_4", loss_expressions=True)
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
        (
            "undeclared_flow_split_parameter",
            _strategy(channel_flow_split=[0.6, 0.4]),
        ),
        ("off_grid_length", _strategy(length="length_3")),
        ("numeric_length_instead_of_a_grid_token", _strategy(length=8.0)),
        ("nonfinite_ridge", _strategy(ridge=math.nan)),
        ("top_level_loader", {**scaffold, "loader": "pickle"}),
        ("top_level_dependencies", {**scaffold, "dependencies": ["torch"]}),
        ("strategy_as_json_text", json.dumps(scaffold)),
        ("parameters_as_a_list", {**scaffold, "parameters": [["length", "length_8"]]}),
        ("future_schema_version", {**scaffold, "schema_version": "2.0"}),
        (
            "another_challenges_id",
            {**scaffold, "challenge_id": "battery-fastcharge-ageing-development-v1"},
        ),
        ("family_outside_the_contract", {**scaffold, "backbone": "transolver"}),
    )


def build(construction, seed=0):
    """Carbon's rebuild of a construction (`graphite.experiment.admit` with
    cooling's `ChallengeScoring`). `construction` is a strategy, or
    `{"strategy": ..., "seed": ...}`. Anything Carbon cannot rebuild carries
    a code from `REFUSAL_CODES`."""
    from carbon.agent_campaign.graphite import experiment
    from carbon.cold_plate.challenge import MaterialMismatch

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
    try:
        record = experiment.admit(strategy, seed, REPOSITORY, scoring=_scoring())
    except experiment.Unrebuildable as error:
        return refused(error.code, error.issues)
    except experiment.NotServed as error:
        return refused("backend_not_served", ((str(error), ""),))
    except MaterialMismatch:
        return refused("public_material_mismatch")
    return Build(strategy, seed, record)


def _recipe_admissible(strategy):
    return build(strategy).rebuilt


def _ablation_admissible(item):
    strategy = item["strategy"]
    return uses(strategy) <= level0_permissions() and _recipe_admissible(strategy)


def clear_caches():
    """Drop every cached read, for a long-lived driver that starts a new
    session."""
    _INDEX_BY_CONTRACT.clear()
    _expected_build_cached.cache_clear()
    _frozen_rule.cache_clear()
    _scoring.cache_clear()
    _control_recipe.cache_clear()


# -- the families ------------------------------------------------------------------------------
SCORE_CHECK = "score_exploitation_and_tail_failures"


@functools.cache
def _families():
    return (
        FamilySpec(
            name="permission_ablation",
            check="baseline_and_permission_ablation",
            protocol_family="the Level 0 baseline under the live gate: every "
            "permission the cooling contract withholds (a neural-operator or "
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
            "(weights, a per-channel flow split), an off-grid or numeric choice, "
            "a nonfinite value, a top-level loader or dependency list, text "
            "instead of an object, another Challenge's id and a family outside "
            "the contract",
            attacks=_recipe_attacks,
            boundary=recipe_boundary,
            specimen=unchecked_compiler,
            breached=lambda r: r["accepted"],
            control_check=lambda s: recipe_boundary(s)["accepted"],
            admissible=_recipe_admissible,
            attack_example="undeclared_flow_split_parameter",
            reads="recipes only",
            runnable=_recipe_admissible,
        ),
        FamilySpec(
            name="recipe_forgery",
            check="artifact_and_dependency_attacks",
            protocol_family="a cold-plate recipe comes only from the compiler and "
            "the rebuild takes only a compiled one: a recipe built without the "
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
            reads="public PRACTICE references",
        ),
        FamilySpec(
            name="mandatory_failure",
            check=SCORE_CHECK,
            protocol_family="one prediction that breaks a validity gate (a "
            "nonfinite or malformed output, a heated face no warmer than the "
            "inlet, a peak below its own profile, a pressure drop that is not "
            "positive) makes the whole set ineligible; the soft score never "
            "compensates it",
            attacks=_mandatory_inputs,
            boundary=score_view,
            specimen=averaging_scorer,
            breached=mandatory_breached,
            control_check=_eligible_control,
            admissible=None,
            attack_example="face_at_inlet_on_a_hot_case",
            reads="public PRACTICE references",
        ),
        FamilySpec(
            name="cooling_optimism",
            check=SCORE_CHECK,
            protocol_family="false cooling optimism: predictions cooler than the "
            "reference that pass every gate score worse than the exact "
            "references, and optimism on the hot group is reported as a "
            "negative peak bias",
            attacks=_optimism_attacks,
            boundary=score_view,
            specimen=signed_scorer,
            breached=optimism_breached,
            control_check=_optimism_control,
            admissible=None,
            attack_example="hot_group_rise_twenty_percent_low",
            reads="public PRACTICE references",
        ),
        FamilySpec(
            name="flow_imbalance_masking",
            check=SCORE_CHECK,
            protocol_family="an imbalance masked behind a correct mean: a heated-"
            "face profile redistributed along the flow with its mean kept costs "
            "profile error, segment by segment",
            attacks=_imbalance_attacks,
            boundary=score_view,
            specimen=mean_only_profile_scorer,
            breached=imbalance_breached,
            control_check=_eligible_control,
            admissible=None,
            attack_example="profile_tilted_mean_kept",
            reads="public PRACTICE references",
        ),
        FamilySpec(
            name="pressure_underprediction",
            check=SCORE_CHECK,
            protocol_family="an under-predicted pressure drop that stays positive "
            "costs pressure error in the score",
            attacks=_pressure_attacks,
            boundary=score_view,
            specimen=temperature_only_scorer,
            breached=pressure_breached,
            control_check=_eligible_control,
            admissible=None,
            attack_example="every_pressure_drop_halved",
            reads="public PRACTICE references",
        ),
        FamilySpec(
            name="group_sacrifice",
            check=SCORE_CHECK,
            protocol_family="sacrificing the hot group to favour the "
            "representative one: with the representative cases exact and the "
            "hot group degraded, the hot group's score is reported apart and "
            "worse than the pooled score",
            attacks=_group_attacks,
            boundary=score_view,
            specimen=pooled_group_scorer,
            breached=group_breached,
            control_check=_group_control,
            admissible=None,
            attack_example="hot_group_rise_twenty_percent_low_rest_exact",
            reads="public PRACTICE references",
        ),
        FamilySpec(
            name="regime_screen",
            check=SCORE_CHECK,
            protocol_family="an out-of-regime Reynolds number: a case whose "
            "closed-form Reynolds number exceeds the registered laminar bound, or "
            "that lies outside the input box, is never a member of the population "
            "that cases are drawn from",
            attacks=_regime_attacks,
            boundary=regime_boundary,
            specimen=box_only_screen,
            breached=regime_breached,
            control_check=_regime_control,
            admissible=None,
            attack_example="box_corner_beyond_the_laminar_bound",
            reads="public closed-form screen and public PRACTICE inputs",
        ),
        FamilySpec(
            name="resource_accounting",
            check="resource_and_failure_accounting",
            protocol_family="the Attacker code-run rule this adapter defines: a "
            "wall allowance above code_run_seconds is refused before dispatch; "
            "and the frozen rule types every case a partial prediction set "
            "leaves out as FAILED_INFRA, never a gate failure, and a set with "
            "nothing scored is never eligible",
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
            protocol_family="a reported build that differs from Carbon's own in "
            "any rebuilt field is detected (experiment.rebuild_differences)",
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
        "length_4_ridge_1e_4",
        lambda: _strategy(length="length_4", ridge="ridge_1e_4"),
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
    for family in ("mandatory_failure", "flow_imbalance_masking", "group_sacrifice"):
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
        "cooling_optimism",
        "trained",
        "exact_predictions",
        lambda: {"predictions": oracle()},
    )
    add(
        "cooling_optimism",
        "held_out",
        "conservative_half_kelvin",
        lambda: {"predictions": _shifted(0.5)},
    )
    add(
        "cooling_optimism",
        "held_out",
        "conservative_two_percent_rise",
        lambda: {"predictions": _rise_scaled(1.02)},
    )
    add(
        "pressure_underprediction",
        "trained",
        "exact_predictions",
        lambda: {"predictions": oracle()},
    )
    add(
        "pressure_underprediction",
        "held_out",
        "conservative_pressure_five_percent_high",
        lambda: {"predictions": _pressure_scaled(1.05)},
    )
    add(
        "pressure_underprediction",
        "held_out",
        "float32_predictions",
        lambda: {"predictions": _single_precision(oracle())},
    )
    records = _records
    add(
        "regime_screen",
        "trained",
        "first_practice_inputs",
        lambda: {"case": dict(records()[0]["inputs"])},
    )
    add(
        "regime_screen",
        "held_out",
        "last_practice_inputs",
        lambda: {"case": dict(records()[-1]["inputs"])},
    )
    add(
        "regime_screen",
        "held_out",
        "nominal_design",
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
        "length_4_seed_11",
        lambda: {"strategy": _strategy(length="length_4"), "seed": 11},
    )
    add("package_integrity", "trained", "pinned_bytes", lambda: {"edit": "none"})
    add(
        "package_integrity",
        "held_out",
        "crlf_line_endings",
        lambda: {"edit": "crlf_line_endings"},
    )
    return tuple(out)


def _nominal():
    from carbon.cold_plate.domain import NOMINAL

    return dict(NOMINAL)


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
        "re-running found attacks needs a fresh cooling case set held by the "
        "evaluator custodian; none exists (the admission study pins its "
        "population as None)",
        "owner: the size and sampling law of cooling's fresh case set",
    ),
    SeamSpec(
        "optimism_bias_tolerance",
        SCORE_CHECK,
        0,
        "false cooling optimism that passes every gate is only scored, never "
        "refused: the frozen rule reports the hot group's signed peak bias beside "
        "the score, and no record says how much optimism makes a set ineligible",
        "owner (science): a tolerance on the hot group's signed peak bias, or "
        "the decision that none applies",
    ),
    SeamSpec(
        "channel_maldistribution",
        SCORE_CHECK,
        0,
        "the registered reference solves one periodic cell, with the plate's flow "
        "shared equally by its channels (domain.derived); flow imbalance between "
        "channels or through a manifold has no reference, no predicted field and "
        "no tolerance",
        "owner (science): a multi-channel or manifold reference and a "
        "maldistribution tolerance",
    ),
    SeamSpec(
        "pressure_bias_and_hydraulic_limit",
        SCORE_CHECK,
        0,
        "the frozen rule penalises pressure error symmetrically in log space and "
        "reports no signed pressure bias; the hydraulic feasibility limit "
        "(exam.feasibility hydraulic_limit_w) is an argument with no registered "
        "value",
        "owner (science/decision): a one-sided pressure under-prediction "
        "tolerance and a registered hydraulic limit",
    ),
    SeamSpec(
        "group_weighting",
        SCORE_CHECK,
        0,
        "the frozen rule weights every PRACTICE case equally and reports the hot "
        "group apart; whether one group's error may be traded for the other's "
        "needs an evidence weighting or a group tolerance. The decision study's "
        "own case groups are not read here",
        "owner (science): an evidence weighting w(x) or a per-group tolerance",
    ),
    SeamSpec(
        "regime_applicability",
        SCORE_CHECK,
        0,
        "the laminar bound is a population membership rule for drawn cases; "
        "whether a construction must refuse or flag a query outside it "
        "(transitional or turbulent flow) has no registered applicability policy",
        "owner (science): an applicability policy for queries outside the "
        "development population",
    ),
    SeamSpec(
        "pod_timeout_typing",
        "resource_and_failure_accounting",
        0,
        "a pod run that times out is typed by experiment's pod outcome, while the "
        "frozen rule types a missing prediction FAILED_INFRA; whether a pod "
        "timeout is FAILED_INFRA or CANDIDATE_FAILED is open, so this adapter "
        "judges neither",
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
        "no Level 1 proposal or expansion record exists for cooling (the "
        "admission study plans physical structure and the objective at Level 1), "
        "so there is no draft permission to ablate",
    ),
    SeamSpec(
        "level_2_schedules_sampling_and_data",
        "adaptive_feedback_and_state_attacks",
        2,
        "no Level 2 proposal or expansion record exists for cooling",
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
        return _MISSING
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


class CoolingLevel0Adapter:
    """Cooling (`chip-cold-plate`) at construction Level 0, for the attack
    engine."""

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
            detail={"record": made.record, "seed": made.seed, "served": True},
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
        from carbon.cold_plate.challenge import CHALLENGE

        return {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version}

    def admission_refusals(self, strategy):
        made = build(strategy)
        if made.rebuilt:
            return []
        return [made.code] + sorted({str(code) for code, *_ in made.issues})

    def code_run_seconds(self):
        return code_run_seconds()

    def recipe_outside_contract(self):
        """Cooling's own dry-run refusal fixture (its `ChallengeScoring`)."""
        return _scoring().fixture_refused_strategy()

    # -- cooling's own reading ----------------------------------------------------------------
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
        """The Test Lead's cooling vectors, each with its check, the families
        that run it and the seam naming the owner value it still needs."""
        return copy.deepcopy(COOLING_VECTORS)

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
            if arguments.get("action") in CODE_ACTIONS:
                return "resource_accounting"
            if arguments.get("action") == "check_design":
                return "permission_ablation"
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
        """Carbon's own reading of one attempt against `family`, by battery's
        rule (`BatteryLevel0Adapter.assess`): a declared attack is BREACH when
        the real boundary's detector fires, else HELD (core HELD only when the
        specimen fired, INCONCLUSIVE otherwise); an observed attempt is BREACH
        when the path accepted what Carbon's gate refuses, WRONGFUL_REFUSAL
        when it refused what Carbon would admit and run, UNDETERMINED when its
        outcome is unknown, HELD when they agree and NOT_APPLICABLE where the
        family has no independent gate; protected material is EXPOSURE when
        it got through and PROTECTED_WITHHELD (no finding) otherwise; a
        boundary that does not answer gives the engine's own verdict."""
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


ADAPTER = CoolingLevel0Adapter()
