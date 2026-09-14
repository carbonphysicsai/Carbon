"""Positive allow-listed projections for signed C-06 DEVELOPMENT evidence."""

from __future__ import annotations

from .model import (
    PUBLIC_SCHEMA,
    REVIEWER_SCHEMA,
    AuditCode,
    AuditFailure,
    LedgerReceiptRef,
    ReceiptLifecycleState,
    SignedDevelopmentEvaluationReceipt,
)


def public_projection(
    signed: SignedDevelopmentEvaluationReceipt,
    reference: LedgerReceiptRef,
    state: ReceiptLifecycleState,
) -> dict[str, object]:
    if (
        type(signed) is not SignedDevelopmentEvaluationReceipt
        or type(reference) is not LedgerReceiptRef
        or type(state) is not ReceiptLifecycleState
        or signed.receipt.receipt_id != reference.receipt_id
        or signed.receipt.receipt_digest != reference.receipt_digest
    ):
        raise AuditFailure(AuditCode.INVALID)
    receipt = signed.receipt
    return {
        "schema": PUBLIC_SCHEMA,
        "receipt_id": receipt.receipt_id,
        "receipt_digest": receipt.receipt_digest,
        "challenge": {
            "id": receipt.binding.challenge_id,
            "version": receipt.binding.challenge_version,
        },
        "submission_id": receipt.binding.submission_id,
        "run_status": receipt.run_status.value,
        "lifecycle_state": state.value,
        "authority_marker": receipt.authority_marker,
        "signing_key_id": receipt.signing_key_id,
        "ledger": {
            "sequence": reference.sequence,
            "entry_digest": reference.entry_digest,
        },
        "eligibility": {
            "official": False,
            "protected": False,
            "score": False,
            "archive_acknowledged": False,
            "network": False,
            "reward": False,
        },
    }


def reviewer_projection(
    signed: SignedDevelopmentEvaluationReceipt,
    reference: LedgerReceiptRef,
    state: ReceiptLifecycleState,
) -> dict[str, object]:
    public = public_projection(signed, reference, state)
    receipt = signed.receipt
    return {
        "schema": REVIEWER_SCHEMA,
        "public": public,
        "binding": receipt.binding.document(),
        "started_at_micros": receipt.started_at_micros,
        "finished_at_micros": receipt.finished_at_micros,
        "supersedes_receipt_id": receipt.supersedes_receipt_id,
        "signature": {
            "algorithm": "Ed25519",
            "public_key_digest": receipt.signing_public_key_digest,
            "signature_hex": signed.signature.hex(),
        },
    }
