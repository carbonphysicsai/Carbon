"""The set-level grade of a Challenge version (OWNER-FULL-EXAM-BANK-01, item 3).

A version's exam is the union of its active sealed batches (`sealed_exam_common`
pack set). Each batch is graded by the unchanged per-pack path; this step reads
those per-batch results, calls `sealed_exam_common.aggregate`, and writes the one
result the rest of the system may read, keyed by the pack-set key. The Validator's
five conditions:

1. **Only the set result counts.** KOTH, the Ladder, the weight source and the
   miner readback read `SetResultStore.result` only. The per-batch rows are
   operator-only (`batch_rows`) and this module never returns one to a miner path.
2. **One graded submission.** `grade_set` reserves the epoch slot once under the
   set key and settles it once, whatever the number of batches.
3. **Completeness.** A batch with no result, an infrastructure or unavailable
   outcome, or a malformed result gives *no set result* (typed, retryable, the
   slot returned), never a partial mean. A gate failure on any batch makes the
   set ineligible.
4. **Rotation.** A new set key is a new evaluation key; `comparable` is the one
   test KOTH uses, so a challenger is only ever compared on the same key (the
   incumbent is regraded on the new key first, by the existing regrade routine).
5. **Tests** in `tests/cpu/test_pack_set_result.py`.

The per-batch grader is injected: the receiver supplies the existing per-pack
scoring (the dual benchmark scored by the ScoreEngine) for each batch, with its
own cap, Ladder and KOTH steps off. DEVELOPMENT only: no qualification, weight,
reward or LIVE authority.
"""

from __future__ import annotations

import json
import math
import time

from . import sealed_exam_common as common

SET_RESULT_SCHEMA = "carbon.sealed-exam.set-result.v1"
SCORED = "SCORED_DEVELOPMENT_CANDIDATE"
GATE_FAILED = "MANDATORY_GATE_FAILED"
UNAVAILABLE = "UNAVAILABLE"

_DDL = """
CREATE TABLE IF NOT EXISTS pack_set_batch(
    set_key TEXT NOT NULL,
    submission_id TEXT NOT NULL,
    batch_digest TEXT NOT NULL,
    status TEXT NOT NULL,
    record TEXT NOT NULL,
    at_ns INTEGER NOT NULL,
    PRIMARY KEY(set_key, submission_id, batch_digest)
);
CREATE TABLE IF NOT EXISTS pack_set_result(
    set_key TEXT NOT NULL,
    submission_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT NOT NULL,
    at_ns INTEGER NOT NULL,
    PRIMARY KEY(set_key, submission_id)
);
"""


class SetResultRefused(ValueError):
    """A typed refusal; the code names the check, never a batch's content."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def comparable(incumbent_key, challenger_key):
    """Whether two results may be compared by KOTH: the same pack-set key,
    exactly. A rotation (a new key) is never comparable until the incumbent is
    regraded on it."""
    return (
        type(incumbent_key) is str
        and type(challenger_key) is str
        and bool(incumbent_key)
        and incumbent_key == challenger_key
    )


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _gate_verdicts(record):
    gates = record.get("gates") if type(record) is dict else None
    if type(gates) is not dict or not gates:
        raise SetResultRefused("set_batch_gates")
    try:
        return {
            name: {"PASS": True, "FAIL": False}[verdict]
            for name, verdict in gates.items()
        }
    except (KeyError, TypeError):
        raise SetResultRefused("set_batch_gates") from None


def _batch_measurement(record):
    """The aggregate input of one batch's graded row, or a refusal. A batch that
    did not run the exam to a graded outcome has no measurement."""
    if type(record) is not dict or type(record.get("status")) is not str:
        raise SetResultRefused("set_batch_malformed")
    status = record["status"]
    if status not in (SCORED, GATE_FAILED):
        raise SetResultRefused("set_batch_" + status.lower())
    gates = _gate_verdicts(record)
    if status == GATE_FAILED:
        if all(gates.values()):
            raise SetResultRefused("set_batch_gate_failed_without_gate")
        return {"gates": gates, "A": None, "D": None}
    legs = record.get("legs")
    if type(legs) is not dict or not (
        _number(legs.get("A")) and _number(legs.get("D"))
    ):
        raise SetResultRefused("set_batch_legs")
    if not all(gates.values()):
        raise SetResultRefused("set_batch_gates")
    return {"gates": gates, "A": float(legs["A"]), "D": float(legs["D"])}


class SetResultStore:
    """Operator-only per-batch rows and the set-level result, in the receiver's
    attempt ledger."""

    def __init__(self, ledger, *, clock=None):
        self.ledger = ledger
        self.clock = clock or time.time_ns
        with ledger._db() as db:
            for statement in _DDL.strip().split(";"):
                if statement.strip():
                    db.execute(statement)

    def record_batch(self, set_key, submission_id, batch_digest, record):
        """Create-only. The row is operator-only and never read by a miner path."""
        raw = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self.ledger._db() as db:
            db.execute(
                "INSERT OR IGNORE INTO pack_set_batch VALUES(?,?,?,?,?,?)",
                (
                    set_key,
                    submission_id,
                    batch_digest,
                    record.get("status") if type(record) is dict else "MALFORMED",
                    raw,
                    int(self.clock()),
                ),
            )

    def batch_rows(self, set_key, submission_id):
        """Operator-only: the per-batch rows, for audits."""
        with self.ledger._db() as db:
            rows = db.execute(
                "SELECT batch_digest, record FROM pack_set_batch "
                "WHERE set_key=? AND submission_id=? ORDER BY batch_digest",
                (set_key, submission_id),
            ).fetchall()
        return {digest: json.loads(raw) for digest, raw in rows}

    def _write_result(self, set_key, submission_id, result):
        raw = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self.ledger._db() as db:
            db.execute(
                "INSERT OR IGNORE INTO pack_set_result VALUES(?,?,?,?,?)",
                (set_key, submission_id, result["status"], raw, int(self.clock())),
            )

    def result(self, set_key, submission_id):
        """The set-level result, or None when none was computed (the only value
        a miner-facing path may read)."""
        with self.ledger._db() as db:
            row = db.execute(
                "SELECT result FROM pack_set_result WHERE set_key=? AND submission_id=?",
                (set_key, submission_id),
            ).fetchone()
        return None if row is None else json.loads(row[0])


def set_graded_row(aggregate):
    """The set-level graded row in the shape the Ladder and KOTH consume
    (`status`, `score`, `legs`, `gates` as PASS/FAIL)."""
    eligible = aggregate["eligible"]
    return {
        "status": SCORED if eligible else GATE_FAILED,
        "score": aggregate["total"],
        "legs": {"A": aggregate["A"], "D": aggregate["D"]},
        "gates": {
            name: ("PASS" if ok else "FAIL") for name, ok in aggregate["gates"].items()
        },
    }


def grade_set(
    cap,
    store,
    *,
    hotkey,
    challenge_id,
    challenge_version,
    set_key,
    batches,
    submission_id,
    block,
    grade_batch,
):
    """Grade one submission on every batch of its pack set and write the one
    set-level result.

    ``batches`` are the set's manifest digests in order; ``grade_batch(digest)``
    returns that batch's graded row (the ScoreEngine's, with the per-pack cap,
    Ladder and KOTH steps off) or raises. The epoch slot is reserved once under
    the set key and settled once. Returns the set result, or
    ``{"state": "UNAVAILABLE", "reason": code}`` with the slot given back and
    nothing written as a result.
    """
    if type(batches) not in (list, tuple) or not batches:
        raise SetResultRefused("set_batches")
    reservation = cap.reserve(
        hotkey=hotkey,
        challenge_id=challenge_id,
        challenge_version=challenge_version,
        exam_key=set_key,
        submission_id=submission_id,
        block=block,
        regrade=False,
    )

    def give_back(reason):
        cap.settle(reservation, UNAVAILABLE)
        return {"state": UNAVAILABLE, "reason": reason}

    measurements = []
    for digest in batches:
        try:
            record = grade_batch(digest)
        except Exception as exc:  # noqa: BLE001 - any batch fault is infrastructure
            return give_back(getattr(exc, "code", "set_batch_unavailable"))
        try:
            measurements.append(_batch_measurement(record))
        except SetResultRefused as exc:
            status = record.get("status") if type(record) is dict else None
            store.record_batch(
                set_key,
                submission_id,
                digest,
                {
                    "status": status if type(status) is str else "MALFORMED",
                    "refused": exc.code,
                },
            )
            return give_back(exc.code)
        store.record_batch(set_key, submission_id, digest, record)
    try:
        aggregate = common.aggregate(measurements)
    except common.PackSetRefused as exc:
        return give_back(exc.code)
    row = set_graded_row(aggregate)
    result = {
        "schema": SET_RESULT_SCHEMA,
        "set_key": set_key,
        "challenge": {"id": challenge_id, "version": challenge_version},
        "batches": len(batches),
        "status": row["status"],
        "eligible": aggregate["eligible"],
        "graded": row,
    }
    store._write_result(set_key, submission_id, result)
    # One slot, settled once on the set's outcome (a gate failure still spends it).
    cap.settle(reservation, row["status"])
    return result
