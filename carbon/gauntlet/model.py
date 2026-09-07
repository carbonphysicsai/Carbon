"""Typed, fail-closed B-E4 experiment design and observation records."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from carbon.research.refs import PriorPackRef, TestOnlyPriorAuthorizationReceiptRef

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


class AgentProfile(str, Enum):
    PLANNER = "PLANNER"
    CODE_GENERATING = "CODE_GENERATING"
    EVOLUTIONARY = "EVOLUTIONARY"
    LITERATURE_GROUNDED = "LITERATURE_GROUNDED"
    MINIMALIST = "MINIMALIST"


class ExperimentalArm(str, Enum):
    NO_PRIOR = "NO_PRIOR"
    GENERIC_PRIOR = "GENERIC_PRIOR"
    V1_DIRECTIVE_PRIOR = "V1_DIRECTIVE_PRIOR"
    V2_TEST_ONLY_PRIOR = "V2_TEST_ONLY_PRIOR"


class RatifyingOwner(str, Enum):
    RESEARCH = "RESEARCH"
    EXACT_PROTOCOL = "EXACT_PROTOCOL"
    SCIENCE = "SCIENCE"
    STATISTICS = "STATISTICS"
    SECURITY = "SECURITY"


class IntegrityCase(str, Enum):
    PROTECTED_CASE_INFERENCE = "PROTECTED_CASE_INFERENCE"
    PROTECTED_MIXTURE_INFERENCE = "PROTECTED_MIXTURE_INFERENCE"
    CHAMPION_RECONSTRUCTION = "CHAMPION_RECONSTRUCTION"
    MEMBERSHIP_INFERENCE = "MEMBERSHIP_INFERENCE"
    RELEASE_DIFFERENCING = "RELEASE_DIFFERENCING"
    NEAR_DUPLICATE_QUERY = "NEAR_DUPLICATE_QUERY"
    DUPLICATE_LINEAGE = "DUPLICATE_LINEAGE"
    REQUESTER_SPLITTING = "REQUESTER_SPLITTING"
    TIMING_RESOURCE_SURFACE = "TIMING_RESOURCE_SURFACE"
    PRIOR_POISONING = "PRIOR_POISONING"
    DUPLICATE_EVIDENCE = "DUPLICATE_EVIDENCE"
    RAW_STRING = "RAW_STRING"
    STRUCTURAL_LABEL_MISREPRESENTATION = "STRUCTURAL_LABEL_MISREPRESENTATION"
    EVIDENCE_ROLE_SUBSTITUTION = "EVIDENCE_ROLE_SUBSTITUTION"
    REFERENCE_CANDIDATE_FAILURE_COLLAPSE = "REFERENCE_CANDIDATE_FAILURE_COLLAPSE"
    PARTIAL_PROXY_SUPERIOR = "PARTIAL_PROXY_SUPERIOR"
    LEARNED_COMPONENT_WRONG_ROLE = "LEARNED_COMPONENT_WRONG_ROLE"
    LEARNED_COMPONENT_INCOMPATIBLE_IO = "LEARNED_COMPONENT_INCOMPATIBLE_IO"
    LEARNED_COMPONENT_STALE_PIN = "LEARNED_COMPONENT_STALE_PIN"
    LEARNED_COMPONENT_SIDE_EFFECT = "LEARNED_COMPONENT_SIDE_EFFECT"


class IntegrityDisposition(str, Enum):
    TYPED_REJECTION = "TYPED_REJECTION"
    TRANSFERABLE_PHYSICS = "TRANSFERABLE_PHYSICS"
    EXAM_VULNERABILITY = "EXAM_VULNERABILITY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class GauntletStatus(str, Enum):
    BLOCKED_PREREGISTRATION = "BLOCKED_PREREGISTRATION"
    ENGINEERING_READY = "ENGINEERING_READY"
    QUALIFYING_EXECUTION_RECORDED = "QUALIFYING_EXECUTION_RECORDED"


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or len(value.encode("utf-8")) > 4096:
        raise ValueError(f"{name} must be bounded non-empty text")
    return value


def _digest(value: object, name: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{name} must be a tagged SHA-256 digest")
    return value


def _finite(value: object, name: str) -> float:
    if type(value) is not float or not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be a non-negative finite float")
    return value


@dataclass(frozen=True, slots=True)
class OwnerRatification:
    owner: RatifyingOwner
    design_digest: str
    ratification_ref: str

    def __post_init__(self) -> None:
        if (
            type(self) is not OwnerRatification
            or type(self.owner) is not RatifyingOwner
        ):
            raise TypeError("ratification requires exact nominal values")
        _digest(self.design_digest, "design_digest")
        _text(self.ratification_ref, "ratification_ref")


@dataclass(frozen=True, slots=True)
class GauntletPreregistration:
    """Opaque owner-supplied design values; this class interprets none of them."""

    design_digest: str | None = None
    representative_agent_profiles: str | None = None
    matched_time_compute_budgets: str | None = None
    utility_estimand: str | None = None
    practical_effect_floor: str | None = None
    uncertainty_aware_decision_rule: str | None = None
    intervention_diversity_metric: str | None = None
    intervention_diversity_floor: str | None = None
    conditional_leakage_limit: str | None = None
    ratifications: tuple[OwnerRatification, ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self) is not GauntletPreregistration
            or type(self.ratifications) is not tuple
        ):
            raise TypeError("preregistration requires exact nominal values")
        if self.design_digest is not None:
            _digest(self.design_digest, "design_digest")
        for name in (
            "representative_agent_profiles",
            "matched_time_compute_budgets",
            "utility_estimand",
            "practical_effect_floor",
            "uncertainty_aware_decision_rule",
            "intervention_diversity_metric",
            "intervention_diversity_floor",
            "conditional_leakage_limit",
        ):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
        if any(type(item) is not OwnerRatification for item in self.ratifications):
            raise TypeError("ratifications require exact OwnerRatification values")

    @property
    def missing_inputs(self) -> tuple[str, ...]:
        missing = tuple(
            name
            for name in (
                "design_digest",
                "representative_agent_profiles",
                "matched_time_compute_budgets",
                "utility_estimand",
                "practical_effect_floor",
                "uncertainty_aware_decision_rule",
                "intervention_diversity_metric",
                "intervention_diversity_floor",
                "conditional_leakage_limit",
            )
            if getattr(self, name) is None
        )
        ratified = {item.owner for item in self.ratifications}
        missing_owners = tuple(
            f"ratification:{owner.value.lower()}"
            for owner in RatifyingOwner
            if owner not in ratified
        )
        if self.design_digest is not None and any(
            item.design_digest != self.design_digest for item in self.ratifications
        ):
            return (*missing, "ratification:exact_design_digest", *missing_owners)
        return (*missing, *missing_owners)

    @property
    def is_complete(self) -> bool:
        return not self.missing_inputs


@dataclass(frozen=True, slots=True)
class MatchedBudget:
    profile: AgentProfile
    wall_time_seconds: float
    compute_units: float
    attempt_limit: int

    def __post_init__(self) -> None:
        if type(self) is not MatchedBudget or type(self.profile) is not AgentProfile:
            raise TypeError("budget requires exact nominal values")
        _finite(self.wall_time_seconds, "wall_time_seconds")
        _finite(self.compute_units, "compute_units")
        if type(self.attempt_limit) is not int or self.attempt_limit < 1:
            raise ValueError("attempt_limit must be a positive integer")


@dataclass(frozen=True, slots=True)
class RunIdentity:
    profile: AgentProfile
    arm: ExperimentalArm
    replicate: int
    prior_pack_ref: PriorPackRef | None = None
    test_only_authorization_ref: TestOnlyPriorAuthorizationReceiptRef | None = None

    def __post_init__(self) -> None:
        if (
            type(self) is not RunIdentity
            or type(self.profile) is not AgentProfile
            or type(self.arm) is not ExperimentalArm
            or type(self.replicate) is not int
            or self.replicate < 0
        ):
            raise TypeError("run identity is invalid")
        v2 = self.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR
        if v2 != (type(self.prior_pack_ref) is PriorPackRef):
            raise ValueError("only the v2 arm requires an exact prior pack pin")
        if v2 != (
            type(self.test_only_authorization_ref)
            is TestOnlyPriorAuthorizationReceiptRef
        ):
            raise ValueError("only the v2 arm requires an exact authorization pin")


@dataclass(frozen=True, slots=True)
class EngineeringObservation:
    run: RunIdentity
    time_to_executable_strategy_seconds: float | None
    compute_to_executable_strategy: float | None
    time_to_first_practice_admissible_seconds: float | None
    attempts_to_first_practice_admissible: int | None
    best_independent_heldout_toy_result: float | None
    transfer_result: float | None
    reconstruction_success: bool
    invalid_run_count: int
    total_run_count: int
    intervention_labels: tuple[str, ...]
    transcript_digest: str

    def __post_init__(self) -> None:
        if (
            type(self) is not EngineeringObservation
            or type(self.run) is not RunIdentity
        ):
            raise TypeError("observation requires exact nominal values")
        for name in (
            "time_to_executable_strategy_seconds",
            "compute_to_executable_strategy",
            "time_to_first_practice_admissible_seconds",
            "best_independent_heldout_toy_result",
            "transfer_result",
        ):
            value = getattr(self, name)
            if value is not None:
                _finite(value, name)
        if self.attempts_to_first_practice_admissible is not None and (
            type(self.attempts_to_first_practice_admissible) is not int
            or self.attempts_to_first_practice_admissible < 1
        ):
            raise ValueError("practice attempts must be positive or absent")
        if type(self.reconstruction_success) is not bool:
            raise TypeError("reconstruction_success must be exact bool")
        if (
            type(self.invalid_run_count) is not int
            or type(self.total_run_count) is not int
            or self.invalid_run_count < 0
            or self.total_run_count < 0
            or self.invalid_run_count > self.total_run_count
        ):
            raise ValueError("run counts are invalid")
        if type(self.intervention_labels) is not tuple or any(
            type(item) is not str or not item for item in self.intervention_labels
        ):
            raise TypeError("intervention labels must be exact bounded text")
        _digest(self.transcript_digest, "transcript_digest")

    @property
    def invalid_run_rate(self) -> float | None:
        return (
            None
            if self.total_run_count == 0
            else self.invalid_run_count / self.total_run_count
        )


@dataclass(frozen=True, slots=True)
class IntegrityObservation:
    case: IntegrityCase
    disposition: IntegrityDisposition
    protocol_outcome: Enum
    fixture_only: bool = True

    def __post_init__(self) -> None:
        if (
            type(self) is not IntegrityObservation
            or type(self.case) is not IntegrityCase
            or type(self.disposition) is not IntegrityDisposition
            or not isinstance(self.protocol_outcome, Enum)
            or type(self.protocol_outcome) in (IntegrityCase, IntegrityDisposition)
            or self.fixture_only is not True
        ):
            raise TypeError("integrity observation is invalid")


@dataclass(frozen=True, slots=True)
class ConditionalLeakageObservation:
    transcript_information: float
    shadow_case_control: float
    conditional_leakage_statistic: float
    shadow_fixture_digest: str

    def __post_init__(self) -> None:
        if type(self) is not ConditionalLeakageObservation:
            raise TypeError("leakage observation subclasses are rejected")
        for name in (
            "transcript_information",
            "shadow_case_control",
            "conditional_leakage_statistic",
        ):
            _finite(getattr(self, name), name)
        _digest(self.shadow_fixture_digest, "shadow_fixture_digest")


@dataclass(frozen=True, slots=True)
class GauntletRecord:
    preregistration: GauntletPreregistration
    budgets: tuple[MatchedBudget, ...]
    observations: tuple[EngineeringObservation, ...]
    integrity_observations: tuple[IntegrityObservation, ...]
    leakage_observations: tuple[ConditionalLeakageObservation, ...]
    qualifying_execution: bool = False

    def __post_init__(self) -> None:
        if type(self) is not GauntletRecord:
            raise TypeError("gauntlet record subclasses are rejected")
        if type(self.preregistration) is not GauntletPreregistration:
            raise TypeError("exact preregistration is required")
        for values, expected in (
            (self.budgets, MatchedBudget),
            (self.observations, EngineeringObservation),
            (self.integrity_observations, IntegrityObservation),
            (self.leakage_observations, ConditionalLeakageObservation),
        ):
            if type(values) is not tuple or any(
                type(item) is not expected for item in values
            ):
                raise TypeError("gauntlet collections require exact nominal records")
        if type(self.qualifying_execution) is not bool:
            raise TypeError("qualifying_execution must be exact bool")
        if self.qualifying_execution and not self.preregistration.is_complete:
            raise ValueError(
                "qualifying execution is blocked before complete preregistration"
            )

    @property
    def status(self) -> GauntletStatus:
        if not self.preregistration.is_complete:
            return GauntletStatus.BLOCKED_PREREGISTRATION
        if self.qualifying_execution:
            return GauntletStatus.QUALIFYING_EXECUTION_RECORDED
        return GauntletStatus.ENGINEERING_READY
