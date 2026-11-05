"""REG-UNAVAILABLE A2 (TL 4 Nov 03:14-03:44; Validator 03:15, 05:17): the one-shot operator tools of
`challenge_validator.infra_requeue` and the receiver's own `ExamCap.release_undelivered`.

Claims:
- ``list`` regenerates the stuck list from the door's own markers and ledger (never a frozen file), split by arrival.
- ``requeue`` hands only FAILED, registration-caused, never-charged tasks back to the receiver's REAL auto-grader, once
  (attempt 2, same task identity, its own row reused: no new slot); a graded task is NEVER re-queued; a dry run changes
  nothing; a task already given back as FAILED_INFRA is left to the door's fresh-rerun path.
- ``release`` frees one COUNTED slot only through `ExamCap.release_undelivered`, keeps the row and its prior state as
  history, never regrades, and refuses when the grade was delivered (marker or Ladder).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from types import SimpleNamespace

import pytest

A, B, C, D, E, F = ("rtsk_" + c * 64 for c in "abcdef")
HOTKEY = "5" + "1" * 47
EXAM = "sha256:" + "e" * 64
#: 3 Nov 2026 00:00Z, the default split, in ns.
SPLIT_NS = 1_793_664_000 * 10**9
CAUSE = "direct_provider_registration_unavailable"
CONTRACT = "sha256:" + "c" * 64
PACK = "sha256:" + "a" * 64


@pytest.fixture(autouse=True)
def served(monkeypatch):
    """The door's served contract for its Challenge (the code registry, patched to the fixture's)."""
    from carbon.reconstruction import served_recipe_contract

    monkeypatch.setattr(
        served_recipe_contract,
        "registered",
        lambda cid, version: SimpleNamespace(digest=CONTRACT),
    )


def _root(tmp_path):
    from carbon.challenge_validator.exam_cap import ExamCap
    from carbon.challenge_validator.ledger import AttemptLedger

    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    ledger = AttemptLedger(root / "attempts.sqlite3")
    ExamCap(ledger)  # the exam tables
    (root / "receiver-binding.json").write_text(
        json.dumps(
            {
                "challenge": {"id": "f02", "version": "2.5"},
                "evaluation_pack_digest": PACK,
            }
        )
    )
    return root, ledger


def _recipe(name, n=0):
    """A valid graph ConstructionRecipe document; ``name`` picks its graph, ``n`` its configuration."""
    digest = "sha256:" + hashlib.sha256(str(name).encode()).hexdigest()
    zero = "sha256:" + "0" * 64
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": {
            "id": "f02",
            "version": "2.5",
            "train_digest": zero,
            "interface_digest": zero,
            "construction_limits_digest": zero,
        },
        "source": {"kind": "graph", "submission_digest": digest},
        "procedure": {
            "entrypoint": None,
            "configuration": {"n": n},
            "train_use": {"cases": "all"},
            "initial_state": None,
        },
        "output": {"format": "carbon.numeric-graph.v1", "interface_digest": zero},
    }


def _store(root, task, recipe, *, pack=PACK, hotkey=HOTKEY):
    """The task's row in its owner's store (a real canonical request), the owner bound to ``pack``."""
    from carbon.registry.model import ChallengeKey
    from carbon.research import DirectStartTaskRequestV3, canonical_bytes

    directory = root / "owners" / hashlib.sha256(hotkey.encode()).hexdigest()
    (directory / "ledger").mkdir(parents=True, exist_ok=True)
    (directory / "tasks").mkdir(parents=True, exist_ok=True)
    campaign = sqlite3.connect(directory / "ledger" / "campaign.sqlite3")
    campaign.execute(
        "CREATE TABLE IF NOT EXISTS campaign(id INTEGER PRIMARY KEY, manifest TEXT)"
    )
    campaign.execute(
        "INSERT OR REPLACE INTO campaign VALUES(1, ?)",
        (json.dumps({"receiver_binding": {"evaluation_pack_digest": pack}}),),
    )
    campaign.commit()
    campaign.close()
    digest = "sha256:" + "0" * 64
    request = DirectStartTaskRequestV3(
        ChallengeKey("f02", "2.5"),
        "lean-recipe-" + task[5:],
        recipe,
        *([digest] * 8),
    )
    tasks = sqlite3.connect(directory / "tasks" / "direct-tasks.sqlite3")
    tasks.execute(
        "CREATE TABLE IF NOT EXISTS direct_tasks(id TEXT PRIMARY KEY, request BLOB)"
    )
    tasks.execute(
        "INSERT INTO direct_tasks VALUES(?,?)", (task, canonical_bytes(request))
    )
    tasks.commit()
    tasks.close()


def _arrived(ledger, task, *, at_ns=SPLIT_NS + 10**9, block=7_200, contract=CONTRACT):
    with ledger._db() as db:
        db.execute(
            "INSERT INTO attempts(at_ns, kind, hotkey, contract_digest, receipt, submission_sha256, "
            "submission_id) VALUES(?, 'OUTCOME', ?, ?, ?, 'sha256:s', ?)",
            (at_ns, HOTKEY, contract, json.dumps({"block": block}), task),
        )


def _row(ledger, task, state, status=None, *, epoch=20):
    with ledger._db() as db:
        return db.execute(
            "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, exam_key, kind, epoch, "
            "submission_id, state, status, reserved_ns) VALUES(?,'f02','2.5',?,'GRADED',?,?,?,?,1)",
            (HOTKEY, EXAM, epoch, task, state, status),
        ).lastrowid


def _rows(ledger, task):
    with ledger._db() as db:
        return db.execute(
            "SELECT state, status FROM exam_graded WHERE submission_id=?", (task,)
        ).fetchall()


def _failed(
    root,
    ledger,
    task,
    *,
    cause=CAUSE,
    state="FAILED",
    arrived=True,
    stored=True,
    recipe=None,
    pack=PACK,
    **when,
):
    from carbon.challenge_validator.auto_grade import SCHEMA

    markers = root / "auto-grade" / "markers"
    failures = root / "auto-grade" / "failures"
    markers.mkdir(parents=True, exist_ok=True)
    failures.mkdir(parents=True, exist_ok=True)
    (markers / (task + ".json")).write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "submission_id": task,
                "state": state,
                "code": "Unavailable:unrecorded",
                "entry_id": None,
            }
        )
    )
    (failures / (task + ".txt")).write_text(f"Traceback ...\nUnavailable: {cause}\n")
    if arrived:
        _arrived(ledger, task, **when)
    if stored:
        _store(root, task, recipe or _recipe(task), pack=pack)


def _kept(root, task, suffix):
    return root / "auto-grade" / "requeued" / f"{task}.attempt-1.{suffix}"


# ---------------------------------------------------------------- list: the regenerated task list


def test_list_regenerates_the_stuck_list_from_the_door_split_at_3_nov(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)  # since 3 Nov
    _failed(root, ledger, B, at_ns=SPLIT_NS - 10**9)  # before 3 Nov
    _failed(root, ledger, C, state="GRADED")  # not FAILED: not listed at all
    _failed(root, ledger, D, cause="WorkerFailure")
    _failed(root, ledger, E)
    _row(ledger, E, "RELEASED", "FAILED_INFRA")  # given back: the fresh-rerun path
    _failed(root, ledger, F)
    _row(ledger, F, "COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")
    out = infra_requeue.scan(root)
    assert out["eligible"] == {"before_split": [B], "since_split": [A]}
    assert out["eligible_counts"] == {"before_split": 1, "since_split": 1}
    assert out["failed_markers"] == 5
    assert out["refused_counts"] == {
        "cause_not_registration_unavailable": 1,
        "given_back_resubmit_runs_fresh": 1,
        "exam_row_counted_or_reserved": 1,
    }
    assert out["arrived"][A] == "2026-11-03T00:00:01Z"
    # the read changes nothing
    assert (root / "auto-grade" / "markers" / (A + ".json")).exists()
    assert not (root / "auto-grade" / "requeued").exists()


def test_list_prints_the_cost_from_this_doors_own_grades(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    _failed(root, ledger, B)
    assert infra_requeue.scan(root)["cost"]["estimated_grade_hours"] is None
    with ledger._db() as db:
        for n, wall_s in enumerate((1200, 2400)):
            db.execute(
                "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, exam_key, kind, "
                "epoch, submission_id, state, status, reserved_ns, settled_ns) VALUES(?,'f02','2.5',?,"
                "'GRADED',1,?,'COUNTED','SCORED_DEVELOPMENT_CANDIDATE',?,?)",
                (HOTKEY, EXAM, "rtsk_" + str(n) * 64, 10**9, 10**9 + wall_s * 10**9),
            )
    cost = infra_requeue.scan(root)["cost"]
    assert cost["requeue_count"] == 2 and cost["grade_wall_samples"] == 2
    assert cost["mean_grade_wall_seconds"] == 1800.0
    assert cost["estimated_grade_hours"] == 1.0


# ---------------------------------------------------------------- requeue


def test_requeue_hands_back_once_and_the_real_auto_grader_takes_it(tmp_path):
    from carbon.challenge_validator import auto_grade, infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    _failed(root, ledger, C, state="GRADED")
    graded = []

    class Intake:
        adapter = SimpleNamespace(
            contract_digest="sha256:c",
            ledger=SimpleNamespace(submitted_outcomes=lambda contract: (A, C)),
            owner=lambda submission_id: HOTKEY,
        )

        def retain_result(self, submission_id, **kwargs):
            graded.append(submission_id)
            return {"entry_id": "sha256:" + "1" * 64}

    grader = auto_grade.AutoGrader(Intake(), root)
    assert grader.pending() == []  # before: both have markers, nothing is graded
    dry = infra_requeue.requeue(root, [A, C])
    assert dry["requeued"] == [A] and dry["refused"] == {C: "marker_graded"}
    assert grader.pending() == []  # a dry run changes nothing
    out = infra_requeue.requeue(root, [A, C], apply=True)
    assert out["requeued"] == [A] and out["refused"] == {C: "marker_graded"}
    assert json.loads(_kept(root, A, "marker.json").read_text())["state"] == "FAILED"
    assert CAUSE in _kept(root, A, "failure.txt").read_text()
    log = (root / "auto-grade" / "requeued" / "requeues.jsonl").read_text().splitlines()
    assert [json.loads(line)["attempt"] for line in log] == [2]
    assert grader.pending() == [A]  # the graded task stays out
    assert grader.run_once() == (A, "GRADED")
    assert graded == [A]
    # one-shot: the same task is never handed back again, graded or not
    again = infra_requeue.requeue(root, [A], apply=True)
    assert again["refused"] == {A: "already_requeued"}


@pytest.mark.parametrize(
    "marker, row, code",
    [
        ("GRADED", None, "marker_graded"),
        ("CANDIDATE_FAILED", None, "marker_candidate_failed"),
        (
            "FAILED",
            ("COUNTED", "REQUIRED_LEG_MINIMUM_FAILED"),
            "exam_row_counted_or_reserved",
        ),
        ("FAILED", ("RESERVED", None), "exam_row_counted_or_reserved"),
    ],
)
def test_a_graded_or_charged_task_is_never_requeued(tmp_path, marker, row, code):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, state=marker)
    if row is not None:
        _row(ledger, A, *row)
    out = infra_requeue.requeue(root, [A], apply=True)
    assert out["requeued"] == [] and out["refused"] == {A: code}
    assert (root / "auto-grade" / "markers" / (A + ".json")).exists()
    assert not _kept(root, A, "marker.json").exists()


def test_requeue_refuses_other_causes_strangers_and_given_back_tasks(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause="WorkerFailure")
    _failed(
        root, ledger, B, arrived=False
    )  # never submitted at this door: the grader would never take it
    _failed(root, ledger, D)
    _row(ledger, D, "RELEASED", "FAILED_INFRA")
    out = infra_requeue.requeue(root, [A, B, D, E, "x"], apply=True)
    assert out["requeued"] == []
    assert out["refused"] == {
        A: "cause_not_registration_unavailable",
        B: "not_submitted_at_this_door",
        D: "given_back_resubmit_runs_fresh",
        E: "no_marker",
        "x": "not_a_task_id",
    }


def test_a_requeued_task_reuses_its_own_row_so_no_new_slot_is_taken(tmp_path):
    from carbon.challenge_validator import infra_requeue
    from carbon.challenge_validator.exam_cap import ExamCap

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    row = _row(ledger, A, "RELEASED", "UNAVAILABLE")
    assert infra_requeue.requeue(root, [A], apply=True)["requeued"] == [A]
    assert _rows(ledger, A) == [("RELEASED", "UNAVAILABLE")]  # untouched by the tool
    cap = ExamCap(
        ledger,
        cadence={
            "capacity_gpu_lane_hours_per_day": 270.0,
            "rebuild_gpu_lane_hours": {"f02": 1.0},
            "lanes": 1,
            "measurement_digest": "sha256:" + "a" * 64,
            "class_record_digest": "sha256:" + "b" * 64,
        },
    )
    again = cap.reserve(
        hotkey=HOTKEY,
        challenge_id="f02",
        challenge_version="2.5",
        exam_key=EXAM,
        submission_id=A,
        block=7_200,
    )
    assert again == row
    with ledger._db() as db:
        assert db.execute("SELECT COUNT(*) FROM exam_graded").fetchone()[0] == 1


# ---------------------------------------------------------------- release


def test_release_frees_an_undelivered_counted_slot_through_exam_cap_and_keeps_history(
    tmp_path,
):
    from carbon.challenge_validator import exam_cap, infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    row = _row(ledger, A, "COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")
    dry = infra_requeue.release(root, A)
    assert dry["released"] == {
        "row": row,
        "prior_state": "COUNTED",
        "prior_status": "REQUIRED_LEG_MINIMUM_FAILED",
    }
    assert _rows(ledger, A) == [
        ("COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")
    ]  # dry: unchanged
    out = infra_requeue.release(root, A, apply=True)
    assert "refused" not in out and out["after"] == {
        "state": "RELEASED",
        "status": "FAILED_INFRA",
    }
    assert _rows(ledger, A) == [
        ("RELEASED", "FAILED_INFRA")
    ]  # the row stays, as history
    assert exam_cap.ExamCap(ledger).released_on_infra(
        hotkey=HOTKEY,
        challenge_id="f02",
        challenge_version="2.5",
        exam_key=EXAM,
        submission_id=A,
    )  # so the door runs the miner's resubmit as a fresh task
    log = (root / "auto-grade" / "requeued" / "releases.jsonl").read_text().splitlines()
    record = json.loads(log[0])
    assert (
        record["prior_state"] == "COUNTED"
        and record["reason"] == "result_not_delivered"
    )
    # no regrade: the marker stays, and the task can never be re-queued afterwards
    assert (root / "auto-grade" / "markers" / (A + ".json")).exists()
    assert infra_requeue.requeue(root, [A], apply=True)["refused"] == {
        A: "given_back_resubmit_runs_fresh"
    }
    # and a second release finds nothing to release
    assert infra_requeue.release(root, A, apply=True)["refused"] == (
        "release_no_single_counted_row"
    )


@pytest.mark.parametrize(
    "marker, code",
    [
        ("GRADED", "grade_delivered_or_unreadable"),
        ("CANDIDATE_FAILED", "grade_delivered_or_unreadable"),
        (None, "grade_not_finished"),
    ],
)
def test_release_refuses_when_the_grade_was_delivered_or_is_not_finished(
    tmp_path, marker, code
):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    if marker is not None:
        _failed(root, ledger, A, state=marker)
    _row(ledger, A, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")
    out = infra_requeue.release(root, A, apply=True)
    assert out["refused"] == code
    assert _rows(ledger, A) == [("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")]


@pytest.mark.parametrize(
    "shown_epoch, refused", [(20, True), (19, False), (None, True)]
)
def test_release_refuses_when_the_miners_ladder_shows_that_round(
    tmp_path, shown_epoch, refused
):
    """A Ladder document of the row's round is a delivered grade (the miner reads best/latest); one with no epoch
    written since the slot was reserved cannot be told apart, so it refuses too (fail closed).
    """
    from carbon.challenge_validator import infra_requeue
    from carbon.challenge_validator.ladder_store import LadderStore

    root, ledger = _root(tmp_path)
    LadderStore(ledger)  # its tables
    _failed(root, ledger, A)
    _row(ledger, A, "COUNTED", "REQUIRED_LEG_MINIMUM_FAILED", epoch=20)
    document = {"status": "NOT_SCORED"}
    if shown_epoch is not None:
        document["epoch"] = shown_epoch
    with ledger._db() as db:
        db.execute(
            "INSERT INTO ladder_feedback_v2(hotkey, challenge_id, evaluation_version, exam_key, "
            "challenge_version, best, latest, updated_ns) VALUES(?,'f02','2.5',?,'2.5',NULL,?,5)",
            (HOTKEY, EXAM, json.dumps(document)),
        )
    out = infra_requeue.release(root, A, apply=True)
    if refused:
        assert out["refused"] == "ladder_shows_this_round"
        assert _rows(ledger, A) == [("COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")]
    else:
        assert "refused" not in out
        assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]


def test_exam_cap_release_undelivered_gives_back_only_a_single_counted_row(tmp_path):
    from carbon.challenge_validator.exam_cap import ExamCap, ExamCapRefused

    _root_dir, ledger = _root(tmp_path)
    cap = ExamCap(ledger)
    for state, status in (
        ("RESERVED", None),
        ("RELEASED", "FAILED_INFRA"),
        ("RELEASED", "UNAVAILABLE"),
    ):
        _row(ledger, A, state, status)
        with pytest.raises(ExamCapRefused) as refused:
            cap.release_undelivered(A)
        assert refused.value.code == "release_no_single_counted_row"
        assert _rows(ledger, A) == [(state, status)]
        with ledger._db() as db:
            db.execute("DELETE FROM exam_graded")
    with pytest.raises(ExamCapRefused):
        cap.release_undelivered("")
    row = _row(ledger, A, "COUNTED", "MANDATORY_GATE_FAILED", epoch=9)
    done = cap.release_undelivered(A)
    assert done["row"] == row and done["epoch"] == 9
    assert (done["prior_state"], done["prior_status"]) == (
        "COUNTED",
        "MANDATORY_GATE_FAILED",
    )
    assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]


# ---------------------------------------------------------------- the operator command


def test_the_command_lists_requeues_and_releases(tmp_path, capsys):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    _failed(root, ledger, B)
    _row(ledger, B, "COUNTED", "REQUIRED_LEG_MINIMUM_FAILED")
    ids = tmp_path / "ids.txt"
    assert infra_requeue.main(["list", "--root", str(root), "--out", str(ids)]) == 0
    assert ids.read_text() == A + "\n"
    assert json.loads(capsys.readouterr().out)["eligible_counts"]["since_split"] == 1
    assert infra_requeue.main(["requeue", "--root", str(root), "--ids", str(ids)]) == 0
    assert json.loads(capsys.readouterr().out)["apply"] is False
    assert (
        infra_requeue.main(
            ["requeue", "--root", str(root), "--ids", str(ids), "--apply"]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["requeued"] == [A]
    assert infra_requeue.main(["release", "--root", str(root), "--id", A]) == 3
    assert json.loads(capsys.readouterr().out)["refused"] == "grade_not_finished"
    assert (
        infra_requeue.main(["release", "--root", str(root), "--id", B, "--apply"]) == 0
    )
    assert json.loads(capsys.readouterr().out)["after"]["status"] == "FAILED_INFRA"


# ---------------------------------------------------------------- Validator 15:53 must-fixes


def test_a_task_off_the_served_contract_or_pack_or_without_its_row_is_refused(tmp_path):
    """Pinned evaluation: only a task the door can still resolve, under what it serves now, is re-queued (else the
    grader would skip it silently as owned_task_unavailable)."""
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, contract="sha256:" + "9" * 64)
    _failed(
        root, ledger, B, stored=False
    )  # no row in the owner's store (the rs15-only 38)
    out = infra_requeue.requeue(root, [A, B], apply=True)
    # B cannot be re-run here: it is archived for the miner's resubmit, never graded by us (next test)
    assert out["refused"] == {A: "contract_not_served"}
    assert out["requeued"] == [] and out["archived"] == [B]
    other = tmp_path / "other"
    other.mkdir()
    root2, ledger2 = _root(other)
    _failed(
        root2, ledger2, C, pack="sha256:" + "b" * 64
    )  # owner bound to an older pack
    assert infra_requeue.requeue(root2, [C], apply=True)["refused"] == {
        C: "pack_not_served"
    }
    (root2 / "receiver-binding.json").unlink()
    assert infra_requeue.requeue(root2, [C])["refused"] == {
        C: "door_binding_unavailable"
    }


@pytest.mark.parametrize("state", ["GRADED", "CANDIDATE_FAILED"])
def test_a_resubmit_of_the_same_recipe_already_graded_is_not_graded_twice(
    tmp_path, state
):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    recipe = _recipe("same")
    _failed(root, ledger, A, recipe=recipe)  # stuck
    _failed(root, ledger, B, recipe=recipe, state=state)  # the same recipe, graded
    _failed(root, ledger, C, recipe=_recipe("same", n=2))  # another recipe
    out = infra_requeue.requeue(root, [A, C], apply=True)
    assert out["refused"] == {A: "same_recipe_already_graded"}
    assert out["requeued"] == [C]


def _cap(ledger):
    from carbon.challenge_validator.exam_cap import ExamCap

    return ExamCap(
        ledger,
        cadence={
            "capacity_gpu_lane_hours_per_day": 1.0,  # allowance a = 1 a day
            "rebuild_gpu_lane_hours": {"f02": 1.0},
            "lanes": 1,
            "measurement_digest": "sha256:" + "a" * 64,
            "class_record_digest": "sha256:" + "b" * 64,
        },
    )


def _reserve(cap, task, block):
    return cap.reserve(
        hotkey=HOTKEY,
        challenge_id="f02",
        challenge_version="2.5",
        exam_key=EXAM,
        submission_id=task,
        block=block,
    )


def _admission(cap, task, block):
    refusal = cap.admission_refusal(
        hotkey=HOTKEY,
        challenge_id="f02",
        challenge_version="2.5",
        exam_key=EXAM,
        submission_id=task,
        block=block,
    )
    return None if refusal is None else refusal["code"]


def test_a_requeued_grade_neither_spends_nor_is_refused_by_the_miners_round_or_day(
    tmp_path,
):
    """Validator 15:53 (3): a miner at its cap still gets the re-queued grade (accounted to the task's ORIGINAL
    epoch), its current round and day are unchanged, and the bypass is one-shot."""
    from carbon.challenge_validator import infra_requeue
    from carbon.challenge_validator.exam_cap import ExamCapRefused, epoch_of

    root, ledger = _root(tmp_path)
    original, now = 20 * 360, 25 * 360  # the stuck task's round, and today's (same day)
    _failed(root, ledger, A, block=original)
    cap = _cap(ledger)
    # the miner's own later grade in the stuck task's round: at its cap for that round and the day
    cap.settle(_reserve(cap, B, original + 1), "SCORED_DEVELOPMENT_CANDIDATE")
    with pytest.raises(ExamCapRefused):
        _reserve(cap, A, original)  # without the requeue the slot rules refuse it
    before = _admission(cap, C, now)
    assert before == "exam_daily_allowance_reached"
    assert infra_requeue.requeue(root, [A], apply=True)["requeued"] == [A]
    row = _reserve(cap, A, original)  # the grader's reserve for attempt 2
    cap.settle(row, "SCORED_DEVELOPMENT_CANDIDATE")
    with ledger._db() as db:
        assert db.execute(
            "SELECT epoch, state FROM exam_graded WHERE submission_id=?", (A,)
        ).fetchone() == (epoch_of(original), "COUNTED")
        assert db.execute(
            "SELECT reserved_ns IS NOT NULL FROM exam_requeues WHERE submission_id=?",
            (A,),
        ).fetchone() == (1,)
    assert _admission(cap, C, now) == before  # today: exactly as before
    assert (
        _reserve(cap, A, original) == row
    )  # a COUNTED row is reused, never re-bypassed
    assert cap.mark_requeued(A) is False  # never twice


def test_a_requeued_grade_inside_todays_window_uses_none_of_todays_allowance(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    original, now = 20 * 360, 21 * 360
    _failed(root, ledger, A, block=original)
    cap = _cap(ledger)
    assert _admission(cap, C, now) is None
    infra_requeue.requeue(root, [A], apply=True)
    cap.settle(_reserve(cap, A, original), "SCORED_DEVELOPMENT_CANDIDATE")
    assert _admission(cap, C, now) is None  # a = 1 a day, still free


def test_a_task_the_door_cannot_resolve_is_archived_so_a_resubmit_grades_once(tmp_path):
    """Validator 16:38: a task_row_missing task is archived (marker + evidence kept, mark_requeued), so the miner's
    resubmit of the same recipe (the SAME task id) is admitted and graded once, even at the miner's cap; a graded id
    is never archived."""
    from carbon.challenge_validator import auto_grade, infra_requeue

    root, ledger = _root(tmp_path)
    original, now = 20 * 360, 25 * 360
    _failed(
        root, ledger, A, stored=False, block=original
    )  # its row is not on this root
    _failed(root, ledger, C, stored=False, state="GRADED")
    cap = _cap(ledger)
    cap.settle(_reserve(cap, B, original + 1), "SCORED_DEVELOPMENT_CANDIDATE")
    assert _admission(cap, A, now) == "exam_daily_allowance_reached"  # before: refused
    listed = infra_requeue.scan(root)
    assert listed["archive_for_resubmit"] == [A] and listed["eligible_counts"] == {
        "before_split": 0,
        "since_split": 0,
    }
    out = infra_requeue.requeue(root, [A, C], apply=True)
    assert out["archived"] == [A] and out["requeued"] == []
    assert out["refused"] == {C: "marker_graded"}
    assert json.loads(_kept(root, A, "marker.json").read_text())["state"] == "FAILED"
    log = (root / "auto-grade" / "requeued" / "requeues.jsonl").read_text()
    assert json.loads(log.splitlines()[0])["kind"] == "archive"
    # the miner resubmits the same recipe: admitted at the cap, its row recreated, graded once
    assert _admission(cap, A, now) is None
    _store(root, A, _recipe(A))
    graded = []

    class Intake:
        adapter = SimpleNamespace(
            contract_digest=CONTRACT,
            ledger=SimpleNamespace(submitted_outcomes=lambda contract: (A, C)),
            owner=lambda submission_id: HOTKEY,
        )

        def retain_result(self, submission_id, **kwargs):
            graded.append(
                _reserve(cap, submission_id, original)
            )  # the real slot rule, bypassed once
            return {"entry_id": "sha256:" + "1" * 64}

    grader = auto_grade.AutoGrader(Intake(), root)
    assert grader.run_once() == (A, "GRADED") and len(graded) == 1
    assert grader.run_once() is None  # C stays graded, nothing else owed
    with ledger._db() as db:  # the bypass is spent: one grade per stuck task
        assert db.execute(
            "SELECT reserved_ns IS NOT NULL FROM exam_requeues WHERE submission_id=?",
            (A,),
        ).fetchone() == (1,)
    assert (
        _admission(cap, A, now) is None
    )  # its own row is held now; never a second bypass
    assert cap.mark_requeued(A) is False


def test_a_release_needs_no_task_row(tmp_path):
    """Validator 15:43: rtsk_61967e83 has NO direct task row; the release keys on the exam ledger row and reads only
    the marker and the ledger."""
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(
        root, ledger, A, arrived=False, stored=False
    )  # no OUTCOME row, no owner store
    assert not (root / "owners").exists()
    _row(ledger, A, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")
    out = infra_requeue.release(root, A, apply=True)
    assert "refused" not in out
    assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]


# ---------------------------------------------------------------- OWNER-RESUBMIT-SLOT-PROMISE-KEEP-01

POSTED, LIVE = "2026-11-04T20:00:00+00:00", "2026-11-05T02:00:00+00:00"
IN_WINDOW_NS = 1_793_829_600 * 10**9  # 4 Nov 22:00Z
AFTER_LIVE_NS = 1_793_862_000 * 10**9  # 5 Nov 07:00Z


def _graded_resubmit(ledger, root, task, *, at_ns=IN_WINDOW_NS, hotkey=HOTKEY):
    """A miner's resubmit that arrived at ``at_ns`` and was graded (COUNTED, marker GRADED)."""
    from carbon.challenge_validator.auto_grade import SCHEMA as MARKER

    with ledger._db() as db:
        db.execute(
            "INSERT INTO attempts(at_ns, kind, hotkey, contract_digest, receipt, submission_sha256, "
            "submission_id) VALUES(?, 'OUTCOME', ?, ?, ?, 'sha256:s', ?)",
            (at_ns, hotkey, CONTRACT, json.dumps({"block": 9_000}), task),
        )
        db.execute(
            "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, exam_key, kind, epoch, "
            "submission_id, state, status, reserved_ns, settled_ns) "
            "VALUES(?,'f02','2.5',?,'GRADED',25,?,'COUNTED','SCORED_DEVELOPMENT_CANDIDATE',1,2)",
            (hotkey, EXAM, task),
        )
    markers = root / "auto-grade" / "markers"
    markers.mkdir(parents=True, exist_ok=True)
    (markers / (task + ".json")).write_text(
        json.dumps({"schema": MARKER, "submission_id": task, "state": "GRADED"})
    )


def test_a_graded_resubmit_in_the_window_gets_its_slot_back_and_its_grade_stands(
    tmp_path,
):
    from carbon.challenge_validator import infra_requeue
    from carbon.challenge_validator.exam_cap import ExamCap

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)  # stuck (arrived 3 Nov)
    _graded_resubmit(ledger, root, B)  # graded resubmit inside the window
    _graded_resubmit(
        ledger, root, C, at_ns=AFTER_LIVE_NS
    )  # after A1 was LIVE: not covered
    _graded_resubmit(ledger, root, D, hotkey="5" + "2" * 47)  # another hotkey
    marker = (root / "auto-grade" / "markers" / (B + ".json")).read_bytes()
    dry = infra_requeue.return_slots(root, [A], window_start=POSTED, window_end=LIVE)
    assert dry["returned"] == {B: A} and _rows(ledger, B) == [
        ("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")
    ]
    out = infra_requeue.return_slots(
        root, [A], window_start=POSTED, window_end=LIVE, apply=True
    )
    assert out["returned"] == {B: A} and out["unmatched"] == [] and out["refused"] == {}
    assert _rows(ledger, B) == [("RELEASED", "SLOT_RETURNED")]  # slot back
    assert (root / "auto-grade" / "markers" / (B + ".json")).read_bytes() == marker
    assert _rows(ledger, C) == [("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")]
    assert _rows(ledger, D) == [("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")]
    ident = {
        "hotkey": HOTKEY,
        "challenge_id": "f02",
        "challenge_version": "2.5",
        "exam_key": EXAM,
        "submission_id": B,
    }
    cap = ExamCap(ledger)
    # NOT an infrastructure give-back: the door never runs the graded recipe again
    assert not cap.released_on_infra(**ident)
    # still graded for the door (same recipe refused, v4 GRADED), while the slot counts toward no limit
    assert cap.holds_slot(**ident)
    with ledger._db() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM exam_graded WHERE hotkey=? AND state IN ('RESERVED','COUNTED')",
            (HOTKEY,),
        ).fetchone() == (
            1,
        )  # only C, outside the window
    record = json.loads(
        (root / "auto-grade" / "requeued" / "slot-returns.jsonl").read_text()
    )
    assert (record["stuck"], record["resubmit"]) == (A, B)
    assert record["reason"] == "OWNER-RESUBMIT-SLOT-PROMISE-KEEP-01"
    # the row's outcome type survives the status overwrite, in the log (Validator 17:24 (1))
    assert (record["prior_state"], record["prior_status"]) == (
        "COUNTED",
        "SCORED_DEVELOPMENT_CANDIDATE",
    )
    # one slot per stuck task, never twice
    again = infra_requeue.return_slots(
        root, [A], window_start=POSTED, window_end=LIVE, apply=True
    )
    assert again["refused"] == {A: "already_returned"} and again["returned"] == {}


def test_one_slot_per_stuck_task_and_only_for_stuck_tasks(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    _failed(root, ledger, B, at_ns=SPLIT_NS + 2 * 10**9)
    _graded_resubmit(ledger, root, C)  # one resubmit for two stuck tasks
    _graded_resubmit(ledger, root, E, at_ns=IN_WINDOW_NS + 10**9)
    _failed(root, ledger, F, cause="WorkerFailure")  # not an A2 stuck task
    out = infra_requeue.return_slots(
        root, [A, B, F, "x"], window_start=POSTED, window_end=LIVE, apply=True
    )
    assert out["returned"] == {C: A, E: B}  # arrival order, each resubmit once
    assert out["refused"] == {F: "not_a_stuck_task", "x": "not_a_task_id"}
    (tmp_path / "two").mkdir()
    root2, ledger2 = _root(tmp_path / "two")
    _failed(root2, ledger2, A)
    _failed(root2, ledger2, B, at_ns=SPLIT_NS + 2 * 10**9)
    _graded_resubmit(ledger2, root2, C)
    out2 = infra_requeue.return_slots(
        root2, [A, B], window_start=POSTED, window_end=LIVE, apply=True
    )
    assert out2["returned"] == {C: A} and out2["unmatched"] == [B]
    assert infra_requeue.return_slots(root2, [A], window_start=LIVE, window_end=POSTED)[
        "refused"
    ] == {"window": "window_empty_or_reversed"}


def test_an_unreadable_owner_store_is_refused_never_archived(tmp_path):
    """Review finding 1: a store that exists but cannot be read now is NOT 'row missing': archiving it on a guess
    would skip the pack and same-recipe checks."""
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    store = root / "owners" / hashlib.sha256(HOTKEY.encode()).hexdigest() / "tasks"
    (store / "direct-tasks.sqlite3").write_bytes(b"not a database")
    out = infra_requeue.requeue(root, [A], apply=True)
    assert out["refused"] == {A: "owner_store_unreadable"} and out["archived"] == []
    assert (root / "auto-grade" / "markers" / (A + ".json")).exists()


def test_a_slot_returned_graded_row_is_never_requeued(tmp_path):
    """Review finding 3: a graded resubmit whose slot was returned is still graded: never handed back."""
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    _row(ledger, A, "RELEASED", "SLOT_RETURNED")
    assert infra_requeue.requeue(root, [A], apply=True)["refused"] == {
        A: "exam_row_graded"
    }


def test_a_counted_resubmit_without_a_delivered_grade_gets_no_slot_back(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A)
    _graded_resubmit(ledger, root, B)
    (
        root / "auto-grade" / "markers" / (B + ".json")
    ).unlink()  # COUNTED but no delivered grade
    out = infra_requeue.return_slots(
        root, [A], window_start=POSTED, window_end=LIVE, apply=True
    )
    assert out["returned"] == {} and out["unmatched"] == [A]
