"""A king hand-over between two exam versions' stores (owner G-LEAD-69, 24 Nov 2026, "Yes, pay 1.8 king"): the slot pays
the previous version's king until the new version's first PAYABLE king, then the new one, never both and never back.

No public transaction happens here: the snapshot and backend are the publication tests' doubles, every store, king and
pack is a synthetic fixture.
"""

import dataclasses
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_od4a_dispatch import chain, snapshot
from test_reward_testnet_winner_publication import (
    BATTERY,
    POLICY,
    _LeanStore,
    authorization,
)

from carbon.rewards import testnet_winner_publication as twp
from carbon.rewards import winner_eligibility as we
from carbon.transport.store import ReceiptJournal

OLD, NEW, NEXT = "miner-hotkey", "king-new", "king-next"
PACK_OLD, PACK_NEW = "sha256:" + "1" * 64, "sha256:" + "2" * 64


def at(block, hotkeys=(NEW, NEXT)):
    """The standard snapshot (it holds the old king's hotkey) plus the new version's miners."""
    base = snapshot(chain(), block=block)
    member = type(base.participants[0])
    extra = tuple(
        member(uid, hotkey, f"cold-{hotkey}", uid + 1)
        for uid, hotkey in enumerate(hotkeys, len(base.participants))
    )
    return dataclasses.replace(base, participants=base.participants + extra)


def rig(tmp_path, *, handover=True):
    old, new = _LeanStore(), _LeanStore()
    old.crown("old-1", OLD, at=1.0)
    auth = authorization()
    issuer = twp.TestnetWinnerIntentIssuer(
        ReceiptJournal(tmp_path / "publication.sqlite3", auth.context),
        auth,
        POLICY,
        we.WinnerLedger(tmp_path / "winners.jsonl"),
        {BATTERY: lambda: we.lean_promotion(old)},
        {BATTERY: lambda recorded: we.lean_crowns_since(old, recorded)},
    )
    issuer.issue(at(925))  # the loop records the old king on the old store
    issuer.sources = {BATTERY: lambda: we.lean_promotion(new)}
    issuer.replays = {BATTERY: lambda recorded: we.lean_crowns_since(new, recorded)}
    if handover:
        issuer.handovers = {
            BATTERY: twp.Handover(
                source=lambda: we.lean_promotion(old),
                replay=lambda recorded: we.lean_crowns_since(old, recorded),
                models=lambda: twp.crowned_models(new),
            )
        }
    return issuer, old, new


def paid(issuer, state):
    """The hotkeys this epoch's targets pay."""
    return [
        holder["hotkey"]
        for holder, _ in twp.preview(issuer, state)["targets"]["winners"]
    ]


def models(issuer):
    return [r["promotion"]["model_id"] for r in issuer.ledger.records(BATTERY)]


def test_the_old_king_is_paid_until_the_first_new_king_and_never_both(tmp_path):
    issuer, _old, new = rig(tmp_path)
    clock = issuer.ledger.records(BATTERY)[0]["clock_ms"]
    assert paid(issuer, at(1100)) == [OLD]  # the new store has no king yet
    issuer.issue(at(1100))
    new.crown("new-1", NEW, at=1.0)
    assert paid(issuer, at(1500)) == [NEW]
    issuer.issue(at(1500))
    assert models(issuer) == ["old-1", "new-1"]
    # the old king kept his own record and decay clock; the new one is a first incumbent of his own store
    first, second = issuer.ledger.records(BATTERY)
    assert first["clock_ms"] == clock
    assert (second["eligible"], second["reason"]) == (
        True,
        "first_incumbent_no_baseline",
    )


def test_an_old_king_crowned_again_during_the_hand_over_is_paid(tmp_path):
    issuer, old, _new = rig(tmp_path)
    old.crown("old-2", NEXT, previous="old-1", at=2.0)
    assert paid(issuer, at(1100)) == [NEXT]


def test_without_the_hand_over_a_re_pointed_loop_refuses_every_cycle(tmp_path):
    """Why a hand-over is needed, and not only a re-point: the new store's journal never held the recorded king."""
    issuer, _old, new = rig(tmp_path, handover=False)
    new.crown("new-1", NEW, at=1.0)
    with pytest.raises(
        twp.WinnerPublicationRefused, match="PREDECESSOR_NOT_IN_DOOR_JOURNAL"
    ):
        twp.preview(issuer, at(1100))


def test_a_new_king_who_is_not_registered_does_not_end_the_old_kings_pay(tmp_path):
    issuer, _old, new = rig(tmp_path)
    new.crown("new-1", NEW, at=1.0)
    assert paid(issuer, at(1100, hotkeys=())) == [OLD]
    issuer.issue(at(1100, hotkeys=()))
    assert paid(issuer, at(1500)) == [NEW]  # registered since


def test_after_a_payable_new_king_the_old_one_is_never_paid_again(tmp_path):
    issuer, old, new = rig(tmp_path)
    new.crown("new-1", NEW, at=1.0)
    issuer.issue(at(1100))
    assert paid(issuer, at(1500, hotkeys=())) == []  # he left: his share burns

    def gone():
        raise RuntimeError("the previous version's store was removed")

    old.incumbent = gone  # and the old store is not even read
    assert paid(issuer, at(1500)) == [NEW]


def test_an_unreadable_store_refuses_while_the_hand_over_is_on(tmp_path):
    issuer, old, _new = rig(tmp_path)

    def gone():
        raise RuntimeError("unreadable")

    old.incumbent = gone
    with pytest.raises(twp.WinnerPublicationRefused, match="WINNER_SOURCE_UNAVAILABLE"):
        twp.preview(issuer, at(1100))


def test_an_unreadable_new_journal_refuses_rather_than_paying_the_old_king(tmp_path):
    issuer, _old, _new = rig(tmp_path)

    def broken():
        raise RuntimeError("unreadable")

    issuer.handovers = {
        BATTERY: dataclasses.replace(issuer.handovers[BATTERY], models=broken)
    }
    with pytest.raises(twp.WinnerPublicationRefused, match="WINNER_SOURCE_UNAVAILABLE"):
        twp.preview(issuer, at(1100))


def test_two_new_kings_before_the_first_observation_are_both_recorded(tmp_path):
    issuer, _old, new = rig(tmp_path)
    new.crown("new-1", NEW, at=1.0)
    new.crown("new-2", NEXT, previous="new-1", at=2.0)
    assert paid(issuer, at(1100)) == [NEXT]
    issuer.issue(at(1100))
    assert models(issuer) == ["old-1", "new-1", "new-2"]
    assert [r["promotion"]["previous"] for r in issuer.ledger.records(BATTERY)] == [
        None,
        None,
        "new-1",
    ]


def test_each_stores_next_king_follows_its_own_last_record(tmp_path, monkeypatch):
    """An unpayable new king (here a Carbon canary) is the ledger's last record; the old store's next king is still
    checked against the old store's own last king, and the new store's next king against the new store's.
    """
    from carbon.challenge_validator import canary

    monkeypatch.setattr(canary, "is_canary", lambda hotkey: hotkey == NEW)
    issuer, old, new = rig(tmp_path)
    new.crown("new-1", NEW, at=1.0)
    assert paid(issuer, at(1100)) == [OLD]
    issuer.issue(at(1100))
    old.crown("old-2", NEXT, previous="old-1", at=2.0)
    assert paid(issuer, at(1500)) == [NEXT]
    issuer.issue(at(1500))
    assert models(issuer) == ["old-1", "new-1", "old-2"]
    new.crown("new-2", NEXT, previous="new-1", at=3.0)
    issuer.issue(at(1900))
    assert models(issuer) == ["old-1", "new-1", "old-2", "new-2"]
    assert issuer.ledger.records(BATTERY)[-1]["reason"] == "bank_improvement"


def test_the_old_king_winning_the_new_exam_keeps_his_clock_as_registered(tmp_path):
    """`decide`'s same-miner rule, unchanged: a first incumbent of the same miner starts no fresh clock."""
    issuer, _old, new = rig(tmp_path)
    clock = issuer.ledger.records(BATTERY)[0]["clock_ms"]
    new.crown("new-1", OLD, at=1.0)
    record = twp.preview(issuer, at(1100))["records"][BATTERY]
    assert (record["reason"], record["clock_ms"]) == ("same_miner_no_reset", clock)


def test_the_published_intent_resolves_to_the_targets_it_was_issued_with(tmp_path):
    issuer, _old, new = rig(tmp_path)
    for block in (1100, 1500):
        state = at(block)
        ref = issuer.issue(state)
        issuer.resolve(ref, state)  # refuses TARGETS_CHANGED_REISSUE_NEXT_EPOCH if not
        new.crown("new-1", NEW, at=1.0)


def _mainnet(issuer, *packs):
    issuer.policy = dataclasses.replace(
        POLICY,
        network="finney",
        qualified_sealed=((BATTERY, "sha256:" + "a" * 64, packs),),
    )


def test_a_new_king_on_an_unqualified_pack_is_not_recorded_until_the_policy_names_it(
    tmp_path, monkeypatch
):
    """A ledger record is permanent, so a policy that does not name the new pack yet must not write 'ineligible'."""
    monkeypatch.setattr(
        we, "_crown_pack_digests", lambda store, _model: getattr(store, "packs", None)
    )
    issuer, old, new = rig(tmp_path)
    old.packs, new.packs = [PACK_OLD], [PACK_NEW]
    new.crown("new-1", NEW, at=1.0)
    _mainnet(issuer, PACK_OLD)
    assert paid(issuer, at(1100)) == [OLD]
    issuer.issue(at(1100))
    assert models(issuer) == ["old-1"]
    _mainnet(issuer, PACK_OLD, PACK_NEW)
    assert paid(issuer, at(1500)) == [NEW]


def test_a_hand_over_needs_the_new_stores_replay(tmp_path):
    issuer, _old, _new = rig(tmp_path)
    with pytest.raises(twp.WinnerPublicationRefused, match="HANDOVER_SOURCE_REQUIRED"):
        twp.TestnetWinnerIntentIssuer(
            issuer.receipts,
            issuer.authorization,
            POLICY,
            issuer.ledger,
            issuer.sources,
            {},
            issuer.handovers,
        )


def test_a_replay_from_the_start_ignores_a_withdrawn_crown():
    store = _LeanStore()
    store.crown("new-1", NEW, at=1.0)
    store._events.append(({"model_id": None, "previous": "new-1", "reason": "x"}, 2.0))
    store.crown("new-2", NEXT, at=3.0)
    assert [c["promotion"]["model_id"] for c in we.lean_crowns_since(store, None)] == [
        "new-1",
        "new-2",
    ]
    assert twp.crowned_models(store) == {"new-1", "new-2"}
