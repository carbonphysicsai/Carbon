"""Per-case worker processes inside ONE graded pass (`carbon.development_session.case_procs`; Lead's order, Mon 16 Nov
2026).

Claims: only Motor 1.8 gets the per-case processes program, four anchored edits of the compiled one, and every other
version's program keeps its bytes; the speed gate's single-call program and the practice timed program derived from it
are byte for byte those of A9's per-case compiled program (timing untouched); the process count is the cpuset's cores,
cut by the operational memory bound. Run for real (subprocesses over a real codec state with seeded synthetic
parameters, POSIX): the workers' reassembled answers equal the one-process program's bit for bit and the workers were
really used; a worker answer that differs on the checked row, and a worker that fails, both give the one-process
answers. Program-contract evidence, not a speed measurement, science or qualification.
"""

from __future__ import annotations

import base64
import hashlib
import inspect
import itertools
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from carbon.development_session import (
    bundle_construction_worker,
    case_procs,
    direct_graph_construction_worker,
    paired_inference,
    physical_graph_adapter_v2,
    single_call_timing,
)

worker = direct_graph_construction_worker
MOTOR_18 = ("electric-motor-magnetics", "1.8")
#: sha256 of A9's (57af6692) Motor 1.8 program, the per-case compiled one (tests/cpu/test_motor18_rollback_program.py).
A9_MOTOR_18_PROGRAM_SHA256 = (
    "512cb25053d6b45b6e0db589618e7da895480f2070640739462dbd0787da248a"
)
MOTOR_18_MEMORY = 17179869184
#: Motor 1.8's registered inference wall (`inference_wall_seconds_max`).
MOTOR_18_WALL = 648
posix = pytest.mark.skipif(
    not hasattr(os, "sched_getaffinity"), reason="worker processes pin by affinity"
)
ROWS = 150


def _procs():
    return worker.case_procs_infer_program(*MOTOR_18)


def test_only_motor_1_8_gets_the_per_case_processes_program():
    assert worker.CASE_PROCS_INFERENCE_VERSIONS == frozenset({MOTOR_18})
    assert worker.CASE_PROCS_INFERENCE_VERSIONS <= worker.JIT_INFERENCE_VERSIONS
    assert not worker.CASE_PROCS_INFERENCE_VERSIONS & worker.VMAP64_INFERENCE_VERSIONS
    for key in physical_graph_adapter_v2.SPECS:
        program = worker.v2_infer_query(*key)["program"]
        expected = _procs() if key == MOTOR_18 else worker.PHYSICAL_V2_INFER_PROGRAM
        assert program == expected, key
    with pytest.raises(RuntimeError, match="not a per-case processes version"):
        worker.case_procs_infer_program("electric-motor-magnetics", "1.6")


def test_its_one_process_program_is_a9s_byte_for_byte_and_timing_is_unchanged():
    procs = _procs()
    compiled = worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
    assert procs != compiled
    serial = case_procs.serial_program(procs)
    assert serial == compiled
    assert hashlib.sha256(serial.encode()).hexdigest() == A9_MOTOR_18_PROGRAM_SHA256
    # the speed gate's single calls and the practice timed program: today's bytes
    assert single_call_timing.program(procs) == single_call_timing.program(compiled)
    assert bundle_construction_worker.timed_program(
        procs
    ) == bundle_construction_worker.timed_program(compiled)
    for derived in (
        single_call_timing.program(procs),
        bundle_construction_worker.timed_program(procs),
    ):
        assert case_procs.CONTROL_NAME not in derived
    # any other program passes unchanged
    for other in (
        compiled,
        worker.PHYSICAL_V2_INFER_PROGRAM,
        bundle_construction_worker.INFER_PROGRAM,
    ):
        assert case_procs.serial_program(other) is other


def test_the_program_is_four_anchored_edits_of_the_compiled_one():
    procs = _procs()
    compiled = worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
    assert case_procs.SERIAL_CALLS == worker._PER_CASE_CALLS
    from carbon.challenge_kit import physical_public

    policy = physical_public.construction_limits_document(*MOTOR_18)[
        "reconstruction_resource_policy"
    ]
    assert policy["inference_wall_seconds_max"] == MOTOR_18_WALL
    edits = case_procs._edits(MOTOR_18_MEMORY, MOTOR_18_WALL)
    assert len(edits) == 4
    rebuilt = compiled
    for old, new in edits:
        assert compiled.count(old) == 1 and procs.count(new) == 1
        rebuilt = rebuilt.replace(old, new)
    assert rebuilt == procs
    # the program carries the host's own count function, byte for byte, and its operational bounds
    body = "".join(
        ("    " + line) if line.strip() else line
        for line in inspect.getsource(case_procs.case_procs_count).splitlines(
            keepends=True
        )
    )
    assert body.rstrip("\n") in procs
    assert (
        "case_procs_count(doc, len(member_arrays), len(state),"
        f" {MOTOR_18_MEMORY}, 0.5, {1024**3}," in procs
    )
    assert "allowance = 4.0 * (first + per_row * len(cores)" in procs
    assert "case_wall_end = case_start + 648 - 30\n" in procs
    assert "time.monotonic() + 1.25 * per_row * left > case_wall_end" in procs
    for placeholder in (
        "__COUNT_SOURCE__",
        "__MEMORY_BYTES__",
        "__SHARE__",
        "__PROCESS_BYTES__",
        "__CONTROL_NAME__",
        "__SLACK__",
        "__WALL_SECONDS__",
        "__WALL_MARGIN__",
        "__FALLBACK_SLACK__",
    ):
        assert placeholder not in procs
    compile(procs, "case-procs", "exec")
    with pytest.raises(RuntimeError, match="anchor moved"):
        case_procs.procs_program(procs, MOTOR_18_MEMORY, MOTOR_18_WALL)
    for memory, wall in ((0, MOTOR_18_WALL), (MOTOR_18_MEMORY, 0)):
        with pytest.raises(RuntimeError, match="worker limits unregistered"):
            case_procs.procs_program(compiled, memory, wall)
    # strict: any other text in the edited block is refused, and the speed gate refuses it as its own anchor error
    for changed in (
        procs.replace("def case_block(index):", "x", 1),
        procs.replace("same(answer[-1:], sample[high - 1])", "True", 1),
        procs.replace("allowance = 4.0 *", "allowance = 40.0 *", 1),
        procs.replace("case_start + 648 - 30", "case_start + 648 - 3", 1),
    ):
        with pytest.raises(RuntimeError, match="anchor moved"):
            case_procs.serial_program(changed)
        with pytest.raises(
            single_call_timing.SingleCallRefused,
            match="single_call_program_anchor_moved",
        ):
            single_call_timing.program(changed)


#: sha256 of Motor 1.8's per-case processes program at this head: any edit of the GRADED program (the count
#: function's source included) must change this pin on purpose.
PROCS_PROGRAM_SHA256 = (
    "76b14f5355b12e3da743975d2c81a23253a853d2258d78ed91afe902ac3f4a3b"
)


def test_the_graded_program_bytes_are_pinned():
    assert hashlib.sha256(_procs().encode()).hexdigest() == PROCS_PROGRAM_SHA256


def _doc(per_case_values, parameter_values, batch=8):
    """A SYNTHETIC graph document carrying only what the count reads (declared shapes, float64)."""
    return {
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": [
                    {"value": 0, "dtype": "float64", "shape": [parameter_values]},
                    {"value": 1, "dtype": "float64", "shape": [batch, 8]},
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
                    }
                ],
                "outputs": [2],
            }
        },
    }


def test_the_process_count_is_the_cores_cut_by_the_memory_bound():
    gib = 1024**3
    count = case_procs.case_procs_count
    small = _doc(1000, 1000)
    # 8 GiB share / (~1 GiB per process) - 1 (the parent) = 6, then the cores and the rows
    assert count(small, 2, 0, 16 * gib, 0.5, gib, 4, ROWS) == 4
    assert count(small, 2, 0, 16 * gib, 0.5, gib, 64, ROWS) == 6
    assert count(small, 2, 0, 16 * gib, 0.5, gib, 4, 3) == 3
    assert count(small, 2, 0, 16 * gib, 0.5, gib, 1, ROWS) == 1
    # the state's bytes and three copies of the parameters count: 8 GiB / (3 GiB + 1 GiB + ...) - 1 = 1
    assert count(small, 2, 3 * gib, 16 * gib, 0.5, gib, 4, ROWS) == 1
    # 2 members x gib/64 values x 8 bytes = gib/4; 8 GiB // (3 x gib/4 + 1 GiB + ...) - 1 = 3
    assert count(_doc(1000, gib // 64), 2, 0, 16 * gib, 0.5, gib, 4, ROWS) == 3
    # a model that leaves room for no worker: one process (the parent's own calls)
    assert count(_doc(1000, gib), 1, 0, 16 * gib, 0.5, gib, 4, ROWS) == 1
    assert count(small, 2, 0, 1, 0.5, gib, 4, ROWS) == 1


# -- the real program -------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def motor18():
    from test_registered_graph_pair_execution import _artifact

    return _artifact("ensemble64", MOTOR_18, seed=18)


def _rows(artifact, count=ROWS):
    base = artifact["inputs"]
    rows = np.concatenate([base * (1.0 + 0.004 * k) for k in range(-(-count // 8))])
    rows = np.ascontiguousarray(rows[:count], dtype=base.dtype)
    assert len({row.tobytes() for row in rows}) == count
    return rows


def _file_runner(ledger, seen, change=lambda source: source):
    """The local runner, but the program runs from a FILE as the carrier runs /input/program.py (so its workers can
    re-run it); ``change`` edits the program text (test variants only)."""
    count = itertools.count()

    def runner(current_ledger, *, source, files, output_validator, identity, **_kw):
        name = f"operation-{next(count):064x}"
        home = ledger.root / name
        work = home / "workspace"
        work.mkdir(parents=True)
        (home / "output").mkdir()
        for filename, body in files.items():
            (work / filename).write_bytes(body)
        program = home / "program.py"
        program.write_text(change(source), encoding="utf-8")
        # as the carrier runs it: an isolated interpreter over a program file
        done = subprocess.run(
            [sys.executable, "-I", str(program)],
            cwd=work,
            env={**os.environ, "JAX_PLATFORMS": "cpu"},
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        seen.append({"source": source, "stderr": done.stderr, "code": done.returncode})
        assert done.returncode == 0, done.stderr[-4000:]
        snapshot = home / "snapshot"
        (home / "output").rename(snapshot)
        output_validator(snapshot)
        result = {
            "operation": name,
            "files": {
                path.name: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                for path in snapshot.iterdir()
            },
        }
        ledger.record(identity, "SUCCEEDED", {"numerical_milliseconds": 1}, result)
        return result

    return runner


def _graded(artifact, ledger, run, identity, inputs):
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


_LEFT = "        left = sum(high - low for low, high in slices if low not in done)\n"


def _workers_used(source):
    """Test variant: the pass must have used every worker's answers (more than one worker)."""
    assert source.count(_LEFT) == 1
    return source.replace(
        _LEFT,
        '        assert len(done) == len(slices) > 1, "per-case workers not used"\n'
        + _LEFT,
    )


def _serial(artifact, tmp_path, inputs):
    from test_paired_inference import FixtureLedger

    ledger, seen = FixtureLedger(tmp_path / "serial"), []
    try:
        primary, repeat = _graded(
            artifact,
            ledger,
            _file_runner(ledger, seen, case_procs.serial_program),
            "one-process",
            inputs,
        )
    finally:
        ledger.connection.close()
    assert primary.tobytes() == repeat.tobytes()
    assert all(case_procs.CONTROL_NAME in call["source"] for call in seen)
    return primary


def _cores():
    return len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else 0


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
def test_the_workers_answer_bit_for_bit_as_one_process(motor18, tmp_path):
    from test_paired_inference import FixtureLedger

    rows = _rows(motor18)
    serial = _serial(motor18, tmp_path, rows)
    assert np.all(np.isfinite(serial)) and len({r.tobytes() for r in serial}) == ROWS
    ledger, seen = FixtureLedger(tmp_path / "procs"), []
    try:
        primary, repeat = _graded(
            motor18,
            ledger,
            _file_runner(ledger, seen, _workers_used),
            "procs",
            rows,
        )
    finally:
        ledger.connection.close()
    assert len(seen) == 2 and all(call["source"] == _procs() for call in seen)
    assert all("case_procs:" not in call["stderr"] for call in seen)
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()


_SAME = "        same = lambda a, b: a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()\n"
_WORKER_START = "        _, low, high, core = case_proc\n"
_WORKER_PART = (
    '        np.save(procs_dir / f"part-{low}.tmp.npy", np.concatenate(blocks))\n'
)
_SPAWN = '                    [sys.executable, "-I", script],\n'


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
@pytest.mark.parametrize(
    ("variant", "said"),
    [
        # a worker answer that differs on its checked row: every call in one process
        (
            lambda source: source.replace(_SAME, "        same = lambda a, b: False\n"),
            "differs from one process",
        ),
        # every worker but the first fails before its first row: their slices in one process
        (
            lambda source: source.replace(
                _WORKER_START,
                _WORKER_START + "        if low > 0:\n            os._exit(3)\n",
            ),
            "exit 3; its rows in one process",
        ),
        # a worker that hangs after its first row: stopped at its deadline, its slice in one process
        (
            lambda source: source.replace(
                _WORKER_PART,
                "        if low > 0:\n            time.sleep(10**6)\n" + _WORKER_PART,
            ),
            "; its rows in one process",
        ),
        # a worker that hangs BEFORE its first row: stopped at its deadline, its slice in one process
        (
            lambda source: source.replace(
                _WORKER_START,
                _WORKER_START + "        if low > 0:\n            time.sleep(10**6)\n",
            ),
            "; its rows in one process",
        ),
        # every worker fails: the whole pass in one process
        (
            lambda source: source.replace(
                _WORKER_START, _WORKER_START + "        os._exit(3)\n"
            ),
            "exit 3; its rows in one process",
        ),
        # no worker can start: every call in one process
        (
            lambda source: source.replace(
                _SPAWN,
                '                    ["/nonexistent/carbon-python", "-I", script],\n',
            ),
            "a worker could not start; every call in one process",
        ),
        # a worker whose first row agrees but whose LAST row differs: every call in one process
        (
            lambda source: source.replace(
                _WORKER_PART,
                "        blocks[-1] = blocks[-1] + 1.0\n" + _WORKER_PART,
            ),
            "differs from one process",
        ),
    ],
)
def test_a_differing_or_failed_worker_gives_the_one_process_answers(
    motor18, tmp_path, variant, said
):
    from test_paired_inference import FixtureLedger

    rows = _rows(motor18, 40)
    serial = _serial(motor18, tmp_path, rows)
    for anchor in (_SAME, _WORKER_START, _WORKER_PART, _SPAWN):
        assert _procs().count(anchor) == 1
    ledger, seen = FixtureLedger(tmp_path / "variant"), []
    try:
        primary, repeat = _graded(
            motor18, ledger, _file_runner(ledger, seen, variant), "variant", rows
        )
    finally:
        ledger.connection.close()
    assert all(said in call["stderr"] for call in seen)
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
def test_a_fallback_that_cannot_finish_inside_the_wall_stops_as_carbons(
    motor18, tmp_path
):
    """Every worker fails and no time is left before the wall margin: the parent stops at once, nonzero, with the
    CARBON line on stderr (the host reads it as Carbon's), never running into the wall.
    """
    from test_paired_inference import FixtureLedger

    def variant(source):
        wall = f"case_start + {MOTOR_18_WALL} - "
        assert source.count(wall) == 1 and source.count(_WORKER_START) == 1
        return source.replace(wall, "case_start + 0 - ").replace(
            _WORKER_START, _WORKER_START + "        os._exit(3)\n"
        )

    ledger, seen = FixtureLedger(tmp_path / "wall"), []
    try:
        raised = None
        try:
            _graded(
                motor18,
                ledger,
                _file_runner(ledger, seen, variant),
                "wall",
                _rows(motor18, 40),
            )
        except Exception as error:  # noqa: BLE001 - the runner refuses the nonzero exit
            raised = error
    finally:
        ledger.connection.close()
    assert raised is not None
    assert seen and seen[0]["code"] == 3
    assert (
        "case_procs: CARBON: 40 rows left cannot finish inside the inference wall"
        in seen[0]["stderr"]
    )


@posix
def test_without_a_program_file_the_pass_is_one_process(motor18, tmp_path):
    """Run as `python -c` (no program file for a worker): one process, no fallback line, the one-process answers."""
    from test_graph_route_v2 import _local_runner
    from test_paired_inference import FixtureLedger

    rows = _rows(motor18, 20)
    serial = _serial(motor18, tmp_path, rows)
    ledger = FixtureLedger(tmp_path / "dash-c")
    local = _local_runner()

    def run(current_ledger, **kwargs):
        result = local(current_ledger, **kwargs)
        ledger.record(
            kwargs["identity"], "SUCCEEDED", {"numerical_milliseconds": 1}, result
        )
        return result

    try:
        primary, repeat = _graded(motor18, ledger, run, "dash-c", rows)
    finally:
        ledger.connection.close()
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()


def test_the_host_never_charges_the_candidate_for_a_pass_that_fell_back():
    """`research_carrier._candidate_resource_stop`: a failure whose stderr carries a per-case fallback line is
    Carbon's, even with the container's OOM flag set (a worker killed for memory); without the line it stays the
    candidate's memory stop, as before."""
    from carbon.development_session import research_carrier
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    observed = {"status": "OBSERVED", "state": {"oom_killed": True}, "memory": None}

    def stop(diagnostic):
        return research_carrier._candidate_resource_stop(
            None,
            WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=diagnostic),
            container_name="c",
            launch_digest="sha256:" + "1" * 64,
            image_id="sha256:" + "2" * 64,
            program_started=0.0,
            program_timeout=648,
            setup_seconds=1.0,
            observation=observed,
            deadline=0.0,
            memory_limit_bytes=16 * 1024**3,
            accelerated=False,
        )

    assert stop(b"exit=1\nstderr:\nTraceback ...") is not None
    assert (
        stop(
            b"exit=1\nstderr:\ncase_procs: worker 2 exit -9; its rows in one process\n"
        )
        is None
    )
    assert (
        stop(
            b"exit=3\nstderr:\ncase_procs: CARBON: 40 rows left cannot finish inside the inference wall\n"
        )
        is None
    )
