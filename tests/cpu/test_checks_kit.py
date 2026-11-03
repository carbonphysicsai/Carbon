"""CHECK (1K), the kit-data fit (`checks_kit.py`, `checks_batch.py --kit-data`; STRONG_CHECKS_SPEC_ADDENDUM_KITFIT_20261103).

Claims: a valid kit manifest runs and the report carries, per member and run, the data used by source, the counted size vs the
budget, A per class and D per target class with a bootstrap interval and the margin vs the best check-(3) learner; the verdict
per class is FAIL on a clear win of a budget-confined member over every learner and PASS on no clear win; a FAIL only on the
in_out run is labelled 'fails only with Carbon-known extents'; an over-budget member is reported with its scores and is never
verdict-bearing; a plan class with no points is N/A with a reason; the manifest is refused (typed ``kit_*``) without a
disjointness receipt, without the counter, on a changed sha256 or row count, and when a kit design lies within the R15 distance
of an exam design (the count only); a member without both runs is refused; the dry mode checks it all and grades nothing; the
batch CLI writes check-1k-report.{json,md} and SUMS.
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

import checks_batch as batch
import checks_kit as kit
import checks_report as report
import q3_q8_whatif as reads
import test_checks_report as fake

from carbon.scoring import grade_feedback, pool_version

EMPTY = "regime:empty"
REGION = {
    "base": {"x": [0.0, 1.0], "y": [0.0, 1.0]},
    "extended": {"x": [0.0, 2.0], "y": [0.0, 2.0]},
}
CONFIG = {"challenge": "c", "version": "v", "margin_n": 0.03}
BUDGET = 1000


def _atom(v):
    # the stub predicts truth + v x U (U = 0.01) on both outputs, scales 0.1: benefit(0.1 v) = 1 / (1 + 0.1 v)
    return 1.0 / (1.0 + 0.1 * v)


class _KitStub(fake._StubRegrader):
    """The checks-report stub, plus the capture's per-set targets (d = 1 / (1 + v) on both targets) for D."""

    def grade(self, rows, entry_id, **kwargs):
        result = super().grade(rows, entry_id, **kwargs)
        if result["basis"] is not None:
            d = 1.0 / (1.0 + rows[0][0])
            result["basis"] = {
                "gated": False,
                "sets": [[{"d": d, "agen": None}, {"d": d, "agen": None}]],
            }
        return result


class _NoGrade(_KitStub):
    def grade(self, *args, **kwargs):
        raise AssertionError("dry graded")


def _patch(monkeypatch, regrader):
    monkeypatch.setattr(reads, "Regrader", regrader)
    monkeypatch.setattr(
        pool_version, "registered_policies", lambda *a, **k: fake.POLICIES
    )
    monkeypatch.setattr(
        reads,
        "_class_source",
        lambda source: (
            fake._klass,
            REGION,
            frozenset({report.IN_TRAIN, fake.OUTER, EMPTY}),
            {"rule_sha256": "r", "region_sha256": "g", "plan_params_sha256": "p"},
        ),
    )


@pytest.fixture
def stubbed(monkeypatch):
    _patch(monkeypatch, _KitStub)


@pytest.fixture
def no_grade(monkeypatch):
    _patch(monkeypatch, _NoGrade)


def _npz(tmp_path, name, inputs):
    inputs = np.asarray(inputs, dtype=float)
    buffer = io.BytesIO()
    np.savez(buffer, inputs=inputs, targets=np.zeros((len(inputs), 2)))
    path = tmp_path / f"{name}.npz"
    path.write_bytes(buffer.getvalue())
    return str(path), hashlib.sha256(buffer.getvalue()).hexdigest()


def _dataset(tmp_path, name, rng, inputs):
    path, sha = _npz(tmp_path, name, inputs)
    return {
        "name": name,
        "npz": path,
        "sha256": sha,
        "range": rng,
        "n": len(inputs),
        "source_status": "not sealed (owner)",
        "disjointness_receipt": f"Validator receipt for {name}",
    }


FAR_IN = [[1.0, 1.5, 1.5], [1.0, 1.6, 1.9], [1.0, 1.9, 1.6], [1.0, 2.0, 2.0]]
FAR_OUT = [[1.0, 1.8, 1.5], [1.0, 1.5, 1.8]]


def _manifest(tmp_path, *, edit=None, datasets=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    panel = tmp_path / "kit-panel.json"
    panel.write_text('{"members": "the check-1 panel, kit fit"}')
    doc = {
        "schema": kit.MANIFEST_SCHEMA,
        "datasets": datasets
        or [
            _dataset(tmp_path, "stage2_train", "in", FAR_IN),
            _dataset(tmp_path, "edge_cells", "out", FAR_OUT),
        ],
        "counter": {
            "name": "graph-route v2",
            "budget_bytes": BUDGET,
            "receipt": "Validator counter receipt",
        },
        "panel_config": {
            "path": str(panel),
            "sha256": hashlib.sha256(panel.read_bytes()).hexdigest(),
        },
    }
    if edit is not None:
        edit(doc)
    path = tmp_path / "kit-manifest.json"
    path.write_text(json.dumps(doc))
    return path


def _run(tmp_path, role, fit_data, value, counted):
    path, sha = fake._npy(
        tmp_path, f"{role}_{fit_data}".replace(":", "_"), np.full((3, 1), value)
    )
    return {
        "role": role,
        "catalog_id": f"cat-{role}",
        "fit": "tuned",
        "record_sha256": "sha256:" + "8" * 64,
        "rows_npy": path,
        "sha256": sha,
        "fit_data": fit_data,
        "info_budget": {"counted_bytes": counted},
    }


def _kit_inputs(tmp_path, members, *, drop=None):
    """``members``: {role: (value on the in run, value on the in_out run, counted bytes)}; the learner is the default model at 1."""
    path = fake._inputs(tmp_path)
    doc = json.loads(path.read_text())
    contenders = [fake._contender(tmp_path, "default_model", 1.0)]
    for role, (v_in, v_out, counted) in members.items():
        for fit_data, value in (("in", v_in), ("in_out", v_out)):
            if (role, fit_data) != drop:
                contenders.append(_run(tmp_path, role, fit_data, value, counted))
    doc["contenders"] = contenders
    path.write_text(json.dumps(doc))
    return path


def _report(tmp_path, members, **manifest):
    config_path = tmp_path / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(CONFIG))
    return kit.run_kit(
        CONFIG,
        config_path,
        _kit_inputs(tmp_path / "in", members),
        _manifest(tmp_path / "kit", **manifest),
    )


def test_a_valid_kit_runs_and_the_report_has_every_field(stubbed, tmp_path):
    out = _report(tmp_path, {"gp": (2.0, 2.0, 10), "catalog_kernel": (3.0, 3.0, 20)})
    assert out["schema"] == kit.SCHEMA and out["check"] == "1K"
    assert out["learner_roles"] == ["default_model"]
    assert out["kit"]["disjointness"] == {
        "distance": 0.10,
        "rule": kit.DISTANCE_RULE,
        "kit_designs": 6,
        "exam_designs": 200,
        "closer_than_distance": 0,
    }
    assert all(
        "npz" not in d and d["disjointness_receipt"] for d in out["kit"]["datasets"]
    )
    assert out["kit"]["counter"]["budget_bytes"] == BUDGET
    assert out["classes"] == [report.IN_TRAIN, fake.OUTER]
    assert out["classes_without_points"] == [EMPTY]
    step = grade_feedback.step(0.03)
    gp = next(m for m in out["members"] if m["role"] == "gp")
    assert set(gp["runs"]) == {"in", "in_out"}
    used_in, used_out = gp["runs"]["in"]["data_used"], gp["runs"]["in_out"]["data_used"]
    assert (used_in["n_in"], used_in["n_out"]) == (4, 0)
    assert (used_out["n_in"], used_out["n_out"]) == (4, 2)
    assert used_out["by_source"] == {
        "in": {"stage2_train": 4},
        "out": {"edge_cells": 2},
    }
    for run in gp["runs"].values():
        assert run["info_budget"] == {
            "counted_bytes": 10,
            "budget_bytes": BUDGET,
            "counter": "graph-route v2",
            "budget": "inside",
        }
        assert run["verdict_bearing"] is True and run["status"] == "SCORED"
        for cls in (report.IN_TRAIN, fake.OUTER):
            row = run["classes"][cls]
            assert row["n"] > 0
            assert row["A"]["value"] == pytest.approx(_atom(2.0))
            assert len(row["A"]["ci95"]) == 2
            margin = row["margin_vs_best_learner"]
            assert margin["learner"] == "default_model"
            assert margin["value"] == pytest.approx(_atom(2.0) - _atom(1.0))
            assert margin["steps"] == pytest.approx(margin["value"] / step)
        d = run["d_by_target_class"]
        assert set(d) == {"in_train", "extended_shell"}
        assert d["in_train"]["D"]["value"] == pytest.approx(1.0 / 3.0)
        assert d["in_train"]["margin_vs_best_learner"]["value"] == pytest.approx(
            1.0 / 3.0 - 0.5
        )
    learner = out["learners"][0]
    assert learner["role"] == "default_model"
    assert learner["classes"][report.IN_TRAIN]["A"]["value"] == pytest.approx(
        _atom(1.0)
    )
    verdicts = out["verdict_by_class"]
    assert verdicts[EMPTY] == {"verdict": "N/A", "label": None, "reason": "no_points"}
    for cls in (report.IN_TRAIN, fake.OUTER):
        row = verdicts[cls]
        assert row["verdict"] == "PASS" and row["label"] is None
        assert row["runs"]["in_out"]["best_budget_confined_member"] == "gp"
        against = row["runs"]["in_out"]["against_learners"]["default_model"]
        assert against["lower_bound_above_margin_n"] is False
    assert out["verdict"] == "PASS" and out["classes_failed"] == []
    assert out["status"] == ["MEASURED"] and out["margin_n"] == 0.03
    assert out["run_digest"]
    text = kit.summary(out)
    assert "| in_train | PASS |" in text and "graph-route v2" in text


def test_a_clear_win_fails_and_a_small_win_passes(stubbed, tmp_path):
    out = _report(tmp_path / "a", {"gp": (0.0, 0.0, 10)})
    for cls in (report.IN_TRAIN, fake.OUTER):
        row = out["verdict_by_class"][cls]
        assert row["verdict"] == "FAIL" and row["label"] is None
        against = row["runs"]["in_out"]["against_learners"]["default_model"]
        assert against["ci95"][0] > 0.03 and against["lower_bound_above_margin_n"]
    assert out["verdict"] == "FAIL"
    assert out["classes_failed"] == sorted([report.IN_TRAIN, fake.OUTER])
    # 0.8 U beats the learner by about 0.017 in A, under margin_n = 0.03: not "clearly"
    out = _report(tmp_path / "b", {"gp": (0.8, 0.8, 10)})
    assert all(
        out["verdict_by_class"][c]["verdict"] == "PASS"
        for c in (report.IN_TRAIN, fake.OUTER)
    )
    assert out["verdict"] == "PASS"


def test_a_fail_only_on_the_in_out_run_is_labelled(stubbed, tmp_path):
    out = _report(tmp_path, {"gp": (2.0, 0.0, 10)})
    for cls in (report.IN_TRAIN, fake.OUTER):
        row = out["verdict_by_class"][cls]
        assert row["verdict"] == "FAIL"
        assert row["label"] == "fails only with Carbon-known extents"
        assert row["runs"]["in"]["verdict"] == "PASS"


def test_an_over_budget_member_is_reported_and_never_verdict_bearing(stubbed, tmp_path):
    out = _report(tmp_path, {"gp": (2.0, 2.0, 10), "knn": (0.0, 0.0, BUDGET + 1)})
    knn = next(m for m in out["members"] if m["role"] == "knn")
    for run in knn["runs"].values():
        assert run["info_budget"]["budget"] == "over"
        assert run["verdict_bearing"] is False
        assert run["not_verdict_bearing_because"] == "over_budget"
        assert run["classes"][report.IN_TRAIN]["A"]["value"] == pytest.approx(1.0)
    for cls in (report.IN_TRAIN, fake.OUTER):
        row = out["verdict_by_class"][cls]
        assert row["verdict"] == "PASS"
        assert row["runs"]["in_out"]["best_budget_confined_member"] == "gp"
    # at exactly the budget a member is inside
    out = _report(tmp_path / "b", {"knn": (0.0, 0.0, BUDGET)})
    assert out["verdict"] == "FAIL"


def _dry(tmp_path, members=None, *, drop=None, **manifest):
    return kit.dry(
        CONFIG,
        _kit_inputs(tmp_path / "in", members or {"gp": (1.0, 1.0, 10)}, drop=drop),
        _manifest(tmp_path / "kit", **manifest),
    )


def test_the_dry_mode_checks_every_input_and_grades_nothing(no_grade, tmp_path):
    out = _dry(tmp_path, {"gp": (1.0, 1.0, 10), "knn": (1.0, 1.0, BUDGET + 5)})
    assert out["dry"] == "OK" and out["check"] == "1K"
    assert out["learners"] == ["default_model"] and out["members"] == ["gp", "knn"]
    assert out["budget"] == {
        "gp@in": "inside",
        "gp@in_out": "inside",
        "knn@in": "over",
        "knn@in_out": "over",
    }
    assert out["kit_rows"] == {"in": 4, "out": 2}
    assert out["disjointness"]["closer_than_distance"] == 0
    assert out["bank_rows"] == 3


@pytest.mark.parametrize(
    "edit, code",
    [
        (
            lambda d: d["datasets"][1].update(disjointness_receipt=""),
            "kit_dataset_lacks_disjointness_receipt",
        ),
        (
            lambda d: d["datasets"][0].pop("disjointness_receipt"),
            "kit_dataset_lacks_disjointness_receipt",
        ),
        (lambda d: d.pop("counter"), "kit_counter_missing"),
        (lambda d: d["counter"].pop("budget_bytes"), "kit_counter_missing"),
        (lambda d: d["counter"].update(budget_bytes="1000"), "kit_counter_missing"),
        (lambda d: d["counter"].update(receipt=""), "kit_counter_missing"),
        (lambda d: d["datasets"][0].update(sha256="0" * 64), "kit_dataset_sha256"),
        (lambda d: d["datasets"][0].update(n=5), "kit_dataset_n_differs"),
        (lambda d: d["datasets"][0].update(range="edge"), "kit_dataset_entry"),
        (lambda d: d.update(extra=1), "kit_manifest_shape"),
        (lambda d: d.update(schema="v0"), "kit_manifest_shape"),
        (
            lambda d: d["panel_config"].update(sha256="1" * 64),
            "kit_panel_config_sha256",
        ),
        (
            lambda d: d.update(
                datasets=[x for x in d["datasets"] if x["range"] == "out"]
            ),
            "kit_no_in_range_data",
        ),
    ],
)
def test_the_manifest_is_refused_typed(no_grade, tmp_path, edit, code):
    with pytest.raises(reads.ReadRefused, match=f"^{code}$"):
        _dry(tmp_path, edit=edit)


def test_a_kit_design_too_close_to_an_exam_design_is_refused_with_the_count_only(
    no_grade, tmp_path
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    near = [[1.0, 0.5, 0.5], [1.0, 0.63, 0.63], *FAR_IN]
    datasets = [
        _dataset(tmp_path, "near", "in", near),
        _dataset(tmp_path, "edge_cells", "out", FAR_OUT),
    ]
    with pytest.raises(reads.ReadRefused) as refused:
        _dry(tmp_path, datasets=datasets)
    assert refused.value.code == "kit_data_not_disjoint:2"


def test_a_member_without_both_runs_is_refused(no_grade, tmp_path):
    with pytest.raises(reads.ReadRefused, match="^kit_member_runs_incomplete$"):
        _dry(
            tmp_path,
            {"gp": (1.0, 1.0, 10), "knn": (1.0, 1.0, 10)},
            drop=("knn", "in_out"),
        )
    path = _kit_inputs(tmp_path / "b", {"gp": (1.0, 1.0, 10)})
    doc = json.loads(path.read_text())
    doc["contenders"].append(dict(doc["contenders"][1]))
    path.write_text(json.dumps(doc))
    with pytest.raises(reads.ReadRefused, match="^kit_member_run_repeated$"):
        kit.load_kit_inputs(path)
    doc["contenders"] = doc["contenders"][:1]
    path.write_text(json.dumps(doc))
    with pytest.raises(reads.ReadRefused, match="^kit_no_members$"):
        kit.load_kit_inputs(path)
    doc = json.loads(_kit_inputs(tmp_path / "c", {"gp": (1.0, 1.0, 10)}).read_text())
    doc["contenders"][1]["info_budget"] = {"counted_bytes": -1}
    path.write_text(json.dumps(doc))
    with pytest.raises(reads.ReadRefused, match="^kit_member_entry$"):
        kit.load_kit_inputs(path)


def test_the_batch_cli_writes_the_check_1k_report_and_its_sums(
    stubbed, tmp_path, monkeypatch
):
    monkeypatch.setattr(reads, "load_config", lambda path: dict(CONFIG))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(CONFIG))
    inputs = _kit_inputs(tmp_path / "in", {"gp": (0.0, 0.0, 10)})
    manifest = _manifest(tmp_path / "kit")
    out = tmp_path / "out"
    args = ["--config", str(config_path), "--inputs", str(inputs)]
    assert (
        batch.main(["run", *args, "--kit-data", str(manifest), "--out", str(out)]) == 0
    )
    assert sorted(p.name for p in out.iterdir()) == [
        "SUMS",
        "check-1k-report.json",
        "check-1k-report.md",
    ]
    sums = (out / "SUMS").read_text()
    for line in sums.splitlines():
        digest, name = line.split("  ")
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    doc = json.loads((out / "check-1k-report.json").read_text())
    assert doc["check"] == "1K" and doc["verdict"] == "FAIL"
    assert batch.main(["dry", *args, "--kit-data", str(manifest)]) == 0
    bad = _manifest(
        tmp_path / "bad",
        edit=lambda d: d["datasets"][0].update(disjointness_receipt=" "),
    )
    assert batch.main(["dry", *args, "--kit-data", str(bad)]) == 2
