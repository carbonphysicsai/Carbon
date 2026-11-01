"""OWNER-BOARD-TRUE-ORDER-01: the v2 board's rank is the TRUE order. The king is always rank 1, the others follow by
descending EXACT best total, equal ranks only when the exact totals are bit-equal; the published total stays
step-floored and no exact total reaches the signed bytes. The v1 board is unchanged."""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_koth_v2_crown_changes import HOTKEY, _args

from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import launch_board as lb

NOW = datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC)
KEY = lb.LaunchBoardKey(bytes(range(32)))
A, B, C, D, E = (("5" + letter * 47) for letter in "ABCDE")
STEP = 0.01


def _floor(value):
    return int(value / STEP) * STEP


def _row(hotkey, exact):
    best = None if exact is None else {"total": lb.floor9(_floor(exact))}
    return (hotkey, best, {"status": "IMPROVED", "gate_names": []})


def _rows(exact):
    return [_row(hotkey, value) for hotkey, value in exact.items()]


def _board(exact, *, king=HOTKEY, v2=True):
    document = (kp.document_v2 if v2 else kp.document)(
        **_args(
            king={"hotkey": king, "total": exact.get(king) or 0.7123, "since_epoch": 12}
        )
    )
    return lb.build(
        king_document=document,
        rows=_rows(exact),
        network="testnet",
        key=KEY,
        version=5,
        now=NOW,
        crown_changes=[] if v2 else None,
        exact_totals=exact if v2 else None,
    )


def _ranks(board):
    return [(row["hotkey"], row["rank"]) for row in board["ladder"]]


def test_the_king_is_first_even_with_a_higher_exact_challenger():
    exact = {
        HOTKEY: 0.7123,
        A: 0.7129,
    }  # inside one step (0.01): the shown totals tie at 0.71
    board = _board(exact)
    assert _ranks(board) == [(HOTKEY, 1), (A, 2)]
    assert (
        board["ladder"][0]["total"] == board["king"]["king"]["total"]
    )  # the king row follows the crown
    # a challenger far above the king still ranks below the king (the crown has not changed hands)
    assert _ranks(_board({HOTKEY: 0.40, A: 0.90}))[0] == (HOTKEY, 1)


def test_the_order_follows_exact_totals_inside_one_floored_step():
    exact = {
        HOTKEY: 0.80,
        A: 0.7101,
        B: 0.7149,
        C: 0.7125,
    }  # all three challengers show 0.71
    board = _board(exact)
    assert _ranks(board) == [(HOTKEY, 1), (B, 2), (C, 3), (A, 4)]
    assert {row["total"] for row in board["ladder"][1:]} == {lb.floor9(0.71)}


def test_bit_equal_exact_totals_share_a_rank_and_only_those():
    exact = {HOTKEY: 0.80, A: 0.7125, B: 0.7125, C: 0.7126, D: None}
    ranks = dict(_ranks(_board(exact)))
    assert ranks[HOTKEY] == 1
    assert ranks[C] == 2  # the highest exact challenger
    assert ranks[A] == ranks[B] == 3  # bit-equal: one rank, and the next rank skips
    assert ranks[D] == 5  # no best total yet: last
    # a total that differs in the last bit does not tie
    near = {HOTKEY: 0.80, A: 0.7125, B: 0.7125 + 1e-16 * 8}
    assert near[B] != near[A]
    assert len({r for _, r in _ranks(_board(near))[1:]}) == 2


def test_the_signed_bytes_hold_no_unfloored_total():
    exact = {HOTKEY: 0.8037421953, A: 0.7129184761, B: 0.7101552937}
    board = _board(exact)
    blob = lb._canonical({k: v for k, v in board.items() if k != "signature"})
    text = json.dumps(board)
    for value in exact.values():
        for rendering in (repr(value), f"{value:.9f}", f"{value:.12f}"):
            assert rendering not in blob and rendering not in text
    assert "exact" not in blob  # no field name that could carry one
    for row in board["ladder"]:
        assert row["total"] is None or lb.on_nine(row["total"])
        assert row["total"] == lb.floor9(
            _floor(exact[row["hotkey"]])
        )  # step-floored only
    assert lb.verify(board, KEY.public_key) == board


def test_the_v1_board_is_unchanged_and_ranks_by_the_floored_total_as_before():
    exact = {HOTKEY: 0.7123, A: 0.7129, B: 0.50}
    board = _board(exact, v2=False)
    assert board["schema"] == lb.SCHEMA and "crown_changes" not in board
    # equal FLOORED totals share rank 1 on v1, ordered by hotkey, with no king-first rule
    assert _ranks(board) == [(A, 1), (HOTKEY, 1), (B, 3)]


def test_the_v2_board_needs_the_exact_totals_and_refuses_inconsistent_ones():
    document = kp.document_v2(**_args())
    with pytest.raises(lb.BoardRefused, match="board_exact_totals_required"):
        lb.build(
            king_document=document,
            rows=_rows({HOTKEY: 0.7123}),
            network="testnet",
            key=KEY,
            version=1,
            crown_changes=[],
        )
    good = {HOTKEY: 0.7123, A: 0.7123}
    for bad in (
        {HOTKEY: 0.7123, A: 0.70},  # below A's shown (floored) total 0.71
        {HOTKEY: 0.7123, A: float("nan")},
        {HOTKEY: 0.7123, A: 1.5},
    ):
        with pytest.raises(lb.BoardRefused, match="board_exact"):
            lb.build(
                king_document=document,
                rows=_rows(good),
                network="testnet",
                key=KEY,
                version=1,
                crown_changes=[],
                exact_totals=bad,
            )
    with pytest.raises(
        lb.BoardRefused, match="board_exact"
    ):  # an exact total for a hotkey with no best
        lb.build(
            king_document=document,
            rows=_rows({HOTKEY: None}),
            network="testnet",
            key=KEY,
            version=1,
            crown_changes=[],
            exact_totals={HOTKEY: 0.5},
        )


def _partial(shown, exact):
    """A v2 board whose rows show ``shown`` (floored) and whose exact totals are only ``exact``."""
    document = kp.document_v2(
        **_args(king={"hotkey": HOTKEY, "total": 0.7123, "since_epoch": 12})
    )
    return lb.build(
        king_document=document,
        rows=_rows(shown),
        network="testnet",
        key=KEY,
        version=5,
        now=NOW,
        crown_changes=[],
        exact_totals=exact,
    )


def test_rows_without_an_exact_total_keep_their_floored_order_and_ties():
    # the pool store holds an exact total only on the crown path (Motor, RB and BT boards failed closed on this): the
    # other rows order by their own floored totals as on v1, equal floored totals share a rank, nothing is invented
    shown = {HOTKEY: 0.7123, A: 0.7129, B: 0.6544, C: 0.6512, D: None}
    board = _partial(shown, {HOTKEY: 0.7123})
    assert _ranks(board) == [(HOTKEY, 1), (A, 2), (B, 3), (C, 3), (D, 5)]
    # the king row shows the crown standing's total, as the king page does
    assert board["ladder"][0]["total"] == board["king"]["king"]["total"]
    for row in board["ladder"][1:]:
        assert row["total"] == (
            None
            if shown[row["hotkey"]] is None
            else lb.floor9(_floor(shown[row["hotkey"]]))
        )
    blob = lb._canonical({k: v for k, v in board.items() if k != "signature"})
    for value in (0.7129, 0.6544, 0.6512):
        assert repr(value) not in blob
    assert lb.verify(board, KEY.public_key) == board
    # mixed: a challenger with an exact total sorts by it, one without by its floored total (both show 0.71)
    # mixed: one shows 0.71 with an exact total, one without; compared on both floored totals they tie (Validator 17:25)
    mixed = _partial({HOTKEY: 0.80, A: 0.7101, B: 0.7149}, {HOTKEY: 0.80, A: 0.7101})
    assert _ranks(mixed) == [(HOTKEY, 1), (A, 2), (B, 2)]


def test_an_exact_total_orders_only_rows_that_also_hold_one():
    # Validator 17:25 CST: exact vs exact by the exact totals; exact vs floored-only on both FLOORED totals
    shown = {HOTKEY: 0.90, A: 0.7149, B: 0.7101, C: 0.7125, D: 0.6549, E: 0.6512}
    exact = {
        HOTKEY: 0.90,
        A: 0.7149,
        B: 0.7101,
        D: 0.6549,
        E: 0.6512,
    }  # C (0.71) has none
    board = _partial(shown, exact)
    ranks = dict(_ranks(board))
    # the 0.71 group holds C (no exact total): C ties A and B, so the whole group is one rank; listed exact-first
    assert ranks[A] == ranks[B] == ranks[C] == 2
    assert [r["hotkey"] for r in board["ladder"][1:4]] == [A, B, C]
    # the 0.65 group holds exact totals only: they order by them
    assert (ranks[D], ranks[E]) == (5, 6)


def test_a_challenger_without_an_exact_total_at_the_kings_shown_total_co_ranks_one():
    king_shown = _partial({HOTKEY: 0.7123}, {HOTKEY: 0.7123})["king"]["king"]["total"]
    document = kp.document_v2(
        **_args(king={"hotkey": HOTKEY, "total": 0.7123, "since_epoch": 12})
    )
    scored = {"status": "IMPROVED", "gate_names": []}
    rows = [
        (HOTKEY, {"total": 0.7123}, scored),
        (A, {"total": king_shown}, scored),  # equal floored total, no exact total held
        (B, {"total": lb.floor9(_floor(0.60))}, scored),
    ]
    board = lb.build(
        king_document=document,
        rows=rows,
        network="testnet",
        key=KEY,
        version=5,
        now=NOW,
        crown_changes=[],
        exact_totals={HOTKEY: 0.7123, B: 0.60},
    )
    assert _ranks(board) == [(HOTKEY, 1), (A, 1), (B, 3)]


def test_the_v1_board_is_untouched_by_the_partial_exact_rule():
    shown = {HOTKEY: 0.7123, A: 0.7129, B: 0.6544, C: 0.6512, D: None}
    document = kp.document(
        **_args(king={"hotkey": HOTKEY, "total": 0.7123, "since_epoch": 12})
    )
    board = lb.build(
        king_document=document,
        rows=_rows(shown),
        network="testnet",
        key=KEY,
        version=5,
        now=NOW,
    )
    assert board["schema"] == lb.SCHEMA
    assert _ranks(board) == [
        (A, 1),
        (HOTKEY, 1),
        (B, 3),
        (C, 3),
        (D, 5),
    ]  # v1: equal floored totals, by hotkey


def test_a_king_who_is_not_on_the_ladder_forces_nothing():
    board = _board({A: 0.9, B: 0.8}, king="5" + "Z" * 47)
    assert _ranks(board) == [(A, 1), (B, 2)]


def test_a_challenger_bit_equal_to_the_king_co_ranks_one_and_is_listed_after_the_king():
    exact = {HOTKEY: 0.7125, A: 0.7125, B: 0.7101}
    board = _board(exact)
    assert _ranks(board) == [
        (HOTKEY, 1),
        (A, 1),
        (B, 3),
    ]  # the king first; the tie is exact equality only
    near = {HOTKEY: 0.7125, A: 0.7125 + 8e-16}
    assert _ranks(_board(near)) == [(HOTKEY, 1), (A, 2)]


class _StubStore:
    """A stand-in for the pool store: private evaluation bodies and the incumbent standing."""

    def __init__(self, bodies, standing=None):
        self._bodies, self._standing = bodies, standing
        self.asked = []

    def private_evaluation_bodies(self):
        return list(self._bodies)

    def incumbent_standing(self, model_id):
        self.asked.append(model_id)
        return self._standing


def _body(
    owner,
    total,
    *,
    status="SCORED_DEVELOPMENT_CANDIDATE",
    version="ev-now",
    challenge="c",
):
    return {
        "owner": owner,
        "evidence": {
            "challenge": challenge,
            "evaluation_version": version,
            "model_p": {"total_score": total, "score_status": status},
        },
    }


def test_the_exact_totals_come_from_scored_private_evaluations_of_the_current_exam_only():
    host = "carbon-crown-average-host"
    store = _StubStore(
        [
            _body({"hotkey": A, "request_digest": "d"}, 0.71),
            _body({"hotkey": A, "request_digest": "d"}, 0.7149),  # the max for A
            _body(
                {"hotkey": A, "request_digest": "d"}, 0.99, version="ev-old"
            ),  # another exam
            _body(
                {"hotkey": B, "request_digest": "d"}, 0.99, status="GATE_FAILED"
            ),  # not scored
            _body({"hotkey": C, "request_digest": "d"}, 0.5, challenge="other"),
            _body(host, 0.95),  # a host-owned derived row is never a hotkey
            _body("not a hotkey", 0.9),
            _body(
                {"hotkey": D, "request_digest": "d"}, 1
            ),  # an int is not an exact float total
        ]
    )
    exact = lb.exact_best_totals(store, challenge_id="c", evaluation_version="ev-now")
    assert exact == {A: 0.7149}
    assert store.asked == []  # no king asked for


def test_the_kings_entry_is_the_incumbents_standing_total_not_its_best_single_row():
    store = _StubStore(
        [_body({"hotkey": HOTKEY, "request_digest": "d"}, 0.80), _body(A, 0.7)],
        standing={"owner": {"hotkey": HOTKEY, "request_digest": "d"}, "total": 0.7712},
    )
    exact = lb.exact_best_totals(
        store, challenge_id="c", evaluation_version="ev-now", king_model_id="m-king"
    )
    assert exact == {
        HOTKEY: 0.7712,
        A: 0.7,
    }  # the crown-average mean replaces the single best row
    assert store.asked == ["m-king"]


def test_the_helper_output_builds_the_v2_board_and_never_reaches_the_bytes():
    store = _StubStore(
        [
            _body({"hotkey": HOTKEY, "request_digest": "d"}, 0.7123),
            _body({"hotkey": A, "request_digest": "d"}, 0.7129),
        ]
    )
    exact = lb.exact_best_totals(store, challenge_id="c", evaluation_version="ev-now")
    board = _board(exact)
    assert _ranks(board) == [(HOTKEY, 1), (A, 2)]
    assert "0.7129" not in json.dumps(board) and "0.7123" not in json.dumps(board)


def test_the_real_pool_store_exposes_the_bodies_read_only(tmp_path):
    from carbon.battery.pool_store import PoolStore

    store = PoolStore(tmp_path / "pool.sqlite3")
    assert store.private_evaluation_bodies() == []
    with store.transaction() as db:
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?)",
            (
                "op1",
                "private_evaluation.v1",
                "BOUND_DEVELOPMENT_ONLY",
                json.dumps(_body({"hotkey": A, "request_digest": "d"}, 0.7)),
            ),
        )
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?)",
            ("op2", "private_evaluation.v1", "OTHER_STATE", "{}"),
        )
    bodies = store.private_evaluation_bodies()
    assert [b["owner"]["hotkey"] for b in bodies] == [A]
    assert lb.exact_best_totals(
        store, challenge_id="c", evaluation_version="ev-now"
    ) == {A: 0.7}


def test_a_king_whose_crown_mean_is_below_its_single_best_shows_the_floored_mean_like_the_koth_page():
    document = kp.document_v2(
        **_args(king={"hotkey": HOTKEY, "total": 0.7712, "since_epoch": 12})
    )
    koth_total = document["king"]["total"]  # what the king page shows: the floored mean
    single_best = {
        "total": lb.floor9(0.80)
    }  # the Ladder's best row for the king: a higher single grade
    rows = [
        (HOTKEY, single_best, {"status": "IMPROVED", "gate_names": []}),
        _row(A, 0.7129),
    ]
    board = lb.build(
        king_document=document,
        rows=rows,
        network="testnet",
        key=KEY,
        version=5,
        now=NOW,
        crown_changes=[],
        exact_totals={
            HOTKEY: 0.7712,
            A: 0.7129,
        },  # the king's entry: the incumbent standing's mean
    )
    king_row = next(r for r in board["ladder"] if r["hotkey"] == HOTKEY)
    assert king_row["total"] == board["king"]["king"]["total"] == koth_total
    assert koth_total < lb.floor9(
        0.80
    )  # the single best is NOT what the king row shows
    assert king_row["rank"] == 1 and _ranks(board) == [(HOTKEY, 1), (A, 2)]
    assert lb.verify(board, KEY.public_key) == board
    # other rows keep their floored ladder best
    other = next(r for r in board["ladder"] if r["hotkey"] == A)
    assert other["total"] == lb.floor9(_floor(0.7129))
