"""Create-only ScoreLab index receipts for public, unbound v2 artifacts.

This module records a byte-verified custody-v2 artifact group in a generic
ScoreLab intake shape. It does not admit, score, qualify, import a constructor,
execute a model, or contact/ACK a receiver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts.dev.score_lab import public_unbound_custody as custody

SCHEMA = "carbon.scorelab.public-synthetic-unbound-entry.v1"
GRAPH_ENTRY_SCHEMA_V3 = "carbon.scorelab.public-model-entry.v3"
GRAPH_ENTRY_SCHEMA_V4 = "carbon.scorelab.public-model-entry.v4"
GRAPH_ENTRY_SCHEMA_V5 = "carbon.scorelab.public-model-entry.v5"
MAX_INPUT_JSON_BYTES = custody.MAX_MANIFEST_BYTES
MAX_ENTRY_BYTES = 1024 * 1024
_SHA = re.compile(r"^sha256:[0-9a-f]{64}$")


class EntryRefused(ValueError):
    """The entry inputs are malformed, inconsistent, or unsafe to create."""


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _bounded_regular_file(value, limit: int, label: str) -> tuple[Path, bytes]:
    path = Path(value)
    try:
        if (
            path.is_symlink()
            or not path.is_file()
            or path.resolve(strict=True) != path.absolute()
        ):
            raise EntryRefused(f"{label}_file")
        size = path.stat().st_size
        if size <= 0 or size > limit:
            raise EntryRefused(f"{label}_size")
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) != size or len(raw) > limit or path.stat().st_size != size:
            raise EntryRefused(f"{label}_size_changed")
    except EntryRefused:
        raise
    except OSError as exc:
        raise EntryRefused(f"{label}_read") from exc
    return path, raw


def _json(raw: bytes, label: str) -> dict:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EntryRefused(f"{label}_json") from exc
    if type(value) is not dict:
        raise EntryRefused(f"{label}_object")
    return value


def _canonical(value: dict) -> bytes:
    try:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise EntryRefused("entry_json_value") from exc


def _verified_custody(
    manifest_path: Path,
    manifest_raw: bytes,
    artifacts_path: Path,
    custody_receipt_path: Path,
    custody_receipt_raw: bytes,
) -> tuple[dict, dict]:
    manifest = _json(manifest_raw, "manifest")
    receipt = _json(custody_receipt_raw, "custody_receipt")
    if (
        manifest.get("schema") != custody.SCHEMA_V2
        or manifest.get("mode") != custody.MODE
        or manifest.get("challenge") is not None
        or manifest.get("challenge_version") is not None
        or manifest.get("interface_digest") is not None
        or manifest.get("official_eligible") is not False
        or manifest.get("serving_verified") is not False
        or manifest.get("receiver_ack")
        != {"state": "PENDING", "receipt_file": None, "receipt_digest": None}
    ):
        raise EntryRefused("manifest_not_public_unbound_v2")
    try:
        expected = custody.prepare_custody_v2(artifacts_path, manifest)
    except custody.CustodyRefused as exc:
        raise EntryRefused(f"custody_v2_{exc}") from exc
    if receipt != expected:
        raise EntryRefused("custody_receipt_mismatch")
    if (
        receipt.get("schema") != "carbon.scorelab.public-unbound-custody-receipt.v2"
        or receipt.get("custody_state") != "PUBLIC_BYTES_REHASHED"
        or receipt.get("replay_state") != "PENDING_EXTERNAL_RECEIVER"
        or receipt.get("receiver_ack_state") != "RECEIVER_ACK_PENDING"
        or receipt.get("receiver_ack_authenticity") != "NOT_VERIFIED_BY_THIS_TOOL"
        or receipt.get("challenge") is not None
        or receipt.get("declared_interface_digest") is not None
        or receipt.get("official_eligible") is not False
        or receipt.get("serving_verified") is not False
    ):
        raise EntryRefused("custody_receipt_not_pending_v2")
    if not manifest_path.name or not custody_receipt_path.name:
        raise EntryRefused("input_filename")
    return manifest, receipt


def _entry_record(
    manifest_path: Path,
    manifest_raw: bytes,
    artifacts_path: Path,
    custody_receipt_path: Path,
    custody_receipt_raw: bytes,
) -> dict:
    manifest, receipt = _verified_custody(
        manifest_path,
        manifest_raw,
        artifacts_path,
        custody_receipt_path,
        custody_receipt_raw,
    )
    fixture = manifest["fixture"]
    state = manifest["state"]
    prediction = manifest["producer_prediction"]
    recipe = manifest["recipe"]
    prediction_binding_ok = (
        prediction["file"] == fixture["file"]
        and prediction["file_digest"] == fixture["file_digest"]
    )
    if prediction["file"] != fixture["file"]:
        prediction_binding_ok = receipt.get("producer_prediction_separate_file") == {
            "file": prediction["file"],
            "file_digest": prediction["file_digest"],
        }
    if (
        not prediction_binding_ok
        or prediction["encoding"] != "C_CONTIGUOUS_RAW_V1"
        or type(prediction["arrays"]) is not dict
        or not prediction["arrays"]
        or any(
            type(item) is not str or not _SHA.fullmatch(item)
            for item in prediction["arrays"].values()
        )
    ):
        raise EntryRefused("producer_prediction_binding")

    lineage = {}
    for name in ("source", "bundle", "environment", "image"):
        declared = manifest["lineage"][name]
        observed = receipt["identity_evidence"][name]
        if (
            observed.get("digest") != declared["digest"]
            or observed.get("proof_kind") != declared["proof_kind"]
            or observed.get("evidence_file") != declared["evidence_file"]
            or observed.get("verification") != "DIGEST_BOUND_UNVERIFIED"
        ):
            raise EntryRefused("lineage_binding")
        lineage[name] = {
            "declared_digest": declared["digest"],
            "proof_kind": declared["proof_kind"],
            "evidence_file": declared["evidence_file"],
            "evidence_file_digest": observed["evidence_file_digest"],
            "verification": "DIGEST_BOUND_UNVERIFIED",
        }

    core = {
        "schema": SCHEMA,
        "mode": custody.MODE,
        "legacy_binding": custody.LEGACY_BINDING,
        "challenge": None,
        "challenge_version": None,
        "interface_digest": None,
        "interface_authority_verified": False,
        "serving_verified": False,
        "official_eligible": False,
        "score_state": "NOT_COMPUTED",
        "qualification_state": "NOT_CLAIMED",
        "admission_state": "NOT_ADMITTED",
        "entry_state": "CREATED_UNBOUND_ONLY",
        "entry_semantics": "RECEIPT_ONLY_NOT_ADMISSION",
        "idempotency_key": _sha(
            b"carbon.scorelab.public-synthetic-unbound-entry.v1\0"
            + manifest_raw
            + b"\0"
            + custody_receipt_raw
        ),
        "inputs": {
            "manifest": {
                "file": manifest_path.name,
                "bytes": len(manifest_raw),
                "sha256": _sha(manifest_raw),
            },
            "custody_receipt": {
                "file": custody_receipt_path.name,
                "bytes": len(custody_receipt_raw),
                "sha256": _sha(custody_receipt_raw),
            },
            "artifact_root_name": artifacts_path.name,
        },
        "custody": {
            "schema": receipt["schema"],
            "receipt_sha256": _sha(custody_receipt_raw),
            "state": receipt["custody_state"],
            "artifact_codec": receipt["state_codec"],
            "replay_state": receipt["replay_state"],
            "receiver_ack_state": receipt["receiver_ack_state"],
            "receiver_ack_authenticity": receipt["receiver_ack_authenticity"],
        },
        "model_artifacts": {
            "fixture": {
                "file": fixture["file"],
                "sha256": fixture["file_digest"],
                "descriptor_sha256": fixture["descriptor_digest"],
                "array_roles": receipt["fixture_array_roles"],
            },
            "native_state": {
                "file": state["file"],
                "sha256": receipt["native_state_digest"],
            },
            "original_prediction": {
                "file": prediction["file"],
                "sha256": prediction["file_digest"],
                "encoding": prediction["encoding"],
                "raw_array_sha256": dict(sorted(prediction["arrays"].items())),
            },
            "auxiliary": receipt["auxiliary_artifacts"],
        },
        "recipe": {
            "constructor_module": recipe["constructor_module"],
            "constructor_name": recipe["constructor_name"],
            "recipe_sha256": recipe["recipe_digest"],
            "constructor_resolution": "NOT_ATTEMPTED",
            "execution": "NOT_ATTEMPTED",
        },
        "lineage": lineage,
        "consumer": {
            "replay_evidence": "NOT_PROVIDED",
            "receiver_ack": "NOT_PROVIDED",
            "consumer_identity": None,
            "status": "PENDING_EXTERNAL_RECEIVER",
        },
    }
    identity = _canonical(core)
    return {**core, "entry_id": _sha(identity)}


def _entry_directory(value) -> Path:
    root = Path(value)
    try:
        if (
            root.is_symlink()
            or not root.is_dir()
            or root.resolve(strict=True) != root.absolute()
        ):
            raise EntryRefused("entry_directory")
    except OSError as exc:
        raise EntryRefused("entry_directory") from exc
    return root.resolve(strict=True)


def _same_existing(path: Path, expected: bytes) -> bool:
    try:
        if path.is_symlink() or not path.is_file():
            return False
        if path.stat().st_size != len(expected) or len(expected) > MAX_ENTRY_BYTES:
            return False
        with path.open("rb") as stream:
            return stream.read(MAX_ENTRY_BYTES + 1) == expected
    except OSError:
        return False


def create_entry_v2(
    manifest_path, artifacts_path, custody_receipt_path, entry_directory
) -> dict:
    """Create or idempotently return a generic pending entry; never admit it."""
    if not Path(artifacts_path).is_dir() or Path(artifacts_path).is_symlink():
        raise EntryRefused("artifact_root")
    artifacts = Path(artifacts_path).resolve(strict=True)
    manifest_file, manifest_raw = _bounded_regular_file(
        manifest_path, MAX_INPUT_JSON_BYTES, "manifest"
    )
    custody_file, custody_raw = _bounded_regular_file(
        custody_receipt_path, MAX_INPUT_JSON_BYTES, "custody_receipt"
    )
    record = _entry_record(
        manifest_file, manifest_raw, artifacts, custody_file, custody_raw
    )
    raw = _canonical(record)
    if len(raw) > MAX_ENTRY_BYTES:
        raise EntryRefused("entry_size")
    directory = _entry_directory(entry_directory)
    out = directory / (record["entry_id"].removeprefix("sha256:") + ".json")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        fd = os.open(out, flags, 0o600)
    except FileExistsError:
        if _same_existing(out, raw):
            return {
                "status": "ALREADY_PRESENT_IDENTICAL",
                "entry": record,
                "path": out.name,
            }
        raise EntryRefused("entry_exists_with_different_bytes") from None
    try:
        with os.fdopen(fd, "wb") as stream:
            if stream.write(raw) != len(raw):
                raise OSError("short entry write")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        try:
            out.unlink()
        except OSError:
            pass
        raise EntryRefused("entry_write") from exc
    return {"status": "CREATED", "entry": record, "path": out.name}


def create_entry_v3(artifacts_path, custody_receipt_path, entry_directory) -> dict:
    """Index a Challenge-bound graph's original bytes without admission or replay.

    This uses the same create-only entry directory and exact-byte idempotence as
    v2. It never imports the graph, scores predictions, or creates receiver ACK.
    """
    try:
        expected = custody.prepare_custody_v3(artifacts_path)
    except custody.CustodyRefused as exc:
        raise EntryRefused(f"custody_v3_{exc}") from exc
    receipt_file, receipt_raw = _bounded_regular_file(
        custody_receipt_path, MAX_INPUT_JSON_BYTES, "custody_receipt"
    )
    receipt = _json(receipt_raw, "custody_receipt")
    if receipt != expected:
        raise EntryRefused("custody_receipt_mismatch")
    core = {
        "schema": GRAPH_ENTRY_SCHEMA_V3,
        "source_schema": expected["source_schema"],
        "scope": expected["scope"],
        "challenge": expected["challenge"],
        "challenge_version": expected["challenge_version"],
        "interface_digest": expected["interface_digest"],
        "train_digest": expected["train_digest"],
        "source_digest": expected["source_digest"],
        "recipe_digest": expected["recipe_digest"],
        "image_digest": expected["image_digest"],
        "original_files": expected["original_files"],
        "lineage_sha256": expected["lineage_sha256"],
        "custody_receipt": {
            "file": receipt_file.name,
            "sha256": _sha(receipt_raw),
            "bytes": len(receipt_raw),
        },
        "admission_state": "NOT_ADMITTED",
        "score_state": "NOT_COMPUTED",
        "qualification_state": "NOT_CLAIMED",
        "replay_state": "PRODUCER_INFERENCE_BOUND_RECEIVER_REPLAY_NOT_ATTEMPTED",
        "receiver_ack_state": "RECEIVER_ACK_PENDING",
        "identity_authenticity": "DIGEST_BOUND_UNVERIFIED",
        "official_eligible": False,
    }
    record = {**core, "entry_id": _sha(_canonical(core))}
    body = _canonical(record)
    if len(body) > MAX_ENTRY_BYTES:
        raise EntryRefused("entry_size")
    directory = _entry_directory(entry_directory)
    out = directory / (record["entry_id"].removeprefix("sha256:") + ".json")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(out, flags, 0o600)
    except FileExistsError:
        if _same_existing(out, body):
            return {
                "status": "ALREADY_PRESENT_IDENTICAL",
                "entry": record,
                "path": out.name,
            }
        raise EntryRefused("entry_exists_with_different_bytes") from None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if stream.write(body) != len(body):
                raise OSError("short entry write")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        try:
            out.unlink()
        except OSError:
            pass
        raise EntryRefused("entry_write") from exc
    return {"status": "CREATED", "entry": record, "path": out.name}


def create_entry_v4(
    artifacts_path, role_manifest_path, custody_receipt_path, entry_directory
) -> dict:
    """Create one pending entry from the same graph custody family and role map."""
    try:
        expected = custody.prepare_custody_v4(artifacts_path, role_manifest_path)
    except custody.CustodyRefused as exc:
        raise EntryRefused(f"custody_v4_{exc}") from exc
    receipt_file, receipt_raw = _bounded_regular_file(
        custody_receipt_path, MAX_INPUT_JSON_BYTES, "custody_receipt"
    )
    if _json(receipt_raw, "custody_receipt") != expected:
        raise EntryRefused("custody_receipt_mismatch")
    core = {
        "schema": GRAPH_ENTRY_SCHEMA_V4,
        "source_schema": expected["source_schema"],
        "scope": expected["scope"],
        "challenge": expected["challenge"],
        "challenge_version": expected["challenge_version"],
        "interface_digest": expected["interface_digest"],
        "train_digest": expected["train_digest"],
        "source_digest": expected["source_digest"],
        "recipe_digest": expected["recipe_digest"],
        "image_digest": expected["image_digest"],
        "state_digest": expected["state_digest"],
        "prediction_digest": expected["prediction_digest"],
        "role_manifest_sha256": expected["role_manifest_sha256"],
        "roles": expected["roles"],
        "original_files": expected["original_files"],
        "lineage_sha256": expected["lineage_sha256"],
        "campaign_id": expected["campaign_id"],
        "task_id": expected["task_id"],
        "operations": expected["operations"],
        "evidence_state": expected["evidence_state"],
        "custody_receipt": {
            "file": receipt_file.name,
            "sha256": _sha(receipt_raw),
            "bytes": len(receipt_raw),
        },
        "admission_state": "NOT_ADMITTED",
        "score_state": "NOT_COMPUTED",
        "qualification_state": "NOT_CLAIMED",
        "replay_state": "PRODUCER_EVIDENCE_BOUND_RECEIVER_REPLAY_NOT_ATTEMPTED",
        "receiver_ack_state": "RECEIVER_ACK_PENDING",
        "identity_authenticity": "DIGEST_BOUND_UNVERIFIED",
        "official_eligible": False,
    }
    record = {**core, "entry_id": _sha(_canonical(core))}
    body = _canonical(record)
    if len(body) > MAX_ENTRY_BYTES:
        raise EntryRefused("entry_size")
    directory = _entry_directory(entry_directory)
    out = directory / (record["entry_id"].removeprefix("sha256:") + ".json")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(out, flags, 0o600)
    except FileExistsError:
        if _same_existing(out, body):
            return {
                "status": "ALREADY_PRESENT_IDENTICAL",
                "entry": record,
                "path": out.name,
            }
        raise EntryRefused("entry_exists_with_different_bytes") from None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if stream.write(body) != len(body):
                raise OSError("short entry write")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        try:
            out.unlink()
        except OSError:
            pass
        raise EntryRefused("entry_write") from exc
    return {"status": "CREATED", "entry": record, "path": out.name}


def create_entry_v5(
    artifacts_path, role_manifest_path, custody_receipt_path, entry_directory
) -> dict:
    """Create a pending common-bundle entry from its original, rehashed bytes."""
    try:
        expected = custody.prepare_custody_v5(artifacts_path, role_manifest_path)
    except custody.CustodyRefused as exc:
        raise EntryRefused(f"custody_v5_{exc}") from exc
    receipt_file, receipt_raw = _bounded_regular_file(
        custody_receipt_path, MAX_INPUT_JSON_BYTES, "custody_receipt"
    )
    if _json(receipt_raw, "custody_receipt") != expected:
        raise EntryRefused("custody_receipt_mismatch")
    core = {
        "schema": GRAPH_ENTRY_SCHEMA_V5,
        "source_schema": expected["source_schema"],
        "scope": expected["scope"],
        "challenge": expected["challenge"],
        "challenge_version": expected["challenge_version"],
        "interface_digest": expected["interface_digest"],
        "train_digest": expected["train_digest"],
        "bundle_digest": expected["bundle_digest"],
        "environment_ref_digest": expected["environment_ref_digest"],
        "source_digest": expected["source_digest"],
        "environment_digest": expected["environment_digest"],
        "image_digest": expected["image_digest"],
        "recipe_digest": expected["recipe_digest"],
        "state_digest": expected["state_digest"],
        "fixture_digest": expected["fixture_digest"],
        "fixture_evidence": expected["fixture_evidence"],
        "prediction_digest": expected["prediction_digest"],
        "prediction_evidence": expected["prediction_evidence"],
        "seed_digest": expected["seed_digest"],
        "seed_provenance": expected["seed_provenance"],
        "physics_contract": expected["physics_contract"],
        "role_manifest_sha256": expected["role_manifest_sha256"],
        "roles": expected["roles"],
        "state_members": expected["state_members"],
        "original_files": expected["original_files"],
        "provenance_state": expected["provenance_state"],
        "custody_receipt": {
            "file": receipt_file.name,
            "sha256": _sha(receipt_raw),
            "bytes": len(receipt_raw),
        },
        "admission_state": "NOT_ADMITTED",
        "score_state": "NOT_COMPUTED",
        "qualification_state": "NOT_CLAIMED",
        "replay_state": expected["replay_state"],
        "receiver_ack_state": "RECEIVER_ACK_PENDING",
        "official_eligible": False,
    }
    record = {**core, "entry_id": _sha(_canonical(core))}
    body = _canonical(record)
    if len(body) > MAX_ENTRY_BYTES:
        raise EntryRefused("entry_size")
    directory = _entry_directory(entry_directory)
    if directory.is_relative_to(Path(artifacts_path).resolve(strict=True)):
        raise EntryRefused("entry_directory_inside_original_artifacts")
    out = directory / (record["entry_id"].removeprefix("sha256:") + ".json")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(out, flags, 0o600)
    except FileExistsError:
        if _same_existing(out, body):
            return {
                "status": "ALREADY_PRESENT_IDENTICAL",
                "entry": record,
                "path": out.name,
            }
        raise EntryRefused("entry_exists_with_different_bytes") from None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if stream.write(body) != len(body):
                raise OSError("short entry write")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        try:
            out.unlink()
        except OSError:
            pass
        raise EntryRefused("entry_write") from exc
    return {"status": "CREATED", "entry": record, "path": out.name}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--bundle-roles", type=Path)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--custody-receipt", type=Path, required=True)
    parser.add_argument("--entry-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.bundle_roles is not None:
            result = create_entry_v5(
                args.artifacts,
                args.bundle_roles,
                args.custody_receipt,
                args.entry_directory,
            )
        else:
            result = create_entry_v2(
                args.manifest,
                args.artifacts,
                args.custody_receipt,
                args.entry_directory,
            )
    except EntryRefused as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "status": result["status"],
                "entry_id": result["entry"]["entry_id"],
                "path": result["path"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
