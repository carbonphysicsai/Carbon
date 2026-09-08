"""B-E4 execution-readiness evidence stays deterministic and fail closed."""

from __future__ import annotations

import hashlib
import pickle
from dataclasses import fields, replace

import pytest

from carbon.gauntlet.design import (
    PROTECTED_TARGETS,
    DesignAnalysisClassification,
    IntervalBound,
    LeakageTargetBound,
    classify_leakage_boundary,
)
from carbon.gauntlet.harness import AgentSession
from carbon.gauntlet.model import (
    AgentProfile,
    EngineeringObservation,
    ExperimentalArm,
    GauntletPreregistration,
    IntegrityCase,
    OwnerRatification,
    RatifyingOwner,
    RunIdentity,
)
from carbon.gauntlet.readiness import (
    RATIFICATION_TRUST_SEAMS,
    READINESS_AUTHORITY_CEILING,
    AttackAttemptReceipt,
    AttackAttemptReceiptRef,
    AttackCampaignRegistration,
    AttackEvidenceKind,
    AttackEvidenceRef,
    AttackEvidenceStore,
    AttackExecutionBinding,
    AttackProcedureRef,
    AttackReceiptStatus,
    AttackTerminalState,
    BlockReplacement,
    ExecutionArtifactKind,
    ExecutionArtifactPin,
    ExecutionEvidenceDraft,
    RatificationUnavailableError,
    ReadinessError,
    ShadowCampaignEstimate,
    ShadowCampaignRegistration,
    ShadowFoldObservation,
    ShadowTargetDefinition,
    SignedLambdaEstimate,
    SignedLambdaState,
    audit_ratification_readiness,
    build_qualifying_execution_evidence,
    clip_and_renormalize_probabilities,
    estimate_shadow_campaign,
    estimate_signed_lambda,
    require_verified_ratification,
    shadow_fold_index,
)
from carbon.qualification.errors import DossierInputCode
from carbon.registry import ChallengeKey
from carbon.research.errors import ResearchServiceErrorCode
from carbon.research.refs import PriorChannel, PriorPackRef
from carbon.research.refs import (
    TestOnlyPriorAuthorizationReceiptRef as PriorAuthorizationRef,
)

DIGEST = "sha256:" + "a" * 64
SECOND_DIGEST = "sha256:" + "b" * 64
KEY = ChallengeKey("be4_readiness_fixture", "1.0")
PACK_REF = PriorPackRef(KEY, PriorChannel.TEST_ONLY_FIXTURE, 1, DIGEST)
AUTH_REF = PriorAuthorizationRef(KEY, "be4_readiness_auth", SECOND_DIGEST)


def _targets() -> tuple[ShadowTargetDefinition, ...]:
    return tuple(
        ShadowTargetDefinition(target, f"{target.lower()}/v1", ("ABSENT", "PRESENT"))
        for target in PROTECTED_TARGETS
    )


def _shadow_registration() -> ShadowCampaignRegistration:
    return ShadowCampaignRegistration(
        KEY,
        DIGEST,
        "be4_shadow_campaign",
        "1.0",
        SECOND_DIGEST,
        DIGEST,
        SECOND_DIGEST,
        DIGEST,
        _targets(),
    )


def _cluster_digest(index: int) -> str:
    return "sha256:" + hashlib.sha256(f"cluster-{index}".encode()).hexdigest()


def _one_cluster_per_fold(
    registration: ShadowCampaignRegistration,
) -> tuple[tuple[str, int], ...]:
    found: dict[int, str] = {}
    for index in range(10_000):
        digest = _cluster_digest(index)
        fold = shadow_fold_index(
            registration,
            profile=AgentProfile.PLANNER,
            transcript_cluster_digest=digest,
        )
        found.setdefault(fold, digest)
        if len(found) == registration.fold_count:
            break
    assert len(found) == registration.fold_count
    return tuple((found[fold], fold) for fold in range(registration.fold_count))


def _shadow_observations(
    registration: ShadowCampaignRegistration,
) -> tuple[ShadowFoldObservation, ...]:
    clusters = _one_cluster_per_fold(registration)
    return tuple(
        ShadowFoldObservation(
            target,
            AgentProfile.PLANNER,
            digest,
            fold,
            registration.fold_count - 1,
            1,
            (0.5, 0.5),
            (0.4, 0.6),
        )
        for target in PROTECTED_TARGETS
        for digest, fold in clusters
    )


def _attack_campaign() -> AttackCampaignRegistration:
    return AttackCampaignRegistration(
        KEY,
        DIGEST,
        "be4_attack_campaign",
        "1.0",
        tuple(
            AttackProcedureRef(case, f"procedure_{case.value.lower()}", "1.0", DIGEST)
            for case in IntegrityCase
        ),
    )


def test_campaign_registrations_reconstruct_nested_identity_values() -> None:
    targets = list(_targets())
    object.__setattr__(targets[0], "class_labels", ())
    with pytest.raises(ReadinessError, match="shadow target definition is invalid"):
        ShadowCampaignRegistration(
            KEY,
            DIGEST,
            "be4_shadow_campaign",
            "1.0",
            SECOND_DIGEST,
            DIGEST,
            SECOND_DIGEST,
            DIGEST,
            tuple(targets),
        )

    procedures = list(_attack_campaign().procedures)
    object.__setattr__(procedures[0], "content_digest", "BROKEN")
    with pytest.raises(ReadinessError, match="attack procedure identity is invalid"):
        AttackCampaignRegistration(
            KEY,
            DIGEST,
            "be4_attack_campaign",
            "1.0",
            tuple(procedures),
        )


def _evidence_refs() -> tuple[AttackEvidenceRef, ...]:
    return (
        AttackEvidenceRef(AttackEvidenceKind.PROVENANCE, DIGEST),
        AttackEvidenceRef(AttackEvidenceKind.EVALUATOR_DECISION_INPUT, SECOND_DIGEST),
        AttackEvidenceRef(AttackEvidenceKind.SHADOW, DIGEST),
    )


def _record_attack(
    store: AttackEvidenceStore,
    campaign: AttackCampaignRegistration,
    *,
    attempt_id: str,
    case: IntegrityCase,
    protocol_outcomes: tuple[object, ...],
    transcript_digest: str = DIGEST,
):
    return store.record_attempt(
        campaign_ref=campaign.to_ref(),
        attempt_id=attempt_id,
        case=case,
        execution_binding=AttackExecutionBinding(
            KEY, DIGEST, None, None, "dedicated_fixture_attack_campaign"
        ),
        protocol_outcomes=protocol_outcomes,  # type: ignore[arg-type]
        transcript_digest=transcript_digest,
        evidence_refs=_evidence_refs(),
        evaluator_inputs_digest=SECOND_DIGEST,
        provenance_digest=DIGEST,
        terminal_state=AttackTerminalState.COMPLETED,
    )


def _observation(run: RunIdentity) -> EngineeringObservation:
    return EngineeringObservation(
        run,
        1.0,
        2.0,
        3.0,
        1,
        0.25,
        0.5,
        True,
        0,
        1,
        ("fixture_family",),
        DIGEST,
    )


def _runs(*, replicates: tuple[int, ...] = (0,)) -> tuple[RunIdentity, ...]:
    return tuple(
        RunIdentity(
            profile,
            arm,
            replicate,
            PACK_REF if arm is ExperimentalArm.V2_TEST_ONLY_PRIOR else None,
            AUTH_REF if arm is ExperimentalArm.V2_TEST_ONLY_PRIOR else None,
        )
        for replicate in replicates
        for profile in AgentProfile
        for arm in ExperimentalArm
    )


def _attack_refs(
    campaign: AttackCampaignRegistration,
) -> tuple[AttackAttemptReceiptRef, ...]:
    return tuple(
        # These public refs are intentionally assertion-only inputs to a carrier
        # whose trust and qualification properties are both false.
        AttackAttemptReceiptRef(
            campaign.to_ref(), f"fixture_{case.value.lower()}", case, DIGEST
        )
        for case in IntegrityCase
    )


def _draft(
    campaign: AttackCampaignRegistration,
    shadow: ShadowCampaignRegistration,
) -> ExecutionEvidenceDraft:
    runs = _runs()
    shadow_estimate = estimate_shadow_campaign(shadow, _shadow_observations(shadow))
    return ExecutionEvidenceDraft(
        KEY,
        DIGEST,
        runs,
        tuple(
            ExecutionArtifactPin(kind, f"{kind.value.lower()}_fixture", "1.0", DIGEST)
            for kind in ExecutionArtifactKind
        ),
        tuple(_observation(run) for run in runs),
        (),
        campaign.to_ref(),
        _attack_refs(campaign),
        shadow.to_ref(),
        shadow_estimate.to_ref(),
        "be4_fixture_analysis/v1",
        20260908,
        DesignAnalysisClassification.PASS_CONDITION,
        DesignAnalysisClassification.INDETERMINATE_CONDITION,
        DesignAnalysisClassification.FAIL_CONDITION,
    )


def _declared_preregistration() -> GauntletPreregistration:
    draft = GauntletPreregistration(
        None,
        "profiles",
        "budgets",
        "estimand",
        "effect-floor",
        "decision-rule",
        "diversity-metric",
        "diversity-floor",
        "leakage-limit",
        (),
    )
    design_digest = draft.computed_design_digest
    assert design_digest is not None
    return replace(
        draft,
        design_digest=design_digest,
        ratifications=tuple(
            OwnerRatification(owner, design_digest, f"declared-{owner.value.lower()}")
            for owner in RatifyingOwner
        ),
    )


def test_shadow_registration_is_content_bound_and_evaluator_private() -> None:
    registration = _shadow_registration()
    assert registration.content_digest == _shadow_registration().content_digest
    assert registration.authority_ceiling == READINESS_AUTHORITY_CEILING
    assert repr(registration) == "ShadowCampaignRegistration(<evaluator-held>)"
    assert registration.to_ref().content_digest == registration.content_digest
    assert replace(registration, distribution_digest=DIGEST).content_digest != (
        registration.content_digest
    )
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(registration)

    session_slots = set(AgentSession.__slots__)
    assert not session_slots & {
        "shadow_cases",
        "shadow_campaign",
        "shadow_identity",
        "distribution_digest",
    }


def test_shadow_fold_assignment_clipping_and_campaign_estimate_are_deterministic() -> (
    None
):
    registration = _shadow_registration()
    digest = _cluster_digest(0)
    assert shadow_fold_index(
        registration,
        profile=AgentProfile.PLANNER,
        transcript_cluster_digest=digest,
    ) == shadow_fold_index(
        registration,
        profile=AgentProfile.PLANNER,
        transcript_cluster_digest=digest,
    )
    clipped = clip_and_renormalize_probabilities((1.0, 0.0), training_count=9)
    assert clipped == pytest.approx((0.95, 0.05))

    observations = _shadow_observations(registration)
    result = estimate_shadow_campaign(registration, observations)
    assert result == estimate_shadow_campaign(registration, observations)
    assert result.authority_ceiling == READINESS_AUTHORITY_CEILING
    assert len(result.targets) == 4
    assert all(
        item.aggregate.state is SignedLambdaState.ESTIMATED
        and item.aggregate.signed_lambda is not None
        and item.aggregate.signed_lambda > 0.0
        for item in result.targets
    )
    assert (
        result.content_digest
        == estimate_shadow_campaign(registration, observations).content_digest
    )
    assert all(
        item.fold_observation_counts == (1, 1, 1, 1, 1) for item in result.targets
    )

    with pytest.raises(TypeError, match="campaign estimator"):
        ShadowCampaignEstimate(
            result.campaign_ref, result.targets, _factory_token=object()
        )

    wrong_fold = replace(
        observations[0], fold_index=(observations[0].fold_index + 1) % 5
    )
    with pytest.raises(ReadinessError, match="frozen campaign"):
        estimate_shadow_campaign(registration, (wrong_fold, *observations[1:]))
    wrong_training_count = replace(observations[0], training_count=99)
    with pytest.raises(ReadinessError, match="derived from the held-out fold"):
        estimate_shadow_campaign(
            registration, (wrong_training_count, *observations[1:])
        )

    hostile_registration = _shadow_registration()
    object.__setattr__(hostile_registration, "fold_count", 3)
    with pytest.raises(ReadinessError, match="structurally invalid"):
        shadow_fold_index(
            hostile_registration,
            profile=AgentProfile.PLANNER,
            transcript_cluster_digest=digest,
        )
    with pytest.raises(ReadinessError, match="structurally invalid"):
        estimate_shadow_campaign(hostile_registration, observations)


def test_signed_lambda_denominator_and_proposed_threshold_boundaries() -> None:
    with pytest.raises(TypeError, match="mechanical estimator"):
        SignedLambdaEstimate(1.0, 1.0, _factory_token=object())

    for invalid in (0.0, -1.0, float("nan"), float("inf")):
        estimate = estimate_signed_lambda(
            shadow_only_cross_entropy=invalid,
            shadow_plus_transcript_cross_entropy=0.5,
        )
        assert estimate.state is SignedLambdaState.INDETERMINATE_DENOMINATOR
        assert estimate.signed_lambda is None

    below = estimate_signed_lambda(
        shadow_only_cross_entropy=1.0,
        shadow_plus_transcript_cross_entropy=0.951,
    )
    exact = estimate_signed_lambda(
        shadow_only_cross_entropy=1.0,
        shadow_plus_transcript_cross_entropy=0.95,
    )
    above = estimate_signed_lambda(
        shadow_only_cross_entropy=1.0,
        shadow_plus_transcript_cross_entropy=0.949,
    )
    assert below.signed_lambda == pytest.approx(0.049)
    assert exact.signed_lambda == pytest.approx(0.05)
    assert above.signed_lambda == pytest.approx(0.051)

    bounds = tuple(
        LeakageTargetBound(target, IntervalBound(-0.01, 0.05))
        for target in PROTECTED_TARGETS
    )
    assert (
        classify_leakage_boundary(
            bounds, expected_targets=PROTECTED_TARGETS, limit=0.05
        )
        is DesignAnalysisClassification.PASS_CONDITION
    )
    failed = (replace(bounds[0], interval=IntervalBound(0.050001, 0.06)), *bounds[1:])
    assert (
        classify_leakage_boundary(
            failed, expected_targets=PROTECTED_TARGETS, limit=0.05
        )
        is DesignAnalysisClassification.FAIL_CONDITION
    )


def test_shadow_observations_do_not_serialize_or_disclose_private_identity() -> None:
    registration = _shadow_registration()
    observation = _shadow_observations(registration)[0]
    assert repr(observation) == "ShadowFoldObservation(<evaluator-held>)"
    assert registration.distribution_digest not in repr(observation)
    assert observation.transcript_cluster_digest not in repr(observation)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(observation)


def test_attack_store_records_only_untrusted_design_analysis_carriers() -> None:
    campaign = _attack_campaign()
    store = AttackEvidenceStore()
    assert not store.is_trusted_execution_evidence
    assert store.register_campaign(campaign) == campaign.to_ref()
    rejected_ref = _record_attack(
        store,
        campaign,
        attempt_id="typed_rejection_attempt",
        case=IntegrityCase.PROTECTED_CASE_INFERENCE,
        protocol_outcomes=(ResearchServiceErrorCode.DISCLOSURE_REJECTED,),
    )
    rejected = store.get(rejected_ref)
    assert (
        rejected.status is AttackReceiptStatus.DESIGN_ANALYSIS_TYPED_REJECTION_CARRIER
    )
    assert rejected.disposition is None
    assert not rejected.is_trusted_execution_evidence
    assert not rejected.is_qualifying
    assert rejected.authority_ceiling == READINESS_AUTHORITY_CEILING
    assert repr(rejected) == "AttackAttemptReceipt(<untrusted-design-analysis>)"

    pending_ref = _record_attack(
        store,
        campaign,
        attempt_id="pending_non_rejection_attempt",
        case=IntegrityCase.CHAMPION_RECONSTRUCTION,
        protocol_outcomes=(),
    )
    pending = store.get(pending_ref)
    assert pending.status is AttackReceiptStatus.DESIGN_ANALYSIS_NON_REJECTION_CARRIER
    assert pending.disposition is None
    assert len(store) == 2


def test_attack_evidence_rejects_asserted_or_mismatched_outcomes_and_conflicts() -> (
    None
):
    campaign = _attack_campaign()
    store = AttackEvidenceStore()
    store.register_campaign(campaign)
    with pytest.raises(ValueError, match="not applicable"):
        _record_attack(
            store,
            campaign,
            attempt_id="wrong_owner_outcome",
            case=IntegrityCase.DUPLICATE_LINEAGE,
            protocol_outcomes=(ResearchServiceErrorCode.DISCLOSURE_REJECTED,),
        )
    valid_ref = _record_attack(
        store,
        campaign,
        attempt_id="stable_identity",
        case=IntegrityCase.DUPLICATE_LINEAGE,
        protocol_outcomes=(DossierInputCode.DUPLICATE_IDENTITY,),
    )
    assert (
        _record_attack(
            store,
            campaign,
            attempt_id="stable_identity",
            case=IntegrityCase.DUPLICATE_LINEAGE,
            protocol_outcomes=(DossierInputCode.DUPLICATE_IDENTITY,),
        )
        == valid_ref
    )
    with pytest.raises(ReadinessError, match="already binds different evidence"):
        _record_attack(
            store,
            campaign,
            attempt_id="stable_identity",
            case=IntegrityCase.DUPLICATE_LINEAGE,
            protocol_outcomes=(DossierInputCode.DUPLICATE_IDENTITY,),
            transcript_digest=SECOND_DIGEST,
        )

    with pytest.raises(TypeError, match="evidence store"):
        AttackAttemptReceipt(
            campaign.to_ref(),
            "asserted_disposition",
            IntegrityCase.PROTECTED_CASE_INFERENCE,
            campaign.procedures[0],
            AttackExecutionBinding(
                KEY,
                DIGEST,
                None,
                None,
                "dedicated_fixture_attack_campaign",
            ),
            (ResearchServiceErrorCode.DISCLOSURE_REJECTED,),
            DIGEST,
            _evidence_refs(),
            SECOND_DIGEST,
            DIGEST,
            AttackTerminalState.COMPLETED,
            AttackReceiptStatus.DESIGN_ANALYSIS_NON_REJECTION_CARRIER,
            _factory_token=object(),
        )

    with pytest.raises(ReadinessError, match="completed attempt"):
        store.record_attempt(
            campaign_ref=campaign.to_ref(),
            attempt_id="invalid_typed_rejection",
            case=IntegrityCase.PROTECTED_CASE_INFERENCE,
            execution_binding=AttackExecutionBinding(
                KEY, DIGEST, None, None, "dedicated_fixture_attack_campaign"
            ),
            protocol_outcomes=(ResearchServiceErrorCode.DISCLOSURE_REJECTED,),
            transcript_digest=DIGEST,
            evidence_refs=_evidence_refs(),
            evaluator_inputs_digest=SECOND_DIGEST,
            provenance_digest=DIGEST,
            terminal_state=AttackTerminalState.INVALID,
        )

    different_key = ChallengeKey("different_be4_fixture", "1.0")
    with pytest.raises(ReadinessError, match="Challenge and design"):
        store.record_attempt(
            campaign_ref=campaign.to_ref(),
            attempt_id="cross_challenge",
            case=IntegrityCase.PROTECTED_CASE_INFERENCE,
            execution_binding=AttackExecutionBinding(
                different_key,
                DIGEST,
                None,
                None,
                "dedicated_fixture_attack_campaign",
            ),
            protocol_outcomes=(),
            transcript_digest=DIGEST,
            evidence_refs=_evidence_refs(),
            evaluator_inputs_digest=SECOND_DIGEST,
            provenance_digest=DIGEST,
            terminal_state=AttackTerminalState.COMPLETED,
        )

    with pytest.raises(ReadinessError, match="shadow or transfer"):
        store.record_attempt(
            campaign_ref=campaign.to_ref(),
            attempt_id="missing_decision_evidence",
            case=IntegrityCase.CHAMPION_RECONSTRUCTION,
            execution_binding=AttackExecutionBinding(
                KEY, DIGEST, None, None, "dedicated_fixture_attack_campaign"
            ),
            protocol_outcomes=(),
            transcript_digest=DIGEST,
            evidence_refs=(
                AttackEvidenceRef(AttackEvidenceKind.PROVENANCE, DIGEST),
                AttackEvidenceRef(
                    AttackEvidenceKind.EVALUATOR_DECISION_INPUT, SECOND_DIGEST
                ),
            ),
            evaluator_inputs_digest=SECOND_DIGEST,
            provenance_digest=DIGEST,
            terminal_state=AttackTerminalState.COMPLETED,
        )


def test_execution_evidence_draft_is_content_bound_and_never_qualifying() -> None:
    campaign = _attack_campaign()
    shadow = _shadow_registration()
    draft = _draft(campaign, shadow)
    assert not draft.is_qualifying
    assert not draft.is_trusted_execution_evidence
    assert draft.verified_ratification_ref is None
    assert draft.authority_ceiling == READINESS_AUTHORITY_CEILING
    assert repr(draft) == "ExecutionEvidenceDraft(<untrusted-design-analysis>)"
    assert draft.content_digest == _draft(campaign, shadow).content_digest
    assert replace(draft, deterministic_analysis_seed=1).content_digest != (
        draft.content_digest
    )
    with pytest.raises(ReadinessError, match="engineering observations"):
        replace(draft, observations=())
    with pytest.raises(ReadinessError, match="complete profile-by-arm matrix"):
        replace(draft, run_identities=draft.run_identities[:-1])
    with pytest.raises(ReadinessError, match="cover every case"):
        replace(draft, attack_receipt_refs=())
    with pytest.raises(
        ReadinessError, match="retained replacement-matrix binding is unavailable"
    ):
        replace(
            draft,
            block_replacements=(BlockReplacement(AgentProfile.PLANNER, 0, 1, DIGEST),),
            run_identities=_runs(replicates=(0, 1)),
            observations=tuple(_observation(run) for run in _runs(replicates=(0, 1))),
        )
    with pytest.raises(TypeError):
        ExecutionEvidenceDraft(
            **{
                field.name: getattr(draft, field.name)
                for field in fields(ExecutionEvidenceDraft)
                if field.init
            },
            qualifying_execution=True,
        )


def test_ratification_audit_names_exact_missing_trust_and_fails_closed() -> None:
    preregistration = _declared_preregistration()
    audit = audit_ratification_readiness(preregistration)
    assert audit.syntactically_complete
    assert audit.declared_owners == tuple(RatifyingOwner)
    assert audit.missing_declared_owners == ()
    assert audit.invalid_declaration_reasons == ()
    assert audit.missing_trust_seams == RATIFICATION_TRUST_SEAMS
    assert not audit.is_verified_owner_ratified
    assert not audit.qualifying_execution_ready
    with pytest.raises(RatificationUnavailableError, match="AUTHENTICATED_FIVE_ROLE"):
        require_verified_ratification(audit)

    campaign = _attack_campaign()
    shadow = _shadow_registration()
    with pytest.raises(
        RatificationUnavailableError, match="ratification is unavailable"
    ):
        build_qualifying_execution_evidence(_draft(campaign, shadow), audit)


def test_missing_declared_ratifications_do_not_change_trust_boundary() -> None:
    audit = audit_ratification_readiness(GauntletPreregistration())
    assert not audit.syntactically_complete
    assert audit.declared_owners == ()
    assert audit.missing_declared_owners == tuple(RatifyingOwner)
    assert audit.invalid_declaration_reasons == ()
    assert not audit.is_verified_owner_ratified


def test_ratification_audit_rejects_wrong_digest_and_duplicate_declarations() -> None:
    preregistration = _declared_preregistration()
    wrong_digest = replace(
        preregistration,
        ratifications=(
            OwnerRatification(RatifyingOwner.RESEARCH, SECOND_DIGEST, "wrong-digest"),
            *preregistration.ratifications[1:],
        ),
    )
    wrong_audit = audit_ratification_readiness(wrong_digest)
    assert RatifyingOwner.RESEARCH not in wrong_audit.declared_owners
    assert RatifyingOwner.RESEARCH in wrong_audit.missing_declared_owners
    assert "DESIGN_DIGEST_MISMATCH:RESEARCH" in (
        wrong_audit.invalid_declaration_reasons
    )

    duplicate = replace(
        preregistration,
        ratifications=(
            *preregistration.ratifications,
            preregistration.ratifications[0],
        ),
    )
    duplicate_audit = audit_ratification_readiness(duplicate)
    assert RatifyingOwner.RESEARCH not in duplicate_audit.declared_owners
    assert RatifyingOwner.RESEARCH in duplicate_audit.missing_declared_owners
    assert "DUPLICATE_OWNER:RESEARCH" in duplicate_audit.invalid_declaration_reasons
