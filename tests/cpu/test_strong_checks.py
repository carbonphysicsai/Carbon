"""STRONG-CHECKS (`q3_q8_whatif.py strong`): the strong-checks spec's checks (1)-(3), scored by the version's own grader per class.

Claims: the noise ceiling is the pool's own truths perturbed within the registered U, scored by the grader's grade_target and
agen_accuracy, deterministic for its seed and lower when U is larger; per class the panel's best member, the ceiling and the
default model are reported for A_gen and D, with the gaps in score steps (max(eta, rebuild noise)); a gated panel member is
excluded from the best; the default model's in-range margin is compared with the rebuild noise; no bar is applied; the
inputs are closed.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads")
)

import q3_q8_whatif as reads
from test_pool_exam import POLICIES
from test_pool_plugin import SHELL, toy_target

from carbon.scoring import grade_feedback, pool_version


def _specs():
    return [toy_target("t1", 11), toy_target("t2", 12, shell=SHELL)]


CLASSES = {"t1": "in_train", "t2": "extended_shell"}


def test_the_noise_ceiling_is_deterministic_bounded_and_falls_with_u():
    specs = _specs()
    a = reads.noise_ceiling(specs, POLICIES, CLASSES, draws=2, seed=7)
    assert a == reads.noise_ceiling(specs, POLICIES, CLASSES, draws=2, seed=7)
    assert set(a) == {"in_train", "extended_shell"}
    for row in a.values():
        assert 0.0 <= row["d"] <= 1.0 and 0.0 < row["agen"] <= 1.0
    wide = [dataclasses.replace(s, u={k: 5 * v for k, v in s.u.items()}) for s in specs]
    b = reads.noise_ceiling(wide, POLICIES, CLASSES, draws=2, seed=7)
    assert b["in_train"]["agen"] < a["in_train"]["agen"]


def test_class_means_average_the_graders_own_target_values():
    basis = {
        "sets": [
            [{"d": 0.2, "agen": 0.5}, {"d": 0.6, "agen": None}],
            [{"d": 0.4, "agen": 0.7}],
        ]
    }
    means = reads.class_means(
        basis, [["t1", "t2"], ["t3"]], {"t1": "in_train", "t2": "x", "t3": "in_train"}
    )
    assert means["in_train"] == {
        "targets": 2,
        "d": pytest.approx(0.3),
        "agen": pytest.approx(0.6),
    }
    assert means["x"] == {"targets": 1, "d": pytest.approx(0.6), "agen": None}


def _rows(tmp_path, name, value):
    buffer = io.BytesIO()
    np.save(buffer, np.full((3, 1), value, dtype=float), allow_pickle=False)
    path = tmp_path / f"{name}.npy"
    path.write_bytes(buffer.getvalue())
    return {
        "rows_npy": str(path),
        "sha256": hashlib.sha256(buffer.getvalue()).hexdigest(),
    }


def _strong(tmp_path, **over):
    tmp_path.mkdir(parents=True, exist_ok=True)
    doc = {
        "panel": [
            {
                "name": "shortcut",
                "kind": "engineer_shortcut",
                **_rows(tmp_path, "shortcut", 1.0),
            },
            {"name": "gp", "kind": "generic_fit", **_rows(tmp_path, "gp", 2.0)},
            {"name": "gated", "kind": "generic_fit", **_rows(tmp_path, "gated", 9.0)},
        ],
        "default_model": {"name": "default", **_rows(tmp_path, "default", 3.0)},
        "ceiling": {"draws": 1, "seed": 0},
        **over,
    }
    path = tmp_path / "strong.json"
    path.write_text(json.dumps(doc))
    return path


class _StubRegrader:
    """The receipted Regrader's surface: a row value v gives every target d = v / 10 and A_gen = v / 10; 9.0 is gated."""

    def __init__(self, config):
        self.graded = SimpleNamespace(bank={"inputs": [[0.0]] * 3})
        self.all_specs = tuple(_specs())

    def sets_and_classes(self):
        return dict(CLASSES), [["t1", "t2"]]

    def grade(self, rows, entry_id, *, classes=None, **_):
        v = rows[0][0]
        if v == 9.0:
            return {
                "status": "GATE_FAILED",
                "gates": ["physics_pool"],
                "basis": {"gated": True},
            }
        target = {"d": v / 10, "agen": v / 10}
        return {
            "status": "SCORED",
            "gates": [],
            "basis": {"gated": False, "sets": [[dict(target), dict(target)]]},
        }


def test_the_checks_report_the_best_member_the_ceiling_and_the_default_in_score_steps(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(reads, "Regrader", _StubRegrader)
    monkeypatch.setattr(pool_version, "registered_policies", lambda *a, **k: POLICIES)
    monkeypatch.setattr(
        reads,
        "noise_ceiling",
        lambda specs, policies, classes, *, draws, seed: {
            "in_train": {"d": 0.9, "agen": 0.95},
            "extended_shell": {"d": 0.8, "agen": 0.85},
        },
    )
    config = {"challenge": "c", "version": "v", "margin_n": 0.03}
    (tmp_path / "config.json").write_text(json.dumps(config))
    out = reads.run_strong(config, tmp_path / "config.json", _strong(tmp_path))
    step = grade_feedback.step(0.03)
    assert out["score_step"] == step == max(grade_feedback.ETA, 0.03)
    assert (
        out["predictors"]["gated"]["status"] == "GATE_FAILED"
        and out["predictors"]["gated"]["classes"] is None
    )
    inside = out["checks_by_class"]["in_train"]["agen"]
    assert (
        inside["best_shortcut"] == pytest.approx(0.2)
        and inside["best_shortcut_member"] == "gp"
    )  # the gated 0.9 is excluded
    assert inside["ceiling_minus_best_in_steps"] == pytest.approx((0.95 - 0.2) / step)
    assert inside["default_model"] == pytest.approx(0.3)
    assert inside["default_minus_best_in_steps"] == pytest.approx((0.3 - 0.2) / step)
    assert inside["default_beats_best_by_more_than_rebuild_noise"] is True  # 0.1 > 0.03
    outside = out["checks_by_class"]["extended_shell"]["d"]
    assert outside["default_model"] == pytest.approx(
        0.3
    )  # the default's out-of-range score is always reported
    assert "default_beats_best_by_more_than_rebuild_noise" not in outside
    assert "owner" in out["bars"] and out["scratch_only"] is True


def test_the_strong_inputs_are_closed(tmp_path):
    with pytest.raises(reads.ReadRefused, match="strong_shape"):
        reads.load_strong(_strong(tmp_path, extra=1))
    doc = json.loads(_strong(tmp_path / "b").read_text())
    doc["panel"][0]["kind"] = "tuned_operator"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(reads.ReadRefused, match="strong_panel_entry"):
        reads.load_strong(path)
    doc = json.loads(_strong(tmp_path / "c").read_text())
    doc["ceiling"] = {"draws": 0, "seed": 0}
    path.write_text(json.dumps(doc))
    with pytest.raises(reads.ReadRefused, match="strong_ceiling"):
        reads.load_strong(path)
