"""Strict canonical JSON profile for implemented B-05 authoring objects."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from carbon.evaluation.refs import ReferencePolicyRef
from carbon.registry.model import ChallengeKey
from carbon.scoring.model import ScorePackPin

from .enums import (
    A5DestinationKind,
    DependenceShortcutKind,
    MeasurementClaimClass,
    MeasurementDefinitionKind,
    MeasurementEvidenceRole,
    MeasurementRole,
    ScientificValueState,
    ScoreAggregationRole,
    ScoreDisclosureClass,
    ScoreEligibilityRole,
    ScoreRankingRole,
    ScoreScalarKind,
    ScoreUseRole,
    StratumApplicabilityStatus,
)
from .errors import MeasurementCanonicalError, MeasurementInputCode
from .model import (
    DependenceShortcutBinding,
    MeasurementAuthoringObject,
    MeasurementContract,
    MeasurementEvidenceItem,
    MeasurementQualificationEvidence,
    ReconstructionEvidencePolicy,
    ScientificValueBinding,
    ScorePackAuthoringContract,
    ScorePackInputBinding,
    StratumApplicabilityBinding,
    StratumEvidenceMinimumBinding,
    UncertaintyComponentBinding,
    UncertaintyPolicy,
    UncertaintyPolicyBinding,
)
from .refs import (
    MEASUREMENT_DOCUMENT_HEADER,
    MeasurementContractRef,
    MeasurementDefinitionRef,
    MeasurementQualificationEvidenceRef,
    ReconstructionEvidencePolicyRef,
    ScorePackAuthoringContractRef,
    UncertaintyPolicyRef,
)

MAX_MEASUREMENT_DOCUMENT_BYTES = 1024 * 1024


def _wrong(path: str, code: MeasurementInputCode = MeasurementInputCode.INVALID_VALUE):
    return MeasurementCanonicalError(code, path=path)


def _challenge_to_dict(value: ChallengeKey) -> dict[str, str]:
    return {"challenge_id": value.challenge_id, "version": value.version}


def _challenge_from_dict(value: object, path: str) -> ChallengeKey:
    fields = _object(value, {"challenge_id", "version"}, path)
    try:
        return ChallengeKey(fields["challenge_id"], fields["version"])
    except (TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _definition_to_dict(value: MeasurementDefinitionRef) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "definition_kind": value.definition_kind.value,
        "object_id": value.object_id,
        "object_version": value.object_version,
        "ref_type": value.ref_type,
        "schema_version": value.schema_version,
    }


def _definition_from_dict(value: object, path: str) -> MeasurementDefinitionRef:
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
        raise _wrong(f"{path}/ref_type")
    try:
        return MeasurementDefinitionRef(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            MeasurementDefinitionKind(fields["definition_kind"]),
            fields["object_id"],
            fields["object_version"],
            fields["content_digest"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _top_ref_to_dict(value: object) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "ref_type": value.ref_type,
        "schema_version": value.schema_version,
    }


def _top_ref_from_dict(value: object, expected: type, path: str):
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
    if fields["ref_type"] != f"{expected.RECORD_TYPE}_ref":
        raise _wrong(f"{path}/ref_type")
    try:
        return expected(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            fields["content_digest"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _reference_policy_to_dict(value: ReferencePolicyRef) -> dict[str, object]:
    return {
        "canonicalization_profile": value.canonicalization_profile,
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "content_digest": value.content_digest,
        "ref_type": value.ref_type,
        "schema_version": value.schema_version,
    }


def _reference_policy_from_dict(value: object, path: str) -> ReferencePolicyRef:
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
    if fields["ref_type"] != "reference_policy_ref":
        raise _wrong(f"{path}/ref_type")
    try:
        return ReferencePolicyRef(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            fields["content_digest"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _score_pack_pin_to_dict(value: ScorePackPin) -> dict[str, object]:
    return {
        "challenge_key": _challenge_to_dict(value.challenge_key),
        "fixture_origin": value.fixture_origin,
        "generator_digest_required": value.generator_digest_required,
        "generator_version_required": value.generator_version_required,
        "numerical_profile": value.numerical_profile,
        "schema_version": value.schema_version,
        "scoring_digest": value.scoring_digest,
        "scoring_version": value.scoring_version,
    }


def _score_pack_pin_from_dict(value: object, path: str) -> ScorePackPin:
    fields = _object(
        value,
        {
            "challenge_key",
            "fixture_origin",
            "generator_digest_required",
            "generator_version_required",
            "numerical_profile",
            "schema_version",
            "scoring_digest",
            "scoring_version",
        },
        path,
    )
    try:
        return ScorePackPin(
            _challenge_from_dict(fields["challenge_key"], f"{path}/challenge_key"),
            fields["scoring_version"],
            fields["scoring_digest"],
            fields["generator_version_required"],
            fields["generator_digest_required"],
            fields["schema_version"],
            fields["numerical_profile"],
            fields["fixture_origin"],
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _score_binding_to_dict(value: ScorePackInputBinding) -> dict[str, object]:
    return {
        "admissibility_policy_ref": _definition_to_dict(value.admissibility_policy_ref),
        "admissibility_evidence_ref": _definition_to_dict(
            value.admissibility_evidence_ref
        ),
        "aggregation_role": value.aggregation_role.value,
        "applicability_evidence_ref": _definition_to_dict(
            value.applicability_evidence_ref
        ),
        "case_scope_ref": _definition_to_dict(value.case_scope_ref),
        "destination_id": value.destination_id,
        "destination_kind": value.destination_kind.value,
        "disclosure_class": value.disclosure_class.value,
        "disclosure_policy_ref": _definition_to_dict(value.disclosure_policy_ref),
        "eligibility_role": value.eligibility_role.value,
        "estimand_ref": _definition_to_dict(value.estimand_ref),
        "fixture_origin": value.fixture_origin,
        "input_key": value.input_key,
        "measurement_contract_ref": _top_ref_to_dict(value.measurement_contract_ref),
        "measurement_output_ref": _definition_to_dict(value.measurement_output_ref),
        "provenance_ref": _definition_to_dict(value.provenance_ref),
        "qualification_ref": _definition_to_dict(value.qualification_ref),
        "ranking_role": value.ranking_role.value,
        "scalar_kind": value.scalar_kind.value,
        "stratum_ref": _definition_to_dict(value.stratum_ref),
        "uncertainty_policy_ref": _top_ref_to_dict(value.uncertainty_policy_ref),
        "use_role": value.use_role.value,
    }


def _score_binding_from_dict(value: object, path: str) -> ScorePackInputBinding:
    names = {
        "admissibility_policy_ref",
        "admissibility_evidence_ref",
        "aggregation_role",
        "applicability_evidence_ref",
        "case_scope_ref",
        "destination_id",
        "destination_kind",
        "disclosure_class",
        "disclosure_policy_ref",
        "eligibility_role",
        "estimand_ref",
        "fixture_origin",
        "input_key",
        "measurement_contract_ref",
        "measurement_output_ref",
        "provenance_ref",
        "qualification_ref",
        "ranking_role",
        "scalar_kind",
        "stratum_ref",
        "uncertainty_policy_ref",
        "use_role",
    }
    fields = _object(value, names, path)
    try:
        return ScorePackInputBinding(
            measurement_contract_ref=_top_ref_from_dict(
                fields["measurement_contract_ref"],
                MeasurementContractRef,
                f"{path}/measurement_contract_ref",
            ),
            measurement_output_ref=_definition_from_dict(
                fields["measurement_output_ref"], f"{path}/measurement_output_ref"
            ),
            input_key=fields["input_key"],
            scalar_kind=ScoreScalarKind(fields["scalar_kind"]),
            use_role=ScoreUseRole(fields["use_role"]),
            estimand_ref=_definition_from_dict(
                fields["estimand_ref"], f"{path}/estimand_ref"
            ),
            case_scope_ref=_definition_from_dict(
                fields["case_scope_ref"], f"{path}/case_scope_ref"
            ),
            stratum_ref=_definition_from_dict(
                fields["stratum_ref"], f"{path}/stratum_ref"
            ),
            uncertainty_policy_ref=_top_ref_from_dict(
                fields["uncertainty_policy_ref"],
                UncertaintyPolicyRef,
                f"{path}/uncertainty_policy_ref",
            ),
            admissibility_policy_ref=_definition_from_dict(
                fields["admissibility_policy_ref"],
                f"{path}/admissibility_policy_ref",
            ),
            admissibility_evidence_ref=_definition_from_dict(
                fields["admissibility_evidence_ref"],
                f"{path}/admissibility_evidence_ref",
            ),
            aggregation_role=ScoreAggregationRole(fields["aggregation_role"]),
            ranking_role=ScoreRankingRole(fields["ranking_role"]),
            disclosure_class=ScoreDisclosureClass(fields["disclosure_class"]),
            disclosure_policy_ref=_definition_from_dict(
                fields["disclosure_policy_ref"], f"{path}/disclosure_policy_ref"
            ),
            eligibility_role=ScoreEligibilityRole(fields["eligibility_role"]),
            destination_kind=A5DestinationKind(fields["destination_kind"]),
            destination_id=fields["destination_id"],
            applicability_evidence_ref=_definition_from_dict(
                fields["applicability_evidence_ref"],
                f"{path}/applicability_evidence_ref",
            ),
            qualification_ref=_definition_from_dict(
                fields["qualification_ref"], f"{path}/qualification_ref"
            ),
            provenance_ref=_definition_from_dict(
                fields["provenance_ref"], f"{path}/provenance_ref"
            ),
            fixture_origin=fields["fixture_origin"],
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _scientific_value_to_dict(value: ScientificValueBinding) -> dict[str, object]:
    return {
        "state": value.state.value,
        "value_ref": (
            None if value.value_ref is None else _definition_to_dict(value.value_ref)
        ),
    }


def _scientific_value_from_dict(value: object, path: str) -> ScientificValueBinding:
    fields = _object(value, {"state", "value_ref"}, path)
    try:
        state = ScientificValueState(fields["state"])
        ref = (
            None
            if fields["value_ref"] is None
            else _definition_from_dict(fields["value_ref"], f"{path}/value_ref")
        )
        return ScientificValueBinding(state, ref)
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _uncertainty_to_dict(value: UncertaintyPolicyBinding) -> dict[str, object]:
    return {
        "policy_ref": (
            None if value.policy_ref is None else _top_ref_to_dict(value.policy_ref)
        ),
        "state": value.state.value,
    }


def _uncertainty_from_dict(value: object, path: str) -> UncertaintyPolicyBinding:
    fields = _object(value, {"policy_ref", "state"}, path)
    try:
        state = ScientificValueState(fields["state"])
        ref = (
            None
            if fields["policy_ref"] is None
            else _top_ref_from_dict(
                fields["policy_ref"], UncertaintyPolicyRef, f"{path}/policy_ref"
            )
        )
        return UncertaintyPolicyBinding(state, ref)
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _component_to_dict(value: UncertaintyComponentBinding) -> dict[str, object]:
    return {
        "component_ref": (
            None
            if value.component_ref is None
            else _definition_to_dict(value.component_ref)
        ),
        "state": value.state.value,
    }


def _component_from_dict(value: object, path: str) -> UncertaintyComponentBinding:
    fields = _object(value, {"component_ref", "state"}, path)
    try:
        return UncertaintyComponentBinding(
            ScientificValueState(fields["state"]),
            (
                None
                if fields["component_ref"] is None
                else _definition_from_dict(
                    fields["component_ref"], f"{path}/component_ref"
                )
            ),
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _stratum_minimum_to_dict(
    value: StratumEvidenceMinimumBinding,
) -> dict[str, object]:
    return {
        "minimum_binding": _component_to_dict(value.minimum_binding),
        "stratum_ref": _definition_to_dict(value.stratum_ref),
    }


def _stratum_minimum_from_dict(
    value: object, path: str
) -> StratumEvidenceMinimumBinding:
    fields = _object(value, {"minimum_binding", "stratum_ref"}, path)
    try:
        return StratumEvidenceMinimumBinding(
            _definition_from_dict(fields["stratum_ref"], f"{path}/stratum_ref"),
            _component_from_dict(fields["minimum_binding"], f"{path}/minimum_binding"),
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _shortcut_to_dict(value: DependenceShortcutBinding) -> dict[str, object]:
    return {
        "applicability_test_ref": _definition_to_dict(value.applicability_test_ref),
        "assumption_ref": _definition_to_dict(value.assumption_ref),
        "case_scope_refs": [
            _definition_to_dict(item) for item in value.case_scope_refs
        ],
        "challenger_evidence_ref": _definition_to_dict(value.challenger_evidence_ref),
        "dossier_qualification_ref": _definition_to_dict(
            value.dossier_qualification_ref
        ),
        "fixture_origin": value.fixture_origin,
        "incumbent_evidence_ref": _definition_to_dict(value.incumbent_evidence_ref),
        "shortcut_id": value.shortcut_id,
        "shortcut_kind": value.shortcut_kind.value,
        "shortcut_version": value.shortcut_version,
        "stratum_scope_refs": [
            _definition_to_dict(item) for item in value.stratum_scope_refs
        ],
    }


def _shortcut_from_dict(value: object, path: str) -> DependenceShortcutBinding:
    fields = _object(
        value,
        {
            "applicability_test_ref",
            "assumption_ref",
            "case_scope_refs",
            "challenger_evidence_ref",
            "dossier_qualification_ref",
            "fixture_origin",
            "incumbent_evidence_ref",
            "shortcut_id",
            "shortcut_kind",
            "shortcut_version",
            "stratum_scope_refs",
        },
        path,
    )
    try:
        return DependenceShortcutBinding(
            fields["shortcut_id"],
            fields["shortcut_version"],
            DependenceShortcutKind(fields["shortcut_kind"]),
            _definition_from_dict(
                fields["incumbent_evidence_ref"],
                f"{path}/incumbent_evidence_ref",
            ),
            _definition_from_dict(
                fields["challenger_evidence_ref"],
                f"{path}/challenger_evidence_ref",
            ),
            tuple(
                _definition_from_dict(item, f"{path}/case_scope_refs/{index}")
                for index, item in enumerate(
                    _array(fields["case_scope_refs"], f"{path}/case_scope_refs")
                )
            ),
            tuple(
                _definition_from_dict(item, f"{path}/stratum_scope_refs/{index}")
                for index, item in enumerate(
                    _array(fields["stratum_scope_refs"], f"{path}/stratum_scope_refs")
                )
            ),
            _definition_from_dict(fields["assumption_ref"], f"{path}/assumption_ref"),
            _definition_from_dict(
                fields["applicability_test_ref"], f"{path}/applicability_test_ref"
            ),
            _definition_from_dict(
                fields["dossier_qualification_ref"],
                f"{path}/dossier_qualification_ref",
            ),
            fields["fixture_origin"],
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _stratum_to_dict(value: StratumApplicabilityBinding) -> dict[str, object]:
    return {
        "evidence_or_reason_ref": (
            None
            if value.evidence_or_reason_ref is None
            else _definition_to_dict(value.evidence_or_reason_ref)
        ),
        "status": value.status.value,
        "stratum_ref": _definition_to_dict(value.stratum_ref),
    }


def _stratum_from_dict(value: object, path: str) -> StratumApplicabilityBinding:
    fields = _object(value, {"evidence_or_reason_ref", "status", "stratum_ref"}, path)
    try:
        detail = (
            None
            if fields["evidence_or_reason_ref"] is None
            else _definition_from_dict(
                fields["evidence_or_reason_ref"], f"{path}/evidence_or_reason_ref"
            )
        )
        return StratumApplicabilityBinding(
            _definition_from_dict(fields["stratum_ref"], f"{path}/stratum_ref"),
            StratumApplicabilityStatus(fields["status"]),
            detail,
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def _evidence_item_to_dict(value: MeasurementEvidenceItem) -> dict[str, object]:
    return {
        "case_scope_refs": [
            _definition_to_dict(item) for item in value.case_scope_refs
        ],
        "evidence_id": value.evidence_id,
        "fixture_origin": value.fixture_origin,
        "role": value.role.value,
        "source_ref": _definition_to_dict(value.source_ref),
        "stratum_scope_refs": [
            _definition_to_dict(item) for item in value.stratum_scope_refs
        ],
        "supported_claims": [item.value for item in value.supported_claims],
        "unsupported_claims": [item.value for item in value.unsupported_claims],
    }


def _evidence_item_from_dict(value: object, path: str) -> MeasurementEvidenceItem:
    fields = _object(
        value,
        {
            "case_scope_refs",
            "evidence_id",
            "fixture_origin",
            "role",
            "source_ref",
            "stratum_scope_refs",
            "supported_claims",
            "unsupported_claims",
        },
        path,
    )
    try:
        return MeasurementEvidenceItem(
            fields["evidence_id"],
            _definition_from_dict(fields["source_ref"], f"{path}/source_ref"),
            MeasurementEvidenceRole(fields["role"]),
            tuple(
                MeasurementClaimClass(item)
                for item in _array(
                    fields["supported_claims"], f"{path}/supported_claims"
                )
            ),
            tuple(
                MeasurementClaimClass(item)
                for item in _array(
                    fields["unsupported_claims"], f"{path}/unsupported_claims"
                )
            ),
            tuple(
                _definition_from_dict(item, f"{path}/case_scope_refs/{index}")
                for index, item in enumerate(
                    _array(fields["case_scope_refs"], f"{path}/case_scope_refs")
                )
            ),
            tuple(
                _definition_from_dict(item, f"{path}/stratum_scope_refs/{index}")
                for index, item in enumerate(
                    _array(fields["stratum_scope_refs"], f"{path}/stratum_scope_refs")
                )
            ),
            fields["fixture_origin"],
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE) from None


def canonical_payload(value: MeasurementAuthoringObject) -> dict[str, object]:
    """Return the complete JSON-safe payload for one exact implemented object."""

    if type(value) is MeasurementContract:
        return {
            "aggregation_ref": _definition_to_dict(value.aggregation_ref),
            "applicability_policy_ref": _definition_to_dict(
                value.applicability_policy_ref
            ),
            "canonicalization_profile": value.canonicalization_profile,
            "challenge_key": _challenge_to_dict(value.challenge_key),
            "coordinate_system_ref": _definition_to_dict(value.coordinate_system_ref),
            "discretization_ref": _definition_to_dict(value.discretization_ref),
            "fixture_origin": value.fixture_origin,
            "implementation_refs": [
                _definition_to_dict(item) for item in value.implementation_refs
            ],
            "intended_role": value.intended_role.value,
            "known_limitation_refs": [
                _definition_to_dict(item) for item in value.known_limitation_refs
            ],
            "measurement_id": value.measurement_id,
            "measurement_version": value.measurement_version,
            "normalization_ref": _definition_to_dict(value.normalization_ref),
            "numerical_floor_binding": _scientific_value_to_dict(
                value.numerical_floor_binding
            ),
            "numerical_operator_ref": _definition_to_dict(value.numerical_operator_ref),
            "observable_refs": [
                _definition_to_dict(item) for item in value.observable_refs
            ],
            "precision_ref": _definition_to_dict(value.precision_ref),
            "record_type": value.RECORD_TYPE,
            "reference_policy_ref": _reference_policy_to_dict(
                value.reference_policy_ref
            ),
            "sampling_quadrature_ref": _definition_to_dict(
                value.sampling_quadrature_ref
            ),
            "schema_version": value.schema_version,
            "scientific_property_ref": _definition_to_dict(
                value.scientific_property_ref
            ),
            "stratum_applicability": [
                _stratum_to_dict(item) for item in value.stratum_applicability
            ],
            "uncertainty_policy_binding": _uncertainty_to_dict(
                value.uncertainty_policy_binding
            ),
            "unit_ref": _definition_to_dict(value.unit_ref),
        }
    if type(value) is MeasurementQualificationEvidence:
        return {
            "canonicalization_profile": value.canonicalization_profile,
            "challenge_key": _challenge_to_dict(value.challenge_key),
            "evidence_id": value.evidence_id,
            "evidence_items": [
                _evidence_item_to_dict(item) for item in value.evidence_items
            ],
            "evidence_version": value.evidence_version,
            "fixture_origin": value.fixture_origin,
            "measurement_contract_ref": _top_ref_to_dict(
                value.measurement_contract_ref
            ),
            "record_type": value.RECORD_TYPE,
            "schema_version": value.schema_version,
        }
    if type(value) is UncertaintyPolicy:
        return {
            "canonicalization_profile": value.canonicalization_profile,
            "censoring_accounting_binding": _component_to_dict(
                value.censoring_accounting_binding
            ),
            "challenge_key": _challenge_to_dict(value.challenge_key),
            "common_case_pairing_binding": _component_to_dict(
                value.common_case_pairing_binding
            ),
            "dependence_shortcuts": [
                _shortcut_to_dict(item) for item in value.dependence_shortcuts
            ],
            "estimand_binding": _component_to_dict(value.estimand_binding),
            "evidence_extension_rule_binding": _component_to_dict(
                value.evidence_extension_rule_binding
            ),
            "execution_dependence_binding": _component_to_dict(
                value.execution_dependence_binding
            ),
            "fixture_origin": value.fixture_origin,
            "independence_unit_binding": _component_to_dict(
                value.independence_unit_binding
            ),
            "interval_error_control_binding": _component_to_dict(
                value.interval_error_control_binding
            ),
            "joint_reference_uncertainty_binding": _component_to_dict(
                value.joint_reference_uncertainty_binding
            ),
            "measurement_contract_ref": _top_ref_to_dict(
                value.measurement_contract_ref
            ),
            "measurement_output_binding": _component_to_dict(
                value.measurement_output_binding
            ),
            "minimum_evidence_binding": _component_to_dict(
                value.minimum_evidence_binding
            ),
            "multiplicity_policy_binding": _component_to_dict(
                value.multiplicity_policy_binding
            ),
            "policy_id": value.policy_id,
            "policy_version": value.policy_version,
            "reconstruction_case_interaction_binding": _component_to_dict(
                value.reconstruction_case_interaction_binding
            ),
            "reconstruction_stratum_interaction_binding": _component_to_dict(
                value.reconstruction_stratum_interaction_binding
            ),
            "record_type": value.RECORD_TYPE,
            "reference_candidate_covariance_binding": _component_to_dict(
                value.reference_candidate_covariance_binding
            ),
            "representation_dependence_binding": _component_to_dict(
                value.representation_dependence_binding
            ),
            "resampling_unit_binding": _component_to_dict(
                value.resampling_unit_binding
            ),
            "sampling_unit_binding": _component_to_dict(value.sampling_unit_binding),
            "schema_version": value.schema_version,
            "stopping_rule_binding": _component_to_dict(value.stopping_rule_binding),
            "stratum_minimum_bindings": [
                _stratum_minimum_to_dict(item)
                for item in value.stratum_minimum_bindings
            ],
        }
    if type(value) is ReconstructionEvidencePolicy:
        return {
            "audit_selection_policy_binding": _component_to_dict(
                value.audit_selection_policy_binding
            ),
            "build_completeness_criteria_binding": _component_to_dict(
                value.build_completeness_criteria_binding
            ),
            "canonicalization_profile": value.canonicalization_profile,
            "case_coverage_requirement_binding": _component_to_dict(
                value.case_coverage_requirement_binding
            ),
            "challenge_key": _challenge_to_dict(value.challenge_key),
            "complete_base_minimum_binding": _component_to_dict(
                value.complete_base_minimum_binding
            ),
            "construction_family_ref": _definition_to_dict(
                value.construction_family_ref
            ),
            "error_control_binding": _component_to_dict(value.error_control_binding),
            "evidence_extension_rule_binding": _component_to_dict(
                value.evidence_extension_rule_binding
            ),
            "fixture_origin": value.fixture_origin,
            "frozen_artifact_reuse_policy_binding": _component_to_dict(
                value.frozen_artifact_reuse_policy_binding
            ),
            "minimum_resolvable_improvement_binding": _component_to_dict(
                value.minimum_resolvable_improvement_binding
            ),
            "nomination_criteria_binding": _component_to_dict(
                value.nomination_criteria_binding
            ),
            "policy_id": value.policy_id,
            "policy_version": value.policy_version,
            "power_requirement_binding": _component_to_dict(
                value.power_requirement_binding
            ),
            "promotion_criteria_binding": _component_to_dict(
                value.promotion_criteria_binding
            ),
            "record_type": value.RECORD_TYPE,
            "schema_version": value.schema_version,
            "scientific_stopping_rule_binding": _component_to_dict(
                value.scientific_stopping_rule_binding
            ),
            "sequential_stopping_rule_binding": _component_to_dict(
                value.sequential_stopping_rule_binding
            ),
            "stability_audit_rate_binding": _component_to_dict(
                value.stability_audit_rate_binding
            ),
            "stratum_coverage_requirement_binding": _component_to_dict(
                value.stratum_coverage_requirement_binding
            ),
        }
    if type(value) is ScorePackAuthoringContract:
        return {
            "canonicalization_profile": value.canonicalization_profile,
            "challenge_key": _challenge_to_dict(value.challenge_key),
            "contract_id": value.contract_id,
            "contract_version": value.contract_version,
            "fixture_origin": value.fixture_origin,
            "input_bindings": [
                _score_binding_to_dict(item) for item in value.input_bindings
            ],
            "record_type": value.RECORD_TYPE,
            "schema_version": value.schema_version,
            "score_pack_pin": _score_pack_pin_to_dict(value.score_pack_pin),
            "threshold_authority_binding": _component_to_dict(
                value.threshold_authority_binding
            ),
            "transform_authority_binding": _component_to_dict(
                value.transform_authority_binding
            ),
            "weight_authority_binding": _component_to_dict(
                value.weight_authority_binding
            ),
        }
    raise _wrong("/record_type", MeasurementInputCode.WRONG_TYPE)


def canonical_bytes(value: MeasurementAuthoringObject) -> bytes:
    payload = json.dumps(
        canonical_payload(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    document = MEASUREMENT_DOCUMENT_HEADER + payload
    if len(document) > MAX_MEASUREMENT_DOCUMENT_BYTES:
        raise _wrong("/", MeasurementInputCode.SIZE_LIMIT)
    return document


def canonical_digest(value: MeasurementAuthoringObject) -> str:
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def measurement_ref(value: MeasurementAuthoringObject):
    digest = canonical_digest(value)
    if type(value) is MeasurementContract:
        return MeasurementContractRef(value.challenge_key, digest)
    if type(value) is MeasurementQualificationEvidence:
        return MeasurementQualificationEvidenceRef(value.challenge_key, digest)
    if type(value) is UncertaintyPolicy:
        return UncertaintyPolicyRef(value.challenge_key, digest)
    if type(value) is ReconstructionEvidencePolicy:
        return ReconstructionEvidencePolicyRef(value.challenge_key, digest)
    if type(value) is ScorePackAuthoringContract:
        return ScorePackAuthoringContractRef(value.challenge_key, digest)
    raise _wrong("/record_type", MeasurementInputCode.WRONG_TYPE)


def load_canonical_document(source: object) -> MeasurementAuthoringObject:
    if type(source) is not bytes:
        raise _wrong("/", MeasurementInputCode.WRONG_TYPE)
    if len(source) > MAX_MEASUREMENT_DOCUMENT_BYTES:
        raise _wrong("/", MeasurementInputCode.SIZE_LIMIT)
    if not source.startswith(MEASUREMENT_DOCUMENT_HEADER):
        raise _wrong("/")
    raw = source[len(MEASUREMENT_DOCUMENT_HEADER) :]
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except MeasurementCanonicalError:
        raise
    except (TypeError, UnicodeDecodeError, ValueError):
        raise _wrong("/") from None
    fields = _object(payload, None, "/")
    record_type = fields.get("record_type")
    if record_type == MeasurementContract.RECORD_TYPE:
        value = _measurement_from_dict(fields)
    elif record_type == MeasurementQualificationEvidence.RECORD_TYPE:
        value = _qualification_from_dict(fields)
    elif record_type == UncertaintyPolicy.RECORD_TYPE:
        value = _uncertainty_policy_from_dict(fields)
    elif record_type == ReconstructionEvidencePolicy.RECORD_TYPE:
        value = _reconstruction_policy_from_dict(fields)
    elif record_type == ScorePackAuthoringContract.RECORD_TYPE:
        value = _score_pack_authoring_from_dict(fields)
    else:
        raise _wrong("/record_type", MeasurementInputCode.UNKNOWN_OBJECT)
    if canonical_bytes(value) != source:
        raise _wrong("/")
    return value


def _measurement_from_dict(fields: Mapping[str, Any]) -> MeasurementContract:
    names = {
        "aggregation_ref",
        "applicability_policy_ref",
        "canonicalization_profile",
        "challenge_key",
        "coordinate_system_ref",
        "discretization_ref",
        "fixture_origin",
        "implementation_refs",
        "intended_role",
        "known_limitation_refs",
        "measurement_id",
        "measurement_version",
        "normalization_ref",
        "numerical_floor_binding",
        "numerical_operator_ref",
        "observable_refs",
        "precision_ref",
        "record_type",
        "reference_policy_ref",
        "sampling_quadrature_ref",
        "schema_version",
        "scientific_property_ref",
        "stratum_applicability",
        "uncertainty_policy_binding",
        "unit_ref",
    }
    fields = _object(fields, names, "/")
    try:
        return MeasurementContract(
            _challenge_from_dict(fields["challenge_key"], "/challenge_key"),
            fields["measurement_id"],
            fields["measurement_version"],
            _definition_from_dict(
                fields["scientific_property_ref"], "/scientific_property_ref"
            ),
            tuple(
                _definition_from_dict(item, f"/observable_refs/{index}")
                for index, item in enumerate(
                    _array(fields["observable_refs"], "/observable_refs")
                )
            ),
            _definition_from_dict(
                fields["coordinate_system_ref"], "/coordinate_system_ref"
            ),
            _definition_from_dict(fields["unit_ref"], "/unit_ref"),
            _definition_from_dict(
                fields["numerical_operator_ref"], "/numerical_operator_ref"
            ),
            _definition_from_dict(fields["discretization_ref"], "/discretization_ref"),
            _definition_from_dict(
                fields["sampling_quadrature_ref"], "/sampling_quadrature_ref"
            ),
            _definition_from_dict(fields["normalization_ref"], "/normalization_ref"),
            _definition_from_dict(fields["aggregation_ref"], "/aggregation_ref"),
            _definition_from_dict(fields["precision_ref"], "/precision_ref"),
            _reference_policy_from_dict(
                fields["reference_policy_ref"], "/reference_policy_ref"
            ),
            _scientific_value_from_dict(
                fields["numerical_floor_binding"], "/numerical_floor_binding"
            ),
            _definition_from_dict(
                fields["applicability_policy_ref"], "/applicability_policy_ref"
            ),
            _uncertainty_from_dict(
                fields["uncertainty_policy_binding"], "/uncertainty_policy_binding"
            ),
            tuple(
                _stratum_from_dict(item, f"/stratum_applicability/{index}")
                for index, item in enumerate(
                    _array(fields["stratum_applicability"], "/stratum_applicability")
                )
            ),
            tuple(
                _definition_from_dict(item, f"/known_limitation_refs/{index}")
                for index, item in enumerate(
                    _array(fields["known_limitation_refs"], "/known_limitation_refs")
                )
            ),
            tuple(
                _definition_from_dict(item, f"/implementation_refs/{index}")
                for index, item in enumerate(
                    _array(fields["implementation_refs"], "/implementation_refs")
                )
            ),
            MeasurementRole(fields["intended_role"]),
            fields["fixture_origin"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong("/", MeasurementInputCode.WRONG_TYPE) from None


def _qualification_from_dict(
    fields: Mapping[str, Any],
) -> MeasurementQualificationEvidence:
    names = {
        "canonicalization_profile",
        "challenge_key",
        "evidence_id",
        "evidence_items",
        "evidence_version",
        "fixture_origin",
        "measurement_contract_ref",
        "record_type",
        "schema_version",
    }
    fields = _object(fields, names, "/")
    try:
        return MeasurementQualificationEvidence(
            _challenge_from_dict(fields["challenge_key"], "/challenge_key"),
            fields["evidence_id"],
            fields["evidence_version"],
            _top_ref_from_dict(
                fields["measurement_contract_ref"],
                MeasurementContractRef,
                "/measurement_contract_ref",
            ),
            tuple(
                _evidence_item_from_dict(item, f"/evidence_items/{index}")
                for index, item in enumerate(
                    _array(fields["evidence_items"], "/evidence_items")
                )
            ),
            fields["fixture_origin"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong("/", MeasurementInputCode.WRONG_TYPE) from None


def _uncertainty_policy_from_dict(fields: Mapping[str, Any]) -> UncertaintyPolicy:
    names = {
        "canonicalization_profile",
        "censoring_accounting_binding",
        "challenge_key",
        "common_case_pairing_binding",
        "dependence_shortcuts",
        "estimand_binding",
        "evidence_extension_rule_binding",
        "execution_dependence_binding",
        "fixture_origin",
        "independence_unit_binding",
        "interval_error_control_binding",
        "joint_reference_uncertainty_binding",
        "measurement_contract_ref",
        "measurement_output_binding",
        "minimum_evidence_binding",
        "multiplicity_policy_binding",
        "policy_id",
        "policy_version",
        "reconstruction_case_interaction_binding",
        "reconstruction_stratum_interaction_binding",
        "record_type",
        "reference_candidate_covariance_binding",
        "representation_dependence_binding",
        "resampling_unit_binding",
        "sampling_unit_binding",
        "schema_version",
        "stopping_rule_binding",
        "stratum_minimum_bindings",
    }
    fields = _object(fields, names, "/")
    try:
        return UncertaintyPolicy(
            _challenge_from_dict(fields["challenge_key"], "/challenge_key"),
            fields["policy_id"],
            fields["policy_version"],
            _top_ref_from_dict(
                fields["measurement_contract_ref"],
                MeasurementContractRef,
                "/measurement_contract_ref",
            ),
            _component_from_dict(fields["estimand_binding"], "/estimand_binding"),
            _component_from_dict(
                fields["measurement_output_binding"], "/measurement_output_binding"
            ),
            _component_from_dict(
                fields["sampling_unit_binding"], "/sampling_unit_binding"
            ),
            _component_from_dict(
                fields["resampling_unit_binding"], "/resampling_unit_binding"
            ),
            _component_from_dict(
                fields["independence_unit_binding"], "/independence_unit_binding"
            ),
            _component_from_dict(
                fields["common_case_pairing_binding"],
                "/common_case_pairing_binding",
            ),
            _component_from_dict(
                fields["reconstruction_case_interaction_binding"],
                "/reconstruction_case_interaction_binding",
            ),
            _component_from_dict(
                fields["reconstruction_stratum_interaction_binding"],
                "/reconstruction_stratum_interaction_binding",
            ),
            _component_from_dict(
                fields["joint_reference_uncertainty_binding"],
                "/joint_reference_uncertainty_binding",
            ),
            _component_from_dict(
                fields["reference_candidate_covariance_binding"],
                "/reference_candidate_covariance_binding",
            ),
            _component_from_dict(
                fields["representation_dependence_binding"],
                "/representation_dependence_binding",
            ),
            _component_from_dict(
                fields["execution_dependence_binding"],
                "/execution_dependence_binding",
            ),
            _component_from_dict(
                fields["censoring_accounting_binding"],
                "/censoring_accounting_binding",
            ),
            _component_from_dict(
                fields["minimum_evidence_binding"], "/minimum_evidence_binding"
            ),
            tuple(
                _stratum_minimum_from_dict(item, f"/stratum_minimum_bindings/{index}")
                for index, item in enumerate(
                    _array(
                        fields["stratum_minimum_bindings"],
                        "/stratum_minimum_bindings",
                    )
                )
            ),
            _component_from_dict(
                fields["stopping_rule_binding"], "/stopping_rule_binding"
            ),
            _component_from_dict(
                fields["evidence_extension_rule_binding"],
                "/evidence_extension_rule_binding",
            ),
            _component_from_dict(
                fields["interval_error_control_binding"],
                "/interval_error_control_binding",
            ),
            _component_from_dict(
                fields["multiplicity_policy_binding"],
                "/multiplicity_policy_binding",
            ),
            tuple(
                _shortcut_from_dict(item, f"/dependence_shortcuts/{index}")
                for index, item in enumerate(
                    _array(fields["dependence_shortcuts"], "/dependence_shortcuts")
                )
            ),
            fields["fixture_origin"],
            fields["schema_version"],
            fields["canonicalization_profile"],
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong("/", MeasurementInputCode.WRONG_TYPE) from None


def _reconstruction_policy_from_dict(
    fields: Mapping[str, Any],
) -> ReconstructionEvidencePolicy:
    component_names = (
        "audit_selection_policy_binding",
        "build_completeness_criteria_binding",
        "case_coverage_requirement_binding",
        "complete_base_minimum_binding",
        "error_control_binding",
        "evidence_extension_rule_binding",
        "frozen_artifact_reuse_policy_binding",
        "minimum_resolvable_improvement_binding",
        "nomination_criteria_binding",
        "power_requirement_binding",
        "promotion_criteria_binding",
        "scientific_stopping_rule_binding",
        "sequential_stopping_rule_binding",
        "stability_audit_rate_binding",
        "stratum_coverage_requirement_binding",
    )
    names = {
        "canonicalization_profile",
        "challenge_key",
        "construction_family_ref",
        "fixture_origin",
        "policy_id",
        "policy_version",
        "record_type",
        "schema_version",
        *component_names,
    }
    fields = _object(fields, names, "/")
    try:
        components = {
            name: _component_from_dict(fields[name], f"/{name}")
            for name in component_names
        }
        return ReconstructionEvidencePolicy(
            challenge_key=_challenge_from_dict(
                fields["challenge_key"], "/challenge_key"
            ),
            policy_id=fields["policy_id"],
            policy_version=fields["policy_version"],
            construction_family_ref=_definition_from_dict(
                fields["construction_family_ref"], "/construction_family_ref"
            ),
            **components,
            fixture_origin=fields["fixture_origin"],
            schema_version=fields["schema_version"],
            canonicalization_profile=fields["canonicalization_profile"],
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong("/", MeasurementInputCode.WRONG_TYPE) from None


def _score_pack_authoring_from_dict(
    fields: Mapping[str, Any],
) -> ScorePackAuthoringContract:
    names = {
        "canonicalization_profile",
        "challenge_key",
        "contract_id",
        "contract_version",
        "fixture_origin",
        "input_bindings",
        "record_type",
        "schema_version",
        "score_pack_pin",
        "threshold_authority_binding",
        "transform_authority_binding",
        "weight_authority_binding",
    }
    fields = _object(fields, names, "/")
    try:
        return ScorePackAuthoringContract(
            challenge_key=_challenge_from_dict(
                fields["challenge_key"], "/challenge_key"
            ),
            contract_id=fields["contract_id"],
            contract_version=fields["contract_version"],
            score_pack_pin=_score_pack_pin_from_dict(
                fields["score_pack_pin"], "/score_pack_pin"
            ),
            input_bindings=tuple(
                _score_binding_from_dict(item, f"/input_bindings/{index}")
                for index, item in enumerate(
                    _array(fields["input_bindings"], "/input_bindings")
                )
            ),
            threshold_authority_binding=_component_from_dict(
                fields["threshold_authority_binding"],
                "/threshold_authority_binding",
            ),
            transform_authority_binding=_component_from_dict(
                fields["transform_authority_binding"],
                "/transform_authority_binding",
            ),
            weight_authority_binding=_component_from_dict(
                fields["weight_authority_binding"], "/weight_authority_binding"
            ),
            fixture_origin=fields["fixture_origin"],
            schema_version=fields["schema_version"],
            canonicalization_profile=fields["canonicalization_profile"],
        )
    except MeasurementCanonicalError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong("/", MeasurementInputCode.WRONG_TYPE) from None


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise _wrong("/", MeasurementInputCode.DUPLICATE_IDENTITY)
        result[key] = value
    return result


def _object(value: object, expected: set[str] | None, path: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE)
    if expected is not None and set(value) != expected:
        raise _wrong(path)
    return value


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        raise _wrong(path, MeasurementInputCode.WRONG_TYPE)
    return value


__all__ = (
    "MAX_MEASUREMENT_DOCUMENT_BYTES",
    "canonical_bytes",
    "canonical_digest",
    "canonical_payload",
    "load_canonical_document",
    "measurement_ref",
)
