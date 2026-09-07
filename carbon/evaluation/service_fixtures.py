"""Deterministic TEST_ONLY reference-service fixtures for B-E2."""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from weakref import WeakKeyDictionary

from carbon.authoring.canonical import tagged_sha256
from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.model import EvidenceRole

from . import fixtures as b04_fixtures
from .comparison import ReferenceComparisonRecord
from .enums import (
    ConditioningStatus,
    ReferenceArtifactOrigin,
    ReferenceAuthorityFunction,
    ReferenceFailureReason,
    ReferenceIdentityKind,
    SupportApplicabilityStatus,
    UncertaintyStatus,
)
from .errors import ReferenceServiceCode, ReferenceServiceError
from .execution import (
    PrimaryReferenceRequest,
    PrimaryRunGrant,
    WitnessReferenceRequest,
    WitnessRunGrant,
)
from .model import ArtifactContentBinding
from .policy import ReferencePolicyEntry
from .service_boundary import (
    ReferenceServiceAttempt,
    ReferenceServiceAttemptHistory,
    ReferenceServiceResponse,
    RegisteredPrimaryReferenceServiceRunner,
    RegisteredReferenceServiceContext,
    RegisteredWitnessReferenceServiceRunner,
)

_FIXTURE_TOKEN = object()
_FIXTURE_PAYLOAD = b"CARBON B-E2 FIXTURE REFERENCE SERVICE PAYLOAD V1\n"


def _components(
    grant: PrimaryRunGrant | WitnessRunGrant,
    graph: b04_fixtures.B04FixtureReferenceGraph,
):
    source = graph.primary_run if type(grant) is PrimaryRunGrant else graph.witness_run
    return tuple(
        replace(
            component,
            configuration_ref=grant.configuration_ref,
            environment_ref=grant.environment_ref,
            hardware_ref=grant.hardware_ref,
            implementation_ref=grant.implementation_ref,
            method_ref=grant.method_ref,
            precision_ref=grant.precision_ref,
        )
        for component in source.component_bindings
    )


def _context(
    grant: PrimaryRunGrant | WitnessRunGrant,
    graph: b04_fixtures.B04FixtureReferenceGraph,
    label: str,
) -> RegisteredReferenceServiceContext:
    source = graph.primary_run if type(grant) is PrimaryRunGrant else graph.witness_run
    return RegisteredReferenceServiceContext(
        applicability_assessment=source.applicability_assessment,
        artifact_descriptor_ref=b04_fixtures._identity(
            ReferenceIdentityKind.ARTIFACT_DESCRIPTOR,
            f"be2_{label}_artifact",
            graph.challenge_key,
        ),
        component_bindings=_components(grant, graph),
        conditioning_assessment=source.conditioning_assessment,
        diagnostics_ref=b04_fixtures._identity(
            ReferenceIdentityKind.DIAGNOSTICS,
            f"be2_{label}_diagnostics",
            graph.challenge_key,
        ),
        provenance_binding=replace(
            source.provenance_binding,
            environment_ref=grant.environment_ref,
            implementation_ref=grant.implementation_ref,
            method_ref=grant.method_ref,
        ),
        resource_receipt_ref=b04_fixtures._identity(
            ReferenceIdentityKind.RESOURCE_RECEIPT,
            f"be2_{label}_receipt",
            graph.challenge_key,
        ),
        run_id=f"be2_fixture_{label}_run",
        run_version="1.0",
        uncertainty_binding=source.uncertainty_binding,
    )


def _response(
    request: PrimaryReferenceRequest | WitnessReferenceRequest,
    grant: PrimaryRunGrant | WitnessRunGrant,
    resolution,
    context: RegisteredReferenceServiceContext,
    *,
    reason: ReferenceFailureReason | None = None,
) -> ReferenceServiceResponse:
    applicability = context.applicability_assessment
    conditioning = context.conditioning_assessment
    uncertainty = context.uncertainty_binding
    if reason is ReferenceFailureReason.POLICY_ENTRY_NOT_APPLICABLE:
        applicability = replace(
            applicability,
            status=SupportApplicabilityStatus.NOT_APPLICABLE,
        )
    elif reason is ReferenceFailureReason.POLICY_ENTRY_UNSUPPORTED:
        applicability = replace(
            applicability,
            status=SupportApplicabilityStatus.UNSUPPORTED,
        )
    elif reason is ReferenceFailureReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE:
        applicability = replace(
            applicability,
            status=SupportApplicabilityStatus.ASSESSMENT_UNAVAILABLE,
        )
    elif reason is ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED:
        conditioning = replace(conditioning, status=ConditioningStatus.UNRESOLVED)
    elif reason is ReferenceFailureReason.UNCERTAINTY_EVIDENCE_UNRESOLVED:
        uncertainty = replace(uncertainty, status=UncertaintyStatus.UNRESOLVED)
    return ReferenceServiceResponse(
        answer_key_authority_target=request.answer_key_authority_target,
        applicability_assessment=applicability,
        artifact_content=(
            ArtifactContentBinding(
                tagged_sha256(_FIXTURE_PAYLOAD),
                context.artifact_descriptor_ref,
                ReferenceArtifactOrigin.FIXTURE_ONLY,
            )
            if reason is None
            else None
        ),
        authority_function=grant.authority_function,
        case_ref=request.case_ref,
        component_bindings=context.component_bindings,
        conditioning_assessment=conditioning,
        configuration_ref=grant.configuration_ref,
        diagnostics_ref=context.diagnostics_ref,
        environment_ref=grant.environment_ref,
        evidence_role_binding=grant.evidence_role_binding,
        execution_target=request.execution_target,
        grant_ref=grant.to_ref(),
        hardware_ref=grant.hardware_ref,
        implementation_ref=grant.implementation_ref,
        method_ref=grant.method_ref,
        observed_reasons=() if reason is None else (reason,),
        policy_ref=request.policy_ref,
        precision_ref=grant.precision_ref,
        provenance_binding=context.provenance_binding,
        representation_ref=grant.representation_ref,
        request_ref=request.to_ref(),
        resolution_ref=resolution.to_ref(),
        resource_receipt_ref=context.resource_receipt_ref,
        run_id=context.run_id,
        run_version=context.run_version,
        scope_binding=request.scope_binding,
        source_class=grant.source_class,
        uncertainty_binding=uncertainty,
    )


def _create_provider_state():
    lock = threading.Lock()
    states: WeakKeyDictionary[object, tuple[str, object]] = WeakKeyDictionary()

    def register(provider: object, kind: str, value: object, token: object) -> None:
        if token is not _FIXTURE_TOKEN:
            raise TypeError("B-E2 fixture providers require the fixed builder")
        with lock:
            states[provider] = (kind, value)

    def execute(provider: object) -> object:
        with lock:
            state = states.get(provider)
        if state is None:
            raise ReferenceServiceError(ReferenceServiceCode.RUNNER_UNAVAILABLE)
        kind, value = state
        if kind == "response":
            return value
        if kind == "timeout":
            raise TimeoutError("protected fixture timeout")
        if kind == "unavailable":
            raise ReferenceServiceError(ReferenceServiceCode.RUNNER_UNAVAILABLE)
        if kind == "transport":
            raise ConnectionError("protected fixture transport")
        if kind == "process":
            raise RuntimeError("protected fixture process")
        raise ReferenceServiceError(ReferenceServiceCode.INTERNAL_FAILURE)

    return register, execute


_register_provider, _execute_provider = _create_provider_state()
del _create_provider_state


class _FixedPrimaryService:
    __slots__ = ("__weakref__",)

    def __init__(self, kind: str, value: object, *, _token: object) -> None:
        _register_provider(self, kind, value, _token)

    def execute_primary(self, grant: PrimaryRunGrant, request: PrimaryReferenceRequest):
        del grant, request
        return _execute_provider(self)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("B-E2 fixture providers are immutable")

    def __repr__(self) -> str:
        return "_FixedPrimaryService(<protected>)"

    __str__ = __repr__


class _FixedWitnessService:
    __slots__ = ("__weakref__",)

    def __init__(self, kind: str, value: object, *, _token: object) -> None:
        _register_provider(self, kind, value, _token)

    def execute_witness(self, grant: WitnessRunGrant, request: WitnessReferenceRequest):
        del grant, request
        return _execute_provider(self)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("B-E2 fixture providers are immutable")

    def __repr__(self) -> str:
        return "_FixedWitnessService(<protected>)"

    __str__ = __repr__


@dataclass(frozen=True, slots=True, repr=False)
class BE2FixtureServicePath:
    """One completed deterministic provider-bound B-04 attempt."""

    attempt: ReferenceServiceAttempt
    response: object
    runner: (
        RegisteredPrimaryReferenceServiceRunner
        | RegisteredWitnessReferenceServiceRunner
    )

    def __repr__(self) -> str:
        return "BE2FixtureServicePath(<protected>)"

    __str__ = __repr__


@dataclass(frozen=True, slots=True, repr=False)
class BE2ReferenceFailureFixtureGraph:
    """Complete bounded fixture proof for B-E2 service failure separation."""

    comparison: ReferenceComparisonRecord
    conditioning: BE2FixtureServicePath
    dependency_unavailable: BE2FixtureServicePath
    identity_mismatch: BE2FixtureServicePath
    malformed: BE2FixtureServicePath
    manufactured_verification_anchor: ReferencePolicyEntry
    not_applicable: BE2FixtureServicePath
    numerical_failure: BE2FixtureServicePath
    process_failure: BE2FixtureServicePath
    provenance_failure: BE2FixtureServicePath
    retry_history: ReferenceServiceAttemptHistory
    supported: BE2FixtureServicePath
    timeout: BE2FixtureServicePath
    transport_failure: BE2FixtureServicePath
    uncertainty: BE2FixtureServicePath
    unsupported: BE2FixtureServicePath
    witness_supported: BE2FixtureServicePath

    def __repr__(self) -> str:
        return "BE2ReferenceFailureFixtureGraph(<protected>)"

    __str__ = __repr__


def _unstarted_attempt(
    graph: b04_fixtures.B04FixtureReferenceGraph,
    label: str,
    *,
    request: PrimaryReferenceRequest | None = None,
    grant: PrimaryRunGrant | None = None,
):
    if request is None:
        created_request = b04_fixtures._request(
            label=f"be2_{label}",
            policy=graph.policy,
            case_ref=graph.case_ref,
            witness=False,
        )
        if type(created_request) is not PrimaryReferenceRequest:
            raise ReferenceServiceError(ReferenceServiceCode.INTERNAL_FAILURE)
        request = created_request
    if grant is None:
        created_grant = b04_fixtures._grant(
            label=f"be2_{label}",
            request=request,
            component_entry_refs=graph.compositions[0].member_entry_refs,
        )
        if type(created_grant) is not PrimaryRunGrant:
            raise ReferenceServiceError(ReferenceServiceCode.INTERNAL_FAILURE)
        grant = created_grant
    resolution = b04_fixtures._resolution(
        label=f"be2_{label}",
        request=request,
        grant=grant,
        policy=graph.policy,
        entries=graph.entries,
        compositions=graph.compositions,
        manifest=graph.precomputed_manifest,
    )
    return request, grant, resolution, _context(grant, graph, label)


def _complete_path(
    graph: b04_fixtures.B04FixtureReferenceGraph,
    label: str,
    *,
    reason: ReferenceFailureReason | None = None,
    provider_kind: str = "response",
    response_mutator=None,
) -> BE2FixtureServicePath:
    request, grant, resolution, context = _unstarted_attempt(graph, label)
    response: object = _response(
        request,
        grant,
        resolution,
        context,
        reason=reason,
    )
    if response_mutator is not None:
        response = response_mutator(response, graph)
    provider = _FixedPrimaryService(provider_kind, response, _token=_FIXTURE_TOKEN)
    runner = RegisteredPrimaryReferenceServiceRunner(
        provider,
        request,
        grant,
        resolution,
        context,
    )
    run = runner.run_primary(grant, request)
    return BE2FixtureServicePath(
        ReferenceServiceAttempt(grant, request, resolution, run),
        response,
        runner,
    )


def _complete_witness_path(
    graph: b04_fixtures.B04FixtureReferenceGraph,
) -> BE2FixtureServicePath:
    label = "witness_supported"
    request = b04_fixtures._request(
        label=f"be2_{label}",
        policy=graph.policy,
        case_ref=graph.case_ref,
        witness=True,
    )
    if type(request) is not WitnessReferenceRequest:
        raise ReferenceServiceError(ReferenceServiceCode.INTERNAL_FAILURE)
    grant = b04_fixtures._grant(
        label=f"be2_{label}",
        request=request,
        component_entry_refs=(graph.entries[-1].to_ref(),),
    )
    if type(grant) is not WitnessRunGrant:
        raise ReferenceServiceError(ReferenceServiceCode.INTERNAL_FAILURE)
    resolution = b04_fixtures._resolution(
        label=f"be2_{label}",
        request=request,
        grant=grant,
        policy=graph.policy,
        entries=graph.entries,
        compositions=graph.compositions,
        manifest=graph.precomputed_manifest,
    )
    context = _context(grant, graph, label)
    response = _response(request, grant, resolution, context)
    provider = _FixedWitnessService("response", response, _token=_FIXTURE_TOKEN)
    runner = RegisteredWitnessReferenceServiceRunner(
        provider,
        request,
        grant,
        resolution,
        context,
    )
    run = runner.run_witness(grant, request)
    return BE2FixtureServicePath(
        ReferenceServiceAttempt(grant, request, resolution, run),
        response,
        runner,
    )


def _retry_history(
    graph: b04_fixtures.B04FixtureReferenceGraph,
) -> ReferenceServiceAttemptHistory:
    first = _complete_path(
        graph,
        "retry_initial",
        provider_kind="unavailable",
    ).attempt
    request = replace(
        first.request,
        request_id="be2_fixture_retry_followup_request",
    )
    grant = replace(
        first.grant,
        grant_id="be2_fixture_retry_followup_grant",
        issuance_token="be2-fixture-retry-followup-issuance-v1",
        request_ref=request.to_ref(),
    )
    request, grant, resolution, context = _unstarted_attempt(
        graph,
        "retry_followup",
        request=request,
        grant=grant,
    )
    response = _response(request, grant, resolution, context)
    provider = _FixedPrimaryService("response", response, _token=_FIXTURE_TOKEN)
    runner = RegisteredPrimaryReferenceServiceRunner(
        provider,
        request,
        grant,
        resolution,
        context,
    )
    run = runner.run_primary(grant, request)
    second = ReferenceServiceAttempt(grant, request, resolution, run)
    return ReferenceServiceAttemptHistory((first, second))


def _build_be2_reference_failure_fixture_graph() -> BE2ReferenceFailureFixtureGraph:
    graph = b04_fixtures.build_b04_fixture_reference_graph()
    anchor = replace(
        graph.entries[-1],
        authority_function=ReferenceAuthorityFunction.VERIFICATION_ANCHOR,
        entry_id="be2_fixture_mms_verification_anchor",
        evidence_role_binding=EvidenceRoleBinding(
            EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
        ),
    )
    supported = _complete_path(graph, "supported")
    uncertainty = _complete_path(
        graph,
        "uncertainty",
        reason=ReferenceFailureReason.UNCERTAINTY_EVIDENCE_UNRESOLVED,
    )
    conditioning = _complete_path(
        graph,
        "conditioning",
        reason=ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED,
    )
    not_applicable = _complete_path(
        graph,
        "not_applicable",
        reason=ReferenceFailureReason.POLICY_ENTRY_NOT_APPLICABLE,
    )
    unsupported = _complete_path(
        graph,
        "unsupported",
        reason=ReferenceFailureReason.POLICY_ENTRY_UNSUPPORTED,
    )
    numerical = _complete_path(
        graph,
        "numerical",
        reason=ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
    )
    malformed = _complete_path(
        graph,
        "malformed",
        response_mutator=lambda response, _: {"partial": response},
    )
    provenance = _complete_path(
        graph,
        "provenance",
        response_mutator=lambda response, fixture: replace(
            response,
            provenance_binding=replace(
                response.provenance_binding,
                source_ref=fixture.witness_run.provenance_binding.source_ref,
            ),
        ),
    )
    identity = _complete_path(
        graph,
        "identity",
        response_mutator=lambda response, _: replace(
            response,
            request_ref=replace(
                response.request_ref,
                content_digest=tagged_sha256(b"stale B-E2 fixture response"),
            ),
        ),
    )
    return BE2ReferenceFailureFixtureGraph(
        comparison=graph.comparison,
        conditioning=conditioning,
        dependency_unavailable=_complete_path(
            graph,
            "dependency_unavailable",
            provider_kind="unavailable",
        ),
        identity_mismatch=identity,
        malformed=malformed,
        manufactured_verification_anchor=anchor,
        not_applicable=not_applicable,
        numerical_failure=numerical,
        process_failure=_complete_path(
            graph,
            "process_failure",
            provider_kind="process",
        ),
        provenance_failure=provenance,
        retry_history=_retry_history(graph),
        supported=supported,
        timeout=_complete_path(graph, "timeout", provider_kind="timeout"),
        transport_failure=_complete_path(
            graph,
            "transport_failure",
            provider_kind="transport",
        ),
        uncertainty=uncertainty,
        unsupported=unsupported,
        witness_supported=_complete_witness_path(graph),
    )


def _memoize_builder(raw_builder):
    lock = threading.Lock()
    graph: BE2ReferenceFailureFixtureGraph | None = None

    def build() -> BE2ReferenceFailureFixtureGraph:
        nonlocal graph
        with lock:
            if graph is None:
                graph = raw_builder()
            return graph

    return build


build_be2_reference_failure_fixture_graph = _memoize_builder(
    _build_be2_reference_failure_fixture_graph
)
del _build_be2_reference_failure_fixture_graph
del _memoize_builder


__all__ = [
    "BE2FixtureServicePath",
    "BE2ReferenceFailureFixtureGraph",
    "build_be2_reference_failure_fixture_graph",
]
