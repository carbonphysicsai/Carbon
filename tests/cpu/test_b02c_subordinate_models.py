"""Focused exact subordinate-model tests for B-02C resource policy."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from carbon.authoring.refs import ChallengeScope, GlobalScope, owner_ref
from carbon.registry import ChallengeKey
from carbon.resource_policy.errors import ResourcePolicyInputRejected
from carbon.resource_policy.model import (
    OPERATIONAL_REQUIREMENT_REQUIRED,
    RESOURCE_POLICY_ISSUE_MESSAGES,
    DeclaredResourceCeiling,
    EnforcementMode,
    EnforcementObservationKind,
    EnforcementPoint,
    FixtureOfficialShapedResourceContext,
    FixturePracticeResourceContext,
    FixtureResourceProvenance,
    ObservationUnavailableReason,
    ObservedMetricObserved,
    ObservedMetricUnavailable,
    ObservedResourceQuantity,
    OperationalReadinessRequirements,
    OperationalRequirementNotApplicable,
    OperationalRequirementRequired,
    ResourceEnforcementObservation,
    ResourceObservationMetric,
    ResourceObservationRole,
    ResourcePolicyAuthorityMarker,
    ResourcePolicyIssue,
    ResourcePolicyIssueCode,
    RuntimeResourceLimit,
    make_resource_policy_issue,
)

_KEY = ChallengeKey("fixture_resource_policy", "1.0")
_OTHER_KEY = ChallengeKey("other_resource_policy", "1.0")
_DIGEST = "sha256:" + "3" * 64


def _field_names(value_type: type) -> tuple[str, ...]:
    return tuple(field.name for field in fields(value_type))


def _owner(
    kind: str,
    object_id: str,
    *,
    key: ChallengeKey = _KEY,
    portable: bool = False,
) -> object:
    return owner_ref(
        kind,
        scope_binding=GlobalScope() if portable else ChallengeScope(key),
        object_id=object_id,
        object_version="1.0",
        content_digest=_DIGEST,
    )


def _practice_context() -> FixturePracticeResourceContext:
    return FixturePracticeResourceContext(
        _KEY,
        "fixture_practice",
        _owner("fixture_registration", "resource_fixture"),
        _owner("internal_service_scope", "resource_practice_scope"),
        ResourcePolicyAuthorityMarker.FIXTURE_PRACTICE_NOT_OFFICIAL,
    )


def test_subordinate_field_inventory_is_exact_and_closed() -> None:
    assert _field_names(FixtureResourceProvenance) == (
        "fixture_registration_ref",
        "source_provenance_refs",
        "authority_marker",
    )
    assert _field_names(FixturePracticeResourceContext) == (
        "challenge_key",
        "context_id",
        "fixture_registration_ref",
        "internal_service_scope_ref",
        "authority_marker",
    )
    assert _field_names(FixtureOfficialShapedResourceContext) == _field_names(
        FixturePracticeResourceContext
    )
    assert _field_names(DeclaredResourceCeiling) == (
        "dimension_id",
        "unit_ref",
        "maximum_quantity",
    )
    assert _field_names(ResourceObservationMetric) == (
        "metric_id",
        "unit_ref",
        "observation_role",
    )
    assert _field_names(ObservedResourceQuantity) == (
        "metric_id",
        "unit_ref",
        "quantity",
        "observation_role",
    )
    assert _field_names(OperationalReadinessRequirements) == (
        "validator_capacity",
        "reconstruction_funding",
        "queue_availability",
        "evidence_budget_availability",
    )
    assert _field_names(RuntimeResourceLimit) == (
        "limit_id",
        "metric_id",
        "unit_ref",
        "maximum_quantity",
        "enforcement_point",
        "enforcement_mode",
    )
    assert _field_names(ResourcePolicyIssue) == ("code", "message", "path")


def test_fixture_contexts_are_exact_scoped_and_nominally_non_official() -> None:
    practice = _practice_context()
    official_shaped = FixtureOfficialShapedResourceContext(
        _KEY,
        "fixture_official_shaped",
        _owner("fixture_registration", "resource_fixture"),
        _owner("internal_service_scope", "resource_official_shaped_scope"),
        ResourcePolicyAuthorityMarker.FIXTURE_OFFICIAL_SHAPED_NOT_OFFICIAL,
    )

    assert type(practice) is FixturePracticeResourceContext
    assert type(official_shaped) is FixtureOfficialShapedResourceContext
    assert type(practice) is not type(official_shaped)
    assert practice.authority_marker.value.endswith("NOT_OFFICIAL")
    assert official_shaped.authority_marker.value.endswith("NOT_OFFICIAL")

    with pytest.raises(ResourcePolicyInputRejected):
        FixturePracticeResourceContext(
            _KEY,
            "cross_challenge",
            _owner(
                "fixture_registration",
                "other_fixture",
                key=_OTHER_KEY,
            ),
            _owner("internal_service_scope", "resource_practice_scope"),
            ResourcePolicyAuthorityMarker.FIXTURE_PRACTICE_NOT_OFFICIAL,
        )
    with pytest.raises(ResourcePolicyInputRejected):
        FixturePracticeResourceContext(
            _KEY,
            "global_registration",
            _owner(
                "fixture_registration",
                "global_fixture",
                portable=True,
            ),
            _owner("internal_service_scope", "resource_practice_scope"),
            ResourcePolicyAuthorityMarker.FIXTURE_PRACTICE_NOT_OFFICIAL,
        )


def test_fixture_provenance_is_sorted_frozen_and_permanently_non_production() -> None:
    later = _owner("provenance", "z_source")
    earlier = _owner("provenance", "a_source")
    provenance = FixtureResourceProvenance(
        _owner("fixture_registration", "resource_fixture"),
        (later, earlier),
        ResourcePolicyAuthorityMarker.FIXTURE_PROVENANCE_NOT_PRODUCTION,
    )

    assert set(provenance.source_provenance_refs) == {earlier, later}
    assert provenance.authority_marker is (
        ResourcePolicyAuthorityMarker.FIXTURE_PROVENANCE_NOT_PRODUCTION
    )
    with pytest.raises(FrozenInstanceError):
        provenance.authority_marker = (  # type: ignore[misc]
            ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_POLICY_NOT_PRODUCTION
        )
    with pytest.raises(ResourcePolicyInputRejected):
        FixtureResourceProvenance(
            _owner("fixture_registration", "resource_fixture"),
            (earlier,),
            ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_POLICY_NOT_PRODUCTION,
        )


def test_unit_and_applicability_refs_are_exact_and_defensively_reconstructed() -> None:
    unit_ref = _owner("unit", "abstract_unit", portable=True)
    reason_ref = _owner("applicability_reason", "not_applicable")

    ceiling = DeclaredResourceCeiling("abstract_units", unit_ref, 4)
    metric = ResourceObservationMetric(
        "consumed_units",
        unit_ref,
        ResourceObservationRole.RESOURCE_CONSUMPTION,
    )
    quantity = ObservedResourceQuantity(
        "consumed_units",
        unit_ref,
        4,
        ResourceObservationRole.RESOURCE_CONSUMPTION,
    )
    not_applicable = OperationalRequirementNotApplicable(reason_ref)

    assert ceiling.unit_ref == metric.unit_ref == quantity.unit_ref == unit_ref
    assert ceiling.unit_ref is not unit_ref
    assert metric.unit_ref is not unit_ref
    assert quantity.unit_ref is not unit_ref
    assert not_applicable.reason_ref == reason_ref
    assert not_applicable.reason_ref is not reason_ref

    with pytest.raises(ResourcePolicyInputRejected):
        DeclaredResourceCeiling("abstract_units", object(), 4)
    with pytest.raises(ResourcePolicyInputRejected):
        ResourceObservationMetric(
            "consumed_units",
            _owner("provenance", "wrong_kind", portable=True),
            ResourceObservationRole.RESOURCE_CONSUMPTION,
        )
    with pytest.raises(ResourcePolicyInputRejected):
        ObservedResourceQuantity(
            "consumed_units",
            object(),
            4,
            ResourceObservationRole.RESOURCE_CONSUMPTION,
        )
    with pytest.raises(ResourcePolicyInputRejected):
        OperationalRequirementNotApplicable(object())


@pytest.mark.parametrize(
    "hostile",
    (True, -1, 1.0, float("inf"), float("nan"), 1 << 64),
)
def test_uint64_resource_quantities_reject_bool_float_nonfinite_and_overflow(
    hostile: object,
) -> None:
    unit_ref = _owner("unit", "abstract_unit", portable=True)
    with pytest.raises(ResourcePolicyInputRejected):
        DeclaredResourceCeiling("abstract_units", unit_ref, hostile)  # type: ignore[arg-type]
    with pytest.raises(ResourcePolicyInputRejected):
        ObservedResourceQuantity(
            "consumed_units",
            unit_ref,
            hostile,  # type: ignore[arg-type]
            ResourceObservationRole.RESOURCE_CONSUMPTION,
        )
    with pytest.raises(ResourcePolicyInputRejected):
        RuntimeResourceLimit(
            "runtime_limit",
            "consumed_units",
            unit_ref,
            hostile,  # type: ignore[arg-type]
            EnforcementPoint.RUNTIME_OBSERVATION,
            EnforcementMode.STOP_ON_FIRST_OBSERVED_EXCESS,
        )


@pytest.mark.parametrize(
    ("point", "mode", "kind"),
    (
        (
            EnforcementPoint.PRE_ALLOCATION_READINESS,
            EnforcementMode.PREVENT_START_ON_EXCESS,
            EnforcementObservationKind.ATTEMPTED_NEXT_TOTAL,
        ),
        (
            EnforcementPoint.PRE_EXECUTION,
            EnforcementMode.PREVENT_NEXT_UNIT_ON_EXCESS,
            EnforcementObservationKind.ATTEMPTED_NEXT_TOTAL,
        ),
        (
            EnforcementPoint.RUNTIME_OBSERVATION,
            EnforcementMode.STOP_ON_FIRST_OBSERVED_EXCESS,
            EnforcementObservationKind.CURRENT_TOTAL,
        ),
    ),
)
def test_enforcement_point_mode_and_observation_kinds_remain_exact(
    point: EnforcementPoint,
    mode: EnforcementMode,
    kind: EnforcementObservationKind,
) -> None:
    unit_ref = _owner("unit", "abstract_unit", portable=True)
    limit = RuntimeResourceLimit(
        f"{point.value.lower()}_limit",
        "consumed_units",
        unit_ref,
        10,
        point,
        mode,
    )
    observation = ResourceEnforcementObservation(
        ObservedResourceQuantity(
            "consumed_units",
            unit_ref,
            10,
            ResourceObservationRole.RESOURCE_CONSUMPTION,
        ),
        kind,
    )
    assert limit.maximum_quantity == observation.metric_quantity.quantity
    assert limit.enforcement_point is point
    assert observation.observation_kind is kind


def test_enforcement_point_mode_mismatch_and_string_aliases_reject() -> None:
    unit_ref = _owner("unit", "abstract_unit", portable=True)
    with pytest.raises(ResourcePolicyInputRejected):
        RuntimeResourceLimit(
            "bad_limit",
            "consumed_units",
            unit_ref,
            10,
            EnforcementPoint.PRE_ALLOCATION_READINESS,
            EnforcementMode.STOP_ON_FIRST_OBSERVED_EXCESS,
        )
    with pytest.raises(ResourcePolicyInputRejected):
        ResourceEnforcementObservation(
            ObservedResourceQuantity(
                "consumed_units",
                unit_ref,
                10,
                ResourceObservationRole.RESOURCE_CONSUMPTION,
            ),
            "CURRENT_TOTAL",  # type: ignore[arg-type]
        )


def test_metric_roles_and_observed_unavailable_bindings_are_nominal() -> None:
    unit_ref = _owner("unit", "abstract_unit", portable=True)
    metric = ResourceObservationMetric(
        "consumed_units",
        unit_ref,
        ResourceObservationRole.RESOURCE_CONSUMPTION,
    )
    quantity = ObservedResourceQuantity(
        metric.metric_id,
        metric.unit_ref,
        4,
        metric.observation_role,
    )
    observed = ObservedMetricObserved(quantity)
    unavailable = ObservedMetricUnavailable(
        ObservationUnavailableReason.OBSERVATION_FAILED
    )

    assert type(observed) is ObservedMetricObserved
    assert type(unavailable) is ObservedMetricUnavailable
    assert observed.observed_quantity == quantity
    assert not hasattr(unavailable, "observed_quantity")


def test_readiness_dispositions_require_exact_nominal_variants() -> None:
    reason = _owner("applicability_reason", "funding_not_applicable")
    requirements = OperationalReadinessRequirements(
        OPERATIONAL_REQUIREMENT_REQUIRED,
        OperationalRequirementNotApplicable(reason),
        OperationalRequirementRequired(),
        OperationalRequirementRequired(),
    )

    assert type(requirements.validator_capacity) is OperationalRequirementRequired
    assert type(requirements.reconstruction_funding) is (
        OperationalRequirementNotApplicable
    )
    with pytest.raises(ResourcePolicyInputRejected):
        OperationalReadinessRequirements(
            True,  # type: ignore[arg-type]
            OperationalRequirementNotApplicable(reason),
            OperationalRequirementRequired(),
            OperationalRequirementRequired(),
        )


def test_resource_policy_issues_are_fixed_bounded_and_non_echoing() -> None:
    issue = make_resource_policy_issue(
        ResourcePolicyIssueCode.STATIC_REQUIREMENT_OVER_LIMIT,
        "/static_resource_requirements/0/quantity",
    )
    assert issue.message == RESOURCE_POLICY_ISSUE_MESSAGES[issue.code]
    assert issue.path == "/static_resource_requirements/0/quantity"

    hostile = "attacker-secret-value-82d7"
    with pytest.raises(ResourcePolicyInputRejected) as wrong_message:
        ResourcePolicyIssue(
            ResourcePolicyIssueCode.STATIC_REQUIREMENT_OVER_LIMIT,
            hostile,
            "/static_resource_requirements/0/quantity",
        )
    assert hostile not in str(wrong_message.value)
    with pytest.raises(ResourcePolicyInputRejected):
        make_resource_policy_issue(
            ResourcePolicyIssueCode.STATIC_REQUIREMENT_OVER_LIMIT,
            "/filesystem/private/path",
        )
    for unsafe_index_path in (
        "/static_resource_requirements/65536/quantity",
        "/static_resource_requirements/999999999999999999999999/quantity",
        "/static_resource_requirements/\u0660/quantity",
    ):
        with pytest.raises(ResourcePolicyInputRejected):
            make_resource_policy_issue(
                ResourcePolicyIssueCode.STATIC_REQUIREMENT_OVER_LIMIT,
                unsafe_index_path,
            )
