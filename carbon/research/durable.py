"""Single-supervisor durable B-07 task provider for public DEVELOPMENT research.

Reuse B-07 resolution, transitions, receipts and wire types. Persist the public
task snapshot before dispatch/acknowledgement. Restart never retries a RUNNING
attempt. Private numerical artifacts remain with their original provider; this
adapter does not reconstruct a private ExperimentRecord from public findings.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager

from .canonical import canonical_bytes, load_canonical
from .errors import ResearchServiceErrorCode
from .lifecycle import InMemoryResearchTaskProvider, ResearchTaskProviderError, _Task
from .model import (
    CancelResearchTaskRequest,
    GetResearchResultResult,
    InfrastructureFailureClass,
    ReplyStatus,
    ResearchTaskState,
    ResearchTaskView,
    ServiceReply,
    StartResearchTaskRequest,
    StartResearchTaskResult,
)
from .records import InfrastructureExecutionFailure


class _NoRetry:
    def __init__(self, executor):
        self.executor = executor

    def execute(self, attempt):
        # The real controller owns metering/reconciliation. B-07's fixture retry
        # policy must never silently duplicate an uncertain numerical attempt.
        try:
            outcome = self.executor.execute(attempt)
        except Exception:  # noqa: BLE001
            return InfrastructureExecutionFailure(
                InfrastructureFailureClass.INTERNAL, False
            )
        if type(outcome) is InfrastructureExecutionFailure:
            return InfrastructureExecutionFailure(
                outcome.failure_class, False, outcome.observed_resource_receipt_ref
            )
        return outcome


class DurableResearchTaskProvider(InMemoryResearchTaskProvider):
    def __init__(self, *, root, requester, **kwargs):
        if (
            not root.is_absolute()
            or root.is_symlink()
            or not isinstance(requester, str)
            or not 1 <= len(requester) <= 128
        ):
            raise ValueError(
                "private absolute root and authenticated requester required"
            )
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self._database = root / "research-tasks.sqlite3"
        if self._database.is_symlink():
            raise ValueError("symlink task store rejected")
        # Linux-only production supervisor lock. It is held for this instance's
        # lifetime, so two restarted controllers cannot each dispatch a queue.
        import fcntl

        self._lease = (root / "supervisor.lock").open("a+b")
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lease.close()
            raise ValueError("research supervisor already active") from None
        self._requests = {}
        queue = kwargs["task_queue"]
        provider = self

        class DurableQueue:
            def enqueue(self, task_id):
                provider._save(provider._tasks[task_id])
                queue.enqueue(task_id)

        kwargs["task_queue"] = DurableQueue()
        kwargs["executor"] = _NoRetry(kwargs["executor"])
        try:
            super().__init__(**kwargs)
            binding = json.dumps(
                [
                    requester,
                    self._worker_digest,
                    self._environment_digest,
                    self._limitations,
                    {
                        key: canonical_bytes(value).hex()
                        for key, value in self._findings.items()
                    },
                ],
                sort_keys=True,
                separators=(",", ":"),
            )
            with self._db() as db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS binding (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL, entropy BLOB NOT NULL);
                    CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, request BLOB NOT NULL, view BLOB NOT NULL, cancellation TEXT, poll INTEGER, reply BLOB);
                    CREATE TABLE IF NOT EXISTS task_observations (id TEXT PRIMARY KEY REFERENCES tasks(id), initial_reply BLOB NOT NULL, queries INTEGER NOT NULL CHECK(queries BETWEEN 0 AND 10000));
                """)
                row = db.execute(
                    "SELECT identity,entropy FROM binding WHERE id=1"
                ).fetchone()
                if row is None:
                    row = (binding, os.urandom(32))
                    db.execute("INSERT INTO binding VALUES(1,?,?)", row)
                if row[0] != binding:
                    raise ValueError("requester or implementation binding changed")
                self._service_instance_id = row[1]
                self._requester_binding = hashlib.sha256(requester.encode()).digest()
                retained = db.execute(
                    "SELECT id,request,view,cancellation,poll,reply FROM tasks ORDER BY id"
                ).fetchall()
            self._database.chmod(0o600)
            for (
                identity,
                request_bytes,
                view_bytes,
                cancellation,
                poll,
                reply,
            ) in retained:
                request = load_canonical(request_bytes, StartResearchTaskRequest)
                view = load_canonical(view_bytes, ResearchTaskView)
                info, _manifest, _kind, resolved, parents, prior, bindings = (
                    self._resolve_start(request)
                )
                if (
                    self._task_id(request) != view.task_id
                    or identity != view.task_id.value
                    or bindings != view.immutable_bindings
                    or request.challenge_key != view.challenge_key
                ):
                    raise ValueError("retained task binding conflict")
                receipt = view.terminal_receipt
                if receipt is not None and (
                    receipt.task_id != view.task_id
                    or receipt.immutable_bindings != bindings
                    or receipt.terminal_state != view.state
                ):
                    raise ValueError("retained receipt association conflict")
                task = _Task(
                    view.task_id,
                    view.challenge_key,
                    self._start_digest(request),
                    bindings,
                    info,
                    resolved,
                    parents,
                    prior,
                    view.state,
                    view.revision,
                    view.created_at_micros,
                    view.updated_at_micros,
                    cancellation_id=cancellation,
                    receipt=receipt,
                    last_poll_sequence=poll,
                    last_poll_result=(
                        load_canonical(reply, GetResearchResultResult)
                        if reply
                        else None
                    ),
                )
                self._tasks[view.task_id] = task
                self._requests[view.task_id] = request_bytes
                self._idempotency[(request.challenge_key, request.idempotency_key)] = (
                    view.task_id
                )
        except BaseException:
            self.close()
            raise

    @contextmanager
    def _db(self):
        if self._lease.closed:
            raise ValueError("research supervisor closed")
        db = sqlite3.connect(self._database, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _save(self, task):
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO tasks VALUES(?,?,?,?,?,?)",
                (
                    task.task_id.value,
                    self._requests[task.task_id],
                    canonical_bytes(self._view(task)),
                    task.cancellation_id,
                    task.last_poll_sequence,
                    (
                        canonical_bytes(task.last_poll_result)
                        if task.last_poll_result
                        else None
                    ),
                ),
            )

    def _transition(self, task, state, *, receipt=None):
        super()._transition(task, state, receipt=receipt)
        self._save(task)

    def start_research_task(self, request):
        # Take the core lock before installing the request bytes. Failed
        # validation does not create a durable task or consume its identity.
        with self._lock:
            if type(request) is not StartResearchTaskRequest:
                return super().start_research_task(request)
            task_id = self._task_id(request)
            if task_id not in self._tasks:
                if len(self._tasks) >= 256:
                    raise ValueError("bounded research task retention exhausted")
                self._requests[task_id] = canonical_bytes(request)
            return super().start_research_task(request)

    def get_research_result(self, request):
        with self._lock:
            result = super().get_research_result(request)
            self._save(self._tasks[result.task.task_id])
            return result

    def run_queued_task(self, task_id):
        if self._lease.closed:
            raise ValueError("research supervisor closed")
        return super().run_queued_task(task_id)

    def bind_task_observation(self, reply):
        """Retain the public start envelope alongside the existing durable task."""
        if (
            type(reply) is not ServiceReply
            or type(reply.result) is not StartResearchTaskResult
        ):
            raise ValueError("public start reply required")
        task_id = reply.result.task.task_id
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.bindings != reply.result.task.immutable_bindings:
                raise ValueError("owned task binding required")
            with self._db() as db:
                db.execute(
                    "INSERT OR IGNORE INTO task_observations VALUES(?,?,0)",
                    (task_id.value, canonical_bytes(reply)),
                )

    def task_observation(self, task_id, challenge, *, count=True):
        """Current owned public view; never advances the legacy polling cursor."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.challenge_key != challenge:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.TASK_NOT_FOUND)
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT initial_reply,queries FROM task_observations WHERE id=?",
                    (task_id.value,),
                ).fetchone()
                if row is None:
                    # Pre-extension tasks and a crash between task persistence
                    # and reply binding retain their original operation identity.
                    # This is an observation of existing work, never a claim that
                    # this client created it or a replacement historical receipt.
                    observed = ServiceReply(
                        ReplyStatus.OK, StartResearchTaskResult(False, self._view(task))
                    )
                    row = (canonical_bytes(observed), 0)
                    db.execute(
                        "INSERT INTO task_observations VALUES(?,?,0)",
                        (task_id.value, row[0]),
                    )
                if count:
                    if row[1] >= 10000:
                        raise ResearchTaskProviderError(
                            ResearchServiceErrorCode.BOUND_EXCEEDED
                        )
                    db.execute(
                        "UPDATE task_observations SET queries=queries+1 WHERE id=?",
                        (task_id.value,),
                    )
            request = load_canonical(self._requests[task_id], StartResearchTaskRequest)
            initial = load_canonical(row[0], ServiceReply)
            if (
                type(initial.result) is not StartResearchTaskResult
                or initial.result.task.task_id != task_id
                or initial.result.task.immutable_bindings != task.bindings
            ):
                raise ValueError("retained public task reply conflict")
            return request.idempotency_key, initial, self._view(task)

    def cancel_observed_task(self, task_id, challenge):
        """Reuse an accepted cancellation identity across protocol surfaces."""
        with self._lock:
            self.task_observation(task_id, challenge, count=False)
            task = self._tasks[task_id]
            cancellation = task.cancellation_id or "mcp-cancel-" + task_id.value
            return self.cancel_research_task(
                CancelResearchTaskRequest(challenge, task_id, cancellation)
            )

    def queued_tasks(self):
        """Trusted supervisor resumes only tasks never marked RUNNING."""
        with self._lock:
            return tuple(
                t.task_id
                for t in self._tasks.values()
                if t.state is ResearchTaskState.QUEUED
            )

    def close(self):
        if not self._lease.closed:
            self._lease.close()
