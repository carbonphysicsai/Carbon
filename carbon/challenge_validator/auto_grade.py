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

import contextlib
import json
import math
import os
import re
import threading
import time
import traceback
from pathlib import Path

SCHEMA = "carbon.challenge-validator.auto-grade-marker.v1"
_TASK = re.compile(r"rtsk_[0-9a-f]{64}")
_PENDING = frozenset({"task_not_succeeded"})
#: Retention codes that mean "not gradable now" without having consumed anything.
_NOT_YET = frozenset({"owned_task_unavailable", "verified_attempt_unavailable"})
#: The exam-cap limit refusals that a passed-over earlier group-mate (or an unknown group in flight) makes "not yet"
#: instead of final (V2, 18 Nov 2026; `AutoGrader._cap_soft`).
_CAP_LIMITS = frozenset({"exam_daily_allowance_reached", "epoch_limit_reached"})
#: A provider that could not read the owner's registration from a fresh snapshot. While the door's chain is degraded
#: this is a chain read that failed: the task waits and is graded once the chain answers, never FAILED and never a
#: slot given back (H8; R38, 5 Nov). With a fresh snapshot it means what it always meant (handled as before).
_CHAIN_CODES = frozenset({"direct_provider_registration_unavailable"})
#: The terminal marker of a submission its owner withdrew while it was still queued (`LeanRecipeAdapter.withdraw`, owner GO
#: 15 Nov 2026): never graded, no try and no allowance used. Not FAILED (the infrastructure requeue, `failures` and
#: `failure_summary` read FAILED) and not VERSION_CLOSED; every marker reader treats any state it does not name as settled.
WITHDRAWN_STATE = "WITHDRAWN_BY_MINER"
WITHDRAWN_CODE = "withdrawn_by_miner"


#: Slow-tail F2: the longest the king's upkeep step is deferred in a row while other doors wait (engineering pacing,
#: not a scientific value; Validator-2B / owner may set it): after this the upkeep runs even with a door waiting.
UPKEEP_DEFER_MAX_SECONDS = 30 * 60
#: OPERATIONAL (V2's ruling, 18 Nov 2026): the longest the start-up filing of stranded challengers holds the door's
#: grades back (`AutoGrader._stranded_holds_grades`; the shorter of this and `UPKEEP_DEFER_MAX_SECONDS`), so a filing
#: that keeps being skipped or refused can never stop grading the way the every-owner wait did.
STRANDED_GRADE_HOLD_SECONDS = 60  # case-procs + V2 (18 Nov 2026): was 600; the builds now wait for the filing first
#: OPERATIONAL (V2's ruling, 18 Nov 2026): the longest the incumbent's steps wait, INSIDE the sequencer's exclusive,
#: for owners other rounds hold (the overdue path, or unreadable owners), polling each second; then they let go and
#: are deferred again (`prelude_owners_busy`), so no running build can stop grading past it.
PRELUDE_OWNER_WAIT_SECONDS = 10 * 60
#: How often the overdue upkeep alert (``prelude_owners_overdue``, `_prelude_owners_held`) is written again.
PRELUDE_ALERT_SECONDS = 10 * 60
#: How long the incumbent's steps wait for the grades in flight to end (`Sequencer.exclusive_within`) before leaving and
#: asking again (Lead, 18 Nov 2026: never an unbounded drain holding the claim lock).
PRELUDE_DRAIN_SECONDS = 60


class _NextTask(Exception):
    """A parallel claim's task was not gradable now: the round claims again with a fresh ticket."""


#: `AutoGrader._grade_one`: not gradable now, try the next pending task.
_NEXT = object()
#: The set of stalled tasks is replaced whole by a door's grade threads; one at a time.
_STALLED_LOCK = threading.Lock()


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
        #: when this grader process started: an evaluation directory older than this is an interrupted attempt's
        #: (`infra_requeue.set_aside_interrupted`)
        self.process_started = time.time()
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

    def _write(
        self,
        submission_id,
        state,
        *,
        code=None,
        entry_id=None,
        next_step=None,
        pass_name=None,
    ):
        body = {
            "schema": SCHEMA,
            "submission_id": submission_id,
            "state": state,
            "code": code,
            "entry_id": entry_id,
            # a FAILED grade's next step (`auto_retry.NEXT_STEPS`, R39); absent on every other marker
            **({} if next_step is None else {"next_step": next_step}),
            # which pass a CANDIDATE_FAILED wall stop ended (exam_feedback v8); absent on every other marker
            **({} if pass_name is None else {"pass": pass_name}),
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

    def withdrawn(self, submission_id):
        """Write ``submission_id``'s terminal WITHDRAWN_BY_MINER marker (create-only, like every marker). Idempotent: an
        existing WITHDRAWN_BY_MINER marker is kept; a marker of any other state is never replaced (raises).
        """
        if type(submission_id) is not str or not _TASK.fullmatch(submission_id):
            raise ValueError("not a task id")
        try:
            self._write(submission_id, WITHDRAWN_STATE, code=WITHDRAWN_CODE)
        except FileExistsError:
            found = self.marker(submission_id)
            if found is None or found.get("state") != WITHDRAWN_STATE:
                raise

    def _settle_withdrawn(self, submission_id):
        """The repair of a withdrawal whose door call stopped after the provider cancel (`DirectRecipeIntake._withdraw`): a
        pending task its owner withdrew (`LeanRecipeAdapter.withdrawn_by_miner`, the provider's durable cancellation id) gets
        its withdrawal row and WITHDRAWN_BY_MINER marker now, so it never stays pending (or holds a later copy WAITING) for
        good, and is never graded. True when it was settled so; any doubt is False (the round goes on as before and asks
        again next round)."""
        adapter = getattr(self.intake, "adapter", None)
        find = getattr(adapter, "withdrawn_by_miner", None)
        if find is None:
            return False
        try:
            hotkey = find(submission_id)
            if hotkey is None:
                return False
            record = getattr(adapter.ledger, "record_miner_withdrawal", None)
            if record is not None:
                record(adapter.contract_digest, submission_id, hotkey)
            self.withdrawn(submission_id)
        except Exception as failure:  # noqa: BLE001 - asked again next round
            from carbon.battery.intake import log

            log("withdraw_repair_failed", type=type(failure).__name__)
            return False
        from carbon.battery.intake import log

        log("withdraw_marker_repaired")
        return True

    def pending(self):
        """Task ids with no marker yet, in the ledger's order: oldest submission first (`AttemptLedger.submitted_outcomes`)."""
        adapter = self.intake.adapter
        return [
            s
            for s in adapter.ledger.submitted_outcomes(adapter.contract_digest)
            if _TASK.fullmatch(s) and not self._marker(s).exists()
        ]

    def oldest_pending_ns(self):
        """When this door's OLDEST ungraded submission was accepted (ns), or None with none: this door's place in the
        host's one waiting list for the grading lock (slow-tail F1a, `direct_intake._WorkLock`), for its rebuild and
        its grade rounds alike, so the door holding the oldest submission on the host goes next.
        """
        adapter = getattr(self.intake, "adapter", None)
        ledger = getattr(adapter, "ledger", None)
        if not hasattr(ledger, "first_outcome_ns"):
            return None
        for submission_id in self.pending():
            since = ledger.first_outcome_ns(adapter.contract_digest, submission_id)
            if since is not None:
                return since
        return None

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

    def _stranded_holds_grades(self):
        """Whether this round claims no grade because the start-up filing of stranded challengers is not made yet
        (ruling C's order: none graded ahead of it; a door with no pool store files nothing and holds nothing).
        Bounded (V2, 18 Nov 2026): from the first round that found it pending, after the shorter of
        `STRANDED_GRADE_HOLD_SECONDS` and `UPKEEP_DEFER_MAX_SECONDS` grading goes on, with ONE alert line
        ``stranded_filing_overdue``; the filing is still tried every round it is due (`STRANDED_RETRY_SECONDS`).
        """
        # a grader built without a pool store (one-shot tools, test doubles) files nothing and holds nothing
        filed = getattr(self, "_stranded_filed", False)
        if filed or getattr(self, "pool_store", None) is None:
            return False
        now = time.monotonic()
        since = self.__dict__.setdefault("_stranded_hold_since", now)
        if now - since < min(STRANDED_GRADE_HOLD_SECONDS, UPKEEP_DEFER_MAX_SECONDS):
            return True
        if not getattr(self, "_stranded_overdue_logged", False):
            from carbon.battery.intake import log

            log(
                "stranded_filing_overdue",
                code=getattr(self, "_stranded_last", "not_run"),
                seconds=round(now - since),
            )
            self._stranded_overdue_logged = True
        return False

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

    #: The re-ask bound of `_settle_queue_places`: at least this many seconds between two asks, at most this many asks in all
    #: (the first at the first tick, so the last is about two hours later), after which it stops asking until the next start.
    PLACES_RETRY_SECONDS = 600.0
    PLACES_MAX_ASKS = 12

    def _settle_queue_places(self):
        """Until it has looked at every task a receiver stop cancelled, ask the adapter to give each already-queued
        resubmission its original arrival place (`LeanRecipeAdapter.settle_stop_cancelled_places`, the owner's ruling of 14
        Nov 2026): at the first tick after a start, then again only while an owner's registration was still unavailable, no
        more often than every `PLACES_RETRY_SECONDS` and at most `PLACES_MAX_ASKS` times in all (an owner who never becomes
        available must not cost a scan of every marker on every tick). An ordering courtesy: nothing it does fails or delays a
        grade."""
        if getattr(self, "_places_settled", False):
            return
        now = time.monotonic()
        if now < getattr(self, "_places_after", 0.0):
            return
        asks = getattr(self, "_places_asks", 0) + 1
        self._places_asks = asks
        self._places_after = now + self.PLACES_RETRY_SECONDS
        last = asks >= self.PLACES_MAX_ASKS
        if last:
            # the last ask: it does not repeat until the next start
            self._places_settled = True
        adapter = getattr(getattr(self, "intake", None), "adapter", None)
        settle = getattr(adapter, "settle_stop_cancelled_places", None)
        if settle is None:
            self._places_settled = True
            return
        try:
            if settle() == 0:
                self._places_settled = True
            elif last:
                from .koth_journal import note

                # giving up: the marked tasks it never managed to look at, for the operator (a resubmission that arrives
                # later still takes its place at its own `evaluate`)
                note(
                    "queue_place_gave_up",
                    tasks=list(getattr(adapter, "queue_places_unresolved", ())),
                )
        except Exception:  # noqa: BLE001 - asked again later, within the bound
            return

    def _crown_held(self):
        """Whether the incumbent's crown steps (the stranded filing, the king's upkeep, the paused-crown sweep) hold this
        round: an owner they need was set aside at this start (`OwnerProviders.restore`; V2 18 Nov 2026: a crown is
        never decided on an incomplete set). The owners they need are `_prelude_owners`; when those cannot be read,
        ANY set-aside owner holds them (doubt never narrows it). Held steps never dethrone: they wait for a start that
        reopens the owner. Grading goes on."""
        import hashlib

        try:
            set_aside = self.intake.adapter.provider_for.set_aside()
        except Exception:  # noqa: BLE001 - no set-aside view: nothing held
            return False
        if not set_aside:
            return False
        owners = self._prelude_owners()
        held = owners is None or any(
            hashlib.sha256(owner.encode()).hexdigest() in set_aside for owner in owners
        )
        if held and not getattr(self, "_crown_held_logged", False):
            from carbon.battery.intake import log

            log("crown_steps_held", reason="owner_set_aside", owners=len(set_aside))
            self._crown_held_logged = True
        return held

    def _crown_steps(self):
        """The incumbent's crown steps in the round's order, unless held (`_crown_held`)."""
        if self._crown_held():
            return
        self.activity = "king"
        try:
            if self._upkeep_deferred():
                self._file_stranded()
            else:
                self._king_upkeep()
        finally:
            self.activity = None
        self._resume_paused_crowns()

    def _run_once(self):
        sequencer = getattr(self, "sequencer", None)
        if sequencer is not None:
            # a door grading one round per lane (`grade_sequencer`)
            return self._run_once_parallel(sequencer)
        if self.chain_degraded():
            return None  # (H8) a stale chain: grade nothing, mark nothing
        self._settle_queue_places()
        self._crown_steps()
        pending = self.pending()
        if self._apply_due_retries(idle=not pending):
            pending = self.pending()  # a retry handed back is graded in this round
        for submission_id in pending:
            if self._settle_withdrawn(submission_id):
                # withdrawn by its owner, its marker missing: settled first, before any copy rule (an unsettled earlier
                # identical recipe must not hold it pending), and never graded or charged
                continue
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
            outcome = self._grade_one(submission_id)
            if outcome is _NEXT:
                continue
            return outcome
        return None

    #: The least time between two runs of the incumbent's steps in a parallel door when nothing new made them due
    #: (an operational bound, not a scientific value): a check that keeps answering "due" without anything to apply
    #: must not hold every lane back each round.
    PRELUDE_MIN_SECONDS = 60.0
    #: How soon the incumbent's steps are asked again after one of their owners was busy in another round (an
    #: operational poll, not a scientific value).
    PRELUDE_REASK_SECONDS = 10.0

    def _prelude_due(self, pending):
        """Whether the incumbent's own steps (stranded challengers, due retries, the crown sweep, the king's upkeep)
        would DO something now, as the round would run them: in a parallel door they run with no grade in flight
        (`grade_sequencer.Sequencer.exclusive`), so a doubtful "due" waits `PRELUDE_MIN_SECONDS`.
        """
        from . import auto_retry

        now = time.monotonic()
        if now < getattr(self, "_prelude_after", 0.0):
            return False
        try:
            retries = bool(auto_retry.due(self.root, idle=not pending))
        except Exception:  # noqa: BLE001
            retries = False
        # (`_upkeep_deferred` is not asked here: it moves its own clock; the prelude asks it once, as the serial round)
        due = bool(
            (self._stranded_due() and getattr(self, "pool_store", None) is not None)
            or retries
            or self._crowns_due()
            or self._upkeep_due()
        )
        if due:
            self._prelude_after = now + self.PRELUDE_MIN_SECONDS
        return due

    def _prelude_owners(self):
        """The owners whose ledgers the incumbent's steps may run in (V2's ruling B, 17 Nov 2026), read before any is
        taken: the king's (his regrade, his crown re-measure), the crown average's own host owner (its derived
        rebuilds), each paused crown's (its decision) and each due retry's (handed back to the grader). None when any
        cannot be read or resolved: then every owner is taken, as before (doubt never narrows it).
        """
        from . import auto_retry
        from .crown_average import HOST_OWNER

        try:
            adapter = self.intake.adapter
            tasks = set()
            pool = self._pool()
            if pool is not None:
                king = (pool.incumbent() or {}).get("model_id")
                if king is not None:
                    tasks.add(king)
                if hasattr(pool, "paused_crowns"):
                    # the kind the sweep decides (`_resume_paused_crowns`)
                    tasks.update(
                        record["submission_id"] for record in pool.paused_crowns("pack")
                    )
            tasks.update(auto_retry.due(self.root, idle=True))
            owners = {HOST_OWNER}
            for task in tasks:
                owner = self._task_owner(adapter, task)
                if owner is None:
                    return None
                owners.add(owner)
            return owners
        except Exception:  # noqa: BLE001 - doubt takes every owner, as before
            return None

    @staticmethod
    def _task_owner(adapter, task):
        """The owner whose ledger the steps open for ``task``, as the retention paths resolve it
        (`lean_recipe_retention.regrade_retained_entry`, `remeasure_incumbent_pack`): the adapter's own (the current
        contract), else the owner of its admission under this contract, else under an EARLIER contract (a king or a
        paused contender admitted before the pack changed). None: not resolvable."""
        owner = adapter.owner(task)
        if owner is not None:
            return owner
        ledger = adapter.ledger
        owner = ledger.owned_outcome(adapter.contract_digest, task)
        if owner is not None:
            return owner
        admitted = ledger.admitted_owner(task)
        return None if admitted is None else admitted[1]

    @contextlib.contextmanager
    def _prelude_owners_held(self, claims):
        """Hold what the incumbent's steps need; yields whether they may run now. One-lane doors (no claims), or owners
        that cannot be read (`_prelude_owners`): skipped this round, holding nothing. Else ONLY those owners, each taken
        without waiting (`OwnerClaims.try_claim`): while any is in another round (that miner's own build or grade), the
        steps are skipped this round and asked again on the next, the door building and grading meanwhile. Never a wait
        (owner, 18 Nov 2026): after `UPKEEP_DEFER_MAX_SECONDS` of skips in a row the steps are still only retried, and an
        ALERT line ``prelude_owners_overdue`` (``alert=True``) is written once, then every `PRELUDE_ALERT_SECONDS`, for
        the operators' stall watch to page on (V2: the upkeep can starve while the king's owner stays busy).
        """
        if claims is None:
            # a one-lane door: no other round of it holds an owner
            yield True
            return
        # the start-up filing of stranded challengers (`_file_stranded`) writes the pool store only, no owner's ledger:
        # it takes the steps' own owners like every other round (V2, 18 Nov 2026). It still comes before the first
        # grade: until it is made, `_run_once_parallel` claims no grade (`_stranded_holds_grades`)
        owners = self._prelude_owners()
        now = time.monotonic()
        since = getattr(self, "_prelude_waiting_since", None)
        overdue = since is not None and now - since >= UPKEEP_DEFER_MAX_SECONDS
        if overdue and now >= getattr(self, "_prelude_alert_after", 0.0):
            from carbon.battery.intake import log

            # still never a wait (owner, 18 Nov 2026: no step stops another owner's grading): an alert, tried again
            log(
                "prelude_owners_overdue",
                alert=True,
                seconds=round(now - since),
                busy=len(claims.held()),
            )
            self._prelude_alert_after = now + PRELUDE_ALERT_SECONDS
        if owners is None:
            from carbon.battery.intake import log

            # unreadable: the steps are asked again next round, holding nothing meanwhile
            log("prelude_deferred", reason="owners_unreadable")
            self._prelude_after = now + self.PRELUDE_REASK_SECONDS
            yield False
            return
        taken = []
        for owner in sorted(owners):
            if not claims.try_claim(owner):
                break
            taken.append(owner)
        try:
            if len(taken) != len(owners):
                if since is None:
                    from carbon.battery.intake import log

                    self._prelude_waiting_since = now
                    log("prelude_deferred", reason="owner_in_flight")
                # still due: asked again soon (`PRELUDE_REASK_SECONDS`), never on every round
                self._prelude_after = now + self.PRELUDE_REASK_SECONDS
                yield False
                return
            self._prelude_waiting_since = None
            yield True
        finally:
            for owner in taken:
                claims.release(owner)

    def _run_prelude(self):
        """The incumbent's own steps of a parallel round (`_run_once_parallel`), in the serial round's order."""
        from .grade_sequencer import CROWN_LOCK

        self._settle_queue_places()
        # the crown lock without waiting: a crown commit running now, the steps come next round
        if CROWN_LOCK.acquire(blocking=False):
            try:
                self._crown_steps()
            finally:
                CROWN_LOCK.release()
        else:
            self._prelude_after = time.monotonic() + self.PRELUDE_REASK_SECONDS
        self._apply_due_retries(idle=not self.pending())

    def _run_once_parallel(self, sequencer):
        """One grade round of a door that grades one round per lane at once (owner's order 16 Nov; `grade_sequencer`).

        The incumbent's own steps run first, with no grade in flight, and only when due. Then this round claims the
        next pending task no other round holds (the claim lock, pending order), grades it on its lane, and commits in
        claim order: `exam_cap` settle, the crown, the Ladder and the marker wait for every earlier claim to finish.
        Same steps as `_run_once`, in the same order for each task."""
        if self.chain_degraded():
            return None  # (H8) a stale chain: grade nothing, mark nothing
        self._end_hung_grades(sequencer)
        claims = getattr(self, "owner_claims", None)
        # only throttled (asked again shortly): the steps are still due, and their deferral clock keeps running
        throttled = time.monotonic() < getattr(self, "_prelude_after", 0.0)
        if not self._prelude_due(self.pending()):
            if not throttled:
                # really nothing due: a later wait for the steps' owners starts its deferral afresh
                self._prelude_waiting_since = None
        else:
            # the incumbent's steps run in the ledgers of the owners they touch: those owners are in no other round
            # meanwhile (A19; V2 ruling B, 17 Nov: only those, `_prelude_owners_held`). A round that finds the steps
            # already running or waiting in another round goes on instead of waiting behind them on its lane (Option A: a build round that gave its lane back for its remote GPU op needs a lane again before it
            # releases its owner, so two grade rounds waiting here would hold both lanes against it)
            prelude = self.__dict__.setdefault("_prelude_lock", threading.Lock())
            if prelude.acquire(blocking=False):
                try:
                    # V2's ruling B (17 Nov 2026): only the owners whose ledgers the steps touch, never every owner
                    # Owner + V2 (18 Nov 2026): NO door-wide exclusive. The steps take only the owners they touch, each
                    # without waiting (a busy one: skipped, asked again next round), so they never stop another owner's
                    # grade; their king/crown writes take the crown lock (`grade_sequencer.CROWN_LOCK`) without waiting
                    with self._prelude_owners_held(claims) as held:
                        if held:
                            self._run_prelude()
                finally:
                    prelude.release()
        if self._stranded_holds_grades():
            # the start-up filing of stranded challengers is not made yet (skipped, deferred, or another round runs
            # it): no grade starts ahead of it (ruling C); builds go on, and the next round asks again
            return None
        skipped = set()
        while True:
            with sequencer.task() as task:
                taken = []
                try:
                    return self._claim_and_grade(
                        sequencer, task, skipped, claims, taken
                    )
                except _NextTask:
                    continue
                finally:
                    for owner in taken:
                        claims.release(owner)

    def _end_hung_grades(self, sequencer):
        """A grade in flight longer than `GRADE_HUNG_SECONDS` is stuck in Carbon's own code (a model cannot run past its
        worker wall; live 116, 17 Nov 2026: two grades parked 85 min and every later commit waited behind them). It is
        ended as Carbon's: its place in the commit order goes (`Sequencer.abandon`), and its slot is given back as
        FAILED_INFRA, uncharged (`_fail`). Its thread keeps what it holds (its lane, its miner) and never commits.
        Off while the constant is None."""
        limit = GRADE_HUNG_SECONDS
        if limit is None:
            return
        from . import infra_requeue

        for ticket, submission_id in sequencer.overdue(limit):
            # its claim age goes in the log line (V2): the first real use shows whether the limit cut a healthy grade
            age = sequencer.age(ticket)
            sequencer.abandon(ticket)
            # V2 (18 Nov 2026): the hung grade's create-only evaluation files (its pack binding first) are set aside
            # NOW, whatever their age (`started` = infinity: this process wrote them), else `_fail`'s automatic retry, in
            # this same process, meets them and burns its one retry on `evaluation_pack_binding_unavailable`. The kept
            # copy also bumps the retry's regrade generation, so it never meets the hung thread's op identities. The
            # hung thread's open files stay valid across the rename, and it never commits.
            kept, root = None, getattr(self, "root", None)
            try:
                if root is not None:
                    kept = infra_requeue.set_aside_interrupted(
                        root, submission_id, started=math.inf
                    )
            except (OSError, ValueError):
                pass  # left in place: the retry meets its conflict as before (FAILED, Carbon's)
            try:
                from carbon.battery.intake import log

                log(
                    "grade_hung_ended",
                    task=submission_id,
                    seconds=limit,
                    claimed_s=None if age is None else round(age, 1),
                    kept=kept,
                )
            except Exception:  # noqa: BLE001, S110 - a log line never stops this
                pass
            self._fail(submission_id, GRADE_HUNG)

    def _claim_and_grade(self, sequencer, task, skipped, claims, taken):
        """The body of one parallel claim (`_run_once_parallel`): returns the round's outcome, or raises `_NextTask` when
        the claimed task was not gradable now. An owner this round takes (`OwnerClaims`) is put in ``taken``, released
        by the caller when the task ends."""
        busy = sequencer.in_flight()
        # exam-cap allowance: a later task of a group with a grade in flight (or one held back below) waits, so
        # each group's allowance is read in that group's submission order after its earlier settles, as one at
        # a time does (None = a group not known: every later task waits behind it)
        held = sequencer.groups_in_flight()
        # V2 (18 Nov 2026) (3): an in-flight grade whose group cannot be read holds nothing; a cap refusal while one
        # is in flight is "not yet" (`_cap_soft`)
        unknown_in_flight = None in held
        held.discard(None)
        # V2 (2): the groups of tasks passed over this round because their owner is in another round
        passed = set()
        building = self._building_views()
        candidates = [
            sid
            for sid in self.pending()
            if sid not in busy and sid not in skipped and sid not in building
        ]
        for submission_id in candidates:
            group = self._allowance_group(submission_id)
            if group is None:
                if busy or held:
                    # an unknown group waits until it is the only grade in flight; only THIS task waits: holding every
                    # later task behind it, with any owner busy, stops all grading (an unknown group in flight still
                    # holds the later ones, below)
                    continue
            elif group in held:
                held.add(group)
                continue
            if claims is not None:
                # A19: never two rounds of one owner (an advance round may build this owner's next task now)
                owner = self._owner_of(submission_id)
                if owner is None:
                    # an owner that cannot be read now (set aside at this start: `OwnerProviders.restore`) skips only
                    # ITS task; holding its unknown group stopped every later grade (live 116, 18 Nov 2026 21:0xZ)
                    continue
                if not claims.try_claim(owner):
                    # V2 (2): a busy owner holds back only its OWN tasks (each fails this claim); a group-mate that
                    # goes ahead is graded, and a cap refusal it meets is "not yet" (`_cap_soft`), never final
                    passed.add(group)
                    continue
                taken.append(owner)
            if self._withdrawn_pending(submission_id):
                # a withdrawal's row and marker are written in this task's commit turn
                task.bind(submission_id, group)
                task.turn()
                if self._settle_withdrawn(submission_id):
                    return submission_id, "WITHDRAWN_BY_MINER"
                # the repair failed (asked again next round): the task goes on as the serial round does; its
                # claim is spent, so this round grades it or ends (it never scans further without the claim)
                spent = True
            else:
                spent = False
            copy = self._copy_decision(submission_id)
            if copy is not None:
                decision, first = copy
                if decision == "wait":
                    self.recipe_copy_waits = getattr(self, "recipe_copy_waits", 0) + 1
                    self._log_copy_waits()
                    if spent:
                        return None
                    if claims is not None and taken:
                        # its owner is free again for a build round (the round goes on with another task)
                        claims.release(taken.pop())
                    # its group's later tasks keep their order behind it
                    held.add(group)
                    continue
                if decision == "copy":
                    task.bind(submission_id, group)
                    self._mark_cap_soft(
                        submission_id, group in passed or unknown_in_flight
                    )
                    outcome = self._grade_copy(submission_id, first)
                    if outcome is _NEXT:
                        skipped.add(submission_id)
                        raise _NextTask
                    return outcome
            task.bind(submission_id, group)
            self._mark_cap_soft(submission_id, group in passed or unknown_in_flight)
            from .grade_sequencer import GradeAbandoned

            try:
                outcome = self._grade_one(submission_id, turn=task.turn)
            except GradeAbandoned:
                # ended as hung meanwhile (`_end_hung_grades` already gave its slot back): this thread writes nothing
                # more and its round simply ends (its lane and miner go back as any round's do)
                return None
            if outcome is _NEXT:
                # not gradable now: the claim may already be spent, so the next task gets a fresh ticket
                skipped.add(submission_id)
                raise _NextTask
            return outcome
        return None

    def _building_views(self):
        """The task ids the door's already-open providers hold as QUEUED, RUNNING or CANCEL_REQUESTED: nothing to grade
        yet (their grade is `task_not_succeeded`, skipped), so the claim scan skips them before the owner check, while
        it holds the claim. Live 116 stacks (18 Nov 2026, 14:27Z): that scan ran the owner check (the served-source hash)
        for every unbuilt submission while every grade and the incumbent's steps waited on the claim. Read from the
        views alone (no ledger); a task not here is scanned as before."""
        from carbon.research import DirectTaskStateV3

        waiting = (
            DirectTaskStateV3.QUEUED,
            DirectTaskStateV3.RUNNING,
            DirectTaskStateV3.CANCEL_REQUESTED,
        )
        adapter = getattr(getattr(self, "intake", None), "adapter", None)
        opened = getattr(getattr(adapter, "provider_for", None), "_providers", None)
        if type(opened) is not dict:
            return frozenset()
        found = set()
        for provider in tuple(opened.values()):
            views = getattr(provider, "_views", None)
            if type(views) is not dict:
                continue
            for task, view in tuple(views.items()):
                if getattr(view, "state", None) in waiting:
                    found.add(task)
        return frozenset(found)

    def _owner_of(self, submission_id):
        """The owner (hotkey) of ``submission_id``, or None when it cannot be read now."""
        try:
            return self.intake.adapter.owner(submission_id)
        except Exception:  # noqa: BLE001
            return None

    def _mark_cap_soft(self, submission_id, soft):
        with _STALLED_LOCK:
            self.__dict__.setdefault("_cap_soft_ids", {})[submission_id] = bool(soft)

    def _cap_soft(self, submission_id):
        """Whether a cap refusal of ``submission_id``'s grade this round is "not yet" (`_claim_and_grade`)."""
        with _STALLED_LOCK:
            return self.__dict__.get("_cap_soft_ids", {}).pop(submission_id, False)

    def _allowance_group(self, submission_id):
        """The exam-cap allowance group of ``submission_id``'s owner (`exam_cap.group_of`), or None when it cannot be
        read now."""
        from . import exam_cap

        try:
            owner = self.intake.adapter.owner(submission_id)
            return None if owner is None else exam_cap.group_of(owner)
        except Exception:  # noqa: BLE001
            return None

    def _withdrawn_pending(self, submission_id):
        """Whether ``submission_id`` is a withdrawal `_settle_withdrawn` would settle now (read only)."""
        find = getattr(
            getattr(self.intake, "adapter", None), "withdrawn_by_miner", None
        )
        if find is None:
            return False
        try:
            return find(submission_id) is not None
        except Exception:  # noqa: BLE001
            return False

    def _grade_one(self, submission_id, turn=lambda: None):
        """`_grade_on_lane`, with one ``grade_lane`` log line when a grade ran (V2, 17 Nov 2026: a grade is tied to its
        lane from records; a task not gradable now writes none): the task, its start time, and the lane it started on
        and the one it ended on (index, cores, daemon: ``local`` for this host's; they differ when the round gave its
        lane back for its commit turn), never a value."""
        from carbon.reconstruction import grade_lanes

        from . import infra_requeue

        # An attempt stopped mid-grade (a crash, a kill, an unplanned restart) left its create-only evaluation files
        # with no marker: they are set aside (moved, never deleted, logged) before this grade, else its pack binding
        # conflicts and the grade fails on Carbon's side, burning the one automatic retry (switch-2 copy, 17 Nov). The
        # task is this round's own here: claimed by it (in flight in this process, never taken by another round).
        # A grader with no root or no recorded start (a partial test double) sets nothing aside.
        root = getattr(self, "root", None)
        process_started = getattr(self, "process_started", None)
        if root is not None and process_started is not None:
            try:
                infra_requeue.set_aside_interrupted(
                    root, submission_id, started=process_started
                )
            except (OSError, ValueError):
                pass  # left in place: the grade meets its conflict as before (FAILED, Carbon's)
        started, started_ns, outcome = grade_lanes.current(), time.time_ns(), None
        try:
            outcome = self._grade_on_lane(submission_id, turn)
            return outcome
        finally:
            if outcome is not _NEXT:
                _log_grade_lane(submission_id, started_ns, started)

    def _grade_on_lane(self, submission_id, turn):
        """Grade ONE pending task; returns ``(submission_id, state)``, None (stop the round), or `_NEXT` (try the next
        pending task). ``turn`` is called before every order-dependent write after the grade's compute (a door grading
        in parallel commits in claim order, `grade_sequencer`); a door with one lane passes a no-op.
        """
        from carbon.reconstruction import remote_lane

        from .lean_recipe_retention import RetentionUnavailable

        lane = remote_lane.current()
        own = None
        if lane is not None:
            # a REMOTE round: the containers on ITS OWN cores of its box and the box's GPU, sampled there (CV-Motor
            # L12624 (b)); each answered sample is a heartbeat of the link, an unanswered one (None) never quiet ((c)).
            # Owner, 17 Nov 2026: lane core pinning is the timing protection, so a neighbour lane of the same box (on
            # other cores, no box gate any more) is accepted, as on a local lane.
            from carbon.reconstruction import grade_lanes

            from . import host_quiet

            own = grade_lanes.current()
            _containers, gpu = host_quiet.box_counters(lane)
            count = getattr(self, "lane_containers", count_lane_containers)
            cpuset = own.cpuset
            sampler = _Sampler(lambda: count(cpuset, lane), self.sample_seconds, gpu)
        else:
            from carbon.reconstruction import grade_lanes

            own = grade_lanes.current()
            if own is not None:
                # V2's ruling (17 Nov 2026, the registered 2-lane regime): a LOCAL lane's wall stop is judged on ITS OWN
                # cores: the Carbon containers there (a neighbour on other cores is accepted), its lane held for the whole
                # run (`_wall_counted`), the program's full wall (the carrier's setup budget) and no
                # foreign GPU, as before. A sample that cannot be read is never quiet.
                count = getattr(self, "lane_containers", count_lane_containers)
                cpuset = own.cpuset
                sampler = _Sampler(
                    lambda: count(cpuset, None),
                    self.sample_seconds,
                    getattr(self, "gpu", None),
                )
            else:
                sampler = _Sampler(
                    self.containers, self.sample_seconds, getattr(self, "gpu", None)
                )
        sampler.lane = own
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
            if code in _NOT_YET:
                # not gradable now: one waiting submission per coldkey (`coldkey_waiting`) does not let it hold its
                # coldkey's place (a new set, swapped whole, so the intake's thread reads it without a lock)
                with _STALLED_LOCK:
                    self.stalled = getattr(self, "stalled", frozenset()) | {
                        submission_id
                    }
            if code in _PENDING or code in _NOT_YET:
                return _NEXT
            if code in _CAP_LIMITS and self._cap_soft(submission_id):
                # V2 (18 Nov 2026): an earlier group-mate was passed over this round, or a grade of an unknown group is
                # in flight: the slot may be that one's or come back, so this refusal is "not yet" (stays pending)
                from carbon.battery.intake import log

                log("cap_refusal_not_yet", code=code)
                return _NEXT
            if isinstance(code, str) and code in _CHAIN_CODES and self.chain_degraded():
                # (H8) the chain went stale under this round: wait, never FAILED, and stop the round (every
                # other pending task would meet the same stale chain)
                return None
            turn()
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
            turn()
            self._keep(submission_id, failure)
            if _candidate_wall_stop(failure) and self._wall_counted(
                submission_id, sampler, started_ns
            ):
                # The candidate's own graph at the graded-inference wall: its outcome, COUNTED, never given back
                # as infrastructure (Validator 4 Nov 16:52: else a changed recipe probes the hidden inputs free).
                self._write(
                    submission_id,
                    "CANDIDATE_FAILED",
                    code=_WALL_LIMIT_REACHED,
                    pass_name=getattr(failure, "carbon_pass", None),
                )
                return submission_id, "CANDIDATE_FAILED"
            self._fail(
                submission_id,
                (
                    REPLAYED_NOT_RERUN
                    if getattr(failure, "replayed", False) is True
                    else type(failure).__name__
                ),
            )
            return submission_id, "FAILED"
        if (
            type(result) is dict
            and result.get("private_evaluation_state") == "UNAVAILABLE"
            and result.get("private_evaluation_reason") in _CAP_LIMITS
            and self._cap_soft(submission_id)
        ):
            # V2 (18 Nov 2026): the cap refused this grade's slot while an earlier group-mate was passed over this round
            # (its owner busy) or a grade of an unknown group is in flight: "not yet", no marker, it stays pending (the
            # slot may be that one's, or come back), never a spent submission
            from carbon.battery.intake import log

            log("cap_refusal_not_yet", code=result["private_evaluation_reason"])
            return _NEXT
        turn()
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
                pass_name=result.get("private_evaluation_pass"),
            )
            return submission_id, "CANDIDATE_FAILED"
        # A grade that could not be computed keeps ITS reason in the marker (a typed code): an operator's
        # idempotent re-retention reports whatever it meets on the retry, which can hide the first reason.
        reason = (
            result.get("private_evaluation_reason") if type(result) is dict else None
        )
        self._write(
            submission_id,
            "GRADED",
            code=_code(reason) if type(reason) is str and reason else None,
            entry_id=entry if type(entry) is str else None,
        )
        return submission_id, "GRADED"

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
            from . import grade_sequencer

            if refused.code in _CAP_LIMITS and self._cap_soft(submission_id):
                return _NEXT  # V2 (18 Nov 2026): "not yet", stays pending (`_claim_and_grade`)
            grade_sequencer.turn()  # a parallel door: the refusal's marker in claim order (no-op otherwise)
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

    def _upkeep_deferred(self):
        """Slow-tail F2 (Graphite-B 8 Nov): whether this round skips the king's upkeep step (his regrade or one crown
        re-measure rebuild, both rebuild-length holds of the host's one grading slot) because another door is waiting
        for the host lock AND this door has a grade to run: the grade goes first and the upkeep runs in a round where
        no door waits. Never longer than `UPKEEP_DEFER_MAX_SECONDS` in a row, so the king stays comparable. Deferring
        decides nothing: a challenger graded meanwhile waits as PENDING_CONTENTION / KING_UNMEASURED (`king_upkeep`),
        never dropped. Without a waiter reader (``others_waiting``, set by `direct_intake.serve_loopback`) nothing is
        ever deferred. Never raises (doubt runs the upkeep).
        """
        from . import koth_journal

        others = getattr(self, "others_waiting", None)
        try:
            wanted = others is not None and bool(others()) and bool(self.pending())
        except Exception:  # noqa: BLE001
            wanted = False
        since = getattr(self, "_upkeep_deferred_since", None)
        if not wanted:
            self._upkeep_deferred_since = None
            return False
        now = time.monotonic()
        if since is None:
            self._upkeep_deferred_since = since = now
            koth_journal.note("king_upkeep_deferred", reason="door_waiting")
        if now - since >= UPKEEP_DEFER_MAX_SECONDS:
            self._upkeep_deferred_since = None
            koth_journal.note("king_upkeep_deferred_cap", seconds=round(now - since))
            return False
        return True

    def _king_upkeep(self):
        """Keep the king comparable on this door's current exam before anything is decided (`king_upkeep`): his
        uncounted regrade when challengers wait for it, or one crown re-measure rebuild. Never raises.
        """
        from . import crown_average, king_upkeep

        opened, pool = self._file_stranded()
        if not opened:
            return None
        return king_upkeep.step(
            pool,
            self.intake,
            root=self.root,
            artifacts=self.artifacts,
            entries=self.entries,
            active=crown_average.ACTIVE,
        )

    def _file_stranded(self):
        """The start-up filing of stranded challengers (`king_upkeep.file_stranded`), when due; returns ``(opened,
        pool store)`` (``(False, None)`` when the store cannot be opened; ``(True, None)`` when it is not configured).
        Runs even when the upkeep step is deferred (F2)."""
        from . import king_upkeep

        try:
            pool = self._pool()
        except Exception:  # noqa: BLE001 - an unopenable store is the sweep's to report
            return False, None
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
                # its refusal code is in the journal (`recontend_checked`)
                self._stranded_last = "retry"
                self._stranded_next = (
                    time.monotonic() + king_upkeep.STRANDED_RETRY_SECONDS
                )
        return True, pool

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
        if code in auto_retry.OWN_NEXT_STEPS:
            return auto_retry.OWN_NEXT_STEPS[code]
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
        own = getattr(sampler, "lane", None)
        if own is not None:
            from carbon.reconstruction import grade_lanes

            # (b) the lane it started on is the lane it held when the run ended (`_Sampler.lane_at_end`: before any
            # commit-turn give-back): else the run was never on its own cores alone
            if getattr(sampler, "lane_at_end", grade_lanes.current()) != own:
                samples, stop = [*samples, None], None
        known = [s for s in samples if s is not None]
        gpu_known = [g for g in sampler.gpu_samples if g is not None]
        # + the GPU condition (Validator-2 5 Nov 21:28): no foreign GPU compute process during the run or at the stop
        uncontended = host_quiet.uncontended(
            lock_held=self.host_lock,
            samples=samples,
            stop=stop,
            gpu_samples=sampler.gpu_samples,
            gpu_stop=sampler.gpu_stop,
            # a wall stop takes the whole wall: one with no in-run sample is a replay of an earlier operation (an
            # automatic retry re-reading the kept ledger row, no new run), never a quiet host observed
            require_samples=True,
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
                            # which rule read the containers: one lane's own cores (V2, 17 Nov), else the whole host
                            "scope": "host" if own is None else "lane",
                            **(
                                {}
                                if own is None
                                else {"lane": own.index, "cpuset": own.cpuset}
                            ),
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
#: The marker code of a grade that REPLAYED a settled candidate failure instead of running (a re-queued task whose
#: first attempt already settled FAILED_MINER): typed so, given back as infrastructure and never counted.
REPLAYED_NOT_RERUN = "replayed_not_rerun"
#: OPERATIONAL, set by the owner (18 Nov 2026: "approved: GRADE_HUNG_SECONDS = 1800"): after how many seconds in flight
#: a grade is ended as hung (`AutoGrader._end_hung_grades`). 2x the longest COUNTED claim-to-commit on live 116 in the
#: 24 h before (902 s; p90 794 s, median 305 s; Live ops). None: off.
GRADE_HUNG_SECONDS = 1800
#: The code of a grade ended as hung: Carbon's, FAILED_INFRA, never the candidate's.
GRADE_HUNG = "grade_hung_carbon"
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


def count_lane_containers(cpuset, lane=None):
    """`host_quiet.count_lane_containers` (kept here: the grader's default lane counter)."""
    from . import host_quiet

    return host_quiet.count_lane_containers(cpuset, lane)


def _log_grade_lane(submission_id, started_ns, started):
    """One ``grade_lane`` log line (`AutoGrader._grade_one`); a log line never stops a grade."""
    try:
        from carbon.battery.intake import log
        from carbon.reconstruction import grade_lanes

        ended = grade_lanes.current()
        if started is None and ended is None:
            return

        def named(lane, prefix):
            if lane is None:
                return {prefix + "lane": None}
            return {
                prefix + "lane": lane.index,
                prefix + "cpuset": lane.cpuset,
                prefix + "docker_host": lane.docker_host or "local",
            }

        log(
            "grade_lane",
            task=submission_id,
            started_ns=started_ns,
            **named(started, ""),
            **named(ended, "end_"),
        )
    except Exception:  # noqa: BLE001, S110 - evidence only
        pass


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
        #: The lane bound when the run ended (`_wall_counted` (b)): read at the exit, or just before the grade gives its
        #: lane back for its commit-turn wait (`grade_lanes.given_back`), whichever comes first.
        self.lane_at_end = None
        self._ended = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._hook = None

    def _run(self):
        while not self._stop.wait(self.seconds):
            self.samples.append(self.count())
            self.gpu_samples.append(self.gpu())

    def _end(self, *, sample=True):
        """Stop sampling and read the lane, once (the run on this lane is over), and with ``sample`` the stop sample."""
        from carbon.reconstruction import grade_lanes

        if not self._stop.is_set():
            self._stop.set()
            self._thread.join(self.seconds + 15)
            self.lane_at_end = grade_lanes.current()
        if sample and self._ended is None:
            self._ended = (self.count(), self.gpu())

    def __enter__(self):
        from carbon.reconstruction import grade_lanes

        self._thread.start()
        # (a): a commit-turn wait inside the grade gives the lane back; the stop sample is read on it first
        self._hook = grade_lanes.before_give_back(self._end)
        self._hook.__enter__()
        return self

    def __exit__(self, kind, value, _trace):
        hook, self._hook = self._hook, None
        if hook is not None:
            hook.__exit__(None, None, None)
        wall = kind is not None and _candidate_wall_stop(value)
        # a stop sample only for a wall stop (a not-ready task costs nothing), unless the give-back already read it
        self._end(sample=wall)
        if wall:
            self.stop_sample, self.gpu_stop = self._ended
        return False


def _candidate_wall_stop(error):
    """The carrier's OBSERVED candidate wall stop (the same predicate as
    `lean_recipe_retention._is_candidate_wall_hit`), never a host fault."""
    from carbon.development_session import research_carrier as carrier
    from carbon.reconstruction.worker.model import WorkerCode

    return (
        isinstance(error, carrier.MinerProgramFailure)
        # a REPLAY of a settled failure (the worker did not run) is the record of an earlier observation: never a new
        # candidate wall stop, so never counted here (`research_carrier.MinerProgramFailure.replayed`)
        and getattr(error, "replayed", False) is not True
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
