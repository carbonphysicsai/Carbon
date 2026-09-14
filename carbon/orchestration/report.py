"""Idempotent private/reviewer/public C-07 report bundle export."""

from __future__ import annotations

import json
import os
from pathlib import Path

from carbon.audit import SignedDevelopmentEvaluationReceipt

from .model import (
    CompletedDevelopmentOrchestration,
    DevelopmentOperationalAccount,
    OrchestrationCode,
    OrchestrationFailure,
)
from .projection import public_projection, reviewer_projection


def _bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            ).encode("ascii")
            + b"\n"
        )
    except (TypeError, ValueError):
        raise OrchestrationFailure(OrchestrationCode.INVALID) from None


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            raise OrchestrationFailure(OrchestrationCode.CONFLICT)
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except FileExistsError:
        raise OrchestrationFailure(OrchestrationCode.CONFLICT) from None


def write_report_bundle(
    output_directory: Path,
    result: CompletedDevelopmentOrchestration | DevelopmentOperationalAccount,
) -> tuple[Path, Path, Path]:
    """Write exact projections; never export TRAIN bytes or a signing key."""

    if (
        not isinstance(output_directory, Path)
        or not output_directory.is_absolute()
        or output_directory.is_symlink()
        or type(result)
        not in {CompletedDevelopmentOrchestration, DevelopmentOperationalAccount}
    ):
        raise OrchestrationFailure(OrchestrationCode.INVALID)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_directory.chmod(0o700)
    account = (
        result.account if type(result) is CompletedDevelopmentOrchestration else result
    )
    private = output_directory / "private-operational-account.json"
    reviewer = output_directory / "reviewer-operational-account.json"
    public = output_directory / "public-operational-account.json"
    private_document: dict[str, object] = {"account": account.document()}
    if type(result) is CompletedDevelopmentOrchestration:
        signed = result.signed_receipt
        assert type(signed) is SignedDevelopmentEvaluationReceipt
        private_document["signed_receipt"] = {
            "body": signed.receipt.document(),
            "signature_hex": signed.signature.hex(),
        }
        # C-07's bundle does not reconstruct ledger lifecycle state. The C-06
        # receipt remains independently resolvable by its exact ledger ref.
        private_document["ledger_reference"] = {
            "entry_digest": result.ledger_reference.entry_digest,
            "receipt_digest": result.ledger_reference.receipt_digest,
            "receipt_id": result.ledger_reference.receipt_id,
            "sequence": result.ledger_reference.sequence,
        }
    _write_exact(private, _bytes(private_document))
    _write_exact(reviewer, _bytes(reviewer_projection(account)))
    _write_exact(public, _bytes(public_projection(account)))
    return private, reviewer, public


__all__ = ["write_report_bundle"]
