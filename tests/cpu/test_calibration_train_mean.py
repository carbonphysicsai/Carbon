"""ctrl.train_mean, the floor: every row is the public TRAIN mean, whatever the model
predicted (the Validator's proof-run ruling: an in-custody transform, no build)."""

from __future__ import annotations

import io

import numpy as np
import pytest
from test_calibration_grade import _bank, _rows

from carbon.challenge_validator import calibration_grade as cg


def _train(width=32, n=5):
    targets = np.arange(n * width, dtype=float).reshape(n, width)
    buffer = io.BytesIO()
    np.savez(buffer, inputs=np.ones((n, 3)), targets=targets)
    return buffer.getvalue(), targets


def _apply(rows, train_raw, bank=None, challenge="f02", control=None):
    return cg.apply_control(
        control or {"name": "ctrl.train_mean"},
        rows,
        bank or _bank(),
        challenge,
        train_raw=train_raw,
    )


def test_every_row_is_the_train_mean_and_the_predictions_are_ignored():
    raw, targets = _train()
    bank = _bank()
    rows = _rows(bank)
    other = [[v * 1000 - 3 for v in row] for row in rows]
    out, again = _apply(rows, raw, bank), _apply(other, raw, bank)
    assert out == again  # the model's predictions are not read
    assert len(out) == len(rows)
    assert all(row == [float(v) for v in targets.mean(axis=0)] for row in out)


@pytest.mark.parametrize("challenge", ["f08", "f02", "motor", "cooling"])
def test_it_applies_to_every_challenge(challenge):
    raw, _ = _train()
    bank = _bank()
    assert _apply(_rows(bank), raw, bank, challenge)


def test_a_caller_cannot_supply_the_train():
    raw, targets = _train()
    bank = _bank()
    out = _apply(
        _rows(bank),
        raw,
        bank,
        control={"name": "ctrl.train_mean", "params": {"_train_raw": b"forged"}},
    )
    assert out[0] == [float(v) for v in targets.mean(axis=0)]


def test_a_missing_or_mismatched_train_refuses():
    bank = _bank()
    rows = _rows(bank)
    with pytest.raises(cg.CalibrationRefused, match="control_train_required"):
        _apply(rows, None, bank)
    narrow, _ = _train(width=7)
    with pytest.raises(cg.CalibrationRefused, match="control_train_width"):
        _apply(rows, narrow, bank)


def test_it_runs_only_under_a_run_config_like_every_control():
    control = {"name": "ctrl.train_mean"}
    with pytest.raises(cg.CalibrationRefused, match="control_run_config_required"):
        cg._require_config(control, None, None)
    config = {"rule": "set before grading", "controls": [control]}
    cg._require_config(control, config, cg.config_digest(config))
