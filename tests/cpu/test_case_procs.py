"""Per-case worker processes inside ONE graded pass (`carbon.development_session.case_procs`; Lead's order, Mon 16 Nov
2026).

Claims: only Motor 1.8 gets the per-case processes program, four anchored edits of the compiled one, and every other
version's program keeps its bytes; the speed gate's single-call program and the practice timed program derived from it
are byte for byte those of A9's per-case compiled program (timing untouched); the process count is the cpuset's cores,
cut by the operational memory bound. Run for real (subprocesses over a real codec state with seeded synthetic
parameters, POSIX): the workers' reassembled answers equal the one-process program's bit for bit and the workers were
really used; a worker answer that differs on the checked row, and a worker that fails, both give the one-process
answers. Validator-2's findings of 16 Nov: workers only when the WORST case fits the wall (F1); a fallback is Carbon's
ONCE and every later run of the same pass is the one-process program (F2); the two program digests (F3). Program-contract
evidence, not a speed measurement, science or qualification.
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
        if key == MOTOR_18:
            expected = _procs()
        elif key in worker.JIT_INFERENCE_VERSIONS:
            # Motor 1.9 (audit #16): compiled, one process (its trust query needs a program with a trust variant)
            expected = worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM
        else:
            expected = worker.PHYSICAL_V2_INFER_PROGRAM
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
    for function in (case_procs.case_procs_count, case_procs.case_procs_deadline):
        assert case_procs._indented_source(function) in procs
    assert "rows, len(sample), case_wall_end,\n" in procs
    assert "                                       4.0, 1.25, 10.0, 1.5)\n" in procs
    # the parent times a row pinned to ONE core (as a worker runs) and gives the whole cpuset back after
    assert "os.sched_setaffinity(int(task), {cores[0]})" in procs
    assert "os.sched_setaffinity(int(task), set(cores))" in procs
    assert "case_wall_end = case_start + 648 - 135\n" in procs
    assert "time.monotonic() + 1.25 * per_row * left > case_wall_end" in procs
    for placeholder in (
        "__COUNT_SOURCE__",
        "__DEADLINE_SOURCE__",
        "__MEMORY_BYTES__",
        "__SHARE__",
        "__PROCESS_BYTES__",
        "__CONTROL_NAME__",
        "__SLACK__",
        "__WALL_SECONDS__",
        "__WALL_MARGIN__",
        "__FALLBACK_SLACK__",
        "__KILL__",
        "__GAIN__",
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
        procs.replace("  4.0, 1.25, 10.0, 1.5)\n", "  40.0, 1.25, 10.0, 1.5)\n", 1),
        procs.replace("  4.0, 1.25, 10.0, 1.5)\n", "  4.0, 1.25, 0.0, 1.5)\n", 1),
        procs.replace("  4.0, 1.25, 10.0, 1.5)\n", "  4.0, 1.25, 10.0, 0.0)\n", 1),
        procs.replace("{cores[0]})", "set(cores))", 1),
        procs.replace("case_start + 648 - 135", "case_start + 648 - 3", 1),
        procs.replace(
            "if fell_back and time.monotonic() + 1.25 * row_time > case_wall_end:",
            "if False:",
            1,
        ),
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
    "b1a5499c0e612d152d69f5117d03796b64c6d725d2c2487e198462596881c08e"
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
    pytest.importorskip("jax")
    from test_registered_graph_pair_execution import _artifact

    return _artifact("ensemble64", MOTOR_18, seed=18)


def _rows(artifact, count=ROWS):
    base = artifact["inputs"]
    rows = np.concatenate([base * (1.0 + 0.004 * k) for k in range(-(-count // 8))])
    rows = np.ascontiguousarray(rows[:count], dtype=base.dtype)
    assert len({row.tobytes() for row in rows}) == count
    return rows


#: The deadline's "workers must beat one process" gate, as the program carries it. The fixture graph is far too small
#: for workers to beat one process, so `_file_runner` drops it (test variants only) unless a test keeps it.
_BEATS_ONE_PROCESS = (
    "        if gain * need > per_row * (rows - sampled):\n            return None\n"
)


#: The deadline call's registered values, as the program carries them (`CASE_PROCS_DEADLINE_SLACK` first).
_DEADLINE_VALUES = "  4.0, 1.25, 10.0, 1.5)\n"


def _patient(source):
    """Test variant for the claims that need every worker to ARRIVE: the deadline is as late as the wall allows, so a busy
    host cannot stop a worker before its answer is read. The registered deadline rule has its own tests, and the variants
    that test a worker stopped at its deadline keep the registered slack."""
    assert source.count(_DEADLINE_VALUES) == 1
    return source.replace(_DEADLINE_VALUES, _DEADLINE_VALUES.replace("4.0", "400.0"))


def _file_runner(ledger, seen, change=lambda source: source, gate=False):
    """The local runner, but the program runs from a FILE as the carrier runs /input/program.py (so its workers can
    re-run it); ``change`` edits the program text (test variants only); ``gate`` keeps the deadline's
    `_BEATS_ONE_PROCESS` gate (else dropped: the fixture graph is too small for workers to win).
    """
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
        text = change(source)
        if not gate and case_procs.is_procs_program(text):
            assert text.count(_BEATS_ONE_PROCESS) == 1
            text = text.replace(_BEATS_ONE_PROCESS, "")
        program.write_text(text, encoding="utf-8")
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
            _file_runner(ledger, seen, lambda text: _patient(_workers_used(text))),
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
            lambda source: _patient(
                source.replace(_SAME, "        same = lambda a, b: False\n")
            ),
            "differs from one process",
        ),
        # every worker but the first fails before its first row: their slices in one process
        (
            lambda source: source.replace(
                _WORKER_START,
                _WORKER_START + "        if low > 0:\n            os._exit(3)\n",
            ),
            "exit 3, no part; its rows in one process",
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
            "exit 3, no part; its rows in one process",
        ),
        # no worker can start: every call in one process
        (
            lambda source: source.replace(
                _SPAWN,
                '                    ["/nonexistent/carbon-python", "-I", script],\n',
            ),
            "workers not started (FileNotFoundError); every call in one process",
        ),
        # a worker whose first row agrees but whose LAST row differs: every call in one process
        (
            lambda source: _patient(
                source.replace(
                    _WORKER_PART,
                    "        blocks[-1] = blocks[-1] + 1.0\n" + _WORKER_PART,
                )
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
    # the answers first (a missed detection would show here), then the fallback line each call wrote (shown on failure)
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()
    lines = [
        [line for line in call["stderr"].splitlines() if "case_procs:" in line]
        for call in seen
    ]
    assert all(said in call["stderr"] for call in seen), lines
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
def test_a_fallback_that_cannot_finish_inside_the_wall_stops_as_carbons(
    motor18, tmp_path
):
    """Every worker fails and (forced here) the parent's own calls for their rows cannot finish before the wall margin:
    the parent stops at once, nonzero, with the CARBON line on stderr (the host reads it as Carbon's), never running
    into the wall.
    """
    from test_paired_inference import FixtureLedger

    def variant(source):
        check = "1.25 * per_row * left > case_wall_end"
        assert source.count(check) == 1 and source.count(_WORKER_START) == 1
        return source.replace(
            check, "1.25 * per_row * left > case_wall_end - 10**9"
        ).replace(_WORKER_START, _WORKER_START + "        os._exit(3)\n")

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


def _stop(diagnostic, observed):
    from carbon.development_session import research_carrier
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

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


def test_a_fallback_is_carbons_only_for_a_per_case_processes_program():
    """Validator-2 F2: a FAILED per-case processes run whose stderr carries a fallback line is Carbon's
    (`research_carrier._case_procs_fell_back`, read before the resource checks); a one-process program's failure is
    never read for the mark, so its OOM and wall stops are classified exactly as main classifies them
    (`_candidate_resource_stop` itself is main's, unchanged)."""
    from carbon.development_session import research_carrier
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    procs, serial = _procs(), case_procs.serial_program(_procs())
    worker_killed = (
        b"exit=1\nstderr:\ncase_procs: worker 2 exit -9; its rows in one process\n"
    )
    past_margin = b"exit=3\nstderr:\ncase_procs: CARBON: row 9 of 40 past the wall margin after a fallback\n"

    def fell_back(source, diagnostic):
        return research_carrier._case_procs_fell_back(
            source, WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=diagnostic)
        )

    for diagnostic in (worker_killed, past_margin):
        assert fell_back(procs, diagnostic)
        # the one-process program (every run after a recorded fallback): the mark is never Carbon's
        assert not fell_back(serial, diagnostic)
    assert not fell_back(procs, b"exit=1\nstderr:\nTraceback ...")
    assert not fell_back(procs, b"stream command timed out")
    # the mark echoed inside an error message (not at a line start) is never a fallback
    assert not fell_back(procs, b"exit=1\nstderr:\nKeyError: 'case_procs: CARBON: x'\n")
    assert not fell_back(procs, b'exit=1\nstderr:\n  File "x", case_procs: w\n')
    assert not research_carrier._case_procs_fell_back(procs, ValueError("other"))
    # the candidate's own stops, as main: an OOM (even with a forged mark) and the wall
    oom = {"status": "OBSERVED", "state": {"oom_killed": True}, "memory": None}
    for diagnostic in (b"exit=1\nstderr:\nTraceback ...", worker_killed):
        assert _stop(diagnostic, oom) == (
            WorkerCode.RUNTIME,
            research_carrier.CANDIDATE_MEMORY_LIMIT,
            {"kind": "memory", "bytes": 16 * 1024**3},
        )
    clean = {"status": "OBSERVED", "state": {"oom_killed": False}, "memory": None}
    assert _stop(b"exit=1\nstderr:\nTraceback ...", clean) is None


def test_the_wall_margin_lies_before_the_hosts_own_program_wall():
    """The program's wall margin is the host's program reserve plus its setup budget plus 30 s, so a fallback's soft
    wall (and the workers' deadlines) always end before the host stops the program (Validator-2 F1/F2).
    """
    from carbon.development_session import research_carrier

    assert (
        case_procs.CASE_PROCS_HOST_SETUP_SECONDS
        == research_carrier._PROGRAM_SETUP_BUDGET_SECONDS
    )
    source = inspect.getsource(research_carrier._run_locked)
    assert (
        "program_timeout = max(1, seconds - "
        f"{case_procs.CASE_PROCS_HOST_RESERVE_SECONDS} - (program_started - started))"
        in source
    )
    assert case_procs.CASE_PROCS_WALL_MARGIN_SECONDS == 45 + 60 + 30


def test_workers_when_the_worst_case_fits_or_one_process_cannot_end_in_the_wall():
    """`case_procs_deadline` (the program carries its source). Validator-2 F1: workers when every worker stopped at its
    deadline, the kill allowance, and then every row made by the parent alone still ends by the wall margin; the
    deadline is capped there. G2 (Lead, 17 Nov): also when the one-process pass cannot end by the wall margin anyway
    but one worker's own need fits: workers until the wall margin. A worker's need is planned at ITS speed (live 116,
    18 Nov): its slice at the one-core per-row time; workers only when 1.5 x that need is within the one-process rows left. Else no workers.
    """
    deadline = case_procs.case_procs_deadline
    end = MOTOR_18_WALL - case_procs.CASE_PROCS_WALL_MARGIN_SECONDS
    kill = case_procs.CASE_PROCS_KILL_SECONDS

    def plan(per_row, rows=1000, now=10.0, startup=5.0, first=2.0, cores=4, one=None):
        return deadline(
            now,
            startup,
            first,
            per_row,
            per_row if one is None else one,
            -(-rows // cores),
            rows,
            2 * cores,
            end,
            case_procs.CASE_PROCS_DEADLINE_SLACK,
            case_procs.CASE_PROCS_FALLBACK_SLACK,
            kill,
            case_procs.CASE_PROCS_MIN_GAIN,
        )

    # 10 s of rows: 1.5 x a worker's need (7 s start + its 2.5 s slice) is past the one-process rows left: no workers
    assert plan(0.01) is None
    # loop-bound rows (one core as fast as the cpuset): 50 s of rows, zone A, deadline = now + 4 x (5 + 2 + 0.05 x 250)
    assert plan(0.05) == pytest.approx(10.0 + 4.0 * (5 + 2 + 0.05 * 250))
    # 200 s of rows on 4 cores: zone A, deadline = now + 4 x (5 + 2 + 0.2 x 250)
    assert plan(0.2) == pytest.approx(10.0 + 4.0 * (5 + 2 + 0.2 * 250))
    # 260 s of rows: zone A, the allowance capped at the latest worst-case deadline, which keeps the kill allowance
    assert plan(0.26) == pytest.approx(end - kill - 1.25 * 0.26 * 1000)
    # 400 s of rows: fits one process but not the worst case, and one process can end in the wall: no workers
    assert 10.0 + 0.4 * 1000 < end and plan(0.4) is None
    # rtsk_90112009-class (0.23 s x 2564 rows ~ 590 s) and MGN-class (~528 s), loop-bound: one process cannot end in
    # the wall, a worker's quarter can: zone B, workers until the wall margin
    assert plan(0.23, rows=2564) == end
    assert plan(528 / 2564, rows=2564) == end
    # zone B needs one worker's own need to fit: a pass far past the wall gets none (its wall stop as before)
    assert plan(4.0, rows=2564) is None
    # live 116, 18 Nov (2611 rows, every worker missed; heavy passes keep 3.5-3.8 of 4 cores busy in one process): a
    # DENSE row, 3.6-4 x slower on one core, never gets workers, in either zone: they gain too little
    assert plan(0.2, rows=2611, one=0.72) is None
    assert plan(0.2, rows=2611, one=0.8) is None
    assert plan(0.23, rows=2564, one=0.92) is None
    assert plan(0.01, one=0.04) is None
    # partly dense (2 x slower on one core) still gains: workers
    assert plan(0.23, rows=2564, one=0.46) == end
    # a row that could not be timed on one core: no workers
    assert plan(0.2, one=float("inf")) is None
    # too few rows to pay a worker's own start: no workers
    assert plan(0.001, rows=64) is None
    for per_row in (0.001, 0.01, 0.05, 0.1, 0.2, 0.23, 0.4, 1.0, 4.0):
        for ratio in (1.0, 2.0, 4.0):
            for rows in (10, 100, 1000, 2564):
                for now in (1.0, 50.0, 300.0):
                    got = plan(per_row, rows=rows, now=now, one=ratio * per_row)
                    if got is None:
                        continue
                    need = 7.0 + ratio * per_row * -(-rows // 4)
                    # workers only when 1.5 x their plan is within the one-process rows left
                    assert 1.5 * need <= per_row * (rows - 8) + 1e-9
                    if now + per_row * (rows - 8) <= end:
                        # the one-process pass can end in the wall: the worst case, with the kill allowance, fits
                        assert got + kill + 1.25 * per_row * rows <= end + 1e-9
                    else:
                        assert got == end
                    assert got > now
    # the sample already made every row: no workers
    assert (
        deadline(0.0, 1.0, 1.0, 0.01, 0.01, 2, 8, 8, end, 4.0, 1.25, kill, 1.5) is None
    )


def _ledger(root):
    from types import SimpleNamespace

    return SimpleNamespace(root=root)


def test_a_recorded_fallback_makes_every_later_run_of_the_pass_one_process(tmp_path):
    """Validator-2 F2: a pass that fell back is recorded durably, keyed on its content (owner, program, control, state,
    inputs) and not on its ledger identity; every later run of that same pass is the one-process program. Any other
    pass, and any program other than a per-case processes one, is unchanged."""
    procs = _procs()
    files = {
        "control.json": b'{"per_case":true}',
        "state.npz": b"state",
        "inputs.npz": b"inputs",
        "recipe.json": b"recipe",
    }
    ledger = _ledger(tmp_path / "ledger")
    assert case_procs.pass_program(ledger, "hk", procs, files) is procs
    case_procs.record_fallback(ledger.root, "hk", procs, files)
    case_procs.record_fallback(ledger.root, "hk", procs, files)  # once is enough
    (record,) = ledger.root.glob("case-procs-fallback-*.json")
    assert json.loads(record.read_bytes()) == {
        "schema": case_procs.FALLBACK_SCHEMA,
        "key": case_procs.fallback_key("hk", procs, files),
    }
    serial = case_procs.pass_program(ledger, "hk", procs, files)
    assert serial == case_procs.serial_program(procs)
    assert hashlib.sha256(serial.encode()).hexdigest() == A9_MOTOR_18_PROGRAM_SHA256
    # only the inputs the program reads key it; another state, inputs, control or owner is another pass
    assert (
        case_procs.pass_program(ledger, "hk", procs, {**files, "recipe.json": b"x"})
        == serial
    )
    for name in ("control.json", "state.npz", "inputs.npz"):
        assert (
            case_procs.pass_program(ledger, "hk", procs, {**files, name: b"x"}) is procs
        )
    assert case_procs.pass_program(ledger, "other", procs, files) is procs
    # a one-process program passes unchanged, and its ledger is not even read
    for other in (serial, worker.PHYSICAL_V2_INFER_PROGRAM):
        assert case_procs.pass_program(None, "hk", other, files) is other
    # the two programs' digests, for the declared-change record and the evidence (F3)
    assert case_procs.program_digests(*MOTOR_18) == {
        "graded_program_sha256": "sha256:" + PROCS_PROGRAM_SHA256,
        "fallback_retry_program_sha256": "sha256:" + A9_MOTOR_18_PROGRAM_SHA256,
    }


class _WorkerFailed(Exception):
    """Test-only: what the carrier raises for a failed program (a WorkerFailure with its private diagnostic)."""


def _failing_runner(ledger, seen, change, fail):
    """`_file_runner`, but a nonzero exit is raised as the carrier raises it: a WorkerFailure whose private diagnostic
    is ``exit=N`` and the program's stderr; ``fail(source)`` says which runs fail on purpose (else as `_file_runner`).
    """
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    plain = _file_runner(ledger, seen, change)

    def runner(current_ledger, *, source, **kwargs):
        if not fail(source):
            return plain(current_ledger, source=source, **kwargs)
        seen.append({"source": source, "stderr": "", "code": None})
        raise WorkerFailure(
            WorkerCode.RUNTIME,
            private_diagnostic=b"exit=3\nstderr:\ncase_procs: CARBON: row 9 of 40 past the wall margin after a fallback\n",
        )

    return runner


def test_the_retry_of_a_pass_that_fell_back_runs_the_one_process_program(
    motor18, tmp_path
):
    """Through the real `_infer_state` (the graded pair's own path): a per-case processes run that fails with a
    fallback line is recorded; the NEXT run of the same pass, under a NEW ledger identity (a re-queued attempt, a
    regrade re-run), is handed the one-process program, and its answers are the one-process answers. Its own failures
    would then be classified exactly as a one-process pass's (no mark is ever read for it).
    """
    pytest.importorskip("jax")
    from test_paired_inference import FixtureLedger

    rows = _rows(motor18, 20)
    serial = _serial(motor18, tmp_path, rows)
    ledger, seen = FixtureLedger(tmp_path / "retry"), []
    try:
        run = _failing_runner(
            ledger, seen, lambda source: source, case_procs.is_procs_program
        )
        with pytest.raises(Exception) as failed:
            _graded(motor18, ledger, run, "attempt-1", rows)
        cause = failed.value.__cause__
        assert case_procs.FALLBACK_MARK in cause.private_diagnostic
        assert len(list(ledger.root.glob("case-procs-fallback-*.json"))) == 1
        assert len(seen) == 1 and seen[0]["source"] == _procs()
        primary, repeat = _graded(motor18, ledger, run, "attempt-2", rows)
    finally:
        ledger.connection.close()
    assert [call["source"] for call in seen[1:]] == [
        case_procs.serial_program(_procs())
    ] * 2
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
def test_a_candidate_too_slow_for_the_wall_in_one_process_gets_no_workers(
    motor18, tmp_path
):
    """The candidate's own one-process time (projected from the sample) is past the wall margin (forced here): no
    worker starts, no fallback line is written, and the pass is the one-process pass, so a real overrun would meet the
    wall and be the candidate's, exactly as before."""
    from test_paired_inference import FixtureLedger

    rows = _rows(motor18, 40)
    serial = _serial(motor18, tmp_path, rows)

    def variant(source):
        wall = f"case_start + {MOTOR_18_WALL} - "
        assert source.count(wall) == 1
        return source.replace(wall, "case_start + 0 - ").replace(
            _WORKER_START,
            _WORKER_START + "        raise SystemExit('no worker may start')\n",
        )

    ledger, seen = FixtureLedger(tmp_path / "slow"), []
    try:
        primary, repeat = _graded(
            motor18, ledger, _file_runner(ledger, seen, variant), "slow", rows
        )
    finally:
        ledger.connection.close()
    assert all("case_procs:" not in call["stderr"] for call in seen)
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()


_ONE_CORE = "            per_row_one = time.perf_counter() - clock\n"


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
def test_a_dense_pass_slow_on_one_core_gets_no_workers(motor18, tmp_path):
    """Live 116, 18 Nov 2026: a dense graph is ~cores x slower per row on ONE core, so workers (one core each) are no
    faster than one process and every worker missed its deadline (all 2611 rows twice). The parent times a row pinned
    to one core; slow there (forced here, with the real gate kept), no worker starts, no fallback line is written, and
    the pass is the one-process pass with the one-process answers."""
    from test_paired_inference import FixtureLedger

    rows = _rows(motor18, 40)
    serial = _serial(motor18, tmp_path, rows)

    def variant(source):
        assert source.count(_ONE_CORE) == 1 and source.count(_WORKER_START) == 1
        return source.replace(
            _ONE_CORE, _ONE_CORE + "            per_row_one = 10**6.0\n"
        ).replace(
            _WORKER_START,
            _WORKER_START + "        raise SystemExit('no worker may start')\n",
        )

    ledger, seen = FixtureLedger(tmp_path / "dense"), []
    try:
        primary, repeat = _graded(
            motor18,
            ledger,
            _file_runner(ledger, seen, variant, gate=True),
            "dense",
            rows,
        )
    finally:
        ledger.connection.close()
    assert len(seen) == 2 and all(call["code"] == 0 for call in seen)
    assert all("case_procs:" not in call["stderr"] for call in seen)
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()


_DEADLINE_CALL = "        deadline = case_procs_deadline(time.monotonic(), "


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
def test_a_near_wall_pass_with_slow_workers_is_graded_in_one_process(motor18, tmp_path):
    """Validator-2 F1 (Runner-B 08:33: workers slower than one process on a dense graph): a pass whose worst case
    (every worker stopped at its deadline, then every row here) does not fit the wall margin starts no worker, even when
    its one-process time fits (forced here: the gate sees the clock 10**6 s later, the workers would be very slow), so
    it is graded, one process, with no fallback line: never FAILED_INFRA."""
    from test_paired_inference import FixtureLedger

    rows = _rows(motor18, 40)
    serial = _serial(motor18, tmp_path, rows)

    def variant(source):
        assert source.count(_DEADLINE_CALL) == 1 and source.count(_WORKER_START) == 1
        return source.replace(
            _DEADLINE_CALL,
            "        deadline = case_procs_deadline(time.monotonic() + 10**6, ",
        ).replace(_WORKER_START, _WORKER_START + "        time.sleep(10**6)\n")

    ledger, seen = FixtureLedger(tmp_path / "near-wall"), []
    try:
        primary, repeat = _graded(
            motor18, ledger, _file_runner(ledger, seen, variant), "near-wall", rows
        )
    finally:
        ledger.connection.close()
    assert all(call["code"] == 0 for call in seen)
    assert all("case_procs:" not in call["stderr"] for call in seen)
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
def test_zone_a_a_worker_slow_on_its_one_core_is_filled_in_by_the_parent_inside_the_wall(
    motor18, tmp_path
):
    """G2 zone A (Validator-2's condition, 17 Nov): the worst case fits, so the deadline lies before the wall margin; a
    worker that is slow on its one core (a dense row; forced here: it hangs after its first row) misses its deadline,
    the parent makes its rows, and the pass ends GRADED (exit 0) inside the wall with the one-process answers.
    """
    from test_paired_inference import FixtureLedger

    rows = _rows(motor18, 40)
    serial = _serial(motor18, tmp_path, rows)

    def variant(source):
        assert source.count(_NO_DEADLINE) == 1 and source.count(_PINNED) == 1
        return source.replace(
            _NO_DEADLINE,
            '        assert deadline is None or deadline < case_wall_end, "not zone A"\n'
            + _NO_DEADLINE,
        ).replace(
            _PINNED, "        if low > 0:\n            time.sleep(10**6)\n" + _PINNED
        )

    ledger, seen = FixtureLedger(tmp_path / "zone-a"), []
    try:
        primary, repeat = _graded(
            motor18, ledger, _file_runner(ledger, seen, variant), "zone-a", rows
        )
    finally:
        ledger.connection.close()
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()
    assert all(call["code"] == 0 for call in seen)
    assert all(
        "past its deadline; its rows in one process" in call["stderr"] for call in seen
    )
    assert "CARBON" not in "".join(call["stderr"] for call in seen)


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
def test_zone_b_failed_workers_are_carbons_once_then_the_one_process_program(
    motor18, tmp_path
):
    """G2 zone B (Validator-2's condition, 17 Nov): the one-process pass cannot end by the wall margin (forced: the
    sampled per-row time), so workers start with the wall margin as their deadline; they fail (forced), the rows left
    cannot end inside the wall, so the parent stops at once with the CARBON mark (exit 3); the host reads it as Carbon's,
    `_infer_state` records the fallback, and the retry of the same pass is the ONE-process program, whose failures are
    never read for the mark (a real overrun there is the candidate's own wall stop, classified as main).
    """
    from test_paired_inference import FixtureLedger

    from carbon.development_session import research_carrier
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    rows = _rows(motor18)
    serial = _serial(motor18, tmp_path, rows)

    def variant(source):
        if not case_procs.is_procs_program(source):
            return source  # the one-process retry runs as it is
        for anchor in (_PER_ROW, _NO_DEADLINE, _WORKER_START):
            assert source.count(anchor) == 1, anchor
        return (
            source.replace(
                _PER_ROW,
                _PER_ROW
                + "        per_row = (case_wall_end - time.monotonic()) / max(1, rows - len(sample) - 1)\n",
            )
            .replace(
                _NO_DEADLINE,
                '        assert deadline == case_wall_end, "not zone B"\n'
                + _NO_DEADLINE,
            )
            .replace(_WORKER_START, _WORKER_START + "        os._exit(3)\n")
        )

    def runner_for(ledger, seen):
        plain = _file_runner(ledger, seen, variant)

        def runner(current_ledger, *, source, **kwargs):
            try:
                return plain(current_ledger, source=source, **kwargs)
            except AssertionError:
                raise WorkerFailure(
                    WorkerCode.RUNTIME,
                    private_diagnostic=(
                        f"exit={seen[-1]['code']}\nstderr:\n{seen[-1]['stderr']}"
                    ).encode(),
                ) from None

        return runner

    ledger, seen = FixtureLedger(tmp_path / "zone-b-fail"), []
    run = runner_for(ledger, seen)  # one runner: its operation names never repeat
    try:
        with pytest.raises(Exception) as failed:
            _graded(motor18, ledger, run, "zone-b-1", rows)
        assert seen[-1]["code"] == 3, seen[-1]["stderr"][-4000:]
        assert "exit 3, no part; its rows in one process" in seen[-1]["stderr"]
        assert "rows left cannot finish inside the inference wall" in seen[-1]["stderr"]
        assert research_carrier._case_procs_fell_back(_procs(), failed.value.__cause__)
        assert len(list(ledger.root.glob("case-procs-fallback-*.json"))) == 1
        first = len(seen)
        primary, repeat = _graded(motor18, ledger, run, "zone-b-2", rows)
    finally:
        ledger.connection.close()
    one_process = case_procs.serial_program(_procs())
    assert [call["source"] for call in seen[first:]] == [one_process] * 2
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()
    # the retry's own failure, whatever its stderr, is never Carbon's: its wall stop is the candidate's, as main
    assert not research_carrier._case_procs_fell_back(
        one_process, failed.value.__cause__
    )


_CASE_BLOCK = "    def case_block(index):\n"
_PER_ROW = "        per_row = (time.perf_counter() - clock) / max(1, len(sample) - 1)\n"
_PINNED = "        pinned = set()\n"


_NO_DEADLINE = "        if deadline is None:\n            slices = []\n"


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
def test_a_pass_one_process_cannot_end_in_the_wall_gets_workers(motor18, tmp_path):
    """G2 (Lead, 17 Nov): the slow loop-bound graphs per-case processes are for (rtsk_90112009-class): the one-process
    pass cannot end by the wall margin (forced here: the sampled per-row time is set so the rows left pass it), but one
    worker's slice fits, so the workers start with the wall margin as their deadline, every worker's answers are used,
    no fallback line is written and the answers are the one-process answers bit for bit.
    """
    from test_paired_inference import FixtureLedger

    rows = _rows(motor18)
    serial = _serial(motor18, tmp_path, rows)

    def variant(source):
        assert source.count(_PER_ROW) == 1 and source.count(_NO_DEADLINE) == 1
        return _workers_used(
            source.replace(
                _PER_ROW,
                _PER_ROW
                + "        per_row = (case_wall_end - time.monotonic()) / max(1, rows - len(sample) - 1)\n",
            ).replace(
                _NO_DEADLINE,
                '        assert deadline == case_wall_end, "not zone B"\n'
                + _NO_DEADLINE,
            )
        )

    ledger, seen = FixtureLedger(tmp_path / "zone-b"), []
    try:
        primary, repeat = _graded(
            motor18, ledger, _file_runner(ledger, seen, variant), "zone-b", rows
        )
    finally:
        ledger.connection.close()
    assert len(seen) == 2 and all(call["code"] == 0 for call in seen)
    assert all("case_procs:" not in call["stderr"] for call in seen)
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()


@posix
@pytest.mark.skipif(_cores() < 2, reason="needs at least two cores in the cpuset")
def test_a_pass_slow_on_unsampled_rows_is_carbons_once_then_one_process(
    motor18, tmp_path
):
    """Validator-2 F2 (a 'cond' graph: per-row time differs by row, the sample under-estimates): the rows after the
    sample are slow (forced here: the workers hang after their first row, this process takes 4 s a row after its
    sample), so the workers pass their deadline, the parent falls back and passes the wall margin (forced near: 150 s
    after the program's start) mid-slice. It stops at once with the mark
    (exit 3), never at the host's wall; the host reads it as Carbon's, `_infer_state` records the fallback, and the
    retry of the same pass runs the ONE-process program, whose outcome (here: it finishes; a real overrun would be
    the candidate's own wall stop, classified as main) is decided exactly as today."""
    from test_paired_inference import FixtureLedger

    from carbon.development_session import research_carrier
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    rows = _rows(motor18)
    serial = _serial(motor18, tmp_path, rows)
    wall = f"case_start + {MOTOR_18_WALL} - "

    def variant(source):
        if not case_procs.is_procs_program(source):
            return source  # the one-process retry runs as it is
        for anchor in (_CASE_BLOCK, _PER_ROW, _PINNED, wall):
            assert source.count(anchor) == 1, anchor
        return (
            source.replace(
                wall,
                f"case_start + {150 + case_procs.CASE_PROCS_WALL_MARGIN_SECONDS} - ",
            )
            .replace(
                _CASE_BLOCK,
                "    slow_rows = []\n"
                + _CASE_BLOCK
                + "        if slow_rows:\n            time.sleep(4)\n",
            )
            .replace(_PER_ROW, _PER_ROW + "        slow_rows.append(1)\n")
            .replace(_PINNED, "        time.sleep(10**6)\n" + _PINNED)
        )

    def runner_for(ledger, seen):
        plain = _file_runner(ledger, seen, variant)

        def runner(current_ledger, *, source, **kwargs):
            try:
                return plain(current_ledger, source=source, **kwargs)
            except AssertionError:
                # as the carrier raises a nonzero exit: a WorkerFailure with the exit and the program's stderr
                raise WorkerFailure(
                    WorkerCode.RUNTIME,
                    private_diagnostic=(
                        f"exit={seen[-1]['code']}\nstderr:\n{seen[-1]['stderr']}"
                    ).encode(),
                ) from None

        return runner

    ledger, seen = FixtureLedger(tmp_path / "cond"), []
    run = runner_for(ledger, seen)  # one runner: its operation names never repeat
    try:
        with pytest.raises(Exception) as failed:
            _graded(motor18, ledger, run, "cond-1", rows)
        assert seen[-1]["code"] == 3, seen[-1]["stderr"][-4000:]
        assert "past its deadline; its rows in one process" in seen[-1]["stderr"]
        assert "past the wall margin after a fallback" in seen[-1]["stderr"]
        assert research_carrier._case_procs_fell_back(_procs(), failed.value.__cause__)
        assert len(list(ledger.root.glob("case-procs-fallback-*.json"))) == 1
        first = len(seen)
        primary, repeat = _graded(motor18, ledger, run, "cond-2", rows)
    finally:
        ledger.connection.close()
    retry = seen[first:]
    assert [call["source"] for call in retry] == [
        case_procs.serial_program(_procs())
    ] * 2
    assert all(
        call["code"] == 0 and "case_procs:" not in call["stderr"] for call in retry
    )
    # the one-process program's failure would never be read for the mark: classified as main
    assert not research_carrier._case_procs_fell_back(
        retry[0]["source"],
        WorkerFailure(
            WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
        ),
    )
    assert primary.tobytes() == repeat.tobytes() == serial.tobytes()


#: A failing run's diagnostic whose candidate-chosen text (a graph node or parameter name echoed by an exception, or
#: anything the candidate can make reach stderr) carries the fallback mark.
_FORGED = (
    b"exit=1\nstderr:\nValueError: graph node "
    b"'case_procs: CARBON: worker 0 exit 3; its rows in one process' refused\n"
)

#: The same, but the candidate-chosen text breaks the line so the mark starts one (the case `fell_back` still counts).
_FORGED_AT_LINE_START = (
    b"exit=1\nstderr:\nValueError: graph node 'x\n"
    b"case_procs: CARBON: worker 0 exit 3; its rows in one process' refused\n"
)


def _infer_args(tmp_path):
    """`_infer_state`'s arguments for Motor 1.8 up to the runner (no state is ever loaded: the runner fails first)."""
    from types import SimpleNamespace

    from carbon.challenge_kit import physical_material
    from carbon.development_session import graph_adapters
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    material = physical_material.bundle_material(*MOTOR_18)
    kit = material["construction_kit"]
    inputs = np.ascontiguousarray(material["practice_inputs"][:4])
    state = b"synthetic state bytes"
    return {
        "ledger": SimpleNamespace(root=tmp_path / "ledger"),
        "owner": "hk",
        "identity": "forged-mark",
        "inference_image": WorkerImageIdentity(*(("sha256:" + "a" * 64,) * 8)),
        "recipe": ConstructionRecipe.from_dict(
            graph_adapters.graph_recipe(*MOTOR_18, "sha256:" + "0" * 64)
        ),
        "binding": {
            "challenge_id": MOTOR_18[0],
            "challenge_version": MOTOR_18[1],
            **{
                name: kit[name]
                for name in (
                    "train_digest",
                    "interface_digest",
                    "construction_limits_digest",
                )
            },
        },
        "state": state,
        "state_digest": "sha256:" + hashlib.sha256(state).hexdigest(),
        "inputs": inputs,
        "expected_output_shape": (len(inputs), 1),
        "expected_output_dtype": "float64",
        "allowlist_bytes": material["allowlist_bytes"],
        "input_name": "inputs/features",
        "provenance": "DIRECT_GRAPH_PUBLIC_INFERENCE",
        "seconds": MOTOR_18_WALL,
    }


def _failing(seen, diagnostic, raised=None):
    """A runner whose run fails as the carrier's does (a WorkerFailure with ``diagnostic``); it notes each source."""
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    def runner(_ledger, *, source, **_kwargs):
        seen.append(source)
        failure = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=diagnostic)
        if raised is not None:
            raised.append(failure)
        raise failure

    return runner


def test_a_candidate_chosen_mark_never_makes_a_one_process_run_fall_back(tmp_path):
    """Review of 2ebb34d6, gap 3: a ONE-process program (the serial retry, any other graph program) that fails with the
    mark in candidate-chosen text is never read as fallen back and writes no record, so its stop is classified as
    main's. A per-case processes program with the same forged text is Carbon's at most ONCE: it is recorded, and every
    later run of the pass is the one-process program, where the same text no longer counts.
    """
    from carbon.development_session import research_carrier
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    infer = bundle_construction_worker._infer_state
    args = _infer_args(tmp_path)
    procs, serial = _procs(), case_procs.serial_program(_procs())
    forged = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=_FORGED)
    seen = []

    def records():
        root = args["ledger"].root
        return list(root.glob("case-procs-fallback-*.json")) if root.exists() else []

    for program in (serial, worker.PHYSICAL_V2_INFER_PROGRAM):
        with pytest.raises(WorkerFailure):
            infer(**args, program=program, runner=_failing(seen, _FORGED))
        assert seen[-1] == program and not records()
        assert not research_carrier._case_procs_fell_back(program, forged)
    # the per-case processes program: a mark inside a line never counts (no record) ...
    assert not research_carrier._case_procs_fell_back(procs, forged)
    with pytest.raises(WorkerFailure):
        infer(**args, program=procs, runner=_failing(seen, _FORGED))
    assert seen[-1] == procs and not records()
    # ... and one the candidate's text puts at a line start is Carbon's once, then one process for good
    forged = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=_FORGED_AT_LINE_START)
    assert research_carrier._case_procs_fell_back(procs, forged)
    with pytest.raises(WorkerFailure):
        infer(**args, program=procs, runner=_failing(seen, _FORGED_AT_LINE_START))
    assert seen[-1] == procs and len(records()) == 1
    for _ in range(2):
        with pytest.raises(WorkerFailure):
            infer(**args, program=procs, runner=_failing(seen, _FORGED_AT_LINE_START))
        assert seen[-1] == serial and len(records()) == 1
        assert not research_carrier._case_procs_fell_back(seen[-1], forged)


def test_a_record_that_cannot_be_written_never_masks_the_runs_own_failure(
    tmp_path, monkeypatch, capsys
):
    """Review of 2ebb34d6, gap 1: when the fallback record cannot be written (disk full), the run's ORIGINAL failure
    leaves `_infer_state` unchanged, with a line saying the record was not written."""
    from carbon.reconstruction.worker.model import WorkerFailure

    def full(*_args, **_kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(case_procs, "record_fallback", full)
    seen, raised = [], []
    with pytest.raises(WorkerFailure) as failed:
        bundle_construction_worker._infer_state(
            **_infer_args(tmp_path),
            program=_procs(),
            runner=_failing(
                seen,
                b"exit=1\nstderr:\ncase_procs: worker 1 exit -9; its rows in one process\n",
                raised,
            ),
        )
    assert failed.value is raised[-1]
    assert "fallback record not written (OSError)" in capsys.readouterr().err


def test_a_fallback_never_starts_a_row_it_cannot_end_by_the_wall_margin():
    """Review of 2ebb34d6, gap 2: after a fallback the parent looks ahead: a row is started only when now plus
    FALLBACK_SLACK x the longest row it has made (the sampled per-row time to start with) ends by the wall margin;
    else it exits 3 with the mark, before the host's wall. The 135 s margin stays."""
    procs = _procs()
    assert (
        "    row_time = per_row if fell_back else 0.0\n" in procs
        and "            if fell_back and time.monotonic() + 1.25 * row_time > case_wall_end:\n"
        in procs
        and "                row_time = max(row_time, time.perf_counter() - row_clock)\n"
        in procs
    )
    assert case_procs.CASE_PROCS_WALL_MARGIN_SECONDS == 135
