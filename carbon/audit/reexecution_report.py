"""Positive projections and immutable report bundle for C-10 outcomes."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .model import canonical_json
from .reexecution_model import (
    PUBLIC_SCHEMA,
    REVIEWER_SCHEMA,
    ReexecutionCode,
    ReexecutionFailure,
    ReexecutionOutcome,
)


def public_projection(outcome: ReexecutionOutcome) -> dict[str, object]:
    if type(outcome) is not ReexecutionOutcome:
        raise ReexecutionFailure(ReexecutionCode.INVALID)
    return {
        "authority": {
            "archive_eligible": False,
            "network_eligible": False,
            "official": False,
            "publishable_winner": False,
            "reward_eligible": False,
            "scientific_resolution": False,
            "weight_eligible": False,
        },
        "disposition": outcome.disposition.value,
        "quarantine_required": outcome.quarantine_required,
        "request_id": outcome.request_id,
        "schema": PUBLIC_SCHEMA,
    }


def reviewer_projection(outcome: ReexecutionOutcome) -> dict[str, object]:
    if type(outcome) is not ReexecutionOutcome:
        raise ReexecutionFailure(ReexecutionCode.INVALID)
    primary_launches = set(outcome.primary_provenance.worker_launch_digests)
    reexecution_launches = set(outcome.reexecution_provenance.worker_launch_digests)
    primary_scratch = set(outcome.primary_provenance.scratch_scope_digests)
    reexecution_scratch = set(outcome.reexecution_provenance.scratch_scope_digests)
    return {
        "authority": {
            "comparison_policy_qualified": False,
            "scientific_resolution": False,
        },
        "different_scientific_fields": list(outcome.different_scientific_fields),
        "disposition": outcome.disposition.value,
        "independence": {
            "administratively_independent": False,
            "distinct_administrator_trust_domain_identities": (
                outcome.primary_provenance.administrator_trust_domain
                != outcome.reexecution_provenance.administrator_trust_domain
            ),
            "fresh_execution_identity": (
                outcome.primary_provenance.execution_id
                != outcome.reexecution_provenance.execution_id
            ),
            "fresh_worker_launches": bool(primary_launches)
            and bool(reexecution_launches)
            and primary_launches.isdisjoint(reexecution_launches),
            "separate_scratch": bool(primary_scratch)
            and bool(reexecution_scratch)
            and primary_scratch.isdisjoint(reexecution_scratch),
            "same_host": (
                outcome.primary_provenance.host_id
                == outcome.reexecution_provenance.host_id
            ),
        },
        "outcome_digest": outcome.outcome_digest,
        "primary": {
            "account_digest": outcome.primary_account_digest,
            "execution_id": outcome.primary_provenance.execution_id,
            "receipt_digest": outcome.primary_receipt.receipt_digest,
            "resources": outcome.primary_resources.document(),
        },
        "quarantine_required": outcome.quarantine_required,
        "reexecution": {
            "account_digest": outcome.reexecution_account_digest,
            "execution_id": outcome.reexecution_provenance.execution_id,
            "receipt_digest": (
                None
                if outcome.reexecution_receipt is None
                else outcome.reexecution_receipt.receipt_digest
            ),
            "resources": outcome.reexecution_resources.document(),
        },
        "request_digest": outcome.request_digest,
        "request_id": outcome.request_id,
        "schema": REVIEWER_SCHEMA,
        "shared_dependency_digests": list(outcome.shared_dependency_digests),
    }


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        try:
            if path.is_symlink() or path.read_bytes() != payload:
                raise ReexecutionFailure(ReexecutionCode.CONFLICT)
        except OSError:
            raise ReexecutionFailure(ReexecutionCode.STORE) from None
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except FileExistsError:
        raise ReexecutionFailure(ReexecutionCode.CONFLICT) from None
    except OSError:
        raise ReexecutionFailure(ReexecutionCode.STORE) from None


def write_reexecution_report_bundle(
    root: Path, outcome: ReexecutionOutcome
) -> tuple[Path, Path, Path]:
    if (
        not isinstance(root, Path)
        or not root.is_absolute()
        or root.is_symlink()
        or type(outcome) is not ReexecutionOutcome
    ):
        raise ReexecutionFailure(ReexecutionCode.INVALID)
    root.mkdir(parents=True, exist_ok=True)
    private = root / "private.json"
    reviewer = root / "reviewer.json"
    public = root / "public.json"
    _write_exact(private, outcome.canonical_bytes + b"\n")
    _write_exact(reviewer, canonical_json(reviewer_projection(outcome)) + b"\n")
    _write_exact(public, canonical_json(public_projection(outcome)) + b"\n")
    # Parse every written projection before returning controller-owned paths.
    try:
        for path in (private, reviewer, public):
            json.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ReexecutionFailure(ReexecutionCode.STORE) from None
    return private, reviewer, public


__all__ = [
    "public_projection",
    "reviewer_projection",
    "write_reexecution_report_bundle",
]
