"""A board whose validator publishes its scores at 2 decimals (owner G-LEAD-91) says so in its unit, and the page then shows 2
decimals. Any other board is shown as before. Synthetic boards only."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "carbon" / "dashboard" / "web" / "dashboard.js"
NODE = shutil.which("node")

TWO = "0 to 1, rounded down to 2 decimals"
THREE = "0 to 1, to 3 decimals"
STEP = "0 to 1, rounded down to the Ladder step"


def test_the_reader_and_the_worker_hold_the_same_two_decimal_unit():
    from carbon.dashboard import launch

    worker = (ROOT / "carbon" / "dashboard" / "worker" / "feed.mjs").read_text(
        encoding="utf-8"
    )
    assert launch.UNIT_V6 == THREE and launch.UNIT_V6_TWO == TWO
    assert f'"{TWO}"' in worker and f'"{THREE}"' in worker


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_page_follows_the_boards_unit():
    cases = [
        # (unit or None, value, shown total, shown score to beat)
        (TWO, 0.97, "0.97", "0.97"),
        (TWO, 0.951, "0.95", "0.96"),
        (THREE, 0.97, "0.970", "0.970"),
        (THREE, 0.9519, "0.951", "0.952"),
        (STEP, 0.96, "0.960", "0.960"),
        (None, 0.97, "0.970", "0.970"),
    ]
    script = (
        "const D = require(process.argv[1]);"
        "const cases = JSON.parse(process.argv[2]);"
        "console.log(JSON.stringify(cases.map(c => {"
        "D.setPlaces(c[0] === null ? null : {ranking_section: {unit: c[0]}});"
        "return [D.total(c[1]), D.toBeat(c[1])]; })));"
    )
    done = subprocess.run(
        [NODE, "-e", script, str(PAGE), json.dumps(cases)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert json.loads(done.stdout) == [[c[2], c[3]] for c in cases]
