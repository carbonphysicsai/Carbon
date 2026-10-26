"""A candidate's own OOM or wall stop is a typed candidate failure, never FAILED_INFRA.

A graph or recipe that exhausts the worker's memory or wall must not be a free
refund or retry (a grading-queue DoS), while a daemon or host fault stays an
infrastructure failure.
"""

import time
from types import SimpleNamespace

import pytest
from test_direct_v3_durable_tasks import _fixture
from test_fixed_practice_failure_diagnostics import harness as _runner_harness
from test_fixed_program_failure_evidence import _overlay_arguments

from carbon import research
from carbon.development_session import bundle_construction_worker
from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

harness = _runner_harness  # pytest discovers the existing fixture by this name

LAUNCH = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
LIMIT = 16 * 1024**3
GRAPH_BUILD = "DIRECT_GRAPH_PUBLIC_RECONSTRUCTION"
GRAPH_INFERENCE = "DIRECT_GRAPH_PUBLIC_INFERENCE"


def _observation(*, oom_killed=False, oom_kill=0, peak=1024, running=True):
    return {
        "status": "OBSERVED",
        "state": {"running": running, "oom_killed": oom_killed, "exit_code": 137},
        "memory": (
            {
                "current_bytes": peak,
                "peak_bytes": peak,
                "events": {"oom": oom_kill, "oom_kill": oom_kill},
            }
            if running
            else None
        ),
    }


def _observe(monkeypatch, observation):
    monkeypatch.setattr(
        carrier, "_fixed_program_container_observation", lambda *a, **k: observation
    )
    monkeypatch.setattr(
        carrier,
        "_worker_profile",
        lambda *a: SimpleNamespace(effective_memory_bytes=LIMIT),
    )


def _state(harness):
    return harness.ledger.operation_state("public-task", owner="alice")


def _run_failing(harness, error, **overrides):
    harness.fail_stage, harness.error = "PROGRAM", error
    return harness.run(**overrides)


def test_every_candidate_build_and_inference_provenance_is_covered():
    assert carrier._CANDIDATE_RESOURCE_PROVENANCES == {
        carrier.LIBRARY_BUILD_PROVENANCE,
        carrier.LIBRARY_OVERLAY_BUILD_PROVENANCE,
        "DIRECT_BUNDLE_PUBLIC_INFERENCE",
        GRAPH_BUILD,
        GRAPH_INFERENCE,
    }
    # The dependency install is Carbon's own work, not the candidate's.
    assert (
        carrier.LIBRARY_PREP_PROVENANCE not in carrier._CANDIDATE_RESOURCE_PROVENANCES
    )


# The bundle build and inference programs need a verified library image to
# reach this stage; the graph and overlay programs run the same carrier path.
@pytest.mark.parametrize(
    "provenance",
    [GRAPH_BUILD, GRAPH_INFERENCE, carrier.LIBRARY_OVERLAY_BUILD_PROVENANCE],
)
@pytest.mark.parametrize(
    "observation",
    [
        # The engine reports the container's init OOM-killed.
        _observation(oom_killed=True, running=False),
        # GeoFNO-style: the kernel kills the exec'd program inside a container
        # that keeps running; only the cgroup's own counter shows it.
        _observation(oom_kill=1, peak=LIMIT),
    ],
)
def test_oom_at_the_worker_limit_is_a_typed_candidate_failure(
    harness, monkeypatch, provenance, observation
):
    _observe(monkeypatch, observation)
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=137\n")
    with pytest.raises(carrier.MinerProgramFailure) as caught:
        _run_failing(
            harness,
            original,
            provenance=provenance,
            **_overlay_arguments(harness, provenance),
        )
    assert caught.value.code is WorkerCode.RUNTIME
    assert caught.value.result["observation"] == carrier.CANDIDATE_MEMORY_LIMIT
    assert caught.value.result["state"] == "FAILED_MINER"
    assert caught.value.result["retry_dispatched"] is False
    assert _state(harness) == "FAILED_MINER"
    # Cleanup of the exact container ran before the failure was settled.
    assert "CLEANUP" in harness.events
    assert harness.events.index("CLEANUP") > harness.events.index("PROGRAM")


def test_the_workers_own_memory_error_at_its_limit_is_a_candidate_failure(
    harness, monkeypatch
):
    _observe(monkeypatch, _observation(peak=LIMIT))
    error = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"exit=1\nstderr:\nMemoryError\n"
    )
    with pytest.raises(carrier.MinerProgramFailure) as caught:
        _run_failing(harness, error, provenance=GRAPH_BUILD)
    assert caught.value.result["observation"] == carrier.CANDIDATE_MEMORY_LIMIT
    assert _state(harness) == "FAILED_MINER"


@pytest.mark.parametrize("provenance", [GRAPH_BUILD, GRAPH_INFERENCE])
def test_the_wall_stop_is_a_typed_candidate_failure(harness, monkeypatch, provenance):
    _observe(monkeypatch, _observation())
    error = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
    )
    # 46 s leaves the program stage a 1 s allowance, which the instant fake
    # stream has used up by the time it reports the timeout.
    with pytest.raises(carrier.MinerProgramFailure) as caught:
        _run_failing(harness, error, provenance=provenance, seconds=46)
    assert caught.value.code is WorkerCode.DEADLINE
    assert caught.value.result["observation"] == carrier.CANDIDATE_WALL_LIMIT
    assert _state(harness) == "FAILED_MINER"
    assert "CLEANUP" in harness.events


def test_a_replay_of_the_settled_failure_stays_typed(harness, monkeypatch):
    _observe(monkeypatch, _observation(oom_kill=2, peak=LIMIT))
    error = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=137\n")
    with pytest.raises(carrier.MinerProgramFailure):
        _run_failing(harness, error, provenance=GRAPH_BUILD)
    harness.fail_stage = None
    with pytest.raises(carrier.MinerProgramFailure) as again:
        harness.run(provenance=GRAPH_BUILD)
    assert again.value.result["observation"] == carrier.CANDIDATE_MEMORY_LIMIT


def test_other_provenances_keep_the_infrastructure_failure(harness, monkeypatch):
    """Carbon's own programs are never blamed on a candidate."""
    _observe(monkeypatch, _observation(oom_killed=True, running=False))
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=137\n")
    with pytest.raises(WorkerFailure) as caught:
        _run_failing(harness, original, provenance="BATTERY_PUBLIC_PRACTICE")
    assert caught.value is original
    assert _state(harness) == "RESERVED"


@pytest.mark.parametrize(
    "observation",
    [
        # A daemon fault: the program stage exited nonzero with nothing observed.
        {"status": "UNKNOWN", "state": None, "memory": None},
        _observation(),
        # A memory exception far below the limit is not the limit being reached.
        _observation(peak=1024),
    ],
)
def test_unobserved_stops_stay_infrastructure(harness, monkeypatch, observation):
    _observe(monkeypatch, observation)
    original = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"exit=1\nstderr:\nMemoryError\n"
    )
    with pytest.raises(WorkerFailure) as caught:
        _run_failing(harness, original, provenance=GRAPH_BUILD)
    assert caught.value is original
    assert _state(harness) == "RESERVED"


def test_a_requested_cancel_is_never_the_candidates_failure(harness, monkeypatch):
    _observe(monkeypatch, _observation(oom_killed=True, running=False))
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=137\n")
    exists = SimpleNamespace(exists=lambda: True)
    monkeypatch.setattr(carrier, "_cancel_path", lambda *a: exists)
    with pytest.raises(WorkerFailure):
        _run_failing(harness, original, provenance=GRAPH_BUILD)
    assert _state(harness) == "RESERVED"


def test_a_wall_after_a_slow_start_is_the_hosts_not_the_candidates(monkeypatch):
    _observe(monkeypatch, _observation())
    error = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
    )

    def stop(setup_seconds):
        return carrier._candidate_resource_stop(
            SimpleNamespace(),
            error,
            container_name="carbon-d4-" + LAUNCH[7:31],
            launch_digest=LAUNCH,
            image_id=IMAGE,
            program_started=time.monotonic() - 100,
            program_timeout=10,
            setup_seconds=setup_seconds,
            memory_limit_bytes=LIMIT,
            deadline=time.monotonic() + 1,
        )

    assert stop(5) == (WorkerCode.DEADLINE, carrier.CANDIDATE_WALL_LIMIT)
    assert stop(carrier._PROGRAM_SETUP_BUDGET_SECONDS + 1) is None


@pytest.mark.parametrize(
    ("failure_code", "observation"),
    [
        (WorkerCode.RUNTIME, carrier.CANDIDATE_MEMORY_LIMIT),
        (WorkerCode.DEADLINE, carrier.CANDIDATE_WALL_LIMIT),
    ],
)
def test_the_task_refuses_a_candidate_resource_failure_not_infrastructure(
    tmp_path, monkeypatch, failure_code, observation
):
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)
        failure = carrier.MinerProgramFailure(
            {
                "schema": carrier.MINER_FAILURE_SCHEMA,
                "failure_code": failure_code.value,
                "observation": observation,
            }
        )

        def failing(*args, **kwargs):
            raise failure

        monkeypatch.setattr(
            bundle_construction_worker, "reconstruct_and_infer_public", failing
        )
        view = tasks.run_queued_task(started.task.task_id)
        assert view.state is research.DirectTaskStateV3.REFUSED
        assert view.terminal_receipt.refusal_code == "candidate_program_failed"
        assert view.terminal_receipt.infrastructure_failure_class is None
    finally:
        tasks.close()
