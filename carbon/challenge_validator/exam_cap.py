"""Submission cadence and the exam key's age limit (OWNER-CADENCE-AND-ROTATION-02).

**Cadence.** A miner may make ``a = max(1, floor(R / (M * sum_t)))`` graded submissions per
Challenge per rolling day, and at most one per 360-block epoch. ``R`` is the validator's
registered rebuild capacity in CPU-hours a day, ``M`` the number of distinct hotkeys with a
graded submission in the rolling day (over all Challenges, plus the requester), and ``sum_t``
the sum over the registered Challenges of the mean rebuild CPU-hours per graded submission,
measured from the receiver's own receipts (a Challenge with no sample yet uses its
registered placeholder). A day is 20 epochs (7200 blocks); the block always comes from the
signed receipt, never from the miner. The registry (``exam_cadence.json``) holds R and the
placeholders; it is changed only by review, and when it is absent or malformed grading
refuses (``exam_cadence_unregistered``): no default, fail closed.

**No per-version cap.** The earlier per-exam-version C = 20 is gone; cadence already bounds
every miner.

**Exam key age.** An exam key (the evaluation pack digest, which binds the case bank) lives
at most 90 days (648,000 blocks) from the first block it graded under. After that grading
refuses (``exam_key_expired``) until the operator rotates it; the refusal is logged loudly.

**Counting.** A grading attempt first RESERVES a slot, atomically, so concurrent attempts
cannot overshoot; it then SETTLES: a graded outcome keeps the slot (COUNTED), anything else
gives it back (RELEASED). Build refusals (capability gaps and the candidate's own),
infrastructure failures and an unmeasured or diagnostic result never count. A reservation
that is never settled (a crash) is released as FAILED_INFRA on recovery once its grading
deadline has passed: our crash is not charged to the miner. A REGRADE (of the incumbent on a
rotated exam, or the weekly fresh-draw check) is its own kind: it bypasses every limit and is
never counted.

Refusals, all before grading, so none consumes exam wear and none writes an attempt row:
``exam_daily_allowance_reached``, ``epoch_limit_reached``, ``exam_key_expired``,
``exam_cap_unregistered`` (a Challenge not registered) and ``exam_cadence_unregistered``.

**Same recipe, same pack set.** A submission is hotkey + contract + recipe + evaluation
pack (the receiver's task identity), so a resubmit of a graded recipe on the same pack set
is the same submission. The receiver refuses it at its door (``holds_slot``;
``same_recipe_already_submitted``, with the earlier result), before any reservation, so
the epoch's slot stays free for a different recipe. On a rotated pack set it is a new
submission (a re-exam). A grading given back as FAILED_INFRA is never the
miner's result: the same recipe then runs again as a fresh task
(``released_on_infra``).

The state lives in the receiver's own attempt ledger file (owner-only SQLite). Nothing here
touches a score, a bank entry or what a miner can see; a refusal is a typed code only.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

EPOCH_BLOCKS = 360
#: One day, in epochs and in blocks (12 s blocks).
DAY_EPOCHS = 20
DAY_BLOCKS = DAY_EPOCHS * EPOCH_BLOCKS
#: An exam key's maximum age, in blocks (90 days).
MAX_EXAM_AGE_BLOCKS = 90 * DAY_BLOCKS
REGISTRY = Path(__file__).with_name("exam_cadence.json")
REGISTRY_SCHEMA = "carbon.exam.cadence-registry.v1"
_LEAN_CHALLENGES = (
    "electric-motor-magnetics",
    "chip-cold-plate",
    "f08-ribbed-bracket",
    "f02",
)

#: The outcomes that spend a slot: anything that ran the sealed evaluation against the
#: candidate (Validator ruling).
COUNTED = frozenset(
    {
        "SCORED_DEVELOPMENT_CANDIDATE",
        "MANDATORY_GATE_FAILED",
        "CANDIDATE_INVALID",
        "REQUIRED_LEG_MINIMUM_FAILED",
        "DECISION_OUTCOME_INELIGIBLE",
    }
)
#: The outcomes that give the slot back.
RELEASED = frozenset(
    {
        "FAILED_INFRA",
        "INDETERMINATE_EVIDENCE",
        "DIAGNOSTIC_Q",
        "CARBON_CAPABILITY_GAP",
        "CANDIDATE_BUILD_REFUSED",
        "UNAVAILABLE",
    }
)

_DDL = """
CREATE TABLE IF NOT EXISTS exam_graded(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hotkey TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    challenge_version TEXT NOT NULL,
    exam_key TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'GRADED' CHECK(kind IN ('GRADED','REGRADE')),
    epoch INTEGER NOT NULL,
    submission_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('RESERVED','COUNTED','RELEASED')),
    status TEXT,
    reserved_ns INTEGER NOT NULL,
    settled_ns INTEGER,
    cpu_seconds REAL,
    UNIQUE(challenge_id, challenge_version, exam_key, submission_id)
);
CREATE INDEX IF NOT EXISTS exam_graded_miner
    ON exam_graded(hotkey, challenge_id, challenge_version, exam_key);
CREATE INDEX IF NOT EXISTS exam_graded_epoch ON exam_graded(epoch, challenge_id);
CREATE TABLE IF NOT EXISTS exam_keys(
    challenge_id TEXT NOT NULL,
    challenge_version TEXT NOT NULL,
    exam_key TEXT NOT NULL,
    first_block INTEGER NOT NULL,
    PRIMARY KEY(challenge_id, challenge_version, exam_key)
);
"""


class ExamCapRefused(ValueError):
    """A typed refusal before grading; ``code`` is the closed reason."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def registered_challenges() -> tuple:
    from carbon.battery import challenge as battery

    return (*_LEAN_CHALLENGES, battery.CHALLENGE.challenge_id)


def registered_cadence(path=None) -> dict:
    """The registered capacity and placeholders, or ``exam_cadence_unregistered``."""
    try:
        document = json.loads(Path(REGISTRY if path is None else path).read_bytes())
        capacity = document["capacity_cpu_hours_per_day"]
        placeholders = document["rebuild_cpu_hours_placeholder"]
        if (
            type(document) is not dict
            or set(document)
            != {
                "schema",
                "source",
                "capacity_cpu_hours_per_day",
                "rebuild_cpu_hours_placeholder",
            }
            or document["schema"] != REGISTRY_SCHEMA
            or type(document["source"]) is not str
            or not document["source"]
            or type(capacity) not in (int, float)
            or not math.isfinite(capacity)
            or capacity <= 0
            or type(placeholders) is not dict
            or any(
                type(name) is not str
                or type(value) not in (int, float)
                or not math.isfinite(value)
                or value <= 0
                for name, value in placeholders.items()
            )
        ):
            raise ValueError("cadence registry malformed")
    except (OSError, ValueError, KeyError, TypeError):
        raise ExamCapRefused("exam_cadence_unregistered") from None
    return {
        "capacity_cpu_hours_per_day": float(capacity),
        "rebuild_cpu_hours_placeholder": dict(placeholders),
    }


def grading_deadline_seconds(material):
    """How long an unsettled reservation may stand before start-up recovery returns it:
    the Challenge's registered total reconstruction wall limit, or None when the material
    carries no such policy (``require_grading_deadline`` refuses that for a registered
    Challenge).
    """
    try:
        policy = material["construction_limits_document"][
            "reconstruction_resource_policy"
        ]
        value = policy["total_reconstruction_wall_seconds_max"]
    except (KeyError, TypeError):
        return None
    return value if type(value) in (int, float) and value > 0 else None


def require_grading_deadline(material, challenge_id: str) -> float:
    """The recovery deadline for a registered Challenge, or refuse (fail closed).

    Without the policy, recovery would silently never run and a crash's held slots would
    stay charged to the miner for good, so the receiver start-up refuses instead.
    """
    deadline = grading_deadline_seconds(material)
    if deadline is None and challenge_id in registered_challenges():
        raise ExamCapRefused("exam_cap_deadline_unregistered")
    return deadline


def epoch_of(block: int) -> int:
    if type(block) is not int or block < 0:
        raise ExamCapRefused("exam_cap_block_unavailable")
    return block // EPOCH_BLOCKS


def submission_block(ledger, contract_digest: str, submission_id: str):
    """The chain block of the signed receipt the submission arrived under, or None."""
    with ledger._db() as db:
        rows = db.execute(
            "SELECT receipt FROM attempts WHERE kind='OUTCOME' AND contract_digest=? "
            "AND submission_id=? AND receipt IS NOT NULL ORDER BY seq LIMIT 1",
            (contract_digest, submission_id),
        ).fetchall()
    if not rows:
        return None
    try:
        block = json.loads(rows[0][0]).get("block")
    except (TypeError, ValueError, AttributeError):
        return None
    return block if type(block) is int else None


def _prepare(db):
    for statement in _DDL.strip().split(";"):
        if statement.strip():
            db.execute(statement)
    columns = {row[1] for row in db.execute("PRAGMA table_info(exam_graded)")}
    if "cpu_seconds" not in columns:
        db.execute("ALTER TABLE exam_graded ADD COLUMN cpu_seconds REAL")


class ExamCap:
    def __init__(
        self, ledger, *, cadence=None, grading_deadline_seconds=None, clock=None
    ):
        """``cadence`` replaces the registry (operator composition and tests only): the
        dict ``registered_cadence`` returns.

        With ``grading_deadline_seconds`` set, reservations older than that and never
        settled are released as FAILED_INFRA now (recovery after a crash).
        """
        self.ledger = ledger
        self.clock = clock or time.time_ns
        self._cadence = cadence
        with ledger._db() as db:
            _prepare(db)
        if grading_deadline_seconds is not None:
            self.recover(grading_deadline_seconds)

    def cadence(self) -> dict:
        return registered_cadence() if self._cadence is None else self._cadence

    def recover(self, grading_deadline_seconds) -> int:
        """Release every open reservation past its grading deadline as FAILED_INFRA.

        Call it only at start-up, when nothing is grading: it is the recovery after a
        crash. A reservation younger than the deadline is never touched, so a grading
        that is still within its deadline keeps its slot even if this runs.
        """
        if type(grading_deadline_seconds) not in (int, float) or not (
            grading_deadline_seconds > 0
        ):
            raise ValueError("a positive grading deadline is required")
        now = int(self.clock())
        cutoff = now - int(grading_deadline_seconds * 1_000_000_000)
        with self.ledger._db() as db:
            return db.execute(
                "UPDATE exam_graded SET state='RELEASED', status='FAILED_INFRA', "
                "settled_ns=? WHERE state='RESERVED' AND reserved_ns<?",
                (now, cutoff),
            ).rowcount

    @staticmethod
    def _window(epoch):
        return epoch - DAY_EPOCHS, epoch

    def _allowance(self, db, hotkey, epoch, cadence):
        """``a`` and its inputs for one requester at one epoch (read-only)."""
        low, high = self._window(epoch)
        rows = db.execute(
            "SELECT DISTINCT hotkey FROM exam_graded WHERE kind='GRADED' AND "
            "state IN ('RESERVED','COUNTED') AND epoch>? AND epoch<=?",
            (low, high),
        ).fetchall()
        active = {row[0] for row in rows} | {hotkey}
        placeholders = cadence["rebuild_cpu_hours_placeholder"]
        total = 0.0
        for challenge_id in placeholders:
            mean = db.execute(
                "SELECT AVG(cpu_seconds) FROM exam_graded WHERE kind='GRADED' AND "
                "state='COUNTED' AND cpu_seconds IS NOT NULL AND challenge_id=? AND "
                "epoch>? AND epoch<=?",
                (challenge_id, low, high),
            ).fetchone()[0]
            if mean is not None:
                total += mean / 3600.0
            else:
                total += placeholders[challenge_id]
        capacity = cadence["capacity_cpu_hours_per_day"]
        allowed = max(1, math.floor(capacity / (len(active) * total)))
        return {
            "allowance": allowed,
            "active_miners": len(active),
            "sum_rebuild_cpu_hours": total,
            "capacity_cpu_hours_per_day": capacity,
        }

    def allowance(self, *, hotkey: str, block: int) -> dict:
        """The current daily allowance for a hotkey (operator view, no side effects)."""
        cadence = self.cadence()
        with self.ledger._db() as db:
            return self._allowance(db, hotkey, epoch_of(block), cadence)

    def reserve(
        self,
        *,
        hotkey: str,
        challenge_id: str,
        challenge_version: str,
        exam_key: str,
        submission_id: str,
        block,
        regrade: bool = False,
    ) -> int:
        """Take one slot or refuse; a repeat for the same submission reuses its row."""
        values = (hotkey, challenge_id, challenge_version, exam_key, submission_id)
        if not all(type(value) is str and value for value in values):
            raise ExamCapRefused("exam_cap_identity_unavailable")
        cadence = self.cadence()
        # The registry's Challenges are the registered set: anything else fails closed.
        if challenge_id not in cadence["rebuild_cpu_hours_placeholder"]:
            raise ExamCapRefused("exam_cap_unregistered")
        # A regrade is never counted and has no signed receipt block; its epoch is inert.
        epoch = 0 if regrade and block is None else epoch_of(block)
        kind = "REGRADE" if regrade else "GRADED"
        key = (challenge_id, challenge_version, exam_key, submission_id)
        refusal = None
        with self.ledger._db() as db:
            row = db.execute(
                "SELECT id, state FROM exam_graded WHERE challenge_id=? AND "
                "challenge_version=? AND exam_key=? AND submission_id=?",
                key,
            ).fetchone()
            if row is not None and row[1] in ("RESERVED", "COUNTED"):
                return row[0]
            if not regrade:
                db.execute(
                    "INSERT OR IGNORE INTO exam_keys VALUES(?,?,?,?)",
                    (challenge_id, challenge_version, exam_key, block),
                )
                first_block = db.execute(
                    "SELECT first_block FROM exam_keys WHERE challenge_id=? AND "
                    "challenge_version=? AND exam_key=?",
                    (challenge_id, challenge_version, exam_key),
                ).fetchone()[0]
                if block - first_block >= MAX_EXAM_AGE_BLOCKS:
                    refusal = "exam_key_expired"
                else:
                    low, high = self._window(epoch)
                    held = (
                        "kind='GRADED' AND state IN ('RESERVED','COUNTED') "
                        "AND submission_id<>?"
                    )
                    allowed = self._allowance(db, hotkey, epoch, cadence)["allowance"]
                    used = db.execute(
                        "SELECT COUNT(*) FROM exam_graded WHERE hotkey=? AND "
                        f"challenge_id=? AND epoch>? AND epoch<=? AND {held}",
                        (hotkey, challenge_id, low, high, submission_id),
                    ).fetchone()[0]
                    in_epoch = db.execute(
                        "SELECT COUNT(*) FROM exam_graded WHERE hotkey=? AND "
                        f"challenge_id=? AND epoch=? AND {held}",
                        (hotkey, challenge_id, epoch, submission_id),
                    ).fetchone()[0]
                    refusal = (
                        "exam_daily_allowance_reached"
                        if used >= allowed
                        else "epoch_limit_reached" if in_epoch >= 1 else None
                    )
            if refusal is None:
                now = int(self.clock())
                if row is not None:
                    db.execute(
                        "UPDATE exam_graded SET state='RESERVED', status=NULL, "
                        "epoch=?, kind=?, reserved_ns=?, settled_ns=NULL, "
                        "cpu_seconds=NULL WHERE id=?",
                        (epoch, kind, now, row[0]),
                    )
                    return row[0]
                cursor = db.execute(
                    "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, "
                    "exam_key, kind, epoch, submission_id, state, reserved_ns) "
                    "VALUES(?,?,?,?,?,?,?, 'RESERVED', ?)",
                    (*values[:4], kind, epoch, submission_id, now),
                )
                return cursor.lastrowid
        # Refused: no row for the attempt (no wear); only an audit line, in its own transaction.
        with self.ledger._db() as db:
            self._refusal(db, refusal, challenge_id)
        if refusal == "exam_key_expired":
            # Loud on purpose: grading on this exam is stopped until the operator rotates it.
            print(
                json.dumps(
                    {
                        "event": "exam_key_expired",
                        "challenge": challenge_id,
                        "version": challenge_version,
                        "action": "rotate the exam key; grading on it is refused",
                    }
                ),
                file=sys.stderr,
                flush=True,
            )
        raise ExamCapRefused(refusal)

    def settle(self, reservation: int, status: str, *, cpu_seconds=None) -> str:
        """Keep the slot for a graded outcome, give it back otherwise; closed vocabulary.

        ``cpu_seconds`` is the allocated rebuild CPU of this submission (wall x cpu count,
        from the receipts); it feeds the rolling mean that sets the cadence.
        """
        if status in COUNTED:
            state = "COUNTED"
        elif status in RELEASED:
            state = "RELEASED"
        else:
            raise ValueError("exam cap outcome is not classified")
        if cpu_seconds is not None and (
            type(cpu_seconds) not in (int, float)
            or not math.isfinite(cpu_seconds)
            or cpu_seconds < 0
        ):
            raise ValueError("rebuild cpu seconds must be a finite non-negative number")
        with self.ledger._db() as db:
            changed = db.execute(
                "UPDATE exam_graded SET state=?, status=?, settled_ns=?, cpu_seconds=? "
                "WHERE id=? AND state='RESERVED'",
                (state, status, int(self.clock()), cpu_seconds, reservation),
            ).rowcount
            if changed != 1:
                row = db.execute(
                    "SELECT state, status FROM exam_graded WHERE id=?", (reservation,)
                ).fetchone()
                if row is None or row != (state, status):
                    raise ValueError("exam cap reservation is not open")
        return state

    def holds_slot(
        self, *, hotkey, challenge_id, challenge_version, exam_key, submission_id
    ) -> bool:
        """Whether this submission is graded (or grading) on this exam key: a
        GRADED row holding its slot. The receiver refuses its resubmit
        (``same_recipe_already_submitted``) before anything is reserved."""
        with self.ledger._db() as db:
            row = db.execute(
                "SELECT 1 FROM exam_graded WHERE hotkey=? AND challenge_id=? AND "
                "challenge_version=? AND exam_key=? AND submission_id=? AND "
                "kind='GRADED' AND state IN ('RESERVED','COUNTED')",
                (hotkey, challenge_id, challenge_version, exam_key, submission_id),
            ).fetchone()
        return row is not None

    def give_back_on_infra(
        self, *, hotkey, challenge_id, challenge_version, exam_key, submission_id
    ) -> str:
        """Record this submission's grading as given back on our infrastructure
        (invariant 7), so the receiver's door runs the recipe again as a fresh task.

        A COUNTED row is a graded result and is never given back. An open or
        otherwise released row becomes RELEASED/FAILED_INFRA; without a row, one is
        written (epoch 0, inert) so the failure is on the record. Returns the
        resulting state: ``COUNTED`` (kept) or ``RELEASED``."""
        values = (hotkey, challenge_id, challenge_version, exam_key, submission_id)
        if not all(type(value) is str and value for value in values):
            raise ExamCapRefused("exam_cap_identity_unavailable")
        now = int(self.clock())
        with self.ledger._db() as db:
            row = db.execute(
                "SELECT id, state FROM exam_graded WHERE challenge_id=? AND "
                "challenge_version=? AND exam_key=? AND submission_id=?",
                (challenge_id, challenge_version, exam_key, submission_id),
            ).fetchone()
            if row is not None and row[1] == "COUNTED":
                return "COUNTED"
            if row is None:
                db.execute(
                    "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, "
                    "exam_key, kind, epoch, submission_id, state, status, reserved_ns, "
                    "settled_ns) VALUES(?,?,?,?,'GRADED',0,?,'RELEASED','FAILED_INFRA',"
                    "?,?)",
                    (*values[:4], submission_id, now, now),
                )
            else:
                db.execute(
                    "UPDATE exam_graded SET state='RELEASED', status='FAILED_INFRA', "
                    "settled_ns=? WHERE id=?",
                    (now, row[0]),
                )
        return "RELEASED"

    def released_on_infra(
        self, *, hotkey, challenge_id, challenge_version, exam_key, submission_id
    ) -> bool:
        """Whether this submission's grading was given back as FAILED_INFRA (our
        failure or a crash): the receiver then runs the recipe again as a fresh
        task, in the miner's next slot (invariant 7)."""
        with self.ledger._db() as db:
            row = db.execute(
                "SELECT 1 FROM exam_graded WHERE hotkey=? AND challenge_id=? AND "
                "challenge_version=? AND exam_key=? AND submission_id=? AND "
                "kind='GRADED' AND state='RELEASED' AND status='FAILED_INFRA'",
                (hotkey, challenge_id, challenge_version, exam_key, submission_id),
            ).fetchone()
        return row is not None

    def count(
        self, *, hotkey, challenge_id, challenge_version=None, exam_key=None
    ) -> int:
        """Graded submissions holding a slot (optionally for one version or key);
        regrades are never counted."""
        query = (
            "SELECT COUNT(*) FROM exam_graded WHERE hotkey=? AND challenge_id=? "
            "AND kind='GRADED' AND state IN ('RESERVED','COUNTED')"
        )
        args = [hotkey, challenge_id]
        for column, value in (
            ("challenge_version", challenge_version),
            ("exam_key", exam_key),
        ):
            if value is not None:
                query += f" AND {column}=?"
                args.append(value)
        with self.ledger._db() as db:
            return db.execute(query, args).fetchone()[0]

    def _refusal(self, db, code, challenge_id):
        db.execute(
            "INSERT INTO operator_refusals(at_ns, action, code, contract_digest) "
            "VALUES(?,?,?,NULL)",
            (int(self.clock()), "grading:" + challenge_id[:40], code),
        )
