"""Public API, epistemic ownership, and non-production boundary tests for B-02C."""

from __future__ import annotations

from inspect import Parameter, signature

from carbon import resource_policy
from carbon.resource_policy import canonical as resource_policy_canonical

_REQUIRED_PUBLIC_OPERATIONS = {
    "assess_static_resources",
    "decide_fixture_readiness",
    "decode_fixture_resource_availability",
    "decode_fixture_resource_decision",
    "decode_observed_resource_receipt",
    "decode_research_resource_policy",
    "decode_resource_cancellation_record",
    "decode_resource_class",
    "decode_resource_enforcement_event",
    "decode_resource_enforcement_result",
    "decode_static_resource_assessment",
    "encode_fixture_resource_availability",
    "encode_fixture_resource_decision",
    "encode_observed_resource_receipt",
    "encode_research_resource_policy",
    "encode_resource_cancellation_record",
    "encode_resource_class",
    "encode_resource_enforcement_event",
    "encode_resource_enforcement_result",
    "encode_static_resource_assessment",
    "evaluate_enforcement",
    "fixture_resource_decision_to_ref",
    "make_cancellation_record",
    "make_observed_resource_receipt",
    "research_resource_policy_to_ref",
    "resource_cancellation_record_to_ref",
    "resource_class_to_ref",
    "static_resource_assessment_to_ref",
    "validate_observed_resource_receipt",
    "validate_research_resource_policy_bundle",
}

_FUTURE_OWNER_NAMES = {
    "BindingExecutionAdmission",
    "BindingExecutionQuote",
    "CalibratedResourceForecast",
    "ProductionResourceClass",
    "ProductionResourceContext",
    "ReconstructionEvidencePolicy",
    "ResourcePrice",
    "ResourceQuota",
}


def test_root_public_surface_is_explicit_sorted_and_has_no_generic_ref_issuer() -> None:
    assert type(resource_policy.__all__) is list
    assert resource_policy.__all__ == sorted(resource_policy.__all__)
    assert len(resource_policy.__all__) == len(set(resource_policy.__all__))
    assert _REQUIRED_PUBLIC_OPERATIONS <= set(resource_policy.__all__)
    assert "make_resource_policy_ref" not in resource_policy.__all__
    assert not hasattr(resource_policy, "make_resource_policy_ref")
    for unguarded_receipt_operation in (
        "observed_resource_receipt_to_ref",
        "verify_observed_resource_receipt_ref",
    ):
        assert unguarded_receipt_operation not in resource_policy.__all__
        assert not hasattr(resource_policy, unguarded_receipt_operation)
        assert unguarded_receipt_operation not in resource_policy_canonical.__all__
        assert not hasattr(resource_policy_canonical, unguarded_receipt_operation)


def test_future_forecast_quote_science_and_production_owners_are_not_exported() -> None:
    assert _FUTURE_OWNER_NAMES.isdisjoint(resource_policy.__all__)
    assert all(not hasattr(resource_policy, name) for name in _FUTURE_OWNER_NAMES)
    assert tuple(resource_policy.ResourceEpistemicLayer) == (
        resource_policy.ResourceEpistemicLayer.STATIC_CONSTRUCTION_REQUIREMENT,
        resource_policy.ResourceEpistemicLayer.OBSERVED_RESOURCE_RECEIPT,
    )


def test_pure_service_builders_use_closed_explicit_keyword_inputs() -> None:
    expected = {
        "assess_static_resources": (
            "plan",
            "plan_ref",
            "policy",
            "policy_ref",
            "class_bundle",
            "selected_class",
            "selected_class_ref",
            "expected_active_policy_ref",
            "expected_active_resource_class_ref",
            "authority_context",
        ),
        "decide_fixture_readiness": (
            "plan",
            "plan_ref",
            "assessment",
            "assessment_ref",
            "policy",
            "policy_ref",
            "class_bundle",
            "selected_class",
            "selected_class_ref",
            "availability_input",
        ),
        "evaluate_enforcement": (
            "plan",
            "plan_ref",
            "policy",
            "policy_ref",
            "class_bundle",
            "selected_class",
            "selected_class_ref",
            "assessment",
            "assessment_ref",
            "decision",
            "decision_ref",
            "limit_id",
            "observation",
        ),
        "make_cancellation_record": (
            "plan",
            "plan_ref",
            "policy",
            "policy_ref",
            "class_bundle",
            "selected_class",
            "selected_class_ref",
            "assessment",
            "assessment_ref",
            "decision",
            "decision_ref",
            "actor",
            "reason",
            "stop_point",
            "work_started",
            "observed_resource_quantities_so_far",
            "enforcement_result",
        ),
        "make_observed_resource_receipt": (
            "plan",
            "plan_ref",
            "policy",
            "policy_ref",
            "class_bundle",
            "selected_class",
            "selected_class_ref",
            "assessment",
            "assessment_ref",
            "decision",
            "decision_ref",
            "build_completion",
            "frozen_artifact_reuse",
            "reconstruction_replicate",
            "observed_consumption_quantities",
            "observed_latency",
            "observed_cost",
            "evidence_stage_label",
            "stop_cause",
            "work_started",
            "stop_record",
            "stop_record_ref",
            "enforcement_result",
        ),
    }

    for operation_name, parameter_names in expected.items():
        parameters = tuple(
            signature(getattr(resource_policy, operation_name)).parameters.values()
        )
        assert tuple(parameter.name for parameter in parameters) == parameter_names
        assert all(parameter.kind is Parameter.KEYWORD_ONLY for parameter in parameters)


def test_policy_bundle_validation_has_one_positional_value_and_keyword_bundle() -> None:
    parameters = tuple(
        signature(
            resource_policy.validate_research_resource_policy_bundle
        ).parameters.values()
    )

    assert tuple(parameter.name for parameter in parameters) == (
        "policy",
        "class_bundle",
    )
    assert parameters[0].kind is Parameter.POSITIONAL_OR_KEYWORD
    assert parameters[1].kind is Parameter.KEYWORD_ONLY


def test_terminal_receipt_validator_requires_pair_and_full_dependency_set() -> None:
    parameters = tuple(
        signature(
            resource_policy.validate_observed_resource_receipt
        ).parameters.values()
    )

    assert tuple(parameter.name for parameter in parameters) == (
        "receipt",
        "receipt_ref",
        "plan",
        "plan_ref",
        "policy",
        "policy_ref",
        "class_bundle",
        "selected_class",
        "selected_class_ref",
        "assessment",
        "assessment_ref",
        "decision",
        "decision_ref",
        "stop_record",
        "stop_record_ref",
        "enforcement_result",
    )
    assert all(
        parameter.kind is Parameter.POSITIONAL_OR_KEYWORD
        for parameter in parameters[:2]
    )
    assert all(parameter.kind is Parameter.KEYWORD_ONLY for parameter in parameters[2:])


def test_package_contains_no_default_policy_class_or_production_authority_value() -> (
    None
):
    concrete_types = {
        resource_policy.ResourceClass,
        resource_policy.ResearchResourcePolicy,
    }
    assert not any(
        type(value) in concrete_types for value in vars(resource_policy).values()
    )
    assert all(
        "PRODUCTION" not in marker.value or "NOT_PRODUCTION" in marker.value
        for marker in resource_policy.ResourcePolicyAuthorityMarker
    )
