"""R39: a grade that fails on Carbon's infrastructure gets a verdict and, once, a free automatic retry (Graphite-B;
Validator-2B 7 Nov rulings (1)-(3); scope codex-queue/reports/GRAPHITE_B_R39_R40_SCOPE_20261107.md). Invariant 7:
infrastructure failure is not scientific failure. Nothing here grades, scores or rescores anything.

- **Next step** (every FAILED marker, private; a closed code whose sentence is true for it, `NEXT_STEPS`):
  ``retry_scheduled`` / ``slot_returned`` / ``resubmit_after_fix``, or None when a charged slot could not be proven
  undelivered (the operator decides; an alert line is written).
- **Retry, once per task for life** (persisted: the schedule log here + the ledger's ``exam_requeues`` row of the
  re-grade). Only for a transient Carbon code (`retryable`): never a version-wide Carbon gap (a registration, a pack,
  the menu keys: a retry meets the same gap, so the slot is returned and the operator re-queues after the fix), never a
  candidate outcome, never a duplicate. It is applied through `infra_requeue.requeue(..., auto=True)`: exactly the
  operator tool's criteria (never a COUNTED / RESERVED / graded task, never a recipe already graded, the task row
  bound to the served pack) minus the 4 Nov incident's cause filter; the re-grade reuses the task's own row (no new
  slot, its original epoch). It is spaced (`RETRY_SECONDS` after the failure; applied on an idle tick, or once overdue
  by `OVERDUE_SECONDS` so a busy door cannot starve it) and never while the door drains.
- **A COUNTED slot with no delivered verdict** (Validator-2B (2)) is released automatically only when ALL hold
  (`undelivered_refusal`): the marker is FAILED with a Carbon code; the pool store was read and holds no graded
  private evaluation of the submission (a missing or unreadable store refuses); no Ladder/feedback document for its round (`infra_requeue._ladder_shows_round`); exactly one COUNTED
  row; its status is a scored outcome (not a candidate outcome, not a duplicate). Else nothing changes and an alert
  line names the reason.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

#: The closed next-step codes and the one sentence each means (Validator-2B traces each in the head).
NEXT_STEPS = {
    "retry_scheduled": "Carbon's infrastructure failed this grade; Carbon grades it again once, automatically, and "
    "it costs you no slot.",
    "slot_returned": "Carbon's infrastructure failed this grade; no slot is charged for it, and a resubmit is graded "
    "in your next round as usual.",
    "resubmit_after_fix": "A Carbon-side gap stopped this grade for this version; no slot is charged for it; resubmit "
    "after Carbon posts the fix.",
}
#: Spacing of the one retry after its failure (the crown sweep's own retry spacing), and when a retry that waited for
#: an idle tick is applied anyway.
RETRY_SECONDS = 15 * 60
OVERDUE_SECONDS = 60 * 60
LOG_NAME = "auto-retry.jsonl"
ALERT_NAME = "auto-retry-alerts.jsonl"

_TASK = re.compile(r"rtsk_[0-9a-f]{64}")

#: Version-wide Carbon gaps (Validator-2B (1)): every grade of the version meets the same gap, so no retry.
_VERSION_WIDE_PREFIXES = (
    "pool_constants_",
    "pool_material_",
    "exam_cap_",
    "exam_cadence_",
    "exam_key_expired",
    "evaluation_pack_",
    "pack_",
    "menu_",
    "contract_not_served",
)
_VERSION_WIDE_SUFFIXES = ("_unregistered",)
#: Typed Carbon exception names that are version-wide (the grader writes a class name for untyped failures).
_VERSION_WIDE_CLASSES = frozenset(
    {"PoolConstantsNotRegistered", "ExamRefused", "MenuRefused", "ExamCapRefused"}
)


def retryable(code) -> bool:
    """Whether a FAILED grade's Carbon code is transient (one free automatic retry)."""
    if type(code) is not str or not code:
        return False
    base = code.split(":", 1)[0]
    if "DUPLICATE" in base.upper():
        return False
    if base in _VERSION_WIDE_CLASSES:
        return False
    if any(base.startswith(p) for p in _VERSION_WIDE_PREFIXES):
        return False
    return not any(base.endswith(s) for s in _VERSION_WIDE_SUFFIXES)


def _dir(root):
    directory = Path(root) / "auto-grade" / "requeued"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory


def _lines(path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if type(record) is dict and type(record.get("task")) is str:
            out.append(record)
    return out


def _append(path, record):
    with open(path, "a", encoding="utf-8") as log:
        log.write(json.dumps(record, sort_keys=True) + "\n")


def used(root, task, ledger=None) -> bool:
    """Whether this task already had its one automatic retry (scheduled, applied or refused) or any re-queue at all."""
    if any(r["task"] == task for r in _lines(_dir(root) / LOG_NAME)):
        return True
    if ledger is None:
        return False
    with ledger._db() as db:
        try:
            row = db.execute(
                "SELECT 1 FROM exam_requeues WHERE submission_id=?", (task,)
            ).fetchone()
        except Exception:  # noqa: BLE001 - no requeue table yet: never re-queued
            row = None
    return row is not None


def schedule(root, task, code, *, ledger=None, clock=time.time_ns) -> bool:
    """Schedule the task's one automatic retry; False when it is not retryable or its retry was already used."""
    if type(task) is not str or not _TASK.fullmatch(task) or not retryable(code):
        return False
    if used(root, task, ledger):
        return False
    _append(
        _dir(root) / LOG_NAME,
        {"task": task, "kind": "scheduled", "code": code, "at_ns": int(clock())},
    )
    return True


def due(root, *, clock=time.time_ns, idle=True):
    """Scheduled retries due now, oldest first: ``RETRY_SECONDS`` after scheduling on an idle tick, else only once
    overdue by ``OVERDUE_SECONDS``."""
    now = int(clock())
    records = _lines(_dir(root) / LOG_NAME)
    done = {r["task"] for r in records if r.get("kind") in ("applied", "refused")}
    wait = RETRY_SECONDS if idle else RETRY_SECONDS + OVERDUE_SECONDS
    return [
        r["task"]
        for r in records
        if r.get("kind") == "scheduled"
        and r["task"] not in done
        and type(r.get("at_ns")) is int
        and now - r["at_ns"] >= wait * 1_000_000_000
    ]


def apply_due(root, *, draining=False, idle=True, clock=time.time_ns):
    """Hand each due retry back to the grader through `infra_requeue.requeue(auto=True)` (its criteria re-checked at
    the moment of applying). Each task is recorded applied or refused exactly once. Nothing while the door drains.
    A refused retry also writes an alert line (Validator-2B 8 Nov must-fix 2): the task's write-once marker still says
    ``retry_scheduled``, so the operator must learn that the retry did not happen.
    """
    if draining:
        return []
    from . import infra_requeue

    results = []
    for task in due(root, clock=clock, idle=idle):
        out = infra_requeue.requeue(root, [task], apply=True, clock=clock, auto=True)
        refused = out["refused"].get(task)
        _append(
            _dir(root) / LOG_NAME,
            {
                "task": task,
                "kind": "refused" if refused else "applied",
                "refusal": refused,
                "at_ns": int(clock()),
            },
        )
        if refused:
            _append(
                _dir(root) / ALERT_NAME,
                {
                    "task": task,
                    "event": "auto_retry_refused",
                    "reason": refused,
                    "at_ns": int(clock()),
                },
            )
        results.append((task, refused))
    return results


#: COUNTED statuses that are the candidate's own verdict (Validator-2B (2): never released automatically).
def _scored_status():
    return "SCORED_DEVELOPMENT_CANDIDATE"


def _pool_refusal(pool_store, task):
    """None only when the pool store was READ and holds no graded private evaluation of this submission, else the
    reason. Fail closed (Validator-2B 8 Nov): a store that is not configured, cannot be opened (the grader passes None)
    or cannot be read never proves that nothing was graded."""
    if pool_store is None:
        return "pool_store_unreadable"
    try:
        found = any(
            type(b) is dict and b.get("submission_id") == task
            for b in pool_store.private_evaluation_bodies()
        )
    except Exception:  # noqa: BLE001
        return "pool_store_unreadable"
    return "pool_store_has_a_graded_evaluation" if found else None


def undelivered_refusal(task, code, *, ledger, pool_store):
    """None when this FAILED task's COUNTED slot may be released automatically (every condition of Validator-2B (2)),
    else the reason it is not."""
    from . import infra_requeue

    if type(code) is not str or not code:
        return "no_carbon_code"
    pool_refusal = _pool_refusal(pool_store, task)
    if pool_refusal is not None:
        return pool_refusal
    with ledger._db() as db:
        rows = infra_requeue._rows(db, task)
        counted = [row for row in rows if row[1] == "COUNTED"]
        if len(counted) != 1:
            return "not_exactly_one_counted_row"
        status = counted[0][2]
        if type(status) is not str or "DUPLICATE" in status.upper():
            return "duplicate_status"
        if status != _scored_status():
            return "candidate_status"
        if infra_requeue._ladder_shows_round(db, counted[0]):
            return "ladder_shows_this_round"
    return None


def release_undelivered(root, task, code, *, ledger, pool_store, clock=time.time_ns):
    """Release the COUNTED slot of a FAILED, never-delivered grade when `undelivered_refusal` allows it. Returns True
    when released; otherwise writes an alert line naming the reason and returns False.
    """
    from .exam_cap import ExamCap, ExamCapRefused

    refusal = undelivered_refusal(task, code, ledger=ledger, pool_store=pool_store)
    if refusal is None:
        try:
            done = ExamCap(ledger).release_undelivered(task)
        except ExamCapRefused as exc:
            refusal = exc.code
        else:
            _append(
                _dir(root) / "releases.jsonl",
                {
                    "task": task,
                    "row": done["row"],
                    "prior_state": done["prior_state"],
                    "prior_status": done["prior_status"],
                    "state": "RELEASED",
                    "status": "FAILED_INFRA",
                    "reason": "result_not_delivered",
                    "automatic": True,
                    "at_ns": int(clock()),
                },
            )
            return True
    _append(
        _dir(root) / ALERT_NAME,
        {
            "task": task,
            "event": "counted_slot_kept",
            "reason": refusal,
            "code": code,
            "at_ns": int(clock()),
        },
    )
    return False
