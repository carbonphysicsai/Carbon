"""Closed vocabularies for the B-06 Validation Dossier foundation."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType


class DossierSlot(str, Enum):
    D1 = "D1"
    D2 = "D2"
    D3 = "D3"
    D4 = "D4"
    D5 = "D5"
    D6 = "D6"
    D7 = "D7"
    D8 = "D8"
    D9 = "D9"
    D10 = "D10"
    D11 = "D11"
    D12 = "D12"


DOSSIER_SLOT_ORDER = tuple(DossierSlot)
DOSSIER_SLOT_TITLES = MappingProxyType(
    {
        DossierSlot.D1: "Physical-system adequacy",
        DossierSlot.D2: "Claim / envelope adequacy",
        DossierSlot.D3: "Target-population adequacy",
        DossierSlot.D4: "SamplingPlan / finite-evidence adequacy",
        DossierSlot.D5: "Generator implementation integrity",
        DossierSlot.D6: "Generator distribution conformance",
        DossierSlot.D7: "Reference / truth adequacy",
        DossierSlot.D8: "Representation fidelity",
        DossierSlot.D9: "Measurement adequacy and applicability",
        DossierSlot.D10: "Statistical sufficiency and estimand clarity",
        DossierSlot.D11: ("Evaluation secrecy, decontamination, and role separation"),
        DossierSlot.D12: "Censoring, limitations, and residual uncertainty",
    }
)


class DossierEvidenceClass(str, Enum):
    PHYSICAL_SYSTEM_ADEQUACY = "PHYSICAL_SYSTEM_ADEQUACY"
    CLAIM_ENVELOPE_ADEQUACY = "CLAIM_ENVELOPE_ADEQUACY"
    TARGET_POPULATION_ADEQUACY = "TARGET_POPULATION_ADEQUACY"
    SAMPLING_PLAN_FINITE_EVIDENCE_ADEQUACY = "SAMPLING_PLAN_FINITE_EVIDENCE_ADEQUACY"
    GENERATOR_IMPLEMENTATION_INTEGRITY = "GENERATOR_IMPLEMENTATION_INTEGRITY"
    GENERATOR_DISTRIBUTION_CONFORMANCE = "GENERATOR_DISTRIBUTION_CONFORMANCE"
    REFERENCE_TRUTH_ADEQUACY = "REFERENCE_TRUTH_ADEQUACY"
    REPRESENTATION_FIDELITY = "REPRESENTATION_FIDELITY"
    MEASUREMENT_ADEQUACY_APPLICABILITY = "MEASUREMENT_ADEQUACY_APPLICABILITY"
    STATISTICAL_SUFFICIENCY_ESTIMAND_CLARITY = (
        "STATISTICAL_SUFFICIENCY_ESTIMAND_CLARITY"
    )
    EVALUATION_SECRECY_DECONTAMINATION_ROLE_SEPARATION = (
        "EVALUATION_SECRECY_DECONTAMINATION_ROLE_SEPARATION"
    )
    CENSORING_LIMITATIONS_RESIDUAL_UNCERTAINTY = (
        "CENSORING_LIMITATIONS_RESIDUAL_UNCERTAINTY"
    )
    MMS_REFINEMENT_OBSERVED_ORDER = "MMS_REFINEMENT_OBSERVED_ORDER"
    PLANTED_DEFECT_MUTATION_CAMPAIGN = "PLANTED_DEFECT_MUTATION_CAMPAIGN"
    ANALYTIC_LIMITING_CASE_ANCHOR = "ANALYTIC_LIMITING_CASE_ANCHOR"
    PRIMARY_WITNESS_CONVERGENCE = "PRIMARY_WITNESS_CONVERGENCE"
    REFERENCE_DISAGREEMENT = "REFERENCE_DISAGREEMENT"
    GENERATOR_ORACLE_ADVERSARIAL_TEST = "GENERATOR_ORACLE_ADVERSARIAL_TEST"
    MEASUREMENT_FLOOR = "MEASUREMENT_FLOOR"
    DECISION_RESOLUTION_STUDY = "DECISION_RESOLUTION_STUDY"
    RESIDUAL_LIMITATION = "RESIDUAL_LIMITATION"


DOSSIER_PRIMARY_EVIDENCE_CLASS = MappingProxyType(
    dict(zip(DOSSIER_SLOT_ORDER, tuple(DossierEvidenceClass)[:12], strict=True))
)


class EvidenceRequirement(str, Enum):
    REQUIRED = "REQUIRED"
    NOT_APPLICABLE_WITH_RATIONALE = "NOT_APPLICABLE_WITH_RATIONALE"
    DEFERRED_BLOCKING_LIVE = "DEFERRED_BLOCKING_LIVE"


class EvidenceCompleteness(str, Enum):
    INCOMPLETE_MISSING = "INCOMPLETE_MISSING"
    INCOMPLETE_PLACEHOLDER = "INCOMPLETE_PLACEHOLDER"
    COMPLETE_REFERENCED = "COMPLETE_REFERENCED"


class EvidenceSectionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"
    PASS_WITH_LIMITATIONS = "PASS_WITH_LIMITATIONS"


class StructuralOrigin(str, Enum):
    FIXTURE_ONLY = "FIXTURE_ONLY"
    DRAFT_OR_UNRESOLVED = "DRAFT_OR_UNRESOLVED"
    REGISTERED_REFERENCE = "REGISTERED_REFERENCE"


class SignerRole(str, Enum):
    PHYSICS_SCIML = "PHYSICS_SCIML"
    STATISTICS = "STATISTICS"
    PROTOCOL = "PROTOCOL"
    SECURITY = "SECURITY"
    INDEPENDENT_REVIEW = "INDEPENDENT_REVIEW"


REQUIRED_SIGNER_ROLE_ORDER = tuple(SignerRole)


class SignerArtifactKind(str, Enum):
    SIGNER_IDENTITY = "SIGNER_IDENTITY"
    SIGNATURE = "SIGNATURE"
    AUTHORIZATION_EVIDENCE = "AUTHORIZATION_EVIDENCE"


class SignerBindingState(str, Enum):
    REQUIRED_MISSING = "REQUIRED_MISSING"
    POPULATED_UNVERIFIED = "POPULATED_UNVERIFIED"


class DossierClaimRole(str, Enum):
    PHYSICAL_SYSTEM_ADEQUACY = "PHYSICAL_SYSTEM_ADEQUACY"
    CLAIM_ENVELOPE_ADEQUACY = "CLAIM_ENVELOPE_ADEQUACY"
    TARGET_POPULATION_ADEQUACY = "TARGET_POPULATION_ADEQUACY"
    SAMPLING_PLAN_ADEQUACY = "SAMPLING_PLAN_ADEQUACY"
    GENERATOR_IMPLEMENTATION_INTEGRITY = "GENERATOR_IMPLEMENTATION_INTEGRITY"
    GENERATOR_DISTRIBUTION_CONFORMANCE = "GENERATOR_DISTRIBUTION_CONFORMANCE"
    REFERENCE_ADEQUACY = "REFERENCE_ADEQUACY"
    REPRESENTATION_FIDELITY = "REPRESENTATION_FIDELITY"
    MEASUREMENT_ADEQUACY = "MEASUREMENT_ADEQUACY"
    STATISTICAL_SUFFICIENCY = "STATISTICAL_SUFFICIENCY"
    SECRECY_ROLE_SEPARATION = "SECRECY_ROLE_SEPARATION"
    CENSORING_LIMITATIONS = "CENSORING_LIMITATIONS"
    IMPLEMENTATION_VERIFICATION = "IMPLEMENTATION_VERIFICATION"
    DISCRETIZATION_CONVERGENCE = "DISCRETIZATION_CONVERGENCE"
    REFERENCE_AGREEMENT = "REFERENCE_AGREEMENT"
    LIMITING_CASE_BEHAVIOR = "LIMITING_CASE_BEHAVIOR"
    GENERATOR_CONFORMANCE_DIAGNOSTIC = "GENERATOR_CONFORMANCE_DIAGNOSTIC"
    MEASUREMENT_FLOOR_DIAGNOSTIC = "MEASUREMENT_FLOOR_DIAGNOSTIC"
    DECISION_RESOLUTION_DIAGNOSTIC = "DECISION_RESOLUTION_DIAGNOSTIC"
    RESIDUAL_LIMITATION_DISCLOSURE = "RESIDUAL_LIMITATION_DISCLOSURE"
    CUSTOMER_CONTEXT_OF_USE = "CUSTOMER_CONTEXT_OF_USE"
    PRODUCT_QUALIFICATION = "PRODUCT_QUALIFICATION"
    LIVE_ACTIVATION = "LIVE_ACTIVATION"


DOSSIER_PRIMARY_CLAIM_ROLE = MappingProxyType(
    dict(
        zip(
            DOSSIER_SLOT_ORDER,
            tuple(DossierClaimRole)[:12],
            strict=True,
        )
    )
)


EVIDENCE_CLASS_ALLOWED_CLAIMS = MappingProxyType(
    {
        **{
            DOSSIER_PRIMARY_EVIDENCE_CLASS[slot]: frozenset(
                {DOSSIER_PRIMARY_CLAIM_ROLE[slot]}
            )
            for slot in DOSSIER_SLOT_ORDER
        },
        DossierEvidenceClass.MMS_REFINEMENT_OBSERVED_ORDER: frozenset(
            {
                DossierClaimRole.IMPLEMENTATION_VERIFICATION,
                DossierClaimRole.DISCRETIZATION_CONVERGENCE,
                DossierClaimRole.REFERENCE_AGREEMENT,
                DossierClaimRole.LIMITING_CASE_BEHAVIOR,
            }
        ),
        DossierEvidenceClass.PLANTED_DEFECT_MUTATION_CAMPAIGN: frozenset(
            {DossierClaimRole.IMPLEMENTATION_VERIFICATION}
        ),
        DossierEvidenceClass.ANALYTIC_LIMITING_CASE_ANCHOR: frozenset(
            {
                DossierClaimRole.IMPLEMENTATION_VERIFICATION,
                DossierClaimRole.REFERENCE_AGREEMENT,
                DossierClaimRole.LIMITING_CASE_BEHAVIOR,
            }
        ),
        DossierEvidenceClass.PRIMARY_WITNESS_CONVERGENCE: frozenset(
            {
                DossierClaimRole.DISCRETIZATION_CONVERGENCE,
                DossierClaimRole.REFERENCE_AGREEMENT,
            }
        ),
        DossierEvidenceClass.REFERENCE_DISAGREEMENT: frozenset(
            {DossierClaimRole.REFERENCE_AGREEMENT}
        ),
        DossierEvidenceClass.GENERATOR_ORACLE_ADVERSARIAL_TEST: frozenset(
            {
                DossierClaimRole.IMPLEMENTATION_VERIFICATION,
                DossierClaimRole.GENERATOR_CONFORMANCE_DIAGNOSTIC,
            }
        ),
        DossierEvidenceClass.MEASUREMENT_FLOOR: frozenset(
            {DossierClaimRole.MEASUREMENT_FLOOR_DIAGNOSTIC}
        ),
        DossierEvidenceClass.DECISION_RESOLUTION_STUDY: frozenset(
            {DossierClaimRole.DECISION_RESOLUTION_DIAGNOSTIC}
        ),
        DossierEvidenceClass.RESIDUAL_LIMITATION: frozenset(
            {DossierClaimRole.RESIDUAL_LIMITATION_DISCLOSURE}
        ),
    }
)


class DependencePolicyAuthorityStatus(str, Enum):
    OWNER_RATIFICATION_PENDING = "OWNER_RATIFICATION_PENDING"


class AttemptDisposition(str, Enum):
    VALID_EVIDENCE = "VALID_EVIDENCE"
    GENERATOR_FAILURE = "GENERATOR_FAILURE"
    REFERENCE_FAILURE = "REFERENCE_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    CANDIDATE_FAILURE = "CANDIDATE_FAILURE"
    TIMEOUT = "TIMEOUT"
    INVALID_CASE = "INVALID_CASE"
    MEASUREMENT_NOT_APPLICABLE = "MEASUREMENT_NOT_APPLICABLE"
    CORRUPTED_OBSERVATION = "CORRUPTED_OBSERVATION"
    EXCLUDED_BY_REGISTERED_POLICY = "EXCLUDED_BY_REGISTERED_POLICY"


class QualificationCandidateState(str, Enum):
    INCOMPLETE = "INCOMPLETE"
    COMPLETE_STRUCTURAL = "COMPLETE_STRUCTURAL"


class ArtifactCurrentness(str, Enum):
    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


class QualificationArtifactKind(str, Enum):
    PHYSICAL_SYSTEM_SPEC = "PHYSICAL_SYSTEM_SPEC"
    CLAIM_SCOPE = "CLAIM_SCOPE"
    TARGET_POPULATION = "TARGET_POPULATION"
    SAMPLING_PLAN = "SAMPLING_PLAN"
    GENERATOR = "GENERATOR"
    REFERENCE_POLICY = "REFERENCE_POLICY"
    CANDIDATE_OUTPUT_CONTRACT = "CANDIDATE_OUTPUT_CONTRACT"
    REPRESENTATION_ADAPTER = "REPRESENTATION_ADAPTER"
    APPLICABILITY_RATIONALE = "APPLICABILITY_RATIONALE"
    MEASUREMENT_CONTRACT = "MEASUREMENT_CONTRACT"
    VALIDATION_DOSSIER = "VALIDATION_DOSSIER"
    EVIDENCE_MANIFEST = "EVIDENCE_MANIFEST"
    SIGNER_IDENTITY = "SIGNER_IDENTITY"
    SIGNER_SIGNATURE = "SIGNER_SIGNATURE"
    SIGNER_AUTHORIZATION_EVIDENCE = "SIGNER_AUTHORIZATION_EVIDENCE"
    A3_QUALIFICATION_ARTIFACT = "A3_QUALIFICATION_ARTIFACT"


class RepresentationApplicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE_WITH_RATIONALE = "NOT_APPLICABLE_WITH_RATIONALE"


class SignerIdentityValidation(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    STRUCTURALLY_VALID = "STRUCTURALLY_VALID"


class SignerRoleAuthorization(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    AUTHORIZED_FOR_ROLE = "AUTHORIZED_FOR_ROLE"


class SignatureVerification(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    CRYPTOGRAPHICALLY_VERIFIED = "CRYPTOGRAPHICALLY_VERIFIED"


class QualificationMismatchReason(str, Enum):
    CHALLENGE_KEY_MISMATCH = "qualification.challenge_key_mismatch"
    CANDIDATE_INCOMPLETE = "qualification.candidate_incomplete"
    DOSSIER_INCOMPLETE = "qualification.dossier_incomplete"
    DOSSIER_FIXTURE_DERIVED = "qualification.dossier_fixture_derived"
    DOSSIER_STALE_OR_SUPERSEDED = "qualification.dossier_stale_or_superseded"
    EVIDENCE_MISSING = "qualification.evidence_missing"
    EVIDENCE_PLACEHOLDER = "qualification.evidence_placeholder"
    EVIDENCE_FIXTURE_DERIVED = "qualification.evidence_fixture_derived"
    EVIDENCE_STALE_OR_SUPERSEDED = "qualification.evidence_stale_or_superseded"
    SIGNER_SLOT_MISSING = "qualification.signer_slot_missing"
    SIGNER_FIXTURE_DERIVED = "qualification.signer_fixture_derived"
    SIGNER_AUTHORIZATION_MISSING = "qualification.signer_authorization_missing"
    SIGNER_AUTHORIZATION_BINDING_MISMATCH = (
        "qualification.signer_authorization_binding_mismatch"
    )
    SIGNER_IDENTITY_UNVERIFIED = "qualification.signer_identity_unverified"
    SIGNER_ROLE_UNAUTHORIZED = "qualification.signer_role_unauthorized"
    SIGNATURE_UNVERIFIED = "qualification.signature_unverified"
    ARTIFACT_FIXTURE_DERIVED = "qualification.artifact_fixture_derived"
    ARTIFACT_STALE_OR_SUPERSEDED = "qualification.artifact_stale_or_superseded"
    REGISTRY_LIFECYCLE_INCOMPATIBLE = "qualification.registry_lifecycle_incompatible"
    REGISTRY_FIXTURE_ORIGIN = "qualification.registry_fixture_origin"
    REGISTRY_QUALIFICATION_MISSING = "qualification.registry_manifest_missing"
    REGISTRY_QUALIFICATION_CHALLENGE_MISMATCH = (
        "qualification.registry_manifest_challenge_mismatch"
    )
    REGISTRY_QUALIFICATION_MODE_MISMATCH = (
        "qualification.registry_manifest_mode_mismatch"
    )
    REGISTRY_QUALIFICATION_DIGEST_MISMATCH = (
        "qualification.registry_manifest_digest_mismatch"
    )
    REGISTRY_AUTHORING_GRAPH_FINGERPRINT_MISSING = (
        "qualification.registry_authoring_graph_fingerprint_missing"
    )
    REGISTRY_AUTHORING_GRAPH_FINGERPRINT_MISMATCH = (
        "qualification.registry_authoring_graph_fingerprint_mismatch"
    )
    REGISTRY_SLOT_MISSING = "qualification.registry_slot_missing"
    REGISTRY_SLOT_STATE_MISMATCH = "qualification.registry_slot_state_mismatch"
    REGISTRY_SLOT_ARTIFACT_MISMATCH = "qualification.registry_slot_artifact_mismatch"
    REGISTRY_ARTIFACT_MISSING = "qualification.registry_artifact_missing"
    REGISTRY_ARTIFACT_UNEXPECTED = "qualification.registry_artifact_unexpected"
    DOSSIER_DIGEST_MISMATCH = "qualification.dossier_digest_mismatch"
    MEASUREMENT_SET_MISMATCH = "qualification.measurement_set_mismatch"
    REGISTRY_ARTIFACT_DIGEST_MISMATCH = (
        "qualification.registry_artifact_digest_mismatch"
    )


__all__ = (
    "DOSSIER_PRIMARY_CLAIM_ROLE",
    "DOSSIER_PRIMARY_EVIDENCE_CLASS",
    "DOSSIER_SLOT_ORDER",
    "DOSSIER_SLOT_TITLES",
    "EVIDENCE_CLASS_ALLOWED_CLAIMS",
    "REQUIRED_SIGNER_ROLE_ORDER",
    "ArtifactCurrentness",
    "AttemptDisposition",
    "DependencePolicyAuthorityStatus",
    "DossierClaimRole",
    "DossierEvidenceClass",
    "DossierSlot",
    "EvidenceCompleteness",
    "EvidenceRequirement",
    "EvidenceSectionStatus",
    "QualificationArtifactKind",
    "QualificationCandidateState",
    "QualificationMismatchReason",
    "RepresentationApplicability",
    "SignatureVerification",
    "SignerArtifactKind",
    "SignerBindingState",
    "SignerIdentityValidation",
    "SignerRole",
    "SignerRoleAuthorization",
    "StructuralOrigin",
)
