"""Owner D14 (17 Nov, via Validator-2): "approved: return the exam slot for the 18 counted wall-stop tasks and the 4 build
failures in V2_RULING.md; their resubmits run uncharged".

`infra_requeue return-slot` gives each listed task's ONE COUNTED graded row back (`ExamCap.return_promised_slot`:
RELEASED / SLOT_RETURNED, the grade untouched), once, logged with the receipt id; ``--resubmits-of`` takes builds that
never graded and returns the slot of each one's owed resubmit (same hotkey, same recipe, arrived later) once it grades.
"""

from __future__ import annotations

import json

from test_infra_requeue import (  # noqa: F401 (the autouse served-contract fixture)
    SPLIT_NS,
    _arrived,
    _recipe,
    _root,
    _row,
    _rows,
    _store,
    served,
)

RULING = "V2-D14-SLOTS"
WALL, OTHER, FAILED_BUILD, RESUBMIT, PENDING, STRANGER = (
    "rtsk_" + c * 64 for c in "abcdef"
)


def _log(root):
    path = root / "auto-grade" / "requeued" / "slot-returns.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_a_counted_wall_stop_gets_its_slot_back_once_its_grade_untouched(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _arrived(ledger, WALL)
    _row(ledger, WALL, "COUNTED", "WORKER_WALL_LIMIT_REACHED")
    _arrived(ledger, OTHER)
    _row(ledger, OTHER, "RELEASED", "FAILED_INFRA")
    assert infra_requeue.return_slot(root, [WALL], ruling="")["refused"] == {
        "*": "ruling_id_required"
    }
    dry = infra_requeue.return_slot(root, [WALL, OTHER, "x"], ruling=RULING)
    assert dry["returned"] == [WALL]
    assert dry["rows"] == {
        WALL: [["COUNTED", "WORKER_WALL_LIMIT_REACHED"]],
        OTHER: [["RELEASED", "FAILED_INFRA"]],
    }
    assert dry["refused"] == {OTHER: "no_single_counted_row", "x": "not_a_task_id"}
    assert _rows(ledger, WALL) == [("COUNTED", "WORKER_WALL_LIMIT_REACHED")]  # dry
    out = infra_requeue.return_slot(root, [WALL], ruling=RULING, apply=True)
    assert out["returned"] == [WALL]
    assert _rows(ledger, WALL) == [("RELEASED", "SLOT_RETURNED")]
    (line,) = _log(root)
    assert (line["task"], line["ruling"], line["prior_status"]) == (
        WALL,
        RULING,
        "WORKER_WALL_LIMIT_REACHED",
    )
    assert infra_requeue.return_slot(root, [WALL], ruling=RULING, apply=True)[
        "refused"
    ] == {WALL: "already_returned"}


def test_a_build_that_never_graded_returns_its_owed_resubmits_slot(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    recipe = _recipe("the failed build")
    _arrived(
        ledger, STRANGER, at_ns=SPLIT_NS + 10**9
    )  # same recipe, but EARLIER: not a resubmit
    _store(root, STRANGER, recipe)
    _arrived(ledger, FAILED_BUILD, at_ns=SPLIT_NS + 2 * 10**9)
    _store(root, FAILED_BUILD, recipe)
    _arrived(ledger, RESUBMIT, at_ns=SPLIT_NS + 3 * 10**9)
    _store(root, RESUBMIT, recipe)
    _row(ledger, RESUBMIT, "COUNTED", "GRADED")
    _arrived(ledger, PENDING, at_ns=SPLIT_NS + 4 * 10**9)
    _store(root, PENDING, recipe)  # not graded yet
    out = infra_requeue.return_slot(
        root, [FAILED_BUILD], ruling=RULING, apply=True, resubmits_of=True
    )
    assert out["returned"] == [RESUBMIT]
    assert out["waiting"] == {FAILED_BUILD: [PENDING]}
    assert _rows(ledger, RESUBMIT) == [("RELEASED", "SLOT_RETURNED")]
    assert _log(root)[0]["resubmit_of"] == FAILED_BUILD
    # once the pending one grades COUNTED, the same command returns it too, and never RESUBMIT again
    _row(ledger, PENDING, "COUNTED", "GRADED")
    again = infra_requeue.return_slot(
        root, [FAILED_BUILD], ruling=RULING, apply=True, resubmits_of=True
    )
    assert again["returned"] == [PENDING]
    assert again["refused"] == {RESUBMIT: "already_returned"}


def test_a_build_with_no_resubmit_yet_waits(tmp_path):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _arrived(ledger, FAILED_BUILD)
    _store(root, FAILED_BUILD, _recipe("alone"))
    out = infra_requeue.return_slot(
        root, [FAILED_BUILD], ruling=RULING, resubmits_of=True
    )
    assert out["returned"] == [] and out["waiting"] == {FAILED_BUILD: []}


def test_the_return_slot_command(tmp_path, capsys):
    from carbon.challenge_validator import infra_requeue

    root, ledger = _root(tmp_path)
    _arrived(ledger, WALL)
    _row(ledger, WALL, "COUNTED", "WORKER_WALL_LIMIT_REACHED")
    ids = tmp_path / "ids.txt"
    ids.write_text(WALL + "\n")
    args = ["return-slot", "--root", str(root), "--ids", str(ids), "--ruling", RULING]
    assert infra_requeue.main(args) == 0
    assert json.loads(capsys.readouterr().out)["returned"] == [WALL]
    assert _rows(ledger, WALL) == [("COUNTED", "WORKER_WALL_LIMIT_REACHED")]
    assert infra_requeue.main([*args, "--apply"]) == 0
    assert _rows(ledger, WALL) == [("RELEASED", "SLOT_RETURNED")]
