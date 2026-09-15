"""Checked testnet publisher for the exact DEVELOPMENT intent family."""

from carbon.chain.publisher import VerifiedWeightPublisher
from carbon.rewards.core import Q12

from .model import (
    DevelopmentTestnetFailure,
    DevelopmentTestnetWeightIntent,
    DevelopmentTransactionAuthorization,
)
from .service import DevelopmentTestnetIntentIssuer


class DevelopmentTestnetPublisher(VerifiedWeightPublisher):
    def __init__(self, issuer, backend, authorization):
        if type(authorization) is not DevelopmentTransactionAuthorization:
            raise DevelopmentTestnetFailure("TRANSACTION_AUTHORIZATION_REQUIRED")
        authorization.validate(issuer.profile, backend.publisher)
        self.authorization = authorization
        super().__init__(
            issuer,
            backend,
            issuer_type=DevelopmentTestnetIntentIssuer,
            intent_type=DevelopmentTestnetWeightIntent,
            network="testnet",
            spec_version=issuer.profile.expected_runtime_spec,
        )

        with issuer.receipts.transaction() as database:
            database.execute(
                "CREATE TABLE IF NOT EXISTS development_testnet_authorization_v1 "
                "(authorization_id TEXT PRIMARY KEY, authority_digest TEXT NOT NULL, "
                "intent_digest TEXT NOT NULL)"
            )

    def validate_stage(self, ref, snapshot, capabilities, resolved, plan):
        if not (
            self.authorization.valid_from_block
            <= snapshot.finalized_block
            <= self.authorization.valid_through_block
        ):
            raise DevelopmentTestnetFailure("TRANSACTION_AUTHORIZATION_EXPIRED")
        if (
            resolved["intent"]["maturity"] != "DEVELOPMENT_ONLY"
            or resolved["intent"]["no_winner"] is not True
            or plan.q12
            != (
                (
                    capabilities.validate(
                        snapshot,
                        self.backend.publisher,
                        network="testnet",
                        spec_version=self.spec_version,
                    )[1].uid,
                    Q12,
                ),
            )
        ):
            raise DevelopmentTestnetFailure("TRANSACTION_AUTHORIZATION_SCOPE_MISMATCH")
        with self.issuer.receipts.transaction() as database:
            row = database.execute(
                "SELECT authority_digest,intent_digest "
                "FROM development_testnet_authorization_v1 WHERE authorization_id=?",
                (self.authorization.authorization_id,),
            ).fetchone()
            expected = (self.authorization.authority_record_digest, ref.digest)
            if row is None:
                database.execute(
                    "INSERT INTO development_testnet_authorization_v1 VALUES (?,?,?)",
                    (self.authorization.authorization_id, *expected),
                )
            elif row != expected:
                raise DevelopmentTestnetFailure("TRANSACTION_AUTHORIZATION_CONSUMED")

    async def heartbeat(self, request_id):
        raise DevelopmentTestnetFailure(
            "DEVELOPMENT_TESTNET_REQUIRES_EXPLICIT_FROZEN_INTENT"
        )
