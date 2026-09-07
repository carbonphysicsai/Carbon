"""Fail-closed service-response boundary for B-E2 reference executions.

The boundary wraps B-04's exact request, grant, resolution, run, provenance,
and failure types.  It adds no reference status, fallback, retry policy,
candidate result, score, artifact store, network transport, or Julia runtime.
Provider responses are treated as hostile and can contribute only closed B-04
facts after every registered execution binding matches.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from types import FunctionType
from typing import Protocol
from weakref import WeakKeyDictionary

from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.refs import CanonicalChallengeCaseRef

from .enums import (
    ConditioningStatus,
    ReferenceArtifactOrigin,
    ReferenceAuthorityFunction,
    ReferenceFailureReason,
    ReferenceRunOutcome,
    ReferenceSourceClass,
    ResolutionOutcome,
    SupportApplicabilityStatus,
    UncertaintyStatus,
)
from .errors import (
    ReferenceInputCode,
    ReferenceServiceCode,
    ReferenceServiceError,
    ReferenceValidationError,
    _reference_provider_control_signal,
)
from .execution import (
    PrimaryReferenceRequest,
    PrimaryRunGrant,
    ReferenceResolutionRecord,
    ReferenceRunRecord,
    WitnessReferenceRequest,
    WitnessRunGrant,
    _bind_run_attempt_executor,
    _claim_run_attempt,
    _inspect_run_attempt,
    create_reference_run_record,
    select_run_terminal,
)
from .model import (
    ArtifactContentBinding,
    ConditioningAssessment,
    PinnedReferenceIdentity,
    ProtectedReferenceValue,
    RealizedComponentBinding,
    ReferenceAuthorityTarget,
    ReferenceProvenance,
    ReferenceScopeBinding,
    ReferenceWitnessTarget,
    SupportApplicabilityAssessment,
    UncertaintyRepresentation,
)
from .refs import (
    PrimaryReferenceRequestRef,
    PrimaryRunGrantRef,
    ReferencePolicyRef,
    ReferenceResolutionRecordRef,
    WitnessReferenceRequestRef,
    WitnessRunGrantRef,
)
from .runners import validate_primary_invocation, validate_witness_invocation


class PrimaryReferenceService(Protocol):
    """Registered primary provider behind a trusted local adapter."""

    def execute_primary(
        self,
        grant: PrimaryRunGrant,
        request: PrimaryReferenceRequest,
    ) -> object: ...


class WitnessReferenceService(Protocol):
    """Registered witness provider behind a trusted local adapter."""

    def execute_witness(
        self,
        grant: WitnessRunGrant,
        request: WitnessReferenceRequest,
    ) -> object: ...


@dataclass(frozen=True, slots=True, repr=False)
class RegisteredReferenceServiceContext(ProtectedReferenceValue):
    """Trusted execution facts fixed before crossing the provider boundary."""

    applicability_assessment: SupportApplicabilityAssessment
    artifact_descriptor_ref: PinnedReferenceIdentity
    component_bindings: tuple[RealizedComponentBinding, ...]
    conditioning_assessment: ConditioningAssessment
    diagnostics_ref: PinnedReferenceIdentity
    provenance_binding: ReferenceProvenance
    resource_receipt_ref: PinnedReferenceIdentity
    run_id: str
    run_version: str
    uncertainty_binding: UncertaintyRepresentation

    def __post_init__(self) -> None:
        expected = (
            (self.applicability_assessment, SupportApplicabilityAssessment),
            (self.artifact_descriptor_ref, PinnedReferenceIdentity),
            (self.conditioning_assessment, ConditioningAssessment),
            (self.diagnostics_ref, PinnedReferenceIdentity),
            (self.provenance_binding, ReferenceProvenance),
            (self.resource_receipt_ref, PinnedReferenceIdentity),
            (self.uncertainty_binding, UncertaintyRepresentation),
        )
        if type(self) is not RegisteredReferenceServiceContext or any(
            type(value) is not exact_type for value, exact_type in expected
        ):
            raise ReferenceValidationError(ReferenceInputCode.WRONG_TYPE)
        if type(self.component_bindings) is not tuple or not self.component_bindings:
            raise ReferenceValidationError(
                ReferenceInputCode.INCOMPLETE_BINDING,
                path="/component_bindings",
            )
        if any(
            type(item) is not RealizedComponentBinding
            for item in self.component_bindings
        ):
            raise ReferenceValidationError(
                ReferenceInputCode.WRONG_TYPE,
                path="/component_bindings",
            )
        if type(self.run_id) is not str or type(self.run_version) is not str:
            raise ReferenceValidationError(ReferenceInputCode.WRONG_TYPE)

    def __repr__(self) -> str:
        return "RegisteredReferenceServiceContext(<protected>)"

    __str__ = __repr__


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceServiceResponse(ProtectedReferenceValue):
    """Untrusted, complete response envelope; validation occurs in the adapter."""

    answer_key_authority_target: ReferenceAuthorityTarget
    applicability_assessment: SupportApplicabilityAssessment
    artifact_content: ArtifactContentBinding | None
    authority_function: ReferenceAuthorityFunction
    case_ref: CanonicalChallengeCaseRef
    component_bindings: tuple[RealizedComponentBinding, ...]
    conditioning_assessment: ConditioningAssessment
    configuration_ref: PinnedReferenceIdentity
    diagnostics_ref: PinnedReferenceIdentity
    environment_ref: PinnedReferenceIdentity
    evidence_role_binding: EvidenceRoleBinding
    execution_target: ReferenceAuthorityTarget | ReferenceWitnessTarget
    grant_ref: PrimaryRunGrantRef | WitnessRunGrantRef
    hardware_ref: PinnedReferenceIdentity
    implementation_ref: PinnedReferenceIdentity
    method_ref: PinnedReferenceIdentity
    observed_reasons: tuple[ReferenceFailureReason, ...]
    policy_ref: ReferencePolicyRef
    precision_ref: PinnedReferenceIdentity
    provenance_binding: ReferenceProvenance
    representation_ref: PinnedReferenceIdentity
    request_ref: PrimaryReferenceRequestRef | WitnessReferenceRequestRef
    resolution_ref: ReferenceResolutionRecordRef
    resource_receipt_ref: PinnedReferenceIdentity
    run_id: str
    run_version: str
    scope_binding: ReferenceScopeBinding
    source_class: ReferenceSourceClass
    uncertainty_binding: UncertaintyRepresentation

    def __repr__(self) -> str:
        return "ReferenceServiceResponse(<protected>)"

    __str__ = __repr__


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceServiceAttempt(ProtectedReferenceValue):
    """One exact B-04 request/grant/resolution/run tuple."""

    grant: PrimaryRunGrant | WitnessRunGrant
    request: PrimaryReferenceRequest | WitnessReferenceRequest
    resolution: ReferenceResolutionRecord
    run: ReferenceRunRecord

    def __post_init__(self) -> None:
        if type(self) is not ReferenceServiceAttempt:
            raise ReferenceValidationError(ReferenceInputCode.WRONG_TYPE)
        if type(self.request) is PrimaryReferenceRequest:
            if type(self.grant) is not PrimaryRunGrant:
                raise ReferenceValidationError(
                    ReferenceInputCode.ROLE_MISMATCH,
                    path="/grant",
                )
        elif type(self.request) is WitnessReferenceRequest:
            if type(self.grant) is not WitnessRunGrant:
                raise ReferenceValidationError(
                    ReferenceInputCode.ROLE_MISMATCH,
                    path="/grant",
                )
        else:
            raise ReferenceValidationError(
                ReferenceInputCode.WRONG_TYPE,
                path="/request",
            )
        if (
            type(self.resolution) is not ReferenceResolutionRecord
            or type(self.run) is not ReferenceRunRecord
            or self.resolution.request_binding.value != self.request.to_ref()
            or self.resolution.grant_binding.value != self.grant.to_ref()
            or self.run.request_binding.value != self.request.to_ref()
            or self.run.grant_binding.value != self.grant.to_ref()
            or self.run.resolution_ref != self.resolution.to_ref()
        ):
            raise ReferenceValidationError(
                ReferenceInputCode.STALE_BINDING,
                path="/resolution_ref",
            )

    def __repr__(self) -> str:
        return "ReferenceServiceAttempt(<protected>)"

    __str__ = __repr__


def _retry_identity(attempt: ReferenceServiceAttempt) -> tuple[object, ...]:
    request = attempt.request
    grant = attempt.grant
    return (
        request.answer_key_authority_target,
        request.case_ref,
        request.challenge_key,
        request.disclosure_policy_ref,
        request.execution_target,
        request.idempotency_ref,
        request.policy_ref,
        request.representation_ref,
        request.request_version,
        request.requested_resource_policy_ref,
        request.scope_binding,
        grant.authority_function,
        grant.capability_ref,
        grant.component_entry_refs,
        grant.configuration_ref,
        grant.environment_ref,
        grant.evidence_role_binding,
        grant.hardware_ref,
        grant.implementation_ref,
        grant.issuer_ref,
        grant.method_ref,
        grant.policy_ref,
        grant.precision_ref,
        grant.representation_ref,
        grant.resource_authorization_ref,
        grant.source_class,
        attempt.run.component_bindings,
        replace(
            attempt.run.applicability_assessment,
            status=SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE,
        ),
        replace(
            attempt.run.conditioning_assessment,
            status=ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE,
        ),
        replace(
            attempt.run.uncertainty_binding,
            status=UncertaintyStatus.RESOLVED,
        ),
        attempt.run.provenance_binding,
    )


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceServiceAttemptHistory(ProtectedReferenceValue):
    """Identity-preserving trace that never collapses retry outcomes."""

    attempts: tuple[ReferenceServiceAttempt, ...]

    def __post_init__(self) -> None:
        if (
            type(self) is not ReferenceServiceAttemptHistory
            or type(self.attempts) is not tuple
        ):
            raise ReferenceValidationError(ReferenceInputCode.WRONG_TYPE)
        if not self.attempts or any(
            type(item) is not ReferenceServiceAttempt for item in self.attempts
        ):
            raise ReferenceValidationError(ReferenceInputCode.INCOMPLETE_BINDING)
        request_refs = tuple(item.request.to_ref() for item in self.attempts)
        grant_refs = tuple(item.grant.to_ref() for item in self.attempts)
        run_refs = tuple(item.run.to_ref() for item in self.attempts)
        if any(
            len(set(refs)) != len(refs) for refs in (request_refs, grant_refs, run_refs)
        ):
            raise ReferenceValidationError(ReferenceInputCode.DUPLICATE_IDENTITY)
        identity = _retry_identity(self.attempts[0])
        for index, attempt in enumerate(self.attempts):
            if _retry_identity(attempt) != identity:
                raise ReferenceValidationError(
                    ReferenceInputCode.STALE_BINDING,
                    path=f"/attempt_binding/{index}",
                )
            if (
                index < len(self.attempts) - 1
                and attempt.run.outcome is ReferenceRunOutcome.SUPPORTED
            ):
                raise ReferenceValidationError(
                    ReferenceInputCode.STALE_BINDING,
                    path=f"/attempt_binding/{index}",
                )

    def __repr__(self) -> str:
        return "ReferenceServiceAttemptHistory(<protected>)"

    __str__ = __repr__


def _safe_exact_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    try:
        return bool(actual == expected)
    except Exception:  # noqa: BLE001 - hostile equality is never authoritative.
        return False


def _same_assessment_identity(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    try:
        return _safe_exact_equal(replace(actual, status=expected.status), expected)
    except Exception:  # noqa: BLE001 - hostile partial carriers fail closed.
        return False


def _expected_identity_fields(
    response: ReferenceServiceResponse,
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    grant: PrimaryRunGrant | WitnessRunGrant,
    resolution: ReferenceResolutionRecord,
    context: RegisteredReferenceServiceContext,
) -> tuple[tuple[object, object], ...]:
    return (
        (response.answer_key_authority_target, request.answer_key_authority_target),
        (response.authority_function, grant.authority_function),
        (response.case_ref, request.case_ref),
        (response.component_bindings, context.component_bindings),
        (response.configuration_ref, grant.configuration_ref),
        (response.diagnostics_ref, context.diagnostics_ref),
        (response.environment_ref, grant.environment_ref),
        (response.evidence_role_binding, grant.evidence_role_binding),
        (response.execution_target, request.execution_target),
        (response.grant_ref, grant.to_ref()),
        (response.hardware_ref, grant.hardware_ref),
        (response.implementation_ref, grant.implementation_ref),
        (response.method_ref, grant.method_ref),
        (response.policy_ref, request.policy_ref),
        (response.precision_ref, grant.precision_ref),
        (response.representation_ref, grant.representation_ref),
        (response.request_ref, request.to_ref()),
        (response.resolution_ref, resolution.to_ref()),
        (response.resource_receipt_ref, context.resource_receipt_ref),
        (response.run_id, context.run_id),
        (response.run_version, context.run_version),
        (response.scope_binding, request.scope_binding),
        (response.source_class, grant.source_class),
    )


def _failure_assessments(
    context: RegisteredReferenceServiceContext,
    reason: ReferenceFailureReason,
) -> tuple[
    SupportApplicabilityAssessment, ConditioningAssessment, UncertaintyRepresentation
]:
    applicability = context.applicability_assessment
    conditioning = context.conditioning_assessment
    uncertainty = context.uncertainty_binding
    if reason is ReferenceFailureReason.POLICY_ENTRY_NOT_APPLICABLE:
        applicability = replace(
            applicability, status=SupportApplicabilityStatus.NOT_APPLICABLE
        )
    elif reason is ReferenceFailureReason.POLICY_ENTRY_UNSUPPORTED:
        applicability = replace(
            applicability, status=SupportApplicabilityStatus.UNSUPPORTED
        )
    elif reason is ReferenceFailureReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE:
        applicability = replace(
            applicability, status=SupportApplicabilityStatus.ASSESSMENT_UNAVAILABLE
        )
    elif reason is ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED:
        conditioning = replace(conditioning, status=ConditioningStatus.UNRESOLVED)
    elif reason is ReferenceFailureReason.UNCERTAINTY_EVIDENCE_UNRESOLVED:
        uncertainty = replace(uncertainty, status=UncertaintyStatus.UNRESOLVED)
    return applicability, conditioning, uncertainty


def _create_failure_run(
    *,
    runner: object,
    capability: object,
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    grant: PrimaryRunGrant | WitnessRunGrant,
    resolution: ReferenceResolutionRecord,
    context: RegisteredReferenceServiceContext,
    reason: ReferenceFailureReason,
) -> ReferenceRunRecord:
    applicability, conditioning, uncertainty = _failure_assessments(context, reason)
    return create_reference_run_record(
        request=request,
        grant=grant,
        resolution=resolution,
        observed_reasons=(reason,),
        artifact_content=None,
        applicability_assessment=applicability,
        component_bindings=context.component_bindings,
        conditioning_assessment=conditioning,
        diagnostics_ref=context.diagnostics_ref,
        provenance_binding=context.provenance_binding,
        resource_receipt_ref=context.resource_receipt_ref,
        run_id=context.run_id,
        run_version=context.run_version,
        uncertainty_binding=uncertainty,
        _attempt_executor=runner,
        _attempt_capability=capability,
    )


def _classify_provider_exception(error: Exception) -> ReferenceFailureReason:
    if type(error) is TimeoutError:
        return ReferenceFailureReason.TIMEOUT
    if type(error) in (ModuleNotFoundError, ImportError):
        return ReferenceFailureReason.DEPENDENCY_UNAVAILABLE
    if isinstance(error, ConnectionError):
        return ReferenceFailureReason.TRANSPORT_FAILURE
    if type(error) is ReferenceServiceError and error.code in {
        ReferenceServiceCode.RESOLVER_UNAVAILABLE.value,
        ReferenceServiceCode.RUNNER_UNAVAILABLE.value,
    }:
        return ReferenceFailureReason.DEPENDENCY_UNAVAILABLE
    return ReferenceFailureReason.PROCESS_FAILURE


def _create_response_run(
    *,
    runner: object,
    capability: object,
    response: object,
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    grant: PrimaryRunGrant | WitnessRunGrant,
    resolution: ReferenceResolutionRecord,
    context: RegisteredReferenceServiceContext,
) -> ReferenceRunRecord:
    if type(response) is not ReferenceServiceResponse:
        return _create_failure_run(
            runner=runner,
            capability=capability,
            request=request,
            grant=grant,
            resolution=resolution,
            context=context,
            reason=ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
        )
    try:
        if any(
            not _safe_exact_equal(actual, expected)
            for actual, expected in _expected_identity_fields(
                response, request, grant, resolution, context
            )
        ):
            reason = ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH
        elif not _safe_exact_equal(
            response.provenance_binding, context.provenance_binding
        ):
            reason = ReferenceFailureReason.PROVENANCE_INVALID
        elif not (
            _same_assessment_identity(
                response.applicability_assessment,
                context.applicability_assessment,
            )
            and _same_assessment_identity(
                response.conditioning_assessment,
                context.conditioning_assessment,
            )
            and _same_assessment_identity(
                response.uncertainty_binding,
                context.uncertainty_binding,
            )
        ):
            reason = ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH
        else:
            select_run_terminal(response.observed_reasons)
            reason = None
    except Exception:  # noqa: BLE001 - malformed hostile response.
        reason = ReferenceFailureReason.PROVIDER_RESULT_MALFORMED
    if reason is not None:
        return _create_failure_run(
            runner=runner,
            capability=capability,
            request=request,
            grant=grant,
            resolution=resolution,
            context=context,
            reason=reason,
        )
    artifact = response.artifact_content
    if artifact is not None and (
        type(artifact) is not ArtifactContentBinding
        or artifact.artifact_origin is not ReferenceArtifactOrigin.FIXTURE_ONLY
        or not _safe_exact_equal(
            artifact.artifact_descriptor_ref,
            context.artifact_descriptor_ref,
        )
    ):
        return _create_failure_run(
            runner=runner,
            capability=capability,
            request=request,
            grant=grant,
            resolution=resolution,
            context=context,
            reason=ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH,
        )
    try:
        return create_reference_run_record(
            request=request,
            grant=grant,
            resolution=resolution,
            observed_reasons=response.observed_reasons,
            artifact_content=artifact,
            applicability_assessment=response.applicability_assessment,
            component_bindings=response.component_bindings,
            conditioning_assessment=response.conditioning_assessment,
            diagnostics_ref=response.diagnostics_ref,
            provenance_binding=response.provenance_binding,
            resource_receipt_ref=response.resource_receipt_ref,
            run_id=response.run_id,
            run_version=response.run_version,
            uncertainty_binding=response.uncertainty_binding,
            _attempt_executor=runner,
            _attempt_capability=capability,
        )
    except ReferenceValidationError:
        return _create_failure_run(
            runner=runner,
            capability=capability,
            request=request,
            grant=grant,
            resolution=resolution,
            context=context,
            reason=ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
        )


def _static_service_method(provider: object, name: str) -> FunctionType:
    try:
        for owner in type.__getattribute__(type(provider), "__mro__"):
            namespace = type.__getattribute__(owner, "__dict__")
            if name in namespace:
                member = namespace[name]
                if type(member) is FunctionType:
                    return member
                break
    except Exception:  # noqa: BLE001 - hostile provider class.
        raise ReferenceValidationError(
            ReferenceInputCode.AUTHORITY_INTERFACE_INVALID,
            path="/runner",
        ) from None
    raise ReferenceValidationError(
        ReferenceInputCode.AUTHORITY_INTERFACE_INVALID,
        path="/runner",
    )


def _create_service_runner_state():
    lock = threading.Lock()
    states: WeakKeyDictionary[object, tuple[object, ...]] = WeakKeyDictionary()

    def register(
        runner: object,
        provider: object,
        method_name: str,
        request: PrimaryReferenceRequest | WitnessReferenceRequest,
        grant: PrimaryRunGrant | WitnessRunGrant,
        resolution: ReferenceResolutionRecord,
        context: RegisteredReferenceServiceContext,
    ) -> None:
        method = _static_service_method(provider, method_name)
        capability = _bind_run_attempt_executor(resolution, runner)
        with lock:
            states[runner] = (
                provider,
                method,
                request,
                grant,
                resolution,
                context,
                capability,
                False,
            )

    def begin(
        runner: object,
        request: PrimaryReferenceRequest | WitnessReferenceRequest,
        grant: PrimaryRunGrant | WitnessRunGrant,
    ) -> tuple[object, ...]:
        with lock:
            state = states.get(runner)
            if (
                state is None
                or state[7] is True
                or state[2] != request
                or state[3] != grant
            ):
                raise ReferenceValidationError(
                    ReferenceInputCode.STALE_BINDING,
                    path="/grant",
                )
            _inspect_run_attempt(state[4], request, grant, runner, state[6])
            claimed = (*state[:7], True)
            states[runner] = claimed
            return claimed

    return register, begin


_register_service_runner, _begin_service_attempt = _create_service_runner_state()
del _create_service_runner_state


class _RegisteredReferenceServiceRunnerBase:
    __slots__ = ("__weakref__",)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("registered reference service runners are immutable")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected reference service runners cannot be pickled")

    def _execute(
        self,
        grant: PrimaryRunGrant | WitnessRunGrant,
        request: PrimaryReferenceRequest | WitnessReferenceRequest,
    ) -> ReferenceRunRecord:
        state = _begin_service_attempt(self, request, grant)
        provider, method, _, _, resolution, context, capability, _ = state
        control_signal = False
        try:
            response = method(provider, grant, request)
        except Exception as error:  # noqa: BLE001 - provider text is discarded.
            reason = _classify_provider_exception(error)
            return _create_failure_run(
                runner=self,
                capability=capability,
                request=request,
                grant=grant,
                resolution=resolution,
                context=context,
                reason=reason,
            )
        except BaseException:  # noqa: BLE001 - normalize provider control flow.
            control_signal = True
        if control_signal:
            _claim_run_attempt(resolution, request, grant, self, capability)
            raise _reference_provider_control_signal() from None
        try:
            return _create_response_run(
                runner=self,
                capability=capability,
                response=response,
                request=request,
                grant=grant,
                resolution=resolution,
                context=context,
            )
        except Exception:  # noqa: BLE001 - post-provider bugs never permit replay.
            try:
                _claim_run_attempt(resolution, request, grant, self, capability)
            except ReferenceValidationError:
                pass
            raise ReferenceServiceError(ReferenceServiceCode.INTERNAL_FAILURE) from None


class RegisteredPrimaryReferenceServiceRunner(_RegisteredReferenceServiceRunnerBase):
    """One-use exact primary adapter for an already registered service."""

    __slots__ = ()

    def __init__(
        self,
        provider: PrimaryReferenceService,
        request: PrimaryReferenceRequest,
        grant: PrimaryRunGrant,
        resolution: ReferenceResolutionRecord,
        context: RegisteredReferenceServiceContext,
    ) -> None:
        validate_primary_invocation(grant, request)
        if (
            type(resolution) is not ReferenceResolutionRecord
            or resolution.outcome is not ResolutionOutcome.PRIMARY_GRANT_ISSUED
            or type(context) is not RegisteredReferenceServiceContext
        ):
            raise ReferenceValidationError(ReferenceInputCode.STALE_BINDING)
        _register_service_runner(
            self,
            provider,
            "execute_primary",
            request,
            grant,
            resolution,
            context,
        )

    def run_primary(
        self,
        grant: PrimaryRunGrant,
        request: PrimaryReferenceRequest,
    ) -> ReferenceRunRecord:
        validate_primary_invocation(grant, request)
        return self._execute(grant, request)


class RegisteredWitnessReferenceServiceRunner(_RegisteredReferenceServiceRunnerBase):
    """One-use exact witness adapter for an already registered service."""

    __slots__ = ()

    def __init__(
        self,
        provider: WitnessReferenceService,
        request: WitnessReferenceRequest,
        grant: WitnessRunGrant,
        resolution: ReferenceResolutionRecord,
        context: RegisteredReferenceServiceContext,
    ) -> None:
        validate_witness_invocation(grant, request)
        if (
            type(resolution) is not ReferenceResolutionRecord
            or resolution.outcome is not ResolutionOutcome.WITNESS_GRANT_ISSUED
            or type(context) is not RegisteredReferenceServiceContext
        ):
            raise ReferenceValidationError(ReferenceInputCode.STALE_BINDING)
        _register_service_runner(
            self,
            provider,
            "execute_witness",
            request,
            grant,
            resolution,
            context,
        )

    def run_witness(
        self,
        grant: WitnessRunGrant,
        request: WitnessReferenceRequest,
    ) -> ReferenceRunRecord:
        validate_witness_invocation(grant, request)
        return self._execute(grant, request)


__all__ = [
    "PrimaryReferenceService",
    "ReferenceServiceAttempt",
    "ReferenceServiceAttemptHistory",
    "ReferenceServiceResponse",
    "RegisteredPrimaryReferenceServiceRunner",
    "RegisteredReferenceServiceContext",
    "RegisteredWitnessReferenceServiceRunner",
    "WitnessReferenceService",
]
