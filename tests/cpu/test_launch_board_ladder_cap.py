"""The board's ladder is capped by showing its TOP rows, never by refusing the whole board (live 116, 22 Nov 2026 11:20Z:
Motor 1.8 passed 512 counted hotkeys and every board run refused `board_ladder_size`, freezing the public feed).

Claims: a ladder longer than `MAX_LADDER` publishes exactly its best `MAX_LADDER` rows in rank order (rank 1 first);
the rows left out are the lowest totals; the board's counts are the shown rows' tally (what every validator checks);
a ladder at or under the cap is unchanged. Synthetic hotkeys and totals only.
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
