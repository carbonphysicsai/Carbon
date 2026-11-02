"""SHORTCUT-GAP (scripts/dev/exam_reads/shortcut_gap.py): the owner's three accuracy checks, measured, never judged.

Claims: per region class it reports every shortcut's and the default model's registered-atom accuracy and the noise ceiling (the
atom at |err| = U); the three gaps are (1) each shortcut's in-range minus out-of-range accuracy, (2) the ceiling minus the best
shortcut out of range, (3) the default model minus the best shortcut in range; no bar is applied; a refused (null) case scores the
atom 0 and makes its predictor GATE_FAILED; predictions bind to the probe set and their file by sha256; a tuned model is refused as
the default; without registered scales no atom gap is computed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads")
)

import shortcut_gap as gap
from test_sep_read import _case, _probe_set

IN, OUT = ("in_train", "in_train"), ("outer_shell", "extended_shell")


def _cases():
    return [_case(0.1 * i, 0.2, 1.0, klass=IN[0], region=IN[1]) for i in range(6)] + [
        _case(0.9, 0.1 * i, 1.0, klass=OUT[0], region=OUT[1]) for i in range(6)
    ]


def _predictions(tmp_path, name, kind, rows, probe_sha):
    body = {
        "schema": gap.PREDICTIONS_SCHEMA,
        "challenge": "electric-motor-magnetics",
        "version": "1.5",
        "name": name,
        "kind": kind,
        "probe_set_sha256": probe_sha,
        "outputs": ["y"],
        "rows": rows,
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(body))
    return {
        "predictions": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


@pytest.fixture
def scales(monkeypatch):
    monkeypatch.setattr(
        gap.sep_read, "agen_scales", lambda challenge, version: {"y": 1.0}
    )


def _config(tmp_path, shortcut_rows, default_rows, *, extra=()):
    probe = _probe_set(tmp_path, _cases())
    _doc, probe_sha = gap.sep_read.load_probe_set(probe)
    config = {
        "probe_set": str(probe),
        "shortcuts": [
            _predictions(tmp_path, "formula", "formula", shortcut_rows, probe_sha),
            *extra,
        ],
        "default_model": _predictions(
            tmp_path, "default", "default_model", default_rows, probe_sha
        ),
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    return path, probe_sha


def test_the_three_gaps_are_measured_and_no_bar_is_applied(tmp_path, scales):
    # the formula: exact in range, off by 2 out of range; the default model: off by 1 everywhere
    formula = [[1.0]] * 6 + [[3.0]] * 6
    default = [[2.0]] * 12
    result = gap.read(_config(tmp_path, formula, default)[0])
    a_in, a_out = 1.0, 1 / 3  # 1/(1+0), 1/(1+2)
    checks = result["checks"]
    assert checks["1_shortcuts_out_of_range"]["formula"]["in_range"] == pytest.approx(
        a_in
    )
    assert checks["1_shortcuts_out_of_range"]["formula"]["out_of_range"] == {
        "outer_shell": pytest.approx(a_out)
    }
    assert checks["1_shortcuts_out_of_range"]["formula"]["drop_in_minus_out"] == {
        "outer_shell": pytest.approx(a_in - a_out)
    }
    ceiling = 1 / (1 + 0.5)  # |err| = U = 0.5, scale 1
    assert result["classes"]["outer_shell"]["noise_ceiling"] == pytest.approx(ceiling)
    assert checks["2_ceiling_minus_best_shortcut"] == {
        "outer_shell": pytest.approx(ceiling - a_out)
    }
    assert checks["3_default_minus_best_shortcut_in_range"] == pytest.approx(0.5 - a_in)
    assert (
        checks["3_holds_as_measured"] is False
    )  # the default model does not beat the exact formula in range
    assert (
        "owner" in result["bars"] and result["status"] == "REPORT_FIELD_AGGREGATES_ONLY"
    )
    assert (
        result["classes"]["in_train"]["range"] == "in"
        and result["classes"]["outer_shell"]["range"] == "out"
    )


def test_the_best_shortcut_is_the_max_over_every_registered_shortcut(tmp_path, scales):
    probe = _probe_set(tmp_path, _cases())
    _doc, probe_sha = gap.sep_read.load_probe_set(probe)
    config = {
        "probe_set": str(probe),
        "shortcuts": [
            _predictions(
                tmp_path, "formula", "formula", [[1.0]] * 6 + [[3.0]] * 6, probe_sha
            ),
            _predictions(tmp_path, "fit", "fit", [[1.5]] * 12, probe_sha),
        ],
        "default_model": _predictions(
            tmp_path, "default", "default_model", [[1.0]] * 12, probe_sha
        ),
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    checks = gap.read(path)["checks"]
    # out of range the fit (|err| 0.5 -> 2/3) beats the formula (1/3): the ceiling gap is taken against the fit
    assert checks["2_ceiling_minus_best_shortcut"]["outer_shell"] == pytest.approx(
        1 / 1.5 - 1 / 1.5
    )
    assert (
        checks["3_holds_as_measured"] is False
    )  # in range the default ties the exact formula: not a strict beat


def test_a_refused_case_scores_zero_and_makes_its_predictor_gate_failed(
    tmp_path, scales
):
    result = gap.read(
        _config(tmp_path, [[1.0]] * 6 + [[3.0]] * 5 + [None], [[1.0]] * 12)[0]
    )
    assert result["predictors"]["formula"] == {
        "kind": "formula",
        "status": "GATE_FAILED",
        "gate_failed_cases": 1,
    }
    out = result["classes"]["outer_shell"]["predictors"]["formula"]
    assert out["gate_failed"] == 1 and out["accuracy"] == pytest.approx((5 / 3) / 6)


def test_predictions_bind_to_their_file_and_probe_set_and_the_default_is_untuned(
    tmp_path, scales
):
    path, probe_sha = _config(tmp_path, [[1.0]] * 12, [[1.0]] * 12)
    config = json.loads(path.read_text())
    Path(config["shortcuts"][0]["predictions"]).write_text("{}")
    with pytest.raises(gap.GapRefused, match="predictions_file_changed"):
        gap.read(path)
    path, probe_sha = _config(tmp_path / "b", [[1.0]] * 12, [[1.0]] * 12)
    config = json.loads(path.read_text())
    other = _predictions(tmp_path / "b", "formula", "formula", [[1.0]] * 12, "0" * 64)
    config["shortcuts"] = [other]
    path.write_text(json.dumps(config))
    with pytest.raises(gap.GapRefused, match="predictions_other_probe_set"):
        gap.read(path)
    config["default_model"] = {
        "predict_record": "x",
        "catalog_id": "v2.motor.fno",
        "fit": "tuned",
    }
    config["shortcuts"] = [
        _predictions(tmp_path / "b", "formula", "formula", [[1.0]] * 12, probe_sha)
    ]
    path.write_text(json.dumps(config))
    with pytest.raises(gap.GapRefused, match="default_model_must_be_untuned"):
        gap.read(path)


def test_without_registered_scales_no_atom_gap_is_computed(tmp_path, monkeypatch):
    monkeypatch.setattr(gap.sep_read, "agen_scales", lambda challenge, version: None)
    result = gap.read(_config(tmp_path, [[1.0]] * 12, [[1.0]] * 12)[0])
    assert result["checks"] is None and "|err|/U only" in result["metric"]
    assert result["classes"]["outer_shell"]["noise_ceiling"] == 1.0
