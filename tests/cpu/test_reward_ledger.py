"""Durable policy tests use explicit synthetic projections, not science evidence."""

import asyncio
import os
from dataclasses import replace

import pytest
from test_net2_transport import headers
from test_net3_candidates import setup
from test_traineval_stub import _limits, _strategy

from carbon.candidates.model import AcceptedFixtureRecord, CandidateFailure
from carbon.candidates.store import CandidateJournal
from carbon.cards.development_scorecard import accepted_scorecard
from carbon.rewards.core import (
    DAY_MS,
    Q12,
    DevelopmentTerms,
    RewardFailure,
    WinnerStatus,
)
from carbon.rewards.ledger import BatchRef, FixtureRewardLedger
from carbon.scoring.pack import LoadedScorePack
from carbon.transport.models import canonical, digest, message


def run(value):
    return asyncio.run(value)


def candidate(journal, gate, index, hotkey="miner"):
    key = journal.context.pack.challenge_key
    strategy = _strategy(
        challenge_id=key.challenge_id, parameters={"synthetic_variant": index}
    )
    body = message(
        gate.context,
        gate.adapter.state.snapshot_id,
        key,
        session="reward",
        request=str(index),
        tool="submit",
        fields={
            "challenge_id": key.challenge_id,
            "challenge_version": key.version,
            "strategy": strategy,
        },
    )
    now = gate.adapter.state.timestamp_ms * 1000000
    gate.clock_ns = lambda: now
    receipt = run(gate.receive(body, headers(body, now + index, hotkey))).receipt
    return journal.commit(receipt.ref, body)


def finish_synthetic(journal, ref, score):
    """Mock the accepted adapter only in this analytical persistence test."""
    artifact, receipt_ref = journal._claim(ref)
    receipt = journal.receipts.resolve(receipt_ref)
    with journal.receipts.transaction() as db:
        strategy_hash = journal._row(db, ref)["strategy_hash"]
    journal._transition(ref, "DISPATCHING", "RUNNING")
    record = AcceptedFixtureRecord(
        ref,
        journal.context.identity,
        receipt.challenge_id,
        receipt.challenge_version,
        digest(canonical(artifact)),
        strategy_hash,
        receipt.ref.sequence,
        receipt.ref.digest,
        receipt.hotkey,
        receipt.coldkey,
        receipt.registered_at,
        receipt.snapshot_id,
        receipt.finalized_block,
        "123e4567-e89b-42d3-a456-426614174000",
        score.hex(),
        (score.hex(), score.hex(), score.hex()),
    )
    journal._complete_fixture(record)
    return record


def synthetic_pack(journal):
    """Private TEST ONLY owner double. Canonical integration uses the real loader."""
    pack = object.__new__(LoadedScorePack)
    object.__setattr__(pack, "pack_pin", journal.context.pack)
    object.__setattr__(pack, "ready", True)
    object.__setattr__(pack, "top_level_weights", (0.5, 0.3, 0.2))
    return pack


def initialized(tmp_path, allocation=Q12):
    journal, gate = setup(tmp_path)
    baseline = candidate(journal, gate, 1)
    finish_synthetic(journal, baseline, 0.8)
    ledger = FixtureRewardLedger(journal.receipts, gate.adapter, (journal,))
    opens = gate.adapter.state.timestamp_ms
    terms = DevelopmentTerms(
        journal.context.identity,
        baseline.identity,
        (0.8).hex(),
        "1",
        opens,
        opens + 29 * DAY_MS,
        opens + 30 * DAY_MS,
        ((opens, allocation),),
    )
    run(ledger.register(terms, synthetic_pack(journal), "synthetic-v1"))
    return ledger, journal, gate, terms


def advance(gate, milliseconds):
    old = gate.adapter.state
    gate.adapter.state = replace(
        old,
        finalized_block=old.finalized_block + 1,
        timestamp_ms=old.timestamp_ms + milliseconds,
        block_hash="0x" + f"{old.finalized_block+1:064x}",
    )


def accepted_batch(ledger, journal, gate, score=0.99, index=2, hotkey="miner"):
    ref = candidate(journal, gate, index, hotkey)
    batch = run(ledger.open_batch(journal.context.identity, f"batch-{index}"))
    finish_synthetic(journal, ref, score)
    state = run(ledger.close_batch(batch))
    return ref, batch, state


def test_zero_opening_then_exact_golden_and_restart(tmp_path):
    ledger, journal, gate, terms = initialized(tmp_path)
    assert ledger.resolve_projection(run(ledger.project()))["targets"]["burn"] == Q12
    _, batch, state = accepted_batch(ledger, journal, gate)
    assert (
        ledger.resolve_projection(run(ledger.project()))["targets"]["burn"]
        == 50000000000
    )
    advance(gate, DAY_MS)
    restarted = FixtureRewardLedger(
        journal.receipts,
        gate.adapter,
        (CandidateJournal(journal.receipts, journal.context, _limits()),),
    )
    assert run(restarted.close_batch(batch)) == state
    assert (
        restarted.resolve_projection(run(restarted.project()))["targets"]["burn"]
        == 525000000000
    )
    advance(gate, 6 * DAY_MS)
    assert (
        restarted.resolve_projection(run(restarted.project()))["targets"]["burn"]
        == 992578125000
    )
    assert (
        run(
            restarted.register(terms, synthetic_pack(journal), "synthetic-v1")
        ).record_hex
        == (0.99).hex()
    )


def test_admission_requires_frozen_batch_and_pending_cannot_be_omitted(tmp_path):
    ledger, journal, gate, _ = initialized(tmp_path)
    a, b = candidate(journal, gate, 2), candidate(journal, gate, 3, "validator")
    with pytest.raises(CandidateFailure, match="INDETERMINATE"):
        journal._claim(a)
    batch = run(ledger.open_batch(journal.context.identity, "closed-intake"))
    finish_synthetic(journal, a, 0.91)
    with pytest.raises(RewardFailure, match="PENDING"):
        run(ledger.close_batch(batch))
    with pytest.raises(RewardFailure, match="PENDING"):
        run(ledger.open_batch(journal.context.identity, "next"))
    advance(gate, DAY_MS)
    finish_synthetic(journal, b, 0.99)
    state = run(ledger.close_batch(batch))
    assert state.holder.hotkey == "validator"
    assert state.anchor_ms == 100000
    assert (
        ledger.resolve_projection(run(ledger.project()))["targets"]["burn"]
        == 525000000000
    )


def test_exact_batch_replay_conflict_and_clock_rollback(tmp_path):
    ledger, journal, gate, _ = initialized(tmp_path)
    _, batch, state = accepted_batch(ledger, journal, gate)
    assert run(ledger.open_batch(journal.context.identity, batch.identity)) == batch
    assert run(ledger.close_batch(batch)) == state
    with pytest.raises(RewardFailure, match="CONFLICTING"):
        run(ledger.close_batch(BatchRef(batch.identity, "0" * 64)))
    old = gate.adapter.state
    advance(gate, DAY_MS)
    run(ledger.project())
    gate.adapter.state = old
    with pytest.raises(RewardFailure, match="STALE"):
        run(ledger.project())


def test_identity_recycling_and_contest_burn_without_replacing_record(tmp_path):
    ledger, journal, gate, _ = initialized(tmp_path)
    candidate_ref, _, _ = accepted_batch(ledger, journal, gate)
    ledger.hold(candidate_ref, WinnerStatus.CONTESTED, "fixture-conflict")
    assert ledger.resolve_projection(run(ledger.project()))["targets"]["burn"] == Q12
    # A new registered occupant cannot inherit the prior identity or reward.
    old = gate.adapter.state
    gate.adapter.state = replace(
        old,
        finalized_block=old.finalized_block + 1,
        timestamp_ms=old.timestamp_ms + 1,
        participants=(
            old.participants[0],
            replace(
                old.participants[1],
                coldkey="new-cold",
                registered_at=old.finalized_block + 1,
            ),
        ),
    )
    result = ledger.resolve_projection(run(ledger.project()))
    assert result["targets"]["burn"] == Q12 and result["targets"]["winners"] == []


def test_copy_wallet_reset_and_old_baseline_cannot_renew_credit(tmp_path):
    ledger, journal, gate, terms = initialized(tmp_path)
    ref, batch, state = accepted_batch(ledger, journal, gate)
    # Same Strategy under another authenticated wallet resolves the same key.
    key = journal.context.pack.challenge_key
    body = message(
        gate.context,
        gate.adapter.state.snapshot_id,
        key,
        session="copy",
        request="copy",
        tool="submit",
        fields={
            "challenge_id": key.challenge_id,
            "challenge_version": key.version,
            "strategy": _strategy(
                challenge_id=key.challenge_id, parameters={"synthetic_variant": 2}
            ),
        },
    )
    receipt = run(gate.receive(body, headers(body, 100000000099, "validator"))).receipt
    assert journal.commit(receipt.ref, body) == ref
    advance(gate, DAY_MS)
    empty = run(ledger.open_batch(terms.context_id, "empty"))
    assert run(ledger.close_batch(empty)) == state
    with pytest.raises(RewardFailure, match="CONFLICTING_REGISTRATION"):
        run(
            ledger.register(
                replace(terms, upper="0.999"), synthetic_pack(journal), "synthetic-v1"
            )
        )
    assert run(ledger.close_batch(batch)) == state


def test_disclosure_allowlist_precision_aliases_and_accounting(tmp_path):
    ledger, journal, gate, terms = initialized(tmp_path)
    registration = ledger.registered_scorecard(terms.context_id)
    assert registration["coefficients"] == {
        "physics": "0.5",
        "robustness": "0.3",
        "accuracy": "0.2",
    }
    assert registration["composition"] == "weighted_geometric_logspace"
    ref, _, state = accepted_batch(ledger, journal, gate, 0.99049)
    public = run(ledger.release_scorecard(terms.context_id, ref))
    assert public["scores"]["combined"] == "0.990"
    assert state.record_hex == (0.99049).hex()
    assert public["miner"].startswith("miner-") and public["miner"] != "miner"
    assert set(public) == {
        "schema",
        "maturity",
        "challenge",
        "miner",
        "accepted_result",
        "release_ms",
        "scores",
        "comparison_source",
    }
    assert run(ledger.release_scorecard(terms.context_id, ref)) == public
    with journal.receipts.transaction() as db:
        assert (
            db.execute("SELECT released FROM reward_disclosure_v1").fetchone()[0] == 1
        )


@pytest.mark.parametrize("alias", ["hidden seed", "../private", "x" * 65, 42])
def test_a6_rejects_unregistered_alias_shapes(alias):
    with pytest.raises(ValueError):
        accepted_scorecard(alias, "miner", "result", 0.9, (0.8, 0.9, 1.0), 0)


def test_multi_challenge_ledger_preserves_allocations_and_shared_holder(tmp_path):
    from test_net2_transport import FakeVerifier

    from carbon.registry import ChallengeKey
    from carbon.transport.gateway import AuthenticatedGateway

    _, a, gate_a, terms_a = initialized(tmp_path, Q12 // 2)
    pack_b = replace(
        a.context.pack, challenge_key=ChallengeKey("second_fixture", "fixture-1.0")
    )
    b = CandidateJournal(a.receipts, replace(a.context, pack=pack_b), _limits())
    gate_b = AuthenticatedGateway(
        gate_a.context,
        pack_b.challenge_key,
        "validator",
        gate_a.adapter,
        FakeVerifier(),
        a.receipts,
    )
    baseline_b = candidate(b, gate_b, 10)
    finish_synthetic(b, baseline_b, 0.8)
    ledger = FixtureRewardLedger(a.receipts, gate_a.adapter, (a, b))
    terms_b = replace(
        terms_a, context_id=b.context.identity, baseline_ref=baseline_b.identity
    )
    run(ledger.register(terms_b, synthetic_pack(b), "second-fixture-v1"))
    accepted_batch(ledger, a, gate_a, 0.99, index=2)
    accepted_batch(ledger, b, gate_b, 0.9, index=11)
    projection = ledger.resolve_projection(run(ledger.project()))
    assert projection["targets"]["burn"] == 275000000000
    assert len(projection["targets"]["winners"]) == 1
    assert projection["targets"]["winners"][0][1] == 725000000000
    assert len(projection["targets"]["challenges"]) == 2


def test_durable_weekly_review_and_duplicate_rollups(tmp_path):
    from carbon.rewards.review import HOUR_MS, Hour

    ledger, journal, gate, terms = initialized(tmp_path)
    assert run(ledger.review_next(terms.context_id)) is None
    advance(gate, 7 * DAY_MS)
    for i in range(72):
        hour = Hour(terms.opens_ms + 4 * DAY_MS + i * HOUR_MS, 100, 5, True, True, 2, 1)
        run(ledger.record_hour(terms.context_id, str(i), hour))
        run(ledger.record_hour(terms.context_id, str(i), hour))
    result = run(ledger.review_next(terms.context_id))
    assert result.status == "PLATEAU_REVIEW" and result.submissions == 144
    assert run(ledger.review_next(terms.context_id)) is None
    advance(gate, 7 * DAY_MS)
    for i in range(72):
        hour = Hour(
            terms.opens_ms + 11 * DAY_MS + i * HOUR_MS, 100, 20, True, True, 2, 1
        )
        run(ledger.record_hour(terms.context_id, str(i + 72), hour))
    run(ledger.record_hour(terms.context_id, "duplicate", hour))
    assert run(ledger.review_next(terms.context_id)).status == "INDETERMINATE_DUPLICATE"
    # Prior alert is retained; a subsequent observation does not rewrite it.
    with journal.receipts.transaction() as db:
        assert db.execute("SELECT count(*) FROM reward_review_v1").fetchone()[0] == 2


def test_pending_processing_survives_funding_end_without_payout_guarantee(tmp_path):
    ledger, journal, gate, terms = initialized(tmp_path)
    advance(gate, 29 * DAY_MS)
    candidate_ref = candidate(journal, gate, 2)
    batch = run(ledger.open_batch(terms.context_id, "last-admitted"))
    advance(gate, 2 * DAY_MS)
    finish_synthetic(journal, candidate_ref, 0.99)
    assert run(ledger.close_batch(batch)).holder.hotkey == "miner"
    assert ledger.resolve_projection(run(ledger.project()))["targets"]["burn"] == Q12
    with pytest.raises(RewardFailure, match="WINDOW_CLOSED"):
        run(ledger.open_batch(terms.context_id, "too-late"))
    public = ledger.published_terms(terms.context_id)
    assert "no guaranteed chain receipts" in public["funding"]
    assert "baseline_ref" not in public and "context_id" not in public


def test_persisted_disclosure_cannot_add_private_fields(tmp_path):
    import json

    ledger, journal, gate, terms = initialized(tmp_path)
    ref, _, _ = accepted_batch(ledger, journal, gate)
    public = run(ledger.release_scorecard(terms.context_id, ref))
    public["hidden_seed"] = "must-not-release"
    with journal.receipts.transaction() as db:
        db.execute(
            "UPDATE reward_scorecard_v1 SET body=? WHERE candidate=?",
            (json.dumps(public), ref.identity),
        )
    with pytest.raises(ValueError, match="DISCLOSURE_SCHEMA"):
        run(ledger.release_scorecard(terms.context_id, ref))


@pytest.mark.skipif(
    os.name == "nt",
    reason="A3 verified artifact/registry integration requires canonical Linux",
)
def test_real_existing_fixture_lifecycle_supplies_baseline_and_improvement(tmp_path):
    import uuid

    from test_traineval_stub import (
        _environment,
        _fixture_registry,
        _pack,
        _profile,
        _provider,
        _service,
    )

    from carbon.candidates.service import FixtureCandidateService
    from carbon.fees import FeePolicyKey, FixtureSubmissionPolicy, SubmissionService

    journal, gate = setup(tmp_path)
    profile = _profile()
    ids = iter(
        (
            uuid.UUID("123e4567-e89b-42d3-a456-426614174000"),
            uuid.UUID("123e4567-e89b-42d3-a456-426614174001"),
        )
    )
    submissions = SubmissionService(
        _limits(),
        _fixture_registry(tmp_path / "science"),
        FixtureSubmissionPolicy(
            FeePolicyKey("reward-fixture-policy"),
            1703,
            2,
            profile.generator_version_required,
            profile.generator_digest_required,
            profile.scoring_version,
            profile.scoring_digest,
            _environment(),
        ),
        _uuid_factory=lambda: next(ids),
    )
    evaluator = _service(provider=_provider(b"C-REWARD paired synthetic fixture 23"))
    candidates = FixtureCandidateService(journal, submissions, evaluator)
    baseline_ref = candidate(journal, gate, 1)
    baseline = candidates.evaluate(baseline_ref)
    assert baseline.score_hex == (0.8869496047434128).hex()
    ledger = FixtureRewardLedger(journal.receipts, gate.adapter, (journal,))
    opens = gate.adapter.state.timestamp_ms
    terms = DevelopmentTerms(
        journal.context.identity,
        baseline_ref.identity,
        baseline.score_hex,
        "1",
        opens,
        opens + 29 * DAY_MS,
        opens + 30 * DAY_MS,
        ((opens, Q12),),
    )
    run(ledger.register(terms, _pack(), "actual-fixture-path"))
    winner_ref = candidate(journal, gate, 2)
    batch = run(ledger.open_batch(terms.context_id, "actual-a7-a8-batch"))
    accepted = candidates.evaluate(winner_ref)
    assert accepted.score_hex == (0.9300680593296387).hex()
    state = run(ledger.close_batch(batch))
    assert state.event == winner_ref.identity and state.record_hex == accepted.score_hex
    projection = ledger.resolve_projection(run(ledger.project()))
    assert 0 < projection["targets"]["burn"] < Q12
    public = run(ledger.release_scorecard(terms.context_id, winner_ref))
    assert public["scores"]["combined"] == "0.930"
