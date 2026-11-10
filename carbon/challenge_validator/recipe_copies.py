"""An identical recipe is graded ONCE across all accounts (OWNER-PROBING-COUNTERS-01 (b); Carbon Validator 11:03 definition,
Validator-2 11:04 in-flight rule; TE scope be9aed9a).

**Identical** = the same admission recipe digest (`ConstructionRecipe.digest`: the canonical recipe document; no hotkey,
signature, nonce or timestamp can be in it) for the same Challenge, version and evaluation key (the pack manifest
digest). Near-identical recipes are NOT identical: they are the per-funder allowance's job, never fuzzy matching here.

**Decision** for a submission about to be graded, over the EARLIER submissions of this receiver's contract in
ADMISSION order (`_admitted`: the attempt ledger's own sequence; never the task id, a content hash) (`decide`):

- an earlier one with the same identity was GRADED (its slot COUNTED on this key) -> this one is a COPY of the earliest
  such: it is not graded (no exam read, no rebuild), it is answered with that grade, and its own slot is counted
  against its own allowance (Carbon Validator 6 Nov 11:03 (3): no free probe);
- an earlier one with the same identity is still unsettled (no verdict marker yet, or its slot RESERVED / in flight)
  -> this one WAITS (pending, retried next round, no slot taken) until it settles (Validator-2 11:04);
- every earlier one settled without a counted grade (refused, FAILED_INFRA, released) -> this one GRADES (the new
  first: none of them read the exam).

A rotated pack is a new key: the first submission on it grades. **Not retroactive:** a submission admitted at or before
this rule's activation on its contract (`_activation`: the ledger sequence at the grader's first start after the
release) is never matched, as a copy or as a first.

State (owner-only, in the receiver's own attempt ledger, beside the exam cap): ``recipe_copy_digests`` (submission ->
recipe digest, immutable, written at admission: `note_admitted`), ``recipe_copy_activation`` (contract -> the ledger index the rule starts at) and
``recipe_copies`` (the copy -> its first, key, digest). Nothing here is a grading path: a copy reads no exam.
"""

from __future__ import annotations

import time

#: The cap status a counted copy settles with (`exam_cap.COUNTED`).
DUPLICATE = "DUPLICATE_OF_EARLIER"
GRADE, WAIT, COPY = "grade", "wait", "copy"

_DDL = """
CREATE TABLE IF NOT EXISTS recipe_copy_digests(
    submission_id TEXT PRIMARY KEY,
    recipe_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recipe_copy_activation(
    contract_digest TEXT PRIMARY KEY,
    after_seq INTEGER NOT NULL,
    activated_ns INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS recipe_copies(
    submission_id TEXT PRIMARY KEY,
    first_id TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    challenge_version TEXT NOT NULL,
    exam_key TEXT NOT NULL,
    recipe_digest TEXT NOT NULL,
    recorded_ns INTEGER NOT NULL
);
"""


def _db(ledger):
    db = ledger._db()
    return db


def _prepare(db):
    # statement by statement inside the ledger's own transaction (executescript would commit it), with the exam cap's
    # tables, which the decision reads
    from . import exam_cap

    exam_cap._prepare(db)
    for statement in _DDL.strip().split(";"):
        if statement.strip():
            db.execute(statement)


def _stored(db, submission_id):
    row = db.execute(
        "SELECT recipe_digest FROM recipe_copy_digests WHERE submission_id=?",
        (submission_id,),
    ).fetchone()
    return None if row is None else row[0]


def _request_digest(adapter, submission_id):
    """The admitted recipe digest from this receiver's own provider, or None when it cannot read it.

    NEVER called inside a ledger transaction: ``adapter.owner`` reads the attempt ledger itself, and two
    ``BEGIN IMMEDIATE`` connections in one process wait on each other until 'database is locked' (the RB door on
    4affa5b9, 9 Nov: every submission after the release stopped grading).
    """
    from carbon.development_session.construction_recipe import ConstructionRecipe

    owner = adapter.owner(submission_id)
    if owner is None:
        return None
    request = adapter._provider(owner)._requests.get(submission_id)
    if request is None:
        return None
    return ConstructionRecipe.from_dict(request.recipe).digest


def recipe_digest(adapter, submission_id, ledger):
    """The admitted recipe digest of ``submission_id``, cached once known (the first stored one wins); None when this
    receiver cannot read it. Opens its own short ledger transactions, so the caller must not hold one.
    """
    with _db(ledger) as db:
        _prepare(db)
        stored = _stored(db, submission_id)
    if stored is not None:
        return stored
    digest = _request_digest(adapter, submission_id)
    if digest is None:
        return None
    with _db(ledger) as db:
        db.execute(
            "INSERT OR IGNORE INTO recipe_copy_digests VALUES(?,?)",
            (submission_id, digest),
        )
        return _stored(db, submission_id)


def _admitted(db, contract_digest):
    """``[(submission id, admission sequence)]`` of a contract's admitted submissions, oldest first: the attempt
    ledger's own autoincrement sequence of each one's first OUTCOME row. A task id is a content hash, so ordering by it
    would make "earlier" arbitrary."""
    return db.execute(
        "SELECT submission_id, MIN(seq) FROM attempts WHERE kind='OUTCOME' AND contract_digest=? "
        "AND submission_id IS NOT NULL GROUP BY submission_id ORDER BY MIN(seq)",
        (contract_digest,),
    ).fetchall()


def _activation(db, contract_digest):
    """The ledger sequence this rule starts AFTER for ``contract_digest`` (set once, at the first call after release)."""
    row = db.execute(
        "SELECT after_seq FROM recipe_copy_activation WHERE contract_digest=?",
        (contract_digest,),
    ).fetchone()
    if row is not None:
        return row[0]
    # Not retroactive: every attempt already in the ledger when the rule first runs here is before it.
    (after,) = db.execute("SELECT COALESCE(MAX(seq), 0) FROM attempts").fetchone()
    db.execute(
        "INSERT INTO recipe_copy_activation VALUES(?,?,?)",
        (contract_digest, after, time.time_ns()),
    )
    return after


def activate(ledger, contract_digest):
    """Record the activation point for a contract now (the release step), so every submission admitted after this call
    is under the rule and none before it is. Idempotent: the first call wins."""
    with _db(ledger) as db:
        _prepare(db)
        return _activation(db, contract_digest)


def note_admitted(adapter, submission_id):
    """Store an admitted submission's recipe digest at once (while its provider still holds the request), so a restart,
    which empties the providers' in-memory requests, cannot make a later copy read as fresh.
    """
    return recipe_digest(adapter, submission_id, adapter.ledger)


def decide(
    *,
    adapter,
    ledger,
    marker,
    submission_id,
    challenge_id,
    challenge_version,
    exam_key,
):
    """``(GRADE | WAIT | COPY, first submission id or None)`` for ``submission_id`` about to be graded (see module).

    The order and the activation point are read in one transaction; each recipe digest is then read (and, the first
    time, stored) outside it (`recipe_digest`), and each earlier first's slot state in its own short transaction.
    """
    with _db(ledger) as db:
        _prepare(db)
        ordered = _admitted(db, adapter.contract_digest)
        own = dict(ordered).get(submission_id)
        if own is None:
            return GRADE, None  # no admission row: nothing to order it by
        start = _activation(db, adapter.contract_digest)
    if own <= start:
        return GRADE, None  # admitted before the rule: never matched
    digest = recipe_digest(adapter, submission_id, ledger)
    if digest is None:
        return GRADE, None
    for earlier, seq in ordered:
        if seq <= start:
            continue  # before the rule: never a first
        if seq >= own:
            break
        if recipe_digest(adapter, earlier, ledger) != digest:
            continue
        with _db(ledger) as db:
            row = db.execute(
                "SELECT state FROM exam_graded WHERE challenge_id=? AND challenge_version=? AND exam_key=? "
                "AND submission_id=? AND kind='GRADED'",
                (challenge_id, challenge_version, exam_key, earlier),
            ).fetchone()
        if row is not None and row[0] == "COUNTED":
            return COPY, earlier
        if row is not None and row[0] == "RESERVED":
            return WAIT, earlier
        if row is None and marker(earlier) is None:
            return WAIT, earlier  # still building or queued: unsettled
        # RELEASED, or settled with no counted grade: never read the exam, not a first
    return GRADE, None


def record_copy(
    ledger,
    *,
    submission_id,
    first_id,
    challenge_id,
    challenge_version,
    exam_key,
    recipe_digest_value,
):
    with _db(ledger) as db:
        _prepare(db)
        db.execute(
            "INSERT OR IGNORE INTO recipe_copies VALUES(?,?,?,?,?,?,?)",
            (
                submission_id,
                first_id,
                challenge_id,
                challenge_version,
                exam_key,
                recipe_digest_value,
                time.time_ns(),
            ),
        )


def first_of(ledger, submission_id):
    """The first submission ``submission_id`` is a copy of, or None."""
    with _db(ledger) as db:
        _prepare(db)
        row = db.execute(
            "SELECT first_id FROM recipe_copies WHERE submission_id=?",
            (submission_id,),
        ).fetchone()
    return None if row is None else row[0]


def stored_digest(ledger, submission_id):
    with _db(ledger) as db:
        _prepare(db)
        row = db.execute(
            "SELECT recipe_digest FROM recipe_copy_digests WHERE submission_id=?",
            (submission_id,),
        ).fetchone()
    return None if row is None else row[0]
