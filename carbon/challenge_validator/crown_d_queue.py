"""Crown-time D custody queue: capped, deduplicated reference solves.

Crown-time D solves the design a challenger's model picks, on a custody host,
with the reference solver. Solves are expensive, so they are capped:

- only crown contenders are enqueued (the caller's rule), coarse rung first;
- one request per (submission, target, rung); a request whose dedupe ``key``
  was already solved is answered from the ``solves`` cache at once and costs
  no budget;
- each Challenge has an owner-set weekly solve COUNT (``weekly_solves``, no
  default) per ISO week (UTC).

Fail closed: a request past the budget stays QUEUED in a visible FIFO
(``status`` shows it as deferred with its position); it is never dropped and
never scored as 0. An infrastructure fault re-queues the request in place. A
reference failure (``REFERENCE_*``) is terminal and typed: it is the
reference's failure, never the miner's. A solve that returns anything outside
the closed status vocabulary is treated as an infrastructure fault
(``solve_status_not_closed``) and counted for an alert.

The solver is injected: ``solve(target_id, fixed, design, rung)`` returns
``{"status": "OK", "outputs": {...}}``, ``{"status": "FAILED_INFRA"}`` or
``{"status": "REFERENCE_<CODE>"}`` (the vocabulary of
``carbon.scoring.pool_solver_reference``). It is always called outside any
database transaction.

``status(submission)`` is the miner-visible view: state and queue position
only, never the design, the fixed inputs, the dedupe key or any outputs.
``results(submission)`` is the custody view.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager
from pathlib import Path

OK = "OK"
FAILED_INFRA = "FAILED_INFRA"
_REFERENCE_STATUS = re.compile(r"REFERENCE_[A-Z][A-Z_]{0,63}")

QUEUED = "QUEUED"
SOLVING = "SOLVING"
SOLVED = "SOLVED"
REFERENCE_FAILED = "REFERENCE_FAILED"

#: Code recorded when ``solve`` returns something outside the closed vocabulary.
NOT_CLOSED = "solve_status_not_closed"
#: Code recorded when ``solve`` raises: a host / runner fault, never the miner's.
SOLVE_RAISED = "solve_raised"

DDL = """
CREATE TABLE IF NOT EXISTS requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  challenge TEXT NOT NULL, version TEXT NOT NULL, submission TEXT NOT NULL,
  target TEXT NOT NULL, rung TEXT NOT NULL, key TEXT NOT NULL,
  body TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('QUEUED','SOLVING','SOLVED','REFERENCE_FAILED')),
  attempts INT NOT NULL DEFAULT 0, code TEXT, outputs TEXT,
  queued_at REAL NOT NULL, finished_at REAL);
CREATE UNIQUE INDEX IF NOT EXISTS requests_triple ON requests(submission, target, rung);
CREATE TABLE IF NOT EXISTS solves(key TEXT PRIMARY KEY, outputs TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS budget(
  challenge TEXT NOT NULL, week TEXT NOT NULL, used INT NOT NULL DEFAULT 0,
  cap INT,
  PRIMARY KEY(challenge, week));
"""


class CrownDQueueRefused(ValueError):
    """A typed refusal; ``code`` names it."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def iso_week(seconds):
    """The ISO week (UTC) of a POSIX time, as ``YYYY-Www``."""
    year, week, _ = datetime.datetime.fromtimestamp(seconds, datetime.UTC).isocalendar()
    return f"{year}-W{week:02d}"


def _text(name, value):
    if not isinstance(value, str) or not value:
        raise CrownDQueueRefused("crown_d_field_invalid", name)
    return value


def _body(fixed, design):
    if not isinstance(fixed, dict):
        raise CrownDQueueRefused("crown_d_field_invalid", "fixed")
    if not isinstance(design, (list, tuple)) or not all(
        isinstance(x, (int, float))
        and not isinstance(x, bool)
        and math.isfinite(float(x))
        for x in design
    ):
        raise CrownDQueueRefused("crown_d_field_invalid", "design")
    try:
        return canonical({"fixed": fixed, "design": [float(x) for x in design]})
    except (TypeError, ValueError) as error:
        raise CrownDQueueRefused("crown_d_field_invalid", "fixed") from error


def _closed(result):
    """(status, outputs) when ``result`` is inside the closed vocabulary, else None."""
    if not isinstance(result, dict):
        return None
    status = result.get("status")
    if status == OK:
        outputs = result.get("outputs")
        if not isinstance(outputs, dict):
            return None
        try:
            canonical(outputs)
        except (TypeError, ValueError):
            return None
        return OK, outputs
    if status == FAILED_INFRA:
        return FAILED_INFRA, None
    if isinstance(status, str) and _REFERENCE_STATUS.fullmatch(status):
        return status, None
    return None


class CrownDQueue:
    """Owner-only custody sqlite: requests, the solve cache and weekly budgets."""

    def __init__(self, path, *, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        #: Solves that returned an unclosed status this process (alert-worthy).
        self.unclosed_statuses = 0
        new = not self.path.exists()
        if self.path.is_symlink():
            raise CrownDQueueRefused("crown_d_state_not_owner_only", "symlink")
        if not new:
            info = os.lstat(self.path)
            # Windows has no POSIX group/world bits (st_mode reads 0o666), so
            # the owner-only check is a POSIX check; the symlink refusal holds.
            if stat.S_ISLNK(info.st_mode) or (os.name != "nt" and info.st_mode & 0o077):
                raise CrownDQueueRefused("crown_d_state_not_owner_only")
        with self.db() as db:
            db.executescript(DDL)
        if new:
            self.path.chmod(0o600)
        # No lost work: a request left SOLVING by a crash goes back to QUEUED
        # in place (same id, so it keeps its FIFO position). Its budget unit
        # is refunded like any infrastructure fault.
        with self.transaction() as db:
            rows = db.execute(
                "SELECT id, challenge FROM requests WHERE state=?", (SOLVING,)
            ).fetchall()
            # The interrupted solve's week is not stored; refunding the current
            # week is the bounded choice (never below zero).
            week = iso_week(self.clock())
            for request_id, challenge in rows:
                db.execute(
                    "UPDATE requests SET state=?, attempts=attempts+1, code=? WHERE id=?",
                    (QUEUED, "solving_interrupted", request_id),
                )
                db.execute(
                    "UPDATE budget SET used=MAX(used-1,0) WHERE challenge=? AND week=?",
                    (challenge, week),
                )

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")

    # --- requests -------------------------------------------------------------

    def enqueue(
        self, *, challenge, version, submission, target, rung, key, fixed, design
    ):
        """File one request; idempotent per (submission, target, rung).

        A cached solve of the same ``key`` answers at once and costs no budget.
        """
        fields = {
            "challenge": challenge,
            "version": version,
            "submission": submission,
            "target": target,
            "rung": rung,
            "key": key,
        }
        for name, value in fields.items():
            _text(name, value)
        body = _body(fixed, design)
        now = self.clock()
        with self.transaction() as db:
            row = db.execute(
                "SELECT id, challenge, version, key, body FROM requests "
                "WHERE submission=? AND target=? AND rung=?",
                (submission, target, rung),
            ).fetchone()
            if row is not None:
                if tuple(row[1:]) != (challenge, version, key, body):
                    raise CrownDQueueRefused(
                        "crown_d_request_changed", f"{submission}/{target}/{rung}"
                    )
                return row[0]
            cached = db.execute(
                "SELECT outputs FROM solves WHERE key=?", (key,)
            ).fetchone()
            state, outputs, finished = (
                (SOLVED, cached[0], now) if cached else (QUEUED, None, None)
            )
            cursor = db.execute(
                "INSERT INTO requests(challenge, version, submission, target, rung, key,"
                " body, state, attempts, code, outputs, queued_at, finished_at)"
                " VALUES(?,?,?,?,?,?,?,?,0,NULL,?,?,?)",
                (
                    challenge,
                    version,
                    submission,
                    target,
                    rung,
                    key,
                    body,
                    state,
                    outputs,
                    now,
                    finished,
                ),
            )
            return cursor.lastrowid

    def run_once(self, solve, *, weekly_solves):
        """Process every QUEUED request once, FIFO by id, within the budgets.

        ``weekly_solves`` is the owner's per-Challenge weekly solve count (an
        int >= 1, no default). Returns ``[{id, state, code}]`` for each request
        that was answered or attempted; deferred requests are not listed.
        """
        if (
            not isinstance(weekly_solves, int)
            or isinstance(weekly_solves, bool)
            or weekly_solves < 1
        ):
            raise CrownDQueueRefused(
                "crown_d_weekly_solves_invalid", repr(weekly_solves)
            )
        week = iso_week(self.clock())
        with self.db() as db:
            queued = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM requests WHERE state=? ORDER BY id", (QUEUED,)
                )
            ]
        processed = []
        for request_id in queued:
            claimed = self._claim(request_id, week, weekly_solves)
            if claimed is None:
                continue
            if claimed[0] == SOLVED:
                processed.append({"id": request_id, "state": SOLVED, "code": None})
                continue
            _, challenge, target, rung, key, body = claimed
            request = json.loads(body)
            try:
                result = solve(target, request["fixed"], request["design"], rung)
            except Exception:  # noqa: BLE001 - a host / runner fault, never the miner's
                outcome = (FAILED_INFRA, None, SOLVE_RAISED)
            else:
                closed = _closed(result)
                if closed is None:
                    self.unclosed_statuses += 1
                    outcome = (FAILED_INFRA, None, NOT_CLOSED)
                else:
                    outcome = (closed[0], closed[1], None)
            processed.append(self._record(request_id, challenge, week, key, *outcome))
        return processed

    def _claim(self, request_id, week, weekly_solves):
        """Answer from the cache, defer (None), or mark SOLVING and spend a unit."""
        now = self.clock()
        with self.transaction() as db:
            row = db.execute(
                "SELECT state, challenge, target, rung, key, body FROM requests WHERE id=?",
                (request_id,),
            ).fetchone()
            if row is None or row[0] != QUEUED:
                return None
            _, challenge, target, rung, key, body = row
            # The cache first: another request may have filled it, and a cached
            # answer costs no budget, so it must never wait behind one.
            cached = db.execute(
                "SELECT outputs FROM solves WHERE key=?", (key,)
            ).fetchone()
            if cached:
                db.execute(
                    "UPDATE requests SET state=?, outputs=?, code=NULL, finished_at=? "
                    "WHERE id=?",
                    (SOLVED, cached[0], now, request_id),
                )
                return (SOLVED,)
            db.execute(
                "INSERT INTO budget(challenge, week, used, cap) VALUES(?,?,0,?) "
                "ON CONFLICT(challenge, week) DO UPDATE SET cap=excluded.cap",
                (challenge, week, weekly_solves),
            )
            used = db.execute(
                "SELECT used FROM budget WHERE challenge=? AND week=?",
                (challenge, week),
            ).fetchone()[0]
            if used >= weekly_solves:
                return None  # deferred: stays QUEUED, keeps its place
            db.execute(
                "UPDATE budget SET used=used+1 WHERE challenge=? AND week=?",
                (challenge, week),
            )
            db.execute("UPDATE requests SET state=? WHERE id=?", (SOLVING, request_id))
            return (SOLVING, challenge, target, rung, key, body)

    def _record(self, request_id, challenge, week, key, status, outputs, code):
        now = self.clock()
        with self.transaction() as db:
            if status == OK:
                text = canonical(outputs)
                db.execute(
                    "INSERT OR IGNORE INTO solves(key, outputs, at) VALUES(?,?,?)",
                    (key, text, now),
                )
                db.execute(
                    "UPDATE requests SET state=?, outputs=?, code=NULL, finished_at=? "
                    "WHERE id=?",
                    (SOLVED, text, now, request_id),
                )
                return {"id": request_id, "state": SOLVED, "code": None}
            if status == FAILED_INFRA:
                # Back to QUEUED under the same id, so it keeps its FIFO place.
                # The budget unit is refunded: an infrastructure fault is not
                # the miner's and must not burn the owner's weekly count.
                db.execute(
                    "UPDATE requests SET state=?, attempts=attempts+1, code=? WHERE id=?",
                    (QUEUED, code or FAILED_INFRA, request_id),
                )
                db.execute(
                    "UPDATE budget SET used=MAX(used-1,0) WHERE challenge=? AND week=?",
                    (challenge, week),
                )
                return {"id": request_id, "state": QUEUED, "code": code or FAILED_INFRA}
            # REFERENCE_*: terminal and typed; the reference's, never the miner's.
            db.execute(
                "UPDATE requests SET state=?, code=?, finished_at=? WHERE id=?",
                (REFERENCE_FAILED, status, now, request_id),
            )
            return {"id": request_id, "state": REFERENCE_FAILED, "code": status}

    # --- views ----------------------------------------------------------------

    def status(self, submission):
        """The miner-visible view: state and FIFO position, nothing else."""
        week = iso_week(self.clock())
        with self.db() as db:
            rows = db.execute(
                "SELECT id, challenge, target, rung, state FROM requests "
                "WHERE submission=? ORDER BY id",
                (submission,),
            ).fetchall()
            view = []
            for request_id, challenge, target, rung, state in rows:
                entry = {
                    "target": target,
                    "rung": rung,
                    "state": state,
                    "position": None,
                    "of": None,
                    "deferred": False,
                }
                if state == QUEUED:
                    ahead, total = db.execute(
                        "SELECT SUM(id<=?), COUNT(*) FROM requests "
                        "WHERE challenge=? AND state=?",
                        (request_id, challenge, QUEUED),
                    ).fetchone()
                    budget = db.execute(
                        "SELECT used, cap FROM budget WHERE challenge=? AND week=?",
                        (challenge, week),
                    ).fetchone()
                    entry["position"], entry["of"] = int(ahead), int(total)
                    entry["deferred"] = bool(
                        budget and budget[1] is not None and budget[0] >= budget[1]
                    )
                view.append(entry)
            return view

    def results(self, submission):
        """The custody view: outputs or the typed code per (target, rung)."""
        with self.db() as db:
            rows = db.execute(
                "SELECT target, rung, state, outputs, code FROM requests "
                "WHERE submission=? ORDER BY id",
                (submission,),
            ).fetchall()
        return {
            (target, rung): {
                "state": state,
                "outputs": json.loads(outputs) if outputs is not None else None,
                "code": code,
            }
            for target, rung, state, outputs, code in rows
        }

    def budget_used(self, challenge, week=None):
        week = iso_week(self.clock()) if week is None else week
        with self.db() as db:
            row = db.execute(
                "SELECT used FROM budget WHERE challenge=? AND week=?",
                (challenge, week),
            ).fetchone()
        return row[0] if row else 0


def body_sha256(fixed, design):
    """``sha256:<hex>`` of a request body (for custody records, never the miner)."""
    return "sha256:" + hashlib.sha256(_body(fixed, design).encode()).hexdigest()
