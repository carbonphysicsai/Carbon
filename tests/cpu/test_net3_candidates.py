"""Commitment integrity and unchanged A7/A8/A6 fixture integration."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from test_net2_transport import CONTEXT, NOW, Adapter, FakeVerifier, headers, snapshot
from test_traineval_stub import (
    _a7_service,
    _environment,
    _limits,
    _profile,
    _provider,
    _service,
    _strategy,
)

from carbon.candidates.model import (
    AcceptedFixtureRecord,
    CandidateFailure,
    CandidateRef,
    FixtureEvaluationContext,
)
from carbon.candidates.service import FixtureCandidateService
from carbon.candidates.store import CandidateJournal
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import ReceiptRef, message
from carbon.transport.store import ReceiptJournal


def setup(tmp_path, *, capacity=10000):
    context = FixtureEvaluationContext(_profile().score_pack_pin(), _environment())
    receipts = ReceiptJournal(tmp_path / "receipts.sqlite", CONTEXT)
    gate = AuthenticatedGateway(
        CONTEXT,
        context.pack.challenge_key,
        "validator",
        Adapter(snapshot()),
        FakeVerifier(),
        receipts,
        clock_ns=lambda: NOW,
    )
    return CandidateJournal(receipts, context, _limits(), capacity=capacity), gate


def signed(gate, index=1, *, strategy=None, hotkey="miner", tool="submit"):
    key = gate.challenge
    body = message(
        CONTEXT,
        gate.adapter.state.snapshot_id,
        key,
        session="test",
        request=str(index),
        tool=tool,
        fields={
            "challenge_id": key.challenge_id,
            "challenge_version": key.version,
            "strategy": _strategy() if strategy is None else strategy,
        },
    )
    received = asyncio.run(gate.receive(body, headers(body, NOW + index, hotkey)))
    return received.receipt.ref, body


def test_available_artifact_exact_replay_and_restart(tmp_path):
    journal, gate = setup(tmp_path)
    receipt, body = signed(gate)
    ref = journal.commit(receipt, body)
    assert journal.commit(receipt, body) == ref
    restarted = CandidateJournal(
        ReceiptJournal(journal.receipts.path, CONTEXT), journal.context, _limits()
    )
    assert restarted.commit(receipt, body) == ref
    assert restarted.state(ref) == "COMMITTED"
    with pytest.raises(CandidateFailure, match="NOT_ACCEPTED"):
        restarted.resolve_accepted_fixture(ref)


def test_altered_body_and_forged_receipt_fail(tmp_path):
    journal, gate = setup(tmp_path)
    receipt, body = signed(gate)
    _, other = signed(gate, 2, strategy=_strategy(parameters={"n": 2}))
    with pytest.raises(CandidateFailure, match="CONFLICT"):
        journal.commit(receipt, other)
    with pytest.raises(Exception, match="TRANSPORT"):
        journal.commit(ReceiptRef(receipt.sequence, "0" * 64), body)


@pytest.mark.parametrize(
    "strategy", [{}, _strategy(challenge_id="different"), _strategy(backbone="invalid")]
)
def test_invalid_artifact_has_no_commitment(tmp_path, strategy):
    journal, gate = setup(tmp_path)
    with pytest.raises(CandidateFailure, match="ARTIFACT"):
        journal.commit(*signed(gate, strategy=strategy))


def test_wallet_copy_retains_first_authenticated_order_even_out_of_order(tmp_path):
    journal, gate = setup(tmp_path)
    first = signed(gate)
    second = signed(gate, 2, hotkey="validator")
    ref = journal.commit(*second)
    assert journal.commit(*first) == ref
    assert journal.commit(*second) == ref
    artifact, receipt = journal._claim(ref)
    assert artifact == _strategy()
    assert receipt == first[0]


def test_claim_is_exclusive_and_restart_never_reissues(tmp_path):
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))

    def claim():
        try:
            journal._claim(ref)
            return "claimed"
        except CandidateFailure:
            return "indeterminate"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: claim(), range(2))) == [
            "claimed",
            "indeterminate",
        ]
    restarted = CandidateJournal(journal.receipts, journal.context, _limits())
    assert restarted.state(ref) == "DISPATCHING"
    with pytest.raises(CandidateFailure, match="INDETERMINATE"):
        restarted._claim(ref)


def test_missing_or_corrupted_artifact_fails_before_dispatch(tmp_path):
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    with journal.receipts.transaction() as db:
        db.execute(
            "UPDATE candidate_v1 SET artifact=? WHERE identity=?",
            (b"corrupted", ref.identity),
        )
    with pytest.raises(CandidateFailure, match="ARTIFACT"):
        journal._claim(ref)
    with pytest.raises(CandidateFailure, match="ARTIFACT"):
        journal.state(CandidateRef("0" * 64))


def test_context_cannot_be_replaced_and_capacity_is_global(tmp_path):
    journal, gate = setup(tmp_path, capacity=1)
    journal.commit(*signed(gate))
    with pytest.raises(CandidateFailure, match="CAPACITY"):
        journal.commit(*signed(gate, 2, strategy=_strategy(parameters={"n": 3})))
    changed = replace(
        journal.context,
        environment=replace(
            journal.context.environment, container_digest="sha256:" + "9" * 64
        ),
    )
    with pytest.raises(CandidateFailure, match="CONFLICT"):
        CandidateJournal(journal.receipts, changed, _limits())


def test_no_caller_evaluator_or_acceptance_capability(tmp_path):
    journal, _ = setup(tmp_path)
    with pytest.raises(CandidateFailure, match="CONTEXT"):
        FixtureCandidateService(journal, object(), object())
    assert not hasattr(FixtureCandidateService, "accept")
    assert not hasattr(FixtureCandidateService, "evaluate_production")


def test_private_fixture_projection_serializes_tuple_and_replays_after_restart(
    tmp_path,
):
    """Serialization unit only; synthetic construction is not science evidence."""
    from carbon.fees.strategy_identity import identify_strategy
    from carbon.transport.models import canonical, digest

    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    artifact, receipt_ref = journal._claim(ref)
    receipt = journal.receipts.resolve(receipt_ref)
    journal._transition(ref, "DISPATCHING", "RUNNING")
    record = AcceptedFixtureRecord(
        ref,
        journal.context.identity,
        receipt.challenge_id,
        receipt.challenge_version,
        digest(canonical(artifact)),
        identify_strategy(artifact, _limits()).strategy_hash.value,
        receipt.ref.sequence,
        receipt.ref.digest,
        receipt.hotkey,
        receipt.coldkey,
        receipt.registered_at,
        receipt.snapshot_id,
        receipt.finalized_block,
        "123e4567-e89b-42d3-a456-426614174000",
        (0.99).hex(),
        ((0.99).hex(), (0.98).hex(), (0.97).hex()),
    )
    journal._complete_fixture(record)
    journal._complete_fixture(record)
    restarted = CandidateJournal(journal.receipts, journal.context, _limits())
    assert restarted.resolve_accepted_fixture(ref) == record
    with pytest.raises(CandidateFailure, match="CONFLICT"):
        journal._complete_fixture(replace(record, score_hex=(0.98).hex()))


@pytest.mark.skipif(
    os.name == "nt", reason="A3 fixture filesystem requires canonical Linux"
)
@pytest.mark.parametrize("failure", ["gate", "infra", "exception", "pack"])
def test_science_and_infrastructure_failures_never_create_acceptance(
    tmp_path, monkeypatch, failure
):
    from test_traineval_stub import _completed_result, _pack

    from carbon.traineval import FixtureTrainEvalService
    from carbon.traineval.model import (
        CompletedFixtureRun,
        InfrastructureCause,
        InfrastructureFailedRun,
        InfrastructureRetryClass,
    )

    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    service = FixtureCandidateService(
        journal, _a7_service(tmp_path / "science"), _service()
    )

    def outcome(_self, envelope):
        if failure == "exception":
            raise RuntimeError("private evaluator detail must never escape")
        if failure == "infra":
            return InfrastructureFailedRun(
                envelope.handle,
                InfrastructureRetryClass.NON_RETRYABLE,
                next(iter(InfrastructureCause)),
            )
        result = _completed_result(
            _pack(), gate_error=1.0 if failure == "gate" else 0.25
        )
        if failure == "pack":
            result = replace(
                result,
                pack_pin=replace(result.pack_pin, scoring_digest="sha256:" + "8" * 64),
            )
        return CompletedFixtureRun(envelope.handle, result)

    monkeypatch.setattr(FixtureTrainEvalService, "run_fixture", outcome)
    with pytest.raises(CandidateFailure) as caught:
        service.evaluate(ref)
    assert "private evaluator detail" not in str(caught.value)
    assert caught.value.__context__ is None
    with pytest.raises(CandidateFailure, match="NOT_ACCEPTED"):
        journal.resolve_accepted_fixture(ref)
    assert (
        journal.state(ref)
        == {
            "gate": "REJECTED_SCIENCE",
            "infra": "FAILED_INFRA",
            "exception": "RUNNING",
            "pack": "FAILED_INFRA",
        }[failure]
    )


@pytest.mark.skipif(
    os.name == "nt",
    reason="Existing A3 secure descriptor-relative filesystem requires canonical Linux",
)
def test_existing_scientific_lifecycle_and_durable_exact_score(tmp_path):
    journal, gate = setup(tmp_path)
    receipt, body = signed(gate)
    ref = journal.commit(receipt, body)
    submissions = _a7_service(tmp_path / "science")
    # Fixed DEVELOPMENT entropy exercises the passing path under the unchanged
    # mandatory threshold. Default entropy is tested separately for rejection.
    evaluator = _service(provider=_provider(b"NET-3 synthetic passing fixture 2"))
    service = FixtureCandidateService(journal, submissions, evaluator)
    record = service.evaluate(ref)
    assert record.receipt_sequence == receipt.sequence
    assert record.receipt_digest == receipt.digest
    assert record.hotkey == "miner"
    assert float.fromhex(record.score_hex).hex() == record.score_hex
    assert len(record.component_hex) == 3
    assert record.context_id == journal.context.identity
    assert service.evaluate(ref) == record
    copied = journal.commit(*signed(gate, 2, hotkey="validator"))
    assert copied == ref and service.evaluate(copied) == record
    restarted = CandidateJournal(
        ReceiptJournal(journal.receipts.path, CONTEXT), journal.context, _limits()
    )
    assert restarted.resolve_accepted_fixture(ref) == record
    with journal.receipts.transaction() as db:
        db.execute(
            "UPDATE candidate_v1 SET accepted='{}' WHERE identity=?", (ref.identity,)
        )
    with pytest.raises(CandidateFailure, match="CONFLICT"):
        restarted.resolve_accepted_fixture(ref)


@pytest.mark.skipif(
    os.name == "nt", reason="A3 fixture filesystem requires canonical Linux"
)
def test_existing_default_fixture_mandatory_failure_is_not_accepted(tmp_path):
    journal, gate = setup(tmp_path)
    ref = journal.commit(*signed(gate))
    service = FixtureCandidateService(
        journal, _a7_service(tmp_path / "science"), _service()
    )
    with pytest.raises(CandidateFailure, match="NOT_ACCEPTED"):
        service.evaluate(ref)
    assert journal.state(ref) == "REJECTED_SCIENCE"
