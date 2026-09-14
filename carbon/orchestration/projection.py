"""Positive allow-listed C-07 operational projections."""

from __future__ import annotations

from .model import (
    PUBLIC_SCHEMA,
    REVIEWER_SCHEMA,
    DevelopmentOperationalAccount,
    OrchestrationCode,
    OrchestrationFailure,
)


def public_projection(account: DevelopmentOperationalAccount) -> dict[str, object]:
    if type(account) is not DevelopmentOperationalAccount:
        raise OrchestrationFailure(OrchestrationCode.INVALID)
    return {
        "schema": PUBLIC_SCHEMA,
        "submission_id": account.submission_id,
        "attempt_number": account.attempt_number,
        "disposition": account.disposition.value,
        "completed_stage_count": len(account.stages),
        "receipt_id": account.receipt_id,
        "authority_marker": account.authority_marker,
        "eligibility": {
            "official": False,
            "protected": False,
            "score": False,
            "archive_acknowledged": False,
            "network": False,
            "reward": False,
        },
    }


def reviewer_projection(account: DevelopmentOperationalAccount) -> dict[str, object]:
    if type(account) is not DevelopmentOperationalAccount:
        raise OrchestrationFailure(OrchestrationCode.INVALID)
    return {
        "schema": REVIEWER_SCHEMA,
        "public": public_projection(account),
        "request_digest": account.request_digest,
        "account_digest": account.account_digest,
        "started_at_micros": account.started_at_micros,
        "finished_at_micros": account.finished_at_micros,
        "stages": [item.document() for item in account.stages],
        "missing_stages": [item.value for item in account.missing_stages],
        "receipt_digest": account.receipt_digest,
    }


__all__ = ["public_projection", "reviewer_projection"]
