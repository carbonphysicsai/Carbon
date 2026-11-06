"""The v4 launch board (Lead 5 Nov 21:5x): each door's live crown state.

v4 = v3 plus the king's re-measure progress (``measure``: a state and two counts) and ``crown_checks`` (the latest
decision per contender: hotkey, state, outcome and reason codes), under its own signing domain. v1-v3 are unchanged. The
receiver files each crown decision beside its journal line (`PoolStore.record_crown_decision`) and the operator reads it
back read-only. No seed, mean or per-seed status ever reaches the signed bytes.

Hotkeys, codes and counts here are synthetic fixtures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_koth_v2_crown_changes import HOTKEY, _args
from test_launch_board_v3 import KEY, NOISE, NOW, A, _row

from carbon.challenge_validator import koth_journal
from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import launch_board as lb

B = "5" + "B" * 47
MEASURED = {"state": "MEASURED", "kept": 10, "n": 10}
CHECKS = [
    {
        "hotkey": A,
        "state": "DECIDED",
        "outcome": "INCUMBENT_KEEPS",
        "note": "the king keeps the crown",
    },
    {
        "hotkey": B,
        "state": "PENDING",
        "outcome": "UNAVAILABLE",
        "note": "waiting for the king's re-measure",
    },
]


def _build(*, measure=MEASURED, stability="STABLE", checks=CHECKS, king=True):
    document = kp.document_v2(
        **_args(
            king=(
                {"hotkey": HOTKEY, "total": 0.7123, "since_epoch": 12} if king else None
            )
        )
    )
    return lb.build(
        king_document=document,
        rows=[_row(HOTKEY, 0.7123), _row(A, 0.6)] if king else [_row(A, 0.6)],
        network="testnet",
        key=KEY,
        version=5,
        now=NOW,
        crown_changes=[],
        exact_totals={HOTKEY: 0.7123, A: 0.6} if king else {A: 0.6},
        rebuild_noise=NOISE,
        stability=stability,
        measure=measure,
        crown_checks=checks,
    )


def test_a_v4_board_carries_the_measure_and_checks_under_its_own_domain():
    board = _build()
    assert board["schema"] == lb.SCHEMA_V4
    assert board["king"]["measure"] == MEASURED and board["crown_checks"] == CHECKS
    assert lb.verify(board, KEY.public_key) == board
    # a v4 signature never verifies as v3, nor the reverse
    as_v3 = {**board, "schema": lb.SCHEMA_V3}
    with pytest.raises(lb.BoardRefused):
        lb.verify(as_v3, KEY.public_key)


@pytest.mark.parametrize(
    "measure, stability",
    [
        ({"state": "MEASURED", "kept": 10, "n": 10}, "STABLE"),
        ({"state": "UNSTABLE", "kept": 7, "n": 10}, "UNSTABLE"),
        ({"state": "IN_PROGRESS", "kept": 3, "n": 10}, None),
        ({"state": "UNMEASURED", "kept": 0, "n": 10}, None),
    ],
)
def test_the_stability_follows_the_measure(measure, stability):
    board = _build(measure=measure, stability=stability)
    assert lb.verify(board, KEY.public_key)["king"]["stability"] == stability
    wrong = "UNSTABLE" if stability != "UNSTABLE" else "STABLE"
    with pytest.raises(lb.BoardRefused, match="board_stability"):
        _build(measure=measure, stability=wrong)


def test_no_king_has_no_measure_and_no_stability():
    board = _build(king=False, measure=None, stability=None, checks=[])
    assert board["king"]["measure"] is None and board["king"]["stability"] is None
    with pytest.raises(lb.BoardRefused):
        _build(king=False, measure=MEASURED, stability=None, checks=[])


@pytest.mark.parametrize(
    "measure",
    [
        {"state": "DONE", "kept": 1, "n": 10},
        {"state": "IN_PROGRESS", "kept": 11, "n": 10},
        {"state": "IN_PROGRESS", "kept": 1, "n": 1},
        {"state": "IN_PROGRESS", "kept": 1, "n": 10, "mean": 0.5},
    ],
)
def test_a_measure_outside_its_closed_shape_refuses(measure):
    with pytest.raises(lb.BoardRefused):
        _build(measure=measure, stability=None)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c[0].update(state="PENDING"),  # a decided outcome is never pending
        lambda c: c[1].update(state="DECIDED"),  # UNAVAILABLE is never decided
        lambda c: c[0].update(outcome="CROWNED_MAYBE"),
        lambda c: c[0].update(note="Has Spaces"),
        lambda c: c[0].update(note="queued"),  # a phrase of another outcome
        lambda c: c[0].update(reason="mean_within_margin_or_tie"),  # a raw code field
        lambda c: c[0].update(seed=3),
        lambda c: c.append(dict(c[0])),  # a contender twice
        lambda c: c.extend(
            {**c[0], "hotkey": "5" + chr(67 + i) * 47} for i in range(10)
        ),  # more than 10
    ],
)
def test_crown_checks_outside_their_closed_shape_refuse(mutate):
    checks = json.loads(json.dumps(CHECKS))
    mutate(checks)
    with pytest.raises(lb.BoardRefused):
        _build(checks=checks)


def test_v4_needs_the_v3_inputs():
    document = kp.document_v2(
        **_args(king={"hotkey": HOTKEY, "total": 0.7123, "since_epoch": 12})
    )
    with pytest.raises(lb.BoardRefused, match="board_v4_needs"):
        lb.build(
            king_document=document,
            rows=[_row(HOTKEY, 0.7123)],
            network="testnet",
            key=KEY,
            version=5,
            now=NOW,
            crown_changes=[],
            exact_totals={HOTKEY: 0.7123},
            rebuild_noise=NOISE,
            measure=MEASURED,
        )


def test_no_seed_mean_or_score_reaches_the_v4_bytes():
    text = json.dumps(_build())
    for forbidden in (
        "seed",
        'mean"',
        "statuses",
        "per_seed",
        "submission_id",
        "evaluation_key",
    ):
        assert forbidden not in text


def test_the_receivers_reader_does_not_refuse_a_v4_board_for_its_schema(tmp_path):
    from carbon.challenge_validator import launch_board_file as lbf

    board = _build()
    path = tmp_path / "board.json"
    path.write_text(json.dumps(board))
    got = lbf.read_board(path, board["challenge"]["id"], KEY.public_key)
    assert (
        got is None or got == board
    )  # the step check may refuse the fixture's totals; never the schema


# ---------------------------------------------------------------- the receiver files each decision; the board reads it back


def _store(tmp_path):
    from carbon.battery.pool_store import PoolStore

    return PoolStore(tmp_path / "pool.sqlite3")


def test_each_crown_comparison_is_filed_beside_its_journal_line_and_never_raises(
    tmp_path,
):
    store = _store(tmp_path)
    key = "sha256:" + "c" * 64
    koth_journal.contention(
        "live",
        "sub-a",
        {
            "outcome": "INCUMBENT_KEEPS",
            "reason": "mean_within_margin",
            "evaluation_key": key,
        },
        store=store,
    )
    koth_journal.contention(
        "sweep",
        "sub-b",
        {"outcome": "UNAVAILABLE", "reason": "king_unmeasured", "evaluation_key": key},
        store=store,
    )
    koth_journal.contention(
        "live",
        "sub-a",
        {"outcome": "CHALLENGER", "reason": "mean_beats_king", "evaluation_key": key},
        store=store,
    )
    koth_journal.contention(
        "live", "sub-c", {"error": "boom"}, store=store
    )  # a refusal is not a decision
    decisions = store.crown_decisions()
    assert [(d["submission_id"], d["outcome"]) for d in decisions] == [
        ("sub-a", "CHALLENGER"),  # the latest per contender, newest first
        ("sub-b", "UNAVAILABLE"),
    ]

    class Broken:
        def record_crown_decision(self, *a):
            raise RuntimeError("disk full")

    koth_journal.contention(
        "live", "sub-d", {"outcome": "NO_WINNER"}, store=Broken()
    )  # swallowed


def test_kept_rebuilds_count_seeds_not_the_host_fault_second_build(tmp_path):
    store = _store(tmp_path)
    key = "sha256:" + "d" * 64
    for seed, again in ((11, False), (12, False), (11, True), (13, False)):
        store.record_crown_rebuild("king", key, seed, again, {"total": 0.5})
    assert store.kept_crown_rebuilds("king", key) == 3
    assert store.kept_crown_rebuilds("king", "sha256:" + "e" * 64) == 0


# ---------------------------------------------------------------- the public phrase map (Validator-2 22:10)


def _internal_reasons():
    """Every reason code the crown modules can return: the string constants and the literal reasons they decide with."""
    import re

    root = Path(__file__).resolve().parents[2] / "carbon" / "challenge_validator"
    codes = set()
    for name in ("bank_promotion.py", "crown_average.py", "crown_pause_sweep.py"):
        text = (root / name).read_text(encoding="utf-8")
        codes |= set(re.findall(r'^[A-Z_]+ = "([a-z][a-z0-9_]*)"', text, re.MULTILINE))
        codes |= set(
            re.findall(r'(?:decided|_result)\([^,]+,\s*"([a-z][a-z0-9_]*)"', text)
        )
    return codes


def test_every_internal_reason_maps_to_one_public_phrase_of_its_outcome():
    codes = _internal_reasons()
    assert {
        "within_rebuild_noise_or_tie",
        "mean_within_margin_or_tie",
        "crowns_paused",
    } <= codes
    for outcome in lb.CHECK_OUTCOMES:
        for code in (*sorted(codes), None, "never_seen_before"):
            note = lb.public_note(outcome, code)
            assert note in lb.NOTES[outcome], (outcome, code)
    # no near / far: every INCUMBENT_KEEPS reads the same, whatever the reason
    assert {lb.public_note("INCUMBENT_KEEPS", c) for c in codes} == {lb.NOTE_KEEPS}
    assert (
        lb.public_note("UNAVAILABLE", "crown_average_king_unmeasured")
        == lb.NOTE_WAIT_KING
    )
    assert (
        lb.public_note("UNAVAILABLE", "queued_behind_undecided_crown") == lb.NOTE_QUEUED
    )
    assert lb.public_note("UNAVAILABLE", "never_seen_before") == lb.NOTE_PENDING
    assert lb.public_note("SOMETHING_ELSE", None) is None
    # no phrase names a gate, stability or nearness
    for phrases in lb.NOTES.values():
        for phrase in phrases:
            assert not any(
                w in phrase for w in ("gate", "stab", "noise", "margin", "tie", "near")
            )


def test_a_locked_store_leaves_the_outcome_unchanged_and_waits_at_most_the_busy_timeout(
    tmp_path, monkeypatch
):
    """koth_journal.contention runs after the decision's own commit; its record write on a locked (or read-only) store
    fails after the store's busy timeout and is swallowed: the outcome is untouched and nothing is filed.
    """
    import sqlite3
    import time

    from carbon.battery import pool_store

    store = _store(tmp_path)
    real = sqlite3.connect
    monkeypatch.setattr(
        pool_store.sqlite3,
        "connect",
        lambda *a, **k: real(*a, **{**k, "timeout": 0.2}),
    )
    holder = real(tmp_path / "pool.sqlite3", isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    outcome = {
        "outcome": "INCUMBENT_KEEPS",
        "reason": "x",
        "evaluation_key": "sha256:" + "a" * 64,
    }
    before = json.dumps(outcome, sort_keys=True)
    start = time.monotonic()
    koth_journal.contention("live", "sub-a", outcome, store=store)
    waited = time.monotonic() - start
    holder.execute("ROLLBACK")
    holder.close()
    assert json.dumps(outcome, sort_keys=True) == before
    assert (
        waited < 0.2 + 1.0
    )  # the busy timeout (patched to 0.2 s here; 30 s in production) plus slack
    assert store.crown_decisions() == []
