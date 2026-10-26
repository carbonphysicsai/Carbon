"""Single-design call timing for pool versions (M4): the derived program, its host checks and the
`_infer_state` stage. The program is run for real (JAX, CPU) on the synthetic graph; the frozen programs stay
byte-identical."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_synthetic_graph_adapter import _build_program_files, _graph_case

from carbon.development_session import (
    bundle_construction_worker as worker,
)
from carbon.development_session import (
    direct_graph_construction_worker as graph_worker,
)
from carbon.development_session import single_call_timing as sct
from carbon.development_session.bundle_construction_worker import (
    INFER_PROGRAM,
    _digest,
    _stage_bundle_modules,
    _tensors,
)
from carbon.development_session.profile import canonical

posix = pytest.mark.skipif(os.name == "nt", reason="the programs need POSIX rlimits")

SHA = lambda raw: "sha256:" + hashlib.sha256(raw).hexdigest()


# --- the derived program ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["INFER_PROGRAM", "PHYSICAL_INFER_PROGRAM", "PHYSICAL_V2_INFER_PROGRAM"],
)
def test_the_program_derives_from_each_graph_route_inference_program_and_compiles(name):
    base = getattr(worker if name == "INFER_PROGRAM" else graph_worker, name)
    derived = sct.program(base)
    compile(derived, name, "exec")
    assert derived != base and base.count("single_call") == 0
    assert derived.count("time.perf_counter()") == base.count("time.perf_counter()") + 2
    assert 'control.get("single_call")' in derived
    assert sct.SCHEMA in derived and sct.SCOPE in derived


def test_the_frozen_programs_keep_their_bytes():
    # Deriving never edits in place (the existing pin tests hold the digests; this holds the property).
    before = (
        worker.INFER_PROGRAM,
        graph_worker.PHYSICAL_INFER_PROGRAM,
        graph_worker.PHYSICAL_V2_INFER_PROGRAM,
    )
    for base in before:
        sct.program(base)
    assert before == (
        worker.INFER_PROGRAM,
        graph_worker.PHYSICAL_INFER_PROGRAM,
        graph_worker.PHYSICAL_V2_INFER_PROGRAM,
    )
    assert "single_call" not in "".join(before)


def test_a_program_whose_anchor_moved_is_refused_not_patched_loosely():
    with pytest.raises(sct.SingleCallRefused, match="anchor_moved"):
        sct.program(INFER_PROGRAM.replace("if per_case:", "if per_case :", 1))
    with pytest.raises(sct.SingleCallRefused, match="anchor_moved"):
        sct.program(INFER_PROGRAM + INFER_PROGRAM)  # an anchor twice


# --- the host's side -------------------------------------------------------------------------


def test_the_control_names_twenty_distinct_in_range_rows_and_a_warmup_digest_only():
    indices = list(range(0, 40, 2))
    block = sct.control_block(indices[::-1], "sha256:" + "a" * 64, rows=40)
    assert block == {"indices": indices, "warmup_digest": "sha256:" + "a" * 64}
    assert set(block) == {"indices", "warmup_digest"}  # never a seed
    for bad in (
        indices[:19],
        indices + [41],
        [*indices[:19], indices[0]],
        [*indices[:19], True],
        [*indices[:19], -1],
        [*indices[:19], 40],
    ):
        with pytest.raises(sct.SingleCallRefused, match="control_invalid"):
            sct.control_block(bad, "sha256:" + "a" * 64, rows=40)
    with pytest.raises(sct.SingleCallRefused):
        sct.control_block(indices, "not-a-digest", rows=40)


def test_the_receipt_block_must_be_exactly_what_the_host_asked_for():
    control = sct.control_block(list(range(20)), "sha256:" + "b" * 64, rows=20)
    good = {
        "scope": sct.SCOPE,
        "indices": control["indices"],
        "warmup_digest": control["warmup_digest"],
        "call_s": [0.01] * 20,
    }
    assert sct.check_receipt_block(good, control=control) == [0.01] * 20
    for change in (
        {"scope": "OTHER"},
        {"indices": list(reversed(control["indices"]))},
        {"warmup_digest": "sha256:" + "c" * 64},
        {"call_s": [0.01] * 19},
        {"call_s": [0.0] * 20},
        {"call_s": [float("nan")] + [0.01] * 19},
        {"call_s": ["x"] * 20},
        {"extra": 1},
    ):
        with pytest.raises(sct.SingleCallRefused, match="receipt_differs"):
            sct.check_receipt_block({**good, **change}, control=control)
    with pytest.raises(sct.SingleCallRefused):
        sct.check_receipt_block(None, control=control)


def test_timed_answers_must_equal_the_graded_answers_on_the_same_rows():
    graded = [[float(i)] for i in range(30)]
    indices = [3, 7, 11]
    assert sct.outputs_match_graded([graded[i] for i in indices], graded, indices)
    assert not sct.outputs_match_graded([[3.0], [7.0], [11.5]], graded, indices)
    assert not sct.outputs_match_graded([[3.0]], graded, indices)


# --- the program, for real -------------------------------------------------------------------


def _run(tmp_path, name, files, program):
    home = tmp_path / name
    work = home / "workspace"
    work.mkdir(parents=True)
    (home / "output").mkdir()
    for filename, body in files.items():
        (work / filename).write_bytes(body)
    done = subprocess.run(
        [sys.executable, "-c", program],
        cwd=work,
        env={**os.environ, "JAX_PLATFORMS": "cpu"},
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    return done, home / "output"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("single-call")
    material, allowed, recipe, raw_manifest, graph_files = _graph_case()
    build_files, binding = _build_program_files(
        material, allowed, recipe, raw_manifest, graph_files
    )
    done, out = _run(tmp, "build", build_files, graph_worker.BUILD_PROGRAM)
    assert done.returncode == 0, done.stderr
    state = (out / "state.npz").read_bytes()
    base = material["practice_inputs"]
    reps = -(-24 // len(base))
    rows = np.concatenate([base] * reps)[:24].astype(np.float32).copy()
    rows += np.linspace(0.0, 0.5, 24, dtype=np.float32).reshape(
        (24,) + (1,) * (rows.ndim - 1)
    )
    return SimpleNamespace(
        tmp=tmp,
        material=material,
        allowed=allowed,
        recipe=recipe,
        binding=binding,
        state=state,
        rows=rows,
        warmup=base[:1].astype(np.float32).copy(),
    )


def _infer_files(b, rows, extra_control=None, extra_files=None):
    files, codec = _stage_bundle_modules(b.binding, training=False)
    raw = _tensors(inputs=rows)
    control = {
        "recipe_digest": b.recipe.digest,
        "binding": b.binding,
        "codec_modules": codec,
        "state_digest": _digest(b.state),
        "inputs_digest": _digest(raw),
        "allowlist_digest": b.allowed.digest,
        "expected_output_shape": list(rows.shape),
        "expected_output_dtype": "float32",
        "input_name": "inputs/forcing",
        **(extra_control or {}),
    }
    files.update(
        {
            "recipe.json": b.recipe.canonical_bytes,
            "state.npz": b.state,
            "inputs.npz": raw,
            "allowlist.json": b.material["allowlist_bytes"],
            "control.json": canonical(control),
            **(extra_files or {}),
        }
    )
    return files


@posix
def test_the_program_times_twenty_single_calls_and_answers_exactly_as_the_graded_run(
    built,
):
    indices = [1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 0]
    graded_done, graded_out = _run(
        built.tmp, "graded", _infer_files(built, built.rows), INFER_PROGRAM
    )
    assert graded_done.returncode == 0, graded_done.stderr
    graded = json.loads((graded_out / "predictions.json").read_bytes())
    warm_raw = _tensors(inputs=built.warmup)
    block = sct.control_block(indices, _digest(warm_raw), rows=len(built.rows))
    expected = [built.rows[i] for i in block["indices"]]
    files = _infer_files(
        built,
        built.rows,
        extra_control={
            "single_call": block,
            "expected_output_shape": [20, *built.rows.shape[1:]],
        },
        extra_files={sct.WARMUP_FILE: warm_raw},
    )
    done, out = _run(built.tmp, "single", files, sct.program(INFER_PROGRAM))
    assert done.returncode == 0, done.stderr
    receipt = json.loads((out / "receipt.json").read_bytes())
    assert receipt["schema"] == sct.SCHEMA
    seconds = sct.check_receipt_block(receipt["single_call"], control=block)
    assert len(seconds) == 20 and all(s > 0 for s in seconds)
    predictions = json.loads((out / "predictions.json").read_bytes())
    assert len(predictions) == 20  # the warm-up row is never answered
    assert sct.outputs_match_graded(predictions, graded, block["indices"])
    assert len(expected) == 20


@posix
def test_the_program_refuses_a_wrong_warmup_or_a_row_out_of_range(built):
    indices = list(range(20))
    warm_raw = _tensors(inputs=built.warmup)
    block = sct.control_block(indices, _digest(warm_raw), rows=len(built.rows))
    common = {"expected_output_shape": [20, *built.rows.shape[1:]]}
    program = sct.program(INFER_PROGRAM)

    wrong = {**block, "warmup_digest": "sha256:" + "0" * 64}
    done, _ = _run(
        built.tmp,
        "bad-warmup",
        _infer_files(
            built,
            built.rows,
            {**common, "single_call": wrong},
            {sct.WARMUP_FILE: warm_raw},
        ),
        program,
    )
    assert done.returncode != 0

    far = {**block, "indices": [*indices[:19], len(built.rows) + 5]}
    done, _ = _run(
        built.tmp,
        "far-row",
        _infer_files(
            built,
            built.rows,
            {**common, "single_call": far},
            {sct.WARMUP_FILE: warm_raw},
        ),
        program,
    )
    assert done.returncode != 0 and "single-call row differs" in done.stderr

    odd = np.zeros((1, 3, 3, 1), np.float32)  # not the graph's row shape
    odd_raw = _tensors(inputs=odd)
    done, _ = _run(
        built.tmp,
        "odd-warmup",
        _infer_files(
            built,
            built.rows,
            {**common, "single_call": {**block, "warmup_digest": _digest(odd_raw)}},
            {sct.WARMUP_FILE: odd_raw},
        ),
        program,
    )
    assert done.returncode != 0


# --- the _infer_state stage ------------------------------------------------------------------


def _runner(tmp, calls):
    """Runs the staged program as the sandbox would and hands the snapshot back (a stand-in for the C-03 run)."""

    def run(ledger, *, owner, identity, source, files, output_validator, **kwargs):
        done, out = _run(tmp, f"stage-{len(calls)}", dict(files), source)
        assert done.returncode == 0, done.stderr
        snapshot = ledger.root / f"op-{len(calls)}" / "snapshot"
        snapshot.mkdir(parents=True)
        for item in out.iterdir():
            (snapshot / item.name).write_bytes(item.read_bytes())
        calls.append({"source": source, "files": sorted(files), **kwargs})
        return {
            "operation": f"op-{len(calls) - 1}",
            "files": {
                item.name: _digest(item.read_bytes()) for item in snapshot.iterdir()
            },
        }

    return run


@posix
def test_infer_state_runs_the_single_call_stage_and_returns_the_per_call_seconds(
    built, tmp_path
):
    calls = []
    result = worker._infer_state(
        SimpleNamespace(root=tmp_path),
        owner="o",
        identity="i",
        inference_image=None,
        recipe=built.recipe,
        binding=built.binding,
        state=built.state,
        state_digest=_digest(built.state),
        inputs=built.rows,
        expected_output_shape=(20, *built.rows.shape[1:]),
        allowlist_bytes=built.material["allowlist_bytes"],
        expected_output_dtype="float32",
        input_name="inputs/forcing",
        runner=_runner(built.tmp, calls),
        program=sct.program(INFER_PROGRAM),
        single_call={"indices": list(range(2, 22)), "warmup": built.warmup},
    )
    assert result.receipt["schema"] == sct.SCHEMA
    assert len(result.receipt["single_call"]["call_s"]) == 20
    assert sct.WARMUP_FILE in calls[0]["files"]
    # the graded rows are exactly the inputs the container already holds; the seed is nowhere in the stage
    assert "seed" not in json.dumps(result.receipt)


@posix
def test_infer_state_refuses_the_stage_without_its_program_or_with_a_measured_query(
    built, tmp_path
):
    common = {
        "owner": "o",
        "identity": "i",
        "inference_image": None,
        "recipe": built.recipe,
        "binding": built.binding,
        "state": built.state,
        "state_digest": _digest(built.state),
        "inputs": built.rows,
        "expected_output_shape": (20, *built.rows.shape[1:]),
        "allowlist_bytes": built.material["allowlist_bytes"],
        "single_call": {"indices": list(range(20)), "warmup": built.warmup},
        "runner": _runner(built.tmp, []),
    }
    ledger = SimpleNamespace(root=tmp_path)
    with pytest.raises(worker.RecipeRefused, match="single_call_needs_its_own_program"):
        worker._infer_state(ledger, **common)  # the frozen program: no `program`
    with pytest.raises(worker.RecipeRefused, match="single_call_needs_its_own_program"):
        worker._infer_state(
            ledger, **common, program=sct.program(INFER_PROGRAM), measure_query=True
        )
