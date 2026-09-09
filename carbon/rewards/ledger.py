"""Finalized-time fixture reward ledger on the existing Carbon journal."""

import json
import uuid
from dataclasses import asdict, dataclass

from carbon.candidates.model import CandidateRef
from carbon.candidates.store import CandidateJournal
from carbon.cards.development_scorecard import (
    accepted_scorecard,
    checked_document,
    coefficients,
)
from carbon.chain import MetagraphSnapshot
from carbon.transport.models import canonical, digest
from carbon.transport.store import ReceiptJournal

from .core import (
    Q12,
    DevelopmentTerms,
    Holder,
    Record,
    RewardFailure,
    State,
    WinnerStatus,
    advance_batch,
    opening,
    targets,
)
from .review import HOUR_MS, Hour, Review, review


def encode(value):
    """Owned dataclasses use tuples; the canonical persisted schema uses arrays."""
    return canonical(json.loads(json.dumps(value, allow_nan=False))).decode()


def load_state(value):
    raw = json.loads(value)
    terms = raw.pop("terms")
    terms["allocation"] = tuple(tuple(point) for point in terms["allocation"])
    raw["holder"] = Holder(**raw["holder"]) if raw["holder"] else None
    return State(DevelopmentTerms(**terms), **raw)


@dataclass(frozen=True)
class BatchRef:
    identity: str
    digest: str


@dataclass(frozen=True)
class ProjectionRef:
    digest: str


class FixtureRewardLedger:
    """Local fixture policy only. Public methods obtain time from ChainAdapter."""

    def __init__(
        self, receipts: ReceiptJournal, adapter, journals: tuple[CandidateJournal, ...]
    ):
        if (
            type(receipts) is not ReceiptJournal
            or receipts.context.network != "localnet"
            or type(journals) is not tuple
            or len(journals) > 64
        ):
            raise RewardFailure("FIXTURE_CONTEXT_REQUIRED")
        if any(
            type(j) is not CandidateJournal
            or j.receipts.path.resolve() != receipts.path.resolve()
            or j.receipts.context != receipts.context
            for j in journals
        ):
            raise RewardFailure("JOURNAL_CONTEXT_MISMATCH")
        self.receipts, self.adapter = receipts, adapter
        self.journals = {j.context.identity: j for j in journals}
        if len(self.journals) != len(journals):
            raise RewardFailure("DUPLICATE_CONTEXT")
        with receipts.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_clock_v1 (id INTEGER PRIMARY KEY CHECK(id=1), block INTEGER NOT NULL, time_ms INTEGER NOT NULL, snapshot TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_state_v1 (context TEXT PRIMARY KEY, terms TEXT NOT NULL, terms_digest TEXT NOT NULL, state TEXT NOT NULL, state_digest TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_batch_v1 (identity TEXT PRIMARY KEY, context TEXT NOT NULL, body TEXT NOT NULL, digest TEXT NOT NULL, status TEXT NOT NULL, result TEXT, result_digest TEXT)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS reward_batch_open ON reward_batch_v1(context,status)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_event_v1 (candidate TEXT PRIMARY KEY, batch TEXT NOT NULL, provenance TEXT NOT NULL, gain_record TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_credit_v1 (batch TEXT PRIMARY KEY, previous_record TEXT NOT NULL, new_record TEXT NOT NULL, activation_ms INTEGER NOT NULL, winner_event TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_hold_v1 (candidate TEXT PRIMARY KEY, status TEXT NOT NULL, reason TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_projection_v1 (digest TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_disclosure_v1 (context TEXT PRIMARY KEY, coefficients TEXT NOT NULL, released INTEGER NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_alias_v1 (identity TEXT PRIMARY KEY, alias TEXT NOT NULL UNIQUE)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_scorecard_v1 (candidate TEXT PRIMARY KEY, context TEXT NOT NULL, bucket INTEGER NOT NULL, body TEXT NOT NULL)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS reward_release_bucket ON reward_scorecard_v1(context,bucket)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_hour_v1 (context TEXT NOT NULL, start_ms INTEGER NOT NULL, body TEXT NOT NULL, conflicted INTEGER NOT NULL, PRIMARY KEY(context,start_ms))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_hour_receipt_v1 (identity TEXT PRIMARY KEY, digest TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reward_review_v1 (context TEXT NOT NULL, review_ms INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(context,review_ms))"
            )

    async def _snapshot(self):
        with self.receipts.transaction() as db:
            row = db.execute("SELECT block FROM reward_clock_v1 WHERE id=1").fetchone()
        snapshot = await self.adapter.observe(
            minimum_finalized_block=row[0] if row else 0
        )
        if (
            type(snapshot) is not MetagraphSnapshot
            or snapshot.context != self.receipts.context
        ):
            raise RewardFailure("CHAIN_CONTEXT_MISMATCH")
        return snapshot

    def _bind_time(self, db, snapshot):
        row = db.execute(
            "SELECT block,time_ms,snapshot FROM reward_clock_v1 WHERE id=1"
        ).fetchone()
        if row and (
            snapshot.finalized_block < row[0]
            or snapshot.timestamp_ms < row[1]
            or (snapshot.finalized_block == row[0] and snapshot.snapshot_id != row[2])
        ):
            raise RewardFailure("STALE_OR_CONFLICTING_CHAIN_TIME")
        db.execute(
            "INSERT OR REPLACE INTO reward_clock_v1 VALUES (1,?,?,?)",
            (snapshot.finalized_block, snapshot.timestamp_ms, snapshot.snapshot_id),
        )

    def _state(self, db, context):
        row = db.execute(
            "SELECT terms,terms_digest,state,state_digest FROM reward_state_v1 WHERE context=?",
            (context,),
        ).fetchone()
        if (
            row is None
            or digest(row[0].encode()) != row[1]
            or digest(row[2].encode()) != row[3]
        ):
            raise RewardFailure("MISSING_OR_CONFLICTING_STATE")
        state = load_state(row[2])
        if state.terms.context_id != context or encode(asdict(state.terms)) != row[0]:
            raise RewardFailure("CONFLICTING_TERMS")
        return state

    async def register(self, terms: DevelopmentTerms, score_pack, challenge_alias):
        if type(terms) is not DevelopmentTerms or terms.context_id not in self.journals:
            raise RewardFailure("UNKNOWN_CONTEXT")
        snapshot = await self._snapshot()
        encoded = encode(asdict(terms))
        journal = self.journals[terms.context_id]
        public_coefficients = encode(
            coefficients(score_pack, challenge_alias, terms.opens_ms)
        )
        if score_pack.pack_pin != journal.context.pack:
            raise RewardFailure("DISCLOSURE_PACK_MISMATCH")
        cutoff = self.receipts.highest_receipt()
        with self.receipts.transaction() as db:
            self._bind_time(db, snapshot)
            old = db.execute(
                "SELECT terms FROM reward_state_v1 WHERE context=?", (terms.context_id,)
            ).fetchone()
            if old:
                disclosed = db.execute(
                    "SELECT coefficients FROM reward_disclosure_v1 WHERE context=?",
                    (terms.context_id,),
                ).fetchone()
                if (
                    old[0] != encoded
                    or disclosed is None
                    or disclosed[0] != public_coefficients
                ):
                    raise RewardFailure("CONFLICTING_REGISTRATION")
                return self._state(db, terms.context_id)
            baseline = journal._resolve_accepted_fixture(
                db, CandidateRef(terms.baseline_ref)
            )
            if (
                baseline.context_id != terms.context_id
                or baseline.score_hex != terms.baseline_hex
                or baseline.finalized_block > snapshot.finalized_block
                or snapshot.timestamp_ms > terms.opens_ms
            ):
                raise RewardFailure("BASELINE_OR_OPENING_MISMATCH")
            existing = [
                self._state(db, row[0]).terms
                for row in db.execute("SELECT context FROM reward_state_v1").fetchall()
            ]
            if len(existing) >= 64:
                raise RewardFailure("CHALLENGE_CAPACITY")
            all_terms = [*existing, terms]
            for when in {p[0] for t in all_terms for p in t.allocation}:
                if sum(t.allocated(when) for t in all_terms) > Q12:
                    raise RewardFailure("OVERALLOCATED_SCHEDULE")
            state = opening(terms)
            state_json = encode(asdict(state))
            db.execute(
                "INSERT INTO reward_state_v1 VALUES (?,?,?,?,?)",
                (
                    terms.context_id,
                    encoded,
                    digest(encoded.encode()),
                    state_json,
                    digest(state_json.encode()),
                ),
            )
            db.execute(
                "INSERT INTO reward_disclosure_v1 VALUES (?,?,0)",
                (terms.context_id, public_coefficients),
            )
            journal._enroll_reward(db, cutoff)
            return state

    async def open_batch(self, context, identity):
        if (
            type(identity) is not str
            or not 1 <= len(identity) <= 128
            or not identity.isascii()
        ):
            raise RewardFailure("INVALID_BATCH_ID")
        snapshot = await self._snapshot()
        cutoff = self.receipts.highest_receipt()
        with self.receipts.transaction() as db:
            self._bind_time(db, snapshot)
            old = db.execute(
                "SELECT context,digest FROM reward_batch_v1 WHERE identity=?",
                (identity,),
            ).fetchone()
            if old:
                if old[0] != context:
                    raise RewardFailure("CONFLICTING_BATCH_REPLAY")
                return BatchRef(identity, old[1])
            state = self._state(db, context)
            if (
                not state.terms.opens_ms
                <= snapshot.timestamp_ms
                <= state.terms.admits_until_ms
            ):
                raise RewardFailure("ADMISSION_WINDOW_CLOSED")
            if db.execute(
                "SELECT 1 FROM reward_batch_v1 WHERE context=? AND status='OPEN'",
                (context,),
            ).fetchone():
                raise RewardFailure("PENDING_ADMITTED_BATCH")
            members = self.journals[context]._seal_reward_batch(
                db, identity, snapshot.timestamp_ms, cutoff
            )
            body = encode(
                {
                    "context": context,
                    "activation_ms": snapshot.timestamp_ms,
                    "block": snapshot.finalized_block,
                    "snapshot": snapshot.snapshot_id,
                    "cutoff": cutoff,
                    "members": [r.identity for r in members],
                }
            )
            key = digest(body.encode())
            db.execute(
                "INSERT INTO reward_batch_v1 VALUES (?,?,?,?,'OPEN',NULL,NULL)",
                (identity, context, body, key),
            )
            return BatchRef(identity, key)

    async def close_batch(self, ref: BatchRef):
        if type(ref) is not BatchRef:
            raise RewardFailure("INVALID_BATCH_REF")
        snapshot = await self._snapshot()
        with self.receipts.transaction() as db:
            self._bind_time(db, snapshot)
            row = db.execute(
                "SELECT context,body,digest,status,result,result_digest FROM reward_batch_v1 WHERE identity=?",
                (ref.identity,),
            ).fetchone()
            if (
                row is None
                or row[2] != ref.digest
                or digest(row[1].encode()) != ref.digest
            ):
                raise RewardFailure("CONFLICTING_BATCH_REPLAY")
            if row[3] == "CLOSED":
                if digest(row[4].encode()) != row[5]:
                    raise RewardFailure("CONFLICTING_BATCH_RESULT")
                return load_state(row[4])
            context, body = row[0], json.loads(row[1])
            journal = self.journals[context]
            members = journal._reward_batch_members(db, ref.identity)
            if [r.identity for r, _ in members] != body["members"]:
                raise RewardFailure("CONFLICTING_MEMBERSHIP")
            if any(
                status not in ("ACCEPTED_FIXTURE", "FAILED_INFRA", "REJECTED_SCIENCE")
                for _, status in members
            ):
                raise RewardFailure("PENDING_ADMITTED_BATCH")
            records = []
            for candidate, status in members:
                if status != "ACCEPTED_FIXTURE":
                    continue
                accepted = journal._resolve_accepted_fixture(db, candidate)
                records.append(
                    Record(
                        candidate.identity,
                        accepted.artifact_digest,
                        accepted.score_hex,
                        Holder(
                            accepted.hotkey, accepted.coldkey, accepted.registered_at
                        ),
                        accepted.receipt_sequence,
                    )
                )
                db.execute(
                    "INSERT INTO reward_event_v1 VALUES (?,?,?,?)",
                    (
                        candidate.identity,
                        ref.identity,
                        encode(asdict(accepted)),
                        accepted.score_hex,
                    ),
                )
            prior = self._state(db, context)
            state = advance_batch(prior, tuple(records), body["activation_ms"])
            if state.record_hex != prior.record_hex:
                db.execute(
                    "INSERT INTO reward_credit_v1 VALUES (?,?,?,?,?)",
                    (
                        ref.identity,
                        prior.record_hex,
                        state.record_hex,
                        body["activation_ms"],
                        state.event,
                    ),
                )
            encoded = encode(asdict(state))
            db.execute(
                "UPDATE reward_state_v1 SET state=?,state_digest=? WHERE context=?",
                (encoded, digest(encoded.encode()), context),
            )
            db.execute(
                "UPDATE reward_batch_v1 SET status='CLOSED',result=?,result_digest=? WHERE identity=?",
                (encoded, digest(encoded.encode()), ref.identity),
            )
            return state

    def hold(self, candidate, status: WinnerStatus, reason):
        """Trusted local operator quarantine, never scientific score replacement."""
        if (
            type(candidate) is not CandidateRef
            or status not in (WinnerStatus.DISQUALIFIED, WinnerStatus.CONTESTED)
            or type(status) is not WinnerStatus
            or type(reason) is not str
            or not 1 <= len(reason) <= 128
            or not reason.isascii()
        ):
            raise RewardFailure("INVALID_HOLD")
        with self.receipts.transaction() as db:
            if not db.execute(
                "SELECT 1 FROM reward_event_v1 WHERE candidate=?", (candidate.identity,)
            ).fetchone():
                raise RewardFailure("UNKNOWN_ACCEPTED_EVENT")
            db.execute(
                "INSERT OR REPLACE INTO reward_hold_v1 VALUES (?,?,?)",
                (candidate.identity, status.value, reason),
            )

    async def project(self):
        snapshot = await self._snapshot()
        with self.receipts.transaction() as db:
            self._bind_time(db, snapshot)
            contexts = [
                row[0]
                for row in db.execute(
                    "SELECT context FROM reward_state_v1 ORDER BY context"
                ).fetchall()
            ]
            if any(context not in self.journals for context in contexts):
                raise RewardFailure("INCOMPLETE_CHALLENGE_CONFIGURATION")
            states, statuses = [], {}
            for context in contexts:
                state = self._state(db, context)
                states.append(state)
                status = WinnerStatus.MISSING
                if state.holder:
                    member = snapshot.resolve(state.holder.hotkey)
                    if member and (member.coldkey, member.registered_at) == (
                        state.holder.coldkey,
                        state.holder.registered_at,
                    ):
                        status = WinnerStatus.USABLE
                hold = db.execute(
                    "SELECT status FROM reward_hold_v1 WHERE candidate=?",
                    (state.event,),
                ).fetchone()
                statuses[context] = WinnerStatus(hold[0]) if hold else status
            complete = targets(tuple(states), snapshot.timestamp_ms, statuses)
            body = encode(
                {
                    "schema": "carbon.fixture.reward.projection.v1",
                    "maturity": "SYNTHETIC_ONLY",
                    "route": "DIRECT_WINNER_PLUS_BURN",
                    "context": asdict(snapshot.context),
                    "snapshot": snapshot.snapshot_id,
                    "block": snapshot.finalized_block,
                    "time_ms": snapshot.timestamp_ms,
                    "targets": asdict(complete),
                    "states": [digest(encode(asdict(s)).encode()) for s in states],
                }
            )
            key = digest(body.encode())
            db.execute(
                "INSERT OR IGNORE INTO reward_projection_v1 VALUES (?,?)", (key, body)
            )
            return ProjectionRef(key)

    def resolve_projection(self, ref):
        if type(ref) is not ProjectionRef:
            raise RewardFailure("INVALID_PROJECTION_REF")
        with self.receipts.transaction() as db:
            row = db.execute(
                "SELECT body FROM reward_projection_v1 WHERE digest=?", (ref.digest,)
            ).fetchone()
            if row is None or digest(row[0].encode()) != ref.digest:
                raise RewardFailure("CONFLICTING_PROJECTION")
            return json.loads(row[0])

    def registered_scorecard(self, context):
        """A6 allow-listed registration available before competition opens."""
        with self.receipts.transaction() as db:
            row = db.execute(
                "SELECT coefficients FROM reward_disclosure_v1 WHERE context=?",
                (context,),
            ).fetchone()
            if row is None:
                raise RewardFailure("UNREGISTERED_DISCLOSURE")
            return checked_document(json.loads(row[0]))

    def published_terms(self, context):
        """Economic/evaluation terms contain no private evidence identifiers."""
        card = self.registered_scorecard(context)
        with self.receipts.transaction() as db:
            terms = self._state(db, context).terms
        return {
            "schema": "carbon.development.reward.terms.v1",
            "maturity": "SYNTHETIC_ONLY",
            "challenge": card["challenge"],
            "baseline": str(float.fromhex(terms.baseline_hex)),
            "upper": terms.upper,
            "opens_ms": terms.opens_ms,
            "admission_cutoff_ms": terms.admits_until_ms,
            "funded_until_ms": terms.funded_until_ms,
            "allocation_q12": [list(point) for point in terms.allocation],
            "opening_credit": 0,
            "half_life_seconds": 86400,
            "route": "DIRECT_WINNER_PLUS_BURN",
            "batch_limit": 256,
            "activation": "finalized chain time sealed before A7 admission",
            "evaluation": "existing A7/A8 fixture lifecycle; scientific gates precede comparison",
            "pending": "finish already admitted processing after cutoff; do not silently retire pending work",
            "funding": "targets apply only in the published funding window; no guaranteed chain receipts or retroactive escrow",
            "disclosure": "A6 fixture allow-list; three decimals; at most 256 new records per opening-anchored hour",
        }

    async def release_scorecard(self, context, candidate):
        """Once per accepted fixture; 256 releases/hour, 10,000/context lifetime."""
        snapshot = await self._snapshot()
        with self.receipts.transaction() as db:
            self._bind_time(db, snapshot)
            state = self._state(db, context)
            if snapshot.timestamp_ms < state.terms.opens_ms:
                raise RewardFailure("DISCLOSURE_NOT_OPEN")
            accepted = self.journals[context]._resolve_accepted_fixture(db, candidate)
            old = db.execute(
                "SELECT body FROM reward_scorecard_v1 WHERE candidate=?",
                (candidate.identity,),
            ).fetchone()
            if old:
                return checked_document(json.loads(old[0]))
            bucket = (snapshot.timestamp_ms - state.terms.opens_ms) // HOUR_MS
            registration = db.execute(
                "SELECT coefficients,released FROM reward_disclosure_v1 WHERE context=?",
                (context,),
            ).fetchone()
            count = db.execute(
                "SELECT count(*) FROM reward_scorecard_v1 WHERE context=? AND bucket=?",
                (context, bucket),
            ).fetchone()[0]
            if registration is None or registration[1] >= 10000 or count >= 256:
                raise RewardFailure("DISCLOSURE_BUDGET")
            holder_identity = encode(
                [accepted.hotkey, accepted.coldkey, accepted.registered_at]
            )
            db.execute(
                "INSERT OR IGNORE INTO reward_alias_v1 VALUES (?,?)",
                (holder_identity, "miner-" + uuid.uuid4().hex),
            )
            miner_alias = db.execute(
                "SELECT alias FROM reward_alias_v1 WHERE identity=?", (holder_identity,)
            ).fetchone()[0]
            public = accepted_scorecard(
                json.loads(registration[0])["challenge"],
                miner_alias,
                "result-" + uuid.uuid4().hex,
                float.fromhex(accepted.score_hex),
                tuple(float.fromhex(value) for value in accepted.component_hex),
                snapshot.timestamp_ms,
            )
            db.execute(
                "INSERT INTO reward_scorecard_v1 VALUES (?,?,?,?)",
                (candidate.identity, context, bucket, encode(public)),
            )
            db.execute(
                "UPDATE reward_disclosure_v1 SET released=released+1 WHERE context=?",
                (context,),
            )
            return public

    async def record_hour(self, context, observation_id, hour):
        """Trusted DEVELOPMENT operator rollup: equal-hour average Q12 targets.

        These are application targets/health, not observed chain settlement.
        Unique evidence identity makes redelivery idempotent; a second logical
        observation of the same window makes its diagnostic indeterminate.
        """
        if (
            type(hour) is not Hour
            or type(observation_id) is not str
            or not 1 <= len(observation_id) <= 128
            or not observation_id.isascii()
        ):
            raise RewardFailure("INVALID_HOURLY_OBSERVATION")
        if (
            type(hour.start_ms) is not int
            or not 0 <= hour.start_ms < 2**63
            or any(
                type(v) is not int or not 0 <= v <= Q12
                for v in (hour.allocated, hour.earned, hour.submissions, hour.accepted)
            )
            or hour.earned > hour.allocated
            or hour.accepted > hour.submissions
            or type(hour.evaluator_healthy) is not bool
            or type(hour.publisher_healthy) is not bool
        ):
            raise RewardFailure("INVALID_HOURLY_OBSERVATION")
        snapshot = await self._snapshot()
        body = encode(asdict(hour))
        identity_digest = digest(encode([context, asdict(hour)]).encode())
        with self.receipts.transaction() as db:
            self._bind_time(db, snapshot)
            state = self._state(db, context)
            if (
                hour.start_ms < state.terms.opens_ms
                or (hour.start_ms - state.terms.opens_ms) % HOUR_MS
                or hour.start_ms + HOUR_MS > snapshot.timestamp_ms
            ):
                raise RewardFailure("INCOMPLETE_HOURLY_WINDOW")
            old = db.execute(
                "SELECT digest FROM reward_hour_receipt_v1 WHERE identity=?",
                (observation_id,),
            ).fetchone()
            if old:
                if old[0] != identity_digest:
                    raise RewardFailure("CONFLICTING_OBSERVATION_REPLAY")
                return
            db.execute(
                "INSERT INTO reward_hour_receipt_v1 VALUES (?,?)",
                (observation_id, identity_digest),
            )
            old = db.execute(
                "SELECT 1 FROM reward_hour_v1 WHERE context=? AND start_ms=?",
                (context, hour.start_ms),
            ).fetchone()
            if old:
                db.execute(
                    "UPDATE reward_hour_v1 SET conflicted=1 WHERE context=? AND start_ms=?",
                    (context, hour.start_ms),
                )
            else:
                db.execute(
                    "INSERT INTO reward_hour_v1 VALUES (?,?,?,0)",
                    (context, hour.start_ms, body),
                )

    async def review_next(self, context):
        """Backfill one scheduled review at a time; preserve prior diagnostics."""
        snapshot = await self._snapshot()
        with self.receipts.transaction() as db:
            self._bind_time(db, snapshot)
            state = self._state(db, context)
            previous = db.execute(
                "SELECT MAX(review_ms) FROM reward_review_v1 WHERE context=?",
                (context,),
            ).fetchone()[0]
            scheduled = (
                previous if previous is not None else state.terms.opens_ms
            ) + 7 * 86400000
            if scheduled > snapshot.timestamp_ms:
                return None
            rows = db.execute(
                "SELECT body,conflicted FROM reward_hour_v1 WHERE context=? AND start_ms>=? AND start_ms<? ORDER BY start_ms",
                (context, scheduled - 3 * 86400000, scheduled),
            ).fetchall()
            result = review(
                state.terms.opens_ms,
                scheduled,
                tuple(Hour(**json.loads(row[0])) for row in rows),
            )
            if any(row[1] for row in rows):
                result = Review(
                    "INDETERMINATE_DUPLICATE",
                    state.terms.opens_ms,
                    scheduled,
                    0,
                    0,
                    0,
                    0,
                )
            db.execute(
                "INSERT INTO reward_review_v1 VALUES (?,?,?)",
                (context, scheduled, encode(asdict(result))),
            )
            return result
