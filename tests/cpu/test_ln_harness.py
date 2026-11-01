"""LN-HARNESS-01: the learning-necessity harness refuses what the Validator's conditions forbid and records what they
require. Synthetic builders stand in for the catalog trainers (no torch, no GPU); the real grid file is checked against the
real catalog vocabulary. The harness has no truth input at all.
"""

from __future__ import annotations

import copy
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

TOOLS = Path(__file__).resolve().parents[2] / "scripts/dev/learning_necessity"
sys.path.insert(0, str(TOOLS))

import ln_harness as h

GRID_FILE = TOOLS / "ln_grid_f02_2_5.json"


def _grid():
    return json.loads(GRID_FILE.read_text(encoding="utf-8"))


def _write(tmp_path, grid, name="grid.json"):
    path = tmp_path / name
    path.write_text(json.dumps(grid), encoding="utf-8")
    return path, h.digest(grid)


def _probe(tmp_path, rows=6):
    path = tmp_path / "probe.npy"
    np.save(path, np.linspace(1.0, 2.0, rows * 2, dtype=np.float32).reshape(rows, 2))
    return path


def _fake_build(train_inputs, train_targets, *, seed, configuration, train_use):
    """A linear least-squares fit whose bias shrinks with more steps and grows with weight decay: a deterministic stand-in
    so that the grid's best setting is known (the first with the most steps and no decay).
    """
    x = np.asarray(train_inputs, dtype=np.float64)
    y = np.asarray(train_targets, dtype=np.float64)
    design = np.hstack([x, np.ones((len(x), 1))])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    steps = train_use.get("steps", 300)
    decay = train_use.get("optimizer", {}).get("weight_decay", 0.0)
    bias = 50.0 / steps + 1000.0 * decay
    beta = beta.copy()
    beta[-1] += bias

    def apply(params, inputs):
        z = np.hstack([np.asarray(inputs, dtype=np.float64), np.ones((len(inputs), 1))])
        return z @ params

    return {"framework": "numpy", "apply": apply, "parameters": beta}


def _builders(grid):
    return {
        candidate: _fake_build
        for each in grid["contenders"]
        for candidate in each["candidates"]
    }


def _never(*_args, **_kwargs):
    raise AssertionError("a refused run must not train anything")


def test_the_run_refuses_without_the_registered_digest_and_trains_nothing(tmp_path):
    path, _digest = _write(tmp_path, _grid())
    out = tmp_path / "out"
    for given, code in (
        (None, "grid_digest_required"),
        ("sha256:" + "0" * 64, "grid_digest_mismatch"),
    ):
        with pytest.raises(h.Refused, match=code):
            h.run(
                path,
                given,
                "2.5",
                _probe(tmp_path),
                out,
                builders=dict.fromkeys(_builders(_grid()), _never),
            )
    assert not out.exists()


def test_a_grid_that_is_not_the_registered_shape_is_refused(tmp_path):
    base = _grid()
    for change, code in (
        ({"k": 1}, "grid_k_invalid"),
        ({"fold_seed": -1}, "grid_fold_seed_invalid"),
        ({"contenders": []}, "grid_contenders_invalid"),
        ({"extra": 1}, "grid_shape_invalid"),
    ):
        path, digest = _write(tmp_path, {**base, **change})
        with pytest.raises(h.Refused, match=code):
            h.load_grid(path, digest)


def test_the_registered_grid_resolves_against_the_real_catalog_vocabulary():
    grid = _grid()
    assert grid["status"] == "PROPOSED_NOT_RULED"
    entries = h.resolve_entries(grid, "f02", "2.5")
    assert [item["catalog_id"] for _, item, _ in entries] == [
        "v2.f02.prior_krr",
        "v2.f02.neuralop.FNO",
        "v2.f02.lno.LNO1d",
        "v2.f02.physicsnemo.FullyConnected",
        "v2.f02.jno.mgno2d",
        "v2.f02.jno.transolver",
    ]
    for each, item, substituted in entries:
        assert substituted is None
        resolved = h.check_settings(each, item)
        assert len(resolved) == (0 if each["settings"] is None else 8)
    assert h.rebuild_wall_seconds("f02", "2.5") == 648


def test_a_knob_outside_the_catalog_vocabulary_refuses_before_anything_trains(tmp_path):
    grid = copy.deepcopy(_grid())
    grid["contenders"][1]["settings"][0]["train_use"][
        "teacher_weights"
    ] = "pretrained.bin"
    path, digest = _write(tmp_path, grid)
    builders = dict.fromkeys(_builders(grid), _never)
    with pytest.raises(h.Refused, match="setting_outside_the_catalog_vocabulary"):
        h.run(
            path, digest, "2.5", _probe(tmp_path), tmp_path / "out", builders=builders
        )


def test_a_missing_contender_is_replaced_by_its_next_family_member_and_recorded(
    tmp_path,
):
    grid = copy.deepcopy(_grid())
    second = grid["contenders"][2]
    second["candidates"] = ["v2.f02.not_in_the_catalog", *second["candidates"]]
    path, digest = _write(tmp_path, grid)
    record = h.run(
        path,
        digest,
        "2.5",
        _probe(tmp_path),
        tmp_path / "out",
        builders=_builders(grid),
        log=lambda *_: None,
    )
    got = {c["catalog_id"]: c["substituted_for"] for c in record["contenders"]}
    assert got["v2.f02.lno.LNO1d"] == "v2.f02.not_in_the_catalog"
    assert got["v2.f02.neuralop.FNO"] is None
    grid["contenders"][2]["candidates"] = ["v2.f02.not_in_the_catalog"]
    path, digest = _write(tmp_path, grid, "none.json")
    with pytest.raises(h.Refused, match="contender_not_offered_by_the_version"):
        h.run(
            path,
            digest,
            "2.5",
            _probe(tmp_path),
            tmp_path / "out2",
            builders=_builders(grid),
        )


def test_the_folds_partition_the_rows_and_follow_the_recorded_seed():
    folds = h.make_folds(40, 5, 7)
    assert sorted(i for fold in folds for i in fold) == list(range(40))
    assert [len(f) for f in folds] == [8] * 5
    assert folds == h.make_folds(40, 5, 7)
    assert folds != h.make_folds(40, 5, 8)
    with pytest.raises(h.Refused, match="k_fold_needs"):
        h.make_folds(4, 5, 0)


def test_a_full_run_selects_by_cross_validation_and_exports_predictions_only(tmp_path):
    grid = _grid()
    path, digest = _write(tmp_path, grid)
    probe = _probe(tmp_path)
    out = tmp_path / "out"
    record = h.run(
        path, digest, "2.5", probe, out, builders=_builders(grid), log=lambda *_: None
    )
    assert record["grid_digest"] == digest and record["truths_read"] is False
    assert record["visibility"] == "CARBON_PRIVATE"
    assert (
        record["k"],
        record["fold_seed"],
        record["train_rows"],
        record["probe_rows"],
    ) == (5, 20261101, 40, 6)
    assert record["rebuild_wall_seconds"] == 648 and len(record["folds"]) == 5
    assert "python" in record["host"] and "gpu" in record["host"]
    by = {c["catalog_id"]: c for c in record["contenders"]}
    reference = by["v2.f02.prior_krr"]
    assert reference["tuned"] is False and set(reference["exports"]) == {"default"}
    fno = by["v2.f02.neuralop.FNO"]
    assert fno["tuned"] is True and len(fno["cv"]) == 8
    assert fno["selected_index"] == 2  # most steps, no decay, the first of equal errors
    assert fno["selected_setting"]["train_use"]["steps"] == 1200
    assert set(fno["exports"]) == {"default", "tuned"}
    exported = np.load(out / "v2.f02.neuralop.FNO" / "tuned.npy")
    assert exported.shape == (6, 1) and exported.dtype == np.float32
    for contender in record["contenders"]:
        for entry in contender["exports"].values():
            assert (out / entry["file"]).is_file()
    assert (
        json.loads((out / "record.json").read_text(encoding="utf-8"))["grid_digest"]
        == digest
    )


def test_a_fit_over_the_registered_rebuild_wall_cannot_be_selected(
    tmp_path, monkeypatch
):
    grid = _grid()
    path, digest = _write(tmp_path, grid)
    monkeypatch.setattr(h, "rebuild_wall_seconds", lambda *_: -1.0)
    record = h.run(
        path,
        digest,
        "2.5",
        _probe(tmp_path),
        tmp_path / "out",
        builders=_builders(grid),
        log=lambda *_: None,
    )
    fno = next(
        c for c in record["contenders"] if c["catalog_id"] == "v2.f02.neuralop.FNO"
    )
    assert all(row["state"] == "OVER_LIMIT" for row in fno["cv"])
    assert fno["selected_index"] is None and fno["exports"] == {}
    assert fno["over_limit_final_fits"] == ["default"]


def test_a_probe_that_is_not_the_inputs_shape_is_refused(tmp_path):
    grid = _grid()
    path, digest = _write(tmp_path, grid)
    bad = tmp_path / "bad.npy"
    np.save(bad, np.zeros((4, 3), dtype=np.float32))
    with pytest.raises(h.Refused, match="probe_inputs_shape_or_values_invalid"):
        h.run(path, digest, "2.5", bad, tmp_path / "out", builders=_builders(grid))


def test_the_harness_has_no_truth_input_and_the_record_holds_none(tmp_path):
    assert set(inspect.signature(h.run).parameters) == {
        "grid_path",
        "grid_digest",
        "version",
        "probe_path",
        "out_dir",
        "builders",
        "challenge_id",
        "log",
    }
    grid = _grid()
    path, digest = _write(tmp_path, grid)
    record = h.run(
        path,
        digest,
        "2.5",
        _probe(tmp_path),
        tmp_path / "out",
        builders=_builders(grid),
        log=lambda *_: None,
    )
    text = json.dumps(record)
    for forbidden in ("truth", "pool_targets", "oracle"):
        assert forbidden not in text.replace('"truths_read": false', "")


def test_the_digest_command_prints_the_canonical_digest(tmp_path, capsys):
    assert h.main(["digest", str(GRID_FILE)]) == 0
    assert capsys.readouterr().out.strip() == h.digest(_grid())


def test_a_pod_run_without_probe_inputs_records_the_selection_and_exports_nothing(
    tmp_path,
):
    grid = _grid()
    path, digest = _write(tmp_path, grid)
    out = tmp_path / "pod"
    record = h.run(
        path, digest, "2.5", None, out, builders=_builders(grid), log=lambda *_: None
    )
    assert record["probe_inputs_sha256"] is None and record["probe_rows"] is None
    fno = next(
        c for c in record["contenders"] if c["catalog_id"] == "v2.f02.neuralop.FNO"
    )
    assert fno["selected_index"] == 2 and fno["exports"] == {}
    assert set(fno["final_fit_seconds"]) == {"default", "tuned"}
    assert not list(out.rglob("*.npy"))  # no prediction file exists


def test_the_custody_step_retrains_the_recorded_selection_and_matches_a_one_process_run(
    tmp_path,
):
    grid = _grid()
    path, digest = _write(tmp_path, grid)
    probe = _probe(tmp_path)
    h.run(
        path,
        digest,
        "2.5",
        None,
        tmp_path / "pod",
        builders=_builders(grid),
        log=lambda *_: None,
    )
    h.run(
        path,
        digest,
        "2.5",
        probe,
        tmp_path / "desk",
        builders=_builders(grid),
        log=lambda *_: None,
    )
    document = h.predict_from_record(
        tmp_path / "pod" / "record.json",
        digest,
        "2.5",
        probe,
        tmp_path / "custody",
        builders=_builders(grid),
        log=lambda *_: None,
    )
    assert document["schema"] == h.PREDICT_SCHEMA and document["truths_read"] is False
    assert document["grid_digest"] == digest and document["probe_rows"] == 6
    for contender in document["contenders"]:
        for label, entry in contender["exports"].items():
            custody = np.load(tmp_path / "custody" / entry["file"])
            desk = np.load(tmp_path / "desk" / entry["file"])
            assert np.array_equal(custody, desk), (contender["catalog_id"], label)
    assert {c["catalog_id"] for c in document["contenders"]} == {
        c["catalog_id"]
        for c in h.json.loads((tmp_path / "pod/record.json").read_text())["contenders"]
    }
    assert set(inspect.signature(h.predict_from_record).parameters) == {
        "record_path",
        "grid_digest",
        "version",
        "probe_path",
        "out_dir",
        "builders",
        "challenge_id",
        "log",
    }


def test_the_custody_step_refuses_a_record_that_is_not_this_grids_selection(tmp_path):
    grid = _grid()
    path, digest = _write(tmp_path, grid)
    probe = _probe(tmp_path)
    h.run(
        path,
        digest,
        "2.5",
        None,
        tmp_path / "pod",
        builders=_builders(grid),
        log=lambda *_: None,
    )
    record_path = tmp_path / "pod" / "record.json"
    builders = dict.fromkeys(_builders(grid), _never)
    with pytest.raises(h.Refused, match="record_is_not_this_grids_selection_record"):
        h.predict_from_record(
            record_path,
            "sha256:" + "1" * 64,
            "2.5",
            probe,
            tmp_path / "a",
            builders=builders,
        )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["truths_read"] = True
    forged = tmp_path / "forged.json"
    forged.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(h.Refused, match="record_is_not_this_grids_selection_record"):
        h.predict_from_record(
            forged, digest, "2.5", probe, tmp_path / "b", builders=builders
        )
    record["truths_read"] = False
    record["contenders"][1]["catalog_id"] = "v2.f02.not_in_the_catalog"
    odd = tmp_path / "odd.json"
    odd.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(
        h.Refused, match="recorded_contender_not_offered_by_the_version"
    ):
        h.predict_from_record(
            odd, digest, "2.5", probe, tmp_path / "c", builders=builders
        )
