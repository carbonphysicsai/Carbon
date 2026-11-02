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


# --- --train-version (Validator 1 Nov 18:53 / 19:05) -------------------------------------------------------------------


def test_a_motor_17_grid_trains_on_the_registered_16_train(tmp_path, monkeypatch):
    # the grid check stays (Motor, 1.7); the TRAIN is the registered 1.6 one the 1.7 build spec declares
    assert version_registry.find("electric-motor-magnetics", "1.6") is not None
    asked = []

    def stop_at_train(challenge_id, version):
        asked.append((challenge_id, version))
        raise h.Refused("stopped_after_the_train_load")

    original = h.load_train
    monkeypatch.setattr(h, "load_train", stop_at_train)
    path, digest = _motor()
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
            "--train-version",
            "1.6",
        ],
        tmp_path,
    )
    assert code == 2 and asked == [("electric-motor-magnetics", "1.6")]
    # the TRAIN it names is the pinned 1.6 one, and it loads
    x, y = original("electric-motor-magnetics", "1.6")
    identity = h.train_identity("electric-motor-magnetics", "1.6")
    assert identity["version"] == "1.6" and identity["sha256"].startswith("sha256:")
    assert len(x) == len(y) > 0


def test_an_unregistered_train_version_is_refused(tmp_path, capsys):
    assert h.train_version_for("electric-motor-magnetics", "1.7", None) == "1.7"
    assert h.train_version_for("electric-motor-magnetics", "1.7", "1.6") == "1.6"
    with pytest.raises(h.Refused, match="train_version_not_registered"):
        h.train_version_for("electric-motor-magnetics", "1.7", "9.9")
    path, digest = _motor()
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
            "--train-version",
            "9.9",
        ],
        tmp_path,
    )
    assert code == 2
    assert "refused: train_version_not_registered" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["run", "predict"])
def test_the_train_version_is_passed_through(command, monkeypatch):
    seen = {}
    target = "run" if command == "run" else "predict_from_record"
    monkeypatch.setattr(h, target, lambda *a, **k: seen.update(k))
    first = ["--grid", "g"] if command == "run" else ["--record", "r"]
    extra = [] if command == "run" else ["--probe-inputs", "p"]
    argv = [
        command,
        *first,
        "--grid-digest",
        "d",
        "--challenge",
        "electric-motor-magnetics",
    ]
    argv += ["--version", "1.7", "--train-version", "1.6", *extra, "--out", "o"]
    assert h.main(argv) == 0
    assert seen["train_version"] == "1.6"
    assert h.main([a for a in argv if a not in ("--train-version", "1.6")]) == 0
    assert seen["train_version"] is None  # default: the --version itself


def _record(tmp_path, train):
    record = {
        "schema": h.RECORD_SCHEMA,
        "truths_read": False,
        "grid_digest": "sha256:" + "0" * 64,
        "challenge": {"id": "electric-motor-magnetics", "version": "1.7"},
        "contenders": [],
        "seed": 0,
    }
    if train is not None:
        record["train"] = train
    path = tmp_path / "record.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_predict_refuses_a_record_trained_on_another_train(tmp_path):
    def go(record_path):
        return h.predict_from_record(
            record_path,
            "sha256:" + "0" * 64,
            "1.7",
            tmp_path / "probe.npy",
            tmp_path / "out",
            challenge_id="electric-motor-magnetics",
            train_version="1.6",
        )

    other = {
        **h.train_identity("electric-motor-magnetics", "1.6"),
        "sha256": "sha256:" + "f" * 64,
    }
    with pytest.raises(h.Refused, match="record_trained_on_another_train"):
        go(_record(tmp_path, other))
    # a record from before the field names no TRAIN: only for its own version, never another
    with pytest.raises(h.Refused, match="record_trained_on_another_train"):
        go(_record(tmp_path, None))
