"""Closed B-04 reference/truth vocabularies and compatibility matrices."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType


class ReferenceAuthorityFunction(str, Enum):
    PRIMARY = "PRIMARY"
    CORROBORATING_WITNESS = "CORROBORATING_WITNESS"
    VERIFICATION_ANCHOR = "VERIFICATION_ANCHOR"
    VALIDATION_ANCHOR = "VALIDATION_ANCHOR"
    REGISTERED_COMPONENT = "REGISTERED_COMPONENT"


class ReferenceSourceClass(str, Enum):
    DIRECT_REGISTERED_SOURCE = "DIRECT_REGISTERED_SOURCE"
    EXPERIMENTAL_DATASET_OR_INSTRUMENT = "EXPERIMENTAL_DATASET_OR_INSTRUMENT"
    INDUSTRIAL_OR_CUSTOMER_HOSTED_REFERENCE = "INDUSTRIAL_OR_CUSTOMER_HOSTED_REFERENCE"
    QUALIFIED_SURROGATE_OR_ACCELERATOR = "QUALIFIED_SURROGATE_OR_ACCELERATOR"


class ReferenceCompositionKind(str, Enum):
    SINGLE_ENTRY = "SINGLE_ENTRY"
    REGISTERED_HYBRID_POLICY = "REGISTERED_HYBRID_POLICY"


class ReferenceIdentityKind(str, Enum):
    SOURCE = "SOURCE"
    IMPLEMENTATION = "IMPLEMENTATION"
    ENVIRONMENT = "ENVIRONMENT"
    METHOD = "METHOD"
    CONFIGURATION = "CONFIGURATION"
    REPRESENTATION = "REPRESENTATION"
    ARTIFACT_SCHEMA = "ARTIFACT_SCHEMA"
    ARTIFACT_DESCRIPTOR = "ARTIFACT_DESCRIPTOR"
    COMBINATION_METHOD = "COMBINATION_METHOD"
    PRECISION = "PRECISION"
    HARDWARE = "HARDWARE"
    PLATFORM = "PLATFORM"
    DEPENDENCY_SET = "DEPENDENCY_SET"
    DETERMINISTIC_MODE = "DETERMINISTIC_MODE"
    RESOURCE_AUTHORIZATION = "RESOURCE_AUTHORIZATION"
    RESOURCE_RECEIPT = "RESOURCE_RECEIPT"
    RESOLVER = "RESOLVER"
    RUN_ISSUER = "RUN_ISSUER"
    ADMISSION_ISSUER = "ADMISSION_ISSUER"
    ADMISSION_AUTHORITY = "ADMISSION_AUTHORITY"
    ADMISSION_PROFILE = "ADMISSION_PROFILE"
    COMPARISON_METHOD = "COMPARISON_METHOD"
    APPLICABILITY_METHOD = "APPLICABILITY_METHOD"
    CONDITIONING_METHOD = "CONDITIONING_METHOD"
    UNCERTAINTY_METHOD = "UNCERTAINTY_METHOD"
    UNCERTAINTY_REPRESENTATION = "UNCERTAINTY_REPRESENTATION"
    DIAGNOSTICS = "DIAGNOSTICS"
    UNITS = "UNITS"
    CONSUMED_GRANT_RECEIPT = "CONSUMED_GRANT_RECEIPT"


class DependencyCategory(str, Enum):
    MODEL_ASSUMPTIONS = "MODEL_ASSUMPTIONS"
    DISCRETIZATION = "DISCRETIZATION"
    MESH_OR_GRID = "MESH_OR_GRID"
    TRANSFORM_OR_ADAPTER = "TRANSFORM_OR_ADAPTER"
    LIBRARY_OR_CODE_LINEAGE = "LIBRARY_OR_CODE_LINEAGE"
    CALIBRATION_OR_DATA = "CALIBRATION_OR_DATA"
    PERSONNEL_OR_ORGANIZATION = "PERSONNEL_OR_ORGANIZATION"
    FLOATING_POINT_OR_RUNTIME = "FLOATING_POINT_OR_RUNTIME"
    HARDWARE_OR_RESOURCE = "HARDWARE_OR_RESOURCE"
    REVIEW_OR_DESIGN_LINEAGE = "REVIEW_OR_DESIGN_LINEAGE"


class DependencyRelation(str, Enum):
    SHARED = "SHARED"
    DISTINCT = "DISTINCT"
    UNDISCLOSED = "UNDISCLOSED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class UncertaintyComponentKind(str, Enum):
    ALEATORY = "ALEATORY"
    NUMERICAL = "NUMERICAL"
    MODEL_FORM = "MODEL_FORM"
    MEASUREMENT = "MEASUREMENT"
    RECONSTRUCTION = "RECONSTRUCTION"
    REPRESENTATION = "REPRESENTATION"
    EXECUTION = "EXECUTION"
    OTHER_REGISTERED = "OTHER_REGISTERED"


class UncertaintyStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


class SupportApplicabilityStatus(str, Enum):
    SUPPORTED_AND_APPLICABLE = "SUPPORTED_AND_APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNSUPPORTED = "UNSUPPORTED"
    ASSESSMENT_UNAVAILABLE = "ASSESSMENT_UNAVAILABLE"


class ConditioningStatus(str, Enum):
    ASSESSED_WITHIN_REGISTERED_SCOPE = "ASSESSED_WITHIN_REGISTERED_SCOPE"
    UNRESOLVED = "UNRESOLVED"
    OUTSIDE_REGISTERED_SCOPE = "OUTSIDE_REGISTERED_SCOPE"
    ASSESSMENT_UNAVAILABLE = "ASSESSMENT_UNAVAILABLE"


class ReferenceArtifactOrigin(str, Enum):
    REGISTERED_REFERENCE = "REGISTERED_REFERENCE"
    FIXTURE_ONLY = "FIXTURE_ONLY"


class AdmissionArtifactAbsenceReason(str, Enum):
    MISSING = "MISSING"
    MALFORMED = "MALFORMED"
    STALE_PROVENANCE = "STALE_PROVENANCE"
    WRONG_CHALLENGE = "WRONG_CHALLENGE"
    WRONG_POLICY = "WRONG_POLICY"
    WRONG_ROLE = "WRONG_ROLE"
    INELIGIBLE_APPLICABILITY = "INELIGIBLE_APPLICABILITY"
    FIXTURE_ONLY = "FIXTURE_ONLY"


class QualificationAbsenceReason(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ReferenceAuthorityTargetKind(str, Enum):
    SINGLE_PRIMARY_ENTRY = "SINGLE_PRIMARY_ENTRY"
    QUALIFIED_PRIMARY_COMPOSITION = "QUALIFIED_PRIMARY_COMPOSITION"


class ReferenceWitnessTargetKind(str, Enum):
    SINGLE_WITNESS_ENTRY = "SINGLE_WITNESS_ENTRY"
    QUALIFIED_WITNESS_COMPOSITION = "QUALIFIED_WITNESS_COMPOSITION"


class ReferenceExecutionTargetKind(str, Enum):
    PRIMARY = "PRIMARY"
    WITNESS = "WITNESS"


class ReferenceRequestBindingKind(str, Enum):
    PRIMARY = "PRIMARY"
    WITNESS = "WITNESS"


class ReferenceGrantBindingKind(str, Enum):
    PRIMARY = "PRIMARY"
    WITNESS = "WITNESS"
    ABSENT = "ABSENT"


class OptionalBindingTag(str, Enum):
    ABSENT = "ABSENT"
    PRESENT = "PRESENT"


class BoundOrAbsentTag(str, Enum):
    BOUND = "BOUND"
    ABSENT = "ABSENT"


class ResolutionOutcome(str, Enum):
    PRIMARY_GRANT_ISSUED = "PRIMARY_GRANT_ISSUED"
    WITNESS_GRANT_ISSUED = "WITNESS_GRANT_ISSUED"
    POLICY_INCOMPLETE = "POLICY_INCOMPLETE"
    ROLE_UNAVAILABLE = "ROLE_UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNSUPPORTED = "UNSUPPORTED"
    APPLICABILITY_UNRESOLVED = "APPLICABILITY_UNRESOLVED"
    QUALIFICATION_UNAVAILABLE = "QUALIFICATION_UNAVAILABLE"
    RESOURCE_AUTHORIZATION_UNAVAILABLE = "RESOURCE_AUTHORIZATION_UNAVAILABLE"
    IDENTITY_OR_PROVENANCE_FAILURE = "IDENTITY_OR_PROVENANCE_FAILURE"


class ResolutionReason(str, Enum):
    RESOLUTION_REQUIREMENTS_SATISFIED = "RESOLUTION_REQUIREMENTS_SATISFIED"
    POLICY_PRIMARY_MISSING = "POLICY_PRIMARY_MISSING"
    POLICY_ENTRY_INCOMPLETE = "POLICY_ENTRY_INCOMPLETE"
    ROLE_NOT_REGISTERED = "ROLE_NOT_REGISTERED"
    CASE_NOT_APPLICABLE = "CASE_NOT_APPLICABLE"
    CASE_UNSUPPORTED = "CASE_UNSUPPORTED"
    APPLICABILITY_ASSESSMENT_UNAVAILABLE = "APPLICABILITY_ASSESSMENT_UNAVAILABLE"
    QUALIFICATION_BINDING_UNAVAILABLE = "QUALIFICATION_BINDING_UNAVAILABLE"
    RESOURCE_POLICY_UNAVAILABLE = "RESOURCE_POLICY_UNAVAILABLE"
    RESOURCE_CAPACITY_UNAVAILABLE = "RESOURCE_CAPACITY_UNAVAILABLE"
    RESOLUTION_IDENTITY_MISMATCH = "RESOLUTION_IDENTITY_MISMATCH"
    RESOLUTION_PROVENANCE_INVALID = "RESOLUTION_PROVENANCE_INVALID"


class ReferenceRunOutcome(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNCERTAINTY_UNRESOLVED = "UNCERTAINTY_UNRESOLVED"
    CONDITIONING_UNRESOLVED = "CONDITIONING_UNRESOLVED"
    APPLICABILITY_UNRESOLVED = "APPLICABILITY_UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNSUPPORTED = "UNSUPPORTED"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    MALFORMED_OR_PROVENANCE_FAILURE = "MALFORMED_OR_PROVENANCE_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    CANCELLED = "CANCELLED"


class ReferenceFailureReason(str, Enum):
    POLICY_ENTRY_NOT_APPLICABLE = "POLICY_ENTRY_NOT_APPLICABLE"
    POLICY_ENTRY_UNSUPPORTED = "POLICY_ENTRY_UNSUPPORTED"
    UNCERTAINTY_EVIDENCE_UNRESOLVED = "UNCERTAINTY_EVIDENCE_UNRESOLVED"
    CONDITIONING_EVIDENCE_UNRESOLVED = "CONDITIONING_EVIDENCE_UNRESOLVED"
    APPLICABILITY_ASSESSMENT_UNAVAILABLE = "APPLICABILITY_ASSESSMENT_UNAVAILABLE"
    REQUEST_OR_GRANT_INVALID = "REQUEST_OR_GRANT_INVALID"
    NUMERICAL_NONCONVERGENCE = "NUMERICAL_NONCONVERGENCE"
    NUMERICAL_INVALID_RESULT = "NUMERICAL_INVALID_RESULT"
    PROVIDER_RESULT_MALFORMED = "PROVIDER_RESULT_MALFORMED"
    PROVENANCE_INVALID = "PROVENANCE_INVALID"
    VERSION_OR_IDENTITY_MISMATCH = "VERSION_OR_IDENTITY_MISMATCH"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    TRANSPORT_FAILURE = "TRANSPORT_FAILURE"
    PROCESS_FAILURE = "PROCESS_FAILURE"
    CAPACITY_UNAVAILABLE = "CAPACITY_UNAVAILABLE"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    TIMEOUT = "TIMEOUT"
    TRUSTED_CANCELLATION = "TRUSTED_CANCELLATION"


class ReferenceComparisonOutcome(str, Enum):
    AGREEMENT_WITHIN_REGISTERED_POLICY = "AGREEMENT_WITHIN_REGISTERED_POLICY"
    CONTESTED_DISAGREEMENT = "CONTESTED_DISAGREEMENT"
    COMPARISON_INDETERMINATE = "COMPARISON_INDETERMINATE"


class ReferenceComparisonReason(str, Enum):
    COMPARISON_REQUIREMENTS_SATISFIED = "COMPARISON_REQUIREMENTS_SATISFIED"
    PRIMARY_OR_WITNESS_NOT_SUPPORTED = "PRIMARY_OR_WITNESS_NOT_SUPPORTED"
    COMPARISON_INPUT_IDENTITY_MISMATCH = "COMPARISON_INPUT_IDENTITY_MISMATCH"
    COMPARISON_PROVENANCE_INVALID = "COMPARISON_PROVENANCE_INVALID"
    COMPARISON_APPLICABILITY_MISMATCH = "COMPARISON_APPLICABILITY_MISMATCH"
    COMPARISON_METHOD_UNAVAILABLE = "COMPARISON_METHOD_UNAVAILABLE"
    COMPARISON_UNCERTAINTY_UNRESOLVED = "COMPARISON_UNCERTAINTY_UNRESOLVED"
    COMPARISON_DEPENDENCE_UNRESOLVED = "COMPARISON_DEPENDENCE_UNRESOLVED"
    REGISTERED_DISAGREEMENT_EXCEEDED = "REGISTERED_DISAGREEMENT_EXCEEDED"


class AdmissionGrantIssuanceOutcome(str, Enum):
    ADMISSION_GRANT_AUTHORIZED = "ADMISSION_GRANT_AUTHORIZED"
    ADMISSION_GRANT_UNAVAILABLE = "ADMISSION_GRANT_UNAVAILABLE"


class AdmissionGrantIssuanceReason(str, Enum):
    ADMISSION_GRANT_REQUIREMENTS_SATISFIED = "ADMISSION_GRANT_REQUIREMENTS_SATISFIED"
    ADMISSION_GRAPH_CROSS_BINDING_MISMATCH = "ADMISSION_GRAPH_CROSS_BINDING_MISMATCH"
    ADMISSION_GRANT_SCOPE_UNAVAILABLE = "ADMISSION_GRANT_SCOPE_UNAVAILABLE"
    ADMISSION_AUTHORITY_BINDING_UNAVAILABLE = "ADMISSION_AUTHORITY_BINDING_UNAVAILABLE"


class TruthAssetAdmissionOutcome(str, Enum):
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"
    INDETERMINATE = "INDETERMINATE"


class TruthAssetAdmissionReason(str, Enum):
    ADMISSION_REQUIREMENTS_SATISFIED = "ADMISSION_REQUIREMENTS_SATISFIED"
    RUN_NOT_SUPPORTED = "RUN_NOT_SUPPORTED"
    ARTIFACT_ABSENT_OR_INELIGIBLE = "ARTIFACT_ABSENT_OR_INELIGIBLE"
    REQUIRED_COMPARISON_CONTESTED = "REQUIRED_COMPARISON_CONTESTED"
    REQUIRED_COMPARISON_INDETERMINATE = "REQUIRED_COMPARISON_INDETERMINATE"
    QUALIFICATION_UNAVAILABLE = "QUALIFICATION_UNAVAILABLE"
    POLICY_OR_IDENTITY_MISMATCH = "POLICY_OR_IDENTITY_MISMATCH"
    PROVENANCE_OR_RIGHTS_INVALID = "PROVENANCE_OR_RIGHTS_INVALID"
    GRANT_INVALID_OR_CONSUMED = "GRANT_INVALID_OR_CONSUMED"
    USE_OR_DISCLOSURE_UNAVAILABLE = "USE_OR_DISCLOSURE_UNAVAILABLE"


RESOLUTION_OUTCOME_REASON_COMPATIBILITY = MappingProxyType(
    {
        ResolutionOutcome.PRIMARY_GRANT_ISSUED: (
            ResolutionReason.RESOLUTION_REQUIREMENTS_SATISFIED,
        ),
        ResolutionOutcome.WITNESS_GRANT_ISSUED: (
            ResolutionReason.RESOLUTION_REQUIREMENTS_SATISFIED,
        ),
        ResolutionOutcome.POLICY_INCOMPLETE: (
            ResolutionReason.POLICY_PRIMARY_MISSING,
            ResolutionReason.POLICY_ENTRY_INCOMPLETE,
        ),
        ResolutionOutcome.ROLE_UNAVAILABLE: (ResolutionReason.ROLE_NOT_REGISTERED,),
        ResolutionOutcome.NOT_APPLICABLE: (ResolutionReason.CASE_NOT_APPLICABLE,),
        ResolutionOutcome.UNSUPPORTED: (ResolutionReason.CASE_UNSUPPORTED,),
        ResolutionOutcome.APPLICABILITY_UNRESOLVED: (
            ResolutionReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE,
        ),
        ResolutionOutcome.QUALIFICATION_UNAVAILABLE: (
            ResolutionReason.QUALIFICATION_BINDING_UNAVAILABLE,
        ),
        ResolutionOutcome.RESOURCE_AUTHORIZATION_UNAVAILABLE: (
            ResolutionReason.RESOURCE_POLICY_UNAVAILABLE,
            ResolutionReason.RESOURCE_CAPACITY_UNAVAILABLE,
        ),
        ResolutionOutcome.IDENTITY_OR_PROVENANCE_FAILURE: (
            ResolutionReason.RESOLUTION_IDENTITY_MISMATCH,
            ResolutionReason.RESOLUTION_PROVENANCE_INVALID,
        ),
    }
)

RUN_OUTCOME_REASON_COMPATIBILITY = MappingProxyType(
    {
        ReferenceRunOutcome.SUPPORTED: (),
        ReferenceRunOutcome.UNCERTAINTY_UNRESOLVED: (
            ReferenceFailureReason.UNCERTAINTY_EVIDENCE_UNRESOLVED,
        ),
        ReferenceRunOutcome.CONDITIONING_UNRESOLVED: (
            ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED,
        ),
        ReferenceRunOutcome.APPLICABILITY_UNRESOLVED: (
            ReferenceFailureReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE,
        ),
        ReferenceRunOutcome.NOT_APPLICABLE: (
            ReferenceFailureReason.POLICY_ENTRY_NOT_APPLICABLE,
        ),
        ReferenceRunOutcome.UNSUPPORTED: (
            ReferenceFailureReason.POLICY_ENTRY_UNSUPPORTED,
        ),
        ReferenceRunOutcome.NUMERICAL_FAILURE: (
            ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
            ReferenceFailureReason.NUMERICAL_INVALID_RESULT,
        ),
        ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE: (
            ReferenceFailureReason.REQUEST_OR_GRANT_INVALID,
            ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
            ReferenceFailureReason.PROVENANCE_INVALID,
            ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH,
        ),
        ReferenceRunOutcome.INFRASTRUCTURE_FAILURE: (
            ReferenceFailureReason.DEPENDENCY_UNAVAILABLE,
            ReferenceFailureReason.TRANSPORT_FAILURE,
            ReferenceFailureReason.PROCESS_FAILURE,
            ReferenceFailureReason.CAPACITY_UNAVAILABLE,
            ReferenceFailureReason.RESOURCE_LIMIT,
            ReferenceFailureReason.TIMEOUT,
        ),
        ReferenceRunOutcome.CANCELLED: (ReferenceFailureReason.TRUSTED_CANCELLATION,),
    }
)

COMPARISON_OUTCOME_REASON_COMPATIBILITY = MappingProxyType(
    {
        ReferenceComparisonOutcome.AGREEMENT_WITHIN_REGISTERED_POLICY: (
            ReferenceComparisonReason.COMPARISON_REQUIREMENTS_SATISFIED,
        ),
        ReferenceComparisonOutcome.CONTESTED_DISAGREEMENT: (
            ReferenceComparisonReason.REGISTERED_DISAGREEMENT_EXCEEDED,
        ),
        ReferenceComparisonOutcome.COMPARISON_INDETERMINATE: (
            ReferenceComparisonReason.PRIMARY_OR_WITNESS_NOT_SUPPORTED,
            ReferenceComparisonReason.COMPARISON_INPUT_IDENTITY_MISMATCH,
            ReferenceComparisonReason.COMPARISON_PROVENANCE_INVALID,
            ReferenceComparisonReason.COMPARISON_APPLICABILITY_MISMATCH,
            ReferenceComparisonReason.COMPARISON_METHOD_UNAVAILABLE,
            ReferenceComparisonReason.COMPARISON_UNCERTAINTY_UNRESOLVED,
            ReferenceComparisonReason.COMPARISON_DEPENDENCE_UNRESOLVED,
        ),
    }
)

ADMISSION_ISSUANCE_OUTCOME_REASON_COMPATIBILITY = MappingProxyType(
    {
        AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED: (
            AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
        ),
        AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_UNAVAILABLE: (
            AdmissionGrantIssuanceReason.ADMISSION_GRAPH_CROSS_BINDING_MISMATCH,
            AdmissionGrantIssuanceReason.ADMISSION_GRANT_SCOPE_UNAVAILABLE,
            AdmissionGrantIssuanceReason.ADMISSION_AUTHORITY_BINDING_UNAVAILABLE,
        ),
    }
)

ADMISSION_OUTCOME_REASON_COMPATIBILITY = MappingProxyType(
    {
        TruthAssetAdmissionOutcome.ADMITTED: (
            TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
        ),
        TruthAssetAdmissionOutcome.REJECTED: (
            TruthAssetAdmissionReason.GRANT_INVALID_OR_CONSUMED,
            TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH,
            TruthAssetAdmissionReason.RUN_NOT_SUPPORTED,
            TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE,
            TruthAssetAdmissionReason.PROVENANCE_OR_RIGHTS_INVALID,
        ),
        TruthAssetAdmissionOutcome.UNAVAILABLE: (
            TruthAssetAdmissionReason.QUALIFICATION_UNAVAILABLE,
            TruthAssetAdmissionReason.USE_OR_DISCLOSURE_UNAVAILABLE,
        ),
        TruthAssetAdmissionOutcome.INDETERMINATE: (
            TruthAssetAdmissionReason.REQUIRED_COMPARISON_CONTESTED,
            TruthAssetAdmissionReason.REQUIRED_COMPARISON_INDETERMINATE,
        ),
    }
)

RESOLUTION_REASON_PRECEDENCE = (
    ResolutionReason.RESOLUTION_IDENTITY_MISMATCH,
    ResolutionReason.RESOLUTION_PROVENANCE_INVALID,
    ResolutionReason.POLICY_PRIMARY_MISSING,
    ResolutionReason.POLICY_ENTRY_INCOMPLETE,
    ResolutionReason.ROLE_NOT_REGISTERED,
    ResolutionReason.CASE_NOT_APPLICABLE,
    ResolutionReason.CASE_UNSUPPORTED,
    ResolutionReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE,
    ResolutionReason.QUALIFICATION_BINDING_UNAVAILABLE,
    ResolutionReason.RESOURCE_POLICY_UNAVAILABLE,
    ResolutionReason.RESOURCE_CAPACITY_UNAVAILABLE,
    ResolutionReason.RESOLUTION_REQUIREMENTS_SATISFIED,
)

RUN_REASON_PRECEDENCE = (
    ReferenceFailureReason.REQUEST_OR_GRANT_INVALID,
    ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH,
    ReferenceFailureReason.PROVENANCE_INVALID,
    ReferenceFailureReason.TRUSTED_CANCELLATION,
    ReferenceFailureReason.TIMEOUT,
    ReferenceFailureReason.RESOURCE_LIMIT,
    ReferenceFailureReason.CAPACITY_UNAVAILABLE,
    ReferenceFailureReason.DEPENDENCY_UNAVAILABLE,
    ReferenceFailureReason.TRANSPORT_FAILURE,
    ReferenceFailureReason.PROCESS_FAILURE,
    ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
    ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
    ReferenceFailureReason.NUMERICAL_INVALID_RESULT,
    ReferenceFailureReason.POLICY_ENTRY_NOT_APPLICABLE,
    ReferenceFailureReason.POLICY_ENTRY_UNSUPPORTED,
    ReferenceFailureReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE,
    ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED,
    ReferenceFailureReason.UNCERTAINTY_EVIDENCE_UNRESOLVED,
)

COMPARISON_REASON_PRECEDENCE = (
    ReferenceComparisonReason.COMPARISON_INPUT_IDENTITY_MISMATCH,
    ReferenceComparisonReason.COMPARISON_PROVENANCE_INVALID,
    ReferenceComparisonReason.PRIMARY_OR_WITNESS_NOT_SUPPORTED,
    ReferenceComparisonReason.COMPARISON_APPLICABILITY_MISMATCH,
    ReferenceComparisonReason.COMPARISON_METHOD_UNAVAILABLE,
    ReferenceComparisonReason.COMPARISON_UNCERTAINTY_UNRESOLVED,
    ReferenceComparisonReason.COMPARISON_DEPENDENCE_UNRESOLVED,
    ReferenceComparisonReason.REGISTERED_DISAGREEMENT_EXCEEDED,
    ReferenceComparisonReason.COMPARISON_REQUIREMENTS_SATISFIED,
)

ADMISSION_ISSUANCE_REASON_PRECEDENCE = (
    AdmissionGrantIssuanceReason.ADMISSION_GRAPH_CROSS_BINDING_MISMATCH,
    AdmissionGrantIssuanceReason.ADMISSION_GRANT_SCOPE_UNAVAILABLE,
    AdmissionGrantIssuanceReason.ADMISSION_AUTHORITY_BINDING_UNAVAILABLE,
    AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
)

ADMISSION_REASON_PRECEDENCE = (
    TruthAssetAdmissionReason.GRANT_INVALID_OR_CONSUMED,
    TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH,
    TruthAssetAdmissionReason.RUN_NOT_SUPPORTED,
    TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE,
    TruthAssetAdmissionReason.REQUIRED_COMPARISON_CONTESTED,
    TruthAssetAdmissionReason.REQUIRED_COMPARISON_INDETERMINATE,
    TruthAssetAdmissionReason.QUALIFICATION_UNAVAILABLE,
    TruthAssetAdmissionReason.PROVENANCE_OR_RIGHTS_INVALID,
    TruthAssetAdmissionReason.USE_OR_DISCLOSURE_UNAVAILABLE,
    TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
)


def _registered_enum_member(value: object, family: type[Enum]) -> bool:
    """Reject exact-type pseudo-members as well as values from other families."""

    return type(value) is family and any(value is member for member in family)


def _registered_reason(
    reason: object,
    family: type[Enum],
    allowed: tuple[Enum, ...],
) -> bool:
    return _registered_enum_member(reason, family) and any(
        reason is member for member in allowed
    )


def outcome_reason_compatible(outcome: object, reason: object | None) -> bool:
    """Return compatibility only for one exact closed outcome family."""

    if type(outcome) is ResolutionOutcome:
        return _registered_enum_member(
            outcome, ResolutionOutcome
        ) and _registered_reason(
            reason,
            ResolutionReason,
            RESOLUTION_OUTCOME_REASON_COMPATIBILITY[outcome],
        )
    if type(outcome) is ReferenceRunOutcome:
        if not _registered_enum_member(outcome, ReferenceRunOutcome):
            return False
        if outcome is ReferenceRunOutcome.SUPPORTED:
            return reason is None
        return _registered_reason(
            reason,
            ReferenceFailureReason,
            RUN_OUTCOME_REASON_COMPATIBILITY[outcome],
        )
    if type(outcome) is ReferenceComparisonOutcome:
        return _registered_enum_member(
            outcome, ReferenceComparisonOutcome
        ) and _registered_reason(
            reason,
            ReferenceComparisonReason,
            COMPARISON_OUTCOME_REASON_COMPATIBILITY[outcome],
        )
    if type(outcome) is AdmissionGrantIssuanceOutcome:
        return _registered_enum_member(
            outcome, AdmissionGrantIssuanceOutcome
        ) and _registered_reason(
            reason,
            AdmissionGrantIssuanceReason,
            ADMISSION_ISSUANCE_OUTCOME_REASON_COMPATIBILITY[outcome],
        )
    if type(outcome) is TruthAssetAdmissionOutcome:
        return _registered_enum_member(
            outcome, TruthAssetAdmissionOutcome
        ) and _registered_reason(
            reason,
            TruthAssetAdmissionReason,
            ADMISSION_OUTCOME_REASON_COMPATIBILITY[outcome],
        )
    return False


__all__ = [
    "ADMISSION_ISSUANCE_OUTCOME_REASON_COMPATIBILITY",
    "ADMISSION_ISSUANCE_REASON_PRECEDENCE",
    "ADMISSION_OUTCOME_REASON_COMPATIBILITY",
    "ADMISSION_REASON_PRECEDENCE",
    "COMPARISON_OUTCOME_REASON_COMPATIBILITY",
    "COMPARISON_REASON_PRECEDENCE",
    "RESOLUTION_OUTCOME_REASON_COMPATIBILITY",
    "RESOLUTION_REASON_PRECEDENCE",
    "RUN_OUTCOME_REASON_COMPATIBILITY",
    "RUN_REASON_PRECEDENCE",
    "AdmissionArtifactAbsenceReason",
    "AdmissionGrantIssuanceOutcome",
    "AdmissionGrantIssuanceReason",
    "BoundOrAbsentTag",
    "ConditioningStatus",
    "DependencyCategory",
    "DependencyRelation",
    "OptionalBindingTag",
    "QualificationAbsenceReason",
    "ReferenceArtifactOrigin",
    "ReferenceAuthorityFunction",
    "ReferenceAuthorityTargetKind",
    "ReferenceComparisonOutcome",
    "ReferenceComparisonReason",
    "ReferenceCompositionKind",
    "ReferenceExecutionTargetKind",
    "ReferenceFailureReason",
    "ReferenceGrantBindingKind",
    "ReferenceIdentityKind",
    "ReferenceRequestBindingKind",
    "ReferenceRunOutcome",
    "ReferenceSourceClass",
    "ReferenceWitnessTargetKind",
    "ResolutionOutcome",
    "ResolutionReason",
    "SupportApplicabilityStatus",
    "TruthAssetAdmissionOutcome",
    "TruthAssetAdmissionReason",
    "UncertaintyComponentKind",
    "UncertaintyStatus",
    "outcome_reason_compatible",
]
