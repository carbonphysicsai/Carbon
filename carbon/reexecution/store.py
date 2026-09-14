"""Durable C-10 association journal over C-01/C-06/C-07 owner records."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from carbon.audit.model import canonical_json, digest_bytes, validate_token

from .model import (
    JournalState,
    LinkedReexecutionRequest,
    ReexecutionCode,
    ReexecutionFailure,
    ReexecutionJournalView,
    ReexecutionLaunchIntent,
    ReexecutionOutcome,
    RequestWriteDisposition,
)

_SCHEMA = "carbon.c10.development-reexecution-journal.v2"
_GENESIS = digest_bytes(b"carbon.c10.development-reexecution-journal.genesis.v2")
_MIGRATION = """
CREATE TABLE IF NOT EXISTS c10_meta_v1 (
    id INTEGER PRIMARY KEY CHECK(id=1),
    schema TEXT NOT NULL,
    migration_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS c10_request_v1 (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    request_digest TEXT NOT NULL UNIQUE,
    request_body TEXT NOT NULL,
    state TEXT NOT NULL,
    outcome_digest TEXT,
    outcome_body TEXT
);
CREATE TABLE IF NOT EXISTS c10_binding_v1 (
    request_id TEXT PRIMARY KEY,
    request_digest TEXT NOT NULL UNIQUE,
    request_body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS c10_event_v1 (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    body TEXT NOT NULL,
    body_digest TEXT NOT NULL,
    previous_entry_digest TEXT NOT NULL,
    entry_digest TEXT NOT NULL UNIQUE
);
"""
_MIGRATION_DIGEST = digest_bytes(_MIGRATION.encode("ascii"))
_STATEMENTS = tuple(part.strip() for part in _MIGRATION.split(";") if part.strip())
_TERMINAL = {JournalState.COMPARED, JournalState.QUARANTINED}


class ReexecutionJournal:
    """Hash-chained intent/outcome store; it owns no execution or receipt bytes."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as database:
            for statement in _STATEMENTS:
                database.execute(statement)
            database.execute(
                "INSERT OR IGNORE INTO c10_meta_v1 VALUES (1,?,?)",
                (_SCHEMA, _MIGRATION_DIGEST),
            )
            if database.execute(
                "SELECT schema,migration_digest FROM c10_meta_v1 WHERE id=1"
            ).fetchone() != (_SCHEMA, _MIGRATION_DIGEST):
                raise ReexecutionFailure(ReexecutionCode.STORE)
            interrupted = database.execute(
                "SELECT request_id FROM c10_request_v1 WHERE state=?",
                (JournalState.RUNNING.value,),
            ).fetchall()
            for (request_id,) in interrupted:
                database.execute(
                    "UPDATE c10_request_v1 SET state=? WHERE request_id=?",
                    (JournalState.RECONCILIATION_REQUIRED.value, request_id),
                )
                self._append_event(
                    database,
                    request_id,
                    "RESTART_RECONCILIATION_REQUIRED",
                    {"prior_state": JournalState.RUNNING.value},
                )
        self.verify_integrity()

    @contextmanager
    def _transaction(self):
        database = None
        try:
            database = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            database.execute("PRAGMA synchronous=FULL")
            database.execute("BEGIN IMMEDIATE")
            yield database
            database.execute("COMMIT")
        except ReexecutionFailure:
            if database is not None and database.in_transaction:
                database.execute("ROLLBACK")
            raise
        except sqlite3.Error:
            if database is not None and database.in_transaction:
                try:
                    database.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise ReexecutionFailure(ReexecutionCode.STORE) from None
        finally:
            if database is not None:
                database.close()

    @staticmethod
    def _head(database: sqlite3.Connection) -> str:
        row = database.execute(
            "SELECT entry_digest FROM c10_event_v1 ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return _GENESIS if row is None else row[0]

    @classmethod
    def _append_event(
        cls,
        database: sqlite3.Connection,
        request_id: str,
        kind: str,
        body: dict[str, object],
    ) -> None:
        request_id = validate_token(request_id)
        kind = validate_token(kind)
        encoded = canonical_json(body).decode("ascii")
        body_digest = digest_bytes(encoded.encode("ascii"))
        previous = cls._head(database)
        entry_digest = digest_bytes(
            canonical_json(
                {
                    "body_digest": body_digest,
                    "kind": kind,
                    "previous_entry_digest": previous,
                    "request_id": request_id,
                }
            )
        )
        database.execute(
            "INSERT INTO c10_event_v1 "
            "(request_id,kind,body,body_digest,previous_entry_digest,entry_digest) "
            "VALUES (?,?,?,?,?,?)",
            (request_id, kind, encoded, body_digest, previous, entry_digest),
        )

    @staticmethod
    def _view(row: tuple[object, ...]) -> ReexecutionJournalView:
        try:
            return ReexecutionJournalView(
                request_id=row[0],
                request_digest=row[1],
                state=JournalState(row[2]),
                outcome_digest=row[3],
            )
        except (TypeError, ValueError, ReexecutionFailure):
            raise ReexecutionFailure(ReexecutionCode.STORE) from None

    def prepare(
        self, intent: ReexecutionLaunchIntent
    ) -> tuple[RequestWriteDisposition, ReexecutionJournalView]:
        if type(intent) is not ReexecutionLaunchIntent:
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        body = intent.canonical_bytes.decode("ascii")
        with self._transaction() as database:
            row = database.execute(
                "SELECT request_id,request_digest,state,outcome_digest,request_body "
                "FROM c10_request_v1 WHERE request_id=?",
                (intent.request_id,),
            ).fetchone()
            if row is not None:
                if row[1] != intent.intent_digest or row[4] != body:
                    raise ReexecutionFailure(ReexecutionCode.CONFLICT)
                return RequestWriteDisposition.ALREADY_PRESENT, self._view(row[:4])
            database.execute(
                "INSERT INTO c10_request_v1 "
                "(request_id,request_digest,request_body,state) VALUES (?,?,?,?)",
                (
                    intent.request_id,
                    intent.intent_digest,
                    body,
                    JournalState.INTENT_RECORDED.value,
                ),
            )
            self._append_event(
                database,
                intent.request_id,
                "INTENT_RECORDED",
                {"intent_digest": intent.intent_digest},
            )
            return RequestWriteDisposition.INSERTED, ReexecutionJournalView(
                intent.request_id,
                intent.intent_digest,
                JournalState.INTENT_RECORDED,
                None,
            )

    def bind(self, request: LinkedReexecutionRequest) -> RequestWriteDisposition:
        if type(request) is not LinkedReexecutionRequest:
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        intent = request.launch_intent
        body = request.canonical_bytes.decode("ascii")
        with self._transaction() as database:
            row = database.execute(
                "SELECT request_digest,request_body,state FROM c10_request_v1 "
                "WHERE request_id=?",
                (request.request_id,),
            ).fetchone()
            if (
                row is None
                or row[0] != intent.intent_digest
                or row[1] != intent.canonical_bytes.decode("ascii")
            ):
                raise ReexecutionFailure(ReexecutionCode.CONFLICT)
            existing = database.execute(
                "SELECT request_digest,request_body FROM c10_binding_v1 "
                "WHERE request_id=?",
                (request.request_id,),
            ).fetchone()
            expected = (request.request_digest, body)
            if existing is not None:
                if existing != expected:
                    raise ReexecutionFailure(ReexecutionCode.CONFLICT)
                return RequestWriteDisposition.ALREADY_PRESENT
            if JournalState(row[2]) not in {
                JournalState.RUNNING,
                JournalState.RECONCILIATION_REQUIRED,
            }:
                raise ReexecutionFailure(ReexecutionCode.STATE)
            database.execute(
                "INSERT INTO c10_binding_v1 VALUES (?,?,?)",
                (request.request_id, request.request_digest, body),
            )
            self._append_event(
                database,
                request.request_id,
                "REQUEST_BOUND",
                {"request_digest": request.request_digest},
            )
            return RequestWriteDisposition.INSERTED

    def mark_running(self, intent: ReexecutionLaunchIntent) -> ReexecutionJournalView:
        if type(intent) is not ReexecutionLaunchIntent:
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        with self._transaction() as database:
            row = database.execute(
                "SELECT request_id,request_digest,state,outcome_digest,request_body "
                "FROM c10_request_v1 WHERE request_id=?",
                (intent.request_id,),
            ).fetchone()
            if (
                row is None
                or row[1] != intent.intent_digest
                or row[4] != intent.canonical_bytes.decode("ascii")
            ):
                raise ReexecutionFailure(ReexecutionCode.CONFLICT)
            state = JournalState(row[2])
            if state is JournalState.RUNNING:
                return self._view(row[:4])
            if state not in {
                JournalState.INTENT_RECORDED,
                JournalState.RECONCILIATION_REQUIRED,
            }:
                raise ReexecutionFailure(ReexecutionCode.STATE)
            database.execute(
                "UPDATE c10_request_v1 SET state=? WHERE request_id=?",
                (JournalState.RUNNING.value, intent.request_id),
            )
            self._append_event(
                database,
                intent.request_id,
                "RUNNING",
                {
                    "claim_id": intent.claim_id,
                    "worker_id": intent.worker_id,
                },
            )
            return ReexecutionJournalView(
                intent.request_id,
                intent.intent_digest,
                JournalState.RUNNING,
                None,
            )

    def mark_reconciliation_required(
        self, intent: ReexecutionLaunchIntent
    ) -> ReexecutionJournalView:
        if type(intent) is not ReexecutionLaunchIntent:
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        with self._transaction() as database:
            row = database.execute(
                "SELECT request_id,request_digest,state,outcome_digest,request_body "
                "FROM c10_request_v1 WHERE request_id=?",
                (intent.request_id,),
            ).fetchone()
            if (
                row is None
                or row[1] != intent.intent_digest
                or row[4] != intent.canonical_bytes.decode("ascii")
            ):
                raise ReexecutionFailure(ReexecutionCode.CONFLICT)
            state = JournalState(row[2])
            if state is JournalState.RECONCILIATION_REQUIRED:
                return self._view(row[:4])
            if state not in {JournalState.INTENT_RECORDED, JournalState.RUNNING}:
                raise ReexecutionFailure(ReexecutionCode.STATE)
            database.execute(
                "UPDATE c10_request_v1 SET state=? WHERE request_id=?",
                (JournalState.RECONCILIATION_REQUIRED.value, intent.request_id),
            )
            self._append_event(
                database,
                intent.request_id,
                "RECONCILIATION_REQUIRED",
                {"prior_state": state.value},
            )
            return ReexecutionJournalView(
                intent.request_id,
                intent.intent_digest,
                JournalState.RECONCILIATION_REQUIRED,
                None,
            )

    def record_outcome(
        self,
        request: LinkedReexecutionRequest,
        outcome: ReexecutionOutcome,
    ) -> ReexecutionJournalView:
        if (
            type(request) is not LinkedReexecutionRequest
            or type(outcome) is not ReexecutionOutcome
            or outcome.request_id != request.request_id
            or outcome.request_digest != request.request_digest
        ):
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        target = (
            JournalState.QUARANTINED
            if outcome.quarantine_required
            else JournalState.COMPARED
        )
        outcome_body = outcome.canonical_bytes.decode("ascii")
        intent = request.launch_intent
        with self._transaction() as database:
            row = database.execute(
                "SELECT request_id,request_digest,state,outcome_digest,outcome_body,"
                "request_body FROM c10_request_v1 WHERE request_id=?",
                (request.request_id,),
            ).fetchone()
            if (
                row is None
                or row[1] != intent.intent_digest
                or row[5] != intent.canonical_bytes.decode("ascii")
            ):
                raise ReexecutionFailure(ReexecutionCode.CONFLICT)
            binding = database.execute(
                "SELECT request_digest,request_body FROM c10_binding_v1 "
                "WHERE request_id=?",
                (request.request_id,),
            ).fetchone()
            if binding != (
                request.request_digest,
                request.canonical_bytes.decode("ascii"),
            ):
                raise ReexecutionFailure(ReexecutionCode.CONFLICT)
            state = JournalState(row[2])
            if state in _TERMINAL:
                if (
                    state is not target
                    or row[3] != outcome.outcome_digest
                    or row[4] != outcome_body
                ):
                    raise ReexecutionFailure(ReexecutionCode.CONFLICT)
                return self._view(row[:4])
            if state not in {
                JournalState.RUNNING,
                JournalState.RECONCILIATION_REQUIRED,
            }:
                raise ReexecutionFailure(ReexecutionCode.STATE)
            database.execute(
                "UPDATE c10_request_v1 SET state=?,outcome_digest=?,outcome_body=? "
                "WHERE request_id=?",
                (
                    target.value,
                    outcome.outcome_digest,
                    outcome_body,
                    request.request_id,
                ),
            )
            self._append_event(
                database,
                request.request_id,
                target.value,
                {
                    "disposition": outcome.disposition.value,
                    "outcome_digest": outcome.outcome_digest,
                },
            )
            return ReexecutionJournalView(
                request.request_id,
                intent.intent_digest,
                target,
                outcome.outcome_digest,
            )

    def status(self, intent: ReexecutionLaunchIntent) -> ReexecutionJournalView:
        if type(intent) is not ReexecutionLaunchIntent:
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        with self._transaction() as database:
            row = database.execute(
                "SELECT request_id,request_digest,state,outcome_digest,request_body "
                "FROM c10_request_v1 WHERE request_id=?",
                (intent.request_id,),
            ).fetchone()
        if (
            row is None
            or row[1] != intent.intent_digest
            or row[4] != intent.canonical_bytes.decode("ascii")
        ):
            raise ReexecutionFailure(ReexecutionCode.CONFLICT)
        return self._view(row[:4])

    def outcome_document(self, request: LinkedReexecutionRequest) -> dict[str, object]:
        status = self.status(request.launch_intent)
        if status.state not in _TERMINAL:
            raise ReexecutionFailure(ReexecutionCode.STATE)
        with self._transaction() as database:
            row = database.execute(
                "SELECT outcome_body,outcome_digest FROM c10_request_v1 "
                "WHERE request_id=?",
                (request.request_id,),
            ).fetchone()
        if (
            row is None
            or type(row[0]) is not str
            or digest_bytes(row[0].encode("ascii")) != row[1]
        ):
            raise ReexecutionFailure(ReexecutionCode.STORE)
        try:
            import json

            value = json.loads(row[0])
            if canonical_json(value).decode("ascii") != row[0]:
                raise ValueError
        except (TypeError, ValueError):
            raise ReexecutionFailure(ReexecutionCode.STORE) from None
        return value

    def verify_integrity(self) -> None:
        with self._transaction() as database:
            previous = _GENESIS
            request_states: dict[str, JournalState] = {}
            bound_requests: set[str] = set()
            for row in database.execute(
                "SELECT request_id,kind,body,body_digest,previous_entry_digest,"
                "entry_digest FROM c10_event_v1 ORDER BY sequence"
            ):
                request_id, kind, body, body_digest, prior, entry_digest = row
                if (
                    digest_bytes(body.encode("ascii")) != body_digest
                    or prior != previous
                    or entry_digest
                    != digest_bytes(
                        canonical_json(
                            {
                                "body_digest": body_digest,
                                "kind": kind,
                                "previous_entry_digest": previous,
                                "request_id": request_id,
                            }
                        )
                    )
                ):
                    raise ReexecutionFailure(ReexecutionCode.STORE)
                if kind == "INTENT_RECORDED":
                    if request_id in request_states:
                        raise ReexecutionFailure(ReexecutionCode.STORE)
                    request_states[request_id] = JournalState.INTENT_RECORDED
                elif kind == "RUNNING":
                    if request_states.get(request_id) not in {
                        JournalState.INTENT_RECORDED,
                        JournalState.RECONCILIATION_REQUIRED,
                    }:
                        raise ReexecutionFailure(ReexecutionCode.STORE)
                    request_states[request_id] = JournalState.RUNNING
                elif kind == "RESTART_RECONCILIATION_REQUIRED":
                    if request_states.get(request_id) is not JournalState.RUNNING:
                        raise ReexecutionFailure(ReexecutionCode.STORE)
                    request_states[request_id] = JournalState.RECONCILIATION_REQUIRED
                elif kind == "RECONCILIATION_REQUIRED":
                    if request_states.get(request_id) not in {
                        JournalState.INTENT_RECORDED,
                        JournalState.RUNNING,
                    }:
                        raise ReexecutionFailure(ReexecutionCode.STORE)
                    request_states[request_id] = JournalState.RECONCILIATION_REQUIRED
                elif kind == "REQUEST_BOUND":
                    if (
                        request_states.get(request_id)
                        not in {
                            JournalState.RUNNING,
                            JournalState.RECONCILIATION_REQUIRED,
                        }
                        or request_id in bound_requests
                    ):
                        raise ReexecutionFailure(ReexecutionCode.STORE)
                    bound_requests.add(request_id)
                elif kind in {state.value for state in _TERMINAL}:
                    if request_states.get(request_id) not in {
                        JournalState.RUNNING,
                        JournalState.RECONCILIATION_REQUIRED,
                    }:
                        raise ReexecutionFailure(ReexecutionCode.STORE)
                    request_states[request_id] = JournalState(kind)
                else:
                    raise ReexecutionFailure(ReexecutionCode.STORE)
                previous = entry_digest
            rows = database.execute(
                "SELECT request_id,request_digest,request_body,state,outcome_digest,"
                "outcome_body FROM c10_request_v1"
            ).fetchall()
            if {row[0] for row in rows} != set(request_states):
                raise ReexecutionFailure(ReexecutionCode.STORE)
            for row in rows:
                state = JournalState(row[3])
                if (
                    digest_bytes(row[2].encode("ascii")) != row[1]
                    or state is not request_states[row[0]]
                    or (row[4] is None) != (row[5] is None)
                    or (state in _TERMINAL) != (row[4] is not None)
                    or (
                        row[5] is not None
                        and digest_bytes(row[5].encode("ascii")) != row[4]
                    )
                ):
                    raise ReexecutionFailure(ReexecutionCode.STORE)
            bindings = database.execute(
                "SELECT request_id,request_digest,request_body FROM c10_binding_v1"
            ).fetchall()
            if {row[0] for row in bindings} != bound_requests:
                raise ReexecutionFailure(ReexecutionCode.STORE)
            if any(digest_bytes(row[2].encode("ascii")) != row[1] for row in bindings):
                raise ReexecutionFailure(ReexecutionCode.STORE)


__all__ = ["ReexecutionJournal"]
