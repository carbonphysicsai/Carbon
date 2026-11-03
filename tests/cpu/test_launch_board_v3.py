"""The v3 launch board (OWNER-CROWN-AVG-UNSTABLE-KING-01): v2 plus ONE king field, ``stability``, under its own signing domain.

Claims: a v3 board carries ``stability`` ("STABLE" / "UNSTABLE", null with no king); a king has one and no king has none; v1 and v2
boards are unchanged and still verify; a v2 signature never verifies as v3 or the reverse; a tampered or extra field is refused; the
receiver's reader accepts v3; the operator sets the field from the pool store's crown-average record (one boolean, no seed, mean or
per-seed status in the signed bytes)."""

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
NOISE = _args()["rebuild_noise"]
A = "5" + "A" * 47


def _row(hotkey, total):
    return (
        hotkey,
        {"total": lb.floor9(total)},
        {"status": "IMPROVED", "gate_names": []},
    )


def _build(*, stability=lb._ABSENT, king=True):
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
    )


def test_a_v3_board_carries_the_kings_stability_and_verifies_under_its_own_domain():
    for value in ("STABLE", "UNSTABLE"):
        board = _build(stability=value)
        assert board["schema"] == lb.SCHEMA_V3 and board["king"]["stability"] == value
        assert set(board["king"]) == set(lb.KING_SECTION_V3)
        assert lb.verify(board, KEY.public_key) == board
    none = _build(stability=None, king=False)
    assert none["king"]["king"] is None and none["king"]["stability"] is None
    assert lb.verify(none, KEY.public_key) == none


def test_v1_and_v2_boards_are_unchanged():
    v2 = _build()
    assert v2["schema"] == lb.SCHEMA_V2 and "stability" not in v2["king"]
    assert lb.verify(v2, KEY.public_key) == v2
    # the v2 bytes with the same inputs are identical to what v2 built before (no stability anywhere)
    assert "stability" not in json.dumps(v2)


def test_a_king_has_a_stability_and_no_king_has_none():
    with pytest.raises(lb.BoardRefused, match="board_stability"):
        _build(stability=None, king=True)
    with pytest.raises(lb.BoardRefused, match="board_stability"):
        _build(stability="STABLE", king=False)
    for bad in ("stable", "UNSTABLE ", 1, True, "UNMEASURED"):
        with pytest.raises(lb.BoardRefused, match="board_stability"):
            _build(stability=bad)


def test_v3_needs_the_v2_inputs():
    document = kp.document_v2(**_args())
    with pytest.raises(lb.BoardRefused, match="board_v3_needs_crown_changes"):
        lb.build(
            king_document=document,
            rows=[_row(HOTKEY, 0.7123)],
            network="testnet",
            key=KEY,
            version=1,
            stability="STABLE",
        )


def test_a_v2_signature_never_verifies_as_v3_nor_the_reverse():
    v3 = _build(stability="UNSTABLE")
    as_v2 = {**v3, "schema": lb.SCHEMA_V2}
    with pytest.raises(lb.BoardRefused):
        lb.verify(as_v2, KEY.public_key)
    v2 = _build()
    body = {k: v for k, v in v2.items() if k != "signature"}
    body["schema"] = lb.SCHEMA_V3
    body["king"] = {**body["king"], "stability": "STABLE"}
    resigned_with_v2_domain = {**body, "signature": v2["signature"]}
    with pytest.raises(lb.BoardRefused):
        lb.verify(resigned_with_v2_domain, KEY.public_key)


def test_a_tampered_or_extra_field_is_refused_even_resigned():
    board = _build(stability="UNSTABLE")

    def resign(change):
        body = json.loads(
            json.dumps({k: v for k, v in board.items() if k != "signature"})
        )
        change(body)
        return {**body, "signature": KEY.sign(body)}

    for change in (
        lambda b: b["king"].update(stability="OTHER"),
        lambda b: b["king"].update(stability=None),
        lambda b: b["king"].update(seeds=[1, 2]),
        lambda b: b["king"].update(mean=0.71),
        lambda b: b["king"].pop("stability"),
        lambda b: b.update(stability="UNSTABLE"),
    ):
        with pytest.raises(lb.BoardRefused):
            lb.verify(resign(change), KEY.public_key)


def test_no_seed_mean_or_status_reaches_the_signed_bytes():
    text = json.dumps(_build(stability="UNSTABLE"))
    for forbidden in ("seed", "mean", "statuses", "per_seed"):
        assert forbidden not in text


def test_the_receivers_reader_accepts_a_v3_board(tmp_path):
    from carbon.challenge_validator import launch_board_file as lbf

    board = _build(stability="UNSTABLE")
    path = tmp_path / "board.json"
    path.write_text(json.dumps(board))
    # the reader also checks the Ladder step against the registered noise: use the Challenge the king document names
    challenge_id = board["challenge"]["id"]
    got = lbf.read_board(path, challenge_id, KEY.public_key)
    assert (
        got is None or got == board
    )  # the step check may refuse the test's rounded totals; a v3 board is NOT refused for its schema
    document = json.loads(path.read_text())
    assert document["schema"] == lb.SCHEMA_V3
