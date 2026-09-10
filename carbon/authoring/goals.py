"""Bounded goal-driven challenge authoring for supported development templates.

Compilation in this module creates a content-addressed development proposal.  It
does not register a Challenge, qualify science, authorize a network operation,
or grant scoring or payment rights.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Final

MAX_GOAL_INTAKE_BYTES: Final = 1_048_576
GOAL_AUTHORING_SCHEMA: Final = "carbon.goal-authoring-proposal/1"
GOAL_AUTHORING_PROFILE: Final = "carbon.goal-authoring.canonical-json.v1"
WORKBENCH_PACKAGE_DOMAIN: Final = b"carbon-authoring-v1\0"
PROPOSAL_DOMAIN: Final = b"carbon.goal-authoring.proposal.v1\0"

BURGERS_DYNAMICS_V1_PACKAGE_DIGEST: Final = (
    "sha256:4fa6828a38050bd34fd76019fa472bdcd141a7f788ac09103544e4de0ffcd716"
)
BURGERS_WORKBENCH_RELEASE_DIGEST: Final = (
    "sha256:7805f87c3b4745454ec9c8fa852a20de6731d8f85e1356eb5d91a708cdafa7ac"
)
BURGERS_CORRECTED_EXECUTION_FREEZE_DIGEST: Final = (
    "sha256:f6624238cb5c07fc15ce0b94477336041fb1ef879454aa2d39e0e6f53eeb2788"
)


class GoalAuthoringCode(str, Enum):
    INVALID_DOCUMENT = "goal_authoring.invalid_document"
    UNSUPPORTED_TEMPLATE = "goal_authoring.unsupported_template"
    SEMANTIC_MISMATCH = "goal_authoring.semantic_mismatch"
    DIGEST_MISMATCH = "goal_authoring.digest_mismatch"
    OUTPUT_CONFLICT = "goal_authoring.output_conflict"
    OUTPUT_UNAVAILABLE = "goal_authoring.output_unavailable"


class GoalAuthoringError(ValueError):
    """Stable, non-echoing goal-authoring failure."""

    def __init__(self, code: GoalAuthoringCode, *, path: str = "/") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code.value} at {path}")


class ProposalWriteDisposition(str, Enum):
    CREATED = "CREATED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


class GoalActivation(str, Enum):
    PRIMARY_CHALLENGE = "PRIMARY_CHALLENGE"
    PREPARED_SPECIALIST_INACTIVE = "PREPARED_SPECIALIST_INACTIVE"


@dataclass(frozen=True, slots=True)
class RationalWeight:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if (
            type(self.numerator) is not int
            or type(self.denominator) is not int
            or self.numerator <= 0
            or self.denominator <= 0
        ):
            raise GoalAuthoringError(GoalAuthoringCode.INVALID_DOCUMENT)
        reduced = Fraction(self.numerator, self.denominator)
        if (reduced.numerator, reduced.denominator) != (
            self.numerator,
            self.denominator,
        ):
            raise GoalAuthoringError(GoalAuthoringCode.INVALID_DOCUMENT)

    def record(self) -> dict[str, int]:
        return {"denominator": self.denominator, "numerator": self.numerator}


_GOAL_WEIGHTS: Final[dict[str, tuple[RationalWeight, ...]]] = {
    "Dynamics": (
        RationalWeight(1, 2),
        RationalWeight(1, 6),
        RationalWeight(1, 6),
        RationalWeight(1, 6),
    ),
    "Transport": (
        RationalWeight(4, 5),
        RationalWeight(1, 10),
        RationalWeight(1, 20),
        RationalWeight(1, 20),
    ),
    "Front Resolution": (
        RationalWeight(2, 5),
        RationalWeight(1, 2),
        RationalWeight(1, 20),
        RationalWeight(1, 20),
    ),
    "Dissipation": (
        RationalWeight(2, 5),
        RationalWeight(1, 20),
        RationalWeight(7, 20),
        RationalWeight(1, 5),
    ),
}

_GOAL_DECISIONS: Final[dict[str, str]] = {
    "Dynamics": "Predict the complete evolution while resolving compression and dissipation without sacrificing a declared regime.",
    "Transport": "Track a moving and deforming field across early, nonlinear and decay phases.",
    "Front Resolution": "Resolve future maximum compression while retaining the complete field evolution.",
    "Dissipation": "Estimate dissipation intensity and energy half-time while retaining field accuracy.",
}

_EXPECTED_TOP_LEVEL = frozenset(
    {
        "assets_rights",
        "budget",
        "challenge_id",
        "claim",
        "generator_recipe",
        "goals",
        "intended_use",
        "mandatory_physics",
        "physical_scope",
        "runtime_status",
        "sampling",
        "schema_version",
        "score_policy",
        "sponsor_type",
        "template",
        "title",
        "tolerances",
    }
)


def _fail(
    path: str, code: GoalAuthoringCode = GoalAuthoringCode.INVALID_DOCUMENT
) -> None:
    raise GoalAuthoringError(code, path=path)


def _exact_dict(value: object, path: str) -> dict[str, object]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        _fail(path)
    return dict(value)


def _closed(value: object, fields: frozenset[str], path: str) -> dict[str, object]:
    record = _exact_dict(value, path)
    if frozenset(record) != fields:
        _fail(path)
    return record


def _exact_string(value: object, path: str, *, minimum: int = 1) -> str:
    if type(value) is not str or len(value) < minimum:
        _fail(path)
    return value


def _exact_int(value: object, path: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(path)
    return value


def _finite(value: object, path: str, *, positive: bool = False) -> float:
    if type(value) is not float or not math.isfinite(value):
        _fail(path)
    if positive and value <= 0.0:
        _fail(path)
    return value


def _literal(value: object, expected: object, path: str) -> None:
    if type(value) is not type(expected) or value != expected:
        _fail(path, GoalAuthoringCode.SEMANTIC_MISMATCH)


def _canonical_json(value: object) -> bytes:
    try:
        text = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError):
        _fail("/")
    return text.encode("utf-8") + b"\n"


def _domain_digest(domain: bytes, payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(domain + payload).hexdigest()}"


def _workbench_digest(value: object) -> str:
    return _domain_digest(
        WORKBENCH_PACKAGE_DOMAIN, _canonical_json(value).rstrip(b"\n")
    )


def _validate_goal(value: object, index: int) -> str:
    path = f"/goals/{index}"
    goal = _closed(
        value,
        frozenset(
            {
                "compression_weight",
                "dissipation_weight",
                "field_weight",
                "half_time_weight",
                "intended_decision",
                "name",
            }
        ),
        path,
    )
    name = _exact_string(goal["name"], f"{path}/name")
    expected = _GOAL_WEIGHTS.get(name)
    if expected is None:
        _fail(f"{path}/name", GoalAuthoringCode.SEMANTIC_MISMATCH)
    _literal(
        goal["intended_decision"],
        _GOAL_DECISIONS[name],
        f"{path}/intended_decision",
    )
    for field, rational in zip(
        (
            "field_weight",
            "compression_weight",
            "dissipation_weight",
            "half_time_weight",
        ),
        expected,
        strict=True,
    ):
        actual = _finite(goal[field], f"{path}/{field}", positive=True)
        if not math.isclose(
            actual,
            rational.numerator / rational.denominator,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            _fail(f"{path}/{field}", GoalAuthoringCode.SEMANTIC_MISMATCH)
    return name


def _validate_sampling(value: object) -> None:
    path = "/sampling"
    sampling = _closed(
        value,
        frozenset(
            {
                "cell_mass",
                "curriculum",
                "independent_learning_builds",
                "learning_per_cell_per_build",
                "performance_per_cell",
                "reliability_per_cell",
                "roles",
            }
        ),
        path,
    )
    masses = sampling["cell_mass"]
    if type(masses) is not list or len(masses) != 12:
        _fail(f"{path}/cell_mass")
    for index, mass in enumerate(masses):
        checked = _finite(mass, f"{path}/cell_mass/{index}", positive=True)
        if not math.isclose(checked, 1.0 / 12.0, rel_tol=0.0, abs_tol=1e-15):
            _fail(
                f"{path}/cell_mass/{index}",
                GoalAuthoringCode.SEMANTIC_MISMATCH,
            )
    for field, expected in (
        ("learning_per_cell_per_build", 3),
        ("independent_learning_builds", 2),
        ("performance_per_cell", 4),
        ("reliability_per_cell", 10),
    ):
        _literal(sampling[field], expected, f"{path}/{field}")
    _literal(sampling["curriculum"], "MATCHED_FULL_SUPPORT", f"{path}/curriculum")
    _literal(sampling["roles"], "TRAIN_EVAL_STRESS_DISJOINT", f"{path}/roles")


def _validate_tolerances(value: object) -> None:
    path = "/tolerances"
    tolerances = _closed(
        value,
        frozenset(
            {
                "basis",
                "compression_relative_with_floor",
                "dissipation_relative_with_floor",
                "field_over_initial_rms",
                "half_time_over_characteristic_time",
                "origin",
                "reference_budget_fraction",
            }
        ),
        path,
    )
    _literal(tolerances["origin"], "INTERNAL_DEVELOPMENT_PROPOSAL", f"{path}/origin")
    _exact_string(tolerances["basis"], f"{path}/basis", minimum=30)
    for field, expected in (
        ("field_over_initial_rms", 0.01),
        ("compression_relative_with_floor", 0.05),
        ("dissipation_relative_with_floor", 0.05),
        ("half_time_over_characteristic_time", 0.05),
        ("reference_budget_fraction", 0.1),
    ):
        _literal(
            _finite(tolerances[field], f"{path}/{field}", positive=True),
            expected,
            f"{path}/{field}",
        )


def _validate_claim(value: object) -> None:
    path = "/claim"
    claim = _closed(
        value,
        frozenset(
            {
                "allowed_evidence",
                "exclusions",
                "maximum_failure_probability",
                "simultaneous_alpha",
                "tail_quantile",
                "target",
            }
        ),
        path,
    )
    _literal(
        claim["allowed_evidence"], "PUBLIC_DEVELOPMENT_ONLY", f"{path}/allowed_evidence"
    )
    _exact_string(claim["target"], f"{path}/target", minimum=30)
    exclusions = claim["exclusions"]
    if type(exclusions) is not list or len(exclusions) < 3:
        _fail(f"{path}/exclusions")
    for index, exclusion in enumerate(exclusions):
        _exact_string(exclusion, f"{path}/exclusions/{index}", minimum=10)
    for field, expected in (
        ("maximum_failure_probability", 0.05),
        ("simultaneous_alpha", 0.05),
        ("tail_quantile", 0.9),
    ):
        _literal(
            _finite(claim[field], f"{path}/{field}", positive=True),
            expected,
            f"{path}/{field}",
        )


def _validate_budget(value: object) -> None:
    path = "/budget"
    budget = _closed(
        value,
        frozenset(
            {
                "local_wall_seconds",
                "max_candidate_trajectories",
                "max_reference_trajectories",
                "official_evaluations",
                "provider_calls",
            }
        ),
        path,
    )
    _exact_int(
        budget["max_reference_trajectories"],
        f"{path}/max_reference_trajectories",
        minimum=240,
    )
    _exact_int(
        budget["max_candidate_trajectories"],
        f"{path}/max_candidate_trajectories",
        minimum=1,
    )
    _finite(budget["local_wall_seconds"], f"{path}/local_wall_seconds", positive=True)
    _literal(budget["provider_calls"], 0, f"{path}/provider_calls")
    _literal(budget["official_evaluations"], 0, f"{path}/official_evaluations")


def _validated_intake(value: object) -> tuple[dict[str, object], tuple[str, ...]]:
    intake = _closed(value, _EXPECTED_TOP_LEVEL, "/intake")
    literals = (
        ("schema_version", "goal-authoring/1"),
        ("sponsor_type", "INTERNAL"),
        ("assets_rights", "SYNTHETIC_INTERNAL"),
        ("template", "periodic_viscous_burgers_1d_v1"),
        (
            "physical_scope",
            "PERIODIC_UNFORCED_POSITIVE_VISCOSITY_FINITE_FOURIER_INPUT",
        ),
        ("generator_recipe", "goal_burgers_12cell_v1"),
        ("mandatory_physics", "IC_PERIODIC_MEAN_MAXIMUM_ENERGY_WEAK_PDE"),
        ("score_policy", "HALF_MEAN_HALF_WORST_CELL_CVAR_PROPOSAL"),
        ("runtime_status", "NOT_INTEGRATED_WITH_CARBON_OR_JAX"),
    )
    for field, expected in literals:
        code = (
            GoalAuthoringCode.UNSUPPORTED_TEMPLATE
            if field == "template"
            else GoalAuthoringCode.SEMANTIC_MISMATCH
        )
        if intake[field] != expected:
            _fail(f"/intake/{field}", code)
    _exact_string(intake["challenge_id"], "/intake/challenge_id")
    _exact_string(intake["title"], "/intake/title")
    _exact_string(intake["intended_use"], "/intake/intended_use", minimum=40)
    goals = intake["goals"]
    if type(goals) is not list or len(goals) != 1:
        _fail("/intake/goals", GoalAuthoringCode.SEMANTIC_MISMATCH)
    names = tuple(_validate_goal(goal, index) for index, goal in enumerate(goals))
    _validate_sampling(intake["sampling"])
    _validate_tolerances(intake["tolerances"])
    _validate_claim(intake["claim"])
    _validate_budget(intake["budget"])
    return intake, names


def _source_intake(document: object) -> tuple[dict[str, object], str, bool]:
    root = _exact_dict(document, "/")
    if "intake" not in root:
        intake, _ = _validated_intake(root)
        return intake, _workbench_digest(intake), False
    intake, _ = _validated_intake(root["intake"])
    expected_intake_digest = _workbench_digest(intake)
    if root.get("intake_digest") != expected_intake_digest:
        _fail("/intake_digest", GoalAuthoringCode.DIGEST_MISMATCH)
    claimed = root.get("package_digest")
    unsigned = dict(root)
    unsigned.pop("package_digest", None)
    if claimed != _workbench_digest(unsigned):
        _fail("/package_digest", GoalAuthoringCode.DIGEST_MISMATCH)
    return intake, claimed, True


def _goal_report(name: str) -> dict[str, object]:
    weights = _GOAL_WEIGHTS[name]
    return {
        "activation": (
            GoalActivation.PRIMARY_CHALLENGE.value
            if name == "Dynamics"
            else GoalActivation.PREPARED_SPECIALIST_INACTIVE.value
        ),
        "intended_decision": _GOAL_DECISIONS[name],
        "name": name,
        "weights": {
            field: weight.record()
            for field, weight in zip(
                ("field", "compression", "peak_dissipation", "half_time"),
                weights,
                strict=True,
            )
        },
    }


def _burgers_contract() -> dict[str, object]:
    return {
        "boundary": "PERIODIC",
        "domain": {"length": {"symbol": "2*pi"}, "space_dimensions": 1},
        "equation": "u_t + d_x(u^2/2) = nu*u_xx",
        "forcing": "NONE",
        "generator_law": {
            "amplitude": {"distribution": "UNIFORM", "maximum": 0.35, "minimum": 0.15},
            "cells": {
                "count": 12,
                "mass": {"denominator": 12, "numerator": 1},
                "shape_families": ["harmonic", "localized_packet", "multiscale"],
                "viscous_regimes": [[0.5, 1.0], [1.0, 2.0], [2.0, 4.0], [4.0, 8.0]],
            },
            "characteristic_time": "min(1/(A*k_rms),1/(nu*k_rms^2))",
            "horizon": "4*t_c",
            "initial_modes": {"first": 1, "last": 12},
            "mean_over_amplitude": {
                "distribution": "UNIFORM",
                "maximum": 1.0,
                "minimum": -1.0,
            },
            "viscosity": "A/(Re_eff*k_rms)",
        },
        "physical_scope": "SYNTHETIC_PERIODIC_VISCOUS_BURGERS_DEVELOPMENT_BENCHMARK",
        "positive_viscosity_required": True,
    }


def _measurement_proposal() -> dict[str, object]:
    return {
        "censoring": {
            "half_time": "CLIP_AT_HORIZON_AND_RETAIN_CENSOR_FLAG_AND_CROSSING_BRACKET"
        },
        "definitions": [
            {
                "id": "field_phase_rms",
                "raw_error_retained": True,
                "tolerance": {
                    "denominator": 100,
                    "numerator": 1,
                    "unit": "INITIAL_FLUCTUATION_RMS",
                },
            },
            {
                "id": "maximum_compression",
                "raw_error_retained": True,
                "tolerance": {
                    "denominator": 20,
                    "numerator": 1,
                    "unit": "max(C_ref,A*k_rms)",
                },
            },
            {
                "id": "peak_dissipation",
                "raw_error_retained": True,
                "tolerance": {
                    "denominator": 20,
                    "numerator": 1,
                    "unit": "max(D_ref,E0/t_c)",
                },
            },
            {
                "id": "energy_half_time",
                "raw_error_retained": True,
                "tolerance": {"denominator": 20, "numerator": 1, "unit": "t_c"},
            },
        ],
        "development_physics_limits": {
            "energy_balance": {"denominator": 100, "numerator": 1},
            "initial_condition": {"denominator": 1_000_000, "numerator": 1},
            "maximum_principle_excess": {"denominator": 1_000, "numerator": 1},
            "mean_conservation": {"denominator": 1_000_000, "numerator": 1},
            "weak_local_pde": {"denominator": 200, "numerator": 1},
        },
        "extrema_rule": "FOURFOLD_PERIODIC_TRIGONOMETRIC_INTERPOLATION_OF_DERIVATIVE",
        "mandatory_physics": [
            "INITIAL_CONDITION",
            "PERIODICITY",
            "CONSERVED_MEAN",
            "MAXIMUM_PRINCIPLE",
            "ENERGY_DISSIPATION_BALANCE",
            "WEAK_LOCAL_PDE",
        ],
        "numerical_uncertainty_policy": "UNRESOLVED_OR_INDETERMINATE_IS_EVALUATOR_FAILURE_NOT_STRATEGY_FAILURE",
        "phase_windows": [[0, "t_c/4"], ["t_c/4", "t_c"], ["t_c", "4*t_c"]],
        "point_query_rule": "EVALUATE_PERIODIC_TRIGONOMETRIC_REPRESENTATION_AT_REQUESTED_POINTS_NO_LOW_PASS_SUBSTITUTION",
        "raw_physical_defects_retained": True,
        "raw_uncertainty_components_retained": True,
        "uncertainty_gate": {
            "fail": "defect-uncertainty>limit",
            "indeterminate": "otherwise",
            "pass": "defect+uncertainty<=limit",
        },
    }


def compile_goal_intake(document: object) -> CompiledGoalProposal:
    """Compile one supported intake or verified workbench package."""

    intake, source_document_digest, packaged = _source_intake(document)
    _, names = _validated_intake(intake)
    source_goal = names[0]
    payload: dict[str, object] = {
        "canonicalization_profile": GOAL_AUTHORING_PROFILE,
        "capabilities": {
            "archive_acknowledged": False,
            "network_authorized": False,
            "payout_authorized": False,
            "registered": False,
            "scientifically_qualified": False,
        },
        "challenge": {
            "challenge_id": "burgers-dynamics-v1",
            "competition_count": 1,
            "primary_goal": "Dynamics",
            "title": "Burgers Dynamics V1",
        },
        "evidence_boundary": {
            "allowed_role": "PUBLIC_DEVELOPMENT_ONLY",
            "corrected_execution_freeze_digest": BURGERS_CORRECTED_EXECUTION_FREEZE_DIGEST,
            "protected_evaluation_eligible": False,
            "source_goal": source_goal,
            "template_package_digest": BURGERS_DYNAMICS_V1_PACKAGE_DIGEST,
            "workbench_release_digest": BURGERS_WORKBENCH_RELEASE_DIGEST,
        },
        "goal_reports": [_goal_report(name) for name in _GOAL_WEIGHTS],
        "measurement_proposal": _measurement_proposal(),
        "owner_bindings": {
            "case_identity": "carbon.authoring.CanonicalChallengeCaseRef",
            "challenge_registration": "carbon.registry",
            "construction_reconstruction": "carbon.construction",
            "generator": "carbon.generators",
            "measurement": "carbon.measurement.MeasurementContractRef",
            "reference_qualification": "D-03/D-04",
            "sampling": "carbon.authoring.SamplingPlanRef",
            "scoring": "carbon.measurement.ScorePackAuthoringContractRef",
            "seeding": "carbon.seeding",
        },
        "physical_contract": _burgers_contract(),
        "plans": {
            "EVAL": {"parents_per_cell": 4, "role": "EVAL", "source": "OWNER_DERIVED"},
            "STRESS": {
                "parents_per_cell": 10,
                "role": "STRESS",
                "source": "OWNER_DERIVED",
            },
            "TRAIN": {
                "builds": 2,
                "labels": "TRAIN_ONLY",
                "parents_per_cell_per_build": 3,
                "role": "TRAIN",
                "source": "OWNER_DERIVED",
            },
        },
        "reference_candidates": [
            {
                "method": "DEALIASED_FOURIER_CONSERVATIVE_ETDRK4_WITH_EXACT_GALILEAN_MEAN",
                "role": "PRIMARY_DEVELOPMENT_CANDIDATE",
                "status": "NOT_QUALIFIED",
            },
            {
                "method": "COLE_HOPF_POSITIVE_GAUSSIAN_EXPECTATION_GAUSS_HERMITE_LOG_STABILIZED",
                "role": "INDEPENDENT_DEVELOPMENT_WITNESS",
                "status": "NOT_QUALIFIED",
            },
        ],
        "development_controls": [
            "SPECTRAL_32",
            "SPECTRAL_64",
            "SPECTRAL_128",
            "HEAT",
            "MEMORIZER",
            "KERNEL_BUILD_0",
            "KERNEL_BUILD_1",
        ],
        "schema_version": GOAL_AUTHORING_SCHEMA,
        "score_proposal": {
            "eligibility_order": "MANDATORY_PHYSICS_BEFORE_QUALITY",
            "performance": "POPULATION_WEIGHTED_MEAN_CASE_LOSS",
            "quality_component_order": [
                "field",
                "compression",
                "peak_dissipation",
                "half_time",
            ],
            "ranking": {
                "performance_weight": {"denominator": 2, "numerator": 1},
                "reliability_weight": {"denominator": 2, "numerator": 1},
            },
            "reliability": "MAXIMUM_CELL_EMPIRICAL_CVAR_90_WITH_FRACTIONAL_TAIL_MASS",
            "status": "NEW_DEVELOPMENT_SCORE_PROPOSAL_NOT_A5_ACTIVATION",
        },
        "source": {
            "document_kind": (
                "VERIFIED_WORKBENCH_PACKAGE" if packaged else "RAW_INTAKE"
            ),
            "intake_digest": _workbench_digest(intake),
            "package_digest": source_document_digest if packaged else None,
        },
        "status": "DEVELOPMENT_PROPOSAL",
        "training_adapter": {
            "candidate_payload_allow_list": [
                "initial_field",
                "viscosity",
                "requested_times",
                "domain_length",
            ],
            "jax_source_status": "UNAVAILABLE",
            "label_access": "TRAIN_ONLY",
            "required_backend_interface": [
                "fit_train_arrays",
                "freeze_artifact",
                "infer_requested_points",
            ],
        },
        "unresolved_inputs": [
            "AUTHORIZED_ACTUAL_JAX_SOURCE_REVISION_AND_API",
            "QUALIFIED_REFERENCE_AND_MEASUREMENT_ERROR_BUDGETS",
            "PRODUCTION_CUSTODY_RETENTION_AND_ARCHIVE_ACKNOWLEDGEMENT",
            "REPRESENTATIVE_RESOURCE_AND_PRECISION_CALIBRATION",
            "PROTECTED_EVALUATOR_SEED_COMMITMENTS_AND_ACCESS_CONTROL",
        ],
    }
    canonical = _canonical_json(payload)
    return CompiledGoalProposal(canonical, _domain_digest(PROPOSAL_DOMAIN, canonical))


@dataclass(frozen=True, slots=True)
class CompiledGoalProposal:
    canonical_bytes: bytes
    content_digest: str

    def __post_init__(self) -> None:
        if (
            type(self.canonical_bytes) is not bytes
            or type(self.content_digest) is not str
        ):
            _fail("/")
        if _domain_digest(PROPOSAL_DOMAIN, self.canonical_bytes) != self.content_digest:
            _fail("/content_digest", GoalAuthoringCode.DIGEST_MISMATCH)

    def document(self) -> dict[str, object]:
        value = json.loads(self.canonical_bytes)
        return _exact_dict(value, "/")


def load_goal_document(path: Path) -> object:
    """Read one bounded JSON input without accepting duplicate keys."""

    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise GoalAuthoringError(GoalAuthoringCode.INVALID_DOCUMENT) from exc
    if len(payload) > MAX_GOAL_INTAKE_BYTES:
        _fail("/")

    def pairs(values: list[tuple[str, object]]) -> Mapping[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                _fail("/")
            result[key] = value
        return result

    try:
        return json.loads(
            payload,
            object_pairs_hook=pairs,
            parse_constant=lambda value: _fail("/"),
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("/")


def _write_exact(path: Path, payload: bytes) -> ProposalWriteDisposition:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise GoalAuthoringError(GoalAuthoringCode.OUTPUT_UNAVAILABLE) from exc
        if existing != payload:
            _fail("/output", GoalAuthoringCode.OUTPUT_CONFLICT)
        return ProposalWriteDisposition.ALREADY_PRESENT
    except OSError as exc:
        raise GoalAuthoringError(GoalAuthoringCode.OUTPUT_UNAVAILABLE) from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise GoalAuthoringError(GoalAuthoringCode.OUTPUT_UNAVAILABLE) from exc
    return ProposalWriteDisposition.CREATED


def write_compiled_proposal(
    output_directory: Path, proposal: CompiledGoalProposal
) -> ProposalWriteDisposition:
    """Write content-addressed bytes and a stable alias, converging exact replay."""

    if (
        not isinstance(output_directory, Path)
        or type(proposal) is not CompiledGoalProposal
    ):
        _fail("/output")
    try:
        output_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if output_directory.is_symlink() or not output_directory.is_dir():
            _fail("/output", GoalAuthoringCode.OUTPUT_UNAVAILABLE)
        objects = output_directory / "objects"
        objects.mkdir(mode=0o700, exist_ok=True)
        if objects.is_symlink() or not objects.is_dir():
            _fail("/output", GoalAuthoringCode.OUTPUT_UNAVAILABLE)
    except OSError as exc:
        raise GoalAuthoringError(GoalAuthoringCode.OUTPUT_UNAVAILABLE) from exc
    digest_hex = proposal.content_digest.removeprefix("sha256:")
    object_disposition = _write_exact(
        objects / f"{digest_hex}.json", proposal.canonical_bytes
    )
    alias_disposition = _write_exact(
        output_directory / "proposal.json", proposal.canonical_bytes
    )
    if (
        object_disposition is ProposalWriteDisposition.ALREADY_PRESENT
        and alias_disposition is ProposalWriteDisposition.ALREADY_PRESENT
    ):
        return ProposalWriteDisposition.ALREADY_PRESENT
    return ProposalWriteDisposition.CREATED


__all__ = (
    "BURGERS_CORRECTED_EXECUTION_FREEZE_DIGEST",
    "BURGERS_DYNAMICS_V1_PACKAGE_DIGEST",
    "BURGERS_WORKBENCH_RELEASE_DIGEST",
    "GOAL_AUTHORING_PROFILE",
    "GOAL_AUTHORING_SCHEMA",
    "CompiledGoalProposal",
    "GoalActivation",
    "GoalAuthoringCode",
    "GoalAuthoringError",
    "ProposalWriteDisposition",
    "RationalWeight",
    "compile_goal_intake",
    "load_goal_document",
    "write_compiled_proposal",
)
