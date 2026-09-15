"""Nominal values for Carbon's public/synthetic DEVELOPMENT testnet profile."""

from __future__ import annotations

import re
from dataclasses import dataclass

from carbon.audit import LedgerReceiptRef
from carbon.chain import ChainContext
from carbon.orchestration import DevelopmentOperationalAccount
from carbon.transport.models import ReceiptRef

PROFILE_ID = "carbon.public-synthetic-testnet.development.v1"
SCHEMA = "carbon.development-testnet.evidence.v1"
INTENT_SCHEMA = "carbon.development-testnet.weight-intent.v1"
AUTHORITY = "PUBLIC_SYNTHETIC_DEVELOPMENT_TESTNET_ONLY"
TRANSACTION_OPERATION = "SubtensorModule.set_mechanism_weights"
DATA_POLICY = "carbon.public-synthetic.permission-cleared.v1"
RETENTION_POLICY = "carbon:development-testnet:local-review-export:v1"
SDK_VERSION = "11.1.0"
MAX_LOCAL_EVIDENCE_BYTES = 2 * 1024**3
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[._:-][A-Za-z0-9]+)*\Z", re.ASCII)


class DevelopmentTestnetFailure(ValueError):
    """Closed DEVELOPMENT admission error."""


def _digest(value: object) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise DevelopmentTestnetFailure("INVALID_DEVELOPMENT_TESTNET_DIGEST")
    return value


def _token(value: object) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 160
        or not _TOKEN.fullmatch(value)
    ):
        raise DevelopmentTestnetFailure("INVALID_DEVELOPMENT_TESTNET_TOKEN")
    return value


@dataclass(frozen=True, slots=True)
class DevelopmentTestnetProfile:
    """Exact public-chain context; it contains no transaction authority."""

    context: ChainContext
    expected_runtime_spec: int
    sdk_version: str = SDK_VERSION
    profile_id: str = PROFILE_ID
    mechanism_id: int = 0

    def __post_init__(self) -> None:
        if (
            type(self.context) is not ChainContext
            or self.context.network != "testnet"
            or not self.context.endpoint.startswith("wss://")
            or type(self.expected_runtime_spec) is not int
            or self.expected_runtime_spec <= 0
            or self.sdk_version != SDK_VERSION
            or self.profile_id != PROFILE_ID
            or self.mechanism_id != 0
        ):
            raise DevelopmentTestnetFailure("INVALID_DEVELOPMENT_TESTNET_PROFILE")


DEVELOPMENT_TESTNET_PROFILE = PROFILE_ID


@dataclass(frozen=True, slots=True)
class LocalRetentionEvidence:
    """Review/replay bytes on one host plus an operator-verified export."""

    evidence_set_digest: str
    export_manifest_digest: str
    retained_bytes: int
    storage_scope: str = "BOUNDED_LOCAL_OPERATOR_STORAGE"
    policy_id: str = RETENTION_POLICY
    host_loss_recoverable: bool = False
    archive_acknowledgement: None = None

    def __post_init__(self) -> None:
        _digest(self.evidence_set_digest)
        _digest(self.export_manifest_digest)
        if (
            type(self.retained_bytes) is not int
            or not 0 <= self.retained_bytes <= MAX_LOCAL_EVIDENCE_BYTES
            or self.storage_scope != "BOUNDED_LOCAL_OPERATOR_STORAGE"
            or self.policy_id != RETENTION_POLICY
            or self.host_loss_recoverable is not False
            or self.archive_acknowledgement is not None
        ):
            raise DevelopmentTestnetFailure("INVALID_LOCAL_RETENTION_EVIDENCE")


@dataclass(frozen=True, slots=True)
class DevelopmentTestnetEvidence:
    """Exact signed DEVELOPMENT result and authenticated-request association."""

    account: DevelopmentOperationalAccount
    ledger_reference: LedgerReceiptRef
    authenticated_request_receipt: ReceiptRef
    local_retention: LocalRetentionEvidence
    data_policy_id: str = DATA_POLICY
    schema: str = SCHEMA
    authority_marker: str = AUTHORITY

    def __post_init__(self) -> None:
        if (
            type(self.account) is not DevelopmentOperationalAccount
            or type(self.ledger_reference) is not LedgerReceiptRef
            or self.account.receipt_id != self.ledger_reference.receipt_id
            or self.account.receipt_digest != self.ledger_reference.receipt_digest
            or type(self.authenticated_request_receipt) is not ReceiptRef
            or type(self.local_retention) is not LocalRetentionEvidence
            or self.data_policy_id != DATA_POLICY
            or self.schema != SCHEMA
            or self.authority_marker != AUTHORITY
        ):
            raise DevelopmentTestnetFailure("INVALID_DEVELOPMENT_EVIDENCE")
        if (
            type(self.authenticated_request_receipt.sequence) is not int
            or not 0 < self.authenticated_request_receipt.sequence < 2**63
            or type(self.authenticated_request_receipt.digest) is not str
            or len(self.authenticated_request_receipt.digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.authenticated_request_receipt.digest
            )
        ):
            raise DevelopmentTestnetFailure("INVALID_AUTHENTICATED_RECEIPT_REFERENCE")


@dataclass(frozen=True, slots=True)
class DevelopmentTestnetWeightIntent:
    identity: str
    digest: str

    def __post_init__(self) -> None:
        _token(self.identity)
        if (
            type(self.digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", self.digest) is None
        ):
            raise DevelopmentTestnetFailure("INVALID_DEVELOPMENT_TESTNET_INTENT")


@dataclass(frozen=True, slots=True)
class DevelopmentTransactionAuthorization:
    """Concrete operator approval input; never inferred from a wallet file."""

    authorization_id: str
    authority_record_digest: str
    context: ChainContext
    publisher_hotkey: str
    expected_runtime_spec: int
    valid_from_block: int
    valid_through_block: int
    operation: str = TRANSACTION_OPERATION
    mechanism_id: int = 0
    max_dispatches: int = 1
    max_spend_tao: int = 0
    development_only: bool = True

    def __post_init__(self) -> None:
        _token(self.authorization_id)
        _digest(self.authority_record_digest)
        _token(self.publisher_hotkey)
        if (
            type(self.context) is not ChainContext
            or self.context.network != "testnet"
            or type(self.expected_runtime_spec) is not int
            or self.expected_runtime_spec <= 0
            or type(self.valid_from_block) is not int
            or type(self.valid_through_block) is not int
            or not 0 <= self.valid_from_block <= self.valid_through_block
            or self.operation != TRANSACTION_OPERATION
            or self.mechanism_id != 0
            or self.max_dispatches != 1
            or self.max_spend_tao != 0
            or self.development_only is not True
        ):
            raise DevelopmentTestnetFailure("INVALID_TRANSACTION_AUTHORIZATION")

    def validate(self, profile: DevelopmentTestnetProfile, publisher: str) -> None:
        if (
            type(profile) is not DevelopmentTestnetProfile
            or self.context != profile.context
            or self.expected_runtime_spec != profile.expected_runtime_spec
            or self.mechanism_id != profile.mechanism_id
            or publisher != self.publisher_hotkey
        ):
            raise DevelopmentTestnetFailure("TRANSACTION_AUTHORIZATION_MISMATCH")
