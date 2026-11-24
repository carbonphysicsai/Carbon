"""The v7 operator run's count (owner DASHBOARD-ALL-TIME-SUBMISSIONS; definition v2 5744): the distinct recipe digests
among the door's admitted submissions, all time, read from the receiver's attempt ledger read-only.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "dev"))

import launch_board_operator as op


def _ledger(tmp_path, rows, *, table=True):
    path = tmp_path / "attempts.sqlite3"
    with sqlite3.connect(path) as db:
        if table:
            db.execute(
                "CREATE TABLE recipe_copy_digests(submission_id TEXT PRIMARY KEY, recipe_digest TEXT NOT NULL)"
            )
            db.executemany("INSERT INTO recipe_copy_digests VALUES(?,?)", rows)
        else:
            db.execute("CREATE TABLE other(x)")
    os.chmod(path, 0o600)
    return {"ledger": str(path)}


def test_the_count_is_distinct_recipe_digests_across_admitted_submissions(tmp_path):
    rows = [
        ("rtsk_a", "sha256:" + "1" * 64),
        ("rtsk_b", "sha256:" + "1" * 64),  # the same recipe resubmitted counts once
        ("rtsk_c", "sha256:" + "2" * 64),
    ]
    assert op.unique_designs(_ledger(tmp_path, rows)) == 2


def test_an_empty_ledger_table_counts_zero(tmp_path):
    assert op.unique_designs(_ledger(tmp_path, [])) == 0


def test_a_ledger_without_the_table_or_file_refuses_never_zero(tmp_path):
    with pytest.raises(op.OperatorRefused, match="ledger_designs_unavailable"):
        op.unique_designs(_ledger(tmp_path, [], table=False))
    with pytest.raises((op.OperatorRefused, OSError)):
        op.unique_designs({"ledger": str(tmp_path / "missing.sqlite3")})


def test_the_ledger_is_never_written(tmp_path):
    config = _ledger(tmp_path, [("rtsk_a", "sha256:" + "1" * 64)])
    before = (tmp_path / "attempts.sqlite3").read_bytes()
    op.unique_designs(config)
    assert (tmp_path / "attempts.sqlite3").read_bytes() == before


def test_v7_is_a_known_board_and_a_v2_family_run():
    assert "v7" in op.BOARDS
