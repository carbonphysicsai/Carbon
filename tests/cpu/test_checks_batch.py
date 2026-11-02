"""CHECKS BATCH (`checks_batch.py` / `.sh`): checks (1)-(3) + the G1-G9 reports for a version in one launch.

Claims: the selftest runs the whole chain on fake targets of the real shapes and writes the report, its summary, the G
reports and a SUMS that hashes each; G4-G6 are a typed NOT_RUN naming what they need; G2 counts the points at or beyond
the owner's threshold (null when unset) and G3 flags classes below the floor; G8 reports the nearest TRAIN / practice
distance and duplicates; the dry mode checks every input and grades nothing; the G inputs are closed; an existing output
directory is refused; the shell wrapper runs the selftest.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
EXAM_READS = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads"
sys.path.insert(0, str(EXAM_READS))

import checks_batch as batch
import g_reports
import q3_q8_whatif as reads


def test_the_selftest_writes_every_report_and_a_sums_of_them(tmp_path):
    sums = batch.selftest(tmp_path / "st")
    out = tmp_path / "st" / "outputs"
    listed = dict(reversed(line.split("  ")) for line in sums.splitlines())
    assert set(listed) == set(batch.OUTPUTS)
    for name, digest in listed.items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    assert (out / "SUMS").read_text() == sums
    checks = json.loads((out / "checks-1-3-report.json").read_text())
    g = json.loads((out / "g-reports.json").read_text())
    assert checks["schema"] == "carbon.checks-1-3-report.v1"
    assert (
        g["schema"] == g_reports.SCHEMA
        and g["checks_report_run_digest"] == checks["run_digest"]
    )
    for axis in ("G4_leave_regime_out", "G5_nearby_variants", "G6_learning_curve"):
        assert g[axis]["status"] == "NOT_RUN" and g[axis]["needs"]
    g2 = g["G2_interpolation_holes"]
    assert g2["threshold"] == 0.1
    for row in g2["by_class"].values():
        assert 0 <= row["at_or_beyond_threshold"] <= row["n"]
        assert row["min_maxnorm"] <= row["max_maxnorm"]
    assert all(
        type(r["below_floor"]) is bool
        for r in g["G3_hard_regimes"]["by_class"].values()
    )
    assert g["G7_seed_robustness"]["score_step"] == checks["score_step"]
    assert (
        set(g["G8_no_leakage"]["train"]) == set(g2["by_class"])
        and g["G8_no_leakage"]["practice"] is None
    )
    assert g["G9_physical_validity"]["contenders"]["knn"]["status"] == "GATE_FAILED"
    assert "owner" in g["bars"]


def test_an_existing_output_is_refused(tmp_path):
    (tmp_path / "out").mkdir()
    assert batch.main(["selftest", "--out", str(tmp_path / "out")]) == 2


def test_unset_owner_values_give_null_counts_and_practice_duplicates_are_counted(
    tmp_path,
):
    train = np.array([[0.0, 0.0], [1.0, 1.0]])
    sink = {
        "points": [("in_train", {"x": 0.0, "y": 0.0}), ("outer", {"x": 0.5, "y": 0.9})],
        "train": train,
        "columns": ["x", "y"],
    }
    checks = {
        "challenge": "c",
        "version": "v",
        "run_digest": "d",
        "classes": [
            {"class": "in_train", "n": 1, "gate_failed": {"a": 0}},
            {"class": "outer", "n": 1, "gate_failed": {"a": 0}},
        ],
        "checks": {"1_shortcuts_out_of_range": {"outer": {"a": {}}}},
        "contenders": [{"role": "a", "status": "SCORED", "gates": []}],
        "margin_n": 0.03,
        "score_step": 0.03,
        "gate_failed_scope": "s",
    }
    practice = tmp_path / "practice.npy"
    np.save(practice, np.array([[0.5, 0.9]]))
    spec = {
        "npy": str(practice),
        "columns": ["x", "y"],
        "sha256": hashlib.sha256(practice.read_bytes()).hexdigest(),
    }
    g = g_reports.build(
        checks,
        sink,
        {"g2_threshold": None, "g3_floor_n": None, "g8_practice_inputs": spec},
    )
    assert (
        g["G2_interpolation_holes"]["by_class"]["outer"]["at_or_beyond_threshold"]
        is None
    )
    assert g["G2_interpolation_holes"]["by_class"]["in_train"]["min_maxnorm"] == 0.0
    assert g["G3_hard_regimes"]["by_class"]["outer"]["below_floor"] is None
    assert g["G8_no_leakage"]["train"]["in_train"]["duplicates"] == 1
    assert g["G8_no_leakage"]["practice"]["outer"]["duplicates"] == 1
    assert g["G8_no_leakage"]["train"]["outer"]["min_maxnorm"] == pytest.approx(0.5)


def test_the_g_inputs_are_closed(tmp_path):
    path = tmp_path / "g.json"
    for doc, code in (
        ({"g2_threshold": 0.1}, "g_inputs_shape"),
        (
            {"g2_threshold": -1, "g3_floor_n": None, "g8_practice_inputs": None},
            "g2_threshold",
        ),
        (
            {"g2_threshold": None, "g3_floor_n": 0, "g8_practice_inputs": None},
            "g3_floor_n",
        ),
    ):
        path.write_text(json.dumps(doc))
        with pytest.raises(reads.ReadRefused, match=code):
            g_reports.load_inputs(path)
    assert g_reports.load_inputs(None) == dict.fromkeys(g_reports.INPUT_KEYS)


def test_the_dry_mode_checks_the_inputs_and_grades_nothing(tmp_path, monkeypatch):
    import test_checks_report as fake

    class NoGrade(fake._StubRegrader):
        def grade(self, *args, **kwargs):
            raise AssertionError("dry graded")

    monkeypatch.setattr(reads, "Regrader", NoGrade)
    monkeypatch.setattr(reads, "_class_source", lambda source: (None, None, None, None))
    monkeypatch.setattr(
        reads, "load_config", lambda path: {"challenge": "c", "version": "v"}
    )
    out = batch.dry(tmp_path / "config.json", fake._inputs(tmp_path / "in"), None)
    assert (
        out["dry"] == "OK"
        and out["bank_rows"] == 3
        and "default_model" in out["contenders"]
    )


@pytest.mark.skipif(os.name == "nt", reason="the wrapper is bash")
def test_the_shell_wrapper_runs_the_selftest(tmp_path):
    done = subprocess.run(
        ["bash", str(EXAM_READS / "checks_batch.sh"), "selftest", str(tmp_path / "w")],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHON": sys.executable},
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "w" / "outputs" / "SUMS").read_text() == done.stdout
