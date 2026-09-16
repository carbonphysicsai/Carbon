"""Conservative durable accounting; an ambiguous reservation cannot be retried."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class SessionBudget:
    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, kind TEXT NOT NULL, reserved REAL NOT NULL, elapsed REAL, state TEXT NOT NULL)"
            )

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def reserve(
        self,
        identity: str,
        kind: str,
        reservation: float,
        limit: float,
        count_limit: int,
    ):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM operations WHERE id=?", (identity,)
            ).fetchone():
                raise ValueError(
                    "operation already recorded; reconcile before continuing"
                )
            used, count = db.execute(
                "SELECT COALESCE(SUM(COALESCE(elapsed,reserved)),0), COUNT(*) FROM operations WHERE kind=?",
                (kind,),
            ).fetchone()
            if used + reservation > limit or count >= count_limit:
                raise ValueError("session budget exhausted")
            db.execute(
                "INSERT INTO operations VALUES (?,?,?,?,?)",
                (identity, kind, reservation, None, "RESERVED"),
            )

    def finish(self, identity: str, elapsed: float, state: str):
        if elapsed < 0 or state not in ("COMPLETE", "FAILED"):
            raise ValueError("invalid accounting result")
        with self.connect() as db:
            changed = db.execute(
                "UPDATE operations SET elapsed=?,state=? WHERE id=? AND state='RESERVED'",
                (elapsed, state, identity),
            ).rowcount
            if changed != 1:
                raise ValueError("accounting transition conflict")

    def run_worker(self, identity: str, operation):
        # 600 productive + 90 bounded validation + 30 cleanup. Unknown elapsed
        # remains charged at the reservation and requires reconciliation.
        count_limit = 270
        if (self.path.parent / "session-limits.json").exists():
            from carbon.development_comparison.experiment import (
                LIMITS,
                WORKER_RESERVATION_BYTES,
                check_storage,
                load_contract,
            )
            from carbon.development_comparison.sources import read_json

            load_contract(self.path.parent)
            if read_json(self.path.parent / "session-limits.json") != LIMITS:
                raise ValueError("comparison limits changed")
            check_storage(self.path.parent, WORKER_RESERVATION_BYTES)
            dispatch = read_json(self.path.parent / "model-session-dispatch.json")
            if (
                time.time() - dispatch["created_unix_ns"] / 1_000_000_000 + 720
                > LIMITS["max_session_seconds"]
            ):
                raise ValueError("comparison wall-time ceiling exhausted")
            count_limit = LIMITS["max_worker_operations"]
        self.reserve(identity, "worker", 720.0, 7200.0, count_limit)
        started = time.monotonic()
        try:
            result = operation()
        except BaseException:
            self.finish(identity, time.monotonic() - started, "FAILED")
            raise
        self.finish(identity, time.monotonic() - started, "COMPLETE")
        return result

    def summary(self):
        with self.connect() as db:
            return [
                dict(
                    zip(
                        ("id", "kind", "reserved", "elapsed", "state"), row, strict=True
                    )
                )
                for row in db.execute(
                    "SELECT id,kind,reserved,elapsed,state FROM operations ORDER BY rowid"
                )
            ]
