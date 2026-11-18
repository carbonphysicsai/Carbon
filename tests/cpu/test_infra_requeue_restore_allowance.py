"""`infra_requeue restore-allowance` (Validator-2's ruling, 18 Nov 2026): a task that waited in Carbon's queue and was
then refused ``exam_daily_allowance_reached`` at its reservation (a GRADED marker keeping that code, NO exam row) is
handed back ONCE, uncharged, on its original arrival epoch and queue place, with every ``requeue`` door check.
"""

from __future__ import annotations

import json

from test_infra_requeue import (  # noqa: F401 - `served` is this module's autouse fixture too
    HOTKEY,
    _DoorIntake,
    _failed,
    _root,
    _row,
    _rows,
    served,
)

from carbon.challenge_validator import auto_grade, infra_requeue

A, B, C, D = ("rtsk_" + c * 64 for c in "abcd")
ALLOWANCE = infra_requeue.ALLOWANCE_CAUSE
RULING = "V2-ruling-18nov-allowance"
KEPT = ("auto-grade", "requeued")


def _refused_on_allowance(
    root, ledger, task, *, code=ALLOWANCE, state="GRADED", arrived=True
):
    """As the grader leaves such a task: arrived and stored, a GRADED marker keeping the code, no failure file, no
    exam row."""
    _failed(root, ledger, task, arrived=arrived)
    (root / "auto-grade" / "failures" / (task + ".txt")).unlink()
    marker = root / "auto-grade" / "markers" / (task + ".json")
    body = json.loads(marker.read_text())
    marker.write_text(json.dumps({**body, "state": state, "code": code}))


def _seq(ledger, task):
    with ledger._db() as db:
        return db.execute(
            "SELECT seq FROM attempts WHERE kind='OUTCOME' AND submission_id=? ORDER BY seq LIMIT 1",
            (task,),
        ).fetchone()[0]


def test_an_allowance_refused_task_is_dry_run_then_handed_back_once_and_grades(
    tmp_path,
):
    root, ledger = _root(tmp_path)
    _refused_on_allowance(root, ledger, A)
    seq = _seq(ledger, A)
    marker = root / "auto-grade" / "markers" / (A + ".json")
    dry = infra_requeue.restore_allowance(root, [A], ruling=RULING)
    assert dry["refused"] == {} and dry["restored"] == [A]
    plan = dry["plan"][A]
    assert plan["marker_before"] == "GRADED:" + ALLOWANCE
    assert plan["charged"] is False
    assert plan["bypass_attempt"] == 2
    assert plan["original_outcome_seq"] == seq
    assert plan["original_arrival"].endswith("Z")
    # a dry run moves nothing and arms nothing
    assert marker.exists() and not root.joinpath(*KEPT).exists()
    with ledger._db() as db:
        assert db.execute("SELECT COUNT(*) FROM exam_requeues").fetchone() == (0,)

    out = infra_requeue.restore_allowance(root, [A], ruling=RULING, apply=True)
    assert out["restored"] == [A]
    kept = root.joinpath(*KEPT)
    old = json.loads((kept / f"{A}.attempt-1.marker.json").read_text())
    assert (old["state"], old["code"]) == ("GRADED", ALLOWANCE)
    assert not marker.exists()
    lines = [
        json.loads(x)
        for x in (kept / infra_requeue.ALLOWANCE_RESTORES).read_text().splitlines()
    ]
    assert [(x["attempt"], x["kind"], x["cause"], x["ruling"]) for x in lines] == [
        (2, "restore-allowance", ALLOWANCE, RULING)
    ]
    # the one round/day bypass is armed; nothing was charged; the queue place is unchanged
    with ledger._db() as db:
        assert db.execute(
            "SELECT attempt, reserved_ns FROM exam_requeues WHERE submission_id=?", (A,)
        ).fetchall() == [(2, None)]
    assert _rows(ledger, A) == []
    assert _seq(ledger, A) == seq

    (root / "auto-grade" / "artifacts" / A).mkdir(mode=0o700, parents=True)
    intake = _DoorIntake(root, ledger, "sha256:" + "3" * 64)
    assert auto_grade.AutoGrader(intake, root).run_once() == (A, "GRADED")
    assert intake.graded == [A]


def test_a_second_apply_changes_nothing(tmp_path):
    root, ledger = _root(tmp_path)
    _refused_on_allowance(root, ledger, A)
    assert infra_requeue.restore_allowance(root, [A], ruling=RULING, apply=True)[
        "restored"
    ] == [A]
    log = root.joinpath(*KEPT) / infra_requeue.ALLOWANCE_RESTORES
    before = log.read_bytes()
    again = infra_requeue.restore_allowance(root, [A], ruling=RULING, apply=True)
    assert again["restored"] == [] and again["refused"] == {A: "already_restored"}
    assert log.read_bytes() == before


def test_only_an_allowance_refusal_with_no_exam_row_is_taken(tmp_path):
    root, ledger = _root(tmp_path)
    _refused_on_allowance(root, ledger, A, code="epoch_limit_reached")
    _refused_on_allowance(root, ledger, B, state="FAILED")
    _refused_on_allowance(root, ledger, C)
    _row(ledger, C, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")
    _refused_on_allowance(root, ledger, D)
    _row(ledger, D, "RELEASED", "SCORED_DEVELOPMENT_CANDIDATE")  # charged
    out = infra_requeue.restore_allowance(
        root, [A, B, C, D, "nope"], ruling=RULING, apply=True
    )
    assert out["restored"] == []
    assert out["refused"] == {
        A: "cause_not_allowance",
        B: "marker_failed",
        C: "exam_row_present",
        D: "exam_row_present",
        "nope": "not_a_task_id",
    }
    assert all(
        (root / "auto-grade" / "markers" / (t + ".json")).exists() for t in (A, B, C, D)
    )


def test_the_door_checks_still_apply(tmp_path):
    root, ledger = _root(tmp_path)
    _refused_on_allowance(root, ledger, A)
    _refused_on_allowance(root, ledger, B, arrived=False)  # no signed OUTCOME here
    out = infra_requeue.restore_allowance(root, [A, B], ruling=RULING)
    assert out["restored"] == [A]
    assert out["refused"] == {B: "not_submitted_at_this_door"}


def test_a_restore_needs_a_ruling_id(tmp_path):
    root, ledger = _root(tmp_path)
    _refused_on_allowance(root, ledger, A)
    out = infra_requeue.restore_allowance(root, [A], ruling="", apply=True)
    assert out["refused"] == {"*": "ruling_id_required"} and out["restored"] == []
    assert (root / "auto-grade" / "markers" / (A + ".json")).exists()


def test_the_command_takes_an_explicit_id_list(tmp_path, capsys):
    root, ledger = _root(tmp_path)
    _refused_on_allowance(root, ledger, A)
    ids = tmp_path / "ids.txt"
    ids.write_text(A + "\n")
    args = [
        "restore-allowance",
        "--root",
        str(root),
        "--ids",
        str(ids),
        "--ruling",
        RULING,
    ]
    assert infra_requeue.main(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["apply"] is False and out["restored"] == [A]
    assert infra_requeue.main([*args, "--apply"]) == 0
    assert json.loads(capsys.readouterr().out)["restored"] == [A]
    assert not (root / "auto-grade" / "markers" / (A + ".json")).exists()


def _spent_bypass(ledger, task, *, attempt=2, reserved_ns=5):
    with ledger._db() as db:
        db.execute(
            "INSERT INTO exam_requeues(submission_id, attempt, queued_ns, reserved_ns) VALUES(?,?,1,?)",
            (task, attempt, reserved_ns),
        )


def _kept_first_attempt(root, task):
    kept = root.joinpath(*KEPT)
    kept.mkdir(mode=0o700, parents=True, exist_ok=True)
    (kept / f"{task}.attempt-1.marker.json").write_text("{}")


def test_a_task_whose_spent_bypass_went_on_a_given_back_attempt_is_re_armed_and_grades(
    tmp_path,
):
    """V2's ruling (a), rtsk_c177bae9's shape: requeued once (attempt 1 kept, its bypass spent), the re-grade given
    back on infrastructure (RELEASED / FAILED_INFRA), then refused on the day. The bypass is re-armed for attempt 3.
    """
    root, ledger = _root(tmp_path)
    _refused_on_allowance(root, ledger, A)
    _row(ledger, A, "RELEASED", "FAILED_INFRA")
    _spent_bypass(ledger, A)
    _kept_first_attempt(root, A)
    dry = infra_requeue.restore_allowance(root, [A], ruling=RULING)
    assert dry["refused"] == {} and dry["restored"] == [A]
    plan = dry["plan"][A]
    assert (plan["bypass"], plan["bypass_attempt"], plan["given_back_rows"]) == (
        "re-armed",
        3,
        1,
    )
    out = infra_requeue.restore_allowance(root, [A], ruling=RULING, apply=True)
    assert out["restored"] == [A]
    kept = root.joinpath(*KEPT)
    assert json.loads((kept / f"{A}.attempt-2.marker.json").read_text())["code"] == (
        ALLOWANCE
    )
    with ledger._db() as db:
        assert db.execute(
            "SELECT attempt, reserved_ns FROM exam_requeues WHERE submission_id=?", (A,)
        ).fetchall() == [(3, None)]
    # its own row stays uncharged and no longer reads as a give-back (no fresh resubmit runs beside it)
    assert _rows(ledger, A) == [("RELEASED", "REQUEUED")]
    (root / "auto-grade" / "artifacts" / A).mkdir(mode=0o700, parents=True)
    intake = _DoorIntake(root, ledger, "sha256:" + "3" * 64)
    assert auto_grade.AutoGrader(intake, root).run_once() == (A, "GRADED")
    assert intake.graded == [A]


def test_any_other_row_or_bypass_shape_is_refused(tmp_path):
    root, ledger = _root(tmp_path)
    # a COUNTED row beside a given-back one (another exam key: one row per key)
    _refused_on_allowance(root, ledger, A)
    _row(ledger, A, "RELEASED", "FAILED_INFRA")
    with ledger._db() as db:
        db.execute(
            "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, exam_key, kind, epoch, "
            "submission_id, state, status, reserved_ns) "
            "VALUES(?,'f02','2.5','other-key','GRADED',20,?,'COUNTED','SCORED_DEVELOPMENT_CANDIDATE',1)",
            (HOTKEY, A),
        )
    _spent_bypass(ledger, A)
    # a charged RELEASED row
    _refused_on_allowance(root, ledger, B)
    _row(ledger, B, "RELEASED", "SLOT_RETURNED")
    # its bypass still armed (unspent)
    _refused_on_allowance(root, ledger, C)
    _row(ledger, C, "RELEASED", "FAILED_INFRA")
    _spent_bypass(ledger, C, reserved_ns=None)
    _kept_first_attempt(root, C)
    # a bypass row with no exam row it was spent on
    _refused_on_allowance(root, ledger, D)
    _spent_bypass(ledger, D)
    out = infra_requeue.restore_allowance(root, [A, B, C, D], ruling=RULING, apply=True)
    assert out["restored"] == []
    assert out["refused"] == {
        A: "exam_row_present",
        B: "exam_row_present",
        C: "bypass_still_armed",
        D: "exam_row_present",
    }
