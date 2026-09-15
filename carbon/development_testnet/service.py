"""Issue an all-burn testnet intent from active, signed DEVELOPMENT evidence."""

from __future__ import annotations

import json
from dataclasses import asdict

from carbon.audit import (
    DevelopmentEvidenceLedger,
    DevelopmentRunStatus,
    ReceiptLifecycleState,
)
from carbon.miner_mcp import MinerMcpJournal
from carbon.orchestration import OperationalDisposition
from carbon.rewards.core import Q12
from carbon.rewards.ledger import encode
from carbon.transport.models import digest
from carbon.transport.store import ReceiptJournal

from .model import (
    AUTHORITY,
    INTENT_SCHEMA,
    PROFILE_ID,
    DevelopmentTestnetEvidence,
    DevelopmentTestnetFailure,
    DevelopmentTestnetProfile,
    DevelopmentTestnetWeightIntent,
)

VALIDITY_MS = 60_000


class DevelopmentTestnetIntentIssuer:
    """A distinct non-official issuer; unresolved science can only burn."""

    def __init__(
        self,
        receipts: ReceiptJournal,
        evidence_ledger: DevelopmentEvidenceLedger,
        authenticated_journal: MinerMcpJournal,
        profile: DevelopmentTestnetProfile,
    ) -> None:
        if (
            type(receipts) is not ReceiptJournal
            or type(evidence_ledger) is not DevelopmentEvidenceLedger
            or type(authenticated_journal) is not MinerMcpJournal
            or type(profile) is not DevelopmentTestnetProfile
            or receipts.context != profile.context
        ):
            raise DevelopmentTestnetFailure("DEVELOPMENT_TESTNET_CONTEXT_REQUIRED")
        self.receipts = receipts
        self.evidence_ledger = evidence_ledger
        self.authenticated_journal = authenticated_journal
        self.profile = profile
        with receipts.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS development_testnet_intent_v1 "
                "(identity TEXT PRIMARY KEY, digest TEXT NOT NULL, body TEXT NOT NULL)"
            )

    def _validate_source(self, source: DevelopmentTestnetEvidence):
        if type(source) is not DevelopmentTestnetEvidence:
            raise DevelopmentTestnetFailure("DEVELOPMENT_EVIDENCE_REQUIRED")
        signed, state = self.evidence_ledger.resolve(
            source.ledger_reference,
            verified_at_micros=source.account.finished_at_micros,
        )
        receipt = signed.receipt
        try:
            authenticated = self.authenticated_journal.resolve_development_source(
                source.authenticated_request_receipt, source.account
            )
        except Exception:  # noqa: BLE001 - normalize cross-owner failures.
            raise DevelopmentTestnetFailure("INELIGIBLE_AUTHENTICATED_SOURCE") from None
        if (
            state is not ReceiptLifecycleState.ACTIVE
            or receipt.run_status is not DevelopmentRunStatus.COMPLETE_UNRESOLVED
            or source.account.disposition
            is not OperationalDisposition.COMPLETE_UNRESOLVED
            or receipt.receipt_id != source.account.receipt_id
            or receipt.receipt_digest != source.account.receipt_digest
            or receipt.binding.submission_id != source.account.submission_id
            or authenticated.challenge_id != receipt.binding.challenge_id
            or authenticated.challenge_version != receipt.binding.challenge_version
            or receipt.started_at_micros != source.account.started_at_micros
            or receipt.finished_at_micros != source.account.finished_at_micros
            or any(
                value is not False
                for value in (
                    receipt.protected_execution_eligible,
                    receipt.score_eligible,
                    receipt.archive_acknowledged,
                    receipt.network_eligible,
                    receipt.reward_eligible,
                    source.account.official,
                    source.account.protected_execution_eligible,
                    source.account.score_eligible,
                    source.account.archive_acknowledged,
                    source.account.network_eligible,
                    source.account.reward_eligible,
                )
            )
        ):
            raise DevelopmentTestnetFailure("INELIGIBLE_DEVELOPMENT_EVIDENCE")
        return authenticated

    def issue(
        self,
        identity: str,
        source: DevelopmentTestnetEvidence,
        *,
        snapshot,
    ) -> DevelopmentTestnetWeightIntent:
        if snapshot.context != self.profile.context:
            raise DevelopmentTestnetFailure("DEVELOPMENT_TESTNET_SNAPSHOT_MISMATCH")
        authenticated = self._validate_source(source)
        body = encode(
            {
                "schema": INTENT_SCHEMA,
                "identity": identity,
                "stage": "PUBLIC_TESTNET_DEVELOPMENT",
                "maturity": "DEVELOPMENT_ONLY",
                "authority": AUTHORITY,
                "profile": PROFILE_ID,
                "context": asdict(self.profile.context),
                "runtime_spec": self.profile.expected_runtime_spec,
                "mechanism_id": self.profile.mechanism_id,
                "valid_from_ms": snapshot.timestamp_ms,
                "valid_until_ms": snapshot.timestamp_ms + VALIDITY_MS,
                "snapshot": snapshot.snapshot_id,
                "block": snapshot.finalized_block,
                "source": {
                    "account_digest": source.account.account_digest,
                    "authenticated_request": {
                        "receipt_sequence": source.authenticated_request_receipt.sequence,
                        "receipt_digest": "sha256:"
                        + source.authenticated_request_receipt.digest,
                        "body_digest": "sha256:" + authenticated.body_digest,
                        "hotkey": authenticated.hotkey,
                        "coldkey": authenticated.coldkey,
                        "uid": authenticated.uid,
                    },
                    "development_receipt_digest": (
                        source.ledger_reference.receipt_digest
                    ),
                    "development_receipt_network_eligible": False,
                    "local_retention": asdict(source.local_retention),
                },
                "scientific_disposition": "UNRESOLVED_UNQUALIFIED",
                "route": "DIRECT_WINNER_PLUS_BURN",
                "no_winner": True,
            }
        )
        key = digest(body.encode())
        with self.receipts.transaction() as db:
            row = db.execute(
                "SELECT digest,body FROM development_testnet_intent_v1 WHERE identity=?",
                (identity,),
            ).fetchone()
            if row:
                if row != (key, body):
                    raise DevelopmentTestnetFailure("CONFLICTING_DEVELOPMENT_INTENT")
            else:
                db.execute(
                    "INSERT INTO development_testnet_intent_v1 VALUES (?,?,?)",
                    (identity, key, body),
                )
        return DevelopmentTestnetWeightIntent(identity, key)

    def resolve(self, ref: DevelopmentTestnetWeightIntent, snapshot):
        if type(ref) is not DevelopmentTestnetWeightIntent:
            raise DevelopmentTestnetFailure("DEVELOPMENT_TESTNET_INTENT_REQUIRED")
        with self.receipts.transaction() as db:
            row = db.execute(
                "SELECT digest,body FROM development_testnet_intent_v1 WHERE identity=?",
                (ref.identity,),
            ).fetchone()
        if row is None or row[0] != ref.digest or digest(row[1].encode()) != ref.digest:
            raise DevelopmentTestnetFailure("UNKNOWN_DEVELOPMENT_TESTNET_INTENT")
        body = json.loads(row[1])
        if (
            body["context"] != asdict(snapshot.context)
            or snapshot.context != self.profile.context
            or body["stage"] != "PUBLIC_TESTNET_DEVELOPMENT"
            or body["maturity"] != "DEVELOPMENT_ONLY"
            or body["authority"] != AUTHORITY
            or body["profile"] != PROFILE_ID
            or body["scientific_disposition"] != "UNRESOLVED_UNQUALIFIED"
            or body["source"]["development_receipt_network_eligible"] is not False
            or body["no_winner"] is not True
            or not body["valid_from_ms"]
            <= snapshot.timestamp_ms
            < body["valid_until_ms"]
            or snapshot.finalized_block < body["block"]
            or (
                snapshot.finalized_block == body["block"]
                and snapshot.snapshot_id != body["snapshot"]
            )
        ):
            raise DevelopmentTestnetFailure("STALE_OR_CONFLICTING_DEVELOPMENT_INTENT")
        projection = {
            "schema": "carbon.development-testnet.all-burn-projection.v1",
            "maturity": "DEVELOPMENT_ONLY",
            "route": "DIRECT_WINNER_PLUS_BURN",
            "context": body["context"],
            "snapshot": body["snapshot"],
            "block": body["block"],
            "time_ms": body["valid_from_ms"],
            "states": [body["source"]["development_receipt_digest"]],
            "targets": {"challenges": [], "winners": [], "burn": Q12},
        }
        return {"intent": body, "projection": projection}
