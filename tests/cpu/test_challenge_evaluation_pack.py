"""The Challenge pack is a pinned index, never a source of inferred science."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    UNAVAILABLE,
    EvaluationPackUnavailable,
    freeze_pack,
    load_pack,
    parse_pack,
)
from carbon.registry.digest import ArtifactAccessError
from carbon.challenge_validator.interface import digest as document_digest
from carbon.challenge_validator.hidden_batch_store import references_digest


def _digest(payload):
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _manifest():
    return {
        "schema": SCHEMA,
        "challenge": {"id": "test-challenge", "version": "1.0"},
        "pack_version": "1",
        "public": {name: UNAVAILABLE for name in PUBLIC_ROLES},
        "private": {name: UNAVAILABLE for name in PRIVATE_ROLES},
    }


def _parse(document, **overrides):
    payload = json.dumps(document, sort_keys=True).encode()
    return parse_pack(
        payload,
        expected_digest=overrides.pop("expected_digest", _digest(payload)),
        challenge_id=overrides.pop("challenge_id", "test-challenge"),
        challenge_version=overrides.pop("challenge_version", "1.0"),
        **overrides,
    )


def test_private_roles_never_enter_public_projection():
    document = _manifest()
    document["public"]["interface"] = {
        "path": "public/interface.json",
        "sha256": _digest(b"interface"),
    }
    document["private"]["reference_rows"] = {
        "path": "protected/exam-reference.json",
        "sha256": _digest(b"secret reference"),
    }
    snapshot = _parse(document)
    projection = snapshot.public_projection()
    assert projection["roles"]["interface"] == {
        "status": "AVAILABLE",
        "sha256": _digest(b"interface"),
    }
    assert "private" not in projection
    assert "reference_rows" not in projection["roles"]
    assert "protected" not in json.dumps(projection)
    assert _digest(b"secret reference") not in json.dumps(projection)
    assert snapshot.private["reference_rows"]["path"] == "protected/exam-reference.json"
    with pytest.raises(TypeError):
        snapshot.private["reference_rows"]["sha256"] = _digest(b"tampered")


@pytest.mark.parametrize("changed", ["id", "version"])
def test_cross_challenge_or_version_binding_refused(changed):
    document = _manifest()
    requested = {"id": "other-challenge", "version": "2.0"}[changed]
    kwargs = {"challenge_id" if changed == "id" else "challenge_version": requested}
    with pytest.raises(EvaluationPackUnavailable, match="evaluation_pack.identity"):
        _parse(document, **kwargs)


def test_manifest_edit_requires_new_external_digest():
    document = _manifest()
    original = json.dumps(document, sort_keys=True).encode()
    document["pack_version"] = "2"
    with pytest.raises(
        EvaluationPackUnavailable, match="evaluation_pack.digest_mismatch"
    ):
        _parse(document, expected_digest=_digest(original))


def test_unavailable_reference_is_typed_and_not_zero():
    snapshot = _parse(_manifest())
    assert "reference_rows" in snapshot.missing_roles()["private"]
    with pytest.raises(EvaluationPackUnavailable) as raised:
        snapshot.read_role(Path("unused"), "private", "reference_rows", max_bytes=100)
    assert raised.value.code == "evaluation_pack.role_unavailable"


@pytest.mark.parametrize(
    "path", ["../reference.json", "/reference.json", "a\\b", "C:/x", "a//b"]
)
def test_unsafe_artifact_path_refused_at_admission(path):
    document = _manifest()
    document["private"]["reference_rows"] = {
        "path": path,
        "sha256": _digest(b"reference"),
    }
    with pytest.raises(
        EvaluationPackUnavailable, match="evaluation_pack.artifact_path"
    ):
        _parse(document)


def test_duplicate_json_key_refused():
    payload = b'{"schema":"x","schema":"y"}'
    with pytest.raises(
        EvaluationPackUnavailable, match="evaluation_pack.duplicate_key"
    ):
        parse_pack(
            payload,
            expected_digest=_digest(payload),
            challenge_id="test-challenge",
            challenge_version="1.0",
        )


def test_role_read_is_exact_byte_verified_and_infra_typed():
    document = _manifest()
    document["private"]["reference_rows"] = {
        "path": "references/rows.json",
        "sha256": _digest(b"original"),
    }
    snapshot = _parse(document)
    with patch(
        "carbon.challenge_validator.evaluation_pack.read_verified_artifact_bytes",
        return_value=b"original",
    ) as reader:
        assert (
            snapshot.read_role(
                Path("/private"), "private", "reference_rows", max_bytes=100
            )
            == b"original"
        )
        reader.assert_called_once_with(
            Path("/private"),
            "references/rows.json",
            _digest(b"original"),
            max_bytes=100,
        )
    with patch(
        "carbon.challenge_validator.evaluation_pack.read_verified_artifact_bytes",
        side_effect=ArtifactAccessError("artifact.digest_mismatch", "changed"),
    ):
        with pytest.raises(EvaluationPackUnavailable) as raised:
            snapshot.read_role(
                Path("/private"), "private", "reference_rows", max_bytes=100
            )
    assert raised.value.code == "evaluation_pack.artifact.digest_mismatch"


def test_existing_hidden_batch_is_bound_without_copying_database():
    document = {"schema": "test", "cases": [{"case_id": "sealed-1"}]}
    references = {"sealed-1": {"status": "OK", "value": 3}}
    fingerprint = document_digest(document)
    ref_digest = references_digest(references)
    manifest = _manifest()
    manifest["private"]["case_bank"] = {
        "kind": "hidden_batch_store",
        "fingerprint": fingerprint,
        "references_digest": ref_digest,
    }
    snapshot = _parse(manifest)

    class Store:
        def batch(self, selected):
            assert selected == fingerprint
            return {
                "state": "COMPLETE",
                "document": document,
                "references_digest": ref_digest,
            }

        def references(self, selected):
            assert selected == fingerprint
            return references

    assert snapshot.resolve_hidden_batch(Store()) == {
        "document": document,
        "references": references,
    }
    with pytest.raises(EvaluationPackUnavailable) as raised:
        snapshot.read_role(Path("unused"), "private", "case_bank", max_bytes=100)
    assert raised.value.code == "evaluation_pack.role_requires_store"

    class ChangedStore(Store):
        def references(self, selected):
            return {"sealed-1": {"status": "OK", "value": 4}}

    with pytest.raises(EvaluationPackUnavailable) as raised:
        snapshot.resolve_hidden_batch(ChangedStore())
    assert raised.value.code == "evaluation_pack.bank_changed"


def test_admission_verifies_available_artifact_identity_and_reports_missing():
    document = _manifest()
    document["public"]["interface"] = {
        "path": "public/interface.json",
        "sha256": _digest(b"interface"),
    }
    snapshot = _parse(document)
    with patch(
        "carbon.challenge_validator.evaluation_pack.digest_artifact",
        return_value=_digest(b"interface"),
    ) as digester:
        missing = snapshot.verify_available(Path("/public"), Path("/private"))
    digester.assert_called_once_with(Path("/public"), "public/interface.json")
    assert "interface" not in missing["public"]
    assert "reference_rows" in missing["private"]
    with patch(
        "carbon.challenge_validator.evaluation_pack.digest_artifact",
        return_value=_digest(b"changed"),
    ):
        with pytest.raises(EvaluationPackUnavailable) as raised:
            snapshot.verify_available(Path("/public"), Path("/private"))
    assert raised.value.code == "evaluation_pack.artifact.digest_mismatch"


def test_loader_uses_external_pin_and_existing_safe_reader():
    payload = json.dumps(_manifest(), sort_keys=True).encode()
    with patch(
        "carbon.challenge_validator.evaluation_pack.read_verified_artifact_bytes",
        return_value=payload,
    ) as reader:
        snapshot = load_pack(
            Path("/private"),
            "test-challenge/pack.json",
            expected_digest=_digest(payload),
            challenge_id="test-challenge",
            challenge_version="1.0",
        )
    assert snapshot.manifest_digest == _digest(payload)
    reader.assert_called_once_with(
        Path("/private"),
        "test-challenge/pack.json",
        _digest(payload),
        max_bytes=64 * 1024,
    )


def test_trusted_freeze_computes_pin_then_uses_same_verified_loader():
    payload = json.dumps(_manifest(), sort_keys=True).encode()
    with (
        patch(
            "carbon.challenge_validator.evaluation_pack.digest_artifact",
            return_value=_digest(payload),
        ) as digester,
        patch(
            "carbon.challenge_validator.evaluation_pack.read_verified_artifact_bytes",
            return_value=payload,
        ),
    ):
        snapshot = freeze_pack(
            Path("/private"),
            "test-challenge/pack.json",
            challenge_id="test-challenge",
            challenge_version="1.0",
        )
    digester.assert_called_once_with(Path("/private"), "test-challenge/pack.json")
    assert snapshot.manifest_digest == _digest(payload)
