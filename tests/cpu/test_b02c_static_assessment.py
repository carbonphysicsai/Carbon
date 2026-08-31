"""Pure B-02C policy-bundle and immutable static-assessment conformance tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from b02c_fixtures import ResourcePolicyFixture, make_resource_policy_fixture

from carbon.authoring.refs import ChallengeScope, GlobalScope, owner_ref
from carbon.construction.model import EnvironmentPin, StaticResourceDimension
from carbon.construction.plan import resolved_construction_plan_canonical_bytes
from carbon.registry import ChallengeKey
from carbon.resource_policy.canonical import (
    research_resource_policy_to_ref,
    resource_class_to_ref,
)
from carbon.resource_policy.errors import (
    ResourcePolicyInputRejected,
    ResourcePolicyReferenceMismatchError,
)
from carbon.resource_policy.model import (
    DeclaredResourceCeiling,
    FixturePracticeResourceContext,
    FixtureResourceProvenance,
    ResourceClass,
    ResourcePolicyAuthorityMarker,
    ResourcePolicyIssueCode,
    StaticAssessmentOutcome,
)
from carbon.resource_policy.service import (
    assess_static_resources,
    validate_research_resource_policy_bundle,
)

_DIGEST = "sha256:" + "7" * 64


def _call(fixture: ResourcePolicyFixture, **overrides: object) -> object:
    values: dict[str, object] = {
        "plan": fixture.plan,
        "plan_ref": fixture.plan_ref,
        "policy": fixture.policy,
        "policy_ref": fixture.policy_ref,
        "class_bundle": fixture.class_bundle,
        "selected_class": fixture.resource_class,
        "selected_class_ref": fixture.resource_class_ref,
        "expected_active_policy_ref": fixture.policy_ref,
        "expected_active_resource_class_ref": fixture.resource_class_ref,
        "authority_context": fixture.context,
    }
    values.update(overrides)
    return assess_static_resources(**values)


def _pinned(key: ChallengeKey, kind: str, object_id: str) -> object:
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(key),
        object_id=object_id,
        object_version="1.0",
        content_digest=_DIGEST,
    )


def _portable(kind: str, object_id: str) -> object:
    return owner_ref(
        kind,
        scope_binding=GlobalScope(),
        object_id=object_id,
        object_version="1.0",
        content_digest=_DIGEST,
    )


def _policy_for_class(
    fixture: ResourcePolicyFixture,
    resource_class: ResourceClass,
    *,
    ceilings: tuple[DeclaredResourceCeiling, ...] | None = None,
) -> tuple[object, object, tuple[tuple[ResourceClass, object], ...]]:
    class_ref = resource_class_to_ref(resource_class)
    old_binding = fixture.policy.class_bindings[0]
    if ceilings is None:
        dimensions = resource_class.supported_dimensions
        ceilings = tuple(
            DeclaredResourceCeiling(
                dimension.dimension_id,
                dimension.unit_ref,
                13,
            )
            for dimension in dimensions
        )
    binding = replace(
        old_binding,
        resource_class_ref=class_ref,
        ceilings=ceilings,
    )
    policy = replace(fixture.policy, class_bindings=(binding,))
    class_bundle = ((resource_class, class_ref),)
    policy_ref = research_resource_policy_to_ref(
        policy,
        class_bundle=class_bundle,
    )
    return policy, policy_ref, class_bundle


def test_complete_policy_bundle_and_exact_at_limit_are_admissible(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path, static_ceiling=13)
    before = resolved_construction_plan_canonical_bytes(fixture.plan)
    before_ref = fixture.plan_ref

    verified_bundle = validate_research_resource_policy_bundle(
        fixture.policy,
        class_bundle=fixture.class_bundle,
    )
    assessment = _call(fixture)

    assert verified_bundle == fixture.class_bundle
    assert assessment.outcome is StaticAssessmentOutcome.ADMISSIBLE
    assert assessment.issues == ()
    assert assessment.static_resource_requirements == (
        fixture.plan.static_resource_requirements
    )
    assert assessment.resource_impact_tags == fixture.plan.resource_impact_tags
    assert resolved_construction_plan_canonical_bytes(fixture.plan) == before
    assert fixture.plan_ref == before_ref


def test_over_limit_does_not_clamp_convert_or_mutate_the_plan(tmp_path: Path) -> None:
    fixture = make_resource_policy_fixture(tmp_path, static_ceiling=12)
    before = resolved_construction_plan_canonical_bytes(fixture.plan)

    assessment = _call(fixture)

    assert assessment.outcome is StaticAssessmentOutcome.OVER_LIMIT
    assert tuple(issue.code for issue in assessment.issues) == (
        ResourcePolicyIssueCode.STATIC_REQUIREMENT_OVER_LIMIT,
    )
    assert assessment.static_resource_requirements[0].quantity == 13
    assert fixture.plan.static_resource_requirements[0].quantity == 13
    assert resolved_construction_plan_canonical_bytes(fixture.plan) == before


def test_stale_valid_policy_and_class_refs_are_semantic_not_digest_failures(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    stale_policy = replace(fixture.policy_ref, content_digest=_DIGEST)
    stale_class = replace(fixture.resource_class_ref, content_digest=_DIGEST)

    policy_result = _call(
        fixture,
        expected_active_policy_ref=stale_policy,
        expected_active_resource_class_ref=stale_class,
    )
    class_result = _call(
        fixture,
        expected_active_resource_class_ref=stale_class,
    )

    assert policy_result.outcome is StaticAssessmentOutcome.STALE_POLICY
    assert tuple(issue.code for issue in policy_result.issues) == (
        ResourcePolicyIssueCode.STALE_POLICY_REF,
    )
    assert class_result.outcome is StaticAssessmentOutcome.STALE_REFERENCE
    assert tuple(issue.code for issue in class_result.issues) == (
        ResourcePolicyIssueCode.STALE_RESOURCE_CLASS_REF,
    )


def test_actual_object_ref_digest_tamper_hard_rejects_without_assessment(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)

    with pytest.raises(ResourcePolicyReferenceMismatchError):
        _call(
            fixture,
            policy_ref=replace(fixture.policy_ref, content_digest=_DIGEST),
        )
    with pytest.raises(ResourcePolicyReferenceMismatchError):
        _call(
            fixture,
            selected_class_ref=replace(
                fixture.resource_class_ref,
                content_digest=_DIGEST,
            ),
        )


def test_cross_challenge_selected_class_is_a_closed_semantic_outcome(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    other_key = ChallengeKey("other_resource_policy", "1.0")
    other_provenance = FixtureResourceProvenance(
        _pinned(other_key, "fixture_registration", "other_registration"),
        (_pinned(other_key, "provenance", "other_source"),),
        ResourcePolicyAuthorityMarker.FIXTURE_PROVENANCE_NOT_PRODUCTION,
    )
    other_class = replace(
        fixture.resource_class,
        challenge_key=other_key,
        object_id="other_resource_class",
        provenance=other_provenance,
    )
    other_ref = resource_class_to_ref(other_class)

    assessment = _call(
        fixture,
        selected_class=other_class,
        selected_class_ref=other_ref,
        expected_active_resource_class_ref=other_ref,
    )

    assert assessment.outcome is StaticAssessmentOutcome.CHALLENGE_MISMATCH
    assert tuple(issue.code for issue in assessment.issues) == (
        ResourcePolicyIssueCode.CHALLENGE_MISMATCH,
    )


def test_unbound_same_challenge_class_is_unsupported_not_implicitly_selected(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    unbound_class = replace(
        fixture.resource_class,
        object_id="unbound_resource_class",
    )
    unbound_ref = resource_class_to_ref(unbound_class)

    assessment = _call(
        fixture,
        selected_class=unbound_class,
        selected_class_ref=unbound_ref,
        expected_active_resource_class_ref=unbound_ref,
    )

    assert assessment.outcome is StaticAssessmentOutcome.UNSUPPORTED_RESOURCE_CLASS
    assert tuple(issue.code for issue in assessment.issues) == (
        ResourcePolicyIssueCode.RESOURCE_CLASS_NOT_BOUND,
    )


def test_unbound_class_environment_mismatch_precedes_unsupported_class(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    other_environment = EnvironmentPin("unbound_other_environment", "1.0", _DIGEST)
    unbound_class = replace(
        fixture.resource_class,
        object_id="unbound_environment_class",
        execution_environment_pin=other_environment,
        required_plan_environment_pins=(other_environment,),
    )
    unbound_ref = resource_class_to_ref(unbound_class)

    assessment = _call(
        fixture,
        selected_class=unbound_class,
        selected_class_ref=unbound_ref,
        expected_active_resource_class_ref=unbound_ref,
    )

    assert assessment.outcome is StaticAssessmentOutcome.ENVIRONMENT_MISMATCH
    assert tuple(issue.code for issue in assessment.issues) == (
        ResourcePolicyIssueCode.PLAN_ENVIRONMENT_MISMATCH,
    )


def test_authority_context_and_plan_bindings_are_exact(tmp_path: Path) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    other_context = FixturePracticeResourceContext(
        fixture.compile_fixture.key,
        "other_practice_context",
        _pinned(
            fixture.compile_fixture.key,
            "fixture_registration",
            "other_registration",
        ),
        _pinned(
            fixture.compile_fixture.key,
            "internal_service_scope",
            "other_service",
        ),
        ResourcePolicyAuthorityMarker.FIXTURE_PRACTICE_NOT_OFFICIAL,
    )
    context_result = _call(fixture, authority_context=other_context)

    other_assembly = replace(
        fixture.policy.candidate_assembly_ref,
        object_id="other_candidate_assembly",
    )
    other_policy = replace(
        fixture.policy,
        candidate_assembly_ref=other_assembly,
    )
    other_policy_ref = research_resource_policy_to_ref(
        other_policy,
        class_bundle=fixture.class_bundle,
    )
    binding_result = _call(
        fixture,
        policy=other_policy,
        policy_ref=other_policy_ref,
        expected_active_policy_ref=other_policy_ref,
    )

    assert context_result.outcome is (
        StaticAssessmentOutcome.AUTHORITY_CONTEXT_MISMATCH
    )
    assert binding_result.outcome is StaticAssessmentOutcome.PLAN_BINDING_MISMATCH
    assert tuple(issue.code for issue in binding_result.issues) == (
        ResourcePolicyIssueCode.PLAN_ASSEMBLY_MISMATCH,
    )


def test_environment_dimension_unit_and_impact_tag_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    other_environment = EnvironmentPin("other_environment", "1.0", _DIGEST)
    environment_class = replace(
        fixture.resource_class,
        execution_environment_pin=other_environment,
        required_plan_environment_pins=(other_environment,),
    )
    environment_policy, environment_policy_ref, environment_bundle = _policy_for_class(
        fixture, environment_class
    )
    environment_result = _call(
        fixture,
        policy=environment_policy,
        policy_ref=environment_policy_ref,
        class_bundle=environment_bundle,
        selected_class=environment_class,
        selected_class_ref=environment_bundle[0][1],
        expected_active_policy_ref=environment_policy_ref,
        expected_active_resource_class_ref=environment_bundle[0][1],
    )

    requirement = fixture.plan.static_resource_requirements[0]
    dimension_class = replace(
        fixture.resource_class,
        supported_dimensions=(
            StaticResourceDimension("other_dimension", requirement.unit_ref),
        ),
    )
    dimension_policy, dimension_policy_ref, dimension_bundle = _policy_for_class(
        fixture,
        dimension_class,
    )
    dimension_result = _call(
        fixture,
        policy=dimension_policy,
        policy_ref=dimension_policy_ref,
        class_bundle=dimension_bundle,
        selected_class=dimension_class,
        selected_class_ref=dimension_bundle[0][1],
        expected_active_policy_ref=dimension_policy_ref,
        expected_active_resource_class_ref=dimension_bundle[0][1],
    )

    other_unit = _portable("unit", "other_unit")
    unit_class = replace(
        fixture.resource_class,
        supported_dimensions=(
            StaticResourceDimension(requirement.dimension_id, other_unit),
        ),
    )
    unit_policy, unit_policy_ref, unit_bundle = _policy_for_class(
        fixture,
        unit_class,
    )
    unit_result = _call(
        fixture,
        policy=unit_policy,
        policy_ref=unit_policy_ref,
        class_bundle=unit_bundle,
        selected_class=unit_class,
        selected_class_ref=unit_bundle[0][1],
        expected_active_policy_ref=unit_policy_ref,
        expected_active_resource_class_ref=unit_bundle[0][1],
    )

    tags_fixture = make_resource_policy_fixture(
        tmp_path,
        supported_impact_tags=("backbone_impact",),
    )
    tag_result = _call(tags_fixture)

    assert environment_result.outcome is StaticAssessmentOutcome.ENVIRONMENT_MISMATCH
    assert dimension_result.outcome is StaticAssessmentOutcome.UNSUPPORTED_REQUIREMENT
    assert tuple(issue.code for issue in dimension_result.issues) == (
        ResourcePolicyIssueCode.UNSUPPORTED_DIMENSION,
    )
    assert unit_result.outcome is StaticAssessmentOutcome.UNSUPPORTED_REQUIREMENT
    assert tuple(issue.code for issue in unit_result.issues) == (
        ResourcePolicyIssueCode.UNSUPPORTED_UNIT,
    )
    assert tag_result.outcome is StaticAssessmentOutcome.UNSUPPORTED_REQUIREMENT
    assert all(
        issue.code is ResourcePolicyIssueCode.UNSUPPORTED_IMPACT_TAG
        for issue in tag_result.issues
    )


def test_policy_ref_issuance_requires_complete_exact_class_cover(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    injected_class = replace(
        fixture.resource_class,
        object_id="injected_resource_class",
    )
    injected_ref = resource_class_to_ref(injected_class)

    with pytest.raises(ResourcePolicyInputRejected) as omitted:
        research_resource_policy_to_ref(fixture.policy, class_bundle=())
    assert omitted.value.code == "POLICY_BUNDLE_INCOMPLETE"
    with pytest.raises(ResourcePolicyInputRejected) as injected:
        validate_research_resource_policy_bundle(
            fixture.policy,
            class_bundle=(*fixture.class_bundle, (injected_class, injected_ref)),
        )
    assert injected.value.code == "POLICY_BUNDLE_INCOMPLETE"
    with pytest.raises(ResourcePolicyInputRejected):
        validate_research_resource_policy_bundle(
            fixture.policy,
            class_bundle=(
                (
                    fixture.resource_class,
                    replace(fixture.resource_class_ref, content_digest=_DIGEST),
                ),
            ),
        )


def test_structurally_missing_ceiling_rejects_before_policy_ref_issuance(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    unit = fixture.plan.static_resource_requirements[0].unit_ref
    two_dimension_class = replace(
        fixture.resource_class,
        supported_dimensions=(
            *fixture.resource_class.supported_dimensions,
            StaticResourceDimension("extra_dimension", unit),
        ),
    )
    class_ref = resource_class_to_ref(two_dimension_class)
    incomplete_binding = replace(
        fixture.policy.class_bindings[0],
        resource_class_ref=class_ref,
    )
    incomplete_policy = replace(
        fixture.policy,
        class_bindings=(incomplete_binding,),
    )

    with pytest.raises(ResourcePolicyInputRejected) as caught:
        research_resource_policy_to_ref(
            incomplete_policy,
            class_bundle=((two_dimension_class, class_ref),),
        )
    assert caught.value.code == "POLICY_BUNDLE_INCOMPLETE"


@pytest.mark.parametrize("hostile", (None, True, 1, 1.0, object()))
def test_static_operation_rejects_wrong_exact_plan_types(
    tmp_path: Path,
    hostile: object,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)

    with pytest.raises(ResourcePolicyInputRejected):
        _call(fixture, plan=hostile)
