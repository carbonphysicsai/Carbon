"""Exact immutable values for the B-02C research-resource policy contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, TypeAlias, TypeVar

from carbon.authoring.canonical import CanonicalText, encode_value
from carbon.authoring.errors import AuthoringError
from carbon.authoring.primitives import (
    MAX_CANONICAL_PAYLOAD_BYTES,
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_exact_bool,
    validate_positive_uint64,
    validate_tagged_sha256,
    validate_uint64,
    validate_version_token,
)
from carbon.authoring.refs import ChallengeScope, GlobalScope, require_owner_ref
from carbon.construction.canonical import from_canonical_value, to_canonical_value
from carbon.construction.model import (
    CompilerIdentity,
    EnvironmentPin,
    StaticResourceDimension,
    StaticResourceRequirement,
)
from carbon.construction.refs import (
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
    ResolvedConstructionPlanRef,
    reconstruct_construction_ref,
)
from carbon.registry import ChallengeKey

from .errors import ResourcePolicyInputCode, ResourcePolicyInputRejected
from .refs import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    FixtureResourceDecisionRef,
    ResearchResourcePolicyRef,
    ResourceCancellationRecordRef,
    ResourceClassRef,
    StaticResourceAssessmentRef,
    reconstruct_resource_policy_ref,
)

_T = TypeVar("_T")


def _wrong(path: str) -> ResourcePolicyInputRejected:
    return ResourcePolicyInputRejected(ResourcePolicyInputCode.WRONG_TYPE, path=path)


def _invalid(path: str) -> ResourcePolicyInputRejected:
    return ResourcePolicyInputRejected(ResourcePolicyInputCode.INVALID_VALUE, path=path)


def _exact_self(value: object, expected: type[object]) -> None:
    if type(value) is not expected:
        raise _wrong("/type")


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _wrong(path) from exc


def _identifier(value: object, path: str) -> str:
    try:
        checked = validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _invalid(path) from exc
    if len(checked.encode("ascii")) > MAX_CANONICAL_PAYLOAD_BYTES:
        raise _invalid(path)
    return checked


def _version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _invalid(path) from exc


def _digest(value: object, path: str) -> str:
    try:
        return validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _invalid(path) from exc


def _uint64(value: object, path: str) -> int:
    try:
        return validate_uint64(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _invalid(path) from exc


def _positive_uint64(value: object, path: str) -> int:
    try:
        return validate_positive_uint64(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _invalid(path) from exc


def _exact_bool(value: object, path: str) -> bool:
    try:
        return validate_exact_bool(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _wrong(path) from exc


def _exact_enum(value: object, expected: type[_T], path: str) -> _T:
    if type(value) is not expected:
        raise _wrong(path)
    return value


def _copy_model(value: object, expected: type[_T], path: str) -> _T:
    if type(value) is not expected:
        raise _wrong(path)
    try:
        copied = from_canonical_value(to_canonical_value(value), expected)
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _invalid(path) from exc
    if type(copied) is not expected:
        raise _wrong(path)
    return copied


def _copy_construction_ref(value: object, expected: type[_T], path: str) -> _T:
    if type(value) is not expected:
        raise _wrong(path)
    try:
        copied = reconstruct_construction_ref(value)
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _invalid(path) from exc
    if type(copied) is not expected:
        raise _wrong(path)
    return copied


def _copy_resource_ref(value: object, expected: type[_T], path: str) -> _T:
    if type(value) is not expected:
        raise _wrong(path)
    try:
        copied = reconstruct_resource_policy_ref(value)
    except (ResourcePolicyInputRejected, TypeError, ValueError) as exc:
        raise _invalid(path) from exc
    if type(copied) is not expected:
        raise _wrong(path)
    return copied


def _owner(
    value: object,
    kind: str,
    *,
    challenge_key: ChallengeKey,
    portable: bool,
    path: str,
) -> object:
    try:
        copied = require_owner_ref(value, kind)
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _wrong(path) from exc
    scope = copied.scope_binding
    if type(scope) is ChallengeScope:
        if scope.challenge_key != challenge_key:
            raise _invalid(path)
    elif not portable or type(scope) is not GlobalScope:
        raise _invalid(path)
    return copied


def _portable_owner_unbound(value: object, kind: str, path: str) -> object:
    """Copy a portable owner ref before a containing Challenge is available."""

    try:
        copied = require_owner_ref(value, kind)
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _wrong(path) from exc
    if type(copied.scope_binding) not in (ChallengeScope, GlobalScope):
        raise _invalid(path)
    return copied


def _pinned_owner_unbound(value: object, kind: str, path: str) -> object:
    copied = _portable_owner_unbound(value, kind, path)
    if type(copied.scope_binding) is not ChallengeScope:
        raise _invalid(path)
    return copied


def _tuple(
    value: object,
    *,
    path: str,
    copier: Callable[[object], _T],
    nonempty: bool = False,
    set_like: bool = False,
) -> tuple[_T, ...]:
    if type(value) is not tuple:
        raise _wrong(path)
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS or (nonempty and not value):
        raise _invalid(path)
    copied = tuple(copier(item) for item in value)
    try:
        has_duplicates = len(set(copied)) != len(copied)
    except TypeError as exc:
        raise _invalid(path) from exc
    if has_duplicates:
        raise _invalid(path)
    if set_like:
        try:
            from .canonical import canonical_sort_key

            copied = tuple(sorted(copied, key=canonical_sort_key))
        except ResourcePolicyInputRejected:
            raise
        except (AuthoringError, TypeError, ValueError) as exc:
            raise _invalid(path) from exc
    return copied


def _ids(
    value: object,
    *,
    path: str,
    nonempty: bool = False,
) -> tuple[str, ...]:
    result = _tuple(
        value,
        path=path,
        copier=lambda item: _identifier(item, path),
        nonempty=nonempty,
    )
    return tuple(sorted(result, key=lambda item: encode_value(CanonicalText(item))))


def _header(
    value: object,
    expected: type[object],
    object_kind: object,
    schema_version: object,
    canonicalization_profile: object,
) -> None:
    _exact_self(value, expected)
    expected_kind = expected.OBJECT_KIND  # type: ignore[attr-defined]
    if type(object_kind) is not str or object_kind != expected_kind:
        raise _invalid("/object_kind")
    if (
        type(schema_version) is not str
        or schema_version != RESOURCE_POLICY_SCHEMA_VERSION
    ):
        raise _invalid("/schema_version")
    if (
        type(canonicalization_profile) is not str
        or canonicalization_profile != RESOURCE_POLICY_CANONICALIZATION_PROFILE
    ):
        raise _invalid("/canonicalization_profile")


def _require_challenge(values: tuple[object, ...], key: ChallengeKey) -> None:
    if any(getattr(value, "challenge_key", None) != key for value in values):
        raise _invalid("/challenge_key")


class ResourcePolicyAuthorityMarker(str, Enum):
    FIXTURE_PROVENANCE_NOT_PRODUCTION = "FIXTURE_PROVENANCE_NOT_PRODUCTION"
    FIXTURE_PRACTICE_NOT_OFFICIAL = "FIXTURE_PRACTICE_NOT_OFFICIAL"
    FIXTURE_OFFICIAL_SHAPED_NOT_OFFICIAL = "FIXTURE_OFFICIAL_SHAPED_NOT_OFFICIAL"
    FIXTURE_RESOURCE_CLASS_NOT_PRODUCTION = "FIXTURE_RESOURCE_CLASS_NOT_PRODUCTION"
    FIXTURE_RESOURCE_POLICY_NOT_PRODUCTION = "FIXTURE_RESOURCE_POLICY_NOT_PRODUCTION"
    STATIC_POLICY_RESULT_NOT_EXECUTION_OR_SCIENCE = (
        "STATIC_POLICY_RESULT_NOT_EXECUTION_OR_SCIENCE"
    )
    FIXTURE_AVAILABILITY_NOT_OPERATIONAL_COMMITMENT = (
        "FIXTURE_AVAILABILITY_NOT_OPERATIONAL_COMMITMENT"
    )
    POLICY_ADMISSIBILITY_NOT_QUOTE_OR_EXECUTION = (
        "POLICY_ADMISSIBILITY_NOT_QUOTE_OR_EXECUTION"
    )
    RESOURCE_ENFORCEMENT_NOT_EXECUTION_OR_SCIENCE = (
        "RESOURCE_ENFORCEMENT_NOT_EXECUTION_OR_SCIENCE"
    )
    RESOURCE_STOP_NOT_SCIENTIFIC_OUTCOME = "RESOURCE_STOP_NOT_SCIENTIFIC_OUTCOME"
    RESOURCE_FACTS_ONLY_NOT_EVIDENCE_OR_PRICE = (
        "RESOURCE_FACTS_ONLY_NOT_EVIDENCE_OR_PRICE"
    )


class ResourceEpistemicLayer(str, Enum):
    STATIC_CONSTRUCTION_REQUIREMENT = "STATIC_CONSTRUCTION_REQUIREMENT"
    OBSERVED_RESOURCE_RECEIPT = "OBSERVED_RESOURCE_RECEIPT"


class UnknownOrInvalidPolicy(str, Enum):
    REJECT = "REJECT"


class ResourceObservationRole(str, Enum):
    RESOURCE_CONSUMPTION = "RESOURCE_CONSUMPTION"
    RESOURCE_COST_NOT_PRICE = "RESOURCE_COST_NOT_PRICE"
    OBSERVED_LATENCY = "OBSERVED_LATENCY"


class ObservationUnavailableReason(str, Enum):
    NO_WORK_STARTED = "NO_WORK_STARTED"
    CANCELLED_BEFORE_OBSERVATION = "CANCELLED_BEFORE_OBSERVATION"
    OBSERVATION_FAILED = "OBSERVATION_FAILED"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


class EnforcementPoint(str, Enum):
    PRE_ALLOCATION_READINESS = "PRE_ALLOCATION_READINESS"
    PRE_EXECUTION = "PRE_EXECUTION"
    RUNTIME_OBSERVATION = "RUNTIME_OBSERVATION"


class EnforcementMode(str, Enum):
    PREVENT_START_ON_EXCESS = "PREVENT_START_ON_EXCESS"
    PREVENT_NEXT_UNIT_ON_EXCESS = "PREVENT_NEXT_UNIT_ON_EXCESS"
    STOP_ON_FIRST_OBSERVED_EXCESS = "STOP_ON_FIRST_OBSERVED_EXCESS"


class EnforcementObservationKind(str, Enum):
    CURRENT_TOTAL = "CURRENT_TOTAL"
    ATTEMPTED_NEXT_TOTAL = "ATTEMPTED_NEXT_TOTAL"


class ResourcePolicyIssueCode(str, Enum):
    STALE_POLICY_REF = "STALE_POLICY_REF"
    STALE_RESOURCE_CLASS_REF = "STALE_RESOURCE_CLASS_REF"
    CHALLENGE_MISMATCH = "CHALLENGE_MISMATCH"
    AUTHORITY_CONTEXT_MISMATCH = "AUTHORITY_CONTEXT_MISMATCH"
    PLAN_ASSEMBLY_MISMATCH = "PLAN_ASSEMBLY_MISMATCH"
    PLAN_CATALOG_MISMATCH = "PLAN_CATALOG_MISMATCH"
    PLAN_COMPILER_MISMATCH = "PLAN_COMPILER_MISMATCH"
    PLAN_ENVIRONMENT_MISMATCH = "PLAN_ENVIRONMENT_MISMATCH"
    RESOURCE_CLASS_NOT_BOUND = "RESOURCE_CLASS_NOT_BOUND"
    UNSUPPORTED_DIMENSION = "UNSUPPORTED_DIMENSION"
    UNSUPPORTED_UNIT = "UNSUPPORTED_UNIT"
    UNSUPPORTED_IMPACT_TAG = "UNSUPPORTED_IMPACT_TAG"
    STATIC_REQUIREMENT_OVER_LIMIT = "STATIC_REQUIREMENT_OVER_LIMIT"
    LIMIT_OBSERVATION_MISMATCH = "LIMIT_OBSERVATION_MISMATCH"
    ENFORCEMENT_EVALUATION_FAILURE = "ENFORCEMENT_EVALUATION_FAILURE"


RESOURCE_POLICY_ISSUE_MESSAGES = {
    ResourcePolicyIssueCode.STALE_POLICY_REF: "selected policy ref is stale",
    ResourcePolicyIssueCode.STALE_RESOURCE_CLASS_REF: (
        "selected resource class ref is stale"
    ),
    ResourcePolicyIssueCode.CHALLENGE_MISMATCH: (
        "resource input has the wrong Challenge"
    ),
    ResourcePolicyIssueCode.AUTHORITY_CONTEXT_MISMATCH: (
        "resource authority context does not match"
    ),
    ResourcePolicyIssueCode.PLAN_ASSEMBLY_MISMATCH: (
        "construction plan assembly does not match policy"
    ),
    ResourcePolicyIssueCode.PLAN_CATALOG_MISMATCH: (
        "construction plan catalog does not match policy"
    ),
    ResourcePolicyIssueCode.PLAN_COMPILER_MISMATCH: (
        "construction plan compiler does not match policy"
    ),
    ResourcePolicyIssueCode.PLAN_ENVIRONMENT_MISMATCH: (
        "construction plan environment is unsupported"
    ),
    ResourcePolicyIssueCode.RESOURCE_CLASS_NOT_BOUND: (
        "resource class is not bound by policy"
    ),
    ResourcePolicyIssueCode.UNSUPPORTED_DIMENSION: (
        "static resource dimension is unsupported"
    ),
    ResourcePolicyIssueCode.UNSUPPORTED_UNIT: "resource unit is unsupported",
    ResourcePolicyIssueCode.UNSUPPORTED_IMPACT_TAG: (
        "resource impact tag is unsupported"
    ),
    ResourcePolicyIssueCode.STATIC_REQUIREMENT_OVER_LIMIT: (
        "static resource requirement exceeds its ceiling"
    ),
    ResourcePolicyIssueCode.LIMIT_OBSERVATION_MISMATCH: (
        "runtime observation does not match its limit"
    ),
    ResourcePolicyIssueCode.ENFORCEMENT_EVALUATION_FAILURE: (
        "resource enforcement failed closed"
    ),
}


class StaticAssessmentOutcome(str, Enum):
    ADMISSIBLE = "ADMISSIBLE"
    UNSUPPORTED_RESOURCE_CLASS = "UNSUPPORTED_RESOURCE_CLASS"
    UNSUPPORTED_REQUIREMENT = "UNSUPPORTED_REQUIREMENT"
    OVER_LIMIT = "OVER_LIMIT"
    STALE_POLICY = "STALE_POLICY"
    STALE_REFERENCE = "STALE_REFERENCE"
    CHALLENGE_MISMATCH = "CHALLENGE_MISMATCH"
    AUTHORITY_CONTEXT_MISMATCH = "AUTHORITY_CONTEXT_MISMATCH"
    PLAN_BINDING_MISMATCH = "PLAN_BINDING_MISMATCH"
    ENVIRONMENT_MISMATCH = "ENVIRONMENT_MISMATCH"


class FixtureAvailabilityState(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FixtureDecisionOutcome(str, Enum):
    FIXTURE_ADMISSIBLE = "FIXTURE_ADMISSIBLE"
    EVIDENCE_DEFERRED = "EVIDENCE_DEFERRED"


class ResourceDeferralCause(str, Enum):
    CAPACITY_UNAVAILABLE = "CAPACITY_UNAVAILABLE"
    RECONSTRUCTION_FUNDING_UNAVAILABLE = "RECONSTRUCTION_FUNDING_UNAVAILABLE"
    QUEUE_UNAVAILABLE = "QUEUE_UNAVAILABLE"
    EVIDENCE_BUDGET_UNAVAILABLE = "EVIDENCE_BUDGET_UNAVAILABLE"


class ResourceEnforcementAction(str, Enum):
    NO_STOP = "NO_STOP"
    PREVENT_FIXTURE_START = "PREVENT_FIXTURE_START"
    PREVENT_NEXT_UNIT = "PREVENT_NEXT_UNIT"
    REQUEST_FIXTURE_STOP = "REQUEST_FIXTURE_STOP"
    FAIL_CLOSED = "FAIL_CLOSED"


class ResourceEnforcementOutcome(str, Enum):
    CONTINUE_FIXTURE = "CONTINUE_FIXTURE"
    STOPPED_OVER_LIMIT = "STOPPED_OVER_LIMIT"
    ENFORCEMENT_FAILURE = "ENFORCEMENT_FAILURE"


class CancellationReason(str, Enum):
    REQUESTER_CANCELLED = "REQUESTER_CANCELLED"
    POLICY_LIMIT_REACHED = "POLICY_LIMIT_REACHED"
    CAPACITY_WITHDRAWN = "CAPACITY_WITHDRAWN"
    FUNDING_WITHDRAWN = "FUNDING_WITHDRAWN"
    QUEUE_WITHDRAWN = "QUEUE_WITHDRAWN"
    EVIDENCE_BUDGET_WITHDRAWN = "EVIDENCE_BUDGET_WITHDRAWN"
    ENFORCEMENT_FAILURE = "ENFORCEMENT_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


class CancellationResultingState(str, Enum):
    CANCELLED_NON_SCIENTIFIC = "CANCELLED_NON_SCIENTIFIC"
    EVIDENCE_DEFERRED = "EVIDENCE_DEFERRED"
    INFRASTRUCTURE_UNAVAILABLE_NON_SCIENTIFIC = (
        "INFRASTRUCTURE_UNAVAILABLE_NON_SCIENTIFIC"
    )


class ReplicateNotApplicableReason(str, Enum):
    NO_WORK_STARTED = "NO_WORK_STARTED"
    NOT_A_RECONSTRUCTION_REPLICATE = "NOT_A_RECONSTRUCTION_REPLICATE"


class DeclaredResourceEvidenceStage(str, Enum):
    NO_WORK_STARTED = "NO_WORK_STARTED"
    DECLARED_PRACTICE_REHEARSAL = "DECLARED_PRACTICE_REHEARSAL"
    DECLARED_BUILD_ACCOUNTING = "DECLARED_BUILD_ACCOUNTING"
    DECLARED_RECONSTRUCTION_REPLICATE_ACCOUNTING = (
        "DECLARED_RECONSTRUCTION_REPLICATE_ACCOUNTING"
    )
    DECLARED_RANDOM_REPEAT_ACCOUNTING = "DECLARED_RANDOM_REPEAT_ACCOUNTING"


class ResourceStopCause(str, Enum):
    COMPLETED_RESOURCE_ACCOUNTING = "COMPLETED_RESOURCE_ACCOUNTING"
    POLICY_LIMIT_REACHED = "POLICY_LIMIT_REACHED"
    CANCELLED = "CANCELLED"
    ENFORCEMENT_FAILURE = "ENFORCEMENT_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    EVIDENCE_DEFERRED = "EVIDENCE_DEFERRED"


@dataclass(frozen=True, slots=True)
class FixtureResourceProvenance:
    fixture_registration_ref: object
    source_provenance_refs: tuple[object, ...]
    authority_marker: ResourcePolicyAuthorityMarker

    def __post_init__(self) -> None:
        _exact_self(self, FixtureResourceProvenance)
        registration = _pinned_owner_unbound(
            self.fixture_registration_ref,
            "fixture_registration",
            "/fixture_registration_ref",
        )
        sources = _tuple(
            self.source_provenance_refs,
            path="/source_provenance_refs",
            copier=lambda item: _pinned_owner_unbound(
                item,
                "provenance",
                "/source_provenance_refs",
            ),
            nonempty=True,
            set_like=True,
        )
        marker = _exact_enum(
            self.authority_marker,
            ResourcePolicyAuthorityMarker,
            "/authority_marker",
        )
        if (
            marker
            is not ResourcePolicyAuthorityMarker.FIXTURE_PROVENANCE_NOT_PRODUCTION
        ):
            raise _invalid("/authority_marker")
        object.__setattr__(self, "fixture_registration_ref", registration)
        object.__setattr__(self, "source_provenance_refs", sources)


def _copy_provenance(
    value: object, key: ChallengeKey, path: str = "/authority_context"
) -> FixtureResourceProvenance:
    if type(value) is not FixtureResourceProvenance:
        raise _wrong(path)
    copied = FixtureResourceProvenance(
        value.fixture_registration_ref,
        value.source_provenance_refs,
        value.authority_marker,
    )
    refs = (copied.fixture_registration_ref, *copied.source_provenance_refs)
    if any(ref.scope_binding.challenge_key != key for ref in refs):
        raise _invalid(path)
    return copied


def _validate_context(value: object, expected: type[object]) -> None:
    _exact_self(value, expected)
    key = _challenge(value.challenge_key)
    object.__setattr__(value, "challenge_key", key)
    object.__setattr__(
        value, "context_id", _identifier(value.context_id, "/context_id")
    )
    object.__setattr__(
        value,
        "fixture_registration_ref",
        _owner(
            value.fixture_registration_ref,
            "fixture_registration",
            challenge_key=key,
            portable=False,
            path="/fixture_registration_ref",
        ),
    )
    object.__setattr__(
        value,
        "internal_service_scope_ref",
        _owner(
            value.internal_service_scope_ref,
            "internal_service_scope",
            challenge_key=key,
            portable=False,
            path="/internal_service_scope_ref",
        ),
    )
    marker = _exact_enum(
        value.authority_marker,
        ResourcePolicyAuthorityMarker,
        "/authority_marker",
    )
    expected_marker = (
        ResourcePolicyAuthorityMarker.FIXTURE_PRACTICE_NOT_OFFICIAL
        if expected is FixturePracticeResourceContext
        else ResourcePolicyAuthorityMarker.FIXTURE_OFFICIAL_SHAPED_NOT_OFFICIAL
    )
    if marker is not expected_marker:
        raise _invalid("/authority_marker")


@dataclass(frozen=True, slots=True)
class FixturePracticeResourceContext:
    challenge_key: ChallengeKey
    context_id: str
    fixture_registration_ref: object
    internal_service_scope_ref: object
    authority_marker: ResourcePolicyAuthorityMarker

    def __post_init__(self) -> None:
        _validate_context(self, FixturePracticeResourceContext)


@dataclass(frozen=True, slots=True)
class FixtureOfficialShapedResourceContext:
    challenge_key: ChallengeKey
    context_id: str
    fixture_registration_ref: object
    internal_service_scope_ref: object
    authority_marker: ResourcePolicyAuthorityMarker

    def __post_init__(self) -> None:
        _validate_context(self, FixtureOfficialShapedResourceContext)


ResourceAuthorityContext: TypeAlias = (
    FixturePracticeResourceContext | FixtureOfficialShapedResourceContext
)


def _copy_authority_context(
    value: object, key: ChallengeKey, path: str = "/authority_context"
) -> ResourceAuthorityContext:
    if type(value) not in (
        FixturePracticeResourceContext,
        FixtureOfficialShapedResourceContext,
    ):
        raise _wrong(path)
    copied = type(value)(
        value.challenge_key,
        value.context_id,
        value.fixture_registration_ref,
        value.internal_service_scope_ref,
        value.authority_marker,
    )
    if copied.challenge_key != key:
        raise _invalid(path)
    return copied


@dataclass(frozen=True, slots=True)
class DeclaredResourceCeiling:
    dimension_id: str
    unit_ref: object
    maximum_quantity: int

    def __post_init__(self) -> None:
        _exact_self(self, DeclaredResourceCeiling)
        object.__setattr__(
            self, "dimension_id", _identifier(self.dimension_id, "/dimension_id")
        )
        object.__setattr__(
            self,
            "unit_ref",
            _portable_owner_unbound(self.unit_ref, "unit", "/unit_ref"),
        )
        object.__setattr__(
            self,
            "maximum_quantity",
            _uint64(self.maximum_quantity, "/maximum_quantity"),
        )


@dataclass(frozen=True, slots=True)
class ResourceObservationMetric:
    metric_id: str
    unit_ref: object
    observation_role: ResourceObservationRole

    def __post_init__(self) -> None:
        _exact_self(self, ResourceObservationMetric)
        object.__setattr__(self, "metric_id", _identifier(self.metric_id, "/metric_id"))
        object.__setattr__(
            self,
            "unit_ref",
            _portable_owner_unbound(self.unit_ref, "unit", "/unit_ref"),
        )
        _exact_enum(self.observation_role, ResourceObservationRole, "/observation_role")


@dataclass(frozen=True, slots=True)
class ObservedResourceQuantity:
    metric_id: str
    unit_ref: object
    quantity: int
    observation_role: ResourceObservationRole

    def __post_init__(self) -> None:
        _exact_self(self, ObservedResourceQuantity)
        object.__setattr__(self, "metric_id", _identifier(self.metric_id, "/metric_id"))
        object.__setattr__(
            self,
            "unit_ref",
            _portable_owner_unbound(self.unit_ref, "unit", "/unit_ref"),
        )
        object.__setattr__(self, "quantity", _uint64(self.quantity, "/quantity"))
        _exact_enum(self.observation_role, ResourceObservationRole, "/observation_role")


@dataclass(frozen=True, slots=True)
class ObservedMetricObserved:
    observed_quantity: ObservedResourceQuantity

    def __post_init__(self) -> None:
        _exact_self(self, ObservedMetricObserved)
        if type(self.observed_quantity) is not ObservedResourceQuantity:
            raise _wrong("/observation")
        object.__setattr__(
            self,
            "observed_quantity",
            ObservedResourceQuantity(
                self.observed_quantity.metric_id,
                self.observed_quantity.unit_ref,
                self.observed_quantity.quantity,
                self.observed_quantity.observation_role,
            ),
        )


@dataclass(frozen=True, slots=True)
class ObservedMetricUnavailable:
    reason: ObservationUnavailableReason

    def __post_init__(self) -> None:
        _exact_self(self, ObservedMetricUnavailable)
        _exact_enum(self.reason, ObservationUnavailableReason, "/observation")


ObservedMetricBinding: TypeAlias = ObservedMetricObserved | ObservedMetricUnavailable


@dataclass(frozen=True, slots=True)
class OperationalRequirementRequired:
    def __post_init__(self) -> None:
        _exact_self(self, OperationalRequirementRequired)


@dataclass(frozen=True, slots=True)
class OperationalRequirementNotApplicable:
    reason_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, OperationalRequirementNotApplicable)
        object.__setattr__(
            self,
            "reason_ref",
            _pinned_owner_unbound(
                self.reason_ref,
                "applicability_reason",
                "/scope_binding",
            ),
        )


OperationalRequirementDisposition: TypeAlias = (
    OperationalRequirementRequired | OperationalRequirementNotApplicable
)


OPERATIONAL_REQUIREMENT_REQUIRED = OperationalRequirementRequired()


@dataclass(frozen=True, slots=True)
class OperationalReadinessRequirements:
    validator_capacity: OperationalRequirementDisposition
    reconstruction_funding: OperationalRequirementDisposition
    queue_availability: OperationalRequirementDisposition
    evidence_budget_availability: OperationalRequirementDisposition

    def __post_init__(self) -> None:
        _exact_self(self, OperationalReadinessRequirements)
        for field in (
            "validator_capacity",
            "reconstruction_funding",
            "queue_availability",
            "evidence_budget_availability",
        ):
            value = getattr(self, field)
            if type(value) is OperationalRequirementRequired:
                copied: OperationalRequirementDisposition = (
                    OperationalRequirementRequired()
                )
            elif type(value) is OperationalRequirementNotApplicable:
                copied = OperationalRequirementNotApplicable(value.reason_ref)
            else:
                raise _wrong(f"/{field}")
            object.__setattr__(self, field, copied)


@dataclass(frozen=True, slots=True)
class RuntimeResourceLimit:
    limit_id: str
    metric_id: str
    unit_ref: object
    maximum_quantity: int
    enforcement_point: EnforcementPoint
    enforcement_mode: EnforcementMode

    def __post_init__(self) -> None:
        _exact_self(self, RuntimeResourceLimit)
        object.__setattr__(self, "limit_id", _identifier(self.limit_id, "/limit_id"))
        object.__setattr__(self, "metric_id", _identifier(self.metric_id, "/metric_id"))
        object.__setattr__(
            self,
            "unit_ref",
            _portable_owner_unbound(self.unit_ref, "unit", "/unit_ref"),
        )
        object.__setattr__(
            self,
            "maximum_quantity",
            _uint64(self.maximum_quantity, "/maximum_quantity"),
        )
        point = _exact_enum(
            self.enforcement_point, EnforcementPoint, "/enforcement_point"
        )
        mode = _exact_enum(self.enforcement_mode, EnforcementMode, "/enforcement_mode")
        expected = {
            EnforcementPoint.PRE_ALLOCATION_READINESS: EnforcementMode.PREVENT_START_ON_EXCESS,
            EnforcementPoint.PRE_EXECUTION: EnforcementMode.PREVENT_NEXT_UNIT_ON_EXCESS,
            EnforcementPoint.RUNTIME_OBSERVATION: EnforcementMode.STOP_ON_FIRST_OBSERVED_EXCESS,
        }[point]
        if mode is not expected:
            raise _invalid("/enforcement")


@dataclass(frozen=True, slots=True)
class ResourceEnforcementObservation:
    metric_quantity: ObservedResourceQuantity
    observation_kind: EnforcementObservationKind

    def __post_init__(self) -> None:
        _exact_self(self, ResourceEnforcementObservation)
        if type(self.metric_quantity) is not ObservedResourceQuantity:
            raise _wrong("/observation")
        object.__setattr__(
            self,
            "metric_quantity",
            ObservedResourceQuantity(
                self.metric_quantity.metric_id,
                self.metric_quantity.unit_ref,
                self.metric_quantity.quantity,
                self.metric_quantity.observation_role,
            ),
        )
        _exact_enum(
            self.observation_kind,
            EnforcementObservationKind,
            "/observation",
        )


_ISSUE_PATHS = {
    ResourcePolicyIssueCode.STALE_POLICY_REF: ("/expected_active_policy_ref",),
    ResourcePolicyIssueCode.STALE_RESOURCE_CLASS_REF: (
        "/expected_active_resource_class_ref",
    ),
    ResourcePolicyIssueCode.CHALLENGE_MISMATCH: ("/challenge_key",),
    ResourcePolicyIssueCode.AUTHORITY_CONTEXT_MISMATCH: ("/authority_context",),
    ResourcePolicyIssueCode.PLAN_ASSEMBLY_MISMATCH: (
        "/construction_plan_ref/candidate_assembly_ref",
    ),
    ResourcePolicyIssueCode.PLAN_CATALOG_MISMATCH: (
        "/construction_plan_ref/parameter_catalog_ref",
    ),
    ResourcePolicyIssueCode.PLAN_COMPILER_MISMATCH: (
        "/construction_plan_ref/compiler_identity",
    ),
    ResourcePolicyIssueCode.PLAN_ENVIRONMENT_MISMATCH: (
        "/resource_class/required_plan_environment_pins/",
    ),
    ResourcePolicyIssueCode.RESOURCE_CLASS_NOT_BOUND: ("/resource_class_ref",),
    ResourcePolicyIssueCode.UNSUPPORTED_DIMENSION: ("/static_resource_requirements/",),
    ResourcePolicyIssueCode.UNSUPPORTED_UNIT: ("/static_resource_requirements/",),
    ResourcePolicyIssueCode.UNSUPPORTED_IMPACT_TAG: ("/resource_impact_tags/",),
    ResourcePolicyIssueCode.STATIC_REQUIREMENT_OVER_LIMIT: (
        "/static_resource_requirements/",
    ),
    ResourcePolicyIssueCode.LIMIT_OBSERVATION_MISMATCH: ("/observation",),
    ResourcePolicyIssueCode.ENFORCEMENT_EVALUATION_FAILURE: ("/enforcement",),
}


def _issue_path_valid(code: ResourcePolicyIssueCode, path: str) -> bool:
    if len(path) > 256 or not path.isascii():
        return False

    def valid_index(value: str) -> bool:
        return (
            value.isascii()
            and value.isdecimal()
            and value == str(int(value))
            and int(value) < MAX_CANONICAL_TUPLE_ITEMS
        )

    prefixes = _ISSUE_PATHS[code]
    if path in prefixes:
        return True
    prefix = prefixes[0]
    if not prefix.endswith("/") or not path.startswith(prefix):
        return False
    suffix = path[len(prefix) :]
    if code is ResourcePolicyIssueCode.PLAN_ENVIRONMENT_MISMATCH:
        return valid_index(suffix)
    index, separator, final = suffix.partition("/")
    expected = {
        ResourcePolicyIssueCode.UNSUPPORTED_DIMENSION: "dimension_id",
        ResourcePolicyIssueCode.UNSUPPORTED_UNIT: "unit_ref",
        ResourcePolicyIssueCode.STATIC_REQUIREMENT_OVER_LIMIT: "quantity",
    }.get(code)
    if expected is None:
        return valid_index(index) and not separator
    return valid_index(index) and separator == "/" and final == expected


@dataclass(frozen=True, slots=True)
class ResourcePolicyIssue:
    code: ResourcePolicyIssueCode
    message: str
    path: str

    def __post_init__(self) -> None:
        _exact_self(self, ResourcePolicyIssue)
        code = _exact_enum(self.code, ResourcePolicyIssueCode, "/type")
        if (
            type(self.message) is not str
            or self.message != RESOURCE_POLICY_ISSUE_MESSAGES[code]
        ):
            raise _invalid("")
        if type(self.path) is not str or not _issue_path_valid(code, self.path):
            raise _invalid("")


def make_resource_policy_issue(
    code: ResourcePolicyIssueCode, path: str
) -> ResourcePolicyIssue:
    checked = _exact_enum(code, ResourcePolicyIssueCode, "/type")
    return ResourcePolicyIssue(checked, RESOURCE_POLICY_ISSUE_MESSAGES[checked], path)


def _copy_dimension(
    value: object, key: ChallengeKey, path: str = "/resource_class"
) -> StaticResourceDimension:
    copied = _copy_model(value, StaticResourceDimension, path)
    _owner(
        copied.unit_ref,
        "unit",
        challenge_key=key,
        portable=True,
        path="/unit_ref",
    )
    return copied


def _copy_requirement(
    value: object, key: ChallengeKey, path: str = "/static_resource_requirements"
) -> StaticResourceRequirement:
    copied = _copy_model(value, StaticResourceRequirement, path)
    _owner(
        copied.unit_ref,
        "unit",
        challenge_key=key,
        portable=True,
        path="/unit_ref",
    )
    return copied


def _copy_metric(
    value: object, key: ChallengeKey, path: str = "/observation"
) -> ResourceObservationMetric:
    if type(value) is not ResourceObservationMetric:
        raise _wrong(path)
    unit = _owner(
        value.unit_ref,
        "unit",
        challenge_key=key,
        portable=True,
        path="/unit_ref",
    )
    return ResourceObservationMetric(value.metric_id, unit, value.observation_role)


def _copy_observed_quantity(
    value: object, key: ChallengeKey, path: str = "/observation"
) -> ObservedResourceQuantity:
    if type(value) is not ObservedResourceQuantity:
        raise _wrong(path)
    unit = _owner(
        value.unit_ref,
        "unit",
        challenge_key=key,
        portable=True,
        path="/unit_ref",
    )
    return ObservedResourceQuantity(
        value.metric_id,
        unit,
        value.quantity,
        value.observation_role,
    )


def _copy_readiness(
    value: object, key: ChallengeKey
) -> OperationalReadinessRequirements:
    if type(value) is not OperationalReadinessRequirements:
        raise _wrong("/type")
    copied: list[OperationalRequirementDisposition] = []
    for field in (
        "validator_capacity",
        "reconstruction_funding",
        "queue_availability",
        "evidence_budget_availability",
    ):
        item = getattr(value, field)
        if type(item) is OperationalRequirementRequired:
            copied.append(OperationalRequirementRequired())
        elif type(item) is OperationalRequirementNotApplicable:
            copied.append(
                OperationalRequirementNotApplicable(
                    _owner(
                        item.reason_ref,
                        "applicability_reason",
                        challenge_key=key,
                        portable=False,
                        path="/scope_binding",
                    )
                )
            )
        else:
            raise _wrong("/type")
    return OperationalReadinessRequirements(*copied)


@dataclass(frozen=True, slots=True)
class ResourceClass:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    execution_environment_pin: EnvironmentPin
    required_plan_environment_pins: tuple[EnvironmentPin, ...]
    supported_dimensions: tuple[StaticResourceDimension, ...]
    observation_metrics: tuple[ResourceObservationMetric, ...]
    provenance: FixtureResourceProvenance
    authority_marker: ResourcePolicyAuthorityMarker

    OBJECT_KIND: ClassVar[str] = "resource_class"

    def __post_init__(self) -> None:
        _header(
            self,
            ResourceClass,
            self.object_kind,
            self.schema_version,
            self.canonicalization_profile,
        )
        key = _challenge(self.challenge_key)
        execution = _copy_model(
            self.execution_environment_pin,
            EnvironmentPin,
            "/resource_class",
        )
        environments = _tuple(
            self.required_plan_environment_pins,
            path="/resource_class",
            copier=lambda item: _copy_model(item, EnvironmentPin, "/resource_class"),
            nonempty=True,
            set_like=True,
        )
        dimensions = _tuple(
            self.supported_dimensions,
            path="/resource_class",
            copier=lambda item: _copy_dimension(item, key),
            nonempty=True,
            set_like=True,
        )
        metrics = _tuple(
            self.observation_metrics,
            path="/resource_class",
            copier=lambda item: _copy_metric(item, key),
            nonempty=True,
            set_like=True,
        )
        provenance = _copy_provenance(self.provenance, key)
        if execution not in environments:
            raise _invalid("/resource_class")
        if len({item.dimension_id for item in dimensions}) != len(dimensions):
            raise _invalid("/resource_class")
        if len({item.metric_id for item in metrics}) != len(metrics):
            raise _invalid("/resource_class")
        roles = tuple(item.observation_role for item in metrics)
        if (
            roles.count(ResourceObservationRole.OBSERVED_LATENCY) != 1
            or roles.count(ResourceObservationRole.RESOURCE_COST_NOT_PRICE) != 1
            or ResourceObservationRole.RESOURCE_CONSUMPTION not in roles
        ):
            raise _invalid("/resource_class")
        marker = _exact_enum(
            self.authority_marker,
            ResourcePolicyAuthorityMarker,
            "/authority_marker",
        )
        if (
            marker
            is not ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_CLASS_NOT_PRODUCTION
        ):
            raise _invalid("/authority_marker")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "object_id", _identifier(self.object_id, "/object_id"))
        object.__setattr__(
            self, "object_version", _version(self.object_version, "/object_version")
        )
        object.__setattr__(self, "execution_environment_pin", execution)
        object.__setattr__(self, "required_plan_environment_pins", environments)
        object.__setattr__(self, "supported_dimensions", dimensions)
        object.__setattr__(self, "observation_metrics", metrics)
        object.__setattr__(self, "provenance", provenance)


@dataclass(frozen=True, slots=True)
class ResourceClassPolicyBinding:
    resource_class_ref: ResourceClassRef
    ceilings: tuple[DeclaredResourceCeiling, ...]
    supported_impact_tags: tuple[str, ...]
    runtime_limits: tuple[RuntimeResourceLimit, ...]
    readiness_requirements: OperationalReadinessRequirements

    def __post_init__(self) -> None:
        _exact_self(self, ResourceClassPolicyBinding)
        class_ref = _copy_resource_ref(
            self.resource_class_ref,
            ResourceClassRef,
            "/resource_class_ref",
        )
        key = class_ref.challenge_key

        def copy_ceiling(value: object) -> DeclaredResourceCeiling:
            if type(value) is not DeclaredResourceCeiling:
                raise _wrong("/resource_class")
            return DeclaredResourceCeiling(
                value.dimension_id,
                _owner(
                    value.unit_ref,
                    "unit",
                    challenge_key=key,
                    portable=True,
                    path="/unit_ref",
                ),
                value.maximum_quantity,
            )

        def copy_limit(value: object) -> RuntimeResourceLimit:
            if type(value) is not RuntimeResourceLimit:
                raise _wrong("/enforcement")
            return RuntimeResourceLimit(
                value.limit_id,
                value.metric_id,
                _owner(
                    value.unit_ref,
                    "unit",
                    challenge_key=key,
                    portable=True,
                    path="/unit_ref",
                ),
                value.maximum_quantity,
                value.enforcement_point,
                value.enforcement_mode,
            )

        ceilings = _tuple(
            self.ceilings,
            path="/resource_class",
            copier=copy_ceiling,
            nonempty=True,
            set_like=True,
        )
        limits = _tuple(
            self.runtime_limits,
            path="/enforcement",
            copier=copy_limit,
            set_like=True,
        )
        if len({item.dimension_id for item in ceilings}) != len(ceilings):
            raise _invalid("/resource_class")
        if len({item.limit_id for item in limits}) != len(limits):
            raise _invalid("/limit_id")
        object.__setattr__(self, "resource_class_ref", class_ref)
        object.__setattr__(self, "ceilings", ceilings)
        object.__setattr__(
            self,
            "supported_impact_tags",
            _ids(self.supported_impact_tags, path="/resource_impact_tags"),
        )
        object.__setattr__(self, "runtime_limits", limits)
        object.__setattr__(
            self,
            "readiness_requirements",
            _copy_readiness(self.readiness_requirements, key),
        )


def _copy_class_binding(value: object) -> ResourceClassPolicyBinding:
    if type(value) is not ResourceClassPolicyBinding:
        raise _wrong("/resource_class_ref")
    return ResourceClassPolicyBinding(
        value.resource_class_ref,
        value.ceilings,
        value.supported_impact_tags,
        value.runtime_limits,
        value.readiness_requirements,
    )


@dataclass(frozen=True, slots=True)
class ResearchResourcePolicy:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    candidate_assembly_ref: CandidateAssemblyContractRef
    parameter_catalog_ref: ParameterCatalogRef
    compiler_identity: CompilerIdentity
    authority_context: ResourceAuthorityContext
    class_bindings: tuple[ResourceClassPolicyBinding, ...]
    policy_authority_ref: object
    provenance: FixtureResourceProvenance
    unknown_or_invalid_policy: UnknownOrInvalidPolicy
    authority_marker: ResourcePolicyAuthorityMarker

    OBJECT_KIND: ClassVar[str] = "research_resource_policy"

    def __post_init__(self) -> None:
        _header(
            self,
            ResearchResourcePolicy,
            self.object_kind,
            self.schema_version,
            self.canonicalization_profile,
        )
        key = _challenge(self.challenge_key)
        assembly_ref = _copy_construction_ref(
            self.candidate_assembly_ref,
            CandidateAssemblyContractRef,
            "/construction_plan_ref/candidate_assembly_ref",
        )
        catalog_ref = _copy_construction_ref(
            self.parameter_catalog_ref,
            ParameterCatalogRef,
            "/construction_plan_ref/parameter_catalog_ref",
        )
        compiler = _copy_model(
            self.compiler_identity,
            CompilerIdentity,
            "/construction_plan_ref/compiler_identity",
        )
        context = _copy_authority_context(self.authority_context, key)
        bindings = _tuple(
            self.class_bindings,
            path="/resource_class_ref",
            copier=_copy_class_binding,
            nonempty=True,
            set_like=True,
        )
        provenance = _copy_provenance(self.provenance, key)
        policy_authority = _owner(
            self.policy_authority_ref,
            "policy_authority",
            challenge_key=key,
            portable=False,
            path="/scope_binding",
        )
        _require_challenge(
            (
                assembly_ref,
                catalog_ref,
                context,
                *(binding.resource_class_ref for binding in bindings),
            ),
            key,
        )
        if len({binding.resource_class_ref for binding in bindings}) != len(bindings):
            raise _invalid("/resource_class_ref")
        unknown = _exact_enum(
            self.unknown_or_invalid_policy,
            UnknownOrInvalidPolicy,
            "/type",
        )
        if unknown is not UnknownOrInvalidPolicy.REJECT:
            raise _invalid("/type")
        marker = _exact_enum(
            self.authority_marker,
            ResourcePolicyAuthorityMarker,
            "/authority_marker",
        )
        if (
            marker
            is not ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_POLICY_NOT_PRODUCTION
        ):
            raise _invalid("/authority_marker")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "object_id", _identifier(self.object_id, "/object_id"))
        object.__setattr__(
            self, "object_version", _version(self.object_version, "/object_version")
        )
        object.__setattr__(self, "candidate_assembly_ref", assembly_ref)
        object.__setattr__(self, "parameter_catalog_ref", catalog_ref)
        object.__setattr__(self, "compiler_identity", compiler)
        object.__setattr__(self, "authority_context", context)
        object.__setattr__(self, "class_bindings", bindings)
        object.__setattr__(self, "policy_authority_ref", policy_authority)
        object.__setattr__(self, "provenance", provenance)


def _copy_issue(value: object) -> ResourcePolicyIssue:
    if type(value) is not ResourcePolicyIssue:
        raise _wrong("/type")
    return ResourcePolicyIssue(value.code, value.message, value.path)


@dataclass(frozen=True, slots=True)
class StaticResourceAssessment:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    expected_active_policy_ref: ResearchResourcePolicyRef
    expected_active_resource_class_ref: ResourceClassRef
    construction_plan_ref: ResolvedConstructionPlanRef
    authority_context: ResourceAuthorityContext
    static_resource_requirements: tuple[StaticResourceRequirement, ...]
    resource_impact_tags: tuple[str, ...]
    outcome: StaticAssessmentOutcome
    issues: tuple[ResourcePolicyIssue, ...]
    epistemic_layer: ResourceEpistemicLayer
    authority_marker: ResourcePolicyAuthorityMarker

    OBJECT_KIND: ClassVar[str] = "static_resource_assessment"

    def __post_init__(self) -> None:
        _header(
            self,
            StaticResourceAssessment,
            self.object_kind,
            self.schema_version,
            self.canonicalization_profile,
        )
        key = _challenge(self.challenge_key)
        policy_ref = _copy_resource_ref(
            self.policy_ref, ResearchResourcePolicyRef, "/policy_ref"
        )
        class_ref = _copy_resource_ref(
            self.resource_class_ref, ResourceClassRef, "/resource_class_ref"
        )
        active_policy = _copy_resource_ref(
            self.expected_active_policy_ref,
            ResearchResourcePolicyRef,
            "/expected_active_policy_ref",
        )
        active_class = _copy_resource_ref(
            self.expected_active_resource_class_ref,
            ResourceClassRef,
            "/expected_active_resource_class_ref",
        )
        plan_ref = _copy_construction_ref(
            self.construction_plan_ref,
            ResolvedConstructionPlanRef,
            "/construction_plan_ref",
        )
        if type(self.authority_context) not in (
            FixturePracticeResourceContext,
            FixtureOfficialShapedResourceContext,
        ):
            raise _wrong("/authority_context")
        context = _copy_authority_context(
            self.authority_context,
            self.authority_context.challenge_key,
        )
        requirements = _tuple(
            self.static_resource_requirements,
            path="/static_resource_requirements",
            copier=lambda item: _copy_requirement(item, plan_ref.challenge_key),
        )
        issues = _tuple(self.issues, path="/type", copier=_copy_issue)
        issues = tuple(sorted(issues, key=lambda item: (item.path, item.code.value)))
        outcome = _exact_enum(self.outcome, StaticAssessmentOutcome, "/type")
        if (outcome is StaticAssessmentOutcome.ADMISSIBLE) != (not issues):
            raise _invalid("/type")
        allowed_issue_codes = {
            StaticAssessmentOutcome.ADMISSIBLE: (),
            StaticAssessmentOutcome.STALE_POLICY: (
                ResourcePolicyIssueCode.STALE_POLICY_REF,
            ),
            StaticAssessmentOutcome.STALE_REFERENCE: (
                ResourcePolicyIssueCode.STALE_RESOURCE_CLASS_REF,
            ),
            StaticAssessmentOutcome.CHALLENGE_MISMATCH: (
                ResourcePolicyIssueCode.CHALLENGE_MISMATCH,
            ),
            StaticAssessmentOutcome.AUTHORITY_CONTEXT_MISMATCH: (
                ResourcePolicyIssueCode.AUTHORITY_CONTEXT_MISMATCH,
            ),
            StaticAssessmentOutcome.PLAN_BINDING_MISMATCH: (
                ResourcePolicyIssueCode.PLAN_ASSEMBLY_MISMATCH,
                ResourcePolicyIssueCode.PLAN_CATALOG_MISMATCH,
                ResourcePolicyIssueCode.PLAN_COMPILER_MISMATCH,
            ),
            StaticAssessmentOutcome.ENVIRONMENT_MISMATCH: (
                ResourcePolicyIssueCode.PLAN_ENVIRONMENT_MISMATCH,
            ),
            StaticAssessmentOutcome.UNSUPPORTED_RESOURCE_CLASS: (
                ResourcePolicyIssueCode.RESOURCE_CLASS_NOT_BOUND,
            ),
            StaticAssessmentOutcome.UNSUPPORTED_REQUIREMENT: (
                ResourcePolicyIssueCode.UNSUPPORTED_DIMENSION,
                ResourcePolicyIssueCode.UNSUPPORTED_UNIT,
                ResourcePolicyIssueCode.UNSUPPORTED_IMPACT_TAG,
            ),
            StaticAssessmentOutcome.OVER_LIMIT: (
                ResourcePolicyIssueCode.STATIC_REQUIREMENT_OVER_LIMIT,
            ),
        }[outcome]
        if any(issue.code not in allowed_issue_codes for issue in issues):
            raise _invalid("/type")
        layer = _exact_enum(self.epistemic_layer, ResourceEpistemicLayer, "/type")
        if layer is not ResourceEpistemicLayer.STATIC_CONSTRUCTION_REQUIREMENT:
            raise _invalid("/type")
        marker = _exact_enum(
            self.authority_marker,
            ResourcePolicyAuthorityMarker,
            "/authority_marker",
        )
        if (
            marker
            is not ResourcePolicyAuthorityMarker.STATIC_POLICY_RESULT_NOT_EXECUTION_OR_SCIENCE
        ):
            raise _invalid("/authority_marker")
        if policy_ref.challenge_key != key:
            raise _invalid("/challenge_key")
        challenge_mismatch = any(
            value.challenge_key != key
            for value in (
                class_ref,
                active_policy,
                active_class,
                plan_ref,
                context,
            )
        )
        if outcome is StaticAssessmentOutcome.CHALLENGE_MISMATCH:
            if not challenge_mismatch:
                raise _invalid("/challenge_key")
        elif (
            outcome
            not in (
                StaticAssessmentOutcome.STALE_POLICY,
                StaticAssessmentOutcome.STALE_REFERENCE,
            )
            and challenge_mismatch
        ):
            raise _invalid("/challenge_key")
        if outcome is StaticAssessmentOutcome.STALE_POLICY:
            if policy_ref == active_policy:
                raise _invalid("/expected_active_policy_ref")
        elif policy_ref != active_policy:
            raise _invalid("/expected_active_policy_ref")
        if outcome is StaticAssessmentOutcome.STALE_REFERENCE:
            if class_ref == active_class:
                raise _invalid("/expected_active_resource_class_ref")
        elif (
            outcome is not StaticAssessmentOutcome.STALE_POLICY
            and class_ref != active_class
        ):
            raise _invalid("/expected_active_resource_class_ref")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "policy_ref", policy_ref)
        object.__setattr__(self, "resource_class_ref", class_ref)
        object.__setattr__(self, "expected_active_policy_ref", active_policy)
        object.__setattr__(self, "expected_active_resource_class_ref", active_class)
        object.__setattr__(self, "construction_plan_ref", plan_ref)
        object.__setattr__(self, "authority_context", context)
        object.__setattr__(self, "static_resource_requirements", requirements)
        object.__setattr__(
            self,
            "resource_impact_tags",
            _ids(self.resource_impact_tags, path="/resource_impact_tags"),
        )
        object.__setattr__(self, "issues", issues)


@dataclass(frozen=True, slots=True)
class NoAvailabilityInput:
    def __post_init__(self) -> None:
        _exact_self(self, NoAvailabilityInput)


NO_AVAILABILITY_INPUT = NoAvailabilityInput()


@dataclass(frozen=True, slots=True)
class FixtureResourceAvailability:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    authority_context: ResourceAuthorityContext
    validator_capacity: FixtureAvailabilityState
    reconstruction_funding: FixtureAvailabilityState
    queue_availability: FixtureAvailabilityState
    evidence_budget_availability: FixtureAvailabilityState
    fixture_registration_ref: object
    authority_marker: ResourcePolicyAuthorityMarker

    OBJECT_KIND: ClassVar[str] = "fixture_resource_availability"

    def __post_init__(self) -> None:
        _header(
            self,
            FixtureResourceAvailability,
            self.object_kind,
            self.schema_version,
            self.canonicalization_profile,
        )
        key = _challenge(self.challenge_key)
        policy_ref = _copy_resource_ref(
            self.policy_ref,
            ResearchResourcePolicyRef,
            "/policy_ref",
        )
        class_ref = _copy_resource_ref(
            self.resource_class_ref,
            ResourceClassRef,
            "/resource_class_ref",
        )
        context = _copy_authority_context(self.authority_context, key)
        registration = _owner(
            self.fixture_registration_ref,
            "fixture_registration",
            challenge_key=key,
            portable=False,
            path="/fixture_registration_ref",
        )
        if registration != context.fixture_registration_ref:
            raise _invalid("/fixture_registration_ref")
        for field in (
            "validator_capacity",
            "reconstruction_funding",
            "queue_availability",
            "evidence_budget_availability",
        ):
            _exact_enum(getattr(self, field), FixtureAvailabilityState, "/type")
        marker = _exact_enum(
            self.authority_marker,
            ResourcePolicyAuthorityMarker,
            "/authority_marker",
        )
        if (
            marker
            is not ResourcePolicyAuthorityMarker.FIXTURE_AVAILABILITY_NOT_OPERATIONAL_COMMITMENT
        ):
            raise _invalid("/authority_marker")
        _require_challenge((policy_ref, class_ref, context), key)
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "policy_ref", policy_ref)
        object.__setattr__(self, "resource_class_ref", class_ref)
        object.__setattr__(self, "authority_context", context)
        object.__setattr__(self, "fixture_registration_ref", registration)


FixtureAvailabilityInput: TypeAlias = NoAvailabilityInput | FixtureResourceAvailability


def _copy_availability_input(
    value: object,
) -> FixtureAvailabilityInput:
    if type(value) is NoAvailabilityInput:
        return NoAvailabilityInput()
    if type(value) is not FixtureResourceAvailability:
        raise _wrong("/type")
    return FixtureResourceAvailability(
        value.object_kind,
        value.schema_version,
        value.canonicalization_profile,
        value.challenge_key,
        value.policy_ref,
        value.resource_class_ref,
        value.authority_context,
        value.validator_capacity,
        value.reconstruction_funding,
        value.queue_availability,
        value.evidence_budget_availability,
        value.fixture_registration_ref,
        value.authority_marker,
    )


@dataclass(frozen=True, slots=True)
class FixtureResourceDecision:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    assessment_ref: StaticResourceAssessmentRef
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    authority_context: ResourceAuthorityContext
    availability_input: FixtureAvailabilityInput
    outcome: FixtureDecisionOutcome
    deferral_causes: tuple[ResourceDeferralCause, ...]
    authority_marker: ResourcePolicyAuthorityMarker

    OBJECT_KIND: ClassVar[str] = "fixture_resource_decision"

    def __post_init__(self) -> None:
        _header(
            self,
            FixtureResourceDecision,
            self.object_kind,
            self.schema_version,
            self.canonicalization_profile,
        )
        key = _challenge(self.challenge_key)
        assessment_ref = _copy_resource_ref(
            self.assessment_ref,
            StaticResourceAssessmentRef,
            "/assessment_ref",
        )
        policy_ref = _copy_resource_ref(
            self.policy_ref,
            ResearchResourcePolicyRef,
            "/policy_ref",
        )
        class_ref = _copy_resource_ref(
            self.resource_class_ref,
            ResourceClassRef,
            "/resource_class_ref",
        )
        context = _copy_authority_context(self.authority_context, key)
        availability = _copy_availability_input(self.availability_input)
        if type(availability) is FixtureResourceAvailability and (
            availability.challenge_key != key
            or availability.policy_ref != policy_ref
            or availability.resource_class_ref != class_ref
            or availability.authority_context != context
        ):
            raise _invalid("/authority_context")
        causes = _tuple(
            self.deferral_causes,
            path="/type",
            copier=lambda item: _exact_enum(item, ResourceDeferralCause, "/type"),
            set_like=True,
        )
        outcome = _exact_enum(self.outcome, FixtureDecisionOutcome, "/type")
        if (outcome is FixtureDecisionOutcome.FIXTURE_ADMISSIBLE) != (not causes):
            raise _invalid("/type")
        marker = _exact_enum(
            self.authority_marker,
            ResourcePolicyAuthorityMarker,
            "/authority_marker",
        )
        if (
            marker
            is not ResourcePolicyAuthorityMarker.POLICY_ADMISSIBILITY_NOT_QUOTE_OR_EXECUTION
        ):
            raise _invalid("/authority_marker")
        _require_challenge((assessment_ref, policy_ref, class_ref, context), key)
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "assessment_ref", assessment_ref)
        object.__setattr__(self, "policy_ref", policy_ref)
        object.__setattr__(self, "resource_class_ref", class_ref)
        object.__setattr__(self, "authority_context", context)
        object.__setattr__(self, "availability_input", availability)
        object.__setattr__(self, "deferral_causes", causes)


@dataclass(frozen=True, slots=True)
class NoIssue:
    def __post_init__(self) -> None:
        _exact_self(self, NoIssue)


NO_ISSUE = NoIssue()
EnforcementIssueBinding: TypeAlias = NoIssue | ResourcePolicyIssue


@dataclass(frozen=True, slots=True)
class ResourceEnforcementEvent:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    construction_plan_ref: ResolvedConstructionPlanRef
    assessment_ref: StaticResourceAssessmentRef
    decision_ref: FixtureResourceDecisionRef
    authority_context: ResourceAuthorityContext
    limit_id: str
    enforcement_point: EnforcementPoint
    enforcement_mode: EnforcementMode
    maximum_quantity: int
    observation: ResourceEnforcementObservation
    action: ResourceEnforcementAction
    outcome: ResourceEnforcementOutcome
    issue: EnforcementIssueBinding

    OBJECT_KIND: ClassVar[str] = "resource_enforcement_event"

    def __post_init__(self) -> None:
        _header(
            self,
            ResourceEnforcementEvent,
            self.object_kind,
            self.schema_version,
            self.canonicalization_profile,
        )
        key = _challenge(self.challenge_key)
        policy_ref = _copy_resource_ref(
            self.policy_ref, ResearchResourcePolicyRef, "/policy_ref"
        )
        class_ref = _copy_resource_ref(
            self.resource_class_ref, ResourceClassRef, "/resource_class_ref"
        )
        plan_ref = _copy_construction_ref(
            self.construction_plan_ref,
            ResolvedConstructionPlanRef,
            "/construction_plan_ref",
        )
        assessment_ref = _copy_resource_ref(
            self.assessment_ref, StaticResourceAssessmentRef, "/assessment_ref"
        )
        decision_ref = _copy_resource_ref(
            self.decision_ref, FixtureResourceDecisionRef, "/fixture_decision_ref"
        )
        context = _copy_authority_context(self.authority_context, key)
        point = _exact_enum(self.enforcement_point, EnforcementPoint, "/enforcement")
        mode = _exact_enum(self.enforcement_mode, EnforcementMode, "/enforcement")
        expected_mode = {
            EnforcementPoint.PRE_ALLOCATION_READINESS: EnforcementMode.PREVENT_START_ON_EXCESS,
            EnforcementPoint.PRE_EXECUTION: EnforcementMode.PREVENT_NEXT_UNIT_ON_EXCESS,
            EnforcementPoint.RUNTIME_OBSERVATION: EnforcementMode.STOP_ON_FIRST_OBSERVED_EXCESS,
        }[point]
        if mode is not expected_mode:
            raise _invalid("/enforcement")
        if type(self.observation) is not ResourceEnforcementObservation:
            raise _wrong("/observation")
        observation = ResourceEnforcementObservation(
            _copy_observed_quantity(self.observation.metric_quantity, key),
            self.observation.observation_kind,
        )
        maximum = _uint64(self.maximum_quantity, "/maximum_quantity")
        action = _exact_enum(self.action, ResourceEnforcementAction, "/enforcement")
        outcome = _exact_enum(self.outcome, ResourceEnforcementOutcome, "/enforcement")
        if type(self.issue) is NoIssue:
            issue: EnforcementIssueBinding = NoIssue()
        elif type(self.issue) is ResourcePolicyIssue:
            issue = _copy_issue(self.issue)
        else:
            raise _wrong("/enforcement")
        over_action = {
            EnforcementMode.PREVENT_START_ON_EXCESS: ResourceEnforcementAction.PREVENT_FIXTURE_START,
            EnforcementMode.PREVENT_NEXT_UNIT_ON_EXCESS: ResourceEnforcementAction.PREVENT_NEXT_UNIT,
            EnforcementMode.STOP_ON_FIRST_OBSERVED_EXCESS: ResourceEnforcementAction.REQUEST_FIXTURE_STOP,
        }[mode]
        valid_triple = (
            (
                outcome is ResourceEnforcementOutcome.CONTINUE_FIXTURE
                and action is ResourceEnforcementAction.NO_STOP
                and type(issue) is NoIssue
            )
            or (
                outcome is ResourceEnforcementOutcome.STOPPED_OVER_LIMIT
                and action is over_action
                and type(issue) is NoIssue
            )
            or (
                outcome is ResourceEnforcementOutcome.ENFORCEMENT_FAILURE
                and action is ResourceEnforcementAction.FAIL_CLOSED
                and type(issue) is ResourcePolicyIssue
                and issue.code
                in (
                    ResourcePolicyIssueCode.LIMIT_OBSERVATION_MISMATCH,
                    ResourcePolicyIssueCode.ENFORCEMENT_EVALUATION_FAILURE,
                )
            )
        )
        if not valid_triple:
            raise _invalid("/enforcement")
        expected_observation_kind = (
            EnforcementObservationKind.CURRENT_TOTAL
            if point is EnforcementPoint.RUNTIME_OBSERVATION
            else EnforcementObservationKind.ATTEMPTED_NEXT_TOTAL
        )
        if observation.observation_kind is not expected_observation_kind and not (
            outcome is ResourceEnforcementOutcome.ENFORCEMENT_FAILURE
            and action is ResourceEnforcementAction.FAIL_CLOSED
            and type(issue) is ResourcePolicyIssue
            and issue.code is ResourcePolicyIssueCode.LIMIT_OBSERVATION_MISMATCH
        ):
            raise _invalid("/enforcement")
        if outcome is ResourceEnforcementOutcome.CONTINUE_FIXTURE and (
            observation.metric_quantity.quantity > maximum
        ):
            raise _invalid("/enforcement")
        if outcome is ResourceEnforcementOutcome.STOPPED_OVER_LIMIT and (
            observation.metric_quantity.quantity <= maximum
        ):
            raise _invalid("/enforcement")
        _require_challenge(
            (policy_ref, class_ref, plan_ref, assessment_ref, decision_ref, context),
            key,
        )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "policy_ref", policy_ref)
        object.__setattr__(self, "resource_class_ref", class_ref)
        object.__setattr__(self, "construction_plan_ref", plan_ref)
        object.__setattr__(self, "assessment_ref", assessment_ref)
        object.__setattr__(self, "decision_ref", decision_ref)
        object.__setattr__(self, "authority_context", context)
        object.__setattr__(self, "limit_id", _identifier(self.limit_id, "/limit_id"))
        object.__setattr__(self, "maximum_quantity", maximum)
        object.__setattr__(self, "observation", observation)
        object.__setattr__(self, "issue", issue)


def _copy_enforcement_event(value: object) -> ResourceEnforcementEvent:
    if type(value) is not ResourceEnforcementEvent:
        raise _wrong("/enforcement")
    return ResourceEnforcementEvent(
        value.object_kind,
        value.schema_version,
        value.canonicalization_profile,
        value.challenge_key,
        value.policy_ref,
        value.resource_class_ref,
        value.construction_plan_ref,
        value.assessment_ref,
        value.decision_ref,
        value.authority_context,
        value.limit_id,
        value.enforcement_point,
        value.enforcement_mode,
        value.maximum_quantity,
        value.observation,
        value.action,
        value.outcome,
        value.issue,
    )


@dataclass(frozen=True, slots=True)
class ResourceEnforcementResult:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    construction_plan_ref: ResolvedConstructionPlanRef
    assessment_ref: StaticResourceAssessmentRef
    decision_ref: FixtureResourceDecisionRef
    authority_context: ResourceAuthorityContext
    event: ResourceEnforcementEvent
    outcome: ResourceEnforcementOutcome
    authority_marker: ResourcePolicyAuthorityMarker

    OBJECT_KIND: ClassVar[str] = "resource_enforcement_result"

    def __post_init__(self) -> None:
        _header(
            self,
            ResourceEnforcementResult,
            self.object_kind,
            self.schema_version,
            self.canonicalization_profile,
        )
        key = _challenge(self.challenge_key)
        policy_ref = _copy_resource_ref(
            self.policy_ref, ResearchResourcePolicyRef, "/policy_ref"
        )
        class_ref = _copy_resource_ref(
            self.resource_class_ref, ResourceClassRef, "/resource_class_ref"
        )
        plan_ref = _copy_construction_ref(
            self.construction_plan_ref,
            ResolvedConstructionPlanRef,
            "/construction_plan_ref",
        )
        assessment_ref = _copy_resource_ref(
            self.assessment_ref, StaticResourceAssessmentRef, "/assessment_ref"
        )
        decision_ref = _copy_resource_ref(
            self.decision_ref, FixtureResourceDecisionRef, "/fixture_decision_ref"
        )
        context = _copy_authority_context(self.authority_context, key)
        event = _copy_enforcement_event(self.event)
        outcome = _exact_enum(self.outcome, ResourceEnforcementOutcome, "/enforcement")
        if (
            event.challenge_key != key
            or event.policy_ref != policy_ref
            or event.resource_class_ref != class_ref
            or event.construction_plan_ref != plan_ref
            or event.assessment_ref != assessment_ref
            or event.decision_ref != decision_ref
            or event.authority_context != context
            or event.outcome is not outcome
        ):
            raise _invalid("/enforcement")
        marker = _exact_enum(
            self.authority_marker,
            ResourcePolicyAuthorityMarker,
            "/authority_marker",
        )
        if (
            marker
            is not ResourcePolicyAuthorityMarker.RESOURCE_ENFORCEMENT_NOT_EXECUTION_OR_SCIENCE
        ):
            raise _invalid("/authority_marker")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "policy_ref", policy_ref)
        object.__setattr__(self, "resource_class_ref", class_ref)
        object.__setattr__(self, "construction_plan_ref", plan_ref)
        object.__setattr__(self, "assessment_ref", assessment_ref)
        object.__setattr__(self, "decision_ref", decision_ref)
        object.__setattr__(self, "authority_context", context)
        object.__setattr__(self, "event", event)


@dataclass(frozen=True, slots=True)
class PolicyEnforcerActor:
    policy_authority_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, PolicyEnforcerActor)
        object.__setattr__(
            self,
            "policy_authority_ref",
            _pinned_owner_unbound(
                self.policy_authority_ref,
                "policy_authority",
                "/scope_binding",
            ),
        )


@dataclass(frozen=True, slots=True)
class FixtureRequesterActor:
    fixture_registration_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, FixtureRequesterActor)
        object.__setattr__(
            self,
            "fixture_registration_ref",
            _pinned_owner_unbound(
                self.fixture_registration_ref,
                "fixture_registration",
                "/fixture_registration_ref",
            ),
        )


@dataclass(frozen=True, slots=True)
class InfrastructureActor:
    infrastructure_failure_ref: object

    def __post_init__(self) -> None:
        _exact_self(self, InfrastructureActor)
        object.__setattr__(
            self,
            "infrastructure_failure_ref",
            _pinned_owner_unbound(
                self.infrastructure_failure_ref,
                "infrastructure_failure",
                "/scope_binding",
            ),
        )


CancellationActor: TypeAlias = (
    PolicyEnforcerActor | FixtureRequesterActor | InfrastructureActor
)


@dataclass(frozen=True, slots=True)
class NoEnforcementPoint:
    def __post_init__(self) -> None:
        _exact_self(self, NoEnforcementPoint)


@dataclass(frozen=True, slots=True)
class AtEnforcementPoint:
    enforcement_point: EnforcementPoint

    def __post_init__(self) -> None:
        _exact_self(self, AtEnforcementPoint)
        _exact_enum(self.enforcement_point, EnforcementPoint, "/enforcement")


StopPointBinding: TypeAlias = NoEnforcementPoint | AtEnforcementPoint
NO_ENFORCEMENT_POINT = NoEnforcementPoint()


@dataclass(frozen=True, slots=True)
class NoEnforcementEvent:
    def __post_init__(self) -> None:
        _exact_self(self, NoEnforcementEvent)


EnforcementEventBinding: TypeAlias = NoEnforcementEvent | ResourceEnforcementEvent
NO_ENFORCEMENT_EVENT = NoEnforcementEvent()


def _copy_actor(value: object, key: ChallengeKey) -> CancellationActor:
    if type(value) is PolicyEnforcerActor:
        return PolicyEnforcerActor(
            _owner(
                value.policy_authority_ref,
                "policy_authority",
                challenge_key=key,
                portable=False,
                path="/scope_binding",
            )
        )
    if type(value) is FixtureRequesterActor:
        return FixtureRequesterActor(
            _owner(
                value.fixture_registration_ref,
                "fixture_registration",
                challenge_key=key,
                portable=False,
                path="/fixture_registration_ref",
            )
        )
    if type(value) is InfrastructureActor:
        return InfrastructureActor(
            _owner(
                value.infrastructure_failure_ref,
                "infrastructure_failure",
                challenge_key=key,
                portable=False,
                path="/scope_binding",
            )
        )
    raise _wrong("/type")


@dataclass(frozen=True, slots=True)
class ResourceCancellationRecord:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    construction_plan_ref: ResolvedConstructionPlanRef
    assessment_ref: StaticResourceAssessmentRef
    fixture_decision_ref: FixtureResourceDecisionRef
    authority_context: ResourceAuthorityContext
    stop_point: StopPointBinding
    actor: CancellationActor
    reason: CancellationReason
    enforcement_event_binding: EnforcementEventBinding
    work_started: bool
    observed_resource_quantities_so_far: tuple[ObservedResourceQuantity, ...]
    resulting_state: CancellationResultingState
    authority_marker: ResourcePolicyAuthorityMarker

    OBJECT_KIND: ClassVar[str] = "resource_cancellation_record"

    def __post_init__(self) -> None:
        _header(
            self,
            ResourceCancellationRecord,
            self.object_kind,
            self.schema_version,
            self.canonicalization_profile,
        )
        key = _challenge(self.challenge_key)
        policy_ref = _copy_resource_ref(
            self.policy_ref, ResearchResourcePolicyRef, "/policy_ref"
        )
        class_ref = _copy_resource_ref(
            self.resource_class_ref, ResourceClassRef, "/resource_class_ref"
        )
        plan_ref = _copy_construction_ref(
            self.construction_plan_ref,
            ResolvedConstructionPlanRef,
            "/construction_plan_ref",
        )
        assessment_ref = _copy_resource_ref(
            self.assessment_ref, StaticResourceAssessmentRef, "/assessment_ref"
        )
        decision_ref = _copy_resource_ref(
            self.fixture_decision_ref,
            FixtureResourceDecisionRef,
            "/fixture_decision_ref",
        )
        context = _copy_authority_context(self.authority_context, key)
        if type(self.stop_point) is NoEnforcementPoint:
            point: StopPointBinding = NoEnforcementPoint()
        elif type(self.stop_point) is AtEnforcementPoint:
            point = AtEnforcementPoint(self.stop_point.enforcement_point)
        else:
            raise _wrong("/enforcement")
        actor = _copy_actor(self.actor, key)
        reason = _exact_enum(self.reason, CancellationReason, "/type")
        if type(self.enforcement_event_binding) is NoEnforcementEvent:
            event_binding: EnforcementEventBinding = NoEnforcementEvent()
        elif type(self.enforcement_event_binding) is ResourceEnforcementEvent:
            event_binding = _copy_enforcement_event(self.enforcement_event_binding)
        else:
            raise _wrong("/enforcement")
        work_started = _exact_bool(self.work_started, "/type")
        observations = _tuple(
            self.observed_resource_quantities_so_far,
            path="/observation",
            copier=lambda item: _copy_observed_quantity(item, key),
            set_like=True,
        )
        if len({item.metric_id for item in observations}) != len(observations):
            raise _invalid("/observation")
        if not work_started and observations:
            raise _invalid("/observation")
        state = _exact_enum(self.resulting_state, CancellationResultingState, "/type")
        event = (
            event_binding if type(event_binding) is ResourceEnforcementEvent else None
        )
        if event is not None and (
            type(point) is not AtEnforcementPoint
            or point.enforcement_point is not event.enforcement_point
            or event.challenge_key != key
            or event.policy_ref != policy_ref
            or event.resource_class_ref != class_ref
            or event.construction_plan_ref != plan_ref
            or event.assessment_ref != assessment_ref
            or event.decision_ref != decision_ref
            or event.authority_context != context
        ):
            raise _invalid("/enforcement")
        if type(actor) is FixtureRequesterActor:
            valid = (
                reason is CancellationReason.REQUESTER_CANCELLED
                and state is CancellationResultingState.CANCELLED_NON_SCIENTIFIC
                and event is None
                and actor.fixture_registration_ref == context.fixture_registration_ref
                and (
                    not work_started
                    and type(point) is NoEnforcementPoint
                    or work_started
                    and type(point) is AtEnforcementPoint
                    and point.enforcement_point
                    in (
                        EnforcementPoint.PRE_EXECUTION,
                        EnforcementPoint.RUNTIME_OBSERVATION,
                    )
                )
            )
        elif type(actor) is InfrastructureActor:
            valid = (
                reason is CancellationReason.INFRASTRUCTURE_FAILURE
                and state
                is CancellationResultingState.INFRASTRUCTURE_UNAVAILABLE_NON_SCIENTIFIC
                and event is None
                and (
                    not work_started
                    and type(point) is NoEnforcementPoint
                    or work_started
                    and type(point) is AtEnforcementPoint
                    and point.enforcement_point
                    in (
                        EnforcementPoint.PRE_EXECUTION,
                        EnforcementPoint.RUNTIME_OBSERVATION,
                    )
                )
            )
        else:
            withdrawal_reasons = (
                CancellationReason.CAPACITY_WITHDRAWN,
                CancellationReason.FUNDING_WITHDRAWN,
                CancellationReason.QUEUE_WITHDRAWN,
                CancellationReason.EVIDENCE_BUDGET_WITHDRAWN,
            )
            if reason in withdrawal_reasons:
                valid = (
                    state is CancellationResultingState.EVIDENCE_DEFERRED
                    and event is None
                    and work_started
                    and type(point) is AtEnforcementPoint
                    and point.enforcement_point
                    in (
                        EnforcementPoint.PRE_EXECUTION,
                        EnforcementPoint.RUNTIME_OBSERVATION,
                    )
                )
            elif reason is CancellationReason.POLICY_LIMIT_REACHED:
                valid = (
                    state is CancellationResultingState.CANCELLED_NON_SCIENTIFIC
                    and event is not None
                    and event.outcome is ResourceEnforcementOutcome.STOPPED_OVER_LIMIT
                )
            elif reason is CancellationReason.ENFORCEMENT_FAILURE:
                valid = (
                    state is CancellationResultingState.CANCELLED_NON_SCIENTIFIC
                    and event is not None
                    and event.outcome is ResourceEnforcementOutcome.ENFORCEMENT_FAILURE
                )
            else:
                valid = False
        if event is not None:
            if event.action is ResourceEnforcementAction.PREVENT_FIXTURE_START:
                valid = valid and not work_started
            elif event.action in (
                ResourceEnforcementAction.PREVENT_NEXT_UNIT,
                ResourceEnforcementAction.REQUEST_FIXTURE_STOP,
            ):
                valid = valid and work_started
            elif event.action is ResourceEnforcementAction.FAIL_CLOSED:
                valid = (
                    valid
                    and (
                        event.enforcement_point
                        is EnforcementPoint.PRE_ALLOCATION_READINESS
                    )
                    != work_started
                )
        if not valid:
            raise _invalid("/enforcement")
        marker = _exact_enum(
            self.authority_marker,
            ResourcePolicyAuthorityMarker,
            "/authority_marker",
        )
        if (
            marker
            is not ResourcePolicyAuthorityMarker.RESOURCE_STOP_NOT_SCIENTIFIC_OUTCOME
        ):
            raise _invalid("/authority_marker")
        _require_challenge(
            (policy_ref, class_ref, plan_ref, assessment_ref, decision_ref, context),
            key,
        )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "policy_ref", policy_ref)
        object.__setattr__(self, "resource_class_ref", class_ref)
        object.__setattr__(self, "construction_plan_ref", plan_ref)
        object.__setattr__(self, "assessment_ref", assessment_ref)
        object.__setattr__(self, "fixture_decision_ref", decision_ref)
        object.__setattr__(self, "authority_context", context)
        object.__setattr__(self, "stop_point", point)
        object.__setattr__(self, "actor", actor)
        object.__setattr__(self, "enforcement_event_binding", event_binding)
        object.__setattr__(self, "work_started", work_started)
        object.__setattr__(self, "observed_resource_quantities_so_far", observations)


def _copy_identity_refs(
    *,
    challenge_key: object,
    construction_plan_ref: object,
    policy_ref: object,
    resource_class_ref: object,
) -> tuple[
    ChallengeKey,
    ResolvedConstructionPlanRef,
    ResearchResourcePolicyRef,
    ResourceClassRef,
]:
    key = _challenge(challenge_key)
    plan = _copy_construction_ref(
        construction_plan_ref,
        ResolvedConstructionPlanRef,
        "/construction_plan_ref",
    )
    policy = _copy_resource_ref(
        policy_ref,
        ResearchResourcePolicyRef,
        "/policy_ref",
    )
    resource_class = _copy_resource_ref(
        resource_class_ref,
        ResourceClassRef,
        "/resource_class_ref",
    )
    _require_challenge((plan, policy, resource_class), key)
    return key, plan, policy, resource_class


@dataclass(frozen=True, slots=True)
class IncompleteBuildIdentity:
    challenge_key: ChallengeKey
    construction_plan_ref: ResolvedConstructionPlanRef
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    execution_environment_pin: EnvironmentPin
    build_attempt_id: str
    build_attempt_digest: str

    def __post_init__(self) -> None:
        _exact_self(self, IncompleteBuildIdentity)
        key, plan, policy, resource_class = _copy_identity_refs(
            challenge_key=self.challenge_key,
            construction_plan_ref=self.construction_plan_ref,
            policy_ref=self.policy_ref,
            resource_class_ref=self.resource_class_ref,
        )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "construction_plan_ref", plan)
        object.__setattr__(self, "policy_ref", policy)
        object.__setattr__(self, "resource_class_ref", resource_class)
        object.__setattr__(
            self,
            "execution_environment_pin",
            _copy_model(
                self.execution_environment_pin, EnvironmentPin, "/resource_class"
            ),
        )
        object.__setattr__(
            self, "build_attempt_id", _identifier(self.build_attempt_id, "/object_id")
        )
        object.__setattr__(
            self,
            "build_attempt_digest",
            _digest(self.build_attempt_digest, "/content_digest"),
        )


@dataclass(frozen=True, slots=True)
class CompleteBuildIdentity:
    challenge_key: ChallengeKey
    construction_plan_ref: ResolvedConstructionPlanRef
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    execution_environment_pin: EnvironmentPin
    build_attempt_id: str
    complete_build_digest: str

    def __post_init__(self) -> None:
        _exact_self(self, CompleteBuildIdentity)
        key, plan, policy, resource_class = _copy_identity_refs(
            challenge_key=self.challenge_key,
            construction_plan_ref=self.construction_plan_ref,
            policy_ref=self.policy_ref,
            resource_class_ref=self.resource_class_ref,
        )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "construction_plan_ref", plan)
        object.__setattr__(self, "policy_ref", policy)
        object.__setattr__(self, "resource_class_ref", resource_class)
        object.__setattr__(
            self,
            "execution_environment_pin",
            _copy_model(
                self.execution_environment_pin, EnvironmentPin, "/resource_class"
            ),
        )
        object.__setattr__(
            self, "build_attempt_id", _identifier(self.build_attempt_id, "/object_id")
        )
        object.__setattr__(
            self,
            "complete_build_digest",
            _digest(self.complete_build_digest, "/content_digest"),
        )


@dataclass(frozen=True, slots=True)
class NoBuildStarted:
    def __post_init__(self) -> None:
        _exact_self(self, NoBuildStarted)


@dataclass(frozen=True, slots=True)
class IncompleteBuild:
    build_identity: IncompleteBuildIdentity

    def __post_init__(self) -> None:
        _exact_self(self, IncompleteBuild)
        if type(self.build_identity) is not IncompleteBuildIdentity:
            raise _wrong("/type")
        value = self.build_identity
        object.__setattr__(
            self,
            "build_identity",
            IncompleteBuildIdentity(
                value.challenge_key,
                value.construction_plan_ref,
                value.policy_ref,
                value.resource_class_ref,
                value.execution_environment_pin,
                value.build_attempt_id,
                value.build_attempt_digest,
            ),
        )


@dataclass(frozen=True, slots=True)
class CompleteBuild:
    build_identity: CompleteBuildIdentity

    def __post_init__(self) -> None:
        _exact_self(self, CompleteBuild)
        if type(self.build_identity) is not CompleteBuildIdentity:
            raise _wrong("/type")
        value = self.build_identity
        object.__setattr__(
            self,
            "build_identity",
            CompleteBuildIdentity(
                value.challenge_key,
                value.construction_plan_ref,
                value.policy_ref,
                value.resource_class_ref,
                value.execution_environment_pin,
                value.build_attempt_id,
                value.complete_build_digest,
            ),
        )


BuildCompletionBinding: TypeAlias = NoBuildStarted | IncompleteBuild | CompleteBuild
NO_BUILD_STARTED = NoBuildStarted()


def _copy_build_completion(value: object) -> BuildCompletionBinding:
    if type(value) is NoBuildStarted:
        return NoBuildStarted()
    if type(value) is IncompleteBuild:
        return IncompleteBuild(value.build_identity)
    if type(value) is CompleteBuild:
        return CompleteBuild(value.build_identity)
    raise _wrong("/type")


@dataclass(frozen=True, slots=True)
class NoReuse:
    def __post_init__(self) -> None:
        _exact_self(self, NoReuse)


NO_REUSE = NoReuse()


@dataclass(frozen=True, slots=True)
class FrozenArtifactReuseWindow:
    window_id: str
    complete_build_identity: CompleteBuildIdentity
    reuse_policy_ref: object
    maximum_declared_uses: int
    observed_use_ordinal: int

    def __post_init__(self) -> None:
        _exact_self(self, FrozenArtifactReuseWindow)
        if type(self.complete_build_identity) is not CompleteBuildIdentity:
            raise _wrong("/type")
        identity = CompleteBuild(self.complete_build_identity).build_identity
        reuse_ref = _owner(
            self.reuse_policy_ref,
            "restriction",
            challenge_key=identity.challenge_key,
            portable=False,
            path="/scope_binding",
        )
        maximum = _positive_uint64(self.maximum_declared_uses, "/type")
        ordinal = _uint64(self.observed_use_ordinal, "/type")
        if not 1 <= ordinal <= maximum:
            raise _invalid("/type")
        object.__setattr__(self, "window_id", _identifier(self.window_id, "/object_id"))
        object.__setattr__(self, "complete_build_identity", identity)
        object.__setattr__(self, "reuse_policy_ref", reuse_ref)
        object.__setattr__(self, "maximum_declared_uses", maximum)
        object.__setattr__(self, "observed_use_ordinal", ordinal)


ArtifactReuseBinding: TypeAlias = NoReuse | FrozenArtifactReuseWindow


@dataclass(frozen=True, slots=True)
class ReconstructionReplicateIdentity:
    challenge_key: ChallengeKey
    construction_plan_ref: ResolvedConstructionPlanRef
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    replicate_id: str
    replicate_digest: str

    def __post_init__(self) -> None:
        _exact_self(self, ReconstructionReplicateIdentity)
        key, plan, policy, resource_class = _copy_identity_refs(
            challenge_key=self.challenge_key,
            construction_plan_ref=self.construction_plan_ref,
            policy_ref=self.policy_ref,
            resource_class_ref=self.resource_class_ref,
        )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "construction_plan_ref", plan)
        object.__setattr__(self, "policy_ref", policy)
        object.__setattr__(self, "resource_class_ref", resource_class)
        object.__setattr__(
            self, "replicate_id", _identifier(self.replicate_id, "/object_id")
        )
        object.__setattr__(
            self, "replicate_digest", _digest(self.replicate_digest, "/content_digest")
        )


@dataclass(frozen=True, slots=True)
class IncompleteReconstructionReplicateIdentity:
    challenge_key: ChallengeKey
    construction_plan_ref: ResolvedConstructionPlanRef
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    replicate_attempt_id: str
    replicate_attempt_digest: str

    def __post_init__(self) -> None:
        _exact_self(self, IncompleteReconstructionReplicateIdentity)
        key, plan, policy, resource_class = _copy_identity_refs(
            challenge_key=self.challenge_key,
            construction_plan_ref=self.construction_plan_ref,
            policy_ref=self.policy_ref,
            resource_class_ref=self.resource_class_ref,
        )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "construction_plan_ref", plan)
        object.__setattr__(self, "policy_ref", policy)
        object.__setattr__(self, "resource_class_ref", resource_class)
        object.__setattr__(
            self,
            "replicate_attempt_id",
            _identifier(self.replicate_attempt_id, "/object_id"),
        )
        object.__setattr__(
            self,
            "replicate_attempt_digest",
            _digest(self.replicate_attempt_digest, "/content_digest"),
        )


@dataclass(frozen=True, slots=True)
class ReplicateNotApplicable:
    reason: ReplicateNotApplicableReason

    def __post_init__(self) -> None:
        _exact_self(self, ReplicateNotApplicable)
        _exact_enum(self.reason, ReplicateNotApplicableReason, "/type")


@dataclass(frozen=True, slots=True)
class IncompleteReconstructionReplicate:
    replicate_identity: IncompleteReconstructionReplicateIdentity

    def __post_init__(self) -> None:
        _exact_self(self, IncompleteReconstructionReplicate)
        if (
            type(self.replicate_identity)
            is not IncompleteReconstructionReplicateIdentity
        ):
            raise _wrong("/type")
        value = self.replicate_identity
        object.__setattr__(
            self,
            "replicate_identity",
            IncompleteReconstructionReplicateIdentity(
                value.challenge_key,
                value.construction_plan_ref,
                value.policy_ref,
                value.resource_class_ref,
                value.replicate_attempt_id,
                value.replicate_attempt_digest,
            ),
        )


@dataclass(frozen=True, slots=True)
class BoundReconstructionReplicate:
    replicate_identity: ReconstructionReplicateIdentity

    def __post_init__(self) -> None:
        _exact_self(self, BoundReconstructionReplicate)
        if type(self.replicate_identity) is not ReconstructionReplicateIdentity:
            raise _wrong("/type")
        value = self.replicate_identity
        object.__setattr__(
            self,
            "replicate_identity",
            ReconstructionReplicateIdentity(
                value.challenge_key,
                value.construction_plan_ref,
                value.policy_ref,
                value.resource_class_ref,
                value.replicate_id,
                value.replicate_digest,
            ),
        )


ReconstructionReplicateBinding: TypeAlias = (
    ReplicateNotApplicable
    | IncompleteReconstructionReplicate
    | BoundReconstructionReplicate
)


def _copy_replicate(value: object) -> ReconstructionReplicateBinding:
    if type(value) is ReplicateNotApplicable:
        return ReplicateNotApplicable(value.reason)
    if type(value) is IncompleteReconstructionReplicate:
        return IncompleteReconstructionReplicate(value.replicate_identity)
    if type(value) is BoundReconstructionReplicate:
        return BoundReconstructionReplicate(value.replicate_identity)
    raise _wrong("/type")


@dataclass(frozen=True, slots=True)
class NoResourceStop:
    def __post_init__(self) -> None:
        _exact_self(self, NoResourceStop)


NO_RESOURCE_STOP = NoResourceStop()
ResourceStopBinding: TypeAlias = NoResourceStop | ResourceCancellationRecordRef


def _copy_metric_binding(value: object, key: ChallengeKey) -> ObservedMetricBinding:
    if type(value) is ObservedMetricObserved:
        return ObservedMetricObserved(
            _copy_observed_quantity(value.observed_quantity, key)
        )
    if type(value) is ObservedMetricUnavailable:
        return ObservedMetricUnavailable(value.reason)
    raise _wrong("/observation")


def _identity_matches(
    value: object,
    *,
    key: ChallengeKey,
    plan_ref: ResolvedConstructionPlanRef,
    policy_ref: ResearchResourcePolicyRef,
    class_ref: ResourceClassRef,
) -> bool:
    return (
        getattr(value, "challenge_key", None) == key
        and getattr(value, "construction_plan_ref", None) == plan_ref
        and getattr(value, "policy_ref", None) == policy_ref
        and getattr(value, "resource_class_ref", None) == class_ref
    )


@dataclass(frozen=True, slots=True)
class ObservedResourceReceipt:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    construction_plan_ref: ResolvedConstructionPlanRef
    assessment_ref: StaticResourceAssessmentRef
    fixture_decision_ref: FixtureResourceDecisionRef
    authority_context: ResourceAuthorityContext
    build_completion: BuildCompletionBinding
    frozen_artifact_reuse: ArtifactReuseBinding
    reconstruction_replicate: ReconstructionReplicateBinding
    observed_consumption_quantities: tuple[ObservedResourceQuantity, ...]
    observed_latency: ObservedMetricBinding
    observed_cost: ObservedMetricBinding
    evidence_stage_label: DeclaredResourceEvidenceStage
    stop_cause: ResourceStopCause
    stop_record_binding: ResourceStopBinding
    enforcement_event_binding: EnforcementEventBinding
    work_started: bool
    epistemic_layer: ResourceEpistemicLayer
    authority_marker: ResourcePolicyAuthorityMarker

    OBJECT_KIND: ClassVar[str] = "observed_resource_receipt"

    def __post_init__(self) -> None:
        _header(
            self,
            ObservedResourceReceipt,
            self.object_kind,
            self.schema_version,
            self.canonicalization_profile,
        )
        key = _challenge(self.challenge_key)
        policy_ref = _copy_resource_ref(
            self.policy_ref, ResearchResourcePolicyRef, "/policy_ref"
        )
        class_ref = _copy_resource_ref(
            self.resource_class_ref, ResourceClassRef, "/resource_class_ref"
        )
        plan_ref = _copy_construction_ref(
            self.construction_plan_ref,
            ResolvedConstructionPlanRef,
            "/construction_plan_ref",
        )
        assessment_ref = _copy_resource_ref(
            self.assessment_ref, StaticResourceAssessmentRef, "/assessment_ref"
        )
        decision_ref = _copy_resource_ref(
            self.fixture_decision_ref,
            FixtureResourceDecisionRef,
            "/fixture_decision_ref",
        )
        context = _copy_authority_context(self.authority_context, key)
        build = _copy_build_completion(self.build_completion)
        if type(self.frozen_artifact_reuse) is NoReuse:
            reuse: ArtifactReuseBinding = NoReuse()
        elif type(self.frozen_artifact_reuse) is FrozenArtifactReuseWindow:
            value = self.frozen_artifact_reuse
            reuse = FrozenArtifactReuseWindow(
                value.window_id,
                value.complete_build_identity,
                value.reuse_policy_ref,
                value.maximum_declared_uses,
                value.observed_use_ordinal,
            )
        else:
            raise _wrong("/type")
        replicate = _copy_replicate(self.reconstruction_replicate)
        consumption = _tuple(
            self.observed_consumption_quantities,
            path="/observation",
            copier=lambda item: _copy_observed_quantity(item, key),
            set_like=True,
        )
        if len({item.metric_id for item in consumption}) != len(consumption) or any(
            item.observation_role is not ResourceObservationRole.RESOURCE_CONSUMPTION
            for item in consumption
        ):
            raise _invalid("/observation")
        latency = _copy_metric_binding(self.observed_latency, key)
        cost = _copy_metric_binding(self.observed_cost, key)
        if type(latency) is ObservedMetricObserved and (
            latency.observed_quantity.observation_role
            is not ResourceObservationRole.OBSERVED_LATENCY
        ):
            raise _invalid("/observation")
        if type(cost) is ObservedMetricObserved and (
            cost.observed_quantity.observation_role
            is not ResourceObservationRole.RESOURCE_COST_NOT_PRICE
        ):
            raise _invalid("/observation")
        stage = _exact_enum(
            self.evidence_stage_label,
            DeclaredResourceEvidenceStage,
            "/type",
        )
        cause = _exact_enum(self.stop_cause, ResourceStopCause, "/type")
        if type(self.stop_record_binding) is NoResourceStop:
            stop: ResourceStopBinding = NoResourceStop()
        elif type(self.stop_record_binding) is ResourceCancellationRecordRef:
            stop = _copy_resource_ref(
                self.stop_record_binding,
                ResourceCancellationRecordRef,
                "/ref",
            )
            if stop.challenge_key != key:
                raise _invalid("/challenge_key")
        else:
            raise _wrong("/ref")
        if type(self.enforcement_event_binding) is NoEnforcementEvent:
            event_binding: EnforcementEventBinding = NoEnforcementEvent()
        elif type(self.enforcement_event_binding) is ResourceEnforcementEvent:
            event_binding = _copy_enforcement_event(self.enforcement_event_binding)
        else:
            raise _wrong("/enforcement")
        work_started = _exact_bool(self.work_started, "/type")
        _require_challenge(
            (policy_ref, class_ref, plan_ref, assessment_ref, decision_ref, context),
            key,
        )
        identities: list[object] = []
        if type(build) in (IncompleteBuild, CompleteBuild):
            identities.append(build.build_identity)
        if type(reuse) is FrozenArtifactReuseWindow:
            identities.append(reuse.complete_build_identity)
        if type(replicate) in (
            IncompleteReconstructionReplicate,
            BoundReconstructionReplicate,
        ):
            identities.append(replicate.replicate_identity)
        if any(
            not _identity_matches(
                item,
                key=key,
                plan_ref=plan_ref,
                policy_ref=policy_ref,
                class_ref=class_ref,
            )
            for item in identities
        ):
            raise _invalid("/challenge_key")
        if type(reuse) is FrozenArtifactReuseWindow and (
            type(build) is not CompleteBuild
            or reuse.complete_build_identity != build.build_identity
        ):
            raise _invalid("/type")
        replicate_stage = stage in (
            DeclaredResourceEvidenceStage.DECLARED_RECONSTRUCTION_REPLICATE_ACCOUNTING,
            DeclaredResourceEvidenceStage.DECLARED_RANDOM_REPEAT_ACCOUNTING,
        )
        if replicate_stage != (
            type(replicate)
            in (IncompleteReconstructionReplicate, BoundReconstructionReplicate)
        ):
            raise _invalid("/type")
        if replicate_stage and (
            cause is ResourceStopCause.COMPLETED_RESOURCE_ACCOUNTING
        ) != (type(replicate) is BoundReconstructionReplicate):
            raise _invalid("/type")
        unstarted_law = (
            type(build) is NoBuildStarted
            and type(reuse) is NoReuse
            and type(replicate) is ReplicateNotApplicable
            and replicate.reason is ReplicateNotApplicableReason.NO_WORK_STARTED
            and stage is DeclaredResourceEvidenceStage.NO_WORK_STARTED
            and not consumption
            and type(latency) is ObservedMetricUnavailable
            and latency.reason is ObservationUnavailableReason.NO_WORK_STARTED
            and type(cost) is ObservedMetricUnavailable
            and cost.reason is ObservationUnavailableReason.NO_WORK_STARTED
        )
        if (not work_started) != unstarted_law:
            raise _invalid("/type")
        if work_started and (
            type(build) is NoBuildStarted
            or stage is DeclaredResourceEvidenceStage.NO_WORK_STARTED
            or type(replicate) is ReplicateNotApplicable
            and replicate.reason is ReplicateNotApplicableReason.NO_WORK_STARTED
            or type(latency) is ObservedMetricUnavailable
            and latency.reason is ObservationUnavailableReason.NO_WORK_STARTED
            or type(cost) is ObservedMetricUnavailable
            and cost.reason is ObservationUnavailableReason.NO_WORK_STARTED
        ):
            raise _invalid("/type")
        has_stop = type(stop) is ResourceCancellationRecordRef
        event = (
            event_binding if type(event_binding) is ResourceEnforcementEvent else None
        )
        if cause is ResourceStopCause.COMPLETED_RESOURCE_ACCOUNTING:
            valid_stop = (
                work_started
                and type(build) is CompleteBuild
                and bool(consumption)
                and type(latency) is ObservedMetricObserved
                and type(cost) is ObservedMetricObserved
                and not has_stop
                and event is None
            )
        elif cause is ResourceStopCause.POLICY_LIMIT_REACHED:
            valid_stop = (
                has_stop
                and event is not None
                and event.outcome is ResourceEnforcementOutcome.STOPPED_OVER_LIMIT
            )
        elif cause is ResourceStopCause.CANCELLED:
            valid_stop = has_stop and event is None
        elif cause is ResourceStopCause.ENFORCEMENT_FAILURE:
            valid_stop = (
                has_stop
                and event is not None
                and event.outcome is ResourceEnforcementOutcome.ENFORCEMENT_FAILURE
            )
        elif cause is ResourceStopCause.INFRASTRUCTURE_FAILURE:
            valid_stop = has_stop and event is None
        else:
            valid_stop = event is None and (
                not work_started and not has_stop or work_started and has_stop
            )
        if not valid_stop:
            raise _invalid("/enforcement")
        if event is not None and (
            event.challenge_key != key
            or event.policy_ref != policy_ref
            or event.resource_class_ref != class_ref
            or event.construction_plan_ref != plan_ref
            or event.assessment_ref != assessment_ref
            or event.decision_ref != decision_ref
            or event.authority_context != context
        ):
            raise _invalid("/enforcement")
        layer = _exact_enum(self.epistemic_layer, ResourceEpistemicLayer, "/type")
        if layer is not ResourceEpistemicLayer.OBSERVED_RESOURCE_RECEIPT:
            raise _invalid("/type")
        marker = _exact_enum(
            self.authority_marker,
            ResourcePolicyAuthorityMarker,
            "/authority_marker",
        )
        if (
            marker
            is not ResourcePolicyAuthorityMarker.RESOURCE_FACTS_ONLY_NOT_EVIDENCE_OR_PRICE
        ):
            raise _invalid("/authority_marker")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "policy_ref", policy_ref)
        object.__setattr__(self, "resource_class_ref", class_ref)
        object.__setattr__(self, "construction_plan_ref", plan_ref)
        object.__setattr__(self, "assessment_ref", assessment_ref)
        object.__setattr__(self, "fixture_decision_ref", decision_ref)
        object.__setattr__(self, "authority_context", context)
        object.__setattr__(self, "build_completion", build)
        object.__setattr__(self, "frozen_artifact_reuse", reuse)
        object.__setattr__(self, "reconstruction_replicate", replicate)
        object.__setattr__(self, "observed_consumption_quantities", consumption)
        object.__setattr__(self, "observed_latency", latency)
        object.__setattr__(self, "observed_cost", cost)
        object.__setattr__(self, "stop_record_binding", stop)
        object.__setattr__(self, "enforcement_event_binding", event_binding)
        object.__setattr__(self, "work_started", work_started)


__all__ = [
    "NO_AVAILABILITY_INPUT",
    "NO_BUILD_STARTED",
    "NO_ENFORCEMENT_EVENT",
    "NO_ENFORCEMENT_POINT",
    "NO_ISSUE",
    "NO_RESOURCE_STOP",
    "NO_REUSE",
    "OPERATIONAL_REQUIREMENT_REQUIRED",
    "RESOURCE_POLICY_ISSUE_MESSAGES",
    "ArtifactReuseBinding",
    "AtEnforcementPoint",
    "BoundReconstructionReplicate",
    "BuildCompletionBinding",
    "CancellationActor",
    "CancellationReason",
    "CancellationResultingState",
    "CompleteBuild",
    "CompleteBuildIdentity",
    "DeclaredResourceCeiling",
    "DeclaredResourceEvidenceStage",
    "EnforcementEventBinding",
    "EnforcementIssueBinding",
    "EnforcementMode",
    "EnforcementObservationKind",
    "EnforcementPoint",
    "FixtureAvailabilityInput",
    "FixtureAvailabilityState",
    "FixtureDecisionOutcome",
    "FixtureOfficialShapedResourceContext",
    "FixturePracticeResourceContext",
    "FixtureRequesterActor",
    "FixtureResourceAvailability",
    "FixtureResourceDecision",
    "FixtureResourceProvenance",
    "FrozenArtifactReuseWindow",
    "IncompleteBuild",
    "IncompleteBuildIdentity",
    "IncompleteReconstructionReplicate",
    "IncompleteReconstructionReplicateIdentity",
    "InfrastructureActor",
    "NoAvailabilityInput",
    "NoBuildStarted",
    "NoEnforcementEvent",
    "NoEnforcementPoint",
    "NoIssue",
    "NoResourceStop",
    "NoReuse",
    "ObservationUnavailableReason",
    "ObservedMetricBinding",
    "ObservedMetricObserved",
    "ObservedMetricUnavailable",
    "ObservedResourceQuantity",
    "ObservedResourceReceipt",
    "OperationalReadinessRequirements",
    "OperationalRequirementDisposition",
    "OperationalRequirementNotApplicable",
    "OperationalRequirementRequired",
    "PolicyEnforcerActor",
    "ReconstructionReplicateBinding",
    "ReconstructionReplicateIdentity",
    "ReplicateNotApplicable",
    "ReplicateNotApplicableReason",
    "ResearchResourcePolicy",
    "ResourceAuthorityContext",
    "ResourceCancellationRecord",
    "ResourceClass",
    "ResourceClassPolicyBinding",
    "ResourceDeferralCause",
    "ResourceEnforcementAction",
    "ResourceEnforcementEvent",
    "ResourceEnforcementObservation",
    "ResourceEnforcementOutcome",
    "ResourceEnforcementResult",
    "ResourceEpistemicLayer",
    "ResourceObservationMetric",
    "ResourceObservationRole",
    "ResourcePolicyAuthorityMarker",
    "ResourcePolicyIssue",
    "ResourcePolicyIssueCode",
    "ResourceStopBinding",
    "ResourceStopCause",
    "RuntimeResourceLimit",
    "StaticAssessmentOutcome",
    "StaticResourceAssessment",
    "StopPointBinding",
    "UnknownOrInvalidPolicy",
    "make_resource_policy_issue",
]
