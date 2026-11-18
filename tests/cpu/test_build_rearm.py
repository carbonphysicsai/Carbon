"""17 Nov (Lead; owner: "miners re-run automatically"): the CPU worker-wall build failures re-run, automatically and on
the operator's receipt.

Live ops / case-procs (codex-queue/reports/A100_INFER_STREAM_TIMEOUT_20261117): an A100-built graph's build-pipeline
inference ran 603 s of 648 on GPUYard's CPU worker (one process, ~2 cores busy) and stopped at the wall. Contended, the
task ended FAILED_INFRA (re-run once by the door); uncontended, the inference child settled FAILED_MINER on the deadline
and the task ended REFUSED (rtsk_af647b3b, itself the door's requeue). Now:
- the door re-runs a build refused ONLY for that wall like a FAILED_INFRA one (once, at its place, capped);
- the operator's `infra_requeue rebuild` (Validator-2's receipt) asks the live door to start the next generation of a
  listed build even when it was itself the door's requeue: a fresh task id and fresh ops, no settled op is cleared.
"""

from __future__ import annotations

import json

import pytest
from test_build_requeue import (  # noqa: F401 (fixtures)
    CONTRACT,
    HOTKEYS,
    A,
    B,
    N,
    _door,
    _plain_requests,
    _Provider,
    _queue,
    _requeue,
)

from carbon.challenge_validator import lean_recipe
from carbon.research import DirectTaskStateV3, ResearchTaskId


@pytest.fixture
def ledger(tmp_path):
    from carbon.challenge_validator.ledger import AttemptLedger

    clock = iter(range(1000, 100_000, 10))
    return AttemptLedger(tmp_path / "attempts.sqlite3", clock=lambda: next(clock))


E = "rtsk_" + "e" * 64
F = "rtsk_" + "f" * 64  # what `_Provider._task_id` gives every later generation


def _inference_settled(provider, tmp_path, task, state, failure_code):
    """The task's build-pipeline inference child, settled in its owner's ledger as the carrier settles it."""
    from carbon.development_session.bundle_construction_worker import (
        direct_child_identity,
    )
    from carbon.development_session.research_ledger import CampaignLedger

    if not hasattr(provider, "ledger"):
        provider.ledger = CampaignLedger(tmp_path / "owner-ledger")
    with provider.ledger.db() as db:
        db.execute(
            "INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?)",
            (
                direct_child_identity(task, "inference"),
                HOTKEYS[0],
                "research",
                "d",
                state,
                "{}",
                "{}",
                json.dumps({"failure_code": failure_code, "observation": "x"}),
                1.0,
            ),
        )


DEADLINE = "reconstruction.worker.deadline.exceeded"
RUNTIME = "reconstruction.worker.runtime.failed"


# --- the ledger: the operator lifts only "a requeue is never requeued" -----------------------------------------------


def test_the_operator_lifts_only_the_requeue_of_a_requeue_refusal(ledger):
    _queue(ledger)
    assert _requeue(ledger) == "requeued"  # A -> N, the door's own requeue
    assert _requeue(ledger, from_task=N, new_task=E) == "from_task_is_a_requeue"
    assert _requeue(ledger, from_task=N, new_task=E, operator=True) == "requeued"
    # every other check stands: N's place is given once, a known task is never requeued
    assert _requeue(ledger, from_task=N, new_task=F, operator=True) == "from_task_used"
    assert _requeue(ledger, from_task=A, new_task=B, operator=True) == "from_task_used"


# --- the door: a build refused only for the CPU worker wall re-runs ---------------------------------------------------


def test_a_build_refused_for_the_cpu_wall_is_rerun_once_like_a_failed_infra_one(
    ledger, tmp_path
):
    _queue(ledger)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.REFUSED})
    _inference_settled(provider, tmp_path, A, "FAILED_MINER", DEADLINE)
    assert lean_recipe._cpu_wall_refusal(provider, HOTKEYS[0], A) is True
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) == N
    assert provider.started == [(("req", HOTKEYS[0], 1), False)]


@pytest.mark.parametrize(
    "state, code",
    [
        ("FAILED_MINER", RUNTIME),  # the candidate's own crash / refused output: never
        ("SUCCEEDED", DEADLINE),
        ("FAILED_INFRA", DEADLINE),
    ],
)
def test_any_other_refusal_is_never_rerun(ledger, tmp_path, state, code):
    _queue(ledger)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.REFUSED})
    _inference_settled(provider, tmp_path, A, state, code)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert provider.started == []


def test_a_requeue_refused_for_the_cpu_wall_is_rerun_again_within_the_caps(
    ledger, tmp_path
):
    """rtsk_af647b3b: the door's own requeue, refused for the wall. Owner D16 (18 Nov 2026, V2 Y): a re-run of a re-run
    is allowed within the caps (3 per failure code, 5 per chain), so it runs its next generation automatically.
    """
    _queue(ledger)
    assert _requeue(ledger) == "requeued"
    door, provider = _door(ledger), _Provider({N: DirectTaskStateV3.REFUSED})
    provider._requests[N] = ("req", HOTKEYS[0], 1)
    _inference_settled(provider, tmp_path, N, "FAILED_MINER", DEADLINE)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(N), provider) == (
        "rtsk_" + "f" * 64
    )
    assert provider.started == [(("req", HOTKEYS[0], 2), False)]


# --- the operator's re-arm, applied by the live door --------------------------------------------------------------------


def _requests(ledger, *lines):
    directory = ledger.path.parent / "auto-grade" / "requeued"
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / lean_recipe.REBUILD_REQUESTS, "a") as log:
        log.writelines(json.dumps(line) + "\n" for line in lines)
    return directory


def test_the_door_applies_an_operator_rebuild_once_even_of_its_own_requeue(
    ledger, tmp_path
):
    _queue(ledger)
    assert _requeue(ledger) == "requeued"  # A -> N
    door, provider = _door(ledger), _Provider({N: DirectTaskStateV3.REFUSED})
    provider._requests[N] = ("req", HOTKEYS[0], 1)
    _inference_settled(provider, tmp_path, N, "FAILED_MINER", DEADLINE)
    door._active_owner = lambda sid: HOTKEYS[0]
    door._provider = lambda owner: provider
    directory = _requests(ledger, {"task": N, "ruling": "V2-REBUILD-1"})
    door._apply_rebuild_requests()
    assert provider.started == [(("req", HOTKEYS[0], 2), False)]  # N's next generation
    applied = [
        json.loads(line)
        for line in (directory / lean_recipe.REBUILD_APPLIED).read_text().splitlines()
    ]
    assert [(a["task"], a["new_task"], a["code"], a["ruling"]) for a in applied] == [
        (N, F, None, "V2-REBUILD-1")
    ]
    door._apply_rebuild_requests()  # applied once: nothing more
    assert len(provider.started) == 1


def test_a_rebuild_request_the_door_cannot_apply_is_logged_and_never_retried(
    ledger, tmp_path
):
    _queue(ledger)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.SUCCEEDED})
    door._active_owner = lambda sid: HOTKEYS[0]
    door._provider = lambda owner: provider
    directory = _requests(ledger, {"task": A, "ruling": "V2-REBUILD-2"})
    door._apply_rebuild_requests()
    door._apply_rebuild_requests()
    applied = (directory / lean_recipe.REBUILD_APPLIED).read_text().splitlines()
    assert [json.loads(line)["code"] for line in applied] == ["not_rebuilt"]
    assert provider.started == []


def test_the_advance_round_never_fails_on_a_broken_request_log(ledger):
    door = _door(ledger)
    directory = ledger.path.parent / "auto-grade" / "requeued"
    directory.mkdir(parents=True)
    (directory / lean_recipe.REBUILD_REQUESTS).write_text("not json\n{]\n")
    door._apply_rebuild_requests()  # nothing raised


# --- the operator tool --------------------------------------------------------------------------------------------------


def test_the_rebuild_command_requests_once_on_a_ruling(tmp_path):
    from test_infra_requeue import _arrived, _root, _row

    from carbon.challenge_validator import infra_requeue

    root, attempts = _root(tmp_path)
    task, other, graded, counted = ("rtsk_" + c * 64 for c in "1234")
    for t in (task, graded, counted):
        _arrived(attempts, t)
    markers = root / "auto-grade" / "markers"
    markers.mkdir(parents=True)
    from carbon.challenge_validator.auto_grade import SCHEMA

    (markers / (graded + ".json")).write_text(
        json.dumps({"schema": SCHEMA, "state": "GRADED"})
    )
    _row(attempts, counted, "COUNTED", "GRADED")
    assert infra_requeue.rebuild(root, [task], ruling="")["refused"] == {
        "*": "ruling_id_required"
    }
    dry = infra_requeue.rebuild(
        root, [task, other, graded, counted, "x"], ruling="V2-REBUILD-3"
    )
    assert dry["requested"] == [task]
    assert dry["refused"] == {
        other: "not_submitted_at_this_door",
        graded: "graded",
        counted: "exam_row_counted_or_reserved",
        "x": "not_a_task_id",
    }
    requests = root / "auto-grade" / "requeued" / lean_recipe.REBUILD_REQUESTS
    assert not requests.exists()  # a dry run writes nothing
    assert infra_requeue.rebuild(root, [task], ruling="V2-REBUILD-3", apply=True)[
        "requested"
    ] == [task]
    assert json.loads(requests.read_text())["ruling"] == "V2-REBUILD-3"
    assert infra_requeue.rebuild(root, [task], ruling="V2-REBUILD-3", apply=True)[
        "refused"
    ] == {task: "already_requested"}
