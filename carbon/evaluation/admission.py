"""Capability-gated positive-only TruthAsset admission for B-04."""

from __future__ import annotations

import threading
from dataclasses import InitVar, dataclass
from types import MappingProxyType
from typing import ClassVar, Protocol, runtime_checkable

from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.refs import CanonicalChallengeCaseRef
from carbon.registry.model import ChallengeKey

from .assets import ReferenceArtifact, validate_reference_artifact
from .comparison import ReferenceComparisonRecord
from .enums import (
    ADMISSION_ISSUANCE_REASON_PRECEDENCE,
    ADMISSION_REASON_PRECEDENCE,
    AdmissionGrantIssuanceOutcome,
    AdmissionGrantIssuanceReason,
    ReferenceArtifactOrigin,
    ReferenceAuthorityFunction,
    ReferenceComparisonOutcome,
    ReferenceExecutionTargetKind,
    ReferenceIdentityKind,
    ReferenceRunOutcome,
    ReferenceSourceClass,
    TruthAssetAdmissionOutcome,
    TruthAssetAdmissionReason,
    outcome_reason_compatible,
)
from .errors import (
    ReferenceInputCode,
    ReferenceServiceCode,
    ReferenceServiceError,
    ReferenceValidationError,
)
from .execution import ReferenceRunRecord
from .model import (
    AdmissionAttemptBinding,
    ConditioningAssessment,
    DependencyDisclosure,
    OptionalBinding,
    PinnedReferenceIdentity,
    ReferenceAuthorityTarget,
    ReferenceProvenance,
    ReferenceScopeBinding,
    ReferenceTruthRecord,
    SupportApplicabilityAssessment,
    UncertaintyRepresentation,
    challenge,
    evidence_role_binding,
    exact,
    exact_enum,
    exact_tuple,
    identifier,
    invalid,
    owner,
    owner_set,
    pinned_identity,
    reference_ref,
    top_ref,
    version,
)
from .policy import ReferencePolicy
from .refs import (
    ReferenceArtifactRef,
    ReferenceComparisonRecordRef,
    ReferencePolicyRef,
    ReferenceRunRecordRef,
    TruthAssetAdmissionDecisionRecordRef,
    TruthAssetAdmissionGrantIssuanceRecordRef,
    TruthAssetAdmissionGrantRef,
    TruthAssetRef,
)
from .runners import PrimaryReferenceRunner, WitnessReferenceRunner

_ISSUANCE_RECORD_TOKEN = object()
_GRANT_TOKEN = object()
_DECISION_TOKEN = object()


_ADMISSION_ISSUANCE_OUTCOMES = MappingProxyType(
    {
        AdmissionGrantIssuanceReason.ADMISSION_GRAPH_CROSS_BINDING_MISMATCH: AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_UNAVAILABLE,
        AdmissionGrantIssuanceReason.ADMISSION_GRANT_SCOPE_UNAVAILABLE: AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_UNAVAILABLE,
        AdmissionGrantIssuanceReason.ADMISSION_AUTHORITY_BINDING_UNAVAILABLE: AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_UNAVAILABLE,
        AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED: AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
    }
)

_ADMISSION_OUTCOMES = MappingProxyType(
    {
        TruthAssetAdmissionReason.GRANT_INVALID_OR_CONSUMED: TruthAssetAdmissionOutcome.REJECTED,
        TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH: TruthAssetAdmissionOutcome.REJECTED,
        TruthAssetAdmissionReason.RUN_NOT_SUPPORTED: TruthAssetAdmissionOutcome.REJECTED,
        TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE: TruthAssetAdmissionOutcome.REJECTED,
        TruthAssetAdmissionReason.REQUIRED_COMPARISON_CONTESTED: TruthAssetAdmissionOutcome.INDETERMINATE,
        TruthAssetAdmissionReason.REQUIRED_COMPARISON_INDETERMINATE: TruthAssetAdmissionOutcome.INDETERMINATE,
        TruthAssetAdmissionReason.QUALIFICATION_UNAVAILABLE: TruthAssetAdmissionOutcome.UNAVAILABLE,
        TruthAssetAdmissionReason.PROVENANCE_OR_RIGHTS_INVALID: TruthAssetAdmissionOutcome.REJECTED,
        TruthAssetAdmissionReason.USE_OR_DISCLOSURE_UNAVAILABLE: TruthAssetAdmissionOutcome.UNAVAILABLE,
        TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED: TruthAssetAdmissionOutcome.ADMITTED,
    }
)


def select_admission_grant_issuance_terminal(
    observed_reasons: tuple[AdmissionGrantIssuanceReason, ...],
) -> tuple[AdmissionGrantIssuanceOutcome, AdmissionGrantIssuanceReason]:
    """Select the first exact D11 grant-issuance reason."""

    reasons = exact_tuple(
        observed_reasons,
        AdmissionGrantIssuanceReason,
        "/reason",
        nonempty=True,
        unique=True,
    )
    observed = set(reasons)
    reason = next(
        item for item in ADMISSION_ISSUANCE_REASON_PRECEDENCE if item in observed
    )
    return _ADMISSION_ISSUANCE_OUTCOMES[reason], reason


def select_truth_asset_admission_terminal(
    observed_reasons: tuple[TruthAssetAdmissionReason, ...],
) -> tuple[TruthAssetAdmissionOutcome, TruthAssetAdmissionReason]:
    """Select the first exact D11 substantive-admission reason."""

    reasons = exact_tuple(
        observed_reasons,
        TruthAssetAdmissionReason,
        "/reason",
        nonempty=True,
        unique=True,
    )
    observed = set(reasons)
    reason = next(item for item in ADMISSION_REASON_PRECEDENCE if item in observed)
    return _ADMISSION_OUTCOMES[reason], reason


@dataclass(frozen=True, slots=True, repr=False)
class AdmissionGrantIssuanceEcho:
    """Exact bounded echo from a separately configured structural issuer."""

    outcome: AdmissionGrantIssuanceOutcome
    reason: AdmissionGrantIssuanceReason
    issuance_token: str

    def __post_init__(self) -> None:
        if type(self) is not AdmissionGrantIssuanceEcho:
            raise invalid("/outcome", ReferenceInputCode.WRONG_TYPE)
        if not outcome_reason_compatible(self.outcome, self.reason):
            raise invalid("/reason", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
        object.__setattr__(
            self,
            "issuance_token",
            identifier(self.issuance_token, "/issuance_token"),
        )


@runtime_checkable
class TruthAssetAdmissionGrantIssuer(Protocol):
    """Nominal structural issuer; it has no substantive admission authority."""

    @property
    def issuer_ref(self) -> PinnedReferenceIdentity: ...

    def evaluate_grant_issuance(
        self,
        attempt: AdmissionAttemptBinding,
    ) -> AdmissionGrantIssuanceEcho: ...


@dataclass(frozen=True, slots=True, repr=False)
class TruthAssetAdmissionEcho:
    """Exact bounded echo from a separately configured admission authority."""

    outcome: TruthAssetAdmissionOutcome
    reason: TruthAssetAdmissionReason
    consumed_grant_receipt_ref: PinnedReferenceIdentity

    def __post_init__(self) -> None:
        if type(self) is not TruthAssetAdmissionEcho:
            raise invalid("/outcome", ReferenceInputCode.WRONG_TYPE)
        if not outcome_reason_compatible(self.outcome, self.reason):
            raise invalid("/reason", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
        exact(
            self.consumed_grant_receipt_ref,
            PinnedReferenceIdentity,
            "/consumed_grant_receipt_ref",
        )


@runtime_checkable
class TruthAssetAdmissionAuthority(Protocol):
    """Nominal substantive authority supplied outside this fixture runtime."""

    @property
    def admission_authority_ref(self) -> PinnedReferenceIdentity: ...

    def evaluate_admission(
        self,
        attempt: AdmissionAttemptBinding,
        grant_ref: TruthAssetAdmissionGrantRef,
    ) -> TruthAssetAdmissionEcho: ...


def _copy_admission_attempt(value: object) -> AdmissionAttemptBinding:
    """Reconstruct every admission-attempt layer from exact validated values."""

    attempt = exact(value, AdmissionAttemptBinding, "/attempt_binding")
    return AdmissionAttemptBinding(
        admission_authority_ref=attempt.admission_authority_ref,
        answer_key_authority_target=attempt.answer_key_authority_target,
        artifact_binding=attempt.artifact_binding,
        case_ref=attempt.case_ref,
        comparison_refs=attempt.comparison_refs,
        decision_profile_ref=attempt.decision_profile_ref,
        disclosure_policy_ref=attempt.disclosure_policy_ref,
        primary_execution_target=attempt.primary_execution_target,
        provenance_policy_ref=attempt.provenance_policy_ref,
        qualification_binding=attempt.qualification_binding,
        rights_profile_ref=attempt.rights_profile_ref,
        run_ref=attempt.run_ref,
        use_restrictions=attempt.use_restrictions,
        witness_targets=attempt.witness_targets,
    )


@dataclass(frozen=True, slots=True, repr=False)
class TruthAssetAdmissionGrantIssuanceRecord(ReferenceTruthRecord):
    attempt_binding: AdmissionAttemptBinding
    challenge_key: ChallengeKey
    issuance_id: str
    issuance_token: str
    issuance_version: str
    issuer_ref: PinnedReferenceIdentity
    outcome: AdmissionGrantIssuanceOutcome
    reason: AdmissionGrantIssuanceReason
    _token: InitVar[object] = None

    OBJECT_KIND: ClassVar[str] = "truth_asset_admission_grant_issuance_record"

    def __post_init__(self, _token: object) -> None:
        if (
            type(self) is not TruthAssetAdmissionGrantIssuanceRecord
            or _token is not _ISSUANCE_RECORD_TOKEN
        ):
            raise TypeError("issuance records require a configured issuer")
        attempt = _copy_admission_attempt(self.attempt_binding)
        key = challenge(self.challenge_key)
        if attempt.challenge_key != key:
            raise invalid("/attempt_binding", ReferenceInputCode.CROSS_CHALLENGE)
        object.__setattr__(self, "attempt_binding", attempt)
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(
            self,
            "issuer_ref",
            pinned_identity(
                self.issuer_ref,
                ReferenceIdentityKind.ADMISSION_ISSUER,
                "/issuer_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self, "issuance_id", identifier(self.issuance_id, "/issuance_id")
        )
        object.__setattr__(
            self, "issuance_token", identifier(self.issuance_token, "/issuance_token")
        )
        object.__setattr__(
            self,
            "issuance_version",
            version(self.issuance_version, "/issuance_version"),
        )
        if not outcome_reason_compatible(self.outcome, self.reason):
            raise invalid("/reason", ReferenceInputCode.OUTCOME_REASON_MISMATCH)


def _new_issuance_record(**fields: object) -> TruthAssetAdmissionGrantIssuanceRecord:
    return TruthAssetAdmissionGrantIssuanceRecord(
        **fields,
        _token=_ISSUANCE_RECORD_TOKEN,
    )  # type: ignore[arg-type]


def _create_admission_one_use_state():
    """Create the private atomic issuance/grant state for this fixture runtime."""

    lock = threading.Lock()
    available_issuances: dict[TruthAssetAdmissionGrantIssuanceRecordRef, object] = {}
    consumed_issuances: set[TruthAssetAdmissionGrantIssuanceRecordRef] = set()
    available_grants: dict[TruthAssetAdmissionGrantRef, object] = {}
    consumed_grants: set[TruthAssetAdmissionGrantRef] = set()

    def register_issuance(
        issuance: TruthAssetAdmissionGrantIssuanceRecord,
        issuer: object,
    ) -> None:
        issuance_ref = issuance.to_ref()
        with lock:
            if (
                issuance_ref in available_issuances
                or issuance_ref in consumed_issuances
            ):
                raise invalid("/issuance_record_ref", ReferenceInputCode.STALE_BINDING)
            available_issuances[issuance_ref] = issuer

    def register_grant(
        issuance: TruthAssetAdmissionGrantIssuanceRecord,
        grant: TruthAssetAdmissionGrant,
    ) -> None:
        issuance_ref = issuance.to_ref()
        grant_ref = grant.to_ref()
        with lock:
            if issuance_ref not in available_issuances:
                raise invalid("/issuance_record_ref", ReferenceInputCode.STALE_BINDING)
            if grant_ref in available_grants or grant_ref in consumed_grants:
                raise invalid("/grant_ref", ReferenceInputCode.STALE_BINDING)
            issuer = available_issuances.pop(issuance_ref)
            consumed_issuances.add(issuance_ref)
            available_grants[grant_ref] = issuer

    def consume_grant(
        grant: TruthAssetAdmissionGrant,
        authority: object,
    ) -> tuple[TruthAssetAdmissionGrantRef, bool]:
        grant_ref = grant.to_ref()
        with lock:
            if grant_ref not in available_grants:
                return grant_ref, False
            if available_grants[grant_ref] is authority:
                raise invalid(
                    "/admission_authority_ref",
                    ReferenceInputCode.STALE_BINDING,
                )
            available_grants.pop(grant_ref)
            consumed_grants.add(grant_ref)
        return grant_ref, True

    return register_issuance, register_grant, consume_grant


(
    _register_authorized_issuance,
    _register_authorized_grant,
    _consume_authorized_grant,
) = _create_admission_one_use_state()
del _create_admission_one_use_state


def issue_truth_asset_admission_grant_record(
    issuer: TruthAssetAdmissionGrantIssuer | None,
    attempt: AdmissionAttemptBinding,
    *,
    issuance_id: str,
    issuance_version: str,
) -> TruthAssetAdmissionGrantIssuanceRecord | None:
    """Return no record when no issuer exists; never fabricate a terminal event."""

    checked_attempt = exact(attempt, AdmissionAttemptBinding, "/attempt_binding")
    if issuer is None:
        return None
    try:
        is_runner = isinstance(issuer, (PrimaryReferenceRunner, WitnessReferenceRunner))
        if is_runner:
            raise ReferenceServiceError(
                ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE,
                path="/issuer_ref",
            )
        has_authority_role = isinstance(issuer, TruthAssetAdmissionAuthority)
        is_issuer = isinstance(issuer, TruthAssetAdmissionGrantIssuer)
    except ReferenceServiceError:
        raise
    except Exception:  # noqa: BLE001 - sanitize structural capability inspection.
        raise ReferenceServiceError(
            ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE,
            path="/issuer_ref",
        ) from None
    if not is_issuer or has_authority_role:
        raise ReferenceServiceError(
            ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE,
            path="/issuer_ref",
        )
    try:
        issuer_ref = pinned_identity(
            issuer.issuer_ref,
            ReferenceIdentityKind.ADMISSION_ISSUER,
            "/issuer_ref",
            challenge_key=checked_attempt.challenge_key,
        )
        echo = issuer.evaluate_grant_issuance(checked_attempt)
    except Exception:  # noqa: BLE001 - sanitize the configured capability boundary.
        raise ReferenceServiceError(
            ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE,
            path="/issuer_ref",
        ) from None
    if type(echo) is not AdmissionGrantIssuanceEcho:
        raise ReferenceServiceError(
            ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE,
            path="/outcome",
        )
    record = _new_issuance_record(
        attempt_binding=checked_attempt,
        challenge_key=checked_attempt.challenge_key,
        issuance_id=issuance_id,
        issuance_token=echo.issuance_token,
        issuance_version=issuance_version,
        issuer_ref=issuer_ref,
        outcome=echo.outcome,
        reason=echo.reason,
    )
    if record.outcome is AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED:
        _register_authorized_issuance(record, issuer)
    return record


@dataclass(frozen=True, slots=True, repr=False)
class TruthAssetAdmissionGrant(ReferenceTruthRecord):
    attempt_binding: AdmissionAttemptBinding
    capability_ref: PinnedReferenceIdentity
    challenge_key: ChallengeKey
    grant_id: str
    grant_version: str
    issuance_record_ref: TruthAssetAdmissionGrantIssuanceRecordRef
    issuance_token: str
    issuer_ref: PinnedReferenceIdentity
    _token: InitVar[object] = None

    OBJECT_KIND: ClassVar[str] = "truth_asset_admission_grant"

    def __post_init__(self, _token: object) -> None:
        if type(self) is not TruthAssetAdmissionGrant or _token is not _GRANT_TOKEN:
            raise TypeError("admission grants require an authorized issuance record")
        attempt = _copy_admission_attempt(self.attempt_binding)
        key = challenge(self.challenge_key)
        if attempt.challenge_key != key:
            raise invalid("/attempt_binding", ReferenceInputCode.CROSS_CHALLENGE)
        object.__setattr__(self, "attempt_binding", attempt)
        object.__setattr__(self, "challenge_key", key)
        for name in ("capability_ref", "issuer_ref"):
            object.__setattr__(
                self,
                name,
                pinned_identity(
                    getattr(self, name),
                    ReferenceIdentityKind.ADMISSION_ISSUER,
                    f"/{name}",
                    challenge_key=key,
                ),
            )
        if self.capability_ref != self.issuer_ref:
            raise invalid("/capability_ref", ReferenceInputCode.STALE_BINDING)
        object.__setattr__(self, "grant_id", identifier(self.grant_id, "/grant_id"))
        object.__setattr__(
            self, "grant_version", version(self.grant_version, "/grant_version")
        )
        object.__setattr__(
            self,
            "issuance_record_ref",
            reference_ref(
                self.issuance_record_ref,
                TruthAssetAdmissionGrantIssuanceRecordRef,
                "/issuance_record_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self, "issuance_token", identifier(self.issuance_token, "/issuance_token")
        )


def _new_admission_grant(**fields: object) -> TruthAssetAdmissionGrant:
    return TruthAssetAdmissionGrant(**fields, _token=_GRANT_TOKEN)  # type: ignore[arg-type]


def create_truth_asset_admission_grant(
    issuance: TruthAssetAdmissionGrantIssuanceRecord,
    *,
    capability_ref: PinnedReferenceIdentity,
    grant_id: str,
    grant_version: str,
) -> TruthAssetAdmissionGrant:
    checked = exact(
        issuance,
        TruthAssetAdmissionGrantIssuanceRecord,
        "/issuance_record_ref",
    )
    if (
        checked.outcome is not AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED
        or checked.reason
        is not AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED
    ):
        raise invalid("/outcome", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    grant = _new_admission_grant(
        attempt_binding=checked.attempt_binding,
        capability_ref=capability_ref,
        challenge_key=checked.challenge_key,
        grant_id=grant_id,
        grant_version=grant_version,
        issuance_record_ref=checked.to_ref(),
        issuance_token=checked.issuance_token,
        issuer_ref=checked.issuer_ref,
    )
    _register_authorized_grant(checked, grant)
    return grant


@dataclass(frozen=True, slots=True, repr=False)
class TruthAssetAdmissionDecisionRecord(ReferenceTruthRecord):
    admission_authority_ref: PinnedReferenceIdentity
    attempt_binding: AdmissionAttemptBinding
    challenge_key: ChallengeKey
    consumed_grant_receipt_ref: PinnedReferenceIdentity
    decision_id: str
    decision_version: str
    grant_ref: TruthAssetAdmissionGrantRef
    issuance_record_ref: TruthAssetAdmissionGrantIssuanceRecordRef
    outcome: TruthAssetAdmissionOutcome
    reason: TruthAssetAdmissionReason
    _token: InitVar[object] = None

    OBJECT_KIND: ClassVar[str] = "truth_asset_admission_decision_record"

    def __post_init__(self, _token: object) -> None:
        if (
            type(self) is not TruthAssetAdmissionDecisionRecord
            or _token is not _DECISION_TOKEN
        ):
            raise TypeError("admission decisions require a configured authority")
        attempt = _copy_admission_attempt(self.attempt_binding)
        key = challenge(self.challenge_key)
        if attempt.challenge_key != key:
            raise invalid("/attempt_binding", ReferenceInputCode.CROSS_CHALLENGE)
        object.__setattr__(self, "attempt_binding", attempt)
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(
            self,
            "admission_authority_ref",
            pinned_identity(
                self.admission_authority_ref,
                ReferenceIdentityKind.ADMISSION_AUTHORITY,
                "/admission_authority_ref",
                challenge_key=key,
            ),
        )
        if self.admission_authority_ref != attempt.admission_authority_ref:
            raise invalid(
                "/admission_authority_ref",
                ReferenceInputCode.STALE_BINDING,
            )
        object.__setattr__(
            self,
            "consumed_grant_receipt_ref",
            pinned_identity(
                self.consumed_grant_receipt_ref,
                ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
                "/consumed_grant_receipt_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self, "decision_id", identifier(self.decision_id, "/decision_id")
        )
        object.__setattr__(
            self,
            "decision_version",
            version(self.decision_version, "/decision_version"),
        )
        object.__setattr__(
            self,
            "grant_ref",
            reference_ref(
                self.grant_ref,
                TruthAssetAdmissionGrantRef,
                "/grant_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self,
            "issuance_record_ref",
            reference_ref(
                self.issuance_record_ref,
                TruthAssetAdmissionGrantIssuanceRecordRef,
                "/issuance_record_ref",
                challenge_key=key,
            ),
        )
        if not outcome_reason_compatible(self.outcome, self.reason):
            raise invalid("/reason", ReferenceInputCode.OUTCOME_REASON_MISMATCH)


def _new_admission_decision(**fields: object) -> TruthAssetAdmissionDecisionRecord:
    return TruthAssetAdmissionDecisionRecord(
        **fields,
        _token=_DECISION_TOKEN,
    )  # type: ignore[arg-type]


def _validate_admission_graph(
    attempt: AdmissionAttemptBinding,
    policy: ReferencePolicy,
    run: ReferenceRunRecord,
    artifact: ReferenceArtifact | None,
    comparisons: tuple[ReferenceComparisonRecord, ...],
) -> tuple[TruthAssetAdmissionReason, ...]:
    failures: list[TruthAssetAdmissionReason] = []
    if (
        policy.challenge_key != attempt.challenge_key
        or run.challenge_key != attempt.challenge_key
        or run.case_ref != attempt.case_ref
        or run.authority_function is not ReferenceAuthorityFunction.PRIMARY
        or run.execution_target.kind is not ReferenceExecutionTargetKind.PRIMARY
        or run.execution_target.value != attempt.primary_execution_target
        or run.answer_key_authority_target != attempt.primary_execution_target
        or policy.answer_key_authority_target.value
        != attempt.answer_key_authority_target
        or policy.registered_witness_targets != attempt.witness_targets
    ):
        failures.append(TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH)
    if (
        policy.to_ref() != run.policy_ref
        or policy.disclosure_policy_ref != attempt.disclosure_policy_ref
        or policy.provenance_policy_ref != attempt.provenance_policy_ref
        or policy.rights_profile_ref != attempt.rights_profile_ref
    ):
        failures.append(TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH)
    if (
        run.to_ref() != attempt.run_ref
        or run.outcome is not ReferenceRunOutcome.SUPPORTED
    ):
        failures.append(TruthAssetAdmissionReason.RUN_NOT_SUPPORTED)
    if artifact is None or not attempt.artifact_binding.is_bound:
        failures.append(TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE)
    else:
        try:
            validate_reference_artifact(artifact, run)
        except Exception:  # noqa: BLE001 - reduce graph mismatch to a closed fact.
            failures.append(TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE)
        else:
            if (
                artifact.to_ref() != attempt.artifact_binding.value
                or artifact.artifact_origin is ReferenceArtifactOrigin.FIXTURE_ONLY
            ):
                failures.append(TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE)
            if (
                artifact.provenance_binding.rights_profile_ref
                != attempt.rights_profile_ref
            ):
                failures.append(TruthAssetAdmissionReason.PROVENANCE_OR_RIGHTS_INVALID)
            if (
                artifact.challenge_key != attempt.challenge_key
                or artifact.case_ref != attempt.case_ref
                or artifact.policy_ref != policy.to_ref()
                or artifact.run_ref != run.to_ref()
                or artifact.provenance_binding != run.provenance_binding
                or attempt.provenance_policy_ref
                not in run.provenance_binding.provenance_refs
            ):
                failures.append(TruthAssetAdmissionReason.PROVENANCE_OR_RIGHTS_INVALID)
    if not attempt.qualification_binding.is_bound:
        failures.append(TruthAssetAdmissionReason.QUALIFICATION_UNAVAILABLE)
    if tuple(item.to_ref() for item in comparisons) != attempt.comparison_refs:
        failures.append(TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH)
    if tuple(item.witness_target for item in comparisons) != attempt.witness_targets:
        failures.append(TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH)
    if any(
        item.challenge_key != attempt.challenge_key
        or item.case_ref != attempt.case_ref
        or item.policy_ref != policy.to_ref()
        or item.primary_run_ref != run.to_ref()
        or item.answer_key_authority_target != attempt.answer_key_authority_target
        or item.comparison_policy_ref != policy.comparison_policy_ref
        or item.scope_binding != policy.scope_binding
        for item in comparisons
    ):
        failures.append(TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH)
    if any(
        item.outcome is ReferenceComparisonOutcome.CONTESTED_DISAGREEMENT
        for item in comparisons
    ):
        failures.append(TruthAssetAdmissionReason.REQUIRED_COMPARISON_CONTESTED)
    elif any(
        item.outcome is ReferenceComparisonOutcome.COMPARISON_INDETERMINATE
        for item in comparisons
    ):
        failures.append(TruthAssetAdmissionReason.REQUIRED_COMPARISON_INDETERMINATE)
    observed = set(failures)
    return tuple(item for item in ADMISSION_REASON_PRECEDENCE if item in observed)


def _decide_truth_asset_admission_record(
    authority: TruthAssetAdmissionAuthority | None,
    issuance: TruthAssetAdmissionGrantIssuanceRecord,
    grant: TruthAssetAdmissionGrant,
    *,
    policy: ReferencePolicy,
    run: ReferenceRunRecord,
    artifact: ReferenceArtifact | None,
    comparisons: tuple[ReferenceComparisonRecord, ...],
    decision_id: str,
    decision_version: str,
) -> TruthAssetAdmissionDecisionRecord | None:
    """Return no decision when authority is absent; validate every positive echo."""

    if authority is None:
        return None
    try:
        is_authority = isinstance(authority, TruthAssetAdmissionAuthority)
        has_issuer_role = isinstance(authority, TruthAssetAdmissionGrantIssuer)
    except Exception:  # noqa: BLE001 - sanitize structural capability inspection.
        raise ReferenceServiceError(
            ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE,
            path="/admission_authority_ref",
        ) from None
    if not is_authority or has_issuer_role:
        raise ReferenceServiceError(
            ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE,
            path="/admission_authority_ref",
        )
    checked_issuance = exact(
        issuance,
        TruthAssetAdmissionGrantIssuanceRecord,
        "/issuance_record_ref",
    )
    checked_grant = exact(grant, TruthAssetAdmissionGrant, "/grant_ref")
    checked_policy = exact(policy, ReferencePolicy, "/policy_ref")
    checked_run = exact(run, ReferenceRunRecord, "/run_ref")
    checked_comparisons = exact_tuple(
        comparisons,
        ReferenceComparisonRecord,
        "/comparison_refs",
        unique=True,
    )
    if (
        checked_grant.issuance_record_ref != checked_issuance.to_ref()
        or checked_grant.attempt_binding != checked_issuance.attempt_binding
        or checked_grant.issuance_token != checked_issuance.issuance_token
        or checked_grant.issuer_ref != checked_issuance.issuer_ref
    ):
        raise invalid("/grant_ref", ReferenceInputCode.STALE_BINDING)
    attempt = checked_grant.attempt_binding
    structural_failures = _validate_admission_graph(
        attempt,
        checked_policy,
        checked_run,
        artifact,
        checked_comparisons,
    )
    try:
        authority_ref = pinned_identity(
            authority.admission_authority_ref,
            ReferenceIdentityKind.ADMISSION_AUTHORITY,
            "/admission_authority_ref",
            challenge_key=attempt.challenge_key,
        )
        if authority_ref != attempt.admission_authority_ref:
            raise ValueError
    except Exception:  # noqa: BLE001 - sanitize the configured capability boundary.
        raise ReferenceServiceError(
            ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE,
            path="/admission_authority_ref",
        ) from None
    consumed_ref, grant_was_available = _consume_authorized_grant(
        checked_grant,
        authority,
    )
    if not grant_was_available:
        observed = {
            *structural_failures,
            TruthAssetAdmissionReason.GRANT_INVALID_OR_CONSUMED,
        }
        structural_failures = tuple(
            item for item in ADMISSION_REASON_PRECEDENCE if item in observed
        )
    try:
        echo = authority.evaluate_admission(attempt, checked_grant.to_ref())
    except Exception:  # noqa: BLE001 - sanitize the configured capability boundary.
        raise ReferenceServiceError(
            ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE,
            path="/admission_authority_ref",
        ) from None
    if type(echo) is not TruthAssetAdmissionEcho:
        raise ReferenceServiceError(
            ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE,
            path="/outcome",
        )
    if structural_failures:
        expected = select_truth_asset_admission_terminal(structural_failures)
        if (echo.outcome, echo.reason) != expected:
            raise invalid("/outcome", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    elif echo.reason in {
        TruthAssetAdmissionReason.GRANT_INVALID_OR_CONSUMED,
        TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH,
        TruthAssetAdmissionReason.RUN_NOT_SUPPORTED,
        TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE,
        TruthAssetAdmissionReason.REQUIRED_COMPARISON_CONTESTED,
        TruthAssetAdmissionReason.REQUIRED_COMPARISON_INDETERMINATE,
    }:
        raise invalid("/reason", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    if consumed_ref != checked_grant.to_ref():
        raise invalid("/grant_ref", ReferenceInputCode.STALE_BINDING)
    receipt = pinned_identity(
        echo.consumed_grant_receipt_ref,
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "/consumed_grant_receipt_ref",
        challenge_key=attempt.challenge_key,
    )
    return _new_admission_decision(
        admission_authority_ref=authority_ref,
        attempt_binding=attempt,
        challenge_key=attempt.challenge_key,
        consumed_grant_receipt_ref=receipt,
        decision_id=decision_id,
        decision_version=decision_version,
        grant_ref=checked_grant.to_ref(),
        issuance_record_ref=checked_issuance.to_ref(),
        outcome=echo.outcome,
        reason=echo.reason,
    )


def _copy_applicability_assessment(value: object) -> SupportApplicabilityAssessment:
    assessment = exact(
        value,
        SupportApplicabilityAssessment,
        "/applicability_assessment",
    )
    return SupportApplicabilityAssessment(
        applicability_evidence_refs=assessment.applicability_evidence_refs,
        limitations=assessment.limitations,
        method_ref=assessment.method_ref,
        status=assessment.status,
        support_boundary_ref=assessment.support_boundary_ref,
    )


def _copy_conditioning_assessment(value: object) -> ConditioningAssessment:
    assessment = exact(
        value,
        ConditioningAssessment,
        "/conditioning_assessment",
    )
    return ConditioningAssessment(
        evidence_refs=assessment.evidence_refs,
        limitations=assessment.limitations,
        method_ref=assessment.method_ref,
        status=assessment.status,
    )


def _copy_dependency_disclosures(
    value: object,
) -> tuple[DependencyDisclosure, ...]:
    disclosures = exact_tuple(
        value,
        DependencyDisclosure,
        "/dependency_disclosures",
    )
    return tuple(
        DependencyDisclosure(
            category=disclosure.category,
            evidence_refs=disclosure.evidence_refs,
            relation=disclosure.relation,
        )
        for disclosure in disclosures
    )


def _copy_provenance(value: object) -> ReferenceProvenance:
    provenance = exact(value, ReferenceProvenance, "/provenance_binding")
    return ReferenceProvenance(
        dependency_disclosures=provenance.dependency_disclosures,
        environment_ref=provenance.environment_ref,
        evidence_campaign_ref=provenance.evidence_campaign_ref,
        generated_or_copied_code_refs=provenance.generated_or_copied_code_refs,
        implementation_ref=provenance.implementation_ref,
        method_ref=provenance.method_ref,
        provenance_refs=provenance.provenance_refs,
        reviewer_authority_refs=provenance.reviewer_authority_refs,
        rights_profile_ref=provenance.rights_profile_ref,
        source_ref=provenance.source_ref,
    )


def _copy_scope(value: object) -> ReferenceScopeBinding:
    scope = exact(value, ReferenceScopeBinding, "/scope_binding")
    return ReferenceScopeBinding(
        candidate_output_contract_ref=scope.candidate_output_contract_ref,
        claim_scope_ref=scope.claim_scope_ref,
        evidence_campaign_ref=scope.evidence_campaign_ref,
        evidence_population_refs=scope.evidence_population_refs,
        physical_system_ref=scope.physical_system_ref,
        proposal_population_ref=scope.proposal_population_ref,
        reference_fidelity_allocation_ref=scope.reference_fidelity_allocation_ref,
        sampling_plan_ref=scope.sampling_plan_ref,
        target_population_ref=scope.target_population_ref,
        truth_target_ref=scope.truth_target_ref,
    )


def _copy_uncertainty(value: object) -> UncertaintyRepresentation:
    uncertainty = exact(
        value,
        UncertaintyRepresentation,
        "/uncertainty_binding",
    )
    return UncertaintyRepresentation(
        component_kinds=uncertainty.component_kinds,
        coverage_ref=uncertainty.coverage_ref,
        dependence_policy_ref=uncertainty.dependence_policy_ref,
        estimand_ref=uncertainty.estimand_ref,
        evidence_refs=uncertainty.evidence_refs,
        limitations=uncertainty.limitations,
        method_ref=uncertainty.method_ref,
        representation_ref=uncertainty.representation_ref,
        status=uncertainty.status,
        units_ref=uncertainty.units_ref,
        use_restrictions=uncertainty.use_restrictions,
    )


def _copy_authority_target(value: object) -> ReferenceAuthorityTarget:
    target = exact(value, ReferenceAuthorityTarget, "/execution_target")
    return ReferenceAuthorityTarget(target.kind, target.value)


@dataclass(frozen=True, slots=True, repr=False, init=False)
class TruthAsset(ReferenceTruthRecord):
    admission_decision_ref: TruthAssetAdmissionDecisionRecordRef
    admission_grant_ref: TruthAssetAdmissionGrantRef
    admission_issuance_record_ref: TruthAssetAdmissionGrantIssuanceRecordRef
    applicability_assessment: SupportApplicabilityAssessment
    artifact_ref: ReferenceArtifactRef
    authority_function: ReferenceAuthorityFunction
    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    comparison_refs: tuple[ReferenceComparisonRecordRef, ...]
    conditioning_assessment: ConditioningAssessment
    configuration_ref: PinnedReferenceIdentity
    dependency_disclosures: tuple[DependencyDisclosure, ...]
    disclosure_policy_ref: object
    environment_ref: PinnedReferenceIdentity
    evidence_role_binding: EvidenceRoleBinding
    execution_target: ReferenceAuthorityTarget
    hardware_ref: PinnedReferenceIdentity
    implementation_ref: PinnedReferenceIdentity
    known_limitations: tuple[object, ...]
    method_ref: PinnedReferenceIdentity
    policy_ref: ReferencePolicyRef
    precision_ref: PinnedReferenceIdentity
    provenance_binding: ReferenceProvenance
    qualification_evidence_ref: object
    representation_ref: PinnedReferenceIdentity
    rights_profile_ref: object
    run_ref: ReferenceRunRecordRef
    scope_binding: ReferenceScopeBinding
    source_class: ReferenceSourceClass
    supersedes: OptionalBinding[TruthAssetRef]
    truth_asset_id: str
    truth_asset_version: str
    uncertainty_binding: UncertaintyRepresentation
    use_restrictions: tuple[object, ...]
    OBJECT_KIND: ClassVar[str] = "truth_asset"

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("TruthAsset requires a complete ADMITTED graph")

    def _validate(self) -> None:
        if type(self) is not TruthAsset:
            raise TypeError("TruthAsset requires a complete ADMITTED graph")
        key = challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(
            self,
            "case_ref",
            top_ref(
                self.case_ref,
                CanonicalChallengeCaseRef,
                "/case_ref",
                challenge_key=key,
            ),
        )
        for name, expected in (
            ("admission_decision_ref", TruthAssetAdmissionDecisionRecordRef),
            ("admission_grant_ref", TruthAssetAdmissionGrantRef),
            (
                "admission_issuance_record_ref",
                TruthAssetAdmissionGrantIssuanceRecordRef,
            ),
            ("artifact_ref", ReferenceArtifactRef),
            ("policy_ref", ReferencePolicyRef),
            ("run_ref", ReferenceRunRecordRef),
        ):
            object.__setattr__(
                self,
                name,
                reference_ref(
                    getattr(self, name),
                    expected,
                    f"/{name}",
                    challenge_key=key,
                ),
            )
        object.__setattr__(
            self,
            "comparison_refs",
            tuple(
                reference_ref(
                    item,
                    ReferenceComparisonRecordRef,
                    "/comparison_refs",
                    challenge_key=key,
                )
                for item in exact_tuple(
                    self.comparison_refs,
                    ReferenceComparisonRecordRef,
                    "/comparison_refs",
                    unique=True,
                )
            ),
        )
        object.__setattr__(
            self,
            "authority_function",
            exact_enum(
                self.authority_function,
                ReferenceAuthorityFunction,
                "/authority_function",
            ),
        )
        if self.authority_function is not ReferenceAuthorityFunction.PRIMARY:
            raise invalid("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
        object.__setattr__(
            self,
            "source_class",
            exact_enum(self.source_class, ReferenceSourceClass, "/source_class"),
        )
        for name, kind in (
            ("configuration_ref", ReferenceIdentityKind.CONFIGURATION),
            ("environment_ref", ReferenceIdentityKind.ENVIRONMENT),
            ("hardware_ref", ReferenceIdentityKind.HARDWARE),
            ("implementation_ref", ReferenceIdentityKind.IMPLEMENTATION),
            ("method_ref", ReferenceIdentityKind.METHOD),
            ("precision_ref", ReferenceIdentityKind.PRECISION),
            ("representation_ref", ReferenceIdentityKind.REPRESENTATION),
        ):
            object.__setattr__(
                self,
                name,
                pinned_identity(
                    getattr(self, name),
                    kind,
                    f"/{name}",
                    challenge_key=key,
                ),
            )
        applicability = _copy_applicability_assessment(self.applicability_assessment)
        conditioning = _copy_conditioning_assessment(self.conditioning_assessment)
        provenance = _copy_provenance(self.provenance_binding)
        scope = _copy_scope(self.scope_binding)
        uncertainty = _copy_uncertainty(self.uncertainty_binding)
        if any(
            item.challenge_key != key
            for item in (applicability, conditioning, provenance, scope, uncertainty)
        ):
            raise invalid("/challenge_key", ReferenceInputCode.CROSS_CHALLENGE)
        disclosures = _copy_dependency_disclosures(self.dependency_disclosures)
        if disclosures != provenance.dependency_disclosures:
            raise invalid("/dependency_disclosures", ReferenceInputCode.STALE_BINDING)
        object.__setattr__(self, "applicability_assessment", applicability)
        object.__setattr__(self, "conditioning_assessment", conditioning)
        object.__setattr__(self, "dependency_disclosures", disclosures)
        object.__setattr__(self, "provenance_binding", provenance)
        object.__setattr__(self, "scope_binding", scope)
        object.__setattr__(self, "uncertainty_binding", uncertainty)
        if (
            self.environment_ref != provenance.environment_ref
            or self.implementation_ref != provenance.implementation_ref
            or self.method_ref != provenance.method_ref
        ):
            raise invalid("/provenance_binding", ReferenceInputCode.STALE_BINDING)
        execution_target = _copy_authority_target(self.execution_target)
        if execution_target.challenge_key != key:
            raise invalid("/execution_target", ReferenceInputCode.CROSS_CHALLENGE)
        object.__setattr__(self, "execution_target", execution_target)
        object.__setattr__(
            self,
            "evidence_role_binding",
            evidence_role_binding(
                self.evidence_role_binding,
                "/evidence_role_binding",
                challenge_key=key,
                authority_function=self.authority_function,
            ),
        )
        object.__setattr__(
            self,
            "disclosure_policy_ref",
            owner(
                self.disclosure_policy_ref,
                "disclosure_policy",
                "/disclosure_policy_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self,
            "qualification_evidence_ref",
            owner(
                self.qualification_evidence_ref,
                "qualification_evidence_bundle",
                "/qualification_evidence_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self,
            "rights_profile_ref",
            owner(
                self.rights_profile_ref,
                "rights_profile",
                "/rights_profile_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self,
            "known_limitations",
            owner_set(
                self.known_limitations,
                "restriction",
                "/known_limitations",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self,
            "use_restrictions",
            owner_set(
                self.use_restrictions,
                "permitted_use",
                "/use_restrictions",
                challenge_key=key,
            ),
        )
        supersedes = exact(self.supersedes, OptionalBinding, "/supersedes")
        if supersedes.is_present:
            supersedes = OptionalBinding.present(
                reference_ref(
                    supersedes.value,
                    TruthAssetRef,
                    "/supersedes",
                    challenge_key=key,
                )
            )
        else:
            supersedes = OptionalBinding.absent()
        object.__setattr__(self, "supersedes", supersedes)
        object.__setattr__(
            self,
            "truth_asset_id",
            identifier(self.truth_asset_id, "/truth_asset_id"),
        )
        object.__setattr__(
            self,
            "truth_asset_version",
            version(self.truth_asset_version, "/truth_asset_version"),
        )


def _validated_truth_asset_fields(
    decision: TruthAssetAdmissionDecisionRecord,
    issuance: TruthAssetAdmissionGrantIssuanceRecord,
    grant: TruthAssetAdmissionGrant,
    artifact: ReferenceArtifact,
    run: ReferenceRunRecord,
    *,
    truth_asset_id: str,
    truth_asset_version: str,
    supersedes: OptionalBinding[TruthAssetRef] | None = None,
) -> dict[str, object]:
    """Return normalized fields only after validating the complete ADMITTED graph."""

    checked = exact(
        decision,
        TruthAssetAdmissionDecisionRecord,
        "/admission_decision_ref",
    )
    if (
        checked.outcome is not TruthAssetAdmissionOutcome.ADMITTED
        or checked.reason
        is not TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED
    ):
        raise invalid("/outcome", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    checked_issuance = exact(
        issuance,
        TruthAssetAdmissionGrantIssuanceRecord,
        "/admission_issuance_record_ref",
    )
    checked_grant = exact(
        grant,
        TruthAssetAdmissionGrant,
        "/admission_grant_ref",
    )
    checked_artifact = exact(artifact, ReferenceArtifact, "/artifact_ref")
    checked_run = exact(run, ReferenceRunRecord, "/run_ref")
    if (
        checked_issuance.outcome
        is not AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED
        or checked_issuance.reason
        is not AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED
        or checked.grant_ref != checked_grant.to_ref()
        or checked.issuance_record_ref != checked_issuance.to_ref()
        or checked_grant.issuance_record_ref != checked_issuance.to_ref()
        or checked_grant.attempt_binding != checked_issuance.attempt_binding
        or checked.attempt_binding != checked_grant.attempt_binding
        or checked.admission_authority_ref
        != checked.attempt_binding.admission_authority_ref
    ):
        raise invalid("/grant_ref", ReferenceInputCode.STALE_BINDING)
    attempt = checked.attempt_binding
    validate_reference_artifact(checked_artifact, checked_run)
    if (
        not attempt.artifact_binding.is_bound
        or checked_artifact.artifact_origin is ReferenceArtifactOrigin.FIXTURE_ONLY
        or checked_artifact.to_ref() != attempt.artifact_binding.value
        or checked_run.to_ref() != attempt.run_ref
        or checked_run.outcome is not ReferenceRunOutcome.SUPPORTED
        or checked_run.authority_function is not ReferenceAuthorityFunction.PRIMARY
        or checked_run.case_ref != attempt.case_ref
        or checked_run.answer_key_authority_target != attempt.primary_execution_target
        or checked_run.execution_target.value != attempt.primary_execution_target
        or checked_artifact.provenance_binding != checked_run.provenance_binding
        or checked_run.provenance_binding.rights_profile_ref
        != attempt.rights_profile_ref
        or attempt.provenance_policy_ref
        not in checked_run.provenance_binding.provenance_refs
        or not attempt.qualification_binding.is_bound
    ):
        raise invalid("/artifact_ref", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    limitations = owner_set(
        tuple(
            dict.fromkeys(
                (
                    *checked_run.applicability_assessment.limitations,
                    *checked_run.conditioning_assessment.limitations,
                    *checked_run.uncertainty_binding.limitations,
                )
            )
        ),
        "restriction",
        "/known_limitations",
        challenge_key=checked_run.challenge_key,
    )
    return {
        "admission_decision_ref": checked.to_ref(),
        "admission_grant_ref": checked_grant.to_ref(),
        "admission_issuance_record_ref": checked_issuance.to_ref(),
        "applicability_assessment": checked_run.applicability_assessment,
        "artifact_ref": checked_artifact.to_ref(),
        "authority_function": checked_run.authority_function,
        "case_ref": checked_run.case_ref,
        "challenge_key": checked_run.challenge_key,
        "comparison_refs": attempt.comparison_refs,
        "conditioning_assessment": checked_run.conditioning_assessment,
        "configuration_ref": checked_run.configuration_ref,
        "dependency_disclosures": (
            checked_run.provenance_binding.dependency_disclosures
        ),
        "disclosure_policy_ref": attempt.disclosure_policy_ref,
        "environment_ref": checked_run.environment_ref,
        "evidence_role_binding": checked_run.evidence_role_binding,
        "execution_target": attempt.primary_execution_target,
        "hardware_ref": checked_run.hardware_ref,
        "implementation_ref": checked_run.implementation_ref,
        "known_limitations": limitations,
        "method_ref": checked_run.method_ref,
        "policy_ref": checked_run.policy_ref,
        "precision_ref": checked_run.precision_ref,
        "provenance_binding": checked_run.provenance_binding,
        "qualification_evidence_ref": attempt.qualification_binding.value,
        "representation_ref": checked_run.representation_ref,
        "rights_profile_ref": attempt.rights_profile_ref,
        "run_ref": checked_run.to_ref(),
        "scope_binding": checked_run.scope_binding,
        "source_class": checked_run.source_class,
        "supersedes": supersedes or OptionalBinding.absent(),
        "truth_asset_id": truth_asset_id,
        "truth_asset_version": truth_asset_version,
        "uncertainty_binding": checked_run.uncertainty_binding,
        "use_restrictions": attempt.use_restrictions,
    }


@dataclass(frozen=True, slots=True)
class _PositiveAdmissionGraph:
    decision_bytes: bytes
    issuance_bytes: bytes
    grant_bytes: bytes
    policy_bytes: bytes
    run_bytes: bytes
    artifact_bytes: bytes
    comparison_bytes: tuple[bytes, ...]


def _build_positive_admission_operations():
    """Close positive graph admission, one-use construction, and reconstruction."""

    lock = threading.RLock()
    positive_graphs: dict[
        TruthAssetAdmissionDecisionRecordRef, _PositiveAdmissionGraph
    ] = {}
    admitted_assets: dict[TruthAssetRef, bytes] = {}

    def decide_truth_asset_admission(
        authority: TruthAssetAdmissionAuthority | None,
        issuance: TruthAssetAdmissionGrantIssuanceRecord,
        grant: TruthAssetAdmissionGrant,
        *,
        policy: ReferencePolicy,
        run: ReferenceRunRecord,
        artifact: ReferenceArtifact | None,
        comparisons: tuple[ReferenceComparisonRecord, ...],
        decision_id: str,
        decision_version: str,
    ) -> TruthAssetAdmissionDecisionRecord | None:
        decision = _decide_truth_asset_admission_record(
            authority,
            issuance,
            grant,
            policy=policy,
            run=run,
            artifact=artifact,
            comparisons=comparisons,
            decision_id=decision_id,
            decision_version=decision_version,
        )
        if (
            decision is None
            or decision.outcome is not TruthAssetAdmissionOutcome.ADMITTED
        ):
            return decision
        from .canonical import canonical_bytes

        checked_decision = exact(
            decision,
            TruthAssetAdmissionDecisionRecord,
            "/admission_decision_ref",
        )
        checked_artifact = exact(artifact, ReferenceArtifact, "/artifact_ref")
        checked_issuance = exact(
            issuance,
            TruthAssetAdmissionGrantIssuanceRecord,
            "/admission_issuance_record_ref",
        )
        checked_grant = exact(grant, TruthAssetAdmissionGrant, "/admission_grant_ref")
        checked_policy = exact(policy, ReferencePolicy, "/policy_ref")
        checked_run = exact(run, ReferenceRunRecord, "/run_ref")
        checked_comparisons = exact_tuple(
            comparisons,
            ReferenceComparisonRecord,
            "/comparison_refs",
            unique=True,
        )
        graph = _PositiveAdmissionGraph(
            canonical_bytes(checked_decision),
            canonical_bytes(checked_issuance),
            canonical_bytes(checked_grant),
            canonical_bytes(checked_policy),
            canonical_bytes(checked_run),
            canonical_bytes(checked_artifact),
            tuple(canonical_bytes(comparison) for comparison in checked_comparisons),
        )
        decision_ref = checked_decision.to_ref()
        with lock:
            if decision_ref in positive_graphs:
                raise invalid(
                    "/admission_decision_ref",
                    ReferenceInputCode.STALE_BINDING,
                )
            positive_graphs[decision_ref] = graph
        return decision

    def create_truth_asset(
        decision: TruthAssetAdmissionDecisionRecord,
        issuance: TruthAssetAdmissionGrantIssuanceRecord,
        grant: TruthAssetAdmissionGrant,
        artifact: ReferenceArtifact,
        run: ReferenceRunRecord,
        *,
        truth_asset_id: str,
        truth_asset_version: str,
        supersedes: OptionalBinding[TruthAssetRef] | None = None,
    ) -> TruthAsset:
        """Atomically consume one exact positive graph to construct one asset."""

        checked_decision = exact(
            decision,
            TruthAssetAdmissionDecisionRecord,
            "/admission_decision_ref",
        )
        decision_ref = checked_decision.to_ref()
        with lock:
            registered = positive_graphs.get(decision_ref)
            if registered is None:
                raise invalid(
                    "/admission_decision_ref",
                    ReferenceInputCode.STALE_BINDING,
                )
            checked_issuance = exact(
                issuance,
                TruthAssetAdmissionGrantIssuanceRecord,
                "/admission_issuance_record_ref",
            )
            checked_grant = exact(
                grant,
                TruthAssetAdmissionGrant,
                "/admission_grant_ref",
            )
            checked_artifact = exact(artifact, ReferenceArtifact, "/artifact_ref")
            checked_run = exact(run, ReferenceRunRecord, "/run_ref")
            from .canonical import canonical_bytes, decode_canonical_bytes

            if (
                registered.decision_bytes != canonical_bytes(checked_decision)
                or registered.issuance_bytes != canonical_bytes(checked_issuance)
                or registered.grant_bytes != canonical_bytes(checked_grant)
                or registered.artifact_bytes != canonical_bytes(checked_artifact)
                or registered.run_bytes != canonical_bytes(checked_run)
            ):
                raise invalid(
                    "/admission_decision_ref",
                    ReferenceInputCode.STALE_BINDING,
                )
            registered_decision = decode_canonical_bytes(
                registered.decision_bytes,
                TruthAssetAdmissionDecisionRecord,
            )
            registered_issuance = decode_canonical_bytes(
                registered.issuance_bytes,
                TruthAssetAdmissionGrantIssuanceRecord,
            )
            registered_grant = decode_canonical_bytes(
                registered.grant_bytes,
                TruthAssetAdmissionGrant,
            )
            registered_policy = decode_canonical_bytes(
                registered.policy_bytes,
                ReferencePolicy,
            )
            registered_run = decode_canonical_bytes(
                registered.run_bytes,
                ReferenceRunRecord,
            )
            registered_artifact = decode_canonical_bytes(
                registered.artifact_bytes,
                ReferenceArtifact,
            )
            registered_comparisons = tuple(
                decode_canonical_bytes(item, ReferenceComparisonRecord)
                for item in registered.comparison_bytes
            )
            if _validate_admission_graph(
                registered_decision.attempt_binding,
                registered_policy,
                registered_run,
                registered_artifact,
                registered_comparisons,
            ):
                raise invalid(
                    "/admission_decision_ref",
                    ReferenceInputCode.STALE_BINDING,
                )
            normalized = _validated_truth_asset_fields(
                registered_decision,
                registered_issuance,
                registered_grant,
                registered_artifact,
                registered_run,
                truth_asset_id=truth_asset_id,
                truth_asset_version=truth_asset_version,
                supersedes=supersedes,
            )
            asset = object.__new__(TruthAsset)
            for name, value in normalized.items():
                object.__setattr__(asset, name, value)
            asset._validate()
            asset_ref = asset.to_ref()
            if asset_ref in admitted_assets:
                raise invalid("/truth_asset_id", ReferenceInputCode.STALE_BINDING)
            positive_graphs.pop(decision_ref)
            admitted_assets[asset_ref] = canonical_bytes(asset)
        return asset

    def reconstruct_truth_asset(
        *,
        _canonical_content_digest: object,
        **fields: object,
    ) -> TruthAsset:
        from .canonical import canonical_bytes

        try:
            asset_ref = TruthAssetRef(
                fields["challenge_key"],
                _canonical_content_digest,
            )
        except (KeyError, ReferenceValidationError, TypeError, ValueError):
            raise invalid(
                "/canonical_bytes",
                ReferenceInputCode.INCOMPLETE_BINDING,
            ) from None
        with lock:
            registered_bytes = admitted_assets.get(asset_ref)
        if registered_bytes is None:
            raise invalid(
                "/canonical_bytes",
                ReferenceInputCode.INCOMPLETE_BINDING,
            )
        asset = object.__new__(TruthAsset)
        for name, value in fields.items():
            object.__setattr__(asset, name, value)
        asset._validate()
        if asset.to_ref() != asset_ref or canonical_bytes(asset) != registered_bytes:
            raise invalid(
                "/canonical_bytes",
                ReferenceInputCode.INCOMPLETE_BINDING,
            )
        return asset

    return (
        decide_truth_asset_admission,
        create_truth_asset,
        reconstruct_truth_asset,
    )


(
    decide_truth_asset_admission,
    create_truth_asset,
    _reconstruct_admitted_truth_asset,
) = _build_positive_admission_operations()
del _build_positive_admission_operations


__all__ = [
    "AdmissionGrantIssuanceEcho",
    "TruthAsset",
    "TruthAssetAdmissionAuthority",
    "TruthAssetAdmissionDecisionRecord",
    "TruthAssetAdmissionEcho",
    "TruthAssetAdmissionGrant",
    "TruthAssetAdmissionGrantIssuanceRecord",
    "TruthAssetAdmissionGrantIssuer",
    "create_truth_asset",
    "create_truth_asset_admission_grant",
    "decide_truth_asset_admission",
    "issue_truth_asset_admission_grant_record",
    "select_admission_grant_issuance_terminal",
    "select_truth_asset_admission_terminal",
]
