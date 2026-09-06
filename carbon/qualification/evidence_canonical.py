"""Strict canonical form for B-06 typed evidence manifests."""

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
from carbon.measurement.refs import (
    MeasurementContractRef,
    MeasurementDefinitionRef,
    MeasurementQualificationEvidenceRef,
    UncertaintyPolicyRef,
)
from carbon.registry.model import ChallengeKey

from .enums import (
    DOSSIER_PRIMARY_EVIDENCE_CLASS,
    AttemptDisposition,
    DependencePolicyAuthorityStatus,
    DossierClaimRole,
    DossierEvidenceClass,
    DossierSlot,
    EvidenceCompleteness,
    StructuralOrigin,
)
from .errors import DossierCanonicalError, DossierInputCode, DossierValidationError
from .evidence import (
    DossierEvidenceManifest,
    EvidenceAccountingManifest,
    EvidenceAttemptBinding,
    EvidenceClaimBinding,
    EvidenceSubjectBindings,
    LimitationBinding,
    SecrecyEvidenceManifest,
    StatisticalScopeManifest,
)
from .refs import (
    EVIDENCE_MANIFEST_DOCUMENT_HEADER,
    DossierEvidenceManifestRef,
    DossierEvidenceRef,
)

MAX_EVIDENCE_MANIFEST_DOCUMENT_BYTES = 1024 * 1024


def _wrong(path: str, code: DossierInputCode = DossierInputCode.INVALID_VALUE):
    return DossierCanonicalError(code, path=path)


def _object(value: object, names: set[str], path: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != names:
        raise _wrong(path)
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise _wrong(path, DossierInputCode.WRONG_TYPE)
    return value


def _challenge_dict(value: ChallengeKey) -> dict[str, str]:
    return {"challenge_id": value.challenge_id, "version": value.version}


def _challenge_load(value: object, path: str) -> ChallengeKey:
    fields = _object(value, {"challenge_id", "version"}, path)
    try:
        return ChallengeKey(fields["challenge_id"], fields["version"])
    except (TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _owner_dict(value: object) -> dict[str, object]:
    return {
        "challenge_key": _challenge_dict(value.scope_binding.challenge_key),
        "content_digest": value.content_digest,
        "object_id": value.object_id,
        "object_version": value.object_version,
        "ref_kind": value.ref_kind,
    }


def _owner_load(value: object, kind: str, path: str):
    fields = _object(
        value,
        {"challenge_key", "content_digest", "object_id", "object_version", "ref_kind"},
        path,
    )
    if fields["ref_kind"] != kind:
        raise _wrong(f"{path}/ref_kind", DossierInputCode.ROLE_CONFUSION)
    try:
        return owner_ref(
            kind,
            scope_binding=ChallengeScope(
                _challenge_load(fields["challenge_key"], f"{path}/challenge_key")
            ),
            object_id=fields["object_id"],
            object_version=fields["object_version"],
            content_digest=fields["content_digest"],
        )
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
        "schema_version": value.schema_version,
    }
    if type(value) is InstanceDistributionContractRef:
        result["expected_population_role"] = value.expected_population_role
    return result


def _top_load(value: object, expected: type, path: str):
    names = {
        "canonicalization_profile",
        "challenge_key",
        "content_digest",
        "object_id",
        "object_kind",
        "object_version",
        "schema_version",
    }
    if expected is InstanceDistributionContractRef:
        names.add("expected_population_role")
    fields = _object(value, names, path)
    if fields["object_kind"] != expected.OBJECT_KIND:
        raise _wrong(f"{path}/object_kind", DossierInputCode.ROLE_CONFUSION)
    common = (
        _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
        fields["object_id"],
        fields["object_version"],
        fields["schema_version"],
        fields["canonicalization_profile"],
        fields["content_digest"],
    )
    try:
        if expected is InstanceDistributionContractRef:
            return expected(*common, fields["expected_population_role"])
        return expected(*common)
    except (TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _runtime_ref_dict(value: object) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "record_type": value.record_type,
        "schema_version": value.schema_version,
    }


def _runtime_ref_load(value: object, expected: type, path: str):
    fields = _object(
        value,
        {
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "record_type",
            "schema_version",
        },
        path,
    )
    if fields["record_type"] != expected.RECORD_TYPE:
        raise _wrong(f"{path}/record_type", DossierInputCode.ROLE_CONFUSION)
    try:
        return expected(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            fields["content_digest"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _definition_dict(value: MeasurementDefinitionRef) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "definition_kind": value.definition_kind.value,
        "object_id": value.object_id,
        "object_version": value.object_version,
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
            "schema_version",
        },
        path,
    )
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
    except (TypeError, ValueError):
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
    except (TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _manifest_ref_dict(value: DossierEvidenceManifestRef) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_dict(value.challenge_key),
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
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _optional(value: object, encoder) -> object:
    return None if value is None else encoder(value)


def _subject_dict(value: EvidenceSubjectBindings) -> dict[str, object]:
    return {
        "candidate_output_ref": _optional(value.candidate_output_ref, _top_dict),
        "challenge_key": _challenge_dict(value.challenge_key),
        "claim_scope_ref": _owner_dict(value.claim_scope_ref),
        "generator_conformance_ref": _optional(
            value.generator_conformance_ref, _owner_dict
        ),
        "generator_ref": _optional(value.generator_ref, _owner_dict),
        "measurement_contract_ref": _optional(
            value.measurement_contract_ref, _runtime_ref_dict
        ),
        "measurement_evidence_ref": _optional(
            value.measurement_evidence_ref, _runtime_ref_dict
        ),
        "physical_system_ref": _optional(value.physical_system_ref, _top_dict),
        "reference_policy_ref": _optional(value.reference_policy_ref, _owner_dict),
        "representation_ref": _optional(value.representation_ref, _owner_dict),
        "sampling_plan_ref": _optional(value.sampling_plan_ref, _top_dict),
        "target_population_ref": _optional(value.target_population_ref, _top_dict),
    }


def _optional_load(value: object, loader, path: str):
    return None if value is None else loader(value, path)


def _subject_load(value: object, path: str) -> EvidenceSubjectBindings:
    names = {
        "candidate_output_ref",
        "challenge_key",
        "claim_scope_ref",
        "generator_conformance_ref",
        "generator_ref",
        "measurement_contract_ref",
        "measurement_evidence_ref",
        "physical_system_ref",
        "reference_policy_ref",
        "representation_ref",
        "sampling_plan_ref",
        "target_population_ref",
    }
    fields = _object(value, names, path)
    try:
        return EvidenceSubjectBindings(
            challenge_key=_challenge_load(
                fields["challenge_key"], f"{path}/challenge_key"
            ),
            claim_scope_ref=_owner_load(
                fields["claim_scope_ref"], "claim_scope", f"{path}/claim_scope_ref"
            ),
            physical_system_ref=_optional_load(
                fields["physical_system_ref"],
                lambda item, item_path: _top_load(
                    item, PhysicalSystemSpecRef, item_path
                ),
                f"{path}/physical_system_ref",
            ),
            candidate_output_ref=_optional_load(
                fields["candidate_output_ref"],
                lambda item, item_path: _top_load(
                    item, CandidateOutputContractRef, item_path
                ),
                f"{path}/candidate_output_ref",
            ),
            target_population_ref=_optional_load(
                fields["target_population_ref"],
                lambda item, item_path: _top_load(
                    item, InstanceDistributionContractRef, item_path
                ),
                f"{path}/target_population_ref",
            ),
            sampling_plan_ref=_optional_load(
                fields["sampling_plan_ref"],
                lambda item, item_path: _top_load(item, SamplingPlanRef, item_path),
                f"{path}/sampling_plan_ref",
            ),
            generator_ref=_optional_load(
                fields["generator_ref"],
                lambda item, item_path: _owner_load(item, "generator", item_path),
                f"{path}/generator_ref",
            ),
            generator_conformance_ref=_optional_load(
                fields["generator_conformance_ref"],
                lambda item, item_path: _owner_load(
                    item, "distribution_conformance", item_path
                ),
                f"{path}/generator_conformance_ref",
            ),
            reference_policy_ref=_optional_load(
                fields["reference_policy_ref"],
                lambda item, item_path: _owner_load(
                    item, "reference_qualification_policy", item_path
                ),
                f"{path}/reference_policy_ref",
            ),
            representation_ref=_optional_load(
                fields["representation_ref"],
                lambda item, item_path: _owner_load(item, "representation", item_path),
                f"{path}/representation_ref",
            ),
            measurement_contract_ref=_optional_load(
                fields["measurement_contract_ref"],
                lambda item, item_path: _runtime_ref_load(
                    item, MeasurementContractRef, item_path
                ),
                f"{path}/measurement_contract_ref",
            ),
            measurement_evidence_ref=_optional_load(
                fields["measurement_evidence_ref"],
                lambda item, item_path: _runtime_ref_load(
                    item, MeasurementQualificationEvidenceRef, item_path
                ),
                f"{path}/measurement_evidence_ref",
            ),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _claim_dict(value: EvidenceClaimBinding) -> dict[str, object]:
    return {
        "challenge_key": _challenge_dict(value.challenge_key),
        "claim_role": value.claim_role.value,
        "claim_scope_ref": _owner_dict(value.claim_scope_ref),
        "evidence_ref": _evidence_dict(value.evidence_ref),
    }


def _claim_load(value: object, path: str) -> EvidenceClaimBinding:
    fields = _object(
        value, {"challenge_key", "claim_role", "claim_scope_ref", "evidence_ref"}, path
    )
    try:
        return EvidenceClaimBinding(
            _challenge_load(fields["challenge_key"], f"{path}/challenge_key"),
            _evidence_load(fields["evidence_ref"], f"{path}/evidence_ref"),
            DossierClaimRole(fields["claim_role"]),
            _owner_load(
                fields["claim_scope_ref"], "claim_scope", f"{path}/claim_scope_ref"
            ),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


_STAT_DEFINITION_FIELDS = (
    "estimand_ref",
    "sampling_unit_ref",
    "resampling_unit_ref",
    "independence_unit_ref",
    "case_scope_ref",
    "stratum_ref",
    "decision_interval_method_ref",
    "dependence_assumption_ref",
    "applicability_test_ref",
    "reconstruction_case_interaction_ref",
    "reconstruction_stratum_interaction_ref",
    "stopping_rule_ref",
    "missing_cell_policy_ref",
    "evidence_set_ref",
)


def _statistical_dict(value: StatisticalScopeManifest) -> dict[str, object]:
    result = {
        "authority_status": value.authority_status.value,
        "challenge_key": _challenge_dict(value.challenge_key),
        "coverage_evidence_ref": _evidence_dict(value.coverage_evidence_ref),
        "uncertainty_policy_ref": _runtime_ref_dict(value.uncertainty_policy_ref),
    }
    result.update(
        {
            name: _definition_dict(getattr(value, name))
            for name in _STAT_DEFINITION_FIELDS
        }
    )
    return result


def _statistical_load(value: object, path: str) -> StatisticalScopeManifest:
    names = {
        "authority_status",
        "challenge_key",
        "coverage_evidence_ref",
        "uncertainty_policy_ref",
        *_STAT_DEFINITION_FIELDS,
    }
    fields = _object(value, names, path)
    kwargs = {
        name: _definition_load(fields[name], f"{path}/{name}")
        for name in _STAT_DEFINITION_FIELDS
    }
    try:
        return StatisticalScopeManifest(
            challenge_key=_challenge_load(
                fields["challenge_key"], f"{path}/challenge_key"
            ),
            authority_status=DependencePolicyAuthorityStatus(
                fields["authority_status"]
            ),
            uncertainty_policy_ref=_runtime_ref_load(
                fields["uncertainty_policy_ref"],
                UncertaintyPolicyRef,
                f"{path}/uncertainty_policy_ref",
            ),
            coverage_evidence_ref=_evidence_load(
                fields["coverage_evidence_ref"], f"{path}/coverage_evidence_ref"
            ),
            **kwargs,
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


_ACCOUNTING_OWNER_FIELDS = {
    "intended_unit_manifest_ref": "protected_unit_manifest",
    "realized_evidence_accounting_ref": "realized_evidence_accounting",
    "censoring_policy_ref": "censoring_policy",
    "missingness_adjustment_ref": "missingness_adjustment",
    "exclusion_assessment_ref": "exclusion_assessment",
}


def _accounting_dict(value: EvidenceAccountingManifest) -> dict[str, object]:
    result = {
        "attempts": [_attempt_dict(item) for item in value.attempts],
        "challenge_key": _challenge_dict(value.challenge_key),
        "sampling_plan_ref": _top_dict(value.sampling_plan_ref),
    }
    result.update(
        {name: _owner_dict(getattr(value, name)) for name in _ACCOUNTING_OWNER_FIELDS}
    )
    return result


def _accounting_load(value: object, path: str) -> EvidenceAccountingManifest:
    names = {
        "attempts",
        "challenge_key",
        "sampling_plan_ref",
        *_ACCOUNTING_OWNER_FIELDS,
    }
    fields = _object(value, names, path)
    kwargs = {
        name: _owner_load(fields[name], kind, f"{path}/{name}")
        for name, kind in _ACCOUNTING_OWNER_FIELDS.items()
    }
    try:
        return EvidenceAccountingManifest(
            challenge_key=_challenge_load(
                fields["challenge_key"], f"{path}/challenge_key"
            ),
            sampling_plan_ref=_top_load(
                fields["sampling_plan_ref"],
                SamplingPlanRef,
                f"{path}/sampling_plan_ref",
            ),
            attempts=tuple(
                _attempt_load(item, f"{path}/attempts/{index}")
                for index, item in enumerate(
                    _array(fields["attempts"], f"{path}/attempts")
                )
            ),
            **kwargs,
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


_SECRECY_OWNER_FIELDS = {
    "disclosure_policy_ref": "disclosure_policy",
    "blinding_policy_ref": "blinding_policy",
    "decontamination_evidence_ref": "audit_evidence",
    "role_separation_evidence_ref": "audit_evidence",
}


def _secrecy_dict(value: SecrecyEvidenceManifest) -> dict[str, object]:
    result = {"challenge_key": _challenge_dict(value.challenge_key)}
    result.update(
        {name: _owner_dict(getattr(value, name)) for name in _SECRECY_OWNER_FIELDS}
    )
    return result


def _secrecy_load(value: object, path: str) -> SecrecyEvidenceManifest:
    fields = _object(value, {"challenge_key", *_SECRECY_OWNER_FIELDS}, path)
    try:
        return SecrecyEvidenceManifest(
            challenge_key=_challenge_load(
                fields["challenge_key"], f"{path}/challenge_key"
            ),
            **{
                name: _owner_load(fields[name], kind, f"{path}/{name}")
                for name, kind in _SECRECY_OWNER_FIELDS.items()
            },
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def _limitation_dict(value: LimitationBinding) -> dict[str, object]:
    return {
        "affected_claim_roles": [item.value for item in value.affected_claim_roles],
        "affected_evidence_refs": [
            _evidence_dict(item) for item in value.affected_evidence_refs
        ],
        "challenge_key": _challenge_dict(value.challenge_key),
        "claim_scope_ref": _owner_dict(value.claim_scope_ref),
        "limitation_ref": _evidence_dict(value.limitation_ref),
    }


def _limitation_load(value: object, path: str) -> LimitationBinding:
    fields = _object(
        value,
        {
            "affected_claim_roles",
            "affected_evidence_refs",
            "challenge_key",
            "claim_scope_ref",
            "limitation_ref",
        },
        path,
    )
    try:
        return LimitationBinding(
            challenge_key=_challenge_load(
                fields["challenge_key"], f"{path}/challenge_key"
            ),
            limitation_ref=_evidence_load(
                fields["limitation_ref"], f"{path}/limitation_ref"
            ),
            affected_evidence_refs=tuple(
                _evidence_load(item, f"{path}/affected_evidence_refs/{index}")
                for index, item in enumerate(
                    _array(
                        fields["affected_evidence_refs"],
                        f"{path}/affected_evidence_refs",
                    )
                )
            ),
            affected_claim_roles=tuple(
                DossierClaimRole(item)
                for item in _array(
                    fields["affected_claim_roles"], f"{path}/affected_claim_roles"
                )
            ),
            claim_scope_ref=_owner_load(
                fields["claim_scope_ref"], "claim_scope", f"{path}/claim_scope_ref"
            ),
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong(path, DossierInputCode.WRONG_TYPE) from None


def evidence_manifest_payload(value: DossierEvidenceManifest) -> dict[str, object]:
    if type(value) is not DossierEvidenceManifest:
        raise _wrong("/", DossierInputCode.WRONG_TYPE)
    return {
        "accounting": _optional(value.accounting, _accounting_dict),
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_dict(value.challenge_key),
        "claim_bindings": [_claim_dict(item) for item in value.claim_bindings],
        "completeness": value.completeness.value,
        "evidence_refs": [_evidence_dict(item) for item in value.evidence_refs],
        "limitations": [_limitation_dict(item) for item in value.limitations],
        "manifest_id": value.manifest_id,
        "manifest_version": value.manifest_version,
        "origin": value.origin.value,
        "record_type": "dossier_evidence_manifest",
        "schema_version": value.schema_version,
        "secrecy": _optional(value.secrecy, _secrecy_dict),
        "slot": value.slot.value,
        "statistical_scope": _optional(value.statistical_scope, _statistical_dict),
        "subject_bindings": _optional(value.subject_bindings, _subject_dict),
        "supersedes": _optional(value.supersedes, _manifest_ref_dict),
    }


def evidence_manifest_bytes(value: DossierEvidenceManifest) -> bytes:
    try:
        payload = json.dumps(
            evidence_manifest_payload(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeError):
        raise _wrong("/") from None
    document = EVIDENCE_MANIFEST_DOCUMENT_HEADER + payload
    if len(document) > MAX_EVIDENCE_MANIFEST_DOCUMENT_BYTES:
        raise _wrong("/", DossierInputCode.SIZE_LIMIT)
    return document


def evidence_manifest_digest(value: DossierEvidenceManifest) -> str:
    return "sha256:" + hashlib.sha256(evidence_manifest_bytes(value)).hexdigest()


def evidence_manifest_ref(value: DossierEvidenceManifest) -> DossierEvidenceManifestRef:
    origin = StructuralOrigin.FIXTURE_ONLY if value.fixture_derived else value.origin
    return DossierEvidenceManifestRef(
        value.challenge_key,
        value.slot,
        value.manifest_id,
        value.manifest_version,
        evidence_manifest_digest(value),
        origin,
        value.schema_version,
        value.canonicalization_profile,
    )


def dossier_evidence_ref(value: DossierEvidenceManifest) -> DossierEvidenceRef:
    origin = StructuralOrigin.FIXTURE_ONLY if value.fixture_derived else value.origin
    return DossierEvidenceRef(
        value.challenge_key,
        DOSSIER_PRIMARY_EVIDENCE_CLASS[value.slot],
        value.manifest_id,
        value.manifest_version,
        evidence_manifest_digest(value),
        origin,
    )


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise _wrong("/", DossierInputCode.DUPLICATE_IDENTITY)
        result[key] = value
    return result


def load_evidence_manifest(document: bytes) -> DossierEvidenceManifest:
    if type(document) is not bytes:
        raise _wrong("/", DossierInputCode.WRONG_TYPE)
    if len(document) > MAX_EVIDENCE_MANIFEST_DOCUMENT_BYTES:
        raise _wrong("/", DossierInputCode.SIZE_LIMIT)
    if not document.startswith(EVIDENCE_MANIFEST_DOCUMENT_HEADER):
        raise _wrong("/")
    payload = document[len(EVIDENCE_MANIFEST_DOCUMENT_HEADER) :]
    try:
        decoded = json.loads(
            payload.decode("utf-8", errors="strict"), object_pairs_hook=_pairs
        )
    except DossierCanonicalError:
        raise
    except (json.JSONDecodeError, UnicodeError):
        raise _wrong("/") from None
    fields = _object(
        decoded,
        {
            "accounting",
            "canonicalization_profile",
            "challenge_key",
            "claim_bindings",
            "completeness",
            "evidence_refs",
            "limitations",
            "manifest_id",
            "manifest_version",
            "origin",
            "record_type",
            "schema_version",
            "secrecy",
            "slot",
            "statistical_scope",
            "subject_bindings",
            "supersedes",
        },
        "/",
    )
    if fields["record_type"] != "dossier_evidence_manifest":
        raise _wrong("/record_type")
    try:
        result = DossierEvidenceManifest(
            challenge_key=_challenge_load(fields["challenge_key"], "/challenge_key"),
            slot=DossierSlot(fields["slot"]),
            manifest_id=fields["manifest_id"],
            manifest_version=fields["manifest_version"],
            completeness=EvidenceCompleteness(fields["completeness"]),
            origin=StructuralOrigin(fields["origin"]),
            subject_bindings=_optional_load(
                fields["subject_bindings"], _subject_load, "/subject_bindings"
            ),
            evidence_refs=tuple(
                _evidence_load(item, f"/evidence_refs/{index}")
                for index, item in enumerate(
                    _array(fields["evidence_refs"], "/evidence_refs")
                )
            ),
            claim_bindings=tuple(
                _claim_load(item, f"/claim_bindings/{index}")
                for index, item in enumerate(
                    _array(fields["claim_bindings"], "/claim_bindings")
                )
            ),
            statistical_scope=_optional_load(
                fields["statistical_scope"], _statistical_load, "/statistical_scope"
            ),
            accounting=_optional_load(
                fields["accounting"], _accounting_load, "/accounting"
            ),
            secrecy=_optional_load(fields["secrecy"], _secrecy_load, "/secrecy"),
            limitations=tuple(
                _limitation_load(item, f"/limitations/{index}")
                for index, item in enumerate(
                    _array(fields["limitations"], "/limitations")
                )
            ),
            supersedes=_optional_load(
                fields["supersedes"], _manifest_ref_load, "/supersedes"
            ),
            schema_version=fields["schema_version"],
            canonicalization_profile=fields["canonicalization_profile"],
        )
    except DossierCanonicalError:
        raise
    except (DossierValidationError, TypeError, ValueError):
        raise _wrong("/", DossierInputCode.WRONG_TYPE) from None
    if evidence_manifest_bytes(result) != document:
        raise _wrong("/", DossierInputCode.DIGEST_MISMATCH)
    return result


__all__ = (
    "MAX_EVIDENCE_MANIFEST_DOCUMENT_BYTES",
    "dossier_evidence_ref",
    "evidence_manifest_bytes",
    "evidence_manifest_digest",
    "evidence_manifest_payload",
    "evidence_manifest_ref",
    "load_evidence_manifest",
)
