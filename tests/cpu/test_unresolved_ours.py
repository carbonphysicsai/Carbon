"""Live 116, 18 Nov 2026 (V2: all ours): 25 tasks ended UNRESOLVED / unresolved_execution. Their typed Carbon-side
causes are FAILED_INFRA now (re-run, uncharged); a lane or slot wait no longer spends the construction's deadline; any
other UNRESOLVED keeps its class (a SUCCEEDED child whose evidence fails verification never earns a free re-run).
"""

from __future__ import annotations

import time

from carbon.development_session import research_tasks
from carbon.development_session.research_carrier import ONE_NUMERICAL_WORKER
from carbon.reconstruction import grade_lanes
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure


def test_a_stale_numerical_op_refusal_is_carbons():
    assert research_tasks._failure_is_carbons(
        ValueError(ONE_NUMERICAL_WORKER), [None, None]
    )


def test_an_export_stream_timeout_after_every_child_succeeded_is_carbons():
    timeout = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
    )
    assert research_tasks._failure_is_carbons(timeout, ["SUCCEEDED", "SUCCEEDED"])
    # a child that did not succeed: not this class
    assert not research_tasks._failure_is_carbons(timeout, ["SUCCEEDED", None])


def test_other_failures_keep_their_class():
    assert not research_tasks._failure_is_carbons(
        ValueError("direct_graph_state_changed"), ["SUCCEEDED", None]
    )
    assert not research_tasks._failure_is_carbons(
        WorkerFailure(WorkerCode.RUNTIME), ["SUCCEEDED", "SUCCEEDED"]
    )
    assert not research_tasks._failure_is_carbons(
        RuntimeError("x"), ["SUCCEEDED", "SUCCEEDED"]
    )


def test_a_lane_wait_is_counted_as_carbons_queue_per_thread():
    before = grade_lanes.waited_seconds()
    with grade_lanes.timed_wait():
        time.sleep(0.05)
    assert grade_lanes.waited_seconds() - before >= 0.05

    class Releaser:
        def retake(self):
            time.sleep(0.05)

    before = grade_lanes.waited_seconds()
    grade_lanes._retake(Releaser())
    assert grade_lanes.waited_seconds() - before >= 0.05
