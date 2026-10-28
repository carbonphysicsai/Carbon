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
import traceback
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
        self.failures = base / "failures"
        for directory in (self.artifacts, self.entries, self.markers, self.failures):
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
                self._keep(submission_id, unavailable)
                self._fail(submission_id, _code(code))
                return submission_id, "FAILED"
            except Exception as failure:  # noqa: BLE001 - typed, no private content
                self._keep(submission_id, failure)
                self._fail(submission_id, type(failure).__name__)
                return submission_id, "FAILED"
            entry = result.get("entry_id") if type(result) is dict else None
            # A grade that could not be computed keeps ITS reason in the marker (a typed code): an operator's
            # idempotent re-retention reports whatever it meets on the retry, which can hide the first reason.
            reason = (
                result.get("private_evaluation_reason")
                if type(result) is dict
                else None
            )
            self._write(
                submission_id,
                "GRADED",
                code=_code(reason) if type(reason) is str and reason else None,
                entry_id=entry if type(entry) is str else None,
            )
            return submission_id, "GRADED"
        return None

    def _keep(self, submission_id, failure):
        """The full traceback of a failed grade, and a worker failure's closed code and
        private diagnostic, in this receiver's PRIVATE evidence (``auto-grade/failures/``,
        owner-only, create-only, one file per task). The marker and the log carry the
        failure's type or code only; this is where an operator reads WHY (valV3 2026-10-27:
        a marker said only 'WorkerFailure'). Best effort: it never changes the outcome.
        """
        try:
            path = self.failures / (submission_id + ".txt")
            diagnostic = getattr(failure, "private_diagnostic", None)
            code = getattr(failure, "code", None)
            lines = ["".join(traceback.format_exception(failure))]
            if code is not None:
                lines.append(f"code: {getattr(code, 'value', code)}")
            if type(diagnostic) is bytes and diagnostic:
                lines.append("private diagnostic (worker output, truncated):")
                lines.append(diagnostic[:16384].decode("utf-8", "replace"))
            text = chr(10).join(lines) + chr(10)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                out.write(text)
        except Exception:  # noqa: BLE001, S110 - evidence is best effort
            pass

    def _fail(self, submission_id, code):
        """Mark the failure and give the grading back on our infrastructure
        (invariant 7): the task stays SUCCEEDED but its exam row is RELEASED as
        FAILED_INFRA, so the miner's resubmit of the recipe runs as a fresh task
        in their next slot. A graded (COUNTED) row is never given back."""
        state = None
        try:
            state = self._give_back(submission_id)
        except Exception:  # noqa: BLE001 - the marker below still records the failure
            state = "UNRECORDED"
        self._write(
            submission_id,
            "FAILED",
            code=code if state in (None, "RELEASED") else code + ":" + state.lower(),
        )

    def _give_back(self, submission_id):
        from .exam_cap import ExamCap

        adapter = self.intake.adapter
        owner = adapter.owner(submission_id)
        if owner is None:
            return None
        provider = adapter._provider(owner)
        exam_key = provider.evaluation_pack_digest
        if exam_key is None:
            return None
        return ExamCap(adapter.ledger).give_back_on_infra(
            hotkey=owner,
            challenge_id=adapter.challenge_id,
            challenge_version=adapter.challenge_version,
            exam_key=exam_key,
            submission_id=submission_id,
        )

    def failures(self):
        """``(count, last code)`` of FAILED markers, for the operator's status."""
        found = []
        for path in sorted(self.markers.glob("*.json")):
            try:
                body = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            if body.get("state") == "FAILED":
                found.append((path.stat().st_mtime_ns, body.get("code")))
        found.sort()
        return len(found), (found[-1][1] if found else None)

    def _pool(self):
        if self.pool_store is None:
            return None
        from .direct_receiver import _open_pool_store

        return _open_pool_store(self.pool_store)


def _code(value):
    return (
        value if re.fullmatch(r"[a-z0-9_.:-]{1,96}", value) else "retention_unavailable"
    )


def failure_summary(root):
    """What an operator's status shows about auto-grade: how many tasks ended FAILED
    and the last failure's code (``{}`` when no receiver auto-grades). Reads markers
    only; never a score, a path or a task's content."""
    markers = Path(root) / "auto-grade" / "markers"
    if not markers.is_dir() or markers.is_symlink():
        return {}
    found = []
    for path in sorted(markers.glob("*.json")):
        try:
            body = json.loads(path.read_text())
            if body.get("state") == "FAILED":
                found.append((path.stat().st_mtime_ns, body.get("code")))
        except (OSError, ValueError):
            continue
    found.sort()
    return {
        "auto_grade_failed": len(found),
        "auto_grade_last_failure": found[-1][1] if found else None,
    }
