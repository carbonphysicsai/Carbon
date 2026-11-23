"""The board's ladder is capped by showing its TOP rows, never by refusing the whole board (live 116, 22 Nov 2026 11:20Z:
Motor 1.8 passed 512 counted hotkeys and every board run refused `board_ladder_size`, freezing the public feed).

Claims: a ladder longer than `MAX_LADDER` publishes exactly its best `MAX_LADDER` rows in rank order (rank 1 first);
the rows left out are the lowest totals; the board's counts are the shown rows' tally (what every validator checks);
a ladder at or under the cap is unchanged; the producer's cap equals the deployed readers' (board step 2, 23 Nov) and
the door serves a worst-case board at that cap (`launch_board_file.MAX_BYTES`). Synthetic hotkeys and totals only.
"""

from __future__ import annotations

import pytest

from carbon.challenge_validator import launch_board as lb

_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _hotkey(i):
    digits = ""
    n = i
    for _ in range(6):
        digits = _ALPHABET[n % len(_ALPHABET)] + digits
        n //= len(_ALPHABET)
    return "5" + "C" * 41 + digits  # 48 base58 characters, the shape the board checks


def _rows(count):
    return [
        (_hotkey(i), {"total": round(0.9 - i * 0.0001, 9)}, {"status": "IMPROVED"})
        for i in range(count)
    ]


def test_a_ladder_over_the_cap_shows_its_top_rows_in_rank_order():
    count = lb.MAX_LADDER + 88
    out = lb.ladder_rows(_rows(count))
    assert len(out) == lb.MAX_LADDER
    assert [row["rank"] for row in out] == list(range(1, lb.MAX_LADDER + 1))
    shown = {row["hotkey"] for row in out}
    assert shown == {_hotkey(i) for i in range(lb.MAX_LADDER)}  # the best totals
    assert lb.counts(out)["graded"] == lb.MAX_LADDER


@pytest.mark.parametrize("count", [1, lb.MAX_LADDER - 1, lb.MAX_LADDER])
def test_a_ladder_at_or_under_the_cap_is_unchanged(count):
    out = lb.ladder_rows(_rows(count))
    assert len(out) == count
    assert out[0]["hotkey"] == _hotkey(0) and out[0]["rank"] == 1


# --- the reader side (Lead handoff 22 Nov 7 3a): launch.py and the Worker accept up to 2048 rows, before the producer ---


def test_the_reader_and_the_worker_share_one_raised_cap_above_the_producer():
    import pathlib
    import re

    from carbon.dashboard import launch

    worker = (
        pathlib.Path(__file__).resolve().parents[2]
        / "carbon"
        / "dashboard"
        / "worker"
        / "feed.mjs"
    ).read_text(encoding="utf-8")
    (js_cap,) = re.findall(r"const LAUNCH_MAX_LADDER = (\d+);", worker)
    assert int(js_cap) == launch.MAX_LADDER == 2048
    # the producer never publishes more rows than the deployed readers accept (it rose only after they were live:
    # board step 2, infra row 4729), and it now shows as many as they accept
    assert lb.MAX_LADDER <= launch.MAX_LADDER
    assert lb.MAX_LADDER == launch.MAX_LADDER == 2048


def test_the_reader_accepts_a_board_up_to_its_cap_and_refuses_one_row_more(
    monkeypatch,
):
    from carbon.dashboard import feed, launch
    from tests.cpu import test_launch_board as tlb

    # a producer allowed past the reader's cap, to hand the reader a board at and over it
    monkeypatch.setattr(lb, "MAX_LADDER", launch.MAX_LADDER + 1)
    board, trust = tlb._board(_rows(launch.MAX_LADDER))
    projected = feed.project(board, trust)
    assert board["counts"]["graded"] == launch.MAX_LADDER
    assert projected is not None
    board, trust = tlb._board(_rows(launch.MAX_LADDER + 1))
    with pytest.raises(feed.FeedRefused) as refused:
        feed.project(board, trust)
    assert refused.value.code == "ladder_invalid"


# --- board step 2: the door serves the largest board the producer can now write ---


def test_the_door_serves_a_worst_case_board_at_the_producer_cap(tmp_path):
    from carbon.challenge_validator import launch_board_file as lbf
    from carbon.challenge_validator.feed_file import write_feed
    from tests.cpu import test_launch_board_feed as tlbf

    # every row but the king's GATE_FAILED with MAX_GATES names of 64 characters (the longest `_GATE` allows)
    gates = [f"g{i:02d}" + "x" * 61 for i in range(lb.MAX_GATES)]
    assert all(len(g) == 64 and lb._GATE.fullmatch(g) for g in gates)
    rows = [(tlbf.KING, {"total": 0.64}, {"status": "IMPROVED", "gate_names": []})]
    rows += [
        (_hotkey(i), None, {"status": "GATE_FAILED", "gate_names": gates})
        for i in range(lb.MAX_LADDER - 1)
    ]
    signer = tlbf._signer()
    board = lb.build(
        king_document=tlbf._king_document(),
        rows=rows,
        network="testnet",
        key=signer,
        version=3,
        now=tlbf.NOW,
    )
    assert len(board["ladder"]) == lb.MAX_LADDER
    path = tmp_path / "board.json"
    write_feed(path, board)  # as the operator writes it
    assert path.stat().st_size <= lbf.MAX_BYTES
    served = lbf.read_board(path, tlbf.CHALLENGE.challenge_id)
    assert served is not None and len(served["ladder"]) == lb.MAX_LADDER
