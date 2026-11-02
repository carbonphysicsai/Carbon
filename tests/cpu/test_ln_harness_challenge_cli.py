"""The harness command names its Challenge (Launchpad, 1 Nov 18:53 CST: the command always checked a grid as F02's).

Claims: ``run`` and ``predict`` require ``--challenge`` and pass it through; a Motor grid run with its own Challenge id
gets past the grid check and then meets the version rule (Motor 1.7 is not registered: refused with its code, exit 2,
never a traceback); the same grid named as another Challenge's is refused; F02 behaves as before.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "scripts/dev/learning_necessity"
sys.path.insert(0, str(TOOLS))

import ln_harness as h

from carbon.challenge_kit import version_registry

MOTOR_GRID = TOOLS / "ln_grid_motor_1_7.json"


def _motor():
    grid = json.loads(MOTOR_GRID.read_text(encoding="utf-8"))
    return str(MOTOR_GRID), h.digest(grid)


def _run(args, tmp_path):
    return h.main(["run", *args, "--out", str(tmp_path / "out")])


def test_a_motor_grid_is_checked_as_motors_and_meets_the_version_rule(tmp_path, capsys):
    path, digest = _motor()
    assert version_registry.find("electric-motor-magnetics", "1.7") is None
    code = _run(
        [
            "--grid",
            path,
            "--grid-digest",
            digest,
            "--challenge",
            "electric-motor-magnetics",
            "--version",
            "1.7",
        ],
        tmp_path,
    )
    # past the grid check (the grid names Motor 1.7); refused at the TRAIN load, with its code and no traceback
    assert code == 2
    assert "refused: version_not_registered" in capsys.readouterr().err


def test_a_grid_named_as_another_challenges_is_refused(tmp_path, capsys):
    path, digest = _motor()
    code = _run(
        [
            "--grid",
            path,
            "--grid-digest",
            digest,
            "--challenge",
            "f02",
            "--version",
            "1.7",
        ],
        tmp_path,
    )
    assert code == 2
    assert "refused: grid_is_for_another_challenge_version" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["run", "predict"])
def test_the_challenge_is_required_and_passed_through(command, monkeypatch):
    seen = {}
    target = "run" if command == "run" else "predict_from_record"
    monkeypatch.setattr(h, target, lambda *a, **k: seen.update(k))
    first = ["--grid", "g"] if command == "run" else ["--record", "r"]
    extra = [] if command == "run" else ["--probe-inputs", "p"]
    base = [command, *first, "--grid-digest", "d", "--version", "1.7", *extra]
    with pytest.raises(SystemExit) as stopped:  # argparse: --challenge is required
        h.main([*base, "--out", "o"])
    assert stopped.value.code == 2
    assert h.main([*base, "--challenge", "electric-motor-magnetics", "--out", "o"]) == 0
    assert seen["challenge_id"] == "electric-motor-magnetics"
