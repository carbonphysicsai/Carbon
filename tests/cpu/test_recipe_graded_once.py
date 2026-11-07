"""OWNER-PROBING-COUNTERS-01 (b): an identical recipe is graded ONCE across all accounts (Carbon Validator 11:03,
Validator-2 11:04). Real `AttemptLedger`, `ExamCap`, `recipe_copies` and `AutoGrader.run_once`; only the providers and
the grade itself (`retain_result`, which reserves and counts a slot exactly as the real one does) are stood in.
Fixture values only."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import (
    auto_grade,
    direct_intake,
    exam_cap,
    recipe_copies,
)
from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable
from carbon.challenge_validator.ledger import AttemptLedger

CHALLENGE = SimpleNamespace(challenge_id="electric-motor-magnetics", version="1.5")
CONTRACT = "sha256:" + "c" * 64
EXAM = "sha256:" + "1" * 64
NEXT_EXAM = "sha256:" + "2" * 64
HOTKEYS = [f"5{chr(65 + i)}" + "x" * 46 for i in range(6)]
D = "sha256:" + "d" * 64


def _recipe(setting=1):
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": {
            "id": CHALLENGE.challenge_id,
            "version": CHALLENGE.version,
            "train_digest": D,
            "interface_digest": D,
            "construction_limits_digest": D,
        },
        "source": {
            "kind": "catalog",
            "catalog_id": "v2.motor.jno.fno1d",
            "catalog_digest": D,
        },
        "procedure": {
            "entrypoint": None,
            "configuration": {"width": setting},
            "train_use": {},
            "initial_state": None,
        },
        "output": {"format": "npz", "interface_digest": D},
    }


def _cadence():
    return {
        "capacity_gpu_lane_hours_per_day": 1000.0,
        "rebuild_gpu_lane_hours": {CHALLENGE.challenge_id: 1.0},
        "lanes": 1,
        "measurement_digest": "sha256:" + "a" * 64,
        "class_record_digest": "sha256:" + "b" * 64,
    }


class Door:
    """One receiver: a real attempt ledger, providers holding each task's recipe, and a grade that reserves + counts."""

    def __init__(self, tmp_path):
        (tmp_path / "ledger").mkdir(mode=0o700)
        self.ledger = AttemptLedger(tmp_path / "ledger" / "attempts.sqlite3")
        self.owners, self.requests = {}, {}
        self.snapshot = SimpleNamespace(manifest_digest=EXAM)
        self.adapter = SimpleNamespace(
            ledger=self.ledger,
            contract_digest=CONTRACT,
            owner=lambda sid: self.owners.get(sid),
            _provider=lambda owner: SimpleNamespace(_requests=self.requests),
            discovery=SimpleNamespace(evaluation_pack_snapshot=self.snapshot),
            exam_cadence=_cadence(),
        )
        self.ready, self.graded, self.outcome = set(), [], {}
        self.intake = SimpleNamespace(
            adapter=self.adapter, challenge=CHALLENGE, retain_result=self.retain_result
        )
        self.grader = auto_grade.AutoGrader(self.intake, tmp_path, pool_store=object())
        self.grader.chain_degraded = lambda: False
        self.grader._pool = lambda: None  # the pool itself is not under test
        self.grader._king_upkeep = lambda: None
        self.grader._resume_paused_crowns = lambda: None
        self.block = 1000

    def submit(self, sid, hotkey, recipe):
        self.owners[sid], self.requests[sid] = hotkey, SimpleNamespace(recipe=recipe)
        self.block += 400  # each submission in its own epoch
        self.ledger.record(
            SimpleNamespace(
                hotkey=hotkey,
                receipt={
                    "sequence": len(self.owners),
                    "digest": "d",
                    "block": self.block,
                },
                contract_digest=CONTRACT,
            ),
            kind="OUTCOME",
            submission_id=sid,
        )

    def cap(self):
        return exam_cap.ExamCap(self.ledger, cadence=_cadence())

    def retain_result(self, submission_id, **_kwargs):
        if submission_id not in self.ready:
            raise RetentionUnavailable("task_not_succeeded")
        cap = self.cap()
        reservation = cap.reserve(
            hotkey=self.owners[submission_id],
            challenge_id=CHALLENGE.challenge_id,
            challenge_version=CHALLENGE.version,
            exam_key=self.snapshot.manifest_digest,
            submission_id=submission_id,
            block=exam_cap.submission_block(self.ledger, CONTRACT, submission_id),
        )
        status = self.outcome.get(submission_id, "SCORED_DEVELOPMENT_CANDIDATE")
        if status == "HOLD":
            return {
                "entry_id": None,
                "private_evaluation_state": "IN_FLIGHT",
            }  # leaves the slot RESERVED
        cap.settle(reservation, status)
        self.graded.append(submission_id)
        if status in exam_cap.RELEASED:
            raise RuntimeError("infrastructure")  # the grader gives it back
        return {"entry_id": "sha256:" + "e" * 64}

    def state(self, sid, key=EXAM):
        with self.ledger._db() as db:
            return db.execute(
                "SELECT state, status FROM exam_graded WHERE submission_id=? AND exam_key=?",
                (sid, key),
            ).fetchone()


T = [f"rtsk_{i:064x}" for i in range(8)]


@pytest.fixture
def door(tmp_path):
    return Door(tmp_path)


def test_a_copy_from_another_account_is_answered_with_the_first_grade_and_reads_no_exam(
    door,
):
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready |= {T[0], T[1]}
    assert door.grader.run_once() == (T[0], "GRADED")
    assert door.grader.run_once() == (T[1], "DUPLICATE")
    assert door.graded == [T[0]]  # the copy never reached the exam
    assert recipe_copies.first_of(door.ledger, T[1]) == T[0]
    assert door.state(T[1]) == (
        "COUNTED",
        recipe_copies.DUPLICATE,
    )  # charged to its own allowance
    assert door.grader.marker(T[1])["state"] == "DUPLICATE"


def test_a_different_recipe_is_graded(door):
    door.submit(T[0], HOTKEYS[0], _recipe(1))
    door.submit(
        T[1], HOTKEYS[1], _recipe(2)
    )  # one setting nudged: near-identical, not identical
    door.ready |= {T[0], T[1]}
    door.grader.run_once()
    assert door.grader.run_once() == (T[1], "GRADED")
    assert door.graded == [T[0], T[1]]


def test_a_copy_waits_while_the_first_is_unsettled_then_becomes_a_copy(door):
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready.add(T[1])  # the later copy built first
    assert door.grader.run_once() is None  # T0 still building, T1 waits (no slot taken)
    assert door.state(T[1]) is None and door.graded == []
    door.ready.add(T[0])
    assert door.grader.run_once() == (T[0], "GRADED")
    assert door.grader.run_once() == (T[1], "DUPLICATE")


def test_a_copy_waits_while_the_first_holds_a_reserved_slot(door):
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready |= {T[0], T[1]}
    door.outcome[T[0]] = "HOLD"
    door.cap().reserve(
        hotkey=HOTKEYS[0],
        challenge_id=CHALLENGE.challenge_id,
        challenge_version=CHALLENGE.version,
        exam_key=EXAM,
        submission_id=T[0],
        block=exam_cap.submission_block(door.ledger, CONTRACT, T[0]),
    )
    decision = recipe_copies.decide(
        adapter=door.adapter,
        ledger=door.ledger,
        marker=door.grader.marker,
        submission_id=T[1],
        challenge_id=CHALLENGE.challenge_id,
        challenge_version=CHALLENGE.version,
        exam_key=EXAM,
    )
    assert decision == (recipe_copies.WAIT, T[0])


def test_a_first_given_back_on_infrastructure_never_read_the_exam_so_the_next_grades(
    door,
):
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready |= {T[0], T[1]}
    door.outcome[T[0]] = "FAILED_INFRA"
    assert door.grader.run_once() == (T[0], "FAILED")
    assert door.state(T[0])[0] == "RELEASED"
    assert door.grader.run_once() == (T[1], "GRADED")  # the new first


def test_a_new_pack_key_grades_the_recipe_again(door):
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready |= {T[0], T[1]}
    door.grader.run_once()
    door.snapshot.manifest_digest = NEXT_EXAM  # rotated pack
    assert door.grader.run_once() == (T[1], "GRADED")


def test_submissions_admitted_before_the_release_are_untouched(tmp_path):
    door = Door.__new__(Door)
    # admit two copies BEFORE the grader (the release) starts
    (tmp_path / "ledger").mkdir(mode=0o700)
    door.ledger = AttemptLedger(tmp_path / "ledger" / "attempts.sqlite3")
    door.owners, door.requests, door.block = {}, {}, 1000
    door.snapshot = SimpleNamespace(manifest_digest=EXAM)
    door.adapter = SimpleNamespace(
        ledger=door.ledger,
        contract_digest=CONTRACT,
        owner=lambda sid: door.owners.get(sid),
        _provider=lambda owner: SimpleNamespace(_requests=door.requests),
        discovery=SimpleNamespace(evaluation_pack_snapshot=door.snapshot),
        exam_cadence=_cadence(),
    )
    door.ready, door.graded, door.outcome = set(), [], {}
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.intake = SimpleNamespace(
        adapter=door.adapter, challenge=CHALLENGE, retain_result=door.retain_result
    )
    door.grader = auto_grade.AutoGrader(door.intake, tmp_path, pool_store=object())
    door.grader.chain_degraded = lambda: False
    door.grader._pool = lambda: None
    door.grader._king_upkeep = lambda: None
    door.grader._resume_paused_crowns = lambda: None
    door.ready |= {T[0], T[1]}
    assert door.grader.run_once() == (T[0], "GRADED")
    assert door.grader.run_once() == (
        T[1],
        "GRADED",
    )  # admitted before the release: graded as before
    door.submit(
        T[2], HOTKEYS[2], _recipe()
    )  # after the release: a copy of the earliest graded AFTER it? none: grades
    door.submit(T[3], HOTKEYS[3], _recipe())
    door.ready |= {T[2], T[3]}
    assert door.grader.run_once() == (T[2], "GRADED")
    assert door.grader.run_once() == (T[3], "DUPLICATE")
    assert recipe_copies.first_of(door.ledger, T[3]) == T[2]


def test_a_copy_beyond_its_own_round_allowance_is_refused_like_any_grade(door):
    door.submit(T[0], HOTKEYS[0], _recipe(1))
    door.submit(T[1], HOTKEYS[1], _recipe(2))
    door.ready |= {T[0], T[1]}
    door.grader.run_once()
    door.grader.run_once()
    # HOTKEYS[1] submits a copy of T0 in the SAME epoch as its graded T1: its round slot is taken
    door.owners[T[2]], door.requests[T[2]] = HOTKEYS[1], SimpleNamespace(
        recipe=_recipe(1)
    )
    door.ledger.record(
        SimpleNamespace(
            hotkey=HOTKEYS[1],
            receipt={"sequence": 9, "digest": "d", "block": door.block},
            contract_digest=CONTRACT,
        ),
        kind="OUTCOME",
        submission_id=T[2],
    )
    door.ready.add(T[2])
    assert door.grader.run_once() == (T[2], "GRADED")
    assert door.grader.marker(T[2])["code"] == "epoch_limit_reached"
    assert recipe_copies.first_of(door.ledger, T[2]) is None


def _copier_intake(door):
    intake = SimpleNamespace(
        grade_marker=door.grader.marker, adapter=door.adapter, challenge=CHALLENGE
    )
    intake._grade_state_v4 = lambda hotkey, sid: (
        direct_intake.DirectRecipeIntake._grade_state_v4(intake, hotkey, sid)
    )
    intake._grade_state = lambda hotkey, sid: (
        direct_intake.DirectRecipeIntake._grade_state(intake, hotkey, sid)
    )
    return intake


def test_the_v4_state_of_a_copy_is_graded_its_slot_is_held(door):
    # Validator-2B 7 Nov must-fix: v4 NOT_GRADED means "slot given back, nothing charged"; a copy's slot is COUNTED.
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready |= {T[0], T[1]}
    door.grader.run_once()
    assert door.grader.run_once() == (T[1], "DUPLICATE")
    assert door.state(T[1]) == ("COUNTED", recipe_copies.DUPLICATE)
    intake = _copier_intake(door)
    assert direct_intake.DirectRecipeIntake._grade_state_v4(
        intake, HOTKEYS[1], T[1]
    ) == ("GRADED", None)


def test_the_copiers_exact_v4_reply_carries_nothing_of_the_first(door, monkeypatch):
    from carbon.challenge_validator import ladder_store

    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready |= {T[0], T[1]}
    door.grader.run_once()
    door.grader.run_once()
    served = []

    class _Ladder:
        def __init__(self, ledger):
            pass

        def served(self, hotkey, challenge, exam_key):
            served.append(hotkey)
            return {"best": None, "latest": None}

    monkeypatch.setattr(ladder_store, "LadderStore", _Ladder)
    reply = direct_intake.DirectRecipeIntake._feedback(
        _copier_intake(door), HOTKEYS[1], submission_id=T[1], v4=True
    )
    assert reply.status == 200
    assert served == [HOTKEYS[1]]  # only the copier's own Ladder is read
    assert reply.body == {
        "schema": direct_intake.FEEDBACK_REPLY_SCHEMA_V4,
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "best": None,
        "latest": None,
        "submission": {"submission_id": T[1], "grade_state": "GRADED", "failure": None},
    }
    flat = repr(reply.body)
    assert T[0] not in flat and HOTKEYS[0] not in flat


def test_earlier_means_admitted_earlier_never_a_smaller_task_id(door):
    # Task ids are content hashes: the first submission may sort AFTER its copy.
    door.submit(T[5], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready |= {T[5], T[1]}
    # T1 is listed first but was admitted second: it waits for T5, then copies it.
    assert door.grader.run_once() == (T[5], "GRADED")
    assert door.grader.run_once() == (T[1], "DUPLICATE")
    assert recipe_copies.first_of(door.ledger, T[1]) == T[5]
    assert door.graded == [T[5]]


def test_a_wait_is_counted_for_the_operator(door):
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready.add(T[1])  # the first is still building
    assert door.grader.run_once() is None
    assert door.grader.recipe_copy_waits == 1


def test_the_digest_noted_at_admission_survives_a_restart(door):
    for sid, hotkey in ((T[0], HOTKEYS[0]), (T[1], HOTKEYS[1])):
        door.submit(sid, hotkey, _recipe())
        intake = SimpleNamespace(adapter=door.adapter)
        direct_intake.DirectRecipeIntake._note_recipe_digest(
            intake, {"kind": "OUTCOME", "outcome": {"task_id": sid}}
        )
    door.requests.clear()  # a restart: the providers' in-memory requests are gone
    door.ready |= {T[0], T[1]}
    assert door.grader.run_once() == (T[0], "GRADED")
    assert door.grader.run_once() == (T[1], "DUPLICATE")


def test_noting_a_digest_never_changes_an_admission(door):
    intake = SimpleNamespace(adapter=door.adapter)
    for result in ({"kind": "REFUSED"}, {"outcome": {"task_id": T[7]}}, None):
        assert direct_intake.DirectRecipeIntake._note_recipe_digest(intake, result) is None


def test_a_copy_is_settled_never_pending(door):
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.ready |= {T[0], T[1]}
    door.grader.run_once()
    door.grader.run_once()
    assert door.grader.pending() == []  # the queue view counts only pending tasks: a copy is in none of its counts


def test_the_digest_is_the_canonical_recipe_digest_and_ignores_the_submitter(door):
    from carbon.development_session.construction_recipe import ConstructionRecipe

    door.submit(T[0], HOTKEYS[0], _recipe())
    door.ready.add(T[0])
    door.grader.run_once()
    assert (
        recipe_copies.stored_digest(door.ledger, T[0])
        == ConstructionRecipe.from_dict(_recipe()).digest
    )
