"""Per-miner graded-submission cap and the epoch limit (OWNER-EXAM-CAP-ROTATION-01).

Counted: graded submissions per (hotkey, Challenge, sealed exam). The sealed exam is keyed
by its identity (the evaluation pack digest, which binds the case bank), so a daily rotation
that changes the bank starts new counts even if the evaluation version is unchanged.

A grading attempt first RESERVES a slot, atomically, so concurrent attempts cannot overshoot;
it then SETTLES: a graded outcome keeps the slot (COUNTED), anything else gives it back
(RELEASED). Build refusals (capability gaps and the candidate's own), infrastructure
failures and an unmeasured or diagnostic result never count. A reservation that is never
settled (a crash) is released as FAILED_INFRA on recovery once its grading deadline has
passed: our crash is not charged to the miner.

Refusals, all before grading, so none consumes exam wear and none writes an attempt row:
``exam_cap_reached`` at the Challenge's cap C, ``epoch_limit_reached`` for a second graded
submission by one hotkey on one Challenge in the same 360-block epoch (the block comes from
the signed receipt, never from the miner), and ``exam_cap_unregistered`` for a Challenge
without a registered cap (no default: fail closed). A REGRADE of the incumbent on a rotated
exam is its own kind: it bypasses both limits and is never counted.

The state lives in the receiver's own attempt ledger file (owner-only SQLite). Nothing here
touches a score, a bank entry or what a miner can see; a refusal is a typed code only.
"""

from __future__ import annotations

import json
import time

EPOCH_BLOCKS = 360
#: Registered policy (Validator): every registered Challenge has C = 20. Battery's earlier cap of
#: 10 stays a recorded policy fallback and is not applied by the check. An unregistered Challenge
#: gets no default and is refused (`exam_cap_unregistered`). F02's id is `f02` (families.json).
DEFAULT_CAP = 20
BATTERY_FALLBACK_CAP = 10
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
    UNIQUE(challenge_id, challenge_version, exam_key, submission_id)
);
CREATE INDEX IF NOT EXISTS exam_graded_miner
    ON exam_graded(hotkey, challenge_id, challenge_version, exam_key);
"""


class ExamCapRefused(ValueError):
    """A typed refusal before grading; ``code`` is the closed reason."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def registered_caps() -> dict:
    from carbon.battery import challenge as battery

    return {
        challenge_id: DEFAULT_CAP
        for challenge_id in (*_LEAN_CHALLENGES, battery.CHALLENGE.challenge_id)
    }


def grading_deadline_seconds(material):
    """How long an unsettled reservation may stand before start-up recovery returns it:
    the Challenge's registered total reconstruction wall limit, or None when the material
    carries no such policy (recovery is then explicit)."""
    try:
        policy = material["construction_limits_document"][
            "reconstruction_resource_policy"
        ]
        value = policy["total_reconstruction_wall_seconds_max"]
    except (KeyError, TypeError):
        return None
    return value if type(value) in (int, float) and value > 0 else None


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


class ExamCap:
    def __init__(self, ledger, *, caps=None, grading_deadline_seconds=None, clock=None):
        """``caps`` replaces the registered policy (operator composition and tests only).

        With ``grading_deadline_seconds`` set, reservations older than that and never
        settled are released as FAILED_INFRA now (recovery after a crash).
        """
        self.ledger = ledger
        self.clock = clock or time.time_ns
        self.caps = dict(registered_caps() if caps is None else caps)
        with ledger._db() as db:
            for statement in _DDL.strip().split(";"):
                if statement.strip():
                    db.execute(statement)
        if grading_deadline_seconds is not None:
            self.recover(grading_deadline_seconds)

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
        cap = self.caps.get(challenge_id)
        if cap is None:
            raise ExamCapRefused("exam_cap_unregistered")
        epoch = epoch_of(block)
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
                held = (
                    "kind='GRADED' AND state IN ('RESERVED','COUNTED') "
                    "AND submission_id<>?"
                )
                used = db.execute(
                    "SELECT COUNT(*) FROM exam_graded WHERE hotkey=? AND challenge_id=? "
                    f"AND challenge_version=? AND exam_key=? AND {held}",
                    (hotkey, challenge_id, challenge_version, exam_key, submission_id),
                ).fetchone()[0]
                in_epoch = db.execute(
                    "SELECT COUNT(*) FROM exam_graded WHERE hotkey=? AND challenge_id=? "
                    f"AND epoch=? AND {held}",
                    (hotkey, challenge_id, epoch, submission_id),
                ).fetchone()[0]
                refusal = (
                    "exam_cap_reached"
                    if used >= cap
                    else "epoch_limit_reached"
                    if in_epoch >= 1
                    else None
                )
            if refusal is None:
                now = int(self.clock())
                if row is not None:
                    db.execute(
                        "UPDATE exam_graded SET state='RESERVED', status=NULL, "
                        "epoch=?, kind=?, reserved_ns=?, settled_ns=NULL WHERE id=?",
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
        raise ExamCapRefused(refusal)

    def settle(self, reservation: int, status: str) -> str:
        """Keep the slot for a graded outcome, give it back otherwise; closed vocabulary."""
        if status in COUNTED:
            state = "COUNTED"
        elif status in RELEASED:
            state = "RELEASED"
        else:
            raise ValueError("exam cap outcome is not classified")
        with self.ledger._db() as db:
            changed = db.execute(
                "UPDATE exam_graded SET state=?, status=?, settled_ns=? "
                "WHERE id=? AND state='RESERVED'",
                (state, status, int(self.clock()), reservation),
            ).rowcount
            if changed != 1:
                row = db.execute(
                    "SELECT state, status FROM exam_graded WHERE id=?", (reservation,)
                ).fetchone()
                if row is None or row != (state, status):
                    raise ValueError("exam cap reservation is not open")
        return state

    def count(self, *, hotkey, challenge_id, challenge_version, exam_key) -> int:
        """Graded submissions holding a slot; regrades are never counted."""
        with self.ledger._db() as db:
            return db.execute(
                "SELECT COUNT(*) FROM exam_graded WHERE hotkey=? AND challenge_id=? "
                "AND challenge_version=? AND exam_key=? AND kind='GRADED' AND "
                "state IN ('RESERVED','COUNTED')",
                (hotkey, challenge_id, challenge_version, exam_key),
            ).fetchone()[0]

    def _refusal(self, db, code, challenge_id):
        db.execute(
            "INSERT INTO operator_refusals(at_ns, action, code, contract_digest) "
            "VALUES(?,?,?,NULL)",
            (int(self.clock()), "grading:" + challenge_id[:40], code),
        )
