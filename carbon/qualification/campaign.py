"""Typed B-06 campaign evidence manifests; no campaign execution or verdicts."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from carbon.authoring.refs import (
    ChallengeScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    owner_ref,
    reconstruct_top_level_ref,
    require_owner_ref,
)
from carbon.measurement.enums import MeasurementDefinitionKind
from carbon.measurement.refs import MeasurementContractRef, MeasurementDefinitionRef
from carbon.registry.model import ChallengeKey

from .enums import (
    CAMPAIGN_ALLOWED_RESULT_STATUSES,
    CAMPAIGN_FAMILY_EVIDENCE_CLASSES,
    ArtifactCurrentness,
    AttemptDisposition,
    CampaignAcquisitionState,
    CampaignArtifactRole,
    CampaignAuthorityStatus,
    CampaignFamily,
    CampaignFieldAuthority,
    CampaignResultStatus,
    CampaignSubjectRole,
    DossierEvidenceClass,
    StructuralOrigin,
    effective_structural_origin,
)
from .errors import DossierInputCode, DossierValidationError
from .evidence import EvidenceAttemptBinding
from .refs import (
    CAMPAIGN_MANIFEST_CANONICALIZATION_PROFILE,
    CAMPAIGN_MANIFEST_SCHEMA_VERSION,
    CampaignEvidenceManifestRef,
    validate_dossier_identifier,
)


def _invalid(path: str, code: DossierInputCode = DossierInputCode.INVALID_VALUE):
    return DossierValidationError(code, path=path)


def _exact(value: object, expected: type, path: str):
    if type(value) is not expected:
        raise _invalid(path, DossierInputCode.WRONG_TYPE)
    return value


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        from carbon.authoring.primitives import reconstruct_challenge_key

        return reconstruct_challenge_key(value)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.WRONG_TYPE) from None


def _same_challenge(value: ChallengeKey, expected: ChallengeKey, path: str) -> None:
    if value != expected:
        raise _invalid(path, DossierInputCode.CROSS_CHALLENGE)


def _identifier(value: object, path: str) -> str:
    return validate_dossier_identifier(value, path)


def _version(value: object, path: str) -> str:
    try:
        from carbon.authoring.primitives import validate_version_token

        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _digest(value: object, path: str) -> str:
    try:
        from carbon.authoring.primitives import validate_tagged_sha256

        return validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _copy_owner(value: object, kind: str, challenge: ChallengeKey, path: str):
    try:
        result = require_owner_ref(value, kind)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.ROLE_CONFUSION) from None
    if type(result.scope_binding) is not ChallengeScope:
        raise _invalid(path, DossierInputCode.ROLE_CONFUSION)
    _same_challenge(result.scope_binding.challenge_key, challenge, path)
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(result.scope_binding.challenge_key),
        object_id=result.object_id,
        object_version=result.object_version,
        content_digest=result.content_digest,
    )


def _copy_top(value: object, expected: type, challenge: ChallengeKey, path: str):
    try:
        result = reconstruct_top_level_ref(value)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.WRONG_TYPE) from None
    if type(result) is not expected:
        raise _invalid(path, DossierInputCode.ROLE_CONFUSION)
    _same_challenge(result.challenge_key, challenge, path)
    return result


def _copy_measurement(value: object, challenge: ChallengeKey, path: str):
    if type(value) is not MeasurementContractRef:
        raise _invalid(path, DossierInputCode.ROLE_CONFUSION)
    try:
        result = MeasurementContractRef(
            value.challenge_key,
            value.content_digest,
            value.schema_version,
            value.canonicalization_profile,
        )
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.WRONG_TYPE) from None
    _same_challenge(result.challenge_key, challenge, path)
    return result


def _copy_definition(value: object, challenge: ChallengeKey, path: str):
    if type(value) is not MeasurementDefinitionRef:
        raise _invalid(path, DossierInputCode.WRONG_TYPE)
    try:
        result = MeasurementDefinitionRef(
            value.challenge_key,
            value.definition_kind,
            value.object_id,
            value.object_version,
            value.content_digest,
            value.schema_version,
            value.canonicalization_profile,
        )
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.WRONG_TYPE) from None
    _same_challenge(result.challenge_key, challenge, path)
    return result


class _ProtectedCampaignRecord:
    def __repr__(self) -> str:
        return f"{type(self).__name__}(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected campaign records cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected campaign records cannot be pickled")


_SUBJECT_SPEC = MappingProxyType(
    {
        CampaignSubjectRole.CLAIM_SCOPE: ("owner", "claim_scope"),
        CampaignSubjectRole.PHYSICAL_SYSTEM: ("top", PhysicalSystemSpecRef),
        CampaignSubjectRole.TARGET_POPULATION: (
            "top",
            InstanceDistributionContractRef,
        ),
        CampaignSubjectRole.SAMPLING_PLAN: ("top", SamplingPlanRef),
        CampaignSubjectRole.GENERATOR: ("owner", "generator"),
        CampaignSubjectRole.REFERENCE_POLICY: (
            "owner",
            "reference_qualification_policy",
        ),
        CampaignSubjectRole.REPRESENTATION: ("owner", "representation"),
        CampaignSubjectRole.MEASUREMENT_CONTRACT: (
            "measurement",
            MeasurementContractRef,
        ),
    }
)


@dataclass(frozen=True, slots=True, repr=False)
class CampaignSubjectBinding(_ProtectedCampaignRecord):
    challenge_key: ChallengeKey
    subject_role: CampaignSubjectRole
    subject_ref: object

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        _exact(self.subject_role, CampaignSubjectRole, "/subject_role")
        category, expected = _SUBJECT_SPEC[self.subject_role]
        if category == "owner":
            value = _copy_owner(self.subject_ref, expected, challenge, "/subject_ref")
        elif category == "top":
            value = _copy_top(self.subject_ref, expected, challenge, "/subject_ref")
            if (
                self.subject_role is CampaignSubjectRole.TARGET_POPULATION
                and value.expected_population_role != "TARGET_WORKLOAD_P"
            ):
                raise _invalid("/subject_ref", DossierInputCode.ROLE_CONFUSION)
        else:
            value = _copy_measurement(self.subject_ref, challenge, "/subject_ref")
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "subject_ref", value)


@dataclass(frozen=True, slots=True, repr=False)
class CampaignArtifactRef(_ProtectedCampaignRecord):
    challenge_key: ChallengeKey
    artifact_role: CampaignArtifactRole
    artifact_id: str
    artifact_version: str
    content_digest: str
    origin: StructuralOrigin
    currentness: ArtifactCurrentness = ArtifactCurrentness.CURRENT

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        _exact(self.artifact_role, CampaignArtifactRole, "/artifact_role")
        _exact(self.origin, StructuralOrigin, "/origin")
        _exact(self.currentness, ArtifactCurrentness, "/currentness")
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self, "artifact_id", _identifier(self.artifact_id, "/artifact_id")
        )
        object.__setattr__(
            self,
            "artifact_version",
            _version(self.artifact_version, "/artifact_version"),
        )
        object.__setattr__(
            self, "content_digest", _digest(self.content_digest, "/content_digest")
        )


_COMMON_ACQUISITION_ROLES = frozenset(
    {
        CampaignArtifactRole.CAMPAIGN_DEFINITION,
        CampaignArtifactRole.ACQUISITION_OPERATION,
        CampaignArtifactRole.PROVENANCE,
        CampaignArtifactRole.ENVIRONMENT_TOOL,
    }
)

CAMPAIGN_REQUIRED_SUBJECT_ROLES = MappingProxyType(
    {
        CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER: frozenset(
            {
                CampaignSubjectRole.CLAIM_SCOPE,
                CampaignSubjectRole.PHYSICAL_SYSTEM,
                CampaignSubjectRole.REFERENCE_POLICY,
                CampaignSubjectRole.MEASUREMENT_CONTRACT,
            }
        ),
        CampaignFamily.PLANTED_DEFECT_MUTATION: frozenset(
            {
                CampaignSubjectRole.CLAIM_SCOPE,
                CampaignSubjectRole.PHYSICAL_SYSTEM,
                CampaignSubjectRole.MEASUREMENT_CONTRACT,
            }
        ),
        CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR: frozenset(
            {
                CampaignSubjectRole.CLAIM_SCOPE,
                CampaignSubjectRole.PHYSICAL_SYSTEM,
                CampaignSubjectRole.REFERENCE_POLICY,
                CampaignSubjectRole.MEASUREMENT_CONTRACT,
            }
        ),
        CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT: frozenset(
            {
                CampaignSubjectRole.CLAIM_SCOPE,
                CampaignSubjectRole.PHYSICAL_SYSTEM,
                CampaignSubjectRole.REFERENCE_POLICY,
            }
        ),
        CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL: frozenset(
            {
                CampaignSubjectRole.CLAIM_SCOPE,
                CampaignSubjectRole.TARGET_POPULATION,
                CampaignSubjectRole.SAMPLING_PLAN,
                CampaignSubjectRole.GENERATOR,
            }
        ),
        CampaignFamily.MEASUREMENT_FLOOR: frozenset(
            {
                CampaignSubjectRole.CLAIM_SCOPE,
                CampaignSubjectRole.REFERENCE_POLICY,
                CampaignSubjectRole.MEASUREMENT_CONTRACT,
            }
        ),
        CampaignFamily.DECISION_RESOLUTION: frozenset(
            {
                CampaignSubjectRole.CLAIM_SCOPE,
                CampaignSubjectRole.TARGET_POPULATION,
                CampaignSubjectRole.SAMPLING_PLAN,
                CampaignSubjectRole.MEASUREMENT_CONTRACT,
            }
        ),
        CampaignFamily.RESIDUAL_LIMITATION: frozenset(
            {CampaignSubjectRole.CLAIM_SCOPE}
        ),
    }
)

CAMPAIGN_ALLOWED_SUBJECT_ROLES = MappingProxyType(
    {
        CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER: (
            CAMPAIGN_REQUIRED_SUBJECT_ROLES[
                CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER
            ]
            | {CampaignSubjectRole.REPRESENTATION}
        ),
        CampaignFamily.PLANTED_DEFECT_MUTATION: (
            CAMPAIGN_REQUIRED_SUBJECT_ROLES[CampaignFamily.PLANTED_DEFECT_MUTATION]
            | {CampaignSubjectRole.REPRESENTATION}
        ),
        CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR: (
            CAMPAIGN_REQUIRED_SUBJECT_ROLES[
                CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR
            ]
            | {CampaignSubjectRole.REPRESENTATION}
        ),
        CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT: (
            CAMPAIGN_REQUIRED_SUBJECT_ROLES[
                CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT
            ]
            | {
                CampaignSubjectRole.REPRESENTATION,
                CampaignSubjectRole.MEASUREMENT_CONTRACT,
            }
        ),
        CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL: (
            CAMPAIGN_REQUIRED_SUBJECT_ROLES[CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL]
            | {CampaignSubjectRole.REPRESENTATION}
        ),
        CampaignFamily.MEASUREMENT_FLOOR: (
            CAMPAIGN_REQUIRED_SUBJECT_ROLES[CampaignFamily.MEASUREMENT_FLOOR]
            | {CampaignSubjectRole.REPRESENTATION}
        ),
        CampaignFamily.DECISION_RESOLUTION: (
            CAMPAIGN_REQUIRED_SUBJECT_ROLES[CampaignFamily.DECISION_RESOLUTION]
            | {
                CampaignSubjectRole.REFERENCE_POLICY,
                CampaignSubjectRole.REPRESENTATION,
            }
        ),
        CampaignFamily.RESIDUAL_LIMITATION: frozenset(CampaignSubjectRole),
    }
)

CAMPAIGN_REQUIRED_DEFINITION_KINDS = MappingProxyType(
    {
        CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER: frozenset(
            {
                MeasurementDefinitionKind.IMPLEMENTATION,
                MeasurementDefinitionKind.OBSERVABLE,
                MeasurementDefinitionKind.DISCRETIZATION,
                MeasurementDefinitionKind.CASE_SCOPE,
            }
        ),
        CampaignFamily.PLANTED_DEFECT_MUTATION: frozenset(
            {
                MeasurementDefinitionKind.SCIENTIFIC_PROPERTY,
                MeasurementDefinitionKind.CASE_SCOPE,
            }
        ),
        CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR: frozenset(
            {
                MeasurementDefinitionKind.IMPLEMENTATION,
                MeasurementDefinitionKind.CASE_SCOPE,
                MeasurementDefinitionKind.APPLICABILITY_POLICY,
            }
        ),
        CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT: frozenset(
            {
                MeasurementDefinitionKind.DISCRETIZATION,
                MeasurementDefinitionKind.CASE_SCOPE,
            }
        ),
        CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL: frozenset(
            {MeasurementDefinitionKind.CASE_SCOPE}
        ),
        CampaignFamily.MEASUREMENT_FLOOR: frozenset(
            {
                MeasurementDefinitionKind.DISCRETIZATION,
                MeasurementDefinitionKind.SAMPLING_QUADRATURE,
                MeasurementDefinitionKind.CASE_SCOPE,
                MeasurementDefinitionKind.APPLICABILITY_POLICY,
            }
        ),
        CampaignFamily.DECISION_RESOLUTION: frozenset(
            {
                MeasurementDefinitionKind.ESTIMAND,
                MeasurementDefinitionKind.RESAMPLING_UNIT,
                MeasurementDefinitionKind.DEPENDENCE_ASSUMPTION,
                MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL,
                MeasurementDefinitionKind.CASE_SCOPE,
                MeasurementDefinitionKind.CENSORING_ACCOUNTING,
                MeasurementDefinitionKind.STOPPING_RULE,
            }
        ),
        CampaignFamily.RESIDUAL_LIMITATION: frozenset(
            {
                MeasurementDefinitionKind.CASE_SCOPE,
                MeasurementDefinitionKind.KNOWN_LIMITATION,
            }
        ),
    }
)

CAMPAIGN_ALLOWED_DEFINITION_KINDS = MappingProxyType(
    {
        CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER: (
            CAMPAIGN_REQUIRED_DEFINITION_KINDS[
                CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER
            ]
            | {
                MeasurementDefinitionKind.STRATUM,
                MeasurementDefinitionKind.SCIENTIFIC_PROPERTY,
                MeasurementDefinitionKind.EVIDENCE_SOURCE,
            }
        ),
        CampaignFamily.PLANTED_DEFECT_MUTATION: (
            CAMPAIGN_REQUIRED_DEFINITION_KINDS[CampaignFamily.PLANTED_DEFECT_MUTATION]
            | {
                MeasurementDefinitionKind.STRATUM,
                MeasurementDefinitionKind.IMPLEMENTATION,
                MeasurementDefinitionKind.OBSERVABLE,
            }
        ),
        CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR: (
            CAMPAIGN_REQUIRED_DEFINITION_KINDS[
                CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR
            ]
            | {
                MeasurementDefinitionKind.STRATUM,
                MeasurementDefinitionKind.OBSERVABLE,
                MeasurementDefinitionKind.DISCRETIZATION,
            }
        ),
        CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT: (
            CAMPAIGN_REQUIRED_DEFINITION_KINDS[
                CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT
            ]
            | {
                MeasurementDefinitionKind.STRATUM,
                MeasurementDefinitionKind.OBSERVABLE,
                MeasurementDefinitionKind.APPLICABILITY_POLICY,
                MeasurementDefinitionKind.APPLICABILITY_EVIDENCE,
                MeasurementDefinitionKind.SCIENTIFIC_VALUE,
            }
        ),
        CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL: (
            CAMPAIGN_REQUIRED_DEFINITION_KINDS[
                CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL
            ]
            | {
                MeasurementDefinitionKind.STRATUM,
                MeasurementDefinitionKind.SCIENTIFIC_PROPERTY,
                MeasurementDefinitionKind.OBSERVABLE,
            }
        ),
        CampaignFamily.MEASUREMENT_FLOOR: (
            CAMPAIGN_REQUIRED_DEFINITION_KINDS[CampaignFamily.MEASUREMENT_FLOOR]
            | {
                MeasurementDefinitionKind.STRATUM,
                MeasurementDefinitionKind.OBSERVABLE,
                MeasurementDefinitionKind.SCIENTIFIC_VALUE,
            }
        ),
        CampaignFamily.DECISION_RESOLUTION: (
            CAMPAIGN_REQUIRED_DEFINITION_KINDS[CampaignFamily.DECISION_RESOLUTION]
            | {
                MeasurementDefinitionKind.STRATUM,
                MeasurementDefinitionKind.SAMPLING_UNIT,
                MeasurementDefinitionKind.INDEPENDENCE_UNIT,
                MeasurementDefinitionKind.COMMON_CASE_PAIRING,
                MeasurementDefinitionKind.RECONSTRUCTION_CASE_INTERACTION,
                MeasurementDefinitionKind.RECONSTRUCTION_STRATUM_INTERACTION,
                MeasurementDefinitionKind.JOINT_REFERENCE_UNCERTAINTY,
                MeasurementDefinitionKind.REFERENCE_CANDIDATE_COVARIANCE,
                MeasurementDefinitionKind.REPRESENTATION_DEPENDENCE,
                MeasurementDefinitionKind.EXECUTION_DEPENDENCE,
                MeasurementDefinitionKind.EVIDENCE_SET,
                MeasurementDefinitionKind.APPLICABILITY_TEST,
                MeasurementDefinitionKind.POWER_REQUIREMENT,
                MeasurementDefinitionKind.MINIMUM_RESOLVABLE_IMPROVEMENT,
                MeasurementDefinitionKind.SEQUENTIAL_STOPPING_RULE,
            }
        ),
        CampaignFamily.RESIDUAL_LIMITATION: (
            CAMPAIGN_REQUIRED_DEFINITION_KINDS[CampaignFamily.RESIDUAL_LIMITATION]
            | {
                MeasurementDefinitionKind.STRATUM,
                MeasurementDefinitionKind.APPLICABILITY_REASON,
                MeasurementDefinitionKind.SCIENTIFIC_VALUE,
            }
        ),
    }
)

CAMPAIGN_REQUIRED_ACQUISITION_ARTIFACT_ROLES = MappingProxyType(
    {
        CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER: _COMMON_ACQUISITION_ROLES
        | {
            CampaignArtifactRole.IMPLEMENTATION_UNDER_TEST,
            CampaignArtifactRole.MANUFACTURED_ANALYTIC_DEFINITION,
            CampaignArtifactRole.REFINEMENT_FAMILY,
        },
        CampaignFamily.PLANTED_DEFECT_MUTATION: _COMMON_ACQUISITION_ROLES
        | {
            CampaignArtifactRole.SYSTEM_COMPONENT,
            CampaignArtifactRole.MUTATION_OPERATOR,
            CampaignArtifactRole.PLANTED_DEFECT,
            CampaignArtifactRole.AFFECTED_PROPERTY,
        },
        CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR: _COMMON_ACQUISITION_ROLES
        | {
            CampaignArtifactRole.ANALYTIC_LIMITING_AUTHORITY,
            CampaignArtifactRole.APPLICABILITY_DOMAIN,
            CampaignArtifactRole.ACQUISITION_CONFIGURATION,
            CampaignArtifactRole.COMPARISON_METHOD,
        },
        CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT: (
            _COMMON_ACQUISITION_ROLES
            | {
                CampaignArtifactRole.PRIMARY_REFERENCE,
                CampaignArtifactRole.WITNESS_REFERENCE,
                CampaignArtifactRole.CONVERGENCE_CONFIGURATION,
                CampaignArtifactRole.COMPARISON_METHOD,
            }
        ),
        CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL: _COMMON_ACQUISITION_ROLES
        | {
            CampaignArtifactRole.ORACLE_CHECKER,
            CampaignArtifactRole.TARGETED_PROPERTY_INVARIANT,
            CampaignArtifactRole.ADVERSARIAL_CONFIGURATION,
        },
        CampaignFamily.MEASUREMENT_FLOOR: _COMMON_ACQUISITION_ROLES
        | {
            CampaignArtifactRole.FLOOR_STUDY,
            CampaignArtifactRole.SOURCE_REFERENCE_CONFIGURATION,
            CampaignArtifactRole.DISCRETIZATION_CONFIGURATION,
            CampaignArtifactRole.SAMPLING_CONFIGURATION,
        },
        CampaignFamily.DECISION_RESOLUTION: _COMMON_ACQUISITION_ROLES
        | {
            CampaignArtifactRole.DECISION_METHOD,
            CampaignArtifactRole.COMPARED_OBJECT,
            CampaignArtifactRole.COVERAGE_POWER_DIAGNOSTIC,
            CampaignArtifactRole.CENSORING_MISSINGNESS,
            CampaignArtifactRole.STOPPING_FALSE_ELIMINATION_AUDIT,
        },
        CampaignFamily.RESIDUAL_LIMITATION: _COMMON_ACQUISITION_ROLES
        | {
            CampaignArtifactRole.AFFECTED_EVIDENCE,
            CampaignArtifactRole.AFFECTED_CLAIM,
            CampaignArtifactRole.AFFECTED_SCOPE,
        },
    }
)

CAMPAIGN_ALLOWED_ACQUISITION_ARTIFACT_ROLES = MappingProxyType(
    {
        **dict(CAMPAIGN_REQUIRED_ACQUISITION_ARTIFACT_ROLES),
        CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER: (
            CAMPAIGN_REQUIRED_ACQUISITION_ARTIFACT_ROLES[
                CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER
            ]
            | {CampaignArtifactRole.FIT_ESTIMATION_METHOD}
        ),
    }
)

CAMPAIGN_REQUIRED_RESULT_ARTIFACT_ROLES = MappingProxyType(
    {
        CampaignFamily.MMS_REFINEMENT_OBSERVED_ORDER: frozenset(
            {
                CampaignArtifactRole.PER_LEVEL_RESULT,
                CampaignArtifactRole.OBSERVED_ORDER_RESULT,
                CampaignArtifactRole.UNCERTAINTY,
                CampaignArtifactRole.LIMITATION,
            }
        ),
        CampaignFamily.PLANTED_DEFECT_MUTATION: frozenset(
            {CampaignArtifactRole.CAMPAIGN_RESULT, CampaignArtifactRole.LIMITATION}
        ),
        CampaignFamily.ANALYTIC_LIMITING_CASE_ANCHOR: frozenset(
            {
                CampaignArtifactRole.COMPARISON_RESULT,
                CampaignArtifactRole.UNCERTAINTY,
                CampaignArtifactRole.LIMITATION,
            }
        ),
        CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT: frozenset(
            {
                CampaignArtifactRole.DISAGREEMENT_RESULT,
                CampaignArtifactRole.UNCERTAINTY,
                CampaignArtifactRole.LIMITATION,
            }
        ),
        CampaignFamily.GENERATOR_ORACLE_ADVERSARIAL: frozenset(
            {CampaignArtifactRole.ADVERSARIAL_RESULT, CampaignArtifactRole.LIMITATION}
        ),
        CampaignFamily.MEASUREMENT_FLOOR: frozenset(
            {
                CampaignArtifactRole.FLOOR_RESULT,
                CampaignArtifactRole.UNCERTAINTY,
                CampaignArtifactRole.LIMITATION,
            }
        ),
        CampaignFamily.DECISION_RESOLUTION: frozenset(
            {
                CampaignArtifactRole.DECISION_RESULT,
                CampaignArtifactRole.UNCERTAINTY,
                CampaignArtifactRole.LIMITATION,
            }
        ),
        CampaignFamily.RESIDUAL_LIMITATION: frozenset(
            {CampaignArtifactRole.LIMITATION, CampaignArtifactRole.UNCERTAINTY}
        ),
    }
)

_RESULT_OPTIONAL_ROLES = frozenset(
    {
        CampaignArtifactRole.EXCLUSION,
        CampaignArtifactRole.FAILURE,
        CampaignArtifactRole.LIMITATION,
        CampaignArtifactRole.UNCERTAINTY,
    }
)

_MULTI_ARTIFACT_ROLES = frozenset(
    {
        CampaignArtifactRole.MUTATION_OPERATOR,
        CampaignArtifactRole.PLANTED_DEFECT,
        CampaignArtifactRole.DISCRETIZATION_CONFIGURATION,
        CampaignArtifactRole.COMPARED_OBJECT,
        CampaignArtifactRole.AFFECTED_EVIDENCE,
        CampaignArtifactRole.AFFECTED_CLAIM,
        CampaignArtifactRole.AFFECTED_SCOPE,
        CampaignArtifactRole.PER_LEVEL_RESULT,
        CampaignArtifactRole.EXCLUSION,
        CampaignArtifactRole.FAILURE,
        CampaignArtifactRole.LIMITATION,
        CampaignArtifactRole.UNCERTAINTY,
    }
)


def _artifact_identity(value: CampaignArtifactRef) -> tuple[object, ...]:
    return (value.artifact_role, value.artifact_id, value.artifact_version)


def _copy_artifacts(
    values: object,
    challenge: ChallengeKey,
    path: str,
    *,
    allowed: frozenset[CampaignArtifactRole],
    required: frozenset[CampaignArtifactRole],
) -> tuple[CampaignArtifactRef, ...]:
    if type(values) is not tuple:
        raise _invalid(path, DossierInputCode.WRONG_TYPE)
    copied: list[CampaignArtifactRef] = []
    for index, value in enumerate(values):
        item = _exact(value, CampaignArtifactRef, f"{path}/{index}")
        _same_challenge(item.challenge_key, challenge, f"{path}/{index}")
        if item.artifact_role not in allowed:
            raise _invalid(
                f"{path}/{index}/artifact_role", DossierInputCode.ROLE_CONFUSION
            )
        copied.append(
            CampaignArtifactRef(
                item.challenge_key,
                item.artifact_role,
                item.artifact_id,
                item.artifact_version,
                item.content_digest,
                item.origin,
                item.currentness,
            )
        )
    identities = tuple(_artifact_identity(item) for item in copied)
    if len(set(identities)) != len(identities):
        raise _invalid(path, DossierInputCode.DUPLICATE_IDENTITY)
    roles = tuple(item.artifact_role for item in copied)
    if not required <= set(roles):
        raise _invalid(path, DossierInputCode.MISSING_EVIDENCE)
    for role in set(roles) - _MULTI_ARTIFACT_ROLES:
        if roles.count(role) != 1:
            raise _invalid(path, DossierInputCode.DUPLICATE_IDENTITY)
    return tuple(sorted(copied, key=_artifact_identity))


def _definition_nominal_key(value: MeasurementDefinitionRef) -> tuple[object, ...]:
    return (
        value.definition_kind,
        value.object_id,
        value.object_version,
    )


def _definition_sort_key(value: MeasurementDefinitionRef) -> tuple[object, ...]:
    return (
        *_definition_nominal_key(value),
        value.content_digest,
    )


def _attempt_nominal_key(value: EvidenceAttemptBinding) -> tuple[object, ...]:
    return (
        value.attempt_ref.evidence_class,
        value.attempt_ref.evidence_id,
        value.attempt_ref.evidence_version,
    )


def _attempt_sort_key(value: EvidenceAttemptBinding) -> tuple[object, ...]:
    return (
        *_attempt_nominal_key(value),
        value.attempt_ref.content_digest,
        value.attempt_ref.origin,
        value.disposition,
    )


def _scope_definitions(
    values: tuple[MeasurementDefinitionRef, ...],
) -> tuple[MeasurementDefinitionRef, ...]:
    return tuple(
        value
        for value in values
        if value.definition_kind
        in {
            MeasurementDefinitionKind.CASE_SCOPE,
            MeasurementDefinitionKind.STRATUM,
            MeasurementDefinitionKind.APPLICABILITY_POLICY,
        }
    )


@dataclass(frozen=True, slots=True, repr=False)
class CampaignAcquisitionManifest(_ProtectedCampaignRecord):
    challenge_key: ChallengeKey
    campaign_family: CampaignFamily
    acquisition_id: str
    acquisition_version: str
    acquisition_state: CampaignAcquisitionState
    authority_status: CampaignAuthorityStatus
    subject_bindings: tuple[CampaignSubjectBinding, ...]
    definition_refs: tuple[MeasurementDefinitionRef, ...]
    artifact_refs: tuple[CampaignArtifactRef, ...]
    attempts: tuple[EvidenceAttemptBinding, ...] = ()

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        _exact(self.campaign_family, CampaignFamily, "/campaign_family")
        _exact(self.acquisition_state, CampaignAcquisitionState, "/acquisition_state")
        _exact(self.authority_status, CampaignAuthorityStatus, "/authority_status")
        expected_authority = (
            CampaignAuthorityStatus.OWNER_RATIFICATION_PENDING
            if self.campaign_family is CampaignFamily.DECISION_RESOLUTION
            else CampaignAuthorityStatus.RATIFIED_V2_0_STRUCTURE
        )
        if self.authority_status is not expected_authority:
            raise _invalid("/authority_status", DossierInputCode.ROLE_CONFUSION)

        if type(self.subject_bindings) is not tuple:
            raise _invalid("/subject_bindings", DossierInputCode.WRONG_TYPE)
        subjects: list[CampaignSubjectBinding] = []
        for index, value in enumerate(self.subject_bindings):
            item = _exact(value, CampaignSubjectBinding, f"/subject_bindings/{index}")
            _same_challenge(item.challenge_key, challenge, f"/subject_bindings/{index}")
            subjects.append(
                CampaignSubjectBinding(challenge, item.subject_role, item.subject_ref)
            )
        subject_roles = tuple(item.subject_role for item in subjects)
        if len(set(subject_roles)) != len(subject_roles):
            raise _invalid("/subject_bindings", DossierInputCode.DUPLICATE_IDENTITY)
        if not CAMPAIGN_REQUIRED_SUBJECT_ROLES[self.campaign_family] <= set(
            subject_roles
        ):
            raise _invalid("/subject_bindings", DossierInputCode.MISSING_EVIDENCE)
        if (
            not set(subject_roles)
            <= CAMPAIGN_ALLOWED_SUBJECT_ROLES[self.campaign_family]
        ):
            raise _invalid("/subject_bindings", DossierInputCode.ROLE_CONFUSION)
        subjects.sort(key=lambda item: item.subject_role.value)

        if type(self.definition_refs) is not tuple:
            raise _invalid("/definition_refs", DossierInputCode.WRONG_TYPE)
        definitions = tuple(
            _copy_definition(value, challenge, f"/definition_refs/{index}")
            for index, value in enumerate(self.definition_refs)
        )
        identities = tuple(_definition_nominal_key(value) for value in definitions)
        if len(set(identities)) != len(identities):
            raise _invalid("/definition_refs", DossierInputCode.DUPLICATE_IDENTITY)
        if any(
            value.definition_kind
            not in CAMPAIGN_ALLOWED_DEFINITION_KINDS[self.campaign_family]
            for value in definitions
        ):
            raise _invalid("/definition_refs", DossierInputCode.ROLE_CONFUSION)
        kinds = {value.definition_kind for value in definitions}
        if not CAMPAIGN_REQUIRED_DEFINITION_KINDS[self.campaign_family] <= kinds:
            raise _invalid("/definition_refs", DossierInputCode.MISSING_EVIDENCE)
        definitions = tuple(sorted(definitions, key=_definition_sort_key))

        required_artifacts = CAMPAIGN_REQUIRED_ACQUISITION_ARTIFACT_ROLES[
            self.campaign_family
        ]
        artifacts = _copy_artifacts(
            self.artifact_refs,
            challenge,
            "/artifact_refs",
            allowed=CAMPAIGN_ALLOWED_ACQUISITION_ARTIFACT_ROLES[self.campaign_family],
            required=required_artifacts,
        )
        if (
            self.campaign_family is CampaignFamily.DECISION_RESOLUTION
            and sum(
                item.artifact_role is CampaignArtifactRole.COMPARED_OBJECT
                for item in artifacts
            )
            < 2
        ):
            raise _invalid("/artifact_refs", DossierInputCode.MISSING_EVIDENCE)
        if (
            self.campaign_family
            is CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT
        ):
            identities_by_role = {
                item.artifact_role: (
                    item.artifact_id,
                    item.artifact_version,
                    item.content_digest,
                )
                for item in artifacts
            }
            if (
                identities_by_role[CampaignArtifactRole.PRIMARY_REFERENCE]
                == identities_by_role[CampaignArtifactRole.WITNESS_REFERENCE]
            ):
                raise _invalid("/artifact_refs", DossierInputCode.ROLE_CONFUSION)

        if type(self.attempts) is not tuple:
            raise _invalid("/attempts", DossierInputCode.WRONG_TYPE)
        attempts: list[EvidenceAttemptBinding] = []
        for index, value in enumerate(self.attempts):
            item = _exact(value, EvidenceAttemptBinding, f"/attempts/{index}")
            _same_challenge(item.challenge_key, challenge, f"/attempts/{index}")
            attempts.append(
                EvidenceAttemptBinding(
                    item.challenge_key, item.attempt_ref, item.disposition
                )
            )
        attempt_ids = tuple(_attempt_nominal_key(item) for item in attempts)
        if len(set(attempt_ids)) != len(attempt_ids):
            raise _invalid("/attempts", DossierInputCode.DUPLICATE_IDENTITY)
        attempts.sort(key=_attempt_sort_key)

        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self, "acquisition_id", _identifier(self.acquisition_id, "/acquisition_id")
        )
        object.__setattr__(
            self,
            "acquisition_version",
            _version(self.acquisition_version, "/acquisition_version"),
        )
        object.__setattr__(self, "subject_bindings", tuple(subjects))
        object.__setattr__(self, "definition_refs", definitions)
        object.__setattr__(self, "artifact_refs", artifacts)
        object.__setattr__(self, "attempts", tuple(attempts))

    @property
    def scope_refs(self) -> tuple[MeasurementDefinitionRef, ...]:
        return _scope_definitions(self.definition_refs)

    @property
    def fixture_derived(self) -> bool:
        return self.effective_origin is StructuralOrigin.FIXTURE_ONLY

    @property
    def effective_origin(self) -> StructuralOrigin:
        return effective_structural_origin(
            *(item.origin for item in self.artifact_refs),
            *(item.attempt_ref.origin for item in self.attempts),
            StructuralOrigin.REGISTERED_REFERENCE,
        )

    @property
    def structurally_current(self) -> bool:
        return all(
            item.currentness is ArtifactCurrentness.CURRENT
            for item in self.artifact_refs
        )


@dataclass(frozen=True, slots=True, repr=False)
class CampaignResultManifest(_ProtectedCampaignRecord):
    challenge_key: ChallengeKey
    campaign_family: CampaignFamily
    result_id: str
    result_version: str
    acquisition_id: str
    acquisition_version: str
    acquisition_digest: str
    result_status: CampaignResultStatus
    scope_refs: tuple[MeasurementDefinitionRef, ...]
    artifact_refs: tuple[CampaignArtifactRef, ...]
    attempts: tuple[EvidenceAttemptBinding, ...] = ()

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        _exact(self.campaign_family, CampaignFamily, "/campaign_family")
        _exact(self.result_status, CampaignResultStatus, "/result_status")
        if (
            self.result_status
            not in CAMPAIGN_ALLOWED_RESULT_STATUSES[self.campaign_family]
        ):
            raise _invalid("/result_status", DossierInputCode.ROLE_CONFUSION)
        if type(self.scope_refs) is not tuple:
            raise _invalid("/scope_refs", DossierInputCode.WRONG_TYPE)
        scopes = tuple(
            _copy_definition(value, challenge, f"/scope_refs/{index}")
            for index, value in enumerate(self.scope_refs)
        )
        if any(
            value.definition_kind
            not in {
                MeasurementDefinitionKind.CASE_SCOPE,
                MeasurementDefinitionKind.STRATUM,
                MeasurementDefinitionKind.APPLICABILITY_POLICY,
            }
            for value in scopes
        ):
            raise _invalid("/scope_refs", DossierInputCode.ROLE_CONFUSION)
        identities = tuple(_definition_nominal_key(value) for value in scopes)
        if len(set(identities)) != len(identities):
            raise _invalid("/scope_refs", DossierInputCode.DUPLICATE_IDENTITY)
        scopes = tuple(sorted(scopes, key=_definition_sort_key))

        family_required = CAMPAIGN_REQUIRED_RESULT_ARTIFACT_ROLES[self.campaign_family]
        if self.result_status in {
            CampaignResultStatus.BLOCKED,
            CampaignResultStatus.INVALID,
            CampaignResultStatus.REFERENCE_FAILURE,
            CampaignResultStatus.GENERATOR_FAILURE,
        }:
            required = frozenset(
                {CampaignArtifactRole.LIMITATION, CampaignArtifactRole.FAILURE}
            )
        elif self.result_status is CampaignResultStatus.NOT_APPLICABLE:
            required = frozenset(
                {CampaignArtifactRole.LIMITATION, CampaignArtifactRole.EXCLUSION}
            )
        elif self.result_status is CampaignResultStatus.EVIDENCE_DEFERRED:
            required = frozenset({CampaignArtifactRole.LIMITATION})
        else:
            required = family_required
        artifacts = _copy_artifacts(
            self.artifact_refs,
            challenge,
            "/artifact_refs",
            allowed=family_required | _RESULT_OPTIONAL_ROLES,
            required=required,
        )
        if type(self.attempts) is not tuple:
            raise _invalid("/attempts", DossierInputCode.WRONG_TYPE)
        attempts: list[EvidenceAttemptBinding] = []
        for index, value in enumerate(self.attempts):
            item = _exact(value, EvidenceAttemptBinding, f"/attempts/{index}")
            _same_challenge(item.challenge_key, challenge, f"/attempts/{index}")
            attempts.append(
                EvidenceAttemptBinding(
                    item.challenge_key, item.attempt_ref, item.disposition
                )
            )
        attempt_ids = tuple(_attempt_nominal_key(item) for item in attempts)
        if len(set(attempt_ids)) != len(attempt_ids):
            raise _invalid("/attempts", DossierInputCode.DUPLICATE_IDENTITY)
        if self.result_status is CampaignResultStatus.REFERENCE_FAILURE and not any(
            item.disposition is AttemptDisposition.REFERENCE_FAILURE
            for item in attempts
        ):
            raise _invalid("/attempts", DossierInputCode.MISSING_EVIDENCE)
        if self.result_status is CampaignResultStatus.GENERATOR_FAILURE and not any(
            item.disposition is AttemptDisposition.GENERATOR_FAILURE
            for item in attempts
        ):
            raise _invalid("/attempts", DossierInputCode.MISSING_EVIDENCE)
        attempts.sort(key=_attempt_sort_key)

        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "result_id", _identifier(self.result_id, "/result_id"))
        object.__setattr__(
            self,
            "result_version",
            _version(self.result_version, "/result_version"),
        )
        object.__setattr__(
            self, "acquisition_id", _identifier(self.acquisition_id, "/acquisition_id")
        )
        object.__setattr__(
            self,
            "acquisition_version",
            _version(self.acquisition_version, "/acquisition_version"),
        )
        object.__setattr__(
            self,
            "acquisition_digest",
            _digest(self.acquisition_digest, "/acquisition_digest"),
        )
        object.__setattr__(self, "scope_refs", scopes)
        object.__setattr__(self, "artifact_refs", artifacts)
        object.__setattr__(self, "attempts", tuple(attempts))

    @property
    def fixture_derived(self) -> bool:
        return self.effective_origin is StructuralOrigin.FIXTURE_ONLY

    @property
    def effective_origin(self) -> StructuralOrigin:
        return effective_structural_origin(
            *(item.origin for item in self.artifact_refs),
            *(item.attempt_ref.origin for item in self.attempts),
            StructuralOrigin.REGISTERED_REFERENCE,
        )

    @property
    def structurally_current(self) -> bool:
        return all(
            item.currentness is ArtifactCurrentness.CURRENT
            for item in self.artifact_refs
        )


@dataclass(frozen=True, slots=True, repr=False)
class CampaignEvidenceManifest(_ProtectedCampaignRecord):
    challenge_key: ChallengeKey
    campaign_family: CampaignFamily
    evidence_class: DossierEvidenceClass
    manifest_id: str
    manifest_version: str
    origin: StructuralOrigin
    currentness: ArtifactCurrentness
    acquisition: CampaignAcquisitionManifest
    result: CampaignResultManifest | None = None
    supersedes: CampaignEvidenceManifestRef | None = None
    schema_version: str = CAMPAIGN_MANIFEST_SCHEMA_VERSION
    canonicalization_profile: str = CAMPAIGN_MANIFEST_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        from .campaign_canonical import campaign_acquisition_digest

        challenge = _challenge(self.challenge_key)
        _exact(self.campaign_family, CampaignFamily, "/campaign_family")
        _exact(self.evidence_class, DossierEvidenceClass, "/evidence_class")
        if (
            self.evidence_class
            not in CAMPAIGN_FAMILY_EVIDENCE_CLASSES[self.campaign_family]
        ):
            raise _invalid("/evidence_class", DossierInputCode.ROLE_CONFUSION)
        _exact(self.origin, StructuralOrigin, "/origin")
        _exact(self.currentness, ArtifactCurrentness, "/currentness")
        if (
            type(self.schema_version) is not str
            or self.schema_version != CAMPAIGN_MANIFEST_SCHEMA_VERSION
            or type(self.canonicalization_profile) is not str
            or self.canonicalization_profile
            != CAMPAIGN_MANIFEST_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")
        acquisition = _exact(
            self.acquisition, CampaignAcquisitionManifest, "/acquisition"
        )
        _same_challenge(acquisition.challenge_key, challenge, "/acquisition")
        if acquisition.campaign_family is not self.campaign_family:
            raise _invalid(
                "/acquisition/campaign_family", DossierInputCode.ROLE_CONFUSION
            )
        result = self.result
        if result is not None:
            result = _exact(result, CampaignResultManifest, "/result")
            _same_challenge(result.challenge_key, challenge, "/result")
            if result.campaign_family is not self.campaign_family:
                raise _invalid(
                    "/result/campaign_family", DossierInputCode.ROLE_CONFUSION
                )
            if (
                result.acquisition_id != acquisition.acquisition_id
                or result.acquisition_version != acquisition.acquisition_version
            ):
                raise _invalid(
                    "/result/acquisition_id", DossierInputCode.VERSION_MISMATCH
                )
            if result.acquisition_digest != campaign_acquisition_digest(acquisition):
                raise _invalid(
                    "/result/acquisition_digest", DossierInputCode.DIGEST_MISMATCH
                )
            if result.scope_refs != acquisition.scope_refs:
                raise _invalid("/result/scope_refs", DossierInputCode.VERSION_MISMATCH)
            if (
                self.campaign_family
                is CampaignFamily.PRIMARY_WITNESS_CONVERGENCE_DISAGREEMENT
            ):
                status_class = {
                    CampaignResultStatus.REFERENCE_AGREEMENT_OBSERVED: (
                        DossierEvidenceClass.PRIMARY_WITNESS_CONVERGENCE
                    ),
                    CampaignResultStatus.REFERENCE_DISAGREEMENT_OBSERVED: (
                        DossierEvidenceClass.REFERENCE_DISAGREEMENT
                    ),
                }.get(result.result_status)
                if status_class is not None and self.evidence_class is not status_class:
                    raise _invalid("/evidence_class", DossierInputCode.ROLE_CONFUSION)
        predecessor = self.supersedes
        if predecessor is not None:
            predecessor = _exact(
                predecessor, CampaignEvidenceManifestRef, "/supersedes"
            )
            _same_challenge(predecessor.challenge_key, challenge, "/supersedes")
            if (
                predecessor.campaign_family is not self.campaign_family
                or predecessor.evidence_class is not self.evidence_class
                or predecessor.manifest_id != self.manifest_id
            ):
                raise _invalid("/supersedes", DossierInputCode.ROLE_CONFUSION)
            if predecessor.manifest_version == self.manifest_version:
                raise _invalid(
                    "/supersedes/manifest_version", DossierInputCode.VERSION_MISMATCH
                )
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self, "manifest_id", _identifier(self.manifest_id, "/manifest_id")
        )
        object.__setattr__(
            self,
            "manifest_version",
            _version(self.manifest_version, "/manifest_version"),
        )
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "supersedes", predecessor)

    @property
    def fixture_derived(self) -> bool:
        return self.effective_origin is StructuralOrigin.FIXTURE_ONLY

    @property
    def effective_origin(self) -> StructuralOrigin:
        return effective_structural_origin(
            self.origin,
            self.acquisition.effective_origin,
            *(() if self.result is None else (self.result.effective_origin,)),
            *(() if self.supersedes is None else (self.supersedes.origin,)),
        )


_STRUCTURAL = CampaignFieldAuthority.STRUCTURAL_IDENTITY_PROVENANCE
_EXTERNAL = CampaignFieldAuthority.EXTERNALLY_SUPPLIED_SCIENTIFIC_RESULT
CAMPAIGN_FIELD_AUTHORITY = MappingProxyType(
    {
        "CampaignSubjectBinding.challenge_key": _STRUCTURAL,
        "CampaignSubjectBinding.subject_role": _STRUCTURAL,
        "CampaignSubjectBinding.subject_ref": _STRUCTURAL,
        "CampaignArtifactRef.challenge_key": _STRUCTURAL,
        "CampaignArtifactRef.artifact_role": _STRUCTURAL,
        "CampaignArtifactRef.artifact_id": _STRUCTURAL,
        "CampaignArtifactRef.artifact_version": _STRUCTURAL,
        "CampaignArtifactRef.content_digest": _STRUCTURAL,
        "CampaignArtifactRef.origin": _STRUCTURAL,
        "CampaignArtifactRef.currentness": _STRUCTURAL,
        "CampaignAcquisitionManifest.challenge_key": _STRUCTURAL,
        "CampaignAcquisitionManifest.campaign_family": _STRUCTURAL,
        "CampaignAcquisitionManifest.acquisition_id": _STRUCTURAL,
        "CampaignAcquisitionManifest.acquisition_version": _STRUCTURAL,
        "CampaignAcquisitionManifest.acquisition_state": _STRUCTURAL,
        "CampaignAcquisitionManifest.authority_status": (
            CampaignFieldAuthority.OWNER_RATIFICATION_PENDING
        ),
        "CampaignAcquisitionManifest.subject_bindings": _STRUCTURAL,
        "CampaignAcquisitionManifest.definition_refs": _STRUCTURAL,
        "CampaignAcquisitionManifest.artifact_refs": _STRUCTURAL,
        "CampaignAcquisitionManifest.attempts": _STRUCTURAL,
        "CampaignResultManifest.challenge_key": _STRUCTURAL,
        "CampaignResultManifest.campaign_family": _STRUCTURAL,
        "CampaignResultManifest.result_id": _STRUCTURAL,
        "CampaignResultManifest.result_version": _STRUCTURAL,
        "CampaignResultManifest.acquisition_id": _STRUCTURAL,
        "CampaignResultManifest.acquisition_version": _STRUCTURAL,
        "CampaignResultManifest.acquisition_digest": _STRUCTURAL,
        "CampaignResultManifest.result_status": _EXTERNAL,
        "CampaignResultManifest.scope_refs": _STRUCTURAL,
        "CampaignResultManifest.artifact_refs": _EXTERNAL,
        "CampaignResultManifest.attempts": _EXTERNAL,
        "CampaignEvidenceManifest.challenge_key": _STRUCTURAL,
        "CampaignEvidenceManifest.campaign_family": _STRUCTURAL,
        "CampaignEvidenceManifest.evidence_class": _STRUCTURAL,
        "CampaignEvidenceManifest.manifest_id": _STRUCTURAL,
        "CampaignEvidenceManifest.manifest_version": _STRUCTURAL,
        "CampaignEvidenceManifest.origin": _STRUCTURAL,
        "CampaignEvidenceManifest.currentness": _STRUCTURAL,
        "CampaignEvidenceManifest.acquisition": _STRUCTURAL,
        "CampaignEvidenceManifest.result": _EXTERNAL,
        "CampaignEvidenceManifest.supersedes": _STRUCTURAL,
        "CampaignEvidenceManifest.schema_version": _STRUCTURAL,
        "CampaignEvidenceManifest.canonicalization_profile": _STRUCTURAL,
    }
)

CAMPAIGN_UNREPRESENTED_HUMAN_JUDGMENTS = frozenset(
    {
        "evidence_adequacy",
        "scientific_acceptance",
        "signer_authorization",
        "security_acceptance",
        "production_qualification",
        "live_activation",
    }
)


__all__ = (
    "CAMPAIGN_ALLOWED_ACQUISITION_ARTIFACT_ROLES",
    "CAMPAIGN_ALLOWED_DEFINITION_KINDS",
    "CAMPAIGN_ALLOWED_SUBJECT_ROLES",
    "CAMPAIGN_FIELD_AUTHORITY",
    "CAMPAIGN_REQUIRED_ACQUISITION_ARTIFACT_ROLES",
    "CAMPAIGN_REQUIRED_DEFINITION_KINDS",
    "CAMPAIGN_REQUIRED_RESULT_ARTIFACT_ROLES",
    "CAMPAIGN_REQUIRED_SUBJECT_ROLES",
    "CAMPAIGN_UNREPRESENTED_HUMAN_JUDGMENTS",
    "CampaignAcquisitionManifest",
    "CampaignArtifactRef",
    "CampaignEvidenceManifest",
    "CampaignResultManifest",
    "CampaignSubjectBinding",
)
