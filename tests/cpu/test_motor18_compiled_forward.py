"""Motor 1.8's inference: each member's forward compiled, and its GRADED per-case procedure run as isolated vmap-64
lanes, as the SAME version (owner, Sun 15 Nov 2026 via the Lead: "nope I'm counting that as the same version. 15
decimal places is fine."; then "I want the 64 rows working" and "Yes and yes"; ~11:1x CST: differences at the
13th-15th decimal are negligible; bound 1e-12, a TEST assertion here, never a runtime rule).

Claims: only Motor 1.8 gets the vmap-64 program, one anchored replacement of the compiled one, and every other
version's program keeps its bytes; every program derived from it (the speed gate's single calls, the practice timing)
still derives, with the timed calls still per-case; over 150 seeded rows (three chunks, the last short) the vmap-64
answers equal the eager interpreter's per-case answers within 1e-12 (bit equality is claimed neither way); the repeat
pair answers bit for bit alike; re-running the ORIGINAL chunks in a fresh process answers bit for bit; and the timed
single calls match the graded rows within a wide combined tolerance (`speed_match`; the values here are a synthetic
fixture, not the registered row). The programs really run (subprocesses) over a real codec state with synthetic
parameters; this is program-contract evidence, not a speed measurement, science or qualification.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os

import numpy as np
import pytest

from carbon.challenge_validator import speed_match
from carbon.development_session import (
    bundle_construction_worker,
    direct_graph_construction_worker,
    paired_inference,
    physical_graph_adapter_v2,
    single_call_timing,
)

worker = direct_graph_construction_worker
MOTOR_18 = ("electric-motor-magnetics", "1.8")
posix = pytest.mark.skipif(os.name != "posix", reason="fixed program subprocesses")
#: The owner's same-version bound (~11:1x): a test assertion only.
SAME_VERSION_BOUND = 1e-12
#: A SYNTHETIC wide tolerance for the timed-call check below (not the registered values row).
FIXTURE_TOLERANCE = (1e-9, 1e-12)
#: The eager and compiled programs' bytes at the vmap-64 head's base (origin/main 57af6692 and later): unchanged.
PROGRAM_SHA256 = {
    "PHYSICAL_V2_INFER_PROGRAM": "db89e9d63e84dda12547e629ab9aee52592c992dff50b0eb292173256a876c65",
    "PHYSICAL_V2_COMPILED_INFER_PROGRAM": "512cb25053d6b45b6e0db589618e7da895480f2070640739462dbd0787da248a",
    "PHYSICAL_INFER_PROGRAM": "dec3bf54fbaee202ed5f1621a7746e8c7f047d0fcdbc93cde32eacff2558d4de",
}
ROWS = 150  # chunks 0 and 1 full, chunk 2 holds 22 rows and 42 all-zero pad lanes


#: Motor 1.8's registered worker memory (16 GiB), baked into its vmap-64 program for the lane count.
MOTOR_18_MEMORY = 17179869184


def _vmap64():
    return worker.vmap64_infer_program(*MOTOR_18)


def test_only_motor_1_8_gets_the_vmap64_program_and_every_other_program_keeps_its_bytes():
    assert worker.JIT_INFERENCE_VERSIONS == frozenset({MOTOR_18})
    assert worker.VMAP64_INFERENCE_VERSIONS == frozenset({MOTOR_18})
    for name, sha in PROGRAM_SHA256.items():
        assert hashlib.sha256(getattr(worker, name).encode()).hexdigest() == sha, name
    for key in physical_graph_adapter_v2.SPECS:
        program = worker.v2_infer_query(*key)["program"]
        expected = _vmap64() if key == MOTOR_18 else worker.PHYSICAL_V2_INFER_PROGRAM
        assert program == expected, key
    with pytest.raises(RuntimeError, match="not a vmap-64 version"):
        worker.vmap64_infer_program("electric-motor-magnetics", "1.6")
    compiled = worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
    assert "jax.jit(rebuild(doc, allowed))" in compiled
    assert "jax.jit" not in worker.PHYSICAL_V2_INFER_PROGRAM
    assert (
        compiled.replace(worker._COMPILED_MEMBER, worker._EAGER_MEMBER)
        == worker.PHYSICAL_V2_INFER_PROGRAM
    )


def test_the_vmap64_program_is_two_anchored_replacements_of_the_compiled_one():
    lanes = _vmap64()
    compiled = worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
    defined = (
        worker._LANES_DEFINED.replace("__MEMORY_BYTES__", str(MOTOR_18_MEMORY))
        .replace("__SHARE__", "0.5")
        .replace("__MOST__", "64")
    )
    assert compiled.count(worker._PER_CASE_CALLS) == 1
    assert lanes.count(worker._VMAP64_CALLS) == 1 and lanes.count(defined) == 1
    assert (
        lanes.replace(worker._VMAP64_CALLS, worker._PER_CASE_CALLS).replace(
            defined, worker._COMPILED_MEMBER
        )
        == compiled
    )
    assert "jax.jit(jax.vmap(" in lanes
    assert (
        f"lane_count = vmap64_lanes(doc, len(member_arrays), {MOTOR_18_MEMORY}, 0.5, 64)"
        in lanes
    )
    # the program carries the host's own lane function, byte for byte
    import inspect

    assert inspect.getsource(worker.vmap64_lanes) in lanes
    assert "__" + "MEMORY_BYTES__" not in lanes
    compile(lanes, "vmap64", "exec")


def _branch(program, head, tail):
    start = program.index(head)
    return program[start : program.index(tail, start)]


def test_the_programs_derived_from_it_still_derive_and_the_timed_calls_stay_per_case():
    lanes = _vmap64()
    single = single_call_timing.program(lanes)
    practice = bundle_construction_worker.timed_program(lanes)
    for derived in (single, practice):
        assert derived != lanes and "jax.jit(rebuild(doc, allowed))" in derived
        compile(derived, "derived", "exec")
    # the speed gate's warm-up and timed calls: one design per call through the per-case compiled forward
    timed = _branch(single, "if single_call is not None:\n", "\nelif per_case:\n")
    assert "forward(*parameter_arrays, part)" in timed and "lane_forward" not in timed
    # the practice per-call timing: one design per call as well
    assert "produced = forward(*parameter_arrays, part)" in practice
    # the graded per-case branch of both derived programs is the vmap lanes
    for program in (lanes, single, practice):
        graded = _branch(
            program, "# One case per call: the case is row 0", "\nelif graph_source:\n"
        )
        assert "lane_forward(arrays, chunk)" in graded
        assert "forward(*parameter_arrays" not in graded


def _doc(per_case_values, parameter_values, batch=8):
    """A SYNTHETIC graph document carrying only what the lane count reads (declared shapes, float64)."""
    return {
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": [
                    {
                        "value": 0,
                        "name": "params/0",
                        "dtype": "float64",
                        "shape": [parameter_values],
                    },
                    {
                        "value": 1,
                        "name": "inputs/features",
                        "dtype": "float64",
                        "shape": [batch, 8],
                    },
                ],
                "nodes": [
                    {
                        "op": "tanh",
                        "in": [1],
                        "params": {},
                        "out": [
                            {
                                "value": 2,
                                "dtype": "float64",
                                "shape": [batch, per_case_values],
                            }
                        ],
                    },
                ],
                "outputs": [2],
            }
        },
    }


def test_the_lane_count_is_cut_until_a_chunk_fits_the_memory_share():
    gib = 1024**3
    # per case: (8 * 8 + 8 * 1000) * 8 bytes = 64512; parameters: 2 members * 1000 * 8 bytes
    small = _doc(1000, 1000)
    assert worker.vmap64_lanes(small, 2, 16 * gib, 0.5, 64) == 64
    assert worker.vmap64_model_lanes(*MOTOR_18, small, 2) == 64
    # a large declared activation: 8 GiB share / (8 * 8 * 8 + 8 * 2**24 * 8) bytes = 7 lanes
    large = _doc(2**24, 1000)
    per_case = (8 * 8 + 8 * 2**24) * 8
    assert (
        worker.vmap64_lanes(large, 2, 16 * gib, 0.5, 64)
        == (8 * gib - 16000) // per_case
        == 7
    )
    assert worker.vmap64_model_lanes(*MOTOR_18, large, 2) == 7
    # parameters that leave less than one per-case call: still one lane (the per-case call itself)
    assert worker.vmap64_lanes(_doc(1000, gib), 1, 16 * gib, 0.5, 64) == 1
    assert worker.vmap64_lanes(large, 1, 1, 0.5, 64) == 1
    # every graph of the document counts, not only the entry
    nested = _doc(1000, 1000)
    nested["graphs"]["body"] = {
        "inputs": [],
        "nodes": large["graphs"]["main"]["nodes"],
        "outputs": [],
    }
    assert worker.vmap64_lanes(nested, 2, 16 * gib, 0.5, 64) == 7


def test_the_original_chunks_of_graded_positions():
    chunks = worker.vmap64_chunks([140, 3, 60, 130, 10], ROWS, 64)
    assert list(chunks) == [0, 2]
    assert chunks[0] == tuple(range(64)) and chunks[2] == tuple(range(128, 150))
    rows, where = worker.vmap64_rerun_rows([140, 3, 60, 130, 10], ROWS, 64)
    assert rows == [*range(64), *range(128, 150)]
    for position, index in zip([140, 3, 60, 130, 10], where):
        assert rows[index] == position and index % 64 == position % 64
    assert worker.vmap64_rerun_rows([7, 7], 8, 64) == (list(range(8)), [7, 7])
    # the model's own L: chunk i // L, lane i % L
    rows, where = worker.vmap64_rerun_rows([149, 12], ROWS, 7)
    assert rows == [*range(7, 14), *range(147, 150)]
    assert [rows[i] for i in where] == [149, 12]
    assert worker.vmap64_rerun_rows([5, 0], 6, 1) == ([0, 5], [1, 0])
    for positions, count, lanes in (
        ([], 10, 64),
        ([10], 10, 64),
        ([-1], 10, 64),
        ([True], 10, 64),
        (["1"], 10, 64),
        ([1], 0, 64),
        (5, 10, 64),
        ([1], 10, 0),
        ([1], 10, 65),
        ([1], 10, True),
    ):
        with pytest.raises(ValueError, match="vmap64_chunk_positions_invalid"):
            worker.vmap64_chunks(positions, count, lanes)


@pytest.fixture(scope="module")
def motor18():
    from test_registered_graph_pair_execution import _artifact

    # seeded random parameters: every public row answers differently, so equality checks cannot pass on a constant
    return _artifact("ensemble64", MOTOR_18, seed=18)


def _rows(artifact, count=ROWS):
    """``count`` distinct rows near the public practice rows (synthetic, public)."""
    base = artifact["inputs"]
    rows = np.concatenate([base * (1.0 + 0.004 * k) for k in range(-(-count // 8))])
    rows = np.ascontiguousarray(rows[:count], dtype=base.dtype)
    assert len({row.tobytes() for row in rows}) == count
    return rows


def _eager(artifact, rows):
    """The interpreter, op by op, one row per call at row 0 of the declared batch (the per-case procedure)."""
    from test_registered_graph_pair_execution import _precision

    from carbon.level4 import interpret

    doc, members, mu, sd, combine = artifact["loaded"]
    batch = doc["graphs"][doc["entry"]]["inputs"][-1]["shape"][0]
    with _precision(artifact["dtype"]):
        import jax.numpy as jnp

        fn = interpret.rebuild(doc, artifact["allowlist"])
        out = []
        for row in rows:
            padded = np.zeros((batch, *rows.shape[1:]), rows.dtype)
            padded[0] = row
            total = sum(
                np.asarray(
                    fn(*[jnp.asarray(p) for p in params], jnp.asarray(padded))[0]
                )
                * combine[index]
                for index, params in enumerate(members)
            )
            out.append((total * sd + mu)[0])
        return np.asarray(out)


def _contract(artifact):
    limits = artifact["material"]["construction_limits_document"]
    bundle_construction_worker.verify_direct_resource_policy(
        artifact["binding"], limits
    )
    _loader, query, dtype = worker.registered_inference_contract(
        artifact["binding"], limits, recipe=artifact["recipe"]
    )
    assert dtype == artifact["dtype"] == "float64"
    assert query["program"] == _vmap64()
    return limits, query


def _pair(artifact, ledger, run, identity, inputs):
    """Both phases of a per-case pair (two fresh processes) over ``inputs``."""
    from test_registered_graph_pair_execution import _image

    evidence = paired_inference.infer_frozen_pair(
        ledger,
        owner="fixture-owner",
        identity=identity,
        inference_image=_image(),
        recipe=artifact["recipe"],
        challenge_binding=artifact["binding"],
        limits_document=artifact["material"]["construction_limits_document"],
        state_bytes=artifact["state"],
        expected_state_digest=paired_inference._digest(artifact["state"]),
        inputs=inputs,
        expected_output_shape=(len(inputs), artifact["width"]),
        expected_output_dtype=artifact["dtype"],
        allowlist_bytes=artifact["material"]["allowlist_bytes"],
        seconds=artifact["policy"]["inference_wall_seconds_max"],
        total_seconds=artifact["policy"]["total_reconstruction_wall_seconds_max"],
        procedure="per_case",
        runner=run,
    ).evidence
    return [
        np.asarray(
            json.loads(
                base64.b64decode(
                    evidence[phase]["originals"]["predictions.json"]["raw_base64"]
                )
            )
        )
        for phase in ("primary", "repeat")
    ]


@posix
def test_the_vmap64_pair_equals_eager_within_1e_12_and_repeats_bit_for_bit(
    motor18, tmp_path
):
    from test_paired_inference import FixtureLedger
    from test_registered_graph_pair_execution import _runner

    _contract(motor18)
    rows = _rows(motor18)
    ledger, seen = FixtureLedger(tmp_path), []
    try:
        primary, repeat = _pair(
            motor18, ledger, _runner(ledger, seen), "vmap64-pair", rows
        )
    finally:
        ledger.connection.close()
    assert len(seen) == 2
    # the child really ran the vmap-64 program (the runner gets it as its source)
    assert all("lane_forward = jax.jit(jax.vmap(" in call["source"] for call in seen)
    assert primary.tobytes() == repeat.tobytes()  # a fresh process repeats bit for bit
    eager = _eager(motor18, rows)
    assert np.all(np.isfinite(eager)) and np.any(eager != 0)
    assert len({row.tobytes() for row in eager}) == len(eager)  # every row differs
    assert primary.shape == eager.shape == (ROWS, motor18["width"])
    # the owner's same-version bound; bit equality is claimed neither way
    assert float(np.max(np.abs(primary - eager))) < SAME_VERSION_BOUND


@posix
def test_rerunning_the_original_chunks_in_a_fresh_process_is_bit_exact(
    motor18, tmp_path
):
    """The menu row check and the subset repeat's form: the rows of the ORIGINAL chunks, ascending, through the same
    program in a fresh process, each graded position answered bit for bit (tolerance 0/0).
    """
    from test_paired_inference import FixtureLedger
    from test_registered_graph_pair_execution import _runner

    _contract(motor18)
    rows = _rows(motor18)
    keyed = [140, 3, 60, 130, 10]  # a keyed order, chunks 0 and 2 (the short last one)
    doc, members = motor18["loaded"][:2]
    assert (
        worker.vmap64_model_lanes(*MOTOR_18, doc, len(members)) == 64
    )  # a small model
    queried, where = worker.vmap64_rerun_rows(keyed, ROWS, 64)
    ledger, seen = FixtureLedger(tmp_path), []
    run = _runner(ledger, seen)
    try:
        graded, _ = _pair(motor18, ledger, run, "vmap64-graded", rows)
        again, _ = _pair(
            motor18, ledger, run, "vmap64-chunks", np.ascontiguousarray(rows[queried])
        )
    finally:
        ledger.connection.close()
    assert len(seen) == 4
    assert again.shape == (len(queried), motor18["width"])
    assert again[where].tobytes() == graded[keyed].tobytes()  # bit for bit, every row
    # every re-run row, not only the keyed ones
    assert again.tobytes() == graded[queried].tobytes()


@posix
def test_the_timed_single_calls_match_the_vmap64_graded_rows_within_the_tolerance(
    motor18, tmp_path
):
    from test_paired_inference import FixtureLedger
    from test_registered_graph_pair_execution import _image, _runner

    limits, query = _contract(motor18)
    program = query.pop("program")
    bank = _rows(motor18)
    indices = list(range(0, ROWS, 7))[: single_call_timing.SAMPLE]  # every chunk
    assert len(indices) == single_call_timing.SAMPLE and indices[-1] >= 128
    common = {
        "owner": "fixture-owner",
        "inference_image": _image(),
        "recipe": motor18["recipe"],
        "binding": motor18["binding"],
        "state": motor18["state"],
        "state_digest": paired_inference._digest(motor18["state"]),
        "expected_output_dtype": motor18["dtype"],
        "allowlist_bytes": motor18["material"]["allowlist_bytes"],
        "seconds": motor18["policy"]["inference_wall_seconds_max"],
        **bundle_construction_worker.rebuild_wall_kwargs(limits),
        **query,
    }
    ledger, seen = FixtureLedger(tmp_path), []
    run = _runner(ledger, seen)
    try:
        graded = bundle_construction_worker._infer_state(
            ledger,
            identity="vmap64-graded",
            inputs=bank,
            expected_output_shape=(len(bank), motor18["width"]),
            program=program,
            runner=run,
            **common,
        )
        timed = bundle_construction_worker._infer_state(
            ledger,
            identity="vmap64-single-call",
            inputs=bank,
            expected_output_shape=(single_call_timing.SAMPLE, motor18["width"]),
            single_call={"indices": indices, "warmup": motor18["inputs"][:1]},
            program=single_call_timing.program(program),
            runner=run,
            **common,
        )
    finally:
        ledger.connection.close()
    single = np.asarray(timed.predictions).tolist()
    whole = np.asarray(graded.predictions).tolist()
    assert speed_match.outputs_agree(single, whole, indices, FIXTURE_TOLERANCE) is True
    # the per-case timed answers are within the same-version bound of the vmap-64 graded rows
    gap = np.abs(np.asarray(single) - np.asarray(whole)[indices])
    assert float(np.max(gap)) < SAME_VERSION_BOUND
    # not vacuous: rows answer differently, so a wrong row does not agree
    assert (
        speed_match.outputs_agree(
            single, whole, indices[1:] + indices[:1], FIXTURE_TOLERANCE
        )
        is False
    )
    # planted: one timed value far beyond the tolerance does not agree
    planted = [list(row) for row in single]
    planted[5][17] = whole[indices[5]][17] + 1e-6
    assert (
        speed_match.outputs_agree(planted, whole, indices, FIXTURE_TOLERANCE) is False
    )


@posix
@pytest.mark.parametrize("lanes", [5, 1])
def test_at_a_smaller_lane_count_the_original_chunks_still_rerun_bit_exact(
    motor18, tmp_path, monkeypatch, lanes
):
    """A model whose declared activations leave room for fewer lanes (here: a smaller registered memory, so the SAME
    small model gets L = 5 or 1): the graded pass and the original-chunk re-run use the same L, bit for bit, and the
    answers stay within the same-version bound of eager."""
    from test_paired_inference import FixtureLedger
    from test_registered_graph_pair_execution import _runner

    from carbon.level4.graph import nbytes

    doc, members = motor18["loaded"][:2]
    declared = doc["graphs"][doc["entry"]]["inputs"]
    parameter_bytes = len(members) * sum(nbytes(entry) for entry in declared[:-1])
    per_case = nbytes(declared[-1]) + sum(
        nbytes(out)
        for graph in doc["graphs"].values()
        for node in graph["nodes"]
        for out in node["out"]
    )
    memory = 2 * (
        parameter_bytes + lanes * per_case
    )  # share 0.5: exactly L per-case calls fit
    monkeypatch.setattr(worker, "_version_memory_bytes", lambda *_key: memory)
    worker.vmap64_infer_program.cache_clear()
    try:
        assert worker.vmap64_model_lanes(*MOTOR_18, doc, len(members)) == lanes
        assert (
            f"lane_count = vmap64_lanes(doc, len(member_arrays), {memory}, 0.5, 64)"
            in _contract(motor18)[1]["program"]
        )
        rows = _rows(motor18)
        keyed = [149, 3, 77, 12]
        queried, where = worker.vmap64_rerun_rows(keyed, ROWS, lanes)
        assert queried == [
            row
            for chunk in sorted({p // lanes for p in keyed})
            for row in range(chunk * lanes, min(chunk * lanes + lanes, ROWS))
        ]
        ledger, seen = FixtureLedger(tmp_path), []
        run = _runner(ledger, seen)
        try:
            graded, repeat = _pair(motor18, ledger, run, f"lanes{lanes}-graded", rows)
            again, _ = _pair(
                motor18,
                ledger,
                run,
                f"lanes{lanes}-chunks",
                np.ascontiguousarray(rows[queried]),
            )
        finally:
            ledger.connection.close()
        assert graded.tobytes() == repeat.tobytes()
        assert again[where].tobytes() == graded[keyed].tobytes()
        assert again.tobytes() == graded[queried].tobytes()
        assert (
            float(np.max(np.abs(graded - _eager(motor18, rows)))) < SAME_VERSION_BOUND
        )
    finally:
        worker.vmap64_infer_program.cache_clear()
