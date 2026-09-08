"""Typed, fail-closed B-E4 experiment design and observation records."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from enum import Enum

from carbon.qualification.errors import DossierInputCode
from carbon.research.errors import ResearchServiceErrorCode
from carbon.research.refs import (
    PriorChannel,
    PriorPackRef,
    TestOnlyPriorAuthorizationReceiptRef,
)
from carbon.resource_policy.errors import ResourcePolicyInputCode

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


_PROTOCOL_OUTCOME_TYPES = (
    ResearchServiceErrorCode,
    ResourcePolicyInputCode,
    DossierInputCode,
)

_APPLICABLE_PROTOCOL_OUTCOMES = {
    IntegrityCase.PROTECTED_CASE_INFERENCE: frozenset(
        {
            ResearchServiceErrorCode.DISCLOSURE_REJECTED,
            ResearchServiceErrorCode.FORBIDDEN_SCIENTIFIC_CONTROL,
        }
    ),
    IntegrityCase.PROTECTED_MIXTURE_INFERENCE: frozenset(
        {
            ResearchServiceErrorCode.DISCLOSURE_REJECTED,
            ResearchServiceErrorCode.FORBIDDEN_SCIENTIFIC_CONTROL,
        }
    ),
    IntegrityCase.CHAMPION_RECONSTRUCTION: frozenset(
        {ResearchServiceErrorCode.DISCLOSURE_REJECTED}
    ),
    IntegrityCase.MEMBERSHIP_INFERENCE: frozenset(
        {ResearchServiceErrorCode.DISCLOSURE_REJECTED}
    ),
    IntegrityCase.RELEASE_DIFFERENCING: frozenset(
        {ResearchServiceErrorCode.DISCLOSURE_REJECTED}
    ),
    IntegrityCase.NEAR_DUPLICATE_QUERY: frozenset(
        {
            ResearchServiceErrorCode.BOUND_EXCEEDED,
            ResearchServiceErrorCode.DISCLOSURE_REJECTED,
        }
    ),
    IntegrityCase.DUPLICATE_LINEAGE: frozenset({DossierInputCode.DUPLICATE_IDENTITY}),
    IntegrityCase.REQUESTER_SPLITTING: frozenset(
        {
            ResearchServiceErrorCode.CONTEXT_SELECTION_FORBIDDEN,
            ResearchServiceErrorCode.DISCLOSURE_REJECTED,
        }
    ),
    IntegrityCase.TIMING_RESOURCE_SURFACE: frozenset(
        {
            ResourcePolicyInputCode.LIMIT_NOT_BOUND,
            ResearchServiceErrorCode.BOUND_EXCEEDED,
        }
    ),
    IntegrityCase.PRIOR_POISONING: frozenset(
        {
            ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID,
            ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID,
        }
    ),
    IntegrityCase.DUPLICATE_EVIDENCE: frozenset(
        {
            DossierInputCode.DUPLICATE_IDENTITY,
        }
    ),
    IntegrityCase.RAW_STRING: frozenset(
        {
            ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID,
            ResearchServiceErrorCode.REQUEST_TYPE_INVALID,
            ResearchServiceErrorCode.UNKNOWN_FIELD,
            ResearchServiceErrorCode.BOUND_EXCEEDED,
        }
    ),
    IntegrityCase.STRUCTURAL_LABEL_MISREPRESENTATION: frozenset(
        {
            DossierInputCode.ROLE_CONFUSION,
        }
    ),
    IntegrityCase.EVIDENCE_ROLE_SUBSTITUTION: frozenset(
        {
            DossierInputCode.ROLE_CONFUSION,
        }
    ),
    IntegrityCase.REFERENCE_CANDIDATE_FAILURE_COLLAPSE: frozenset(
        {ResearchServiceErrorCode.REFERENCE_MISMATCH}
    ),
    IntegrityCase.PARTIAL_PROXY_SUPERIOR: frozenset(
        {
            DossierInputCode.ROLE_CONFUSION,
            DossierInputCode.SLOT_MISMATCH,
            DossierInputCode.PLACEHOLDER_EVIDENCE,
        }
    ),
    IntegrityCase.LEARNED_COMPONENT_WRONG_ROLE: frozenset(
        {DossierInputCode.ROLE_CONFUSION}
    ),
    IntegrityCase.LEARNED_COMPONENT_INCOMPATIBLE_IO: frozenset(
        {DossierInputCode.SLOT_MISMATCH}
    ),
    IntegrityCase.LEARNED_COMPONENT_STALE_PIN: frozenset(
        {
            DossierInputCode.VERSION_MISMATCH,
            DossierInputCode.DIGEST_MISMATCH,
        }
    ),
    IntegrityCase.LEARNED_COMPONENT_SIDE_EFFECT: frozenset(
        {
            DossierInputCode.ROLE_CONFUSION,
        }
    ),
}


class GauntletStatus(str, Enum):
    BLOCKED_PREREGISTRATION = "BLOCKED_PREREGISTRATION"
    ENGINEERING_READY = "ENGINEERING_READY"


_DESIGN_FIELDS = (
    "representative_agent_profiles",
    "matched_time_compute_budgets",
    "utility_estimand",
    "practical_effect_floor",
    "uncertainty_aware_decision_rule",
    "intervention_diversity_metric",
    "intervention_diversity_floor",
    "conditional_leakage_limit",
)

_DESIGN_DIGEST_DOMAIN = b"carbon.gauntlet-preregistration.v1\x00"


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


def _finite_signed(value: object, name: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite float")
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
    """Opaque design values with deterministic content binding only.

    Declared completeness is not verified owner ratification. The repository has
    no B-E4 integration contract that can verify owner approval or execution
    evidence yet, so neither can be inferred from these caller-supplied records.
    """

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
        for name in _DESIGN_FIELDS:
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
        if any(type(item) is not OwnerRatification for item in self.ratifications):
            raise TypeError("ratifications require exact OwnerRatification values")

    @property
    def missing_design_inputs(self) -> tuple[str, ...]:
        missing = tuple(
            name
            for name in ("design_digest", *_DESIGN_FIELDS)
            if getattr(self, name) is None
        )
        computed = self.computed_design_digest
        if (
            self.design_digest is not None
            and computed is not None
            and self.design_digest != computed
        ):
            return (*missing, "design_digest:content_mismatch")
        return missing

    @property
    def missing_ratifications(self) -> tuple[str, ...]:
        ratified = {item.owner for item in self.ratifications}
        duplicate_owner = (
            ("ratification:duplicate_owner",)
            if len(ratified) != len(self.ratifications)
            else ()
        )
        missing_owners = tuple(
            f"ratification:{owner.value.lower()}"
            for owner in RatifyingOwner
            if owner not in ratified
        )
        if self.design_digest is not None and any(
            item.design_digest != self.design_digest for item in self.ratifications
        ):
            return (
                *duplicate_owner,
                "ratification:exact_design_digest",
                *missing_owners,
            )
        return (*duplicate_owner, *missing_owners)

    @property
    def missing_inputs(self) -> tuple[str, ...]:
        return (*self.missing_design_inputs, *self.missing_ratifications)

    @property
    def computed_design_digest(self) -> str | None:
        values = tuple(getattr(self, name) for name in _DESIGN_FIELDS)
        if any(value is None for value in values):
            return None
        payload = bytearray(_DESIGN_DIGEST_DOMAIN)
        for name, value in zip(_DESIGN_FIELDS, values):
            assert type(value) is str
            for item in (name, value):
                encoded = item.encode("utf-8", errors="strict")
                payload.extend(len(encoded).to_bytes(4, "big"))
                payload.extend(encoded)
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    @property
    def is_complete(self) -> bool:
        """Return declared structural completeness, never approval authority."""

        return self.is_syntactically_complete and self.has_declared_ratifications

    @property
    def is_syntactically_complete(self) -> bool:
        """Return whether immutable design content is present and digest-bound."""

        return not self.missing_design_inputs

    @property
    def has_declared_ratifications(self) -> bool:
        """Return whether caller records name every owner on the bound digest."""

        return not self.missing_ratifications

    @property
    def is_verified_owner_ratified(self) -> bool:
        """Fail closed until a domain-owned ratification verifier is specified."""

        return False


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
        if self.arm is not ExperimentalArm.V2_TEST_ONLY_PRIOR:
            if (
                self.prior_pack_ref is not None
                or self.test_only_authorization_ref is not None
            ):
                raise ValueError("non-v2 arm pin fields must be exactly None")
            return
        if (
            type(self.prior_pack_ref) is not PriorPackRef
            or type(self.test_only_authorization_ref)
            is not TestOnlyPriorAuthorizationReceiptRef
        ):
            raise ValueError("the v2 arm requires exact pack and authorization pins")
        try:
            pack = PriorPackRef(
                self.prior_pack_ref.challenge_key,
                self.prior_pack_ref.channel,
                self.prior_pack_ref.publication_sequence,
                self.prior_pack_ref.content_hash,
            )
            receipt = TestOnlyPriorAuthorizationReceiptRef(
                self.test_only_authorization_ref.challenge_key,
                self.test_only_authorization_ref.authorization_id,
                self.test_only_authorization_ref.content_digest,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("v2 pin values are structurally invalid") from exc
        if pack.channel is not PriorChannel.TEST_ONLY_FIXTURE:
            raise ValueError("the v2 pack channel must be TEST_ONLY_FIXTURE")
        if pack.challenge_key != receipt.challenge_key:
            raise ValueError("the v2 pack and receipt must bind one Challenge")
        object.__setattr__(self, "prior_pack_ref", pack)
        object.__setattr__(self, "test_only_authorization_ref", receipt)


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
    protocol_outcome: (
        ResearchServiceErrorCode | ResourcePolicyInputCode | DossierInputCode
    )
    fixture_only: bool = True

    def __post_init__(self) -> None:
        if (
            type(self) is not IntegrityObservation
            or type(self.case) is not IntegrityCase
            or type(self.disposition) is not IntegrityDisposition
            or self.fixture_only is not True
        ):
            raise TypeError("integrity observation is invalid")
        if type(self.protocol_outcome) not in _PROTOCOL_OUTCOME_TYPES:
            raise TypeError(
                "integrity observation requires a registered protocol outcome"
            )
        if self.protocol_outcome not in _APPLICABLE_PROTOCOL_OUTCOMES[self.case]:
            raise ValueError("protocol outcome is not applicable to the integrity case")
        if self.disposition is not IntegrityDisposition.TYPED_REJECTION:
            raise ValueError(
                "non-rejection dispositions require unavailable executed-attack evidence"
            )


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
        ):
            _finite(getattr(self, name), name)
        _finite_signed(
            self.conditional_leakage_statistic, "conditional_leakage_statistic"
        )
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
        if self.qualifying_execution:
            raise ValueError(
                "qualifying execution recording unavailable until verified owner "
                "ratification and execution-evidence integration exist"
            )

    @property
    def status(self) -> GauntletStatus:
        if not self.preregistration.is_complete:
            return GauntletStatus.BLOCKED_PREREGISTRATION
        return GauntletStatus.ENGINEERING_READY
