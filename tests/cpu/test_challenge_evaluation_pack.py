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
    prepare_pack,
)
from carbon.challenge_validator.hidden_batch_store import references_digest
from carbon.challenge_validator.interface import digest as document_digest
from carbon.registry.digest import ArtifactAccessError


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


def test_excessive_json_nesting_is_a_typed_refusal():
    payload = b"[" * 1200 + b"0" + b"]" * 1200
    with pytest.raises(EvaluationPackUnavailable) as raised:
        parse_pack(
            payload,
            expected_digest=_digest(payload),
            challenge_id="test-challenge",
            challenge_version="1.0",
        )
    assert raised.value.code == "evaluation_pack.json"


def test_excessive_json_integer_is_a_typed_refusal():
    payload = b'{"n":' + b"9" * 5000 + b"}"
    with pytest.raises(EvaluationPackUnavailable) as raised:
        parse_pack(
            payload,
            expected_digest=_digest(payload),
            challenge_id="test-challenge",
            challenge_version="1.0",
        )
    assert raised.value.code == "evaluation_pack.json"


@pytest.mark.parametrize(
    "payload,code",
    [
        (b'{"x":1,"x":2}', "evaluation_pack.duplicate_key"),
        (b'{"x":NaN}', "evaluation_pack.nonfinite"),
        (b"[" * 1200 + b"0" + b"]" * 1200, "evaluation_pack.json"),
    ],
)
def test_verified_json_role_reuses_typed_parser(payload, code):
    document = _manifest()
    document["public"]["interface"] = {
        "path": "interface.json",
        "sha256": _digest(payload),
    }
    snapshot = _parse(document)
    with (
        patch(
            "carbon.challenge_validator.evaluation_pack.read_verified_artifact_bytes",
            return_value=payload,
        ) as reader,
        pytest.raises(EvaluationPackUnavailable) as raised,
    ):
        snapshot.read_json_role(Path("/public"), "public", "interface", max_bytes=4096)
    assert raised.value.code == code
    reader.assert_called_once_with(
        Path("/public"), "interface.json", _digest(payload), max_bytes=4096
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
    with (
        patch(
            "carbon.challenge_validator.evaluation_pack.read_verified_artifact_bytes",
            side_effect=ArtifactAccessError("artifact.digest_mismatch", "changed"),
        ),
        pytest.raises(EvaluationPackUnavailable) as raised,
    ):
        snapshot.read_role(Path("/private"), "private", "reference_rows", max_bytes=100)
    assert raised.value.code == "evaluation_pack.artifact.digest_mismatch"


def test_existing_hidden_batch_is_bound_without_copying_database():
    document = {
        "schema": "test",
        "challenge": {"id": "test-challenge", "version": "1.0"},
        "cases": [{"case_id": "sealed-1"}],
    }
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

    other = {**document, "challenge": {"id": "other", "version": "1.0"}}

    class CrossChallengeStore(Store):
        def batch(self, selected):
            return {**super().batch(selected), "document": other}

    with pytest.raises(EvaluationPackUnavailable) as raised:
        snapshot.resolve_hidden_batch(CrossChallengeStore())
    assert raised.value.code == "evaluation_pack.bank_changed"

    dynamic_manifest = _manifest()
    dynamic_manifest["private"]["case_bank"] = {"kind": "hidden_batch_store"}
    dynamic = _parse(dynamic_manifest)
    assert dynamic.run_bindings_required() == ("case_bank",)
    with pytest.raises(EvaluationPackUnavailable) as raised:
        dynamic.resolve_hidden_batch(Store())
    assert raised.value.code == "evaluation_pack.bank_run_pin"
    assert (
        dynamic.resolve_hidden_batch(
            Store(), fingerprint=fingerprint, expected_references_digest=ref_digest
        )["references"]
        == references
    )


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
    with (
        patch(
            "carbon.challenge_validator.evaluation_pack.digest_artifact",
            return_value=_digest(b"changed"),
        ),
        pytest.raises(EvaluationPackUnavailable) as raised,
    ):
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


def test_operator_draft_auto_pins_artifacts_into_separate_frozen_bytes():
    draft = _manifest()
    draft["public"]["interface"] = {"path": "interface.json"}
    draft_bytes = json.dumps(draft, sort_keys=True).encode()

    def digester(root, path):
        if path == "test-challenge/evaluation-pack.json":
            return _digest(draft_bytes)
        assert root == Path("/public") and path == "interface.json"
        return _digest(b"interface v1")

    with (
        patch(
            "carbon.challenge_validator.evaluation_pack.digest_artifact",
            side_effect=digester,
        ),
        patch(
            "carbon.challenge_validator.evaluation_pack.read_verified_artifact_bytes",
            return_value=draft_bytes,
        ),
    ):
        prepared = prepare_pack(
            Path("/private"),
            "test-challenge/evaluation-pack.json",
            public_root=Path("/public"),
            private_root=Path("/private"),
            challenge_id="test-challenge",
            challenge_version="1.0",
        )
    assert prepared.draft_digest == _digest(draft_bytes)
    assert prepared.snapshot.manifest_digest == _digest(prepared.sealed_bytes)
    assert prepared.snapshot.public["interface"]["sha256"] == _digest(b"interface v1")
    assert draft["public"]["interface"] == {"path": "interface.json"}
    assert prepared.snapshot.missing_roles()["private"] == tuple(sorted(PRIVATE_ROLES))

    new_bytes = json.dumps({**draft, "pack_version": "2"}, sort_keys=True).encode()
    assert _digest(new_bytes) != prepared.draft_digest
    assert _digest(prepared.sealed_bytes) == prepared.snapshot.manifest_digest


def test_small_challenge_rules_can_be_edited_inline_without_manual_hashes():
    draft = _manifest()
    draft["public"]["interface"] = {
        "inline": {
            "inputs": [{"name": "temperature", "unit": "K"}],
            "outputs": [{"name": "heat_flux", "unit": "W/m2"}],
        }
    }
    draft_bytes = json.dumps(draft, sort_keys=True).encode()
    with (
        patch(
            "carbon.challenge_validator.evaluation_pack.digest_artifact",
            return_value=_digest(draft_bytes),
        ),
        patch(
            "carbon.challenge_validator.evaluation_pack.read_verified_artifact_bytes",
            return_value=draft_bytes,
        ),
    ):
        prepared = prepare_pack(
            Path("/private"),
            "test-challenge/evaluation-pack.json",
            public_root=Path("/public"),
            private_root=Path("/private"),
            challenge_id="test-challenge",
            challenge_version="1.0",
        )
    interface = prepared.snapshot.read_role(
        Path("unused"), "public", "interface", max_bytes=1000
    )
    assert json.loads(interface)["outputs"][0]["unit"] == "W/m2"
    with pytest.raises(EvaluationPackUnavailable) as raised:
        prepared.snapshot.read_role(
            Path("unused"), "private", "score_pack", max_bytes=1000
        )
    assert raised.value.code == "evaluation_pack.role_unavailable"
    with pytest.raises(EvaluationPackUnavailable) as raised:
        prepared.snapshot.read_role(Path("unused"), "public", "interface", max_bytes=1)
    assert raised.value.code == "evaluation_pack.artifact.too_large"
    draft["public"]["interface"]["inline"]["outputs"][0]["unit"] = "wrong"
    assert (
        json.loads(
            prepared.snapshot.read_role(
                Path("unused"), "public", "interface", max_bytes=1000
            )
        )["outputs"][0]["unit"]
        == "W/m2"
    )

    sealed = json.loads(prepared.sealed_bytes)
    sealed["public"]["interface"]["inline"]["outputs"][0]["unit"] = "wrong"
    with pytest.raises(
        EvaluationPackUnavailable, match="evaluation_pack.inline_digest"
    ):
        _parse(sealed)


def test_hidden_reference_rows_cannot_be_embedded_in_manifest():
    document = _manifest()
    document["private"]["reference_rows"] = {
        "inline": {"secret_answer": 7},
        "sha256": _digest(b"secret"),
    }
    with pytest.raises(EvaluationPackUnavailable, match="evaluation_pack.inline_entry"):
        _parse(document)
    document["private"]["reference_rows"] = UNAVAILABLE
    document["private"]["score_pack"] = {
        "inline": {"schema": "fixture"},
        "sha256": _digest(b"x"),
    }
    with pytest.raises(EvaluationPackUnavailable, match="evaluation_pack.inline_entry"):
        _parse(document)
