"""The v7 launch board (owner DASHBOARD-ALL-TIME-SUBMISSIONS, pick 'unique model designs'; definition v2 5744): v6's shape
plus ONE signed field, ``designs`` = ``{"unique_submitted": n}``, under its own signing domain. v1-v6 stay byte-identical.
"""

from __future__ import annotations

import copy

import pytest
from test_koth_display_three_decimals import (
    KING,
    KING_EXACT,
    NOISE,
    NOW,
    SIGNER,
    _args,
    _rows,
)

from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import launch_board as lb


def _board(**extra):
    return lb.build(
        king_document=kp.document_v3(**_args()),
        rows=_rows([(KING, KING_EXACT)]),
        network="testnet",
        key=SIGNER,
        version=7,
        now=NOW,
        crown_changes=[],
        exact_totals={KING: KING_EXACT},
        rebuild_noise=NOISE,
        stability="STABLE",
        crowned_utc=None,
        v6=True,
        **extra,
    )


def test_a_v7_board_is_the_v6_board_plus_the_signed_designs_count():
    v6, v7 = _board(), _board(designs=3891)
    assert v7["schema"] == lb.SCHEMA_V7 == "carbon.validator.launch-board.v7"
    assert v7["designs"] == {"unique_submitted": 3891}
    body6 = {k: v for k, v in v6.items() if k not in ("signature", "schema")}
    body7 = {k: v for k, v in v7.items() if k not in ("signature", "schema", "designs")}
    assert body6 == body7  # nothing else differs
    assert lb.verify(v7, SIGNER.public_key) == v7
    # its own signing domain: a v7 body never verifies as v6, and the count cannot be changed
    with pytest.raises(lb.BoardRefused):
        lb.verify({**v7, "schema": lb.SCHEMA_V6}, SIGNER.public_key)
    changed = copy.deepcopy(v7)
    changed["designs"]["unique_submitted"] = 3892
    with pytest.raises(lb.BoardRefused):
        lb.verify(changed, SIGNER.public_key)
    # the v6 board is unchanged by this head (no designs field)
    assert v6["schema"] == lb.SCHEMA_V6 and "designs" not in v6


@pytest.mark.parametrize("bad", [-1, True, 1.0, "3891", None, lb.MAX_DESIGNS + 1])
def test_a_designs_count_that_is_not_a_whole_number_in_range_refuses(bad):
    with pytest.raises(lb.BoardRefused, match="board_designs"):
        _board(designs=bad)


def test_designs_needs_a_v6_board():
    with pytest.raises(lb.BoardRefused, match="board_designs"):
        lb.build(
            king_document=kp.document_v2(**_args()),
            rows=_rows([(KING, KING_EXACT)]),
            network="testnet",
            key=SIGNER,
            version=7,
            now=NOW,
            crown_changes=[],
            exact_totals={KING: KING_EXACT},
            rebuild_noise=NOISE,
            designs=5,
        )


def test_the_check_refuses_extra_or_missing_designs_fields():
    board = _board(designs=0)
    unsigned = {k: v for k, v in board.items() if k != "signature"}
    for designs in ({}, {"unique_submitted": 1, "graded": 1}, [1]):
        with pytest.raises(lb.BoardRefused):
            lb.check({**unsigned, "designs": designs}, unsigned=True)
    without = {k: v for k, v in unsigned.items() if k != "designs"}
    with pytest.raises(lb.BoardRefused, match="board_fields"):
        lb.check(without, unsigned=True)
