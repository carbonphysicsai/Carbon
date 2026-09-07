"""Immutable models for the B-E1 fixture reproducibility harness."""

from __future__ import annotations

import math
from dataclasses import dataclass

from carbon.authoring.primitives import reconstruct_challenge_key
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    CanonicalChallengeCaseRef,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
)
from carbon.construction import ResolvedConstructionPlanRef
from carbon.evaluation import (
    ReferenceComparisonOutcome,
    ReferenceRunOutcome,
)
from carbon.evaluation.refs import ReferencePolicyRef
from carbon.measurement import (
    DependenceShortcutKind,
    MeasurementDefinitionKind,
    MeasurementDefinitionRef,
    ReconstructionEvidencePolicyRef,
    ReconstructionEvidenceStatus,
    UncertaintyPolicyRef,
)
from carbon.registry import ChallengeKey

from .enums import (
    REQUIRED_EVIDENCE_FACTORS,
    ApplicabilityStatus,
    AuditStageState,
    BackendProfileSupport,
    ComparisonArm,
    DecisionStability,
    DependencyRelation,
    EvidenceCellState,
    EvidenceFactorKind,
    EvidenceFactorState,
    ProcedureKind,
    ProducerRole,
    R0Outcome,
    R1Outcome,
    ReconstructionAuditStage,
    ReproducibilityRefKind,
    ScientificOutcome,
    ScientificSequentialAction,
    SharedDependencyKind,
    UnresolvedClaimKind,
)
from .errors import ReproducibilityErrorCode, ReproducibilityValidationError
from .refs import (
    REPRODUCIBILITY_CANONICALIZATION_PROFILE,
    REPRODUCIBILITY_SCHEMA_VERSION,
    ReproducibilityRef,
)

MAX_REPRODUCIBILITY_ITEMS = 65_536


def _invalid(
    path: str,
    code: ReproducibilityErrorCode = ReproducibilityErrorCode.INVALID_VALUE,
):
    return ReproducibilityValidationError(code, path=path)


def _exact(value: object, expected: type, path: str):
    if type(value) is not expected:
        raise _invalid(path, ReproducibilityErrorCode.WRONG_TYPE)
    return value


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, ReproducibilityErrorCode.WRONG_TYPE) from None


def _same_challenge(value: ChallengeKey, expected: ChallengeKey, path: str) -> None:
    if value != expected:
        raise _invalid(path, ReproducibilityErrorCode.CROSS_CHALLENGE)


def _ref(
    value: object,
    kind: ReproducibilityRefKind,
    challenge: ChallengeKey,
    path: str,
) -> ReproducibilityRef:
    value = _exact(value, ReproducibilityRef, path)
    if value.ref_kind is not kind:
        raise _invalid(path, ReproducibilityErrorCode.ROLE_CONFUSION)
    _same_challenge(value.challenge_key, challenge, path)
    return value


def _finite(value: object, path: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise _invalid(path, ReproducibilityErrorCode.WRONG_TYPE)
    if value == 0.0 and math.copysign(1.0, value) < 0.0:
        raise _invalid(path)
    return value


def _tuple(value: object, expected: type, path: str, *, nonempty: bool = False):
    if type(value) is not tuple or len(value) > MAX_REPRODUCIBILITY_ITEMS:
        raise _invalid(path, ReproducibilityErrorCode.WRONG_TYPE)
    if nonempty and not value:
        raise _invalid(path, ReproducibilityErrorCode.INCOMPLETE_EVIDENCE)
    return tuple(_exact(item, expected, f"{path}/{i}") for i, item in enumerate(value))


def _ref_key(value: ReproducibilityRef) -> tuple[str, str, str, str]:
    return (
        value.ref_kind.value,
        value.object_id,
        value.object_version,
        value.content_digest,
    )


def _dependency_member_key(
    value: ReproducibilityRef | CanonicalChallengeCaseRef,
) -> tuple[str, str, str, str]:
    if type(value) is ReproducibilityRef:
        return _ref_key(value)
    return (
        "CANONICAL_CHALLENGE_CASE",
        value.object_id,
        value.object_version,
        value.content_digest,
    )


def _dependency_members(
    value: object, path: str
) -> tuple[ReproducibilityRef | CanonicalChallengeCaseRef, ...]:
    if type(value) is not tuple or not value or len(value) > MAX_REPRODUCIBILITY_ITEMS:
        raise _invalid(path, ReproducibilityErrorCode.WRONG_TYPE)
    result = []
    for index, item in enumerate(value):
        if type(item) not in (ReproducibilityRef, CanonicalChallengeCaseRef):
            raise _invalid(f"{path}/{index}", ReproducibilityErrorCode.WRONG_TYPE)
        result.append(item)
    return tuple(result)


def _measurement_ref_key(value: MeasurementDefinitionRef) -> tuple[str, str, str]:
    return value.object_id, value.object_version, value.content_digest


@dataclass(frozen=True, slots=True)
class ExactIdentityManifest:
    challenge_key: ChallengeKey
    candidate_artifact_ref: ReproducibilityRef
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_contract_ref: CandidateOutputContractRef
    target_distribution_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    resolved_plan_ref: ResolvedConstructionPlanRef
    uncertainty_policy_ref: UncertaintyPolicyRef
    reconstruction_policy_ref: ReconstructionEvidencePolicyRef
    reference_policy_ref: ReferencePolicyRef
    generator_ref: ReproducibilityRef
    scoring_ref: ReproducibilityRef
    backend_profile_ref: ReproducibilityRef
    backend_support: BackendProfileSupport
    environment_ref: ReproducibilityRef
    execution_limits_ref: ReproducibilityRef
    seed_role_structure_ref: ReproducibilityRef
    receipt_construction_ref: ReproducibilityRef
    hardware_role_ref: ReproducibilityRef
    fixture_origin: bool
    schema_version: str = REPRODUCIBILITY_SCHEMA_VERSION
    canonicalization_profile: str = REPRODUCIBILITY_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        if type(self) is not ExactIdentityManifest:
            raise _invalid("/record_type", ReproducibilityErrorCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        for name, kind in (
            ("candidate_artifact_ref", ReproducibilityRefKind.CANDIDATE_ARTIFACT),
            ("generator_ref", ReproducibilityRefKind.GENERATOR),
            ("scoring_ref", ReproducibilityRefKind.SCORING),
            ("backend_profile_ref", ReproducibilityRefKind.BACKEND_PROFILE),
            ("environment_ref", ReproducibilityRefKind.ENVIRONMENT),
            ("execution_limits_ref", ReproducibilityRefKind.EXECUTION_LIMITS),
            ("seed_role_structure_ref", ReproducibilityRefKind.SEED_ROLE_STRUCTURE),
            ("receipt_construction_ref", ReproducibilityRefKind.RECEIPT_CONSTRUCTION),
            ("hardware_role_ref", ReproducibilityRefKind.HARDWARE_ROLE),
        ):
            _ref(getattr(self, name), kind, challenge, f"/{name}")
        for name, expected in (
            ("physical_system_ref", PhysicalSystemSpecRef),
            ("candidate_output_contract_ref", CandidateOutputContractRef),
            ("target_distribution_ref", InstanceDistributionContractRef),
            ("sampling_plan_ref", SamplingPlanRef),
            ("resolved_plan_ref", ResolvedConstructionPlanRef),
            ("uncertainty_policy_ref", UncertaintyPolicyRef),
            ("reconstruction_policy_ref", ReconstructionEvidencePolicyRef),
            ("reference_policy_ref", ReferencePolicyRef),
        ):
            value = _exact(getattr(self, name), expected, f"/{name}")
            _same_challenge(value.challenge_key, challenge, f"/{name}")
        _exact(self.backend_support, BackendProfileSupport, "/backend_support")
        if type(self.fixture_origin) is not bool:
            raise _invalid("/fixture_origin", ReproducibilityErrorCode.WRONG_TYPE)
        if not self.fixture_origin:
            raise _invalid("/fixture_origin", ReproducibilityErrorCode.INVALID_VALUE)
        if (
            self.schema_version != REPRODUCIBILITY_SCHEMA_VERSION
            or self.canonicalization_profile != REPRODUCIBILITY_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")


@dataclass(frozen=True, slots=True)
class R0Result:
    outcome: R0Outcome
    mismatched_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        _exact(self.outcome, R0Outcome, "/outcome")
        if type(self.mismatched_fields) is not tuple or any(
            type(item) is not str for item in self.mismatched_fields
        ):
            raise _invalid("/mismatched_fields", ReproducibilityErrorCode.WRONG_TYPE)
        if tuple(sorted(set(self.mismatched_fields))) != self.mismatched_fields:
            raise _invalid("/mismatched_fields")
        if (self.outcome is R0Outcome.EXACT_MATCH) != (not self.mismatched_fields):
            raise _invalid("/outcome")


@dataclass(frozen=True, slots=True)
class NumericalDatum:
    output_ref: ReproducibilityRef
    value: float

    def __post_init__(self) -> None:
        if type(self) is not NumericalDatum:
            raise _invalid("/record_type", ReproducibilityErrorCode.WRONG_TYPE)
        if self.output_ref.ref_kind is not ReproducibilityRefKind.NUMERICAL_OUTPUT:
            raise _invalid("/output_ref", ReproducibilityErrorCode.ROLE_CONFUSION)
        object.__setattr__(self, "value", _finite(self.value, "/value"))


@dataclass(frozen=True, slots=True)
class NumericalRunCapture:
    identity: ExactIdentityManifest
    outputs: tuple[NumericalDatum, ...]

    def __post_init__(self) -> None:
        identity = _exact(self.identity, ExactIdentityManifest, "/identity")
        outputs = _tuple(self.outputs, NumericalDatum, "/outputs", nonempty=True)
        for index, item in enumerate(outputs):
            _same_challenge(
                item.output_ref.challenge_key,
                identity.challenge_key,
                f"/outputs/{index}/output_ref",
            )
        if len({item.output_ref for item in outputs}) != len(outputs):
            raise _invalid("/outputs", ReproducibilityErrorCode.DUPLICATE_IDENTITY)
        object.__setattr__(
            self,
            "outputs",
            tuple(sorted(outputs, key=lambda item: _ref_key(item.output_ref))),
        )


@dataclass(frozen=True, slots=True)
class NumericalProcedureQualification:
    procedure_ref: ReproducibilityRef
    tolerance_policy_ref: ReproducibilityRef
    dossier_qualification_ref: MeasurementDefinitionRef
    backend_profile_ref: ReproducibilityRef
    fixture_origin: bool

    def __post_init__(self) -> None:
        if type(self) is not NumericalProcedureQualification:
            raise _invalid("/record_type", ReproducibilityErrorCode.WRONG_TYPE)
        challenge = self.procedure_ref.challenge_key
        _ref(
            self.procedure_ref,
            ReproducibilityRefKind.PROCEDURE,
            challenge,
            "/procedure_ref",
        )
        _ref(
            self.tolerance_policy_ref,
            ReproducibilityRefKind.TOLERANCE_POLICY,
            challenge,
            "/tolerance_policy_ref",
        )
        _ref(
            self.backend_profile_ref,
            ReproducibilityRefKind.BACKEND_PROFILE,
            challenge,
            "/backend_profile_ref",
        )
        dossier = _exact(
            self.dossier_qualification_ref,
            MeasurementDefinitionRef,
            "/dossier_qualification_ref",
        )
        if (
            dossier.definition_kind
            is not MeasurementDefinitionKind.DOSSIER_QUALIFICATION
        ):
            raise _invalid(
                "/dossier_qualification_ref", ReproducibilityErrorCode.ROLE_CONFUSION
            )
        _same_challenge(dossier.challenge_key, challenge, "/dossier_qualification_ref")
        if self.fixture_origin is not True:
            raise _invalid("/fixture_origin")


@dataclass(frozen=True, slots=True)
class NumericalDelta:
    output_ref: ReproducibilityRef
    absolute_delta: float

    def __post_init__(self) -> None:
        if self.output_ref.ref_kind is not ReproducibilityRefKind.NUMERICAL_OUTPUT:
            raise _invalid("/output_ref", ReproducibilityErrorCode.ROLE_CONFUSION)
        value = _finite(self.absolute_delta, "/absolute_delta")
        if value < 0.0:
            raise _invalid("/absolute_delta")
        object.__setattr__(self, "absolute_delta", value)


@dataclass(frozen=True, slots=True)
class NumericalProcedureDecision:
    outcome: R1Outcome
    deltas: tuple[NumericalDelta, ...]
    decision_ref: ReproducibilityRef

    def __post_init__(self) -> None:
        if self.outcome not in (
            R1Outcome.REPRODUCIBLE,
            R1Outcome.NOT_REPRODUCIBLE,
            R1Outcome.INDETERMINATE,
        ):
            raise _invalid("/outcome")
        deltas = _tuple(self.deltas, NumericalDelta, "/deltas", nonempty=True)
        if len({item.output_ref for item in deltas}) != len(deltas):
            raise _invalid("/deltas", ReproducibilityErrorCode.DUPLICATE_IDENTITY)
        object.__setattr__(
            self,
            "deltas",
            tuple(sorted(deltas, key=lambda item: _ref_key(item.output_ref))),
        )
        if self.decision_ref.ref_kind is not ReproducibilityRefKind.EVIDENCE:
            raise _invalid("/decision_ref", ReproducibilityErrorCode.ROLE_CONFUSION)


@dataclass(frozen=True, slots=True)
class R1Result:
    outcome: R1Outcome
    r0_result: R0Result
    deltas: tuple[NumericalDelta, ...]
    procedure_ref: ReproducibilityRef | None
    decision_ref: ReproducibilityRef | None

    def __post_init__(self) -> None:
        _exact(self.outcome, R1Outcome, "/outcome")
        _exact(self.r0_result, R0Result, "/r0_result")
        _tuple(self.deltas, NumericalDelta, "/deltas")
        if (self.procedure_ref is None) != (self.decision_ref is None):
            raise _invalid("/procedure_ref")


@dataclass(frozen=True, slots=True)
class CaseDesignUnit:
    case_ref: CanonicalChallengeCaseRef
    case_scope_ref: MeasurementDefinitionRef
    stratum_ref: MeasurementDefinitionRef

    def __post_init__(self) -> None:
        case_ref = _exact(self.case_ref, CanonicalChallengeCaseRef, "/case_ref")
        challenge = case_ref.challenge_key
        for name, kind in (
            ("case_scope_ref", MeasurementDefinitionKind.CASE_SCOPE),
            ("stratum_ref", MeasurementDefinitionKind.STRATUM),
        ):
            value = _exact(getattr(self, name), MeasurementDefinitionRef, f"/{name}")
            if value.definition_kind is not kind:
                raise _invalid(f"/{name}", ReproducibilityErrorCode.ROLE_CONFUSION)
            _same_challenge(value.challenge_key, challenge, f"/{name}")


@dataclass(frozen=True, slots=True)
class DependencyDisclosure:
    dependency_ref: ReproducibilityRef
    dependency_kind: SharedDependencyKind
    relation: DependencyRelation
    member_refs: tuple[ReproducibilityRef | CanonicalChallengeCaseRef, ...]
    case_scope_refs: tuple[MeasurementDefinitionRef, ...]
    stratum_scope_refs: tuple[MeasurementDefinitionRef, ...]

    def __post_init__(self) -> None:
        challenge = self.dependency_ref.challenge_key
        _ref(
            self.dependency_ref,
            ReproducibilityRefKind.SHARED_DEPENDENCY,
            challenge,
            "/dependency_ref",
        )
        _exact(self.dependency_kind, SharedDependencyKind, "/dependency_kind")
        _exact(self.relation, DependencyRelation, "/relation")
        members = _dependency_members(self.member_refs, "/member_refs")
        for index, item in enumerate(members):
            _same_challenge(item.challenge_key, challenge, f"/member_refs/{index}")
        if len(set(members)) != len(members):
            raise _invalid("/member_refs", ReproducibilityErrorCode.DUPLICATE_IDENTITY)
        object.__setattr__(
            self, "member_refs", tuple(sorted(members, key=_dependency_member_key))
        )
        for name, kind in (
            ("case_scope_refs", MeasurementDefinitionKind.CASE_SCOPE),
            ("stratum_scope_refs", MeasurementDefinitionKind.STRATUM),
        ):
            values = _tuple(
                getattr(self, name), MeasurementDefinitionRef, f"/{name}", nonempty=True
            )
            for index, item in enumerate(values):
                if item.definition_kind is not kind:
                    raise _invalid(
                        f"/{name}/{index}", ReproducibilityErrorCode.ROLE_CONFUSION
                    )
                _same_challenge(item.challenge_key, challenge, f"/{name}/{index}")
            if len(set(values)) != len(values):
                raise _invalid(f"/{name}", ReproducibilityErrorCode.DUPLICATE_IDENTITY)
            object.__setattr__(
                self, name, tuple(sorted(values, key=_measurement_ref_key))
            )


@dataclass(frozen=True, slots=True)
class CrossedEvidenceDesign:
    challenge_key: ChallengeKey
    incumbent_evidence_ref: MeasurementDefinitionRef
    challenger_evidence_ref: MeasurementDefinitionRef
    uncertainty_policy_ref: UncertaintyPolicyRef
    reconstruction_policy_ref: ReconstructionEvidencePolicyRef
    incumbent_reconstruction_refs: tuple[ReproducibilityRef, ...]
    challenger_reconstruction_refs: tuple[ReproducibilityRef, ...]
    case_units: tuple[CaseDesignUnit, ...]
    required_dependency_kinds: tuple[SharedDependencyKind, ...]
    fixture_origin: bool

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        for name in ("incumbent_evidence_ref", "challenger_evidence_ref"):
            value = _exact(getattr(self, name), MeasurementDefinitionRef, f"/{name}")
            if value.definition_kind is not MeasurementDefinitionKind.EVIDENCE_SET:
                raise _invalid(f"/{name}", ReproducibilityErrorCode.ROLE_CONFUSION)
            _same_challenge(value.challenge_key, challenge, f"/{name}")
        if self.incumbent_evidence_ref == self.challenger_evidence_ref:
            raise _invalid(
                "/challenger_evidence_ref", ReproducibilityErrorCode.DUPLICATE_IDENTITY
            )
        for name, expected in (
            ("uncertainty_policy_ref", UncertaintyPolicyRef),
            ("reconstruction_policy_ref", ReconstructionEvidencePolicyRef),
        ):
            value = _exact(getattr(self, name), expected, f"/{name}")
            _same_challenge(value.challenge_key, challenge, f"/{name}")
        reconstruction_sets: list[tuple[ReproducibilityRef, ...]] = []
        for name in (
            "incumbent_reconstruction_refs",
            "challenger_reconstruction_refs",
        ):
            values = _tuple(
                getattr(self, name), ReproducibilityRef, f"/{name}", nonempty=True
            )
            for index, item in enumerate(values):
                _ref(
                    item,
                    ReproducibilityRefKind.RECONSTRUCTION,
                    challenge,
                    f"/{name}/{index}",
                )
            if len(set(values)) != len(values):
                raise _invalid(f"/{name}", ReproducibilityErrorCode.DUPLICATE_IDENTITY)
            ordered = tuple(sorted(values, key=_ref_key))
            object.__setattr__(self, name, ordered)
            reconstruction_sets.append(ordered)
        if set(reconstruction_sets[0]) & set(reconstruction_sets[1]):
            raise _invalid(
                "/challenger_reconstruction_refs",
                ReproducibilityErrorCode.DUPLICATE_IDENTITY,
            )
        cases = _tuple(self.case_units, CaseDesignUnit, "/case_units", nonempty=True)
        for index, item in enumerate(cases):
            _same_challenge(
                item.case_ref.challenge_key, challenge, f"/case_units/{index}"
            )
        if len({item.case_ref for item in cases}) != len(cases):
            raise _invalid("/case_units", ReproducibilityErrorCode.DUPLICATE_IDENTITY)
        object.__setattr__(
            self,
            "case_units",
            tuple(
                sorted(
                    cases,
                    key=lambda item: (
                        item.case_ref.object_id,
                        item.case_ref.object_version,
                        item.case_ref.content_digest,
                    ),
                )
            ),
        )
        kinds = self.required_dependency_kinds
        if type(kinds) is not tuple or any(
            type(item) is not SharedDependencyKind for item in kinds
        ):
            raise _invalid(
                "/required_dependency_kinds", ReproducibilityErrorCode.WRONG_TYPE
            )
        mandatory = {SharedDependencyKind.COMMON_CASE}
        if not mandatory.issubset(kinds) or len(set(kinds)) != len(kinds):
            raise _invalid("/required_dependency_kinds")
        object.__setattr__(
            self,
            "required_dependency_kinds",
            tuple(sorted(kinds, key=lambda item: item.value)),
        )
        if self.fixture_origin is not True:
            raise _invalid("/fixture_origin")


@dataclass(frozen=True, slots=True)
class EvidenceFactorObservation:
    factor_kind: EvidenceFactorKind
    state: EvidenceFactorState
    evidence_ref: ReproducibilityRef
    value: float | None = None
    reason_ref: ReproducibilityRef | None = None

    def __post_init__(self) -> None:
        _exact(self.factor_kind, EvidenceFactorKind, "/factor_kind")
        _exact(self.state, EvidenceFactorState, "/state")
        challenge = self.evidence_ref.challenge_key
        _ref(
            self.evidence_ref,
            ReproducibilityRefKind.EVIDENCE,
            challenge,
            "/evidence_ref",
        )
        if self.state is EvidenceFactorState.OBSERVED:
            object.__setattr__(self, "value", _finite(self.value, "/value"))
            if self.reason_ref is not None:
                raise _invalid("/reason_ref")
        else:
            if self.value is not None:
                raise _invalid("/value")
            if self.reason_ref is None:
                raise _invalid(
                    "/reason_ref", ReproducibilityErrorCode.INCOMPLETE_EVIDENCE
                )
            _ref(
                self.reason_ref, ReproducibilityRefKind.REASON, challenge, "/reason_ref"
            )


@dataclass(frozen=True, slots=True)
class EvidenceCell:
    arm: ComparisonArm
    reconstruction_ref: ReproducibilityRef
    producer_role: ProducerRole
    case_ref: CanonicalChallengeCaseRef
    stratum_ref: MeasurementDefinitionRef
    reference_realization_ref: ReproducibilityRef
    randomness_role_ref: ReproducibilityRef
    training_seed_role_ref: ReproducibilityRef
    hardware_role_ref: ReproducibilityRef
    representation_ref: ReproducibilityRef
    execution_ref: ReproducibilityRef
    provenance_ref: ReproducibilityRef
    reference_run_outcome: ReferenceRunOutcome
    reference_comparison_outcome: ReferenceComparisonOutcome | None
    state: EvidenceCellState
    value: float | None
    factor_observations: tuple[EvidenceFactorObservation, ...]
    reason_ref: ReproducibilityRef | None = None

    def __post_init__(self) -> None:
        _exact(self.arm, ComparisonArm, "/arm")
        _exact(self.producer_role, ProducerRole, "/producer_role")
        challenge = self.reconstruction_ref.challenge_key
        for name, kind in (
            ("reconstruction_ref", ReproducibilityRefKind.RECONSTRUCTION),
            ("reference_realization_ref", ReproducibilityRefKind.REFERENCE_REALIZATION),
            ("randomness_role_ref", ReproducibilityRefKind.RANDOMNESS_ROLE),
            ("training_seed_role_ref", ReproducibilityRefKind.TRAINING_SEED_ROLE),
            ("hardware_role_ref", ReproducibilityRefKind.HARDWARE_ROLE),
            ("representation_ref", ReproducibilityRefKind.REPRESENTATION),
            ("execution_ref", ReproducibilityRefKind.EXECUTION),
            ("provenance_ref", ReproducibilityRefKind.PROVENANCE),
        ):
            _ref(getattr(self, name), kind, challenge, f"/{name}")
        case_ref = _exact(self.case_ref, CanonicalChallengeCaseRef, "/case_ref")
        _same_challenge(case_ref.challenge_key, challenge, "/case_ref")
        stratum = _exact(self.stratum_ref, MeasurementDefinitionRef, "/stratum_ref")
        if stratum.definition_kind is not MeasurementDefinitionKind.STRATUM:
            raise _invalid("/stratum_ref", ReproducibilityErrorCode.ROLE_CONFUSION)
        _same_challenge(stratum.challenge_key, challenge, "/stratum_ref")
        _exact(self.state, EvidenceCellState, "/state")
        _exact(
            self.reference_run_outcome, ReferenceRunOutcome, "/reference_run_outcome"
        )
        if self.reference_comparison_outcome is not None:
            _exact(
                self.reference_comparison_outcome,
                ReferenceComparisonOutcome,
                "/reference_comparison_outcome",
            )
        if (
            self.reference_run_outcome is not ReferenceRunOutcome.SUPPORTED
            and self.reference_comparison_outcome is not None
        ):
            raise _invalid("/reference_comparison_outcome")
        factors = _tuple(
            self.factor_observations,
            EvidenceFactorObservation,
            "/factor_observations",
        )
        for index, item in enumerate(factors):
            _same_challenge(
                item.evidence_ref.challenge_key,
                challenge,
                f"/factor_observations/{index}",
            )
        if self.state is EvidenceCellState.OBSERVED:
            object.__setattr__(self, "value", _finite(self.value, "/value"))
            if {item.factor_kind for item in factors} != set(REQUIRED_EVIDENCE_FACTORS):
                raise _invalid(
                    "/factor_observations", ReproducibilityErrorCode.INCOMPLETE_EVIDENCE
                )
            if len(factors) != len(REQUIRED_EVIDENCE_FACTORS):
                raise _invalid(
                    "/factor_observations", ReproducibilityErrorCode.DUPLICATE_IDENTITY
                )
            if self.reason_ref is not None:
                raise _invalid("/reason_ref")
        else:
            if self.value is not None or factors:
                raise _invalid("/value")
            if self.reason_ref is None:
                raise _invalid(
                    "/reason_ref", ReproducibilityErrorCode.INCOMPLETE_EVIDENCE
                )
            _ref(
                self.reason_ref, ReproducibilityRefKind.REASON, challenge, "/reason_ref"
            )
        object.__setattr__(
            self,
            "factor_observations",
            tuple(sorted(factors, key=lambda item: item.factor_kind.value)),
        )

    @property
    def coordinate(
        self,
    ) -> tuple[ComparisonArm, ReproducibilityRef, CanonicalChallengeCaseRef]:
        return self.arm, self.reconstruction_ref, self.case_ref


@dataclass(frozen=True, slots=True)
class VerificationAnchor:
    anchor_ref: ReproducibilityRef
    numerically_exact: bool
    unresolved_claims: tuple[UnresolvedClaimKind, ...]

    def __post_init__(self) -> None:
        challenge = self.anchor_ref.challenge_key
        _ref(
            self.anchor_ref,
            ReproducibilityRefKind.VERIFICATION_ANCHOR,
            challenge,
            "/anchor_ref",
        )
        if type(self.numerically_exact) is not bool:
            raise _invalid("/numerically_exact", ReproducibilityErrorCode.WRONG_TYPE)
        if type(self.unresolved_claims) is not tuple or any(
            type(item) is not UnresolvedClaimKind for item in self.unresolved_claims
        ):
            raise _invalid("/unresolved_claims", ReproducibilityErrorCode.WRONG_TYPE)
        if len(set(self.unresolved_claims)) != len(self.unresolved_claims):
            raise _invalid(
                "/unresolved_claims", ReproducibilityErrorCode.DUPLICATE_IDENTITY
            )
        object.__setattr__(
            self,
            "unresolved_claims",
            tuple(sorted(self.unresolved_claims, key=lambda item: item.value)),
        )


_DETECTABLE_SHARED_FIELDS = (
    ("case_ref", SharedDependencyKind.COMMON_CASE),
    ("reference_realization_ref", SharedDependencyKind.JOINT_REFERENCE_REALIZATION),
    ("randomness_role_ref", SharedDependencyKind.COMMON_RANDOM_NUMBERS),
    ("training_seed_role_ref", SharedDependencyKind.PAIRED_TRAINING_SEED),
    ("hardware_role_ref", SharedDependencyKind.HARDWARE_ROLE),
    ("representation_ref", SharedDependencyKind.REPRESENTATION),
    ("execution_ref", SharedDependencyKind.EXECUTION),
)


@dataclass(frozen=True, slots=True)
class CrossedEvidenceGraph:
    design: CrossedEvidenceDesign
    cells: tuple[EvidenceCell, ...]
    dependency_disclosures: tuple[DependencyDisclosure, ...]
    verification_anchors: tuple[VerificationAnchor, ...]
    unresolved_claims: tuple[UnresolvedClaimKind, ...]

    def __post_init__(self) -> None:
        design = _exact(self.design, CrossedEvidenceDesign, "/design")
        cells = _tuple(self.cells, EvidenceCell, "/cells", nonempty=True)
        for index, item in enumerate(cells):
            _same_challenge(
                item.reconstruction_ref.challenge_key,
                design.challenge_key,
                f"/cells/{index}",
            )
        if len({item.coordinate for item in cells}) != len(cells):
            raise _invalid("/cells", ReproducibilityErrorCode.DUPLICATE_IDENTITY)
        expected = {
            (arm, reconstruction_ref, case.case_ref)
            for arm, reconstructions in (
                (ComparisonArm.INCUMBENT, design.incumbent_reconstruction_refs),
                (ComparisonArm.CHALLENGER, design.challenger_reconstruction_refs),
            )
            for reconstruction_ref in reconstructions
            for case in design.case_units
        }
        actual = {item.coordinate for item in cells}
        if actual != expected:
            raise _invalid("/cells", ReproducibilityErrorCode.INCOMPLETE_EVIDENCE)
        case_by_ref = {item.case_ref: item for item in design.case_units}
        for index, item in enumerate(cells):
            unit = case_by_ref[item.case_ref]
            if item.stratum_ref != unit.stratum_ref:
                raise _invalid(
                    f"/cells/{index}/stratum_ref",
                    ReproducibilityErrorCode.ROLE_CONFUSION,
                )
        ordered_cells = tuple(
            sorted(
                cells,
                key=lambda item: (
                    item.arm.value,
                    _ref_key(item.reconstruction_ref),
                    item.case_ref.object_id,
                    item.case_ref.object_version,
                    item.case_ref.content_digest,
                ),
            )
        )
        object.__setattr__(self, "cells", ordered_cells)

        disclosures = _tuple(
            self.dependency_disclosures,
            DependencyDisclosure,
            "/dependency_disclosures",
            nonempty=True,
        )
        if len({item.dependency_ref for item in disclosures}) != len(disclosures):
            raise _invalid(
                "/dependency_disclosures", ReproducibilityErrorCode.DUPLICATE_IDENTITY
            )
        for index, item in enumerate(disclosures):
            _same_challenge(
                item.dependency_ref.challenge_key,
                design.challenge_key,
                f"/dependency_disclosures/{index}",
            )
        disclosed_kinds = {item.dependency_kind for item in disclosures}
        if not set(design.required_dependency_kinds).issubset(disclosed_kinds):
            raise _invalid(
                "/dependency_disclosures",
                ReproducibilityErrorCode.DEPENDENCY_UNDISCLOSED,
            )
        for field_name, dependency_kind in _DETECTABLE_SHARED_FIELDS:
            incumbent = {
                getattr(item, field_name)
                for item in cells
                if item.arm is ComparisonArm.INCUMBENT
            }
            challenger = {
                getattr(item, field_name)
                for item in cells
                if item.arm is ComparisonArm.CHALLENGER
            }
            for shared_ref in incumbent & challenger:
                if not any(
                    item.dependency_kind is dependency_kind
                    and shared_ref in item.member_refs
                    for item in disclosures
                ):
                    raise _invalid(
                        "/dependency_disclosures",
                        ReproducibilityErrorCode.DEPENDENCY_UNDISCLOSED,
                    )
        object.__setattr__(
            self,
            "dependency_disclosures",
            tuple(sorted(disclosures, key=lambda item: _ref_key(item.dependency_ref))),
        )
        anchors = _tuple(
            self.verification_anchors, VerificationAnchor, "/verification_anchors"
        )
        for index, item in enumerate(anchors):
            _same_challenge(
                item.anchor_ref.challenge_key,
                design.challenge_key,
                f"/verification_anchors/{index}",
            )
        if len({item.anchor_ref for item in anchors}) != len(anchors):
            raise _invalid(
                "/verification_anchors", ReproducibilityErrorCode.DUPLICATE_IDENTITY
            )
        object.__setattr__(
            self,
            "verification_anchors",
            tuple(sorted(anchors, key=lambda item: _ref_key(item.anchor_ref))),
        )
        claims = self.unresolved_claims
        if type(claims) is not tuple or any(
            type(item) is not UnresolvedClaimKind for item in claims
        ):
            raise _invalid("/unresolved_claims", ReproducibilityErrorCode.WRONG_TYPE)
        combined_claims = set(claims)
        for anchor in anchors:
            combined_claims.update(anchor.unresolved_claims)
        object.__setattr__(
            self,
            "unresolved_claims",
            tuple(sorted(combined_claims, key=lambda item: item.value)),
        )

    @property
    def case_scope_refs(self) -> tuple[MeasurementDefinitionRef, ...]:
        return tuple(
            sorted(
                {item.case_scope_ref for item in self.design.case_units},
                key=_measurement_ref_key,
            )
        )

    @property
    def stratum_scope_refs(self) -> tuple[MeasurementDefinitionRef, ...]:
        return tuple(
            sorted(
                {item.stratum_ref for item in self.design.case_units},
                key=_measurement_ref_key,
            )
        )


@dataclass(frozen=True, slots=True)
class ProcedureQualification:
    procedure_kind: ProcedureKind
    procedure_ref: ReproducibilityRef
    applicability_test_ref: MeasurementDefinitionRef
    dossier_qualification_ref: MeasurementDefinitionRef
    dependence_assumption_ref: MeasurementDefinitionRef | None
    coverage_qualification_ref: ReproducibilityRef
    power_qualification_ref: ReproducibilityRef
    fixture_origin: bool

    def __post_init__(self) -> None:
        _exact(self.procedure_kind, ProcedureKind, "/procedure_kind")
        challenge = self.procedure_ref.challenge_key
        _ref(
            self.procedure_ref,
            ReproducibilityRefKind.PROCEDURE,
            challenge,
            "/procedure_ref",
        )
        for name, kind in (
            ("applicability_test_ref", MeasurementDefinitionKind.APPLICABILITY_TEST),
            (
                "dossier_qualification_ref",
                MeasurementDefinitionKind.DOSSIER_QUALIFICATION,
            ),
        ):
            value = _exact(getattr(self, name), MeasurementDefinitionRef, f"/{name}")
            if value.definition_kind is not kind:
                raise _invalid(f"/{name}", ReproducibilityErrorCode.ROLE_CONFUSION)
            _same_challenge(value.challenge_key, challenge, f"/{name}")
        if self.shortcut_kind is None:
            if self.dependence_assumption_ref is not None:
                raise _invalid("/dependence_assumption_ref")
        else:
            assumption = _exact(
                self.dependence_assumption_ref,
                MeasurementDefinitionRef,
                "/dependence_assumption_ref",
            )
            if (
                assumption.definition_kind
                is not MeasurementDefinitionKind.DEPENDENCE_ASSUMPTION
            ):
                raise _invalid(
                    "/dependence_assumption_ref",
                    ReproducibilityErrorCode.ROLE_CONFUSION,
                )
            _same_challenge(
                assumption.challenge_key, challenge, "/dependence_assumption_ref"
            )
        _ref(
            self.coverage_qualification_ref,
            ReproducibilityRefKind.COVERAGE_QUALIFICATION,
            challenge,
            "/coverage_qualification_ref",
        )
        _ref(
            self.power_qualification_ref,
            ReproducibilityRefKind.POWER_QUALIFICATION,
            challenge,
            "/power_qualification_ref",
        )
        if self.fixture_origin is not True:
            raise _invalid("/fixture_origin")

    @property
    def shortcut_kind(self) -> DependenceShortcutKind | None:
        return {
            ProcedureKind.QUALIFIED_QUADRATURE: DependenceShortcutKind.QUADRATURE,
            ProcedureKind.QUALIFIED_INDEPENDENCE: DependenceShortcutKind.INDEPENDENCE,
            ProcedureKind.QUALIFIED_ZERO_COVARIANCE: DependenceShortcutKind.ZERO_COVARIANCE,
        }.get(self.procedure_kind)


@dataclass(frozen=True, slots=True)
class ProcedureApplicability:
    status: ApplicabilityStatus
    result_ref: ReproducibilityRef
    applicability_test_ref: MeasurementDefinitionRef
    incumbent_evidence_ref: MeasurementDefinitionRef
    challenger_evidence_ref: MeasurementDefinitionRef
    case_scope_refs: tuple[MeasurementDefinitionRef, ...]
    stratum_scope_refs: tuple[MeasurementDefinitionRef, ...]

    def __post_init__(self) -> None:
        _exact(self.status, ApplicabilityStatus, "/status")
        challenge = self.result_ref.challenge_key
        _ref(
            self.result_ref,
            ReproducibilityRefKind.APPLICABILITY_RESULT,
            challenge,
            "/result_ref",
        )
        applicability_test = _exact(
            self.applicability_test_ref,
            MeasurementDefinitionRef,
            "/applicability_test_ref",
        )
        if (
            applicability_test.definition_kind
            is not MeasurementDefinitionKind.APPLICABILITY_TEST
        ):
            raise _invalid(
                "/applicability_test_ref", ReproducibilityErrorCode.ROLE_CONFUSION
            )
        _same_challenge(
            applicability_test.challenge_key, challenge, "/applicability_test_ref"
        )
        for name, kind in (
            ("incumbent_evidence_ref", MeasurementDefinitionKind.EVIDENCE_SET),
            ("challenger_evidence_ref", MeasurementDefinitionKind.EVIDENCE_SET),
        ):
            value = _exact(getattr(self, name), MeasurementDefinitionRef, f"/{name}")
            if value.definition_kind is not kind:
                raise _invalid(f"/{name}", ReproducibilityErrorCode.ROLE_CONFUSION)
            _same_challenge(value.challenge_key, challenge, f"/{name}")
        for name, kind in (
            ("case_scope_refs", MeasurementDefinitionKind.CASE_SCOPE),
            ("stratum_scope_refs", MeasurementDefinitionKind.STRATUM),
        ):
            values = _tuple(
                getattr(self, name), MeasurementDefinitionRef, f"/{name}", nonempty=True
            )
            for index, item in enumerate(values):
                if item.definition_kind is not kind:
                    raise _invalid(
                        f"/{name}/{index}", ReproducibilityErrorCode.ROLE_CONFUSION
                    )
                _same_challenge(item.challenge_key, challenge, f"/{name}/{index}")
            object.__setattr__(
                self, name, tuple(sorted(values, key=_measurement_ref_key))
            )


@dataclass(frozen=True, slots=True)
class ProcedureDecision:
    stability: DecisionStability
    scientific_outcome: ScientificOutcome
    interval_lower: float | None
    interval_upper: float | None
    decision_ref: ReproducibilityRef

    def __post_init__(self) -> None:
        _exact(self.stability, DecisionStability, "/stability")
        _exact(self.scientific_outcome, ScientificOutcome, "/scientific_outcome")
        resolved = self.scientific_outcome in (
            ScientificOutcome.RESOLVED_SUPERIOR,
            ScientificOutcome.RESOLVED_NOT_SUPERIOR,
        )
        if resolved != (self.stability is DecisionStability.STABLE):
            raise _invalid("/stability")
        if resolved:
            lower = _finite(self.interval_lower, "/interval_lower")
            upper = _finite(self.interval_upper, "/interval_upper")
            if lower > upper:
                raise _invalid("/interval_lower")
            object.__setattr__(self, "interval_lower", lower)
            object.__setattr__(self, "interval_upper", upper)
        elif self.interval_lower is not None or self.interval_upper is not None:
            raise _invalid("/interval_lower")
        if self.decision_ref.ref_kind is not ReproducibilityRefKind.EVIDENCE:
            raise _invalid("/decision_ref", ReproducibilityErrorCode.ROLE_CONFUSION)


@dataclass(frozen=True, slots=True)
class R2Result:
    stability: DecisionStability
    scientific_outcome: ScientificOutcome
    procedure_kind: ProcedureKind | None
    procedure_ref: ReproducibilityRef | None
    applicability_ref: ReproducibilityRef | None
    decision_ref: ReproducibilityRef | None
    interval_lower: float | None = None
    interval_upper: float | None = None

    def __post_init__(self) -> None:
        _exact(self.stability, DecisionStability, "/stability")
        _exact(self.scientific_outcome, ScientificOutcome, "/scientific_outcome")
        supplied = (
            self.procedure_kind is not None,
            self.procedure_ref is not None,
            self.applicability_ref is not None,
            self.decision_ref is not None,
        )
        if any(supplied) and not all(supplied):
            raise _invalid("/procedure_ref")
        if self.procedure_kind is not None:
            _exact(self.procedure_kind, ProcedureKind, "/procedure_kind")


@dataclass(frozen=True, slots=True)
class ReconstructionStageEvent:
    stage: ReconstructionAuditStage
    state: AuditStageState
    evidence_refs: tuple[ReproducibilityRef, ...]

    def __post_init__(self) -> None:
        _exact(self.stage, ReconstructionAuditStage, "/stage")
        _exact(self.state, AuditStageState, "/state")
        values = _tuple(self.evidence_refs, ReproducibilityRef, "/evidence_refs")
        if self.state is AuditStageState.SATISFIED and not values:
            raise _invalid(
                "/evidence_refs", ReproducibilityErrorCode.INCOMPLETE_EVIDENCE
            )
        if len(set(values)) != len(values):
            raise _invalid(
                "/evidence_refs", ReproducibilityErrorCode.DUPLICATE_IDENTITY
            )
        object.__setattr__(self, "evidence_refs", tuple(sorted(values, key=_ref_key)))


@dataclass(frozen=True, slots=True)
class ScientificStoppingQualification:
    procedure_ref: ReproducibilityRef
    stopping_rule_ref: MeasurementDefinitionRef
    coverage_qualification_ref: ReproducibilityRef
    error_control_ref: MeasurementDefinitionRef
    fixture_origin: bool

    def __post_init__(self) -> None:
        challenge = self.procedure_ref.challenge_key
        _ref(
            self.procedure_ref,
            ReproducibilityRefKind.PROCEDURE,
            challenge,
            "/procedure_ref",
        )
        for name, kind in (
            ("stopping_rule_ref", MeasurementDefinitionKind.STOPPING_RULE),
            ("error_control_ref", MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL),
        ):
            value = _exact(getattr(self, name), MeasurementDefinitionRef, f"/{name}")
            if value.definition_kind is not kind:
                raise _invalid(f"/{name}", ReproducibilityErrorCode.ROLE_CONFUSION)
            _same_challenge(value.challenge_key, challenge, f"/{name}")
        _ref(
            self.coverage_qualification_ref,
            ReproducibilityRefKind.COVERAGE_QUALIFICATION,
            challenge,
            "/coverage_qualification_ref",
        )
        if self.fixture_origin is not True:
            raise _invalid("/fixture_origin")


@dataclass(frozen=True, slots=True)
class ScientificStoppingDecision:
    action: ScientificSequentialAction
    decision_ref: ReproducibilityRef

    def __post_init__(self) -> None:
        _exact(self.action, ScientificSequentialAction, "/action")
        if self.decision_ref.ref_kind is not ReproducibilityRefKind.EVIDENCE:
            raise _invalid("/decision_ref", ReproducibilityErrorCode.ROLE_CONFUSION)


@dataclass(frozen=True, slots=True)
class ReconstructionCampaignResult:
    policy_ref: ReconstructionEvidencePolicyRef
    evidence_status: ReconstructionEvidenceStatus
    scientific_outcome: ScientificOutcome
    stage_events: tuple[ReconstructionStageEvent, ...]
    sequential_action: ScientificSequentialAction | None
    decision_ref: ReproducibilityRef | None

    def __post_init__(self) -> None:
        _exact(self.policy_ref, ReconstructionEvidencePolicyRef, "/policy_ref")
        _exact(self.evidence_status, ReconstructionEvidenceStatus, "/evidence_status")
        _exact(self.scientific_outcome, ScientificOutcome, "/scientific_outcome")
        _tuple(self.stage_events, ReconstructionStageEvent, "/stage_events")
        if (self.sequential_action is None) != (self.decision_ref is None):
            raise _invalid("/sequential_action")
