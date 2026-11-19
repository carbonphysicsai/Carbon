"""V2-OWED-NOW (19 Nov 2026), class (d): ``infra_requeue regrade --ruling``, one uncharged re-grade at the original place.

The live shapes (Live ops, OWED_CLASSIFY_20261119T0215Z):
- rtsk_0de4b0ba + cc907910: same-recipe twins, both FAILED and given back: ONE grade owed, the other then settles;
- rtsk_92b9c1c6 / ce773a20: FAILED, given back, their only same-recipe tasks EARLIER and never graded;
- rtsk_521d5609 / 240250af / 6f108573: released by ``release`` (slot back), grade still owed;
- rtsk_2f56796b: FAILED ``reclassed_not_the_candidates`` (``reclass``), first attempt;
- rtsk_5b6f627b: GRADED ``subset_repeat_incomplete``, row RELEASED / UNAVAILABLE (V2: ours, slot back + re-grade).
"""

from __future__ import annotations

import json
import sqlite3

from test_infra_requeue import (  # noqa: F401 (the autouse served-contract fixture)
    SPLIT_NS,
    A,
    B,
    C,
    D,
    _arrived,
    _recipe,
    _root,
    _row,
    _rows,
    _store,
    served,
)
from test_infra_requeue_rearm import CUSTODY, _failure, _marker

RULING = "V2-OWED-NOW-20261119"
E = "rtsk_" + "e" * 64
F = "rtsk_" + "f" * 64


def _owed(
    root,
    ledger,
    task,
    recipe,
    *,
    at_ns=SPLIT_NS + 10**9,
    state="FAILED",
    code=CUSTODY,
    row=("RELEASED", "FAILED_INFRA"),
):
    _marker(root, task, state, code, "retry_scheduled")
    _failure(root, task, code)
    _arrived(ledger, task, at_ns=at_ns)
    _store(root, task, recipe)
    if row is not None:
        _row(ledger, task, *row)


def _log(root, name, task):
    directory = root / "auto-grade" / "requeued"
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / name, "a", encoding="utf-8") as log:
        log.write(json.dumps({"task": task, "state": "RELEASED"}) + "\n")


def _bypass(root, task):
    return sqlite3.connect(root / "attempts.sqlite3").execute(
        "SELECT attempt, reserved_ns FROM exam_requeues WHERE submission_id=?", (task,)
    ).fetchall()


def test_one_of_two_failed_twins_is_regraded_and_the_other_then_waits(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    recipe = _recipe("twins")
    _owed(root, ledger, A, recipe, at_ns=SPLIT_NS + 1 * 10**9)
    _owed(root, ledger, B, recipe, at_ns=SPLIT_NS + 2 * 10**9)
    dry = infra_requeue.regrade(root, [A], ruling=RULING)
    assert dry["regraded"] == [A]
    assert dry["twins"] == {A: [{"task": B, "marker": "FAILED"}]}
    # a dry run moves nothing
    assert (root / "auto-grade/markers" / (A + ".json")).exists()
    out = infra_requeue.regrade(root, [A], ruling=RULING, apply=True)
    assert out["regraded"] == [A]
    # the grader takes it next, on its own row, holding no slot
    assert not (root / "auto-grade/markers" / (A + ".json")).exists()
    assert _rows(ledger, A) == [("RELEASED", "REQUEUED")]
    assert _bypass(root, A) == [(2, None)]  # its one uncharged reservation
    again = infra_requeue.regrade(root, [A, B], ruling=RULING, apply=True)
    assert again["regraded"] == []
    assert again["refused"] == {
        A: "already_regraded",
        B: "same_recipe_regrade_pending",
    }


def test_earlier_never_graded_twins_do_not_hold_a_regrade(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    recipe = _recipe("earlier")
    _owed(root, ledger, E, recipe, at_ns=SPLIT_NS + 1 * 10**9)
    _store(root, F, recipe)  # stored, never graded, never handed back
    _owed(root, ledger, A, recipe, at_ns=SPLIT_NS + 3 * 10**9)
    assert infra_requeue.requeue(root, [A])["refused"] == {
        A: "given_back_rerun_exists"
    }
    out = infra_requeue.regrade(root, [A], ruling=RULING, apply=True)
    assert out["regraded"] == [A] and out["refused"] == {}


def test_released_and_reclassed_first_attempts_are_regraded(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _owed(root, ledger, A, _recipe("released"))
    _log(root, "releases.jsonl", A)
    _owed(root, ledger, B, _recipe("reclassed"), code=infra_requeue.RECLASSED_CODE)
    _log(root, "reclass.jsonl", B)
    assert infra_requeue.requeue(root, [A])["refused"] == {
        A: "released_not_regraded"
    }
    assert infra_requeue.rearm(root, [B], ruling=RULING)["refused"] == {
        B: "not_rearmed_before"
    }
    out = infra_requeue.regrade(root, [A, B], ruling=RULING, apply=True)
    assert out["regraded"] == [A, B]
    assert out["causes"] == {A: CUSTODY, B: infra_requeue.RECLASSED_CODE}
    lines = (root / "auto-grade/requeued/regrades.jsonl").read_text().splitlines()
    assert [json.loads(line)["task"] for line in lines] == [A, B]
    assert {json.loads(line)["ruling"] for line in lines} == {RULING}


def test_an_incomplete_grade_ruled_ours_is_regraded_uncharged(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _owed(
        root,
        ledger,
        A,
        _recipe("subset"),
        state="GRADED",
        code="subset_repeat_incomplete",
        row=("RELEASED", "UNAVAILABLE"),
    )
    out = infra_requeue.regrade(root, [A], ruling=RULING, apply=True)
    assert out["regraded"] == [A]
    assert (root / "auto-grade/requeued" / f"{A}.attempt-1.marker.json").exists()
    assert not (root / "auto-grade/markers" / (A + ".json")).exists()
    assert _rows(ledger, A) == [("RELEASED", "UNAVAILABLE")]  # holds no slot
    assert _bypass(root, A) == [(2, None)]


def test_regrade_keeps_the_checks_that_protect_the_grade(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    # the candidate's own outcome
    _owed(root, ledger, A, _recipe("candidate"), state="CANDIDATE_FAILED")
    # its own row still counted
    _owed(root, ledger, B, _recipe("counted"), row=("COUNTED", "SCORED"))
    # a same-recipe twin already graded
    graded = _recipe("graded-twin")
    _owed(root, ledger, C, graded)
    _store(root, E, graded)
    _marker(root, E, "GRADED", None, None)
    # a same-recipe twin holding a slot
    held = _recipe("held-twin")
    _owed(root, ledger, D, held)
    _owed(root, ledger, F, held, at_ns=SPLIT_NS + 5 * 10**9, row=("RESERVED", None))
    out = infra_requeue.regrade(root, [A, B, C, D], ruling=RULING, apply=True)
    assert out["regraded"] == []
    assert out["refused"] == {
        A: "marker_candidate_failed",
        B: "exam_row_counted_or_reserved",
        C: "same_recipe_already_graded",
        D: "same_recipe_slot_held",
    }
    assert infra_requeue.regrade(root, [A], ruling="")["refused"] == {
        "*": "ruling_id_required"
    }


def test_the_regrade_command(tmp_path, capsys):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _owed(root, ledger, A, _recipe("cli"))
    _log(root, "releases.jsonl", A)
    ids = tmp_path / "ids.txt"
    ids.write_text(A + "\n")
    args = ["regrade", "--root", str(root), "--ids", str(ids), "--ruling", RULING]
    assert infra_requeue.main(args) == 0
    assert json.loads(capsys.readouterr().out)["regraded"] == [A]
    assert (root / "auto-grade/markers" / (A + ".json")).exists()  # dry run
    assert infra_requeue.main([*args, "--apply"]) == 0
    assert not (root / "auto-grade/markers" / (A + ".json")).exists()
    assert _rows(ledger, A) == [("RELEASED", "REQUEUED")]
