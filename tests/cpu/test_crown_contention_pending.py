"""A challenger that never met the king is kept and contended after his regrade (Lead 5 Nov, the Validator's kings trace).

When the sitting king has no evaluation on a challenger's key, `consider_private` answers UNAVAILABLE
``incumbent_regrade_required`` and compares nothing. Before this fix the live path filed nothing and logged nothing, so 381
graded challengers on the four doors were never contended. Claims: the live path files the challenger PENDING_CONTENTION,
writes a journal line per challenger and one operator alert per king and key; the sweep does not try it (no GPU, no counted
attempt, no host alert) until the king is regraded on its key, then contends every pending challenger in filing order; a
record waiting on a key the king may never be regraded on holds no later crown back. Real pool store and real private
evaluations (synthetic graph case, synthetic source pins); no model, solver or network runs.
"""

from __future__ import annotations

import json

import pytest
from test_bank_private_evaluation import admitted, inputs
from test_score_lab_private_evaluation_evidence import _graph_case

from carbon.battery.pool_store import PENDING_CONTENTION, PoolStore
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_pause_sweep as sweeper
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.interface import digest

EXAM = digest("exam")
ENTRY = digest("entry")


class Repeat:
    entry_id = ENTRY


@pytest.fixture
def rig(tmp_path):
    """The kings-trace state: the king graded on the OLD evaluation version only, two challengers graded on the NEW one."""
    case = _graph_case(tmp_path)
    store = PoolStore(tmp_path / "private.sqlite", clock=lambda: 123.0)
    for model in ("king", "first", "second"):
        admitted(store, case, model)
    store.set_incumbent("king", "historical fixture")
    old_pin, old_args = inputs(case)
    BankPromotion = bp.BankPromotion
    old = BankPromotion(store, registered_source_receipt_sha256=old_pin).retain_private(
        "king", **old_args
    )
    pin, args = inputs(case, version="synthetic-eval-v2")
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    keys = {
        sid: flow.retain_private(sid, **args)["evaluation_key"]
        for sid in ("first", "second")
    }
    assert keys["first"] == keys["second"] != old["evaluation_key"]
    comparator = {
        "challenge": case["entry"]["challenge"],
        "score_pack_digest": args["score_pack"]["pack_digest"],
        "baseline_total": None,
    }

    def live(sid):
        """What the receiver's `_contend` does after a grade: consider it, then file what must be kept."""
        outcome = flow.consider_private(sid, keys[sid], comparator, repeat=Repeat())
        retention._file_if_paused(store, outcome, "pack", sid, EXAM, Repeat(), pin)
        return outcome

    def regrade_king():
        return flow.retain_private("king", **args)

    return store, flow, live, regrade_king, keys["first"], old["evaluation_key"]


def journal(capsys):
    return [json.loads(line) for line in capsys.readouterr().err.splitlines() if line]


def sweep(store, reconsider):
    return sweeper.sweep(store, reconsider, kind="pack", current_exam=EXAM)


def test_a_challenger_the_king_cannot_meet_is_filed_pending_and_logged_never_dropped(
    rig, capsys
):
    store, _flow, live, _regrade, key, _old = rig
    outcome = live("first")
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert (
        outcome["reason"]
        == bp.INCUMBENT_REGRADE_REQUIRED
        == "incumbent_regrade_required"
    )
    assert outcome["incumbent"] == "king"
    live("second")
    pending = store.pending_contentions("pack")
    assert [(r["submission_id"], r["evaluation_key"]) for r in pending] == [
        ("first", key),
        ("second", key),
    ]
    assert pending == store.paused_crowns(
        "pack"
    )  # in the sweep's queue, in grading order
    with store.db() as db:
        states = {
            s
            for (s,) in db.execute(
                "SELECT state FROM operations WHERE kind='crown_paused.v1'"
            )
        }
    assert states == {PENDING_CONTENTION}
    assert store.crown_pause_attempts("first", key) == (
        0,
        None,
    )  # not a failed attempt: nothing was tried
    lines = journal(capsys)
    contention = [line for line in lines if line["event"] == "crown_contention_pending"]
    assert [
        (line["candidate"], line["incumbent"], line["evaluation_key"], line["filed"])
        for line in contention
    ] == [
        ("first", "king", key, True),
        ("second", "king", key, True),
    ]
    (alert,) = [
        line for line in lines if line["event"] == "operator_alert"
    ]  # one per king and key, not per challenger
    assert alert["code"] == "incumbent_regrade_required"
    assert alert["action"] == "regrade_incumbent_on_evaluation_key"
    assert (alert["incumbent"], alert["evaluation_key"]) == ("king", key)
    (filed,) = store.crown_contention_alerts()
    assert (filed["incumbent"], filed["evaluation_key"], filed["code"]) == (
        "king",
        key,
        "incumbent_regrade_required",
    )
    live("first")  # considered again: the same record, no second alert
    assert (
        len(store.pending_contentions()) == 2
        and len(store.crown_contention_alerts()) == 1
    )
    assert [line["event"] for line in journal(capsys)] == ["crown_contention_pending"]


def test_the_sweep_waits_for_the_kings_regrade_then_contends_every_pending_challenger_in_order(
    rig,
):
    store, _flow, live, regrade_king, key, _old = rig
    live("first")
    live("second")
    asked = []

    def reconsider(record):
        asked.append(record["submission_id"])
        return {
            "outcome": bp.INCUMBENT_KEEPS,
            "reason": "bank_comparison_development",
            "evaluation_key": key,
        }

    for _tick in range(
        5
    ):  # every tick before the regrade: nothing tried, counted, alerted or resolved
        assert sweep(store, reconsider) == []
    assert asked == []
    assert store.crown_pause_attempts("first", key) == (0, None)
    assert store.crown_pause_alerts() == []
    assert all(store.awaits_incumbent_regrade(r) for r in store.pending_contentions())
    regrade_king()  # the king's uncounted regrade on the challengers' key
    assert not any(
        store.awaits_incumbent_regrade(r) for r in store.pending_contentions()
    )
    assert [sid for sid, _ in sweep(store, reconsider)] == ["first", "second"]
    assert asked == ["first", "second"]
    assert store.pending_contentions() == [] and store.paused_crowns() == []


def test_after_the_regrade_the_real_consider_path_meets_the_king(rig):
    _store, flow, live, regrade_king, key, _old = rig
    live("first")
    regrade_king()
    pair = flow.private_pair("first", key)
    assert (
        pair["expected_incumbent"] == "king"
        and pair["incumbent"]["evaluation_key"] == key
    )


def test_a_record_waiting_on_a_key_the_king_lacks_holds_no_later_crown_back(rig):
    """A deploy that moves the key may strand a record for good: it must not queue every later crown behind it."""
    store, flow, live, _regrade, _key, old = rig
    live("first")  # waits on the new key, where the king has no evaluation
    old_flow = bp.BankPromotion(
        store, registered_source_receipt_sha256=store.paused_crowns()[0]["pin"]
    )
    assert flow._undecided_before("late", old) == []
    assert old_flow._undecided_before("late", old) == []
    # a record that is NOT waiting for a regrade still holds later crowns back, as before
    store.record_crown_paused(
        "other", old, kind="pack", exam=EXAM, entry_id=ENTRY, pin=digest("pin")
    )
    assert [r["submission_id"] for r in flow._undecided_before("late", old)] == [
        "other"
    ]


def test_the_sweep_skips_a_waiting_record_and_still_decides_a_later_one(rig):
    store, _flow, live, _regrade, _key, old = rig
    live("first")
    store.record_crown_paused(
        "other", old, kind="pack", exam=EXAM, entry_id=ENTRY, pin=digest("pin")
    )
    done = sweep(
        store,
        lambda record: {
            "outcome": bp.INCUMBENT_KEEPS,
            "reason": "kept",
            "evaluation_key": old,
        },
    )
    assert done == [("other", "INCUMBENT_KEEPS:kept")]
    assert [r["submission_id"] for r in store.pending_contentions()] == ["first"]


def test_without_a_retained_entry_the_journal_and_the_alert_say_it_could_not_be_filed(
    rig, capsys
):
    store, flow, _live, _regrade, key, _old = rig
    outcome = flow.consider_private(
        "first",
        key,
        {"challenge": "x", "score_pack_digest": digest("p"), "baseline_total": None},
    )
    retention._file_if_paused(
        store, outcome, "pack", "first", EXAM, None, digest("pin")
    )
    assert store.paused_crowns() == []
    lines = journal(capsys)
    assert [(line["event"], line.get("filed")) for line in lines] == [
        ("crown_contention_pending", False),
        ("operator_alert", None),
    ]
    assert (
        lines[1]["code"] == "crown_contention_unfiled"
        and lines[1]["candidate"] == "first"
    )


def test_a_race_where_the_king_loses_the_key_between_reads_stays_pending_and_counts_nothing(
    tmp_path,
):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    store = PoolStore(state / "pool.sqlite3", clock=lambda: 5.0)
    for sid in ("a", "b"):
        store.record_crown_paused(
            sid,
            digest("k" + sid),
            kind="pack",
            exam=EXAM,
            entry_id=ENTRY,
            pin=digest("pin"),
        )

    def reconsider(record):
        if record["submission_id"] == "a":
            return {"outcome": bp.UNAVAILABLE, "reason": bp.INCUMBENT_REGRADE_REQUIRED}
        return {"outcome": bp.INCUMBENT_KEEPS, "reason": "kept"}

    assert sweep(store, reconsider) == [("b", "INCUMBENT_KEEPS:kept")]
    assert store.crown_pause_attempts("a", digest("ka")) == (0, None)
    assert [r["submission_id"] for r in store.paused_crowns()] == ["a"]


def test_the_state_of_a_filing_is_closed(tmp_path):
    from carbon.battery.pool_store import StateError

    store = PoolStore(tmp_path / "pool.sqlite3")
    with pytest.raises(StateError, match="crown_paused_invalid"):
        store.record_crown_paused(
            "a",
            digest("k"),
            kind="pack",
            exam=EXAM,
            entry_id=ENTRY,
            pin=digest("p"),
            state="X",
        )
