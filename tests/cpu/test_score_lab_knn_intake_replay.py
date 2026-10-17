#!/usr/bin/env python3
"""Safe prospective KNN intake replay; synthetic data only, no solver/score."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import recipes
from carbon.battery.domain import TrainingData
from carbon.battery.recipes import Structure
from scripts.dev.score_lab import model_entry_admission
from scripts.dev.score_lab.__main__ import main as score_lab_main

ROOT = Path(__file__).resolve().parents[2]
INTAKE_PATH = ROOT / "scripts/dev/score_lab/knn_intake_replay.py"
INTAKE_SPEC = importlib.util.spec_from_file_location("scorelab_knn_intake_replay", INTAKE_PATH)
assert INTAKE_SPEC is not None and INTAKE_SPEC.loader is not None
intake = importlib.util.module_from_spec(INTAKE_SPEC)
INTAKE_SPEC.loader.exec_module(intake)


RECORD = (
    ROOT
    / "docs/development/scorelab/model-intake/knn-public-train-replay-2026-10-17"
    / "prospective-intake-v2.json"
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_artifact(root: Path, name: str, body: bytes) -> dict:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {"path": name, "sha256": _sha(body), "bytes": len(body)}


def _synthetic_bundle(tmp_path: Path) -> tuple[Path, Path]:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    x = np.asarray(
        [
            [0.5, 0.2, 15.0, 0.1],
            [1.0, 0.4, 20.0, 0.2],
            [1.5, 0.7, 30.0, 0.3],
            [2.0, 1.0, 35.0, 0.5],
        ],
        dtype=np.float64,
    )
    training = TrainingData(
        x=x,
        v=np.tile(np.linspace(3.6, 4.1, 5), (4, 1)),
        t=np.tile(np.linspace(20.0, 24.0, 5), (4, 1)),
        eta=np.asarray([0.01, 0.02, 0.03, 0.04]),
        q=np.tile(np.asarray([3.0, 2.9]), (4, 1)),
        case_ids=("synthetic-1", "synthetic-2", "synthetic-3", "synthetic-4"),
        important=np.zeros(4, dtype=bool),
    )
    model = recipes.KNN(neighbours=2)
    model.fit(training, Structure(np.asarray([0.0, 1.0]), np.asarray([3.0, 4.2])), 11)
    state = recipes.state_bytes(model)
    outputs = model.predict(x)

    arrays = {
        "input": x,
        "eta": np.asarray(outputs["eta"], dtype="<f8"),
        "q": np.asarray(outputs["q"], dtype="<f8"),
        "t": np.asarray(outputs["t"], dtype="<f8"),
        "v": np.asarray(outputs["v"], dtype="<f8"),
    }
    import io

    archive = io.BytesIO()
    np.savez(archive, **arrays)
    fixture = archive.getvalue()
    state_sha = _sha(state)
    train_sha = "3a7c763cca272df729268759e3062abd79e104a5c527c17314aef663944cf0e3"
    parent = {
        "schema": "carbon.scorelab.testing-model-bank-reference.v1",
        "additional_testing_model": {
            "model_id": "battery-public-train-knn-retention-smoke-20261016",
            "native_model_state": {"sha256": state_sha},
        },
    }
    parent_bytes = json.dumps(parent, sort_keys=True).encode()
    parent_ref = _write_artifact(artifact_root, "parent.json", parent_bytes)
    state_ref = _write_artifact(artifact_root, "state.npz", state)
    producer_sidecar = {
        "schema": "carbon.packets2.public-test-model-retention-smoke.v1",
        "native_model_state": {"sha256": f"sha256:{state_sha}"},
        "public_data": {
            "source_sha256": f"sha256:{train_sha}",
            "subset": "first 32 training cases",
            "seed": 11,
        },
        "recipe": {"family": "knn"},
        "recipe_digest": "sha256:7c3f0e5a46d8b0a9d1d9ac762ba4c85862ee219d46cb39a434ec927de89f55e6",
    }
    producer_sidecar_bytes = json.dumps(producer_sidecar, sort_keys=True).encode()
    producer_ref = _write_artifact(artifact_root, "producer.json", producer_sidecar_bytes)
    fixture_ref = _write_artifact(artifact_root, "replay.npz", fixture)
    array_sidecar = {
        name: {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "sha256": _sha(np.ascontiguousarray(value).tobytes()),
        }
        for name, value in arrays.items()
    }
    replay_sidecar = {
        "kind": "NEW_REPLAY_NOT_HISTORICAL_PRODUCER_OUTPUT",
        "fixture": array_sidecar,
        "fixture_archive": {"sha256": _sha(fixture)},
        "state_sha256": state_sha,
        "public_train_sha256": train_sha,
        "source_commit": "2ec54fee8bffe08d521847290982e2b147be55ba",
        "source_recipes_git_blob": "13dd0182b698551554496d59700d0a265b315d7b",
    }
    replay_sidecar_bytes = json.dumps(replay_sidecar, sort_keys=True).encode()
    replay_ref = _write_artifact(artifact_root, "replay.json", replay_sidecar_bytes)
    receiver_check = {
        "manifest_sha256": _sha(parent_bytes),
        "disposition": "INCOMPLETE_RECEIVER_RELOAD_PASS_PRODUCER_COMPARISON_MISSING",
        "ingested": False,
        "scored": False,
        "qualification_claimed": False,
    }
    receiver_check_bytes = json.dumps(receiver_check, sort_keys=True).encode()
    receiver_check_ref = _write_artifact(artifact_root, "receiver-check.json", receiver_check_bytes)
    comparison = {
        "schema": "carbon.scorelab.public-knn-receiver-replay-comparison.v1",
        "disposition": "RECEIVER_VERIFIED_PROSPECTIVE_PUBLIC_TRAIN_REPLAY",
        "array_names": ["eta", "input", "q", "t", "v"],
        "original_intake_manifest_sha256": _sha(parent_bytes),
        "producer_replay_fixture_sha256": _sha(fixture),
        "producer_replay_sidecar_sha256": _sha(replay_sidecar_bytes),
        "receiver_copy_state_sha256": state_sha,
        "historical_original_output_recovered": False,
        "ingested": False,
        "scored": False,
        "qualification_claimed": False,
    }
    comparison_bytes = json.dumps(comparison, sort_keys=True).encode()
    comparison_ref = _write_artifact(artifact_root, "comparison.json", comparison_bytes)

    manifest = json.loads(RECORD.read_text(encoding="utf-8"))
    manifest["historical_record"]["parent_manifest"] = parent_ref
    entry = manifest["entry"]
    entry["source"]["commit"] = "2ec54fee8bffe08d521847290982e2b147be55ba"
    entry["training_data"]["dataset_sha256"] = train_sha
    entry["recipe"]["neighbours"] = 2
    entry["recipe"]["strategy"]["parameters"]["neighbours"] = 2
    entry["artifacts"]["native_state"] = {
        **state_ref,
        "schema": "carbon.battery.model-state.v1",
    }
    entry["artifacts"]["producer_lineage"] = producer_ref
    entry["artifacts"]["prospective_saved_state_replay"]["fixture"] = fixture_ref
    entry["artifacts"]["prospective_saved_state_replay"]["lineage"] = replay_ref
    entry["receiver_evidence"]["receiver_check"] = receiver_check_ref
    entry["receiver_evidence"]["replay_comparison"] = comparison_ref
    manifest_path = tmp_path / "prospective.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return manifest_path, artifact_root


def test_prospective_replay_uses_existing_safe_loader_without_fit(tmp_path, monkeypatch):
    manifest, artifact_root = _synthetic_bundle(tmp_path)

    def forbidden_fit(*_args, **_kwargs):
        raise AssertionError("replay intake must never fit or refit")

    monkeypatch.setattr(recipes.KNN, "fit", forbidden_fit)
    report = intake.verify_knn_intake_replay(manifest, artifact_root=artifact_root)
    assert report["disposition"] == "LOCAL_PROSPECTIVE_REPLAY_CHECK_ONLY"
    assert report["receiver_ack_pending"] is True
    assert report["integrated_intake_acceptance"] is False
    assert report["placement"] == "PROSPECTIVE_OUTSIDE_FROZEN18"
    assert report["historical_original_output_recovered"] is False
    assert set(report["outputs"]) == {"eta", "q", "t", "v"}


def test_receiver_admission_writes_content_bound_create_only_receipt(tmp_path, monkeypatch):
    manifest, artifact_root = _synthetic_bundle(tmp_path)
    original_manifest = manifest.read_bytes()
    receipt_path = tmp_path / "receiver" / "prospective-entry.json"

    def forbidden_fit(*_args, **_kwargs):
        raise AssertionError("receiver admission must not fit or refit")

    monkeypatch.setattr(recipes.KNN, "fit", forbidden_fit)
    first = model_entry_admission.admit_public_train_entry(
        manifest,
        artifact_root=artifact_root,
        receipt_path=receipt_path,
    )
    receipt = first["receipt"]
    assert first["created"] is True
    assert first["status"] == "ADMITTED_PROSPECTIVE_PUBLIC_TRAIN_ENTRY"
    assert first["receipt_sha256"] == _sha(receipt_path.read_bytes())
    assert receipt["schema"] == model_entry_admission.RECEIPT_SCHEMA
    assert receipt["status"] == "ACK_PROSPECTIVE_PUBLIC_TRAIN_ENTRY"
    assert receipt["source_addendum"]["sha256"] == _sha(original_manifest)
    assert receipt["entry"]["model_id"] == (
        "battery-public-train-knn-retention-smoke-20261016"
    )
    assert receipt["entry"]["training_data"]["scope"] == "PUBLIC_TRAIN_ONLY"
    assert receipt["artifact_bindings"]["native_state"]["sha256"] == json.loads(
        original_manifest
    )["entry"]["artifacts"]["native_state"]["sha256"]
    assert receipt["receiver_replay"]["status"] == "PASS"
    assert receipt["receiver_replay"]["output_bindings"]
    assert receipt["placement"] == "PROSPECTIVE_OUTSIDE_FROZEN18"
    assert receipt["effects"] == {
        "prospective_entry_admitted": True,
        "ingested": True,
        "frozen18_modified": False,
        "scored": False,
        "score_or_truth_join_created": False,
        "qualification_claimed": False,
    }
    assert manifest.read_bytes() == original_manifest
    producer_record = json.loads(original_manifest)
    assert producer_record["entry"]["ingested"] is False
    retry = model_entry_admission.admit_public_train_entry(
        manifest,
        artifact_root=artifact_root,
        receipt_path=receipt_path,
    )
    assert retry["created"] is False
    assert retry["receipt_sha256"] == first["receipt_sha256"]


def test_receiver_admission_refuses_tamper_and_never_overwrites_receipt(tmp_path):
    manifest, artifact_root = _synthetic_bundle(tmp_path)
    state_path = artifact_root / "state.npz"
    state_path.write_bytes(state_path.read_bytes() + b"tamper")
    receipt_path = tmp_path / "receiver" / "entry.json"
    with pytest.raises(model_entry_admission.ModelEntryRefused, match="replay_refused"):
        model_entry_admission.admit_public_train_entry(
            manifest,
            artifact_root=artifact_root,
            receipt_path=receipt_path,
        )
    assert not receipt_path.exists()

    second_dir = tmp_path / "second"
    second_dir.mkdir()
    manifest, artifact_root = _synthetic_bundle(second_dir)
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text("existing", encoding="utf-8")
    with pytest.raises(
        model_entry_admission.ModelEntryRefused,
        match="receipt_exists_with_different_bytes",
    ):
        model_entry_admission.admit_public_train_entry(
            manifest,
            artifact_root=artifact_root,
            receipt_path=receipt_path,
        )
    assert receipt_path.read_text(encoding="utf-8") == "existing"


def test_score_lab_cli_admits_only_by_writing_receiver_receipt(tmp_path, capsys):
    manifest, artifact_root = _synthetic_bundle(tmp_path)
    receipt_path = tmp_path / "receiver" / "entry.json"
    code = score_lab_main(
        [
            "model-entry-admit",
            "--manifest",
            str(manifest),
            "--artifact-root",
            str(artifact_root),
            "--receipt",
            str(receipt_path),
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert result["status"] == "ADMITTED_PROSPECTIVE_PUBLIC_TRAIN_ENTRY"
    assert result["created"] is True
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["effects"]["ingested"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("unsafe_path", "escapes"),
        ("state_digest", "SHA-256"),
        ("acceptance", "forbidden acceptance effect"),
        ("historical", "INCOMPLETE"),
    ],
)
def test_prospective_replay_refuses_misbound_or_authority_changing_inputs(
    tmp_path, mutation, message
):
    manifest_path, artifact_root = _synthetic_bundle(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if mutation == "unsafe_path":
        manifest["entry"]["artifacts"]["native_state"]["path"] = "../escape.npz"
    elif mutation == "state_digest":
        manifest["entry"]["artifacts"]["native_state"]["sha256"] = "0" * 64
    elif mutation == "acceptance":
        manifest["entry"]["scored"] = True
    else:
        manifest["historical_record"]["status"] = "ACCEPTED"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(intake.IntakeReplayRefused, match=message):
        intake.verify_knn_intake_replay(manifest_path, artifact_root=artifact_root)
