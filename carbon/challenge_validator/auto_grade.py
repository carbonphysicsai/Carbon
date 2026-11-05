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
- **Paused crowns resume by themselves.** A crown decision the operator paused
  (`operator_pause`) is filed in the pool store; once the flag is gone each tick first makes those
  decisions again (`crown_pause_sweep`), from the filed evaluation, with no regrade.
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
import time
import traceback
from pathlib import Path

SCHEMA = "carbon.challenge-validator.auto-grade-marker.v1"
_TASK = re.compile(r"rtsk_[0-9a-f]{64}")
_PENDING = frozenset({"task_not_succeeded"})
#: Retention codes that mean "not gradable now" without having consumed anything.
_NOT_YET = frozenset({"owned_task_unavailable", "verified_attempt_unavailable"})


class AutoGrader:
    """Grades each SUCCEEDED task of one served adapter, once."""

    def __init__(
        self,
        intake,
        root,
        *,
        pool_store=None,
        host_lock=False,
        containers=None,
        sample_seconds=5.0,
    ):
        """``host_lock``: each grade runs under the host's official-grading lock (`direct_intake._WorkLock` with a
        lock dir). ``containers``: how many Carbon worker containers run on the host now (None = unknown); sampled
        every ``sample_seconds`` while a grade runs, for the wall-stop contention guard (Validator 4 Nov 17:16).
        """
        self.intake = intake
        self.host_lock = host_lock is True
        self.containers = count_worker_containers if containers is None else containers
        self.sample_seconds = sample_seconds
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

    def marker(self, submission_id):
        """The task's marker (``{"state", "code", ...}``), or None before it has one (or for a name
        that is not a task id, or an unreadable marker)."""
        if type(submission_id) is not str or not _TASK.fullmatch(submission_id):
            return None
        path = self._marker(submission_id)
        try:
            if path.is_symlink():
                return None
            body = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        return body if type(body) is dict and body.get("schema") == SCHEMA else None

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

        ``state`` is GRADED, CANDIDATE_FAILED, FAILED or PENDING (nothing written for PENDING).
        """
        from .lean_recipe_retention import RetentionUnavailable

        self._resume_paused_crowns()
        for submission_id in self.pending():
            sampler = _Sampler(self.containers, self.sample_seconds)
            started_ns = time.time_ns()
            try:
                with sampler:
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
                if _candidate_wall_stop(failure) and self._wall_counted(
                    submission_id, sampler, started_ns
                ):
                    # The candidate's own graph at the graded-inference wall: its outcome, COUNTED, never given back
                    # as infrastructure (Validator 4 Nov 16:52: else a changed recipe probes the hidden inputs free).
                    self._write(
                        submission_id, "CANDIDATE_FAILED", code=_WALL_LIMIT_REACHED
                    )
                    return submission_id, "CANDIDATE_FAILED"
                self._fail(submission_id, type(failure).__name__)
                return submission_id, "FAILED"
            entry = result.get("entry_id") if type(result) is dict else None
            if (
                type(result) is dict
                and result.get("private_evaluation_state") == "CANDIDATE_FAILED"
            ):
                # The candidate's own wall hit, twice, in the official inference pair
                # (Validator ruling 2026-11-01): typed, unscored, the slot COUNTED. Not a
                # FAILED marker, and nothing is given back.
                self._write(
                    submission_id,
                    "CANDIDATE_FAILED",
                    code=result.get("private_evaluation_reason"),
                    entry_id=entry if type(entry) is str else None,
                )
                return submission_id, "CANDIDATE_FAILED"
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

    def _resume_paused_crowns(self):
        """Make the crown decisions the operator's pause withheld, once it is lifted."""
        from . import crown_pause_sweep
        from .lean_recipe_retention import reconsider_paused_pack

        pool = self._pool()
        if pool is None or not hasattr(pool, "paused_crowns"):
            return
        adapter = self.intake.adapter
        crown_pause_sweep.sweep(
            pool,
            lambda record: reconsider_paused_pack(
                adapter,
                pool,
                record,
                artifact_directory=self.artifacts,
                entry_directory=self.entries,
            ),
            kind="pack",
            current_exam=adapter.discovery.evaluation_pack_digest,
        )

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
        # The pack digest every provider of this adapter is bound to (`lean_recipe._provider` refuses any other), read
        # without opening the owner's provider: that open re-checks registration, and a stale snapshot there made the
        # give-back itself raise, so a never-graded task kept no FAILED_INFRA row (REG-UNAVAILABLE, TL 4 Nov 03:14).
        exam_key = adapter.discovery.evaluation_pack_digest
        if exam_key is None:
            return None
        return ExamCap(adapter.ledger).give_back_on_infra(
            hotkey=owner,
            challenge_id=adapter.challenge_id,
            challenge_version=adapter.challenge_version,
            exam_key=exam_key,
            submission_id=submission_id,
        )

    def _wall_counted(self, submission_id, sampler, started_ns):
        """The contention guard (Validator 4 Nov 17:16, invariant 7) and the count itself. A wall stop is the
        candidate's only when this grade held the host lock for the whole run, no other Carbon worker container ran
        during it (every in-run sample saw at most this grade's own), and none ran at the stop (taken after the
        carrier removed this grade's own container, so it must read 0). Then this attempt's slot is re-settled
        COUNTED; any failure there gives it back as before, never a crash (the task would run again on hidden
        inputs). Logged AFTER the outcome is known (``auto-grade/wall-stops.jsonl``: counts only).
        """
        samples, stop = sampler.samples, sampler.stop_sample
        known = [s for s in samples if s is not None]
        uncontended = (
            self.host_lock
            and stop == 0
            and len(known) == len(samples)
            and (not known or max(known) <= 1)
        )
        counted = False
        if uncontended:
            try:
                counted = self._count_wall(submission_id, since_ns=started_ns)
            except Exception:  # noqa: BLE001 - give back as before, never a crash
                counted = False
        try:
            with open(
                self.markers.parent / "wall-stops.jsonl", "a", encoding="utf-8"
            ) as log:
                log.write(
                    json.dumps(
                        {
                            "task": submission_id,
                            "counted": counted,
                            "uncontended": uncontended,
                            "host_lock": self.host_lock,
                            "samples": len(samples),
                            "unknown_samples": len(samples) - len(known),
                            "max_worker_containers": max(known) if known else None,
                            "stop_worker_containers": stop,
                        },
                        sort_keys=True,
                    )
                    + chr(10)
                )
        except OSError:
            pass
        return counted

    def _count_wall(self, submission_id, *, since_ns):
        """Re-settle this task's slot COUNTED as the candidate's wall stop (`ExamCap.count_candidate_wall`); False
        when there is no such slot (the stop came before any reservation), so the failure is given back as before.
        """
        from .exam_cap import ExamCap

        adapter = self.intake.adapter
        owner = adapter.owner(submission_id)
        # the pack digest the bank grade reserved under (the discovery binds it == the snapshot's manifest digest)
        exam_key = adapter.discovery.evaluation_pack_digest
        if owner is None or exam_key is None:
            return False
        return (
            ExamCap(adapter.ledger).count_candidate_wall(
                hotkey=owner,
                challenge_id=adapter.challenge_id,
                challenge_version=adapter.challenge_version,
                exam_key=exam_key,
                submission_id=submission_id,
                since_ns=since_ns,
            )
            == "COUNTED"
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


_WALL_LIMIT_REACHED = "WORKER_WALL_LIMIT_REACHED"
#: The carrier names every worker container it starts ``carbon-d4-<launch digest>`` (`research_carrier`).
_WORKER_PREFIX = "carbon-d4-"


def count_worker_containers():
    """How many Carbon worker containers run on this host now, or None when the daemon cannot say."""
    import subprocess

    try:
        done = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=" + _WORKER_PREFIX,
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return sum(
        1
        for name in done.stdout.decode("utf-8", "replace").split()
        if name.startswith(_WORKER_PREFIX)
    )


class _Sampler:
    """Samples `count_worker_containers` every ``seconds`` while a grade runs, on its own thread. A call that returns
    within the first interval costs nothing (the not-ready tasks of every tick); a run that ends in a wall stop always
    has its samples, the last one taken at the stop."""

    def __init__(self, count, seconds):
        import threading

        self.count, self.seconds, self.samples = count, seconds, []
        self.stop_sample = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.wait(self.seconds):
            self.samples.append(self.count())

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, kind, value, _trace):
        self._stop.set()
        self._thread.join(self.seconds + 15)
        if kind is not None and _candidate_wall_stop(value):
            self.stop_sample = self.count()
        return False


def _candidate_wall_stop(error):
    """The carrier's OBSERVED candidate wall stop (the same predicate as
    `lean_recipe_retention._is_candidate_wall_hit`), never a host fault."""
    from carbon.development_session import research_carrier as carrier
    from carbon.reconstruction.worker.model import WorkerCode

    return (
        isinstance(error, carrier.MinerProgramFailure)
        and error.code is WorkerCode.DEADLINE
        and error.result.get("observation") == carrier.CANDIDATE_WALL_LIMIT
    )


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
