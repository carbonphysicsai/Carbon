"""The receiver's queue reader for `queue_public` (``GET /carbon/v1/queue/<challenge_id>``): counts only, read from what
this door already keeps. Reads; writes nothing.

- **waiting to build / building now / waiting to grade:** the auto-grader's PENDING tasks (submitted, no verdict marker
  yet: `AutoGrader.pending`), split by the task's own state in the providers ALREADY OPEN on this receiver: QUEUED
  waits to build; RUNNING or CANCEL_REQUESTED is building; SUCCEEDED (built, its grade not run yet) waits to grade.
  NOTHING ELSE is counted (Deploy 6 Nov 18:59, all 4 doors read-only): a miner-CANCELLED task, a build that ended
  REFUSED / FAILED_INFRA / UNRESOLVED, and a task no open store holds (A2 'archived for resubmit') never get a verdict
  marker, so they stay in `pending()` forever; counting them inflated RB's queue by ~270 with none truly waiting.
- **A GET never slows a grade** (Validator-2 12:37): task states come from ONE pass over the open providers' task views
  (dict reads, no lock taken, no provider opened, no `owner()` / `_provider()` call, so no source-identity hashing and no
  registration read). A provider being changed mid-read is skipped for that one snapshot (its tasks drop out of the
  counts until the next read, 30 s later: a brief undercount, never an inflated queue).
- **what actually runs, in the ROWS (Live ops' queue truth audit, 18 Nov 2026):** a RUNNING task is BUILDING only
  while one of its
  own operations (prep, build, practice inference or timing, `direct_child_identity`; or its remote GPU build's
  shadow) is RESERVED in its owner's campaign ledger, which happens only once it holds a build slot;
  a RUNNING task with none is still WAITING TO BUILD (its round waits for a slot). The counts keep RUNNING as building
  (the A100 autoscaler sizes on ``waiting_to_build``, and such a task may wait for a CPU lane, not an A100). The
  ledger is read on a read-only connection (``mode=ro``: no write lock, never blocks a build or a grade); an unreadable
  ledger counts its RUNNING tasks as building, as before. A SUCCEEDED task whose grade is already claimed (in flight,
  `grade_sequencer`) is no longer waiting to grade.
- **grading now:** on a door grading one round per lane, 1 while any claimed grade is in flight; else this door's
  in-flight record (``work-inflight.json``, `direct_intake._WorkLock`) is a GRADE round and the grader is grading a
  submission (not its king's upkeep).
- **door state:** ``draining for an update`` while the operator's per-door DRAINING flag is set; ``paused`` while the
  door's chain read is stale (it grades nothing until the chain answers, H8); ``re-measuring the king`` while the
  grader runs its king's upkeep; otherwise ``grading``.
- **waits:** for every VERDICT marker (GRADED or CANDIDATE_FAILED) written in the last 24 h: its write time minus the
  task's own creation time. Not samples (18 Nov 2026): a FAILED marker (no verdict), a withdrawal, and a task handed
  back and graded again (a kept ``requeued/<id>.attempt-N.marker.json``: its clock runs from its first arrival, through
  our outage, not the wait a submission now meets).

- **held for review (v2):** on a door whose crown hold is on (`crown_hold.holding()`: a menu-D version whose hold the registry does not list off), the
  unresolved filed contenders (`PoolStore.paused_crowns`, all kinds, filing order). Neither that record nor the grade
  marker keeps WHY a contender was filed, and on such a door every crown change is held before anything else is
  decided, so each is waiting for a crown decision. On every other door: None.

The snapshot is cached for `CACHE_S` seconds: a busy page never rescans the markers per request.

PER-SUBMISSION ROWS (v3, owner 14 Nov "show the actual queue"; `snapshot_v3`): one row per pending submission, oldest first, then
one per graded contender waiting for the crown sweep ("crown check"). A row is ``position``, ``hotkey`` (first and last 4 characters
of the OWNING provider's key: the open providers' own keys, never an ``owner()`` / ``_provider()`` call), ``state`` and ``in_queue_s``
(seconds since the task was created, floored to `queue_public.ROWS_QUANTUM_S`). The rows are rebuilt ONLY when the wall clock crosses
a quantum boundary, never per request, so no row's state or disappearance is visible finer than the quantum: the per-submission timing
channel a finer view would open (a model that spends longer on some hidden input would show it in its own row's duration) is cut to
that resolution. Nothing else about a submission is read: no recipe, score, pack, case or duration.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from . import queue_public as qp

CACHE_S = 30.0
DAY_S = 86400.0
_BUILDING = frozenset({"RUNNING", "CANCEL_REQUESTED"})
#: The verdict markers whose write time ends a submission's wait (`auto_grade`).
_VERDICTS = frozenset({"GRADED", "CANDIDATE_FAILED"})
#: The one state that waits for a grade: built, no verdict yet.
_BUILT = "SUCCEEDED"


def _marker_state(marker):
    """The marker's ``state``, or None when it cannot be read."""
    try:
        body = json.loads(marker.read_bytes())
    except (OSError, ValueError):
        return None
    return body.get("state") if type(body) is dict else None


def _withdrawn(marker):
    """Whether the marker file is a withdrawal's (`auto_grade.WITHDRAWN_STATE`); read only for a CANCELLED task."""
    from .auto_grade import WITHDRAWN_STATE

    try:
        body = json.loads(marker.read_bytes())
    except (OSError, ValueError):
        return False
    return type(body) is dict and body.get("state") == WITHDRAWN_STATE


class QueueView:
    def __init__(self, intake, grader, state_dir, *, clock=time.time):
        self.intake = intake
        self.grader = grader
        self.state = Path(state_dir)
        self.clock = clock
        self._lock = threading.Lock()
        self._cached = None
        self._rows_cached = None
        #: ``{task id: provider key}`` from the last `_index` pass (the owning provider's own key; read only).
        self._owners = {}

    def _index(self):
        """``{task id: (state name, created unix seconds)}`` over the providers already open on this receiver: a
        read of their task views only (never opens one, never takes a lock, never asks ``owner()`` / ``_provider()``).
        """
        opened = getattr(self.intake.adapter.provider_for, "_providers", None)
        if not isinstance(opened, dict):
            return {}
        for _attempt in range(2):
            try:
                providers = tuple(opened.items())
                break
            except (
                RuntimeError
            ):  # the receiver opened or closed a provider mid-read: read once more
                continue
        else:
            # still changing: the page answers 503 (the contract), never a 500 or a guess (Validator-2 15:11)
            raise qp.QueuePublicRefused("queue_unavailable")
        index, owners = {}, {}
        for key, provider in providers:
            try:
                views = tuple(getattr(provider, "_views", {}).items())
            except (
                RuntimeError
            ):  # changed while read: its tasks drop out of this snapshot only
                continue
            for task, view in views:
                try:
                    index[task] = (view.state.value, view.created_at_micros / 1e6)
                    owners[task] = key
                except (AttributeError, TypeError):
                    # a malformed view is not a count: the page answers 503, never a guess (Validator-2 12:24)
                    raise qp.QueuePublicRefused(
                        "queue_provider_state_invalid"
                    ) from None
        self._owners = owners
        return index

    def _reserved_ops(self, provider):
        """The operation ids RESERVED in ``provider``'s campaign ledger, read on a read-only connection (never a write
        lock, never a wait past a second), or None when it cannot be read."""
        path = getattr(getattr(provider, "ledger", None), "path", None)
        if path is None:
            return None
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)
            try:
                rows = db.execute(
                    "SELECT id FROM operations WHERE state='RESERVED'"
                ).fetchall()
            finally:
                db.close()
        except sqlite3.Error:
            return None
        return {row[0] for row in rows}

    def _waiting_for_slot(self, index):
        """The RUNNING tasks no build operation of which is RESERVED: their round is still waiting for a build slot."""
        from carbon.development_session.bundle_construction_worker import (
            direct_child_identity,
        )

        opened = getattr(self.intake.adapter.provider_for, "_providers", None)
        if not isinstance(opened, dict):
            return set()
        reserved, waiting = {}, set()
        for task, (state, _created) in index.items():
            if state != "RUNNING":
                continue
            key = self._owners.get(task)
            provider = opened.get(key)
            if provider is None:
                continue
            if key not in reserved:
                reserved[key] = self._reserved_ops(provider)
            held = reserved[key]
            if held is None:
                continue  # unreadable: counted as building, as before
            # any of the task's own operations (`direct_child_identity`: prep, build, practice inference, timing, or
            # its remote GPU build shadow) RESERVED: it holds a slot and runs
            own = direct_child_identity(task, "build")[: -len("build")]
            if not any(op.startswith(own) or op.startswith(task) for op in held):
                waiting.add(task)
        return waiting

    def _claimed_grades(self):
        sequencer = getattr(self.grader, "sequencer", None)
        return set() if sequencer is None else set(sequencer.in_flight())

    def held(self):
        """The held contenders' submission ids, oldest filing first, on a crown-hold door; None on every other door.
        A read of the pool store's filed contenders only (no grade, no lock)."""
        from . import crown_hold

        if not crown_hold.holding():
            return None
        opener = getattr(self.grader, "_pool", None)
        store = opener() if callable(opener) else None
        if store is None:
            return []
        return [record["submission_id"] for record in store.paused_crowns()]

    def _door_state(self):
        if (self.state / "draining").exists():
            return qp.DRAINING
        if self.grader.chain_degraded():
            return qp.PAUSED
        if getattr(self.grader, "activity", None) == "king":
            return qp.KING
        return qp.GRADING

    def _grading_now(self):
        """1 while this door grades, else 0 (the public flag). A door grading one round per lane (`grade_sequencer`)
        grades while any claimed grade is in flight (Lead, 18 Nov 2026: live 116 showed 0 with 5 grades running, because
        its one in-flight record and one activity field are a single-round door's)."""
        sequencer = getattr(self.grader, "sequencer", None)
        if sequencer is not None:
            return int(bool(sequencer.in_flight()))
        try:
            record = json.loads((self.state / "work-inflight.json").read_bytes())
        except (OSError, ValueError):
            return 0
        grading = type(record) is dict and record.get("kind") == "grade"
        return int(grading and getattr(self.grader, "activity", None) == "grade")

    def _waits(self, now, index):
        waits = []
        kept = self.grader.markers.parent / "requeued"
        for marker in self.grader.markers.glob("rtsk_*.json"):
            try:
                written = marker.stat().st_mtime
            except OSError:
                continue
            if now - written > DAY_S:
                continue
            state, created = index.get(marker.stem, (None, None))
            if state == "CANCELLED" and _withdrawn(marker):
                continue  # withdrawn by its owner while queued: no grade was waited for
            if _marker_state(marker) not in _VERDICTS:
                continue  # no verdict (a FAILED marker): not a wait for a grade
            if (kept / (marker.stem + ".attempt-1.marker.json")).exists():
                continue  # handed back and graded again: its clock runs through our outage
            if created is not None and written >= created:
                waits.append(written - created)
        return waits

    def _read(self):
        now = self.clock()
        index = self._index()
        counts = {"waiting_to_build": 0, "building_now": 0, "waiting_to_grade": 0}
        claimed = self._claimed_grades()
        for submission_id in self.grader.pending():
            state, _created = index.get(submission_id, (None, None))
            # the COUNTS keep RUNNING as building (V2, 18 Nov 2026): the A100 autoscaler sizes on `waiting_to_build`,
            # and a RUNNING task waiting for a slot may wait for a CPU lane, not an A100; only the rows tell them apart
            if state == "QUEUED":
                counts["waiting_to_build"] += 1
            elif state in _BUILDING:
                counts["building_now"] += 1
            elif state == _BUILT and submission_id not in claimed:
                counts["waiting_to_grade"] += 1
            # cancelled, a build that ended without success, or a task in no open store: closed, never waiting
        return {
            "door_state": self._door_state(),
            **counts,
            "grading_now": self._grading_now(),
            "waits_s": self._waits(now, index),
            "as_of_unix": now,
            qp.HELD: None if (held := self.held()) is None else len(held),
        }

    def _read_rows(self, boundary):
        """The per-submission rows as of the quantum ``boundary`` (see the module text): pending submissions in the ledger's order
        (oldest first), then the graded contenders waiting for the crown sweep."""
        index = self._index()
        origins = self._place_origins()
        slotless = self._waiting_for_slot(index)
        entries = []
        for submission_id in self.grader.pending():
            state, created = index.get(submission_id, (None, None))
            if state == "QUEUED" or submission_id in slotless:
                label = qp.WAITING_TO_BUILD
            elif state in _BUILDING:
                label = qp.BUILDING
            elif state == _BUILT:
                label = (
                    qp.IN_GRADING
                )  # built, no verdict yet: waiting or being graded, not told apart per row
            else:
                continue  # cancelled, a build that ended without success, or a task in no open store: never waiting
            if created is not None and submission_id in origins:
                # a granted queue place: the wait runs from the ORIGINAL arrival (the clock only moves earlier, never later)
                created = min(created, origins[submission_id])
            entries.append((submission_id, label, created))
        for submission_id, since in self._crown_checks():
            entries.append((submission_id, qp.CROWN_CHECK, since))
        rows = []
        for position, (submission_id, label, created) in enumerate(entries, 1):
            age = 0 if created is None else boundary - created
            rows.append(
                {
                    "position": position,
                    "hotkey": qp.short_hotkey(self._owners.get(submission_id)),
                    "state": label,
                    "in_queue_s": qp.floor_to_quantum(age),
                }
            )
        return rows

    def _place_origins(self):
        """``{task id: original arrival (unix seconds)}`` of every task that holds a queue place (`AttemptLedger.grant_queue_place`: a
        resubmission of a stop-cancelled task takes that task's original arrival PLACE, so its rank is the original's while its task is new).
        Counting its wait from the ORIGINAL arrival makes the clock agree with the rank. A ledger without the read (a stand-in) gives none.
        """
        adapter = self.intake.adapter
        reader = getattr(getattr(adapter, "ledger", None), "queue_place_origins", None)
        if not callable(reader):
            return {}
        try:
            return {
                task: ns / 1e9 for task, ns in reader(adapter.contract_digest).items()
            }
        except (OSError, ValueError, sqlite3.Error) as failure:
            raise qp.QueuePublicRefused("queue_rows_unavailable") from failure

    def _crown_checks(self):
        """``[(submission id, graded-at unix seconds or None)]`` of the graded contenders still waiting for the crown sweep
        (`PoolStore.paused_crowns`, filing order). A read of the pool's filed contenders and the grade markers' write times only.
        """
        opener = getattr(self.grader, "_pool", None)
        try:
            store = opener() if callable(opener) else None
            records = [] if store is None else store.paused_crowns()
        except (OSError, ValueError, KeyError, LookupError) as failure:
            raise qp.QueuePublicRefused("queue_rows_unavailable") from failure
        waiting = []
        for record in records:
            submission_id = record["submission_id"]
            try:
                graded = (self.grader.markers / f"{submission_id}.json").stat().st_mtime
            except OSError:
                graded = None
            waiting.append((submission_id, graded))
        return waiting

    def snapshot_v3(self):
        """`snapshot` plus the per-submission rows, rebuilt only when the clock crosses a quantum boundary."""
        base = self.snapshot()
        with self._lock:
            boundary = int(self.clock() // qp.ROWS_QUANTUM_S) * qp.ROWS_QUANTUM_S
            if self._rows_cached is None or self._rows_cached["as_of_unix"] != boundary:
                self._rows_cached = {
                    "rows": self._read_rows(boundary),
                    "as_of_unix": float(boundary),
                }
            return {qp.ROWS: dict(self._rows_cached), **base}

    def snapshot(self):
        with self._lock:
            now = self.clock()
            if self._cached is None or now - self._cached["as_of_unix"] >= CACHE_S:
                self._cached = self._read()
            return dict(self._cached)
