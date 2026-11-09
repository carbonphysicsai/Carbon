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
#: A provider that could not read the owner's registration from a fresh snapshot. While the door's chain is degraded
#: this is a chain read that failed: the task waits and is graded once the chain answers, never FAILED and never a
#: slot given back (H8; R38, 5 Nov). With a fresh snapshot it means what it always meant (handled as before).
_CHAIN_CODES = frozenset({"direct_provider_registration_unavailable"})


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
        gpu=None,
    ):
        """``host_lock``: each grade runs under the host's official-grading lock (`direct_intake._WorkLock` with a
        lock dir). ``containers``: how many Carbon worker containers run on the host now (None = unknown); sampled
        every ``sample_seconds`` while a grade runs, for the wall-stop contention guard (Validator 4 Nov 17:16).
        ``gpu``: how many foreign GPU compute processes run now (None = unknown; `host_quiet.foreign_gpu_compute`),
        sampled beside it: the quiet-host rule's GPU condition (Validator-2 5 Nov 21:28). The same three conditions
        decide whether a crown rebuild's failure was the model's or a busy host's (`host_quiet`).
        """
        self.intake = intake
        self.host_lock = host_lock is True
        self.containers = count_worker_containers if containers is None else containers
        from . import host_quiet

        self.gpu = host_quiet.foreign_gpu_compute if gpu is None else gpu
        self.sample_seconds = sample_seconds
        self.root = Path(root)
        base = self.root / "auto-grade"
        self.artifacts = base / "artifacts"
        self.entries = base / "entries"
        self.markers = base / "markers"
        self.pool_store = pool_store
        self.failures = base / "failures"
        #: What this grader is doing right now, for the public queue view (`queue_view`): "king" during the king's
        #: upkeep, "grade" while a submission is graded, else None. Read only; it gates nothing.
        self.activity = None
        for directory in (self.artifacts, self.entries, self.markers, self.failures):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if pool_store is not None and hasattr(intake.adapter.ledger, "_db"):
            # OWNER-PROBING-COUNTERS-01 (b) is not retroactive: every submission already admitted when this grader
            # starts after the release is outside the copy rule (`recipe_copies.activate`, first start wins).
            from . import recipe_copies

            adapter = intake.adapter
            recipe_copies.activate(adapter.ledger, adapter.contract_digest)

    def _marker(self, submission_id):
        return self.markers / (submission_id + ".json")

    def _write(self, submission_id, state, *, code=None, entry_id=None, next_step=None):
        body = {
            "schema": SCHEMA,
            "submission_id": submission_id,
            "state": state,
            "code": code,
            "entry_id": entry_id,
            # a FAILED grade's next step (`auto_retry.NEXT_STEPS`, R39); absent on every other marker
            **({} if next_step is None else {"next_step": next_step}),
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

    def has_work(self):
        """Whether a grade round has anything to do: a task with no marker yet, or a paused crown decision the sweep
        would make NOW (`crown_pause_sweep.sweep`'s own gates: crowns not paused by the operator, kind ``pack``, the
        first unresolved record not inside its one-epoch retry spacing). A round without either never takes the
        host's grading lock (MAINNET_UPDATE_ARCHITECTURE s2.4 Step A), so an idle door never stands between another
        door and its grade, or between a deploy and its idle check.

        With the king's upkeep (`king_upkeep`), a round also runs: once after every start (it queues the challengers
        stranded while the king could not be met, ahead of any new grade), and whenever the upkeep is due (`due`: the
        king's regrade, or one crown re-measure rebuild), so an idle door still keeps its king comparable.
        """
        if self.chain_degraded():
            # No fresh chain snapshot: every round would open a provider against a stale chain (H8). Nothing runs,
            # nothing is marked; the round resumes by itself when the snapshot refresher reads the chain again.
            return False
        if self._stranded_due():
            return True
        if self.pending():
            return True
        if self._retries_due():
            return True
        if self._crowns_due():
            return True
        return self._upkeep_due()

    def _retries_due(self):
        """Whether an automatic retry (R39) is due on this idle door: without it a quiet door never runs the round
        that applies it. Never raises (doubt waits for the next round with other work).
        """
        from . import auto_retry

        try:
            return bool(auto_retry.due(self.root, idle=True))
        except Exception:  # noqa: BLE001
            return False

    def chain_degraded(self):
        """Whether this door has no fresh chain snapshot now (the intake's window: ``latest()`` is None past its age
        bound, on a conflict, or while unavailable). A grader without a window (tests, tools) is never degraded.
        """
        window = getattr(self.intake, "window", None)
        if window is None:
            return False
        try:
            return window.latest() is None
        except Exception:  # noqa: BLE001
            # an unreadable window is a degraded chain: grade nothing until it reads
            return True

    def _stranded_due(self):
        """Whether the start-up filing of stranded challengers is still to be made now (`_king_upkeep`)."""
        if getattr(self, "_stranded_filed", False):
            return False
        return time.monotonic() >= getattr(self, "_stranded_next", 0.0)

    def _upkeep_due(self):
        from . import crown_average, king_upkeep

        try:
            pool = self._pool()
        except Exception:  # noqa: BLE001
            # doubt runs the round, where the sweep reports an unopenable store
            return True
        return king_upkeep.due(pool, self.intake, active=crown_average.ACTIVE)

    def _crowns_due(self):
        from . import crown_hold, crown_pause_sweep, operator_pause

        pool = self._pool()
        if pool is None or not hasattr(pool, "paused_crowns"):
            return False
        if operator_pause.crowns_paused(pool.path.parent):
            return False
        incumbent = pool.incumbent() or {}
        exam = self.intake.adapter.discovery.evaluation_pack_digest
        awaits = getattr(pool, "awaits_incumbent_regrade", None)
        for record in pool.paused_crowns("pack"):
            if (
                incumbent.get("model_id") == record["submission_id"]
                or record["exam"] != exam
            ):
                return True  # resolved at once, without a grade
            if awaits is not None and awaits(record):
                # the sweep skips it until the king's regrade, which `_upkeep_due` asks about: no round for it here,
                # else a failing regrade (retried once an epoch) would take the host lock every poll for nothing
                continue
            if crown_hold.held(pool.path.parent, record["submission_id"]):
                return False  # a held menu-D crown stops the sweep there until the operator's release: no round
            attempts, last = pool.crown_pause_attempts(
                record["submission_id"], record["evaluation_key"]
            )
            return not (crown_pause_sweep.spaced(pool, attempts, last))
        return False

    def run_once(self):
        """Grade at most one ready task; returns ``(submission_id, state)`` or None.

        ``state`` is GRADED, CANDIDATE_FAILED, FAILED or PENDING (nothing written for PENDING). Every crown rebuild
        started inside it (the king's re-measure, a challenger's averaging) probes whether the host is quiet
        (`host_quiet`): this loop holds the host lock exactly when ``host_lock``.
        """
        from . import host_quiet

        # (a grader built without __init__, as some tests do, probes with the not-quiet defaults: no lock held)
        token = host_quiet.activate(
            lock_held=getattr(self, "host_lock", False),
            containers=getattr(self, "containers", count_worker_containers),
            gpu=getattr(self, "gpu", host_quiet.foreign_gpu_compute),
            seconds=getattr(self, "sample_seconds", 5.0),
        )
        try:
            return self._run_once()
        finally:
            host_quiet.deactivate(token)

    def _run_once(self):
        from .lean_recipe_retention import RetentionUnavailable

        if self.chain_degraded():
            return None  # (H8) a stale chain: grade nothing, mark nothing
        self.activity = "king"
        try:
            self._king_upkeep()
        finally:
            self.activity = None
        self._resume_paused_crowns()
        pending = self.pending()
        if self._apply_due_retries(idle=not pending):
            pending = self.pending()  # a retry handed back is graded in this round
        for submission_id in pending:
            copy = self._copy_decision(submission_id)
            if copy is not None:
                decision, first = copy
                if decision == "wait":
                    # an earlier identical recipe is still unsettled on this key: retried next round (counted for the
                    # operator's read: `recipe_copy_waits`)
                    self.recipe_copy_waits = getattr(self, "recipe_copy_waits", 0) + 1
                    self._log_copy_waits()
                    continue
                if decision == "copy":
                    return self._grade_copy(submission_id, first)
            sampler = _Sampler(
                self.containers, self.sample_seconds, getattr(self, "gpu", None)
            )
            started_ns = time.time_ns()
            try:
                self.activity = "grade"
                try:
                    with sampler:
                        result = self.intake.retain_result(
                            submission_id,
                            artifact_directory=self.artifacts,
                            entry_directory=self.entries,
                            pool_store=self._pool(),
                        )
                finally:
                    self.activity = None
            except RetentionUnavailable as unavailable:
                code = getattr(unavailable, "code", None) or str(unavailable)
                if not isinstance(code, str):
                    # a non-str code (unhashable, e.g. a structured worker code) is never a set member: typed by text
                    code = str(unavailable) or type(unavailable).__name__
                if code in _PENDING or code in _NOT_YET:
                    continue
                if (
                    isinstance(code, str)
                    and code in _CHAIN_CODES
                    and self.chain_degraded()
                ):
                    # (H8) the chain went stale under this round: wait, never FAILED, and stop the round (every
                    # other pending task would meet the same stale chain)
                    return None
                self._keep(submission_id, unavailable)
                self._fail(submission_id, _code(code))
                return submission_id, "FAILED"
            except Exception as failure:  # noqa: BLE001 - typed, no private content
                failure_code = getattr(failure, "code", None)
                if (
                    # a code may be any type (a WorkerFailure carries an unhashable one): only a str is a chain code
                    isinstance(failure_code, str)
                    and failure_code in _CHAIN_CODES
                    and self.chain_degraded()
                ):
                    # the provider could not read the owner's registration because the chain went stale under this
                    # round: not yet, never FAILED (H8; the cause the A2 one-shot requeue had to repair by hand). The
                    # round stops here. Narrow race left (a refresh landing between the provider's read and this check):
                    # it gives today's behaviour, a FAILED_INFRA give-back = a free rerun.
                    return None
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

    def _log_copy_waits(self):
        """At most one ``recipe_copy_waits_hourly`` line per hour: how many grade rounds left a copy waiting for its
        unsettled first (Validator-2B 7 Nov; a WAIT is never silent). Counts only, never an id.
        """
        from carbon.battery.intake import log

        now = getattr(self, "clock", time.monotonic)()
        since = getattr(self, "_copy_waits_since", None)
        if since is None:
            self._copy_waits_since, self._copy_waits_logged = now, 0
            return
        if now - since >= 3600:
            log(
                "recipe_copy_waits_hourly",
                waits=self.recipe_copy_waits - self._copy_waits_logged,
                period_s=round(now - since),
            )
            self._copy_waits_since, self._copy_waits_logged = (
                now,
                self.recipe_copy_waits,
            )

    def _exam_key(self):
        snapshot = getattr(
            getattr(self.intake.adapter, "discovery", None),
            "evaluation_pack_snapshot",
            None,
        )
        return getattr(snapshot, "manifest_digest", None)

    def _copy_decision(self, submission_id):
        """OWNER-PROBING-COUNTERS-01 (b) (`recipe_copies.decide`): ``(grade | wait | copy, first)``, or None where the
        rule does not apply (no pool, or no pack: nothing is graded on a key)."""
        from . import recipe_copies

        ledger = getattr(getattr(self.intake, "adapter", None), "ledger", None)
        if getattr(self, "pool_store", None) is None or not hasattr(ledger, "_db"):
            return None
        exam_key = self._exam_key()
        if exam_key is None:
            return None
        return recipe_copies.decide(
            adapter=self.intake.adapter,
            ledger=self.intake.adapter.ledger,
            marker=self.marker,
            submission_id=submission_id,
            challenge_id=self.intake.challenge.challenge_id,
            challenge_version=self.intake.challenge.version,
            exam_key=exam_key,
        )

    def _grade_copy(self, submission_id, first):
        """A copy of ``first``, already graded on this key: no exam read; its own slot is counted against its own
        allowance (a refusal is answered as any grade's refusal), the copy recorded, its marker DUPLICATE.
        """
        from . import exam_cap, recipe_copies

        adapter = self.intake.adapter
        challenge = self.intake.challenge
        exam_key = self._exam_key()
        cap = exam_cap.ExamCap(
            adapter.ledger, cadence=getattr(adapter, "exam_cadence", None)
        )
        try:
            reservation = cap.reserve(
                hotkey=adapter.owner(submission_id),
                challenge_id=challenge.challenge_id,
                challenge_version=challenge.version,
                exam_key=exam_key,
                submission_id=submission_id,
                block=exam_cap.submission_block(
                    adapter.ledger, adapter.contract_digest, submission_id
                ),
            )
        except exam_cap.ExamCapRefused as refused:
            self._write(submission_id, "GRADED", code=refused.code)
            return submission_id, "GRADED"
        cap.settle(reservation, recipe_copies.DUPLICATE)
        recipe_copies.record_copy(
            adapter.ledger,
            submission_id=submission_id,
            first_id=first,
            challenge_id=challenge.challenge_id,
            challenge_version=challenge.version,
            exam_key=exam_key,
            recipe_digest_value=recipe_copies.stored_digest(
                adapter.ledger, submission_id
            ),
        )
        self._write(submission_id, "DUPLICATE", code=recipe_copies.DUPLICATE)
        return submission_id, "DUPLICATE"

    def _king_upkeep(self):
        """Keep the king comparable on this door's current exam before anything is decided (`king_upkeep`): his
        uncounted regrade when challengers wait for it, or one crown re-measure rebuild. Never raises.
        """
        from . import crown_average, king_upkeep

        pool = None
        try:
            pool = self._pool()
        except Exception:  # noqa: BLE001 - an unopenable store is the sweep's to report
            return None
        if pool is not None and self._stranded_due():
            # Once per start, before the first grade: queue every challenger graded while the king could not be met
            # (`recontend`), so it is contended ahead of anything graded after. Marked done only once the check was
            # MADE (a refusal or a missing exam is tried again a minute later, never left silent until a restart).
            state, _filed = king_upkeep.file_stranded(
                self.root, self.pool_store, self.intake.adapter.discovery
            )
            if state == king_upkeep.STRANDED_DONE:
                self._stranded_filed = True
            else:
                self._stranded_next = (
                    time.monotonic() + king_upkeep.STRANDED_RETRY_SECONDS
                )
        return king_upkeep.step(
            pool,
            self.intake,
            root=self.root,
            artifacts=self.artifacts,
            entries=self.entries,
            active=crown_average.ACTIVE,
        )

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
        try:
            next_step = self._next_step(submission_id, code, state)
        except Exception:  # noqa: BLE001
            next_step = None
        self._write(
            submission_id,
            "FAILED",
            code=code if state in (None, "RELEASED") else code + ":" + state.lower(),
            next_step=next_step,
        )

    def _next_step(self, submission_id, code, state):
        """R39 (Validator-2B 7 Nov): the FAILED grade's next step. A COUNTED slot whose verdict was never delivered is
        released (`auto_retry.release_undelivered`, every condition) and says so; a given-back grade gets its one free
        automatic retry when its code is transient; a version-wide Carbon gap is given back for a resubmit after the
        fix. None (operator alert) when a charged slot cannot be proven undelivered."""
        from . import auto_retry

        ledger = self.intake.adapter.ledger
        if state == "COUNTED":
            pool = None
            try:
                pool = self._pool()
            except Exception:  # noqa: BLE001
                pool = None
            released = auto_retry.release_undelivered(
                self.root, submission_id, code, ledger=ledger, pool_store=pool
            )
            return "slot_returned" if released else None
        if state not in (None, "RELEASED"):
            return None
        if auto_retry.schedule(self.root, submission_id, code, ledger=ledger):
            return "retry_scheduled"
        return "slot_returned" if auto_retry.retryable(code) else "resubmit_after_fix"

    def _apply_due_retries(self, *, idle):
        """Hand each due automatic retry back to the grader (`auto_retry.apply_due`): on an idle tick (or overdue),
        never while the door drains. True when one was handed back (the round re-lists its tasks once). Never
        raises."""
        from . import auto_retry

        try:
            draining = getattr(self.intake, "draining", None)
            draining = bool(draining()) if callable(draining) else False
            results = auto_retry.apply_due(self.root, draining=draining, idle=idle)
        except Exception:  # noqa: BLE001
            return False
        return any(refused is None for _task, refused in results)

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
        from . import host_quiet

        samples, stop = sampler.samples, sampler.stop_sample
        known = [s for s in samples if s is not None]
        gpu_known = [g for g in sampler.gpu_samples if g is not None]
        # + the GPU condition (Validator-2 5 Nov 21:28): no foreign GPU compute process during the run or at the stop
        uncontended = host_quiet.uncontended(
            lock_held=self.host_lock,
            samples=samples,
            stop=stop,
            gpu_samples=sampler.gpu_samples,
            gpu_stop=sampler.gpu_stop,
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
                            "gpu_unknown_samples": len(sampler.gpu_samples)
                            - len(gpu_known),
                            "max_foreign_gpu": max(gpu_known) if gpu_known else None,
                            "stop_foreign_gpu": sampler.gpu_stop,
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

    def __init__(self, count, seconds, gpu=None):
        import threading

        self.count, self.seconds, self.samples = count, seconds, []
        self.gpu = (lambda: 0) if gpu is None else gpu
        self.gpu_samples, self.gpu_stop = [], None
        self.stop_sample = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.wait(self.seconds):
            self.samples.append(self.count())
            self.gpu_samples.append(self.gpu())

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, kind, value, _trace):
        self._stop.set()
        self._thread.join(self.seconds + 15)
        if kind is not None and _candidate_wall_stop(value):
            self.stop_sample = self.count()
            self.gpu_stop = self.gpu()
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
