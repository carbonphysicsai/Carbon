"""C-10 linked re-execution, disagreement, quarantine, and recovery tests."""

from __future__ import annotations

import dataclasses
import json

import pytest
from c10_fixtures import complete_c07, make_fixture, provenance, resources, sha

from carbon import audit
from carbon.execution import (
    DurableExecutionQueue,
    ExecutionCode,
    ExecutionFailure,
    ExecutionRelationKind,
    ExecutionStage,
    PartialWorkRef,
)
from carbon.orchestration import (
    DevelopmentEvaluationOrchestrator,
    OperationalDisposition,
    ResultOwnerRefs,
)
from carbon.reexecution.model import (
    ComparisonDisposition,
    JournalState,
    ReexecutionCode,
    ReexecutionFailure,
    RequestWriteDisposition,
    ResourceObservationState,
)
from carbon.reexecution.report import (
    public_projection,
    reviewer_projection,
    write_reexecution_report_bundle,
)
from carbon.reexecution.service import DevelopmentReexecutionService
from carbon.reexecution.store import ReexecutionJournal


def _service(fixture):
    journal = ReexecutionJournal(fixture.root / "c10.sqlite3")
    return journal, DevelopmentReexecutionService(
        fixture.orchestrator, fixture.ledger, journal
    )


def _complete_pair(fixture, service):
    service.launch(fixture.launch_intent)
    handle = service.bind_request(fixture.linked_request)
    result = complete_c07(
        fixture,
        fixture.reexecution_request,
        receipt_id="c10-reexecution-receipt",
        handle=handle,
    )
    outcome = service.associate_completed(
        fixture.linked_request,
        result,
        primary_provenance=provenance("primary"),
        reexecution_provenance=provenance("reexecution"),
        primary_resources=resources(),
        reexecution_resources=resources(),
        verified_at_micros=8_000,
    )
    return result, outcome


def test_fresh_execution_agrees_without_scientific_or_economic_authority(
    tmp_path,
) -> None:
    fixture = make_fixture(tmp_path)
    journal, service = _service(fixture)
    result, outcome = _complete_pair(fixture, service)

    assert outcome.disposition is ComparisonDisposition.EXACT_BYTES_AGREE_DEVELOPMENT
    assert outcome.different_scientific_fields == ()
    assert (
        fixture.primary_request.evidence.reconstruction_attempt_digests
        != fixture.reexecution_request.evidence.reconstruction_attempt_digests
    )
    assert outcome.quarantine_required is False
    assert outcome.primary_receipt != outcome.reexecution_receipt
    assert result.account.attempt_number == 2
    assert fixture.primary_result.account.attempt_number == 1
    relation = fixture.queue.relation(fixture.reexecution_request.execution.ref)
    assert relation is not None
    assert relation.kind is ExecutionRelationKind.REEXECUTION_OF
    assert relation.source == fixture.primary_request.execution.ref
    assert fixture.ledger.checkpoint().receipt_count == 2
    assert journal.status(fixture.launch_intent).state is JournalState.COMPARED
    assert set(public_projection(outcome)["authority"].values()) == {False}
    assert reviewer_projection(outcome)["independence"] == {
        "administratively_independent": False,
        "distinct_administrator_trust_domain_identities": False,
        "fresh_execution_identity": True,
        "fresh_worker_launches": True,
        "same_host": True,
        "separate_scratch": True,
    }


def test_reexecution_admission_is_not_an_ordinary_retry_or_second_audit(
    tmp_path,
) -> None:
    fixture = make_fixture(tmp_path)
    with pytest.raises(ExecutionFailure) as ordinary_retry:
        fixture.queue.admit(fixture.reexecution_request.execution)
    assert ordinary_retry.value.code is ExecutionCode.CONFLICT

    _, service = _service(fixture)
    service.launch(fixture.launch_intent)
    duplicate = dataclasses.replace(
        fixture.reexecution_request.execution,
        handle=dataclasses.replace(
            fixture.reexecution_request.execution.handle,
            attempt_number=3,
        ),
    )
    with pytest.raises(ExecutionFailure) as second_audit:
        fixture.queue.admit_reexecution(
            duplicate,
            source=fixture.primary_request.execution.ref,
        )
    assert second_audit.value.code is ExecutionCode.CONFLICT


def test_exact_request_and_outcome_replay_create_no_new_execution_effect(
    tmp_path,
) -> None:
    fixture = make_fixture(tmp_path)
    journal, service = _service(fixture)
    result, outcome = _complete_pair(fixture, service)
    disposition, view = service.request(fixture.linked_request)
    assert disposition is RequestWriteDisposition.ALREADY_PRESENT
    assert view.state is JournalState.COMPARED
    with pytest.raises(ReexecutionFailure) as launch:
        service.launch(fixture.launch_intent)
    assert launch.value.code is ReexecutionCode.RECONCILIATION_REQUIRED
    replay = service.associate_completed(
        fixture.linked_request,
        result,
        primary_provenance=provenance("primary"),
        reexecution_provenance=provenance("reexecution"),
        primary_resources=resources(),
        reexecution_resources=resources(),
        verified_at_micros=8_000,
    )
    assert replay == outcome
    assert fixture.ledger.checkpoint().receipt_count == 2
    assert (
        journal.status(fixture.launch_intent).outcome_digest == outcome.outcome_digest
    )


def test_changed_bytes_remain_unresolved_and_quarantine_without_tolerance(
    tmp_path,
) -> None:
    fixture = make_fixture(tmp_path, output_suffix="different")
    journal, service = _service(fixture)
    _, outcome = _complete_pair(fixture, service)
    assert outcome.disposition is ComparisonDisposition.DIFFERENT_BYTES_UNRESOLVED
    assert outcome.different_scientific_fields == (
        "reconstruction_replica_0",
        "reconstruction_replica_1",
        "reconstruction_replica_2",
        "prediction",
        "reference",
        "measurement",
    )
    assert outcome.comparison_policy_qualified is False
    assert outcome.scientific_resolution is False
    assert outcome.quarantine_required is True
    assert journal.status(fixture.launch_intent).state is JournalState.QUARANTINED


def test_material_case_policy_and_request_replay_mismatch_fail_before_dispatch(
    tmp_path,
) -> None:
    fixture = make_fixture(tmp_path)
    journal, service = _service(fixture)
    service.launch(fixture.launch_intent)
    service.request(fixture.linked_request)
    changed_id = dataclasses.replace(fixture.linked_request, worker_id="other-worker")
    with pytest.raises(ReexecutionFailure) as replay:
        service.request(changed_id)
    assert replay.value.code is ReexecutionCode.CONFLICT

    changed_case = dataclasses.replace(
        fixture.reexecution_request, case_manifest_digest=sha("other-case")
    )
    with pytest.raises(ReexecutionFailure) as case:
        dataclasses.replace(fixture.linked_request, reexecution_request=changed_case)
    assert case.value.code is ReexecutionCode.CONFLICT

    changed_execution = dataclasses.replace(
        fixture.reexecution_request.execution,
        reconstruction_policy_digest=sha("other-policy"),
    )
    changed_policy = dataclasses.replace(
        fixture.reexecution_request, execution=changed_execution
    )
    with pytest.raises(ReexecutionFailure) as policy:
        dataclasses.replace(fixture.linked_request, reexecution_request=changed_policy)
    assert policy.value.code is ReexecutionCode.CONFLICT
    assert journal.status(fixture.launch_intent).state is JournalState.RUNNING


@pytest.mark.parametrize("which", ("primary", "reexecution"))
def test_missing_or_revoked_receipt_evidence_quarantines(tmp_path, which) -> None:
    fixture = make_fixture(tmp_path)
    journal, service = _service(fixture)
    service.launch(fixture.launch_intent)
    handle = service.bind_request(fixture.linked_request)
    result = complete_c07(
        fixture,
        fixture.reexecution_request,
        receipt_id="c10-reexecution-receipt",
        handle=handle,
    )
    target = (
        fixture.primary_result.ledger_reference
        if which == "primary"
        else result.ledger_reference
    )
    fixture.ledger.revoke(target.receipt_id, sha(f"revoked-{which}"))
    outcome = service.associate_completed(
        fixture.linked_request,
        result,
        primary_provenance=provenance("primary"),
        reexecution_provenance=provenance("reexecution"),
        primary_resources=resources(),
        reexecution_resources=resources(),
        verified_at_micros=8_000,
    )
    expected = (
        ComparisonDisposition.PRIMARY_EVIDENCE_UNAVAILABLE
        if which == "primary"
        else ComparisonDisposition.REEXECUTION_EVIDENCE_UNAVAILABLE
    )
    assert outcome.disposition is expected
    assert outcome.quarantine_required
    assert journal.status(fixture.launch_intent).state is JournalState.QUARANTINED


@pytest.mark.parametrize(
    ("operational", "expected"),
    (
        (
            OperationalDisposition.CANCELLED,
            ComparisonDisposition.REEXECUTION_CANCELLED,
        ),
        (
            OperationalDisposition.FAILED_INFRASTRUCTURE,
            ComparisonDisposition.REEXECUTION_INFRASTRUCTURE_UNAVAILABLE,
        ),
        (
            OperationalDisposition.FAILED_RECONSTRUCTION,
            ComparisonDisposition.REEXECUTION_FAILED,
        ),
        (
            OperationalDisposition.INDETERMINATE,
            ComparisonDisposition.REEXECUTION_UNRESOLVED,
        ),
    ),
)
def test_terminal_outcomes_stay_distinct_and_non_scientific(
    tmp_path, operational, expected
) -> None:
    fixture = make_fixture(tmp_path)
    journal, service = _service(fixture)
    service.launch(fixture.launch_intent)
    handle = service.bind_request(fixture.linked_request)
    fixture.queue.record_partial(
        handle.claimed.claim,
        PartialWorkRef(
            ExecutionStage.GENERATOR,
            "case-manifest-" + fixture.reexecution_request.case_manifest_digest[7:39],
            fixture.reexecution_request.case_manifest_digest,
        ),
    )
    account = fixture.orchestrator.conclude_without_receipt(
        handle,
        disposition=operational,
        failed_stage=ExecutionStage.RECONSTRUCTION,
        failure_evidence_ref="c10-terminal-evidence",
        failure_evidence_digest=sha(operational.value),
        result_owners=ResultOwnerRefs(
            "c10-terminal-card", "c10-terminal-transcript", sha("terminal-transcript")
        ),
        started_at_micros=4_000,
        finished_at_micros=4_500,
    )
    outcome = service.associate_terminal(
        fixture.linked_request,
        account,
        primary_provenance=provenance("primary"),
        reexecution_provenance=provenance("reexecution", launches=1),
        primary_resources=resources(),
        reexecution_resources=resources(ResourceObservationState.PARTIAL),
        failure_evidence_digest=sha(f"terminal-{operational.value}"),
    )
    assert outcome.disposition is expected
    assert outcome.reexecution_receipt is None
    assert outcome.quarantine_required
    assert journal.status(fixture.launch_intent).state is JournalState.QUARANTINED


def test_unavailable_worker_retains_budget_and_no_replacement(tmp_path) -> None:
    fixture = make_fixture(tmp_path)
    journal, service = _service(fixture)
    launch = service.launch(fixture.launch_intent)
    service.request(fixture.linked_request)
    fixture.queue.fail_infrastructure(launch.claimed.claim)
    outcome = service.associate_unavailable(
        fixture.linked_request,
        primary_provenance=provenance("primary"),
        reexecution_provenance=provenance("reexecution", launches=0),
        primary_resources=resources(),
        reexecution_resources=resources(ResourceObservationState.UNAVAILABLE),
        failure_evidence_digest=sha("worker-unavailable"),
    )
    assert (
        outcome.disposition
        is ComparisonDisposition.REEXECUTION_INFRASTRUCTURE_UNAVAILABLE
    )
    assert fixture.linked_request.budget.automatic_replacements == 0
    assert journal.status(fixture.launch_intent).state is JournalState.QUARANTINED


def test_restart_resumes_same_claim_and_crash_after_result_attaches_without_reexecution(
    tmp_path,
) -> None:
    fixture = make_fixture(tmp_path)
    journal, service = _service(fixture)
    service.launch(fixture.launch_intent)
    handle = service.bind_request(fixture.linked_request)
    fixture.queue.record_partial(
        handle.claimed.claim,
        PartialWorkRef(
            ExecutionStage.GENERATOR,
            "case-manifest-" + fixture.reexecution_request.case_manifest_digest[7:39],
            fixture.reexecution_request.case_manifest_digest,
        ),
    )

    restarted_queue = DurableExecutionQueue(fixture.queue.path)
    restarted_ledger = audit.DevelopmentEvidenceLedger(
        fixture.ledger.path, (fixture.signer.verification_key,)
    )
    restarted_orchestrator = DevelopmentEvaluationOrchestrator(
        restarted_queue, restarted_ledger
    )
    restarted_journal = ReexecutionJournal(journal.path)
    restarted = DevelopmentReexecutionService(
        restarted_orchestrator, restarted_ledger, restarted_journal
    )
    assert (
        restarted_journal.status(fixture.launch_intent).state
        is JournalState.RECONCILIATION_REQUIRED
    )
    resumed = restarted.resume(fixture.launch_intent)
    fixture.queue = restarted_queue
    fixture.ledger = restarted_ledger
    fixture.orchestrator = restarted_orchestrator
    result = complete_c07(
        fixture,
        fixture.reexecution_request,
        receipt_id="c10-reexecution-receipt",
        handle=restarted.bind_request(fixture.linked_request),
    )

    # Simulate controller loss after C-07 persisted the result but before C-10
    # associated it. Reopening C-10 requires explicit completed attachment.
    after_result_journal = ReexecutionJournal(restarted_journal.path)
    after_result_service = DevelopmentReexecutionService(
        restarted_orchestrator, restarted_ledger, after_result_journal
    )
    attached = after_result_service.attach_completed(fixture.linked_request)
    assert attached.claimed.claim == resumed.claimed.claim
    outcome = after_result_service.associate_completed(
        fixture.linked_request,
        result,
        primary_provenance=provenance("primary"),
        reexecution_provenance=provenance("reexecution"),
        primary_resources=resources(),
        reexecution_resources=resources(),
        verified_at_micros=8_000,
    )
    assert outcome.disposition is ComparisonDisposition.EXACT_BYTES_AGREE_DEVELOPMENT
    assert restarted_ledger.checkpoint().receipt_count == 2


def test_restart_after_c01_claim_before_c10_running_reconciles_same_claim(
    tmp_path,
) -> None:
    fixture = make_fixture(tmp_path)
    journal, service = _service(fixture)
    service.prepare(fixture.launch_intent)
    fixture.queue.admit_reexecution(
        fixture.launch_intent.reexecution_execution,
        source=fixture.primary_request.execution.ref,
    )
    claimed = fixture.queue.claim(
        fixture.launch_intent.reexecution_execution.ref,
        fixture.launch_intent.worker_id,
        claim_id=fixture.launch_intent.claim_id,
    )
    fixture.queue.mark_running(claimed.claim)

    restarted_queue = DurableExecutionQueue(fixture.queue.path)
    restarted_orchestrator = DevelopmentEvaluationOrchestrator(
        restarted_queue, fixture.ledger
    )
    restarted = DevelopmentReexecutionService(
        restarted_orchestrator, fixture.ledger, ReexecutionJournal(journal.path)
    )
    resumed = restarted.resume(fixture.launch_intent)
    assert resumed.claimed.claim == claimed.claim
    assert restarted.journal.status(fixture.launch_intent).state is JournalState.RUNNING


def test_conflicting_outcome_replay_and_journal_tamper_fail_closed(tmp_path) -> None:
    fixture = make_fixture(tmp_path)
    journal, service = _service(fixture)
    result, _ = _complete_pair(fixture, service)
    changed_primary = dataclasses.replace(provenance("primary"), host_id="other-host")
    with pytest.raises(ReexecutionFailure) as conflict:
        service.associate_completed(
            fixture.linked_request,
            result,
            primary_provenance=changed_primary,
            reexecution_provenance=provenance("reexecution"),
            primary_resources=resources(),
            reexecution_resources=resources(),
            verified_at_micros=8_000,
        )
    assert conflict.value.code is ReexecutionCode.CONFLICT

    import sqlite3

    database = sqlite3.connect(journal.path)
    database.execute(
        "UPDATE c10_event_v1 SET body_digest=? WHERE sequence=1", (sha("tamper"),)
    )
    database.commit()
    database.close()
    with pytest.raises(ReexecutionFailure) as tamper:
        ReexecutionJournal(journal.path)
    assert tamper.value.code is ReexecutionCode.STORE


def test_report_bundle_is_idempotent_bounded_and_keeps_private_dependencies_private(
    tmp_path,
) -> None:
    fixture = make_fixture(tmp_path)
    _, service = _service(fixture)
    _, outcome = _complete_pair(fixture, service)
    root = (tmp_path / "report").resolve()
    paths = write_reexecution_report_bundle(root, outcome)
    assert write_reexecution_report_bundle(root, outcome) == paths
    private = json.loads(paths[0].read_text(encoding="ascii"))
    reviewer = json.loads(paths[1].read_text(encoding="ascii"))
    public = json.loads(paths[2].read_text(encoding="ascii"))
    assert private["shared_dependency_digests"]
    assert reviewer["shared_dependency_digests"]
    assert "shared_dependency_digests" not in public
    assert "administrator_trust_domain" not in json.dumps(public)
    assert set(public["authority"].values()) == {False}
