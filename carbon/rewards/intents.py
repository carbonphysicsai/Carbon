"""Nominal C0 intent references. Issuance is journal-backed, never a stage flag."""

import json
import re
from dataclasses import asdict, dataclass

from carbon.transport.models import digest

from .core import Q12, RewardFailure
from .ledger import FixtureRewardLedger, ProjectionRef, encode

VALIDITY_MS = 60_000  # DEVELOPMENT maximum, not a production SLO.
POLICY = "carbon.development.bounded_linear.q12.v1"


@dataclass(frozen=True)
class StructuralLocalnetWeightIntent:
    identity: str
    digest: str

    def __post_init__(self):
        if (
            type(self.identity) is not str
            or not 1 <= len(self.identity) <= 128
            or not self.identity.isascii()
            or type(self.digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", self.digest) is None
        ):
            raise RewardFailure("INVALID_INTENT_REFERENCE")


class TestnetWinnerWeightIntent:
    """Reserved C2 family; only C2 real eligibility may provide its issuer."""

    def __new__(cls, *args, **kwargs):
        raise RewardFailure("C2_REAL_ELIGIBILITY_ISSUER_UNAVAILABLE")


class TreasuryRoutingWeightIntent:
    """Optional reserve family; custody and pending-liability admission are absent."""

    def __new__(cls, *args, **kwargs):
        raise RewardFailure("OPTIONAL_TREASURY_ISSUER_UNAVAILABLE")


class LocalnetIntentIssuer:
    def __init__(self, ledger):
        if type(ledger) is not FixtureRewardLedger:
            raise RewardFailure("FIXTURE_LEDGER_REQUIRED")
        if ledger.receipts.context.network != "localnet":
            raise RewardFailure("LOCALNET_REQUIRED")
        self.ledger = ledger
        self.receipts = ledger.receipts
        self.context = digest(encode(asdict(self.receipts.context)).encode())
        with self.receipts.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS localnet_intent_v1 (identity TEXT PRIMARY KEY, digest TEXT NOT NULL, body TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS localnet_intent_active_v1 (context TEXT PRIMARY KEY, identity TEXT NOT NULL)"
            )

    def _load(self, db, identity):
        row = db.execute(
            "SELECT digest,body FROM localnet_intent_v1 WHERE identity=?", (identity,)
        ).fetchone()
        if row and digest(row[1].encode()) != row[0]:
            raise RewardFailure("CONFLICTING_INTENT")
        return row

    def _current(self, db, projection):
        contexts = [
            row[0]
            for row in db.execute(
                "SELECT context FROM reward_state_v1 ORDER BY context"
            ).fetchall()
        ]
        states = [self.ledger._state(db, context) for context in contexts]
        if [digest(encode(asdict(s)).encode()) for s in states] != projection["states"]:
            raise RewardFailure("SUPERSEDED_SCIENTIFIC_STATE")
        earned = {
            row["context_id"]: row["earned"]
            for row in projection["targets"]["challenges"]
        }
        for state in states:
            if (
                earned.get(state.terms.context_id, 0)
                and db.execute(
                    "SELECT 1 FROM reward_hold_v1 WHERE candidate=?", (state.event,)
                ).fetchone()
            ):
                raise RewardFailure("WINNER_QUARANTINED")
        return states

    async def issue(self, identity):
        if (
            type(identity) is not str
            or not 1 <= len(identity) <= 128
            or not identity.isascii()
        ):
            raise RewardFailure("INVALID_INTENT_IDENTITY")
        with self.receipts.transaction() as db:
            old = self._load(db, identity)
            if old:
                return StructuralLocalnetWeightIntent(identity, old[0])
        ref = await self.ledger.project()
        projection = self.ledger.resolve_projection(ref)
        if (
            projection["schema"] != "carbon.fixture.reward.projection.v1"
            or projection["maturity"] != "SYNTHETIC_ONLY"
            or projection["route"] != "DIRECT_WINNER_PLUS_BURN"
            or projection["context"] != asdict(self.receipts.context)
        ):
            raise RewardFailure("WRONG_PROJECTION_AUTHORITY")
        now = projection["time_ms"]
        with self.receipts.transaction() as db:
            old = self._load(db, identity)
            if old:
                return StructuralLocalnetWeightIntent(identity, old[0])
            states = self._current(db, projection)
            boundaries = [now + VALIDITY_MS]
            for state in states:
                boundaries.extend(
                    when
                    for when in (
                        state.terms.opens_ms,
                        state.terms.funded_until_ms,
                        *(p[0] for p in state.terms.allocation),
                    )
                    if when > now
                )
            body = encode(
                {
                    "schema": "carbon.localnet.weight_intent.v1",
                    "identity": identity,
                    "stage": "DISPOSABLE_LOCALNET",
                    "maturity": "SYNTHETIC_ONLY",
                    "policy": POLICY,
                    "route": "DIRECT_WINNER_PLUS_BURN",
                    "context": asdict(self.receipts.context),
                    "projection": ref.digest,
                    "snapshot": projection["snapshot"],
                    "block": projection["block"],
                    "valid_from_ms": now,
                    "valid_until_ms": min(boundaries),
                    "challenge_states": projection["states"],
                    "no_winner": projection["targets"]["burn"] == Q12,
                }
            )
            key = digest(body.encode())
            db.execute(
                "INSERT INTO localnet_intent_v1 VALUES (?,?,?)", (identity, key, body)
            )
            db.execute(
                "INSERT OR REPLACE INTO localnet_intent_active_v1 VALUES (?,?)",
                (self.context, identity),
            )
            return StructuralLocalnetWeightIntent(identity, key)

    def resolve(self, ref, snapshot):
        """NET-4B supplies a freshly observed finalized snapshot before execution.

        A reference alone grants no authority. Resolve immutable journal provenance,
        current scientific state, active issuance, context and chain validity.
        Recipient UID/identity and runtime compatibility are NET-4B's next checks.
        """
        from carbon.chain import MetagraphSnapshot

        if type(ref) is not StructuralLocalnetWeightIntent:
            raise RewardFailure("LOCALNET_INTENT_REQUIRED")
        if type(snapshot) is not MetagraphSnapshot:
            raise RewardFailure("FINALIZED_SNAPSHOT_REQUIRED")
        with self.receipts.transaction() as db:
            row = self._load(db, ref.identity)
            if row is None or ref.digest != row[0]:
                raise RewardFailure("UNKNOWN_OR_CONFLICTING_INTENT")
            body = json.loads(row[1])
            active = db.execute(
                "SELECT identity FROM localnet_intent_active_v1 WHERE context=?",
                (self.context,),
            ).fetchone()
            if active is None or active[0] != ref.identity:
                raise RewardFailure("SUPERSEDED_INTENT")
            if (
                body["context"] != asdict(snapshot.context)
                or snapshot.context != self.receipts.context
                or body["stage"] != "DISPOSABLE_LOCALNET"
                or body["maturity"] != "SYNTHETIC_ONLY"
                or body["policy"] != POLICY
                or body["route"] != "DIRECT_WINNER_PLUS_BURN"
            ):
                raise RewardFailure("INTENT_CONTEXT_OR_STAGE_MISMATCH")
            if (
                snapshot.finalized_block < body["block"]
                or not body["valid_from_ms"]
                <= snapshot.timestamp_ms
                < body["valid_until_ms"]
                or (
                    snapshot.finalized_block == body["block"]
                    and snapshot.snapshot_id != body["snapshot"]
                )
            ):
                raise RewardFailure("STALE_OR_EXPIRED_INTENT")
        projection = self.ledger.resolve_projection(ProjectionRef(body["projection"]))
        if (
            projection["snapshot"] != body["snapshot"]
            or projection["block"] != body["block"]
            or projection["states"] != body["challenge_states"]
            or projection["context"] != body["context"]
            or projection["time_ms"] != body["valid_from_ms"]
        ):
            raise RewardFailure("CONFLICTING_INTENT_PROVENANCE")
        with self.receipts.transaction() as db:
            self.ledger._bind_time(db, snapshot)
            self._current(db, projection)
            # Recheck active issuance after resolving the separate immutable row.
            active = db.execute(
                "SELECT identity FROM localnet_intent_active_v1 WHERE context=?",
                (self.context,),
            ).fetchone()
            if active is None or active[0] != ref.identity:
                raise RewardFailure("SUPERSEDED_INTENT")
        return {"intent": body, "projection": projection}
