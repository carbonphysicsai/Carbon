"""Prospectively admit one public-TRAIN model record to ScoreLab.

This development consumer creates a create-only receipt beside the existing
model artifacts. It does not rewrite the historical parent manifest, score,
qualify, or change the frozen cohort.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import knn_intake_replay

RECEIPT_SCHEMA = "carbon.scorelab.prospective-model-entry-receipt.v1"


class ModelEntryRefused(ValueError):
    """A prospective entry failed integrity, scope, or immutable-write checks."""


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ModelEntryRefused("receipt_noncanonical") from exc


def _artifact_bindings(manifest: dict) -> dict[str, dict]:
    entry = manifest["entry"]
    replay = entry["artifacts"]["prospective_saved_state_replay"]
    receiver = entry["receiver_evidence"]
    return {
        "parent_manifest": dict(manifest["historical_record"]["parent_manifest"]),
        "native_state": dict(entry["artifacts"]["native_state"]),
        "producer_lineage": dict(entry["artifacts"]["producer_lineage"]),
        "replay_fixture": dict(replay["fixture"]),
        "replay_lineage": dict(replay["lineage"]),
        "receiver_check": dict(receiver["receiver_check"]),
        "replay_comparison": dict(receiver["replay_comparison"]),
    }


def _write_create_only(path: Path, body: bytes) -> bool:
    """Write once; an exact retry is idempotent, a different receipt refuses."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise ModelEntryRefused("receipt_existing_unreadable") from exc
        if existing != body:
            raise ModelEntryRefused("receipt_exists_with_different_bytes")
        return False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise ModelEntryRefused("receipt_write_failed") from exc
    return True


def admit_public_train_entry(
    manifest_path: str | Path,
    *,
    artifact_root: str | Path,
    receipt_path: str | Path,
) -> dict:
    """Verify and append one prospective public-TRAIN entry receipt.

    The `ingested` field is true only in the returned receiver receipt after
    this operation has created or verified the exact create-only receipt. The
    producer addendum remains unchanged and continues to say `ingested: false`.
    """
    manifest_path = Path(manifest_path).resolve(strict=True)
    artifact_root = Path(artifact_root).resolve(strict=True)
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelEntryRefused("manifest_unreadable") from exc

    try:
        replay = knn_intake_replay.verify_knn_intake_replay(
            manifest_path, artifact_root=artifact_root
        )
    except (knn_intake_replay.IntakeReplayRefused, OSError) as exc:
        raise ModelEntryRefused(f"replay_refused:{exc}") from exc

    # Bind what the receiver actually checked, not only declarations copied
    # from the producer record. Re-read after replay to detect in-place changes.
    try:
        if manifest_path.read_bytes() != manifest_bytes:
            raise ModelEntryRefused("manifest_changed_during_admission")
        producer_entry = knn_intake_replay.validate_producer_authority(manifest)
        bindings = _artifact_bindings(manifest)
        for ref in bindings.values():
            knn_intake_replay._artifact(artifact_root, ref)
    except (KeyError, TypeError) as exc:
        raise ModelEntryRefused("manifest_binding_shape") from exc
    except knn_intake_replay.IntakeReplayRefused as exc:
        raise ModelEntryRefused(f"artifact_changed_during_admission:{exc}") from exc

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "revision": 1,
        "status": "ACK_PROSPECTIVE_PUBLIC_TRAIN_ENTRY",
        "admission_scope": "PUBLIC_TRAIN_DEVELOPMENT_ONLY",
        "source_addendum": {
            "sha256": _sha256(manifest_bytes),
            "bytes": len(manifest_bytes),
            "schema": manifest.get("schema"),
            "record_revision": manifest.get("record_revision"),
        },
        "entry": {
            "model_id": producer_entry["model_id"],
            "classification": producer_entry["classification"],
            "challenge": producer_entry["challenge"],
            "recipe": producer_entry["recipe"],
            "source": producer_entry["source"],
            "training_data": producer_entry["training_data"],
        },
        "historical_parent": {
            "sha256": bindings["parent_manifest"]["sha256"],
            "status_preserved": "INCOMPLETE",
            "original_output_recovered": False,
        },
        "artifact_bindings": bindings,
        "receiver_replay": {
            "status": "PASS",
            "method": "SAVED_STATE_RELOAD_AND_EXACT_PUBLIC_FIXTURE_REPLAY",
            "report_sha256": _sha256(_canonical_bytes(replay)),
            "state_sha256": replay["state_sha256"],
            "output_bindings": replay["outputs"],
            "historical_original_output_recovered": False,
        },
        "placement": "PROSPECTIVE_OUTSIDE_FROZEN18",
        "effects": {
            "prospective_entry_admitted": True,
            "ingested": True,
            "frozen18_modified": False,
            "scored": False,
            "score_or_truth_join_created": False,
            "qualification_claimed": False,
        },
    }
    receipt_bytes = _canonical_bytes(receipt)
    created = _write_create_only(Path(receipt_path), receipt_bytes)
    return {
        "status": "ADMITTED_PROSPECTIVE_PUBLIC_TRAIN_ENTRY",
        "receipt_sha256": _sha256(receipt_bytes),
        "receipt": receipt,
        "created": created,
    }
