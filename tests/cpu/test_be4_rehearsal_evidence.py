"""B-E4 non-qualifying correlation, lineage, and reserve regressions."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from test_be4_execution_integration import (
    _DESIGN_DIGEST,
    _REQUESTER,
    _extended_resource_fixture,
    _official_graph,
    _published_prior,
)
from test_be4_nonqualifying_lifecycle import _lifecycle_research_graph

from carbon.fees import SubmissionAdmissionError, SubmissionService
from carbon.gauntlet import (
    AgentProfile,
    AgentSession,
    ExperimentalArm,
    LifecycleFailureKind,
    MatchedBudget,
    NonQualifyingLifecycleError,
    OfficialLifecycleBridge,
    RehearsalPurpose,
    RehearsalSlotRole,
    ReplacementEligibility,
    ResearchLifecycleBridge,
    authorize_replacement,
    bind_rehearsal_execution,
    build_nonqualifying_lifecycle_four_arm_block,
    build_rehearsal_campaign_manifest,
    fixture_agent_drivers,
    fixture_strategy_domain,
    record_block_failure,
    record_rehearsal_campaign,
    record_rehearsal_run,
    record_rejected_operation,
    run_nonqualifying_lifecycle,
)
from carbon.gauntlet.execution import ResearchOperationFailure
from carbon.gauntlet.meter import PolicyWorkMeter
from carbon.practice import MockTrainEvalService
from carbon.research import ResearchServiceErrorCode, ResourceObservation
from carbon.traineval.model import (
    InfrastructureCause,
    InfrastructureFailedRun,
    InfrastructureRetryClass,
)
from carbon.traineval.resolved_fixture import (
    FixtureReferenceCause,
    FixtureReferenceFailed,
    ResolvedPlanFixtureTrainEvalService,
)


def _sha(character: str) -> str:
    return "sha256:" + character * 64


def _one_v2_run(
    tmp_path: Path,
    *,
    budget: MatchedBudget | None = None,
    fixture_resource_ceiling: int = 223,
    manifest=None,
    slot=None,
    borrow_session: bool = False,
):
    domain = _extended_resource_fixture(tmp_path / "domain")
    store, prior_provider, lookup = _published_prior(tmp_path / "prior", domain)
    service, provider, scaffold_ref, practice_pack_ref = _lifecycle_research_graph(
        tmp_path / "research", domain, store, prior_provider, lookup
    )
    driver = fixture_agent_drivers()[0]
    block, projection = build_nonqualifying_lifecycle_four_arm_block(
        design_digest=_DESIGN_DIGEST,
        block_id="evidence-planner-0000" if slot is None else slot.block_id,
        profile=driver.profile,
        replicate=0 if slot is None else slot.number,
        driver_ref=driver.ref,
        budget=budget or MatchedBudget(driver.profile, 30.0, 250.0, 8),
        fixture_resource_ceiling=fixture_resource_ceiling,
        scaffold_ref=scaffold_ref,
        practice_pack_ref=practice_pack_ref,
        v2_prior_pack=store.read_pack(lookup.prior_pack_ref),
        v2_authorization_ref=lookup.authorization.receipt_ref,
    )
    plan = next(
        item
        for item in block.runs
        if item.identity.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR
    )
    official, submission_service, adapter = _official_graph(
        tmp_path / "official", domain
    )
    meter = PolicyWorkMeter()
    session = AgentSession(service, official, _REQUESTER, meter)
    execution_binding = (
        None
        if manifest is None
        else bind_rehearsal_execution(
            manifest=manifest, slot=slot, plan=plan, session=session
        )
    )
    if borrow_session:
        session = AgentSession(service, official, _REQUESTER, meter)
    run = run_nonqualifying_lifecycle(
        session=session,
        plan=plan,
        driver=driver,
        projection=projection,
        strategy_domain=fixture_strategy_domain(
            domain.compile_fixture.catalog.to_ref(
                candidate_assembly=domain.compile_fixture.assembly
            )
        ),
        parameter_catalog=domain.compile_fixture.catalog,
        candidate_assembly=domain.compile_fixture.assembly,
        meter=meter,
        research_bridge=ResearchLifecycleBridge(service, provider),
        official_bridge=OfficialLifecycleBridge(
            official, submission_service, adapter, _REQUESTER
        ),
        execution_binding=execution_binding,
    )
    catalog_ref = domain.compile_fixture.catalog.to_ref(
        candidate_assembly=domain.compile_fixture.assembly
    )
    evidence = record_rehearsal_run(
        run,
        catalog=domain.compile_fixture.catalog,
        candidate_assembly=domain.compile_fixture.assembly,
        catalog_ref=catalog_ref,
    )
    return domain, driver, run, evidence


def _campaign_manifest(campaign_id: str, *, primary: int = 1, reserve: int = 1):
    return build_rehearsal_campaign_manifest(
        purpose=RehearsalPurpose.DEVELOPMENT,
        design_digest=_DESIGN_DIGEST,
        implementation_digest=_sha("a"),
        treatment_digests=tuple(_sha(str(i)) for i in range(4)),
        driver_digests=tuple(_sha(chr(98 + i)) for i in range(5)),
        budget_digests=tuple(_sha(character) for character in "56789"),
        primary_blocks_per_profile=primary,
        reserve_blocks_per_profile=reserve,
        campaign_id=campaign_id,
        stopping_rule="ATTEMPT_EVERY_PROSPECTIVE_PRIMARY_ONCE",
        failure_handling="REPLACE_ONLY_INFRASTRUCTURE_OR_REFERENCE",
    )


@pytest.fixture(scope="module")
def v2_bundle(tmp_path_factory: pytest.TempPathFactory):
    return _one_v2_run(tmp_path_factory.mktemp("be4-rehearsal-evidence"))


def test_rehearsal_evidence_correlates_owner_records_and_never_qualifies(
    v2_bundle,
) -> None:
    _, _, run, evidence = v2_bundle
    assert evidence.lifecycle_digest == run.content_digest
    assert evidence.plan_slot_digest == run.plan.final_submission_slot_digest
    assert evidence.driver_digest == run.driver_artifact.content_digest
    assert evidence.treatment_digest == run.treatment_artifact.content_digest
    assert evidence.selected_proposal_digest == run.selection.selected_proposal_digest
    assert evidence.submission_id == run.public_result.status.submission_id.value
    assert evidence.endpoint_receipt_ref == (
        run.official_outcome.endpoint_observation_receipt.receipt_ref
    )
    assert evidence.practice_correlation_digests == tuple(
        item.content_digest for item in run.practice
    )
    assert evidence.practice_task_ids == tuple(
        item.experiment_record.task_id.value for item in run.practice
    )
    assert len(evidence.canonical_family_ids) == len(run.practice)
    assert len(evidence.experiment_record_digests) == len(run.practice)
    assert run.qualifying_execution_ready is False
    assert evidence.qualifying_execution_ready is False


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("plan_slot_digest", _sha("1")),
        ("driver_digest", _sha("2")),
        ("treatment_digest", _sha("3")),
        ("selected_proposal_digest", _sha("4")),
        ("session_binding_digest", _sha("5")),
        ("endpoint_receipt_ref", _sha("6")),
        ("transcript_cluster_digest", _sha("7")),
    ),
)
def test_correlation_substitution_is_rejected(
    v2_bundle, field: str, value: str
) -> None:
    _, _, _, evidence = v2_bundle
    with pytest.raises(ValueError, match="does not bind"):
        replace(evidence, **{field: value})


def test_lifecycle_and_practice_records_reject_posthoc_substitution(
    v2_bundle,
) -> None:
    _, _, run, _ = v2_bundle
    with pytest.raises(ValueError, match="owner correlations"):
        replace(run, heldout_mse=run.heldout_mse + 1.0)
    with pytest.raises(ValueError, match="does not bind"):
        replace(run.practice[0], start_reply_digest=_sha("8"))
    with pytest.raises(ValueError, match="transcript"):
        replace(
            run.prepared,
            service_request_digests=(
                _sha("9"),
                *run.prepared.service_request_digests[1:],
            ),
        )


def test_manifest_and_typed_reserve_policy_preserve_failed_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = build_rehearsal_campaign_manifest(
        purpose=RehearsalPurpose.CALIBRATION,
        design_digest=_DESIGN_DIGEST,
        implementation_digest=_sha("a"),
        treatment_digests=tuple(_sha(str(i)) for i in range(4)),
        driver_digests=tuple(_sha(chr(98 + i)) for i in range(5)),
        budget_digests=tuple(_sha(character) for character in "56789"),
        primary_blocks_per_profile=2,
        reserve_blocks_per_profile=1,
        campaign_id="be4-calibration-v1",
        stopping_rule="ATTEMPT_EVERY_PROSPECTIVE_PRIMARY_ONCE",
        failure_handling="REPLACE_ONLY_INFRASTRUCTURE_OR_REFERENCE",
    )
    assert len(manifest.slots) == 15
    primary = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.PRIMARY
    )
    reserve = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.RESERVE
    )
    monkeypatch.setattr(
        ResolvedPlanFixtureTrainEvalService,
        "run_fixture",
        lambda _self, envelope: FixtureReferenceFailed(
            envelope.handle, FixtureReferenceCause.REFERENCE_EVALUATION_FAILED
        ),
    )
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path, manifest=manifest, slot=primary)
    failure = record_block_failure(manifest, captured.value)
    mapping = authorize_replacement(failed=failure, replacement=reserve)
    rejected = record_rejected_operation(
        primary,
        ResearchOperationFailure(
            "dry_validate",
            ResearchServiceErrorCode.REQUEST_TYPE_INVALID,
            _sha("c"),
            _sha("d"),
        ),
    )
    campaign = record_rehearsal_campaign(
        manifest=manifest,
        runs=(),
        failures=(failure,),
        rejected_operations=(rejected,),
        replacements=(mapping,),
    )
    assert campaign.failures == (failure,)
    assert campaign.rejected_operations == (rejected,)
    assert campaign.replacements == (mapping,)
    assert campaign.qualifying_execution_ready is False


def test_one_failed_source_cannot_be_rebound_or_replaced_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _campaign_manifest("be4-failure-one-use-v1", primary=1, reserve=2)
    primary = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.PRIMARY
    )
    reserves = tuple(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.RESERVE
    )
    monkeypatch.setattr(
        ResolvedPlanFixtureTrainEvalService,
        "run_fixture",
        lambda _self, envelope: FixtureReferenceFailed(
            envelope.handle, FixtureReferenceCause.REFERENCE_EVALUATION_FAILED
        ),
    )
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path, manifest=manifest, slot=primary)
    failure = record_block_failure(manifest, captured.value)
    mappings = tuple(
        authorize_replacement(failed=failure, replacement=reserve)
        for reserve in reserves
    )
    with pytest.raises(ValueError, match="unique failures"):
        record_rehearsal_campaign(
            manifest=manifest,
            runs=(),
            failures=(failure,),
            replacements=mappings,
        )
    with pytest.raises(ValueError, match="duplicate failed source"):
        record_rehearsal_campaign(
            manifest=manifest,
            runs=(),
            failures=(failure, failure),
        )

    other = _campaign_manifest("be4-other-campaign-v1")
    with pytest.raises(ValueError, match="another campaign"):
        record_block_failure(other, captured.value)


def test_prebound_failure_cannot_be_borrowed_by_another_session(
    tmp_path: Path,
) -> None:
    manifest = _campaign_manifest("be4-cross-session-v1")
    primary = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.PRIMARY
    )
    with pytest.raises(ValueError, match="exact lifecycle run"):
        _one_v2_run(
            tmp_path,
            manifest=manifest,
            slot=primary,
            borrow_session=True,
        )


def test_candidate_failures_and_cross_profile_reserves_cannot_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _campaign_manifest("be4-development-v1")
    primary = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.PRIMARY
    )
    planner_reserve = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.RESERVE
    )
    other_reserve = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.MINIMALIST
        and item.role is RehearsalSlotRole.RESERVE
    )
    with pytest.raises(NonQualifyingLifecycleError) as candidate_error:
        _one_v2_run(
            tmp_path / "candidate",
            fixture_resource_ceiling=1,
            manifest=manifest,
            slot=primary,
        )
    candidate = record_block_failure(manifest, candidate_error.value)
    with pytest.raises(ValueError, match="not authorized"):
        authorize_replacement(failed=candidate, replacement=planner_reserve)
    monkeypatch.setattr(
        ResolvedPlanFixtureTrainEvalService,
        "run_fixture",
        lambda _self, envelope: InfrastructureFailedRun(
            envelope.handle,
            InfrastructureRetryClass.RETRYABLE,
            InfrastructureCause.BACKEND_UNAVAILABLE,
        ),
    )
    with pytest.raises(NonQualifyingLifecycleError) as infrastructure_error:
        _one_v2_run(tmp_path / "infrastructure", manifest=manifest, slot=primary)
    infrastructure = record_block_failure(manifest, infrastructure_error.value)
    with pytest.raises(ValueError, match="not authorized"):
        authorize_replacement(failed=infrastructure, replacement=other_reserve)


@pytest.mark.parametrize(
    "stage",
    (
        "wall_budget_before_selection",
        "wall_budget_after_endpoint",
        "fixture_resource_budget",
        "normalized_compute_budget",
        "attempt_budget",
        "service_budget",
    ),
)
def test_policy_exhaustion_cannot_acquire_an_infrastructure_replacement(
    stage: str,
) -> None:
    manifest = build_rehearsal_campaign_manifest(
        purpose=RehearsalPurpose.DEVELOPMENT,
        design_digest=_DESIGN_DIGEST,
        implementation_digest=_sha("a"),
        treatment_digests=tuple(_sha(str(i)) for i in range(4)),
        driver_digests=tuple(_sha(chr(98 + i)) for i in range(5)),
        budget_digests=tuple(_sha(character) for character in "56789"),
        primary_blocks_per_profile=1,
        reserve_blocks_per_profile=1,
        campaign_id="be4-policy-exhaustion-no-replacement-v1",
        stopping_rule="ATTEMPT_EVERY_PROSPECTIVE_PRIMARY_ONCE",
        failure_handling="REPLACE_ONLY_INFRASTRUCTURE_OR_REFERENCE",
    )
    primary = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.PRIMARY
    )
    reserve = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.RESERVE
    )
    del primary, reserve
    with pytest.raises(ValueError, match="unbound"):
        record_block_failure(
            manifest,
            NonQualifyingLifecycleError(LifecycleFailureKind.INFRASTRUCTURE, stage),
        )


def test_caller_asserted_infrastructure_failure_cannot_grant_replacement() -> None:
    manifest = build_rehearsal_campaign_manifest(
        purpose=RehearsalPurpose.DEVELOPMENT,
        design_digest=_DESIGN_DIGEST,
        implementation_digest=_sha("a"),
        treatment_digests=tuple(_sha(str(i)) for i in range(4)),
        driver_digests=tuple(_sha(chr(98 + i)) for i in range(5)),
        budget_digests=tuple(_sha(character) for character in "56789"),
        primary_blocks_per_profile=1,
        reserve_blocks_per_profile=1,
        campaign_id="be4-forged-infrastructure-no-replacement-v1",
        stopping_rule="ATTEMPT_EVERY_PROSPECTIVE_PRIMARY_ONCE",
        failure_handling="REPLACE_ONLY_INFRASTRUCTURE_OR_REFERENCE",
    )
    primary = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.PRIMARY
    )
    reserve = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.RESERVE
    )
    del primary, reserve
    with pytest.raises(ValueError, match="unbound"):
        record_block_failure(
            manifest,
            NonQualifyingLifecycleError(
                LifecycleFailureKind.INFRASTRUCTURE, "fixture_official"
            ),
        )


@pytest.mark.parametrize(
    ("budget", "fixture_ceiling", "expected_stage"),
    (
        (MatchedBudget(AgentProfile.PLANNER, 30.0, 1.0, 8), 223, "service_budget"),
        (
            MatchedBudget(AgentProfile.PLANNER, 0.000000001, 250.0, 8),
            223,
            "wall_budget_before_practice",
        ),
        (
            MatchedBudget(AgentProfile.PLANNER, 30.0, 250.0, 8),
            1,
            "fixture_resource_budget_before_practice",
        ),
    ),
)
def test_executed_policy_exhaustion_retains_resources_and_never_replaces(
    tmp_path: Path,
    budget: MatchedBudget,
    fixture_ceiling: int,
    expected_stage: str,
) -> None:
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(
            tmp_path,
            budget=budget,
            fixture_resource_ceiling=fixture_ceiling,
        )
    error = captured.value
    assert error.kind is LifecycleFailureKind.POLICY_EXHAUSTION
    assert error.stage == expected_stage
    assert error.replacement_eligibility is ReplacementEligibility.NOT_ELIGIBLE
    assert error.resource_observation is not None
    assert error.resource_observation.normalized_compute.total_work_units >= 0
    assert error.resource_observation.fixture_units >= 0.0
    assert error.resource_observation.wall_time.elapsed_seconds >= 0.0


@pytest.mark.parametrize(
    ("retry_class", "cause", "expected"),
    (
        (
            InfrastructureRetryClass.RETRYABLE,
            InfrastructureCause.BACKEND_UNAVAILABLE,
            ReplacementEligibility.VERIFIED_INFRASTRUCTURE,
        ),
        (
            InfrastructureRetryClass.RETRYABLE,
            InfrastructureCause.EXECUTION_TIMEOUT,
            ReplacementEligibility.NOT_ELIGIBLE,
        ),
        (
            InfrastructureRetryClass.NON_RETRYABLE,
            InfrastructureCause.RESOURCE_VIOLATION,
            ReplacementEligibility.NOT_ELIGIBLE,
        ),
    ),
)
def test_official_owner_outcome_controls_infrastructure_replacement_eligibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    retry_class: InfrastructureRetryClass,
    cause: InfrastructureCause,
    expected: ReplacementEligibility,
) -> None:
    monkeypatch.setattr(
        ResolvedPlanFixtureTrainEvalService,
        "run_fixture",
        lambda _self, envelope: InfrastructureFailedRun(
            envelope.handle, retry_class, cause
        ),
    )
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path)
    assert captured.value.kind is LifecycleFailureKind.INFRASTRUCTURE
    assert captured.value.replacement_eligibility is expected
    assert (captured.value.owner_failure_digest is not None) is (
        expected is ReplacementEligibility.VERIFIED_INFRASTRUCTURE
    )


def test_typed_reference_owner_outcome_remains_replaceable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ResolvedPlanFixtureTrainEvalService,
        "run_fixture",
        lambda _self, envelope: FixtureReferenceFailed(
            envelope.handle, FixtureReferenceCause.REFERENCE_EVALUATION_FAILED
        ),
    )
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path)
    assert captured.value.kind is LifecycleFailureKind.REFERENCE
    assert (
        captured.value.replacement_eligibility
        is ReplacementEligibility.VERIFIED_REFERENCE
    )
    assert captured.value.owner_failure_digest is not None


def test_campaign_rejects_forged_slot_metadata_with_a_real_block_id(
    tmp_path: Path,
) -> None:
    manifest = build_rehearsal_campaign_manifest(
        purpose=RehearsalPurpose.DEVELOPMENT,
        design_digest=_DESIGN_DIGEST,
        implementation_digest=_sha("a"),
        treatment_digests=tuple(_sha(str(i)) for i in range(4)),
        driver_digests=tuple(_sha(chr(98 + i)) for i in range(5)),
        budget_digests=tuple(_sha(character) for character in "56789"),
        primary_blocks_per_profile=1,
        reserve_blocks_per_profile=1,
        campaign_id="be4-development-slot-integrity-v1",
        stopping_rule="ATTEMPT_EVERY_PROSPECTIVE_PRIMARY_ONCE",
        failure_handling="REPLACE_ONLY_INFRASTRUCTURE_OR_REFERENCE",
    )
    primary = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.PRIMARY
    )
    forged = replace(primary, number=primary.number + 1)
    with pytest.raises(ValueError, match="frozen manifest"):
        _one_v2_run(tmp_path, manifest=manifest, slot=forged)


def test_campaign_rejects_duplicate_run_evidence(v2_bundle) -> None:
    _, _, _, evidence = v2_bundle
    manifest = build_rehearsal_campaign_manifest(
        purpose=RehearsalPurpose.DEVELOPMENT,
        design_digest=_DESIGN_DIGEST,
        implementation_digest=_sha("a"),
        treatment_digests=tuple(_sha(str(i)) for i in range(4)),
        driver_digests=tuple(_sha(chr(98 + i)) for i in range(5)),
        budget_digests=tuple(_sha(character) for character in "56789"),
        primary_blocks_per_profile=1,
        reserve_blocks_per_profile=0,
        campaign_id="be4-development-v2",
        stopping_rule="ATTEMPT_EVERY_PROSPECTIVE_PRIMARY_ONCE",
        failure_handling="NO_REPLACEMENT_WITHOUT_TYPED_RESERVE",
    )
    with pytest.raises(ValueError, match="duplicate run"):
        record_rehearsal_campaign(manifest=manifest, runs=(evidence, evidence))


def test_completed_practice_consumption_survives_a_later_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    completed: list[object] = []
    original = MockTrainEvalService.run_mock

    def counted(service, request):
        result = original(service, request)
        completed.append(result)
        return result

    timestamps = iter((0, 0, 0, 31_000_000_000, 31_000_000_000))
    monkeypatch.setattr(MockTrainEvalService, "run_mock", counted)
    monkeypatch.setattr(
        "carbon.gauntlet.lifecycle.time.monotonic_ns",
        lambda: next(timestamps, 31_000_000_000),
    )

    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path)

    observation = captured.value.resource_observation
    assert len(completed) == 1
    assert observation is not None
    assert observation.schema_version == "2.0"
    assert observation.confirmed_fixture_units > 0.0
    assert observation.unreconciled_fixture_units == 0.0


def test_complete_pair_is_admitted_before_practice_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    completed: list[object] = []
    original = MockTrainEvalService.run_mock

    def counted(service, request):
        result = original(service, request)
        completed.append(result)
        return result

    monkeypatch.setattr(MockTrainEvalService, "run_mock", counted)
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path, fixture_resource_ceiling=15)

    observation = captured.value.resource_observation
    assert captured.value.stage == "fixture_resource_budget_before_practice"
    assert completed == []
    assert observation is not None
    assert observation.predicted_fixture_units == 22.0
    assert observation.confirmed_fixture_units == 0.0


def test_preflight_rejection_does_not_report_predicted_work_as_consumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    completed: list[object] = []
    original = MockTrainEvalService.run_mock

    def counted(service, request):
        result = original(service, request)
        completed.append(result)
        return result

    monkeypatch.setattr(MockTrainEvalService, "run_mock", counted)
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path, fixture_resource_ceiling=1)

    observation = captured.value.resource_observation
    assert completed == []
    assert observation is not None
    assert observation.predicted_fixture_units > 0.0
    assert observation.confirmed_fixture_units == 0.0
    assert observation.reserved_fixture_units == 0.0


def test_later_service_budget_stop_retains_prior_confirmed_consumption(
    tmp_path: Path,
) -> None:
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(
            tmp_path,
            budget=MatchedBudget(AgentProfile.PLANNER, 30.0, 32.0, 8),
        )
    observation = captured.value.resource_observation
    assert captured.value.stage == "service_budget"
    assert observation is not None
    assert observation.confirmed_fixture_units == 22.0
    assert observation.reserved_fixture_units == 0.0
    assert observation.unreconciled_fixture_units == 0.0


def test_post_operation_overrun_is_confirmed_not_rewritten_as_prediction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = MockTrainEvalService._observations

    def inflated(attempt):
        return tuple(
            ResourceObservation(item.dimension_id, item.quantity + 4.0, item.unit)
            for item in original(attempt)
        )

    monkeypatch.setattr(MockTrainEvalService, "_observations", staticmethod(inflated))
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path, fixture_resource_ceiling=25)
    observation = captured.value.resource_observation
    assert captured.value.stage == "fixture_resource_budget_after_practice"
    assert observation is not None
    assert observation.predicted_fixture_units == 22.0
    assert observation.confirmed_fixture_units == 26.0
    assert observation.reserved_fixture_units == 0.0


def test_rejected_final_admission_does_not_consume_predicted_final_units(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        SubmissionService,
        "admit_fixture",
        lambda _self, _submission_id, _requester: (_ for _ in ()).throw(
            SubmissionAdmissionError()
        ),
    )
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path)
    observation = captured.value.resource_observation
    assert captured.value.stage == "fixture_official_admission"
    assert observation is not None
    assert observation.predicted_fixture_units == 11.0
    assert observation.confirmed_fixture_units == 70.0
    assert observation.reserved_fixture_units == 0.0


def test_ambiguous_dispatched_failure_retains_unreconciled_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ResolvedPlanFixtureTrainEvalService,
        "run_fixture",
        lambda _self, _envelope: (_ for _ in ()).throw(RuntimeError("ambiguous")),
    )
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path)
    observation = captured.value.resource_observation
    assert captured.value.stage == "fixture_official_unreconciled"
    assert observation is not None
    assert observation.confirmed_fixture_units == 70.0
    assert observation.reserved_fixture_units == 11.0
    assert observation.unreconciled_fixture_units == 11.0


def test_unreconciled_owner_failure_cannot_spend_a_reserve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _campaign_manifest("be4-unreconciled-no-replacement-v1")
    primary = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.PRIMARY
    )
    reserve = next(
        item
        for item in manifest.slots
        if item.profile is AgentProfile.PLANNER
        and item.role is RehearsalSlotRole.RESERVE
    )
    monkeypatch.setattr(
        ResolvedPlanFixtureTrainEvalService,
        "run_fixture",
        lambda _self, envelope: InfrastructureFailedRun(
            envelope.handle,
            InfrastructureRetryClass.RETRYABLE,
            InfrastructureCause.BACKEND_UNAVAILABLE,
        ),
    )
    with pytest.raises(NonQualifyingLifecycleError) as captured:
        _one_v2_run(tmp_path, manifest=manifest, slot=primary)
    failure = record_block_failure(manifest, captured.value)
    assert (
        failure.replacement_eligibility
        is ReplacementEligibility.VERIFIED_INFRASTRUCTURE
    )
    assert failure.resource_observation is not None
    assert failure.resource_observation.unreconciled_fixture_units == 11.0
    with pytest.raises(ValueError, match="not authorized"):
        authorize_replacement(failed=failure, replacement=reserve)


def test_success_resource_totals_are_fully_reconciled(v2_bundle) -> None:
    _, _, run, _ = v2_bundle
    assert run.fixture_units == 81.0
    assert run.resource_observation.confirmed_fixture_units == 81.0
    assert run.resource_observation.reserved_fixture_units == 0.0
    assert run.resource_observation.unreconciled_fixture_units == 0.0
