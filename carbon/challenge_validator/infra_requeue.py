"""One-shot operator tools for the REG-UNAVAILABLE incident (TL 4 Nov 03:14-03:44; Validator 03:15 and 05:17).

A registration snapshot that went stale under chain 429s failed tasks when the receiver opened the miner's provider
(`direct_receiver.OwnerProviders._open`, ``direct_provider_registration_unavailable``), BEFORE anything was retained,
reserved or graded. `auto_grade._give_back` then raised as well (fixed in A1), so each task kept a FAILED marker
(``...:unrecorded``) and no exam row. Those tasks are Carbon's infrastructure failures: never graded, never charged.

    python -m carbon.challenge_validator.infra_requeue list    --root RECEIVER_ROOT [--out IDS.txt]
    python -m carbon.challenge_validator.infra_requeue requeue --root RECEIVER_ROOT --ids IDS.txt [--apply]
    python -m carbon.challenge_validator.infra_requeue release --root RECEIVER_ROOT --id rtsk_... [--apply]

``list`` (read-only) regenerates the task list from the door itself, never from a frozen file: every FAILED task
that ``requeue`` would accept, with the time it arrived (split at ``--split``, default 3 Nov 00:00Z), the counts of
the FAILED tasks it would refuse by reason, and, per accepted task, the round/day limit its regrade would meet now
(``limit_preview``: the slot rule `ExamCap.reserve` still applies; Validator ruling pending).

``requeue``: each listed task whose marker is FAILED, whose private evidence (``auto-grade/failures/<id>.txt``) names
``direct_provider_registration_unavailable``, that arrived at this door and has no exam row other than an
uncharged, not-given-back one, goes back to the receiver's own auto-grader ONCE: its marker and failure evidence move
to ``auto-grade/requeued/<id>.attempt-1.{marker.json,failure.txt}`` (kept, never deleted), a line goes to
``requeued/requeues.jsonl``, and the next tick grades it as attempt 2 over the same retained bytes and task identity.
`ExamCap.reserve` reuses the task's own row if it has one, so no new slot. REFUSED per task: any other marker
(GRADED, CANDIDATE_FAILED: a graded task is NEVER re-queued), any other cause, a second requeue, a COUNTED or RESERVED
row, and a row already given back as FAILED_INFRA (the door then runs the miner's resubmit as a fresh task, so a
requeue could grade the same recipe twice).

``release``: one task whose COUNTED grade never reached the miner (its marker is FAILED, so its feedback shows no grade,
and the miner's Ladder shows nothing from that round) is given back through the receiver's own
`ExamCap.release_undelivered`: RELEASED / FAILED_INFRA, the prior state written to ``requeued/releases.jsonl`` with its
reason; no regrade, no rescore. REFUSED when the grade was delivered (a GRADED or CANDIDATE_FAILED marker, or a Ladder
document of that round), when the task has no marker yet, or when the row is not COUNTED.

Without ``--apply`` nothing changes. Each prints one JSON document: task ids, codes and counts only (no hotkey, path or
score). Runs with the door up: sqlite writes go through the ledger's own transactions, and the marker move is the
single commit point the grader observes.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

CAUSE = "direct_provider_registration_unavailable"
SCHEMA = "carbon.challenge-validator.infra-requeue.v2"
#: The first stuck task the TL found (1 Nov 14:24Z) predates this; the Validator's 43 are the ones since 3 Nov 00:00Z.
DEFAULT_SPLIT = "2026-11-03T00:00:00Z"
_TASK = re.compile(r"rtsk_[0-9a-f]{64}")
_ATTEMPT = 1  # the attempt that failed; a requeue grades attempt 2, once


def _paths(root, task):
    base = Path(root) / "auto-grade"
    kept = base / "requeued"
    return {
        "marker": base / "markers" / (task + ".json"),
        "failure": base / "failures" / (task + ".txt"),
        "kept_marker": kept / f"{task}.attempt-{_ATTEMPT}.marker.json",
        "kept_failure": kept / f"{task}.attempt-{_ATTEMPT}.failure.txt",
    }


def _marker(path):
    """The marker's state, None when there is none, or UNREADABLE."""
    from .auto_grade import SCHEMA as MARKER_SCHEMA

    if path.is_symlink():
        return "UNREADABLE"
    try:
        body = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return "UNREADABLE"
    if type(body) is not dict or body.get("schema") != MARKER_SCHEMA:
        return "UNREADABLE"
    return str(body.get("state"))


def _cause(paths):
    for name in ("failure", "kept_failure"):
        try:
            text = paths[name].read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        return CAUSE in text
    return False


def _ledger(root):
    from .exam_cap import ExamCap
    from .ledger import AttemptLedger

    ledger = AttemptLedger(Path(root) / "attempts.sqlite3")
    return ledger, ExamCap(ledger)


def _arrival(db, task):
    """``(at_ns, block, hotkey)`` of the task's first signed OUTCOME at this door, or None."""
    row = db.execute(
        "SELECT at_ns, receipt, hotkey FROM attempts WHERE kind='OUTCOME' AND submission_id=? "
        "ORDER BY seq LIMIT 1",
        (task,),
    ).fetchone()
    if row is None:
        return None
    try:
        block = json.loads(row[1]).get("block")
    except (TypeError, ValueError, AttributeError):
        block = None
    return row[0], (block if type(block) is int else None), row[2]


def _rows(db, task):
    return db.execute(
        "SELECT id, state, status, hotkey, challenge_id, exam_key, epoch, reserved_ns "
        "FROM exam_graded WHERE submission_id=? AND kind='GRADED'",
        (task,),
    ).fetchall()


def _requeue_refusal(root, db, task):
    """None when ``requeue`` accepts the task, else its refusal code (read-only)."""
    if type(task) is not str or not _TASK.fullmatch(task):
        return "not_a_task_id"
    paths = _paths(root, task)
    if paths["kept_marker"].exists() or paths["kept_marker"].is_symlink():
        return "already_requeued"
    state = _marker(paths["marker"])
    if state is None:
        return "no_marker"
    if state != "FAILED":
        return "marker_" + state.lower()
    if not _cause(paths):
        return "cause_not_registration_unavailable"
    if _arrival(db, task) is None:
        return "not_submitted_at_this_door"
    for _id, row_state, status, *_rest in _rows(db, task):
        if row_state in ("COUNTED", "RESERVED"):
            return "exam_row_counted_or_reserved"
        if status == "FAILED_INFRA":
            return "given_back_resubmit_runs_fresh"
    return None


def _limit_preview(cap, db, task):
    """The limit refusal `ExamCap.reserve` would give this task's regrade now, None, or ``unknown``."""
    try:
        challenges = [
            row[0]
            for row in db.execute(
                "SELECT DISTINCT challenge_id FROM exam_graded"
            ).fetchall()
        ]
        arrival = _arrival(db, task)
        if len(challenges) != 1 or arrival is None or arrival[1] is None:
            return "unknown"
        from .exam_cap import epoch_of

        return cap._limit_refusal(
            db, arrival[2], challenges[0], task, epoch_of(arrival[1]), cap.cadence()
        )
    except Exception:  # noqa: BLE001 - a preview never blocks the list
        return "unknown"


def _iso(at_ns):
    return (
        datetime.datetime.fromtimestamp(at_ns / 1e9, tz=datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def scan(root, *, split=DEFAULT_SPLIT):
    """Read-only: the tasks ``requeue`` accepts now, grouped at ``split``, and the refusal counts."""
    edge = datetime.datetime.fromisoformat(split)
    edge_ns = int(edge.timestamp()) * 1_000_000_000
    markers = Path(root) / "auto-grade" / "markers"
    failed = sorted(
        path.stem
        for path in markers.glob("rtsk_*.json")
        if _TASK.fullmatch(path.stem) and _marker(path) == "FAILED"
    )
    ledger, cap = _ledger(root)
    out = {
        "schema": SCHEMA,
        "action": "list",
        "split": split,
        "failed_markers": len(failed),
        "eligible": {"before_split": [], "since_split": []},
        "arrived": {},
        "limit_preview": {},
        "refused_counts": {},
    }
    with ledger._db() as db:
        for task in failed:
            code = _requeue_refusal(root, db, task)
            if code is not None:
                out["refused_counts"][code] = out["refused_counts"].get(code, 0) + 1
                continue
            at_ns = _arrival(db, task)[0]
            group = "since_split" if at_ns >= edge_ns else "before_split"
            out["eligible"][group].append(task)
            out["arrived"][task] = _iso(at_ns)
            preview = _limit_preview(cap, db, task)
            if preview is not None:
                out["limit_preview"][task] = preview
    out["eligible_counts"] = {k: len(v) for k, v in out["eligible"].items()}
    return out


def requeue(root, tasks, *, apply=False, clock=time.time_ns):
    """``{"requeued": [...], "refused": {task: code}}`` for each task (see the module text)."""
    out = {
        "schema": SCHEMA,
        "action": "requeue",
        "apply": apply,
        "requeued": [],
        "refused": {},
    }
    ledger, _cap = _ledger(root)
    for task in tasks:
        with ledger._db() as db:
            code = _requeue_refusal(root, db, task)
        if code is not None:
            out["refused"][task] = code
            continue
        if apply:
            paths = _paths(root, task)
            paths["kept_marker"].parent.mkdir(mode=0o700, exist_ok=True)
            if paths["failure"].exists():
                # Evidence first, so attempt 2 can write its own (create-only) failure file.
                os.replace(paths["failure"], paths["kept_failure"])
            # The commit point: with no marker, the grader's next tick takes the task.
            os.replace(paths["marker"], paths["kept_marker"])
            with open(
                paths["kept_marker"].parent / "requeues.jsonl", "a", encoding="utf-8"
            ) as log:
                log.write(
                    json.dumps(
                        {"task": task, "attempt": _ATTEMPT + 1, "at_ns": int(clock())},
                        sort_keys=True,
                    )
                    + "\n"
                )
        out["requeued"].append(task)
    return out


def _ladder_shows_round(db, row):
    """Whether the miner's Ladder may show a grade from this row's round: a document of that epoch, or one written
    since the slot was reserved that names no epoch (fail closed)."""
    _id, _state, _status, hotkey, challenge_id, exam_key, epoch, reserved_ns = row
    for table in ("ladder_feedback_v2", "ladder_feedback"):
        try:
            found = db.execute(
                f"SELECT best, latest, updated_ns FROM {table} WHERE hotkey=? AND "
                "challenge_id=? AND exam_key=?",
                (hotkey, challenge_id, exam_key),
            ).fetchall()
        except sqlite3.OperationalError:  # no Ladder table: nothing was shown
            continue
        for best, latest, updated_ns in found:
            for raw in (best, latest):
                if raw is None:
                    continue
                try:
                    document = json.loads(raw)
                except ValueError:
                    return True
                shown = document.get("epoch") if type(document) is dict else None
                if shown == epoch:
                    return True
                if shown is None and updated_ns >= reserved_ns:
                    return True
    return False


def release(root, task, *, apply=False, clock=time.time_ns):
    """Give back one COUNTED slot whose grade was never delivered (see the module text)."""
    out = {"schema": SCHEMA, "action": "release", "apply": apply, "task": task}
    if type(task) is not str or not _TASK.fullmatch(task):
        return {**out, "refused": "not_a_task_id"}
    state = _marker(_paths(root, task)["marker"])
    if state != "FAILED":
        return {
            **out,
            "refused": (
                "grade_not_finished"
                if state is None
                else "grade_delivered_or_unreadable"
            ),
        }
    ledger, cap = _ledger(root)
    with ledger._db() as db:
        counted = [row for row in _rows(db, task) if row[1] == "COUNTED"]
        if len(counted) != 1:
            return {**out, "refused": "release_no_single_counted_row"}
        if _ladder_shows_round(db, counted[0]):
            return {**out, "refused": "ladder_shows_this_round"}
    row = counted[0]
    before = {"row": row[0], "prior_state": row[1], "prior_status": row[2]}
    if not apply:
        return {**out, "released": before}
    from .exam_cap import ExamCapRefused

    try:
        done = cap.release_undelivered(task)
    except ExamCapRefused as refused:
        return {**out, "refused": refused.code}
    record = {
        "task": task,
        "row": done["row"],
        "prior_state": done["prior_state"],
        "prior_status": done["prior_status"],
        "state": "RELEASED",
        "status": "FAILED_INFRA",
        "reason": "result_not_delivered",
        "at_ns": int(clock()),
    }
    directory = _paths(root, task)["kept_marker"].parent
    directory.mkdir(mode=0o700, exist_ok=True)
    with open(directory / "releases.jsonl", "a", encoding="utf-8") as log:
        log.write(json.dumps(record, sort_keys=True) + "\n")
    return {
        **out,
        "released": before,
        "after": {"state": "RELEASED", "status": "FAILED_INFRA"},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    listing = sub.add_parser("list")
    listing.add_argument("--root", type=Path, required=True)
    listing.add_argument("--split", default=DEFAULT_SPLIT)
    listing.add_argument(
        "--out", type=Path, help="write the since-split ids, one per line"
    )
    one = sub.add_parser("requeue")
    one.add_argument("--root", type=Path, required=True)
    one.add_argument("--ids", type=Path, required=True)
    one.add_argument("--apply", action="store_true")
    two = sub.add_parser("release")
    two.add_argument("--root", type=Path, required=True)
    two.add_argument("--id", required=True)
    two.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "list":
        out = scan(args.root, split=args.split)
        if args.out is not None:
            args.out.write_text(
                "".join(task + "\n" for task in out["eligible"]["since_split"])
            )
    elif args.cmd == "requeue":
        tasks = [
            line.strip() for line in args.ids.read_text().splitlines() if line.strip()
        ]
        out = requeue(args.root, tasks, apply=args.apply)
    else:
        out = release(args.root, args.id, apply=args.apply)
    print(json.dumps(out, sort_keys=True))
    return 3 if args.cmd == "release" and out.get("refused") else 0


if __name__ == "__main__":
    sys.exit(main())
