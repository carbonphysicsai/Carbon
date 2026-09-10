"""Deterministic publication/ambiguity tests; these are not localnet evidence."""

import asyncio
import copy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_reward_ledger import accepted_batch, advance, initialized, run

from carbon.chain.dispatch import DispatchJournal
from carbon.chain.publication import (
    PublicationFailure,
    RuntimeCapabilities,
    compile_targets,
    validate_integers,
)
from carbon.chain.publisher import LocalnetPublisher, TransactionObservation
from carbon.rewards.core import Q12
from carbon.rewards.intents import LocalnetIntentIssuer


def capabilities(snapshot, **changes):
    return replace(
        RuntimeCapabilities(
            snapshot.snapshot_id,
            445,
            1,
            2,
            "Burn",
            "owner",
            "validator",
            ("validator",),
            1,
            65535,
            0,
            0,
            0,
            False,
            True,
            True,
        ),
        **changes,
    )


def prepared(tmp_path, *, winner=True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    ledger, journal, gate, _ = initialized(tmp_path)
    if winner:
        accepted_batch(ledger, journal, gate)
    issuer = LocalnetIntentIssuer(ledger)
    ref = run(issuer.issue("publish-1"))
    snapshot = gate.adapter.state
    caps = capabilities(snapshot)
    resolved = issuer.resolve(ref, snapshot)
    return issuer, ref, gate, caps, resolved


def test_complete_winner_burn_vector_and_all_burn(tmp_path):
    _, ref, gate, caps, resolved = prepared(tmp_path)
    plan = compile_targets(resolved, gate.adapter.state, caps, "validator")
    assert plan.intent_digest == ref.digest
    assert dict(plan.q12) == {0: 50000000000, 1: 950000000000}
    assert dict(plan.integers) == {0: 3449, 1: 65535}
    validate_integers(plan, [0, 1], [3449, 65535], caps)
    _, _, gate, caps, resolved = prepared(tmp_path / "empty", winner=False)
    plan = compile_targets(resolved, gate.adapter.state, caps, "validator")
    assert plan.q12 == ((0, Q12),) and plan.integers == ((0, 65535),)


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"spec_version": 446}, "RUNTIME_VERSION"),
        ({"burn_mode": "Recycle"}, "BURN_MODE"),
        ({"owner_hotkey": "missing"}, "OWNER_SINK"),
        ({"owner_coldkey": "wrong"}, "OWNER_SINK"),
        ({"mechanism_count": 3}, "MECHANISM"),
        ({"max_weight": 32767}, "MAXIMUM_WEIGHT"),
        ({"min_weights": 3}, "MINIMUM_WEIGHT"),
        ({"sufficient_stake": False}, "STAKE"),
        ({"last_update": 10, "rate_limit": 10}, "RATE_LIMIT"),
        ({"pending_commits": 1}, "UNREVEALED"),
    ],
)
def test_unsupported_runtime_configuration_fails_without_loser_distribution(
    tmp_path, change, reason
):
    _, _, gate, caps, resolved = prepared(tmp_path)
    with pytest.raises(PublicationFailure, match=reason):
        compile_targets(
            resolved, gate.adapter.state, replace(caps, **change), "validator"
        )


@pytest.mark.parametrize(
    "case", ["loser", "zero", "duplicate", "clip", "negative", "float"]
)
def test_final_integer_guard_rejects_changed_or_malformed_representation(
    tmp_path, case
):
    _, _, gate, caps, resolved = prepared(tmp_path)
    plan = compile_targets(resolved, gate.adapter.state, caps, "validator")
    pairs = {
        "loser": ([0, 1, 2], [3449, 65535, 1]),
        "zero": ([], []),
        "duplicate": ([1, 1], [1, 65535]),
        "clip": ([0, 1], [65535, 65535]),
        "negative": ([0, 1], [-1, 65535]),
        "float": ([0, 1], [3449.0, 65535]),
    }
    with pytest.raises(PublicationFailure):
        validate_integers(plan, *pairs[case], caps)


def test_missing_recycled_and_owner_associated_winners_cannot_be_paid(tmp_path):
    _, _, gate, caps, resolved = prepared(tmp_path)
    old = gate.adapter.state
    for member in (
        replace(old.participants[1], hotkey="replacement"),
        replace(old.participants[1], registered_at=3),
    ):
        snapshot = replace(old, participants=(old.participants[0], member))
        with pytest.raises(PublicationFailure, match="IDENTITY_CHANGED"):
            compile_targets(
                resolved,
                snapshot,
                replace(caps, snapshot_id=snapshot.snapshot_id),
                "validator",
            )
    with pytest.raises(PublicationFailure, match="OWNER_ASSOCIATED"):
        compile_targets(
            resolved,
            old,
            replace(caps, owner_hotkeys=("validator", "miner")),
            "validator",
        )
    with pytest.raises(PublicationFailure, match="SELF_WINNER"):
        compile_targets(resolved, old, caps, "miner")


def test_challenge_accounting_corruption_never_normalizes_earned_subset(tmp_path):
    _, _, gate, caps, resolved = prepared(tmp_path)
    for case in ("burn", "unearned", "winners"):
        bad = copy.deepcopy(resolved)
        target = bad["projection"]["targets"]
        if case == "burn":
            target["burn"] = 0
        if case == "unearned":
            target["challenges"][0]["unearned"] = 0
        if case == "winners":
            target["winners"][0][1] = Q12
        with pytest.raises(PublicationFailure):
            compile_targets(bad, gate.adapter.state, caps, "validator")


def test_quantization_dust_has_explicit_bound_and_no_extra_recipient(tmp_path):
    _, _, gate, caps, resolved = prepared(tmp_path)
    target = resolved["projection"]["targets"]
    target["challenges"][0].update(earned=1, unearned=Q12 - 1)
    target["winners"][0][1] = 1
    target["burn"] = Q12 - 1
    plan = compile_targets(resolved, gate.adapter.state, caps, "validator")
    assert plan.q12 == ((0, Q12 - 1), (1, 1))
    assert plan.integers == ((0, 65535),)
    assert plan.tolerance_q12 < 31000000


class Backend:
    """Explicit deterministic chain double; no real SDK, keys or chain effects."""

    def __init__(self, gate, journal):
        self.gate, self.journal = gate, journal
        self.context, self.publisher = gate.context, "validator"
        self.caps = capabilities(gate.adapter.state)
        self.mode = "plain"
        self.signatures = self.executions = self.scans = 0
        self.tx_hash = "0x" + "a" * 64
        self.tx_block = None
        self.success = True
        self.row = []
        self.reveal_block = None
        self.outage = False

    async def observe(self):
        if self.outage:
            raise PublicationFailure("PROVIDER_UNAVAILABLE")
        return self.gate.adapter.state, replace(
            self.caps, snapshot_id=self.gate.adapter.state.snapshot_id
        )

    async def execute(self, plan, guard, call_checked, before_sign, before_dispatch):
        self.executions += 1
        self.tx_hash = "0x" + f"{self.executions:064x}"
        pf = SimpleNamespace(
            uid=0,
            min_allowed_weights=1,
            max_weight_limit=65535,
            commit_reveal=self.caps.commit_reveal,
        )
        uids, values = [u for u, _ in plan.integers], [v for _, v in plan.integers]
        await guard(uids, values, pf)
        if self.mode == "rebuild_clip":
            values = [65535] * len(uids)
        if self.mode == "runtime_change":
            self.caps = replace(self.caps, version_key=1)
        if self.mode == "uid_change":
            advance(self.gate, 1000)
            a, b = self.gate.adapter.state.participants
            self.gate.adapter.state = replace(
                self.gate.adapter.state,
                participants=(replace(b, uid=0), replace(a, uid=1)),
            )
        await guard(uids, values, pf)
        call = SimpleNamespace(data=b"validated fixture call", spec_version=445)
        await call_checked(
            call, {"reveal_round": 123} if self.caps.commit_reveal else {}
        )
        if self.mode == "call_change":
            call.data = b"changed after build"
        await before_sign(call, self.publisher)
        self.signatures += 1
        await before_dispatch(self.tx_hash)
        assert self.journal.pending() is not None
        assert (
            self.journal.get(self.journal.pending())["tracking"]["tx_hash"]
            == self.tx_hash
        )
        advance(self.gate, 1000)
        self.tx_block = self.gate.adapter.state.finalized_block
        self.row = [list(p) for p in plan.integers]
        if self.mode == "ambiguous":
            raise ConnectionError("sensitive provider transcript")

    async def transaction(self, tx_hash, block):
        self.scans += 1
        if tx_hash == self.tx_hash and block == self.tx_block:
            return TransactionObservation(self.success, block, "0x" + f"{block:064x}")
        return None

    async def revealed(self, publisher, block):
        return self.reveal_block == block

    async def weight_row(self, snapshot, uid):
        return self.row, self.tx_block


def publisher(tmp_path, *, cr=False):
    issuer, ref, gate, _, _ = prepared(tmp_path)
    journal = DispatchJournal(issuer.receipts)
    backend = Backend(gate, journal)
    backend.caps = replace(backend.caps, commit_reveal=cr)
    return LocalnetPublisher(issuer, backend), ref, backend


def test_dispatch_journals_before_wire_and_separates_settlement_from_verified_row(
    tmp_path,
):
    pub, ref, backend = publisher(tmp_path)
    result = run(pub.publish(ref))
    assert result["state"] == "ROW_VERIFIED"
    facts = result["tracking"]
    assert facts["tx_hash"] == backend.tx_hash
    assert facts["included_block"] == facts["finalized_block"] == backend.tx_block
    assert facts["stored_row"] == backend.row
    assert facts["settlement"] == "UNOBSERVED"
    assert facts["revealed"] is False  # plain mode needs no reveal
    assert run(pub.publish(ref)) == result
    assert backend.executions == backend.signatures == 1
    assert pub.exposure()["stored_weights_may_remain_effective"] is True


@pytest.mark.parametrize(
    "mode", ["rebuild_clip", "runtime_change", "uid_change", "call_change"]
)
def test_execution_rebuild_and_presign_changes_fail_before_signing(tmp_path, mode):
    pub, ref, backend = publisher(tmp_path)
    backend.mode = mode
    result = run(pub.publish(ref))
    assert result["state"] == "FAILED_BEFORE_SIGNING"
    assert backend.signatures == 0
    assert result["tracking"]["tx_hash"] is None


def test_ambiguous_outcome_restart_reconciles_without_resend(tmp_path):
    pub, ref, backend = publisher(tmp_path)
    backend.mode = "ambiguous"
    result = run(pub.publish(ref))
    assert result["state"] == "AMBIGUOUS"
    assert "sensitive" not in repr(result)
    restarted = LocalnetPublisher(LocalnetIntentIssuer(pub.issuer.ledger), backend)
    result = run(restarted.heartbeat("recovery"))
    assert result["state"] == "ROW_VERIFIED"
    assert backend.signatures == 1


def test_commit_finality_and_old_matching_row_do_not_prove_reveal(tmp_path):
    pub, ref, backend = publisher(tmp_path, cr=True)
    result = run(pub.publish(ref))
    assert result["state"] == "REVEAL_PENDING"
    assert result["tracking"]["finalized_block"] is not None
    assert result["tracking"]["revealed"] is False
    advance(backend.gate, 1000)
    backend.reveal_block = backend.gate.adapter.state.finalized_block
    result = run(pub.reconcile(ref.digest))
    assert result["state"] == "ROW_VERIFIED" and result["tracking"]["revealed"] is True
    assert result["tracking"]["reveal_block"] == backend.reveal_block


def test_bounded_backfill_and_outage_never_issue_duplicate(tmp_path):
    pub, ref, backend = publisher(tmp_path)
    backend.mode = "ambiguous"
    run(pub.publish(ref))
    backend.tx_block = 600
    backend.gate.adapter.state = replace(
        backend.gate.adapter.state, finalized_block=700
    )
    result = run(pub.reconcile(ref.digest))
    assert result["state"] == "AMBIGUOUS" and backend.scans == 256
    backend.outage = True
    with pytest.raises(PublicationFailure, match="UNAVAILABLE"):
        run(pub.heartbeat("outage"))
    assert backend.signatures == 1
    backend.outage = False
    run(pub.heartbeat("backfill-2"))
    result = run(pub.heartbeat("backfill-3"))
    assert result["state"] == "ROW_VERIFIED" and backend.signatures == 1


def test_finalized_rejection_is_distinct_and_journal_tampering_fails(tmp_path):
    pub, ref, backend = publisher(tmp_path)
    backend.success = False
    result = run(pub.publish(ref))
    assert result["state"] == "CHAIN_REJECTED"
    assert result["tracking"]["stored_row"] is None
    with pub.issuer.receipts.transaction() as db:
        db.execute("UPDATE publication_v1 SET tracking='{}'")
    with pytest.raises(PublicationFailure, match="CONFLICTING_DISPATCH"):
        pub.journal.get(ref.digest)


def test_shared_winner_is_aggregated_once_before_uid_mapping(tmp_path):
    _, _, gate, caps, resolved = prepared(tmp_path)
    target = resolved["projection"]["targets"]
    a = target["challenges"][0]
    a.update(allocated=Q12 // 2, earned=475000000000, unearned=25000000000)
    b = copy.deepcopy(a)
    b["context_id"] = "b" * 64
    target["challenges"].append(b)
    plan = compile_targets(resolved, gate.adapter.state, caps, "validator")
    assert plan.q12 == ((0, 50000000000), (1, 950000000000))


def test_recycled_recipient_after_dispatch_is_reported_and_fresh_tick_burns(tmp_path):
    pub, ref, backend = publisher(tmp_path)
    backend.mode = "ambiguous"
    run(pub.publish(ref))
    advance(backend.gate, 1000)
    state = backend.gate.adapter.state
    backend.gate.adapter.state = replace(
        state,
        participants=(
            state.participants[0],
            replace(state.participants[1], hotkey="replacement"),
        ),
    )
    result = run(pub.reconcile(ref.digest))
    assert result["state"] == "EXPOSURE_CHANGED"
    assert result["tracking"]["finalized_block"] is not None
    assert result["tracking"]["stored_row"] is None
    backend.mode = "plain"
    fresh = run(pub.heartbeat("recycle-recovery"))
    assert fresh["state"] == "ROW_VERIFIED"
    assert fresh["document"]["plan"]["q12"] == [[0, Q12]]


def test_heartbeat_publishes_decay_and_funding_end_burn_without_treasury(tmp_path):
    pub, ref, backend = publisher(tmp_path)
    run(pub.publish(ref))
    advance(backend.gate, 86400000)
    decayed = run(pub.heartbeat("decay"))
    assert decayed["state"] == "ROW_VERIFIED"
    amounts = dict(decayed["document"]["plan"]["q12"])
    assert 474000000000 < amounts[1] < 475000000000
    advance(backend.gate, 30 * 86400000)
    burned = run(pub.heartbeat("funding-end"))
    assert burned["state"] == "ROW_VERIFIED"
    assert burned["document"]["plan"]["q12"] == [[0, Q12]]


def test_explicit_heartbeat_loop_exposes_outage_without_claiming_zero_payout(tmp_path):
    pub, _, backend = publisher(tmp_path)
    backend.outage = True
    report = run(pub.run(asyncio.Event(), max_ticks=1))
    assert report["publisher_status"] == "PROVIDER_UNAVAILABLE"
    assert report["stored_weights_may_remain_effective"] is True
    assert backend.signatures == 0


def test_unhashed_interruption_cannot_be_silently_reset_or_resent(tmp_path):
    pub, ref, backend = publisher(tmp_path)
    snapshot, caps = run(backend.observe())
    plan = compile_targets(
        pub.issuer.resolve(ref, snapshot), snapshot, caps, backend.publisher
    )
    pub.journal.prepare(ref, plan, snapshot, caps)
    pub.journal.update(ref.digest, "SIGNING")
    result = run(pub.reconcile(ref.digest))
    assert result["state"] == "AMBIGUOUS" and "OPERATOR" in result["tracking"]["reason"]
    with pytest.raises(PublicationFailure, match="CANNOT_BE_RESET"):
        pub.journal.update(ref.digest, "FAILED_BEFORE_SIGNING")
    assert run(pub.publish(ref))["state"] == "AMBIGUOUS" and backend.signatures == 0


def test_settlement_observations_are_separate_idempotent_and_conflict_checked(tmp_path):
    pub, ref, backend = publisher(tmp_path)
    run(pub.publish(ref))
    facts = {"miner_burned": 0.05, "burn_mode": "Burn", "epoch": 3}
    receipt = pub.journal.observe_settlement(
        ref.digest, "epoch-3", backend.tx_block, facts
    )
    assert (
        pub.journal.observe_settlement(ref.digest, "epoch-3", backend.tx_block, facts)
        == receipt
    )
    assert receipt["meaning"] == "OBSERVATION_NOT_TARGET_EQUALITY"
    with pytest.raises(PublicationFailure, match="CONFLICTING_SETTLEMENT"):
        pub.journal.observe_settlement(
            ref.digest, "epoch-3", backend.tx_block, {"epoch": 4}
        )
