"""Externally supplied Ed25519 DEVELOPMENT signing boundary for C-06."""

from __future__ import annotations

from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .model import (
    SIGNING_SCOPE,
    AuditCode,
    AuditFailure,
    DevelopmentEvaluationReceipt,
    SignedDevelopmentEvaluationReceipt,
    digest_bytes,
    validate_digest,
    validate_token,
)


@dataclass(frozen=True, slots=True)
class DevelopmentVerificationKey:
    key_id: str
    public_key: bytes = field(repr=False)
    valid_from_micros: int
    valid_until_micros: int
    scope: str = SIGNING_SCOPE
    revoked_at_micros: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "key_id", validate_token(self.key_id))
        if type(self.public_key) is not bytes or len(self.public_key) != 32:
            raise AuditFailure(AuditCode.INVALID)
        if (
            type(self.valid_from_micros) is not int
            or type(self.valid_until_micros) is not int
            or not 0 <= self.valid_from_micros < self.valid_until_micros < 2**63
            or self.scope != SIGNING_SCOPE
            or (
                self.revoked_at_micros is not None
                and (
                    type(self.revoked_at_micros) is not int
                    or not self.valid_from_micros
                    <= self.revoked_at_micros
                    <= self.valid_until_micros
                )
            )
        ):
            raise AuditFailure(AuditCode.INVALID)

    @property
    def public_key_digest(self) -> str:
        return digest_bytes(self.public_key)

    def permits(self, issued_at_micros: int, verified_at_micros: int) -> bool:
        if (
            type(issued_at_micros) is not int
            or type(verified_at_micros) is not int
            or not self.valid_from_micros <= issued_at_micros <= self.valid_until_micros
            or verified_at_micros < issued_at_micros
        ):
            return False
        return (
            self.revoked_at_micros is None or issued_at_micros < self.revoked_at_micros
        )


class DevelopmentReceiptSigner:
    """Ephemeral signer; callers supply bytes and own custody outside Carbon."""

    __slots__ = ("_private_key", "verification_key")

    def __init__(
        self,
        *,
        key_id: str,
        private_key: bytes,
        valid_from_micros: int,
        valid_until_micros: int,
    ) -> None:
        if type(private_key) is not bytes or len(private_key) != 32:
            raise AuditFailure(AuditCode.INVALID)
        try:
            key = Ed25519PrivateKey.from_private_bytes(private_key)
            public = key.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        except ValueError:
            raise AuditFailure(AuditCode.INVALID) from None
        self._private_key = key
        self.verification_key = DevelopmentVerificationKey(
            key_id=key_id,
            public_key=public,
            valid_from_micros=valid_from_micros,
            valid_until_micros=valid_until_micros,
        )

    def sign(
        self, receipt: DevelopmentEvaluationReceipt
    ) -> SignedDevelopmentEvaluationReceipt:
        if type(receipt) is not DevelopmentEvaluationReceipt:
            raise AuditFailure(AuditCode.INVALID)
        if (
            receipt.signing_key_id != self.verification_key.key_id
            or receipt.signing_public_key_digest
            != self.verification_key.public_key_digest
            or not self.verification_key.permits(
                receipt.finished_at_micros, receipt.finished_at_micros
            )
        ):
            raise AuditFailure(AuditCode.STALE_KEY)
        return SignedDevelopmentEvaluationReceipt(
            receipt=receipt,
            signature=self._private_key.sign(receipt.canonical_bytes),
        )


def verify_signed_receipt(
    signed: SignedDevelopmentEvaluationReceipt,
    key: DevelopmentVerificationKey,
    *,
    verified_at_micros: int,
) -> None:
    if (
        type(signed) is not SignedDevelopmentEvaluationReceipt
        or type(key) is not DevelopmentVerificationKey
    ):
        raise AuditFailure(AuditCode.INVALID)
    receipt = signed.receipt
    if (
        receipt.signing_key_id != key.key_id
        or receipt.signing_public_key_digest != key.public_key_digest
        or not key.permits(receipt.finished_at_micros, verified_at_micros)
    ):
        raise AuditFailure(AuditCode.STALE_KEY)
    try:
        Ed25519PublicKey.from_public_bytes(key.public_key).verify(
            signed.signature, receipt.canonical_bytes
        )
    except (InvalidSignature, ValueError):
        raise AuditFailure(AuditCode.SIGNATURE) from None
    validate_digest(receipt.receipt_digest)
