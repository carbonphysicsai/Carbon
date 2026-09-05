"""Strict canonical representation for B-06 Validation Dossiers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from carbon.registry.model import ChallengeKey

from .enums import (
    DossierEvidenceClass,
    DossierSlot,
    EvidenceCompleteness,
    EvidenceRequirement,
    EvidenceSectionStatus,
    SignerArtifactKind,
    SignerBindingState,
    SignerRole,
    StructuralOrigin,
)
from .errors import (
    DossierCanonicalError,
    DossierInputCode,
    DossierValidationError,
)
from .model import DossierSection, SignerBinding, ValidationDossier
from .refs import (
    DOSSIER_DOCUMENT_HEADER,
    DossierEvidenceRef,
    SignerArtifactRef,
    ValidationDossierRef,
)

MAX_DOSSIER_DOCUMENT_BYTES = 1024 * 1024


def _wrong(path: str, code: DossierInputCode = DossierInputCode.INVALID_VALUE):
    return DossierCanonicalError(code, path=path)


def _challenge_to_dict(value: ChallengeKey) -> dict[str, str]:
    return {"challenge_id": value.challenge_id, "version": value.version}


def _challenge_from_dict(value: object, path: str) -> ChallengeKey:
    fields = _object(value, {"challenge_id", "version"}, path)
    try:
        return ChallengeKey(fields["challenge_id"], fields["version"])
    except (TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _evidence_to_dict(value: DossierEvidenceRef) -> dict[str, object]:
    return {
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "evidence_class": value.evidence_class.value,
        "evidence_id": value.evidence_id,
        "evidence_version": value.evidence_version,
        "origin": value.origin.value,
        "ref_type": value.ref_type,
    }


def _evidence_from_dict(value: object, path: str) -> DossierEvidenceRef:
    fields = _object(
        value,
        {
            "challenge_key",
            "content_digest",
            "evidence_class",
            "evidence_id",
            "evidence_version",
            "origin",
            "ref_type",
        },
        path,
    )
    if fields["ref_type"] != "dossier_evidence_ref":
        raise _wrong(f"{path}/ref_type")
    try:
        return DossierEvidenceRef(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            DossierEvidenceClass(fields["evidence_class"]),
            fields["evidence_id"],
            fields["evidence_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _artifact_to_dict(value: SignerArtifactRef) -> dict[str, object]:
    return {
        "artifact_id": value.artifact_id,
        "artifact_kind": value.artifact_kind.value,
        "artifact_version": value.artifact_version,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "origin": value.origin.value,
        "ref_type": value.ref_type,
        "signer_role": value.signer_role.value,
    }


def _artifact_from_dict(value: object, path: str) -> SignerArtifactRef:
    fields = _object(
        value,
        {
            "artifact_id",
            "artifact_kind",
            "artifact_version",
            "challenge_key",
            "content_digest",
            "origin",
            "ref_type",
            "signer_role",
        },
        path,
    )
    if fields["ref_type"] != "signer_artifact_ref":
        raise _wrong(f"{path}/ref_type")
    try:
        return SignerArtifactRef(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            SignerRole(fields["signer_role"]),
            SignerArtifactKind(fields["artifact_kind"]),
            fields["artifact_id"],
            fields["artifact_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _dossier_ref_to_dict(value: ValidationDossierRef) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "dossier_id": value.dossier_id,
        "dossier_version": value.dossier_version,
        "ref_type": value.ref_type,
        "schema_version": value.schema_version,
    }


def _dossier_ref_from_dict(value: object, path: str) -> ValidationDossierRef:
    fields = _object(
        value,
        {
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "dossier_id",
            "dossier_version",
            "ref_type",
            "schema_version",
        },
        path,
    )
    if fields["ref_type"] != "validation_dossier_ref":
        raise _wrong(f"{path}/ref_type")
    try:
        return ValidationDossierRef(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            fields["dossier_id"],
            fields["dossier_version"],
            fields["content_digest"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _section_to_dict(value: DossierSection) -> dict[str, object]:
    return {
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "completeness": value.completeness.value,
        "evidence_refs": [_evidence_to_dict(ref) for ref in value.evidence_refs],
        "rationale_ref": (
            None
            if value.rationale_ref is None
            else _evidence_to_dict(value.rationale_ref)
        ),
        "requirement": value.requirement.value,
        "slot": value.slot.value,
        "status": value.status.value,
    }


def _section_from_dict(value: object, path: str) -> DossierSection:
    fields = _object(
        value,
        {
            "challenge_key",
            "completeness",
            "evidence_refs",
            "rationale_ref",
            "requirement",
            "slot",
            "status",
        },
        path,
    )
    refs = _array(fields["evidence_refs"], f"{path}/evidence_refs")
    rationale_value = fields["rationale_ref"]
    try:
        return DossierSection(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            DossierSlot(fields["slot"]),
            EvidenceRequirement(fields["requirement"]),
            EvidenceCompleteness(fields["completeness"]),
            EvidenceSectionStatus(fields["status"]),
            tuple(
                _evidence_from_dict(item, f"{path}/evidence_refs/{index}")
                for index, item in enumerate(refs)
            ),
            (
                None
                if rationale_value is None
                else _evidence_from_dict(rationale_value, f"{path}/rationale_ref")
            ),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _binding_to_dict(value: SignerBinding) -> dict[str, object]:
    return {
        "authorization_evidence_ref": (
            None
            if value.authorization_evidence_ref is None
            else _artifact_to_dict(value.authorization_evidence_ref)
        ),
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "identity_ref": (
            None
            if value.identity_ref is None
            else _artifact_to_dict(value.identity_ref)
        ),
        "signature_ref": (
            None
            if value.signature_ref is None
            else _artifact_to_dict(value.signature_ref)
        ),
        "signer_role": value.signer_role.value,
        "state": value.state.value,
    }


def _optional_artifact(value: object, path: str) -> SignerArtifactRef | None:
    return None if value is None else _artifact_from_dict(value, path)


def _binding_from_dict(value: object, path: str) -> SignerBinding:
    fields = _object(
        value,
        {
            "authorization_evidence_ref",
            "challenge_key",
            "identity_ref",
            "signature_ref",
            "signer_role",
            "state",
        },
        path,
    )
    try:
        return SignerBinding(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            SignerRole(fields["signer_role"]),
            SignerBindingState(fields["state"]),
            _optional_artifact(fields["identity_ref"], f"{path}/identity_ref"),
            _optional_artifact(fields["signature_ref"], f"{path}/signature_ref"),
            _optional_artifact(
                fields["authorization_evidence_ref"],
                f"{path}/authorization_evidence_ref",
            ),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def canonical_payload(value: ValidationDossier) -> dict[str, object]:
    if type(value) is not ValidationDossier:
        raise _wrong("/", DossierInputCode.WRONG_TYPE)
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "dossier_id": value.dossier_id,
        "dossier_version": value.dossier_version,
        "origin": value.origin.value,
        "record_type": "validation_dossier",
        "schema_version": value.schema_version,
        "sections": [_section_to_dict(section) for section in value.sections],
        "signer_bindings": [
            _binding_to_dict(binding) for binding in value.signer_bindings
        ],
        "supersedes": (
            None if value.supersedes is None else _dossier_ref_to_dict(value.supersedes)
        ),
    }


def canonical_bytes(value: ValidationDossier) -> bytes:
    try:
        payload = json.dumps(
            canonical_payload(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeError):
        raise _wrong("/") from None
    document = DOSSIER_DOCUMENT_HEADER + payload
    if len(document) > MAX_DOSSIER_DOCUMENT_BYTES:
        raise _wrong("/", DossierInputCode.SIZE_LIMIT)
    return document


def canonical_digest(value: ValidationDossier) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def dossier_ref(value: ValidationDossier) -> ValidationDossierRef:
    return ValidationDossierRef(
        value.challenge_key,
        value.dossier_id,
        value.dossier_version,
        canonical_digest(value),
        value.schema_version,
        value.canonicalization_profile,
    )


def load_canonical_document(document: bytes) -> ValidationDossier:
    if type(document) is not bytes:
        raise _wrong("/", DossierInputCode.WRONG_TYPE)
    if len(document) > MAX_DOSSIER_DOCUMENT_BYTES:
        raise _wrong("/", DossierInputCode.SIZE_LIMIT)
    if not document.startswith(DOSSIER_DOCUMENT_HEADER):
        raise _wrong("/")
    payload = document[len(DOSSIER_DOCUMENT_HEADER) :]
    try:
        decoded = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except DossierCanonicalError:
        raise
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise _wrong("/") from None
    fields = _object(
        decoded,
        {
            "canonicalization_profile",
            "challenge_key",
            "dossier_id",
            "dossier_version",
            "origin",
            "record_type",
            "schema_version",
            "sections",
            "signer_bindings",
            "supersedes",
        },
        "/",
    )
    if fields["record_type"] != "validation_dossier":
        raise _wrong("/record_type")
    sections = _array(fields["sections"], "/sections")
    bindings = _array(fields["signer_bindings"], "/signer_bindings")
    try:
        value = ValidationDossier(
            _challenge_from_dict(fields["challenge_key"], "/challenge_key"),
            fields["dossier_id"],
            fields["dossier_version"],
            tuple(
                _section_from_dict(item, f"/sections/{index}")
                for index, item in enumerate(sections)
            ),
            tuple(
                _binding_from_dict(item, f"/signer_bindings/{index}")
                for index, item in enumerate(bindings)
            ),
            StructuralOrigin(fields["origin"]),
            (
                None
                if fields["supersedes"] is None
                else _dossier_ref_from_dict(fields["supersedes"], "/supersedes")
            ),
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong("/", DossierInputCode.WRONG_TYPE) from None
    if canonical_bytes(value) != document:
        raise _wrong("/", DossierInputCode.DIGEST_MISMATCH)
    return value


def _reject_number(value: str):
    del value
    raise _wrong("/", DossierInputCode.WRONG_TYPE)


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise _wrong("/", DossierInputCode.DUPLICATE_IDENTITY)
        result[key] = value
    return result


def _object(value: object, expected: set[str], path: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise _wrong(path, DossierInputCode.WRONG_TYPE)
    if set(value) != expected:
        raise _wrong(path)
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise _wrong(path, DossierInputCode.WRONG_TYPE)
    return value


__all__ = (
    "MAX_DOSSIER_DOCUMENT_BYTES",
    "canonical_bytes",
    "canonical_digest",
    "canonical_payload",
    "dossier_ref",
    "load_canonical_document",
)
