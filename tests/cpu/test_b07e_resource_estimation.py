from __future__ import annotations

import inspect
from dataclasses import replace

import pytest
from b02c_fixtures import ResourcePolicyFixture, make_resource_policy_fixture
from b07b_fixtures import Compiler

from carbon import research
from carbon.authoring.primitives import CANONICALIZATION_PROFILE
from carbon.authoring.refs import InstanceDistributionContractRef
from carbon.construction.model import CompilerIdentity, EnvironmentPin
from carbon.resource_policy import ObservedResourceReceiptRef


def _digest(character: str = "9") -> str:
    return "sha256:" + character * 64


def _distribution(
    fixture: ResourcePolicyFixture, character: str = "7"
) -> InstanceDistributionContractRef:
    return InstanceDistributionContractRef(
        challenge_key=fixture.policy.challenge_key,
        object_id="fixture_forecast_distribution",
        object_version="1.0",
        schema_version="1.0",
        canonicalization_profile=CANONICALIZATION_PROFILE,
        content_digest=_digest(character),
        expected_population_role="TARGET_WORKLOAD_P",
    )


def _inspection(
    fixture: ResourcePolicyFixture,
) -> research.StaticResourceInspectionProvider:
    return research.StaticResourceInspectionProvider(
        compilation_resolver=Compiler(fixture),
        expected_training_support_ref=fixture.plan.training_support_ref,
        policy=fixture.policy,
        policy_ref=fixture.policy_ref,
        class_bundle=fixture.class_bundle,
        selected_resource_class=fixture.resource_class,
        selected_resource_class_ref=fixture.resource_class_ref,
        authority_context=fixture.context,
    )


def _inspect_request(
    fixture: ResourcePolicyFixture,
) -> research.InspectResourcesRequest:
    return research.InspectResourcesRequest(
        fixture.policy.challenge_key,
        fixture.compile_fixture.strategy,
        fixture.policy_ref,
    )


def _forecast_request(
    fixture: ResourcePolicyFixture, horizon: int = 20
) -> research.ForecastResourcesRequest:
    return research.ForecastResourcesRequest(
        fixture.policy.challenge_key,
        fixture.compile_fixture.strategy,
        fixture.policy_ref,
        horizon,
    )


def _calibration(
    fixture: ResourcePolicyFixture,
    distribution: InstanceDistributionContractRef,
) -> research.SyntheticForecastCalibration:
    return research.SyntheticForecastCalibration(
        research.SyntheticForecastModelIdentity(
            "fixture_forecast_model",
            "1.0",
            _digest("a"),
            _digest("b"),
            1,
            100,
        ),
        research.SyntheticForecastCalibrationWindow(
            "fixture_calibration_window",
            "1.0",
            _digest("c"),
            1,
            10,
            100,
        ),
        research.SyntheticForecastScope(
            fixture.policy.challenge_key,
            distribution,
            fixture.policy_ref,
            fixture.resource_class_ref,
            fixture.plan.compiler_identity,
            fixture.resource_class.execution_environment_pin,
        ),
        60,
        research.ForecastCalibrationStatus.VALID,
        research.ForecastAuthorityMarker.TEST_ONLY_SYNTHETIC_CALIBRATION_NOT_PRODUCTION,
    )


class _Engine:
    def __init__(self, material: object | None = None, *, fails: bool = False):
        self.calls = 0
        self.material = material
        self.fails = fails

    def forecast(self, request, static_result, calibration):
        self.calls += 1
        if self.fails:
            raise RuntimeError("private model failure must not escape")
        if self.material is not None:
            return self.material
        return research.SyntheticForecastMaterial(
            (
                research.SyntheticForecastEstimate("consumed_units", 7.0, 6.0, 8.0),
                research.SyntheticForecastEstimate("latency_units", 2.0, 1.0, 3.0),
                research.SyntheticForecastEstimate(
                    "cost_units_not_price", 9.0, 8.0, 10.0
                ),
            )
        )


def _fixture_forecaster(
    fixture: ResourcePolicyFixture,
    calibration: research.SyntheticForecastCalibration,
    engine: object,
    *,
    active_distribution: InstanceDistributionContractRef | None = None,
    as_of_epoch: int = 50,
) -> research.TestOnlyCalibratedResourceForecastProvider:
    return research.TestOnlyCalibratedResourceForecastProvider.for_test_fixture(
        inspection_provider=_inspection(fixture),
        active_distribution_ref=active_distribution
        or calibration.scope.instance_distribution_ref,
        calibration=calibration,
        engine=engine,
        as_of_epoch=as_of_epoch,
    )


def _reason(result: research.ResourceForecast) -> str:
    return next(item for item in result.limitations if item.startswith("REASON:"))


def test_static_inspection_is_exact_deterministic_and_policy_owned(tmp_path):
    fixture = make_resource_policy_fixture(tmp_path)
    provider = _inspection(fixture)
    request = _inspect_request(fixture)

    first = provider.inspect_resources(request)
    second = provider.inspect_resources(request)

    assert research.canonical_bytes(first) == research.canonical_bytes(second)
    assert first.static_assessment_ref.challenge_key == fixture.policy.challenge_key
    assert len(first.line_items) == len(fixture.plan.static_resource_requirements)
    for item, requirement in zip(
        first.line_items, fixture.plan.static_resource_requirements, strict=True
    ):
        assert item.resource_class_ref == fixture.resource_class_ref
        assert item.quantity == float(requirement.quantity)
        assert item.confidence_band == (item.quantity, item.quantity)
        assert (
            item.unit == f"{requirement.dimension_id}:{requirement.unit_ref.object_id}"
        )
    assert "STATIC_EXACT_PLAN_DERIVED" in first.limitations
    assert "ASSESSMENT:ADMISSIBLE" in first.limitations
    assert "DECLARED_CEILING:abstract_units:13" in first.limitations
    assert "NOT_FORECAST" in first.limitations


def test_static_policy_outcome_is_not_replaced_by_forecast(tmp_path):
    fixture = make_resource_policy_fixture(tmp_path, static_ceiling=1)
    static = _inspection(fixture).inspect_resources(_inspect_request(fixture))
    forecast = research.UncalibratedResourceForecastProvider(
        _inspection(fixture)
    ).forecast_resources(_forecast_request(fixture))

    assert "ASSESSMENT:OVER_LIMIT" in static.limitations
    assert _reason(forecast) == "REASON:CALIBRATION_AUTHORITY_UNAVAILABLE"
    assert forecast.line_items == ()
    assert forecast.static_assessment_ref == static.static_assessment_ref


def test_static_inspection_rejects_stale_or_cross_bound_policy_refs(tmp_path):
    fixture = make_resource_policy_fixture(tmp_path)
    provider = _inspection(fixture)
    stale = replace(fixture.policy_ref, content_digest=_digest("f"))
    request = research.InspectResourcesRequest(
        fixture.policy.challenge_key,
        fixture.compile_fixture.strategy,
        stale,
    )
    with pytest.raises(research.ResourceEstimationProviderError) as failure:
        provider.inspect_resources(request)
    assert failure.value.code is research.ResearchServiceErrorCode.REFERENCE_MISMATCH

    other_key = research.ChallengeKey("other_fixture", "1.0")
    other = replace(stale, challenge_key=other_key)
    cross = research.InspectResourcesRequest(
        other_key,
        fixture.compile_fixture.strategy,
        other,
    )
    with pytest.raises(research.ResourceEstimationProviderError) as failure:
        provider.inspect_resources(cross)
    assert failure.value.code is research.ResearchServiceErrorCode.REFERENCE_MISMATCH


def test_general_forecast_has_no_calibration_input_and_is_unresolved(tmp_path):
    fixture = make_resource_policy_fixture(tmp_path)
    provider = research.UncalibratedResourceForecastProvider(_inspection(fixture))

    result = provider.forecast_resources(_forecast_request(fixture))

    assert result.line_items == ()
    assert result.total_wall_seconds_band == (0.0, 0.0)
    assert result.limitations[:2] == (
        "SUPPORT:UNRESOLVED",
        "REASON:CALIBRATION_AUTHORITY_UNAVAILABLE",
    )
    assert "ZERO_BAND_IS_UNRESOLVED_PLACEHOLDER" in result.limitations
    assert set(inspect.signature(type(provider)).parameters) == {"inspection_provider"}


def test_fixture_calibration_is_nominal_and_supported_output_is_provenanced(tmp_path):
    fixture = make_resource_policy_fixture(tmp_path)
    distribution = _distribution(fixture)
    calibration = _calibration(fixture, distribution)
    engine = _Engine()
    provider = _fixture_forecaster(fixture, calibration, engine)
    request = _forecast_request(fixture)

    first = provider.forecast_resources(request)
    second = provider.forecast_resources(request)

    assert engine.calls == 2
    assert research.canonical_bytes(first) == research.canonical_bytes(second)
    assert first.total_wall_seconds_band == (1.0, 3.0)
    assert len(first.line_items) == 3
    assert first.limitations[:2] == (
        "SUPPORT:SUPPORTED",
        "TEST_ONLY_SYNTHETIC_CALIBRATION",
    )
    assert "MODEL_ID:fixture_forecast_model" in first.limitations
    assert "CALIBRATION_WINDOW:fixture_calibration_window@1.0" in first.limitations
    assert "RESOURCE_CLASS:fixture_resource_class@1.0" in first.limitations
    assert "NOT_PRODUCTION_CALIBRATION" in first.limitations

    with pytest.raises(TypeError):
        research.TestOnlyCalibratedResourceForecastProvider(
            _inspection(fixture), distribution, calibration, engine, 50, object()
        )
    assert not issubclass(
        research.TestOnlyCalibratedResourceForecastProvider,
        research.UncalibratedResourceForecastProvider,
    )


@pytest.mark.parametrize(
    ("mutate", "expected"),
    (
        (
            lambda fixture, distribution, calibration: replace(
                calibration,
                status=research.ForecastCalibrationStatus.MISCALIBRATED,
            ),
            research.ForecastUnresolvedReason.MISCALIBRATED,
        ),
        (
            lambda fixture, distribution, calibration: replace(
                calibration,
                model=replace(calibration.model, valid_through_epoch=40),
            ),
            research.ForecastUnresolvedReason.STALE_MODEL,
        ),
        (
            lambda fixture, distribution, calibration: replace(
                calibration,
                window=replace(calibration.window, valid_through_epoch=40),
            ),
            research.ForecastUnresolvedReason.STALE_CALIBRATION,
        ),
        (
            lambda fixture, distribution, calibration: replace(
                calibration,
                scope=replace(
                    calibration.scope,
                    compiler_identity=CompilerIdentity(
                        "other_compiler",
                        "1.0",
                        _digest("d"),
                        "1.0",
                        "carbon_construction_canonical_v1",
                    ),
                ),
            ),
            research.ForecastUnresolvedReason.MODEL_SCOPE_MISMATCH,
        ),
        (
            lambda fixture, distribution, calibration: replace(
                calibration,
                scope=replace(
                    calibration.scope,
                    environment_pin=EnvironmentPin(
                        "other_environment", "1.0", _digest("e")
                    ),
                ),
            ),
            research.ForecastUnresolvedReason.HARDWARE_SCOPE_MISMATCH,
        ),
    ),
)
def test_fixture_forecast_fail_closed_matrix(tmp_path, mutate, expected):
    fixture = make_resource_policy_fixture(tmp_path)
    distribution = _distribution(fixture)
    calibration = mutate(fixture, distribution, _calibration(fixture, distribution))
    engine = _Engine()

    result = _fixture_forecaster(fixture, calibration, engine).forecast_resources(
        _forecast_request(fixture)
    )

    assert result.line_items == ()
    assert _reason(result) == f"REASON:{expected.value}"
    assert engine.calls == 0


def test_unsupported_distribution_and_horizon_are_unresolved(tmp_path):
    fixture = make_resource_policy_fixture(tmp_path)
    distribution = _distribution(fixture)
    calibration = _calibration(fixture, distribution)
    engine = _Engine()

    unsupported = _fixture_forecaster(
        fixture,
        calibration,
        engine,
        active_distribution=replace(distribution, content_digest=_digest("8")),
    ).forecast_resources(_forecast_request(fixture))
    assert _reason(unsupported) == "REASON:UNSUPPORTED_DISTRIBUTION"

    long_horizon = _fixture_forecaster(fixture, calibration, engine).forecast_resources(
        _forecast_request(fixture, horizon=61)
    )
    assert _reason(long_horizon) == "REASON:UNSUPPORTED_HORIZON"
    assert engine.calls == 0


def test_model_failure_and_malformed_or_nonfinite_material_are_unresolved(tmp_path):
    fixture = make_resource_policy_fixture(tmp_path)
    distribution = _distribution(fixture)
    calibration = _calibration(fixture, distribution)

    failed = _fixture_forecaster(
        fixture, calibration, _Engine(fails=True)
    ).forecast_resources(_forecast_request(fixture))
    assert _reason(failed) == "REASON:MODEL_EVALUATION_FAILED"

    malformed = _fixture_forecaster(
        fixture, calibration, _Engine(material=object())
    ).forecast_resources(_forecast_request(fixture))
    assert _reason(malformed) == "REASON:MODEL_OUTPUT_INVALID"

    with pytest.raises(ValueError):
        research.SyntheticForecastEstimate("latency_units", float("nan"), 0.0, 1.0)
    with pytest.raises(ValueError):
        research.SyntheticForecastEstimate("latency_units", 2.0, 3.0, 4.0)


def test_resource_layers_do_not_convert_to_quote_receipt_or_official_outcome(tmp_path):
    fixture = make_resource_policy_fixture(tmp_path)
    inspection = _inspection(fixture)
    static = inspection.inspect_resources(_inspect_request(fixture))
    forecast_provider = research.UncalibratedResourceForecastProvider(inspection)
    forecast = forecast_provider.forecast_resources(_forecast_request(fixture))

    assert type(static.static_assessment_ref) is research.StaticResourceAssessmentRef
    assert type(forecast.resource_forecast_ref) is research.ResourceForecastRef
    assert not isinstance(forecast.resource_forecast_ref, ObservedResourceReceiptRef)
    assert not hasattr(inspection, "quote_execution")
    assert not hasattr(forecast_provider, "quote_execution")
    assert not hasattr(forecast, "observed_resource_receipt_ref")
    assert not hasattr(forecast, "price")
    assert not hasattr(forecast, "score")


def test_resource_outputs_are_positive_allow_lists_without_protected_material(tmp_path):
    fixture = make_resource_policy_fixture(tmp_path)
    inspection = _inspection(fixture)
    outputs = (
        inspection.inspect_resources(_inspect_request(fixture)),
        research.UncalibratedResourceForecastProvider(inspection).forecast_resources(
            _forecast_request(fixture)
        ),
    )
    forbidden = (
        "official_seed",
        "protected_case",
        "stress_composition",
        "strong_anchor",
        "evaluator_topology",
        "official_score",
        "winner_probability",
        "truth_asset",
        "scorer_configuration",
    )
    for output in outputs:
        payload = research.canonical_bytes(output).lower()
        assert not any(term.encode() in payload for term in forbidden)
