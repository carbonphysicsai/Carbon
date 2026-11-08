"""One-shot operator tools for the REG-UNAVAILABLE incident (TL 4 Nov 03:14-03:44; Validator 03:15, 05:17, 15:38, 15:43,
15:53).

A registration snapshot that went stale under chain 429s failed tasks when the receiver opened the miner's provider
(`direct_receiver.OwnerProviders._open`, ``direct_provider_registration_unavailable``), BEFORE anything was retained,
reserved or graded. `auto_grade._give_back` then raised as well (fixed in A1), so each task kept a FAILED marker
(``...:unrecorded``) and no exam row. Those tasks are Carbon's infrastructure failures: never graded, never charged.

    python -m carbon.challenge_validator.infra_requeue list    --root RECEIVER_STATE [--out IDS.txt]
    python -m carbon.challenge_validator.infra_requeue requeue --root RECEIVER_STATE --ids IDS.txt [--apply]
    python -m carbon.challenge_validator.infra_requeue release --root RECEIVER_STATE --id rtsk_... [--apply]
    python -m carbon.challenge_validator.infra_requeue keep-evaluation --root RECEIVER_STATE --ids IDS.txt [--apply]

``list`` (read-only) regenerates the task list from the door itself, BY CRITERION, never from a frozen file: every
FAILED task ``requeue`` would accept (with its arrival time, grouped at ``--split``, 3 Nov 00:00Z by default, for
reading only: the criterion has no date), the FAILED tasks it refuses counted by reason, and the cost: the count and
the estimated grade hours (count x this door's own mean wall per counted grade, with its sample size). Grades run one
at a time per door, interleaved with live submissions in task-id order.

``requeue``: a listed task goes back to the receiver's own auto-grader ONCE when ALL hold:
- its marker is FAILED and its private evidence (``auto-grade/failures/<id>.txt``) names the registration cause;
- it arrived at this door, under the contract this door serves (``contract_not_served``);
- its exam row, if any, is neither COUNTED nor RESERVED (a graded task is NEVER re-queued) nor already given back as
  FAILED_INFRA while a task of the same recipe exists (``given_back_rerun_exists``; with none, it is re-queued and
  `ExamCap.mark_requeued` stops the door from also running a resubmit of it fresh; a given-back task with no row is
  ``given_back_resubmit_runs_fresh``), and a task ``release`` gave back (``released_not_regraded``);
- its task row is in its owner's store and that owner is bound to the pack this door serves now (``task_row_missing``,
  ``pack_not_served``: pinned evaluation; otherwise the grader could not resolve it and would skip it silently);
- no other task of the same owner with the SAME recipe is GRADED or CANDIDATE_FAILED here (``same_recipe_already_graded``:
  a resubmit already graded, never a double grade).
Then `ExamCap.mark_requeued` records it (its one grade neither spends nor is refused by the miner's current round or day,
and stays accounted to its ORIGINAL arrival epoch), its marker and failure evidence move to
``auto-grade/requeued/<id>.attempt-1.{marker.json,failure.txt}`` (kept), a line goes to ``requeued/requeues.jsonl``, and
the next tick grades it as attempt 2 over the same retained bytes and task identity, reusing its own row (no new slot).
A first attempt that got as far as its private evaluation files (``auto-grade/artifacts/<id>.evaluation/``: the pack
binding first, all create-only, bound to that attempt's entry and state) has that directory kept beside them as
``<id>.attempt-1.evaluation/`` in the same move, so attempt 2 writes its own (TL 4 Nov 23:34: without it every such
re-run failed ``evaluation_pack_binding_unavailable``).

``keep-evaluation`` (TL 4 Nov 23:34) does that one step for a task ``requeue`` handed back before it did so itself: the
task was re-queued, attempt 2 has not been graded yet (no marker, no RESERVED row), and every file in its evaluation
directory is older than its requeue line (so all of it is attempt 1's). Run it while the door's re-run pickups are
paused: a grade that started in the same instant would fail as before, uncharged. A re-queued task whose attempt 2
already FAILED this way is refused (``failed_again_use_requeue``); ``requeue`` takes it instead, once more:

``requeue`` also takes, ONCE, a task whose A2 re-run (attempt 2) FAILED on attempt 1's binding (Lead 4 Nov 23:5x; the
cause ``evaluation_pack_binding_unavailable`` in attempt 2's own failure evidence): its evaluation directory must hold
attempt 1's files alone (every file older than the attempt-2 requeue line: attempt 2 wrote nothing, so nothing of it is
lost), and every other check above holds (attempt 2's give-back left a RELEASED / FAILED_INFRA row, so a rerun of the
same recipe refuses ``given_back_rerun_exists``). Attempt 2's marker and failure are kept as ``<id>.attempt-2.*``,
attempt 1's directory as ``<id>.attempt-1.evaluation/``, and `ExamCap.mark_requeued` re-arms the task's one limit
bypass for attempt 3. A task re-queued twice is never re-queued again (``already_requeued``).

``requeue`` ARCHIVES instead (Validator 4 Nov 16:38) a task that passes every check up to the contract but whose row
is not in its owner's store on this root (``task_row_missing``: the rs15-only rows): Carbon cannot re-run it, so the
miner must RESUBMIT the same recipe, which recreates the SAME task id; without the archive the old FAILED marker would
make the grader skip that resubmit forever. The archive is the same one-shot move and `ExamCap.mark_requeued` (the
resubmit grades once without spending, or being refused by, the miner's round or day), logged as ``archive``.

``release``: one task whose COUNTED grade never reached the miner (its marker is FAILED, so its feedback shows no grade,
and the miner's Ladder shows nothing from that round) is given back through the receiver's own
`ExamCap.release_undelivered`, keyed on the exam ledger row (it needs no task row): RELEASED / FAILED_INFRA, the prior
state written to ``requeued/releases.jsonl`` with its reason; no regrade, no rescore. REFUSED when the grade was
delivered (a GRADED or CANDIDATE_FAILED marker, or a Ladder document of that round), when the task has no marker yet,
or when the row is not COUNTED. Whether the result was filed in the pool/KOTH store is read by the TL before a release.

Without ``--apply`` nothing changes. Each prints one JSON document: task ids, codes and counts only (no hotkey, path or
score). Runs with the door up: sqlite writes go through the ledger's own transactions, the owner stores are opened
read-only, and the marker move is the single commit point the grader observes.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
import time
from pathlib import Path

#: The Carbon-side causes a stuck task may be re-queued for, by its private failure evidence: the stale registration
#: snapshot (REG-UNAVAILABLE) and a construction overlay the door switch did not carry (Deploy 4 Nov 20:29: overlays/
#: was left behind, so the retained source could not be re-read; uncharged, raised before any reservation).
CAUSES = (
    "direct_provider_registration_unavailable",
    "source_overlay_unavailable",
)
CAUSE = CAUSES[0]
SCHEMA = "carbon.challenge-validator.infra-requeue.v2"
DEFAULT_SPLIT = "2026-11-03T00:00:00Z"
_TASK = re.compile(r"rtsk_[0-9a-f]{64}")
_ATTEMPT = 1  # the attempt that failed; a requeue grades attempt 2, once
_DELIVERED = ("GRADED", "CANDIDATE_FAILED")


def _graded_statuses():
    from .exam_cap import COUNTED

    return frozenset(COUNTED)


_GRADED_STATUSES = _graded_statuses()


#: The last attempt whose failure ``requeue`` may hand back: attempt 2, for the binding cause only.
_LAST_REQUEUED_FAILURE = 2
BINDING_CAUSE = "evaluation_pack_binding_unavailable"


def _paths(root, task, attempt=_ATTEMPT):
    """The task's marker, failure and evaluation paths, and where ``attempt``'s are kept once it is handed back."""
    base = Path(root) / "auto-grade"
    kept = base / "requeued"
    return {
        "marker": base / "markers" / (task + ".json"),
        "failure": base / "failures" / (task + ".txt"),
        "kept_marker": kept / f"{task}.attempt-{attempt}.marker.json",
        "kept_failure": kept / f"{task}.attempt-{attempt}.failure.txt",
        # the private evaluation directory `lean_recipe_retention._private_evaluation_directory` writes (beside the
        # task's artifacts, in the grader's ``auto-grade/artifacts``), and where attempt 1's copy is kept
        "evaluation": base / "artifacts" / (task + ".evaluation"),
        "kept_evaluation": kept / f"{task}.attempt-{_ATTEMPT}.evaluation",
    }


def _evaluation_refusal(paths):
    """None when the evaluation directory is absent or a plain directory, and nothing is kept for it yet."""
    if paths["kept_evaluation"].exists() or paths["kept_evaluation"].is_symlink():
        return "evaluation_already_kept"
    evaluation = paths["evaluation"]
    if evaluation.is_symlink() or (evaluation.exists() and not evaluation.is_dir()):
        return "evaluation_directory_unreadable"
    return None


def _keep_evaluation(paths):
    """Move attempt 1's private evaluation files aside (one rename, same filesystem); True when there were any."""
    if not paths["evaluation"].is_dir():
        return False
    paths["kept_evaluation"].parent.mkdir(mode=0o700, exist_ok=True)
    os.replace(paths["evaluation"], paths["kept_evaluation"])
    return True


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
        return any(cause in text for cause in CAUSES)
    return False


def _ledger(root):
    from .exam_cap import ExamCap
    from .ledger import AttemptLedger

    ledger = AttemptLedger(Path(root) / "attempts.sqlite3")
    return ledger, ExamCap(ledger)


def _readonly(path):
    return sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True)


class _Door:
    """What this door serves (its door binding, `state_binding.read_door`: the Challenge and pack are fixed for the
    state's life) and read-only access to its owners' stores. Anything unreadable leaves ``served`` None, and every
    requeue then refuses.
    """

    def __init__(self, root):
        self.root = Path(root)
        self.served = None
        self._stores = {}
        try:
            from carbon.challenge_validator.state_binding import read_door

            binding = read_door(self.root)
            from carbon.reconstruction.served_recipe_contract import registered

            challenge = binding["challenge"]
            self.served = {
                "pack": binding["evaluation_pack_digest"],
                "contract": registered(challenge["id"], challenge["version"]).digest,
            }
        except (OSError, ValueError, KeyError, TypeError, LookupError):
            self.served = None

    def owner_dir(self, hotkey):
        return self.root / "owners" / hashlib.sha256(hotkey.encode()).hexdigest()

    def store(self, hotkey):
        """``(owner pack, {task id: canonical recipe bytes})`` of one owner's store; ``(None, {})`` when the owner has
        no store on this root (nothing to resolve); None when a store exists but cannot be read (never archived).
        """
        if hotkey in self._stores:
            return self._stores[hotkey]
        from carbon.research import DirectStartTaskRequestV3, load_canonical

        found = None
        directory = self.owner_dir(hotkey)
        if (
            not (directory / "tasks" / "direct-tasks.sqlite3").exists()
            and not (directory / "ledger" / "campaign.sqlite3").exists()
        ):
            self._stores[hotkey] = (None, {})
            return self._stores[hotkey]
        try:
            with contextlib.closing(
                _readonly(directory / "ledger" / "campaign.sqlite3")
            ) as db:
                manifest = db.execute(
                    "SELECT manifest FROM campaign WHERE id=1"
                ).fetchone()
            pack = json.loads(manifest[0])["receiver_binding"].get(
                "evaluation_pack_digest"
            )
            with contextlib.closing(
                _readonly(directory / "tasks" / "direct-tasks.sqlite3")
            ) as db:
                rows = db.execute("SELECT id, request FROM direct_tasks").fetchall()
            recipes = {}
            for identity, raw in rows:
                request = load_canonical(raw, DirectStartTaskRequestV3)
                # the recipe document as canonical JSON: the same recipe is the same bytes
                recipes[identity] = json.dumps(
                    request.recipe, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            found = (pack, recipes)
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
            found = None
        self._stores[hotkey] = found
        return found


def _arrival(db, task):
    """``(at_ns, block, hotkey, contract)`` of the task's first signed OUTCOME at this door, or None."""
    row = db.execute(
        "SELECT at_ns, receipt, hotkey, contract_digest FROM attempts WHERE kind='OUTCOME' AND "
        "submission_id=? ORDER BY seq LIMIT 1",
        (task,),
    ).fetchone()
    if row is None:
        return None
    try:
        block = json.loads(row[1]).get("block")
    except (TypeError, ValueError, AttributeError):
        block = None
    return row[0], (block if type(block) is int else None), row[2], row[3]


def _rows(db, task):
    return db.execute(
        "SELECT id, state, status, hotkey, challenge_id, exam_key, epoch, reserved_ns "
        "FROM exam_graded WHERE submission_id=? AND kind='GRADED'",
        (task,),
    ).fetchall()


def _failed_attempt(root, task):
    """The attempt the task's current marker records: 1 + the attempts already kept (None: one ``requeue`` may not
    hand back, or a kept path is not a plain file)."""
    for attempt in range(1, _LAST_REQUEUED_FAILURE + 1):
        kept = _paths(root, task, attempt)["kept_marker"]
        if kept.is_symlink():
            return None
        if not kept.exists():
            return attempt
    return None


def _binding_refusal(root, task, paths):
    """None when attempt 2 failed on attempt 1's binding alone (see the module text), else the refusal code."""
    try:
        text = paths["failure"].read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if BINDING_CAUSE not in text:
        return "cause_not_requeueable"
    if not paths["evaluation"].is_dir():
        # the binding attempt 2 met is not attempt 1's directory: not this cause
        return "binding_conflict_without_attempt_ones_files"
    at_ns = _requeued_at(root, task)
    if at_ns is None:
        return "requeue_record_missing"
    if _written_since(paths["evaluation"], at_ns):
        return "evaluation_written_since_requeue"
    return None


def _requeue_refusal(root, db, door, task, *, auto=False):
    """None when ``requeue`` accepts the task, else its refusal code (read-only). ``auto`` (the receiver's own one
    automatic retry, `auto_retry`): the same criteria without the 4 Nov incident's cause filter, attempt 1 only.
    """
    if type(task) is not str or not _TASK.fullmatch(task):
        return "not_a_task_id"
    attempt = _failed_attempt(root, task)
    if attempt is None:
        return "already_requeued"
    paths = _paths(root, task, attempt)
    state = _marker(paths["marker"])
    if attempt == _ATTEMPT:
        if state is None:
            return "no_marker"
        if state != "FAILED":
            return "marker_" + state.lower()
        if not auto and not _cause(paths):
            return "cause_not_requeueable"
    elif auto:
        return "already_requeued"
    else:
        # handed back once already: only attempt 2's FAILED binding conflict is handed back again
        if state != "FAILED":
            return "already_requeued"
        code = _binding_refusal(root, task, paths)
        if code is not None:
            return "already_requeued" if code == "cause_not_requeueable" else code
    evaluation = _evaluation_refusal(paths)
    if evaluation is not None:
        return evaluation
    if _released(root, task):
        # its charged-but-undelivered slot was given back by `release`: never re-graded to replace the record
        return "released_not_regraded"
    arrival = _arrival(db, task)
    if arrival is None:
        return "not_submitted_at_this_door"
    given_back = False
    for _id, row_state, status, *_rest in _rows(db, task):
        if row_state in ("COUNTED", "RESERVED"):
            return "exam_row_counted_or_reserved"
        if status == "FAILED_INFRA":
            # given back on infrastructure (A1 and later): the door runs a resubmit of this recipe fresh, so it is
            # re-queued only while no such fresh task exists (checked below), and `mark_requeued` then closes that path
            given_back = True
        if status == "SLOT_RETURNED" or status in _GRADED_STATUSES:
            # a graded outcome, whatever its slot state now: never re-queued (review finding 3)
            return "exam_row_graded"
    if door.served is None:
        return "door_binding_unavailable"
    hotkey, contract = arrival[2], arrival[3]
    if contract != door.served["contract"]:
        return "contract_not_served"
    store = door.store(hotkey) if type(hotkey) is str else None
    if store is None:
        # unreadable now (locked, torn): never archived on a guess (review finding 1)
        return "owner_store_unreadable"
    if task not in store[1]:
        # given back: the miner's resubmit already runs fresh, nothing to archive
        return "given_back_resubmit_runs_fresh" if given_back else "task_row_missing"
    pack, recipes = store
    if pack != door.served["pack"]:
        return "pack_not_served"
    if given_back and any(
        other != task and recipe == recipes[task] for other, recipe in recipes.items()
    ):
        # a fresh rerun (or another task) of this same recipe exists: it grades, this one never does twice
        return "given_back_rerun_exists"
    for other, recipe in recipes.items():
        if (
            other != task
            and recipe == recipes[task]
            and _marker(_paths(root, other)["marker"]) in _DELIVERED
        ):
            return "same_recipe_already_graded"
    return None


def _decision(root, db, door, task, *, auto=False):
    """``(action, refusal)``: ``("requeue", None)``, ``("archive", None)`` for a task the door cannot resolve that a
    resubmit will recreate, or ``(None, code)``."""
    code = _requeue_refusal(root, db, door, task, auto=auto)
    if code is None:
        return "requeue", None
    if code == "task_row_missing":
        return "archive", None
    return None, code


def _grade_wall(db):
    """``(mean wall seconds, samples)`` of this door's counted grades (reserve to settle), or ``(None, 0)``."""
    row = db.execute(
        "SELECT AVG(settled_ns - reserved_ns), COUNT(*) FROM exam_graded WHERE kind='GRADED' "
        "AND state='COUNTED' AND settled_ns IS NOT NULL AND settled_ns > reserved_ns"
    ).fetchone()
    return (None, 0) if not row[1] else (row[0] / 1e9, row[1])


def _iso(at_ns):
    return (
        datetime.datetime.fromtimestamp(at_ns / 1e9, tz=datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def scan(root, *, split=DEFAULT_SPLIT):
    """Read-only: the tasks ``requeue`` accepts now, the refusal counts, and the cost (see the module text)."""
    edge_ns = int(datetime.datetime.fromisoformat(split).timestamp()) * 1_000_000_000
    markers = Path(root) / "auto-grade" / "markers"
    failed = sorted(
        path.stem
        for path in markers.glob("rtsk_*.json")
        if _TASK.fullmatch(path.stem) and _marker(path) == "FAILED"
    )
    ledger, _cap = _ledger(root)
    door = _Door(root)
    out = {
        "schema": SCHEMA,
        "action": "list",
        "split": split,
        "failed_markers": len(failed),
        "eligible": {"before_split": [], "since_split": []},
        "archive_for_resubmit": [],
        "arrived": {},
        "refused_counts": {},
    }
    with ledger._db() as db:
        for task in failed:
            action, code = _decision(root, db, door, task)
            if action is None:
                out["refused_counts"][code] = out["refused_counts"].get(code, 0) + 1
                continue
            if action == "archive":
                out["archive_for_resubmit"].append(task)
                continue
            at_ns = _arrival(db, task)[0]
            group = "since_split" if at_ns >= edge_ns else "before_split"
            out["eligible"][group].append(task)
            out["arrived"][task] = _iso(at_ns)
        wall, samples = _grade_wall(db)
    count = sum(len(v) for v in out["eligible"].values())
    out["eligible_counts"] = {k: len(v) for k, v in out["eligible"].items()}
    out["cost"] = {
        "requeue_count": count,
        "mean_grade_wall_seconds": None if wall is None else round(wall, 1),
        "grade_wall_samples": samples,
        "estimated_grade_hours": (
            None if wall is None else round(count * wall / 3600, 2)
        ),
        "order": "one grade at a time per door, interleaved with live submissions in task-id order",
    }
    return out


def requeue(root, tasks, *, apply=False, clock=time.time_ns, auto=False):
    """``{"requeued": [...], "refused": {task: code}}`` for each task (see the module text). ``auto``: the receiver's
    own one automatic retry (`auto_retry`), logged as such."""
    out = {
        "schema": SCHEMA,
        "action": "requeue",
        "apply": apply,
        "requeued": [],
        "archived": [],
        "refused": {},
    }
    ledger, cap = _ledger(root)
    door = _Door(root)
    for task in tasks:
        with ledger._db() as db:
            action, code = _decision(root, db, door, task, auto=auto)
        if action is None:
            out["refused"][task] = code
            continue
        if apply:
            attempt = _failed_attempt(root, task)
            paths = _paths(root, task, attempt)
            paths["kept_marker"].parent.mkdir(mode=0o700, exist_ok=True)
            # Its one bypass of the round/day limits is on record before the grader can see the task.
            cap.mark_requeued(task, attempt=attempt + 1)
            if paths["failure"].exists():
                # Evidence first, so attempt 2 can write its own (create-only) failure file.
                os.replace(paths["failure"], paths["kept_failure"])
            # Attempt 1's create-only evaluation files too, so attempt 2 binds and grades under its own entry.
            kept_evaluation = _keep_evaluation(paths)
            # The commit point: with no marker, the grader's next tick takes the task.
            os.replace(paths["marker"], paths["kept_marker"])
            with open(
                paths["kept_marker"].parent / "requeues.jsonl", "a", encoding="utf-8"
            ) as log:
                log.write(
                    json.dumps(
                        {
                            "task": task,
                            "attempt": attempt + 1,
                            "kind": action,
                            "evaluation_kept": kept_evaluation,
                            "at_ns": int(clock()),
                            **({"auto": True} if auto else {}),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        out["requeued" if action == "requeue" else "archived"].append(task)
    return out


def _requeued_at(root, task):
    """The ``at_ns`` of the task's attempt-2 line in ``requeued/requeues.jsonl``, or None."""
    log = Path(root) / "auto-grade" / "requeued" / "requeues.jsonl"
    try:
        lines = log.read_text().splitlines()
    except OSError:
        return None
    found = None
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if (
            type(record) is dict
            and record.get("task") == task
            and record.get("attempt") == _ATTEMPT + 1
            and record.get("kind") in ("requeue", "archive")
            and type(record.get("at_ns")) is int
        ):
            found = record["at_ns"]
    return found


def _written_since(directory, at_ns):
    """Whether anything in ``directory`` (itself included) was written at or after ``at_ns``, or cannot be read."""
    try:
        if os.lstat(directory).st_mtime_ns >= at_ns:
            return True
        for parent, names, files in os.walk(directory):
            for name in (*names, *files):
                info = os.lstat(Path(parent) / name)
                if stat.S_ISLNK(info.st_mode) or info.st_mtime_ns >= at_ns:
                    return True
    except OSError:
        return True
    return False


def _keep_evaluation_refusal(root, db, task):
    """None when ``keep_evaluation`` accepts the task, else its refusal code (read-only)."""
    if type(task) is not str or not _TASK.fullmatch(task):
        return "not_a_task_id"
    paths = _paths(root, task)
    if not paths["kept_marker"].exists():
        return "not_requeued"
    code = _evaluation_refusal(paths)
    if code is not None:
        return code
    if not paths["evaluation"].exists():
        return "no_evaluation_directory"
    state = _marker(paths["marker"])
    if state == "FAILED":
        try:
            text = paths["failure"].read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        return "failed_again_use_requeue" if BINDING_CAUSE in text else "marker_failed"
    if state is not None:
        return "marker_" + state.lower()
    if any(row[1] == "RESERVED" for row in _rows(db, task)):
        return "grade_in_flight"
    at_ns = _requeued_at(root, task)
    if at_ns is None:
        return "requeue_record_missing"
    if _written_since(paths["evaluation"], at_ns):
        # attempt 2 has written there already: not attempt 1's alone, never moved on a guess
        return "evaluation_written_since_requeue"
    return None


def keep_evaluation(root, tasks, *, apply=False, clock=time.time_ns):
    """``{"kept": [...], "refused": {task: code}}``: keep attempt 1's evaluation directory of tasks re-queued before
    ``requeue`` did so itself (see the module text)."""
    out = {
        "schema": SCHEMA,
        "action": "keep_evaluation",
        "apply": apply,
        "kept": [],
        "refused": {},
    }
    ledger, _cap = _ledger(root)
    for task in tasks:
        with ledger._db() as db:
            code = _keep_evaluation_refusal(root, db, task)
        if code is not None:
            out["refused"][task] = code
            continue
        if apply:
            paths = _paths(root, task)
            _keep_evaluation(paths)
            with open(
                paths["kept_marker"].parent / "requeues.jsonl", "a", encoding="utf-8"
            ) as log:
                log.write(
                    json.dumps(
                        {
                            "task": task,
                            "attempt": _ATTEMPT + 1,
                            "kind": "keep_evaluation",
                            "at_ns": int(clock()),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        out["kept"].append(task)
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


def _stuck(root, task):
    """Whether ``task`` is one of this door's A2 stuck tasks: handed back or archived by ``requeue``, released by
    ``release``, or still FAILED for the registration cause."""
    paths = _paths(root, task)
    if paths["kept_marker"].exists():
        return True
    released = paths["kept_marker"].parent / "releases.jsonl"
    try:
        if any(
            json.loads(line).get("task") == task
            for line in released.read_text().splitlines()
            if line.strip()
        ):
            return True
    except (OSError, ValueError, AttributeError):
        pass
    return _marker(paths["marker"]) == "FAILED" and _cause(paths)


def _released(root, task):
    """Whether ``release`` gave this task's slot back (its line in ``requeued/releases.jsonl``)."""
    log = Path(root) / "auto-grade" / "requeued" / "releases.jsonl"
    try:
        return any(
            json.loads(line).get("task") == task
            for line in log.read_text().splitlines()
            if line.strip()
        )
    except (OSError, ValueError, AttributeError):
        return False


def _ns(text):
    return int(datetime.datetime.fromisoformat(text).timestamp() * 1_000_000_000)


def return_slots(
    root, stuck, *, window_start, window_end, apply=False, clock=time.time_ns
):
    """OWNER-RESUBMIT-SLOT-PROMISE-KEEP-01 (owner 4 Nov, option A): ONE released slot per A2-listed stuck task, for a
    GRADED resubmit (a COUNTED row) by the SAME hotkey at THIS door that arrived inside ``[window_start, window_end]``
    (the miner note's post time to this door's A1 LIVE + checked time, UTC). The resubmit's grade stands, never
    rescored; only its slot goes back, through `ExamCap.return_promised_slot`. Pairs are made in arrival order, each
    resubmit used once, and logged to ``requeued/slot-returns.jsonl`` (a re-run skips what is logged).
    """
    start, end = _ns(window_start), _ns(window_end)
    out = {
        "schema": SCHEMA,
        "action": "return_slots",
        "apply": apply,
        "window": [window_start, window_end],
        "returned": {},
        "unmatched": [],
        "refused": {},
    }
    if not start < end:
        return {**out, "refused": {"window": "window_empty_or_reversed"}}
    log_path = Path(root) / "auto-grade" / "requeued" / "slot-returns.jsonl"
    done = []
    try:
        done = [
            json.loads(line)
            for line in log_path.read_text().splitlines()
            if line.strip()
        ]
    except (OSError, ValueError):
        done = []
    used = {record.get("resubmit") for record in done}
    paired = {record.get("stuck") for record in done}
    ledger, cap = _ledger(root)
    tasks = []
    for task in stuck:
        if type(task) is not str or not _TASK.fullmatch(task):
            out["refused"][str(task)] = "not_a_task_id"
        elif task in paired:
            out["refused"][task] = "already_returned"
        elif not _stuck(root, task):
            out["refused"][task] = "not_a_stuck_task"
        else:
            tasks.append(task)
    stuck_set = set(stuck)
    plan = []
    with ledger._db() as db:
        arrivals = []
        for task in tasks:
            arrival = _arrival(db, task)
            if arrival is None or type(arrival[2]) is not str:
                out["refused"][task] = "stuck_not_at_this_door"
            else:
                arrivals.append((arrival[0], task, arrival[2]))
        for _at, task, hotkey in sorted(arrivals):
            found = None
            for resubmit, _first in db.execute(
                "SELECT submission_id, MIN(at_ns) AS first_ns FROM attempts WHERE kind='OUTCOME' "
                "AND hotkey=? AND submission_id IS NOT NULL GROUP BY submission_id "
                "HAVING first_ns>=? AND first_ns<=? ORDER BY first_ns, submission_id",
                (hotkey, start, end),
            ).fetchall():
                if resubmit in stuck_set or resubmit in used:
                    continue
                counted = db.execute(
                    "SELECT COUNT(*) FROM exam_graded WHERE submission_id=? AND hotkey=? "
                    "AND kind='GRADED' AND state='COUNTED'",
                    (resubmit, hotkey),
                ).fetchone()[0]
                delivered = _marker(_paths(root, resubmit)["marker"]) in _DELIVERED
                if counted == 1 and delivered:
                    found = resubmit
                    break
            if found is None:
                out["unmatched"].append(task)
            else:
                used.add(found)
                plan.append((task, found))
    for task, resubmit in plan:
        if apply:
            from .exam_cap import ExamCapRefused

            try:
                before = cap.return_promised_slot(resubmit)
            except ExamCapRefused as refused:
                out["refused"][task] = refused.code
                continue
            log_path.parent.mkdir(mode=0o700, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as log:
                log.write(
                    json.dumps(
                        {
                            "stuck": task,
                            "resubmit": resubmit,
                            "row": before["row"],
                            "prior_state": before["prior_state"],
                            "prior_status": before["prior_status"],
                            "state": "RELEASED",
                            "status": "SLOT_RETURNED",
                            "reason": "OWNER-RESUBMIT-SLOT-PROMISE-KEEP-01",
                            "at_ns": int(clock()),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        out["returned"][resubmit] = task
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    listing = sub.add_parser("list")
    listing.add_argument("--root", type=Path, required=True)
    listing.add_argument("--split", default=DEFAULT_SPLIT)
    listing.add_argument(
        "--out", type=Path, help="write every accepted id, one per line"
    )
    one = sub.add_parser("requeue")
    one.add_argument("--root", type=Path, required=True)
    one.add_argument("--ids", type=Path, required=True)
    one.add_argument("--apply", action="store_true")
    two = sub.add_parser("release")
    two.add_argument("--root", type=Path, required=True)
    two.add_argument("--id", required=True)
    two.add_argument("--apply", action="store_true")
    three = sub.add_parser("return-slots")
    three.add_argument("--root", type=Path, required=True)
    three.add_argument("--ids", type=Path, required=True, help="the A2 stuck task ids")
    three.add_argument(
        "--from",
        dest="window_start",
        required=True,
        help="the note's post time, UTC ISO",
    )
    three.add_argument(
        "--to",
        dest="window_end",
        required=True,
        help="this door's A1 LIVE + checked time, UTC ISO",
    )
    three.add_argument("--apply", action="store_true")
    four = sub.add_parser("keep-evaluation")
    four.add_argument("--root", type=Path, required=True)
    four.add_argument("--ids", type=Path, required=True, help="the re-queued task ids")
    four.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "list":
        out = scan(args.root, split=args.split)
        if args.out is not None:
            args.out.write_text(
                "".join(
                    task + "\n"
                    for task in (
                        *out["eligible"]["before_split"],
                        *out["eligible"]["since_split"],
                        *out["archive_for_resubmit"],
                    )
                )
            )
    elif args.cmd == "requeue":
        tasks = [
            line.strip() for line in args.ids.read_text().splitlines() if line.strip()
        ]
        out = requeue(args.root, tasks, apply=args.apply)
    elif args.cmd == "keep-evaluation":
        tasks = [
            line.strip() for line in args.ids.read_text().splitlines() if line.strip()
        ]
        out = keep_evaluation(args.root, tasks, apply=args.apply)
    elif args.cmd == "return-slots":
        tasks = [
            line.strip() for line in args.ids.read_text().splitlines() if line.strip()
        ]
        out = return_slots(
            args.root,
            tasks,
            window_start=args.window_start,
            window_end=args.window_end,
            apply=args.apply,
        )
    else:
        out = release(args.root, args.id, apply=args.apply)
    print(json.dumps(out, sort_keys=True))
    return 3 if args.cmd == "release" and out.get("refused") else 0


if __name__ == "__main__":
    sys.exit(main())
