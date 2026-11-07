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
#: The one state that waits for a grade: built, no verdict yet.
_BUILT = "SUCCEEDED"


class QueueView:
    def __init__(self, intake, grader, state_dir, *, clock=time.time):
        self.intake = intake
        self.grader = grader
        self.state = Path(state_dir)
        self.clock = clock
        self._lock = threading.Lock()
        self._cached = None

    def _index(self):
        """``{task id: (state name, created unix seconds)}`` over the providers already open on this receiver: a
        read of their task views only (never opens one, never takes a lock, never asks ``owner()`` / ``_provider()``).
        """
        opened = getattr(self.intake.adapter.provider_for, "_providers", None)
        if not isinstance(opened, dict):
            return {}
        for _attempt in range(2):
            try:
                providers = tuple(opened.values())
                break
            except (
                RuntimeError
            ):  # the receiver opened or closed a provider mid-read: read once more
                continue
        else:
            # still changing: the page answers 503 (the contract), never a 500 or a guess (Validator-2 15:11)
            raise qp.QueuePublicRefused("queue_unavailable")
        index = {}
        for provider in providers:
            try:
                views = tuple(getattr(provider, "_views", {}).items())
            except (
                RuntimeError
            ):  # changed while read: its tasks drop out of this snapshot only
                continue
            for task, view in views:
                try:
                    index[task] = (view.state.value, view.created_at_micros / 1e6)
                except (AttributeError, TypeError):
                    # a malformed view is not a count: the page answers 503, never a guess (Validator-2 12:24)
                    raise qp.QueuePublicRefused(
                        "queue_provider_state_invalid"
                    ) from None
        return index

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

    def _waits(self, now, index):
        waits = []
        for marker in self.grader.markers.glob("rtsk_*.json"):
            try:
                written = marker.stat().st_mtime
            except OSError:
                continue
            if now - written > DAY_S:
                continue
            _state, created = index.get(marker.stem, (None, None))
            if created is not None and written >= created:
                waits.append(written - created)
        return waits

    def _read(self):
        now = self.clock()
        index = self._index()
        counts = {"waiting_to_build": 0, "building_now": 0, "waiting_to_grade": 0}
        for submission_id in self.grader.pending():
            state, _created = index.get(submission_id, (None, None))
            if state == "QUEUED":
                counts["waiting_to_build"] += 1
            elif state in _BUILDING:
                counts["building_now"] += 1
            elif state == _BUILT:
                counts["waiting_to_grade"] += 1
            # cancelled, a build that ended without success, or a task in no open store: closed, never waiting
        return {
            "door_state": self._door_state(),
            **counts,
            "grading_now": self._grading_now(),
            "waits_s": self._waits(now, index),
            "as_of_unix": now,
        }

    def snapshot(self):
        with self._lock:
            now = self.clock()
            if self._cached is None or now - self._cached["as_of_unix"] >= CACHE_S:
                self._cached = self._read()
            return dict(self._cached)
