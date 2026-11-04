"""G6 for a CATALOG default (`g6_catalog`): the official bundle build program, cut to a nested TRAIN subset in its child.

Claims: the anchor occurs exactly once in the real `BUILD_PROGRAM`, and the patched program is the official one plus exactly
`SUBSET_BLOCK` after it (anything else refuses); the patched program, run as the bundle worker runs it, trains on the subset's
rows only and refuses a subset file whose indices or sha differ; the runner swaps only the build child (the inference child
passes through untouched, a taken file name refuses); the capture keeps the practice's arguments except the QUERY, the output
shape, seed 0, no timed query and the runner, and refuses a TRAIN or subset that is not the practice's; a failed build is
NOT_RUN, never a learner row; `g6_fit --default-kind catalog` fills the default column. Every value is synthetic.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads")
)

import g6_catalog
import g6_fit
import g6_subsets as subsets
import test_bundle_construction_worker as bw

import carbon.development_session.bundle_construction_worker as worker
from carbon.level4 import allowlist

posix = pytest.mark.skipif(os.name != "posix", reason="isolated build programs")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------- the patch


def test_the_anchor_occurs_once_and_the_patch_only_inserts_the_block():
    program = worker.BUILD_PROGRAM
    assert program.count(g6_catalog.ANCHOR) == 1
    patched = g6_catalog.patched_build_program(program)
    head, tail = program.split(g6_catalog.ANCHOR)
    assert patched == head + g6_catalog.ANCHOR + g6_catalog.SUBSET_BLOCK + tail
    assert patched.count(g6_catalog.SUBSET_BLOCK) == 1
    compile(patched, "<patched>", "exec")


@pytest.mark.parametrize(
    "program", ["no anchor here\n", g6_catalog.ANCHOR * 2, None, b"bytes"]
)
def test_a_program_without_exactly_one_anchor_is_refused(program):
    with pytest.raises(subsets.SubsetsRefused, match="g6_build_program_anchor"):
        g6_catalog.patched_build_program(program)


@pytest.mark.parametrize(
    "indices",
    [[0], [1, 1, 2], [2, 1], [-1, 2], [0, 4], [[0, 1]]],
)
def test_bad_subset_indices_are_refused(indices):
    with pytest.raises(subsets.SubsetsRefused, match="g6_subset_indices"):
        g6_catalog.subset_document(indices, 4)


# ---------------------------------------------------------------- the patched program, run as the worker runs it

_BUILDER = (
    "import numpy as np\n"
    "import jax.numpy as jnp\n"
    "def build(train_inputs, train_targets, *, seed, configuration, train_use):\n"
    "    scale = np.float32(np.sum(train_targets * train_inputs) / np.sum(train_inputs ** 2))\n"
    "    return {'framework': 'jax', 'apply': lambda x: x * jnp.asarray(scale), 'parameters': []}\n"
)


def _build_files(tmp_path):
    library = tmp_path / "installed-library"
    candidate = library / "candidate"
    candidate.mkdir(parents=True)
    (candidate / "__init__.py").write_text("")
    (candidate / "build.py").write_text(_BUILDER)
    # rows 0 and 2 follow y = 3x, rows 1 and 3 follow y = 5x: the fitted scale says which rows the build saw
    x = np.asarray([[1.0, 2.0], [1.0, 2.0], [3.0, 4.0], [3.0, 4.0]], dtype=np.float32)
    y = x * np.asarray([[3.0], [5.0], [3.0], [5.0]], dtype=np.float32)
    train = bw._tensors(inputs=x, targets=y)
    example = bw._tensors(inputs=x[:2])
    recipe = bw._recipe(bw._digest(train))
    binding = bw._binding(recipe)
    allowed = allowlist.load(Path(allowlist.PATH).with_name("allowlist_v2.json"))
    files, modules = bw._stage_bundle_modules(binding, training=True)
    files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "train.npz": train,
            "example.npz": example,
            "allowlist.json": allowed.raw,
            "control.json": json.dumps(
                {
                    "recipe_digest": recipe.digest,
                    "bundle_ref": recipe.to_dict()["source"]["bundle_ref"],
                    "binding": binding,
                    "codec_modules": modules,
                    "example_digest": bw._digest(example),
                    "allowlist_digest": allowed.digest,
                    "seed": 0,
                },
                sort_keys=True,
            ).encode(),
        }
    )
    return library, files, x


def _run_program(tmp_path, name, library, files, program):
    work = bw._stage(tmp_path / name, files)
    done = subprocess.run(
        [sys.executable, "-c", program],
        cwd=work,
        env={**os.environ, "PYTHONPATH": str(library)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return work, done


@posix
def test_the_patched_build_trains_on_the_subset_rows_only(tmp_path):
    library, files, x = _build_files(tmp_path)
    patched = g6_catalog.patched_build_program(worker.BUILD_PROGRAM)
    for name, indices, scale in (("three", [0, 2], 3.0), ("five", [1, 3], 5.0)):
        staged = {**files, "g6-subset.json": g6_catalog.subset_document(indices, 4)}
        work, done = _run_program(tmp_path, name, library, staged, patched)
        assert done.returncode == 0, done.stderr
        native = json.loads(
            (work.parent / "output/native-predictions.json").read_bytes()
        )
        np.testing.assert_allclose(np.asarray(native), scale * x[:2], rtol=1e-6)
        receipt = json.loads((work.parent / "output/receipt.json").read_bytes())
        # the receipt keeps the official schema and keys: the host's identity check is unchanged
        assert set(receipt) == {
            "schema",
            "example_digest",
            "native_predictions_digest",
            "native_dtype",
            "native_shape",
            "recipe_digest",
            "bundle_digest",
            "train_digest",
            "state_digest",
            "allowlist_digest",
            "framework",
        }
    # the official program on the same files sees every row: scale 4
    work, done = _run_program(tmp_path, "full", library, files, worker.BUILD_PROGRAM)
    assert done.returncode == 0, done.stderr
    native = json.loads((work.parent / "output/native-predictions.json").read_bytes())
    np.testing.assert_allclose(np.asarray(native), 4.0 * x[:2], rtol=1e-6)


@posix
@pytest.mark.parametrize("tamper", ["sha", "k", "n_train", "order", "missing"])
def test_the_patched_build_refuses_a_tampered_subset_file(tmp_path, tamper):
    library, files, _x = _build_files(tmp_path)
    doc = json.loads(g6_catalog.subset_document([0, 2], 4))
    if tamper == "sha":
        doc["indices"] = [0, 3]
    elif tamper == "k":
        doc["k"] = 3
    elif tamper == "n_train":
        doc["n_train"] = 5
    elif tamper == "order":
        doc["indices"] = [2, 0]
        doc["indices_sha256"] = _sha(np.asarray([2, 0], dtype="<i8").tobytes())
    staged = dict(files)
    if tamper != "missing":
        staged["g6-subset.json"] = json.dumps(doc).encode()
    patched = g6_catalog.patched_build_program(worker.BUILD_PROGRAM)
    work, done = _run_program(tmp_path, tamper, library, staged, patched)
    assert done.returncode != 0
    assert not (work.parent / "output/state.npz").exists()
    if tamper != "missing":
        assert "g6 subset rows differ" in done.stderr


# ---------------------------------------------------------------- the runner


def test_the_runner_swaps_only_the_build_child():
    seen = []

    def run(ledger, **kw):
        seen.append(kw)
        return {"ok": kw["identity"]}

    calls = []
    runner = g6_catalog.subset_runner(b"SUB", worker.BUILD_PROGRAM, run, calls)
    files = {"train.npz": b"T"}
    assert runner("L", identity="b", source=worker.BUILD_PROGRAM, files=files) == {
        "ok": "b"
    }
    assert runner("L", identity="i", source=worker.INFER_PROGRAM, files=files) == {
        "ok": "i"
    }
    build, infer = seen
    assert build["source"] == g6_catalog.patched_build_program(worker.BUILD_PROGRAM)
    assert build["files"] == {"train.npz": b"T", "g6-subset.json": b"SUB"}
    assert files == {"train.npz": b"T"}  # the caller's dict is not changed
    assert infer["source"] == worker.INFER_PROGRAM and infer["files"] is files
    assert [c["child"] for c in calls] == ["build", "other"]
    assert calls[0]["official_program_sha256"] == _sha(worker.BUILD_PROGRAM.encode())
    with pytest.raises(subsets.SubsetsRefused, match="g6_subset_file_name_taken"):
        runner(
            "L",
            identity="b",
            source=worker.BUILD_PROGRAM,
            files={"g6-subset.json": b"x"},
        )


# ---------------------------------------------------------------- the capture and default_rows (stand-in practice + carrier)


def _train(n=8, d=3, m=2):
    rng = np.random.default_rng(5)
    return bw._tensors(
        inputs=rng.uniform(0, 1, (n, d)).astype(np.float32),
        targets=rng.normal(0, 1, (n, m)).astype(np.float32),
    )


def _subsets(tmp_path, train):
    (tmp_path / "train.npz").write_bytes(train)
    subsets.write(
        tmp_path / "train.npz", "seed:2", "ceil", (0.5, 1.0), tmp_path / "subsets"
    )
    manifest = json.loads((tmp_path / "subsets" / subsets.MANIFEST).read_bytes())
    files = {
        float(label): (tmp_path / "subsets" / row["file"]).read_bytes()
        for label, row in manifest["subsets"].items()
    }
    return manifest, files


class _Practice:
    """Calls `reconstruct_and_infer_public` as a catalog practice does (the module attribute, so the capture sees it)."""

    def __init__(self, train, recipe, *, fail=None):
        self.train, self.recipe, self.fail = train, recipe, fail

    def __call__(self, identity, catalog_recipe):
        if self.fail is not None:
            raise self.fail
        worker.reconstruct_and_infer_public(
            "LEDGER",
            owner="curves",
            identity=identity,
            recipe=self.recipe,
            challenge_binding=bw._binding(self.recipe),
            train=self.train,
            inputs=np.zeros((40, 3), dtype=np.float32),
            expected_output_shape=(40, 2),
            seed=0,
            measure_query=True,
            timing_optional=True,
        )
        raise AssertionError("the capture must leave the practice")


def _fake_reconstruct(record):
    """Stands in for the real `reconstruct_and_infer_public`: one build child, one inference child, through the runner."""

    def fake(ledger, **kw):
        record.update(kw)
        kw["runner"](ledger, identity="b", source=worker.BUILD_PROGRAM, files={})
        kw["runner"](ledger, identity="i", source=worker.INFER_PROGRAM, files={})
        rows = np.asarray(kw["inputs"], dtype=np.float64)
        return SimpleNamespace(
            build=SimpleNamespace(
                recipe_digest=kw["recipe"].digest,
                state_digest="sha256:" + "5" * 64,
                receipt={"schema": "carbon.development.bundle-build.v2"},
            ),
            inference=SimpleNamespace(predictions=(rows[:, :2] * 2).tolist()),
            execution_boundary="TEST_ONLY_LOCAL_RUNNER",
        )

    return fake


def _carrier(staged):
    def run(ledger, **kw):
        staged.append(kw)
        return {}

    return run


def _default(monkeypatch, tmp_path, *, practice_train=None, subset=None, fail=None):
    train = _train()
    manifest, files = _subsets(tmp_path, train)
    recipe = bw._recipe(bw._digest(practice_train or train))
    seen, staged = {}, []
    monkeypatch.setattr(worker, "reconstruct_and_infer_public", _fake_reconstruct(seen))
    monkeypatch.setattr(g6_catalog, "_recipe_for", lambda route, cid: "catalog-recipe")
    query = np.random.default_rng(9).uniform(0, 1, (6, 3))
    rows, record = g6_catalog.default_rows(
        "motor",
        "v2.motor.cno.CNO1d",
        Namespace(gpu_image=None),
        manifest,
        0.5,
        files[0.5] if subset is None else subset,
        query,
        factory=lambda route, args: _Practice(
            practice_train or train, recipe, fail=fail
        ),
        run=_carrier(staged),
        official=False,
        version="1.7",
    )
    return rows, record, seen, staged, query, manifest, train


def test_default_rows_build_the_subset_and_predict_the_query(monkeypatch, tmp_path):
    rows, record, seen, staged, query, manifest, train = _default(monkeypatch, tmp_path)
    assert record["status"] == "FITTED"
    np.testing.assert_allclose(rows, query.astype(np.float32)[:, :2] * 2)
    assert record["train_cases"] == manifest["subsets"]["0.5"]["n"] == 4
    assert record["indices_sha256"] == manifest["subsets"]["0.5"]["indices_sha256"]
    # the practice's own arguments, except the QUERY, its output shape, seed 0, no timed query and the runner
    assert seen["train"] == train and seen["seed"] == 0
    assert seen["inputs"].shape == (6, 3) and seen["inputs"].dtype == np.float32
    assert seen["expected_output_shape"] == (6, 2)
    assert seen["measure_query"] is False and seen["timing_optional"] is False
    build, infer = staged
    doc = json.loads(build["files"]["g6-subset.json"])
    assert doc["k"] == 4 and doc["n_train"] == 8
    assert doc["indices_sha256"] == manifest["subsets"]["0.5"]["indices_sha256"]
    assert build["source"] == g6_catalog.patched_build_program(worker.BUILD_PROGRAM)
    assert (
        infer["source"] == worker.INFER_PROGRAM
        and "g6-subset.json" not in infer["files"]
    )
    assert record["execution"]["subset_block_sha256"] == _sha(
        g6_catalog.SUBSET_BLOCK.encode()
    )
    assert record["execution"]["official_build_program_sha256"] == _sha(
        worker.BUILD_PROGRAM.encode()
    )
    # a CPU curve (no GPU twin checked) says so; the receipt's train digest is the full TRAIN, flagged
    assert record["official_bundle_verified"] is False
    assert record["receipt_train_digest_is_pre_cut"] is True


def test_the_version_is_required_and_the_practice_targets_are_restored(tmp_path):
    import practice_v2_curves as curves

    before = dict(curves.TARGETS)
    with pytest.raises(subsets.SubsetsRefused, match="g6_catalog_version_required"):
        g6_catalog.default_rows(
            "motor", "x", Namespace(gpu_image=None), {}, 1.0, b"", np.zeros((1, 1))
        )
    with pytest.raises(subsets.SubsetsRefused):
        g6_catalog.default_rows(
            "motor",
            "x",
            Namespace(gpu_image=None),
            {},
            1.0,
            b"",
            np.zeros((1, 1)),
            version="9.9",
            factory=lambda route, args: (_ for _ in ()).throw(
                subsets.SubsetsRefused("stop")
            ),
        )
    assert curves.TARGETS == before


@pytest.mark.parametrize(
    "module",
    [
        "carbon.motor.catalog_practice",
        "carbon.cold_plate.catalog_practice",
        "carbon.direct_campaign.practice",
    ],
)
def test_the_practices_read_the_build_call_from_the_module_at_call_time(module):
    """The capture replaces `bundle_construction_worker.reconstruct_and_infer_public`; a practice that bound the name at
    import would bypass it (it would still fail closed, but only after a full-TRAIN build).
    """
    import importlib

    assert not hasattr(importlib.import_module(module), "reconstruct_and_infer_public")


def test_a_practice_train_that_is_not_the_manifest_train_refuses(monkeypatch, tmp_path):
    with pytest.raises(
        subsets.SubsetsRefused, match="g6_train_differs_from_the_practice_train"
    ):
        _default(monkeypatch, tmp_path, practice_train=_train(n=9))


def test_a_subset_file_whose_rows_are_not_train_rows_refuses(monkeypatch, tmp_path):
    other = subsets.npz_bytes(
        ["inputs", "targets"],
        {
            "inputs": np.zeros((4, 3), dtype=np.float32),
            "targets": np.zeros((4, 2), dtype=np.float32),
        },
    )
    with pytest.raises(
        subsets.SubsetsRefused, match="g6_subset_rows_differ_from_train"
    ):
        _default(monkeypatch, tmp_path, subset=other)


def test_a_failed_build_is_not_run_never_a_row(monkeypatch, tmp_path):
    rows, record, *_ = _default(monkeypatch, tmp_path, fail=RuntimeError("docker"))
    assert rows is None
    assert record == {
        "status": "NOT_RUN",
        "code": "g6_catalog_build_failed:RuntimeError",
    }


def test_the_capture_is_removed_after_the_run(monkeypatch, tmp_path):
    sentinel = object()
    monkeypatch.setattr(worker, "reconstruct_and_infer_public", sentinel)
    monkeypatch.setattr(g6_catalog, "_recipe_for", lambda route, cid: "r")
    train = _train()
    manifest, files = _subsets(tmp_path, train)
    g6_catalog.default_rows(
        "f08",
        "x",
        Namespace(gpu_image=None),
        manifest,
        0.5,
        files[0.5],
        np.zeros((2, 3)),
        factory=lambda route, args: _Practice(train, None, fail=RuntimeError()),
        run=_carrier([]),
        official=False,
        version="1.7",
    )
    assert worker.reconstruct_and_infer_public is sentinel


def test_an_unknown_route_refuses():
    with pytest.raises(subsets.SubsetsRefused, match="g6_catalog_route"):
        g6_catalog.default_rows(
            "battery", "x", Namespace(), {}, 1.0, b"", np.zeros((1, 1))
        )


# ---------------------------------------------------------------- g6_fit --default-kind catalog


def test_g6_fit_catalog_mode_fills_the_default_column(monkeypatch, tmp_path):
    train = _train()
    _manifest, _files = _subsets(tmp_path, train)
    query = np.random.default_rng(1).uniform(0, 1, (5, 3))
    buffer = io.BytesIO()
    np.save(buffer, query)
    (tmp_path / "query.npy").write_bytes(buffer.getvalue())
    called = []

    def fake_default(route, cid, practice_args, manifest, fraction, subset, q, **kw):
        called.append((route, cid, subsets.frac_label(fraction), kw))
        return np.asarray(q)[:, :2], {"status": "FITTED", "route": route}

    monkeypatch.setattr(g6_catalog, "default_rows", fake_default)
    args = Namespace(
        subsets=tmp_path / "subsets",
        train=tmp_path / "train.npz",
        query=tmp_path / "query.npy",
        query_sha256=_sha(buffer.getvalue()),
        member="knn",
        shortcut_role="knn",
        shortcut_catalog_id="shortcut_panel:knn",
        shortcut_fit="default",
        recipe=None,
        submission_dir=None,
        default_catalog_id="v2.motor.cno.CNO1d",
        default_kind="catalog",
        route="motor",
        version="1.7",
        parent_identity=tmp_path / "parent.json",
        cache_root=tmp_path / "cache",
        gpu_image=None,
        gpu_cache_root=None,
        gpu_receipts=None,
        work_dir=None,
        out=tmp_path / "fit",
    )
    fragment = g6_fit.run(args)
    roles = [c["role"] for c in fragment["contenders"]]
    assert "default_model@frac:0.5" in roles and "default_model@frac:1.0" in roles
    # the default column is filled (the tiny knn shortcut may refuse its own subset: not this test's claim)
    assert not [e for e in fragment["not_run"] if e["role"].startswith("default_model")]
    assert [c[:3] for c in called] == [
        ("motor", "v2.motor.cno.CNO1d", "0.5"),
        ("motor", "v2.motor.cno.CNO1d", "1.0"),
    ]
    assert {c[3]["version"] for c in called} == {"1.7"}
    with pytest.raises(
        subsets.SubsetsRefused,
        match="g6_catalog_default_needs_route_version_catalog_id_parent_and_cache",
    ):
        g6_fit.run(Namespace(**{**vars(args), "route": None, "out": tmp_path / "x"}))
