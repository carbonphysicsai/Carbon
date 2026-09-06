"""B-07B task identity, lifecycle, receipt, and private-record tests."""

from __future__ import annotations

import hashlib
import threading
from dataclasses import replace

import pytest
from b07a_fixtures import digest
from b07b_fixtures import make_fixture, outcome, private_ref

from carbon.authoring.model import EvidenceRole
from carbon.fees import StrategyHash
from carbon.research import (
    ActivePriorSelector,
    AvailablePriorAvailability,
    CancellationDisposition,
    CancelResearchTaskRequest,
    EpistemicType,
    EvidenceQualityMetadata,
    GetResearchResultRequest,
    InfrastructureExecutionFailure,
    InfrastructureFailureClass,
    PracticeScopeStatementRef,
    PriorChannel,
    PriorChannelRef,
    PriorIndexSnapshotRef,
    PriorPackRef,
    PriorPolicyBundleRef,
    PriorResolution,
    ResearchEvidenceClass,
    ResearchFailureCategory,
    ResearchRetentionScope,
    ResearchServiceErrorCode,
    ResearchTaskProviderError,
    ResearchTaskState,
    RetentionReuseBinding,
    canonical_bytes,
    load_canonical,
)
from carbon.research.canonical import _canonical_record_payload_without
from carbon.resource_policy.refs import ObservedResourceReceiptRef


def test_atomic_duplicate_replay_and_conflict_do_not_duplicate_work(tmp_path):
    fixture = make_fixture(tmp_path)
    request = fixture.request()
    results = []

    threads = [
        threading.Thread(
            target=lambda: results.append(fixture.provider.start_research_task(request))
        )
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(result.created for result in results) == 1
    assert len({result.task.task_id for result in results}) == 1
    assert fixture.compiler.calls == 2
    assert fixture.resources.calls == 1
    assert fixture.queue.items == [results[0].task.task_id]

    changed = fixture.request(
        strategies=(
            request.task_spec.baseline_strategy,
            {
                **request.task_spec.intervention_strategy,
                "parameters": {"fixture_sampling_level": 1},
            },
        )
    )
    with pytest.raises(ResearchTaskProviderError) as error:
        fixture.provider.start_research_task(changed)
    assert error.value.code is ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
    assert fixture.compiler.calls == 2
    assert fixture.queue.items == [results[0].task.task_id]


def test_failed_resolution_inserts_no_idempotency_or_task(tmp_path):
    fixture = make_fixture(tmp_path)
    request = fixture.request()
    wrong_scope = PracticeScopeStatementRef(
        request.challenge_key, content_digest=digest("f")
    )
    with pytest.raises(ResearchTaskProviderError) as error:
        fixture.provider.start_research_task(
            replace(request, practice_scope_ref=wrong_scope)
        )
    assert error.value.code is ResearchServiceErrorCode.REFERENCE_MISMATCH

    created = fixture.provider.start_research_task(request)
    assert created.created is True
    assert fixture.queue.items == [created.task.task_id]


def test_constructor_requester_binding_is_local_isolation_not_identity_claim(tmp_path):
    first = make_fixture(tmp_path / "first")
    second = make_fixture(tmp_path / "second")

    left = first.provider.start_research_task(first.request()).task.task_id
    right = second.provider.start_research_task(second.request()).task.task_id

    assert left != right
    assert not hasattr(first.provider, "authenticate")
    assert not hasattr(first.provider, "miner_identity")


def test_success_pins_lineage_and_authoritative_plan_difference(tmp_path):
    fixture = make_fixture(tmp_path)
    started = fixture.provider.start_research_task(fixture.request())

    terminal = fixture.provider.run_queued_task(started.task.task_id)
    record = fixture.provider.get_experiment_record(started.task.task_id)

    assert terminal.state is ResearchTaskState.SUCCEEDED
    assert terminal.revision == 2
    assert terminal.immutable_bindings == started.task.immutable_bindings
    assert (
        terminal.terminal_receipt.immutable_bindings == started.task.immutable_bindings
    )
    assert record.plan_difference.surface_id == "fixture_sampling_level"
    assert record.parent_strategy_hashes == (None, None)
    assert record.execution_identity.attempts == 1
    assert record.evidence_context.epistemic_status is None
    assert terminal.terminal_receipt.receipt_ref.task_id == started.task.task_id
    assert terminal.terminal_receipt.infrastructure_failure_class is None
    expected_digest = (
        "sha256:"
        + hashlib.sha256(
            b"carbon.research-receipt.v2\x00"
            + _canonical_record_payload_without(
                terminal.terminal_receipt, frozenset({"receipt_ref"})
            )
        ).hexdigest()
    )
    assert terminal.terminal_receipt.receipt_ref.receipt_digest == expected_digest
    assert load_canonical(canonical_bytes(terminal), type(terminal)) == terminal


def test_single_strategy_parent_lineage_is_preserved(tmp_path):
    fixture = make_fixture(tmp_path)
    request = fixture.request(paired=False)
    parent = StrategyHash("sha256:" + "a" * 64)
    request = replace(
        request, task_spec=replace(request.task_spec, parent_strategy_hash=parent)
    )

    started = fixture.provider.start_research_task(request)
    fixture.provider.run_queued_task(started.task.task_id)
    record = fixture.provider.get_experiment_record(started.task.task_id)

    assert record.parent_strategy_hashes == (parent,)
    assert record.plan_difference is None


def test_poll_sequence_replays_captured_bytes_and_never_advances_work(tmp_path):
    fixture = make_fixture(tmp_path)
    started = fixture.provider.start_research_task(fixture.request())
    task_id = started.task.task_id
    poll0 = GetResearchResultRequest(started.task.challenge_key, task_id, 0)

    first = fixture.provider.get_research_result(poll0)
    assert first.task.state is ResearchTaskState.QUEUED
    assert fixture.executor.attempts == []
    fixture.provider.run_queued_task(task_id)
    replay = fixture.provider.get_research_result(poll0)
    assert canonical_bytes(replay) == canonical_bytes(first)
    latest = fixture.provider.get_research_result(replace(poll0, poll_sequence=1))
    assert latest.task.state is ResearchTaskState.SUCCEEDED
    with pytest.raises(ResearchTaskProviderError) as error:
        fixture.provider.get_research_result(replace(poll0, poll_sequence=0))
    assert error.value.code is ResearchServiceErrorCode.POLL_SEQUENCE_INVALID
    with pytest.raises(ResearchTaskProviderError):
        fixture.provider.get_research_result(replace(poll0, poll_sequence=3))


def test_queued_cancellation_is_terminal_and_receipt_never_rewrites(tmp_path):
    fixture = make_fixture(tmp_path)
    started = fixture.provider.start_research_task(fixture.request())
    request = CancelResearchTaskRequest(
        started.task.challenge_key, started.task.task_id, "cancel-fixture-0001"
    )

    cancelled = fixture.provider.cancel_research_task(request)
    receipt_bytes = canonical_bytes(cancelled.task.terminal_receipt)
    repeated = fixture.provider.cancel_research_task(request)

    assert cancelled.disposition is CancellationDisposition.ACCEPTED
    assert cancelled.task.state is ResearchTaskState.CANCELLED
    assert cancelled.task.revision == 1
    assert repeated.disposition is CancellationDisposition.TOO_LATE
    assert canonical_bytes(repeated.task.terminal_receipt) == receipt_bytes
    assert fixture.executor.attempts == []


def test_running_cancellation_wins_cutoff_and_different_id_is_rejected(tmp_path):
    entered = threading.Event()
    release = threading.Event()

    class BlockingExecutor:
        def execute(self, attempt):
            entered.set()
            assert release.wait(5)
            return outcome()

    fixture = make_fixture(tmp_path)
    fixture.provider._executor = BlockingExecutor()
    started = fixture.provider.start_research_task(fixture.request())
    result = []
    worker = threading.Thread(
        target=lambda: result.append(
            fixture.provider.run_queued_task(started.task.task_id)
        )
    )
    worker.start()
    assert entered.wait(5)
    cancellation = CancelResearchTaskRequest(
        started.task.challenge_key, started.task.task_id, "cancel-fixture-0002"
    )
    accepted = fixture.provider.cancel_research_task(cancellation)
    assert accepted.task.state is ResearchTaskState.CANCEL_REQUESTED
    assert accepted.task.revision == 2
    with pytest.raises(ResearchTaskProviderError) as error:
        fixture.provider.cancel_research_task(
            replace(cancellation, cancellation_id="cancel-fixture-0003")
        )
    assert error.value.code is ResearchServiceErrorCode.INVALID_TASK_TRANSITION
    same = fixture.provider.cancel_research_task(cancellation)
    assert same.disposition is CancellationDisposition.ALREADY_ACCEPTED
    release.set()
    worker.join(5)
    assert result[0].state is ResearchTaskState.CANCELLED
    assert result[0].revision == 3


def test_terminal_commit_wins_late_cancellation(tmp_path):
    fixture = make_fixture(tmp_path)
    started = fixture.provider.start_research_task(fixture.request())
    terminal = fixture.provider.run_queued_task(started.task.task_id)

    cancelled = fixture.provider.cancel_research_task(
        CancelResearchTaskRequest(
            started.task.challenge_key,
            started.task.task_id,
            "cancel-fixture-0004",
        )
    )
    assert cancelled.disposition is CancellationDisposition.TOO_LATE
    assert canonical_bytes(cancelled.task) == canonical_bytes(terminal)


def test_forbidden_provider_transition_has_no_mutation(tmp_path):
    fixture = make_fixture(tmp_path)
    started = fixture.provider.start_research_task(fixture.request())
    task = fixture.provider._tasks[started.task.task_id]
    before = fixture.provider._view(task)

    with pytest.raises(ResearchTaskProviderError) as error:
        fixture.provider._transition(task, ResearchTaskState.SUCCEEDED)

    assert error.value.code is ResearchServiceErrorCode.INVALID_TASK_TRANSITION
    assert fixture.provider._view(task) == before


def test_provider_retries_three_attempts_with_unchanged_pins(tmp_path):
    failures = [
        InfrastructureExecutionFailure(
            InfrastructureFailureClass.DEPENDENCY_UNAVAILABLE, True
        ),
        InfrastructureExecutionFailure(InfrastructureFailureClass.WORKER_LOST, True),
        outcome(),
    ]
    fixture = make_fixture(tmp_path, outcomes=failures)
    started = fixture.provider.start_research_task(fixture.request())

    terminal = fixture.provider.run_queued_task(started.task.task_id)
    attempts = fixture.executor.attempts
    assert terminal.state is ResearchTaskState.SUCCEEDED
    assert [attempt.attempt for attempt in attempts] == [1, 2, 3]
    assert len({attempt.task_id for attempt in attempts}) == 1
    assert all(
        attempt.resolved_strategies == attempts[0].resolved_strategies
        for attempt in attempts
    )
    assert (
        fixture.provider.get_experiment_record(
            started.task.task_id
        ).execution_identity.attempts
        == 3
    )


def test_exhausted_infrastructure_is_not_negative_scientific_evidence(tmp_path):
    fixture = make_fixture(tmp_path)
    observed = ObservedResourceReceiptRef(
        fixture.domain.compile_fixture.key, content_digest=digest("7")
    )
    failure = InfrastructureExecutionFailure(
        InfrastructureFailureClass.EXECUTION_TIMEOUT, True, observed
    )
    fixture.executor.outcomes = [failure, failure, failure]
    started = fixture.provider.start_research_task(fixture.request())

    terminal = fixture.provider.run_queued_task(started.task.task_id)
    assert terminal.state is ResearchTaskState.FAILED_INFRA
    assert terminal.terminal_receipt.public_findings == ()
    assert terminal.terminal_receipt.infrastructure_failure_class is (
        InfrastructureFailureClass.EXECUTION_TIMEOUT
    )
    assert terminal.terminal_receipt.observed_resource_receipt_ref == observed
    with pytest.raises(ResearchTaskProviderError):
        fixture.provider.get_experiment_record(started.task.task_id)


def test_queue_loss_commits_one_typed_terminal_receipt(tmp_path):
    class LostQueue:
        def __init__(self):
            self.calls = 0

        def enqueue(self, task_id):
            self.calls += 1
            raise RuntimeError("private queue detail")

    queue = LostQueue()
    fixture = make_fixture(tmp_path, queue=queue)
    started = fixture.provider.start_research_task(fixture.request())

    assert started.created is True
    assert started.task.state is ResearchTaskState.FAILED_INFRA
    assert started.task.terminal_receipt.infrastructure_failure_class is (
        InfrastructureFailureClass.QUEUE_LOST
    )
    assert queue.calls == 1
    assert b"private queue detail" not in canonical_bytes(started.task)
    duplicate = fixture.provider.start_research_task(fixture.request())
    assert duplicate.created is False
    assert queue.calls == 1


def test_active_prior_is_resolved_inside_start_and_remains_pinned(tmp_path):
    fixture = make_fixture(tmp_path)
    key = fixture.domain.compile_fixture.key
    channel_ref = PriorChannelRef(key, PriorChannel.PUBLIC, content_digest=digest("1"))
    fixture.provider._manifests.manifest = replace(
        fixture.provider._manifests.manifest,
        prior_availability=AvailablePriorAvailability(
            channel_ref,
            PriorPolicyBundleRef(key, content_digest=digest("2")),
        ),
    )
    first = PriorResolution(
        PriorIndexSnapshotRef(key, PriorChannel.PUBLIC, 1, content_digest=digest("3")),
        PriorPackRef(key, PriorChannel.PUBLIC, 1, digest("4")),
    )
    second = PriorResolution(
        PriorIndexSnapshotRef(key, PriorChannel.PUBLIC, 2, content_digest=digest("5")),
        PriorPackRef(key, PriorChannel.PUBLIC, 2, digest("6")),
    )

    class MovingPrior:
        current = first

        def resolve_prior(self, request):
            return self.current

    resolver = MovingPrior()
    fixture.provider._priors = resolver
    request = replace(
        fixture.request(), prior_selector=ActivePriorSelector(PriorChannel.PUBLIC)
    )
    started = fixture.provider.start_research_task(request)
    resolver.current = second
    terminal = fixture.provider.run_queued_task(started.task.task_id)
    record = fixture.provider.get_experiment_record(started.task.task_id)

    assert (
        terminal.immutable_bindings.prior_index_snapshot_ref == first.index_snapshot_ref
    )
    assert terminal.immutable_bindings.prior_pack_ref == first.prior_pack_ref
    assert record.prior_resolution == first


def test_scientific_negative_is_retained_on_operational_success(tmp_path):
    fixture = make_fixture(
        tmp_path,
        outcomes=[outcome(failure=ResearchFailureCategory.REFERENCE)],
    )
    started = fixture.provider.start_research_task(fixture.request())
    terminal = fixture.provider.run_queued_task(started.task.task_id)
    record = fixture.provider.get_experiment_record(started.task.task_id)

    assert terminal.state is ResearchTaskState.SUCCEEDED
    assert record.scientific_failure_category is ResearchFailureCategory.REFERENCE
    assert terminal.terminal_receipt.public_findings


def test_receipt_uses_allowlist_and_cannot_leak_private_aliases(tmp_path):
    fixture = make_fixture(
        tmp_path, outcomes=[outcome(finding_ids=("not_registered",))]
    )
    started = fixture.provider.start_research_task(fixture.request())
    terminal = fixture.provider.run_queued_task(started.task.task_id)

    assert terminal.state is ResearchTaskState.FAILED_INFRA
    encoded = canonical_bytes(terminal.terminal_receipt)
    assert b"not_registered" not in encoded
    assert b"aggregate_outcome" not in encoded
    assert b"research_evidence_origin" not in encoded


def test_worker_exception_text_is_not_retained_or_disclosed(tmp_path):
    class ExplodingExecutor:
        def execute(self, attempt):
            raise RuntimeError("hidden_seed=do-not-disclose")

    fixture = make_fixture(tmp_path)
    fixture.provider._executor = ExplodingExecutor()
    started = fixture.provider.start_research_task(fixture.request())
    terminal = fixture.provider.run_queued_task(started.task.task_id)

    assert terminal.state is ResearchTaskState.FAILED_INFRA
    assert terminal.terminal_receipt.infrastructure_failure_class is (
        InfrastructureFailureClass.INTERNAL
    )
    assert b"hidden_seed" not in canonical_bytes(terminal)


def test_missing_rights_excludes_learned_aggregation(tmp_path):
    local = make_fixture(tmp_path / "local")
    local_task = local.provider.start_research_task(local.request())
    local.provider.run_queued_task(local_task.task.task_id)
    assert local.provider.records_authorized_for_learned_aggregation() == ()

    authorized = RetentionReuseBinding(
        ResearchRetentionScope.LEARNED_AGGREGATION_AUTHORIZED,
        private_ref("rights_authorization"),
    )
    allowed = make_fixture(
        tmp_path / "allowed", outcomes=[outcome(retention=authorized)]
    )
    allowed_task = allowed.provider.start_research_task(allowed.request())
    allowed.provider.run_queued_task(allowed_task.task.task_id)
    assert allowed.provider.records_authorized_for_learned_aggregation() == (
        allowed.provider.get_experiment_record(allowed_task.task.task_id),
    )
    with pytest.raises(ValueError):
        RetentionReuseBinding(ResearchRetentionScope.LEARNED_AGGREGATION_AUTHORIZED)


def test_evidence_quality_requires_explicit_science_authority(tmp_path):
    quality = EvidenceQualityMetadata(provenance_complete=True)
    with pytest.raises(ValueError):
        outcome(evidence_quality=quality)

    authorized = outcome(
        evidence_quality=quality,
        evidence_quality_authorization_ref=private_ref(
            "evidence_quality_authorization"
        ),
    )
    fixture = make_fixture(tmp_path, outcomes=[authorized])
    started = fixture.provider.start_research_task(fixture.request())
    terminal = fixture.provider.run_queued_task(started.task.task_id)

    assert terminal.state is ResearchTaskState.SUCCEEDED
    assert (
        fixture.provider.get_experiment_record(
            started.task.task_id
        ).evidence_context.evidence_quality
        == quality
    )


def test_mms_cannot_be_relabelled_or_bound_to_target_population(tmp_path):
    campaign = private_ref("verification_campaign")
    verified = outcome(
        role=EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION,
        evidence_class=ResearchEvidenceClass.MMS_VERIFICATION,
        finding_ids=(),
        verification_campaign_ref=campaign,
    )
    fixture = make_fixture(tmp_path, outcomes=[verified])
    started = fixture.provider.start_research_task(fixture.request())
    fixture.provider.run_queued_task(started.task.task_id)
    record = fixture.provider.get_experiment_record(started.task.task_id)
    assert record.evidence_class is ResearchEvidenceClass.MMS_VERIFICATION
    assert record.evidence_context.population_ref is None

    with pytest.raises(ValueError):
        outcome(
            role=EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION,
            evidence_class=ResearchEvidenceClass.PRACTICE_NON_AUTHORITATIVE,
            verification_campaign_ref=campaign,
        )
    with pytest.raises(ValueError):
        outcome(
            role=EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION,
            evidence_class=ResearchEvidenceClass.MMS_VERIFICATION,
            verification_campaign_ref=campaign,
            population_ref=private_ref("target_population"),
        )


def test_epistemic_status_never_defaults_or_self_promotes(tmp_path):
    assert "OFFICIAL_EVIDENCE" not in ResearchEvidenceClass.__members__
    fixture = make_fixture(
        tmp_path,
        outcomes=[outcome(epistemic_status=EpistemicType.EXPERIMENTALLY_SUPPORTED)],
    )
    started = fixture.provider.start_research_task(fixture.request())
    terminal = fixture.provider.run_queued_task(started.task.task_id)

    assert terminal.state is ResearchTaskState.FAILED_INFRA
    with pytest.raises(ResearchTaskProviderError):
        fixture.provider.get_experiment_record(started.task.task_id)


def test_mutating_request_after_start_cannot_change_pins(tmp_path):
    fixture = make_fixture(tmp_path)
    request = fixture.request()
    started = fixture.provider.start_research_task(request)
    original = started.task.immutable_bindings
    request.task_spec.intervention_strategy["parameters"]["fixture_sampling_level"] = 1

    terminal = fixture.provider.run_queued_task(started.task.task_id)
    assert terminal.immutable_bindings == original
    with pytest.raises(ResearchTaskProviderError) as error:
        fixture.provider.start_research_task(request)
    assert error.value.code is ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
