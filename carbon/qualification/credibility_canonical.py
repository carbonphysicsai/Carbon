"""Deterministic canonical representation for B-E3 credibility crosswalks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.registry.model import ChallengeKey

from .credibility import (
    CREDIBILITY_CANONICALIZATION_PROFILE,
    CREDIBILITY_DOCUMENT_HEADER,
    CREDIBILITY_SCHEMA_VERSION,
    ClaimEvidenceLink,
    CredibilityCanonicalError,
    CredibilityCrosswalk,
    CredibilityCrosswalkRef,
    CredibilityEvidenceSource,
    CredibilityIssueCode,
    CredibilityRef,
    CredibilityRefKind,
    EvidenceAvailability,
    EvidenceCategory,
    EvidenceDisclosure,
    EvidenceIndependence,
    EvidenceMaturity,
    EvidenceOwnerRole,
    EvidenceSourceKind,
    HumanInputBinding,
    HumanInputDisposition,
)
from .enums import (
    ArtifactCurrentness,
    DossierClaimRole,
    DossierEvidenceClass,
    DossierSlot,
    StructuralOrigin,
)
from .refs import DossierEvidenceManifestRef, DossierEvidenceRef, ValidationDossierRef

MAX_CREDIBILITY_CROSSWALK_DOCUMENT_BYTES = 2 * 1024 * 1024


def _wrong(
    path: str, code: CredibilityIssueCode = CredibilityIssueCode.MALFORMED_DOCUMENT
):
    return CredibilityCanonicalError(code, path=path)


def _object(value: object, names: set[str], path: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != names:
        raise _wrong(path)
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise _wrong(path)
    return value


def _challenge(value: object) -> dict[str, str]:
    return {"challenge_id": value.challenge_id, "version": value.version}


def _challenge_load(value: object, path: str) -> ChallengeKey:
    fields = _object(value, {"challenge_id", "version"}, path)
    try:
        return ChallengeKey(fields["challenge_id"], fields["version"])
    except (TypeError, ValueError):
        raise _wrong(path) from None


def _evidence(value: object | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "challenge_key": _challenge(value.challenge_key),
        "content_digest": value.content_digest,
        "evidence_class": value.evidence_class.value,
        "evidence_id": value.evidence_id,
        "evidence_version": value.evidence_version,
        "origin": value.origin.value,
    }


def _evidence_load(value: object, path: str) -> DossierEvidenceRef:
    fields = _object(
        value,
        {
            "challenge_key",
            "content_digest",
            "evidence_class",
            "evidence_id",
            "evidence_version",
            "origin",
        },
        path,
    )
    try:
        return DossierEvidenceRef(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            DossierEvidenceClass(fields["evidence_class"]),
            fields["evidence_id"],
            fields["evidence_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
        )
    except (TypeError, ValueError):
        raise _wrong(path) from None


def _manifest_ref(value: object) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge(value.challenge_key),
        "content_digest": value.content_digest,
        "manifest_id": value.manifest_id,
        "manifest_version": value.manifest_version,
        "origin": value.origin.value,
        "schema_version": value.schema_version,
        "slot": value.slot.value,
    }


def _manifest_ref_load(value: object, path: str) -> DossierEvidenceManifestRef:
    fields = _object(
        value,
        {
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "manifest_id",
            "manifest_version",
            "origin",
            "schema_version",
            "slot",
        },
        path,
    )
    try:
        return DossierEvidenceManifestRef(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            DossierSlot(fields["slot"]),
            fields["manifest_id"],
            fields["manifest_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (TypeError, ValueError):
        raise _wrong(path) from None


def _dossier_ref(value: object) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge(value.challenge_key),
        "content_digest": value.content_digest,
        "dossier_id": value.dossier_id,
        "dossier_version": value.dossier_version,
        "origin": value.origin.value,
        "schema_version": value.schema_version,
    }


def _dossier_ref_load(value: object, path: str) -> ValidationDossierRef:
    fields = _object(
        value,
        {
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "dossier_id",
            "dossier_version",
            "origin",
            "schema_version",
        },
        path,
    )
    try:
        return ValidationDossierRef(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            fields["dossier_id"],
            fields["dossier_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (TypeError, ValueError):
        raise _wrong(path) from None


def _use_ref(value: CredibilityRef) -> dict[str, object]:
    return {
        "challenge_key": _challenge(value.challenge_key),
        "content_digest": value.content_digest,
        "currentness": value.currentness.value,
        "object_id": value.object_id,
        "object_version": value.object_version,
        "ref_kind": value.ref_kind.value,
    }


def _use_ref_load(value: object, path: str) -> CredibilityRef:
    fields = _object(
        value,
        {
            "challenge_key",
            "content_digest",
            "currentness",
            "object_id",
            "object_version",
            "ref_kind",
        },
        path,
    )
    try:
        return CredibilityRef(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            CredibilityRefKind(fields["ref_kind"]),
            fields["object_id"],
            fields["object_version"],
            fields["content_digest"],
            ArtifactCurrentness(fields["currentness"]),
        )
    except (TypeError, ValueError):
        raise _wrong(path) from None


def _human_input(value: HumanInputBinding) -> dict[str, object]:
    return {
        "disposition": value.disposition.value,
        "input_ref": _use_ref(value.input_ref),
    }


def _human_input_load(value: object, path: str) -> HumanInputBinding:
    fields = _object(value, {"disposition", "input_ref"}, path)
    try:
        return HumanInputBinding(
            _use_ref_load(fields["input_ref"], f"{path}/input_ref"),
            HumanInputDisposition(fields["disposition"]),
        )
    except (TypeError, ValueError):
        raise _wrong(path) from None


def _source(value: CredibilityEvidenceSource) -> dict[str, object]:
    return {
        "availability": value.availability.value,
        "category": value.category.value,
        "challenge_key": _challenge(value.challenge_key),
        "disclosure": value.disclosure.value,
        "evidence_currentness": value.evidence_currentness.value,
        "evidence_ref": _evidence(value.evidence_ref),
        "human_inputs": [_human_input(item) for item in value.human_inputs],
        "independence": value.independence.value,
        "maturity": value.maturity.value,
        "owner": value.owner.value,
        "permitted_claim_roles": [item.value for item in value.permitted_claim_roles],
        "source_id": value.source_id,
        "source_kind": value.source_kind.value,
        "source_version": value.source_version,
        "use_refs": [_use_ref(item) for item in value.use_refs],
    }


def _source_load(value: object, path: str) -> CredibilityEvidenceSource:
    fields = _object(
        value,
        {
            "availability",
            "category",
            "challenge_key",
            "disclosure",
            "evidence_currentness",
            "evidence_ref",
            "human_inputs",
            "independence",
            "maturity",
            "owner",
            "permitted_claim_roles",
            "source_id",
            "source_kind",
            "source_version",
            "use_refs",
        },
        path,
    )
    evidence_value = fields["evidence_ref"]
    evidence = (
        None
        if evidence_value is None
        else _evidence_load(evidence_value, f"{path}/evidence_ref")
    )
    try:
        return CredibilityEvidenceSource(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            fields["source_id"],
            fields["source_version"],
            EvidenceSourceKind(fields["source_kind"]),
            EvidenceCategory(fields["category"]),
            EvidenceMaturity(fields["maturity"]),
            EvidenceAvailability(fields["availability"]),
            EvidenceOwnerRole(fields["owner"]),
            EvidenceIndependence(fields["independence"]),
            EvidenceDisclosure(fields["disclosure"]),
            evidence,
            ArtifactCurrentness(fields["evidence_currentness"]),
            tuple(
                DossierClaimRole(item)
                for item in _array(
                    fields["permitted_claim_roles"], f"{path}/permitted_claim_roles"
                )
            ),
            tuple(
                _use_ref_load(item, f"{path}/use_refs/{index}")
                for index, item in enumerate(
                    _array(fields["use_refs"], f"{path}/use_refs")
                )
            ),
            tuple(
                _human_input_load(item, f"{path}/human_inputs/{index}")
                for index, item in enumerate(
                    _array(fields["human_inputs"], f"{path}/human_inputs")
                )
            ),
        )
    except (TypeError, ValueError):
        raise _wrong(path) from None


def _claim_scope(value: object) -> dict[str, object]:
    return {
        "challenge_key": _challenge(value.scope_binding.challenge_key),
        "content_digest": value.content_digest,
        "object_id": value.object_id,
        "object_version": value.object_version,
        "ref_kind": value.ref_kind,
    }


def _claim_scope_load(value: object, path: str):
    fields = _object(
        value,
        {"challenge_key", "content_digest", "object_id", "object_version", "ref_kind"},
        path,
    )
    if fields["ref_kind"] != "claim_scope":
        raise _wrong(f"{path}/ref_kind")
    try:
        return owner_ref(
            "claim_scope",
            scope_binding=ChallengeScope(
                _challenge_load(fields["challenge_key"], f"{path}/challenge_key")
            ),
            object_id=fields["object_id"],
            object_version=fields["object_version"],
            content_digest=fields["content_digest"],
        )
    except (TypeError, ValueError):
        raise _wrong(path) from None


def _link(value: ClaimEvidenceLink) -> dict[str, object]:
    return {
        "challenge_key": _challenge(value.challenge_key),
        "claim_owner": value.claim_owner.value,
        "claim_role": value.claim_role.value,
        "claim_scope_ref": _claim_scope(value.claim_scope_ref),
        "evidence_manifest_ref": _manifest_ref(value.evidence_manifest_ref),
        "evidence_ref": _evidence(value.evidence_ref),
        "slot": value.slot.value,
        "source_id": value.source_id,
        "source_version": value.source_version,
    }


def _link_load(value: object, path: str) -> ClaimEvidenceLink:
    fields = _object(
        value,
        {
            "challenge_key",
            "claim_owner",
            "claim_role",
            "claim_scope_ref",
            "evidence_manifest_ref",
            "evidence_ref",
            "slot",
            "source_id",
            "source_version",
        },
        path,
    )
    try:
        return ClaimEvidenceLink(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            DossierSlot(fields["slot"]),
            _manifest_ref_load(
                fields["evidence_manifest_ref"], f"{path}/evidence_manifest_ref"
            ),
            _claim_scope_load(fields["claim_scope_ref"], f"{path}/claim_scope_ref"),
            DossierClaimRole(fields["claim_role"]),
            EvidenceOwnerRole(fields["claim_owner"]),
            fields["source_id"],
            fields["source_version"],
            _evidence_load(fields["evidence_ref"], f"{path}/evidence_ref"),
        )
    except (TypeError, ValueError):
        raise _wrong(path) from None


def _crosswalk_ref(value: CredibilityCrosswalkRef | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge(value.challenge_key),
        "content_digest": value.content_digest,
        "crosswalk_id": value.crosswalk_id,
        "crosswalk_version": value.crosswalk_version,
        "origin": value.origin.value,
        "schema_version": value.schema_version,
    }


def _crosswalk_ref_load(value: object, path: str) -> CredibilityCrosswalkRef | None:
    if value is None:
        return None
    fields = _object(
        value,
        {
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "crosswalk_id",
            "crosswalk_version",
            "origin",
            "schema_version",
        },
        path,
    )
    try:
        return CredibilityCrosswalkRef(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            fields["crosswalk_id"],
            fields["crosswalk_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (TypeError, ValueError):
        raise _wrong(path) from None


def credibility_crosswalk_payload(value: CredibilityCrosswalk) -> dict[str, object]:
    if type(value) is not CredibilityCrosswalk:
        raise TypeError("value must be an exact CredibilityCrosswalk")
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge(value.challenge_key),
        "crosswalk_id": value.crosswalk_id,
        "crosswalk_version": value.crosswalk_version,
        "dossier_ref": _dossier_ref(value.dossier_ref),
        "evidence_manifest_refs": [
            _manifest_ref(item) for item in value.evidence_manifest_refs
        ],
        "links": [_link(item) for item in value.links],
        "origin": value.origin.value,
        "schema_version": value.schema_version,
        "sources": [_source(item) for item in value.sources],
        "supersedes": _crosswalk_ref(value.supersedes),
    }


def credibility_crosswalk_bytes(value: CredibilityCrosswalk) -> bytes:
    try:
        payload = json.dumps(
            credibility_crosswalk_payload(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeError):
        raise ValueError("credibility canonicalization failed") from None
    document = CREDIBILITY_DOCUMENT_HEADER + payload
    if len(document) > MAX_CREDIBILITY_CROSSWALK_DOCUMENT_BYTES:
        raise ValueError("credibility crosswalk exceeds canonical size limit")
    return document


def credibility_crosswalk_digest(value: CredibilityCrosswalk) -> str:
    return "sha256:" + hashlib.sha256(credibility_crosswalk_bytes(value)).hexdigest()


def credibility_crosswalk_ref(value: CredibilityCrosswalk) -> CredibilityCrosswalkRef:
    if type(value) is not CredibilityCrosswalk:
        raise TypeError("value must be an exact CredibilityCrosswalk")
    return CredibilityCrosswalkRef(
        value.challenge_key,
        value.crosswalk_id,
        value.crosswalk_version,
        credibility_crosswalk_digest(value),
        value.effective_origin,
        value.schema_version,
        value.canonicalization_profile,
    )


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise _wrong("/", CredibilityIssueCode.DUPLICATE_IDENTITY)
        result[key] = value
    return result


def _number(_: str):
    raise _wrong("/")


def load_credibility_crosswalk(document: bytes) -> CredibilityCrosswalk:
    """Load strict canonical bytes; caller-controlled documents fail closed."""
    if type(document) is not bytes:
        raise _wrong("/")
    if len(document) > MAX_CREDIBILITY_CROSSWALK_DOCUMENT_BYTES:
        raise _wrong("/", CredibilityIssueCode.SIZE_LIMIT)
    if not document.startswith(CREDIBILITY_DOCUMENT_HEADER):
        raise _wrong("/")
    try:
        payload = json.loads(
            document[len(CREDIBILITY_DOCUMENT_HEADER) :].decode(
                "utf-8", errors="strict"
            ),
            object_pairs_hook=_pairs,
            parse_int=_number,
            parse_float=_number,
            parse_constant=_number,
        )
        fields = _object(
            payload,
            {
                "canonicalization_profile",
                "challenge_key",
                "crosswalk_id",
                "crosswalk_version",
                "dossier_ref",
                "evidence_manifest_refs",
                "links",
                "origin",
                "schema_version",
                "sources",
                "supersedes",
            },
            "/",
        )
        if (
            fields["schema_version"] != CREDIBILITY_SCHEMA_VERSION
            or fields["canonicalization_profile"]
            != CREDIBILITY_CANONICALIZATION_PROFILE
        ):
            raise _wrong("/schema_version")
        value = CredibilityCrosswalk(
            _challenge_load(fields["challenge_key"], "/challenge_key"),
            fields["crosswalk_id"],
            fields["crosswalk_version"],
            _dossier_ref_load(fields["dossier_ref"], "/dossier_ref"),
            tuple(
                _manifest_ref_load(item, f"/evidence_manifest_refs/{index}")
                for index, item in enumerate(
                    _array(fields["evidence_manifest_refs"], "/evidence_manifest_refs")
                )
            ),
            tuple(
                _source_load(item, f"/sources/{index}")
                for index, item in enumerate(_array(fields["sources"], "/sources"))
            ),
            tuple(
                _link_load(item, f"/links/{index}")
                for index, item in enumerate(_array(fields["links"], "/links"))
            ),
            StructuralOrigin(fields["origin"]),
            _crosswalk_ref_load(fields["supersedes"], "/supersedes"),
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except CredibilityCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise _wrong("/") from None
    if credibility_crosswalk_bytes(value) != document:
        raise _wrong("/")
    return value


__all__ = (
    "MAX_CREDIBILITY_CROSSWALK_DOCUMENT_BYTES",
    "credibility_crosswalk_bytes",
    "credibility_crosswalk_digest",
    "credibility_crosswalk_payload",
    "credibility_crosswalk_ref",
    "load_credibility_crosswalk",
)
