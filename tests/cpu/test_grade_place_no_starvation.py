"""No door starves behind a frozen place (10 Nov 06:15, Deploy-B: on abf143d4 RB + Motor graded 17 times in 6 h and BT +
Cooling 0, with uploads waiting).

The place of a door in the host's waiting list (slow-tail F1a) is the acceptance time of its oldest unmarked submission.
A cancelled or orphaned task never gets a marker, so that place never moves; the door's two loops (rebuild and grade, one
door lock) alternate across the post-round stand-back and always show the oldest live waiter. Here two REAL door
processes share one host lock directory (waiters are keyed by pid, so two doors must be two processes), each with a
real on-disk `AttemptLedger` and `AutoGrader` giving its place:

- TWO OLD doors (as RB and Motor were): each one's oldest submission is dead (never marked); each runs a rebuild loop and
  a grade loop at the receiver's cadence ratio (rebuild every poll, grade every 5 polls), holding the host lock briefly
  each round. One old door alone leaves gaps a waiter slips through; two cover each other's gaps, as live;
- the YOUNG door: one live submission, accepted later; its grade round marks it.

The young door must grade within the window (before the fix it never did), and the old doors keep working. Linux only
(a waiter's identity is its /proc start time). Fixture ids and times only.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

POLL = 0.05
WINDOW_S = 6.0
CONTRACT = "sha256:" + "c" * 64
DEAD = "rtsk_" + "d" * 64
LIVE = "rtsk_" + "a" * 64

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="waiters are /proc identities"
)


def _door(role, host, root, seconds, out):
    """One door process (run by the test through ``python -c``)."""
    from carbon.challenge_validator import auto_grade, direct_intake
    from carbon.challenge_validator.ledger import AttemptLedger

    root = Path(root)
    (root / "ledger").mkdir(mode=0o700, parents=True, exist_ok=True)
    accepted = {"old": 1_000, "old2": 1_100, "young": 2_000}[
        role
    ]  # ns: the old doors' submissions are older
    ledger = AttemptLedger(root / "ledger" / "attempts.sqlite3", clock=lambda: accepted)
    sid = LIVE if role == "young" else DEAD
    ledger.record(
        SimpleNamespace(
            hotkey="5" + role[0] * 47,
            receipt={"sequence": 1, "digest": "d", "block": 1},
            contract_digest=CONTRACT,
        ),
        kind="OUTCOME",
        submission_id=sid,
    )
    intake = SimpleNamespace(
        adapter=SimpleNamespace(ledger=ledger, contract_digest=CONTRACT)
    )
    grader = auto_grade.AutoGrader(
        intake, root / "receiver"
    )  # no pool: the copy rule is not under test
    assert grader.oldest_pending_ns() == accepted
    stop = threading.Event()
    work = direct_intake._WorkLock(host, state_dir=root, stop=stop, poll_s=POLL)
    counts = {"advance": 0, "grade": 0, "graded": 0, "first_grade_s": None}
    started = time.monotonic()

    def rounds(kind, wait):
        while not stop.is_set():
            try:
                with work.taking(
                    kind,
                    has_work=(
                        (lambda: bool(grader.pending())) if kind == "grade" else None
                    ),
                    since=grader.oldest_pending_ns,
                ):
                    counts[kind] += 1
                    if role == "young" and kind == "grade":
                        for pending in grader.pending():
                            grader._write(
                                pending, "GRADED"
                            )  # the grade itself is not under test
                            counts["graded"] += 1
                            counts["first_grade_s"] = round(
                                time.monotonic() - started, 3
                            )
                    time.sleep(
                        POLL / 2
                    )  # a short round holding the host (a rebuild pass with nothing to build)
            except direct_intake.WorkDeclined:
                pass
            stop.wait(wait)

    loops = [threading.Thread(target=rounds, args=("grade", 5 * POLL), daemon=True)]
    if role != "young":
        loops.append(
            threading.Thread(target=rounds, args=("advance", POLL), daemon=True)
        )
    for loop in loops:
        loop.start()
    time.sleep(seconds)
    stop.set()
    for loop in loops:
        loop.join(5)
    Path(out).write_text(json.dumps(counts))


def _spawn(role, host, root, seconds, out):
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import test_grade_place_no_starvation as t; "
        "t._door(sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]), sys.argv[6])"
    )
    here = str(Path(__file__).parent)
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            code,
            here,
            role,
            str(host),
            str(root),
            str(seconds),
            str(out),
        ]
    )


def test_a_door_whose_oldest_item_never_settles_does_not_starve_a_younger_door(
    tmp_path,
):
    host = tmp_path / "host"
    host.mkdir(mode=0o700)
    olds = [
        _spawn(role, host, tmp_path / role, WINDOW_S + 1.0, tmp_path / f"{role}.json")
        for role in ("old", "old2")
    ]
    time.sleep(
        1.0
    )  # the old doors are already cycling when the young door's upload arrives
    young = _spawn("young", host, tmp_path / "young", WINDOW_S, tmp_path / "young.json")
    assert young.wait(WINDOW_S + 20) == 0
    for old in olds:
        assert old.wait(20) == 0
    counts = {
        role: json.loads((tmp_path / f"{role}.json").read_text())
        for role in ("old", "old2", "young")
    }
    assert counts["young"]["graded"] == 1, counts  # the younger door got its grade
    assert (
        tmp_path / "young" / "receiver" / "auto-grade" / "markers" / f"{LIVE}.json"
    ).exists()
    for role in ("old", "old2"):
        assert (
            counts[role]["advance"] > 0 and counts[role]["grade"] > 0
        ), counts  # they kept working
        assert not (
            tmp_path / role / "receiver" / "auto-grade" / "markers" / f"{DEAD}.json"
        ).exists()
