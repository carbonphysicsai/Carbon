"""Week-1 dashboard changes: Challenge order and description from the names file, the score to beat and the margin said
plainly on every launch card, and a crown-change strip drawn only from the signed board's `crown_changes`
(tests/cpu/dashboard_week1_check.cjs, in Node, no browser)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from carbon.challenge_validator import launch_board as lb
from carbon.dashboard import build, feed
from tests.cpu import test_dashboard_display as base


def test_the_week1_cards_and_strip(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed here")
    signer = lb.LaunchBoardKey(os.urandom(32))
    boards = [
        base._board("f02", "2.5", 0.519901, signer),
        base._board("f08-ribbed-bracket", "1.7", 0.52, signer),
    ]
    trust = feed.Trust(keys=frozenset({signer.public_key}))
    build.build(tmp_path / "site", boards, trust, now=base.NOW)
    check = base.CHECK.with_name("dashboard_week1_check.cjs")
    result = subprocess.run(
        [node, str(check), str(tmp_path / "site"), str(base.NOW)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["boards"] == 2


@pytest.mark.parametrize(
    "entry",
    [
        {"name": "Motor", "order": 1, "about": "Electric motor magnetics: torque"},
        {"name": "Motor", "about": "A plain line"},
        {"name": "Motor", "order": 99},
    ],
)
def test_the_names_file_accepts_order_and_about(tmp_path, entry):
    build.write_names(tmp_path, {"electric-motor-magnetics": entry})
    written = json.loads((tmp_path / "data" / "names.json").read_text(encoding="utf-8"))
    assert written["names"]["electric-motor-magnetics"] == entry


@pytest.mark.parametrize(
    "entry",
    [
        {"name": "Motor", "order": 0},
        {"name": "Motor", "order": 100},
        {"name": "Motor", "order": True},
        {"name": "Motor", "order": "1"},
        {"name": "Motor", "about": "<b>bold</b>"},
        {"name": "Motor", "about": "x" * 91},
        {"name": "Motor", "extra": "no"},
    ],
)
def test_the_names_file_refuses_a_bad_order_or_description(tmp_path, entry):
    with pytest.raises(ValueError):
        build.write_names(tmp_path, {"electric-motor-magnetics": entry})
    assert not (tmp_path / "data" / "names.json").exists()
