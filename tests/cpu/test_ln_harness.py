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
        for candidate in each.get("candidates", [h.inpack_item("f02")["catalog_id"]])
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
        "inpack.learned_baseline",
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
    grid["contenders"][2]["settings"][0]["train_use"][
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
    second = grid["contenders"][3]
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
    grid["contenders"][3]["candidates"] = ["v2.f02.not_in_the_catalog"]
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
    for untuned in ("inpack.learned_baseline", "v2.f02.prior_krr"):
        reference = by[untuned]
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
        "train_version",
        "runtime",
        "cpu_only",
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
        "train_version",
        "runtime",
        "cpu_only",
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


def _runtime_builders(grid, runtime):
    """Fake builders that fail for a contender outside ``runtime``: the other stack is not installed in that image."""
    items = {e[1]["catalog_id"]: e[1] for e in h.resolve_entries(grid, "f02", "2.5")}
    return {
        cid: (_fake_build if h.entry_runtime(item) == runtime else _never)
        for cid, item in items.items()
    }


def test_each_entry_belongs_to_one_runtime_stack():
    items = [e[1] for e in h.resolve_entries(_grid(), "f02", "2.5")]
    got = {i["catalog_id"]: h.entry_runtime(i) for i in items}
    assert {c for c, r in got.items() if r == "jax"} == {
        "inpack.learned_baseline",
        "v2.f02.prior_krr",
        "v2.f02.jno.mgno2d",
    }
    assert sum(r == "torch" for r in got.values()) == 4
    with pytest.raises(h.Refused, match="entry_runtime_unknown"):
        h.entry_runtime({"catalog_id": "x", "settings_schema": "carbon-candidate-v9"})
    with pytest.raises(h.Refused, match="runtime_must_be_torch_or_jax"):
        h.for_runtime([("a", {"settings_schema": "x-torch-y"}, None)], "tensorflow")


def test_a_runtime_run_trains_only_that_stack_and_the_two_records_cover_the_grid(
    tmp_path,
):
    grid = _grid()
    path, digest = _write(tmp_path, grid)
    probe = _probe(tmp_path)
    records = {}
    for runtime in h.RUNTIMES:
        records[runtime] = h.run(
            path,
            digest,
            "2.5",
            None,
            tmp_path / runtime,
            builders=_runtime_builders(grid, runtime),
            runtime=runtime,
            log=lambda *_: None,
        )
    assert {
        r: [c["catalog_id"] for c in v["contenders"]] for r, v in records.items()
    } == {
        "jax": ["inpack.learned_baseline", "v2.f02.prior_krr", "v2.f02.jno.mgno2d"],
        "torch": [
            "v2.f02.neuralop.FNO",
            "v2.f02.lno.LNO1d",
            "v2.f02.physicsnemo.FullyConnected",
            "v2.f02.jno.transolver",
        ],
    }
    for runtime, record in records.items():
        assert record["runtime"] == runtime and len(record["contenders_expected"]) == 7
        assert record["grid_digest"] == digest
    merged = h.merge_check(list(records.values()))
    assert (
        sorted(merged["runtimes"]) == ["jax", "torch"]
        and len(merged["contenders"]) == 7
    )
    # the custody step per runtime reproduces the one-process run for the same contenders
    h.run(
        path,
        digest,
        "2.5",
        probe,
        tmp_path / "desk",
        builders=_builders(grid),
        log=lambda *_: None,
    )
    for runtime in h.RUNTIMES:
        document = h.predict_from_record(
            tmp_path / runtime / "record.json",
            digest,
            "2.5",
            probe,
            tmp_path / f"cust-{runtime}",
            builders=_runtime_builders(grid, runtime),
            runtime=runtime,
            log=lambda *_: None,
        )
        assert (
            document["runtime"] == runtime and len(document["contenders_expected"]) == 7
        )
        for contender in document["contenders"]:
            for entry in contender["exports"].values():
                assert np.array_equal(
                    np.load(tmp_path / f"cust-{runtime}" / entry["file"]),
                    np.load(tmp_path / "desk" / entry["file"]),
                )
    with pytest.raises(h.Refused, match="record_is_not_this_grids_selection_record"):
        h.predict_from_record(
            tmp_path / "torch" / "record.json",
            digest,
            "2.5",
            probe,
            tmp_path / "x",
            builders=_builders(grid),
            runtime="jax",
        )


def test_the_merge_check_refuses_a_result_that_misses_or_doubles_a_contender():
    base = {
        "grid_digest": "sha256:" + "a" * 64,
        "challenge": {"id": "f02", "version": "2.5"},
        "contenders_expected": ["a", "b", "c"],
    }
    torch = {
        **base,
        "runtime": "torch",
        "contenders": [{"catalog_id": "a"}, {"catalog_id": "b"}],
    }
    jax = {**base, "runtime": "jax", "contenders": [{"catalog_id": "c"}]}
    assert h.merge_check([torch, jax])["contenders"] == ["a", "b", "c"]
    with pytest.raises(h.Refused, match="merged_result_missing_contender:c"):
        h.merge_check([torch])
    with pytest.raises(h.Refused, match="merged_result_missing_contender:b"):
        h.merge_check([{**torch, "contenders": [{"catalog_id": "a"}]}, jax])
    with pytest.raises(h.Refused, match="duplicate_or_foreign"):
        h.merge_check(
            [torch, {**jax, "contenders": [{"catalog_id": "c"}, {"catalog_id": "a"}]}]
        )
    with pytest.raises(h.Refused, match="duplicate_or_foreign"):
        h.merge_check(
            [torch, {**jax, "contenders": [{"catalog_id": "c"}, {"catalog_id": "z"}]}]
        )
    with pytest.raises(h.Refused, match="merge_needs_one_record_per_runtime"):
        h.merge_check([torch, {**torch, "contenders": [{"catalog_id": "c"}]}])
    with pytest.raises(h.Refused, match="merge_needs_one_record_per_runtime"):
        h.merge_check([torch, {**jax, "runtime": None}])
    with pytest.raises(h.Refused, match="different_grids"):
        h.merge_check([torch, {**jax, "grid_digest": "sha256:" + "b" * 64}])
    with pytest.raises(h.Refused, match="merge_needs_records"):
        h.merge_check([])


def _tarball(files, prefix=""):
    import io
    import tarfile

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, text in files.items():
            raw = text.encode()
            info = tarfile.TarInfo(prefix + name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    return buffer.getvalue()


_PACKAGE = {
    "carbon_candidate/__init__.py": "",
    "carbon_candidate/common.py": "VALUE = 7\n",
    "carbon_candidate/build.py": (
        "def build(x, y, *, seed, configuration, train_use):\n"
        "    from carbon_candidate import common  # a lazy sibling import, as the pinned builds do\n"
        "    return common.VALUE\n"
    ),
}


@pytest.mark.parametrize("prefix", ["", "f02x-catalog-neuralop-fno-baseline-v2/"])
def test_the_builder_imports_from_a_flat_or_a_prefixed_bundle_tarball(prefix):
    build = h.import_builder(_tarball(_PACKAGE, prefix))
    assert build(None, None, seed=0, configuration={}, train_use={}) == 7


def test_a_second_bundle_gets_its_own_fresh_package():
    """The harness loads one entry's builder and uses it fully before loading the next, so each sees its own package."""
    first = h.import_builder(_tarball(_PACKAGE, "a/"))
    assert first(None, None, seed=0, configuration={}, train_use={}) == 7
    other = {**_PACKAGE, "carbon_candidate/common.py": "VALUE = 9\n"}
    second = h.import_builder(_tarball(other, "b/"))
    assert second(None, None, seed=0, configuration={}, train_use={}) == 9


def test_a_bundle_with_no_or_two_builds_is_refused():
    with pytest.raises(h.Refused, match="holds_0_carbon_candidate_builds"):
        h.import_builder(_tarball({"README": "x"}, "a/"))
    both = _tarball(
        {
            **{f"a/{k}": v for k, v in _PACKAGE.items()},
            **{f"b/{k}": v for k, v in _PACKAGE.items()},
        }
    )
    with pytest.raises(h.Refused, match="holds_2_carbon_candidate_builds"):
        h.import_builder(both)


def test_every_real_f02_entry_bundle_holds_exactly_one_importable_package_dir(tmp_path):
    """The pinned bundles' real layout (a top-level directory): the import root must resolve for each, no torch needed."""
    import io
    import tarfile

    from carbon.backbone_catalog import listing, pipeline

    for each, item, _ in h.resolve_entries(_grid(), "f02", "2.5"):
        if h.is_inpack(item):
            continue  # the in-pack baseline has no bundle
        source = pipeline.bundle_files(item)["source.tar.gz"]
        target = tmp_path / item["catalog_id"]
        with tarfile.open(fileobj=io.BytesIO(source), mode="r:gz") as archive:
            archive.extractall(target, filter="data")
        builds = sorted(target.glob("**/carbon_candidate/build.py"))
        assert len(builds) == 1, item["catalog_id"]
        assert (builds[0].parent / "__init__.py").is_file(), item["catalog_id"]
    assert listing


def test_an_existing_empty_output_directory_is_accepted_and_a_filled_one_is_not(
    tmp_path,
):
    empty = tmp_path / "empty"
    empty.mkdir()
    h.make_output_dir(empty)
    h.make_output_dir(tmp_path / "new" / "deep")
    assert (tmp_path / "new" / "deep").is_dir()
    filled = tmp_path / "filled"
    filled.mkdir()
    (filled / "x").write_text("1")
    with pytest.raises(h.Refused, match="output_directory_not_empty"):
        h.make_output_dir(filled)


class _Tensor:
    """A stand-in tensor: a device and a cpu() that returns a CPU copy."""

    def __init__(self, device="cuda"):
        self.device = type("Device", (), {"type": device})()

    def cpu(self):
        return _Tensor("cpu")


class _Module:
    def __init__(self, **attributes):
        self.__dict__.update(attributes)
        self.moved = False
        self.children_ = []

    def cpu(self):
        self.moved = (
            True  # registered parameters and buffers move; plain attributes do not
        )
        return self

    def modules(self):
        yield self
        yield from self.children_


def _closure_over(model):
    def apply(params, inputs):
        return model

    return {"apply": apply, "parameters": []}


def test_plain_tensor_attributes_of_a_trained_module_are_moved_to_the_cpu():
    """The real failure: a library module caches a grid tensor on the GPU, and model.cpu() leaves it there."""
    inner = _Module(
        grid=_Tensor(), cache={"a": _Tensor(), "b": 1}, stack=[_Tensor(), 2], name="x"
    )
    outer = _Module(embedding=_Tensor())
    outer.children_ = [inner]
    product = _closure_over(outer)
    assert h.to_cpu_inference(product) is product
    assert outer.moved and outer.embedding.device.type == "cpu"
    assert inner.grid.device.type == "cpu"
    assert inner.cache["a"].device.type == "cpu" and inner.cache["b"] == 1
    assert inner.stack[0].device.type == "cpu" and inner.stack[1] == 2
    assert inner.name == "x"


def test_a_product_without_a_torch_module_is_returned_unchanged():
    jax_like = {"apply": lambda params, inputs: inputs, "parameters": [1, 2]}
    assert h.to_cpu_inference(jax_like) is jax_like
    numpy_like = _fake_build(
        np.zeros((3, 2)), np.zeros((3, 1)), seed=0, configuration={}, train_use={}
    )
    assert h.to_cpu_inference(numpy_like) is numpy_like


def test_every_fit_goes_through_the_cpu_normalisation(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(h, "to_cpu_inference", lambda p: (calls.append(1), p)[1])
    h.timed_fit(
        _fake_build,
        np.zeros((4, 2)),
        np.zeros((4, 1)),
        seed=0,
        configuration={},
        train_use={},
    )
    assert calls == [1]


def test_cpu_only_hides_the_gpu_before_anything_runs(tmp_path, monkeypatch):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    seen = {}

    def fake_run(*args, **kwargs):
        seen["cuda"] = h.os.environ.get("CUDA_VISIBLE_DEVICES")

    monkeypatch.setattr(h, "run", fake_run)
    h.main(
        [
            "run",
            "--grid",
            "g",
            "--grid-digest",
            "d",
            "--challenge",
            "f02",
            "--version",
            "2.5",
            "--out",
            "o",
            "--cpu-only",
        ]
    )
    assert seen["cuda"] == ""
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    h.main(
        [
            "run",
            "--grid",
            "g",
            "--grid-digest",
            "d",
            "--challenge",
            "f02",
            "--version",
            "2.5",
            "--out",
            "o",
        ]
    )
    assert seen["cuda"] is None


def test_a_cpu_only_run_does_not_exclude_settings_by_the_gpu_timed_wall_and_says_so(
    tmp_path, monkeypatch
):
    grid = _grid()
    path, digest = _write(tmp_path, grid)
    monkeypatch.setattr(
        h, "rebuild_wall_seconds", lambda *_: -1.0
    )  # every fit is "over" it
    gpu = h.run(
        path,
        digest,
        "2.5",
        None,
        tmp_path / "gpu",
        builders=_builders(grid),
        log=lambda *_: None,
    )
    cpu = h.run(
        path,
        digest,
        "2.5",
        None,
        tmp_path / "cpu",
        builders=_builders(grid),
        cpu_only=True,
        log=lambda *_: None,
    )
    pick = lambda record: next(
        c for c in record["contenders"] if c["catalog_id"] == "v2.f02.neuralop.FNO"
    )
    assert (
        gpu["cpu_only"] is False and gpu["wall_enforced"] is True and "label" not in gpu
    )
    assert pick(gpu)["selected_index"] is None  # the GPU rule excludes them
    assert cpu["cpu_only"] is True and cpu["wall_enforced"] is False
    assert cpu["label"].startswith("CPU_ONLY")
    assert pick(cpu)["selected_index"] == 2  # not excluded: the walls are informational
    assert all(row["state"] == "OK" for row in pick(cpu)["cv"])
    assert all(
        row["slowest_fit_seconds"] >= 0 for row in pick(cpu)["cv"]
    )  # still recorded
    assert "over_limit_final_fits" not in pick(cpu)
    assert cpu["rebuild_wall_seconds"] == -1.0  # the registered value, unchanged


def test_the_custody_step_and_the_merge_carry_the_cpu_only_label(tmp_path):
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
        cpu_only=True,
        log=lambda *_: None,
    )
    document = h.predict_from_record(
        tmp_path / "pod" / "record.json",
        digest,
        "2.5",
        probe,
        tmp_path / "c",
        builders=_builders(grid),
        cpu_only=True,
        log=lambda *_: None,
    )
    assert document["cpu_only"] is True and document["label"].startswith("CPU_ONLY")
    plain = h.predict_from_record(
        tmp_path / "pod" / "record.json",
        digest,
        "2.5",
        probe,
        tmp_path / "g",
        builders=_builders(grid),
        log=lambda *_: None,
    )
    assert plain["cpu_only"] is False and "label" not in plain
    base = {
        "grid_digest": "d",
        "challenge": {"id": "f02", "version": "2.5"},
        "contenders_expected": ["a", "b"],
    }
    torch = {
        **base,
        "runtime": "torch",
        "cpu_only": True,
        "contenders": [{"catalog_id": "a"}],
    }
    jax = {
        **base,
        "runtime": "jax",
        "cpu_only": False,
        "contenders": [{"catalog_id": "b"}],
    }
    assert h.merge_check([torch, jax])["cpu_only"] is True
    assert h.merge_check([{**torch, "cpu_only": False}, jax])["cpu_only"] is False
