# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The escalation rule on the owner's Engy ladder (order of 2026-09-26).

The rule, per role (plan §3; OWNER-GRAPHITE-01 item 2):

- a role starts on its starting rung;
- it moves up **exactly one rung**, and only by consuming one **recorded,
  typed research-failure observation** of a kind that role escalates on;
- each observation escalates at most once;
- a rung is never skipped, and nothing moves above the top rung;
- every escalation is recorded with the observation it consumed.

There is no path that escalates on success, on an infrastructure failure, or
on a model's own request: the only input is a typed observation recorded here
by Carbon, with the digest of its evidence. Whether an outcome *is* such a
failure (for example "builds stall against the baseline over a registered
number of attempts") is decided by whoever records it; phase 1 does not
automate that judgement (GRAPHITE-D6).

A running session keeps the model it started with; an escalation applies to
the next session of that role.

The store is a small SQLite file under the provider's private root.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from carbon.development_session.model_provider import ENGY_LADDER

from ..provider import digest_text
from .roles import ROLES, FailureKind, RoleName

LADDER = ENGY_LADDER
TOP = len(LADDER) - 1


class LadderError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _next_rung(current):
    """One rung up. The only place a rung index is advanced."""
    return current + 1


class Ladder:
    def __init__(self, root):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise LadderError("ladder_root_must_be_private_absolute")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = root / "ladder.sqlite3"
        schema = sqlite3.connect(self.path)
        try:
            schema.executescript("""
                CREATE TABLE IF NOT EXISTS failures (id TEXT PRIMARY KEY, role TEXT NOT NULL, kind TEXT NOT NULL, evidence TEXT NOT NULL, ordinal INTEGER NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS escalations (sequence INTEGER PRIMARY KEY, role TEXT NOT NULL, failure TEXT NOT NULL UNIQUE REFERENCES failures(id), from_rung INTEGER NOT NULL, to_rung INTEGER NOT NULL);
            """)
        finally:
            schema.close()
        self.path.chmod(0o600)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, isolation_level=None)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    @staticmethod
    def _role(role):
        if type(role) is not RoleName:
            raise TypeError("exact RoleName required")
        return ROLES[role]

    def _rung(self, db, role):
        row = db.execute(
            "SELECT to_rung FROM escalations WHERE role=? ORDER BY sequence DESC",
            (role.value,),
        ).fetchone()
        return self._role(role).start_rung if row is None else row[0]

    def rung(self, role):
        with self._db() as db:
            return self._rung(db, role)

    def model(self, role):
        """The model the next session of `role` starts on."""
        return LADDER[self.rung(role)]

    def record_failure(self, role, kind, evidence):
        """Record one typed research-failure observation; returns its id."""
        spec = self._role(role)
        if type(kind) is not FailureKind:
            raise LadderError("not_a_typed_research_failure")
        if kind not in spec.escalation_kinds:
            raise LadderError("failure_kind_not_for_this_role")
        digest_text(evidence, "evidence")
        with self._db() as db:
            ordinal = db.execute("SELECT COUNT(*) FROM failures").fetchone()[0]
            failure_id = (
                "failure-"
                + hashlib.sha256(
                    f"{ordinal}|{role.value}|{kind.value}|{evidence}".encode()
                ).hexdigest()[:16]
            )
            db.execute(
                "INSERT INTO failures VALUES(?,?,?,?,?)",
                (failure_id, role.value, kind.value, evidence, ordinal),
            )
        return failure_id

    @staticmethod
    def _consumable(db, role, failure_id):
        """The observation exists, is this role's, and has not escalated."""
        row = db.execute(
            "SELECT role FROM failures WHERE id=?", (failure_id,)
        ).fetchone()
        if row is None:
            raise LadderError("no_recorded_failure")
        if row[0] != role.value:
            raise LadderError("failure_belongs_to_another_role")
        if db.execute(
            "SELECT 1 FROM escalations WHERE failure=?", (failure_id,)
        ).fetchone():
            raise LadderError("failure_already_consumed")

    def escalate(self, role, failure_id):
        """Move `role` up exactly one rung by consuming `failure_id`."""
        self._role(role)
        with self._db() as db:
            self._consumable(db, role, failure_id)
            current = self._rung(db, role)
            if current >= TOP:
                raise LadderError("ladder_top")
            target = _next_rung(current)
            sequence = db.execute("SELECT COUNT(*) FROM escalations").fetchone()[0] + 1
            db.execute(
                "INSERT INTO escalations VALUES(?,?,?,?,?)",
                (sequence, role.value, failure_id, current, target),
            )
        return {
            "sequence": sequence,
            "role": role.value,
            "failure": failure_id,
            "from_model": LADDER[current],
            "to_model": LADDER[target],
        }

    def history(self):
        """Every escalation, in order, with the observation it consumed."""
        with self._db() as db:
            rows = db.execute(
                "SELECT e.sequence, e.role, e.failure, f.kind, f.evidence, "
                "e.from_rung, e.to_rung FROM escalations e "
                "JOIN failures f ON f.id = e.failure ORDER BY e.sequence"
            ).fetchall()
        return [
            {
                "sequence": sequence,
                "role": role,
                "failure": failure,
                "kind": kind,
                "evidence": evidence,
                "from_model": LADDER[low],
                "to_model": LADDER[high],
            }
            for sequence, role, failure, kind, evidence, low, high in rows
        ]
