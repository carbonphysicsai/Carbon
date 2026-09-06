from __future__ import annotations

from dataclasses import replace

import pytest
from b07c_fixtures import make_fixture

from carbon.practice import (
    MockFixtureBehavior,
    MockPackRegistryError,
    MockTrainEvalService,
    PracticeAggregateKind,
    VersionedMockPackRegistry,
)
from carbon.registry import ChallengeKey
from carbon.research import (
    CancellationDisposition,
    CancelResearchTaskRequest,
    GetMockScaffoldRequest,
    GetResearchResultRequest,
    InfrastructureFailureClass,
    PublicFindingEvidenceClass,
    ResearchFailureCategory,
    ResearchTaskProviderError,
    ResearchTaskState,
    canonical_bytes,
)
from carbon.resource_policy.refs import ObservedResourceReceiptRef


@pytest.mark.parametrize(
    ("kind", "aggregate_kind"),
    (
        ("reconstruction", PracticeAggregateKind.RECONSTRUCTION),
        ("practice", PracticeAggregateKind.SINGLE_PRACTICE),
        ("paired", PracticeAggregateKind.PAIRED_DIFFERENCE),
        ("calibration", PracticeAggregateKind.RESOURCE_CALIBRATION),
    ),
)
def test_all_four_task_kinds_execute_through_b07b(tmp_path, kind, aggregate_kind):
    fixture = make_fixture(tmp_path)
    started = fixture.provider.start_research_task(
        fixture.request(kind, key=f"b07c-{kind}-idempotency")
    )
    terminal = fixture.provider.run_queued_task(started.task.task_id)

    assert terminal.state is ResearchTaskState.SUCCEEDED
    record = fixture.provider.get_experiment_record(terminal.task_id)
    aggregate_ref = next(
        ref
        for ref in record.aggregate_outcome_refs
        if ref.ref_type == "practice_aggregate"
    )
    aggregate = fixture.practice.get_private_aggregate(aggregate_ref)
    assert aggregate.kind is aggregate_kind
    assert record.task_bindings == terminal.immutable_bindings
    assert all(
        item.resolved_plan.environment_pins for item in record.resolved_strategies
    )
    if kind == "paired":
        assert aggregate.common_cases is True
        assert record.plan_difference is not None
        assert terminal.terminal_receipt.public_findings[0].kind == (
            "paired_practice_observed_difference"
        )
    elif kind == "practice":
        assert terminal.terminal_receipt.public_findings[0].kind == (
            "practice_observed_range"
        )
    elif kind == "calibration":
        assert terminal.immutable_bindings.practice_scope_ref is None
        assert aggregate.case_count == 0
        assert aggregate.aggregate_value is None
        assert aggregate.observed_range is None
        assert "RESOURCE_FACTS_ONLY" in aggregate.limitations
        assert terminal.terminal_receipt.public_findings == ()
        assert type(terminal.terminal_receipt.observed_resource_receipt_ref) is (
            ObservedResourceReceiptRef
        )
        assert fixture.recorder.calls[-1][2] is True


def test_non_champion_scaffold_compiles_and_runs(tmp_path):
    fixture = make_fixture(tmp_path)
    scaffold = fixture.scaffold.get_mock_scaffold(
        GetMockScaffoldRequest(
            fixture.info.challenge_key, fixture.info.training_support_ref, None
        )
    )
    assert scaffold.limitations == ("MOCK_ONLY", "NON_CHAMPION")
    request = fixture.request("practice", key="scaffold-to-execution")
    request = replace(
        request,
        task_spec=replace(request.task_spec, strategy=scaffold.strategy_template),
    )
    started = fixture.provider.start_research_task(request)
    assert fixture.provider.run_queued_task(started.task.task_id).state is (
        ResearchTaskState.SUCCEEDED
    )


def test_fresh_experiments_and_idempotent_replay(tmp_path):
    fixture = make_fixture(tmp_path)
    first = fixture.provider.start_research_task(
        fixture.request("practice", key="fresh-practice-one")
    )
    replay = fixture.provider.start_research_task(
        fixture.request("practice", key="fresh-practice-one")
    )
    assert replay.created is False
    assert replay.task.task_id == first.task.task_id
    assert len(fixture.queue.items) == 1
    first_terminal = fixture.provider.run_queued_task(first.task.task_id)
    assert fixture.provider.run_queued_task(first.task.task_id) == first_terminal

    second = fixture.provider.start_research_task(
        fixture.request("practice", key="fresh-practice-two")
    )
    second_terminal = fixture.provider.run_queued_task(second.task.task_id)
    first_ref = fixture.provider.get_experiment_record(
        first.task.task_id
    ).aggregate_outcome_refs[0]
    second_ref = fixture.provider.get_experiment_record(
        second.task.task_id
    ).aggregate_outcome_refs[0]
    assert first_ref != second_ref
    assert second_terminal.state is ResearchTaskState.SUCCEEDED


def test_poll_replay_and_queued_cancellation_do_not_execute_practice(tmp_path):
    fixture = make_fixture(tmp_path)
    started = fixture.provider.start_research_task(
        fixture.request("practice", key="poll-and-cancel-without-execution")
    )
    poll = GetResearchResultRequest(fixture.info.challenge_key, started.task.task_id, 0)
    first = fixture.provider.get_research_result(poll)
    replay = fixture.provider.get_research_result(poll)
    assert canonical_bytes(first) == canonical_bytes(replay)
    assert first.task.state is ResearchTaskState.QUEUED

    cancelled = fixture.provider.cancel_research_task(
        CancelResearchTaskRequest(
            fixture.info.challenge_key,
            started.task.task_id,
            "cancel-integrated-practice-0001",
        )
    )
    assert cancelled.disposition is CancellationDisposition.ACCEPTED
    assert cancelled.task.state is ResearchTaskState.CANCELLED
    assert cancelled.task.terminal_receipt.public_findings == ()
    assert fixture.recorder.calls == []
    assert fixture.provider.run_queued_task(started.task.task_id) == cancelled.task


def test_paired_zero_or_multiple_plan_differences_reject(tmp_path):
    fixture = make_fixture(tmp_path)
    request = fixture.request("paired")
    same = request.task_spec.baseline_strategy
    with pytest.raises(ResearchTaskProviderError):
        fixture.provider.start_research_task(
            replace(
                request,
                task_spec=replace(request.task_spec, intervention_strategy=same),
            )
        )
    multiple = {
        **request.task_spec.intervention_strategy,
        "backbone": "not_registered",
    }
    with pytest.raises(ResearchTaskProviderError):
        fixture.provider.start_research_task(
            replace(
                request,
                idempotency_key="multiple-plan-differences",
                task_spec=replace(request.task_spec, intervention_strategy=multiple),
            )
        )


def test_resource_calibration_rejects_practice_scope(tmp_path):
    fixture = make_fixture(tmp_path)
    request = fixture.request("calibration")
    with pytest.raises(ResearchTaskProviderError):
        fixture.provider.start_research_task(
            replace(request, practice_scope_ref=fixture.scope.to_ref())
        )


@pytest.mark.parametrize(
    ("behavior", "terminal", "failure"),
    (
        (
            MockFixtureBehavior.REFERENCE_FAILURE,
            ResearchTaskState.SUCCEEDED,
            ResearchFailureCategory.REFERENCE,
        ),
        (
            MockFixtureBehavior.MEASUREMENT_FAILURE,
            ResearchTaskState.SUCCEEDED,
            ResearchFailureCategory.MEASUREMENT,
        ),
        (
            MockFixtureBehavior.INFRASTRUCTURE_FAILURE,
            ResearchTaskState.FAILED_INFRA,
            InfrastructureFailureClass.DEPENDENCY_UNAVAILABLE,
        ),
        (
            MockFixtureBehavior.RESOURCE_KILL,
            ResearchTaskState.FAILED_INFRA,
            InfrastructureFailureClass.RESOURCE_LIMIT,
        ),
    ),
)
def test_failures_remain_typed_and_non_scientific_when_required(
    tmp_path, behavior, terminal, failure
):
    fixture = make_fixture(tmp_path, behavior=behavior)
    started = fixture.provider.start_research_task(fixture.request("practice"))
    view = fixture.provider.run_queued_task(started.task.task_id)
    assert view.state is terminal
    receipt = view.terminal_receipt
    assert receipt.public_findings == ()
    if terminal is ResearchTaskState.SUCCEEDED:
        record = fixture.provider.get_experiment_record(view.task_id)
        assert record.scientific_failure_category is failure
        assert receipt.infrastructure_failure_class is None
    else:
        assert receipt.infrastructure_failure_class is failure
        if behavior is MockFixtureBehavior.RESOURCE_KILL:
            assert (
                type(receipt.observed_resource_receipt_ref)
                is ObservedResourceReceiptRef
            )
            assert fixture.recorder.calls[-1][2] is False


def test_registry_rejects_cross_challenge_and_type_confusion(tmp_path):
    fixture = make_fixture(tmp_path)
    with pytest.raises(ValueError):
        replace(
            fixture.pack,
            challenge_key=ChallengeKey("other_fixture", "1.0"),
        )
    with pytest.raises(TypeError):
        VersionedMockPackRegistry(scopes=(fixture.scope,), packs=(object(),))
    with pytest.raises(MockPackRegistryError):
        VersionedMockPackRegistry(scopes=(fixture.scope,), packs=(fixture.pack,)).get(
            object()
        )
    with pytest.raises(ValueError):
        replace(
            fixture.pack.measurement_pack,
            non_authoritative_configuration_ref=(fixture.info.measurement_contract_ref),
        )


def test_stale_or_substituted_mock_pack_pin_fails_closed(tmp_path):
    fixture = make_fixture(tmp_path)
    substituted = replace(
        fixture.pack,
        limitations=(*fixture.pack.limitations, "SUBSTITUTED"),
    )
    fixture.provider._executor = MockTrainEvalService(
        registry=VersionedMockPackRegistry(
            scopes=(fixture.scope,), packs=(substituted,)
        ),
        interaction_manifest=fixture.manifest,
        resource_recorder=fixture.recorder,
    )
    started = fixture.provider.start_research_task(
        fixture.request("practice", key="stale-or-substituted-pack")
    )
    terminal = fixture.provider.run_queued_task(started.task.task_id)
    assert terminal.state is ResearchTaskState.FAILED_INFRA
    assert terminal.terminal_receipt.infrastructure_failure_class is (
        InfrastructureFailureClass.INTERNAL
    )
    assert "SUBSTITUTED" not in repr(terminal.terminal_receipt)


def test_official_or_substituted_context_factory_is_rejected(tmp_path):
    fixture = make_fixture(tmp_path)

    class WrongFactory:
        def make_context(self, task_id_value, pack):
            return object()

    service = MockTrainEvalService(
        registry=VersionedMockPackRegistry(
            scopes=(fixture.scope,), packs=(fixture.pack,)
        ),
        interaction_manifest=fixture.manifest,
        context_factory=WrongFactory(),
        resource_recorder=fixture.recorder,
    )
    fixture.provider._executor = service  # trusted composition fault injection
    started = fixture.provider.start_research_task(
        fixture.request("practice", key="context-source-attempt")
    )
    terminal = fixture.provider.run_queued_task(started.task.task_id)
    assert terminal.state is ResearchTaskState.FAILED_INFRA
    assert terminal.terminal_receipt.infrastructure_failure_class is (
        InfrastructureFailureClass.INTERNAL
    )


def test_public_receipt_is_bounded_and_has_no_score_or_hidden_material(tmp_path):
    fixture = make_fixture(tmp_path)
    started = fixture.provider.start_research_task(fixture.request("paired"))
    receipt = fixture.provider.run_queued_task(started.task.task_id).terminal_receipt
    rendered = repr(receipt)
    forbidden = (
        "ScoreInput",
        "ScorePack",
        "combined_score",
        "seed",
        "draw_index",
        "private_key",
        "official",
    )
    assert not any(token in rendered for token in forbidden)
    assert (
        receipt.public_findings[0].evidence_class
        is PublicFindingEvidenceClass.TEST_ONLY
    )
    assert (
        receipt.public_findings[0].measurement_ref
        == fixture.info.measurement_contract_ref
    )
    assert receipt.limitations == (
        "LOCAL_RESEARCH_ONLY",
        "MOCK_ONLY",
        "NOT_OFFICIAL_EVIDENCE",
        "NOT_SCIENTIFICALLY_QUALIFIED",
    )
