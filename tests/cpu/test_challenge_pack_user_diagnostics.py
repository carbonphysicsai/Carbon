"""Operator workflow and safe diagnostics for one pinned Challenge data pack."""

import hashlib
import json
import os

import pytest

from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    EvaluationPackUnavailable,
    freeze_pack,
    load_pack,
)

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="real artifact reads require POSIX descriptor-relative I/O"
)


def _digest(payload):
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _pack():
    return {
        "schema": SCHEMA,
        "challenge": {"id": "operator-fixture", "version": "1"},
        "pack_version": "1",
        "public": {role: "HUMAN_INPUT" for role in PUBLIC_ROLES},
        "private": {role: "HUMAN_INPUT" for role in PRIVATE_ROLES},
    }


def _write_manifest(private_root, document):
    path = private_root / "operator-fixture" / "evaluation-pack.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(document, sort_keys=True).encode("utf-8"))
    return "operator-fixture/evaluation-pack.json"


def _freeze(private_root, relative_path):
    return freeze_pack(
        private_root,
        relative_path,
        challenge_id="operator-fixture",
        challenge_version="1",
    )


def _load(private_root, relative_path, digest):
    return load_pack(
        private_root,
        relative_path,
        expected_digest=digest,
        challenge_id="operator-fixture",
        challenge_version="1",
    )


def test_operator_edits_one_manifest_and_freezes_each_prospective_version(tmp_path):
    public_root = tmp_path / "public"
    private_root = tmp_path / "private"
    public_root.mkdir()
    private_root.mkdir()
    interface = b'{"input":"fixture"}'
    reference = b'{"sealed_answer":"private-fixture"}'
    (public_root / "interface.json").write_bytes(interface)
    (private_root / "sealed-reference.json").write_bytes(reference)
    document = _pack()
    document["public"]["interface"] = {
        "path": "interface.json",
        "sha256": _digest(interface),
    }
    document["private"]["reference_rows"] = {
        "path": "sealed-reference.json",
        "sha256": _digest(reference),
    }
    relative_path = _write_manifest(private_root, document)

    admitted = _freeze(private_root, relative_path)
    run = _load(private_root, relative_path, admitted.manifest_digest)
    assert run.manifest_digest == admitted.manifest_digest
    missing = run.verify_available(public_root, private_root)
    assert "interface" not in missing["public"]
    assert "reference_rows" not in missing["private"]
    assert "train" in missing["public"]
    assert "score_pack" in missing["private"]
    assert (
        run.read_role(public_root, "public", "interface", max_bytes=1024) == interface
    )
    assert (
        run.read_role(private_root, "private", "reference_rows", max_bytes=1024)
        == reference
    )
    projection = json.dumps(run.public_projection(), sort_keys=True)
    assert "interface" in projection
    assert "sealed-reference" not in projection
    assert "private-fixture" not in projection
    assert _digest(reference) not in projection
    assert admitted.manifest_digest not in projection

    document["pack_version"] = "2"
    _write_manifest(private_root, document)
    with pytest.raises(EvaluationPackUnavailable) as refusal:
        _load(private_root, relative_path, admitted.manifest_digest)
    assert refusal.value.code == "evaluation_pack.artifact.digest_mismatch"
    prospective = _freeze(private_root, relative_path)
    assert prospective.manifest_digest != admitted.manifest_digest
    assert prospective.pack_version == "2"
    assert admitted.pack_version == "1"


def test_operator_gets_typed_missing_changed_and_unfilled_role_feedback(tmp_path):
    public_root = tmp_path / "public"
    private_root = tmp_path / "private"
    public_root.mkdir()
    private_root.mkdir()
    expected = b"synthetic solver evidence"
    document = _pack()
    document["private"]["solver_evidence"] = {
        "path": "solver-evidence.json",
        "sha256": _digest(expected),
    }
    relative_path = _write_manifest(private_root, document)
    snapshot = _freeze(private_root, relative_path)
    with pytest.raises(EvaluationPackUnavailable) as refusal:
        snapshot.verify_available(public_root, private_root)
    assert refusal.value.code == "evaluation_pack.artifact.missing"

    evidence_path = private_root / "solver-evidence.json"
    evidence_path.write_bytes(b"wrong bytes")
    with pytest.raises(EvaluationPackUnavailable) as refusal:
        snapshot.verify_available(public_root, private_root)
    assert refusal.value.code == "evaluation_pack.artifact.digest_mismatch"

    evidence_path.write_bytes(expected)
    missing = snapshot.verify_available(public_root, private_root)
    assert "solver_evidence" not in missing["private"]
    assert "case_bank" in missing["private"]
    with pytest.raises(EvaluationPackUnavailable) as refusal:
        snapshot.read_role(private_root, "private", "score_pack", max_bytes=1024)
    assert refusal.value.code == "evaluation_pack.role_unavailable"

    evidence_path.write_bytes(b"edited after admission")
    with pytest.raises(EvaluationPackUnavailable) as refusal:
        snapshot.read_role(private_root, "private", "solver_evidence", max_bytes=1024)
    assert refusal.value.code == "evaluation_pack.artifact.digest_mismatch"
    assert _load(
        private_root, relative_path, snapshot.manifest_digest
    ).manifest_digest == (snapshot.manifest_digest)
