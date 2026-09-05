from __future__ import annotations

from dataclasses import replace

import pytest

from carbon import measurement
from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.construction import EnvironmentPin, ResolvedConstructionPlanRef
from carbon.registry import ChallengeKey
from carbon.resource_policy import (
    BoundReconstructionReplicate,
    CompleteBuild,
    CompleteBuildIdentity,
    FrozenArtifactReuseWindow,
    IncompleteBuild,
    IncompleteBuildIdentity,
    NoBuildStarted,
    NoReuse,
    ObservedResourceReceiptRef,
    ReconstructionReplicateIdentity,
    ReplicateNotApplicable,
    ReplicateNotApplicableReason,
    ResearchResourcePolicyRef,
    ResourceClassRef,
    ResourceStopCause,
    StaticResourceAssessmentRef,
)

_DIGEST_A = "sha256:" + "a" * 64
_DIGEST_B = "sha256:" + "b" * 64
_KEY = ChallengeKey("fixture-burgers", "1.0")

_COMPONENTS = {
    "complete_base_minimum_binding": (
        measurement.MeasurementDefinitionKind.COMPLETE_BASE_MINIMUM
    ),
    "build_completeness_criteria_binding": (
        measurement.MeasurementDefinitionKind.BUILD_COMPLETENESS_CRITERIA
    ),
    "frozen_artifact_reuse_policy_binding": (
        measurement.MeasurementDefinitionKind.FROZEN_ARTIFACT_REUSE_POLICY
    ),
    "nomination_criteria_binding": (
        measurement.MeasurementDefinitionKind.NOMINATION_CRITERIA
    ),
    "promotion_criteria_binding": (
        measurement.MeasurementDefinitionKind.PROMOTION_CRITERIA
    ),
    "case_coverage_requirement_binding": (
        measurement.MeasurementDefinitionKind.CASE_COVERAGE_REQUIREMENT
    ),
    "stratum_coverage_requirement_binding": (
        measurement.MeasurementDefinitionKind.STRATUM_COVERAGE_REQUIREMENT
    ),
    "evidence_extension_rule_binding": (
        measurement.MeasurementDefinitionKind.EVIDENCE_EXTENSION_RULE
    ),
    "scientific_stopping_rule_binding": (
        measurement.MeasurementDefinitionKind.STOPPING_RULE
    ),
    "stability_audit_rate_binding": (
        measurement.MeasurementDefinitionKind.STABILITY_AUDIT_RATE
    ),
    "audit_selection_policy_binding": (
        measurement.MeasurementDefinitionKind.AUDIT_SELECTION_POLICY
    ),
    "error_control_binding": (
        measurement.MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL
    ),
    "power_requirement_binding": measurement.MeasurementDefinitionKind.POWER_REQUIREMENT,
    "minimum_resolvable_improvement_binding": (
        measurement.MeasurementDefinitionKind.MINIMUM_RESOLVABLE_IMPROVEMENT
    ),
    "sequential_stopping_rule_binding": (
        measurement.MeasurementDefinitionKind.SEQUENTIAL_STOPPING_RULE
    ),
}


def definition(
    kind: measurement.MeasurementDefinitionKind,
    object_id: str,
    *,
    challenge: ChallengeKey = _KEY,
    digest: str = _DIGEST_A,
) -> measurement.MeasurementDefinitionRef:
    return measurement.MeasurementDefinitionRef(
        challenge, kind, object_id, "1.0", digest
    )


def component(
    kind: measurement.MeasurementDefinitionKind,
    *,
    bound: bool,
) -> measurement.UncertaintyComponentBinding:
    if not bound:
        return measurement.UncertaintyComponentBinding(
            measurement.ScientificValueState.HUMAN_INPUT
        )
    return measurement.UncertaintyComponentBinding(
        measurement.ScientificValueState.BOUND,
        definition(kind, f"fixture-{kind.value.casefold().replace('_', '-')}"),
    )


def policy(*, bound: bool = False) -> measurement.ReconstructionEvidencePolicy:
    return measurement.ReconstructionEvidencePolicy(
        challenge_key=_KEY,
        policy_id="fixture-reconstruction-evidence",
        policy_version="1.0",
        construction_family_ref=definition(
            measurement.MeasurementDefinitionKind.CONSTRUCTION_FAMILY,
            "fixture-family",
        ),
        **{name: component(kind, bound=bound) for name, kind in _COMPONENTS.items()},
        fixture_origin=True,
    )


def _resource_identity(*, complete: bool = True, challenge: ChallengeKey = _KEY):
    plan_ref = ResolvedConstructionPlanRef(
        challenge_key=challenge, content_digest=_DIGEST_A
    )
    policy_ref = ResearchResourcePolicyRef(
        challenge_key=challenge,
        object_id="fixture-resource-policy",
        object_version="1.0",
        content_digest=_DIGEST_A,
    )
    class_ref = ResourceClassRef(
        challenge_key=challenge,
        object_id="fixture-resource-class",
        object_version="1.0",
        content_digest=_DIGEST_A,
    )
    environment = EnvironmentPin("fixture-environment", "1.0", _DIGEST_A)
    identity_type = CompleteBuildIdentity if complete else IncompleteBuildIdentity
    return identity_type(
        challenge,
        plan_ref,
        policy_ref,
        class_ref,
        environment,
        "fixture-build",
        _DIGEST_A,
    )


def resource_facts(
    *,
    build: object | None = None,
    replicate: object | None = None,
    reuse: object | None = None,
    stop: ResourceStopCause = ResourceStopCause.COMPLETED_RESOURCE_ACCOUNTING,
    receipt: ObservedResourceReceiptRef | None = None,
) -> measurement.ReconstructionResourceFacts:
    return measurement.ReconstructionResourceFacts(
        build if build is not None else CompleteBuild(_resource_identity()),
        reuse if reuse is not None else NoReuse(),
        (
            replicate
            if replicate is not None
            else ReplicateNotApplicable(
                ReplicateNotApplicableReason.NOT_A_RECONSTRUCTION_REPLICATE
            )
        ),
        stop,
        None,
        None,
        receipt,
    )


def stage_ref(
    kind: measurement.MeasurementDefinitionKind,
) -> measurement.MeasurementDefinitionRef:
    return definition(kind, f"fixture-{kind.value.casefold().replace('_', '-')}")


def evidence_input(
    value: measurement.ReconstructionEvidencePolicy,
    *,
    facts: measurement.ReconstructionResourceFacts | None = None,
    base: bool = False,
    nominated: bool = False,
    extended: bool = False,
    promoted: bool = False,
    remaining_requirement_count: int = 1,
    stop_kind: measurement.ReconstructionStopKind = measurement.ReconstructionStopKind.NONE,
    family_ref: measurement.MeasurementDefinitionRef | None = None,
) -> measurement.ReconstructionEvidenceInput:
    return measurement.ReconstructionEvidenceInput(
        measurement.measurement_ref(value),
        family_ref or value.construction_family_ref,
        facts or resource_facts(),
        (
            stage_ref(measurement.MeasurementDefinitionKind.COMPLETE_BASE_EVIDENCE)
            if base
            else None
        ),
        (
            stage_ref(measurement.MeasurementDefinitionKind.NOMINATION_EVIDENCE)
            if nominated
            else None
        ),
        (
            stage_ref(measurement.MeasurementDefinitionKind.EXTENSION_EVIDENCE)
            if extended
            else None
        ),
        (
            stage_ref(measurement.MeasurementDefinitionKind.PROMOTION_EVIDENCE)
            if promoted
            else None
        ),
        tuple(
            definition(
                measurement.MeasurementDefinitionKind.REMAINING_EVIDENCE_REQUIREMENT,
                f"fixture-remaining-requirement-{index}",
            )
            for index in range(remaining_requirement_count)
        ),
        stop_kind,
        (
            stage_ref(
                measurement.MeasurementDefinitionKind.RECONSTRUCTION_EXECUTION_FAILURE
            )
            if stop_kind
            is measurement.ReconstructionStopKind.RECONSTRUCTION_EXECUTION_FAILURE
            else None
        ),
    )


def test_policy_is_challenge_family_bound_canonical_and_content_addressed() -> None:
    value = policy()
    source = measurement.canonical_bytes(value)
    loaded = measurement.load_canonical_document(source)

    assert loaded == value
    assert measurement.canonical_bytes(loaded) == source
    assert measurement.measurement_ref(
        value
    ) == measurement.ReconstructionEvidencePolicyRef(
        _KEY, measurement.canonical_digest(value)
    )
    assert len(source) == 1903
    assert measurement.canonical_digest(value) == (
        "sha256:fa84699b2ee533c6d56f017da37744d37c8f3457d7b4bdaeb1bf247bfd2a599b"
    )


def test_human_owned_values_are_explicit_and_have_no_numeric_defaults() -> None:
    value = policy()
    assert not value.has_complete_human_authority
    for name in _COMPONENTS:
        binding = getattr(value, name)
        assert binding.state is measurement.ScientificValueState.HUMAN_INPUT
        assert binding.component_ref is None
        assert not isinstance(binding, (int, float))

    status = measurement.assess_reconstruction_evidence(
        value, evidence_input(value, base=True)
    )
    assert status.outcome is measurement.ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED


@pytest.mark.parametrize(
    "field_name",
    (
        "stability_audit_rate_binding",
        "scientific_stopping_rule_binding",
        "error_control_binding",
    ),
)
def test_missing_stability_stopping_or_error_authority_fails_closed(field_name) -> None:
    value = policy(bound=True)
    value = replace(
        value,
        **{
            field_name: measurement.UncertaintyComponentBinding(
                measurement.ScientificValueState.BLOCKED_FOR_LIVE_UNTIL_SET
            )
        },
    )
    status = measurement.assess_reconstruction_evidence(
        value, evidence_input(value, base=True)
    )
    assert status.outcome is measurement.ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED


def test_complete_base_nomination_extension_and_promotion_are_distinct() -> None:
    value = policy(bound=True)
    base = measurement.assess_reconstruction_evidence(
        value, evidence_input(value, base=True)
    )
    nominated = measurement.assess_reconstruction_evidence(
        value, evidence_input(value, base=True, nominated=True)
    )

    replicate_identity = ReconstructionReplicateIdentity(
        _KEY,
        _resource_identity().construction_plan_ref,
        _resource_identity().policy_ref,
        _resource_identity().resource_class_ref,
        "fixture-replicate",
        _DIGEST_B,
    )
    promoted = measurement.assess_reconstruction_evidence(
        value,
        evidence_input(
            value,
            facts=resource_facts(
                replicate=BoundReconstructionReplicate(replicate_identity)
            ),
            base=True,
            nominated=True,
            extended=True,
            promoted=True,
            remaining_requirement_count=0,
        ),
    )

    assert base.stage is measurement.ReconstructionEvidenceStage.BASE_COMPLETE
    assert nominated.stage is measurement.ReconstructionEvidenceStage.NOMINATED
    assert promoted.stage is measurement.ReconstructionEvidenceStage.PROMOTION_ELIGIBLE
    assert (
        promoted.outcome is measurement.ReconstructionEvidenceOutcome.STAGE_ESTABLISHED
    )
    assert promoted.remaining_requirement_refs == ()
    assert nominated.stage is not promoted.stage


@pytest.mark.parametrize("remaining_requirement_count", (1, 2))
def test_remaining_requirements_prevent_promotion_readiness(
    remaining_requirement_count,
) -> None:
    value = policy(bound=True)
    replicate_identity = ReconstructionReplicateIdentity(
        _KEY,
        _resource_identity().construction_plan_ref,
        _resource_identity().policy_ref,
        _resource_identity().resource_class_ref,
        "fixture-deferred-promotion-replicate",
        _DIGEST_B,
    )
    evidence = evidence_input(
        value,
        facts=resource_facts(
            replicate=BoundReconstructionReplicate(replicate_identity)
        ),
        base=True,
        nominated=True,
        extended=True,
        promoted=True,
        remaining_requirement_count=remaining_requirement_count,
    )

    status = measurement.assess_reconstruction_evidence(value, evidence)

    assert status.stage is measurement.ReconstructionEvidenceStage.EXTENDED
    assert status.outcome is measurement.ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED
    assert status.remaining_requirement_refs == evidence.remaining_requirement_refs


@pytest.mark.parametrize(
    ("evidence_changes", "expected_stage"),
    (
        ({"base": True}, measurement.ReconstructionEvidenceStage.BASE_COMPLETE),
        (
            {"base": True, "nominated": True},
            measurement.ReconstructionEvidenceStage.NOMINATED,
        ),
        (
            {"base": True, "nominated": True, "extended": True},
            measurement.ReconstructionEvidenceStage.EXTENDED,
        ),
    ),
)
def test_remaining_requirements_defer_without_erasing_established_stage(
    evidence_changes,
    expected_stage,
) -> None:
    value = policy(bound=True)
    facts = None
    if evidence_changes.get("extended"):
        build_identity = _resource_identity()
        facts = resource_facts(
            replicate=BoundReconstructionReplicate(
                ReconstructionReplicateIdentity(
                    _KEY,
                    build_identity.construction_plan_ref,
                    build_identity.policy_ref,
                    build_identity.resource_class_ref,
                    "fixture-stage-replicate",
                    _DIGEST_B,
                )
            )
        )
    evidence = evidence_input(value, facts=facts, **evidence_changes)

    status = measurement.assess_reconstruction_evidence(value, evidence)

    assert status.stage is expected_stage
    assert status.outcome is measurement.ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED
    assert status.remaining_requirement_refs == evidence.remaining_requirement_refs


def test_extension_is_only_established_by_a_bound_reconstruction_replicate() -> None:
    value = policy(bound=True)
    without_replicate = measurement.assess_reconstruction_evidence(
        value,
        evidence_input(value, base=True, nominated=True, extended=True),
    )
    replicate_identity = ReconstructionReplicateIdentity(
        _KEY,
        _resource_identity().construction_plan_ref,
        _resource_identity().policy_ref,
        _resource_identity().resource_class_ref,
        "fixture-promotion-replicate",
        _DIGEST_B,
    )
    with_replicate = measurement.assess_reconstruction_evidence(
        value,
        evidence_input(
            value,
            facts=resource_facts(
                replicate=BoundReconstructionReplicate(replicate_identity)
            ),
            base=True,
            nominated=True,
            extended=True,
        ),
    )

    assert without_replicate.stage is measurement.ReconstructionEvidenceStage.NOMINATED
    assert with_replicate.stage is measurement.ReconstructionEvidenceStage.EXTENDED
    assert (
        with_replicate.stage
        is not measurement.ReconstructionEvidenceStage.PROMOTION_ELIGIBLE
    )


@pytest.mark.parametrize(
    "mismatched_field",
    ("construction_plan_ref", "policy_ref", "resource_class_ref"),
)
def test_bound_replicate_must_match_complete_build_construction_identity(
    mismatched_field,
) -> None:
    build_identity = _resource_identity()
    identity_values = {
        "construction_plan_ref": build_identity.construction_plan_ref,
        "policy_ref": build_identity.policy_ref,
        "resource_class_ref": build_identity.resource_class_ref,
    }
    replacements = {
        "construction_plan_ref": replace(
            build_identity.construction_plan_ref, content_digest=_DIGEST_B
        ),
        "policy_ref": replace(build_identity.policy_ref, content_digest=_DIGEST_B),
        "resource_class_ref": replace(
            build_identity.resource_class_ref, content_digest=_DIGEST_B
        ),
    }
    identity_values[mismatched_field] = replacements[mismatched_field]
    replicate = BoundReconstructionReplicate(
        ReconstructionReplicateIdentity(
            _KEY,
            identity_values["construction_plan_ref"],
            identity_values["policy_ref"],
            identity_values["resource_class_ref"],
            "fixture-foreign-replicate",
            _DIGEST_B,
        )
    )

    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        resource_facts(build=CompleteBuild(build_identity), replicate=replicate)
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION
    assert exc_info.value.path.endswith(mismatched_field)


def test_frozen_reuse_is_explicit_and_does_not_require_one_build_per_case() -> None:
    value = policy(bound=True)
    build = CompleteBuild(_resource_identity())
    reuse = FrozenArtifactReuseWindow(
        "fixture-reuse-window",
        build.build_identity,
        owner_ref(
            "restriction",
            scope_binding=ChallengeScope(_KEY),
            object_id="fixture-reuse-policy",
            object_version="1.0",
            content_digest=_DIGEST_A,
        ),
        3,
        2,
    )
    facts = resource_facts(build=build, reuse=reuse)

    deferred = measurement.assess_reconstruction_evidence(
        value, evidence_input(value, facts=facts)
    )
    complete = measurement.assess_reconstruction_evidence(
        value, evidence_input(value, facts=facts, base=True)
    )
    assert (
        deferred.outcome is measurement.ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED
    )
    assert complete.stage is measurement.ReconstructionEvidenceStage.BASE_COMPLETE


def test_partial_build_and_resource_refs_cannot_satisfy_complete_base() -> None:
    value = policy(bound=True)
    partial = IncompleteBuild(_resource_identity(complete=False))
    receipt = ObservedResourceReceiptRef(_KEY, content_digest=_DIGEST_A)
    facts = resource_facts(build=partial, receipt=receipt)
    status = measurement.assess_reconstruction_evidence(
        value, evidence_input(value, facts=facts, base=True)
    )
    assert status.stage is measurement.ReconstructionEvidenceStage.BASE_REQUIRED
    assert status.outcome is measurement.ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED

    resource_only = measurement.ReconstructionResourceFacts(
        NoBuildStarted(),
        NoReuse(),
        ReplicateNotApplicable(ReplicateNotApplicableReason.NO_WORK_STARTED),
        ResourceStopCause.EVIDENCE_DEFERRED,
        StaticResourceAssessmentRef(_KEY, content_digest=_DIGEST_A),
        None,
        receipt,
    )
    status = measurement.assess_reconstruction_evidence(
        value, evidence_input(value, facts=resource_only)
    )
    assert status.stage is measurement.ReconstructionEvidenceStage.BASE_REQUIRED
    assert status.outcome is measurement.ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED


def test_heuristic_or_resource_screen_defers_without_erasing_complete_base() -> None:
    value = policy(bound=True)
    heuristic = measurement.assess_reconstruction_evidence(
        value,
        evidence_input(
            value,
            base=True,
            stop_kind=measurement.ReconstructionStopKind.HEURISTIC_FUTILITY,
        ),
    )
    resource_screen = measurement.assess_reconstruction_evidence(
        value,
        evidence_input(
            value,
            base=True,
            facts=resource_facts(stop=ResourceStopCause.POLICY_LIMIT_REACHED),
        ),
    )
    for status in (heuristic, resource_screen):
        assert status.stage is measurement.ReconstructionEvidenceStage.BASE_COMPLETE
        assert (
            status.outcome
            is measurement.ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED
        )
        assert "NOT_SUPERIOR" not in status.outcome.value


def test_cross_challenge_wrong_family_and_wrong_role_reject() -> None:
    value = policy(bound=True)
    wrong_family = definition(
        measurement.MeasurementDefinitionKind.CONSTRUCTION_FAMILY,
        "another-family",
        digest=_DIGEST_B,
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        measurement.assess_reconstruction_evidence(
            value, evidence_input(value, base=True, family_ref=wrong_family)
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION

    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            value,
            construction_family_ref=definition(
                measurement.MeasurementDefinitionKind.STRATUM, "wrong-role"
            ),
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION

    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            value,
            complete_base_minimum_binding=measurement.UncertaintyComponentBinding(
                measurement.ScientificValueState.BOUND,
                definition(measurement.MeasurementDefinitionKind.UNIT, "wrong-minimum"),
            ),
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION

    other = ChallengeKey("other-fixture", "1.0")
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        evidence_input(
            value,
            facts=resource_facts(
                build=CompleteBuild(_resource_identity(challenge=other))
            ),
            base=True,
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.CROSS_CHALLENGE


def test_execution_and_infrastructure_failures_are_not_scientific_insufficiency() -> (
    None
):
    value = policy(bound=True)
    infrastructure = measurement.assess_reconstruction_evidence(
        value,
        evidence_input(
            value,
            facts=resource_facts(stop=ResourceStopCause.INFRASTRUCTURE_FAILURE),
        ),
    )
    reconstruction = measurement.assess_reconstruction_evidence(
        value,
        evidence_input(
            value,
            stop_kind=measurement.ReconstructionStopKind.RECONSTRUCTION_EXECUTION_FAILURE,
        ),
    )
    insufficient = measurement.assess_reconstruction_evidence(
        value,
        evidence_input(
            value,
            base=True,
            stop_kind=measurement.ReconstructionStopKind.SCIENTIFIC_EVIDENCE_EXHAUSTED,
        ),
    )
    pre_base_exhaustion = measurement.assess_reconstruction_evidence(
        value,
        evidence_input(
            value,
            stop_kind=measurement.ReconstructionStopKind.SCIENTIFIC_EVIDENCE_EXHAUSTED,
        ),
    )
    assert (
        infrastructure.outcome
        is measurement.ReconstructionEvidenceOutcome.INFRASTRUCTURE_FAILURE
    )
    assert (
        reconstruction.outcome
        is measurement.ReconstructionEvidenceOutcome.RECONSTRUCTION_FAILURE
    )
    assert (
        insufficient.outcome
        is measurement.ReconstructionEvidenceOutcome.INDETERMINATE_INSUFFICIENT_EVIDENCE
    )
    assert (
        pre_base_exhaustion.outcome
        is measurement.ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED
    )
    assert (
        len({infrastructure.outcome, reconstruction.outcome, insufficient.outcome}) == 3
    )


def test_fixture_store_round_trip_preserves_policy_pin() -> None:
    value = policy()
    store = measurement.MeasurementFixtureStore()
    ref = store.put(value)
    assert type(ref) is measurement.ReconstructionEvidencePolicyRef
    assert store.get(ref) == value
