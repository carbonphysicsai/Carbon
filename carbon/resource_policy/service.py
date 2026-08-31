"""Pure fail-closed operations for the B-02C research-resource policy domain."""

from __future__ import annotations

import hmac

from carbon.authoring.errors import AuthoringError
from carbon.authoring.primitives import (
    MAX_CANONICAL_PAYLOAD_BYTES,
    MAX_CANONICAL_TUPLE_ITEMS,
    validate_canonical_id,
)
from carbon.construction.errors import ConstructionError
from carbon.construction.plan import (
    ResolvedConstructionPlan,
    resolved_construction_plan_canonical_bytes,
)
from carbon.construction.refs import (
    ResolvedConstructionPlanRef,
    verify_construction_ref,
)

from . import canonical as c
from . import model as m
from .errors import ResourcePolicyInputCode, ResourcePolicyInputRejected
from .refs import (
    FixtureResourceDecisionRef,
    ObservedResourceReceiptRef,
    ResearchResourcePolicyRef,
    ResourceCancellationRecordRef,
    ResourceClassRef,
    StaticResourceAssessmentRef,
    encode_resource_policy_ref,
    verify_resource_policy_ref,
)

ClassBundle = tuple[tuple[m.ResourceClass, ResourceClassRef], ...]


def _wrong(path: str) -> ResourcePolicyInputRejected:
    return ResourcePolicyInputRejected(ResourcePolicyInputCode.WRONG_TYPE, path=path)


def _invalid(path: str) -> ResourcePolicyInputRejected:
    return ResourcePolicyInputRejected(ResourcePolicyInputCode.INVALID_VALUE, path=path)


def _bundle_error() -> ResourcePolicyInputRejected:
    return ResourcePolicyInputRejected(
        ResourcePolicyInputCode.POLICY_BUNDLE_INCOMPLETE,
        path="/resource_class_ref",
    )


def _verify_class_pair(
    resource_class: object,
    resource_class_ref: object,
) -> tuple[m.ResourceClass, ResourceClassRef]:
    if type(resource_class) is not m.ResourceClass:
        raise _wrong("/resource_class")
    if type(resource_class_ref) is not ResourceClassRef:
        raise _wrong("/resource_class_ref")
    payload = c.encode_resource_class(resource_class)
    verified = verify_resource_policy_ref(
        resource_class_ref,
        canonical_bytes=payload,
        challenge_key=resource_class.challenge_key,
        object_id=resource_class.object_id,
        object_version=resource_class.object_version,
    )
    assert type(verified) is ResourceClassRef
    decoded = c.decode_resource_class(payload, expected_ref=resource_class_ref)
    if decoded != resource_class:
        raise _invalid("/resource_class")
    return decoded, verified


def validate_resource_class(resource_class: object) -> m.ResourceClass:
    """Defensively round-trip one structurally valid exact ResourceClass."""

    if type(resource_class) is not m.ResourceClass:
        raise _wrong("/resource_class")
    payload = c.encode_resource_class(resource_class)
    decoded = c.decode_resource_class(payload)
    if decoded != resource_class:
        raise _invalid("/resource_class")
    return decoded


def _validate_binding_against_class(
    binding: m.ResourceClassPolicyBinding,
    resource_class: m.ResourceClass,
) -> None:
    dimensions = {
        (dimension.dimension_id, dimension.unit_ref)
        for dimension in resource_class.supported_dimensions
    }
    ceilings = {
        (ceiling.dimension_id, ceiling.unit_ref) for ceiling in binding.ceilings
    }
    if ceilings != dimensions or len(binding.ceilings) != len(dimensions):
        raise _bundle_error()
    metrics = {
        metric.metric_id: metric for metric in resource_class.observation_metrics
    }
    for limit in binding.runtime_limits:
        metric = metrics.get(limit.metric_id)
        if metric is None or metric.unit_ref != limit.unit_ref:
            raise _bundle_error()


def validate_research_resource_policy_bundle(
    policy: object,
    *,
    class_bundle: object,
) -> ClassBundle:
    """Verify the complete one-to-one class cover and all dormant bindings."""

    if type(policy) is not m.ResearchResourcePolicy:
        raise _wrong("/policy_ref")
    if (
        type(class_bundle) is not tuple
        or not class_bundle
        or len(class_bundle) > MAX_CANONICAL_TUPLE_ITEMS
        or len(class_bundle) != len(policy.class_bindings)
    ):
        raise _bundle_error()
    verified_pairs: list[tuple[m.ResourceClass, ResourceClassRef]] = []
    for pair in class_bundle:
        if type(pair) is not tuple or len(pair) != 2:
            raise _bundle_error()
        verified_pairs.append(_verify_class_pair(pair[0], pair[1]))
    if len({pair[1] for pair in verified_pairs}) != len(verified_pairs):
        raise _bundle_error()
    bound_refs = tuple(binding.resource_class_ref for binding in policy.class_bindings)
    supplied_refs = tuple(pair[1] for pair in verified_pairs)
    if set(bound_refs) != set(supplied_refs) or len(bound_refs) != len(supplied_refs):
        raise _bundle_error()
    by_ref = {ref: value for value, ref in verified_pairs}
    for binding in policy.class_bindings:
        resource_class = by_ref[binding.resource_class_ref]
        if resource_class.challenge_key != policy.challenge_key:
            raise _bundle_error()
        _validate_binding_against_class(binding, resource_class)
    verified_pairs.sort(
        key=lambda pair: c.canonical_sort_key(pair[0])
        + encode_resource_policy_ref(pair[1])
    )
    return tuple(verified_pairs)


def _verify_policy(
    policy: object,
    policy_ref: object,
    class_bundle: object,
) -> tuple[m.ResearchResourcePolicy, ResearchResourcePolicyRef, ClassBundle]:
    if type(policy) is not m.ResearchResourcePolicy:
        raise _wrong("/policy_ref")
    if type(policy_ref) is not ResearchResourcePolicyRef:
        raise _wrong("/policy_ref")
    bundle = validate_research_resource_policy_bundle(
        policy,
        class_bundle=class_bundle,
    )
    payload = c.encode_research_resource_policy(policy)
    verified = verify_resource_policy_ref(
        policy_ref,
        canonical_bytes=payload,
        challenge_key=policy.challenge_key,
        object_id=policy.object_id,
        object_version=policy.object_version,
    )
    assert type(verified) is ResearchResourcePolicyRef
    decoded = c.decode_research_resource_policy(payload, class_bundle=bundle)
    if decoded != policy:
        raise _invalid("/policy_ref")
    return decoded, verified, bundle


def _selected_pair(
    selected_class: object,
    selected_class_ref: object,
    bundle: ClassBundle,
) -> tuple[m.ResourceClass, ResourceClassRef, bool]:
    resource_class, resource_class_ref = _verify_class_pair(
        selected_class,
        selected_class_ref,
    )
    matching = tuple(pair for pair in bundle if pair[1] == resource_class_ref)
    if matching and matching != ((resource_class, resource_class_ref),):
        raise _bundle_error()
    return resource_class, resource_class_ref, bool(matching)


def _binding_for(
    policy: m.ResearchResourcePolicy,
    resource_class_ref: ResourceClassRef,
) -> m.ResourceClassPolicyBinding | None:
    matching = tuple(
        binding
        for binding in policy.class_bindings
        if binding.resource_class_ref == resource_class_ref
    )
    if len(matching) > 1:
        raise _bundle_error()
    return matching[0] if matching else None


def _verify_plan(
    plan: object,
    plan_ref: object,
) -> tuple[ResolvedConstructionPlan, ResolvedConstructionPlanRef, bytes]:
    if type(plan) is not ResolvedConstructionPlan:
        raise _wrong("/construction_plan_ref")
    if type(plan_ref) is not ResolvedConstructionPlanRef:
        raise _wrong("/construction_plan_ref")
    try:
        payload = resolved_construction_plan_canonical_bytes(plan)
        verified = verify_construction_ref(
            plan_ref,
            canonical_bytes=payload,
            challenge_key=plan.challenge_key,
        )
    except ConstructionError as exc:
        raise ResourcePolicyInputRejected(
            ResourcePolicyInputCode.REF_DIGEST_MISMATCH,
            path="/construction_plan_ref",
        ) from exc
    assert type(verified) is ResolvedConstructionPlanRef
    return plan, verified, payload


def _plan_unchanged(plan: ResolvedConstructionPlan, before: bytes) -> None:
    try:
        after = resolved_construction_plan_canonical_bytes(plan)
    except ConstructionError as exc:
        raise _invalid("/construction_plan_ref") from exc
    if not hmac.compare_digest(before, after):
        raise _invalid("/construction_plan_ref")


def _verify_assessment(
    assessment: object,
    assessment_ref: object,
) -> tuple[m.StaticResourceAssessment, StaticResourceAssessmentRef]:
    if type(assessment) is not m.StaticResourceAssessment:
        raise _wrong("/assessment_ref")
    if type(assessment_ref) is not StaticResourceAssessmentRef:
        raise _wrong("/assessment_ref")
    payload = c.encode_static_resource_assessment(assessment)
    verified = verify_resource_policy_ref(
        assessment_ref,
        canonical_bytes=payload,
        challenge_key=assessment.challenge_key,
    )
    assert type(verified) is StaticResourceAssessmentRef
    return assessment, verified


def _verify_decision(
    decision: object,
    decision_ref: object,
) -> tuple[m.FixtureResourceDecision, FixtureResourceDecisionRef]:
    if type(decision) is not m.FixtureResourceDecision:
        raise _wrong("/fixture_decision_ref")
    if type(decision_ref) is not FixtureResourceDecisionRef:
        raise _wrong("/fixture_decision_ref")
    payload = c.encode_fixture_resource_decision(decision)
    verified = verify_resource_policy_ref(
        decision_ref,
        canonical_bytes=payload,
        challenge_key=decision.challenge_key,
    )
    assert type(verified) is FixtureResourceDecisionRef
    return decision, verified


def _issue(
    code: m.ResourcePolicyIssueCode,
    path: str,
) -> m.ResourcePolicyIssue:
    return m.make_resource_policy_issue(code, path)


def assess_static_resources(
    *,
    plan: object,
    plan_ref: object,
    policy: object,
    policy_ref: object,
    class_bundle: object,
    selected_class: object,
    selected_class_ref: object,
    expected_active_policy_ref: object,
    expected_active_resource_class_ref: object,
    authority_context: object,
) -> m.StaticResourceAssessment:
    """Evaluate exact plan requirements with fixed category precedence."""

    verified_plan, verified_plan_ref, before = _verify_plan(plan, plan_ref)
    verified_policy, verified_policy_ref, bundle = _verify_policy(
        policy,
        policy_ref,
        class_bundle,
    )
    resource_class, resource_class_ref, class_is_in_bundle = _selected_pair(
        selected_class,
        selected_class_ref,
        bundle,
    )
    if type(expected_active_policy_ref) is not ResearchResourcePolicyRef:
        raise _wrong("/expected_active_policy_ref")
    if type(expected_active_resource_class_ref) is not ResourceClassRef:
        raise _wrong("/expected_active_resource_class_ref")
    expected_policy = ResearchResourcePolicyRef(
        expected_active_policy_ref.challenge_key,
        expected_active_policy_ref.object_id,
        expected_active_policy_ref.object_version,
        expected_active_policy_ref.schema_version,
        expected_active_policy_ref.canonicalization_profile,
        expected_active_policy_ref.content_digest,
    )
    expected_class = ResourceClassRef(
        expected_active_resource_class_ref.challenge_key,
        expected_active_resource_class_ref.object_id,
        expected_active_resource_class_ref.object_version,
        expected_active_resource_class_ref.schema_version,
        expected_active_resource_class_ref.canonicalization_profile,
        expected_active_resource_class_ref.content_digest,
    )
    if type(authority_context) not in (
        m.FixturePracticeResourceContext,
        m.FixtureOfficialShapedResourceContext,
    ):
        raise _wrong("/authority_context")
    supplied_context = type(authority_context)(
        authority_context.challenge_key,
        authority_context.context_id,
        authority_context.fixture_registration_ref,
        authority_context.internal_service_scope_ref,
        authority_context.authority_marker,
    )
    outcome = m.StaticAssessmentOutcome.ADMISSIBLE
    issues: tuple[m.ResourcePolicyIssue, ...] = ()
    if verified_policy_ref != expected_policy:
        outcome = m.StaticAssessmentOutcome.STALE_POLICY
        issues = (
            _issue(
                m.ResourcePolicyIssueCode.STALE_POLICY_REF,
                "/expected_active_policy_ref",
            ),
        )
    elif resource_class_ref != expected_class:
        outcome = m.StaticAssessmentOutcome.STALE_REFERENCE
        issues = (
            _issue(
                m.ResourcePolicyIssueCode.STALE_RESOURCE_CLASS_REF,
                "/expected_active_resource_class_ref",
            ),
        )
    elif any(
        value != verified_policy.challenge_key
        for value in (
            verified_plan.challenge_key,
            verified_plan_ref.challenge_key,
            resource_class.challenge_key,
            resource_class_ref.challenge_key,
            supplied_context.challenge_key,
        )
    ):
        outcome = m.StaticAssessmentOutcome.CHALLENGE_MISMATCH
        issues = (
            _issue(m.ResourcePolicyIssueCode.CHALLENGE_MISMATCH, "/challenge_key"),
        )
    elif supplied_context != verified_policy.authority_context:
        outcome = m.StaticAssessmentOutcome.AUTHORITY_CONTEXT_MISMATCH
        issues = (
            _issue(
                m.ResourcePolicyIssueCode.AUTHORITY_CONTEXT_MISMATCH,
                "/authority_context",
            ),
        )
    else:
        binding_issues: list[m.ResourcePolicyIssue] = []
        if (
            verified_plan.candidate_assembly_ref
            != verified_policy.candidate_assembly_ref
        ):
            binding_issues.append(
                _issue(
                    m.ResourcePolicyIssueCode.PLAN_ASSEMBLY_MISMATCH,
                    "/construction_plan_ref/candidate_assembly_ref",
                )
            )
        if verified_plan.parameter_catalog_ref != verified_policy.parameter_catalog_ref:
            binding_issues.append(
                _issue(
                    m.ResourcePolicyIssueCode.PLAN_CATALOG_MISMATCH,
                    "/construction_plan_ref/parameter_catalog_ref",
                )
            )
        if verified_plan.compiler_identity != verified_policy.compiler_identity:
            binding_issues.append(
                _issue(
                    m.ResourcePolicyIssueCode.PLAN_COMPILER_MISMATCH,
                    "/construction_plan_ref/compiler_identity",
                )
            )
        if binding_issues:
            outcome = m.StaticAssessmentOutcome.PLAN_BINDING_MISMATCH
            issues = tuple(binding_issues)
        else:
            environment_issues = tuple(
                _issue(
                    m.ResourcePolicyIssueCode.PLAN_ENVIRONMENT_MISMATCH,
                    f"/resource_class/required_plan_environment_pins/{index}",
                )
                for index, environment in enumerate(
                    resource_class.required_plan_environment_pins
                )
                if environment not in verified_plan.environment_pins
            )
            if environment_issues:
                outcome = m.StaticAssessmentOutcome.ENVIRONMENT_MISMATCH
                issues = environment_issues
        if outcome is m.StaticAssessmentOutcome.ADMISSIBLE and not class_is_in_bundle:
            outcome = m.StaticAssessmentOutcome.UNSUPPORTED_RESOURCE_CLASS
            issues = (
                _issue(
                    m.ResourcePolicyIssueCode.RESOURCE_CLASS_NOT_BOUND,
                    "/resource_class_ref",
                ),
            )
        if outcome is m.StaticAssessmentOutcome.ADMISSIBLE:
            binding = _binding_for(verified_policy, resource_class_ref)
            assert binding is not None
            dimensions = {
                item.dimension_id: item for item in resource_class.supported_dimensions
            }
            requirement_issues: list[m.ResourcePolicyIssue] = []
            for index, requirement in enumerate(
                verified_plan.static_resource_requirements
            ):
                dimension = dimensions.get(requirement.dimension_id)
                if dimension is None:
                    requirement_issues.append(
                        _issue(
                            m.ResourcePolicyIssueCode.UNSUPPORTED_DIMENSION,
                            f"/static_resource_requirements/{index}/dimension_id",
                        )
                    )
                elif dimension.unit_ref != requirement.unit_ref:
                    requirement_issues.append(
                        _issue(
                            m.ResourcePolicyIssueCode.UNSUPPORTED_UNIT,
                            f"/static_resource_requirements/{index}/unit_ref",
                        )
                    )
            for index, tag in enumerate(verified_plan.resource_impact_tags):
                if tag not in binding.supported_impact_tags:
                    requirement_issues.append(
                        _issue(
                            m.ResourcePolicyIssueCode.UNSUPPORTED_IMPACT_TAG,
                            f"/resource_impact_tags/{index}",
                        )
                    )
            if requirement_issues:
                outcome = m.StaticAssessmentOutcome.UNSUPPORTED_REQUIREMENT
                issues = tuple(requirement_issues)
            else:
                ceilings = {
                    ceiling.dimension_id: ceiling for ceiling in binding.ceilings
                }
                over_issues = tuple(
                    _issue(
                        m.ResourcePolicyIssueCode.STATIC_REQUIREMENT_OVER_LIMIT,
                        f"/static_resource_requirements/{index}/quantity",
                    )
                    for index, requirement in enumerate(
                        verified_plan.static_resource_requirements
                    )
                    if requirement.quantity
                    > ceilings[requirement.dimension_id].maximum_quantity
                )
                if over_issues:
                    outcome = m.StaticAssessmentOutcome.OVER_LIMIT
                    issues = over_issues
    result = m.StaticResourceAssessment(
        m.StaticResourceAssessment.OBJECT_KIND,
        c.RESOURCE_POLICY_SCHEMA_VERSION,
        c.RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        verified_policy.challenge_key,
        verified_policy_ref,
        resource_class_ref,
        expected_policy,
        expected_class,
        verified_plan_ref,
        supplied_context,
        verified_plan.static_resource_requirements,
        verified_plan.resource_impact_tags,
        outcome,
        issues,
        m.ResourceEpistemicLayer.STATIC_CONSTRUCTION_REQUIREMENT,
        m.ResourcePolicyAuthorityMarker.STATIC_POLICY_RESULT_NOT_EXECUTION_OR_SCIENCE,
    )
    _plan_unchanged(verified_plan, before)
    return result


_READINESS_FIELDS = (
    (
        "validator_capacity",
        m.ResourceDeferralCause.CAPACITY_UNAVAILABLE,
    ),
    (
        "reconstruction_funding",
        m.ResourceDeferralCause.RECONSTRUCTION_FUNDING_UNAVAILABLE,
    ),
    ("queue_availability", m.ResourceDeferralCause.QUEUE_UNAVAILABLE),
    (
        "evidence_budget_availability",
        m.ResourceDeferralCause.EVIDENCE_BUDGET_UNAVAILABLE,
    ),
)


def _verify_core_outcome_inputs(
    *,
    plan: object,
    plan_ref: object,
    policy: object,
    policy_ref: object,
    class_bundle: object,
    selected_class: object,
    selected_class_ref: object,
    assessment: object,
    assessment_ref: object,
) -> tuple[
    ResolvedConstructionPlan,
    ResolvedConstructionPlanRef,
    bytes,
    m.ResearchResourcePolicy,
    ResearchResourcePolicyRef,
    ClassBundle,
    m.ResourceClass,
    ResourceClassRef,
    m.ResourceClassPolicyBinding,
    m.StaticResourceAssessment,
    StaticResourceAssessmentRef,
]:
    verified_plan, verified_plan_ref, before = _verify_plan(plan, plan_ref)
    verified_policy, verified_policy_ref, bundle = _verify_policy(
        policy, policy_ref, class_bundle
    )
    resource_class, resource_class_ref, in_bundle = _selected_pair(
        selected_class, selected_class_ref, bundle
    )
    if not in_bundle:
        raise _bundle_error()
    binding = _binding_for(verified_policy, resource_class_ref)
    assert binding is not None
    verified_assessment, verified_assessment_ref = _verify_assessment(
        assessment, assessment_ref
    )
    if (
        verified_assessment.outcome is not m.StaticAssessmentOutcome.ADMISSIBLE
        or verified_assessment.policy_ref != verified_policy_ref
        or verified_assessment.resource_class_ref != resource_class_ref
        or verified_assessment.construction_plan_ref != verified_plan_ref
        or verified_assessment.authority_context != verified_policy.authority_context
    ):
        raise _invalid("/assessment_ref")
    recomputed_assessment = assess_static_resources(
        plan=verified_plan,
        plan_ref=verified_plan_ref,
        policy=verified_policy,
        policy_ref=verified_policy_ref,
        class_bundle=bundle,
        selected_class=resource_class,
        selected_class_ref=resource_class_ref,
        expected_active_policy_ref=verified_assessment.expected_active_policy_ref,
        expected_active_resource_class_ref=(
            verified_assessment.expected_active_resource_class_ref
        ),
        authority_context=verified_assessment.authority_context,
    )
    if recomputed_assessment != verified_assessment:
        raise _invalid("/assessment_ref")
    return (
        verified_plan,
        verified_plan_ref,
        before,
        verified_policy,
        verified_policy_ref,
        bundle,
        resource_class,
        resource_class_ref,
        binding,
        verified_assessment,
        verified_assessment_ref,
    )


def decide_fixture_readiness(
    *,
    plan: object,
    plan_ref: object,
    assessment: object,
    assessment_ref: object,
    policy: object,
    policy_ref: object,
    class_bundle: object,
    selected_class: object,
    selected_class_ref: object,
    availability_input: object,
) -> m.FixtureResourceDecision:
    """Resolve every required fixture-only readiness fact without optimism."""

    (
        verified_plan,
        _verified_plan_ref,
        before,
        verified_policy,
        verified_policy_ref,
        _,
        _resource_class,
        resource_class_ref,
        binding,
        _verified_assessment,
        verified_assessment_ref,
    ) = _verify_core_outcome_inputs(
        plan=plan,
        plan_ref=plan_ref,
        policy=policy,
        policy_ref=policy_ref,
        class_bundle=class_bundle,
        selected_class=selected_class,
        selected_class_ref=selected_class_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
    )
    if type(availability_input) is m.NoAvailabilityInput:
        availability: m.FixtureAvailabilityInput = m.NoAvailabilityInput()
    elif type(availability_input) is m.FixtureResourceAvailability:
        availability = m.FixtureResourceAvailability(
            availability_input.object_kind,
            availability_input.schema_version,
            availability_input.canonicalization_profile,
            availability_input.challenge_key,
            availability_input.policy_ref,
            availability_input.resource_class_ref,
            availability_input.authority_context,
            availability_input.validator_capacity,
            availability_input.reconstruction_funding,
            availability_input.queue_availability,
            availability_input.evidence_budget_availability,
            availability_input.fixture_registration_ref,
            availability_input.authority_marker,
        )
        if (
            availability.policy_ref != verified_policy_ref
            or availability.resource_class_ref != resource_class_ref
            or availability.authority_context != verified_policy.authority_context
        ):
            raise _invalid("/authority_context")
    else:
        raise _wrong("/type")
    causes: list[m.ResourceDeferralCause] = []
    for field, cause in _READINESS_FIELDS:
        requirement = getattr(binding.readiness_requirements, field)
        if type(availability) is m.NoAvailabilityInput:
            if type(requirement) is m.OperationalRequirementRequired:
                causes.append(cause)
            continue
        state = getattr(availability, field)
        if type(requirement) is m.OperationalRequirementRequired:
            if state is m.FixtureAvailabilityState.NOT_APPLICABLE:
                raise _invalid("/type")
            if state is m.FixtureAvailabilityState.UNAVAILABLE:
                causes.append(cause)
        elif state is not m.FixtureAvailabilityState.NOT_APPLICABLE:
            raise _invalid("/type")
    outcome = (
        m.FixtureDecisionOutcome.EVIDENCE_DEFERRED
        if causes
        else m.FixtureDecisionOutcome.FIXTURE_ADMISSIBLE
    )
    result = m.FixtureResourceDecision(
        m.FixtureResourceDecision.OBJECT_KIND,
        c.RESOURCE_POLICY_SCHEMA_VERSION,
        c.RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        verified_policy.challenge_key,
        verified_assessment_ref,
        verified_policy_ref,
        resource_class_ref,
        verified_policy.authority_context,
        availability,
        outcome,
        tuple(causes),
        m.ResourcePolicyAuthorityMarker.POLICY_ADMISSIBILITY_NOT_QUOTE_OR_EXECUTION,
    )
    _plan_unchanged(verified_plan, before)
    return result


def _verify_decision_semantics(
    decision: object,
    decision_ref: object,
    *,
    plan: ResolvedConstructionPlan,
    plan_ref: ResolvedConstructionPlanRef,
    assessment: m.StaticResourceAssessment,
    assessment_ref: StaticResourceAssessmentRef,
    policy: m.ResearchResourcePolicy,
    policy_ref: ResearchResourcePolicyRef,
    class_bundle: ClassBundle,
    selected_class: m.ResourceClass,
    selected_class_ref: ResourceClassRef,
    require_admissible: bool,
) -> tuple[m.FixtureResourceDecision, FixtureResourceDecisionRef]:
    verified, verified_ref = _verify_decision(decision, decision_ref)
    recomputed = decide_fixture_readiness(
        plan=plan,
        plan_ref=plan_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
        policy=policy,
        policy_ref=policy_ref,
        class_bundle=class_bundle,
        selected_class=selected_class,
        selected_class_ref=selected_class_ref,
        availability_input=verified.availability_input,
    )
    if (
        recomputed != verified
        or require_admissible
        and verified.outcome is not m.FixtureDecisionOutcome.FIXTURE_ADMISSIBLE
    ):
        raise _invalid("/fixture_decision_ref")
    return verified, verified_ref


def evaluate_enforcement(
    *,
    plan: object,
    plan_ref: object,
    policy: object,
    policy_ref: object,
    class_bundle: object,
    selected_class: object,
    selected_class_ref: object,
    assessment: object,
    assessment_ref: object,
    decision: object,
    decision_ref: object,
    limit_id: object,
    observation: object,
) -> m.ResourceEnforcementResult:
    """Evaluate one inclusive limit and return a pure fail-closed event/result."""

    (
        verified_plan,
        verified_plan_ref,
        before,
        verified_policy,
        verified_policy_ref,
        verified_bundle,
        resource_class,
        resource_class_ref,
        binding,
        verified_assessment,
        verified_assessment_ref,
    ) = _verify_core_outcome_inputs(
        plan=plan,
        plan_ref=plan_ref,
        policy=policy,
        policy_ref=policy_ref,
        class_bundle=class_bundle,
        selected_class=selected_class,
        selected_class_ref=selected_class_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
    )
    _, verified_decision_ref = _verify_decision_semantics(
        decision,
        decision_ref,
        plan=verified_plan,
        plan_ref=verified_plan_ref,
        assessment=verified_assessment,
        assessment_ref=verified_assessment_ref,
        policy=verified_policy,
        policy_ref=verified_policy_ref,
        class_bundle=verified_bundle,
        selected_class=resource_class,
        selected_class_ref=resource_class_ref,
        require_admissible=True,
    )
    if type(limit_id) is not str:
        raise _wrong("/limit_id")
    try:
        checked_limit_id = validate_canonical_id(limit_id, "limit_id")
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _invalid("/limit_id") from exc
    if len(checked_limit_id.encode("ascii")) > MAX_CANONICAL_PAYLOAD_BYTES:
        raise _invalid("/limit_id")
    limits = tuple(
        limit for limit in binding.runtime_limits if limit.limit_id == checked_limit_id
    )
    if len(limits) != 1:
        raise ResourcePolicyInputRejected(
            ResourcePolicyInputCode.LIMIT_NOT_BOUND,
            path="/limit_id",
        )
    limit = limits[0]
    if type(observation) is not m.ResourceEnforcementObservation:
        raise _wrong("/observation")
    observed = m.ResourceEnforcementObservation(
        observation.metric_quantity,
        observation.observation_kind,
    )
    metrics = {
        metric.metric_id: metric for metric in resource_class.observation_metrics
    }
    metric = metrics.get(limit.metric_id)
    expected_kind = (
        m.EnforcementObservationKind.CURRENT_TOTAL
        if limit.enforcement_point is m.EnforcementPoint.RUNTIME_OBSERVATION
        else m.EnforcementObservationKind.ATTEMPTED_NEXT_TOTAL
    )
    mismatch = (
        metric is None
        or observed.metric_quantity.metric_id != limit.metric_id
        or observed.metric_quantity.unit_ref != limit.unit_ref
        or metric is not None
        and observed.metric_quantity.observation_role is not metric.observation_role
        or observed.observation_kind is not expected_kind
    )
    if mismatch:
        outcome = m.ResourceEnforcementOutcome.ENFORCEMENT_FAILURE
        action = m.ResourceEnforcementAction.FAIL_CLOSED
        issue: m.EnforcementIssueBinding = _issue(
            m.ResourcePolicyIssueCode.LIMIT_OBSERVATION_MISMATCH,
            "/observation",
        )
    elif observed.metric_quantity.quantity <= limit.maximum_quantity:
        outcome = m.ResourceEnforcementOutcome.CONTINUE_FIXTURE
        action = m.ResourceEnforcementAction.NO_STOP
        issue = m.NoIssue()
    else:
        outcome = m.ResourceEnforcementOutcome.STOPPED_OVER_LIMIT
        action = {
            m.EnforcementMode.PREVENT_START_ON_EXCESS: m.ResourceEnforcementAction.PREVENT_FIXTURE_START,
            m.EnforcementMode.PREVENT_NEXT_UNIT_ON_EXCESS: m.ResourceEnforcementAction.PREVENT_NEXT_UNIT,
            m.EnforcementMode.STOP_ON_FIRST_OBSERVED_EXCESS: m.ResourceEnforcementAction.REQUEST_FIXTURE_STOP,
        }[limit.enforcement_mode]
        issue = m.NoIssue()
    event = m.ResourceEnforcementEvent(
        m.ResourceEnforcementEvent.OBJECT_KIND,
        c.RESOURCE_POLICY_SCHEMA_VERSION,
        c.RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        verified_policy.challenge_key,
        verified_policy_ref,
        resource_class_ref,
        verified_plan_ref,
        verified_assessment_ref,
        verified_decision_ref,
        verified_policy.authority_context,
        limit.limit_id,
        limit.enforcement_point,
        limit.enforcement_mode,
        limit.maximum_quantity,
        observed,
        action,
        outcome,
        issue,
    )
    result = m.ResourceEnforcementResult(
        m.ResourceEnforcementResult.OBJECT_KIND,
        c.RESOURCE_POLICY_SCHEMA_VERSION,
        c.RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        verified_policy.challenge_key,
        verified_policy_ref,
        resource_class_ref,
        verified_plan_ref,
        verified_assessment_ref,
        verified_decision_ref,
        verified_policy.authority_context,
        event,
        outcome,
        m.ResourcePolicyAuthorityMarker.RESOURCE_ENFORCEMENT_NOT_EXECUTION_OR_SCIENCE,
    )
    _plan_unchanged(verified_plan, before)
    return result


def _copy_enforcement_result(value: object) -> m.ResourceEnforcementResult:
    if type(value) is not m.ResourceEnforcementResult:
        raise _wrong("/enforcement")
    payload = c.encode_resource_enforcement_result(value)
    return c.decode_resource_enforcement_result(payload)


def _check_enforcement_result_bindings(
    result: m.ResourceEnforcementResult,
    *,
    plan_ref: ResolvedConstructionPlanRef,
    policy_ref: ResearchResourcePolicyRef,
    class_ref: ResourceClassRef,
    assessment_ref: StaticResourceAssessmentRef,
    decision_ref: FixtureResourceDecisionRef,
    context: m.ResourceAuthorityContext,
) -> None:
    if (
        result.construction_plan_ref != plan_ref
        or result.policy_ref != policy_ref
        or result.resource_class_ref != class_ref
        or result.assessment_ref != assessment_ref
        or result.decision_ref != decision_ref
        or result.authority_context != context
    ):
        raise _invalid("/enforcement")


def _verify_enforcement_result_semantics(
    value: object,
    *,
    plan: ResolvedConstructionPlan,
    plan_ref: ResolvedConstructionPlanRef,
    policy: m.ResearchResourcePolicy,
    policy_ref: ResearchResourcePolicyRef,
    class_bundle: ClassBundle,
    selected_class: m.ResourceClass,
    selected_class_ref: ResourceClassRef,
    assessment: m.StaticResourceAssessment,
    assessment_ref: StaticResourceAssessmentRef,
    decision: m.FixtureResourceDecision,
    decision_ref: FixtureResourceDecisionRef,
) -> m.ResourceEnforcementResult:
    copied = _copy_enforcement_result(value)
    _check_enforcement_result_bindings(
        copied,
        plan_ref=plan_ref,
        policy_ref=policy_ref,
        class_ref=selected_class_ref,
        assessment_ref=assessment_ref,
        decision_ref=decision_ref,
        context=policy.authority_context,
    )
    recomputed = evaluate_enforcement(
        plan=plan,
        plan_ref=plan_ref,
        policy=policy,
        policy_ref=policy_ref,
        class_bundle=class_bundle,
        selected_class=selected_class,
        selected_class_ref=selected_class_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
        decision=decision,
        decision_ref=decision_ref,
        limit_id=copied.event.limit_id,
        observation=copied.event.observation,
    )
    if recomputed != copied:
        raise _invalid("/enforcement")
    return copied


_WITHDRAWAL_REQUIREMENT_FIELDS = {
    m.CancellationReason.CAPACITY_WITHDRAWN: "validator_capacity",
    m.CancellationReason.FUNDING_WITHDRAWN: "reconstruction_funding",
    m.CancellationReason.QUEUE_WITHDRAWN: "queue_availability",
    m.CancellationReason.EVIDENCE_BUDGET_WITHDRAWN: ("evidence_budget_availability"),
}


def make_cancellation_record(
    *,
    plan: object,
    plan_ref: object,
    policy: object,
    policy_ref: object,
    class_bundle: object,
    selected_class: object,
    selected_class_ref: object,
    assessment: object,
    assessment_ref: object,
    decision: object,
    decision_ref: object,
    actor: object,
    reason: object,
    stop_point: object,
    work_started: object,
    observed_resource_quantities_so_far: object,
    enforcement_result: object | None = None,
) -> m.ResourceCancellationRecord:
    """Create one immutable cancellation record after verifying every seam."""

    (
        verified_plan,
        verified_plan_ref,
        before,
        verified_policy,
        verified_policy_ref,
        verified_bundle,
        resource_class,
        resource_class_ref,
        binding,
        verified_assessment,
        verified_assessment_ref,
    ) = _verify_core_outcome_inputs(
        plan=plan,
        plan_ref=plan_ref,
        policy=policy,
        policy_ref=policy_ref,
        class_bundle=class_bundle,
        selected_class=selected_class,
        selected_class_ref=selected_class_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
    )
    verified_decision, verified_decision_ref = _verify_decision_semantics(
        decision,
        decision_ref,
        plan=verified_plan,
        plan_ref=verified_plan_ref,
        assessment=verified_assessment,
        assessment_ref=verified_assessment_ref,
        policy=verified_policy,
        policy_ref=verified_policy_ref,
        class_bundle=verified_bundle,
        selected_class=resource_class,
        selected_class_ref=resource_class_ref,
        require_admissible=False,
    )
    if type(reason) is not m.CancellationReason:
        raise _wrong("/type")
    if type(actor) not in (
        m.PolicyEnforcerActor,
        m.FixtureRequesterActor,
        m.InfrastructureActor,
    ):
        raise _wrong("/type")
    if type(stop_point) not in (m.NoEnforcementPoint, m.AtEnforcementPoint):
        raise _wrong("/enforcement")
    if type(work_started) is not bool:
        raise _wrong("/type")
    if (
        type(observed_resource_quantities_so_far) is not tuple
        or len(observed_resource_quantities_so_far) > MAX_CANONICAL_TUPLE_ITEMS
    ):
        raise _wrong("/observation")
    observations = tuple(
        (
            m.ObservedResourceQuantity(
                item.metric_id,
                item.unit_ref,
                item.quantity,
                item.observation_role,
            )
            if type(item) is m.ObservedResourceQuantity
            else (_ for _ in ()).throw(_wrong("/observation"))
        )
        for item in observed_resource_quantities_so_far
    )
    metrics = {
        metric.metric_id: metric for metric in resource_class.observation_metrics
    }
    if len({item.metric_id for item in observations}) != len(observations):
        raise _invalid("/observation")
    for observed in observations:
        metric = metrics.get(observed.metric_id)
        if (
            metric is None
            or metric.unit_ref != observed.unit_ref
            or metric.observation_role is not observed.observation_role
        ):
            raise _invalid("/observation")
    exact_actor: m.CancellationActor
    if type(actor) is m.PolicyEnforcerActor:
        exact_actor = m.PolicyEnforcerActor(actor.policy_authority_ref)
        if exact_actor.policy_authority_ref != verified_policy.policy_authority_ref:
            raise _invalid("/scope_binding")
    elif type(actor) is m.FixtureRequesterActor:
        exact_actor = m.FixtureRequesterActor(actor.fixture_registration_ref)
        if (
            exact_actor.fixture_registration_ref
            != verified_policy.authority_context.fixture_registration_ref
        ):
            raise _invalid("/fixture_registration_ref")
    else:
        exact_actor = m.InfrastructureActor(actor.infrastructure_failure_ref)
    if enforcement_result is None:
        event_binding: m.EnforcementEventBinding = m.NoEnforcementEvent()
    else:
        verified_enforcement = _verify_enforcement_result_semantics(
            enforcement_result,
            plan=verified_plan,
            plan_ref=verified_plan_ref,
            policy=verified_policy,
            policy_ref=verified_policy_ref,
            class_bundle=verified_bundle,
            selected_class=resource_class,
            selected_class_ref=resource_class_ref,
            assessment=verified_assessment,
            assessment_ref=verified_assessment_ref,
            decision=verified_decision,
            decision_ref=verified_decision_ref,
        )
        event_binding = verified_enforcement.event
    if (
        type(event_binding) is m.ResourceEnforcementEvent
        and event_binding.enforcement_point is m.EnforcementPoint.RUNTIME_OBSERVATION
        and event_binding.observation.observation_kind
        is m.EnforcementObservationKind.CURRENT_TOTAL
    ):
        event_quantity = event_binding.observation.metric_quantity
        event_metric = metrics.get(event_quantity.metric_id)
        if (
            event_metric is not None
            and event_metric.unit_ref == event_quantity.unit_ref
            and event_metric.observation_role is event_quantity.observation_role
            and event_quantity not in observations
        ):
            raise _invalid("/observation")
    if (
        reason
        in (
            m.CancellationReason.POLICY_LIMIT_REACHED,
            m.CancellationReason.ENFORCEMENT_FAILURE,
            *_WITHDRAWAL_REQUIREMENT_FIELDS,
        )
        and verified_decision.outcome is not m.FixtureDecisionOutcome.FIXTURE_ADMISSIBLE
    ):
        raise _invalid("/fixture_decision_ref")
    if reason in _WITHDRAWAL_REQUIREMENT_FIELDS:
        requirement = getattr(
            binding.readiness_requirements,
            _WITHDRAWAL_REQUIREMENT_FIELDS[reason],
        )
        if type(requirement) is not m.OperationalRequirementRequired:
            raise _invalid("/type")
        state = m.CancellationResultingState.EVIDENCE_DEFERRED
    elif reason is m.CancellationReason.INFRASTRUCTURE_FAILURE:
        state = m.CancellationResultingState.INFRASTRUCTURE_UNAVAILABLE_NON_SCIENTIFIC
    else:
        state = m.CancellationResultingState.CANCELLED_NON_SCIENTIFIC
    record = m.ResourceCancellationRecord(
        m.ResourceCancellationRecord.OBJECT_KIND,
        c.RESOURCE_POLICY_SCHEMA_VERSION,
        c.RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        verified_policy.challenge_key,
        verified_policy_ref,
        resource_class_ref,
        verified_plan_ref,
        verified_assessment_ref,
        verified_decision_ref,
        verified_policy.authority_context,
        stop_point,
        exact_actor,
        reason,
        event_binding,
        work_started,
        observations,
        state,
        m.ResourcePolicyAuthorityMarker.RESOURCE_STOP_NOT_SCIENTIFIC_OUTCOME,
    )
    _plan_unchanged(verified_plan, before)
    return record


def _verify_stop_record(
    record: object,
    record_ref: object,
) -> tuple[m.ResourceCancellationRecord, ResourceCancellationRecordRef]:
    if type(record) is not m.ResourceCancellationRecord:
        raise _wrong("/ref")
    if type(record_ref) is not ResourceCancellationRecordRef:
        raise _wrong("/ref")
    payload = c.encode_resource_cancellation_record(record)
    verified = verify_resource_policy_ref(
        record_ref,
        canonical_bytes=payload,
        challenge_key=record.challenge_key,
    )
    assert type(verified) is ResourceCancellationRecordRef
    decoded = c.decode_resource_cancellation_record(payload, expected_ref=verified)
    return decoded, verified


def _metric_binding_quantity(
    value: m.ObservedMetricBinding,
) -> m.ObservedResourceQuantity | None:
    if type(value) is m.ObservedMetricObserved:
        return value.observed_quantity
    return None


def _check_receipt_metrics(
    *,
    resource_class: m.ResourceClass,
    consumption: tuple[m.ObservedResourceQuantity, ...],
    latency: m.ObservedMetricBinding,
    cost: m.ObservedMetricBinding,
) -> None:
    metrics = {
        metric.metric_id: metric for metric in resource_class.observation_metrics
    }
    quantities = (
        *consumption,
        *(
            (latency.observed_quantity,)
            if type(latency) is m.ObservedMetricObserved
            else ()
        ),
        *((cost.observed_quantity,) if type(cost) is m.ObservedMetricObserved else ()),
    )
    if len({item.metric_id for item in quantities}) != len(quantities):
        raise _invalid("/observation")
    for observed in quantities:
        metric = metrics.get(observed.metric_id)
        if (
            metric is None
            or metric.unit_ref != observed.unit_ref
            or metric.observation_role is not observed.observation_role
        ):
            raise _invalid("/observation")
    latency_metrics = tuple(
        item
        for item in resource_class.observation_metrics
        if item.observation_role is m.ResourceObservationRole.OBSERVED_LATENCY
    )
    cost_metrics = tuple(
        item
        for item in resource_class.observation_metrics
        if item.observation_role is m.ResourceObservationRole.RESOURCE_COST_NOT_PRICE
    )
    if type(latency) is m.ObservedMetricObserved and (
        latency.observed_quantity.metric_id != latency_metrics[0].metric_id
    ):
        raise _invalid("/observation")
    if type(cost) is m.ObservedMetricObserved and (
        cost.observed_quantity.metric_id != cost_metrics[0].metric_id
    ):
        raise _invalid("/observation")


def _check_stop_observations_preserved(
    record: m.ResourceCancellationRecord,
    *,
    consumption: tuple[m.ObservedResourceQuantity, ...],
    latency: m.ObservedMetricBinding,
    cost: m.ObservedMetricBinding,
) -> None:
    final_quantities = {item.metric_id: item for item in consumption}
    for binding in (latency, cost):
        item = _metric_binding_quantity(binding)
        if item is not None:
            final_quantities[item.metric_id] = item
    for earlier in record.observed_resource_quantities_so_far:
        final = final_quantities.get(earlier.metric_id)
        if (
            final is None
            or final.unit_ref != earlier.unit_ref
            or final.observation_role is not earlier.observation_role
            or final.quantity < earlier.quantity
        ):
            raise _invalid("/observation")


def make_observed_resource_receipt(
    *,
    plan: object,
    plan_ref: object,
    policy: object,
    policy_ref: object,
    class_bundle: object,
    selected_class: object,
    selected_class_ref: object,
    assessment: object,
    assessment_ref: object,
    decision: object,
    decision_ref: object,
    build_completion: object,
    frozen_artifact_reuse: object,
    reconstruction_replicate: object,
    observed_consumption_quantities: object,
    observed_latency: object,
    observed_cost: object,
    evidence_stage_label: object,
    stop_cause: object,
    work_started: object,
    stop_record: object | None = None,
    stop_record_ref: object | None = None,
    enforcement_result: object | None = None,
) -> tuple[m.ObservedResourceReceipt, ObservedResourceReceiptRef]:
    """Issue an immutable resource-facts receipt after all cross-law checks."""

    (
        verified_plan,
        verified_plan_ref,
        before,
        verified_policy,
        verified_policy_ref,
        verified_bundle,
        resource_class,
        resource_class_ref,
        _,
        verified_assessment,
        verified_assessment_ref,
    ) = _verify_core_outcome_inputs(
        plan=plan,
        plan_ref=plan_ref,
        policy=policy,
        policy_ref=policy_ref,
        class_bundle=class_bundle,
        selected_class=selected_class,
        selected_class_ref=selected_class_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
    )
    verified_decision, verified_decision_ref = _verify_decision_semantics(
        decision,
        decision_ref,
        plan=verified_plan,
        plan_ref=verified_plan_ref,
        assessment=verified_assessment,
        assessment_ref=verified_assessment_ref,
        policy=verified_policy,
        policy_ref=verified_policy_ref,
        class_bundle=verified_bundle,
        selected_class=resource_class,
        selected_class_ref=resource_class_ref,
        require_admissible=False,
    )
    if type(work_started) is not bool:
        raise _wrong("/type")
    if work_started and (
        verified_decision.outcome is not m.FixtureDecisionOutcome.FIXTURE_ADMISSIBLE
    ):
        raise _invalid("/fixture_decision_ref")
    if (
        type(observed_consumption_quantities) is not tuple
        or len(observed_consumption_quantities) > MAX_CANONICAL_TUPLE_ITEMS
    ):
        raise _wrong("/observation")
    consumption = tuple(
        (
            m.ObservedResourceQuantity(
                item.metric_id,
                item.unit_ref,
                item.quantity,
                item.observation_role,
            )
            if type(item) is m.ObservedResourceQuantity
            else (_ for _ in ()).throw(_wrong("/observation"))
        )
        for item in observed_consumption_quantities
    )
    if type(observed_latency) is m.ObservedMetricObserved:
        latency: m.ObservedMetricBinding = m.ObservedMetricObserved(
            observed_latency.observed_quantity
        )
    elif type(observed_latency) is m.ObservedMetricUnavailable:
        latency = m.ObservedMetricUnavailable(observed_latency.reason)
    else:
        raise _wrong("/observation")
    if type(observed_cost) is m.ObservedMetricObserved:
        cost: m.ObservedMetricBinding = m.ObservedMetricObserved(
            observed_cost.observed_quantity
        )
    elif type(observed_cost) is m.ObservedMetricUnavailable:
        cost = m.ObservedMetricUnavailable(observed_cost.reason)
    else:
        raise _wrong("/observation")
    _check_receipt_metrics(
        resource_class=resource_class,
        consumption=consumption,
        latency=latency,
        cost=cost,
    )
    if (stop_record is None) != (stop_record_ref is None):
        raise _wrong("/ref")
    if stop_record is None:
        verified_stop: m.ResourceCancellationRecord | None = None
        stop_binding: m.ResourceStopBinding = m.NoResourceStop()
    else:
        verified_stop, verified_stop_ref = _verify_stop_record(
            stop_record, stop_record_ref
        )
        if (
            verified_stop.policy_ref != verified_policy_ref
            or verified_stop.resource_class_ref != resource_class_ref
            or verified_stop.construction_plan_ref != verified_plan_ref
            or verified_stop.assessment_ref != verified_assessment_ref
            or verified_stop.fixture_decision_ref != verified_decision_ref
            or verified_stop.authority_context != verified_policy.authority_context
            or verified_stop.work_started is not work_started
        ):
            raise _invalid("/ref")
        _check_stop_observations_preserved(
            verified_stop,
            consumption=consumption,
            latency=latency,
            cost=cost,
        )
        stop_binding = verified_stop_ref
    if enforcement_result is None:
        verified_enforcement: m.ResourceEnforcementResult | None = None
        event_binding: m.EnforcementEventBinding = m.NoEnforcementEvent()
    else:
        verified_enforcement = _verify_enforcement_result_semantics(
            enforcement_result,
            plan=verified_plan,
            plan_ref=verified_plan_ref,
            policy=verified_policy,
            policy_ref=verified_policy_ref,
            class_bundle=verified_bundle,
            selected_class=resource_class,
            selected_class_ref=resource_class_ref,
            assessment=verified_assessment,
            assessment_ref=verified_assessment_ref,
            decision=verified_decision,
            decision_ref=verified_decision_ref,
        )
        event_binding = verified_enforcement.event
    if type(stop_cause) is not m.ResourceStopCause:
        raise _wrong("/type")
    if verified_stop is None:
        if stop_cause not in (
            m.ResourceStopCause.COMPLETED_RESOURCE_ACCOUNTING,
            m.ResourceStopCause.EVIDENCE_DEFERRED,
        ):
            raise _invalid("/type")
        if (
            stop_cause is m.ResourceStopCause.EVIDENCE_DEFERRED
            and verified_decision.outcome
            is not m.FixtureDecisionOutcome.EVIDENCE_DEFERRED
        ):
            raise _invalid("/fixture_decision_ref")
    else:
        expected_record_law = {
            m.ResourceStopCause.POLICY_LIMIT_REACHED: (
                m.PolicyEnforcerActor,
                m.CancellationReason.POLICY_LIMIT_REACHED,
            ),
            m.ResourceStopCause.CANCELLED: (
                m.FixtureRequesterActor,
                m.CancellationReason.REQUESTER_CANCELLED,
            ),
            m.ResourceStopCause.ENFORCEMENT_FAILURE: (
                m.PolicyEnforcerActor,
                m.CancellationReason.ENFORCEMENT_FAILURE,
            ),
            m.ResourceStopCause.INFRASTRUCTURE_FAILURE: (
                m.InfrastructureActor,
                m.CancellationReason.INFRASTRUCTURE_FAILURE,
            ),
        }
        if stop_cause is m.ResourceStopCause.EVIDENCE_DEFERRED:
            valid_record = (
                verified_stop.reason in _WITHDRAWAL_REQUIREMENT_FIELDS
                and verified_stop.resulting_state
                is m.CancellationResultingState.EVIDENCE_DEFERRED
            )
        elif stop_cause in expected_record_law:
            actor_type, expected_reason = expected_record_law[stop_cause]
            valid_record = (
                type(verified_stop.actor) is actor_type
                and verified_stop.reason is expected_reason
            )
        else:
            valid_record = False
        if not valid_record:
            raise _invalid("/type")
    stop_event = (
        verified_stop.enforcement_event_binding
        if verified_stop is not None
        and type(verified_stop.enforcement_event_binding) is m.ResourceEnforcementEvent
        else None
    )
    if stop_event is None:
        if verified_enforcement is not None:
            raise _invalid("/enforcement")
    elif verified_enforcement is None or verified_enforcement.event != stop_event:
        raise _invalid("/enforcement")
    if verified_stop is not None:
        recomputed_stop = make_cancellation_record(
            plan=verified_plan,
            plan_ref=verified_plan_ref,
            policy=verified_policy,
            policy_ref=verified_policy_ref,
            class_bundle=verified_bundle,
            selected_class=resource_class,
            selected_class_ref=resource_class_ref,
            assessment=verified_assessment,
            assessment_ref=verified_assessment_ref,
            decision=verified_decision,
            decision_ref=verified_decision_ref,
            actor=verified_stop.actor,
            reason=verified_stop.reason,
            stop_point=verified_stop.stop_point,
            work_started=verified_stop.work_started,
            observed_resource_quantities_so_far=(
                verified_stop.observed_resource_quantities_so_far
            ),
            enforcement_result=verified_enforcement,
        )
        if recomputed_stop != verified_stop:
            raise _invalid("/ref")
    build_identity = (
        build_completion.build_identity
        if type(build_completion) in (m.IncompleteBuild, m.CompleteBuild)
        else None
    )
    if build_identity is not None and (
        build_identity.execution_environment_pin
        != resource_class.execution_environment_pin
    ):
        raise _invalid("/resource_class")
    receipt = m.ObservedResourceReceipt(
        m.ObservedResourceReceipt.OBJECT_KIND,
        c.RESOURCE_POLICY_SCHEMA_VERSION,
        c.RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        verified_policy.challenge_key,
        verified_policy_ref,
        resource_class_ref,
        verified_plan_ref,
        verified_assessment_ref,
        verified_decision_ref,
        verified_policy.authority_context,
        build_completion,
        frozen_artifact_reuse,
        reconstruction_replicate,
        consumption,
        latency,
        cost,
        evidence_stage_label,
        stop_cause,
        stop_binding,
        event_binding,
        work_started,
        m.ResourceEpistemicLayer.OBSERVED_RESOURCE_RECEIPT,
        m.ResourcePolicyAuthorityMarker.RESOURCE_FACTS_ONLY_NOT_EVIDENCE_OR_PRICE,
    )
    _plan_unchanged(verified_plan, before)
    receipt_ref = c._observed_resource_receipt_to_ref(receipt)
    return receipt, receipt_ref


def validate_observed_resource_receipt(
    receipt: object,
    receipt_ref: object,
    *,
    plan: object,
    plan_ref: object,
    policy: object,
    policy_ref: object,
    class_bundle: object,
    selected_class: object,
    selected_class_ref: object,
    assessment: object,
    assessment_ref: object,
    decision: object,
    decision_ref: object,
    stop_record: object | None = None,
    stop_record_ref: object | None = None,
    enforcement_result: object | None = None,
) -> tuple[m.ObservedResourceReceipt, ObservedResourceReceiptRef]:
    """Semantically reconstruct and verify one terminal receipt/ref pair."""

    if type(receipt) is not m.ObservedResourceReceipt:
        raise _wrong("/ref")
    if type(receipt_ref) is not ObservedResourceReceiptRef:
        raise _wrong("/ref")
    rebuilt_receipt, rebuilt_ref = make_observed_resource_receipt(
        plan=plan,
        plan_ref=plan_ref,
        policy=policy,
        policy_ref=policy_ref,
        class_bundle=class_bundle,
        selected_class=selected_class,
        selected_class_ref=selected_class_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
        decision=decision,
        decision_ref=decision_ref,
        build_completion=receipt.build_completion,
        frozen_artifact_reuse=receipt.frozen_artifact_reuse,
        reconstruction_replicate=receipt.reconstruction_replicate,
        observed_consumption_quantities=receipt.observed_consumption_quantities,
        observed_latency=receipt.observed_latency,
        observed_cost=receipt.observed_cost,
        evidence_stage_label=receipt.evidence_stage_label,
        stop_cause=receipt.stop_cause,
        work_started=receipt.work_started,
        stop_record=stop_record,
        stop_record_ref=stop_record_ref,
        enforcement_result=enforcement_result,
    )
    if rebuilt_receipt != receipt:
        raise _invalid("/ref")
    if rebuilt_ref != receipt_ref:
        raise ResourcePolicyInputRejected(
            ResourcePolicyInputCode.REF_DIGEST_MISMATCH,
            path="/ref",
        )
    return rebuilt_receipt, rebuilt_ref


__all__ = [
    "ClassBundle",
    "assess_static_resources",
    "decide_fixture_readiness",
    "evaluate_enforcement",
    "make_cancellation_record",
    "make_observed_resource_receipt",
    "validate_observed_resource_receipt",
    "validate_research_resource_policy_bundle",
    "validate_resource_class",
]
