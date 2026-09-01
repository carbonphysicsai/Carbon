"""Positive, categorical public projections for the B-04 runtime.

Protected reference records are never redacted in place.  The two factories in
this module first reconstruct an exact protected source, require a separately
issued disclosure-policy capability, and then create a fresh audience-owned
value containing only the fixed categorical allow-list below.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from enum import Enum
from threading import RLock
from typing import Protocol
from weakref import WeakKeyDictionary

from carbon.authoring.errors import AuthoringError

from .canonical import canonical_bytes, decode_canonical_bytes
from .enums import (
    ConditioningStatus,
    ReferenceAuthorityFunction,
    ReferenceAuthorityTargetKind,
    ReferenceCompositionKind,
    ReferenceFailureReason,
    ReferenceGrantBindingKind,
    ReferenceRunOutcome,
    ReferenceSourceClass,
    SupportApplicabilityStatus,
    UncertaintyStatus,
)
from .errors import (
    ReferenceDisclosureCode,
    ReferenceDisclosureError,
    ReferenceValidationError,
)
from .execution import (
    PrimaryRunGrant,
    ReferenceRunRecord,
    WitnessRunGrant,
    select_run_terminal,
)
from .model import ProtectedReferenceValue, owner
from .policy import ReferencePolicy
from .refs import (
    REFERENCE_TRUTH_SCHEMA_VERSION,
    ReferencePolicyRef,
    ReferenceRunRecordRef,
    require_reference_truth_ref,
)


class _ReferenceProjectionKind(str, Enum):
    POLICY = "POLICY"
    OUTCOME = "OUTCOME"


_PUBLIC_PROJECTION_TOKEN = object()
_DISCLOSURE_AUTHORITY_TOKEN = object()


def _disclosure_error(
    code: ReferenceDisclosureCode,
) -> ReferenceDisclosureError:
    return ReferenceDisclosureError(code, path="/projection")


def _copy_policy_ref(value: object, challenge_key: object) -> object:
    try:
        return owner(
            value,
            "disclosure_policy",
            "/disclosure_policy_ref",
            challenge_key=challenge_key,
        )
    except (
        AttributeError,
        AuthoringError,
        ReferenceValidationError,
        TypeError,
        ValueError,
    ):
        raise _disclosure_error(
            ReferenceDisclosureCode.DISCLOSURE_POLICY_REQUIRED
        ) from None


def _copy_source(value: object, expected_type: type) -> object:
    if type(value) is not expected_type:
        raise _disclosure_error(ReferenceDisclosureCode.SOURCE_RECORD_REQUIRED)
    try:
        return decode_canonical_bytes(canonical_bytes(value), expected_type)
    except (
        AttributeError,
        AuthoringError,
        ReferenceValidationError,
        TypeError,
        ValueError,
    ):
        raise _disclosure_error(
            ReferenceDisclosureCode.SOURCE_RECORD_REQUIRED
        ) from None


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceDisclosureVerificationEcho(ProtectedReferenceValue):
    """Exact positive echo from the separately controlled policy registry."""

    disclosure_policy_ref: object
    projection_kind: _ReferenceProjectionKind
    source_ref: ReferencePolicyRef | ReferenceRunRecordRef

    def __post_init__(self) -> None:
        if type(self) is not ReferenceDisclosureVerificationEcho:
            raise TypeError("disclosure verification echo has the wrong exact type")
        if type(self.projection_kind) is not _ReferenceProjectionKind:
            raise TypeError("projection kind has the wrong exact type")
        expected_ref = (
            ReferencePolicyRef
            if self.projection_kind is _ReferenceProjectionKind.POLICY
            else ReferenceRunRecordRef
        )
        checked_ref = require_reference_truth_ref(
            self.source_ref,
            expected_ref,
            path="/ref",
        )
        checked_policy = _copy_policy_ref(
            self.disclosure_policy_ref,
            checked_ref.challenge_key,
        )
        object.__setattr__(self, "source_ref", checked_ref)
        object.__setattr__(self, "disclosure_policy_ref", checked_policy)


class ReferenceDisclosureRegistryAuthority(Protocol):
    """Trusted registry seam that positively permits an exact projection."""

    def verify_reference_disclosure(
        self,
        *,
        disclosure_policy_ref: object,
        projection_kind: _ReferenceProjectionKind,
        source_ref: ReferencePolicyRef | ReferenceRunRecordRef,
    ) -> ReferenceDisclosureVerificationEcho:
        """Return the exact active positive policy/source binding."""
        ...


def _build_disclosure_authority_state_operations():
    """Close mutable capability state over identity-keyed operations only."""

    lock = RLock()
    states: WeakKeyDictionary[
        object, tuple[ReferenceDisclosureRegistryAuthority, object]
    ] = WeakKeyDictionary()

    def state_for(
        capability: object,
    ) -> tuple[ReferenceDisclosureRegistryAuthority, object]:
        if type(capability) is not ReferenceDisclosureAuthority:
            raise TypeError("disclosure authority has the wrong exact type")
        with lock:
            try:
                return states[capability]
            except (KeyError, TypeError):
                raise TypeError(
                    "disclosure authority requires controlled issuance"
                ) from None

    def register(
        capability: object,
        authority: ReferenceDisclosureRegistryAuthority,
        disclosure_policy_ref: object,
    ) -> None:
        if type(capability) is not ReferenceDisclosureAuthority:
            raise TypeError("disclosure authority has the wrong exact type")
        with lock:
            if capability in states:
                raise TypeError("disclosure authority is already initialized")
            states[capability] = (authority, disclosure_policy_ref)

    def copy_policy(capability: object) -> object:
        _, disclosure_policy_ref = state_for(capability)
        return _copy_policy_ref(disclosure_policy_ref, None)

    def verify(
        capability: object,
        *,
        disclosure_policy_ref: object,
        projection_kind: _ReferenceProjectionKind,
        source_ref: ReferencePolicyRef | ReferenceRunRecordRef,
    ) -> object:
        authority, registered_policy_ref = state_for(capability)
        if (
            type(disclosure_policy_ref) is not type(registered_policy_ref)
            or disclosure_policy_ref != registered_policy_ref
        ):
            raise ValueError("disclosure policy does not match the capability")
        return authority.verify_reference_disclosure(
            disclosure_policy_ref=disclosure_policy_ref,
            projection_kind=projection_kind,
            source_ref=source_ref,
        )

    return register, copy_policy, verify


(
    _register_disclosure_authority,
    _copy_disclosure_authority_policy,
    _verify_disclosure_authority,
) = _build_disclosure_authority_state_operations()
del _build_disclosure_authority_state_operations


class ReferenceDisclosureAuthority(ProtectedReferenceValue):
    """State-externalized capability bound to one disclosure policy."""

    __slots__ = ("__weakref__",)

    def __init__(
        self,
        *,
        _token: object,
        disclosure_policy_ref: object,
        authority: ReferenceDisclosureRegistryAuthority,
    ) -> None:
        if _token is not _DISCLOSURE_AUTHORITY_TOKEN:
            raise PermissionError("disclosure authority requires controlled issuance")
        checked_policy = _copy_policy_ref(disclosure_policy_ref, None)
        try:
            verifier = object.__getattribute__(
                authority,
                "verify_reference_disclosure",
            )
        except (AttributeError, TypeError):
            verifier = None
        if not callable(verifier):
            raise TypeError(
                "disclosure registry authority must provide "
                "verify_reference_disclosure"
            )
        _register_disclosure_authority(self, authority, checked_policy)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise FrozenInstanceError("disclosure authority is immutable")

    @property
    def disclosure_policy_ref(self) -> object:
        return _copy_disclosure_authority_policy(self)

    def require_projection(
        self,
        *,
        disclosure_policy_ref: object,
        projection_kind: _ReferenceProjectionKind,
        source_ref: ReferencePolicyRef | ReferenceRunRecordRef,
    ) -> None:
        if type(projection_kind) is not _ReferenceProjectionKind:
            raise TypeError("projection kind has the wrong exact type")
        expected_ref = (
            ReferencePolicyRef
            if projection_kind is _ReferenceProjectionKind.POLICY
            else ReferenceRunRecordRef
        )
        checked_ref = require_reference_truth_ref(
            source_ref,
            expected_ref,
            path="/ref",
        )
        checked_policy = _copy_policy_ref(
            disclosure_policy_ref,
            checked_ref.challenge_key,
        )
        result = _verify_disclosure_authority(
            self,
            disclosure_policy_ref=checked_policy,
            projection_kind=projection_kind,
            source_ref=checked_ref,
        )
        if type(result) is not ReferenceDisclosureVerificationEcho:
            raise TypeError("disclosure verification has the wrong exact type")
        result = ReferenceDisclosureVerificationEcho(
            result.disclosure_policy_ref,
            result.projection_kind,
            result.source_ref,
        )
        if (
            result.projection_kind is not projection_kind
            or type(result.source_ref) is not type(checked_ref)
            or result.source_ref != checked_ref
            or type(result.disclosure_policy_ref) is not type(checked_policy)
            or result.disclosure_policy_ref != checked_policy
        ):
            raise ValueError("disclosure verification does not match the request")


def _issue_reference_disclosure_authority(
    *,
    disclosure_policy_ref: object,
    authority: ReferenceDisclosureRegistryAuthority,
) -> ReferenceDisclosureAuthority:
    """Bind a trusted registry adapter to one exact disclosure policy."""

    return ReferenceDisclosureAuthority(
        _token=_DISCLOSURE_AUTHORITY_TOKEN,
        disclosure_policy_ref=disclosure_policy_ref,
        authority=authority,
    )


@dataclass(frozen=True, slots=True, repr=False, init=False)
class PublicReferencePolicyProjection:
    """Fresh public copy of the policy's two non-reversible categories."""

    schema_version: str
    answer_key_target_kind: ReferenceAuthorityTargetKind
    composition_kind: ReferenceCompositionKind

    def __init__(
        self,
        *,
        schema_version: str,
        answer_key_target_kind: ReferenceAuthorityTargetKind,
        composition_kind: ReferenceCompositionKind,
        _token: object,
    ) -> None:
        if (
            type(self) is not PublicReferencePolicyProjection
            or _token is not _PUBLIC_PROJECTION_TOKEN
        ):
            raise TypeError("public policy projections require the validated factory")
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "answer_key_target_kind", answer_key_target_kind)
        object.__setattr__(self, "composition_kind", composition_kind)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self) is not PublicReferencePolicyProjection:
            raise TypeError("public policy projection subclasses are rejected")
        if (
            type(self.schema_version) is not str
            or self.schema_version != REFERENCE_TRUTH_SCHEMA_VERSION
        ):
            raise TypeError("public policy projection schema is invalid")
        if type(self.answer_key_target_kind) is not ReferenceAuthorityTargetKind:
            raise TypeError("answer-key target kind has the wrong exact type")
        if type(self.composition_kind) is not ReferenceCompositionKind:
            raise TypeError("composition kind has the wrong exact type")
        expected_composition = (
            ReferenceCompositionKind.SINGLE_ENTRY
            if self.answer_key_target_kind
            is ReferenceAuthorityTargetKind.SINGLE_PRIMARY_ENTRY
            else ReferenceCompositionKind.REGISTERED_HYBRID_POLICY
        )
        if self.composition_kind is not expected_composition:
            raise ValueError("policy projection categories are incompatible")

    def __repr__(self) -> str:
        return "PublicReferencePolicyProjection(<public>)"

    __str__ = __repr__

    def __reduce__(self):
        return self.__reduce_ex__(4)

    def __reduce_ex__(self, protocol: int):
        del protocol
        self.__post_init__()
        return (
            _restore_public_reference_policy_projection,
            (
                self.schema_version,
                self.answer_key_target_kind,
                self.composition_kind,
            ),
        )

    @classmethod
    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("public policy projections cannot be subclassed")


@dataclass(frozen=True, slots=True, repr=False, init=False)
class PublicReferenceOutcomeProjection:
    """Fresh public copy of one run's categorical terminal facts."""

    schema_version: str
    authority_function: ReferenceAuthorityFunction
    source_class: ReferenceSourceClass
    outcome: ReferenceRunOutcome
    reason: ReferenceFailureReason | None
    applicability_status: SupportApplicabilityStatus
    conditioning_status: ConditioningStatus
    uncertainty_status: UncertaintyStatus

    def __init__(
        self,
        *,
        schema_version: str,
        authority_function: ReferenceAuthorityFunction,
        source_class: ReferenceSourceClass,
        outcome: ReferenceRunOutcome,
        reason: ReferenceFailureReason | None,
        applicability_status: SupportApplicabilityStatus,
        conditioning_status: ConditioningStatus,
        uncertainty_status: UncertaintyStatus,
        _token: object,
    ) -> None:
        if (
            type(self) is not PublicReferenceOutcomeProjection
            or _token is not _PUBLIC_PROJECTION_TOKEN
        ):
            raise TypeError("public outcome projections require the validated factory")
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "authority_function", authority_function)
        object.__setattr__(self, "source_class", source_class)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "applicability_status", applicability_status)
        object.__setattr__(self, "conditioning_status", conditioning_status)
        object.__setattr__(self, "uncertainty_status", uncertainty_status)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self) is not PublicReferenceOutcomeProjection:
            raise TypeError("public outcome projection subclasses are rejected")
        if (
            type(self.schema_version) is not str
            or self.schema_version != REFERENCE_TRUTH_SCHEMA_VERSION
        ):
            raise TypeError("public outcome projection schema is invalid")
        for value, expected, message in (
            (
                self.authority_function,
                ReferenceAuthorityFunction,
                "authority function",
            ),
            (self.source_class, ReferenceSourceClass, "source class"),
            (self.outcome, ReferenceRunOutcome, "run outcome"),
            (
                self.applicability_status,
                SupportApplicabilityStatus,
                "applicability status",
            ),
            (
                self.conditioning_status,
                ConditioningStatus,
                "conditioning status",
            ),
            (
                self.uncertainty_status,
                UncertaintyStatus,
                "uncertainty status",
            ),
        ):
            if type(value) is not expected:
                raise TypeError(f"{message} has the wrong exact type")
        if self.outcome is ReferenceRunOutcome.SUPPORTED:
            if self.reason is not None:
                raise ValueError("supported public outcome cannot carry a reason")
        else:
            if type(self.reason) is not ReferenceFailureReason:
                raise TypeError("failure reason has the wrong exact type")
            selected_outcome, _ = select_run_terminal((self.reason,))
            if selected_outcome is not self.outcome:
                raise ValueError("public outcome and reason are incompatible")

    def __repr__(self) -> str:
        return "PublicReferenceOutcomeProjection(<public>)"

    __str__ = __repr__

    def __reduce__(self):
        return self.__reduce_ex__(4)

    def __reduce_ex__(self, protocol: int):
        del protocol
        self.__post_init__()
        return (
            _restore_public_reference_outcome_projection,
            (
                self.schema_version,
                self.authority_function,
                self.source_class,
                self.outcome,
                self.reason,
                self.applicability_status,
                self.conditioning_status,
                self.uncertainty_status,
            ),
        )

    @classmethod
    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("public outcome projections cannot be subclassed")


def _restore_public_reference_policy_projection(
    schema_version: str,
    answer_key_target_kind: ReferenceAuthorityTargetKind,
    composition_kind: ReferenceCompositionKind,
) -> PublicReferencePolicyProjection:
    return PublicReferencePolicyProjection(
        schema_version=schema_version,
        answer_key_target_kind=answer_key_target_kind,
        composition_kind=composition_kind,
        _token=_PUBLIC_PROJECTION_TOKEN,
    )


def _restore_public_reference_outcome_projection(
    schema_version: str,
    authority_function: ReferenceAuthorityFunction,
    source_class: ReferenceSourceClass,
    outcome: ReferenceRunOutcome,
    reason: ReferenceFailureReason | None,
    applicability_status: SupportApplicabilityStatus,
    conditioning_status: ConditioningStatus,
    uncertainty_status: UncertaintyStatus,
) -> PublicReferenceOutcomeProjection:
    return PublicReferenceOutcomeProjection(
        schema_version=schema_version,
        authority_function=authority_function,
        source_class=source_class,
        outcome=outcome,
        reason=reason,
        applicability_status=applicability_status,
        conditioning_status=conditioning_status,
        uncertainty_status=uncertainty_status,
        _token=_PUBLIC_PROJECTION_TOKEN,
    )


def _require_authority(
    authority: object,
    *,
    disclosure_policy_ref: object,
    projection_kind: _ReferenceProjectionKind,
    source_ref: ReferencePolicyRef | ReferenceRunRecordRef,
) -> None:
    if type(authority) is not ReferenceDisclosureAuthority:
        raise _disclosure_error(ReferenceDisclosureCode.DISCLOSURE_POLICY_REQUIRED)
    try:
        authority.require_projection(
            disclosure_policy_ref=disclosure_policy_ref,
            projection_kind=projection_kind,
            source_ref=source_ref,
        )
    except Exception:  # noqa: BLE001 - sanitize the trusted capability boundary.
        raise _disclosure_error(
            ReferenceDisclosureCode.PROJECTION_NOT_PERMITTED
        ) from None


def create_public_reference_policy_projection(
    policy: object,
    *,
    disclosure_authority: ReferenceDisclosureAuthority | None,
) -> PublicReferencePolicyProjection:
    """Create the exact policy-category allow-list after positive permission."""

    checked = _copy_source(policy, ReferencePolicy)
    if type(checked) is not ReferencePolicy:
        raise _disclosure_error(ReferenceDisclosureCode.SOURCE_RECORD_REQUIRED)
    if not checked.answer_key_authority_target.is_bound:
        raise _disclosure_error(ReferenceDisclosureCode.PROJECTION_NOT_PERMITTED)
    target = checked.answer_key_authority_target.value
    _require_authority(
        disclosure_authority,
        disclosure_policy_ref=checked.disclosure_policy_ref,
        projection_kind=_ReferenceProjectionKind.POLICY,
        source_ref=checked.to_ref(),
    )
    composition_kind = (
        ReferenceCompositionKind.SINGLE_ENTRY
        if target.kind is ReferenceAuthorityTargetKind.SINGLE_PRIMARY_ENTRY
        else ReferenceCompositionKind.REGISTERED_HYBRID_POLICY
    )
    return PublicReferencePolicyProjection(
        schema_version=REFERENCE_TRUTH_SCHEMA_VERSION,
        answer_key_target_kind=target.kind,
        composition_kind=composition_kind,
        _token=_PUBLIC_PROJECTION_TOKEN,
    )


def _copy_matching_grant(
    run: ReferenceRunRecord,
    grant: object,
) -> PrimaryRunGrant | WitnessRunGrant:
    if run.grant_binding.kind is ReferenceGrantBindingKind.PRIMARY:
        expected_type = PrimaryRunGrant
    elif run.grant_binding.kind is ReferenceGrantBindingKind.WITNESS:
        expected_type = WitnessRunGrant
    else:
        raise _disclosure_error(ReferenceDisclosureCode.SOURCE_RECORD_REQUIRED)
    checked = _copy_source(grant, expected_type)
    if type(checked) is not expected_type:
        raise _disclosure_error(ReferenceDisclosureCode.SOURCE_RECORD_REQUIRED)
    if (
        not run.grant_binding.is_bound
        or run.grant_binding.value != checked.to_ref()
        or run.answer_key_authority_target != checked.answer_key_authority_target
        or run.authority_function is not checked.authority_function
        or run.case_ref != checked.case_ref
        or run.challenge_key != checked.challenge_key
        or tuple(item.entry_ref for item in run.component_bindings)
        != checked.component_entry_refs
        or run.configuration_ref != checked.configuration_ref
        or run.environment_ref != checked.environment_ref
        or run.evidence_role_binding != checked.evidence_role_binding
        or run.execution_target.value != checked.execution_target
        or run.hardware_ref != checked.hardware_ref
        or run.implementation_ref != checked.implementation_ref
        or run.method_ref != checked.method_ref
        or run.policy_ref != checked.policy_ref
        or run.precision_ref != checked.precision_ref
        or run.representation_ref != checked.representation_ref
        or run.scope_binding != checked.scope_binding
        or run.source_class is not checked.source_class
    ):
        raise _disclosure_error(ReferenceDisclosureCode.SOURCE_RECORD_REQUIRED)
    return checked


def create_public_reference_outcome_projection(
    run: object,
    *,
    grant: object,
    disclosure_authority: ReferenceDisclosureAuthority | None,
) -> PublicReferenceOutcomeProjection:
    """Create the exact run-category allow-list after positive permission."""

    checked = _copy_source(run, ReferenceRunRecord)
    if type(checked) is not ReferenceRunRecord:
        raise _disclosure_error(ReferenceDisclosureCode.SOURCE_RECORD_REQUIRED)
    checked_grant = _copy_matching_grant(checked, grant)
    _require_authority(
        disclosure_authority,
        disclosure_policy_ref=checked_grant.disclosure_policy_ref,
        projection_kind=_ReferenceProjectionKind.OUTCOME,
        source_ref=checked.to_ref(),
    )
    reason = checked.reason.value if checked.reason.is_present else None
    return PublicReferenceOutcomeProjection(
        schema_version=REFERENCE_TRUTH_SCHEMA_VERSION,
        authority_function=checked.authority_function,
        source_class=checked.source_class,
        outcome=checked.outcome,
        reason=reason,
        applicability_status=checked.applicability_assessment.status,
        conditioning_status=checked.conditioning_assessment.status,
        uncertainty_status=checked.uncertainty_binding.status,
        _token=_PUBLIC_PROJECTION_TOKEN,
    )


__all__ = [
    "PublicReferenceOutcomeProjection",
    "PublicReferencePolicyProjection",
    "ReferenceDisclosureAuthority",
    "ReferenceDisclosureRegistryAuthority",
    "ReferenceDisclosureVerificationEcho",
    "_issue_reference_disclosure_authority",
    "create_public_reference_outcome_projection",
    "create_public_reference_policy_projection",
]
