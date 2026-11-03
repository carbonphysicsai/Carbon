"""The dashboard's display rules (tests/cpu/dashboard_display_check.cjs, in Node, no browser):

1. every public total is shown TRUNCATED to 3 decimals, never rounded up (Burst Thermal 0.519901 reads 0.519, Ribbed
   Bracket 0.52 reads 0.520); margins and the score to beat keep their exact reading (a bar is never understated);
2. the device-class chip is hidden while the feed carries one class and shown again once a second class appears. CPU and
   GPU boards are still never ranked together: the sort by class is untouched."""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from carbon.challenge_validator import launch_board as lb
from carbon.dashboard import build, feed

KING = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"
OTHER = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy"
NOW_DT = datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC)
NOW = 1_800_000_000
CHECK = Path(__file__).with_name("dashboard_display_check.cjs")


def _board(challenge_id, version, total, signer):
    rows = [
        (KING, {"total": total}, {"status": "IMPROVED", "gate_names": []}),
        (OTHER, {"total": 0.4}, {"status": "IMPROVED", "gate_names": []}),
    ]
    king = {
        "schema": "carbon.koth.public.v1",
        "challenge_id": challenge_id,
        "challenge_version": version,
        "exam_version_label": "exam-1",
        "king": {"hotkey": KING, "total": total, "since_epoch": 7},
        "margin": 0.007923679,
        "to_beat": 0.527824679,
        "baseline_total": None,
    }
    return lb.build(
        king_document=king,
        rows=rows,
        network="testnet",
        key=signer,
        version=3,
        now=NOW_DT,
    )


def test_totals_are_truncated_and_the_class_chip_follows_the_feed(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed here")
    signer = lb.LaunchBoardKey(os.urandom(32))
    boards = [
        _board("f02", "2.5", 0.519901, signer),
        _board("f08-ribbed-bracket", "1.7", 0.52, signer),
    ]
    trust = feed.Trust(keys=frozenset({signer.public_key}))
    build.build(tmp_path / "site", boards, trust, now=NOW)
    result = subprocess.run(
        [node, str(CHECK), str(tmp_path / "site"), str(NOW)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["boards"] == 2


def test_the_two_named_readings_are_pinned_in_the_source():
    source = (
        Path(__file__).parents[2] / "carbon/dashboard/web/dashboard.js"
    ).read_text(encoding="utf-8")
    # the helpers exist and the king and ladder totals go through them, not through fmt
    assert (
        "function total(v)" in source and "function classChipShown(classes)" in source
    )
    assert "fmt(k.value" not in source and "fmt(r.screening_value" not in source
    assert "fmt(entry.screening_value" not in source and "fmt(king.value" not in source
