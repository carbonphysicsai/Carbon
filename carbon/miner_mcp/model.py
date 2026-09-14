"""Closed C-08 values; no listener, official result, or execution authority."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum

from carbon.mcp import (
    ChallengeInfo,
    DryValidateResponse,
    PublishedPrior,
    PublishedScaffold,
    StructuralEstimate,
    SubmissionResult,
    SubmitReceipt,
)
from carbon.transport.models import ReceiptRef, canonical

SCHEMA = "carbon.c08.authenticated-development-composition.v1"


class MinerMcpCode(StrEnum):
    INVALID = "miner_mcp.request.invalid"
    CONFLICT = "miner_mcp.operation.conflict"
    STATE = "miner_mcp.state.invalid"
    RECONCILIATION_REQUIRED = "miner_mcp.reconciliation.required"
    DENIED = "miner_mcp.authority.denied"
    STORE = "miner_mcp.store.failure"


class MinerMcpFailure(RuntimeError):
    """Stable non-echoing C-08 boundary error."""

    def __init__(self, code: MinerMcpCode) -> None:
        self.code = code if type(code) is MinerMcpCode else MinerMcpCode.INVALID
        super().__init__("Authenticated Miner MCP composition failed.")


class BindMode(StrEnum):
    START = "START"
    RESUME_EXISTING = "RESUME_EXISTING"
    ATTACH_COMPLETED = "ATTACH_COMPLETED"


_MCP_RESULTS = (
    ChallengeInfo,
    PublishedPrior,
    PublishedScaffold,
    DryValidateResponse,
    StructuralEstimate,
    SubmitReceipt,
    SubmissionResult,
)
_PUBLIC_KEYS = {
    "schema",
    "submission_id",
    "attempt_number",
    "disposition",
    "completed_stage_count",
    "receipt_id",
    "authority_marker",
    "eligibility",
}
_ELIGIBILITY_KEYS = {
    "official",
    "protected",
    "score",
    "archive_acknowledged",
    "network",
    "reward",
}
_DISPOSITIONS = {
    "COMPLETE_UNRESOLVED",
    "FAILED_GENERATOR",
    "FAILED_RECONSTRUCTION",
    "FAILED_REFERENCE",
    "FAILED_MEASUREMENT",
    "FAILED_INFRASTRUCTURE",
    "CANCELLED",
    "CONTESTED",
    "INDETERMINATE",
}


def _copy_receipt_ref(value: object) -> ReceiptRef:
    if type(value) is not ReceiptRef:
        raise MinerMcpFailure(MinerMcpCode.INVALID)
    try:
        copied = ReceiptRef(value.sequence, value.digest)
    except Exception:  # noqa: BLE001 - normalize the source boundary.
        raise MinerMcpFailure(MinerMcpCode.INVALID) from None
    if (
        type(copied.sequence) is not int
        or not 0 < copied.sequence < 2**63
        or type(copied.digest) is not str
        or len(copied.digest) != 64
        or any(character not in "0123456789abcdef" for character in copied.digest)
    ):
        raise MinerMcpFailure(MinerMcpCode.INVALID)
    return copied


def _copy_public_projection(value: object, submission_id: str) -> dict[str, object]:
    if type(value) is not dict:
        raise MinerMcpFailure(MinerMcpCode.INVALID)
    try:
        encoded = canonical(value)
        copied = json.loads(encoded)
    except Exception:  # noqa: BLE001 - canonical transport error is private here.
        raise MinerMcpFailure(MinerMcpCode.INVALID) from None
    if (
        type(copied) is not dict
        or set(copied) != _PUBLIC_KEYS
        or copied["schema"] != "carbon.c07.public-operational-account.v1"
        or copied["submission_id"] != submission_id
        or type(copied["attempt_number"]) is not int
        or not 1 <= copied["attempt_number"] < 2**63
        or type(copied["disposition"]) is not str
        or copied["disposition"] not in _DISPOSITIONS
        or type(copied["completed_stage_count"]) is not int
        or not 0 <= copied["completed_stage_count"] <= 8
        or (copied["receipt_id"] is not None and type(copied["receipt_id"]) is not str)
        or copied["authority_marker"] != "DEVELOPMENT_ORCHESTRATION_ONLY_NOT_OFFICIAL"
        or type(copied["eligibility"]) is not dict
        or set(copied["eligibility"]) != _ELIGIBILITY_KEYS
        or any(item is not False for item in copied["eligibility"].values())
    ):
        raise MinerMcpFailure(MinerMcpCode.DENIED)
    return copied


@dataclass(frozen=True, slots=True, repr=False)
class AuthenticatedMcpResult:
    """Exact A9 result plus a bounded positive C-07 extension when available."""

    transport_receipt: ReceiptRef
    mcp_result: object
    _orchestration_input: dict[str, object] | None = field(default=None, repr=False)
    schema: str = SCHEMA
    _orchestration_bytes: bytes | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        receipt = _copy_receipt_ref(self.transport_receipt)
        if self.schema != SCHEMA or type(self.mcp_result) not in _MCP_RESULTS:
            raise MinerMcpFailure(MinerMcpCode.INVALID)
        projection = self._orchestration_input
        if projection is not None:
            if type(self.mcp_result) is not SubmissionResult:
                raise MinerMcpFailure(MinerMcpCode.DENIED)
            projection = _copy_public_projection(
                projection, self.mcp_result.status.submission_id.value
            )
        object.__setattr__(self, "transport_receipt", receipt)
        object.__setattr__(
            self,
            "_orchestration_bytes",
            None if projection is None else canonical(projection),
        )
        object.__setattr__(self, "_orchestration_input", None)

    @property
    def orchestration(self) -> dict[str, object] | None:
        if self._orchestration_bytes is None:
            return None
        value = json.loads(self._orchestration_bytes)
        assert type(value) is dict
        return value

    @property
    def extension_bytes(self) -> bytes:
        """Canonical bounded metadata added by C-08; A9 owns its result encoding."""

        return canonical(
            {
                "orchestration": self.orchestration,
                "schema": self.schema,
                "transport_receipt": {
                    "digest": self.transport_receipt.digest,
                    "sequence": self.transport_receipt.sequence,
                },
            }
        )


__all__ = [
    "SCHEMA",
    "AuthenticatedMcpResult",
    "BindMode",
    "MinerMcpCode",
    "MinerMcpFailure",
]
