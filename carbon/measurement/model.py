"""Immutable B-05 measurement-definition and evidence records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from carbon.authoring.primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_exact_bool,
    validate_version_token,
)
from carbon.evaluation.refs import ReferencePolicyRef
from carbon.registry.model import ChallengeKey

from .enums import (
    MEASUREMENT_EVIDENCE_ROLE_CLAIMS,
    MeasurementClaimClass,
    MeasurementDefinitionKind,
    MeasurementEvidenceRole,
    MeasurementRole,
    ScientificValueState,
    StratumApplicabilityStatus,
)
from .errors import MeasurementInputCode, MeasurementValidationError
from .refs import (
    MEASUREMENT_CANONICALIZATION_PROFILE,
    MEASUREMENT_SCHEMA_VERSION,
    MeasurementContractRef,
    MeasurementDefinitionRef,
    UncertaintyPolicyRef,
)

T = TypeVar("T")


def _invalid(
    path: str, code: MeasurementInputCode = MeasurementInputCode.INVALID_VALUE
):
    return MeasurementValidationError(code, path=path)


def _exact(value: object, expected: type[T], path: str) -> T:
    if type(value) is not expected:
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    return value


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE) from None


def _identifier(value: object, path: str) -> str:
    try:
        return validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _boolean(value: object, path: str) -> bool:
    try:
        return validate_exact_bool(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE) from None


def _same_challenge(value: ChallengeKey, expected: ChallengeKey, path: str) -> None:
    if value != expected:
        raise _invalid(path, MeasurementInputCode.CROSS_CHALLENGE)


def _definition(
    value: object,
    kind: MeasurementDefinitionKind,
    challenge_key: ChallengeKey,
    path: str,
) -> MeasurementDefinitionRef:
    ref = _exact(value, MeasurementDefinitionRef, path)
    if ref.definition_kind is not kind:
        raise _invalid(path, MeasurementInputCode.ROLE_CONFUSION)
    _same_challenge(ref.challenge_key, challenge_key, path)
    return MeasurementDefinitionRef(
        ref.challenge_key,
        ref.definition_kind,
        ref.object_id,
        ref.object_version,
        ref.content_digest,
        ref.schema_version,
        ref.canonicalization_profile,
    )


def _definition_tuple(
    value: object,
    kind: MeasurementDefinitionKind,
    challenge_key: ChallengeKey,
    path: str,
    *,
    nonempty: bool = False,
) -> tuple[MeasurementDefinitionRef, ...]:
    if type(value) is not tuple:
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS or (nonempty and not value):
        raise _invalid(path)
    copied = tuple(
        _definition(item, kind, challenge_key, f"{path}/{index}")
        for index, item in enumerate(value)
    )
    if len(set(copied)) != len(copied):
        raise _invalid(path, MeasurementInputCode.DUPLICATE_IDENTITY)
    return tuple(sorted(copied, key=_definition_sort_key))


def _definition_sort_key(ref: MeasurementDefinitionRef) -> tuple[str, ...]:
    return (
        ref.definition_kind.value,
        ref.object_id,
        ref.object_version,
        ref.content_digest,
    )


@dataclass(frozen=True, slots=True)
class ScientificValueBinding:
    """Exact approved-value ref or an explicit unresolved/inapplicable state."""

    state: ScientificValueState
    value_ref: MeasurementDefinitionRef | None = None

    def __post_init__(self) -> None:
        _exact(self.state, ScientificValueState, "/state")
        if self.state is ScientificValueState.BOUND:
            if type(self.value_ref) is not MeasurementDefinitionRef:
                raise _invalid("/value_ref", MeasurementInputCode.WRONG_TYPE)
            if (
                self.value_ref.definition_kind
                is not MeasurementDefinitionKind.SCIENTIFIC_VALUE
            ):
                raise _invalid("/value_ref", MeasurementInputCode.ROLE_CONFUSION)
        elif self.state is ScientificValueState.NOT_APPLICABLE:
            if type(self.value_ref) is not MeasurementDefinitionRef:
                raise _invalid("/value_ref", MeasurementInputCode.WRONG_TYPE)
            if (
                self.value_ref.definition_kind
                is not MeasurementDefinitionKind.APPLICABILITY_REASON
            ):
                raise _invalid("/value_ref", MeasurementInputCode.ROLE_CONFUSION)
        elif self.value_ref is not None:
            raise _invalid("/value_ref")


@dataclass(frozen=True, slots=True)
class UncertaintyPolicyBinding:
    """Exact uncertainty-policy ref or explicit unresolved state."""

    state: ScientificValueState
    policy_ref: UncertaintyPolicyRef | None = None

    def __post_init__(self) -> None:
        _exact(self.state, ScientificValueState, "/state")
        if self.state is ScientificValueState.BOUND:
            _exact(self.policy_ref, UncertaintyPolicyRef, "/policy_ref")
        elif self.state in (
            ScientificValueState.HUMAN_INPUT,
            ScientificValueState.BLOCKED_FOR_LIVE_UNTIL_SET,
        ):
            if self.policy_ref is not None:
                raise _invalid("/policy_ref")
        else:
            raise _invalid("/state")


@dataclass(frozen=True, slots=True)
class StratumApplicabilityBinding:
    stratum_ref: MeasurementDefinitionRef
    status: StratumApplicabilityStatus
    evidence_or_reason_ref: MeasurementDefinitionRef | None = None

    def __post_init__(self) -> None:
        if type(self.stratum_ref) is not MeasurementDefinitionRef:
            raise _invalid("/stratum_ref", MeasurementInputCode.WRONG_TYPE)
        if self.stratum_ref.definition_kind is not MeasurementDefinitionKind.STRATUM:
            raise _invalid("/stratum_ref", MeasurementInputCode.ROLE_CONFUSION)
        _exact(self.status, StratumApplicabilityStatus, "/status")
        expected_kind = None
        if self.status is StratumApplicabilityStatus.APPLICABLE:
            expected_kind = MeasurementDefinitionKind.APPLICABILITY_EVIDENCE
        elif self.status is StratumApplicabilityStatus.NOT_APPLICABLE:
            expected_kind = MeasurementDefinitionKind.APPLICABILITY_REASON
        if expected_kind is None:
            if self.evidence_or_reason_ref is not None:
                raise _invalid("/evidence_or_reason_ref")
        elif (
            type(self.evidence_or_reason_ref) is not MeasurementDefinitionRef
            or self.evidence_or_reason_ref.definition_kind is not expected_kind
        ):
            raise _invalid(
                "/evidence_or_reason_ref", MeasurementInputCode.ROLE_CONFUSION
            )


def _strata(
    value: object, challenge_key: ChallengeKey, path: str
) -> tuple[StratumApplicabilityBinding, ...]:
    if type(value) is not tuple or not value or len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    copied: list[StratumApplicabilityBinding] = []
    seen: set[MeasurementDefinitionRef] = set()
    for index, item in enumerate(value):
        binding = _exact(item, StratumApplicabilityBinding, f"{path}/{index}")
        _same_challenge(
            binding.stratum_ref.challenge_key, challenge_key, f"{path}/{index}"
        )
        if binding.evidence_or_reason_ref is not None:
            _same_challenge(
                binding.evidence_or_reason_ref.challenge_key,
                challenge_key,
                f"{path}/{index}/evidence_or_reason_ref",
            )
        if binding.stratum_ref in seen:
            raise _invalid(path, MeasurementInputCode.DUPLICATE_IDENTITY)
        seen.add(binding.stratum_ref)
        copied.append(binding)
    return tuple(
        sorted(copied, key=lambda item: _definition_sort_key(item.stratum_ref))
    )


@dataclass(frozen=True, slots=True)
class MeasurementContract:
    challenge_key: ChallengeKey
    measurement_id: str
    measurement_version: str
    scientific_property_ref: MeasurementDefinitionRef
    observable_refs: tuple[MeasurementDefinitionRef, ...]
    coordinate_system_ref: MeasurementDefinitionRef
    unit_ref: MeasurementDefinitionRef
    numerical_operator_ref: MeasurementDefinitionRef
    discretization_ref: MeasurementDefinitionRef
    sampling_quadrature_ref: MeasurementDefinitionRef
    normalization_ref: MeasurementDefinitionRef
    aggregation_ref: MeasurementDefinitionRef
    precision_ref: MeasurementDefinitionRef
    reference_policy_ref: ReferencePolicyRef
    numerical_floor_binding: ScientificValueBinding
    applicability_policy_ref: MeasurementDefinitionRef
    uncertainty_policy_binding: UncertaintyPolicyBinding
    stratum_applicability: tuple[StratumApplicabilityBinding, ...]
    known_limitation_refs: tuple[MeasurementDefinitionRef, ...]
    implementation_refs: tuple[MeasurementDefinitionRef, ...]
    intended_role: MeasurementRole
    fixture_origin: bool
    schema_version: str = MEASUREMENT_SCHEMA_VERSION
    canonicalization_profile: str = MEASUREMENT_CANONICALIZATION_PROFILE

    RECORD_TYPE = "measurement_contract"

    def __post_init__(self) -> None:
        if type(self) is not MeasurementContract:
            raise _invalid("/record_type", MeasurementInputCode.WRONG_TYPE)
        challenge_key = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(
            self, "measurement_id", _identifier(self.measurement_id, "/measurement_id")
        )
        object.__setattr__(
            self,
            "measurement_version",
            _version(self.measurement_version, "/measurement_version"),
        )
        fields = (
            ("scientific_property_ref", MeasurementDefinitionKind.SCIENTIFIC_PROPERTY),
            ("coordinate_system_ref", MeasurementDefinitionKind.COORDINATE_SYSTEM),
            ("unit_ref", MeasurementDefinitionKind.UNIT),
            ("numerical_operator_ref", MeasurementDefinitionKind.NUMERICAL_OPERATOR),
            ("discretization_ref", MeasurementDefinitionKind.DISCRETIZATION),
            ("sampling_quadrature_ref", MeasurementDefinitionKind.SAMPLING_QUADRATURE),
            ("normalization_ref", MeasurementDefinitionKind.NORMALIZATION),
            ("aggregation_ref", MeasurementDefinitionKind.AGGREGATION),
            ("precision_ref", MeasurementDefinitionKind.PRECISION),
            (
                "applicability_policy_ref",
                MeasurementDefinitionKind.APPLICABILITY_POLICY,
            ),
        )
        for name, kind in fields:
            object.__setattr__(
                self,
                name,
                _definition(getattr(self, name), kind, challenge_key, f"/{name}"),
            )
        object.__setattr__(
            self,
            "observable_refs",
            _definition_tuple(
                self.observable_refs,
                MeasurementDefinitionKind.OBSERVABLE,
                challenge_key,
                "/observable_refs",
                nonempty=True,
            ),
        )
        reference = _exact(
            self.reference_policy_ref, ReferencePolicyRef, "/reference_policy_ref"
        )
        _same_challenge(reference.challenge_key, challenge_key, "/reference_policy_ref")
        object.__setattr__(
            self,
            "reference_policy_ref",
            ReferencePolicyRef(
                reference.challenge_key,
                reference.content_digest,
                reference.schema_version,
                reference.canonicalization_profile,
            ),
        )
        floor = _exact(
            self.numerical_floor_binding,
            ScientificValueBinding,
            "/numerical_floor_binding",
        )
        if floor.state is ScientificValueState.NOT_APPLICABLE:
            raise _invalid("/numerical_floor_binding/state")
        if floor.value_ref is not None:
            _same_challenge(
                floor.value_ref.challenge_key,
                challenge_key,
                "/numerical_floor_binding/value_ref",
            )
        uncertainty = _exact(
            self.uncertainty_policy_binding,
            UncertaintyPolicyBinding,
            "/uncertainty_policy_binding",
        )
        if uncertainty.policy_ref is not None:
            _same_challenge(
                uncertainty.policy_ref.challenge_key,
                challenge_key,
                "/uncertainty_policy_binding/policy_ref",
            )
        object.__setattr__(
            self,
            "stratum_applicability",
            _strata(
                self.stratum_applicability, challenge_key, "/stratum_applicability"
            ),
        )
        object.__setattr__(
            self,
            "known_limitation_refs",
            _definition_tuple(
                self.known_limitation_refs,
                MeasurementDefinitionKind.KNOWN_LIMITATION,
                challenge_key,
                "/known_limitation_refs",
            ),
        )
        object.__setattr__(
            self,
            "implementation_refs",
            _definition_tuple(
                self.implementation_refs,
                MeasurementDefinitionKind.IMPLEMENTATION,
                challenge_key,
                "/implementation_refs",
                nonempty=True,
            ),
        )
        _exact(self.intended_role, MeasurementRole, "/intended_role")
        object.__setattr__(
            self, "fixture_origin", _boolean(self.fixture_origin, "/fixture_origin")
        )
        if (
            self.schema_version != MEASUREMENT_SCHEMA_VERSION
            or self.canonicalization_profile != MEASUREMENT_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")


@dataclass(frozen=True, slots=True)
class MeasurementEvidenceItem:
    evidence_id: str
    source_ref: MeasurementDefinitionRef
    role: MeasurementEvidenceRole
    supported_claims: tuple[MeasurementClaimClass, ...]
    unsupported_claims: tuple[MeasurementClaimClass, ...]
    case_scope_refs: tuple[MeasurementDefinitionRef, ...]
    stratum_scope_refs: tuple[MeasurementDefinitionRef, ...]
    fixture_origin: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _identifier(self.evidence_id, "/evidence_id")
        )
        if (
            type(self.source_ref) is not MeasurementDefinitionRef
            or self.source_ref.definition_kind
            is not MeasurementDefinitionKind.EVIDENCE_SOURCE
        ):
            raise _invalid("/source_ref", MeasurementInputCode.ROLE_CONFUSION)
        _exact(self.role, MeasurementEvidenceRole, "/role")
        supported = _claim_tuple(
            self.supported_claims, "/supported_claims", nonempty=True
        )
        unsupported = _claim_tuple(
            self.unsupported_claims, "/unsupported_claims", nonempty=True
        )
        if set(supported) & set(unsupported) or set(supported) | set(
            unsupported
        ) != set(MeasurementClaimClass):
            raise _invalid(
                "/supported_claims", MeasurementInputCode.CLAIM_MATRIX_VIOLATION
            )
        if not set(supported) <= MEASUREMENT_EVIDENCE_ROLE_CLAIMS[self.role]:
            raise _invalid(
                "/supported_claims", MeasurementInputCode.CLAIM_MATRIX_VIOLATION
            )
        object.__setattr__(self, "supported_claims", supported)
        object.__setattr__(self, "unsupported_claims", unsupported)
        challenge_key = self.source_ref.challenge_key
        object.__setattr__(
            self,
            "case_scope_refs",
            _definition_tuple(
                self.case_scope_refs,
                MeasurementDefinitionKind.CASE_SCOPE,
                challenge_key,
                "/case_scope_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "stratum_scope_refs",
            _definition_tuple(
                self.stratum_scope_refs,
                MeasurementDefinitionKind.STRATUM,
                challenge_key,
                "/stratum_scope_refs",
                nonempty=True,
            ),
        )
        object.__setattr__(
            self, "fixture_origin", _boolean(self.fixture_origin, "/fixture_origin")
        )


def _claim_tuple(
    value: object, path: str, *, nonempty: bool
) -> tuple[MeasurementClaimClass, ...]:
    if (
        type(value) is not tuple
        or (nonempty and not value)
        or len(value) > len(MeasurementClaimClass)
    ):
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    if any(type(item) is not MeasurementClaimClass for item in value):
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE)
    if len(set(value)) != len(value):
        raise _invalid(path, MeasurementInputCode.DUPLICATE_IDENTITY)
    return tuple(sorted(value, key=lambda item: item.value))


@dataclass(frozen=True, slots=True)
class MeasurementQualificationEvidence:
    challenge_key: ChallengeKey
    evidence_id: str
    evidence_version: str
    measurement_contract_ref: MeasurementContractRef
    evidence_items: tuple[MeasurementEvidenceItem, ...]
    fixture_origin: bool
    schema_version: str = MEASUREMENT_SCHEMA_VERSION
    canonicalization_profile: str = MEASUREMENT_CANONICALIZATION_PROFILE

    RECORD_TYPE = "measurement_qualification_evidence"

    def __post_init__(self) -> None:
        if type(self) is not MeasurementQualificationEvidence:
            raise _invalid("/record_type", MeasurementInputCode.WRONG_TYPE)
        challenge_key = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(
            self, "evidence_id", _identifier(self.evidence_id, "/evidence_id")
        )
        object.__setattr__(
            self,
            "evidence_version",
            _version(self.evidence_version, "/evidence_version"),
        )
        contract_ref = _exact(
            self.measurement_contract_ref,
            MeasurementContractRef,
            "/measurement_contract_ref",
        )
        _same_challenge(
            contract_ref.challenge_key, challenge_key, "/measurement_contract_ref"
        )
        if (
            type(self.evidence_items) is not tuple
            or not self.evidence_items
            or len(self.evidence_items) > MAX_CANONICAL_TUPLE_ITEMS
        ):
            raise _invalid("/evidence_items", MeasurementInputCode.WRONG_TYPE)
        items = tuple(
            _exact(item, MeasurementEvidenceItem, f"/evidence_items/{index}")
            for index, item in enumerate(self.evidence_items)
        )
        if len({item.evidence_id for item in items}) != len(items):
            raise _invalid("/evidence_items", MeasurementInputCode.DUPLICATE_IDENTITY)
        for index, item in enumerate(items):
            _same_challenge(
                item.source_ref.challenge_key,
                challenge_key,
                f"/evidence_items/{index}/source_ref",
            )
        fixture_origin = _boolean(self.fixture_origin, "/fixture_origin")
        if not fixture_origin and any(item.fixture_origin for item in items):
            raise _invalid("/evidence_items", MeasurementInputCode.FIXTURE_REQUIRED)
        object.__setattr__(
            self,
            "evidence_items",
            tuple(sorted(items, key=lambda item: item.evidence_id)),
        )
        object.__setattr__(self, "fixture_origin", fixture_origin)
        if (
            self.schema_version != MEASUREMENT_SCHEMA_VERSION
            or self.canonicalization_profile != MEASUREMENT_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")


MeasurementAuthoringObject = MeasurementContract | MeasurementQualificationEvidence


__all__ = (
    "MeasurementAuthoringObject",
    "MeasurementContract",
    "MeasurementEvidenceItem",
    "MeasurementQualificationEvidence",
    "ScientificValueBinding",
    "StratumApplicabilityBinding",
    "UncertaintyPolicyBinding",
)
