"""C-EP1 durable DEVELOPMENT evaluation-pack integration and attack probes."""

from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from test_c01_durable_execution import _binding
from test_net3_candidates import setup, signed
from test_traineval_stub import _a7_service, _provider, _service, _strategy

from carbon.candidates.model import CandidateFailure
from carbon.evaluation_packs import (
    DevelopmentEvaluationPackLedger,
    DevelopmentEvaluationPackService,
    PackAttemptBinding,
    PackCode,
    PackFailure,
    PackState,
    PackWriteDisposition,
)
from carbon.execution import DurableExecutionQueue, ExecutionAttemptRef, ExecutionState
from carbon.fees import AdmissionKind, SubmissionId, SubmissionStateError
from carbon.traineval import service as traineval_service_module
from carbon.traineval.model import (
    InfrastructureCause,
    InfrastructureFailedRun,
    InfrastructureRetryClass,
)
from carbon.transport.gateway import requester_for_receipt

PASSING_FIXTURE = b"NET-3 synthetic passing fixture 2"


def _pack_service(tmp_path, journal, *, ids=()):
    supplied = iter(ids)
    ledger = DevelopmentEvaluationPackLedger(
        journal,
        id_factory=lambda: next(supplied, uuid.uuid4()),
    )
    submissions = _a7_service(tmp_path / "science")
    submission_sequence = iter(
        uuid.UUID(f"00000000-0000-4000-8000-{index:012d}") for index in range(1, 10_001)
    )
    submissions._store.uuid_factory = lambda: next(submission_sequence)
    service = DevelopmentEvaluationPackService(
        ledger,
        submissions,
        _service(provider=_provider(PASSING_FIXTURE)),
        DurableExecutionQueue(tmp_path / "execution.sqlite3"),
    )
    return ledger, service


def test_distinct_jobs_get_distinct_child_packs_and_fixture_material(
    tmp_path, monkeypatch
) -> None:
    journal, gate = setup(tmp_path)
    first = journal.commit(*signed(gate, 1))
    second = journal.commit(*signed(gate, 2, strategy=_strategy(parameters={"n": 3})))
    ledger, service = _pack_service(
        tmp_path,
        journal,
        ids=(
            uuid.UUID("00000000-0000-0000-0000-000000000001"),
            uuid.UUID("00000000-0000-0000-0000-000000000002"),
        ),
    )
    derived_seeds = []
    original_derive = traineval_service_module.derive_fixture_official_seed

    def derive_spy(context, domain, role, draw_index):
        value = original_derive(context, domain, role, draw_index)
        derived_seeds.append(value.as_backend_bytes())
        return value

    monkeypatch.setattr(
        traineval_service_module, "derive_fixture_official_seed", derive_spy
    )

    first_card = service.evaluate(first)
    second_card = service.evaluate(second)
    first_pack = ledger.internal_assignment(first).pack
    second_pack = ledger.internal_assignment(second).pack

    assert first_pack.parent_context_id == second_pack.parent_context_id
    assert first_pack.parent_context_id == journal.context.identity
    assert first_pack.identity != second_pack.identity
    assert (
        first_pack.evaluation_binding_bytes() != second_pack.evaluation_binding_bytes()
    )
    assert first_card.result_id != second_card.result_id
    assert len(derived_seeds) == 6
    assert all(
        first_seed != second_seed
        for first_seed, second_seed in zip(
            derived_seeds[:3], derived_seeds[3:], strict=True
        )
    )
    assert ledger.trace_counts() == {
        "ATTEMPT_BOUND": 2,
        "FIXTURE_EXECUTION": 2,
        "PACK_ASSIGNED": 2,
        "PACK_CLOSED": 2,
        "RESULT_RECORDED": 2,
        "SUMMARY_DELIVERED": 2,
    }


def test_copy_lost_response_repeated_read_and_restart_reuse_one_pack(tmp_path) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate, 1))
    copied = journal.commit(*signed(gate, 2, hotkey="validator"))
    assert copied == ref
    ledger, service = _pack_service(
        tmp_path,
        journal,
        ids=(uuid.UUID("00000000-0000-0000-0000-000000000003"),),
    )
    card = service.evaluate(ref)
    assignment = ledger.internal_assignment(ref)
    assert service.evaluate(copied) == card
    assert service.read_summary(ref) == card

    reopened = DevelopmentEvaluationPackLedger(journal)
    assert reopened.internal_assignment(ref) == assignment
    assert reopened.read_summary(ref) == card
    assert reopened.trace_counts()["PACK_ASSIGNED"] == 1


def test_independent_connections_race_to_one_assignment(tmp_path) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    fixed = uuid.UUID("00000000-0000-0000-0000-000000000004")
    left = DevelopmentEvaluationPackLedger(journal, id_factory=lambda: fixed)
    right = DevelopmentEvaluationPackLedger(journal, id_factory=lambda: fixed)

    def assign(owner):
        return owner.assign(ref)

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(assign, (left, right)))
    assert sorted(value[1].value for value in results) == [
        PackWriteDisposition.ALREADY_PRESENT.value,
        PackWriteDisposition.INSERTED.value,
    ]
    assert results[0][0] == results[1][0]


def test_assignment_is_pre_draw_and_opening_a_connection_is_not_recovery(
    tmp_path,
) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger = DevelopmentEvaluationPackLedger(journal)
    assignment, _ = ledger.assign(ref)
    assert ledger.status(ref).state is PackState.ASSIGNED

    attached = DevelopmentEvaluationPackLedger(journal)
    assert attached.status(ref).state is PackState.ASSIGNED
    assert attached.internal_assignment(ref) == assignment
    with pytest.raises(PackFailure) as caught:
        attached.read_summary(ref)
    assert caught.value.code is PackCode.STATE

    attached.require_reconciliation(ref)
    assert attached.status(ref).state is PackState.RECONCILIATION_REQUIRED
    replay, disposition = attached.assign(ref)
    assert replay == assignment
    assert disposition is PackWriteDisposition.ALREADY_PRESENT


def test_crash_before_attempt_binding_preserves_pack_and_requires_reconciliation(
    tmp_path, monkeypatch
) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger, service = _pack_service(tmp_path, journal)
    original = ledger.candidate_inputs

    def crash(_assignment):
        raise RuntimeError("simulated crash after assignment")

    monkeypatch.setattr(ledger, "candidate_inputs", crash)
    with pytest.raises(PackFailure) as caught:
        service.evaluate(ref)
    assert caught.value.code is PackCode.INDETERMINATE
    retained = ledger.internal_assignment(ref)
    assert ledger.status(ref).state is PackState.RECONCILIATION_REQUIRED
    monkeypatch.setattr(ledger, "candidate_inputs", original)
    reopened = DevelopmentEvaluationPackLedger(journal)
    replay, disposition = reopened.assign(ref)
    assert replay == retained
    assert disposition is PackWriteDisposition.ALREADY_PRESENT


def test_crash_after_fixture_materialization_never_redraws(
    tmp_path, monkeypatch
) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger, service = _pack_service(tmp_path, journal)
    original = traineval_service_module.FixtureTrainEvalService.run_fixture

    def crash_after_run(owner, envelope):
        original(owner, envelope)
        raise RuntimeError("simulated crash after fixture materialization")

    monkeypatch.setattr(
        traineval_service_module.FixtureTrainEvalService,
        "run_fixture",
        crash_after_run,
    )
    with pytest.raises(PackFailure) as caught:
        service.evaluate(ref)
    assert caught.value.code is PackCode.INDETERMINATE
    retained = ledger.internal_assignment(ref)
    assert ledger.status(ref).state is PackState.RECONCILIATION_REQUIRED
    restarted = DurableExecutionQueue(service.executions.path)
    assert restarted.claim_next("replacement-worker") is None
    assert DevelopmentEvaluationPackLedger(journal).internal_assignment(ref) == retained


def test_worker_attach_does_not_trigger_owner_restart_reconciliation(tmp_path) -> None:
    path = tmp_path / "execution.sqlite3"
    owner = DurableExecutionQueue(path)
    binding = _binding(kind=AdmissionKind.FIXTURE)
    owner.admit(binding)
    claimed = owner.claim_next("worker", claim_id="claim")
    assert claimed is not None

    attached = DurableExecutionQueue.attach(path)
    assert (
        attached.status(binding.ref, binding.requester_identity).state
        is ExecutionState.DISPATCHING
    )
    restarted_owner = DurableExecutionQueue(path)
    assert (
        restarted_owner.status(binding.ref, binding.requester_identity).state
        is ExecutionState.RECONCILIATION_REQUIRED
    )


def test_wrong_pack_binding_rejects_before_attempt_persistence(tmp_path) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger = DevelopmentEvaluationPackLedger(journal)
    assignment, _ = ledger.assign(ref)
    wrong = _binding(kind=AdmissionKind.FIXTURE)
    with pytest.raises(PackFailure) as caught:
        PackAttemptBinding(
            assignment,
            wrong,
            "0" * 64,
            "1" * 64,
        )
    assert caught.value.code is PackCode.CONFLICT
    assert ledger.status(ref).state is PackState.ASSIGNED

    with pytest.raises(PackFailure) as caught:
        ledger.close(
            assignment,
            DurableExecutionQueue(tmp_path / "empty-execution.sqlite3"),
            wrong.requester_identity,
        )
    assert caught.value.code is PackCode.STATE


def test_crash_after_closure_reconciles_idempotent_summary_delivery(
    tmp_path, monkeypatch
) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger, service = _pack_service(tmp_path, journal)
    original = ledger.deliver_summary
    calls = 0

    def crash_once(candidate):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated crash after durable closure")
        return original(candidate)

    monkeypatch.setattr(ledger, "deliver_summary", crash_once)
    with pytest.raises(PackFailure) as caught:
        service.evaluate(ref)
    assert caught.value.code is PackCode.INDETERMINATE
    assert ledger.status(ref).state is PackState.CLOSED

    card = service.evaluate(ref)
    assert ledger.status(ref).state is PackState.SUMMARY_DELIVERED
    assert service.evaluate(ref) == card
    assert ledger.trace_counts()["SUMMARY_DELIVERED"] == 1


def test_crash_after_result_binding_closes_without_redispatch(
    tmp_path, monkeypatch
) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger, service = _pack_service(tmp_path, journal)
    original = ledger.close
    calls = 0

    def crash_once(assignment, executions, requester):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated crash after result binding")
        return original(assignment, executions, requester)

    monkeypatch.setattr(ledger, "close", crash_once)
    with pytest.raises(PackFailure) as caught:
        service.evaluate(ref)
    assert caught.value.code is PackCode.INDETERMINATE
    assert ledger.status(ref).state is PackState.RESULT_RECORDED
    submission = SubmissionId(next(iter(service.submissions._store.records)))
    receipt = journal.receipts.resolve(ledger.receipt_ref(ref))
    requester = requester_for_receipt(journal.receipts.context, receipt)
    with pytest.raises(SubmissionStateError):
        service.submissions.read_published(submission, requester)

    card = service.evaluate(ref)
    assert card == service.read_summary(ref)
    counts = ledger.trace_counts()
    assert counts["PACK_ASSIGNED"] == 1
    assert counts["ATTEMPT_BOUND"] == 1
    assert counts["RESULT_RECORDED"] == 1
    assert counts["PACK_CLOSED"] == 1


def test_infrastructure_failure_closes_incomplete_without_summary(
    tmp_path, monkeypatch
) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger, service = _pack_service(tmp_path, journal)

    def fail(_owner, envelope):
        return InfrastructureFailedRun(
            envelope.handle,
            InfrastructureRetryClass.NON_RETRYABLE,
            InfrastructureCause.CONFIGURATION_UNAVAILABLE,
        )

    monkeypatch.setattr(
        traineval_service_module.FixtureTrainEvalService, "run_fixture", fail
    )
    with pytest.raises(PackFailure) as caught:
        service.evaluate(ref)
    assert caught.value.code is PackCode.STATE
    assert ledger.status(ref).state is PackState.INCOMPLETE_CLOSED
    with pytest.raises(PackFailure) as caught:
        service.read_summary(ref)
    assert caught.value.code is PackCode.STATE


def test_retryable_infrastructure_uses_successor_attempt_and_same_pack(
    tmp_path, monkeypatch
) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger, service = _pack_service(tmp_path, journal)
    original = traineval_service_module.FixtureTrainEvalService.run_fixture
    handles = []

    def retry_once(owner, envelope):
        handles.append(envelope.handle)
        if len(handles) == 1:
            return InfrastructureFailedRun(
                envelope.handle,
                InfrastructureRetryClass.RETRYABLE,
                InfrastructureCause.EXECUTION_TIMEOUT,
            )
        return original(owner, envelope)

    monkeypatch.setattr(
        traineval_service_module.FixtureTrainEvalService, "run_fixture", retry_once
    )
    card = service.evaluate(ref)

    assert card == service.read_summary(ref)
    assert [handle.attempt_number for handle in handles] == [1, 2]
    assert handles[0].seed_pin == handles[1].seed_pin
    assert handles[0].environment_pin == handles[1].environment_pin
    with journal.receipts.transaction() as db:
        attempts = db.execute(
            "SELECT attempt_number,materialization FROM candidate_pack_attempt_v1 "
            "WHERE candidate=? ORDER BY attempt_number",
            (ref.identity,),
        ).fetchall()
        assert db.execute("SELECT count(*) FROM candidate_pack_v1").fetchone() == (1,)
    assert [attempt for attempt, _ in attempts] == [1, 2]
    first_manifest, second_manifest = (json.loads(row[1]) for row in attempts)
    for key in (
        "pack",
        "candidate",
        "submission_id",
        "artifact_digest",
        "configuration_digest",
        "evaluation_binding_digest",
    ):
        assert first_manifest[key] == second_manifest[key]
    receipt = journal.receipts.resolve(ledger.receipt_ref(ref))
    requester = requester_for_receipt(journal.receipts.context, receipt)
    submission = SubmissionId(first_manifest["submission_id"])
    assert (
        service.executions.status(ExecutionAttemptRef(submission, 1), requester).state
        is ExecutionState.RETRYABLE_INFRA
    )
    assert (
        service.executions.status(ExecutionAttemptRef(submission, 2), requester).state
        is ExecutionState.RESULT_RECORDED
    )
    counts = ledger.trace_counts()
    assert counts["PACK_ASSIGNED"] == 1
    assert counts["ATTEMPT_BOUND"] == 2
    assert counts["FIXTURE_EXECUTION"] == 2


def test_closed_pack_rejects_late_membership_and_changed_result(tmp_path) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger, service = _pack_service(tmp_path, journal)
    service.evaluate(ref)
    assignment = ledger.internal_assignment(ref)
    with pytest.raises(PackFailure) as caught:
        ledger.close_incomplete(
            assignment,
            service.executions,
            _binding(kind=AdmissionKind.FIXTURE).requester_identity,
        )
    assert caught.value.code in (PackCode.STATE, PackCode.INDETERMINATE)
    with pytest.raises(PackFailure) as caught:
        ledger.bind_attempt(
            PackAttemptBinding(
                assignment,
                _binding(kind=AdmissionKind.FIXTURE),
                "0" * 64,
                "1" * 64,
            )
        )
    assert caught.value.code in (PackCode.CONFLICT, PackCode.STATE)


def test_legacy_upgrade_preserves_candidate_identity_and_no_pack_backfill(
    tmp_path,
) -> None:
    journal, gate = setup(tmp_path)
    legacy = journal.commit(*signed(gate))
    original_state = journal.state(legacy)
    with journal.receipts.transaction() as db:
        assert db.execute("SELECT count(*) FROM candidate_v1").fetchone() == (1,)

    ledger = DevelopmentEvaluationPackLedger(journal)
    with journal.receipts.transaction() as db:
        assert db.execute("SELECT count(*) FROM candidate_pack_v1").fetchone() == (0,)
    assert journal.state(legacy) == original_state == "COMMITTED"
    assert journal.commit(*signed(gate, 2, hotkey="validator")) == legacy
    with pytest.raises(PackFailure) as caught:
        ledger.status(legacy)
    assert caught.value.code is PackCode.NOT_FOUND


def test_corrupt_binding_and_forged_authority_fail_closed(tmp_path) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger = DevelopmentEvaluationPackLedger(journal)
    ledger.assign(ref)
    with journal.receipts.transaction() as db:
        db.execute(
            "UPDATE candidate_pack_v1 SET binding_digest='forged',state='SUMMARY_DELIVERED',delivered=1 WHERE candidate=?",
            (ref.identity,),
        )
    with pytest.raises(PackFailure) as caught:
        ledger.status(ref)
    assert caught.value.code is PackCode.STORE


def test_mutated_materialization_manifest_fails_closed(tmp_path) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger, service = _pack_service(tmp_path, journal)
    service.evaluate(ref)
    with journal.receipts.transaction() as db:
        db.execute(
            "UPDATE candidate_pack_v1 SET materialization='{}' WHERE candidate=?",
            (ref.identity,),
        )
    with pytest.raises(PackFailure) as caught:
        ledger.status(ref)
    assert caught.value.code is PackCode.STORE


def test_mutated_result_association_fails_closed(tmp_path) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    ledger, service = _pack_service(tmp_path, journal)
    service.evaluate(ref)
    with journal.receipts.transaction() as db:
        db.execute(
            "UPDATE candidate_pack_v1 SET result_digest=? WHERE candidate=?",
            ("sha256:" + "0" * 64, ref.identity),
        )
    with pytest.raises(PackFailure) as caught:
        ledger.status(ref)
    assert caught.value.code is PackCode.STORE


def test_pack_result_never_enters_legacy_acceptance_reward_or_production(
    tmp_path,
) -> None:
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    _ledger, service = _pack_service(tmp_path, journal)
    card = service.evaluate(ref)
    assert card.fixture_origin is True
    assert card.eligible_for_emission is False
    assert service.status(ref).production_eligible is False
    assert service.status(ref).reward_eligible is False
    with pytest.raises(CandidateFailure, match="NOT_ACCEPTED"):
        journal.resolve_accepted_fixture(ref)
    with journal.receipts.transaction() as db:
        assert db.execute(
            "SELECT count(*) FROM candidate_reward_batch_v1 WHERE candidate=?",
            (ref.identity,),
        ).fetchone() == (0,)


def test_variant_b_c_answer_and_authority_interfaces_are_absent(tmp_path) -> None:
    journal, _ = setup(tmp_path)
    ledger = DevelopmentEvaluationPackLedger(journal)
    policy = ledger.policy
    assert policy.variant == "A_FRESH_PACK_PER_JOB"
    assert policy.summary_release == "PACK_CLOSURE"
    assert policy.sharing == "UNAVAILABLE"
    assert policy.intentional_wait == "NONE"
    assert policy.answer_publication == "UNAVAILABLE"
    assert policy.production_eligible is False
    assert policy.reward_eligible is False
    for forbidden in (
        "share_pack",
        "publish_answers",
        "admit_production",
        "set_security_approved",
        "reevaluate",
        "add_replica",
    ):
        assert not hasattr(ledger, forbidden)


def test_malformed_schema_is_an_unsupported_downgrade_not_silent_relabel(
    tmp_path,
) -> None:
    journal, _ = setup(tmp_path)
    DevelopmentEvaluationPackLedger(journal)
    with journal.receipts.transaction() as db:
        db.execute(
            "UPDATE candidate_pack_meta_v1 SET schema_version='older-or-forged' WHERE id=1"
        )
    with pytest.raises(PackFailure) as caught:
        DevelopmentEvaluationPackLedger(journal)
    assert caught.value.code is PackCode.STORE


def test_all_gauntlet_dispositions_are_retained_without_upgrading_blocks() -> None:
    root = Path(__file__).resolve().parents[2]
    value = json.loads(
        (
            root / "docs/development/evaluation_pack_attack_dispositions_v1.json"
        ).read_text()
    )
    attacks = value["attacks"]
    assert [item["id"] for item in attacks] == [
        f"AT-{index:02d}" for index in range(1, 31)
    ]
    assert {
        item["id"]
        for item in attacks
        if item["source"] == "BLOCKED_MISSING_IMPLEMENTATION_OR_DECISION"
    } == {"AT-09", "AT-16", "AT-19", "AT-22", "AT-30"}
    assert all(
        item["c_ep1"] == "BLOCKED"
        for item in attacks
        if item["source"] == "BLOCKED_MISSING_IMPLEMENTATION_OR_DECISION"
    )
