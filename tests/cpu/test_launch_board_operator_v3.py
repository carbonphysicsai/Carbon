"""The operator's v3 board (OWNER-CROWN-AVG-UNSTABLE-KING-01): the king's ``stability`` is one boolean read from the pool store's
crown-average record, read-only; no seed, mean or per-seed status reaches the signed bytes. v2 runs are untouched.
"""

# ruff: noqa: F811
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "dev"))

import launch_board_operator as operator
from test_launch_board_operator_v2 import (  # noqa: F401 - the fixtures and helpers
    COOLING,
    EXAM,
    KING,
    _board_bytes,
    _v2_fixture,
    door,
    frozen,
)

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import launch_board as lb


def _run(tmp_path, door, *, record=None):
    config, pool = _v2_fixture(tmp_path, door)
    if record is not None:
        PoolStore(pool).record_crown_average("m-king", EXAM, record)
        os.chmod(pool, 0o600)
    config["board"] = "v3"
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE", row
    return row, json.loads(_board_bytes(config, COOLING)), config


def test_a_seed_fragile_king_is_flagged_unstable(tmp_path, door, frozen):
    row, board, _ = _run(tmp_path, door, record={"statuses": ["OK", "FAILED_INFRA"]})
    assert row["board"] == "v3" and board["schema"] == lb.SCHEMA_V3
    assert board["king"]["stability"] == "UNSTABLE"
    assert lb.verify(board, board["validator"]["feed_key"]) == board


def test_a_measured_king_and_a_king_with_no_record_are_not_flagged(
    tmp_path, door, frozen
):
    record = {"mean": 0.7, "statuses": ["OK", "OK"]}
    _, measured, _ = _run(tmp_path / "a", door, record=record)
    assert measured["king"]["stability"] == "STABLE"
    _, none, _ = _run(tmp_path / "b", door)
    assert none["king"]["stability"] == "STABLE"  # nothing filed: not flagged


def test_no_seed_mean_or_status_reaches_the_signed_bytes(tmp_path, door, frozen):
    record = {"statuses": ["OK", "FAILED_INFRA"], "seeds": [11, 12, 13]}
    _, _board, config = _run(tmp_path, door, record=record)
    text = _board_bytes(config, COOLING).decode()
    for forbidden in ("seeds", "11, 12", "FAILED_INFRA", "statuses", '"mean"'):
        assert forbidden not in text
    assert KING in text  # the king is on the board; only the flag is new


def test_a_v2_run_is_unchanged(tmp_path, door, frozen):
    config, _ = _v2_fixture(tmp_path, door)
    (row,) = operator.run_once(config, version=9)
    board = json.loads(_board_bytes(config, COOLING))
    assert row["board"] == "v2" and board["schema"] == lb.SCHEMA_V2
    assert "stability" not in board["king"]
