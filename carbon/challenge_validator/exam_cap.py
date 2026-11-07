"""Submission cadence and the exam key's age limit (OWNER-CADENCE-AND-ROTATION-02).

**Cadence.** A miner may make ``a = max(1, floor(R / (M * sum_t)))`` graded submissions per
Challenge per rolling day, and at most one per 360-block epoch. ``R`` is the validator's
registered rebuild capacity in GPU-lane-hours a day (``R = L x 24 x 0.7``, ``L`` the measured
official GPU lanes), ``M`` the number of distinct hotkeys with a graded submission in the
rolling day (over all Challenges, plus the requester), and ``sum_t`` the sum over the
registered Challenges of the mean GPU-lane-hours per graded submission (lane start to
release), measured from the receiver's own receipts (a Challenge with no sample yet uses its
registered measured value). A day is 20 epochs (7200 blocks); the block always comes from the
signed receipt, never from the miner. The registry (``exam_cadence.json``, schema v2) holds
R, the per-Challenge lane-hours, the lane count and the digests of the measurement and of the
host-class record they came from; the recalibration writes it and it is changed only by
review. When it is absent, malformed, unvalued or inconsistent grading refuses
(``exam_cadence_unregistered``); a v1 (CPU-hours) file is refused as
``exam_cadence_schema_unsupported``: no default, fail closed.

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
``exam_cap_unregistered`` (a Challenge not registered), ``exam_cadence_unregistered`` and
``exam_cadence_schema_unsupported``.

**Admission check.** The two limit refusals above are also checked, read-only, when a submission is
admitted and before anything is built (`ExamCap.admission_refusal`): a hotkey that already holds its graded
exam in this epoch (or has used its day's allowance) is told so at once, in plain words with the next
round's block and time (`plain_text`), instead of after the build. It reads exactly the rows `reserve`
counts, takes no slot, writes no row and grades nothing; `reserve` stays the authority at grading time (an
in-flight build holds no slot, so a race between two builds is still decided there, with the same plain text).

**Same recipe, same pack set.** A submission is hotkey + contract + recipe + evaluation
pack (the receiver's task identity), so a resubmit of a graded recipe on the same pack set
is the same submission. The receiver refuses it at its door (``holds_slot``;
``same_recipe_already_submitted``, with the earlier result), before any reservation, so
the epoch's slot stays free for a different recipe. On a rotated pack set it is a new
submission (a re-exam). A grading given back as FAILED_INFRA is never the
miner's result: the same recipe then runs again as a fresh task
(``released_on_infra``).

**Per funder (OWNER-PROBING-COUNTERS-01 (a)).** With a grouping installed (`install_grouping`,
`allowance_groups`), the epoch slot and the daily allowance are counted per ALLOWANCE GROUP (every hotkey of one
coldkey, joined per funder by the Chain Auditor's map) and ``M`` counts groups. A row filed before the grouping keeps
its own hotkey (not retroactive): it still counts for that hotkey, never for its group's other hotkeys. With no grouping
installed, every hotkey is its own group, exactly as before.

The state lives in the receiver's own attempt ledger file (owner-only SQLite). Nothing here
touches a score, a bank entry or what a miner can see; a refusal is a typed code only.
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
from pathlib import Path

EPOCH_BLOCKS = 360
#: A chain block, in seconds (12 s blocks): the clock behind "next round opens at <UTC time>".
BLOCK_SECONDS = 12
#: One day, in epochs and in blocks (12 s blocks).
DAY_EPOCHS = 20
DAY_BLOCKS = DAY_EPOCHS * EPOCH_BLOCKS
#: An exam key's maximum age, in blocks (90 days).
MAX_EXAM_AGE_BLOCKS = 90 * DAY_BLOCKS
REGISTRY = Path(__file__).with_name("exam_cadence.json")
REGISTRY_SCHEMA = "carbon.exam.cadence-registry.v2"
#: The retired CPU-hours schema: refused, never read.
REGISTRY_SCHEMA_V1 = "carbon.exam.cadence-registry.v1"
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
        # The candidate's graph hit the inference wall twice in the official grade's pair
        # (Validator ruling, 2026-11-01): typed, unscored, charged.
        "WORKER_WALL_LIMIT_REACHED",
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
    lane_seconds REAL,
    UNIQUE(challenge_id, challenge_version, exam_key, submission_id)
);
CREATE INDEX IF NOT EXISTS exam_graded_miner
    ON exam_graded(hotkey, challenge_id, challenge_version, exam_key);
CREATE INDEX IF NOT EXISTS exam_graded_epoch ON exam_graded(epoch, challenge_id);
CREATE TABLE IF NOT EXISTS exam_requeues(
    submission_id TEXT PRIMARY KEY,
    attempt INTEGER NOT NULL,
    queued_ns INTEGER NOT NULL,
    reserved_ns INTEGER
);
CREATE TABLE IF NOT EXISTS exam_keys(
    challenge_id TEXT NOT NULL,
    challenge_version TEXT NOT NULL,
    exam_key TEXT NOT NULL,
    first_block INTEGER NOT NULL,
    PRIMARY KEY(challenge_id, challenge_version, exam_key)
);
"""


#: Miner-facing words for the two limit refusals, said plainly (week-1 item 104). ``{when}`` is the next
#: round's block and, when known, its approximate UTC time.
LIMIT_TEXT = {
    "epoch_limit_reached": (
        "One graded exam per Challenge per round, and this hotkey's graded exam for this round is already "
        "used or in progress. Nothing was built or graded for this submission and it used none of your "
        "allowance. The next round opens at {when}."
    ),
    "exam_daily_allowance_reached": (
        "This hotkey has used its graded exams for the day on this Challenge. Nothing was built or graded "
        "for this submission and it used none of your allowance. A slot frees as earlier graded exams age "
        "past one day; try again in a later round."
    ),
}
#: The same refusals with an allowance grouping installed (OWNER-PROBING-COUNTERS-01 (a)): the slot is shared by every
#: hotkey funded from the same wallet, so "this hotkey's" would be false. DRAFT wording, Miner X's to finalise.
GROUPED_LIMIT_TEXT = {
    "epoch_limit_reached": (
        "One graded exam per Challenge per round is shared by all hotkeys funded from the same wallet, and this "
        "round's graded exam for them is already used or in progress. Nothing was built or graded for this "
        "submission and it used none of your allowance. The next round opens at {when}."
    ),
    "exam_daily_allowance_reached": (
        "The hotkeys funded from the same wallet as this one have used their shared graded exams for the day on "
        "this Challenge. Nothing was built or graded for this submission and it used none of your allowance. A "
        "slot frees as earlier graded exams age past one day; try again in a later round."
    ),
    "allowance_group_unmapped": (
        "This hotkey's funding is not yet in the validator's allowance map, so it cannot be graded yet. Nothing "
        "was built or graded for this submission and it used none of your allowance. Try again in a later round."
    ),
    "allowance_group_unresolved": (
        "The validator cannot read this hotkey's registration right now, so it cannot be graded yet. Nothing was "
        "built or graded for this submission and it used none of your allowance. Try again in a later round."
    ),
}
#: OWNER-PROBING-COUNTERS-01 (a): ``hotkey -> group id`` (`allowance_groups.Grouping`), or None = every hotkey is its own
#: group (as before). Installed once per receiver process (`install_grouping`), like `crown_average.ACTIVE`.
GROUPING = None
#: The key of a row filed with no group (before the release, or with no grouping): its own hotkey.
_ROW_GROUP = "COALESCE(group_id, 'h:' || hotkey)"


def install_grouping(grouping):
    """Install (or, with None, remove) this process's allowance grouping."""
    global GROUPING
    GROUPING = grouping


def group_of(hotkey):
    """The allowance group of ``hotkey``: the installed grouping's (it may raise `ExamCapRefused`), else its own."""
    return "h:" + hotkey if GROUPING is None else GROUPING(hotkey)


def next_round(block, *, now=None):
    """``{"next_block", "next_utc"}`` of the round after the one ``block`` is in: the block that opens it and
    its approximate UTC time (``now`` plus the blocks left at 12 s; ``now`` defaults to the clock).
    """
    epoch = epoch_of(block)
    opens = (epoch + 1) * EPOCH_BLOCKS
    seconds = (time.time() if now is None else now) + (opens - block) * BLOCK_SECONDS
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(seconds))
    return {"next_block": opens, "next_utc": stamp}


def plain_text(code, retry=None):
    """The miner-facing sentence for a limit refusal ``code``, or None for any other code."""
    text = (LIMIT_TEXT if GROUPING is None else GROUPED_LIMIT_TEXT).get(code)
    if text is None:
        return None
    retry = retry or {}
    when = (
        f"block {retry['next_block']} (about {retry['next_utc']})"
        if "next_block" in retry and "next_utc" in retry
        else "the next 360-block round"
    )
    return text.format(when=when)


class ExamCapRefused(ValueError):
    """A typed refusal before grading; ``code`` is the closed reason."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def registered_challenges() -> tuple:
    from carbon.battery import challenge as battery

    return (*_LEAN_CHALLENGES, battery.CHALLENGE.challenge_id)


_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_V2_KEYS = {
    "schema",
    "source",
    "capacity_gpu_lane_hours_per_day",
    "rebuild_gpu_lane_hours",
    "lanes",
    "measurement_digest",
    "class_record_digest",
}


def _positive(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def registered_cadence(path=None) -> dict:
    """The registered capacity and per-Challenge lane-hours (schema v2), or a typed refusal.

    ``exam_cadence_schema_unsupported`` for the retired v1 (CPU-hours) file; ``exam_cadence_unregistered`` for a file
    that is absent, malformed, carries no values yet (the recalibration writes them) or is not exactly v2.
    """
    try:
        document = json.loads(Path(REGISTRY if path is None else path).read_bytes())
    except (OSError, ValueError):
        raise ExamCapRefused("exam_cadence_unregistered") from None
    if type(document) is dict and document.get("schema") == REGISTRY_SCHEMA_V1:
        raise ExamCapRefused("exam_cadence_schema_unsupported")
    try:
        if (
            type(document) is not dict
            or set(document) != _V2_KEYS
            or document["schema"] != REGISTRY_SCHEMA
            or type(document["source"]) is not str
            or not document["source"]
            or not _positive(document["capacity_gpu_lane_hours_per_day"])
            or type(document["lanes"]) is not int
            or document["lanes"] < 1
            or type(document["rebuild_gpu_lane_hours"]) is not dict
            or not document["rebuild_gpu_lane_hours"]
            or any(
                type(name) is not str or not _positive(value)
                for name, value in document["rebuild_gpu_lane_hours"].items()
            )
            or any(
                type(document[key]) is not str
                or _DIGEST.fullmatch(document[key]) is None
                for key in ("measurement_digest", "class_record_digest")
            )
        ):
            raise ValueError("cadence registry malformed")
    except (ValueError, KeyError, TypeError):
        raise ExamCapRefused("exam_cadence_unregistered") from None
    return {
        "capacity_gpu_lane_hours_per_day": float(
            document["capacity_gpu_lane_hours_per_day"]
        ),
        "rebuild_gpu_lane_hours": dict(document["rebuild_gpu_lane_hours"]),
        "lanes": document["lanes"],
        "measurement_digest": document["measurement_digest"],
        "class_record_digest": document["class_record_digest"],
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


def later_own_holds_the_round(
    ledger, contract_digest: str, *, hotkey, challenge_id, submission_id
) -> bool:
    """Whether the slot of ``submission_id``'s round (the epoch of its signed block) is held by
    one of ``hotkey``'s OWN later submissions: a graded row (RESERVED or COUNTED) of the same
    hotkey and Challenge in that epoch, the rows `_limit_refusal` counts, whose submission
    arrived after this one in the attempt ledger. Read-only; False when the block, the rows or
    the order are unknown."""
    import sqlite3

    block = submission_block(ledger, contract_digest, submission_id)
    if type(block) is not int or block < 0:
        return False
    try:
        with ledger._db() as db:
            holders = db.execute(
                "SELECT submission_id FROM exam_graded WHERE hotkey=? AND challenge_id=? "
                "AND epoch=? AND kind='GRADED' AND state IN ('RESERVED','COUNTED') "
                "AND submission_id<>?",
                (hotkey, challenge_id, epoch_of(block), submission_id),
            ).fetchall()
            arrived = {}
            for name in (submission_id, *(row[0] for row in holders)):
                arrived[name] = db.execute(
                    "SELECT MIN(seq) FROM attempts WHERE kind='OUTCOME' AND "
                    "contract_digest=? AND submission_id=?",
                    (contract_digest, name),
                ).fetchone()[0]
    except sqlite3.OperationalError:  # no slot table yet: nothing holds the round
        return False
    mine = arrived.pop(submission_id)
    return mine is not None and any(
        seq is not None and seq > mine for seq in arrived.values()
    )


def _prepare(db):
    for statement in _DDL.strip().split(";"):
        if statement.strip():
            db.execute(statement)
    columns = {row[1] for row in db.execute("PRAGMA table_info(exam_graded)")}
    if "cpu_seconds" not in columns:
        db.execute("ALTER TABLE exam_graded ADD COLUMN cpu_seconds REAL")
    if "lane_seconds" not in columns:
        # The cadence's rolling mean reads lane_seconds only: older cpu_seconds rows are CPU time, a different unit.
        db.execute("ALTER TABLE exam_graded ADD COLUMN lane_seconds REAL")
    if "group_id" not in columns:
        # OWNER-PROBING-COUNTERS-01 (a): the allowance group a graded row was reserved under. NULL on every older row,
        # which keeps its own hotkey (not retroactive).
        db.execute("ALTER TABLE exam_graded ADD COLUMN group_id TEXT")


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

    def _allowance(self, db, group, epoch, cadence):
        """``a`` and its inputs for one requester's allowance group at one epoch (read-only). ``M`` counts groups
        (each pre-release row is its own hotkey's)."""
        low, high = self._window(epoch)
        rows = db.execute(
            f"SELECT DISTINCT {_ROW_GROUP} FROM exam_graded WHERE kind='GRADED' AND "
            "state IN ('RESERVED','COUNTED') AND epoch>? AND epoch<=?",
            (low, high),
        ).fetchall()
        active = {row[0] for row in rows} | {group}
        measured = cadence["rebuild_gpu_lane_hours"]
        total = 0.0
        for challenge_id in measured:
            mean = db.execute(
                "SELECT AVG(lane_seconds) FROM exam_graded WHERE kind='GRADED' AND "
                "state='COUNTED' AND lane_seconds IS NOT NULL AND challenge_id=? AND "
                "epoch>? AND epoch<=?",
                (challenge_id, low, high),
            ).fetchone()[0]
            if mean is not None:
                total += mean / 3600.0
            else:
                total += measured[challenge_id]
        capacity = cadence["capacity_gpu_lane_hours_per_day"]
        allowed = max(1, math.floor(capacity / (len(active) * total)))
        return {
            "allowance": allowed,
            "active_miners": len(active),
            "sum_rebuild_gpu_lane_hours": total,
            "capacity_gpu_lane_hours_per_day": capacity,
        }

    def allowance(self, *, hotkey: str, block: int) -> dict:
        """The current daily allowance for a hotkey's group (operator view, no side effects)."""
        cadence = self.cadence()
        group = group_of(hotkey)
        with self.ledger._db() as db:
            return self._allowance(db, group, epoch_of(block), cadence)

    def _limit_refusal(
        self, db, hotkey, challenge_id, submission_id, epoch, cadence, group=None
    ):
        """The daily-allowance or epoch refusal code for a graded submission, or None (read-only). The rows counted
        are its allowance group's, plus its own hotkey's rows filed before any grouping (not retroactive)."""
        group = "h:" + hotkey if group is None else group
        low, high = self._window(epoch)
        # A re-queued stuck task (`mark_requeued`) never counts against anyone's round or day (Validator 4 Nov 15:53).
        held = (
            "kind='GRADED' AND state IN ('RESERVED','COUNTED') AND submission_id<>? "
            "AND submission_id NOT IN (SELECT submission_id FROM exam_requeues)"
        )
        allowed = self._allowance(db, group, epoch, cadence)["allowance"]
        mine = f"({_ROW_GROUP}=? OR (group_id IS NULL AND hotkey=?))"
        used = db.execute(
            f"SELECT COUNT(*) FROM exam_graded WHERE {mine} AND "
            f"challenge_id=? AND epoch>? AND epoch<=? AND {held}",
            (group, hotkey, challenge_id, low, high, submission_id),
        ).fetchone()[0]
        in_epoch = db.execute(
            f"SELECT COUNT(*) FROM exam_graded WHERE {mine} AND "
            f"challenge_id=? AND epoch=? AND {held}",
            (group, hotkey, challenge_id, epoch, submission_id),
        ).fetchone()[0]
        return (
            "exam_daily_allowance_reached"
            if used >= allowed
            else "epoch_limit_reached" if in_epoch >= 1 else None
        )

    def admission_refusal(
        self, *, hotkey, challenge_id, challenge_version, exam_key, submission_id, block
    ):
        """At admission, before anything is built: the limit refusal `reserve` would give this graded
        submission now, as ``{"code", "message"}`` plus ``next_block``/``next_utc`` for the epoch limit, or None.

        Read-only: no slot is taken, no row written, nothing graded, no allowance used. It answers None
        wherever `reserve` would not reach the limits (no block, an unregistered Challenge or cadence, a
        submission that already holds its row, an expired exam key): those stay `reserve`'s to decide.
        """
        if type(block) is not int or block < 0:
            return None
        values = (hotkey, challenge_id, challenge_version, exam_key, submission_id)
        if not all(type(value) is str and value for value in values):
            return None
        try:
            cadence = self.cadence()
        except ExamCapRefused:
            return None
        if challenge_id not in cadence["rebuild_gpu_lane_hours"]:
            return None
        try:
            group = group_of(hotkey)
        except ExamCapRefused as refused:
            # the grouping's own refusal (an owner-chosen ``refuse`` policy): told at once, like a limit
            return {"code": refused.code, "message": plain_text(refused.code)}
        epoch = epoch_of(block)
        with self.ledger._db() as db:
            row = db.execute(
                "SELECT state FROM exam_graded WHERE challenge_id=? AND "
                "challenge_version=? AND exam_key=? AND submission_id=?",
                (challenge_id, challenge_version, exam_key, submission_id),
            ).fetchone()
            if row is not None and row[0] in ("RESERVED", "COUNTED"):
                return None
            if db.execute(
                "SELECT 1 FROM exam_requeues WHERE submission_id=? AND reserved_ns IS NULL",
                (submission_id,),
            ).fetchone():
                # its one re-queued grade (`mark_requeued`): `reserve` bypasses the limits for it, so admission does too
                return None
            first = db.execute(
                "SELECT first_block FROM exam_keys WHERE challenge_id=? AND "
                "challenge_version=? AND exam_key=?",
                (challenge_id, challenge_version, exam_key),
            ).fetchone()
            if first is not None and block - first[0] >= MAX_EXAM_AGE_BLOCKS:
                return None
            code = self._limit_refusal(
                db, hotkey, challenge_id, submission_id, epoch, cadence, group
            )
        if code is None:
            return None
        retry = next_round(block) if code == "epoch_limit_reached" else {}
        return {"code": code, **retry, "message": plain_text(code, retry)}

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
        if challenge_id not in cadence["rebuild_gpu_lane_hours"]:
            raise ExamCapRefused("exam_cap_unregistered")
        # A regrade is never counted and has no signed receipt block; its epoch is inert.
        epoch = 0 if regrade and block is None else epoch_of(block)
        kind = "REGRADE" if regrade else "GRADED"
        key = (challenge_id, challenge_version, exam_key, submission_id)
        refusal = None
        # NULL with no grouping installed: such a row keeps its own hotkey once a grouping is turned on
        group = None
        if not regrade and GROUPING is not None:
            try:
                group = GROUPING(hotkey)
            except ExamCapRefused as refused:
                refusal = refused.code
        with self.ledger._db() as db:
            row = db.execute(
                "SELECT id, state FROM exam_graded WHERE challenge_id=? AND "
                "challenge_version=? AND exam_key=? AND submission_id=?",
                key,
            ).fetchone()
            if row is not None and row[1] in ("RESERVED", "COUNTED"):
                return row[0]
            if refusal is not None:
                pass  # the grouping refused: no row, no key, only the audit line below
            elif not regrade:
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
                elif self._take_requeue(db, submission_id):
                    # Its one re-queued grade: the round/day limits neither refuse it nor are spent by it.
                    refusal = None
                else:
                    refusal = self._limit_refusal(
                        db, hotkey, challenge_id, submission_id, epoch, cadence, group
                    )
            if refusal is None:
                now = int(self.clock())
                if row is not None:
                    db.execute(
                        "UPDATE exam_graded SET state='RESERVED', status=NULL, "
                        "epoch=?, kind=?, reserved_ns=?, settled_ns=NULL, "
                        "lane_seconds=NULL, group_id=? WHERE id=?",
                        (epoch, kind, now, group, row[0]),
                    )
                    return row[0]
                cursor = db.execute(
                    "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, "
                    "exam_key, kind, epoch, submission_id, state, reserved_ns, group_id) "
                    "VALUES(?,?,?,?,?,?,?, 'RESERVED', ?, ?)",
                    (*values[:4], kind, epoch, submission_id, now, group),
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

    def mark_requeued(self, submission_id: str, *, attempt: int = 2) -> bool:
        """Record that a stuck, never-charged task was handed back to the grader ONCE (`infra_requeue`, Validator
        4 Nov 15:53 (3)): its next reservation bypasses the round and day limits a single time, its row stays
        accounted to its ORIGINAL arrival epoch (`reserve` takes the signed receipt's block), and it never counts
        against any later submission's limits. True when newly recorded, False when it already was.
        """
        if type(submission_id) is not str or not submission_id:
            raise ExamCapRefused("exam_cap_identity_unavailable")
        if type(attempt) is not int or attempt < 2:
            raise ValueError("a re-queued grade is attempt 2 or later")
        with self.ledger._db() as db:
            added = (
                db.execute(
                    "INSERT OR IGNORE INTO exam_requeues(submission_id, attempt, queued_ns) "
                    "VALUES(?,?,?)",
                    (submission_id, attempt, int(self.clock())),
                ).rowcount
                == 1
            )
            if not added:
                # a LATER attempt (`infra_requeue`: an A2 re-run that failed on attempt 1's binding, Lead 4 Nov):
                # its own single bypass, re-armed once per attempt; the same attempt twice changes nothing
                added = (
                    db.execute(
                        "UPDATE exam_requeues SET attempt=?, queued_ns=?, reserved_ns=NULL "
                        "WHERE submission_id=? AND attempt<?",
                        (attempt, int(self.clock()), submission_id, attempt),
                    ).rowcount
                    == 1
                )
            # A row given back as FAILED_INFRA would make the door run a resubmit of this recipe as a FRESH task while
            # this one is being re-graded (a double grade): it stays RELEASED (no slot) but is no longer 'ended on
            # infrastructure'. If the re-grade fails on infrastructure again, the give-back sets FAILED_INFRA again.
            db.execute(
                "UPDATE exam_graded SET status='REQUEUED' WHERE submission_id=? AND "
                "kind='GRADED' AND state='RELEASED' AND status='FAILED_INFRA'",
                (submission_id,),
            )
            return added

    def _take_requeue(self, db, submission_id) -> bool:
        """Consume this submission's one limit bypass, if it has an unused one (inside `reserve`'s transaction)."""
        return (
            db.execute(
                "UPDATE exam_requeues SET reserved_ns=? WHERE submission_id=? AND "
                "reserved_ns IS NULL",
                (int(self.clock()), submission_id),
            ).rowcount
            == 1
        )

    def settle(self, reservation: int, status: str, *, lane_seconds=None) -> str:
        """Keep the slot for a graded outcome, give it back otherwise; closed vocabulary.

        ``lane_seconds`` is the GPU-lane time of this submission (lane start to release, from
        the receipts); it feeds the rolling mean that sets the cadence.
        """
        if status in COUNTED:
            state = "COUNTED"
        elif status in RELEASED:
            state = "RELEASED"
        else:
            raise ValueError("exam cap outcome is not classified")
        if lane_seconds is not None and (
            type(lane_seconds) not in (int, float)
            or not math.isfinite(lane_seconds)
            or lane_seconds < 0
        ):
            raise ValueError(
                "rebuild lane seconds must be a finite non-negative number"
            )
        with self.ledger._db() as db:
            changed = db.execute(
                "UPDATE exam_graded SET state=?, status=?, settled_ns=?, lane_seconds=? "
                "WHERE id=? AND state='RESERVED'",
                (state, status, int(self.clock()), lane_seconds, reservation),
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
        GRADED row holding its slot, or a graded one whose slot was returned
        under the owner's resubmit promise (`return_promised_slot`: its grade
        stands). The receiver refuses its resubmit
        (``same_recipe_already_submitted``) before anything is reserved."""
        with self.ledger._db() as db:
            row = db.execute(
                "SELECT 1 FROM exam_graded WHERE hotkey=? AND challenge_id=? AND "
                "challenge_version=? AND exam_key=? AND submission_id=? AND "
                "kind='GRADED' AND (state IN ('RESERVED','COUNTED') OR "
                "(state='RELEASED' AND status='SLOT_RETURNED'))",
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

    def release_undelivered(self, submission_id: str) -> dict:
        """Give back the one COUNTED slot of a graded submission whose result never reached the
        miner (Validator 4 Nov 03:15 (b) and 05:17 (3)): our infrastructure lost it, so the charge
        is ours (invariant 7). With `return_promised_slot`, the only ways a COUNTED row is ever given back.

        The CALLER proves the result was not delivered (`infra_requeue.release`: the task's grade
        marker is FAILED and the miner's Ladder shows nothing from that round); this checks only
        the slot. Nothing is regraded or rescored: the row stays as history, now
        RELEASED/FAILED_INFRA (`released_on_infra`), so the same recipe runs again as a fresh
        task. Returns the row as it was; refuses ``release_no_single_counted_row`` unless exactly
        one GRADED row of this submission is COUNTED, ``release_row_changed`` on a race.
        """
        if type(submission_id) is not str or not submission_id:
            raise ExamCapRefused("exam_cap_identity_unavailable")
        with self.ledger._db() as db:
            rows = db.execute(
                "SELECT id, hotkey, challenge_id, challenge_version, exam_key, epoch, "
                "state, status FROM exam_graded WHERE submission_id=? AND "
                "kind='GRADED' AND state='COUNTED'",
                (submission_id,),
            ).fetchall()
            if len(rows) != 1:
                raise ExamCapRefused("release_no_single_counted_row")
            row = rows[0]
            changed = db.execute(
                "UPDATE exam_graded SET state='RELEASED', status='FAILED_INFRA', "
                "settled_ns=? WHERE id=? AND state='COUNTED'",
                (int(self.clock()), row[0]),
            ).rowcount
            if changed != 1:
                raise ExamCapRefused("release_row_changed")
        names = (
            "row",
            "hotkey",
            "challenge_id",
            "challenge_version",
            "exam_key",
            "epoch",
            "prior_state",
            "prior_status",
        )
        return dict(zip(names, row))

    def return_promised_slot(self, submission_id: str) -> dict:
        """Give the slot of one GRADED resubmit back WITHOUT touching its grade (OWNER-RESUBMIT-SLOT-PROMISE-KEEP-01,
        4 Nov: 'If you want to resubmit in the meantime, it won't cost you a slot'). The row stays as history and its
        grade stands (never rescored); it becomes RELEASED / ``SLOT_RETURNED``, which no limit counts. Deliberately NOT
        FAILED_INFRA: that would make the door treat the graded recipe as ended on infrastructure and run it again.
        The caller (`infra_requeue.return_slots`) decides which resubmit qualifies. Returns the row as it was; refuses
        ``slot_return_no_single_counted_row`` unless exactly one GRADED row is COUNTED, ``slot_return_row_changed`` on a
        race."""
        if type(submission_id) is not str or not submission_id:
            raise ExamCapRefused("exam_cap_identity_unavailable")
        with self.ledger._db() as db:
            rows = db.execute(
                "SELECT id, hotkey, epoch, state, status FROM exam_graded WHERE "
                "submission_id=? AND kind='GRADED' AND state='COUNTED'",
                (submission_id,),
            ).fetchall()
            if len(rows) != 1:
                raise ExamCapRefused("slot_return_no_single_counted_row")
            changed = db.execute(
                "UPDATE exam_graded SET state='RELEASED', status='SLOT_RETURNED', "
                "settled_ns=? WHERE id=? AND state='COUNTED'",
                (int(self.clock()), rows[0][0]),
            ).rowcount
            if changed != 1:
                raise ExamCapRefused("slot_return_row_changed")
        return dict(
            zip(("row", "hotkey", "epoch", "prior_state", "prior_status"), rows[0])
        )

    def count_candidate_wall(
        self,
        *,
        hotkey,
        challenge_id,
        challenge_version,
        exam_key,
        submission_id,
        since_ns,
    ) -> str | None:
        """The candidate's own wall stop on the graded bank inference is ITS outcome, COUNTED as the inference pair's
        (Validator 4 Nov 03:17 (1); interim 16:52, orchestration only): the bank grade settled that slot UNAVAILABLE
        before the stop reached the auto-grader, so this re-settles that one row COUNTED / WORKER_WALL_LIMIT_REACHED.
        Otherwise a changed recipe could probe the hidden inputs ('did it hit the wall') uncharged, as often as it likes.

        Only a GRADED row in exactly RELEASED / UNAVAILABLE is moved (compare-and-swap); anything else is left as it
        is, and only a row reserved by THIS attempt (``reserved_ns >= since_ns``). Returns ``"COUNTED"`` when moved, else None (the caller then gives back as before).
        """
        values = (hotkey, challenge_id, challenge_version, exam_key, submission_id)
        if not all(type(value) is str and value for value in values):
            raise ExamCapRefused("exam_cap_identity_unavailable")
        with self.ledger._db() as db:
            changed = db.execute(
                "UPDATE exam_graded SET state='COUNTED', status='WORKER_WALL_LIMIT_REACHED', "
                "settled_ns=? WHERE challenge_id=? AND challenge_version=? AND exam_key=? AND "
                "submission_id=? AND hotkey=? AND kind='GRADED' AND state='RELEASED' AND "
                "status='UNAVAILABLE' AND reserved_ns>=?",
                (
                    int(self.clock()),
                    challenge_id,
                    challenge_version,
                    exam_key,
                    submission_id,
                    hotkey,
                    int(since_ns),
                ),
            ).rowcount
        return "COUNTED" if changed == 1 else None

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
