"""C-06 signatures for derived DEVELOPMENT evidence, never official receipts."""

from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from carbon.audit.model import validate_digest, validate_token
from carbon.audit.signing import DevelopmentReceiptSigner, DevelopmentVerificationKey
from carbon.development_session.profile import canonical

DOMAIN = b"carbon.c06.development-derivation.v1\x00"


@dataclass(frozen=True)
class DevelopmentDerivation:
    rule_digest: str
    input_receipts: tuple[str, ...]
    artifact_digest: str
    issued_at_micros: int
    key_id: str
    public_key_digest: str
    kind: str

    def __post_init__(self):
        for v in (
            self.rule_digest,
            self.artifact_digest,
            self.public_key_digest,
            *self.input_receipts,
        ):
            validate_digest(v)
        validate_token(self.key_id)
        if (
            type(self.input_receipts) is not tuple
            or len(self.input_receipts) not in (0, 2)
            or type(self.issued_at_micros) is not int
            or not 0 <= self.issued_at_micros < 2**63
            or self.kind not in ("RULE_REGISTRATION", "DERIVED_COMPARISON")
            or (self.kind == "RULE_REGISTRATION") != (len(self.input_receipts) == 0)
        ):
            raise ValueError("invalid development derivation")

    def document(self):
        return {
            "schema": "carbon.c06.development-derivation.v1",
            "rule_digest": self.rule_digest,
            "input_receipts": list(self.input_receipts),
            "artifact_digest": self.artifact_digest,
            "issued_at_micros": self.issued_at_micros,
            "key_id": self.key_id,
            "public_key_digest": self.public_key_digest,
            "kind": self.kind,
            "scope": "DEVELOPMENT_NONPAYING",
            "official_eligible": False,
            "protected_eligible": False,
            "settlement_eligible": False,
            "network_eligible": False,
        }

    @property
    def canonical_bytes(self):
        return DOMAIN + canonical(self.document())


def sign_derivation(signer, derivation):
    if (
        type(signer) is not DevelopmentReceiptSigner
        or type(derivation) is not DevelopmentDerivation
    ):
        raise ValueError("C-06 nominal signer and derivation required")
    return signer.sign_derivation(derivation)


def verify_derivation(derivation, signature, key, *, now_micros):
    if (
        type(derivation) is not DevelopmentDerivation
        or type(key) is not DevelopmentVerificationKey
        or derivation.key_id != key.key_id
        or derivation.public_key_digest != key.public_key_digest
        or not key.permits(derivation.issued_at_micros, now_micros)
        or key.revoked_at_micros is not None
    ):
        raise ValueError("untrusted, expired or revoked derivation authority")
    Ed25519PublicKey.from_public_bytes(key.public_key).verify(
        signature, derivation.canonical_bytes
    )
