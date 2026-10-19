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
    load_pack,
    prepare_pack,
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


def _prepare(private_root, relative_path, public_root):
    return prepare_pack(
        private_root,
        relative_path,
        public_root=public_root,
        private_root=private_root,
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
    document["public"]["interface"] = {"path": "interface.json"}
    document["public"]["design_objective"] = {
        "inline": {"fixture_marker": "draft-rule-v1"}
    }
    document["private"]["reference_rows"] = {"path": "sealed-reference.json"}
    draft_path = _write_manifest(private_root, document)

    prepared = _prepare(private_root, draft_path, public_root)
    admitted = prepared.snapshot
    assert prepared.draft_digest == _digest((private_root / draft_path).read_bytes())
    assert admitted.public["interface"]["sha256"] == _digest(interface)
    assert admitted.private["reference_rows"]["sha256"] == _digest(reference)
    assert admitted.public["design_objective"]["sha256"] == _digest(
        b'{"fixture_marker":"draft-rule-v1"}'
    )
    assert json.loads((private_root / draft_path).read_bytes()) == document
    sealed_path = (
        "operator-fixture/frozen/" + admitted.manifest_digest.split(":", 1)[1] + ".json"
    )
    sealed_file = private_root / sealed_path
    sealed_file.parent.mkdir(parents=True)
    sealed_file.write_bytes(prepared.sealed_bytes)
    run = _load(private_root, sealed_path, admitted.manifest_digest)
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
    assert json.loads(
        run.read_role(public_root, "public", "design_objective", max_bytes=1024)
    ) == {"fixture_marker": "draft-rule-v1"}
    projection = json.dumps(run.public_projection(), sort_keys=True)
    assert "interface" in projection
    assert "sealed-reference" not in projection
    assert "private-fixture" not in projection
    assert _digest(reference) not in projection
    assert admitted.manifest_digest not in projection

    document["pack_version"] = "2"
    document["public"]["design_objective"]["inline"]["fixture_marker"] = "draft-rule-v2"
    _write_manifest(private_root, document)
    with pytest.raises(EvaluationPackUnavailable) as refusal:
        _load(private_root, draft_path, admitted.manifest_digest)
    assert refusal.value.code == "evaluation_pack.artifact.digest_mismatch"
    old_run = _load(private_root, sealed_path, admitted.manifest_digest)
    assert old_run.pack_version == "1"
    assert json.loads(
        old_run.read_role(public_root, "public", "design_objective", max_bytes=1024)
    ) == {"fixture_marker": "draft-rule-v1"}
    prospective = _prepare(private_root, draft_path, public_root)
    assert prospective.snapshot.manifest_digest != admitted.manifest_digest
    assert prospective.snapshot.pack_version == "2"
    assert admitted.pack_version == "1"
    document["private"]["score_pack"] = {"inline": {"fixture_marker": "invalid"}}
    _write_manifest(private_root, document)
    with pytest.raises(EvaluationPackUnavailable) as refusal:
        _prepare(private_root, draft_path, public_root)
    assert refusal.value.code == "evaluation_pack.inline_entry"


def test_operator_gets_typed_missing_changed_and_unfilled_role_feedback(tmp_path):
    public_root = tmp_path / "public"
    private_root = tmp_path / "private"
    public_root.mkdir()
    private_root.mkdir()
    expected = b"synthetic solver evidence"
    document = _pack()
    document["private"]["solver_evidence"] = {"path": "solver-evidence.json"}
    relative_path = _write_manifest(private_root, document)
    with pytest.raises(EvaluationPackUnavailable) as refusal:
        _prepare(private_root, relative_path, public_root)
    assert refusal.value.code == "evaluation_pack.artifact.missing"

    evidence_path = private_root / "solver-evidence.json"
    evidence_path.write_bytes(expected)
    snapshot = _prepare(private_root, relative_path, public_root).snapshot
    assert snapshot.private["solver_evidence"]["sha256"] == _digest(expected)
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
