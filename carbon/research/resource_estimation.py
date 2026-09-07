"""B-07E exact static inspection and fail-closed resource forecasting.

This module implements the two existing B-07S provider seams.  It deliberately
does not implement dispatch, execution admission, quotes, observed receipts,
or a production calibration path.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_uint64,
    validate_version_token,
)
from carbon.authoring.refs import InstanceDistributionContractRef
from carbon.construction.model import CompilerIdentity, EnvironmentPin
from carbon.registry import ChallengeKey
from carbon.research.canonical import _canonical_tuple_payload
from carbon.research.errors import ResearchServiceErrorCode
from carbon.research.model import (
    CompileStrategyRequest,
    ForecastResourcesRequest,
    InspectResourcesRequest,
    InspectResourcesResult,
    ResourceForecast,
    ResourceLineItem,
)
from carbon.research.records import ResolvedStrategy
from carbon.research.refs import ResourceForecastRef
from carbon.resource_policy import (
    ClassBundle,
    ResearchResourcePolicy,
    ResearchResourcePolicyRef,
    ResourceClass,
    ResourceClassRef,
    ResourceObservationRole,
    StaticAssessmentOutcome,
    StaticResourceAssessment,
    assess_static_resources,
    research_resource_policy_to_ref,
    static_resource_assessment_to_ref,
    validate_research_resource_policy_bundle,
)

_FORECAST_DOMAIN = b"carbon.resource-forecast.v2\x00"
_MAX_EXACT_BINARY64_INTEGER = 1 << 53


class ResourceEstimationProviderError(RuntimeError):
    """Closed provider failure for later B-07G wire translation."""

    def __init__(self, code: ResearchServiceErrorCode):
        if type(code) is not ResearchServiceErrorCode:
            raise TypeError("code must use the exact research error enum")
        self.code = code
        super().__init__(code.value)


class ForecastSupportState(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNRESOLVED = "UNRESOLVED"


class ForecastUnresolvedReason(str, Enum):
    CALIBRATION_AUTHORITY_UNAVAILABLE = "CALIBRATION_AUTHORITY_UNAVAILABLE"
    STATIC_ASSESSMENT_NOT_ADMISSIBLE = "STATIC_ASSESSMENT_NOT_ADMISSIBLE"
    UNSUPPORTED_DISTRIBUTION = "UNSUPPORTED_DISTRIBUTION"
    UNSUPPORTED_HORIZON = "UNSUPPORTED_HORIZON"
    STALE_MODEL = "STALE_MODEL"
    STALE_CALIBRATION = "STALE_CALIBRATION"
    MISCALIBRATED = "MISCALIBRATED"
    MODEL_SCOPE_MISMATCH = "MODEL_SCOPE_MISMATCH"
    HARDWARE_SCOPE_MISMATCH = "HARDWARE_SCOPE_MISMATCH"
    MODEL_EVALUATION_FAILED = "MODEL_EVALUATION_FAILED"
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"


class ForecastCalibrationStatus(str, Enum):
    VALID = "VALID"
    MISCALIBRATED = "MISCALIBRATED"


class ForecastAuthorityMarker(str, Enum):
    TEST_ONLY_SYNTHETIC_CALIBRATION_NOT_PRODUCTION = (
        "TEST_ONLY_SYNTHETIC_CALIBRATION_NOT_PRODUCTION"
    )


class _CompilationResolver(Protocol):
    def resolve_strategy(self, request: CompileStrategyRequest) -> ResolvedStrategy: ...


class SyntheticForecastEngine(Protocol):
    def forecast(
        self,
        request: ForecastResourcesRequest,
        static_result: InspectResourcesResult,
        calibration: SyntheticForecastCalibration,
    ) -> SyntheticForecastMaterial: ...


def _exact_type(value: object, expected: type[object], name: str) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must use its exact nominal type")


def _canonical_id(value: object, name: str) -> str:
    return validate_canonical_id(value, name)


def _version(value: object, name: str) -> str:
    return validate_version_token(value, name)


def _digest(value: object, name: str) -> str:
    return validate_tagged_sha256(value, name)


def _epoch(value: object, name: str) -> int:
    return validate_uint64(value, name)


def _finite_nonnegative(value: object, name: str) -> float:
    if type(value) is not float or not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be an exact finite non-negative float")
    return value


def _exact_float(quantity: int) -> float:
    if quantity > _MAX_EXACT_BINARY64_INTEGER:
        raise ResourceEstimationProviderError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    projected = float(quantity)
    if int(projected) != quantity:
        raise ResourceEstimationProviderError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    return projected


def _unit_label(dimension_or_metric_id: str, unit_ref: object) -> str:
    object_id = getattr(unit_ref, "object_id", None)
    if type(object_id) is not str:
        raise ResourceEstimationProviderError(
            ResearchServiceErrorCode.REFERENCE_MISMATCH
        )
    return f"{dimension_or_metric_id}:{object_id}"


@dataclass(frozen=True, slots=True)
class _StaticResolution:
    resolved_strategy: ResolvedStrategy
    assessment: StaticResourceAssessment
    result: InspectResourcesResult


class StaticResourceInspectionProvider:
    """Exact plan-derived inspection behind the ratified v2 provider Protocol."""

    __slots__ = (
        "_authority_context",
        "_class_bundle",
        "_compiler",
        "_expected_training_support_ref",
        "_policy",
        "_policy_ref",
        "_resource_class",
        "_resource_class_ref",
    )

    def __init__(
        self,
        *,
        compilation_resolver: _CompilationResolver,
        expected_training_support_ref: object,
        policy: ResearchResourcePolicy,
        policy_ref: ResearchResourcePolicyRef,
        class_bundle: ClassBundle,
        selected_resource_class: ResourceClass,
        selected_resource_class_ref: ResourceClassRef,
        authority_context: object,
    ) -> None:
        from carbon.authoring.refs import TrainingSupportContractRef

        if not callable(getattr(compilation_resolver, "resolve_strategy", None)):
            raise TypeError("a compilation resolver is required")
        _exact_type(
            expected_training_support_ref,
            TrainingSupportContractRef,
            "expected_training_support_ref",
        )
        _exact_type(policy, ResearchResourcePolicy, "policy")
        _exact_type(policy_ref, ResearchResourcePolicyRef, "policy_ref")
        _exact_type(selected_resource_class, ResourceClass, "selected_resource_class")
        _exact_type(
            selected_resource_class_ref,
            ResourceClassRef,
            "selected_resource_class_ref",
        )
        verified_bundle = validate_research_resource_policy_bundle(
            policy, class_bundle=class_bundle
        )
        if (
            research_resource_policy_to_ref(policy, class_bundle=verified_bundle)
            != policy_ref
        ):
            raise ValueError("policy bytes and ref differ")
        if (
            selected_resource_class,
            selected_resource_class_ref,
        ) not in verified_bundle:
            raise ValueError("selected resource class is outside the policy bundle")
        if (
            policy.challenge_key != selected_resource_class.challenge_key
            or policy.challenge_key != expected_training_support_ref.challenge_key
            or policy.authority_context != authority_context
        ):
            raise ValueError("static provider bindings cross authority scopes")
        self._compiler = compilation_resolver
        self._expected_training_support_ref = expected_training_support_ref
        self._policy = policy
        self._policy_ref = policy_ref
        self._class_bundle = verified_bundle
        self._resource_class = selected_resource_class
        self._resource_class_ref = selected_resource_class_ref
        self._authority_context = authority_context

    @property
    def challenge_key(self) -> ChallengeKey:
        return self._policy.challenge_key

    @property
    def policy_ref(self) -> ResearchResourcePolicyRef:
        return self._policy_ref

    @property
    def resource_class(self) -> ResourceClass:
        return self._resource_class

    @property
    def resource_class_ref(self) -> ResourceClassRef:
        return self._resource_class_ref

    def inspect_resources(
        self, request: InspectResourcesRequest
    ) -> InspectResourcesResult:
        return self._resolve_static(request).result

    def _resolve_static(self, request: object) -> _StaticResolution:
        if type(request) is not InspectResourcesRequest:
            raise ResourceEstimationProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            )
        if (
            request.challenge_key != self._policy.challenge_key
            or request.resource_policy_ref != self._policy_ref
        ):
            raise ResourceEstimationProviderError(
                ResearchServiceErrorCode.REFERENCE_MISMATCH
            )
        compile_request = CompileStrategyRequest(
            request.challenge_key,
            request.strategy,
            self._expected_training_support_ref,
        )
        try:
            resolved = self._compiler.resolve_strategy(compile_request)
        except ResourceEstimationProviderError:
            raise
        except Exception:  # noqa: BLE001 - compiler diagnostics cannot cross.
            raise ResourceEstimationProviderError(
                ResearchServiceErrorCode.PROVIDER_UNAVAILABLE
            ) from None
        if type(resolved) is not ResolvedStrategy:
            raise ResourceEstimationProviderError(
                ResearchServiceErrorCode.PROVIDER_UNAVAILABLE
            )
        if (
            resolved.resolved_plan.challenge_key != request.challenge_key
            or resolved.resolved_plan.training_support_ref
            != self._expected_training_support_ref
        ):
            raise ResourceEstimationProviderError(
                ResearchServiceErrorCode.REFERENCE_MISMATCH
            )
        try:
            assessment = assess_static_resources(
                plan=resolved.resolved_plan,
                plan_ref=resolved.resolved_plan_ref,
                policy=self._policy,
                policy_ref=self._policy_ref,
                class_bundle=self._class_bundle,
                selected_class=self._resource_class,
                selected_class_ref=self._resource_class_ref,
                expected_active_policy_ref=self._policy_ref,
                expected_active_resource_class_ref=self._resource_class_ref,
                authority_context=self._authority_context,
            )
            assessment_ref = static_resource_assessment_to_ref(assessment)
            if len(assessment.static_resource_requirements) > 128:
                raise ResourceEstimationProviderError(
                    ResearchServiceErrorCode.BOUND_EXCEEDED
                )
            line_items = tuple(
                ResourceLineItem(
                    self._resource_class_ref,
                    _exact_float(requirement.quantity),
                    _unit_label(requirement.dimension_id, requirement.unit_ref),
                    (
                        _exact_float(requirement.quantity),
                        _exact_float(requirement.quantity),
                    ),
                )
                for requirement in assessment.static_resource_requirements
            )
            binding = next(
                item
                for item in self._policy.class_bindings
                if item.resource_class_ref == self._resource_class_ref
            )
            ceilings = {
                item.dimension_id: item.maximum_quantity for item in binding.ceilings
            }
            limitations = (
                "STATIC_EXACT_PLAN_DERIVED",
                f"ASSESSMENT:{assessment.outcome.value}",
                "NOT_FORECAST",
                "NOT_BINDING_QUOTE_OR_ADMISSION",
                "NOT_OBSERVED_RESOURCE_RECEIPT",
                "NOT_SCIENTIFIC_EVIDENCE",
                *tuple(
                    f"DECLARED_CEILING:{item.dimension_id}:{ceilings[item.dimension_id]}"
                    for item in assessment.static_resource_requirements
                ),
            )
            result = InspectResourcesResult(assessment_ref, line_items, limitations)
        except ResourceEstimationProviderError:
            raise
        except Exception:  # noqa: BLE001 - policy internals cannot cross.
            raise ResourceEstimationProviderError(
                ResearchServiceErrorCode.REFERENCE_MISMATCH
            ) from None
        return _StaticResolution(resolved, assessment, result)


@dataclass(frozen=True, slots=True)
class SyntheticForecastModelIdentity:
    model_id: str
    model_version: str
    implementation_digest: str
    provenance_digest: str
    valid_from_epoch: int
    valid_through_epoch: int

    def __post_init__(self) -> None:
        _exact_type(self, SyntheticForecastModelIdentity, "model identity")
        object.__setattr__(self, "model_id", _canonical_id(self.model_id, "model_id"))
        object.__setattr__(
            self, "model_version", _version(self.model_version, "model_version")
        )
        object.__setattr__(
            self,
            "implementation_digest",
            _digest(self.implementation_digest, "implementation_digest"),
        )
        object.__setattr__(
            self,
            "provenance_digest",
            _digest(self.provenance_digest, "provenance_digest"),
        )
        start = _epoch(self.valid_from_epoch, "valid_from_epoch")
        end = _epoch(self.valid_through_epoch, "valid_through_epoch")
        if start > end:
            raise ValueError("model validity interval is reversed")
        object.__setattr__(self, "valid_from_epoch", start)
        object.__setattr__(self, "valid_through_epoch", end)


@dataclass(frozen=True, slots=True)
class SyntheticForecastCalibrationWindow:
    window_id: str
    window_version: str
    calibration_digest: str
    evidence_start_epoch: int
    evidence_end_epoch: int
    valid_through_epoch: int

    def __post_init__(self) -> None:
        _exact_type(self, SyntheticForecastCalibrationWindow, "calibration window")
        object.__setattr__(
            self, "window_id", _canonical_id(self.window_id, "window_id")
        )
        object.__setattr__(
            self, "window_version", _version(self.window_version, "window_version")
        )
        object.__setattr__(
            self,
            "calibration_digest",
            _digest(self.calibration_digest, "calibration_digest"),
        )
        start = _epoch(self.evidence_start_epoch, "evidence_start_epoch")
        end = _epoch(self.evidence_end_epoch, "evidence_end_epoch")
        valid = _epoch(self.valid_through_epoch, "valid_through_epoch")
        if start > end or end > valid:
            raise ValueError("calibration window is reversed or stale at creation")
        object.__setattr__(self, "evidence_start_epoch", start)
        object.__setattr__(self, "evidence_end_epoch", end)
        object.__setattr__(self, "valid_through_epoch", valid)


@dataclass(frozen=True, slots=True)
class SyntheticForecastScope:
    challenge_key: ChallengeKey
    instance_distribution_ref: InstanceDistributionContractRef
    resource_policy_ref: ResearchResourcePolicyRef
    resource_class_ref: ResourceClassRef
    compiler_identity: CompilerIdentity
    environment_pin: EnvironmentPin

    def __post_init__(self) -> None:
        _exact_type(self, SyntheticForecastScope, "forecast scope")
        key = reconstruct_challenge_key(self.challenge_key)
        _exact_type(
            self.instance_distribution_ref,
            InstanceDistributionContractRef,
            "instance_distribution_ref",
        )
        _exact_type(
            self.resource_policy_ref,
            ResearchResourcePolicyRef,
            "resource_policy_ref",
        )
        _exact_type(self.resource_class_ref, ResourceClassRef, "resource_class_ref")
        _exact_type(self.compiler_identity, CompilerIdentity, "compiler_identity")
        _exact_type(self.environment_pin, EnvironmentPin, "environment_pin")
        if any(
            ref.challenge_key != key
            for ref in (
                self.instance_distribution_ref,
                self.resource_policy_ref,
                self.resource_class_ref,
            )
        ):
            raise ValueError("forecast scope crosses Challenge identities")
        object.__setattr__(self, "challenge_key", key)


@dataclass(frozen=True, slots=True)
class SyntheticForecastCalibration:
    model: SyntheticForecastModelIdentity
    window: SyntheticForecastCalibrationWindow
    scope: SyntheticForecastScope
    maximum_horizon_seconds: int
    status: ForecastCalibrationStatus
    authority_marker: ForecastAuthorityMarker

    def __post_init__(self) -> None:
        _exact_type(self, SyntheticForecastCalibration, "calibration")
        _exact_type(self.model, SyntheticForecastModelIdentity, "model")
        _exact_type(self.window, SyntheticForecastCalibrationWindow, "window")
        _exact_type(self.scope, SyntheticForecastScope, "scope")
        horizon = _epoch(self.maximum_horizon_seconds, "maximum_horizon_seconds")
        if horizon < 1 or horizon > 604_800:
            raise ValueError("maximum forecast horizon is outside the wire bound")
        if type(self.status) is not ForecastCalibrationStatus:
            raise TypeError("calibration status must use its exact enum")
        if (
            type(self.authority_marker) is not ForecastAuthorityMarker
            or self.authority_marker
            is not ForecastAuthorityMarker.TEST_ONLY_SYNTHETIC_CALIBRATION_NOT_PRODUCTION
        ):
            raise ValueError("synthetic calibration lacks its test-only marker")
        object.__setattr__(self, "maximum_horizon_seconds", horizon)


@dataclass(frozen=True, slots=True)
class SyntheticForecastEstimate:
    metric_id: str
    quantity: float
    lower: float
    upper: float

    def __post_init__(self) -> None:
        _exact_type(self, SyntheticForecastEstimate, "forecast estimate")
        object.__setattr__(
            self, "metric_id", _canonical_id(self.metric_id, "metric_id")
        )
        quantity = _finite_nonnegative(self.quantity, "quantity")
        lower = _finite_nonnegative(self.lower, "lower")
        upper = _finite_nonnegative(self.upper, "upper")
        if not lower <= quantity <= upper:
            raise ValueError("forecast point must fall inside its interval")
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)


@dataclass(frozen=True, slots=True)
class SyntheticForecastMaterial:
    estimates: tuple[SyntheticForecastEstimate, ...]

    def __post_init__(self) -> None:
        _exact_type(self, SyntheticForecastMaterial, "forecast material")
        if (
            type(self.estimates) is not tuple
            or not self.estimates
            or len(self.estimates) > 128
            or any(
                type(item) is not SyntheticForecastEstimate for item in self.estimates
            )
        ):
            raise TypeError("forecast material requires a bounded exact estimate tuple")
        ids = tuple(item.metric_id for item in self.estimates)
        if len(ids) != len(set(ids)):
            raise ValueError("forecast metric ids must be unique")


def _forecast_ref(
    request: ForecastResourcesRequest,
    static_ref: object,
    line_items: tuple[ResourceLineItem, ...],
    wall_band: tuple[float, ...],
    limitations: tuple[str, ...],
    private_binding: tuple[str, ...],
) -> ResourceForecastRef:
    digest = hashlib.sha256(
        _FORECAST_DOMAIN
        + _canonical_tuple_payload(
            (
                request,
                static_ref,
                line_items,
                wall_band,
                limitations,
                private_binding,
            )
        )
    ).hexdigest()
    return ResourceForecastRef(request.challenge_key, content_digest="sha256:" + digest)


def _unresolved(
    request: ForecastResourcesRequest,
    static_ref: object,
    reason: ForecastUnresolvedReason,
    *,
    private_binding: tuple[str, ...] = (),
) -> ResourceForecast:
    limitations = (
        f"SUPPORT:{ForecastSupportState.UNRESOLVED.value}",
        f"REASON:{reason.value}",
        "NO_RESOURCE_PREDICTION",
        "ZERO_BAND_IS_UNRESOLVED_PLACEHOLDER",
        "NON_BINDING_NOT_QUOTE_OR_ADMISSION",
        "NOT_OBSERVED_RESOURCE_RECEIPT",
        "NOT_SCIENTIFIC_EVIDENCE",
    )
    line_items: tuple[ResourceLineItem, ...] = ()
    wall_band = (0.0, 0.0)
    return ResourceForecast(
        _forecast_ref(
            request,
            static_ref,
            line_items,
            wall_band,
            limitations,
            (reason.value, *private_binding),
        ),
        static_ref,
        line_items,
        wall_band,
        limitations,
    )


class UncalibratedResourceForecastProvider:
    """General provider: calibration is unavailable, so every result is unresolved."""

    __slots__ = ("_inspection",)

    def __init__(self, inspection_provider: StaticResourceInspectionProvider) -> None:
        _exact_type(
            inspection_provider, StaticResourceInspectionProvider, "inspection_provider"
        )
        self._inspection = inspection_provider

    def forecast_resources(self, request: ForecastResourcesRequest) -> ResourceForecast:
        if type(request) is not ForecastResourcesRequest:
            raise ResourceEstimationProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            )
        static = self._inspection._resolve_static(
            InspectResourcesRequest(
                request.challenge_key, request.strategy, request.resource_policy_ref
            )
        )
        return _unresolved(
            request,
            static.result.static_assessment_ref,
            ForecastUnresolvedReason.CALIBRATION_AUTHORITY_UNAVAILABLE,
        )


class _TestOnlyForecastCapability:
    __slots__ = ()


_TEST_ONLY_FORECAST_CAPABILITY = _TestOnlyForecastCapability()


class TestOnlyCalibratedResourceForecastProvider:
    """Nominal synthetic-only provider used to test calibration mechanics."""

    __slots__ = (
        "_active_distribution_ref",
        "_as_of_epoch",
        "_calibration",
        "_engine",
        "_inspection",
    )

    def __init__(
        self,
        inspection_provider: StaticResourceInspectionProvider,
        active_distribution_ref: InstanceDistributionContractRef,
        calibration: SyntheticForecastCalibration,
        engine: SyntheticForecastEngine,
        as_of_epoch: int,
        capability: _TestOnlyForecastCapability,
    ) -> None:
        if capability is not _TEST_ONLY_FORECAST_CAPABILITY:
            raise TypeError("test-only forecast capability is required")
        _exact_type(
            inspection_provider, StaticResourceInspectionProvider, "inspection_provider"
        )
        _exact_type(
            active_distribution_ref,
            InstanceDistributionContractRef,
            "active_distribution_ref",
        )
        _exact_type(calibration, SyntheticForecastCalibration, "calibration")
        if not callable(getattr(engine, "forecast", None)):
            raise TypeError("a synthetic forecast engine is required")
        epoch = _epoch(as_of_epoch, "as_of_epoch")
        if active_distribution_ref.challenge_key != inspection_provider.challenge_key:
            raise ValueError("active distribution crosses the provider Challenge")
        self._inspection = inspection_provider
        self._active_distribution_ref = active_distribution_ref
        self._calibration = calibration
        self._engine = engine
        self._as_of_epoch = epoch

    @classmethod
    def for_test_fixture(
        cls,
        *,
        inspection_provider: StaticResourceInspectionProvider,
        active_distribution_ref: InstanceDistributionContractRef,
        calibration: SyntheticForecastCalibration,
        engine: SyntheticForecastEngine,
        as_of_epoch: int,
    ) -> TestOnlyCalibratedResourceForecastProvider:
        return cls(
            inspection_provider,
            active_distribution_ref,
            calibration,
            engine,
            as_of_epoch,
            _TEST_ONLY_FORECAST_CAPABILITY,
        )

    def _preflight_reason(
        self, request: ForecastResourcesRequest, static: _StaticResolution
    ) -> ForecastUnresolvedReason | None:
        calibration = self._calibration
        scope = calibration.scope
        if calibration.status is ForecastCalibrationStatus.MISCALIBRATED:
            return ForecastUnresolvedReason.MISCALIBRATED
        if not (
            calibration.model.valid_from_epoch
            <= self._as_of_epoch
            <= calibration.model.valid_through_epoch
        ):
            return ForecastUnresolvedReason.STALE_MODEL
        if not (
            calibration.window.evidence_end_epoch
            <= self._as_of_epoch
            <= calibration.window.valid_through_epoch
        ):
            return ForecastUnresolvedReason.STALE_CALIBRATION
        if scope.instance_distribution_ref != self._active_distribution_ref:
            return ForecastUnresolvedReason.UNSUPPORTED_DISTRIBUTION
        if (
            scope.challenge_key != request.challenge_key
            or scope.resource_policy_ref != request.resource_policy_ref
            or scope.compiler_identity
            != static.resolved_strategy.resolved_plan.compiler_identity
        ):
            return ForecastUnresolvedReason.MODEL_SCOPE_MISMATCH
        resource_class = self._inspection.resource_class
        if (
            scope.resource_class_ref != self._inspection.resource_class_ref
            or scope.environment_pin != resource_class.execution_environment_pin
            or scope.environment_pin
            not in static.resolved_strategy.resolved_plan.environment_pins
        ):
            return ForecastUnresolvedReason.HARDWARE_SCOPE_MISMATCH
        if request.forecast_horizon_seconds > calibration.maximum_horizon_seconds:
            return ForecastUnresolvedReason.UNSUPPORTED_HORIZON
        if static.assessment.outcome is not StaticAssessmentOutcome.ADMISSIBLE:
            return ForecastUnresolvedReason.STATIC_ASSESSMENT_NOT_ADMISSIBLE
        return None

    def forecast_resources(self, request: ForecastResourcesRequest) -> ResourceForecast:
        if type(request) is not ForecastResourcesRequest:
            raise ResourceEstimationProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            )
        static = self._inspection._resolve_static(
            InspectResourcesRequest(
                request.challenge_key, request.strategy, request.resource_policy_ref
            )
        )
        private_binding = self._private_binding()
        reason = self._preflight_reason(request, static)
        if reason is not None:
            return _unresolved(
                request,
                static.result.static_assessment_ref,
                reason,
                private_binding=private_binding,
            )
        try:
            material = self._engine.forecast(request, static.result, self._calibration)
        except Exception:  # noqa: BLE001 - model diagnostics never cross the boundary.
            return _unresolved(
                request,
                static.result.static_assessment_ref,
                ForecastUnresolvedReason.MODEL_EVALUATION_FAILED,
                private_binding=private_binding,
            )
        try:
            return self._supported_forecast(request, static, material, private_binding)
        except Exception:  # noqa: BLE001 - malformed model material fails closed.
            return _unresolved(
                request,
                static.result.static_assessment_ref,
                ForecastUnresolvedReason.MODEL_OUTPUT_INVALID,
                private_binding=private_binding,
            )

    def _private_binding(self) -> tuple[str, ...]:
        calibration = self._calibration
        return (
            calibration.model.model_id,
            calibration.model.model_version,
            calibration.model.implementation_digest,
            calibration.model.provenance_digest,
            calibration.window.window_id,
            calibration.window.window_version,
            calibration.window.calibration_digest,
            calibration.scope.resource_policy_ref.content_digest,
            calibration.scope.resource_class_ref.content_digest,
            calibration.scope.environment_pin.content_digest,
            str(calibration.maximum_horizon_seconds),
            str(self._as_of_epoch),
        )

    def _supported_forecast(
        self,
        request: ForecastResourcesRequest,
        static: _StaticResolution,
        material: object,
        private_binding: tuple[str, ...],
    ) -> ResourceForecast:
        if type(material) is not SyntheticForecastMaterial:
            raise TypeError("synthetic engine returned a wrong material type")
        metrics = {
            item.metric_id: item
            for item in self._inspection.resource_class.observation_metrics
        }
        observed_ids = tuple(item.metric_id for item in material.estimates)
        if any(metric_id not in metrics for metric_id in observed_ids):
            raise ValueError("synthetic forecast contains an unregistered metric")
        latency = tuple(
            item
            for item in material.estimates
            if metrics[item.metric_id].observation_role
            is ResourceObservationRole.OBSERVED_LATENCY
        )
        if len(latency) != 1:
            raise ValueError(
                "synthetic forecast requires its registered latency metric"
            )
        line_items = tuple(
            ResourceLineItem(
                self._inspection.resource_class_ref,
                estimate.quantity,
                _unit_label(estimate.metric_id, metrics[estimate.metric_id].unit_ref),
                (estimate.lower, estimate.upper),
            )
            for estimate in material.estimates
        )
        wall_band = (latency[0].lower, latency[0].upper)
        calibration = self._calibration
        limitations = (
            f"SUPPORT:{ForecastSupportState.SUPPORTED.value}",
            "TEST_ONLY_SYNTHETIC_CALIBRATION",
            f"MODEL_ID:{calibration.model.model_id}",
            f"MODEL_VERSION:{calibration.model.model_version}",
            f"MODEL_IMPLEMENTATION:{calibration.model.implementation_digest}",
            f"MODEL_PROVENANCE:{calibration.model.provenance_digest}",
            f"CALIBRATION_WINDOW:{calibration.window.window_id}@{calibration.window.window_version}",
            f"CALIBRATION_DIGEST:{calibration.window.calibration_digest}",
            f"RESOURCE_CLASS:{calibration.scope.resource_class_ref.object_id}@{calibration.scope.resource_class_ref.object_version}",
            f"ENVIRONMENT:{calibration.scope.environment_pin.environment_id}@{calibration.scope.environment_pin.environment_version}",
            "NON_BINDING_NOT_QUOTE_OR_ADMISSION",
            "NOT_OBSERVED_RESOURCE_RECEIPT",
            "NOT_SCIENTIFIC_EVIDENCE",
            "NOT_PRODUCTION_CALIBRATION",
        )
        forecast_ref = _forecast_ref(
            request,
            static.result.static_assessment_ref,
            line_items,
            wall_band,
            limitations,
            private_binding,
        )
        return ResourceForecast(
            forecast_ref,
            static.result.static_assessment_ref,
            line_items,
            wall_band,
            limitations,
        )


__all__ = (
    "ForecastAuthorityMarker",
    "ForecastCalibrationStatus",
    "ForecastSupportState",
    "ForecastUnresolvedReason",
    "ResourceEstimationProviderError",
    "StaticResourceInspectionProvider",
    "SyntheticForecastCalibration",
    "SyntheticForecastCalibrationWindow",
    "SyntheticForecastEngine",
    "SyntheticForecastEstimate",
    "SyntheticForecastMaterial",
    "SyntheticForecastModelIdentity",
    "SyntheticForecastScope",
    "TestOnlyCalibratedResourceForecastProvider",
    "UncalibratedResourceForecastProvider",
)
