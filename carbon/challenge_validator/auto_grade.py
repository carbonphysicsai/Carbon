"""A receiver that grades its own submissions (E2E gap 1; Ladder v3).

Until now a graded row existed only after an operator stopped the serve unit and ran
`--retain-task` by hand. With `"auto_grade"` in the receiver configuration the serving
process does it itself: each task that reaches SUCCEEDED is retained and graded once, by
the same `retain_result` the operator call uses (bank custody, the selected pack's
private evaluation, the Ladder document that names its submission and epoch, KOTH). The
grade is the receiver's ordinary official path; nothing here scores, ranks or decides.

Safety properties:
- **Once.** A create-only marker per task. Retention consumes a task's single inference
  pair, so a failed attempt is never retried by itself: its marker records the typed
  code, and an operator deletes the marker to retry.
- **Not while building.** Grading and the construction `advance` pass share one lock, so
  a grade never competes with a reconstruction for the host.
- **Never a candidate failure.** An unavailable retention is recorded as infrastructure
  (`state` FAILED, a code), not as a scientific result.
- **No secrets.** Markers hold the task id, state, a code and the entry id (digests).

DEVELOPMENT receiver only; mainnet policy is not decided here.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

SCHEMA = "carbon.challenge-validator.auto-grade-marker.v1"
_TASK = re.compile(r"rtsk_[0-9a-f]{64}")
_PENDING = frozenset({"task_not_succeeded"})
#: Retention codes that mean "not gradable now" without having consumed anything.
_NOT_YET = frozenset({"owned_task_unavailable", "verified_attempt_unavailable"})


class AutoGrader:
    """Grades each SUCCEEDED task of one served adapter, once."""

    def __init__(self, intake, root, *, pool_store=None):
        self.intake = intake
        base = Path(root) / "auto-grade"
        self.artifacts = base / "artifacts"
        self.entries = base / "entries"
        self.markers = base / "markers"
        self.pool_store = pool_store
        for directory in (self.artifacts, self.entries, self.markers):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _marker(self, submission_id):
        return self.markers / (submission_id + ".json")

    def _write(self, submission_id, state, *, code=None, entry_id=None):
        body = {
            "schema": SCHEMA,
            "submission_id": submission_id,
            "state": state,
            "code": code,
            "entry_id": entry_id,
        }
        fd = os.open(
            self._marker(submission_id), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(fd, "w") as handle:
            json.dump(body, handle, sort_keys=True)
            handle.write("\n")

    def pending(self):
        """Task ids with no marker yet, in the ledger's order."""
        adapter = self.intake.adapter
        return [
            s
            for s in adapter.ledger.submitted_outcomes(adapter.contract_digest)
            if _TASK.fullmatch(s) and not self._marker(s).exists()
        ]

    def run_once(self):
        """Grade at most one ready task; returns ``(submission_id, state)`` or None.

        ``state`` is GRADED, FAILED or PENDING (nothing written for PENDING)."""
        from .lean_recipe_retention import RetentionUnavailable

        for submission_id in self.pending():
            try:
                result = self.intake.retain_result(
                    submission_id,
                    artifact_directory=self.artifacts,
                    entry_directory=self.entries,
                    pool_store=self._pool(),
                )
            except RetentionUnavailable as unavailable:
                code = getattr(unavailable, "code", None) or str(unavailable)
                if code in _PENDING or code in _NOT_YET:
                    continue
                self._write(submission_id, "FAILED", code=_code(code))
                return submission_id, "FAILED"
            except Exception as failure:  # noqa: BLE001 - typed, no private content
                self._write(submission_id, "FAILED", code=type(failure).__name__)
                return submission_id, "FAILED"
            entry = result.get("entry_id") if type(result) is dict else None
            self._write(
                submission_id,
                "GRADED",
                entry_id=entry if type(entry) is str else None,
            )
            return submission_id, "GRADED"
        return None

    def _pool(self):
        if self.pool_store is None:
            return None
        from .direct_receiver import _open_pool_store

        return _open_pool_store(self.pool_store)


def _code(value):
    return (
        value if re.fullmatch(r"[a-z0-9_.:-]{1,96}", value) else "retention_unavailable"
    )
