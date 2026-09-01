"""Protected request, grant, resolution, and run records for B-04.

This module deliberately has no provider discovery, dynamic execution, filesystem,
network, retry, fallback, or candidate/scoring integration.  Trusted callers supply
only already-registered identities.  The factories derive the single terminal
outcome from closed observed-fact families; decoded records are checked again by
the immutable record constructors.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import ClassVar, TypeVar

from carbon.authoring.errors import AuthoringError
from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.model import EvidenceRole
from carbon.authoring.primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_utf8_text,
    validate_version_token,
)
from carbon.authoring.refs import (
    CanonicalChallengeCaseRef,
    ChallengeScope,
    reconstruct_top_level_ref,
    require_owner_ref,
)
from carbon.registry.model import ChallengeKey

from .enums import (
    RESOLUTION_OUTCOME_REASON_COMPATIBILITY,
    RUN_OUTCOME_REASON_COMPATIBILITY,
    ConditioningStatus,
    ReferenceAuthorityFunction,
    ReferenceFailureReason,
    ReferenceIdentityKind,
    ReferenceRunOutcome,
    ReferenceSourceClass,
    ResolutionOutcome,
    ResolutionReason,
    SupportApplicabilityStatus,
    UncertaintyStatus,
)
from .errors import ReferenceInputCode, ReferenceValidationError
from .model import (
    ArtifactContentBinding,
    ConditioningAssessment,
    OptionalBinding,
    PinnedReferenceIdentity,
    QualificationBinding,
    RealizedComponentBinding,
    ReferenceAuthorityTarget,
    ReferenceExecutionTarget,
    ReferenceGrantBinding,
    ReferenceProvenance,
    ReferenceRequestBinding,
    ReferenceScopeBinding,
    ReferenceTruthRecord,
    ReferenceWitnessTarget,
    RunArtifactBinding,
    SupportApplicabilityAssessment,
    UncertaintyRepresentation,
)
from .refs import (
    PrimaryReferenceRequestRef,
    PrimaryRunGrantRef,
    ReferencePolicyEntryRef,
    ReferencePolicyRef,
    ReferenceResolutionRecordRef,
    WitnessReferenceRequestRef,
    WitnessRunGrantRef,
    reconstruct_reference_truth_ref,
)

_T = TypeVar("_T")


def _reject(path: str, code: ReferenceInputCode) -> ReferenceValidationError:
    return ReferenceValidationError(code, path=path)


def _exact(value: object, expected: type[_T], path: str) -> _T:
    if type(value) is not expected:
        raise _reject(path, ReferenceInputCode.WRONG_TYPE)
    return value


def _copy(value: object, expected: type[_T], path: str) -> _T:
    checked = _exact(value, expected, path)
    try:
        return replace(checked)
    except (AttributeError, AuthoringError, TypeError, ValueError):
        raise _reject(path, ReferenceInputCode.INVALID_VALUE) from None


def _challenge(value: object) -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AuthoringError, TypeError, ValueError):
        raise _reject("/challenge_key", ReferenceInputCode.WRONG_TYPE) from None


def _identifier(value: object, path: str) -> str:
    try:
        return validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        raise _reject(path, ReferenceInputCode.INVALID_VALUE) from None


def _version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        raise _reject(path, ReferenceInputCode.INVALID_VALUE) from None


def _text(value: object, path: str) -> str:
    try:
        return validate_utf8_text(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        raise _reject(path, ReferenceInputCode.INVALID_VALUE) from None


def _top_ref(
    value: object, expected: type[_T], challenge: ChallengeKey, path: str
) -> _T:
    if type(value) is not expected:
        raise _reject(path, ReferenceInputCode.WRONG_TYPE)
    try:
        copied = reconstruct_top_level_ref(value)
    except (AttributeError, AuthoringError, TypeError, ValueError):
        raise _reject(path, ReferenceInputCode.INVALID_VALUE) from None
    if type(copied) is not expected:
        raise _reject(path, ReferenceInputCode.WRONG_TYPE)
    if copied.challenge_key != challenge:
        raise _reject(path, ReferenceInputCode.CROSS_CHALLENGE)
    return copied  # type: ignore[return-value]


def _b04_ref(
    value: object, expected: type[_T], challenge: ChallengeKey, path: str
) -> _T:
    if type(value) is not expected:
        raise _reject(path, ReferenceInputCode.WRONG_TYPE)
    try:
        copied = reconstruct_reference_truth_ref(value)
    except (
        AttributeError,
        AuthoringError,
        ReferenceValidationError,
        TypeError,
        ValueError,
    ):
        raise _reject(path, ReferenceInputCode.INVALID_VALUE) from None
    if type(copied) is not expected:
        raise _reject(path, ReferenceInputCode.WRONG_TYPE)
    if copied.challenge_key != challenge:
        raise _reject(path, ReferenceInputCode.CROSS_CHALLENGE)
    return copied  # type: ignore[return-value]


def _owner(value: object, kind: str, challenge: ChallengeKey, path: str) -> object:
    try:
        copied = require_owner_ref(value, kind)
    except (AttributeError, AuthoringError, TypeError, ValueError):
        raise _reject(path, ReferenceInputCode.WRONG_TYPE) from None
    scope = copied.scope_binding
    if type(scope) is not ChallengeScope or scope.challenge_key != challenge:
        raise _reject(path, ReferenceInputCode.CROSS_CHALLENGE)
    return copied


def _identity(
    value: object,
    kind: ReferenceIdentityKind,
    challenge: ChallengeKey,
    path: str,
) -> PinnedReferenceIdentity:
    copied = _copy(value, PinnedReferenceIdentity, path)
    if copied.challenge_key != challenge:
        raise _reject(path, ReferenceInputCode.CROSS_CHALLENGE)
    if copied.identity_kind is not kind:
        raise _reject(path, ReferenceInputCode.ROLE_MISMATCH)
    return copied


def _scope(value: object, challenge: ChallengeKey) -> ReferenceScopeBinding:
    copied = _copy(value, ReferenceScopeBinding, "/scope_binding")
    if copied.challenge_key != challenge:
        raise _reject("/scope_binding", ReferenceInputCode.CROSS_CHALLENGE)
    return copied


def _role(value: object, challenge: ChallengeKey) -> EvidenceRoleBinding:
    checked = _exact(value, EvidenceRoleBinding, "/evidence_role_binding")
    hybrid = checked.hybrid_role_ref
    if hybrid is not None:
        hybrid = _owner(hybrid, "hybrid_evidence_role", challenge, "/hybrid_role_ref")
    try:
        return EvidenceRoleBinding(checked.role, hybrid)
    except (AuthoringError, TypeError, ValueError):
        raise _reject(
            "/evidence_role_binding", ReferenceInputCode.INVALID_VALUE
        ) from None


def _model(value: object, expected: type[_T], challenge: ChallengeKey, path: str) -> _T:
    copied = _copy(value, expected, path)
    bound_challenge = (
        object.__getattribute__(copied, "challenge_key")
        if hasattr(copied, "challenge_key")
        else None
    )
    if bound_challenge is not None and bound_challenge != challenge:
        raise _reject(path, ReferenceInputCode.CROSS_CHALLENGE)
    return copied


def _ref_tuple(
    value: object,
    expected: type[_T],
    challenge: ChallengeKey,
    path: str,
    *,
    nonempty: bool = False,
) -> tuple[_T, ...]:
    if type(value) is not tuple:
        raise _reject(path, ReferenceInputCode.WRONG_TYPE)
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _reject(path, ReferenceInputCode.INVALID_VALUE)
    if nonempty and not value:
        raise _reject(path, ReferenceInputCode.INCOMPLETE_BINDING)
    copied = tuple(
        _b04_ref(item, expected, challenge, f"{path}/{index}")
        for index, item in enumerate(value)
    )
    if len(set(copied)) != len(copied):
        raise _reject(path, ReferenceInputCode.DUPLICATE_IDENTITY)
    return copied


def _model_tuple(
    value: object,
    expected: type[_T],
    challenge: ChallengeKey,
    path: str,
    *,
    nonempty: bool = False,
) -> tuple[_T, ...]:
    if type(value) is not tuple:
        raise _reject(path, ReferenceInputCode.WRONG_TYPE)
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _reject(path, ReferenceInputCode.INVALID_VALUE)
    if nonempty and not value:
        raise _reject(path, ReferenceInputCode.INCOMPLETE_BINDING)
    copied = tuple(
        _model(item, expected, challenge, f"{path}/{index}")
        for index, item in enumerate(value)
    )
    if len(set(copied)) != len(copied):
        raise _reject(path, ReferenceInputCode.DUPLICATE_IDENTITY)
    return copied


@dataclass(frozen=True, slots=True, repr=False)
class PrimaryReferenceRequest(ReferenceTruthRecord):
    answer_key_authority_target: ReferenceAuthorityTarget
    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    disclosure_policy_ref: object
    execution_target: ReferenceAuthorityTarget
    idempotency_ref: PinnedReferenceIdentity
    policy_ref: ReferencePolicyRef
    representation_ref: PinnedReferenceIdentity
    request_id: str
    request_version: str
    requested_resource_policy_ref: object
    scope_binding: ReferenceScopeBinding

    OBJECT_KIND: ClassVar[str] = "primary_reference_request"

    def __post_init__(self) -> None:
        if type(self) is not PrimaryReferenceRequest:
            raise _reject("/record", ReferenceInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        answer = _model(
            self.answer_key_authority_target,
            ReferenceAuthorityTarget,
            challenge,
            "/answer_key_authority_target",
        )
        execution = _model(
            self.execution_target,
            ReferenceAuthorityTarget,
            challenge,
            "/execution_target",
        )
        if answer != execution:
            raise _reject("/execution_target", ReferenceInputCode.STALE_BINDING)
        object.__setattr__(self, "answer_key_authority_target", answer)
        object.__setattr__(self, "execution_target", execution)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self,
            "case_ref",
            _top_ref(self.case_ref, CanonicalChallengeCaseRef, challenge, "/case_ref"),
        )
        object.__setattr__(
            self,
            "disclosure_policy_ref",
            _owner(
                self.disclosure_policy_ref,
                "disclosure_policy",
                challenge,
                "/disclosure_policy_ref",
            ),
        )
        object.__setattr__(
            self,
            "idempotency_ref",
            _identity(
                self.idempotency_ref,
                ReferenceIdentityKind.DETERMINISTIC_MODE,
                challenge,
                "/idempotency_ref",
            ),
        )
        object.__setattr__(
            self,
            "policy_ref",
            _b04_ref(self.policy_ref, ReferencePolicyRef, challenge, "/policy_ref"),
        )
        object.__setattr__(
            self,
            "representation_ref",
            _identity(
                self.representation_ref,
                ReferenceIdentityKind.REPRESENTATION,
                challenge,
                "/representation_ref",
            ),
        )
        object.__setattr__(
            self, "request_id", _identifier(self.request_id, "/request_id")
        )
        object.__setattr__(
            self, "request_version", _version(self.request_version, "/request_version")
        )
        object.__setattr__(
            self,
            "requested_resource_policy_ref",
            _owner(
                self.requested_resource_policy_ref,
                "reference_resource_limit",
                challenge,
                "/requested_resource_policy_ref",
            ),
        )
        object.__setattr__(self, "scope_binding", _scope(self.scope_binding, challenge))


@dataclass(frozen=True, slots=True, repr=False)
class WitnessReferenceRequest(ReferenceTruthRecord):
    answer_key_authority_target: ReferenceAuthorityTarget
    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    disclosure_policy_ref: object
    execution_target: ReferenceWitnessTarget
    idempotency_ref: PinnedReferenceIdentity
    policy_ref: ReferencePolicyRef
    representation_ref: PinnedReferenceIdentity
    request_id: str
    request_version: str
    requested_resource_policy_ref: object
    scope_binding: ReferenceScopeBinding

    OBJECT_KIND: ClassVar[str] = "witness_reference_request"

    def __post_init__(self) -> None:
        if type(self) is not WitnessReferenceRequest:
            raise _reject("/record", ReferenceInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(
            self,
            "answer_key_authority_target",
            _model(
                self.answer_key_authority_target,
                ReferenceAuthorityTarget,
                challenge,
                "/answer_key_authority_target",
            ),
        )
        object.__setattr__(
            self,
            "execution_target",
            _model(
                self.execution_target,
                ReferenceWitnessTarget,
                challenge,
                "/execution_target",
            ),
        )
        if set(_target_entry_refs(self.answer_key_authority_target)) & set(
            _target_entry_refs(self.execution_target)
        ):
            raise _reject("/execution_target", ReferenceInputCode.ROLE_MISMATCH)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self,
            "case_ref",
            _top_ref(self.case_ref, CanonicalChallengeCaseRef, challenge, "/case_ref"),
        )
        object.__setattr__(
            self,
            "disclosure_policy_ref",
            _owner(
                self.disclosure_policy_ref,
                "disclosure_policy",
                challenge,
                "/disclosure_policy_ref",
            ),
        )
        object.__setattr__(
            self,
            "idempotency_ref",
            _identity(
                self.idempotency_ref,
                ReferenceIdentityKind.DETERMINISTIC_MODE,
                challenge,
                "/idempotency_ref",
            ),
        )
        object.__setattr__(
            self,
            "policy_ref",
            _b04_ref(self.policy_ref, ReferencePolicyRef, challenge, "/policy_ref"),
        )
        object.__setattr__(
            self,
            "representation_ref",
            _identity(
                self.representation_ref,
                ReferenceIdentityKind.REPRESENTATION,
                challenge,
                "/representation_ref",
            ),
        )
        object.__setattr__(
            self, "request_id", _identifier(self.request_id, "/request_id")
        )
        object.__setattr__(
            self, "request_version", _version(self.request_version, "/request_version")
        )
        object.__setattr__(
            self,
            "requested_resource_policy_ref",
            _owner(
                self.requested_resource_policy_ref,
                "reference_resource_limit",
                challenge,
                "/requested_resource_policy_ref",
            ),
        )
        object.__setattr__(self, "scope_binding", _scope(self.scope_binding, challenge))


@dataclass(frozen=True, slots=True, repr=False)
class PrimaryRunGrant(ReferenceTruthRecord):
    answer_key_authority_target: ReferenceAuthorityTarget
    authority_function: ReferenceAuthorityFunction
    capability_ref: PinnedReferenceIdentity
    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    component_entry_refs: tuple[ReferencePolicyEntryRef, ...]
    configuration_ref: PinnedReferenceIdentity
    disclosure_policy_ref: object
    environment_ref: PinnedReferenceIdentity
    evidence_role_binding: EvidenceRoleBinding
    execution_target: ReferenceAuthorityTarget
    grant_id: str
    grant_version: str
    hardware_ref: PinnedReferenceIdentity
    implementation_ref: PinnedReferenceIdentity
    issuance_token: str
    issuer_ref: PinnedReferenceIdentity
    method_ref: PinnedReferenceIdentity
    policy_ref: ReferencePolicyRef
    precision_ref: PinnedReferenceIdentity
    representation_ref: PinnedReferenceIdentity
    request_ref: PrimaryReferenceRequestRef
    resource_authorization_ref: PinnedReferenceIdentity
    scope_binding: ReferenceScopeBinding
    source_class: ReferenceSourceClass

    OBJECT_KIND: ClassVar[str] = "primary_run_grant"

    def __post_init__(self) -> None:
        if type(self) is not PrimaryRunGrant:
            raise _reject("/grant", ReferenceInputCode.WRONG_TYPE)
        challenge = _validate_grant_common(self, "primary_run_grant")
        if self.authority_function is not ReferenceAuthorityFunction.PRIMARY:
            raise _reject("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
        object.__setattr__(
            self,
            "execution_target",
            _model(
                self.execution_target,
                ReferenceAuthorityTarget,
                challenge,
                "/execution_target",
            ),
        )
        if self.answer_key_authority_target != self.execution_target:
            raise _reject("/execution_target", ReferenceInputCode.STALE_BINDING)
        object.__setattr__(
            self,
            "request_ref",
            _b04_ref(
                self.request_ref, PrimaryReferenceRequestRef, challenge, "/request_ref"
            ),
        )


@dataclass(frozen=True, slots=True, repr=False)
class WitnessRunGrant(ReferenceTruthRecord):
    answer_key_authority_target: ReferenceAuthorityTarget
    authority_function: ReferenceAuthorityFunction
    capability_ref: PinnedReferenceIdentity
    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    component_entry_refs: tuple[ReferencePolicyEntryRef, ...]
    configuration_ref: PinnedReferenceIdentity
    disclosure_policy_ref: object
    environment_ref: PinnedReferenceIdentity
    evidence_role_binding: EvidenceRoleBinding
    execution_target: ReferenceWitnessTarget
    grant_id: str
    grant_version: str
    hardware_ref: PinnedReferenceIdentity
    implementation_ref: PinnedReferenceIdentity
    issuance_token: str
    issuer_ref: PinnedReferenceIdentity
    method_ref: PinnedReferenceIdentity
    policy_ref: ReferencePolicyRef
    precision_ref: PinnedReferenceIdentity
    representation_ref: PinnedReferenceIdentity
    request_ref: WitnessReferenceRequestRef
    resource_authorization_ref: PinnedReferenceIdentity
    scope_binding: ReferenceScopeBinding
    source_class: ReferenceSourceClass

    OBJECT_KIND: ClassVar[str] = "witness_run_grant"

    def __post_init__(self) -> None:
        if type(self) is not WitnessRunGrant:
            raise _reject("/grant", ReferenceInputCode.WRONG_TYPE)
        challenge = _validate_grant_common(self, "witness_run_grant")
        if (
            self.authority_function
            is not ReferenceAuthorityFunction.CORROBORATING_WITNESS
        ):
            raise _reject("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
        object.__setattr__(
            self,
            "execution_target",
            _model(
                self.execution_target,
                ReferenceWitnessTarget,
                challenge,
                "/execution_target",
            ),
        )
        object.__setattr__(
            self,
            "request_ref",
            _b04_ref(
                self.request_ref, WitnessReferenceRequestRef, challenge, "/request_ref"
            ),
        )
        if set(self.component_entry_refs) & set(
            _target_entry_refs(self.answer_key_authority_target)
        ):
            raise _reject("/component_entry_refs", ReferenceInputCode.ROLE_MISMATCH)


def _target_entry_refs(target: object) -> tuple[ReferencePolicyEntryRef, ...]:
    """Return the directly named entry for a single target, else no inferred members."""

    if type(target) not in (ReferenceAuthorityTarget, ReferenceWitnessTarget):
        return ()
    return target.expanded_entry_refs


def _validate_grant_common(grant: object, object_kind: str) -> ChallengeKey:
    if grant.object_kind != object_kind:
        raise _reject("/object_kind", ReferenceInputCode.INVALID_VALUE)
    challenge = _challenge(grant.challenge_key)
    object.__setattr__(grant, "challenge_key", challenge)
    object.__setattr__(
        grant,
        "answer_key_authority_target",
        _model(
            grant.answer_key_authority_target,
            ReferenceAuthorityTarget,
            challenge,
            "/answer_key_authority_target",
        ),
    )
    object.__setattr__(
        grant,
        "authority_function",
        _exact(
            grant.authority_function, ReferenceAuthorityFunction, "/authority_function"
        ),
    )
    object.__setattr__(
        grant,
        "capability_ref",
        _identity(
            grant.capability_ref,
            ReferenceIdentityKind.RUN_ISSUER,
            challenge,
            "/capability_ref",
        ),
    )
    object.__setattr__(
        grant,
        "case_ref",
        _top_ref(grant.case_ref, CanonicalChallengeCaseRef, challenge, "/case_ref"),
    )
    object.__setattr__(
        grant,
        "component_entry_refs",
        _ref_tuple(
            grant.component_entry_refs,
            ReferencePolicyEntryRef,
            challenge,
            "/component_entry_refs",
            nonempty=True,
        ),
    )
    object.__setattr__(
        grant,
        "configuration_ref",
        _identity(
            grant.configuration_ref,
            ReferenceIdentityKind.CONFIGURATION,
            challenge,
            "/configuration_ref",
        ),
    )
    object.__setattr__(
        grant,
        "disclosure_policy_ref",
        _owner(
            grant.disclosure_policy_ref,
            "disclosure_policy",
            challenge,
            "/disclosure_policy_ref",
        ),
    )
    object.__setattr__(
        grant,
        "environment_ref",
        _identity(
            grant.environment_ref,
            ReferenceIdentityKind.ENVIRONMENT,
            challenge,
            "/environment_ref",
        ),
    )
    object.__setattr__(
        grant, "evidence_role_binding", _role(grant.evidence_role_binding, challenge)
    )
    if (
        grant.evidence_role_binding.role
        is EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
        and grant.authority_function
        is not ReferenceAuthorityFunction.VERIFICATION_ANCHOR
    ):
        raise _reject("/evidence_role_binding", ReferenceInputCode.ROLE_MISMATCH)
    object.__setattr__(grant, "grant_id", _identifier(grant.grant_id, "/grant_id"))
    object.__setattr__(
        grant, "grant_version", _version(grant.grant_version, "/grant_version")
    )
    object.__setattr__(
        grant,
        "hardware_ref",
        _identity(
            grant.hardware_ref,
            ReferenceIdentityKind.HARDWARE,
            challenge,
            "/hardware_ref",
        ),
    )
    object.__setattr__(
        grant,
        "implementation_ref",
        _identity(
            grant.implementation_ref,
            ReferenceIdentityKind.IMPLEMENTATION,
            challenge,
            "/implementation_ref",
        ),
    )
    object.__setattr__(
        grant, "issuance_token", _text(grant.issuance_token, "/issuance_token")
    )
    object.__setattr__(
        grant,
        "issuer_ref",
        _identity(
            grant.issuer_ref, ReferenceIdentityKind.RUN_ISSUER, challenge, "/issuer_ref"
        ),
    )
    if grant.capability_ref != grant.issuer_ref:
        raise _reject("/capability_ref", ReferenceInputCode.STALE_BINDING)
    object.__setattr__(
        grant,
        "method_ref",
        _identity(
            grant.method_ref, ReferenceIdentityKind.METHOD, challenge, "/method_ref"
        ),
    )
    object.__setattr__(
        grant,
        "policy_ref",
        _b04_ref(grant.policy_ref, ReferencePolicyRef, challenge, "/policy_ref"),
    )
    object.__setattr__(
        grant,
        "precision_ref",
        _identity(
            grant.precision_ref,
            ReferenceIdentityKind.PRECISION,
            challenge,
            "/precision_ref",
        ),
    )
    object.__setattr__(
        grant,
        "representation_ref",
        _identity(
            grant.representation_ref,
            ReferenceIdentityKind.REPRESENTATION,
            challenge,
            "/representation_ref",
        ),
    )
    object.__setattr__(
        grant,
        "resource_authorization_ref",
        _identity(
            grant.resource_authorization_ref,
            ReferenceIdentityKind.RESOURCE_AUTHORIZATION,
            challenge,
            "/resource_authorization_ref",
        ),
    )
    object.__setattr__(grant, "scope_binding", _scope(grant.scope_binding, challenge))
    object.__setattr__(
        grant,
        "source_class",
        _exact(grant.source_class, ReferenceSourceClass, "/source_class"),
    )
    direct = _target_entry_refs(grant.execution_target)
    if direct and grant.component_entry_refs != direct:
        raise _reject("/component_entry_refs", ReferenceInputCode.STALE_BINDING)
    return challenge


def _derive_resolution_outcomes():
    outcomes: dict[ResolutionReason, ResolutionOutcome | None] = {}
    for outcome, reasons in RESOLUTION_OUTCOME_REASON_COMPATIBILITY.items():
        for reason in reasons:
            if reason in outcomes and outcomes[reason] is not outcome:
                outcomes[reason] = None
            else:
                outcomes[reason] = outcome
    if set(outcomes) != set(ResolutionReason):
        raise RuntimeError("resolution compatibility matrix is incomplete")
    return MappingProxyType(outcomes)


_RESOLUTION_OUTCOMES = _derive_resolution_outcomes()
del _derive_resolution_outcomes

RESOLUTION_REASON_PRECEDENCE = (
    ResolutionReason.RESOLUTION_IDENTITY_MISMATCH,
    ResolutionReason.RESOLUTION_PROVENANCE_INVALID,
    ResolutionReason.POLICY_PRIMARY_MISSING,
    ResolutionReason.POLICY_ENTRY_INCOMPLETE,
    ResolutionReason.ROLE_NOT_REGISTERED,
    ResolutionReason.CASE_NOT_APPLICABLE,
    ResolutionReason.CASE_UNSUPPORTED,
    ResolutionReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE,
    ResolutionReason.QUALIFICATION_BINDING_UNAVAILABLE,
    ResolutionReason.RESOURCE_POLICY_UNAVAILABLE,
    ResolutionReason.RESOURCE_CAPACITY_UNAVAILABLE,
    ResolutionReason.RESOLUTION_REQUIREMENTS_SATISFIED,
)


def select_resolution_terminal(
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    observed_reasons: tuple[ResolutionReason, ...],
) -> tuple[ResolutionOutcome, ResolutionReason]:
    if type(request) not in (PrimaryReferenceRequest, WitnessReferenceRequest):
        raise _reject("/request_binding", ReferenceInputCode.WRONG_TYPE)
    if type(observed_reasons) is not tuple:
        raise _reject("/reason", ReferenceInputCode.WRONG_TYPE)
    if len(observed_reasons) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _reject("/reason", ReferenceInputCode.INVALID_VALUE)
    if any(type(item) is not ResolutionReason for item in observed_reasons):
        raise _reject("/reason", ReferenceInputCode.WRONG_TYPE)
    if len(set(observed_reasons)) != len(observed_reasons):
        raise _reject("/reason", ReferenceInputCode.DUPLICATE_IDENTITY)
    observed = set(observed_reasons)
    if not observed:
        observed.add(ResolutionReason.RESOLUTION_REQUIREMENTS_SATISFIED)
    reason = next(item for item in RESOLUTION_REASON_PRECEDENCE if item in observed)
    outcome = _RESOLUTION_OUTCOMES[reason]
    if outcome is None:
        outcome = (
            ResolutionOutcome.PRIMARY_GRANT_ISSUED
            if type(request) is PrimaryReferenceRequest
            else ResolutionOutcome.WITNESS_GRANT_ISSUED
        )
    return outcome, reason


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceResolutionRecord(ReferenceTruthRecord):
    answer_key_authority_target: ReferenceAuthorityTarget
    applicability_assessment: SupportApplicabilityAssessment
    authority_function: ReferenceAuthorityFunction
    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    evidence_role_binding: EvidenceRoleBinding
    execution_target: ReferenceExecutionTarget
    grant_binding: ReferenceGrantBinding
    outcome: ResolutionOutcome
    policy_ref: ReferencePolicyRef
    qualification_binding: QualificationBinding
    reason: ResolutionReason
    request_binding: ReferenceRequestBinding
    resolution_id: str
    resolution_version: str
    resolver_ref: PinnedReferenceIdentity
    resource_policy_ref: object
    scope_binding: ReferenceScopeBinding
    source_class: ReferenceSourceClass

    OBJECT_KIND: ClassVar[str] = "reference_resolution_record"

    def __post_init__(self) -> None:
        if type(self) is not ReferenceResolutionRecord:
            raise _reject("/record", ReferenceInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        outcome = _exact(self.outcome, ResolutionOutcome, "/outcome")
        reason = _exact(self.reason, ResolutionReason, "/reason")
        expected = _RESOLUTION_OUTCOMES[reason]
        if expected is None:
            if outcome not in (
                ResolutionOutcome.PRIMARY_GRANT_ISSUED,
                ResolutionOutcome.WITNESS_GRANT_ISSUED,
            ):
                raise _reject("/outcome", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
        elif outcome is not expected:
            raise _reject("/outcome", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self,
            "answer_key_authority_target",
            _model(
                self.answer_key_authority_target,
                ReferenceAuthorityTarget,
                challenge,
                "/answer_key_authority_target",
            ),
        )
        applicability = _model(
            self.applicability_assessment,
            SupportApplicabilityAssessment,
            challenge,
            "/applicability_assessment",
        )
        object.__setattr__(self, "applicability_assessment", applicability)
        object.__setattr__(
            self,
            "authority_function",
            _exact(
                self.authority_function,
                ReferenceAuthorityFunction,
                "/authority_function",
            ),
        )
        object.__setattr__(
            self,
            "case_ref",
            _top_ref(self.case_ref, CanonicalChallengeCaseRef, challenge, "/case_ref"),
        )
        object.__setattr__(
            self, "evidence_role_binding", _role(self.evidence_role_binding, challenge)
        )
        object.__setattr__(
            self,
            "execution_target",
            _model(
                self.execution_target,
                ReferenceExecutionTarget,
                challenge,
                "/execution_target",
            ),
        )
        object.__setattr__(
            self,
            "grant_binding",
            _model(
                self.grant_binding, ReferenceGrantBinding, challenge, "/grant_binding"
            ),
        )
        object.__setattr__(
            self,
            "policy_ref",
            _b04_ref(self.policy_ref, ReferencePolicyRef, challenge, "/policy_ref"),
        )
        qualification = _model(
            self.qualification_binding,
            QualificationBinding,
            challenge,
            "/qualification_binding",
        )
        if qualification.is_bound:
            _owner(
                qualification.value,
                "qualification_evidence_bundle",
                challenge,
                "/qualification_binding",
            )
        object.__setattr__(self, "qualification_binding", qualification)
        object.__setattr__(
            self,
            "request_binding",
            _model(
                self.request_binding,
                ReferenceRequestBinding,
                challenge,
                "/request_binding",
            ),
        )
        object.__setattr__(
            self, "resolution_id", _identifier(self.resolution_id, "/resolution_id")
        )
        object.__setattr__(
            self,
            "resolution_version",
            _version(self.resolution_version, "/resolution_version"),
        )
        object.__setattr__(
            self,
            "resolver_ref",
            _identity(
                self.resolver_ref,
                ReferenceIdentityKind.RESOLVER,
                challenge,
                "/resolver_ref",
            ),
        )
        object.__setattr__(
            self,
            "resource_policy_ref",
            _owner(
                self.resource_policy_ref,
                "reference_resource_limit",
                challenge,
                "/resource_policy_ref",
            ),
        )
        object.__setattr__(self, "scope_binding", _scope(self.scope_binding, challenge))
        object.__setattr__(
            self,
            "source_class",
            _exact(self.source_class, ReferenceSourceClass, "/source_class"),
        )
        _validate_resolution_bindings(self)


def _validate_resolution_bindings(record: ReferenceResolutionRecord) -> None:
    issued_primary = record.outcome is ResolutionOutcome.PRIMARY_GRANT_ISSUED
    issued_witness = record.outcome is ResolutionOutcome.WITNESS_GRANT_ISSUED
    request_tag = record.request_binding.kind
    grant_tag = record.grant_binding.kind
    request_kind = request_tag.value
    execution_kind = record.execution_target.kind.value
    if request_kind != execution_kind:
        raise _reject("/execution_target", ReferenceInputCode.ROLE_MISMATCH)
    if (
        request_kind == "PRIMARY"
        and record.authority_function is not ReferenceAuthorityFunction.PRIMARY
    ) or (
        request_kind == "WITNESS"
        and record.authority_function
        is not ReferenceAuthorityFunction.CORROBORATING_WITNESS
    ):
        raise _reject("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    if (
        record.evidence_role_binding.role
        is EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
    ):
        raise _reject("/evidence_role_binding", ReferenceInputCode.ROLE_MISMATCH)
    if issued_primary:
        if (
            getattr(request_tag, "value", None) != "PRIMARY"
            or getattr(grant_tag, "value", None) != "PRIMARY"
        ):
            raise _reject("/grant_binding", ReferenceInputCode.ROLE_MISMATCH)
        if (
            record.authority_function is not ReferenceAuthorityFunction.PRIMARY
            or record.execution_target.kind.value != "PRIMARY"
        ):
            raise _reject("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    elif issued_witness:
        if (
            getattr(request_tag, "value", None) != "WITNESS"
            or getattr(grant_tag, "value", None) != "WITNESS"
        ):
            raise _reject("/grant_binding", ReferenceInputCode.ROLE_MISMATCH)
        if (
            record.authority_function
            is not ReferenceAuthorityFunction.CORROBORATING_WITNESS
            or record.execution_target.kind.value != "WITNESS"
        ):
            raise _reject("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    elif (
        getattr(grant_tag, "value", None) != "ABSENT"
        or record.grant_binding.value is not record.reason
    ):
        raise _reject("/grant_binding", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    if (issued_primary or issued_witness) and (
        record.applicability_assessment.status
        is not SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE
        or not record.qualification_binding.is_bound
    ):
        raise _reject("/outcome", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    if (
        record.outcome is ResolutionOutcome.NOT_APPLICABLE
        and record.applicability_assessment.status
        is not SupportApplicabilityStatus.NOT_APPLICABLE
    ):
        raise _reject(
            "/applicability_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        record.outcome is ResolutionOutcome.UNSUPPORTED
        and record.applicability_assessment.status
        is not SupportApplicabilityStatus.UNSUPPORTED
    ):
        raise _reject(
            "/applicability_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        record.outcome is ResolutionOutcome.APPLICABILITY_UNRESOLVED
        and record.applicability_assessment.status
        is not SupportApplicabilityStatus.ASSESSMENT_UNAVAILABLE
    ):
        raise _reject(
            "/applicability_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        record.outcome is ResolutionOutcome.QUALIFICATION_UNAVAILABLE
        and record.qualification_binding.is_bound
    ):
        raise _reject(
            "/qualification_binding", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )


def create_reference_resolution_record(
    *,
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    grant: PrimaryRunGrant | WitnessRunGrant | None,
    observed_reasons: tuple[ResolutionReason, ...],
    applicability_assessment: SupportApplicabilityAssessment,
    authority_function: ReferenceAuthorityFunction,
    evidence_role_binding: EvidenceRoleBinding,
    qualification_binding: QualificationBinding,
    resolution_id: str,
    resolution_version: str,
    resolver_ref: PinnedReferenceIdentity,
    resource_policy_ref: object,
    source_class: ReferenceSourceClass,
    policy: object | None = None,
    entries: tuple[object, ...] = (),
    compositions: tuple[object, ...] = (),
    precomputed_manifests: tuple[object, ...] = (),
) -> ReferenceResolutionRecord:
    if type(request) not in (PrimaryReferenceRequest, WitnessReferenceRequest):
        raise _reject("/request_binding", ReferenceInputCode.WRONG_TYPE)
    checked_resource_policy_ref = _owner(
        resource_policy_ref,
        "reference_resource_limit",
        request.challenge_key,
        "/resource_policy_ref",
    )
    if checked_resource_policy_ref != request.requested_resource_policy_ref:
        raise _reject("/resource_policy_ref", ReferenceInputCode.STALE_BINDING)
    outcome, reason = select_resolution_terminal(request, observed_reasons)
    registered_run_binding: tuple[object, ...] | None = None
    if outcome is ResolutionOutcome.PRIMARY_GRANT_ISSUED:
        if type(grant) is not PrimaryRunGrant or grant.request_ref != request.to_ref():
            raise _reject("/grant_binding", ReferenceInputCode.STALE_BINDING)
        registered_run_binding = _validate_issued_inventory(
            request,
            grant,
            policy,
            entries,
            compositions,
            precomputed_manifests,
        )
        grant_binding = ReferenceGrantBinding.primary(grant.to_ref())
        request_binding = ReferenceRequestBinding.primary(request.to_ref())
        execution_target = ReferenceExecutionTarget.primary(request.execution_target)
    elif outcome is ResolutionOutcome.WITNESS_GRANT_ISSUED:
        if type(grant) is not WitnessRunGrant or grant.request_ref != request.to_ref():
            raise _reject("/grant_binding", ReferenceInputCode.STALE_BINDING)
        registered_run_binding = _validate_issued_inventory(
            request,
            grant,
            policy,
            entries,
            compositions,
            precomputed_manifests,
        )
        grant_binding = ReferenceGrantBinding.witness(grant.to_ref())
        request_binding = ReferenceRequestBinding.witness(request.to_ref())
        execution_target = ReferenceExecutionTarget.witness(request.execution_target)
    else:
        if grant is not None:
            raise _reject("/grant_binding", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
        grant_binding = ReferenceGrantBinding.absent(reason)
        if type(request) is PrimaryReferenceRequest:
            request_binding = ReferenceRequestBinding.primary(request.to_ref())
            execution_target = ReferenceExecutionTarget.primary(
                request.execution_target
            )
        else:
            request_binding = ReferenceRequestBinding.witness(request.to_ref())
            execution_target = ReferenceExecutionTarget.witness(
                request.execution_target
            )
    issued = outcome in (
        ResolutionOutcome.PRIMARY_GRANT_ISSUED,
        ResolutionOutcome.WITNESS_GRANT_ISSUED,
    )
    reserved = False
    if issued:
        if grant is None or registered_run_binding is None:
            raise _reject("/grant_binding", ReferenceInputCode.INCOMPLETE_BINDING)
        _reserve_run_attempt(request, grant, registered_run_binding)
        reserved = True
    try:
        record = ReferenceResolutionRecord(
            answer_key_authority_target=request.answer_key_authority_target,
            applicability_assessment=applicability_assessment,
            authority_function=authority_function,
            case_ref=request.case_ref,
            challenge_key=request.challenge_key,
            evidence_role_binding=evidence_role_binding,
            execution_target=execution_target,
            grant_binding=grant_binding,
            outcome=outcome,
            policy_ref=request.policy_ref,
            qualification_binding=qualification_binding,
            reason=reason,
            request_binding=request_binding,
            resolution_id=resolution_id,
            resolution_version=resolution_version,
            resolver_ref=resolver_ref,
            resource_policy_ref=checked_resource_policy_ref,
            scope_binding=request.scope_binding,
            source_class=source_class,
        )
        if issued:
            if grant is None:
                raise _reject("/grant_binding", ReferenceInputCode.INCOMPLETE_BINDING)
            _complete_run_attempt(record, request, grant)
            reserved = False
        return record
    except BaseException:
        if reserved and grant is not None:
            _abandon_run_attempt(request, grant)
        raise


def _validate_issued_inventory(
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    grant: PrimaryRunGrant | WitnessRunGrant,
    policy: object | None,
    entries: tuple[object, ...],
    compositions: tuple[object, ...],
    precomputed_manifests: tuple[object, ...],
) -> tuple[object, ...]:
    """Cross-check the expanded registered target before a grant becomes usable."""

    from .policy import (
        PrecomputedReferenceSourceManifest,
        ReferenceComposition,
        ReferencePolicy,
        ReferencePolicyEntry,
        expand_authority_target,
        expand_witness_target,
        validate_reference_policy_graph,
    )

    if (
        type(policy) is not ReferencePolicy
        or type(entries) is not tuple
        or any(type(item) is not ReferencePolicyEntry for item in entries)
        or type(compositions) is not tuple
        or any(type(item) is not ReferenceComposition for item in compositions)
        or type(precomputed_manifests) is not tuple
        or any(
            type(item) is not PrecomputedReferenceSourceManifest
            for item in precomputed_manifests
        )
    ):
        raise _reject("/component_entry_refs", ReferenceInputCode.WRONG_TYPE)
    if policy.to_ref() != request.policy_ref:
        raise _reject("/policy_ref", ReferenceInputCode.STALE_BINDING)
    validate_reference_policy_graph(
        policy,
        entries=entries,
        compositions=compositions,
        precomputed_manifests=precomputed_manifests,
    )
    if (
        policy.scope_binding != request.scope_binding
        or policy.disclosure_policy_ref != request.disclosure_policy_ref
        or policy.resource_policy_ref != request.requested_resource_policy_ref
    ):
        raise _reject("/policy_ref", ReferenceInputCode.STALE_BINDING)
    if (
        not policy.answer_key_authority_target.is_bound
        or policy.answer_key_authority_target.value
        != request.answer_key_authority_target
    ):
        raise _reject("/answer_key_authority_target", ReferenceInputCode.STALE_BINDING)
    if type(request) is PrimaryReferenceRequest:
        expected = expand_authority_target(
            request.execution_target,
            entries=entries,
            compositions=compositions,
        )
    else:
        if request.execution_target not in policy.registered_witness_targets:
            raise _reject("/execution_target", ReferenceInputCode.STALE_BINDING)
        expected = expand_witness_target(
            request.execution_target,
            entries=entries,
            compositions=compositions,
        )
        primary = expand_authority_target(
            request.answer_key_authority_target,
            entries=entries,
            compositions=compositions,
        )
        if set(primary) & set(expected):
            raise _reject("/component_entry_refs", ReferenceInputCode.ROLE_MISMATCH)
    if grant.component_entry_refs != expected:
        raise _reject("/component_entry_refs", ReferenceInputCode.STALE_BINDING)
    entry_index = {entry.to_ref(): entry for entry in entries}
    expected_entries = tuple(entry_index[entry_ref] for entry_ref in expected)
    if any(
        entry.expected_representation_ref != request.representation_ref
        for entry in expected_entries
    ):
        raise _reject("/representation_ref", ReferenceInputCode.STALE_BINDING)
    if len(expected_entries) == 1 and request.execution_target.entry_ref is not None:
        entry = expected_entries[0]
        if (
            entry.authority_function is not grant.authority_function
            or entry.source_class is not grant.source_class
            or entry.evidence_role_binding != grant.evidence_role_binding
        ):
            raise _reject("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    _validate_request_grant_pair(request, grant)
    composition_index = {
        composition.to_ref(): composition for composition in compositions
    }
    target_entry_ref = request.execution_target.entry_ref
    if target_entry_ref is not None:
        target_entry = entry_index.get(target_entry_ref)
        if target_entry is None:
            raise _reject("/execution_target", ReferenceInputCode.STALE_BINDING)
        target_rights_profile_ref = target_entry.rights_profile_ref
    else:
        target_composition_ref = request.execution_target.composition_ref
        target_composition = composition_index.get(target_composition_ref)
        if target_composition is None:
            raise _reject("/execution_target", ReferenceInputCode.STALE_BINDING)
        target_rights_profile_ref = target_composition.rights_profile_ref
    manifest_index = {manifest.to_ref(): manifest for manifest in precomputed_manifests}
    selected_manifest_list = []
    for entry in expected_entries:
        if not entry.precomputed_source_manifest_ref.is_present:
            continue
        manifest = manifest_index.get(entry.precomputed_source_manifest_ref.value)
        if manifest is None:
            raise _reject(
                "/precomputed_source_manifest_ref", ReferenceInputCode.STALE_BINDING
            )
        selected_manifest_list.append(manifest)
    selected_manifests = tuple(selected_manifest_list)
    return (
        replace(policy),
        tuple(replace(entry) for entry in expected_entries),
        tuple(replace(manifest) for manifest in selected_manifests),
        _owner(
            target_rights_profile_ref,
            "rights_profile",
            request.challenge_key,
            "/rights_profile_ref",
        ),
    )


_RUN_OUTCOMES = MappingProxyType(
    {
        reason: outcome
        for outcome, reasons in RUN_OUTCOME_REASON_COMPATIBILITY.items()
        for reason in reasons
    }
)
if set(_RUN_OUTCOMES) != set(ReferenceFailureReason):
    raise RuntimeError("run compatibility matrix is incomplete")

RUN_REASON_PRECEDENCE = (
    ReferenceFailureReason.REQUEST_OR_GRANT_INVALID,
    ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH,
    ReferenceFailureReason.PROVENANCE_INVALID,
    ReferenceFailureReason.TRUSTED_CANCELLATION,
    ReferenceFailureReason.TIMEOUT,
    ReferenceFailureReason.RESOURCE_LIMIT,
    ReferenceFailureReason.CAPACITY_UNAVAILABLE,
    ReferenceFailureReason.DEPENDENCY_UNAVAILABLE,
    ReferenceFailureReason.TRANSPORT_FAILURE,
    ReferenceFailureReason.PROCESS_FAILURE,
    ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
    ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
    ReferenceFailureReason.NUMERICAL_INVALID_RESULT,
    ReferenceFailureReason.POLICY_ENTRY_NOT_APPLICABLE,
    ReferenceFailureReason.POLICY_ENTRY_UNSUPPORTED,
    ReferenceFailureReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE,
    ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED,
    ReferenceFailureReason.UNCERTAINTY_EVIDENCE_UNRESOLVED,
)


def select_run_terminal(
    observed_reasons: tuple[ReferenceFailureReason, ...],
) -> tuple[ReferenceRunOutcome, OptionalBinding[ReferenceFailureReason]]:
    if type(observed_reasons) is not tuple:
        raise _reject("/reason", ReferenceInputCode.WRONG_TYPE)
    if len(observed_reasons) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _reject("/reason", ReferenceInputCode.INVALID_VALUE)
    if any(type(item) is not ReferenceFailureReason for item in observed_reasons):
        raise _reject("/reason", ReferenceInputCode.WRONG_TYPE)
    if len(set(observed_reasons)) != len(observed_reasons):
        raise _reject("/reason", ReferenceInputCode.DUPLICATE_IDENTITY)
    observed = set(observed_reasons)
    if not observed:
        return ReferenceRunOutcome.SUPPORTED, OptionalBinding.absent()
    reason = next(item for item in RUN_REASON_PRECEDENCE if item in observed)
    return _RUN_OUTCOMES[reason], OptionalBinding.present(reason)


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceRunRecord(ReferenceTruthRecord):
    answer_key_authority_target: ReferenceAuthorityTarget
    applicability_assessment: SupportApplicabilityAssessment
    artifact_binding: RunArtifactBinding
    authority_function: ReferenceAuthorityFunction
    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    component_bindings: tuple[RealizedComponentBinding, ...]
    conditioning_assessment: ConditioningAssessment
    configuration_ref: PinnedReferenceIdentity
    diagnostics_ref: PinnedReferenceIdentity
    environment_ref: PinnedReferenceIdentity
    evidence_role_binding: EvidenceRoleBinding
    execution_target: ReferenceExecutionTarget
    grant_binding: ReferenceGrantBinding
    hardware_ref: PinnedReferenceIdentity
    implementation_ref: PinnedReferenceIdentity
    method_ref: PinnedReferenceIdentity
    outcome: ReferenceRunOutcome
    policy_ref: ReferencePolicyRef
    precision_ref: PinnedReferenceIdentity
    provenance_binding: ReferenceProvenance
    reason: OptionalBinding[ReferenceFailureReason]
    representation_ref: PinnedReferenceIdentity
    request_binding: ReferenceRequestBinding
    resolution_ref: ReferenceResolutionRecordRef
    resource_receipt_ref: PinnedReferenceIdentity
    run_id: str
    run_version: str
    scope_binding: ReferenceScopeBinding
    source_class: ReferenceSourceClass
    uncertainty_binding: UncertaintyRepresentation

    OBJECT_KIND: ClassVar[str] = "reference_run_record"

    def __post_init__(self) -> None:
        if type(self) is not ReferenceRunRecord:
            raise _reject("/record", ReferenceInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        outcome = _exact(self.outcome, ReferenceRunOutcome, "/outcome")
        reason_binding = _copy(self.reason, OptionalBinding, "/reason")
        if outcome is ReferenceRunOutcome.SUPPORTED:
            if reason_binding.is_present:
                raise _reject("/reason", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
        else:
            reason = reason_binding.value
            if (
                not reason_binding.is_present
                or type(reason) is not ReferenceFailureReason
                or _RUN_OUTCOMES.get(reason) is not outcome
            ):
                raise _reject("/reason", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self,
            "answer_key_authority_target",
            _model(
                self.answer_key_authority_target,
                ReferenceAuthorityTarget,
                challenge,
                "/answer_key_authority_target",
            ),
        )
        applicability = _model(
            self.applicability_assessment,
            SupportApplicabilityAssessment,
            challenge,
            "/applicability_assessment",
        )
        artifact = _model(
            self.artifact_binding, RunArtifactBinding, challenge, "/artifact_binding"
        )
        if artifact.is_bound and artifact.value.challenge_key != challenge:
            raise _reject("/artifact_binding", ReferenceInputCode.CROSS_CHALLENGE)
        conditioning = _model(
            self.conditioning_assessment,
            ConditioningAssessment,
            challenge,
            "/conditioning_assessment",
        )
        uncertainty = _model(
            self.uncertainty_binding,
            UncertaintyRepresentation,
            challenge,
            "/uncertainty_binding",
        )
        object.__setattr__(self, "applicability_assessment", applicability)
        object.__setattr__(self, "artifact_binding", artifact)
        object.__setattr__(
            self,
            "authority_function",
            _exact(
                self.authority_function,
                ReferenceAuthorityFunction,
                "/authority_function",
            ),
        )
        object.__setattr__(
            self,
            "case_ref",
            _top_ref(self.case_ref, CanonicalChallengeCaseRef, challenge, "/case_ref"),
        )
        components = _model_tuple(
            self.component_bindings,
            RealizedComponentBinding,
            challenge,
            "/component_bindings",
            nonempty=True,
        )
        if len({item.entry_ref for item in components}) != len(components):
            raise _reject("/component_bindings", ReferenceInputCode.DUPLICATE_IDENTITY)
        object.__setattr__(self, "component_bindings", components)
        object.__setattr__(self, "conditioning_assessment", conditioning)
        for name, kind in (
            ("configuration_ref", ReferenceIdentityKind.CONFIGURATION),
            ("diagnostics_ref", ReferenceIdentityKind.DIAGNOSTICS),
            ("environment_ref", ReferenceIdentityKind.ENVIRONMENT),
            ("hardware_ref", ReferenceIdentityKind.HARDWARE),
            ("implementation_ref", ReferenceIdentityKind.IMPLEMENTATION),
            ("method_ref", ReferenceIdentityKind.METHOD),
            ("precision_ref", ReferenceIdentityKind.PRECISION),
            ("representation_ref", ReferenceIdentityKind.REPRESENTATION),
            ("resource_receipt_ref", ReferenceIdentityKind.RESOURCE_RECEIPT),
        ):
            object.__setattr__(
                self, name, _identity(getattr(self, name), kind, challenge, f"/{name}")
            )
        object.__setattr__(
            self, "evidence_role_binding", _role(self.evidence_role_binding, challenge)
        )
        object.__setattr__(
            self,
            "execution_target",
            _model(
                self.execution_target,
                ReferenceExecutionTarget,
                challenge,
                "/execution_target",
            ),
        )
        object.__setattr__(
            self,
            "grant_binding",
            _model(
                self.grant_binding, ReferenceGrantBinding, challenge, "/grant_binding"
            ),
        )
        object.__setattr__(
            self,
            "policy_ref",
            _b04_ref(self.policy_ref, ReferencePolicyRef, challenge, "/policy_ref"),
        )
        object.__setattr__(
            self,
            "provenance_binding",
            _model(
                self.provenance_binding,
                ReferenceProvenance,
                challenge,
                "/provenance_binding",
            ),
        )
        if (
            self.provenance_binding.environment_ref != self.environment_ref
            or self.provenance_binding.implementation_ref != self.implementation_ref
            or self.provenance_binding.method_ref != self.method_ref
        ):
            raise _reject("/provenance_binding", ReferenceInputCode.STALE_BINDING)
        object.__setattr__(self, "reason", reason_binding)
        object.__setattr__(
            self,
            "request_binding",
            _model(
                self.request_binding,
                ReferenceRequestBinding,
                challenge,
                "/request_binding",
            ),
        )
        object.__setattr__(
            self,
            "resolution_ref",
            _b04_ref(
                self.resolution_ref,
                ReferenceResolutionRecordRef,
                challenge,
                "/resolution_ref",
            ),
        )
        object.__setattr__(self, "run_id", _identifier(self.run_id, "/run_id"))
        object.__setattr__(
            self, "run_version", _version(self.run_version, "/run_version")
        )
        object.__setattr__(self, "scope_binding", _scope(self.scope_binding, challenge))
        object.__setattr__(
            self,
            "source_class",
            _exact(self.source_class, ReferenceSourceClass, "/source_class"),
        )
        object.__setattr__(self, "uncertainty_binding", uncertainty)
        _validate_run_matrix(self)


def _validate_run_matrix(record: ReferenceRunRecord) -> None:
    artifact_tag = getattr(getattr(record.artifact_binding, "tag", None), "value", None)
    request_kind = record.request_binding.kind.value
    grant_kind = record.grant_binding.kind.value
    execution_kind = record.execution_target.kind.value
    if "ABSENT" in (request_kind, grant_kind, execution_kind):
        raise _reject("/grant_binding", ReferenceInputCode.INCOMPLETE_BINDING)
    if request_kind != grant_kind or request_kind != execution_kind:
        raise _reject("/grant_binding", ReferenceInputCode.ROLE_MISMATCH)
    if (
        request_kind == "PRIMARY"
        and record.authority_function is not ReferenceAuthorityFunction.PRIMARY
    ) or (
        request_kind == "WITNESS"
        and record.authority_function
        is not ReferenceAuthorityFunction.CORROBORATING_WITNESS
    ):
        raise _reject("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    if (
        record.evidence_role_binding.role
        is EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
    ):
        raise _reject("/evidence_role_binding", ReferenceInputCode.ROLE_MISMATCH)
    target = record.execution_target.value
    if request_kind == "PRIMARY" and target != record.answer_key_authority_target:
        raise _reject("/execution_target", ReferenceInputCode.STALE_BINDING)
    component_entry_refs = tuple(
        component.entry_ref for component in record.component_bindings
    )
    direct_target_refs = _target_entry_refs(target)
    if direct_target_refs and component_entry_refs != direct_target_refs:
        raise _reject("/component_bindings", ReferenceInputCode.STALE_BINDING)
    if request_kind == "WITNESS" and set(component_entry_refs) & set(
        _target_entry_refs(record.answer_key_authority_target)
    ):
        raise _reject("/component_bindings", ReferenceInputCode.ROLE_MISMATCH)
    if record.outcome is ReferenceRunOutcome.SUPPORTED:
        if artifact_tag != "BOUND":
            raise _reject(
                "/artifact_binding", ReferenceInputCode.OUTCOME_REASON_MISMATCH
            )
        if (
            record.applicability_assessment.status
            is not SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE
            or record.conditioning_assessment.status
            is not ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE
            or record.uncertainty_binding.status is not UncertaintyStatus.RESOLVED
        ):
            raise _reject("/outcome", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    else:
        if artifact_tag != "ABSENT":
            raise _reject(
                "/artifact_binding", ReferenceInputCode.OUTCOME_REASON_MISMATCH
            )
        if record.artifact_binding.value is not record.reason.value:
            raise _reject(
                "/artifact_binding", ReferenceInputCode.OUTCOME_REASON_MISMATCH
            )
    if (
        record.outcome is ReferenceRunOutcome.NOT_APPLICABLE
        and record.applicability_assessment.status
        is not SupportApplicabilityStatus.NOT_APPLICABLE
    ):
        raise _reject(
            "/applicability_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        record.outcome is ReferenceRunOutcome.UNSUPPORTED
        and record.applicability_assessment.status
        is not SupportApplicabilityStatus.UNSUPPORTED
    ):
        raise _reject(
            "/applicability_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        record.outcome is ReferenceRunOutcome.APPLICABILITY_UNRESOLVED
        and record.applicability_assessment.status
        is not SupportApplicabilityStatus.ASSESSMENT_UNAVAILABLE
    ):
        raise _reject(
            "/applicability_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        record.outcome is ReferenceRunOutcome.CONDITIONING_UNRESOLVED
        and record.conditioning_assessment.status
        is ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE
    ):
        raise _reject(
            "/conditioning_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        record.outcome is ReferenceRunOutcome.UNCERTAINTY_UNRESOLVED
        and record.uncertainty_binding.status is not UncertaintyStatus.UNRESOLVED
    ):
        raise _reject(
            "/uncertainty_binding", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )


def _create_run_attempt_state():
    """Create closure-owned registration and atomic claim authority."""

    lock = threading.Lock()
    available: dict[
        PrimaryRunGrantRef | WitnessRunGrantRef,
        tuple[
            ReferenceResolutionRecord | None,
            ReferenceResolutionRecordRef | None,
            PrimaryReferenceRequestRef | WitnessReferenceRequestRef,
            object | None,
            type | None,
            object | None,
            tuple[object, ...],
        ],
    ] = {}
    consumed: set[PrimaryRunGrantRef | WitnessRunGrantRef] = set()

    def reserve(
        request: PrimaryReferenceRequest | WitnessReferenceRequest,
        grant: PrimaryRunGrant | WitnessRunGrant,
        registered_run_binding: tuple[object, ...],
    ) -> None:
        _validate_request_grant_pair(request, grant)
        if type(registered_run_binding) is not tuple:
            raise _reject("/policy_ref", ReferenceInputCode.WRONG_TYPE)
        request_ref = request.to_ref()
        grant_ref = grant.to_ref()
        with lock:
            if grant_ref in available or grant_ref in consumed:
                raise _reject("/grant_binding", ReferenceInputCode.STALE_BINDING)
            available[grant_ref] = (
                None,
                None,
                request_ref,
                None,
                None,
                None,
                registered_run_binding,
            )

    def complete(
        resolution: ReferenceResolutionRecord,
        request: PrimaryReferenceRequest | WitnessReferenceRequest,
        grant: PrimaryRunGrant | WitnessRunGrant,
    ) -> None:
        resolution_ref = resolution.to_ref()
        request_ref = request.to_ref()
        grant_ref = grant.to_ref()
        if (
            resolution.request_binding.value != request_ref
            or resolution.grant_binding.value != grant_ref
        ):
            raise _reject("/resolution_ref", ReferenceInputCode.STALE_BINDING)
        with lock:
            state = available.get(grant_ref)
            if state is None or state[0] is not None or state[2] != request_ref:
                raise _reject("/grant_binding", ReferenceInputCode.STALE_BINDING)
            available[grant_ref] = (
                resolution,
                resolution_ref,
                request_ref,
                None,
                None,
                None,
                state[6],
            )

    def abandon(
        request: PrimaryReferenceRequest | WitnessReferenceRequest,
        grant: PrimaryRunGrant | WitnessRunGrant,
    ) -> None:
        request_ref = request.to_ref()
        grant_ref = grant.to_ref()
        with lock:
            state = available.get(grant_ref)
            if state is not None and state[0] is None and state[2] == request_ref:
                del available[grant_ref]
                consumed.add(grant_ref)

    def bind_executor(
        resolution: ReferenceResolutionRecord,
        executor: object,
    ) -> object:
        if type(resolution) is not ReferenceResolutionRecord or executor is None:
            raise _reject("/runner", ReferenceInputCode.AUTHORITY_INTERFACE_INVALID)
        resolution_ref = resolution.to_ref()
        grant_ref = resolution.grant_binding.value
        if type(grant_ref) not in (PrimaryRunGrantRef, WitnessRunGrantRef):
            raise _reject("/grant_binding", ReferenceInputCode.STALE_BINDING)
        with lock:
            state = available.get(grant_ref)
            if (
                state is None
                or state[0] is None
                or state[1] is None
                or state[0] is not resolution
                or state[1] != resolution_ref
                or state[3] is not None
            ):
                raise _reject("/resolution_ref", ReferenceInputCode.STALE_BINDING)
            capability = object()
            available[grant_ref] = (
                state[0],
                state[1],
                state[2],
                executor,
                type(executor),
                capability,
                state[6],
            )
            return capability

    def inspect(
        resolution: ReferenceResolutionRecord,
        request: PrimaryReferenceRequest | WitnessReferenceRequest,
        grant: PrimaryRunGrant | WitnessRunGrant,
        executor: object | None,
        capability: object | None,
    ) -> tuple[object, ...]:
        if executor is None or capability is None:
            raise _reject("/runner", ReferenceInputCode.AUTHORITY_INTERFACE_INVALID)
        resolution_ref = resolution.to_ref()
        request_ref = request.to_ref()
        grant_ref = grant.to_ref()
        with lock:
            state = available.get(grant_ref)
            if (
                state is None
                or state[0] is None
                or state[1] is None
                or state[0] is not resolution
                or state[1] != resolution_ref
                or state[2] != request_ref
                or state[3] is not executor
                or state[4] is not type(executor)
                or state[5] is not capability
            ):
                raise _reject("/grant", ReferenceInputCode.STALE_BINDING)
            return state[6]

    def claim(
        resolution: ReferenceResolutionRecord,
        request: PrimaryReferenceRequest | WitnessReferenceRequest,
        grant: PrimaryRunGrant | WitnessRunGrant,
        executor: object | None,
        capability: object | None,
    ) -> None:
        if executor is None or capability is None:
            raise _reject("/runner", ReferenceInputCode.AUTHORITY_INTERFACE_INVALID)
        resolution_ref = resolution.to_ref()
        request_ref = request.to_ref()
        grant_ref = grant.to_ref()
        with lock:
            state = available.get(grant_ref)
            if (
                state is None
                or state[0] is None
                or state[1] is None
                or state[0] is not resolution
                or state[1] != resolution_ref
                or state[2] != request_ref
                or state[3] is not executor
                or state[4] is not type(executor)
                or state[5] is not capability
            ):
                raise _reject("/grant", ReferenceInputCode.STALE_BINDING)
            del available[grant_ref]
            consumed.add(grant_ref)

    return reserve, complete, abandon, bind_executor, inspect, claim


(
    _reserve_run_attempt,
    _complete_run_attempt,
    _abandon_run_attempt,
    _bind_run_attempt_executor,
    _inspect_run_attempt,
    _claim_run_attempt,
) = _create_run_attempt_state()
del _create_run_attempt_state


def _validate_registered_run_provenance(
    registered_run_binding: tuple[object, ...],
    component_bindings: tuple[RealizedComponentBinding, ...],
    provenance_binding: ReferenceProvenance,
) -> None:
    """Cross-bind a supported run to the resolution's closed policy snapshot."""

    from .policy import (
        PrecomputedReferenceSourceManifest,
        ReferencePolicy,
        ReferencePolicyEntry,
    )

    if type(registered_run_binding) is not tuple or len(registered_run_binding) != 4:
        raise _reject("/policy_ref", ReferenceInputCode.STALE_BINDING)
    policy, entries, manifests, target_rights_profile_ref = registered_run_binding
    if (
        type(policy) is not ReferencePolicy
        or type(entries) is not tuple
        or not entries
        or any(type(item) is not ReferencePolicyEntry for item in entries)
        or type(manifests) is not tuple
        or any(
            type(item) is not PrecomputedReferenceSourceManifest for item in manifests
        )
    ):
        raise _reject("/policy_ref", ReferenceInputCode.STALE_BINDING)
    if tuple(item.entry_ref for item in component_bindings) != tuple(
        entry.to_ref() for entry in entries
    ):
        raise _reject("/component_bindings", ReferenceInputCode.STALE_BINDING)

    expected_sources = tuple(entry.source_ref for entry in entries)
    if provenance_binding.source_ref not in expected_sources:
        raise _reject(
            "/provenance_binding/source_ref", ReferenceInputCode.STALE_BINDING
        )
    expected_rights = (
        policy.rights_profile_ref,
        target_rights_profile_ref,
        *(entry.rights_profile_ref for entry in entries),
        *(manifest.rights_profile_ref for manifest in manifests),
        *(manifest.provenance_binding.rights_profile_ref for manifest in manifests),
    )
    if any(
        rights_profile_ref != provenance_binding.rights_profile_ref
        for rights_profile_ref in expected_rights
    ):
        raise _reject(
            "/provenance_binding/rights_profile_ref",
            ReferenceInputCode.STALE_BINDING,
        )
    expected_campaign = policy.scope_binding.evidence_campaign_ref
    if (
        provenance_binding.evidence_campaign_ref != expected_campaign
        or any(
            entry.scope_binding.evidence_campaign_ref != expected_campaign
            for entry in entries
        )
        or any(
            manifest.scope_binding.evidence_campaign_ref != expected_campaign
            or manifest.provenance_binding.evidence_campaign_ref != expected_campaign
            for manifest in manifests
        )
    ):
        raise _reject(
            "/provenance_binding/evidence_campaign_ref",
            ReferenceInputCode.STALE_BINDING,
        )

    run_disclosures = {
        disclosure.category: disclosure
        for disclosure in provenance_binding.dependency_disclosures
    }
    for manifest in manifests:
        if manifest.source_ref != provenance_binding.source_ref:
            continue
        manifest_provenance = manifest.provenance_binding
        if (
            not set(manifest_provenance.generated_or_copied_code_refs).issubset(
                provenance_binding.generated_or_copied_code_refs
            )
            or not set(manifest_provenance.provenance_refs).issubset(
                provenance_binding.provenance_refs
            )
            or not set(manifest_provenance.reviewer_authority_refs).issubset(
                provenance_binding.reviewer_authority_refs
            )
        ):
            raise _reject("/provenance_binding", ReferenceInputCode.STALE_BINDING)
        for manifest_disclosure in manifest_provenance.dependency_disclosures:
            run_disclosure = run_disclosures.get(manifest_disclosure.category)
            if (
                run_disclosure is None
                or run_disclosure.relation is not manifest_disclosure.relation
                or not set(manifest_disclosure.evidence_refs).issubset(
                    run_disclosure.evidence_refs
                )
            ):
                raise _reject(
                    "/provenance_binding/dependency_disclosures",
                    ReferenceInputCode.STALE_BINDING,
                )


def create_reference_run_record(
    *,
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    grant: PrimaryRunGrant | WitnessRunGrant,
    resolution: ReferenceResolutionRecord,
    observed_reasons: tuple[ReferenceFailureReason, ...],
    artifact_content: ArtifactContentBinding | None,
    applicability_assessment: SupportApplicabilityAssessment,
    component_bindings: tuple[RealizedComponentBinding, ...],
    conditioning_assessment: ConditioningAssessment,
    diagnostics_ref: PinnedReferenceIdentity,
    provenance_binding: ReferenceProvenance,
    resource_receipt_ref: PinnedReferenceIdentity,
    run_id: str,
    run_version: str,
    uncertainty_binding: UncertaintyRepresentation,
    _attempt_executor: object | None = None,
    _attempt_capability: object | None = None,
) -> ReferenceRunRecord:
    if type(request) is PrimaryReferenceRequest:
        checked_request = _copy(request, PrimaryReferenceRequest, "/request")
        checked_grant = _copy(grant, PrimaryRunGrant, "/grant")
    elif type(request) is WitnessReferenceRequest:
        checked_request = _copy(request, WitnessReferenceRequest, "/request")
        checked_grant = _copy(grant, WitnessRunGrant, "/grant")
    else:
        raise _reject("/request", ReferenceInputCode.WRONG_TYPE)
    checked_resolution = _copy(
        resolution,
        ReferenceResolutionRecord,
        "/resolution_ref",
    )
    _validate_request_grant_pair(checked_request, checked_grant)
    expected_resolution_outcome = (
        ResolutionOutcome.PRIMARY_GRANT_ISSUED
        if type(checked_request) is PrimaryReferenceRequest
        else ResolutionOutcome.WITNESS_GRANT_ISSUED
    )
    if checked_resolution.outcome is not expected_resolution_outcome:
        raise _reject("/resolution_ref", ReferenceInputCode.STALE_BINDING)
    if (
        checked_resolution.request_binding.value != checked_request.to_ref()
        or checked_resolution.grant_binding.value != checked_grant.to_ref()
        or checked_resolution.case_ref != checked_request.case_ref
        or checked_resolution.policy_ref != checked_request.policy_ref
        or checked_resolution.answer_key_authority_target
        != checked_request.answer_key_authority_target
        or checked_resolution.scope_binding != checked_request.scope_binding
        or checked_resolution.authority_function is not checked_grant.authority_function
        or checked_resolution.evidence_role_binding
        != checked_grant.evidence_role_binding
        or checked_resolution.source_class is not checked_grant.source_class
    ):
        raise _reject("/resolution_ref", ReferenceInputCode.STALE_BINDING)

    outcome, reason_binding = select_run_terminal(observed_reasons)
    challenge = checked_request.challenge_key
    checked_applicability = _model(
        applicability_assessment,
        SupportApplicabilityAssessment,
        challenge,
        "/applicability_assessment",
    )
    checked_components = _model_tuple(
        component_bindings,
        RealizedComponentBinding,
        challenge,
        "/component_bindings",
        nonempty=True,
    )
    if (
        tuple(item.entry_ref for item in checked_components)
        != checked_grant.component_entry_refs
    ):
        raise _reject("/component_bindings", ReferenceInputCode.STALE_BINDING)
    checked_conditioning = _model(
        conditioning_assessment,
        ConditioningAssessment,
        challenge,
        "/conditioning_assessment",
    )
    checked_diagnostics_ref = _identity(
        diagnostics_ref,
        ReferenceIdentityKind.DIAGNOSTICS,
        challenge,
        "/diagnostics_ref",
    )
    checked_provenance = _model(
        provenance_binding,
        ReferenceProvenance,
        challenge,
        "/provenance_binding",
    )
    if (
        checked_provenance.environment_ref != checked_grant.environment_ref
        or checked_provenance.implementation_ref != checked_grant.implementation_ref
        or checked_provenance.method_ref != checked_grant.method_ref
    ):
        raise _reject("/provenance_binding", ReferenceInputCode.STALE_BINDING)
    checked_resource_receipt_ref = _identity(
        resource_receipt_ref,
        ReferenceIdentityKind.RESOURCE_RECEIPT,
        challenge,
        "/resource_receipt_ref",
    )
    checked_run_id = _identifier(run_id, "/run_id")
    checked_run_version = _version(run_version, "/run_version")
    checked_uncertainty = _model(
        uncertainty_binding,
        UncertaintyRepresentation,
        challenge,
        "/uncertainty_binding",
    )
    if outcome is ReferenceRunOutcome.SUPPORTED:
        if type(artifact_content) is not ArtifactContentBinding:
            raise _reject("/artifact_binding", ReferenceInputCode.INCOMPLETE_BINDING)
        checked_artifact_content = _model(
            artifact_content,
            ArtifactContentBinding,
            challenge,
            "/artifact_binding",
        )
        artifact_binding = RunArtifactBinding.bound(checked_artifact_content)
    else:
        reason = reason_binding.value
        if artifact_content is not None or type(reason) is not ReferenceFailureReason:
            raise _reject(
                "/artifact_binding", ReferenceInputCode.OUTCOME_REASON_MISMATCH
            )
        artifact_binding = RunArtifactBinding.absent(reason)
    if outcome is ReferenceRunOutcome.SUPPORTED and (
        checked_applicability.status
        is not SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE
        or checked_conditioning.status
        is not ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE
        or checked_uncertainty.status is not UncertaintyStatus.RESOLVED
    ):
        raise _reject("/outcome", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    if (
        outcome is ReferenceRunOutcome.NOT_APPLICABLE
        and checked_applicability.status
        is not SupportApplicabilityStatus.NOT_APPLICABLE
    ):
        raise _reject(
            "/applicability_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        outcome is ReferenceRunOutcome.UNSUPPORTED
        and checked_applicability.status is not SupportApplicabilityStatus.UNSUPPORTED
    ):
        raise _reject(
            "/applicability_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        outcome is ReferenceRunOutcome.APPLICABILITY_UNRESOLVED
        and checked_applicability.status
        is not SupportApplicabilityStatus.ASSESSMENT_UNAVAILABLE
    ):
        raise _reject(
            "/applicability_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        outcome is ReferenceRunOutcome.CONDITIONING_UNRESOLVED
        and checked_conditioning.status
        is ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE
    ):
        raise _reject(
            "/conditioning_assessment", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )
    if (
        outcome is ReferenceRunOutcome.UNCERTAINTY_UNRESOLVED
        and checked_uncertainty.status is not UncertaintyStatus.UNRESOLVED
    ):
        raise _reject(
            "/uncertainty_binding", ReferenceInputCode.OUTCOME_REASON_MISMATCH
        )

    registered_run_binding = _inspect_run_attempt(
        resolution,
        request,
        grant,
        _attempt_executor,
        _attempt_capability,
    )
    try:
        _validate_registered_run_provenance(
            registered_run_binding,
            checked_components,
            checked_provenance,
        )
    except ReferenceValidationError:
        if reason_binding.value is not ReferenceFailureReason.PROVENANCE_INVALID:
            raise

    if type(checked_request) is PrimaryReferenceRequest:
        request_binding = ReferenceRequestBinding.primary(checked_request.to_ref())
        grant_binding = ReferenceGrantBinding.primary(checked_grant.to_ref())
        execution_target = ReferenceExecutionTarget.primary(
            checked_request.execution_target
        )
    else:
        request_binding = ReferenceRequestBinding.witness(checked_request.to_ref())
        grant_binding = ReferenceGrantBinding.witness(checked_grant.to_ref())
        execution_target = ReferenceExecutionTarget.witness(
            checked_request.execution_target
        )
    checked_resolution_ref = checked_resolution.to_ref()
    _claim_run_attempt(
        resolution,
        request,
        grant,
        _attempt_executor,
        _attempt_capability,
    )
    return ReferenceRunRecord(
        answer_key_authority_target=checked_request.answer_key_authority_target,
        applicability_assessment=checked_applicability,
        artifact_binding=artifact_binding,
        authority_function=checked_grant.authority_function,
        case_ref=checked_request.case_ref,
        challenge_key=challenge,
        component_bindings=checked_components,
        conditioning_assessment=checked_conditioning,
        configuration_ref=checked_grant.configuration_ref,
        diagnostics_ref=checked_diagnostics_ref,
        environment_ref=checked_grant.environment_ref,
        evidence_role_binding=checked_grant.evidence_role_binding,
        execution_target=execution_target,
        grant_binding=grant_binding,
        hardware_ref=checked_grant.hardware_ref,
        implementation_ref=checked_grant.implementation_ref,
        method_ref=checked_grant.method_ref,
        outcome=outcome,
        policy_ref=checked_request.policy_ref,
        precision_ref=checked_grant.precision_ref,
        provenance_binding=checked_provenance,
        reason=reason_binding,
        representation_ref=checked_grant.representation_ref,
        request_binding=request_binding,
        resolution_ref=checked_resolution_ref,
        resource_receipt_ref=checked_resource_receipt_ref,
        run_id=checked_run_id,
        run_version=checked_run_version,
        scope_binding=checked_request.scope_binding,
        source_class=checked_grant.source_class,
        uncertainty_binding=checked_uncertainty,
    )


def _validate_request_grant_pair(
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    grant: PrimaryRunGrant | WitnessRunGrant,
) -> None:
    if type(request) is PrimaryReferenceRequest:
        if type(grant) is not PrimaryRunGrant:
            raise _reject("/grant", ReferenceInputCode.ROLE_MISMATCH)
    elif type(request) is WitnessReferenceRequest:
        if type(grant) is not WitnessRunGrant:
            raise _reject("/grant", ReferenceInputCode.ROLE_MISMATCH)
    else:
        raise _reject("/request", ReferenceInputCode.WRONG_TYPE)
    if (
        grant.request_ref != request.to_ref()
        or grant.challenge_key != request.challenge_key
        or grant.case_ref != request.case_ref
        or grant.policy_ref != request.policy_ref
        or grant.answer_key_authority_target != request.answer_key_authority_target
        or grant.execution_target != request.execution_target
        or grant.representation_ref != request.representation_ref
        or grant.disclosure_policy_ref != request.disclosure_policy_ref
        or grant.scope_binding != request.scope_binding
    ):
        raise _reject("/grant", ReferenceInputCode.STALE_BINDING)


__all__ = [
    "RESOLUTION_REASON_PRECEDENCE",
    "RUN_REASON_PRECEDENCE",
    "PrimaryReferenceRequest",
    "PrimaryRunGrant",
    "ReferenceResolutionRecord",
    "ReferenceRunRecord",
    "WitnessReferenceRequest",
    "WitnessRunGrant",
    "create_reference_resolution_record",
    "create_reference_run_record",
    "select_resolution_terminal",
    "select_run_terminal",
]
