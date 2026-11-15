"""R1 (CV-Motor-B): under vmap-64, Motor 1.8's row independence is STRUCTURAL (owner, Sun 15 Nov 2026 via the Lead,
"Yes and yes": the menu row check becomes "structural under isolated vmap" once this proof is met and Validator-2
signs FINAL; until then the row check keeps running, bit exact, over the ORIGINAL chunks).

(a) Code path: every bank prediction of Motor 1.8 (the graded run, the repeat pair, the menu row check) is the per-case
    procedure of the vmap-64 program, whose only model call is one isolated lane per case (the case at row 0 of its own
    zero-padded block); every menu prediction is a lookup of those graded rows, never a model call.
(b) A PLANTED cross-row model (every row also adds the mean over its batch rows): batched, a row's answer moves with its
    companions; under the isolated layout each row's answer is bit for bit the same whatever the other lanes hold.

Program-contract evidence over synthetic parameters and public rows; not science, security or qualification.
"""

from __future__ import annotations

import inspect
import os

import numpy as np
import pytest
from test_motor18_compiled_forward import MOTOR_18, SAME_VERSION_BOUND, _eager, _pair

from carbon.challenge_validator import lean_recipe_retention
from carbon.development_session import (
    bundle_construction_worker,
    direct_graph_construction_worker,
    paired_inference,
)

worker = direct_graph_construction_worker
posix = pytest.mark.skipif(os.name != "posix", reason="fixed program subprocesses")


def _graded_branch(program):
    start = program.index("# One case per call: the case is row 0")
    return program[start : program.index("\nelif graph_source:\n", start)]


def test_every_bank_prediction_of_motor_1_8_is_an_isolated_lane():
    program = worker.v2_infer_query(*MOTOR_18)["program"]
    assert program == worker.vmap64_infer_program(*MOTOR_18)
    # the graded per-case branch: one lane per case, each lane a zero block with the case at row 0, nothing else
    graded = _graded_branch(program)
    assert (
        "chunk = jnp.zeros((lane_count, batch) + tuple(input_array.shape[1:])" in graded
    )
    # the lane count is the model's own, fixed (`vmap64_lanes` of its graph): defined once, before any call
    assert program.count("lane_count = vmap64_lanes(doc, len(member_arrays), ") == 1
    assert "chunk = chunk.at[:used, 0].set(input_array[start:start + used])" in graded
    assert (
        "jax.jit(jax.vmap(lambda arrays, block: member_forward(*arrays, block),"
        in graded
    )
    assert "in_axes=(None, 0)" in graded
    assert "produced[0][:, 0]" in graded and "blocks.append(total[:used])" in graded
    assert (
        "forward(*parameter_arrays" not in graded and "input_array[index" not in graded
    )
    # the model's other calls are the batched TIMING query and the non-graph route, never a graded row
    assert program.count("forward(*parameter_arrays") == 2
    timing = program[program.index("\nelif graph_source:\n") :]
    assert "never graded" in timing.split("\n", 3)[2]
    # the graded run is the per-case procedure (the default, and the graph route's explicit choice)
    signature = inspect.signature(bundle_construction_worker._infer_state)
    assert signature.parameters["per_case"].default is True
    graph_route = inspect.getsource(worker.reconstruct_and_infer_graph_public)
    assert "measure_query=False,\n        per_case=True," in graph_route
    assert "registered_inference_contract(" in graph_route
    # the repeat pair, the menu row check and the subset repeat repeat the registered procedure, which for Motor 1.8 is
    # per-case (its query form lives in `_frozen_query`, shared by the pair and the subset repeat's one run)
    assert '{"measure_query": False, "per_case": True}' in inspect.getsource(
        paired_inference._frozen_query
    )
    for run in (paired_inference.infer_frozen_pair, paired_inference.infer_frozen_once):
        assert "_frozen_query(" in inspect.getsource(run)
    subset_run = inspect.getsource(lean_recipe_retention._subset_repeat_raw)
    assert 'procedure="per_case"' in subset_run and "vmap64_rerun_rows(" in subset_run
    from carbon.scoring import motor18_dual_pack

    assert '"paired_repeat_procedure": "per_case"' in inspect.getsource(
        motor18_dual_pack._sl().definition
    )
    # the row check: a vmap-64 version's is STRUCTURAL (no op; tests/cpu/test_motor18_structural_rowcheck.py), every
    # other version's repeats the registered procedure
    rowcheck = inspect.getsource(lean_recipe_retention._menu_rowcheck_raw)
    assert "procedure=procedure" in rowcheck and "_structural_rowcheck(" in rowcheck


def test_every_menu_prediction_is_a_lookup_of_the_graded_rows():
    from carbon.scoring import pool_exam

    measure = inspect.getsource(pool_exam.measure_pool)
    # the model's one table over every exam row: the graded outputs, read by exact input
    assert (
        'table = table_server([r["inputs"] for r in bank_rows], outputs, binding.input_names)'
        in measure
    )
    assert "def serve(rows):\n        return table(" in measure
    menu = measure[measure.index("def predict_rows(rows):") :]
    assert "answers = serve(rows)" in menu.split("\n\n", 1)[0]


@pytest.fixture(scope="module")
def planted():
    """Motor 1.8's ensemble state over a PLANTED cross-row graph: every row adds the mean, over its batch rows, of the
    hidden layer through the output weights. Seeded synthetic parameters."""
    pytest.importorskip("jax")
    import jax.numpy as jnp
    from test_registered_graph_pair_execution import _artifact

    from carbon.level4 import tooling

    real = tooling.through_bprime

    def cross_row(w1, b1, w2, b2, x):
        hidden = jnp.tanh(x @ w1 + b1)
        return hidden @ w2 + b2 + jnp.mean(hidden, axis=0, keepdims=True) @ w2

    def lowered(_fn, example_args, **kwargs):
        return real(cross_row, example_args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(tooling, "through_bprime", lowered)
        return _artifact("ensemble64", MOTOR_18, seed=19)


def test_the_planted_model_really_depends_on_its_batch_rows(planted):
    from test_registered_graph_pair_execution import _precision

    from carbon.level4 import interpret

    doc, members, _mu, _sd, _combine = planted["loaded"]
    nodes = doc["graphs"][doc["entry"]]["nodes"]
    assert any(node["op"] == "reduce_sum" for node in nodes)  # the planted batch mean
    batch = doc["graphs"][doc["entry"]]["inputs"][-1]["shape"][0]
    rows = planted["inputs"]
    alone = np.zeros((batch, *rows.shape[1:]), rows.dtype)
    alone[0] = rows[0]
    crowded = alone.copy()
    crowded[1:] = rows[1:batch] if len(rows) >= batch else rows[1]
    with _precision(planted["dtype"]):
        import jax.numpy as jnp

        fn = interpret.rebuild(doc, planted["allowlist"])
        params = [jnp.asarray(p) for p in members[0]]
        first = np.asarray(fn(*params, jnp.asarray(alone))[0])[0]
        second = np.asarray(fn(*params, jnp.asarray(crowded))[0])[0]
    assert (
        np.max(np.abs(first - second)) > 1e-3
    )  # batched, row 0's answer moves with its companions


@posix
def test_under_isolated_lanes_a_rows_answer_ignores_its_companion_lanes(
    planted, tmp_path
):
    from test_paired_inference import FixtureLedger
    from test_registered_graph_pair_execution import _runner

    base = planted["inputs"]
    one = np.ascontiguousarray(
        np.concatenate([base * (1.0 + 0.004 * k) for k in range(8)]), base.dtype
    )
    assert one.shape[0] == worker.VMAP64_LANES
    doc, members = planted["loaded"][:2]
    assert worker.vmap64_model_lanes(*MOTOR_18, doc, len(members)) == 64  # one chunk
    kept = [0, 17, 40, 63]
    other = one[::-1] * 1.5  # every other lane holds a different row
    two = np.ascontiguousarray(other)
    two[kept] = one[kept]
    ledger, seen = FixtureLedger(tmp_path), []
    run = _runner(ledger, seen)
    try:
        first, _ = _pair(planted, ledger, run, "planted-a", one)
        second, _ = _pair(planted, ledger, run, "planted-b", two)
    finally:
        ledger.connection.close()
    assert all("lane_forward = jax.jit(jax.vmap(" in call["source"] for call in seen)
    changed = [i for i in range(len(one)) if i not in kept]
    assert not np.any(
        first[changed] == second[changed]
    )  # the companions really changed
    assert (
        first[kept].tobytes() == second[kept].tobytes()
    )  # bit for bit, whatever the companions
    # and each lane is the row answered alone (zero companions): the eager per-case answer, within the owner's bound
    assert float(np.max(np.abs(first - _eager(planted, one)))) < SAME_VERSION_BOUND


@pytest.fixture(autouse=True)
def _vmap64_machinery_opted_in(monkeypatch):
    """Motor 1.8 is NOT a vmap-64 version since the owner's 116 rollback to A9 behaviour (Sun 15 Nov 2026; it grades
    with the per-case compiled program, tests/cpu/test_motor18_rollback_program.py). These tests exercise the dormant
    vmap-64 machinery with Motor 1.8 opted back in."""
    from carbon.development_session import direct_graph_construction_worker

    monkeypatch.setattr(
        direct_graph_construction_worker,
        "VMAP64_INFERENCE_VERSIONS",
        frozenset({("electric-motor-magnetics", "1.8")}),
    )
