"""B-07G local research-service composition and closed dispatch.

This module deliberately owns no domain semantics or mutable lifecycle state.
It selects constructor-bound providers, enforces the B-07S service boundary,
and projects provider results through the one canonical v2 codec.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields, replace
from enum import Enum
from typing import Protocol

from carbon.construction.compiler import (
    CompileAccepted,
    CompileRejected,
    compile_strategy,
)
from carbon.research.canonical import (
    CanonicalWireError,
    _canonical_tuple_payload,
    canonical_bytes,
    load_canonical,
)
from carbon.research.errors import (
    DiscoveryProviderUnavailable,
    ResearchServiceErrorCode,
    public_error,
)
from carbon.research.model import (
    OFFICIAL_V1_OPERATIONS,
    RESEARCH_NAMESPACE,
    SUPPORTED_OPERATIONS,
    ActivePriorSelector,
    CancelResearchTaskRequest,
    CancelResearchTaskResult,
    ChallengeInfo,
    CompileIssue,
    CompileStrategyRequest,
    CompileStrategyResult,
    DryValidateRequest,
    DryValidationResult,
    ExactPriorSelector,
    FixturePriorAuthorization,
    ForecastResourcesRequest,
    GetChallengeInfoRequest,
    GetInteractionManifestRequest,
    GetMockScaffoldRequest,
    GetPriorRequest,
    GetResearchResultRequest,
    GetResearchResultResult,
    InspectPriorAlignmentRequest,
    InspectResourcesRequest,
    InspectResourcesResult,
    InteractionManifest,
    MockScaffold,
    NoPriorSelector,
    PriorAlignmentResult,
    PriorLookupResult,
    PriorPublicationClass,
    PublicFindingEvidenceClass,
    PublicPriorAuthorization,
    ReplyStatus,
    ResourceForecast,
    ServiceCall,
    ServiceReply,
    StartResearchTaskRequest,
    StartResearchTaskResult,
    ValidationIssue,
)
from carbon.research.prior_store import (
    TestOnlyPriorAuthorizationReceipt,
    prior_pack_ref,
)
from carbon.research.providers import (
    ChallengeCatalogProvider,
    CompilationProvider,
    ManifestProvider,
    PriorAlignmentProvider,
    PublicPriorProvider,
    ResearchTaskProvider,
    ResourceForecastProvider,
    ResourceInspectionProvider,
    ScaffoldProvider,
    TestOnlyPriorProvider,
    ValidationProvider,
)
from carbon.research.records import ResolvedStrategy
from carbon.research.refs import (
    PriorChannel,
    StrategyCompilationRef,
    TestOnlyPriorAuthorizationReceiptRef,
    ValidationResultRef,
)
from carbon.schema.strategy import dry_validate

_VALIDATION_DOMAIN = b"carbon.research-validation-result.v2\x00"
_COMPILATION_DOMAIN = b"carbon.research-strategy-compilation.v2\x00"
_FIXTURE_LIMITATIONS = frozenset({"TEST_ONLY", "NOT_UTILITY_QUALIFIED"})
_PROTECTED_RESULT_TOKENS = (
    "official_seed",
    "protected_case",
    "stress_set",
    "truth_asset",
    "gate_configuration",
    "scorer_configuration",
    "private_key",
    "signing_key",
    "credential",
)


class TestOnlyAuthorizationProvider(Protocol):
    """B-07D3-owned lookup used to verify a fixture authorization receipt."""

    def fixture_authorization(
        self, ref: TestOnlyPriorAuthorizationReceiptRef
    ) -> TestOnlyPriorAuthorizationReceipt: ...


def _provider(value: object, method: str) -> None:
    if value is None or not callable(getattr(value, method, None)):
        raise TypeError(f"{method} provider capability is required")


@dataclass(frozen=True, slots=True)
class ExternalPublicResearchContext:
    challenge_catalog_provider: ChallengeCatalogProvider
    manifest_provider: ManifestProvider
    public_prior_provider: PublicPriorProvider
    scaffold_provider: ScaffoldProvider
    validation_provider: ValidationProvider
    compilation_provider: CompilationProvider
    prior_alignment_provider: PriorAlignmentProvider
    resource_inspection_provider: ResourceInspectionProvider
    resource_forecast_provider: ResourceForecastProvider
    research_task_provider: ResearchTaskProvider

    def __post_init__(self) -> None:
        if type(self) is not ExternalPublicResearchContext:
            raise TypeError("external context subclasses are rejected")
        _validate_context(self)


@dataclass(frozen=True, slots=True)
class FixtureResearchContext:
    challenge_catalog_provider: ChallengeCatalogProvider
    manifest_provider: ManifestProvider
    public_prior_provider: PublicPriorProvider
    test_only_prior_provider: TestOnlyPriorProvider
    test_only_authorization_provider: TestOnlyAuthorizationProvider
    scaffold_provider: ScaffoldProvider
    validation_provider: ValidationProvider
    compilation_provider: CompilationProvider
    prior_alignment_provider: PriorAlignmentProvider
    resource_inspection_provider: ResourceInspectionProvider
    resource_forecast_provider: ResourceForecastProvider
    research_task_provider: ResearchTaskProvider

    def __post_init__(self) -> None:
        if type(self) is not FixtureResearchContext:
            raise TypeError("fixture context subclasses are rejected")
        _validate_context(self)
        _provider(self.test_only_prior_provider, "get_prior")
        _provider(
            self.test_only_authorization_provider,
            "fixture_authorization",
        )


def _validate_context(context: object) -> None:
    required = (
        ("challenge_catalog_provider", "get_challenge_info"),
        ("manifest_provider", "get_interaction_manifest"),
        ("public_prior_provider", "get_prior"),
        ("scaffold_provider", "get_mock_scaffold"),
        ("validation_provider", "dry_validate"),
        ("compilation_provider", "compile_strategy"),
        ("prior_alignment_provider", "inspect_prior_alignment"),
        ("resource_inspection_provider", "inspect_resources"),
        ("resource_forecast_provider", "forecast_resources"),
    )
    for attribute, method in required:
        _provider(getattr(context, attribute), method)
    tasks = context.research_task_provider
    for method in (
        "start_research_task",
        "get_research_result",
        "cancel_research_task",
    ):
        _provider(tasks, method)


@dataclass(frozen=True, slots=True)
class OperationContract:
    operation: str
    request_type: type[object]
    result_type: type[object]
    semantic_owner: str
    provider_name: str
    provider_method: str
    context_availability: tuple[str, ...]
    authority_ceiling: str
    disclosure_class: str
    resource_accounting_class: str
    error_surface: tuple[ResearchServiceErrorCode, ...]
    forbidden_cross_namespace_result: ResearchServiceErrorCode


_COMMON_ERRORS = (
    ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID,
    ResearchServiceErrorCode.NAMESPACE_MISMATCH,
    ResearchServiceErrorCode.OPERATION_UNSUPPORTED,
    ResearchServiceErrorCode.REQUEST_TYPE_INVALID,
    ResearchServiceErrorCode.UNKNOWN_FIELD,
    ResearchServiceErrorCode.BOUND_EXCEEDED,
    ResearchServiceErrorCode.FORBIDDEN_SCIENTIFIC_CONTROL,
    ResearchServiceErrorCode.CONTEXT_SELECTION_FORBIDDEN,
    ResearchServiceErrorCode.CHALLENGE_NOT_FOUND,
    ResearchServiceErrorCode.REFERENCE_NOT_FOUND,
    ResearchServiceErrorCode.REFERENCE_MISMATCH,
    ResearchServiceErrorCode.PROVIDER_UNAVAILABLE,
    ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE,
    ResearchServiceErrorCode.DISCLOSURE_REJECTED,
    ResearchServiceErrorCode.INTERNAL_FAILURE,
)
_PRIOR_ERRORS = (
    ResearchServiceErrorCode.PRIOR_INDEX_CHANGED,
    ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID,
    ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID,
)
_TASK_ERRORS = (
    ResearchServiceErrorCode.TASK_NOT_FOUND,
    ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT,
    ResearchServiceErrorCode.INVALID_TASK_TRANSITION,
    ResearchServiceErrorCode.POLL_SEQUENCE_INVALID,
)


def _contract(
    operation: str,
    request_type: type[object],
    result_type: type[object],
    owner: str,
    provider_name: str,
    provider_method: str,
    *,
    authority: str,
    disclosure: str,
    resources: str,
    errors: tuple[ResearchServiceErrorCode, ...] = (),
) -> OperationContract:
    return OperationContract(
        operation,
        request_type,
        result_type,
        owner,
        provider_name,
        provider_method,
        ("EXTERNAL_PUBLIC", "FIXTURE"),
        authority,
        disclosure,
        resources,
        (*_COMMON_ERRORS, *errors),
        ResearchServiceErrorCode.NAMESPACE_MISMATCH,
    )


OPERATION_MATRIX = (
    _contract(
        "get_challenge_info",
        GetChallengeInfoRequest,
        ChallengeInfo,
        "B-07A",
        "challenge_catalog_provider",
        "get_challenge_info",
        authority="PUBLIC_RESEARCH_DISCOVERY",
        disclosure="PUBLIC_RESEARCH",
        resources="NONE",
    ),
    _contract(
        "get_interaction_manifest",
        GetInteractionManifestRequest,
        InteractionManifest,
        "B-07A",
        "manifest_provider",
        "get_interaction_manifest",
        authority="CONTEXT_BOUND_CAPABILITY_DISCOVERY",
        disclosure="PUBLIC_RESEARCH",
        resources="NONE",
    ),
    _contract(
        "get_prior",
        GetPriorRequest,
        PriorLookupResult,
        "B-07D3",
        "ContextPriorProvider",
        "get_prior",
        authority="PUBLIC_OR_TEST_ONLY_FIXTURE",
        disclosure="APPROVED_PRIOR_PROJECTION",
        resources="NONE",
        errors=_PRIOR_ERRORS,
    ),
    _contract(
        "get_mock_scaffold",
        GetMockScaffoldRequest,
        MockScaffold,
        "B-07C",
        "scaffold_provider",
        "get_mock_scaffold",
        authority="MOCK_ONLY_NON_CHAMPION",
        disclosure="MOCK_PRACTICE_ONLY",
        resources="NONE",
    ),
    _contract(
        "dry_validate",
        DryValidateRequest,
        DryValidationResult,
        "A2",
        "validation_provider",
        "dry_validate",
        authority="STRUCTURAL_VALIDATION_ONLY",
        disclosure="PUBLIC_STRUCTURAL_ISSUES",
        resources="NONE",
    ),
    _contract(
        "compile_strategy",
        CompileStrategyRequest,
        CompileStrategyResult,
        "B-02B",
        "compilation_provider",
        "compile_strategy",
        authority="CONSTRUCTION_ONLY_NOT_QUALIFICATION",
        disclosure="PUBLIC_COMPILATION_PROJECTION",
        resources="STATIC_PLAN_METADATA_ONLY",
    ),
    _contract(
        "inspect_prior_alignment",
        InspectPriorAlignmentRequest,
        PriorAlignmentResult,
        "B-07D3",
        "prior_alignment_provider",
        "inspect_prior_alignment",
        authority="GUIDANCE_NOT_GATE",
        disclosure="COARSENED_ALIGNMENT",
        resources="NONE",
        errors=_PRIOR_ERRORS,
    ),
    _contract(
        "inspect_resources",
        InspectResourcesRequest,
        InspectResourcesResult,
        "B-07E",
        "resource_inspection_provider",
        "inspect_resources",
        authority="STATIC_EXACT_NOT_ADMISSION",
        disclosure="PUBLIC_COARSENED_RESOURCE",
        resources="STATIC_INSPECTION",
    ),
    _contract(
        "forecast_resources",
        ForecastResourcesRequest,
        ResourceForecast,
        "B-07E",
        "resource_forecast_provider",
        "forecast_resources",
        authority="NON_BINDING_FORECAST",
        disclosure="PUBLIC_COARSENED_RESOURCE",
        resources="FORECAST_NOT_QUOTE_OR_OBSERVED",
    ),
    _contract(
        "start_research_task",
        StartResearchTaskRequest,
        StartResearchTaskResult,
        "B-07B",
        "research_task_provider",
        "start_research_task",
        authority="LOCAL_RESEARCH_ONLY",
        disclosure="PUBLIC_SAFE_TASK_VIEW",
        resources="REQUESTED_CLASS_BINDING_ONLY",
        errors=(*_PRIOR_ERRORS, *_TASK_ERRORS),
    ),
    _contract(
        "get_research_result",
        GetResearchResultRequest,
        GetResearchResultResult,
        "B-07B",
        "research_task_provider",
        "get_research_result",
        authority="LOCAL_RESEARCH_ONLY",
        disclosure="PUBLIC_SAFE_TASK_OR_RECEIPT",
        resources="OBSERVED_RECEIPT_REF_ONLY",
        errors=_TASK_ERRORS,
    ),
    _contract(
        "cancel_research_task",
        CancelResearchTaskRequest,
        CancelResearchTaskResult,
        "B-07B",
        "research_task_provider",
        "cancel_research_task",
        authority="LOCAL_RESEARCH_ONLY",
        disclosure="CANCELLATION_ACKNOWLEDGEMENT",
        resources="NO_ACCOUNTING_MUTATION",
        errors=_TASK_ERRORS,
    ),
)
OPERATION_CONTRACTS = {item.operation: item for item in OPERATION_MATRIX}
RESERVED_OPERATION = OperationContract(
    "quote_execution",
    object,
    object,
    "FUTURE_WAVE_C",
    "NONE",
    "NONE",
    ("UNAVAILABLE",),
    "CAPABILITY_UNAVAILABLE",
    "NO_RESULT",
    "QUOTE_NOT_IMPLEMENTED",
    (ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE,),
    ResearchServiceErrorCode.NAMESPACE_MISMATCH,
)


class A2ValidationProvider:
    """Thin public projection over A2's existing validation function."""

    __slots__ = ()

    def dry_validate(self, request: DryValidateRequest) -> DryValidationResult:
        if type(request) is not DryValidateRequest:
            raise TypeError("exact DryValidateRequest required")
        result = dry_validate(request.strategy)
        issues = tuple(
            ValidationIssue(
                item.code,
                tuple(part for part in item.path.split("/") if part),
                item.message,
            )
            for item in result.errors
        )
        digest = (
            "sha256:"
            + hashlib.sha256(
                _VALIDATION_DOMAIN
                + _canonical_tuple_payload(
                    (request.challenge_key, request.strategy, issues)
                )
            ).hexdigest()
        )
        return DryValidationResult(
            result.ok,
            issues,
            ValidationResultRef(request.challenge_key, content_digest=digest),
        )


class B02BCompilationProvider:
    """Thin projection/resolver over the one B-02B compiler implementation."""

    __slots__ = (
        "_assembly",
        "_assembly_ref",
        "_authoring_artifacts",
        "_authoring_origin",
        "_catalog",
        "_catalog_ref",
        "_compiler_identity",
        "_strategy_limits",
    )

    def __init__(
        self,
        *,
        candidate_assembly: object,
        candidate_assembly_ref: object,
        parameter_catalog: object,
        parameter_catalog_ref: object,
        authoring_origin: object,
        authoring_artifacts: object,
        compiler_identity: object,
        strategy_limits: object,
    ) -> None:
        self._assembly = candidate_assembly
        self._assembly_ref = candidate_assembly_ref
        self._catalog = parameter_catalog
        self._catalog_ref = parameter_catalog_ref
        self._authoring_origin = authoring_origin
        self._authoring_artifacts = authoring_artifacts
        self._compiler_identity = compiler_identity
        self._strategy_limits = strategy_limits

    def _compile(self, request: CompileStrategyRequest) -> object:
        if type(request) is not CompileStrategyRequest:
            raise TypeError("exact CompileStrategyRequest required")
        return compile_strategy(
            request.strategy,
            challenge_key=request.challenge_key,
            candidate_assembly=self._assembly,
            candidate_assembly_ref=self._assembly_ref,
            parameter_catalog=self._catalog,
            parameter_catalog_ref=self._catalog_ref,
            authoring_origin=self._authoring_origin,
            authoring_artifacts=self._authoring_artifacts,
            compiler_identity=self._compiler_identity,
            strategy_limits=self._strategy_limits,
        )

    @staticmethod
    def _issue_path(path: str) -> tuple[str, ...]:
        return tuple(part for part in path.split("/") if part)

    def compile_strategy(
        self, request: CompileStrategyRequest
    ) -> CompileStrategyResult:
        compiled = self._compile(request)
        if type(compiled) is CompileRejected:
            return CompileStrategyResult(
                False,
                tuple(
                    CompileIssue(
                        item.code,
                        self._issue_path(item.path),
                        item.message,
                    )
                    for item in compiled.issues
                ),
                None,
                None,
                None,
                None,
            )
        if type(compiled) is not CompileAccepted:
            raise TypeError("B-02B compiler returned an invalid result")
        plan = compiled.construction_plan
        if (
            plan.challenge_key != request.challenge_key
            or plan.training_support_ref != request.expected_training_support_ref
        ):
            raise ValueError("B-02B result crosses the request binding")
        digest = (
            "sha256:"
            + hashlib.sha256(
                _COMPILATION_DOMAIN
                + _canonical_tuple_payload(
                    (
                        request,
                        plan.strategy_hash,
                        compiled.training_policy_ref,
                        compiled.construction_plan_ref,
                    )
                )
            ).hexdigest()
        )
        return CompileStrategyResult(
            True,
            (),
            plan.strategy_hash,
            compiled.training_policy_ref,
            compiled.construction_plan_ref,
            StrategyCompilationRef(request.challenge_key, content_digest=digest),
        )

    def resolve_strategy(self, request: CompileStrategyRequest) -> ResolvedStrategy:
        compiled = self._compile(request)
        if type(compiled) is not CompileAccepted:
            raise ValueError("Strategy compilation was rejected")
        return ResolvedStrategy(
            compiled.construction_plan.strategy_hash,
            compiled.training_policy_ref,
            compiled.construction_plan_ref,
            compiled.construction_plan,
            compiled.training_policy,
        )


def _failure(
    code: ResearchServiceErrorCode, *, path: tuple[str, ...] = ()
) -> ServiceReply:
    return ServiceReply(ReplyStatus.ERROR, public_error(code, path=path))


def _request_challenge(request: object) -> object:
    return getattr(request, "challenge_key", None)


def _result_challenge_refs(result: object) -> tuple[object, ...]:
    refs: list[object] = []
    active: set[int] = set()
    stack = [result]
    while stack:
        value = stack.pop()
        if value is None or type(value) in (str, bytes, bool, int, float):
            continue
        if isinstance(value, Enum):
            continue
        if hasattr(value, "challenge_key"):
            refs.append(value)
        if type(value) in (tuple, list):
            stack.extend(value)
        elif hasattr(type(value), "__dataclass_fields__") and id(value) not in active:
            active.add(id(value))
            stack.extend(getattr(value, item.name) for item in fields(value))
    return tuple(refs)


def _discovery_pair_matches(info: object, manifest: object) -> bool:
    if type(info) is not ChallengeInfo or type(manifest) is not InteractionManifest:
        return False
    return (
        info.challenge_key == manifest.challenge_key
        and manifest.challenge_info_ref == info.to_ref()
        and manifest.physical_system_ref == info.physical_system_ref
        and manifest.candidate_output_ref == info.candidate_output_ref
        and manifest.instance_distribution_ref == info.instance_distribution_ref
        and manifest.sampling_plan_ref == info.sampling_plan_ref
        and manifest.training_support_ref == info.training_support_ref
        and manifest.measurement_contract_ref == info.measurement_contract_ref
        and manifest.public_score_policy_ref == info.public_score_policy_ref
    )


def _task_result(result: object) -> object | None:
    if type(result) in (
        StartResearchTaskResult,
        GetResearchResultResult,
        CancelResearchTaskResult,
    ):
        return result.task
    return None


def _contains_protected_result_material(value: object) -> bool:
    active: set[int] = set()
    stack = [value]
    while stack:
        item = stack.pop()
        if type(item) is str:
            normalized = item.casefold().replace("-", "_").replace(" ", "_")
            if any(token in normalized for token in _PROTECTED_RESULT_TOKENS):
                return True
        elif (
            type(item) in (bytes, bool, int, float)
            or item is None
            or isinstance(item, Enum)
        ):
            continue
        elif type(item) in (tuple, list):
            stack.extend(item)
        elif type(item) is dict:
            stack.extend(item.keys())
            stack.extend(item.values())
        elif hasattr(type(item), "__dataclass_fields__") and id(item) not in active:
            active.add(id(item))
            stack.extend(getattr(item, field.name) for field in fields(item))
    return False


class LocalResearchService:
    """Exact local-only ``carbon_research_v2`` service adapter."""

    __slots__ = ("_context", "_fixture")

    def __init__(
        self, context: ExternalPublicResearchContext | FixtureResearchContext
    ) -> None:
        if type(context) not in (
            ExternalPublicResearchContext,
            FixtureResearchContext,
        ):
            raise TypeError("an exact nominal research context is required")
        self._context = context
        self._fixture = type(context) is FixtureResearchContext

    def call(self, call: object) -> ServiceReply:
        if type(call) is not ServiceCall:
            return _failure(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        try:
            canonical_call = load_canonical(canonical_bytes(call), ServiceCall)
        except CanonicalWireError as exc:
            return _failure(exc.code)
        assert type(canonical_call) is ServiceCall
        if canonical_call.namespace != RESEARCH_NAMESPACE:
            return _failure(ResearchServiceErrorCode.NAMESPACE_MISMATCH)
        operation = canonical_call.operation
        if operation in OFFICIAL_V1_OPERATIONS:
            return _failure(ResearchServiceErrorCode.NAMESPACE_MISMATCH)
        if operation == RESERVED_OPERATION.operation:
            return _failure(ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE)
        contract = OPERATION_CONTRACTS.get(operation)
        if contract is None:
            return _failure(ResearchServiceErrorCode.OPERATION_UNSUPPORTED)
        request = canonical_call.request
        if type(request) is not contract.request_type:
            return _failure(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        capability = self._preflight_capability(request)
        if capability is not None:
            return capability
        info: ChallengeInfo | None = None
        try:
            if operation != "get_challenge_info":
                info = self._context.challenge_catalog_provider.get_challenge_info(
                    request.challenge_key
                )
                if type(info) is not ChallengeInfo:
                    return _failure(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
                if info.challenge_key != request.challenge_key:
                    return _failure(ResearchServiceErrorCode.REFERENCE_MISMATCH)
            result = self._dispatch(contract, request)
        except Exception as exc:  # noqa: BLE001 - translated without diagnostics
            return self._provider_failure(exc, operation)
        projected = self._project(contract, request, result, info)
        if type(projected) is ServiceReply:
            return projected
        reply = ServiceReply(ReplyStatus.OK, projected)
        try:
            canonical_bytes(reply)
        except CanonicalWireError as exc:
            return _failure(
                exc.code
                if exc.code is ResearchServiceErrorCode.BOUND_EXCEEDED
                else ResearchServiceErrorCode.DISCLOSURE_REJECTED
            )
        return reply

    def call_bytes(self, payload: object) -> bytes:
        try:
            call = load_canonical(payload, ServiceCall)
        except CanonicalWireError as exc:
            return canonical_bytes(_failure(exc.code))
        return canonical_bytes(self.call(call))

    def _preflight_capability(self, request: object) -> ServiceReply | None:
        if type(request) is GetPriorRequest:
            if type(request.selector) is NoPriorSelector:
                return _failure(
                    ResearchServiceErrorCode.REQUEST_TYPE_INVALID,
                    path=("request", "selector"),
                )
            channel = (
                request.selector.channel
                if type(request.selector) is ActivePriorSelector
                else request.selector.prior_pack_ref.channel
            )
            if channel is PriorChannel.TEST_ONLY_FIXTURE:
                if not self._fixture or type(request.selector) is ActivePriorSelector:
                    return _failure(
                        ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID,
                        path=("request", "selector"),
                    )
            elif channel is not PriorChannel.PUBLIC:
                return _failure(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        if type(request) is StartResearchTaskRequest:
            selector = request.prior_selector
            if type(selector) is ActivePriorSelector:
                channel = selector.channel
            elif type(selector) is ExactPriorSelector:
                channel = selector.prior_pack_ref.channel
            else:
                channel = None
            if channel is PriorChannel.TEST_ONLY_FIXTURE and not self._fixture:
                return _failure(
                    ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID,
                    path=("request", "prior_selector"),
                )
        return None

    def _dispatch(self, contract: OperationContract, request: object) -> object:
        if contract.operation == "get_prior":
            assert type(request) is GetPriorRequest
            selector = request.selector
            channel = (
                selector.channel
                if type(selector) is ActivePriorSelector
                else selector.prior_pack_ref.channel
            )
            provider = (
                self._context.test_only_prior_provider
                if channel is PriorChannel.TEST_ONLY_FIXTURE
                and type(self._context) is FixtureResearchContext
                else self._context.public_prior_provider
            )
            return provider.get_prior(request)
        provider = getattr(self._context, contract.provider_name)
        method = getattr(provider, contract.provider_method)
        if contract.operation in ("get_challenge_info", "get_interaction_manifest"):
            return method(request.challenge_key)
        return method(request)

    def _project(
        self,
        contract: OperationContract,
        request: object,
        result: object,
        info: ChallengeInfo | None,
    ) -> object:
        if type(result) is not contract.result_type:
            return _failure(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        if _contains_protected_result_material(result):
            return _failure(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        challenge = _request_challenge(request)
        if any(
            item.challenge_key != challenge for item in _result_challenge_refs(result)
        ):
            return _failure(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        if type(result) is InteractionManifest:
            try:
                if not _discovery_pair_matches(info, result):
                    return _failure(ResearchServiceErrorCode.REFERENCE_MISMATCH)
                result = replace(
                    result,
                    capability_labels=(
                        ("TEST_ONLY_FIXTURE_PRIOR",) if self._fixture else ()
                    ),
                )
            except Exception:  # noqa: BLE001 - provider graph is untrusted
                return _failure(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        if type(result) is PriorLookupResult:
            error = self._validate_prior_result(request, result)
            if error is not None:
                return error
        if type(result) is MockScaffold and (
            not result.limitations or "MOCK_ONLY" not in result.limitations
        ):
            return _failure(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        task = _task_result(result)
        if task is not None:
            if task.challenge_key != challenge:
                return _failure(ResearchServiceErrorCode.REFERENCE_MISMATCH)
            receipt = task.terminal_receipt
            prior_ref = task.immutable_bindings.prior_pack_ref
            if (
                receipt is not None
                and prior_ref is not None
                and prior_ref.channel is PriorChannel.TEST_ONLY_FIXTURE
                and (
                    not _FIXTURE_LIMITATIONS.issubset(receipt.limitations)
                    or any(
                        finding.evidence_class
                        is not PublicFindingEvidenceClass.TEST_ONLY
                        for finding in receipt.public_findings
                    )
                )
            ):
                return _failure(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
        try:
            detached = load_canonical(canonical_bytes(result), contract.result_type)
        except CanonicalWireError as exc:
            return _failure(
                exc.code
                if exc.code is ResearchServiceErrorCode.BOUND_EXCEEDED
                else ResearchServiceErrorCode.DISCLOSURE_REJECTED
            )
        return detached

    def _validate_prior_result(
        self, request: object, result: PriorLookupResult
    ) -> ServiceReply | None:
        assert type(request) is GetPriorRequest
        pack = result.prior_pack
        if (
            result.prior_pack_ref.challenge_key != request.challenge_key
            or pack.challenge_key != request.challenge_key
            or result.prior_pack_ref != prior_pack_ref(pack)
            or result.index_snapshot_ref.channel is not pack.channel
        ):
            return _failure(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        if pack.channel is PriorChannel.PUBLIC:
            if type(
                result.authorization
            ) is not PublicPriorAuthorization or pack.publication_class not in (
                PriorPublicationClass.BOOTSTRAP_PUBLIC,
                PriorPublicationClass.LEARNED_PUBLIC,
            ):
                return _failure(ResearchServiceErrorCode.DISCLOSURE_REJECTED)
            return None
        if not self._fixture or (
            type(result.authorization) is not FixturePriorAuthorization
            or pack.publication_class is not PriorPublicationClass.TEST_ONLY
            or not _FIXTURE_LIMITATIONS.issubset(pack.limitations)
        ):
            return _failure(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        context = self._context
        assert type(context) is FixtureResearchContext
        try:
            receipt = context.test_only_authorization_provider.fixture_authorization(
                result.authorization.receipt_ref
            )
        except Exception:  # noqa: BLE001 - authorization diagnostics are private
            return _failure(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        if (
            type(receipt) is not TestOnlyPriorAuthorizationReceipt
            or receipt.challenge_key != request.challenge_key
            or receipt.prior_pack_ref != result.prior_pack_ref
            or receipt.authority_ceiling != "NOT_UTILITY_QUALIFIED"
        ):
            return _failure(ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID)
        return None

    @staticmethod
    def _provider_failure(exc: Exception, operation: str) -> ServiceReply:
        if type(exc) is DiscoveryProviderUnavailable:
            code = ResearchServiceErrorCode.PROVIDER_UNAVAILABLE
        elif type(exc) in (TimeoutError, ConnectionError):
            code = ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE
        elif isinstance(exc, (KeyError, LookupError)):
            code = (
                ResearchServiceErrorCode.CHALLENGE_NOT_FOUND
                if operation in ("get_challenge_info", "get_interaction_manifest")
                else ResearchServiceErrorCode.REFERENCE_NOT_FOUND
            )
        else:
            candidate = getattr(exc, "code", None)
            provider_codes = {
                ResearchServiceErrorCode.CHALLENGE_NOT_FOUND,
                ResearchServiceErrorCode.REFERENCE_NOT_FOUND,
                ResearchServiceErrorCode.REFERENCE_MISMATCH,
                ResearchServiceErrorCode.PRIOR_INDEX_CHANGED,
                ResearchServiceErrorCode.PRIOR_IDENTITY_INVALID,
                ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID,
                ResearchServiceErrorCode.TASK_NOT_FOUND,
                ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT,
                ResearchServiceErrorCode.INVALID_TASK_TRANSITION,
                ResearchServiceErrorCode.POLL_SEQUENCE_INVALID,
                ResearchServiceErrorCode.PROVIDER_UNAVAILABLE,
                ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE,
            }
            code = (
                candidate
                if type(candidate) is ResearchServiceErrorCode
                and candidate in provider_codes
                else ResearchServiceErrorCode.INTERNAL_FAILURE
            )
        return _failure(code)


assert tuple(OPERATION_CONTRACTS) == SUPPORTED_OPERATIONS


__all__ = (
    "OPERATION_CONTRACTS",
    "OPERATION_MATRIX",
    "RESERVED_OPERATION",
    "A2ValidationProvider",
    "B02BCompilationProvider",
    "ExternalPublicResearchContext",
    "FixtureResearchContext",
    "LocalResearchService",
    "OperationContract",
    "TestOnlyAuthorizationProvider",
)
