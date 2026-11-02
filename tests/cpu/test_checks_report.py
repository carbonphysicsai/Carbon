"""CHECKS 1-3 REPORT (`checks_report.py`): the Validator's report format rev 2, schema carbon.checks-1-3-report.v1.

Claims: every contender is graded through the Regrader's surface with the A_gen recorder, and each point's class is the
geometric-v1 rule's; per class the accuracy is the grader's own atom, |err|/U is measured against the registered U, the
noise ceiling is the Monte-Carlo U-perturbed truth scored by the same atom, and nearest_train is the TRAIN-scaled distance;
a gated contender is reported with its gate count and is never the best shortcut; every gap has a within-class bootstrap
95 % interval over 2000 draws and is given in score steps; the status names who gate-failed; no bar is applied; the inputs
are closed and the panel file is bound by its sha256.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads")
)

import checks_report as report
import q3_q8_whatif as reads
from test_pool_exam import POLICIES
from test_pool_plugin import SHELL, U, toy_target

from carbon.scoring import grade_feedback, pool_grader, pool_version

SPECS = (toy_target("t1", 11), toy_target("t2", 12, shell=SHELL))
CLASSES = {"t1": "in_train", "t2": "extended_shell"}
OUTER = "regime:outer"


def _klass(region, names, inputs):
    return report.IN_TRAIN if inputs["x"] + inputs["y"] < 1.4 else OUTER


class _StubRegrader:
    """The receipted Regrader's surface: a row value v predicts every A_gen point as the truth + v x U on each output (graded by
    the real `pool_grader.agen_accuracy`, so the recorder sees it); v = 9 is gated."""

    def __init__(self, config):
        self.graded = type(
            "G",
            (),
            {
                "bank": {
                    "inputs": [[0.0]] * 3,
                    pool_version.POOL_KEY: {"design_names": ["x", "y"]},
                }
            },
        )()
        self.all_specs = SPECS

    def sets_and_classes(self):
        return dict(CLASSES), [["t1", "t2"]]

    def grade(self, rows, entry_id, *, classes=None, slacks=False, **_):
        v = rows[0][0]
        if v == 9.0:
            return {
                "status": "GATE_FAILED",
                "gates": ["physics_pool"],
                "basis": None,
                "physics_slack": {"schema_failed": 2, "laws": {"g_le": {"fail": 3}}},
            }
        by_id = {s.target_id: s for s in SPECS}

        def predict(conditions, designs):
            spec = by_id[conditions["target_id"]]
            index = {tuple(d): i for i, d in enumerate(spec.designs)}
            return [
                {k: spec.truths[index[tuple(d)]][k] + v * U for k in spec.outputs}
                for d in designs
            ]

        pool_grader.agen_accuracy(list(SPECS), predict, POLICIES.agen_scales)
        return {
            "status": "SCORED",
            "gates": [],
            "basis": {"gated": False},
            "physics_slack": {"schema_failed": 0, "laws": {"g_le": {"fail": 0}}},
        }


def _npy(tmp_path, name, array):
    buffer = io.BytesIO()
    np.save(buffer, np.asarray(array, dtype=float), allow_pickle=False)
    path = tmp_path / f"{name}.npy"
    path.write_bytes(buffer.getvalue())
    return str(path), hashlib.sha256(buffer.getvalue()).hexdigest()


def _contender(tmp_path, role, value):
    path, sha = _npy(tmp_path, role.replace(":", "_"), np.full((3, 1), value))
    return {
        "role": role,
        "catalog_id": f"cat-{role}",
        "fit": "default",
        "record_sha256": "sha256:" + "7" * 64,
        "rows_npy": path,
        "sha256": sha,
    }


def _inputs(tmp_path, **over):
    tmp_path.mkdir(parents=True, exist_ok=True)
    panel = tmp_path / "panel.json"
    panel.write_text('{"members": "pre-registered"}')
    rng = np.random.default_rng(0)
    train = np.column_stack([np.ones(50), rng.uniform(0, 0.6, (50, 2))])
    train_path, train_sha = _npy(tmp_path, "train", train)
    doc = {
        "header": {
            "train_version": {
                "version": "1.6",
                "name": "toy-train",
                "sha256": "sha256:" + "1" * 64,
            },
            "probe_set": {"sha256": "sha256:" + "2" * 64, "provisional": False},
            "u_record": {"id": "toy-u", "sha256": "sha256:" + "3" * 64},
            "tool_commit": "a" * 40,
            "coverage_table": None,
        },
        "panel_file": {
            "path": str(panel),
            "sha256": hashlib.sha256(panel.read_bytes()).hexdigest(),
        },
        "contenders": [
            _contender(tmp_path, "engineer_shortcut", 3.0),
            _contender(tmp_path, "gp", 2.0),
            _contender(tmp_path, "knn", 9.0),
            _contender(tmp_path, "default_model", 1.0),
        ],
        "class_source": {},
        "train_inputs": {
            "npy": train_path,
            "columns": ["cond", "x", "y"],
            "sha256": train_sha,
        },
        "bootstrap_seed": 5,
        "ceiling_seed": 6,
        **over,
    }
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(doc))
    return path


@pytest.fixture
def stubbed(tmp_path, monkeypatch):
    monkeypatch.setattr(reads, "Regrader", _StubRegrader)
    monkeypatch.setattr(pool_version, "registered_policies", lambda *a, **k: POLICIES)
    monkeypatch.setattr(
        reads,
        "_class_source",
        lambda source: (
            _klass,
            {"base": {"x": 0, "y": 0}},
            frozenset({report.IN_TRAIN, OUTER}),
            {"rule_sha256": "r", "region_sha256": "g", "plan_params_sha256": "p"},
        ),
    )
    config = {"challenge": "c", "version": "v", "margin_n": 0.03}
    (tmp_path / "config.json").write_text(json.dumps(config))
    return config, tmp_path / "config.json"


def test_the_report_measures_every_class_and_gives_each_gap_in_steps_with_a_ci(
    stubbed, tmp_path
):
    config, config_path = stubbed
    out = report.run_report(config, config_path, _inputs(tmp_path / "in"))
    assert out["schema"] == "carbon.checks-1-3-report.v1"
    assert out["bootstrap"] == {"draws": 2000, "resampling": "within class", "seed": 5}
    assert out["noise_ceiling_mc"]["draws"] == 2000
    step = grade_feedback.step(0.03)
    assert out["score_step"] == step
    rows = {row["class"]: row for row in out["classes"]}
    assert next(iter(rows)) == report.IN_TRAIN and set(rows) == {report.IN_TRAIN, OUTER}
    for row in rows.values():
        acc = row["accuracy"]
        assert acc["knn"] is None  # gated: no accuracy, never the bar
        assert acc["default_model"] > acc["gp"] > acc["engineer_shortcut"]
        assert row["best_shortcut"] == "gp"
        assert (
            row["noise_ceiling"] > acc["default_model"]
        )  # errs within U, the default by exactly U
        assert row["gate_failed"]["knn"] == 5 and row["gate_failed"]["gp"] == 0
        # the default errs by exactly U on every output
        assert row["err_over_u"]["default_model"]["f"]["median"] == pytest.approx(1.0)
        assert row["err_over_u"]["engineer_shortcut"]["g"]["p90"] == pytest.approx(3.0)
    gap = out["checks"]["3_default"][report.IN_TRAIN]["gap"]
    assert gap["value"] == pytest.approx(
        rows[report.IN_TRAIN]["accuracy"]["default_model"]
        - rows[report.IN_TRAIN]["accuracy"]["gp"]
    )
    assert gap["steps"] == pytest.approx(gap["value"] / step)
    # the toy's errors are constant, so the interval collapses onto the value (to float rounding)
    assert gap["ci95"][0] - 1e-12 <= gap["value"] <= gap["ci95"][1] + 1e-12
    ceiling = out["checks"]["2_ceiling_gap"][OUTER]
    assert ceiling["member"] == "gp" and ceiling["value"] > 0
    assert set(out["checks"]["1_shortcuts_out_of_range"][OUTER]) == {
        "engineer_shortcut",
        "gp",
    }
    nearest = out["checks"]["3_coverage"]["nearest_train"]
    assert 0 <= nearest[report.IN_TRAIN]["min"] <= nearest[OUTER]["max"]
    assert out["status"] == [{"MEASURED_WITH_GATE_FAILURES": ["knn"]}]
    assert "owner" in out["bars"] and out["panel_file_sha256"]
    text = report.summary(out)
    assert "| in_train |" in text and "steps" in text


def test_a_provisional_probe_set_says_so(stubbed, tmp_path):
    config, config_path = stubbed
    path = _inputs(tmp_path / "in")
    doc = json.loads(path.read_text())
    doc["header"]["probe_set"]["provisional"] = True
    doc["contenders"] = [c for c in doc["contenders"] if c["role"] != "knn"]
    path.write_text(json.dumps(doc))
    out = report.run_report(config, config_path, path)
    assert out["status"] == ["MEASURED", "PROVISIONAL"]


def test_the_inputs_are_closed_and_bind_the_panel_file(tmp_path):
    with pytest.raises(reads.ReadRefused, match="report_inputs_shape"):
        report.load_inputs(_inputs(tmp_path / "a", extra=1))
    path = _inputs(tmp_path / "b")
    doc = json.loads(path.read_text())
    Path(doc["panel_file"]["path"]).write_text("edited after registration")
    with pytest.raises(reads.ReadRefused, match="report_panel_file_sha256"):
        report.load_inputs(path)
    path = _inputs(tmp_path / "c")
    doc = json.loads(path.read_text())
    doc["contenders"] = [c for c in doc["contenders"] if c["role"] != "default_model"]
    path.write_text(json.dumps(doc))
    with pytest.raises(reads.ReadRefused, match="report_needs_default_and_a_panel"):
        report.load_inputs(path)
    doc["contenders"][0]["role"] = "tuned_operator"
    path.write_text(json.dumps(doc))
    with pytest.raises(reads.ReadRefused, match="report_contender_entry"):
        report.load_inputs(path)
