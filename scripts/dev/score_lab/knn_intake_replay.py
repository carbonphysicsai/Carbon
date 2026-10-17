#!/usr/bin/env python3
"""Verify a prospective public-TRAIN KNN saved-state replay bundle.

This is a development-only wrapper around Carbon's existing non-pickle
``recipes.model_from_bytes`` loader. It is not an integrated ScoreLab intake,
receiver ACK, scoring path, or qualification decision.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np

from carbon.battery import recipes

_RECORD_SCHEMA = "carbon.scorelab.testing-model-bank-reference.v1"
_MODEL_SCHEMA = "carbon.battery.model-state.v1"
_COMPARISON_SCHEMA = "carbon.scorelab.public-knn-receiver-replay-comparison.v1"
_EXPECTED_OUTPUTS = {"eta": "eta", "q": "q", "t": "t", "v": "v"}
_MAX_STATE_BYTES = 256 * 1024
_MAX_REPLAY_BYTES = 16 * 1024


class IntakeReplayRefused(ValueError):
    """The prospective bundle is malformed, misbound, or out of scope."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_subset(value: object) -> tuple[str, ...]:
    """Normalize producer wording without weakening the TRAIN subset identity."""
    if not isinstance(value, str):
        return ()
    return tuple(
        token
        for token in value.lower().replace("-", " ").split()
        if token != "training"
    )


def _artifact(root: Path, ref: dict) -> bytes:
    if not isinstance(ref, dict):
        raise IntakeReplayRefused("artifact reference must be an object")
    relative = ref.get("path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise IntakeReplayRefused("artifact path must be a nonempty relative path")
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise IntakeReplayRefused("artifact path escapes the intake bundle") from exc
    if not path.is_file():
        raise IntakeReplayRefused("artifact is missing or not a file")
    try:
        body = path.read_bytes()
    except OSError as exc:
        raise IntakeReplayRefused("artifact is unreadable") from exc
    if ref.get("bytes") != len(body):
        raise IntakeReplayRefused("artifact byte length mismatch")
    if ref.get("sha256") != _sha256(body):
        raise IntakeReplayRefused("artifact SHA-256 mismatch")
    return body


def verify_knn_intake_replay(
    manifest_path: str | Path, *, artifact_root: str | Path | None = None
) -> dict:
    """Reload and compare a KNN replay without fitting or accepting the intake.

    The returned report is a local verification result only. Callers must not
    turn it into a receiver ACK; Optimizer owns the separate ACK contract.
    """
    manifest_path = Path(manifest_path).resolve(strict=True)
    if not manifest_path.is_file():
        raise IntakeReplayRefused("prospective manifest path is not a file")
    root = (
        Path(artifact_root).resolve(strict=True)
        if artifact_root is not None
        else Path(__file__).resolve().parents[3]
    )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IntakeReplayRefused("prospective manifest is unreadable JSON") from exc

    if manifest.get("schema") != _RECORD_SCHEMA or manifest.get("record_revision") != 2:
        raise IntakeReplayRefused("unsupported prospective record identity")
    if manifest.get("record_role") != "PRODUCER_PROSPECTIVE_PUBLIC_TRAIN_ADDENDUM":
        raise IntakeReplayRefused("record is not a producer prospective addendum")
    if manifest.get("status") != "RECEIVER_ACK_PENDING":
        raise IntakeReplayRefused("formal receiver ACK must remain pending")

    historical = manifest.get("historical_record", {})
    parent = historical.get("parent_manifest", {})
    parent_bytes = _artifact(root, parent)
    if historical.get("status") != "INCOMPLETE":
        raise IntakeReplayRefused("historical producer disposition must remain INCOMPLETE")
    try:
        parent_manifest = json.loads(parent_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise IntakeReplayRefused("parent manifest is invalid JSON") from exc
    if parent_manifest.get("schema") != _RECORD_SCHEMA:
        raise IntakeReplayRefused("parent manifest schema mismatch")

    entry = manifest.get("entry", {})
    if entry.get("placement") != "PROSPECTIVE_OUTSIDE_FROZEN18":
        raise IntakeReplayRefused("prospective placement is required")
    if any(entry.get(flag) is not False for flag in (
        "ingested", "scored", "qualification_claimed", "frozen_18_modified",
        "score_or_truth_join_created",
    )):
        raise IntakeReplayRefused("prospective entry has a forbidden acceptance effect")
    if entry.get("training_data", {}).get("scope") != "PUBLIC_TRAIN_ONLY":
        raise IntakeReplayRefused("public TRAIN-only scope is required")
    if entry.get("training_data", {}).get("dataset_sha256") != (
        "3a7c763cca272df729268759e3062abd79e104a5c527c17314aef663944cf0e3"
    ):
        raise IntakeReplayRefused("unexpected public TRAIN identity")

    artifacts = entry.get("artifacts", {})
    state_ref = artifacts.get("native_state", {})
    if state_ref.get("schema") != _MODEL_SCHEMA:
        raise IntakeReplayRefused("unsupported native KNN state schema")
    state_bytes = _artifact(root, state_ref)
    if len(state_bytes) > _MAX_STATE_BYTES:
        raise IntakeReplayRefused("KNN state exceeds the bounded intake size")
    producer_sidecar_bytes = _artifact(root, artifacts.get("producer_lineage", {}))
    try:
        producer_sidecar = json.loads(producer_sidecar_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise IntakeReplayRefused("producer sidecar is invalid JSON") from exc
    parent_knn = parent_manifest.get("additional_testing_model", {})
    parent_state = parent_knn.get("native_model_state", {})
    if parent_knn.get("model_id") != entry.get("model_id"):
        raise IntakeReplayRefused("parent manifest model identity mismatch")
    if parent_state.get("sha256") != _sha256(state_bytes):
        raise IntakeReplayRefused("parent manifest is bound to a different KNN state")
    if producer_sidecar.get("schema") != "carbon.packets2.public-test-model-retention-smoke.v1":
        raise IntakeReplayRefused("unsupported producer-sidecar schema")
    if producer_sidecar.get("native_model_state", {}).get("sha256") != (
        "sha256:" + _sha256(state_bytes)
    ):
        raise IntakeReplayRefused("producer sidecar is bound to a different KNN state")
    train = entry.get("training_data", {})
    if producer_sidecar.get("public_data", {}).get("source_sha256") != (
        "sha256:" + train.get("dataset_sha256", "")
    ):
        raise IntakeReplayRefused("producer sidecar is bound to a different public TRAIN set")
    recipe = entry.get("recipe", {})
    sidecar_recipe = producer_sidecar.get("recipe", {})
    recipe_digest = recipe.get("recipe_digest")
    if sidecar_recipe.get("family") != recipe.get("family") or producer_sidecar.get(
        "recipe_digest"
    ) not in {recipe_digest, "sha256:" + str(recipe_digest)}:
        raise IntakeReplayRefused("producer sidecar recipe identity mismatch")
    producer_subset = producer_sidecar.get("public_data", {}).get("subset")
    if (
        _canonical_subset(producer_subset) != _canonical_subset(train.get("subset"))
        or not _canonical_subset(train.get("subset"))
    ):
        raise IntakeReplayRefused("producer sidecar TRAIN subset mismatch")
    if producer_sidecar.get("public_data", {}).get("seed") != train.get("public_seed"):
        raise IntakeReplayRefused("producer sidecar public TRAIN seed mismatch")
    if train.get("rows") != 32:
        raise IntakeReplayRefused("expected bounded 32-row public TRAIN subset")
    replay = artifacts.get("prospective_saved_state_replay", {})
    if replay.get("kind") != "NEW_REPLAY_NOT_HISTORICAL_PRODUCER_OUTPUT":
        raise IntakeReplayRefused("replay must be marked prospective")
    fixture_bytes = _artifact(root, replay.get("fixture", {}))
    if len(fixture_bytes) > _MAX_REPLAY_BYTES:
        raise IntakeReplayRefused("replay fixture exceeds the bounded intake size")
    replay_sidecar_bytes = _artifact(root, replay.get("lineage", {}))

    evidence = entry.get("receiver_evidence", {})
    if evidence.get("formal_receiver_ack") != "PENDING_OPTIMIZER_IMPLEMENTATION":
        raise IntakeReplayRefused("receiver ACK is owned separately by Optimizer")
    if evidence.get("integrated_intake_acceptance") is not False:
        raise IntakeReplayRefused("integrated intake acceptance must remain false")
    comparison_bytes = _artifact(root, evidence.get("replay_comparison", {}))
    comparison = json.loads(comparison_bytes.decode("utf-8"))
    if comparison.get("schema") != _COMPARISON_SCHEMA:
        raise IntakeReplayRefused("unsupported receiver comparison record")
    if comparison.get("original_intake_manifest_sha256") != _sha256(parent_bytes):
        raise IntakeReplayRefused("comparison is bound to a different parent manifest")
    if comparison.get("producer_replay_fixture_sha256") != _sha256(fixture_bytes):
        raise IntakeReplayRefused("comparison is bound to a different replay fixture")
    if comparison.get("producer_replay_sidecar_sha256") != _sha256(replay_sidecar_bytes):
        raise IntakeReplayRefused("comparison is bound to a different replay sidecar")
    if comparison.get("receiver_copy_state_sha256") != _sha256(state_bytes):
        raise IntakeReplayRefused("comparison is bound to a different saved state")
    if comparison.get("disposition") != "RECEIVER_VERIFIED_PROSPECTIVE_PUBLIC_TRAIN_REPLAY":
        raise IntakeReplayRefused("receiver comparison disposition is not the expected replay result")
    if comparison.get("array_names") != ["eta", "input", "q", "t", "v"]:
        raise IntakeReplayRefused("receiver comparison array inventory mismatch")
    if comparison.get("historical_original_output_recovered") is not False:
        raise IntakeReplayRefused("historical output must remain unrecovered")
    if any(comparison.get(flag) is not False for flag in (
        "ingested", "scored", "qualification_claimed",
    )):
        raise IntakeReplayRefused("receiver comparison has a forbidden acceptance effect")

    receiver_check_bytes = _artifact(root, evidence.get("receiver_check", {}))
    receiver_check = json.loads(receiver_check_bytes.decode("utf-8"))
    if receiver_check.get("manifest_sha256") != _sha256(parent_bytes):
        raise IntakeReplayRefused("receiver check is bound to a different parent manifest")
    if receiver_check.get("disposition") != (
        "INCOMPLETE_RECEIVER_RELOAD_PASS_PRODUCER_COMPARISON_MISSING"
    ):
        raise IntakeReplayRefused("historical receiver check must remain incomplete")
    if any(receiver_check.get(flag) is not False for flag in (
        "ingested", "scored", "qualification_claimed",
    )):
        raise IntakeReplayRefused("historical receiver check has a forbidden acceptance effect")

    try:
        with np.load(io.BytesIO(fixture_bytes), allow_pickle=False) as fixture:
            arrays = {name: fixture[name] for name in fixture.files}
    except (OSError, ValueError, KeyError) as exc:
        raise IntakeReplayRefused("replay fixture is not a safe numeric NPZ") from exc
    sidecar = json.loads(replay_sidecar_bytes.decode("utf-8"))
    if sidecar.get("kind") != "NEW_REPLAY_NOT_HISTORICAL_PRODUCER_OUTPUT":
        raise IntakeReplayRefused("replay sidecar must declare prospective replay")
    if sidecar.get("state_sha256") != _sha256(state_bytes):
        raise IntakeReplayRefused("replay sidecar is bound to a different state")
    if sidecar.get("fixture_archive", {}).get("sha256") != _sha256(fixture_bytes):
        raise IntakeReplayRefused("replay sidecar is bound to a different fixture")
    if sidecar.get("public_train_sha256") != train.get("dataset_sha256"):
        raise IntakeReplayRefused("replay sidecar is bound to a different public TRAIN set")
    source = entry.get("source", {})
    if sidecar.get("source_commit") != source.get("commit"):
        raise IntakeReplayRefused("replay sidecar source commit mismatch")
    if sidecar.get("source_recipes_git_blob") != source.get("recipes_git_blob"):
        raise IntakeReplayRefused("replay sidecar recipe source mismatch")
    for name, array in arrays.items():
        declared = sidecar.get("fixture", {}).get(name)
        if declared is None:
            raise IntakeReplayRefused(f"fixture array {name!r} is not declared")
        if declared.get("dtype") != str(array.dtype) or declared.get("shape") != list(array.shape):
            raise IntakeReplayRefused(f"fixture array {name!r} dtype or shape mismatch")
        if declared.get("sha256") != _sha256(np.ascontiguousarray(array).tobytes()):
            raise IntakeReplayRefused(f"fixture array {name!r} digest mismatch")
    if set(arrays) != {"input", "eta", "q", "t", "v"}:
        raise IntakeReplayRefused("replay fixture must contain exactly input, eta, q, t, v")

    model = recipes.model_from_bytes(state_bytes)
    if type(model) is not recipes.KNN:
        raise IntakeReplayRefused("saved state did not load as the declared KNN")
    if model.k != recipe.get("neighbours") or model.fraction != recipe.get("train_fraction"):
        raise IntakeReplayRefused("loaded KNN settings differ from the registered recipe")
    input_array = arrays["input"]
    if input_array.dtype != np.dtype("float64") or input_array.ndim != 2:
        raise IntakeReplayRefused("replay input must be a float64 matrix")
    output = model.predict(input_array)
    actual = {name: np.asarray(output[name]) for name in _EXPECTED_OUTPUTS}
    compared = {}
    for actual_name, expected_name in _EXPECTED_OUTPUTS.items():
        got, expected = actual[actual_name], arrays[expected_name]
        if got.dtype != expected.dtype or got.shape != expected.shape:
            raise IntakeReplayRefused(f"replay output {actual_name!r} dtype/shape mismatch")
        if not np.array_equal(got, expected):
            raise IntakeReplayRefused(f"replay output {actual_name!r} differs from fixture")
        compared[actual_name] = {
            "dtype": str(got.dtype),
            "shape": list(got.shape),
            "sha256": _sha256(np.ascontiguousarray(got).tobytes()),
        }

    return {
        "disposition": "LOCAL_PROSPECTIVE_REPLAY_CHECK_ONLY",
        "state_sha256": _sha256(state_bytes),
        "parent_manifest_sha256": _sha256(parent_bytes),
        "replay_fixture_sha256": _sha256(fixture_bytes),
        "outputs": compared,
        "historical_original_output_recovered": False,
        "receiver_ack_pending": True,
        "integrated_intake_acceptance": False,
        "ingested": False,
        "scored": False,
        "qualification_claimed": False,
        "placement": "PROSPECTIVE_OUTSIDE_FROZEN18",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="repository/public artifact root (default: Carbon repository root)",
    )
    args = parser.parse_args(argv)
    try:
        report = verify_knn_intake_replay(args.manifest, artifact_root=args.artifact_root)
    except (IntakeReplayRefused, OSError) as exc:
        print(json.dumps({"disposition": "REFUSED", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
