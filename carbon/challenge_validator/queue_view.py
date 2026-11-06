"""The receiver's queue reader for `queue_public` (``GET /carbon/v1/queue/<challenge_id>``): counts only, read from what
this door already keeps. Reads; writes nothing.

- **waiting to build / building now / waiting to grade:** the auto-grader's PENDING tasks (submitted, no verdict marker
  yet: `AutoGrader.pending`), split by the task's own provider state: QUEUED waits to build; RUNNING or CANCEL_REQUESTED
  is building; anything else (built, or a task whose provider this door no longer holds, e.g. admitted under an earlier
  contract, or requeued after an infrastructure failure) waits to grade. A pending task is always counted somewhere.
- **grading now:** this door's in-flight record (``work-inflight.json``, `direct_intake._WorkLock`) is a GRADE round and
  the grader is grading a submission (not its king's upkeep).
- **door state:** ``draining for an update`` while the operator's per-door DRAINING flag is set; ``paused`` while the
  door's chain read is stale (it grades nothing until the chain answers, H8); ``re-measuring the king`` while the
  grader runs its king's upkeep; otherwise ``grading``.
- **waits:** for every verdict marker written in the last 24 h: its write time minus the task's own creation time.

The snapshot is cached for `CACHE_S` seconds: a busy page never rescans the markers per request.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from . import queue_public as qp

CACHE_S = 30.0
DAY_S = 86400.0
_BUILDING = frozenset({"RUNNING", "CANCEL_REQUESTED"})


class QueueView:
    def __init__(self, intake, grader, state_dir, *, clock=time.time):
        self.intake = intake
        self.grader = grader
        self.state = Path(state_dir)
        self.clock = clock
        self._lock = threading.Lock()
        self._cached = None

    def _task_state(self, submission_id):
        """``(state name, created unix seconds)`` of a task in its own provider, or ``(None, None)``."""
        adapter = self.intake.adapter
        owner = adapter.owner(submission_id)
        if owner is None:
            return None, None
        view = adapter._provider(owner)._views.get(submission_id)
        if view is None:
            return None, None
        return view.state.value, view.created_at_micros / 1e6

    def _door_state(self):
        if (self.state / "draining").exists():
            return qp.DRAINING
        if self.grader.chain_degraded():
            return qp.PAUSED
        if getattr(self.grader, "activity", None) == "king":
            return qp.KING
        return qp.GRADING

    def _grading_now(self):
        try:
            record = json.loads((self.state / "work-inflight.json").read_bytes())
        except (OSError, ValueError):
            return 0
        grading = type(record) is dict and record.get("kind") == "grade"
        return int(grading and getattr(self.grader, "activity", None) == "grade")

    def _waits(self, now):
        waits = []
        for marker in self.grader.markers.glob("rtsk_*.json"):
            try:
                written = marker.stat().st_mtime
            except OSError:
                continue
            if now - written > DAY_S:
                continue
            _state, created = self._task_state(marker.stem)
            if created is not None and written >= created:
                waits.append(written - created)
        return waits

    def _read(self):
        now = self.clock()
        counts = {"waiting_to_build": 0, "building_now": 0, "waiting_to_grade": 0}
        for submission_id in self.grader.pending():
            state, _created = self._task_state(submission_id)
            if state == "QUEUED":
                counts["waiting_to_build"] += 1
            elif state in _BUILDING:
                counts["building_now"] += 1
            else:
                counts["waiting_to_grade"] += 1
        return {
            "door_state": self._door_state(),
            **counts,
            "grading_now": self._grading_now(),
            "waits_s": self._waits(now),
            "as_of_unix": now,
        }

    def snapshot(self):
        with self._lock:
            now = self.clock()
            if self._cached is None or now - self._cached["as_of_unix"] >= CACHE_S:
                self._cached = self._read()
            return dict(self._cached)
