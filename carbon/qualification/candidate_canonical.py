"""Canonical identity for B-06 qualification-manifest candidates."""

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
from carbon.measurement.refs import MeasurementContractRef
from carbon.registry.model import (
    REQUIRED_QUALIFICATION_SLOTS,
    ChallengeKey,
    QualificationEvidence,
    QualificationManifest,
)

from .candidate import (
    EvidenceManifestCandidateBinding,
    QualificationArtifactRef,
    QualificationArtifactSet,
    QualificationManifestCandidate,
    RegistryQualificationSlotBinding,
    RepresentationBinding,
)
from .enums import (
    ArtifactCurrentness,
    DossierEvidenceClass,
    DossierSlot,
    EvidenceCompleteness,
    QualificationArtifactKind,
    QualificationCandidateState,
    RepresentationApplicability,
    SignerArtifactKind,
    SignerBindingState,
    SignerRole,
    StructuralOrigin,
)
from .errors import DossierCanonicalError, DossierInputCode, DossierValidationError
from .model import SignerBinding
from .refs import (
    A3_QUALIFICATION_SNAPSHOT_DOCUMENT_HEADER,
    QUALIFICATION_CANDIDATE_DOCUMENT_HEADER,
    DossierEvidenceManifestRef,
    DossierEvidenceRef,
    QualificationManifestCandidateRef,
    SignerArtifactRef,
    ValidationDossierRef,
)

MAX_QUALIFICATION_CANDIDATE_DOCUMENT_BYTES = 2 * 1024 * 1024
_ARTIFACT_SET_HEADER = b"carbon.qualification.artifact-set.canonical.v1\x00"


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


def _top_to_dict(value: object) -> dict[str, object]:
    result = {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_to_dict(value.challenge_key),
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


def _top_from_dict(value: object, path: str):
    common = {
        "canonicalization_profile",
        "challenge_key",
        "content_digest",
        "object_id",
        "object_kind",
        "object_version",
        "ref_family",
        "schema_version",
    }
    raw = _object_any(value, path)
    kind = raw.get("object_kind")
    if type(kind) is not str:
        raise _wrong(f"{path}/object_kind", DossierInputCode.WRONG_TYPE)
    expected = common | (
        {"expected_population_role"}
        if kind == "instance_distribution_contract"
        else set()
    )
    fields = _object(value, expected, path)
    if fields["ref_family"] != "authoring_top_level" or kind not in _TOP_TYPES:
        raise _wrong(path)
    args = (
        _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
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


def _owner_to_dict(value: object) -> dict[str, object]:
    return {
        "challenge_key": _challenge_to_dict(value.scope_binding.challenge_key),
        "content_digest": value.content_digest,
        "object_id": value.object_id,
        "object_version": value.object_version,
        "ref_family": "authoring_owner",
        "ref_kind": value.ref_kind,
    }


def _owner_from_dict(value: object, path: str, expected_kind: str):
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
                _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key")
            ),
            object_id=fields["object_id"],
            object_version=fields["object_version"],
            content_digest=fields["content_digest"],
        )
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _measurement_to_dict(value: MeasurementContractRef) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "ref_type": value.ref_type,
        "schema_version": value.schema_version,
    }


def _measurement_from_dict(value: object, path: str) -> MeasurementContractRef:
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
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            fields["content_digest"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (AttributeError, TypeError, ValueError):
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
        raise _wrong(path)
    try:
        return ValidationDossierRef(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            fields["dossier_id"],
            fields["dossier_version"],
            fields["content_digest"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _manifest_ref_to_dict(value: DossierEvidenceManifestRef) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "manifest_id": value.manifest_id,
        "manifest_version": value.manifest_version,
        "origin": value.origin.value,
        "ref_type": value.ref_type,
        "schema_version": value.schema_version,
        "slot": value.slot.value,
    }


def _manifest_ref_from_dict(value: object, path: str) -> DossierEvidenceManifestRef:
    fields = _object(
        value,
        {
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "manifest_id",
            "manifest_version",
            "origin",
            "ref_type",
            "schema_version",
            "slot",
        },
        path,
    )
    if fields["ref_type"] != "dossier_evidence_manifest_ref":
        raise _wrong(path)
    try:
        return DossierEvidenceManifestRef(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            DossierSlot(fields["slot"]),
            fields["manifest_id"],
            fields["manifest_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _evidence_ref_to_dict(value: DossierEvidenceRef) -> dict[str, object]:
    return {
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "evidence_class": value.evidence_class.value,
        "evidence_id": value.evidence_id,
        "evidence_version": value.evidence_version,
        "origin": value.origin.value,
        "ref_type": value.ref_type,
    }


def _evidence_ref_from_dict(value: object, path: str) -> DossierEvidenceRef:
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
        raise _wrong(path)
    try:
        return DossierEvidenceRef(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            DossierEvidenceClass(fields["evidence_class"]),
            fields["evidence_id"],
            fields["evidence_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
        )
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _signer_artifact_to_dict(value: SignerArtifactRef) -> dict[str, object]:
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


def _optional_signer_artifact(value: object, path: str) -> SignerArtifactRef | None:
    if value is None:
        return None
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
        raise _wrong(path)
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
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _signer_to_dict(value: SignerBinding) -> dict[str, object]:
    return {
        "authorization_evidence_ref": (
            None
            if value.authorization_evidence_ref is None
            else _signer_artifact_to_dict(value.authorization_evidence_ref)
        ),
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "identity_ref": (
            None
            if value.identity_ref is None
            else _signer_artifact_to_dict(value.identity_ref)
        ),
        "signature_ref": (
            None
            if value.signature_ref is None
            else _signer_artifact_to_dict(value.signature_ref)
        ),
        "signer_role": value.signer_role.value,
        "state": value.state.value,
    }


def _signer_from_dict(value: object, path: str) -> SignerBinding:
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
            _optional_signer_artifact(fields["identity_ref"], f"{path}/identity_ref"),
            _optional_signer_artifact(fields["signature_ref"], f"{path}/signature_ref"),
            _optional_signer_artifact(
                fields["authorization_evidence_ref"],
                f"{path}/authorization_evidence_ref",
            ),
        )
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _artifact_to_dict(value: QualificationArtifactRef) -> dict[str, object]:
    return {
        "artifact_kind": value.artifact_kind.value,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "currentness": value.currentness.value,
        "object_id": value.object_id,
        "object_version": value.object_version,
        "origin": value.origin.value,
        "registry_artifact_id": value.registry_artifact_id,
    }


def _artifact_from_dict(value: object, path: str) -> QualificationArtifactRef:
    fields = _object(
        value,
        {
            "artifact_kind",
            "challenge_key",
            "content_digest",
            "currentness",
            "object_id",
            "object_version",
            "origin",
            "registry_artifact_id",
        },
        path,
    )
    try:
        return QualificationArtifactRef(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            fields["registry_artifact_id"],
            QualificationArtifactKind(fields["artifact_kind"]),
            fields["object_id"],
            fields["object_version"],
            fields["content_digest"],
            StructuralOrigin(fields["origin"]),
            ArtifactCurrentness(fields["currentness"]),
        )
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _artifact_set_to_dict(value: QualificationArtifactSet) -> dict[str, object]:
    return {
        "artifact_set_id": value.artifact_set_id,
        "artifact_set_version": value.artifact_set_version,
        "artifacts": [_artifact_to_dict(item) for item in value.artifacts],
        "challenge_key": _challenge_to_dict(value.challenge_key),
    }


def _artifact_set_from_dict(value: object, path: str) -> QualificationArtifactSet:
    fields = _object(
        value,
        {"artifact_set_id", "artifact_set_version", "artifacts", "challenge_key"},
        path,
    )
    artifacts = _array(fields["artifacts"], f"{path}/artifacts")
    try:
        return QualificationArtifactSet(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            fields["artifact_set_id"],
            fields["artifact_set_version"],
            tuple(
                _artifact_from_dict(item, f"{path}/artifacts/{index}")
                for index, item in enumerate(artifacts)
            ),
        )
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def artifact_set_digest(value: QualificationArtifactSet) -> str:
    if type(value) is not QualificationArtifactSet:
        raise _wrong("/artifact_set", DossierInputCode.WRONG_TYPE)
    payload = _json_bytes(_artifact_set_to_dict(value), "/artifact_set")
    return "sha256:" + hashlib.sha256(_ARTIFACT_SET_HEADER + payload).hexdigest()


def _candidate_ref_to_dict(
    value: QualificationManifestCandidateRef,
) -> dict[str, object]:
    return {
        "candidate_id": value.candidate_id,
        "candidate_version": value.candidate_version,
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "ref_type": value.ref_type,
        "schema_version": value.schema_version,
    }


def _candidate_ref_from_dict(
    value: object, path: str
) -> QualificationManifestCandidateRef:
    fields = _object(
        value,
        {
            "candidate_id",
            "candidate_version",
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "ref_type",
            "schema_version",
        },
        path,
    )
    if fields["ref_type"] != "qualification_manifest_candidate_ref":
        raise _wrong(path)
    try:
        return QualificationManifestCandidateRef(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            fields["candidate_id"],
            fields["candidate_version"],
            fields["content_digest"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def qualification_candidate_payload(
    value: QualificationManifestCandidate,
) -> dict[str, object]:
    if type(value) is not QualificationManifestCandidate:
        raise _wrong("/", DossierInputCode.WRONG_TYPE)
    return {
        "artifact_set": _artifact_set_to_dict(value.artifact_set),
        "artifact_set_digest": artifact_set_digest(value.artifact_set),
        "candidate_id": value.candidate_id,
        "candidate_output_ref": _top_to_dict(value.candidate_output_ref),
        "candidate_version": value.candidate_version,
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "claim_scope_ref": _owner_to_dict(value.claim_scope_ref),
        "dossier_completeness": value.dossier_completeness.value,
        "dossier_currentness": value.dossier_currentness.value,
        "dossier_origin": value.dossier_origin.value,
        "dossier_ref": _dossier_ref_to_dict(value.dossier_ref),
        "evidence_manifest_bindings": [
            {
                "completeness": item.completeness.value,
                "currentness": item.currentness.value,
                "manifest_ref": (
                    None
                    if item.manifest_ref is None
                    else _manifest_ref_to_dict(item.manifest_ref)
                ),
                "slot": item.slot.value,
            }
            for item in value.evidence_manifest_bindings
        ],
        "expected_registry_qualification_digest": value.expected_registry_qualification_digest,
        "generator_ref": _owner_to_dict(value.generator_ref),
        "measurement_contract_refs": [
            _measurement_to_dict(item) for item in value.measurement_contract_refs
        ],
        "physical_system_ref": _top_to_dict(value.physical_system_ref),
        "record_type": "qualification_manifest_candidate",
        "reference_policy_ref": _owner_to_dict(value.reference_policy_ref),
        "registry_slot_bindings": [
            {"registry_artifact_id": item.registry_artifact_id, "slot": item.slot}
            for item in value.registry_slot_bindings
        ],
        "representation": {
            "applicability": value.representation.applicability.value,
            "rationale_ref": (
                None
                if value.representation.rationale_ref is None
                else _evidence_ref_to_dict(value.representation.rationale_ref)
            ),
            "representation_refs": [
                _owner_to_dict(item)
                for item in value.representation.representation_refs
            ],
        },
        "sampling_plan_ref": _top_to_dict(value.sampling_plan_ref),
        "schema_version": value.schema_version,
        "signer_bindings": [_signer_to_dict(item) for item in value.signer_bindings],
        "state": value.state.value,
        "supersedes": (
            None
            if value.supersedes is None
            else _candidate_ref_to_dict(value.supersedes)
        ),
        "target_population_ref": _top_to_dict(value.target_population_ref),
    }


def qualification_candidate_bytes(value: QualificationManifestCandidate) -> bytes:
    document = QUALIFICATION_CANDIDATE_DOCUMENT_HEADER + _json_bytes(
        qualification_candidate_payload(value), "/"
    )
    if len(document) > MAX_QUALIFICATION_CANDIDATE_DOCUMENT_BYTES:
        raise _wrong("/", DossierInputCode.SIZE_LIMIT)
    return document


def qualification_candidate_digest(value: QualificationManifestCandidate) -> str:
    return "sha256:" + hashlib.sha256(qualification_candidate_bytes(value)).hexdigest()


def qualification_candidate_ref(
    value: QualificationManifestCandidate,
) -> QualificationManifestCandidateRef:
    return QualificationManifestCandidateRef(
        value.challenge_key,
        value.candidate_id,
        value.candidate_version,
        qualification_candidate_digest(value),
        value.schema_version,
        value.canonicalization_profile,
    )


def _a3_evidence_payload(value: QualificationEvidence | None) -> object:
    if value is None:
        return None
    if type(value) is not QualificationEvidence:
        raise _wrong("/a3_qualification", DossierInputCode.WRONG_TYPE)
    return {
        "artifact_id": value.artifact_id,
        "backend_profile_ids": list(value.backend_profile_ids),
        "receipt_schema_version": value.receipt_schema_version,
        "reference": value.reference,
        "state": value.state,
    }


def a3_qualification_snapshot_payload(
    value: QualificationManifest,
) -> dict[str, object]:
    if type(value) is not QualificationManifest:
        raise _wrong("/a3_qualification", DossierInputCode.WRONG_TYPE)
    return {
        "challenge_id": value.challenge_id,
        "challenge_version": value.challenge_version,
        "mode": value.mode,
        "scientific_authoring_graph_fingerprint": value.scientific_authoring_graph_fingerprint,
        "slots": {
            slot: _a3_evidence_payload(value.slots.get(slot))
            for slot in REQUIRED_QUALIFICATION_SLOTS
        },
    }


def a3_qualification_snapshot_digest(value: QualificationManifest) -> str:
    payload = _json_bytes(a3_qualification_snapshot_payload(value), "/a3_qualification")
    return (
        "sha256:"
        + hashlib.sha256(
            A3_QUALIFICATION_SNAPSHOT_DOCUMENT_HEADER + payload
        ).hexdigest()
    )


def load_qualification_candidate(document: bytes) -> QualificationManifestCandidate:
    if type(document) is not bytes:
        raise _wrong("/", DossierInputCode.WRONG_TYPE)
    if len(document) > MAX_QUALIFICATION_CANDIDATE_DOCUMENT_BYTES:
        raise _wrong("/", DossierInputCode.SIZE_LIMIT)
    if not document.startswith(QUALIFICATION_CANDIDATE_DOCUMENT_HEADER):
        raise _wrong("/")
    payload_bytes = document[len(QUALIFICATION_CANDIDATE_DOCUMENT_HEADER) :]
    try:
        decoded = json.loads(
            payload_bytes.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs,
            parse_float=_reject_number,
            parse_int=_reject_number,
            parse_constant=_reject_number,
        )
    except DossierCanonicalError:
        raise
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise _wrong("/") from None
    fields = _object(
        decoded,
        {
            "artifact_set",
            "artifact_set_digest",
            "candidate_id",
            "candidate_output_ref",
            "candidate_version",
            "canonicalization_profile",
            "challenge_key",
            "claim_scope_ref",
            "dossier_completeness",
            "dossier_currentness",
            "dossier_origin",
            "dossier_ref",
            "evidence_manifest_bindings",
            "expected_registry_qualification_digest",
            "generator_ref",
            "measurement_contract_refs",
            "physical_system_ref",
            "record_type",
            "reference_policy_ref",
            "registry_slot_bindings",
            "representation",
            "sampling_plan_ref",
            "schema_version",
            "signer_bindings",
            "state",
            "supersedes",
            "target_population_ref",
        },
        "/",
    )
    if fields["record_type"] != "qualification_manifest_candidate":
        raise _wrong("/record_type")
    artifact_set = _artifact_set_from_dict(fields["artifact_set"], "/artifact_set")
    if fields["artifact_set_digest"] != artifact_set_digest(artifact_set):
        raise _wrong("/artifact_set_digest", DossierInputCode.DIGEST_MISMATCH)
    evidence_values = _array(
        fields["evidence_manifest_bindings"], "/evidence_manifest_bindings"
    )
    registry_values = _array(
        fields["registry_slot_bindings"], "/registry_slot_bindings"
    )
    signer_values = _array(fields["signer_bindings"], "/signer_bindings")
    measurement_values = _array(
        fields["measurement_contract_refs"], "/measurement_contract_refs"
    )
    representation_fields = _object(
        fields["representation"],
        {"applicability", "rationale_ref", "representation_refs"},
        "/representation",
    )
    representation_values = _array(
        representation_fields["representation_refs"],
        "/representation/representation_refs",
    )
    try:
        value = QualificationManifestCandidate(
            _challenge_from_dict(fields["challenge_key"], "/challenge_key"),
            fields["candidate_id"],
            fields["candidate_version"],
            QualificationCandidateState(fields["state"]),
            _dossier_ref_from_dict(fields["dossier_ref"], "/dossier_ref"),
            EvidenceCompleteness(fields["dossier_completeness"]),
            StructuralOrigin(fields["dossier_origin"]),
            ArtifactCurrentness(fields["dossier_currentness"]),
            _top_from_dict(fields["physical_system_ref"], "/physical_system_ref"),
            _owner_from_dict(
                fields["claim_scope_ref"], "/claim_scope_ref", "claim_scope"
            ),
            _top_from_dict(fields["target_population_ref"], "/target_population_ref"),
            _top_from_dict(fields["sampling_plan_ref"], "/sampling_plan_ref"),
            _owner_from_dict(fields["generator_ref"], "/generator_ref", "generator"),
            _owner_from_dict(
                fields["reference_policy_ref"],
                "/reference_policy_ref",
                "reference_qualification_policy",
            ),
            _top_from_dict(fields["candidate_output_ref"], "/candidate_output_ref"),
            RepresentationBinding(
                RepresentationApplicability(representation_fields["applicability"]),
                tuple(
                    _owner_from_dict(
                        item,
                        f"/representation/representation_refs/{index}",
                        "representation",
                    )
                    for index, item in enumerate(representation_values)
                ),
                (
                    None
                    if representation_fields["rationale_ref"] is None
                    else _evidence_ref_from_dict(
                        representation_fields["rationale_ref"],
                        "/representation/rationale_ref",
                    )
                ),
            ),
            tuple(
                _measurement_from_dict(item, f"/measurement_contract_refs/{index}")
                for index, item in enumerate(measurement_values)
            ),
            tuple(
                _evidence_binding_from_dict(
                    item, f"/evidence_manifest_bindings/{index}"
                )
                for index, item in enumerate(evidence_values)
            ),
            tuple(
                _signer_from_dict(item, f"/signer_bindings/{index}")
                for index, item in enumerate(signer_values)
            ),
            artifact_set,
            tuple(
                _registry_slot_from_dict(item, f"/registry_slot_bindings/{index}")
                for index, item in enumerate(registry_values)
            ),
            fields["expected_registry_qualification_digest"],
            (
                None
                if fields["supersedes"] is None
                else _candidate_ref_from_dict(fields["supersedes"], "/supersedes")
            ),
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong("/", DossierInputCode.WRONG_TYPE) from None
    if qualification_candidate_bytes(value) != document:
        raise _wrong("/", DossierInputCode.DIGEST_MISMATCH)
    return value


def _evidence_binding_from_dict(
    value: object, path: str
) -> EvidenceManifestCandidateBinding:
    fields = _object(
        value, {"completeness", "currentness", "manifest_ref", "slot"}, path
    )
    try:
        return EvidenceManifestCandidateBinding(
            DossierSlot(fields["slot"]),
            EvidenceCompleteness(fields["completeness"]),
            (
                None
                if fields["manifest_ref"] is None
                else _manifest_ref_from_dict(
                    fields["manifest_ref"], f"{path}/manifest_ref"
                )
            ),
            ArtifactCurrentness(fields["currentness"]),
        )
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _registry_slot_from_dict(
    value: object, path: str
) -> RegistryQualificationSlotBinding:
    fields = _object(value, {"registry_artifact_id", "slot"}, path)
    try:
        return RegistryQualificationSlotBinding(
            fields["slot"], fields["registry_artifact_id"]
        )
    except (DossierValidationError, AttributeError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _json_bytes(value: object, path: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeError):
        raise _wrong(path) from None


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


def _object_any(value: object, path: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise _wrong(path, DossierInputCode.WRONG_TYPE)
    return value


def _object(value: object, expected: set[str], path: str) -> Mapping[str, Any]:
    result = _object_any(value, path)
    if set(result) != expected:
        raise _wrong(path)
    return result


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise _wrong(path, DossierInputCode.WRONG_TYPE)
    return value


__all__ = (
    "MAX_QUALIFICATION_CANDIDATE_DOCUMENT_BYTES",
    "a3_qualification_snapshot_digest",
    "a3_qualification_snapshot_payload",
    "artifact_set_digest",
    "load_qualification_candidate",
    "qualification_candidate_bytes",
    "qualification_candidate_digest",
    "qualification_candidate_payload",
    "qualification_candidate_ref",
)
