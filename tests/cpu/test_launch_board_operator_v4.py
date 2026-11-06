"""The operator's v4 sources: the king's re-measure progress on his CURRENT key and the crown checks, read-only."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "dev"))

import launch_board_operator as operator
from test_launch_board_operator_v2 import (  # noqa: F401 - the fixtures and helpers
    COOLING,
    EXAM,
    OTHER,
    _board_bytes,
    _v2_fixture,
    door,
    frozen,
)

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import launch_board as lb


def _keyed(pool):
    """The king's latest evaluation names its key (as every real filed evaluation does), and OTHER is an admitted
    submission with a hotkey."""
    store = PoolStore(pool)
    with store.transaction() as db:
        row = db.execute("SELECT body FROM operations WHERE op_id='op-king'").fetchone()
        body = {**json.loads(row[0]), "evaluation_key": EXAM}
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?)",
            (
                "op-king-2",
                "private_evaluation.v1",
                "BOUND_DEVELOPMENT_ONLY",
                json.dumps(body),
            ),
        )
        columns = [
            c[1] for c in db.execute("PRAGMA table_info(submissions)").fetchall()
        ]
        values = {name: "x" for name in columns}
        values.update(submission_id="m-other", hotkey=OTHER)
        db.execute(
            f"INSERT INTO submissions({','.join(columns)}) VALUES({','.join('?' * len(columns))})",
            [values[c] for c in columns],
        )
    return store


def _v4(tmp_path, door, prepare):  # noqa: F811
    config, pool = _v2_fixture(tmp_path, door)
    store = _keyed(pool)
    prepare(store)
    os.chmod(pool, 0o600)
    config["board"] = "v4"
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE" and row["board"] == "v4", row
    return json.loads(_board_bytes(config, COOLING))


@pytest.mark.usefixtures("frozen")
def test_a_measured_king_and_a_decided_check(tmp_path, request):
    the_door = request.getfixturevalue("door")

    def prepare(store):
        store.record_crown_average("m-king", EXAM, {"mean": 0.7})
        store.record_crown_decision(
            "m-other", EXAM, "INCUMBENT_KEEPS", "mean_within_margin_or_tie"
        )

    board = _v4(tmp_path, the_door, prepare)
    assert board["schema"] == lb.SCHEMA_V4
    assert board["king"]["stability"] == "STABLE"
    assert board["king"]["measure"]["state"] == "MEASURED"
    assert board["crown_checks"] == [
        {
            "hotkey": OTHER,
            "state": "DECIDED",
            "outcome": "INCUMBENT_KEEPS",
            "note": "the king keeps the crown",
        }
    ]
    text = json.dumps(board)
    assert '"mean"' not in text  # the mean never leaves
    assert (
        "within_margin" not in text and "reason" not in text
    )  # the raw code never leaves
    assert "m-other" not in text and "m-king" not in text  # submission ids never leave


@pytest.mark.usefixtures("frozen")
def test_a_king_mid_re_measure_shows_its_progress_and_no_stability(tmp_path, request):
    the_door = request.getfixturevalue("door")

    def prepare(store):
        for seed in (11, 12, 13):
            store.record_crown_rebuild("m-king", EXAM, seed, False, {"total": 0.6})
        store.record_crown_rebuild("m-king", EXAM, 11, True, {"total": 0.6})
        store.record_crown_decision(
            "m-other", EXAM, "UNAVAILABLE", "crown_average_king_unmeasured"
        )

    board = _v4(tmp_path, the_door, prepare)
    n = board["king"]["measure"]["n"]
    assert board["king"]["measure"] == {"state": "IN_PROGRESS", "kept": 3, "n": n}
    assert board["king"]["stability"] is None
    assert board["crown_checks"][0]["state"] == "PENDING"


@pytest.mark.usefixtures("frozen")
def test_a_decision_without_an_admitted_hotkey_is_left_out(tmp_path, request):
    the_door = request.getfixturevalue("door")

    def prepare(store):
        store.record_crown_average("m-king", EXAM, {"mean": 0.7})
        store.record_crown_decision("krb_derived", EXAM, "INCUMBENT_KEEPS", None)

    board = _v4(tmp_path, the_door, prepare)
    assert board["crown_checks"] == []
