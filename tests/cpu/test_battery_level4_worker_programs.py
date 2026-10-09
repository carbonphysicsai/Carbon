"""Battery's Level 4 worker programs, run as the carrier runs them (Phase 3).

`CarrierBackend` runs battery's fixed reconstruct and inference programs in
an isolated worker on staged files only. Here each program runs in an
isolated interpreter (`python -I`, so `carbon` is importable only through the
staged modules) in a fresh work directory holding exactly the staged files:
no Docker, the same programs and bytes.

Claims tested:

1. Reconstruct: the Level 4 program (`level4_worker.program`), staged with
   the record, Carbon's modules and the validator's workspace, trains the
   submission to the native recipe's parameters: classic MLP and general
   DeepONet.
2. Inference: a Level 4 state's inference program (`infer_program`, with
   `infer_staged`) predicts exactly what the in-process backend predicts
   from the same state.
3. With no documents staged, the program records Carbon's environment
   (`failure.json`, stage `environment`), never the candidate's.
4. Level 0 programs are unchanged by Level 4: a non-Level-4 state keeps the
   Level 0 inference program.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.battery import development_rebuild, level4_worker, worker
from carbon.battery import level4 as battery
from carbon.battery.compile import compile_recipe
from carbon.battery.domain import INPUTS
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import intake, staging, submission

REPOSITORY = Path(__file__).resolve().parents[2]
SEED = 7
STEPS = 16


def _run(program, files):
    """The program in an isolated interpreter on exactly `files`."""
    with tempfile.TemporaryDirectory() as directory:
        work, out = Path(directory) / "work", Path(directory) / "output"
        work.mkdir()
        out.mkdir()
        for name, body in files.items():
            (work / name).write_bytes(body)
        environment = {"JAX_PLATFORMS": "cpu", "PATH": os.environ.get("PATH", "")}
        if os.name == "nt":
            environment["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
        done = subprocess.run(
            [sys.executable, "-I", "-c", program],
            cwd=work,
            capture_output=True,
            env=environment,
            timeout=1200,
            check=False,
        )
        assert done.returncode == 0, done.stderr.decode(errors="replace")[-3000:]
        return {path.name: path.read_bytes() for path in out.iterdir()}


def _strategy(label):
    return battery._steps(battery.level0_strategies()[label], STEPS)


def _staged(strategy):
    allowlist = allowlist_module.load()
    manifest, files = battery.lower_recipe(
        strategy, allowlist, max_bytes=intake.BOUNDS["document_bytes"]
    )
    found = {"schema": level4_worker.SCHEMA, "submission": submission.digest(manifest)}
    return found, staging.workspace(submission.canonical(manifest), files)


def _reconstruct(recipe, found, workspace):
    files = worker.reconstruct_files(REPOSITORY, recipe, SEED)
    program, files, trainer = development_rebuild.stage(
        found, worker.RECONSTRUCT_PROGRAM, files, level1_program=lambda: None
    )
    assert trainer == development_rebuild.LEVEL4
    return _run(program, {**files, **(workspace or {})})


@pytest.fixture(scope="module", params=["scaffold_mlp", "panel_deeponet"])
def reconstructed(request):
    strategy = _strategy(request.param)
    _, recipe = compile_recipe(strategy)
    found, workspace = _staged(strategy)
    out = _reconstruct(recipe, found, workspace)
    return request.param, recipe, found, workspace, out


def test_the_worker_trains_the_staged_graph_to_the_native_parameters(reconstructed):
    label, recipe, _found, _workspace, out = reconstructed
    assert "failure.json" not in out, out.get("failure.json")
    fit = json.loads(out["fit.json"])
    native = worker.DirectBackend(REPOSITORY).reconstruct(None, recipe, SEED)[1]
    assert fit["params_sha256"] == native["params_sha256"], label
    assert worker.state_kind(out["state.npz"]) == "level4_graph"


def test_a_level4_state_predicts_in_the_worker_as_in_process(reconstructed):
    _label, _recipe, _found, _workspace, out = reconstructed
    state = out["state.npz"]
    material = worker.DirectBackend(REPOSITORY).material
    inputs = {
        case_id: dict(zip(INPUTS, map(float, x), strict=True))
        for case_id, x in list(zip(material.train.case_ids, material.train.x))[:12]
    }
    program = level4_worker.infer_program(worker.INFER_PROGRAM)
    files = {**worker.infer_files(state, inputs), **level4_worker.infer_staged()}
    predicted = json.loads(_run(program, files)["predictions.json"])
    in_process = worker.DirectBackend(REPOSITORY).infer(None, state, inputs)
    assert predicted == in_process


def test_no_staged_documents_is_carbons_environment():
    strategy = _strategy("scaffold_mlp")
    _, recipe = compile_recipe(strategy)
    found, _workspace = _staged(strategy)
    out = _reconstruct(recipe, found, None)
    failure = json.loads(out["failure.json"])
    assert failure["stage"] == "environment" and failure["error"] == "ImportError"


def test_level_0_programs_are_unchanged():
    assert level4_worker.infer_program(worker.INFER_PROGRAM) != worker.INFER_PROGRAM
    assert worker.INFER_PROGRAM.count("model = recipes.model_from_bytes(") == 1
    assert "carbon.level4" not in worker.INFER_PROGRAM
    assert "carbon.level4" not in worker.RECONSTRUCT_PROGRAM
