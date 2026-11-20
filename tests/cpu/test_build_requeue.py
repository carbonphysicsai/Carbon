"""Order 3 (Lead 17 Nov 2026, handoff s3 item 5): a build that ends on Carbon's infrastructure is queued again ONCE.

`LeanRecipeAdapter._requeue_failed_build` starts the failed task's next generation (the task its miner's resubmit would
make) at the failed task's ORIGINAL queue place and epoch (`AttemptLedger.requeue_failed_build`: the queue-place grant
plus an accepted-submission row copied from the original, its signed receipt included), and its grade neither spends nor
is refused by the miner's round or day (`ExamCap.mark_requeued`). Never a requeue of a requeue, never when the miner
already resubmitted, never anything but FAILED_INFRA, and never a failure of the build round. Fixture ids only.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test_recipe_graded_once import CONTRACT, HOTKEYS

from carbon.challenge_validator import exam_cap
from carbon.challenge_validator.lean_recipe import MAX_INFRA_RERUNS, LeanRecipeAdapter
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.research import ChallengeKey, DirectTaskStateV3, ResearchTaskId

IDS = {name: "rtsk_" + char * 64 for name, char in zip("ABCN", "abcd", strict=True)}
A, B, C, N = (IDS[k] for k in "ABCN")
BLOCK = 4321


@pytest.fixture
def ledger(tmp_path):
    clock = iter(range(1000, 100_000, 10))
    return AttemptLedger(tmp_path / "attempts.sqlite3", clock=lambda: next(clock))


def _outcome(ledger, sid, hotkey=HOTKEYS[0], block=BLOCK):
    ledger.record(
        SimpleNamespace(
            hotkey=hotkey,
            receipt={"sequence": 1, "digest": "d", "block": block},
            contract_digest=CONTRACT,
        ),
        kind="OUTCOME",
        submission_id=sid,
        state="ADMITTED",
    )


def _queue(ledger):
    _outcome(ledger, A)  # the build that fails on Carbon's side
    _outcome(ledger, B, block=BLOCK + 500)
    _outcome(ledger, C, block=BLOCK + 900)


def _requeue(ledger, **changes):
    values = {"from_task": A, "new_task": N, "hotkey": HOTKEYS[0], **changes}
    return ledger.requeue_failed_build(CONTRACT, **values)


# --- the ledger ---------------------------------------------------------------------------------------------------------


def test_the_requeue_takes_the_original_place_and_epoch(ledger):
    _queue(ledger)
    assert _requeue(ledger) == "requeued"
    order = ledger.submitted_outcomes(CONTRACT)
    assert order.index(N) < order.index(
        B
    )  # A's place, ahead of everything that arrived after A
    # its grade reserves under A's signed receipt: A's block, so A's epoch
    assert exam_cap.submission_block(ledger, CONTRACT, N) == BLOCK
    assert ledger.owned_outcome(CONTRACT, N) == HOTKEYS[0]
    with ledger._db() as db:
        code = db.execute(
            "SELECT code FROM attempts WHERE kind='OUTCOME' AND submission_id=?", (N,)
        ).fetchone()[0]
    assert code == AttemptLedger.BUILD_REQUEUED


def test_a_build_is_requeued_once_and_a_requeue_never_again(ledger):
    _queue(ledger)
    assert _requeue(ledger) == "requeued"
    assert _requeue(ledger) == "already_requeued"
    assert _requeue(ledger, new_task=C) == "from_task_used"
    # the requeue itself failing on Carbon's side again: never queued a third time
    assert _requeue(ledger, from_task=N, new_task=B) == "from_task_is_a_requeue"


def test_refusals_write_nothing(ledger):
    _queue(ledger)
    _outcome(ledger, N)  # the miner already resubmitted
    for changes, code in (
        ({"hotkey": HOTKEYS[1]}, "hotkey_mismatch"),
        ({"from_task": "rtsk_" + "e" * 64}, "no_original"),
        ({"new_task": A}, "same_task"),
        ({"hotkey": ""}, "incomplete"),
        ({}, "new_task_known"),
    ):
        with ledger._db() as db:
            before = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        assert _requeue(ledger, **changes) == code
        with ledger._db() as db:
            assert db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == before
            assert not db.execute("SELECT 1 FROM queue_place_grants").fetchone()


# --- the door -----------------------------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _plain_requests(monkeypatch):
    # the fixture's requests are plain tuples, not wire records: their intent digest is over their repr
    import carbon.research

    monkeypatch.setattr(
        carbon.research, "canonical_bytes", lambda request: repr(request).encode()
    )


#: A retained diagnosis of a proven Carbon-side failure (a build wall on a busy box: owner G-LEAD-10's one rebuild).
BUSY_BOX = {
    "failed_stage": "build",
    "reason_code": "reconstruction.worker.runtime.failed",
    "tail": "stream command timed out",
}


class _Provider:
    """The provider surface the requeue reads: task states, retained requests, task ids, a start, the failure's
    retained diagnosis (default a proven Carbon-side one) and, when set, its completion time.
    """

    evaluation_pack_digest = "sha256:" + "p" * 64

    def __init__(self, states, diagnosis=BUSY_BOX, completed=None):
        self.states = dict(states)
        self._requests = {A: ("req", HOTKEYS[0], 0)}
        self.started = []
        self.diagnosis = diagnosis
        self.completed = completed

    def get_research_result(self, request):
        return SimpleNamespace(
            task=SimpleNamespace(
                state=self.states[request.task_id.value],
                terminal_receipt=SimpleNamespace(completed_at_micros=self.completed),
            )
        )

    def private_infra_diagnosis(self, task_id):
        return self.diagnosis

    @staticmethod
    def _task_id(request):
        return ResearchTaskId({0: A, 1: N}.get(request[2], "rtsk_" + "f" * 64))

    def start_research_task(self, request, *, measure_query, rebuild_of=None):
        self.started.append((request, measure_query))
        self.rebuilt_from = getattr(self, "rebuilt_from", []) + [rebuild_of]


def _door(ledger):
    door = object.__new__(LeanRecipeAdapter)
    door.ledger, door.contract_digest, door._measure_query = ledger, CONTRACT, False
    door.discovery = SimpleNamespace(
        info=SimpleNamespace(
            challenge_key=ChallengeKey("electric-motor-magnetics", "1.8")
        )
    )
    door._retained_recipe = lambda retained: "recipe"
    door._request = lambda owner, recipe, *, evaluation_pack_digest, rerun: (
        "req",
        owner,
        rerun,
    )
    return door


def test_the_door_requeues_a_failed_infra_build_once_at_its_place(ledger):
    _queue(ledger)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.FAILED_INFRA})
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) == N
    assert provider.started == [(("req", HOTKEYS[0], 1), False)]  # the next generation
    order = ledger.submitted_outcomes(CONTRACT)
    assert order.index(N) < order.index(B)
    with ledger._db() as db:  # its one round/day bypass, as the operator requeue's
        assert db.execute(
            "SELECT 1 FROM exam_requeues WHERE submission_id=?", (N,)
        ).fetchone()
    # a second pass over the same failed task: nothing new
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert len(provider.started) == 1


@pytest.mark.parametrize(
    "state",
    [
        DirectTaskStateV3.SUCCEEDED,
        DirectTaskStateV3.REFUSED,
        DirectTaskStateV3.CANCELLED,
    ],
)
def test_only_a_build_that_failed_on_carbons_side_is_requeued(ledger, state):
    _queue(ledger)
    door, provider = _door(ledger), _Provider({A: state})
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert provider.started == []
    assert ledger.submitted_outcomes(CONTRACT)[-1] != N


def test_the_last_generation_is_never_requeued(ledger):
    _queue(ledger)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.FAILED_INFRA})
    provider._requests[A] = ("req", HOTKEYS[0], MAX_INFRA_RERUNS)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    assert provider.started == []


def test_a_requeue_never_fails_the_build_round(ledger, monkeypatch):
    _queue(ledger)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.FAILED_INFRA})

    def boom(*args, **kwargs):
        raise RuntimeError("provider busy")

    monkeypatch.setattr(provider, "start_research_task", boom)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    monkeypatch.setattr(provider, "get_research_result", boom)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    door.ledger = SimpleNamespace()  # a ledger without the method: nothing
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None


# --- end to end with the real grader, ledger and exam cap (`test_recipe_graded_once.Door`) ---------------------------


def test_a_requeued_build_is_graded_never_held_back_by_its_failed_original(tmp_path):
    """The copy rule (`recipe_copies.decide`) used to WAIT on an earlier task of the same recipe that never got a grade
    marker: a build that ended on Carbon's side never gets one, so its requeue (or its miner's resubmit) waited for
    good. An earlier task that ended without a build never read the exam: the later one is graded.
    """
    from test_recipe_graded_once import Door, T, _recipe

    door = Door(tmp_path)
    door.submit(
        T[0], HOTKEYS[0], _recipe()
    )  # its build ends FAILED_INFRA: no marker, no slot
    door.adapter.outcome = lambda sid: {
        "state": "FAILED_INFRA" if sid == T[0] else "RECONSTRUCTED"
    }
    assert (
        door.ledger.requeue_failed_build(
            CONTRACT, from_task=T[0], new_task=T[2], hotkey=HOTKEYS[0]
        )
        == "requeued"
    )
    exam_cap.ExamCap(door.ledger).mark_requeued(T[2])
    door.owners[T[2]], door.requests[T[2]] = HOTKEYS[0], door.requests[T[0]]
    door.ready.add(T[2])
    assert door.grader.run_once() == (T[2], "GRADED")
    assert door.state(T[2]) == ("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")


def test_without_the_unbuilt_read_the_copy_rule_waits_as_before(tmp_path):
    from test_recipe_graded_once import Door, T, _recipe

    door = Door(tmp_path)
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready.add(T[1])
    door.adapter.outcome = lambda sid: {"state": "ADMITTED"}  # still building
    assert door.grader.run_once() is None and door.graded == []


def test_a_start_that_fails_leaves_no_place_and_no_bypass(ledger, monkeypatch):
    _queue(ledger)
    door, provider = _door(ledger), _Provider({A: DirectTaskStateV3.FAILED_INFRA})

    def refused(*args, **kwargs):
        raise RuntimeError("bound exceeded")

    monkeypatch.setattr(provider, "start_research_task", refused)
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), provider) is None
    exam_cap.ExamCap(ledger)  # its tables, so the bypass can be looked up
    with ledger._db() as db:
        assert not db.execute("SELECT 1 FROM queue_place_grants").fetchone()
        assert not db.execute(
            "SELECT 1 FROM attempts WHERE kind='OUTCOME' AND submission_id=?", (N,)
        ).fetchone()
        assert not db.execute(
            "SELECT 1 FROM exam_requeues WHERE submission_id=?", (N,)
        ).fetchone()
    # an intent only, as an interrupted resubmit leaves: the miner's own resubmit still starts this task
    assert N in ledger.submitted_outcomes(CONTRACT)


def test_a_stop_cancel_resubmission_that_fails_is_requeued_at_the_original_place(
    ledger,
):
    """A task holding a stop-cancelled task's place (`grant_queue_place`) that then fails on Carbon's side is requeued
    once, and its requeue keeps the ORIGINAL place (a chain), never the resubmission's own later one.
    """
    stopped, resubmit = "rtsk_" + "1" * 64, "rtsk_" + "2" * 64
    _outcome(ledger, stopped)
    _queue(ledger)
    _outcome(ledger, resubmit)
    assert (
        ledger.grant_queue_place(
            CONTRACT, from_task=stopped, new_task=resubmit, hotkey=HOTKEYS[0]
        )
        == "granted"
    )
    assert _requeue(ledger, from_task=resubmit) == "requeued"
    order = ledger.submitted_outcomes(CONTRACT)
    assert order.index(N) < order.index(A)  # the stopped task's place, ahead of A
