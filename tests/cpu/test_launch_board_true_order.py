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
from carbon.scoring import grade_feedback as gf

NOW = datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC)
KEY = lb.LaunchBoardKey(bytes(range(32)))
A, B, C, D, E = (("5" + letter * 47) for letter in "ABCDE")
#: the Challenge's registered noise, as the king document (`_args`) carries it: the Ladder's step is max(eta, it)
NOISE = _args()["rebuild_noise"]
PACK = "sha256:" + "c" * 64  # the board rows' exam: the sealed evaluation pack digest


def _floor(value):
    """What the Ladder publishes for ``value``: floored to its step."""
    return gf.floor_to_step(value, NOISE["value"])


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
        rebuild_noise=NOISE,
    )


def _ranks(board):
    return [(row["hotkey"], row["rank"]) for row in board["ladder"]]


def test_the_king_is_first_even_with_a_higher_exact_challenger():
    exact = {
        HOTKEY: 0.7123,
        A: 0.7129,
    }  # inside one step (0.02): the shown totals tie at 0.70
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
    }  # all three challengers show 0.70
    board = _board(exact)
    assert _ranks(board) == [(HOTKEY, 1), (B, 2), (C, 3), (A, 4)]
    assert {row["total"] for row in board["ladder"][1:]} == {lb.floor9(_floor(0.71))}


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


def _build(rows, exact, **extra):
    # the king (HOTKEY) holds the crown at 0.90 in every row set built here
    king = {"hotkey": HOTKEY, "total": 0.90, "since_epoch": 12}
    return lb.build(
        king_document=kp.document_v2(**_args(king=king)),
        rows=rows,
        network="testnet",
        key=KEY,
        version=1,
        now=NOW,
        crown_changes=[],
        **({"exact_totals": exact} if exact is not None else {}),
        **extra,
    )


def test_the_v2_board_needs_the_exact_totals_and_the_noise_and_refuses_malformed_ones():
    rows = _rows({HOTKEY: 0.7123})
    with pytest.raises(lb.BoardRefused, match="board_exact_totals_required"):
        _build(rows, None, rebuild_noise=NOISE)
    # no default: None is a value (no registered noise), so leaving it out is refused
    with pytest.raises(lb.BoardRefused, match="board_rebuild_noise_required"):
        _build(rows, {HOTKEY: 0.7123})
    with pytest.raises(lb.BoardRefused, match="board_rebuild_noise"):
        _build(rows, {HOTKEY: 0.7123}, rebuild_noise={"value": 0.01})
    good = {HOTKEY: 0.7123, A: 0.7123}
    for bad in (
        {HOTKEY: 0.7123, A: float("nan")},
        {HOTKEY: 0.7123, A: 1.5},
        {HOTKEY: 0.7123, A: 1},  # an int is not an exact float total
    ):
        with pytest.raises(lb.BoardRefused, match="board_exact"):
            _build(_rows(good), bad, rebuild_noise=NOISE)


# --- the consistency check (Validator 1 Nov 19:05 CST) ------------------------------------------------------------


def test_an_exact_total_that_does_not_floor_to_its_rows_total_falls_back_to_the_floored_rule():
    # A shows 0.70 on the Ladder; an exact total of 0.7349 floors to 0.72 at the Ladder's step, so it is not A's total
    # (another exam's grade, or a read that raced a new grade): A keeps the floored rule and ties B, whose exact total
    # is consistent. Without the check A (0.7349) would rank above B (0.7101).
    rows = [_row(HOTKEY, 0.90), _row(A, 0.7001), _row(B, 0.7101)]
    exact = {HOTKEY: 0.90, A: 0.7349, B: 0.7101}
    assert lb.floor9(_floor(exact[A])) != rows[1][1]["total"]
    board = _build(rows, exact, rebuild_noise=NOISE)
    assert _ranks(board) == [(HOTKEY, 1), (B, 2), (A, 2)]
    # consistent, the same exact total orders the row
    rows[1] = _row(A, 0.7349)
    assert _ranks(_build(rows, exact, rebuild_noise=NOISE)) == [
        (HOTKEY, 1),
        (A, 2),
        (B, 3),
    ]
    # below the published total, or for a row with no best: never used, never a refusal
    rows = [_row(HOTKEY, 0.90), _row(A, 0.7101), _row(B, 0.7149), _row(C, None)]
    board = _build(
        rows, {HOTKEY: 0.90, A: 0.65, B: 0.7149, C: 0.5}, rebuild_noise=NOISE
    )
    assert _ranks(board) == [(HOTKEY, 1), (B, 2), (A, 2), (C, 4)]  # listed exact-first


def test_the_check_floors_at_the_registered_noise_not_at_eta():
    # an F02-like registration: step 0.05 > eta. A row floored on that step shows 0.70 for 0.7349; checked at eta
    # (0.72) the same exact total would be refused as inconsistent
    wide = {"value": 0.05, "measurement_digest": "sha256:" + "a" * 64}
    shown = lb.floor9(gf.floor_to_step(0.7349, wide["value"]))
    scored = {"status": "IMPROVED", "gate_names": []}
    rows = [
        (A, {"total": shown}, scored),
        (B, {"total": lb.floor9(gf.floor_to_step(0.7101, wide["value"]))}, scored),
    ]
    exact = {A: 0.7349, B: 0.7101}
    document = kp.document_v2(**_args(king=None))
    build = lb.build(
        king_document=document,
        rows=rows,
        network="testnet",
        key=KEY,
        version=1,
        now=NOW,
        crown_changes=[],
        exact_totals=exact,
        rebuild_noise=wide,
    )
    assert _ranks(build) == [(A, 1), (B, 2)]  # both consistent at 0.05: the exact order
    at_eta = lb.build(
        king_document=document,
        rows=rows,
        network="testnet",
        key=KEY,
        version=1,
        now=NOW,
        crown_changes=[],
        exact_totals=exact,
        rebuild_noise=None,
    )
    # A inconsistent at eta: no exact total, so its 0.70 group is one floored tie (listed exact-first)
    assert _ranks(at_eta) == [(B, 1), (A, 1)]


def _partial(shown, exact):
    """A v2 board whose rows show ``shown`` (floored) and whose exact totals are only ``exact``; the king holds the
    crown at its own shown total."""
    document = kp.document_v2(
        **_args(king={"hotkey": HOTKEY, "total": shown[HOTKEY], "since_epoch": 12})
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
        rebuild_noise=NOISE,
    )


def test_rows_without_an_exact_total_keep_their_floored_order_and_ties():
    # the pool store holds an exact total only on the crown path (Motor, RB and BT boards failed closed on this): the
    # other rows order by their own floored totals as on v1, equal floored totals share a rank, nothing is invented
    shown = {HOTKEY: 0.80, A: 0.7129, B: 0.6544, C: 0.6512, D: None}
    board = _partial(shown, {HOTKEY: 0.80})
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
        rebuild_noise=NOISE,
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
    pack=PACK,
    version="ev-now-judge-97b1eda23adc",
    challenge="c",
):
    # the pool evidence names a judge-suffixed evaluation version (the TL's 19:04 counts), never the Ladder's label
    return {
        "owner": owner,
        "evidence": {
            "challenge": challenge,
            "evaluation_version": version,
            "evaluation_pack_digest": pack,
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
                {"hotkey": A, "request_digest": "d"}, 0.99, pack="sha256:" + "d" * 64
            ),  # another exam (a rotated bank), even under the same evaluation version
            _body(
                {"hotkey": A, "request_digest": "d"}, 0.98, pack=None
            ),  # evidence that names no exam
            _body(
                {"hotkey": B, "request_digest": "d"},
                0.99,
                status="MANDATORY_GATE_FAILED",
            ),  # not scored
            _body(
                {"hotkey": B, "request_digest": "d"},
                0.97,
                status="REQUIRED_LEG_MINIMUM_FAILED",
            ),  # not scored
            _body({"hotkey": C, "request_digest": "d"}, 0.5, challenge="other"),
            _body(host, 0.95),  # a host-owned derived row is never a hotkey
            _body("not a hotkey", 0.9),
            _body(
                {"hotkey": D, "request_digest": "d"}, 1
            ),  # an int is not an exact float total
        ]
    )
    exact = lb.exact_best_totals(store, challenge_id="c", exam_key=PACK)
    assert exact == {A: 0.7149}
    assert store.asked == []  # no king asked for
    # the Ladder's own scored statuses, exactly
    assert gf._SCORED == {"SCORED_DEVELOPMENT_CANDIDATE"}
    # no exam yet (nothing graded): no exact total
    assert lb.exact_best_totals(store, challenge_id="c", exam_key=None) == {}


def test_the_true_order_comes_from_pool_evaluations_under_the_rows_exam():
    # the TL's F02 case (1 Nov 19:04): every pool body names "<label>-judge-<id>", the Ladder the bare label. Matched
    # by the rows' exam key, the distinct exact totals order a floored group that used to show "=1" throughout
    store = _StubStore(
        [
            _body({"hotkey": h, "request_digest": "d"}, total)
            for h, total in ((A, 0.7101), (B, 0.7149), (C, 0.7125))
        ]
        + [_body({"hotkey": C, "request_digest": "d"}, 0.99, pack="sha256:" + "d" * 64)]
    )
    exact = lb.exact_best_totals(store, challenge_id="c", exam_key=PACK)
    assert exact == {A: 0.7101, B: 0.7149, C: 0.7125}
    rows = [_row(HOTKEY, 0.90), _row(A, 0.7101), _row(B, 0.7149), _row(C, 0.7125)]
    board = _build(rows, {**exact, HOTKEY: 0.90}, rebuild_noise=NOISE)
    assert _ranks(board) == [(HOTKEY, 1), (B, 2), (C, 3), (A, 4)]


def test_the_kings_entry_is_the_incumbents_standing_total_not_its_best_single_row():
    store = _StubStore(
        [_body({"hotkey": HOTKEY, "request_digest": "d"}, 0.80), _body(A, 0.7)],
        standing={"owner": {"hotkey": HOTKEY, "request_digest": "d"}, "total": 0.7712},
    )
    exact = lb.exact_best_totals(
        store, challenge_id="c", exam_key=PACK, king_model_id="m-king"
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
    exact = lb.exact_best_totals(store, challenge_id="c", exam_key=PACK)
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
    assert lb.exact_best_totals(store, challenge_id="c", exam_key=PACK) == {A: 0.7}


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
        rebuild_noise=NOISE,
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
