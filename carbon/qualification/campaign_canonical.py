"""Strict canonical bytes for B-06 campaign acquisition/result evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from carbon.authoring.refs import (
    CandidateOutputContractRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    owner_ref,
)
from carbon.measurement.enums import MeasurementDefinitionKind
from carbon.measurement.refs import MeasurementContractRef, MeasurementDefinitionRef
from carbon.registry.model import ChallengeKey

from .campaign import (
    CampaignAcquisitionManifest,
    CampaignArtifactRef,
    CampaignEvidenceManifest,
    CampaignResultManifest,
    CampaignSubjectBinding,
)
from .enums import (
    ArtifactCurrentness,
    AttemptDisposition,
    CampaignAcquisitionState,
    CampaignArtifactRole,
    CampaignAuthorityStatus,
    CampaignFamily,
    CampaignResultStatus,
    CampaignSubjectRole,
    DossierEvidenceClass,
    StructuralOrigin,
)
from .errors import DossierCanonicalError, DossierInputCode, DossierValidationError
from .evidence import EvidenceAttemptBinding
from .refs import (
    CAMPAIGN_ACQUISITION_DOCUMENT_HEADER,
    CAMPAIGN_MANIFEST_DOCUMENT_HEADER,
    CampaignEvidenceManifestRef,
    DossierEvidenceRef,
)

MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES = 2 * 1024 * 1024

_NON_EVIDENTIARY_RESULT_STATUSES = frozenset(
    {
        CampaignResultStatus.BLOCKED,
        CampaignResultStatus.EVIDENCE_DEFERRED,
        CampaignResultStatus.GENERATOR_FAILURE,
        CampaignResultStatus.INVALID,
        CampaignResultStatus.NOT_APPLICABLE,
        CampaignResultStatus.REFERENCE_FAILURE,
    }
)


def _wrong(path: str, code: DossierInputCode = DossierInputCode.INVALID_VALUE):
    return DossierCanonicalError(code, path=path)


def _challenge_dict(value: ChallengeKey) -> dict[str, str]:
    return {"challenge_id": value.challenge_id, "version": value.version}


def _challenge_load(value: object, path: str) -> ChallengeKey:
    fields = _object(value, {"challenge_id", "version"}, path)
    try:
        return ChallengeKey(fields["challenge_id"], fields["version"])
    except (TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _top_dict(value: object) -> dict[str, object]:
    result = {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "object_id": value.object_id,
        "object_kind": value.object_kind,
        "object_version": value.object_version,
        "ref_family": "authoring_top_level",
        "schema_version": value.schema_version,
    }
    if type(value) is InstanceDistributionContractRef:
        result["expected_population_role"] = value.expected_population_role
    return result


_TOP_TYPES = {
    "physical_system_spec": PhysicalSystemSpecRef,
    "candidate_output_contract": CandidateOutputContractRef,
    "instance_distribution_contract": InstanceDistributionContractRef,
    "sampling_plan": SamplingPlanRef,
}


def _top_load(value: object, path: str):
    raw = _object_any(value, path)
    kind = raw.get("object_kind")
    if type(kind) is not str:
        raise _wrong(f"{path}/object_kind", DossierInputCode.WRONG_TYPE)
    names = {
        "canonicalization_profile",
        "challenge_key",
        "content_digest",
        "object_id",
        "object_kind",
        "object_version",
        "ref_family",
        "schema_version",
    }
    if kind == "instance_distribution_contract":
        names.add("expected_population_role")
    fields = _object(value, names, path)
    if fields["ref_family"] != "authoring_top_level" or kind not in _TOP_TYPES:
        raise _wrong(path, DossierInputCode.ROLE_CONFUSION)
    args = (
        _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
        fields["object_id"],
        fields["object_version"],
        fields["schema_version"],
        fields["canonicalization_profile"],
        fields["content_digest"],
    )
    if kind == "instance_distribution_contract":
        args = (*args, fields["expected_population_role"])
    try:
        return _TOP_TYPES[kind](*args)
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _owner_dict(value: object) -> dict[str, object]:
    return {
        "challenge_key": _challenge_dict(value.scope_binding.challenge_key),
        "content_digest": value.content_digest,
        "object_id": value.object_id,
        "object_version": value.object_version,
        "ref_family": "authoring_owner",
        "ref_kind": value.ref_kind,
    }


def _owner_load(value: object, path: str, expected_kind: str):
    fields = _object(
        value,
        {
            "challenge_key",
            "content_digest",
            "object_id",
            "object_version",
            "ref_family",
            "ref_kind",
        },
        path,
    )
    if fields["ref_family"] != "authoring_owner" or fields["ref_kind"] != expected_kind:
        raise _wrong(path, DossierInputCode.ROLE_CONFUSION)
    try:
        return owner_ref(
            expected_kind,
            scope_binding=ChallengeScope(
                _challenge_load(fields["challenge_key"], f"{path}/challenge_key")
            ),
            object_id=fields["object_id"],
            object_version=fields["object_version"],
            content_digest=fields["content_digest"],
        )
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _measurement_dict(value: MeasurementContractRef) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "ref_type": value.ref_type,
        "schema_version": value.schema_version,
    }


def _measurement_load(value: object, path: str) -> MeasurementContractRef:
    fields = _object(
        value,
        {
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "ref_type",
            "schema_version",
        },
        path,
    )
    if fields["ref_type"] != "measurement_contract_ref":
        raise _wrong(path, DossierInputCode.ROLE_CONFUSION)
    try:
        return MeasurementContractRef(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            fields["content_digest"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _definition_dict(value: MeasurementDefinitionRef) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "definition_kind": value.definition_kind.value,
        "object_id": value.object_id,
        "object_version": value.object_version,
        "ref_type": value.ref_type,
        "schema_version": value.schema_version,
    }


def _definition_load(value: object, path: str) -> MeasurementDefinitionRef:
    fields = _object(
        value,
        {
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "definition_kind",
            "object_id",
            "object_version",
            "ref_type",
            "schema_version",
        },
        path,
    )
    if fields["ref_type"] != "measurement_definition_ref":
        raise _wrong(path, DossierInputCode.ROLE_CONFUSION)
    try:
        return MeasurementDefinitionRef(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            MeasurementDefinitionKind(fields["definition_kind"]),
            fields["object_id"],
            fields["object_version"],
            fields["content_digest"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


_SUBJECT_OWNER_KINDS = {
    CampaignSubjectRole.CLAIM_SCOPE: "claim_scope",
    CampaignSubjectRole.GENERATOR: "generator",
    CampaignSubjectRole.REFERENCE_POLICY: "reference_qualification_policy",
    CampaignSubjectRole.REPRESENTATION: "representation",
}


def _subject_dict(value: CampaignSubjectBinding) -> dict[str, object]:
    if value.subject_role in _SUBJECT_OWNER_KINDS:
        encoded = _owner_dict(value.subject_ref)
    elif value.subject_role is CampaignSubjectRole.MEASUREMENT_CONTRACT:
        encoded = _measurement_dict(value.subject_ref)
    else:
        encoded = _top_dict(value.subject_ref)
    return {
        "challenge_key": _challenge_dict(value.challenge_key),
        "subject_ref": encoded,
        "subject_role": value.subject_role.value,
    }


def _subject_load(value: object, path: str) -> CampaignSubjectBinding:
    fields = _object(value, {"challenge_key", "subject_ref", "subject_role"}, path)
    try:
        role = CampaignSubjectRole(fields["subject_role"])
        if role in _SUBJECT_OWNER_KINDS:
            subject = _owner_load(
                fields["subject_ref"], f"{path}/subject_ref", _SUBJECT_OWNER_KINDS[role]
            )
        elif role is CampaignSubjectRole.MEASUREMENT_CONTRACT:
            subject = _measurement_load(fields["subject_ref"], f"{path}/subject_ref")
        else:
            subject = _top_load(fields["subject_ref"], f"{path}/subject_ref")
        return CampaignSubjectBinding(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            role,
            subject,
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _artifact_dict(value: CampaignArtifactRef) -> dict[str, object]:
    return {
        "artifact_id": value.artifact_id,
        "artifact_role": value.artifact_role.value,
        "artifact_version": value.artifact_version,
        "challenge_key": _challenge_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "currentness": value.currentness.value,
        "origin": value.origin.value,
    }


def _artifact_load(value: object, path: str) -> CampaignArtifactRef:
    fields = _object(
        value,
        {
            "artifact_id",
            "artifact_role",
            "artifact_version",
            "challenge_key",
            "content_digest",
            "currentness",
            "origin",
        },
        path,
    )
    try:
        return CampaignArtifactRef(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            CampaignArtifactRole(fields["artifact_role"]),
            fields["artifact_id"],
            fields["artifact_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
            ArtifactCurrentness(fields["currentness"]),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _evidence_dict(value: DossierEvidenceRef) -> dict[str, object]:
    return {
        "challenge_key": _challenge_dict(value.challenge_key),
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
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _attempt_dict(value: EvidenceAttemptBinding) -> dict[str, object]:
    return {
        "attempt_ref": _evidence_dict(value.attempt_ref),
        "challenge_key": _challenge_dict(value.challenge_key),
        "disposition": value.disposition.value,
    }


def _attempt_load(value: object, path: str) -> EvidenceAttemptBinding:
    fields = _object(value, {"attempt_ref", "challenge_key", "disposition"}, path)
    try:
        return EvidenceAttemptBinding(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            _evidence_load(fields["attempt_ref"], f"{path}/attempt_ref"),
            AttemptDisposition(fields["disposition"]),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def campaign_acquisition_payload(
    value: CampaignAcquisitionManifest,
) -> dict[str, object]:
    if type(value) is not CampaignAcquisitionManifest:
        raise _wrong("/acquisition", DossierInputCode.WRONG_TYPE)
    return {
        "acquisition_id": value.acquisition_id,
        "acquisition_state": value.acquisition_state.value,
        "acquisition_version": value.acquisition_version,
        "artifact_refs": [_artifact_dict(item) for item in value.artifact_refs],
        "attempts": [_attempt_dict(item) for item in value.attempts],
        "authority_status": value.authority_status.value,
        "campaign_family": value.campaign_family.value,
        "challenge_key": _challenge_dict(value.challenge_key),
        "definition_refs": [_definition_dict(item) for item in value.definition_refs],
        "subject_bindings": [_subject_dict(item) for item in value.subject_bindings],
    }


def campaign_acquisition_bytes(value: CampaignAcquisitionManifest) -> bytes:
    document = CAMPAIGN_ACQUISITION_DOCUMENT_HEADER + _json_bytes(
        campaign_acquisition_payload(value), "/acquisition"
    )
    if len(document) > MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES:
        raise _wrong("/acquisition", DossierInputCode.SIZE_LIMIT)
    return document


def campaign_acquisition_digest(value: CampaignAcquisitionManifest) -> str:
    return "sha256:" + hashlib.sha256(campaign_acquisition_bytes(value)).hexdigest()


def _acquisition_load(value: object, path: str) -> CampaignAcquisitionManifest:
    fields = _object(
        value,
        {
            "acquisition_id",
            "acquisition_state",
            "acquisition_version",
            "artifact_refs",
            "attempts",
            "authority_status",
            "campaign_family",
            "challenge_key",
            "definition_refs",
            "subject_bindings",
        },
        path,
    )
    try:
        return CampaignAcquisitionManifest(
            challenge_key=_challenge_load(
                fields["challenge_key"], f"{path}/challenge_key"
            ),
            campaign_family=CampaignFamily(fields["campaign_family"]),
            acquisition_id=fields["acquisition_id"],
            acquisition_version=fields["acquisition_version"],
            acquisition_state=CampaignAcquisitionState(fields["acquisition_state"]),
            authority_status=CampaignAuthorityStatus(fields["authority_status"]),
            subject_bindings=tuple(
                _subject_load(item, f"{path}/subject_bindings/{index}")
                for index, item in enumerate(
                    _array(fields["subject_bindings"], f"{path}/subject_bindings")
                )
            ),
            definition_refs=tuple(
                _definition_load(item, f"{path}/definition_refs/{index}")
                for index, item in enumerate(
                    _array(fields["definition_refs"], f"{path}/definition_refs")
                )
            ),
            artifact_refs=tuple(
                _artifact_load(item, f"{path}/artifact_refs/{index}")
                for index, item in enumerate(
                    _array(fields["artifact_refs"], f"{path}/artifact_refs")
                )
            ),
            attempts=tuple(
                _attempt_load(item, f"{path}/attempts/{index}")
                for index, item in enumerate(
                    _array(fields["attempts"], f"{path}/attempts")
                )
            ),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _result_dict(value: CampaignResultManifest) -> dict[str, object]:
    return {
        "acquisition_digest": value.acquisition_digest,
        "acquisition_id": value.acquisition_id,
        "acquisition_version": value.acquisition_version,
        "artifact_refs": [_artifact_dict(item) for item in value.artifact_refs],
        "attempts": [_attempt_dict(item) for item in value.attempts],
        "campaign_family": value.campaign_family.value,
        "challenge_key": _challenge_dict(value.challenge_key),
        "result_id": value.result_id,
        "result_status": value.result_status.value,
        "result_version": value.result_version,
        "scope_refs": [_definition_dict(item) for item in value.scope_refs],
    }


def _result_load(value: object, path: str) -> CampaignResultManifest:
    fields = _object(
        value,
        {
            "acquisition_digest",
            "acquisition_id",
            "acquisition_version",
            "artifact_refs",
            "attempts",
            "campaign_family",
            "challenge_key",
            "result_id",
            "result_status",
            "result_version",
            "scope_refs",
        },
        path,
    )
    try:
        return CampaignResultManifest(
            challenge_key=_challenge_load(
                fields["challenge_key"], f"{path}/challenge_key"
            ),
            campaign_family=CampaignFamily(fields["campaign_family"]),
            result_id=fields["result_id"],
            result_version=fields["result_version"],
            acquisition_id=fields["acquisition_id"],
            acquisition_version=fields["acquisition_version"],
            acquisition_digest=fields["acquisition_digest"],
            result_status=CampaignResultStatus(fields["result_status"]),
            scope_refs=tuple(
                _definition_load(item, f"{path}/scope_refs/{index}")
                for index, item in enumerate(
                    _array(fields["scope_refs"], f"{path}/scope_refs")
                )
            ),
            artifact_refs=tuple(
                _artifact_load(item, f"{path}/artifact_refs/{index}")
                for index, item in enumerate(
                    _array(fields["artifact_refs"], f"{path}/artifact_refs")
                )
            ),
            attempts=tuple(
                _attempt_load(item, f"{path}/attempts/{index}")
                for index, item in enumerate(
                    _array(fields["attempts"], f"{path}/attempts")
                )
            ),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _manifest_ref_dict(value: CampaignEvidenceManifestRef) -> dict[str, object]:
    return {
        "campaign_family": value.campaign_family.value,
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "evidence_class": value.evidence_class.value,
        "manifest_id": value.manifest_id,
        "manifest_version": value.manifest_version,
        "origin": value.origin.value,
        "schema_version": value.schema_version,
    }


def _manifest_ref_load(value: object, path: str) -> CampaignEvidenceManifestRef:
    fields = _object(
        value,
        {
            "campaign_family",
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "evidence_class",
            "manifest_id",
            "manifest_version",
            "origin",
            "schema_version",
        },
        path,
    )
    try:
        return CampaignEvidenceManifestRef(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            CampaignFamily(fields["campaign_family"]),
            DossierEvidenceClass(fields["evidence_class"]),
            fields["manifest_id"],
            fields["manifest_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def campaign_manifest_payload(value: CampaignEvidenceManifest) -> dict[str, object]:
    if type(value) is not CampaignEvidenceManifest:
        raise _wrong("/manifest", DossierInputCode.WRONG_TYPE)
    return {
        "acquisition": campaign_acquisition_payload(value.acquisition),
        "campaign_family": value.campaign_family.value,
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_dict(value.challenge_key),
        "currentness": value.currentness.value,
        "evidence_class": value.evidence_class.value,
        "manifest_id": value.manifest_id,
        "manifest_version": value.manifest_version,
        "origin": value.origin.value,
        "result": None if value.result is None else _result_dict(value.result),
        "schema_version": value.schema_version,
        "supersedes": (
            None if value.supersedes is None else _manifest_ref_dict(value.supersedes)
        ),
    }


def campaign_manifest_bytes(value: CampaignEvidenceManifest) -> bytes:
    document = CAMPAIGN_MANIFEST_DOCUMENT_HEADER + _json_bytes(
        campaign_manifest_payload(value), "/manifest"
    )
    if len(document) > MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES:
        raise _wrong("/manifest", DossierInputCode.SIZE_LIMIT)
    return document


def campaign_manifest_digest(value: CampaignEvidenceManifest) -> str:
    return "sha256:" + hashlib.sha256(campaign_manifest_bytes(value)).hexdigest()


def campaign_manifest_ref(
    value: CampaignEvidenceManifest,
) -> CampaignEvidenceManifestRef:
    origin = StructuralOrigin.FIXTURE_ONLY if value.fixture_derived else value.origin
    return CampaignEvidenceManifestRef(
        value.challenge_key,
        value.campaign_family,
        value.evidence_class,
        value.manifest_id,
        value.manifest_version,
        campaign_manifest_digest(value),
        origin,
    )


def campaign_evidence_ref(value: CampaignEvidenceManifest) -> DossierEvidenceRef:
    if type(value) is not CampaignEvidenceManifest:
        raise DossierValidationError(DossierInputCode.WRONG_TYPE, path="/manifest")
    if value.currentness is not ArtifactCurrentness.CURRENT:
        raise DossierValidationError(
            DossierInputCode.VERSION_MISMATCH, path="/currentness"
        )
    if not value.acquisition.structurally_current or (
        value.result is not None and not value.result.structurally_current
    ):
        raise DossierValidationError(
            DossierInputCode.VERSION_MISMATCH, path="/artifact_refs/currentness"
        )
    if value.result is None:
        raise DossierValidationError(DossierInputCode.MISSING_EVIDENCE, path="/result")
    if value.result.result_status in _NON_EVIDENTIARY_RESULT_STATUSES:
        raise DossierValidationError(
            DossierInputCode.MISSING_EVIDENCE, path="/result/result_status"
        )
    origin = StructuralOrigin.FIXTURE_ONLY if value.fixture_derived else value.origin
    return DossierEvidenceRef(
        value.challenge_key,
        value.evidence_class,
        value.manifest_id,
        value.manifest_version,
        campaign_manifest_digest(value),
        origin,
    )


def load_campaign_manifest(document: bytes) -> CampaignEvidenceManifest:
    if type(document) is not bytes:
        raise _wrong("/document", DossierInputCode.WRONG_TYPE)
    if len(document) > MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES:
        raise _wrong("/document", DossierInputCode.SIZE_LIMIT)
    if not document.startswith(CAMPAIGN_MANIFEST_DOCUMENT_HEADER):
        raise _wrong("/document", DossierInputCode.DIGEST_MISMATCH)
    raw = document[len(CAMPAIGN_MANIFEST_DOCUMENT_HEADER) :]
    try:
        text = raw.decode("utf-8", errors="strict")
        payload = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_int=_reject_number,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except DossierCanonicalError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise _wrong("/document", DossierInputCode.WRONG_TYPE) from None
    fields = _object(
        payload,
        {
            "acquisition",
            "campaign_family",
            "canonicalization_profile",
            "challenge_key",
            "currentness",
            "evidence_class",
            "manifest_id",
            "manifest_version",
            "origin",
            "result",
            "schema_version",
            "supersedes",
        },
        "/",
    )
    try:
        manifest = CampaignEvidenceManifest(
            challenge_key=_challenge_load(fields["challenge_key"], "/challenge_key"),
            campaign_family=CampaignFamily(fields["campaign_family"]),
            evidence_class=DossierEvidenceClass(fields["evidence_class"]),
            manifest_id=fields["manifest_id"],
            manifest_version=fields["manifest_version"],
            origin=StructuralOrigin(fields["origin"]),
            currentness=ArtifactCurrentness(fields["currentness"]),
            acquisition=_acquisition_load(fields["acquisition"], "/acquisition"),
            result=(
                None
                if fields["result"] is None
                else _result_load(fields["result"], "/result")
            ),
            supersedes=(
                None
                if fields["supersedes"] is None
                else _manifest_ref_load(fields["supersedes"], "/supersedes")
            ),
            schema_version=fields["schema_version"],
            canonicalization_profile=fields["canonicalization_profile"],
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong("/", DossierInputCode.WRONG_TYPE) from None
    if campaign_manifest_bytes(manifest) != document:
        raise _wrong("/document", DossierInputCode.DIGEST_MISMATCH)
    return manifest


def _json_bytes(value: object, path: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _reject_number(value: str):
    del value
    raise _wrong("/document", DossierInputCode.WRONG_TYPE)


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise _wrong("/document", DossierInputCode.DUPLICATE_IDENTITY)
        result[key] = value
    return result


def _object_any(value: object, path: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise _wrong(path, DossierInputCode.WRONG_TYPE)
    return value


def _object(value: object, names: set[str], path: str) -> Mapping[str, Any]:
    result = _object_any(value, path)
    if set(result) != names:
        raise _wrong(path, DossierInputCode.WRONG_TYPE)
    return result


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise _wrong(path, DossierInputCode.WRONG_TYPE)
    return value


__all__ = (
    "MAX_CAMPAIGN_MANIFEST_DOCUMENT_BYTES",
    "campaign_acquisition_bytes",
    "campaign_acquisition_digest",
    "campaign_acquisition_payload",
    "campaign_evidence_ref",
    "campaign_manifest_bytes",
    "campaign_manifest_digest",
    "campaign_manifest_payload",
    "campaign_manifest_ref",
    "load_campaign_manifest",
)
