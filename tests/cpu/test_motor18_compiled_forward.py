"""Motor 1.8's inference compiles each member's forward, as the SAME version (owner, Sun 15 Nov 2026 via the Lead:
"nope I'm counting that as the same version. 15 decimal places is fine.").

Claims: only Motor 1.8 gets the compiled program, which differs from the eager one by one anchored line, and every
program derived from it (the speed gate's single calls, the practice timing) still derives; on PUBLIC practice rows the
compiled per-case answers equal the eager interpreter's within 1e-12; the repeat pair answers bit for bit alike; and the
speed gate's timed single calls answer EXACTLY as the compiled graded run did (`outputs_match_graded`), so no grade
fails speed on a rounding difference. The programs really run (subprocesses) over a real codec state with synthetic
parameters; this is program-contract evidence, not a speed measurement, science or qualification.
"""

from __future__ import annotations

import base64
import json
import os

import numpy as np
import pytest

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


def test_only_motor_1_8_gets_the_compiled_program_and_it_differs_by_one_line():
    assert worker.JIT_INFERENCE_VERSIONS == frozenset({MOTOR_18})
    for key in physical_graph_adapter_v2.SPECS:
        program = worker.v2_infer_query(*key)["program"]
        expected = (
            worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
            if key == MOTOR_18
            else worker.PHYSICAL_V2_INFER_PROGRAM
        )
        assert program == expected, key
    compiled = worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
    assert "jax.jit(rebuild(doc, allowed))" in compiled
    assert "jax.jit" not in worker.PHYSICAL_V2_INFER_PROGRAM
    assert (
        compiled.replace(worker._COMPILED_MEMBER, worker._EAGER_MEMBER)
        == worker.PHYSICAL_V2_INFER_PROGRAM
    )
    compile(compiled, "compiled", "exec")


def test_the_programs_derived_from_the_compiled_one_still_derive_and_stay_compiled():
    compiled = worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
    for derived in (
        single_call_timing.program(compiled),
        bundle_construction_worker.timed_program(compiled),
    ):
        assert derived != compiled and "jax.jit(rebuild(doc, allowed))" in derived
        compile(derived, "derived", "exec")


@pytest.fixture(scope="module")
def motor18():
    from test_registered_graph_pair_execution import _artifact

    # seeded random parameters: every public row answers differently, so equality checks cannot pass on a constant
    return _artifact("ensemble64", MOTOR_18, seed=18)


def _contract(artifact):
    limits = artifact["material"]["construction_limits_document"]
    bundle_construction_worker.verify_direct_resource_policy(
        artifact["binding"], limits
    )
    _loader, query, dtype = worker.registered_inference_contract(
        artifact["binding"], limits, recipe=artifact["recipe"]
    )
    assert dtype == artifact["dtype"] == "float64"
    assert query["program"] == worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
    return limits, query


@posix
def test_the_compiled_pair_equals_the_eager_answers_within_1e_12_on_public_rows(
    motor18, tmp_path
):
    from test_paired_inference import FixtureLedger
    from test_registered_graph_pair_execution import _expected, _image, _runner

    _contract(motor18)
    ledger, seen = FixtureLedger(tmp_path), []
    try:
        evidence = paired_inference.infer_frozen_pair(
            ledger,
            owner="fixture-owner",
            identity="compiled-pair",
            inference_image=_image(),
            recipe=motor18["recipe"],
            challenge_binding=motor18["binding"],
            limits_document=motor18["material"]["construction_limits_document"],
            state_bytes=motor18["state"],
            expected_state_digest=paired_inference._digest(motor18["state"]),
            inputs=motor18["inputs"],
            expected_output_shape=(len(motor18["inputs"]), motor18["width"]),
            expected_output_dtype=motor18["dtype"],
            allowlist_bytes=motor18["material"]["allowlist_bytes"],
            seconds=motor18["policy"]["inference_wall_seconds_max"],
            total_seconds=motor18["policy"]["total_reconstruction_wall_seconds_max"],
            procedure="per_case",
            runner=_runner(ledger, seen),
        ).evidence
    finally:
        ledger.connection.close()
    assert len(seen) == 2
    # the child really ran the compiled program (the runner gets it as its source)
    assert all(
        "member_forward = jax.jit(rebuild(doc, allowed))" in call["source"]
        for call in seen
    )
    phases = [
        np.asarray(
            json.loads(
                base64.b64decode(
                    evidence[phase]["originals"]["predictions.json"]["raw_base64"]
                )
            )
        )
        for phase in ("primary", "repeat")
    ]
    np.testing.assert_array_equal(phases[0], phases[1])  # the repeat: bit for bit
    eager = _expected(motor18, per_case=True)  # the interpreter, op by op
    assert np.all(np.isfinite(eager)) and np.any(eager != 0)
    assert len({row.tobytes() for row in eager}) == len(eager)  # every row differs
    np.testing.assert_allclose(phases[0], eager, rtol=1e-12, atol=1e-12)


@posix
def test_the_timed_single_calls_answer_exactly_as_the_compiled_graded_run(
    motor18, tmp_path
):
    from test_paired_inference import FixtureLedger
    from test_registered_graph_pair_execution import _image, _runner

    limits, query = _contract(motor18)
    program = query.pop("program")
    bank = np.tile(motor18["inputs"], (4, 1))
    indices = list(range(single_call_timing.SAMPLE))
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
    run = _runner(
        ledger, seen
    )  # one runner: its operation folders are numbered per runner
    try:
        graded = bundle_construction_worker._infer_state(
            ledger,
            identity="compiled-graded",
            inputs=bank,
            expected_output_shape=(len(bank), motor18["width"]),
            program=program,
            runner=run,
            **common,
        )
        timed = bundle_construction_worker._infer_state(
            ledger,
            identity="compiled-single-call",
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
    assert single_call_timing.outputs_match_graded(single, whole, indices) is True
    # not vacuous: the eight public rows answer differently, so a wrong row would not match
    assert len({tuple(row) for row in whole[:8]}) == 8
    assert (
        single_call_timing.outputs_match_graded(
            single, whole, indices[1:] + indices[:1]
        )
        is False
    )


@posix
def test_the_menu_row_check_answers_every_row_bit_for_bit_as_the_compiled_graded_run(
    motor18, tmp_path
):
    """The menu row check (tolerance 0/0) runs a FRESH process over a keyed subset in a keyed order, through the same
    registered procedure (Motor: ``per_case``). Under the compiled forward each row is still answered alone, at row 0
    of the declared batch, by a function compiled for that one shape, so neither the companions nor the position nor
    the subset size can change a bit."""
    import inspect

    from test_paired_inference import FixtureLedger
    from test_registered_graph_pair_execution import _image, _runner

    from carbon.scoring import motor18_dual_pack

    # Motor 1.8's definition is the sealed Motor one's, which registers the per-case repeat procedure
    assert motor18_dual_pack._sl().__name__ == "carbon.scoring.motor_sealed_dual_pack"
    assert '"paired_repeat_procedure": "per_case"' in inspect.getsource(
        motor18_dual_pack._sl().definition
    )
    _contract(motor18)  # Motor 1.8 resolves to the compiled program
    rows = motor18["inputs"]
    keyed = [5, 0, 7, 2, 3]  # a subset, out of order, of a different size
    ledger, seen = FixtureLedger(tmp_path), []
    run = _runner(
        ledger, seen
    )  # one runner: its operation folders are numbered per runner

    def pair(identity, inputs):
        evidence = paired_inference.infer_frozen_pair(
            ledger,
            owner="fixture-owner",
            identity=identity,
            inference_image=_image(),
            recipe=motor18["recipe"],
            challenge_binding=motor18["binding"],
            limits_document=motor18["material"]["construction_limits_document"],
            state_bytes=motor18["state"],
            expected_state_digest=paired_inference._digest(motor18["state"]),
            inputs=inputs,
            expected_output_shape=(len(inputs), motor18["width"]),
            expected_output_dtype=motor18["dtype"],
            allowlist_bytes=motor18["material"]["allowlist_bytes"],
            seconds=motor18["policy"]["inference_wall_seconds_max"],
            total_seconds=motor18["policy"]["total_reconstruction_wall_seconds_max"],
            procedure="per_case",
            runner=run,
        ).evidence
        raw = evidence["primary"]["originals"]["predictions.json"]["raw_base64"]
        return np.asarray(json.loads(base64.b64decode(raw)))

    try:
        graded = pair("compiled-graded-rows", rows)
        checked = pair("compiled-menu-rowcheck", np.ascontiguousarray(rows[keyed]))
    finally:
        ledger.connection.close()
    assert len(seen) == 4 and all(
        "member_forward = jax.jit(rebuild(doc, allowed))" in call["source"]
        for call in seen
    )
    assert len({row.tobytes() for row in graded}) == len(graded)  # every row differs
    assert checked.tobytes() == graded[keyed].tobytes()  # bit for bit, every row
