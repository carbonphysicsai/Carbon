"""A practice whose own graph hit the memory or time limit is told so (Validator
V8_RULINGS section 9).

Graphite's real worker showed a FAILED_MINER operation (reservation kept) still
read to the miner as "practice_could_not_run ... an infrastructure problem ...
nothing counts against you". The task now completes with the typed candidate
outcome and the door says which limit was reached, with its value, and that the
attempt's reservation is used. An allocation larger than memory.max in the fixed
graph program is the candidate's memory stop even though no kernel OOM happens.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from test_launchpad_smoke_practice import HEAVY, FixturePractice, ledger_at, prepared

from carbon.development_session import research_campaign as rc
from carbon.development_session import research_carrier as carrier
from carbon.development_session import research_tasks
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure
from scripts.dev.miner_launchpad import supervisor

GIB = 1024**3


def _failure(code, observation, limit=None):
    result = {
        "schema": carrier.MINER_FAILURE_SCHEMA,
        "failure_code": code.value,
        "observation": observation,
    }
    if limit is not None:
        result["limit"] = limit
    return carrier.MinerProgramFailure(result)


MEMORY = _failure(
    WorkerCode.RUNTIME,
    carrier.CANDIDATE_MEMORY_LIMIT,
    {"kind": "memory", "bytes": 16 * GIB},
)
WALL = _failure(
    WorkerCode.DEADLINE, carrier.CANDIDATE_WALL_LIMIT, {"kind": "wall", "seconds": 900}
)


# --- the words -----------------------------------------------------------------


def test_the_memory_message_names_the_limit_and_says_the_reservation_is_used():
    text = research_tasks.miner_failure_correction(MEMORY)
    assert "16 GiB" in text
    assert "not an infrastructure problem" in text
    assert "reservation is used" in text and "nothing was scored" in text


def test_the_wall_message_names_the_seconds():
    text = research_tasks.miner_failure_correction(WALL)
    assert "900 s" in text and "reservation is used" in text


def test_a_failure_with_no_known_limit_still_is_the_recipes_not_infrastructure():
    text = research_tasks.miner_failure_correction(
        _failure(WorkerCode.RUNTIME, "NONZERO_EXIT")
    )
    assert "not an infrastructure problem" in text
    assert "nothing counts against you" not in text


def test_the_typed_task_result_carries_the_limit_and_no_scientific_claim():
    result = research_tasks.miner_failure_result(MEMORY)
    assert result["outcome"] == "MINER_PROGRAM_FAILED"
    assert result["limit"] == {"kind": "memory", "bytes": 16 * GIB}
    assert result["reservation_used"] is True and result["nothing_scored"] is True
    assert result["authority_granted"] is False


# --- the task completes with it, never FAILED_INFRA ----------------------------


def test_the_executor_completes_the_task_with_the_typed_outcome():
    completed = []
    executor = SimpleNamespace(
        _complete=lambda identity, result, evidence: completed.append(
            (identity, result, evidence)
        )
        or "outcome"
    )
    attempt = SimpleNamespace(task_id=SimpleNamespace(value="task-1"))
    outcome = research_tasks.PublicResearchExecutor.refusal_outcome(
        executor, attempt, MEMORY
    )
    assert outcome == "outcome"
    assert completed[0][0] == "task-1"
    assert completed[0][1]["outcome"] == "MINER_PROGRAM_FAILED"


# --- the door ------------------------------------------------------------------


def _door(tmp_path, public_result):
    ledger, manifest = ledger_at(tmp_path)
    practice = FixturePractice(ledger)
    practice.seconds = 10**6

    async def call(name, args, identity):
        return {
            "terminal_task": {"state": "SUCCEEDED"},
            "public_result": public_result,
        }

    value = prepared(ledger, manifest, practice)
    value.sdk = SimpleNamespace(call=call)
    return asyncio.run(
        rc.practice_recipe(
            value, strategy=HEAVY, hypothesis="h", expected_effect="e", identity="oom"
        )
    )


def test_the_door_refuses_with_the_miner_fault_message(tmp_path):
    result = research_tasks.miner_failure_result(MEMORY)
    with pytest.raises(rc.OperationRefused) as refused:
        _door(tmp_path, {"result": result})
    assert refused.value.code == "practice_candidate_failed"
    step = refused.value.next_step
    assert "16 GiB" in step and "reservation is used" in step
    assert "infrastructure problem: " not in step.replace("not an infrastructure", "")


def test_an_ordinary_result_is_returned_as_before(tmp_path):
    answer = _door(tmp_path, {"result": {"outcome": "SUCCEEDED"}})
    assert answer["terminal_task"]["state"] == "SUCCEEDED"


def test_the_catalog_has_a_fixed_fallback_that_is_not_the_infrastructure_text():
    step = supervisor.next_action("practice_candidate_failed")
    assert "reservation is used" in step and "recipe's own limit" in step
    assert "nothing counts against you" not in step


# --- the classification: a refused allocation larger than memory.max ----------

LIMIT = 16 * GIB
XLA = (
    b"exit=1\nstderr:\nTraceback (most recent call last):\n"
    b'  File "program.py", line 12, in <module>\n'
    b"jaxlib.xla_extension.XlaRuntimeError: RESOURCE_EXHAUSTED: Out of memory "
    b"allocating 34359738368 bytes.\n"
)


@pytest.mark.parametrize(
    "text,expected",
    [
        (XLA, 34359738368),
        (b"RESOURCE_EXHAUSTED: Failed to allocate request for 32.00GiB (34359738368B)", 34359738368),
        (b"numpy._ArrayMemoryError: Unable to allocate 32.0 GiB for an array", 32 * GIB),
        (b"MemoryError", None),
        (b"RESOURCE_EXHAUSTED: Out of memory allocating 1048576 bytes.", 1048576),
        (b"", None),
    ],
)
def test_the_requested_allocation_is_read_from_the_workers_own_error(text, expected):
    assert carrier.requested_allocation_bytes(text) == expected


def _stop(diagnostic, *, observation=None, accelerated=False, limit=LIMIT):
    error = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=diagnostic)
    return carrier._candidate_resource_stop(
        SimpleNamespace(
            json=lambda *a, **k: (_ for _ in ()).throw(WorkerFailure(WorkerCode.RUNTIME))
        ),
        error,
        container_name="carbon-d4-" + "1" * 24,
        launch_digest="sha256:" + "1" * 64,
        image_id="sha256:" + "2" * 64,
        program_started=0.0,
        program_timeout=900,
        setup_seconds=1,
        memory_limit_bytes=limit,
        deadline=1e18,
        observation=observation
        or {"status": "UNKNOWN", "state": None, "memory": None},
        accelerated=accelerated,
    )


def test_a_request_above_the_limit_is_the_candidates_memory_stop_with_no_kernel_oom():
    stop = _stop(XLA)
    assert stop == (
        WorkerCode.RUNTIME,
        carrier.CANDIDATE_MEMORY_LIMIT,
        {"kind": "memory", "bytes": LIMIT},
    )


def test_an_allocation_failure_below_the_limit_stays_infrastructure():
    small = XLA.replace(b"34359738368", b"1073741824")
    assert _stop(small) is None


def test_a_gpu_runs_device_memory_is_not_judged_by_the_host_limit():
    assert _stop(XLA, accelerated=True) is None


def test_the_unrelated_error_is_not_classified():
    assert _stop(b"exit=1\nstderr:\nValueError: shapes differ\n") is None
