"""Typed B-06 evidence manifests with structural non-substitution only."""

from __future__ import annotations

from dataclasses import dataclass

from carbon.authoring.refs import (
    AuditEvidenceRef,
    BlindingPolicyRef,
    CandidateOutputContractRef,
    CensoringPolicyRef,
    ChallengeScope,
    ClaimScopeRef,
    DisclosurePolicyRef,
    DistributionConformanceRef,
    ExclusionAssessmentRef,
    GeneratorRef,
    InstanceDistributionContractRef,
    MissingnessAdjustmentRef,
    PhysicalSystemSpecRef,
    ProtectedUnitManifestRef,
    RealizedEvidenceAccountingRef,
    ReferenceQualificationPolicyRef,
    RepresentationRef,
    SamplingPlanRef,
    owner_ref,
    reconstruct_top_level_ref,
    require_owner_ref,
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
    DOSSIER_PRIMARY_CLAIM_ROLE,
    DOSSIER_PRIMARY_EVIDENCE_CLASS,
    EVIDENCE_CLASS_ALLOWED_CLAIMS,
    AttemptDisposition,
    DependencePolicyAuthorityStatus,
    DossierClaimRole,
    DossierEvidenceClass,
    DossierSlot,
    EvidenceCompleteness,
    StructuralOrigin,
    effective_structural_origin,
)
from .errors import DossierInputCode, DossierValidationError
from .refs import (
    EVIDENCE_MANIFEST_CANONICALIZATION_PROFILE,
    EVIDENCE_MANIFEST_SCHEMA_VERSION,
    DossierEvidenceManifestRef,
    DossierEvidenceRef,
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


def _copy_top(value: object, expected: type, challenge: ChallengeKey, path: str):
    try:
        result = reconstruct_top_level_ref(value)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.WRONG_TYPE) from None
    if type(result) is not expected:
        raise _invalid(path, DossierInputCode.ROLE_CONFUSION)
    _same_challenge(result.challenge_key, challenge, path)
    return result


def _copy_owner(value: object, kind: str, challenge: ChallengeKey, path: str):
    try:
        result = require_owner_ref(value, kind)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.WRONG_TYPE) from None
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


def _copy_measurement_top(
    value: object, expected: type, challenge: ChallengeKey, path: str
):
    if type(value) is not expected:
        raise _invalid(path, DossierInputCode.ROLE_CONFUSION)
    try:
        result = expected(
            value.challenge_key,
            value.content_digest,
            value.schema_version,
            value.canonicalization_profile,
        )
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.WRONG_TYPE) from None
    _same_challenge(result.challenge_key, challenge, path)
    return result


def _copy_definition(
    value: object,
    expected: MeasurementDefinitionKind | tuple[MeasurementDefinitionKind, ...],
    challenge: ChallengeKey,
    path: str,
) -> MeasurementDefinitionRef:
    if type(value) is not MeasurementDefinitionRef:
        raise _invalid(path, DossierInputCode.WRONG_TYPE)
    expected_kinds = expected if type(expected) is tuple else (expected,)
    if value.definition_kind not in expected_kinds:
        raise _invalid(path, DossierInputCode.ROLE_CONFUSION)
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


def _copy_evidence(value: object, challenge: ChallengeKey, path: str):
    if type(value) is not DossierEvidenceRef:
        raise _invalid(path, DossierInputCode.WRONG_TYPE)
    _same_challenge(value.challenge_key, challenge, path)
    return DossierEvidenceRef(
        value.challenge_key,
        value.evidence_class,
        value.evidence_id,
        value.evidence_version,
        value.content_digest,
        value.origin,
    )


def _evidence_nominal_key(value: DossierEvidenceRef) -> tuple[object, ...]:
    return (
        value.evidence_class,
        value.evidence_id,
        value.evidence_version,
    )


def _evidence_sort_key(value: DossierEvidenceRef) -> tuple[object, ...]:
    return (
        *_evidence_nominal_key(value),
        value.content_digest,
        value.origin,
    )


def _owner_identity(value: object) -> tuple[object, ...]:
    return (
        value.ref_kind,
        value.object_id,
        value.object_version,
        value.content_digest,
    )


class _ProtectedRecord:
    def __repr__(self) -> str:
        return f"{type(self).__name__}(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected Dossier evidence records cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected Dossier evidence records cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceSubjectBindings(_ProtectedRecord):
    challenge_key: ChallengeKey
    claim_scope_ref: ClaimScopeRef
    physical_system_ref: PhysicalSystemSpecRef | None = None
    candidate_output_ref: CandidateOutputContractRef | None = None
    target_population_ref: InstanceDistributionContractRef | None = None
    sampling_plan_ref: SamplingPlanRef | None = None
    generator_ref: GeneratorRef | None = None
    generator_conformance_ref: DistributionConformanceRef | None = None
    reference_policy_ref: ReferenceQualificationPolicyRef | None = None
    representation_ref: RepresentationRef | None = None
    measurement_contract_ref: MeasurementContractRef | None = None
    measurement_evidence_ref: MeasurementQualificationEvidenceRef | None = None

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        object.__setattr__(
            self,
            "claim_scope_ref",
            _copy_owner(
                self.claim_scope_ref, "claim_scope", challenge, "/claim_scope_ref"
            ),
        )
        top_fields = (
            ("physical_system_ref", PhysicalSystemSpecRef),
            ("candidate_output_ref", CandidateOutputContractRef),
            ("target_population_ref", InstanceDistributionContractRef),
            ("sampling_plan_ref", SamplingPlanRef),
        )
        for name, expected in top_fields:
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self, name, _copy_top(value, expected, challenge, f"/{name}")
                )
        if self.target_population_ref is not None and (
            self.target_population_ref.expected_population_role != "TARGET_WORKLOAD_P"
        ):
            raise _invalid("/target_population_ref", DossierInputCode.ROLE_CONFUSION)
        owner_fields = (
            ("generator_ref", "generator"),
            ("generator_conformance_ref", "distribution_conformance"),
            ("reference_policy_ref", "reference_qualification_policy"),
            ("representation_ref", "representation"),
        )
        for name, kind in owner_fields:
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self, name, _copy_owner(value, kind, challenge, f"/{name}")
                )
        measurement_fields = (
            ("measurement_contract_ref", MeasurementContractRef),
            ("measurement_evidence_ref", MeasurementQualificationEvidenceRef),
        )
        for name, expected in measurement_fields:
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _copy_measurement_top(value, expected, challenge, f"/{name}"),
                )
        object.__setattr__(self, "challenge_key", challenge)


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceClaimBinding(_ProtectedRecord):
    challenge_key: ChallengeKey
    evidence_ref: DossierEvidenceRef
    claim_role: DossierClaimRole
    claim_scope_ref: ClaimScopeRef

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        _exact(self.claim_role, DossierClaimRole, "/claim_role")
        object.__setattr__(
            self,
            "evidence_ref",
            _copy_evidence(self.evidence_ref, challenge, "/evidence_ref"),
        )
        object.__setattr__(
            self,
            "claim_scope_ref",
            _copy_owner(
                self.claim_scope_ref, "claim_scope", challenge, "/claim_scope_ref"
            ),
        )
        if (
            self.claim_role
            not in EVIDENCE_CLASS_ALLOWED_CLAIMS[self.evidence_ref.evidence_class]
        ):
            raise _invalid("/claim_role", DossierInputCode.ROLE_CONFUSION)
        object.__setattr__(self, "challenge_key", challenge)


@dataclass(frozen=True, slots=True, repr=False)
class StatisticalScopeManifest(_ProtectedRecord):
    challenge_key: ChallengeKey
    authority_status: DependencePolicyAuthorityStatus
    uncertainty_policy_ref: UncertaintyPolicyRef
    estimand_ref: MeasurementDefinitionRef
    sampling_unit_ref: MeasurementDefinitionRef
    resampling_unit_ref: MeasurementDefinitionRef
    independence_unit_ref: MeasurementDefinitionRef
    case_scope_ref: MeasurementDefinitionRef
    stratum_ref: MeasurementDefinitionRef
    decision_interval_method_ref: MeasurementDefinitionRef
    dependence_assumption_ref: MeasurementDefinitionRef
    applicability_test_ref: MeasurementDefinitionRef
    reconstruction_case_interaction_ref: MeasurementDefinitionRef
    reconstruction_stratum_interaction_ref: MeasurementDefinitionRef
    coverage_evidence_ref: DossierEvidenceRef
    stopping_rule_ref: MeasurementDefinitionRef
    missing_cell_policy_ref: MeasurementDefinitionRef
    evidence_set_ref: MeasurementDefinitionRef

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        if (
            self.authority_status
            is not DependencePolicyAuthorityStatus.OWNER_RATIFICATION_PENDING
        ):
            raise _invalid("/authority_status", DossierInputCode.ROLE_CONFUSION)
        object.__setattr__(
            self,
            "uncertainty_policy_ref",
            _copy_measurement_top(
                self.uncertainty_policy_ref,
                UncertaintyPolicyRef,
                challenge,
                "/uncertainty_policy_ref",
            ),
        )
        requirements = (
            ("estimand_ref", MeasurementDefinitionKind.ESTIMAND),
            ("sampling_unit_ref", MeasurementDefinitionKind.SAMPLING_UNIT),
            ("resampling_unit_ref", MeasurementDefinitionKind.RESAMPLING_UNIT),
            ("independence_unit_ref", MeasurementDefinitionKind.INDEPENDENCE_UNIT),
            ("case_scope_ref", MeasurementDefinitionKind.CASE_SCOPE),
            ("stratum_ref", MeasurementDefinitionKind.STRATUM),
            (
                "decision_interval_method_ref",
                MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL,
            ),
            (
                "dependence_assumption_ref",
                MeasurementDefinitionKind.DEPENDENCE_ASSUMPTION,
            ),
            ("applicability_test_ref", MeasurementDefinitionKind.APPLICABILITY_TEST),
            (
                "reconstruction_case_interaction_ref",
                MeasurementDefinitionKind.RECONSTRUCTION_CASE_INTERACTION,
            ),
            (
                "reconstruction_stratum_interaction_ref",
                MeasurementDefinitionKind.RECONSTRUCTION_STRATUM_INTERACTION,
            ),
            (
                "stopping_rule_ref",
                (
                    MeasurementDefinitionKind.STOPPING_RULE,
                    MeasurementDefinitionKind.SEQUENTIAL_STOPPING_RULE,
                ),
            ),
            ("missing_cell_policy_ref", MeasurementDefinitionKind.CENSORING_ACCOUNTING),
            ("evidence_set_ref", MeasurementDefinitionKind.EVIDENCE_SET),
        )
        for name, expected in requirements:
            object.__setattr__(
                self,
                name,
                _copy_definition(getattr(self, name), expected, challenge, f"/{name}"),
            )
        coverage = _copy_evidence(
            self.coverage_evidence_ref, challenge, "/coverage_evidence_ref"
        )
        if (
            coverage.evidence_class
            is not DossierEvidenceClass.DECISION_RESOLUTION_STUDY
        ):
            raise _invalid("/coverage_evidence_ref", DossierInputCode.ROLE_CONFUSION)
        object.__setattr__(self, "coverage_evidence_ref", coverage)
        object.__setattr__(self, "challenge_key", challenge)

    @property
    def fixture_derived(self) -> bool:
        return self.effective_origin is StructuralOrigin.FIXTURE_ONLY

    @property
    def effective_origin(self) -> StructuralOrigin:
        return self.coverage_evidence_ref.origin


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceAttemptBinding(_ProtectedRecord):
    challenge_key: ChallengeKey
    attempt_ref: DossierEvidenceRef
    disposition: AttemptDisposition

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        _exact(self.disposition, AttemptDisposition, "/disposition")
        object.__setattr__(
            self,
            "attempt_ref",
            _copy_evidence(self.attempt_ref, challenge, "/attempt_ref"),
        )
        object.__setattr__(self, "challenge_key", challenge)


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceAccountingManifest(_ProtectedRecord):
    challenge_key: ChallengeKey
    sampling_plan_ref: SamplingPlanRef
    intended_unit_manifest_ref: ProtectedUnitManifestRef
    realized_evidence_accounting_ref: RealizedEvidenceAccountingRef
    censoring_policy_ref: CensoringPolicyRef
    missingness_adjustment_ref: MissingnessAdjustmentRef
    exclusion_assessment_ref: ExclusionAssessmentRef
    attempts: tuple[EvidenceAttemptBinding, ...]

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        object.__setattr__(
            self,
            "sampling_plan_ref",
            _copy_top(
                self.sampling_plan_ref, SamplingPlanRef, challenge, "/sampling_plan_ref"
            ),
        )
        owner_fields = (
            ("intended_unit_manifest_ref", "protected_unit_manifest"),
            ("realized_evidence_accounting_ref", "realized_evidence_accounting"),
            ("censoring_policy_ref", "censoring_policy"),
            ("missingness_adjustment_ref", "missingness_adjustment"),
            ("exclusion_assessment_ref", "exclusion_assessment"),
        )
        for name, kind in owner_fields:
            object.__setattr__(
                self,
                name,
                _copy_owner(getattr(self, name), kind, challenge, f"/{name}"),
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
        identities = tuple(_evidence_nominal_key(item.attempt_ref) for item in attempts)
        if len(set(identities)) != len(identities):
            raise _invalid("/attempts", DossierInputCode.DUPLICATE_IDENTITY)
        attempts.sort(
            key=lambda item: (
                _evidence_sort_key(item.attempt_ref),
                item.disposition.value,
            )
        )
        object.__setattr__(self, "attempts", tuple(attempts))
        object.__setattr__(self, "challenge_key", challenge)

    @property
    def fixture_derived(self) -> bool:
        return self.effective_origin is StructuralOrigin.FIXTURE_ONLY

    @property
    def effective_origin(self) -> StructuralOrigin:
        return effective_structural_origin(
            *(item.attempt_ref.origin for item in self.attempts),
            StructuralOrigin.REGISTERED_REFERENCE,
        )


@dataclass(frozen=True, slots=True, repr=False)
class SecrecyEvidenceManifest(_ProtectedRecord):
    challenge_key: ChallengeKey
    disclosure_policy_ref: DisclosurePolicyRef
    blinding_policy_ref: BlindingPolicyRef
    decontamination_evidence_ref: AuditEvidenceRef
    role_separation_evidence_ref: AuditEvidenceRef

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        fields = (
            ("disclosure_policy_ref", "disclosure_policy"),
            ("blinding_policy_ref", "blinding_policy"),
            ("decontamination_evidence_ref", "audit_evidence"),
            ("role_separation_evidence_ref", "audit_evidence"),
        )
        for name, kind in fields:
            object.__setattr__(
                self,
                name,
                _copy_owner(getattr(self, name), kind, challenge, f"/{name}"),
            )
        if _owner_identity(self.decontamination_evidence_ref) == _owner_identity(
            self.role_separation_evidence_ref
        ):
            raise _invalid(
                "/role_separation_evidence_ref", DossierInputCode.ROLE_CONFUSION
            )
        object.__setattr__(self, "challenge_key", challenge)


@dataclass(frozen=True, slots=True, repr=False)
class LimitationBinding(_ProtectedRecord):
    challenge_key: ChallengeKey
    limitation_ref: DossierEvidenceRef
    affected_evidence_refs: tuple[DossierEvidenceRef, ...]
    affected_claim_roles: tuple[DossierClaimRole, ...]
    claim_scope_ref: ClaimScopeRef

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        limitation = _copy_evidence(self.limitation_ref, challenge, "/limitation_ref")
        if limitation.evidence_class is not DossierEvidenceClass.RESIDUAL_LIMITATION:
            raise _invalid("/limitation_ref", DossierInputCode.ROLE_CONFUSION)
        if (
            type(self.affected_evidence_refs) is not tuple
            or not self.affected_evidence_refs
        ):
            raise _invalid("/affected_evidence_refs", DossierInputCode.MISSING_EVIDENCE)
        affected = tuple(
            _copy_evidence(item, challenge, f"/affected_evidence_refs/{index}")
            for index, item in enumerate(self.affected_evidence_refs)
        )
        identities = tuple(_evidence_nominal_key(item) for item in affected)
        if len(set(identities)) != len(identities):
            raise _invalid(
                "/affected_evidence_refs", DossierInputCode.DUPLICATE_IDENTITY
            )
        if (
            type(self.affected_claim_roles) is not tuple
            or not self.affected_claim_roles
        ):
            raise _invalid("/affected_claim_roles", DossierInputCode.MISSING_EVIDENCE)
        roles = tuple(
            _exact(item, DossierClaimRole, "/affected_claim_roles")
            for item in self.affected_claim_roles
        )
        if len(set(roles)) != len(roles):
            raise _invalid("/affected_claim_roles", DossierInputCode.DUPLICATE_IDENTITY)
        object.__setattr__(self, "limitation_ref", limitation)
        object.__setattr__(
            self,
            "affected_evidence_refs",
            tuple(sorted(affected, key=_evidence_sort_key)),
        )
        object.__setattr__(
            self,
            "affected_claim_roles",
            tuple(sorted(roles, key=lambda item: item.value)),
        )
        object.__setattr__(
            self,
            "claim_scope_ref",
            _copy_owner(
                self.claim_scope_ref, "claim_scope", challenge, "/claim_scope_ref"
            ),
        )
        object.__setattr__(self, "challenge_key", challenge)

    @property
    def fixture_derived(self) -> bool:
        return self.effective_origin is StructuralOrigin.FIXTURE_ONLY

    @property
    def effective_origin(self) -> StructuralOrigin:
        return effective_structural_origin(
            self.limitation_ref.origin,
            *(item.origin for item in self.affected_evidence_refs),
        )


_SUBJECT_REQUIREMENTS = {
    DossierSlot.D1: ("physical_system_ref",),
    DossierSlot.D2: ("physical_system_ref",),
    DossierSlot.D3: ("physical_system_ref", "target_population_ref"),
    DossierSlot.D4: ("target_population_ref", "sampling_plan_ref"),
    DossierSlot.D5: ("generator_ref",),
    DossierSlot.D6: (
        "target_population_ref",
        "sampling_plan_ref",
        "generator_ref",
        "generator_conformance_ref",
    ),
    DossierSlot.D7: ("reference_policy_ref",),
    DossierSlot.D8: ("candidate_output_ref", "representation_ref"),
    DossierSlot.D9: (
        "target_population_ref",
        "measurement_contract_ref",
        "measurement_evidence_ref",
    ),
    DossierSlot.D10: (
        "target_population_ref",
        "sampling_plan_ref",
        "measurement_contract_ref",
    ),
    DossierSlot.D11: (),
    DossierSlot.D12: ("target_population_ref", "sampling_plan_ref"),
}


@dataclass(frozen=True, slots=True, repr=False)
class DossierEvidenceManifest(_ProtectedRecord):
    challenge_key: ChallengeKey
    slot: DossierSlot
    manifest_id: str
    manifest_version: str
    completeness: EvidenceCompleteness
    origin: StructuralOrigin
    subject_bindings: EvidenceSubjectBindings | None = None
    evidence_refs: tuple[DossierEvidenceRef, ...] = ()
    claim_bindings: tuple[EvidenceClaimBinding, ...] = ()
    statistical_scope: StatisticalScopeManifest | None = None
    accounting: EvidenceAccountingManifest | None = None
    secrecy: SecrecyEvidenceManifest | None = None
    limitations: tuple[LimitationBinding, ...] = ()
    supersedes: DossierEvidenceManifestRef | None = None
    schema_version: str = EVIDENCE_MANIFEST_SCHEMA_VERSION
    canonicalization_profile: str = EVIDENCE_MANIFEST_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        _exact(self.slot, DossierSlot, "/slot")
        _exact(self.completeness, EvidenceCompleteness, "/completeness")
        _exact(self.origin, StructuralOrigin, "/origin")
        manifest_id = _identifier(self.manifest_id, "/manifest_id")
        manifest_version = _version(self.manifest_version, "/manifest_version")
        if (
            type(self.schema_version) is not str
            or self.schema_version != EVIDENCE_MANIFEST_SCHEMA_VERSION
            or type(self.canonicalization_profile) is not str
            or self.canonicalization_profile
            != EVIDENCE_MANIFEST_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")
        if (
            type(self.evidence_refs) is not tuple
            or type(self.claim_bindings) is not tuple
        ):
            raise _invalid("/evidence_refs", DossierInputCode.WRONG_TYPE)
        if type(self.limitations) is not tuple:
            raise _invalid("/limitations", DossierInputCode.WRONG_TYPE)

        if self.completeness is not EvidenceCompleteness.COMPLETE_REFERENCED:
            if any(
                (
                    self.subject_bindings is not None,
                    bool(self.evidence_refs),
                    bool(self.claim_bindings),
                    self.statistical_scope is not None,
                    self.accounting is not None,
                    self.secrecy is not None,
                    bool(self.limitations),
                )
            ):
                raise _invalid("/completeness", DossierInputCode.MISSING_EVIDENCE)
            subjects = None
            refs: tuple[DossierEvidenceRef, ...] = ()
            claims: tuple[EvidenceClaimBinding, ...] = ()
            statistical = None
            accounting = None
            secrecy = None
            limitations: tuple[LimitationBinding, ...] = ()
        else:
            subjects = _exact(
                self.subject_bindings, EvidenceSubjectBindings, "/subject_bindings"
            )
            _same_challenge(subjects.challenge_key, challenge, "/subject_bindings")
            for name in _SUBJECT_REQUIREMENTS[self.slot]:
                if getattr(subjects, name) is None:
                    raise _invalid(
                        f"/subject_bindings/{name}", DossierInputCode.MISSING_EVIDENCE
                    )
            refs = tuple(
                _copy_evidence(item, challenge, f"/evidence_refs/{index}")
                for index, item in enumerate(self.evidence_refs)
            )
            identities = tuple(_evidence_nominal_key(item) for item in refs)
            if len(set(identities)) != len(identities):
                raise _invalid("/evidence_refs", DossierInputCode.DUPLICATE_IDENTITY)
            refs = tuple(sorted(refs, key=_evidence_sort_key))
            content_identities = tuple(_evidence_sort_key(item) for item in refs)
            primary_class = DOSSIER_PRIMARY_EVIDENCE_CLASS[self.slot]
            primary_refs = tuple(
                item for item in refs if item.evidence_class is primary_class
            )
            if not primary_refs:
                raise _invalid("/evidence_refs", DossierInputCode.SLOT_MISMATCH)

            claims_list: list[EvidenceClaimBinding] = []
            for index, value in enumerate(self.claim_bindings):
                item = _exact(value, EvidenceClaimBinding, f"/claim_bindings/{index}")
                _same_challenge(
                    item.challenge_key, challenge, f"/claim_bindings/{index}"
                )
                if _evidence_sort_key(item.evidence_ref) not in content_identities:
                    raise _invalid(
                        f"/claim_bindings/{index}/evidence_ref",
                        DossierInputCode.MISSING_EVIDENCE,
                    )
                if _owner_identity(item.claim_scope_ref) != _owner_identity(
                    subjects.claim_scope_ref
                ):
                    raise _invalid(
                        f"/claim_bindings/{index}/claim_scope_ref",
                        DossierInputCode.VERSION_MISMATCH,
                    )
                claims_list.append(
                    EvidenceClaimBinding(
                        item.challenge_key,
                        item.evidence_ref,
                        item.claim_role,
                        item.claim_scope_ref,
                    )
                )
            claim_identities = tuple(
                (
                    _evidence_sort_key(item.evidence_ref),
                    item.claim_role,
                    _owner_identity(item.claim_scope_ref),
                )
                for item in claims_list
            )
            if len(set(claim_identities)) != len(claim_identities):
                raise _invalid("/claim_bindings", DossierInputCode.DUPLICATE_IDENTITY)
            claims = tuple(
                sorted(
                    claims_list,
                    key=lambda item: (
                        item.claim_role.value,
                        _evidence_sort_key(item.evidence_ref),
                    ),
                )
            )
            primary_role = DOSSIER_PRIMARY_CLAIM_ROLE[self.slot]
            if not any(
                item.evidence_ref.evidence_class is primary_class
                and item.claim_role is primary_role
                for item in claims
            ):
                raise _invalid("/claim_bindings", DossierInputCode.SLOT_MISMATCH)

            statistical = self.statistical_scope
            if statistical is not None:
                statistical = _exact(
                    statistical, StatisticalScopeManifest, "/statistical_scope"
                )
                _same_challenge(
                    statistical.challenge_key, challenge, "/statistical_scope"
                )
                if (
                    _evidence_sort_key(statistical.coverage_evidence_ref)
                    not in content_identities
                ):
                    raise _invalid(
                        "/statistical_scope/coverage_evidence_ref",
                        DossierInputCode.MISSING_EVIDENCE,
                    )
            if self.slot is DossierSlot.D10 and statistical is None:
                raise _invalid("/statistical_scope", DossierInputCode.MISSING_EVIDENCE)

            accounting = self.accounting
            if accounting is not None:
                accounting = _exact(
                    accounting, EvidenceAccountingManifest, "/accounting"
                )
                _same_challenge(accounting.challenge_key, challenge, "/accounting")
                if subjects.sampling_plan_ref != accounting.sampling_plan_ref:
                    raise _invalid(
                        "/accounting/sampling_plan_ref",
                        DossierInputCode.VERSION_MISMATCH,
                    )
            if (
                self.slot in (DossierSlot.D4, DossierSlot.D6, DossierSlot.D12)
                and accounting is None
            ):
                raise _invalid("/accounting", DossierInputCode.MISSING_EVIDENCE)

            secrecy = self.secrecy
            if secrecy is not None:
                secrecy = _exact(secrecy, SecrecyEvidenceManifest, "/secrecy")
                _same_challenge(secrecy.challenge_key, challenge, "/secrecy")
            if self.slot is DossierSlot.D11 and secrecy is None:
                raise _invalid("/secrecy", DossierInputCode.MISSING_EVIDENCE)

            limitation_list: list[LimitationBinding] = []
            for index, value in enumerate(self.limitations):
                item = _exact(value, LimitationBinding, f"/limitations/{index}")
                _same_challenge(item.challenge_key, challenge, f"/limitations/{index}")
                if _evidence_sort_key(item.limitation_ref) not in content_identities:
                    raise _invalid(
                        f"/limitations/{index}/limitation_ref",
                        DossierInputCode.MISSING_EVIDENCE,
                    )
                if any(
                    _evidence_sort_key(ref) not in content_identities
                    for ref in item.affected_evidence_refs
                ):
                    raise _invalid(
                        f"/limitations/{index}/affected_evidence_refs",
                        DossierInputCode.MISSING_EVIDENCE,
                    )
                if _owner_identity(item.claim_scope_ref) != _owner_identity(
                    subjects.claim_scope_ref
                ):
                    raise _invalid(
                        f"/limitations/{index}/claim_scope_ref",
                        DossierInputCode.VERSION_MISMATCH,
                    )
                limitation_list.append(item)
            limitation_ids = tuple(
                _evidence_nominal_key(item.limitation_ref) for item in limitation_list
            )
            if len(set(limitation_ids)) != len(limitation_ids):
                raise _invalid("/limitations", DossierInputCode.DUPLICATE_IDENTITY)
            limitations = tuple(
                sorted(
                    limitation_list,
                    key=lambda item: _evidence_sort_key(item.limitation_ref),
                )
            )

        predecessor = self.supersedes
        if predecessor is not None:
            predecessor = _exact(predecessor, DossierEvidenceManifestRef, "/supersedes")
            _same_challenge(predecessor.challenge_key, challenge, "/supersedes")
            if (
                predecessor.slot is not self.slot
                or predecessor.manifest_id != manifest_id
            ):
                raise _invalid("/supersedes", DossierInputCode.ROLE_CONFUSION)
            if predecessor.manifest_version == manifest_version:
                raise _invalid(
                    "/supersedes/manifest_version", DossierInputCode.VERSION_MISMATCH
                )
            predecessor = DossierEvidenceManifestRef(
                predecessor.challenge_key,
                predecessor.slot,
                predecessor.manifest_id,
                predecessor.manifest_version,
                predecessor.content_digest,
                predecessor.origin,
                predecessor.schema_version,
                predecessor.canonicalization_profile,
            )

        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "manifest_id", manifest_id)
        object.__setattr__(self, "manifest_version", manifest_version)
        object.__setattr__(self, "subject_bindings", subjects)
        object.__setattr__(self, "evidence_refs", refs)
        object.__setattr__(self, "claim_bindings", claims)
        object.__setattr__(self, "statistical_scope", statistical)
        object.__setattr__(self, "accounting", accounting)
        object.__setattr__(self, "secrecy", secrecy)
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(self, "supersedes", predecessor)

    @property
    def fixture_derived(self) -> bool:
        return self.effective_origin is StructuralOrigin.FIXTURE_ONLY

    @property
    def effective_origin(self) -> StructuralOrigin:
        return effective_structural_origin(
            self.origin,
            *(item.origin for item in self.evidence_refs),
            *(() if self.supersedes is None else (self.supersedes.origin,)),
            *(
                ()
                if self.statistical_scope is None
                else (self.statistical_scope.effective_origin,)
            ),
            *(() if self.accounting is None else (self.accounting.effective_origin,)),
            *(item.effective_origin for item in self.limitations),
        )


__all__ = (
    "DossierEvidenceManifest",
    "EvidenceAccountingManifest",
    "EvidenceAttemptBinding",
    "EvidenceClaimBinding",
    "EvidenceSubjectBindings",
    "LimitationBinding",
    "SecrecyEvidenceManifest",
    "StatisticalScopeManifest",
)
