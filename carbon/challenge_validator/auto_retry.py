"""R39: a grade that fails on Carbon's infrastructure gets a verdict and, once, a free automatic retry (Graphite-B;
Validator-2B 7 Nov rulings (1)-(3); scope codex-queue/reports/GRAPHITE_B_R39_R40_SCOPE_20261107.md). Invariant 7:
infrastructure failure is not scientific failure. Nothing here grades, scores or rescores anything.

- **Next step** (every FAILED marker, private; a closed code whose sentence is true for it, `NEXT_STEPS`):
  ``retry_scheduled`` / ``slot_returned`` / ``resubmit_after_fix`` / ``resubmit_program_changed``, or None when a
  charged slot could not be proven undelivered (the operator decides; an alert line is written).
- **Retry, bounded per cause** (switch 5, owner: Carbon's failures re-run automatically; persisted in the schedule log
  here): up to `PER_CAUSE_RETRIES` automatic retries for each Carbon code (`CAUSE_RETRIES` names a smaller one) and
  `TASK_RETRIES` in all for a task, a backstop against a hot loop. Only for a transient Carbon code (`retryable`): never
  a version-wide Carbon gap (a registration, a pack, the menu keys: a retry meets the same gap, so the slot is returned
  and the operator re-queues after the fix), never a candidate outcome, never a duplicate. It is applied through
  `infra_requeue.requeue(..., auto=True)`: exactly the operator tool's criteria (never a COUNTED / RESERVED / graded
  task, never a recipe already graded, the task row bound to the served pack) minus the 4 Nov incident's cause filter,
  and for a later attempt ``rearm``'s (every earlier attempt FAILED on Carbon's side), with no receipt; the re-grade
  reuses the task's own row (no new slot, its original epoch). The first retry goes back at the next round, busy door
  or idle; only a later retry of the same cause waits `RETRY_SECONDS`; nothing is applied while the door drains.
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
    "retry_scheduled": "Carbon's infrastructure failed this grade; Carbon grades it again automatically, and it costs "
    "you no slot.",
    "slot_returned": "Carbon's infrastructure failed this grade; no slot is charged for it, and a resubmit is graded "
    "in your next round as usual.",
    "resubmit_after_fix": "A Carbon-side gap stopped this grade for this version; no slot is charged for it; resubmit "
    "after Carbon posts the fix.",
    "resubmit_program_changed": "Carbon's grading program changed while this grade was in progress; no slot was charged "
    "for it; resubmit it and it is built and graded again from the start under the current program.",
}
#: Carbon codes an automatic retry cannot fix (review of 15 Nov, finding 3): a vmap-64 grade off its sealed pack
#: (`VMAP64_NEEDS_SEALED_PACK`). Never retried. (``graded_program_changed`` IS retried since switch 5: its hand-back
#: leaves a ``.regenerate`` mark, `infra_requeue.REGENERATE_CAUSES`, so the retry's graded pass runs afresh.)
_NOT_RETRIED = frozenset({"vmap64_grade_needs_sealed_pack"})
#: The next step a FAILED marker shows for a code that names its own (the operator's plain line), else the usual rule.
#: ``resubmit_program_changed`` stays a closed code for markers written before switch 5; no code chooses it now.
OWN_NEXT_STEPS = {}
#: Spacing of a task's second and later retry of the SAME cause after its scheduling (`due`): a backstop against a hot
#: loop on one fault, with the per-cause and per-task caps below. 5 min (Validator-2's ruling on the over-broad rules
#: audit #6, 18 Nov 2026: next tick for the first retry, then 5 min; was 15 min).
RETRY_SECONDS = 5 * 60
#: Automatic retries per Carbon code (its base, before any ``:``) and per task in all (switch 5): a backstop against a
#: hot loop, not a policy on miners (each retry is uncharged on the task's own row and cannot probe the exam).
PER_CAUSE_RETRIES = 3
TASK_RETRIES = 5
#: A smaller bound for a code whose repeat is not plainly Carbon's: a timed answer beyond the speed-match tolerance
#: keeps its one retry (Validator-2B ruling, 15 Nov; the speed gate stays honest), a second stays FAILED.
CAUSE_RETRIES = {"speed_outputs_disagree": 1}
#: A graded inference whose worker program refused its own output (`bundle_construction_worker`'s check: shape, dtype,
#: kind or a non-finite value; the carrier's marker OUTPUT_CONTRACT_DIFFERS). Deterministic: the same state and query
#: give byte-identical failures (live-ops 20 Nov 20:27Z: 3 Motor 1.8 tasks, 4 attempts each, about 96 lane-min). Its
#: side is not proven yet (V2 rules it from the output_finite_counter counts), so it is the owner's G-LEAD-10 CAUSE
#: UNKNOWN row: its spot returned, NO automatic regrade (0 here: the first failure is at once cap spent, so the marker
#: says slot_returned and the task goes on the owed list), the miner resubmits when ready (V2 pre-read 20 Nov 20:57Z).
#: Nothing here charges or types it the candidate's. Prospective: a marker already written keeps its code.
OUTPUT_CONTRACT_DIFFERS = "output_contract_differs"
CAUSE_RETRIES[OUTPUT_CONTRACT_DIFFERS] = 0
#: The worker program's own closed raise (`bundle_construction_worker`, its inference program text), matched in the
#: failure's private diagnostic only to NAME the code: a candidate that printed it could only lower its own free retries.
_OUTPUT_CONTRACT_RAISE = b"bundle inference output contract differs"
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
    # a dotted reason of the version's own pack (`evaluation_pack.<role>`), its reference solves (invariant 7.5) and its
    # calibrated inference image: every grade of the version meets the same gap (V2-L2-RETENTION-20261120 (3))
    "evaluation_pack.",
    "dual_native_reference_",
    "leg_minimum_platform_mismatch",
    "pack_",
    "menu_",
    "contract_not_served",
)
_VERSION_WIDE_SUFFIXES = ("_unregistered",)
#: Per-task codes under a version-wide prefix: retried as usual. ``evaluation_pack_binding_unavailable`` is one task's
#: write-once binding sidecar (an interrupted grade's leftover; `infra_requeue.set_aside_interrupted` moves it aside
#: before the re-grade), never a gap of the version's pack.
_PER_TASK_CODES = frozenset(
    {
        "evaluation_pack_binding_unavailable",
        # one task's pack-source registration, not the version's pack (V2-L2-RETENTION-20261120)
        "evaluation_pack_source_registration_unavailable",
    }
)
#: Typed Carbon exception names that are version-wide (the grader writes a class name for untyped failures).
_VERSION_WIDE_CLASSES = frozenset(
    {"PoolConstantsNotRegistered", "ExamRefused", "MenuRefused", "ExamCapRefused"}
)


def failure_code(failure) -> str:
    """The marker code of a graded failure that is not otherwise typed: `OUTPUT_CONTRACT_DIFFERS` for a worker failure
    whose program refused its own output, else the failure's class name (today's code, e.g. ``WorkerFailure``).
    """
    from carbon.reconstruction.worker.model import WorkerFailure

    diagnostic = getattr(failure, "private_diagnostic", None)
    if (
        isinstance(failure, WorkerFailure)
        and type(diagnostic) is bytes
        and _OUTPUT_CONTRACT_RAISE in diagnostic
    ):
        return OUTPUT_CONTRACT_DIFFERS
    return type(failure).__name__


def retryable(code) -> bool:
    """Whether a FAILED grade's Carbon code is transient (one free automatic retry)."""
    if type(code) is not str or not code:
        return False
    base = code.split(":", 1)[0]
    if "DUPLICATE" in base.upper():
        return False
    if base in _VERSION_WIDE_CLASSES or base in _NOT_RETRIED:
        return False
    if base not in _PER_TASK_CODES and any(
        base.startswith(p) for p in _VERSION_WIDE_PREFIXES
    ):
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


def _cause(code):
    return code.split(":", 1)[0] if type(code) is str else None


def used(root, task, ledger=None, *, code=None) -> bool:
    """Whether this task's automatic retries are spent: `TASK_RETRIES` scheduled in all, or (with ``code``) the bound
    for that code's cause (`CAUSE_RETRIES`, else `PER_CAUSE_RETRIES`). ``ledger`` is unused (kept for callers).
    """
    del ledger
    scheduled = [
        r
        for r in _lines(_dir(root) / LOG_NAME)
        if r["task"] == task and r.get("kind") == "scheduled"
    ]
    if len(scheduled) >= TASK_RETRIES:
        return True
    if code is None:
        return False
    cause = _cause(code)
    same = sum(1 for r in scheduled if _cause(r.get("code")) == cause)
    return same >= CAUSE_RETRIES.get(cause, PER_CAUSE_RETRIES)


def schedule(root, task, code, *, ledger=None, clock=time.time_ns) -> bool:
    """Schedule an automatic retry of the task; False when its code is not retryable, a retry of it is still pending,
    or its retries for this cause (or in all) are spent. A spent cap writes an ``auto_retry_cap_spent`` line to the
    alert log (`ALERT_NAME`): the task then goes on the owed list (owner D16, 18 Nov: "capped at 3 per failure code and
    5 per task, then the owed list")."""
    if type(task) is not str or not _TASK.fullmatch(task) or not retryable(code):
        return False
    if task in _pending(root):
        return False
    if used(root, task, ledger, code=code):
        _append(
            _dir(root) / ALERT_NAME,
            {
                "task": task,
                "event": "auto_retry_cap_spent",
                "reason": "owed_list",
                "code": code,
                "at_ns": int(clock()),
            },
        )
        return False
    _append(
        _dir(root) / LOG_NAME,
        {"task": task, "kind": "scheduled", "code": code, "at_ns": int(clock())},
    )
    return True


def _pending(root):
    """``{task: scheduled at_ns}`` for each task whose LAST schedule has no applied/refused record after it, in log
    order (one task may be retried more than once, each schedule closed by its own outcome).
    """
    pending = {}
    for r in _lines(_dir(root) / LOG_NAME):
        if r.get("kind") == "scheduled":
            pending[r["task"]] = r.get("at_ns")
        elif r.get("kind") in ("applied", "refused"):
            pending.pop(r["task"], None)
    return pending


def _earlier_same_cause(root):
    """``{task: how many schedules of the task's PENDING retry's cause came before it}`` (its spacing, `due`)."""
    counts, earlier = {}, {}
    for r in _lines(_dir(root) / LOG_NAME):
        if r.get("kind") != "scheduled":
            continue
        key = (r["task"], _cause(r.get("code")))
        earlier[r["task"]] = counts.get(key, 0)
        counts[key] = counts.get(key, 0) + 1
    return earlier


def due(root, *, clock=time.time_ns, idle=True):
    """Scheduled retries due now, oldest first. V2-OWED-NOW-20261119 (b): a Carbon-side retry goes back at the NEXT
    round, busy door or idle (no idle-tick wait, no overdue wait); only a task's second and later retry of the SAME
    cause waits `RETRY_SECONDS` after its scheduling (a backstop against a hot loop on one fault; the D16 caps bound
    the rest). ``idle`` is kept for callers and no longer delays anything."""
    del idle
    now = int(clock())
    earlier = _earlier_same_cause(root)

    def ready(task, at_ns):
        spacing = RETRY_SECONDS if earlier.get(task, 0) else 0
        return type(at_ns) is int and now - at_ns >= spacing * 1_000_000_000

    pending = sorted(
        (at_ns, task) for task, at_ns in _pending(root).items() if ready(task, at_ns)
    )
    return [task for _at_ns, task in pending]


#: CARBON-CUT REQUEUE (V2's ruling, 18 Nov 2026): how often the sweep looks for Carbon-side FAILED grades no retry was
#: ever scheduled for (a grade cut by our own stop or restart is marked at restore, never scheduled), and how far back.
SWEEP_SECONDS = 60 * 60
#: 72 h (Lead, 19 Nov 2026: tasks owed since 18 Nov 00:12Z must still be in reach when this ships)
SWEEP_WINDOW_SECONDS = 72 * 60 * 60
#: when this process last swept, per state root (monotonic seconds)
_SWEPT = {}
#: the owed-list line for a FAILED marker whose exam row is still COUNTED (released only by the operator's
#: `infra_requeue release`, which proves the result never reached the miner)
COUNTED_UNDER_FAILED = "counted_row_under_failed_marker"


def _held_rows(root):
    """``{task: {state, ...}}`` of every GRADED exam row (read-only), or None when the ledger cannot be read."""
    import sqlite3

    path = Path(root) / "attempts.sqlite3"
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            rows = db.execute(
                "SELECT submission_id, state FROM exam_graded WHERE kind='GRADED'"
            ).fetchall()
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - unreadable: nothing is scheduled
        return None
    held = {}
    for task, state in rows:
        held.setdefault(task, set()).add(state)
    return held


def sweep_carbon_cut(root, *, clock=time.time_ns, monotonic=time.monotonic):
    """At most once per `SWEEP_SECONDS` per process: schedule an automatic retry (`schedule`, under owner D16's caps)
    for every FAILED grade marker written in the last `SWEEP_WINDOW_SECONDS` that has none pending and none spent, and
    whose exam rows hold no slot (no COUNTED or RESERVED row: it was given back on Carbon's side). A FAILED marker is
    Carbon's by construction (the candidate's own outcome is CANDIDATE_FAILED). One with a COUNTED row is never
    retried here: it is named once on the owed list (`COUNTED_UNDER_FAILED`) for the operator's release. Returns the
    tasks scheduled. Never raises."""
    key = str(root)
    now = monotonic()
    last = _SWEPT.get(key)
    if last is not None and now - last < SWEEP_SECONDS:
        return []
    _SWEPT[key] = now
    try:
        held = _held_rows(root)
        if held is None:
            return []
        markers = Path(root) / "auto-grade" / "markers"
        cutoff = clock() / 1e9 - SWEEP_WINDOW_SECONDS
        pending = _pending(root)
        flagged = {
            r["task"]
            for r in _lines(_dir(root) / ALERT_NAME)
            if r.get("event") == COUNTED_UNDER_FAILED
        }
        scheduled = []
        for path in sorted(markers.glob("rtsk_*.json")):
            try:
                if path.stat().st_mtime < cutoff:
                    continue
                marker = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if type(marker) is not dict or marker.get("state") != "FAILED":
                continue
            task, code = path.stem, marker.get("code")
            states = held.get(task, set())
            if "COUNTED" in states:
                if task not in flagged:
                    _append(
                        _dir(root) / ALERT_NAME,
                        {
                            "task": task,
                            "event": COUNTED_UNDER_FAILED,
                            "reason": "owed_list",
                            "code": code,
                            "at_ns": int(clock()),
                        },
                    )
                    flagged.add(task)
                continue
            if "RESERVED" in states or task in pending or not retryable(code):
                continue
            if used(root, task, code=code):
                continue  # its cap's owed line was written when it was spent
            if schedule(root, task, code, clock=clock):
                scheduled.append(task)
        return scheduled
    except Exception:  # noqa: BLE001 - the sweep never fails the grader's round
        return []


def apply_due(root, *, draining=False, idle=True, clock=time.time_ns):
    """Hand each due retry back to the grader through `infra_requeue.requeue(auto=True)` (its criteria re-checked at
    the moment of applying). Each task is recorded applied or refused exactly once. Nothing while the door drains.
    A refused retry also writes an alert line (Validator-2B 8 Nov must-fix 2): the task's write-once marker still says
    ``retry_scheduled``, so the operator must learn that the retry did not happen.
    """
    if draining:
        return []
    from . import infra_requeue

    # a Carbon-side FAILED grade no retry was scheduled for (cut by our own stop or restart): scheduled here
    sweep_carbon_cut(root, clock=clock)
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
