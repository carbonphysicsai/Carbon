"""B-06 qualification candidates and pure A3 snapshot comparison."""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from carbon.authoring.refs import (
    CandidateOutputContractRef,
    ChallengeScope,
    ClaimScopeRef,
    GeneratorRef,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    ReferenceQualificationPolicyRef,
    RepresentationRef,
    SamplingPlanRef,
    owner_ref,
    reconstruct_top_level_ref,
    require_owner_ref,
)
from carbon.measurement.refs import MeasurementContractRef
from carbon.registry.model import (
    REQUIRED_QUALIFICATION_SLOTS,
    REQUIRED_QUALIFICATION_STATES,
    ChallengeKey,
    ChallengeRecord,
    QualificationEvidence,
)

from .enums import (
    DOSSIER_SLOT_ORDER,
    REQUIRED_SIGNER_ROLE_ORDER,
    ArtifactCurrentness,
    DossierSlot,
    EvidenceCompleteness,
    QualificationArtifactKind,
    QualificationCandidateState,
    QualificationMismatchReason,
    RepresentationApplicability,
    SignatureVerification,
    SignerArtifactKind,
    SignerBindingState,
    SignerIdentityValidation,
    SignerRole,
    SignerRoleAuthorization,
    StructuralOrigin,
)
from .errors import DossierInputCode, DossierValidationError
from .model import SignerBinding, ValidationDossier
from .refs import (
    QUALIFICATION_CANDIDATE_CANONICALIZATION_PROFILE,
    QUALIFICATION_CANDIDATE_SCHEMA_VERSION,
    DossierEvidenceManifestRef,
    DossierEvidenceRef,
    QualificationManifestCandidateRef,
    SignerArtifactRef,
    ValidationDossierRef,
)


def _invalid(path: str, code: DossierInputCode = DossierInputCode.INVALID_VALUE):
    return DossierValidationError(code, path=path)


def _exact(value: object, expected: type, path: str):
    if type(value) is not expected:
        raise _invalid(path, DossierInputCode.WRONG_TYPE)
    return value


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    if type(value) is not ChallengeKey:
        raise _invalid(path, DossierInputCode.WRONG_TYPE)
    try:
        return ChallengeKey(value.challenge_id, value.version)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.WRONG_TYPE) from None


def _same_challenge(value: ChallengeKey, expected: ChallengeKey, path: str) -> None:
    if value != expected:
        raise _invalid(path, DossierInputCode.CROSS_CHALLENGE)


def _identifier(value: object, path: str) -> str:
    from carbon.authoring.primitives import validate_canonical_id

    try:
        return validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _version(value: object, path: str) -> str:
    from carbon.authoring.primitives import validate_version_token

    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _digest(value: object, path: str) -> str:
    from carbon.authoring.primitives import validate_tagged_sha256

    try:
        return validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
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


def _copy_dossier_ref(value: object, challenge: ChallengeKey, path: str):
    item = _exact(value, ValidationDossierRef, path)
    _same_challenge(item.challenge_key, challenge, path)
    return ValidationDossierRef(
        item.challenge_key,
        item.dossier_id,
        item.dossier_version,
        item.content_digest,
        item.schema_version,
        item.canonicalization_profile,
    )


def _copy_evidence_manifest_ref(value: object, challenge: ChallengeKey, path: str):
    item = _exact(value, DossierEvidenceManifestRef, path)
    _same_challenge(item.challenge_key, challenge, path)
    return DossierEvidenceManifestRef(
        item.challenge_key,
        item.slot,
        item.manifest_id,
        item.manifest_version,
        item.content_digest,
        item.origin,
        item.schema_version,
        item.canonicalization_profile,
    )


def _copy_signer_artifact(
    value: object,
    challenge: ChallengeKey,
    role: SignerRole,
    path: str,
    expected_kind: SignerArtifactKind | None = None,
) -> SignerArtifactRef | None:
    if value is None:
        return None
    item = _exact(value, SignerArtifactRef, path)
    _same_challenge(item.challenge_key, challenge, path)
    if item.signer_role is not role or (
        expected_kind is not None and item.artifact_kind is not expected_kind
    ):
        raise _invalid(path, DossierInputCode.ROLE_CONFUSION)
    return SignerArtifactRef(
        item.challenge_key,
        item.signer_role,
        item.artifact_kind,
        item.artifact_id,
        item.artifact_version,
        item.content_digest,
        item.origin,
    )


def _copy_signer_binding(
    value: object, challenge: ChallengeKey, path: str
) -> SignerBinding:
    item = _exact(value, SignerBinding, path)
    _same_challenge(item.challenge_key, challenge, path)
    return SignerBinding(
        item.challenge_key,
        item.signer_role,
        item.state,
        item.identity_ref,
        item.signature_ref,
        item.authorization_evidence_ref,
    )


class _ProtectedRecord:
    def __repr__(self) -> str:
        return f"{type(self).__name__}(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected qualification records cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected qualification records cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class QualificationArtifactRef(_ProtectedRecord):
    challenge_key: ChallengeKey
    registry_artifact_id: str
    artifact_kind: QualificationArtifactKind
    object_id: str
    object_version: str
    content_digest: str
    origin: StructuralOrigin
    currentness: ArtifactCurrentness = ArtifactCurrentness.CURRENT

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        _exact(self.artifact_kind, QualificationArtifactKind, "/artifact_kind")
        _exact(self.origin, StructuralOrigin, "/origin")
        _exact(self.currentness, ArtifactCurrentness, "/currentness")
        object.__setattr__(
            self,
            "registry_artifact_id",
            _identifier(self.registry_artifact_id, "/registry_artifact_id"),
        )
        object.__setattr__(self, "object_id", _identifier(self.object_id, "/object_id"))
        object.__setattr__(
            self,
            "object_version",
            _version(self.object_version, "/object_version"),
        )
        object.__setattr__(
            self, "content_digest", _digest(self.content_digest, "/content_digest")
        )
        object.__setattr__(self, "challenge_key", challenge)

    @property
    def identity(self) -> tuple[object, ...]:
        return (
            self.artifact_kind,
            self.object_id,
            self.object_version,
        )


@dataclass(frozen=True, slots=True, repr=False)
class QualificationArtifactSet(_ProtectedRecord):
    challenge_key: ChallengeKey
    artifact_set_id: str
    artifact_set_version: str
    artifacts: tuple[QualificationArtifactRef, ...]

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        object.__setattr__(
            self,
            "artifact_set_id",
            _identifier(self.artifact_set_id, "/artifact_set_id"),
        )
        object.__setattr__(
            self,
            "artifact_set_version",
            _version(self.artifact_set_version, "/artifact_set_version"),
        )
        if type(self.artifacts) is not tuple:
            raise _invalid("/artifacts", DossierInputCode.WRONG_TYPE)
        artifacts: list[QualificationArtifactRef] = []
        for index, value in enumerate(self.artifacts):
            item = _exact(value, QualificationArtifactRef, f"/artifacts/{index}")
            _same_challenge(item.challenge_key, challenge, f"/artifacts/{index}")
            artifacts.append(
                QualificationArtifactRef(
                    item.challenge_key,
                    item.registry_artifact_id,
                    item.artifact_kind,
                    item.object_id,
                    item.object_version,
                    item.content_digest,
                    item.origin,
                    item.currentness,
                )
            )
        ids = tuple(item.registry_artifact_id for item in artifacts)
        identities = tuple(item.identity for item in artifacts)
        if len(set(ids)) != len(ids) or len(set(identities)) != len(identities):
            raise _invalid("/artifacts", DossierInputCode.DUPLICATE_IDENTITY)
        object.__setattr__(
            self,
            "artifacts",
            tuple(sorted(artifacts, key=lambda item: item.registry_artifact_id)),
        )
        object.__setattr__(self, "challenge_key", challenge)


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceManifestCandidateBinding(_ProtectedRecord):
    slot: DossierSlot
    completeness: EvidenceCompleteness
    manifest_ref: DossierEvidenceManifestRef | None
    currentness: ArtifactCurrentness = ArtifactCurrentness.CURRENT

    def __post_init__(self) -> None:
        _exact(self.slot, DossierSlot, "/slot")
        _exact(self.completeness, EvidenceCompleteness, "/completeness")
        _exact(self.currentness, ArtifactCurrentness, "/currentness")
        if self.manifest_ref is not None:
            item = _exact(
                self.manifest_ref, DossierEvidenceManifestRef, "/manifest_ref"
            )
            if item.slot is not self.slot:
                raise _invalid("/manifest_ref", DossierInputCode.SLOT_MISMATCH)
        elif self.completeness is EvidenceCompleteness.COMPLETE_REFERENCED:
            raise _invalid("/manifest_ref", DossierInputCode.MISSING_EVIDENCE)


@dataclass(frozen=True, slots=True, repr=False)
class RepresentationBinding(_ProtectedRecord):
    applicability: RepresentationApplicability
    representation_refs: tuple[RepresentationRef, ...] = ()
    rationale_ref: DossierEvidenceRef | None = None

    def __post_init__(self) -> None:
        _exact(self.applicability, RepresentationApplicability, "/applicability")
        if type(self.representation_refs) is not tuple:
            raise _invalid("/representation_refs", DossierInputCode.WRONG_TYPE)
        if self.applicability is RepresentationApplicability.APPLICABLE:
            if not self.representation_refs or self.rationale_ref is not None:
                raise _invalid(
                    "/representation_refs", DossierInputCode.MISSING_EVIDENCE
                )
        elif self.representation_refs or self.rationale_ref is None:
            raise _invalid("/rationale_ref", DossierInputCode.MISSING_EVIDENCE)


@dataclass(frozen=True, slots=True, repr=False)
class RegistryQualificationSlotBinding(_ProtectedRecord):
    slot: str
    registry_artifact_id: str

    def __post_init__(self) -> None:
        if type(self.slot) is not str or self.slot not in REQUIRED_QUALIFICATION_SLOTS:
            raise _invalid("/slot", DossierInputCode.ROLE_CONFUSION)
        object.__setattr__(
            self,
            "registry_artifact_id",
            _identifier(self.registry_artifact_id, "/registry_artifact_id"),
        )


@dataclass(frozen=True, slots=True, repr=False)
class SignerAuthorizationResult(_ProtectedRecord):
    challenge_key: ChallengeKey
    signer_role: SignerRole
    identity_ref: SignerArtifactRef
    signature_ref: SignerArtifactRef
    authorization_evidence_ref: SignerArtifactRef | None
    identity_validation: SignerIdentityValidation
    role_authorization: SignerRoleAuthorization
    signature_verification: SignatureVerification

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        role = _exact(self.signer_role, SignerRole, "/signer_role")
        _exact(
            self.identity_validation, SignerIdentityValidation, "/identity_validation"
        )
        _exact(self.role_authorization, SignerRoleAuthorization, "/role_authorization")
        _exact(
            self.signature_verification,
            SignatureVerification,
            "/signature_verification",
        )
        identity = _copy_signer_artifact(
            self.identity_ref,
            challenge,
            role,
            "/identity_ref",
            SignerArtifactKind.SIGNER_IDENTITY,
        )
        signature = _copy_signer_artifact(
            self.signature_ref,
            challenge,
            role,
            "/signature_ref",
            SignerArtifactKind.SIGNATURE,
        )
        authorization = _copy_signer_artifact(
            self.authorization_evidence_ref,
            challenge,
            role,
            "/authorization_evidence_ref",
            SignerArtifactKind.AUTHORIZATION_EVIDENCE,
        )
        if identity is None or signature is None:
            raise _invalid("/identity_ref", DossierInputCode.MISSING_EVIDENCE)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "identity_ref", identity)
        object.__setattr__(self, "signature_ref", signature)
        object.__setattr__(self, "authorization_evidence_ref", authorization)


@dataclass(frozen=True, slots=True, repr=False)
class QualificationManifestCandidate(_ProtectedRecord):
    challenge_key: ChallengeKey
    candidate_id: str
    candidate_version: str
    state: QualificationCandidateState
    dossier_ref: ValidationDossierRef
    dossier_completeness: EvidenceCompleteness
    dossier_origin: StructuralOrigin
    dossier_currentness: ArtifactCurrentness
    physical_system_ref: PhysicalSystemSpecRef
    claim_scope_ref: ClaimScopeRef
    target_population_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    generator_ref: GeneratorRef
    reference_policy_ref: ReferenceQualificationPolicyRef
    candidate_output_ref: CandidateOutputContractRef
    representation: RepresentationBinding
    measurement_contract_refs: tuple[MeasurementContractRef, ...]
    evidence_manifest_bindings: tuple[EvidenceManifestCandidateBinding, ...]
    signer_bindings: tuple[SignerBinding, ...]
    artifact_set: QualificationArtifactSet
    registry_slot_bindings: tuple[RegistryQualificationSlotBinding, ...]
    expected_registry_qualification_digest: str
    supersedes: QualificationManifestCandidateRef | None = None
    schema_version: str = QUALIFICATION_CANDIDATE_SCHEMA_VERSION
    canonicalization_profile: str = QUALIFICATION_CANDIDATE_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        candidate_id = _identifier(self.candidate_id, "/candidate_id")
        candidate_version = _version(self.candidate_version, "/candidate_version")
        _exact(self.state, QualificationCandidateState, "/state")
        _exact(self.dossier_completeness, EvidenceCompleteness, "/dossier_completeness")
        _exact(self.dossier_origin, StructuralOrigin, "/dossier_origin")
        _exact(self.dossier_currentness, ArtifactCurrentness, "/dossier_currentness")
        if (
            type(self.schema_version) is not str
            or self.schema_version != QUALIFICATION_CANDIDATE_SCHEMA_VERSION
            or type(self.canonicalization_profile) is not str
            or self.canonicalization_profile
            != QUALIFICATION_CANDIDATE_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")
        dossier = _copy_dossier_ref(self.dossier_ref, challenge, "/dossier_ref")
        physical = _copy_top(
            self.physical_system_ref,
            PhysicalSystemSpecRef,
            challenge,
            "/physical_system_ref",
        )
        claim = _copy_owner(
            self.claim_scope_ref, "claim_scope", challenge, "/claim_scope_ref"
        )
        population = _copy_top(
            self.target_population_ref,
            InstanceDistributionContractRef,
            challenge,
            "/target_population_ref",
        )
        if population.expected_population_role != "TARGET_WORKLOAD_P":
            raise _invalid("/target_population_ref", DossierInputCode.ROLE_CONFUSION)
        sampling = _copy_top(
            self.sampling_plan_ref, SamplingPlanRef, challenge, "/sampling_plan_ref"
        )
        generator = _copy_owner(
            self.generator_ref, "generator", challenge, "/generator_ref"
        )
        reference = _copy_owner(
            self.reference_policy_ref,
            "reference_qualification_policy",
            challenge,
            "/reference_policy_ref",
        )
        output = _copy_top(
            self.candidate_output_ref,
            CandidateOutputContractRef,
            challenge,
            "/candidate_output_ref",
        )
        representation = _exact(
            self.representation, RepresentationBinding, "/representation"
        )
        representation_refs: list[RepresentationRef] = []
        for index, value in enumerate(representation.representation_refs):
            representation_refs.append(
                _copy_owner(
                    value,
                    "representation",
                    challenge,
                    f"/representation/representation_refs/{index}",
                )
            )
        rationale = representation.rationale_ref
        if rationale is not None:
            rationale = _exact(
                rationale, DossierEvidenceRef, "/representation/rationale_ref"
            )
            _same_challenge(
                rationale.challenge_key,
                challenge,
                "/representation/rationale_ref",
            )
            rationale = DossierEvidenceRef(
                rationale.challenge_key,
                rationale.evidence_class,
                rationale.evidence_id,
                rationale.evidence_version,
                rationale.content_digest,
                rationale.origin,
            )
        representation = RepresentationBinding(
            representation.applicability,
            tuple(representation_refs),
            rationale,
        )
        if (
            type(self.measurement_contract_refs) is not tuple
            or not self.measurement_contract_refs
        ):
            raise _invalid(
                "/measurement_contract_refs", DossierInputCode.MISSING_EVIDENCE
            )
        measurements = tuple(
            _copy_measurement(value, challenge, f"/measurement_contract_refs/{index}")
            for index, value in enumerate(self.measurement_contract_refs)
        )
        measurement_ids = tuple(
            (item.schema_version, item.canonicalization_profile, item.content_digest)
            for item in measurements
        )
        if len(set(measurement_ids)) != len(measurement_ids):
            raise _invalid(
                "/measurement_contract_refs", DossierInputCode.DUPLICATE_IDENTITY
            )
        measurements = tuple(sorted(measurements, key=lambda item: item.content_digest))

        if type(self.evidence_manifest_bindings) is not tuple:
            raise _invalid("/evidence_manifest_bindings", DossierInputCode.WRONG_TYPE)
        evidence_bindings: list[EvidenceManifestCandidateBinding] = []
        for index, value in enumerate(self.evidence_manifest_bindings):
            item = _exact(
                value,
                EvidenceManifestCandidateBinding,
                f"/evidence_manifest_bindings/{index}",
            )
            if item.manifest_ref is not None:
                copied_ref = _copy_evidence_manifest_ref(
                    item.manifest_ref,
                    challenge,
                    f"/evidence_manifest_bindings/{index}/manifest_ref",
                )
            else:
                copied_ref = None
            evidence_bindings.append(
                EvidenceManifestCandidateBinding(
                    item.slot, item.completeness, copied_ref, item.currentness
                )
            )
        if tuple(item.slot for item in evidence_bindings) != DOSSIER_SLOT_ORDER:
            raise _invalid(
                "/evidence_manifest_bindings", DossierInputCode.SLOT_MISMATCH
            )

        if type(self.signer_bindings) is not tuple:
            raise _invalid("/signer_bindings", DossierInputCode.WRONG_TYPE)
        signers = tuple(
            _copy_signer_binding(value, challenge, f"/signer_bindings/{index}")
            for index, value in enumerate(self.signer_bindings)
        )
        if tuple(item.signer_role for item in signers) != REQUIRED_SIGNER_ROLE_ORDER:
            raise _invalid("/signer_bindings", DossierInputCode.ROLE_CONFUSION)

        artifact_set = _exact(
            self.artifact_set, QualificationArtifactSet, "/artifact_set"
        )
        _same_challenge(artifact_set.challenge_key, challenge, "/artifact_set")
        if type(self.registry_slot_bindings) is not tuple:
            raise _invalid("/registry_slot_bindings", DossierInputCode.WRONG_TYPE)
        slot_bindings = tuple(
            _exact(
                value,
                RegistryQualificationSlotBinding,
                f"/registry_slot_bindings/{index}",
            )
            for index, value in enumerate(self.registry_slot_bindings)
        )
        if tuple(item.slot for item in slot_bindings) != REQUIRED_QUALIFICATION_SLOTS:
            raise _invalid("/registry_slot_bindings", DossierInputCode.ROLE_CONFUSION)
        artifact_ids = {item.registry_artifact_id for item in artifact_set.artifacts}
        if any(item.registry_artifact_id not in artifact_ids for item in slot_bindings):
            raise _invalid("/registry_slot_bindings", DossierInputCode.MISSING_EVIDENCE)

        used_artifacts: set[str] = {item.registry_artifact_id for item in slot_bindings}

        def require_artifact(
            kind: QualificationArtifactKind,
            object_id: str | None,
            object_version: str,
            content_digest: str,
            path: str,
        ) -> None:
            matches = tuple(
                item
                for item in artifact_set.artifacts
                if item.artifact_kind is kind
                and (object_id is None or item.object_id == object_id)
                and item.object_version == object_version
                and item.content_digest == content_digest
            )
            if len(matches) != 1:
                raise _invalid(path, DossierInputCode.MISSING_EVIDENCE)
            used_artifacts.add(matches[0].registry_artifact_id)

        require_artifact(
            QualificationArtifactKind.VALIDATION_DOSSIER,
            dossier.dossier_id,
            dossier.dossier_version,
            dossier.content_digest,
            "/artifact_set/dossier",
        )
        core_refs = (
            (QualificationArtifactKind.PHYSICAL_SYSTEM_SPEC, physical),
            (QualificationArtifactKind.CLAIM_SCOPE, claim),
            (QualificationArtifactKind.TARGET_POPULATION, population),
            (QualificationArtifactKind.SAMPLING_PLAN, sampling),
            (QualificationArtifactKind.GENERATOR, generator),
            (QualificationArtifactKind.REFERENCE_POLICY, reference),
            (QualificationArtifactKind.CANDIDATE_OUTPUT_CONTRACT, output),
        )
        for kind, ref in core_refs:
            require_artifact(
                kind,
                ref.object_id,
                ref.object_version,
                ref.content_digest,
                f"/artifact_set/{kind.value.lower()}",
            )
        for index, ref in enumerate(representation.representation_refs):
            require_artifact(
                QualificationArtifactKind.REPRESENTATION_ADAPTER,
                ref.object_id,
                ref.object_version,
                ref.content_digest,
                f"/artifact_set/representation/{index}",
            )
        if representation.rationale_ref is not None:
            require_artifact(
                QualificationArtifactKind.APPLICABILITY_RATIONALE,
                representation.rationale_ref.evidence_id,
                representation.rationale_ref.evidence_version,
                representation.rationale_ref.content_digest,
                "/artifact_set/representation/rationale",
            )
        for index, ref in enumerate(measurements):
            require_artifact(
                QualificationArtifactKind.MEASUREMENT_CONTRACT,
                None,
                ref.schema_version,
                ref.content_digest,
                f"/artifact_set/measurement/{index}",
            )
        for index, binding in enumerate(evidence_bindings):
            ref = binding.manifest_ref
            if ref is not None:
                require_artifact(
                    QualificationArtifactKind.EVIDENCE_MANIFEST,
                    ref.manifest_id,
                    ref.manifest_version,
                    ref.content_digest,
                    f"/artifact_set/evidence/{index}",
                )
        signer_kind = {
            SignerArtifactKind.SIGNER_IDENTITY: QualificationArtifactKind.SIGNER_IDENTITY,
            SignerArtifactKind.SIGNATURE: QualificationArtifactKind.SIGNER_SIGNATURE,
            SignerArtifactKind.AUTHORIZATION_EVIDENCE: (
                QualificationArtifactKind.SIGNER_AUTHORIZATION_EVIDENCE
            ),
        }
        for signer_index, signer in enumerate(signers):
            for name, ref in (
                ("identity", signer.identity_ref),
                ("signature", signer.signature_ref),
                ("authorization", signer.authorization_evidence_ref),
            ):
                if ref is not None:
                    require_artifact(
                        signer_kind[ref.artifact_kind],
                        ref.artifact_id,
                        ref.artifact_version,
                        ref.content_digest,
                        f"/artifact_set/signers/{signer_index}/{name}",
                    )
        if used_artifacts != artifact_ids:
            raise _invalid("/artifact_set", DossierInputCode.ROLE_CONFUSION)
        expected_digest = _digest(
            self.expected_registry_qualification_digest,
            "/expected_registry_qualification_digest",
        )

        shape_complete = (
            self.dossier_completeness is EvidenceCompleteness.COMPLETE_REFERENCED
            and all(
                item.completeness is EvidenceCompleteness.COMPLETE_REFERENCED
                and item.manifest_ref is not None
                for item in evidence_bindings
            )
            and all(
                item.state is SignerBindingState.POPULATED_UNVERIFIED
                for item in signers
            )
        )
        expected_state = (
            QualificationCandidateState.COMPLETE_STRUCTURAL
            if shape_complete
            else QualificationCandidateState.INCOMPLETE
        )
        if self.state is not expected_state:
            raise _invalid("/state", DossierInputCode.MISSING_EVIDENCE)

        predecessor = self.supersedes
        if predecessor is not None:
            predecessor = _exact(
                predecessor, QualificationManifestCandidateRef, "/supersedes"
            )
            _same_challenge(predecessor.challenge_key, challenge, "/supersedes")
            if predecessor.candidate_id != candidate_id:
                raise _invalid(
                    "/supersedes/candidate_id", DossierInputCode.ROLE_CONFUSION
                )
            if predecessor.candidate_version == candidate_version:
                raise _invalid(
                    "/supersedes/candidate_version", DossierInputCode.VERSION_MISMATCH
                )

        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "candidate_version", candidate_version)
        object.__setattr__(self, "dossier_ref", dossier)
        object.__setattr__(self, "physical_system_ref", physical)
        object.__setattr__(self, "claim_scope_ref", claim)
        object.__setattr__(self, "target_population_ref", population)
        object.__setattr__(self, "sampling_plan_ref", sampling)
        object.__setattr__(self, "generator_ref", generator)
        object.__setattr__(self, "reference_policy_ref", reference)
        object.__setattr__(self, "candidate_output_ref", output)
        object.__setattr__(self, "representation", representation)
        object.__setattr__(self, "measurement_contract_refs", measurements)
        object.__setattr__(self, "evidence_manifest_bindings", tuple(evidence_bindings))
        object.__setattr__(self, "signer_bindings", signers)
        object.__setattr__(self, "registry_slot_bindings", slot_bindings)
        object.__setattr__(
            self, "expected_registry_qualification_digest", expected_digest
        )
        object.__setattr__(self, "supersedes", predecessor)

    @property
    def fixture_derived(self) -> bool:
        return (
            self.dossier_origin is StructuralOrigin.FIXTURE_ONLY
            or any(
                item.manifest_ref is not None
                and item.manifest_ref.origin is StructuralOrigin.FIXTURE_ONLY
                for item in self.evidence_manifest_bindings
            )
            or any(item.fixture_derived for item in self.signer_bindings)
            or any(
                item.origin is StructuralOrigin.FIXTURE_ONLY
                for item in self.artifact_set.artifacts
            )
        )


@dataclass(frozen=True, slots=True)
class QualificationComparisonResult:
    machine_prerequisites_satisfied: bool
    reasons: tuple[QualificationMismatchReason, ...]

    def __post_init__(self) -> None:
        if type(self.machine_prerequisites_satisfied) is not bool:
            raise TypeError("machine_prerequisites_satisfied must be a boolean")
        if type(self.reasons) is not tuple or any(
            type(item) is not QualificationMismatchReason for item in self.reasons
        ):
            raise TypeError("reasons must be exact QualificationMismatchReason values")
        if self.machine_prerequisites_satisfied != (not self.reasons):
            raise ValueError("machine readiness must match the exact reason set")


def _artifact_by_id(candidate: QualificationManifestCandidate):
    return {
        item.registry_artifact_id: item for item in candidate.artifact_set.artifacts
    }


def compare_qualification_candidate(
    candidate: QualificationManifestCandidate,
    active_record: ChallengeRecord,
    signer_authorizations: tuple[SignerAuthorizationResult, ...],
) -> QualificationComparisonResult:
    """Purely compare exact snapshots; never verify artifacts or activate LIVE."""
    from .candidate_canonical import a3_qualification_snapshot_digest

    _exact(candidate, QualificationManifestCandidate, "/candidate")
    _exact(active_record, ChallengeRecord, "/active_record")
    if type(signer_authorizations) is not tuple:
        raise _invalid("/signer_authorizations", DossierInputCode.WRONG_TYPE)

    found: set[QualificationMismatchReason] = set()
    add = found.add
    if active_record.key != candidate.challenge_key:
        add(QualificationMismatchReason.CHALLENGE_KEY_MISMATCH)
    if candidate.state is QualificationCandidateState.INCOMPLETE:
        add(QualificationMismatchReason.CANDIDATE_INCOMPLETE)
    if candidate.dossier_completeness is not EvidenceCompleteness.COMPLETE_REFERENCED:
        add(QualificationMismatchReason.DOSSIER_INCOMPLETE)
    if candidate.dossier_origin is StructuralOrigin.FIXTURE_ONLY:
        add(QualificationMismatchReason.DOSSIER_FIXTURE_DERIVED)
    if candidate.dossier_currentness is not ArtifactCurrentness.CURRENT:
        add(QualificationMismatchReason.DOSSIER_STALE_OR_SUPERSEDED)

    for item in candidate.evidence_manifest_bindings:
        if item.completeness is EvidenceCompleteness.INCOMPLETE_MISSING:
            add(QualificationMismatchReason.EVIDENCE_MISSING)
        elif item.completeness is EvidenceCompleteness.INCOMPLETE_PLACEHOLDER:
            add(QualificationMismatchReason.EVIDENCE_PLACEHOLDER)
        if (
            item.manifest_ref is not None
            and item.manifest_ref.origin is StructuralOrigin.FIXTURE_ONLY
        ):
            add(QualificationMismatchReason.EVIDENCE_FIXTURE_DERIVED)
        if item.currentness is not ArtifactCurrentness.CURRENT:
            add(QualificationMismatchReason.EVIDENCE_STALE_OR_SUPERSEDED)

    for signer in candidate.signer_bindings:
        if signer.state is not SignerBindingState.POPULATED_UNVERIFIED:
            add(QualificationMismatchReason.SIGNER_SLOT_MISSING)
        if signer.fixture_derived:
            add(QualificationMismatchReason.SIGNER_FIXTURE_DERIVED)

    for artifact in candidate.artifact_set.artifacts:
        if artifact.origin is StructuralOrigin.FIXTURE_ONLY:
            add(QualificationMismatchReason.ARTIFACT_FIXTURE_DERIVED)
        if artifact.currentness is not ArtifactCurrentness.CURRENT:
            add(QualificationMismatchReason.ARTIFACT_STALE_OR_SUPERSEDED)

    if active_record.status != "draft":
        add(QualificationMismatchReason.REGISTRY_LIFECYCLE_INCOMPATIBLE)
    if active_record.fixture_origin:
        add(QualificationMismatchReason.REGISTRY_FIXTURE_ORIGIN)
    manifest = active_record.qualification
    if manifest is None:
        add(QualificationMismatchReason.REGISTRY_QUALIFICATION_MISSING)
    else:
        if (
            manifest.challenge_id != candidate.challenge_key.challenge_id
            or manifest.challenge_version != candidate.challenge_key.version
        ):
            add(QualificationMismatchReason.REGISTRY_QUALIFICATION_CHALLENGE_MISMATCH)
        if manifest.mode != "production":
            add(QualificationMismatchReason.REGISTRY_QUALIFICATION_MODE_MISMATCH)
        actual_snapshot_digest = a3_qualification_snapshot_digest(manifest)
        if not hmac.compare_digest(
            actual_snapshot_digest,
            candidate.expected_registry_qualification_digest,
        ):
            add(QualificationMismatchReason.REGISTRY_QUALIFICATION_DIGEST_MISMATCH)
        record_graph = active_record.scientific_authoring_graph_fingerprint
        manifest_graph = manifest.scientific_authoring_graph_fingerprint
        if record_graph is None or manifest_graph is None:
            add(
                QualificationMismatchReason.REGISTRY_AUTHORING_GRAPH_FINGERPRINT_MISSING
            )
        elif not hmac.compare_digest(record_graph, manifest_graph):
            add(
                QualificationMismatchReason.REGISTRY_AUTHORING_GRAPH_FINGERPRINT_MISMATCH
            )
        slot_map = {item.slot: item for item in candidate.registry_slot_bindings}
        for slot, expected_state in REQUIRED_QUALIFICATION_STATES:
            evidence = manifest.slots.get(slot)
            if not isinstance(evidence, QualificationEvidence):
                add(QualificationMismatchReason.REGISTRY_SLOT_MISSING)
                continue
            if evidence.state != expected_state:
                add(QualificationMismatchReason.REGISTRY_SLOT_STATE_MISMATCH)
            if evidence.artifact_id != slot_map[slot].registry_artifact_id:
                add(QualificationMismatchReason.REGISTRY_SLOT_ARTIFACT_MISMATCH)

    candidate_artifacts = _artifact_by_id(candidate)
    record_ids = set(active_record.artifacts)
    candidate_ids = set(candidate_artifacts)
    if candidate_ids - record_ids:
        add(QualificationMismatchReason.REGISTRY_ARTIFACT_MISSING)
    if record_ids - candidate_ids:
        add(QualificationMismatchReason.REGISTRY_ARTIFACT_UNEXPECTED)
    for artifact_id in sorted(candidate_ids & record_ids):
        expected = candidate_artifacts[artifact_id]
        actual = active_record.artifacts[artifact_id]
        if actual.digest != expected.content_digest:
            if expected.artifact_kind is QualificationArtifactKind.VALIDATION_DOSSIER:
                add(QualificationMismatchReason.DOSSIER_DIGEST_MISMATCH)
            elif (
                expected.artifact_kind is QualificationArtifactKind.MEASUREMENT_CONTRACT
            ):
                add(QualificationMismatchReason.MEASUREMENT_SET_MISMATCH)
            else:
                add(QualificationMismatchReason.REGISTRY_ARTIFACT_DIGEST_MISMATCH)

    authorizations: dict[SignerRole, SignerAuthorizationResult] = {}
    for index, value in enumerate(signer_authorizations):
        item = _exact(
            value, SignerAuthorizationResult, f"/signer_authorizations/{index}"
        )
        if item.signer_role in authorizations:
            add(QualificationMismatchReason.SIGNER_AUTHORIZATION_BINDING_MISMATCH)
        authorizations[item.signer_role] = item
    for signer in candidate.signer_bindings:
        result = authorizations.get(signer.signer_role)
        if result is None:
            add(QualificationMismatchReason.SIGNER_AUTHORIZATION_MISSING)
            continue
        if result.challenge_key != candidate.challenge_key:
            add(QualificationMismatchReason.SIGNER_AUTHORIZATION_BINDING_MISMATCH)
        if (
            result.identity_ref != signer.identity_ref
            or result.signature_ref != signer.signature_ref
            or result.authorization_evidence_ref != signer.authorization_evidence_ref
        ):
            add(QualificationMismatchReason.SIGNER_AUTHORIZATION_BINDING_MISMATCH)
        if (
            result.identity_validation
            is not SignerIdentityValidation.STRUCTURALLY_VALID
        ):
            add(QualificationMismatchReason.SIGNER_IDENTITY_UNVERIFIED)
        if result.role_authorization is not SignerRoleAuthorization.AUTHORIZED_FOR_ROLE:
            add(QualificationMismatchReason.SIGNER_ROLE_UNAUTHORIZED)
        if (
            result.signature_verification
            is not SignatureVerification.CRYPTOGRAPHICALLY_VERIFIED
        ):
            add(QualificationMismatchReason.SIGNATURE_UNVERIFIED)
    if set(authorizations) - set(REQUIRED_SIGNER_ROLE_ORDER):
        add(QualificationMismatchReason.SIGNER_AUTHORIZATION_BINDING_MISMATCH)

    reasons = tuple(reason for reason in QualificationMismatchReason if reason in found)
    return QualificationComparisonResult(not reasons, reasons)


def dossier_completeness(value: ValidationDossier) -> EvidenceCompleteness:
    """Collapse only structural section completeness for candidate construction."""
    _exact(value, ValidationDossier, "/dossier")
    states = tuple(item.completeness for item in value.sections)
    if EvidenceCompleteness.INCOMPLETE_PLACEHOLDER in states:
        return EvidenceCompleteness.INCOMPLETE_PLACEHOLDER
    if EvidenceCompleteness.INCOMPLETE_MISSING in states:
        return EvidenceCompleteness.INCOMPLETE_MISSING
    return EvidenceCompleteness.COMPLETE_REFERENCED


def build_qualification_manifest_candidate(
    *,
    candidate_id: str,
    candidate_version: str,
    dossier: ValidationDossier,
    evidence_manifests: tuple[object, ...],
    artifact_set: QualificationArtifactSet,
    registry_slot_bindings: tuple[RegistryQualificationSlotBinding, ...],
    expected_registry_qualification_digest: str,
    dossier_currentness: ArtifactCurrentness = ArtifactCurrentness.CURRENT,
    evidence_currentness: tuple[ArtifactCurrentness, ...] | None = None,
    supersedes: QualificationManifestCandidateRef | None = None,
) -> QualificationManifestCandidate:
    """Construct one exact candidate from current B-06 dossier/evidence objects."""
    from .canonical import dossier_ref
    from .evidence import DossierEvidenceManifest
    from .evidence_canonical import evidence_manifest_ref

    value = _exact(dossier, ValidationDossier, "/dossier")
    challenge = value.challenge_key
    if type(evidence_manifests) is not tuple or len(evidence_manifests) != len(
        DOSSIER_SLOT_ORDER
    ):
        raise _invalid("/evidence_manifests", DossierInputCode.SLOT_MISMATCH)
    manifests = tuple(
        _exact(item, DossierEvidenceManifest, f"/evidence_manifests/{index}")
        for index, item in enumerate(evidence_manifests)
    )
    if tuple(item.slot for item in manifests) != DOSSIER_SLOT_ORDER:
        raise _invalid("/evidence_manifests", DossierInputCode.SLOT_MISMATCH)
    if any(item.challenge_key != challenge for item in manifests):
        raise _invalid("/evidence_manifests", DossierInputCode.CROSS_CHALLENGE)
    if any(item.subject_bindings is None for item in manifests):
        raise _invalid("/evidence_manifests", DossierInputCode.MISSING_EVIDENCE)
    currentness = (
        tuple(ArtifactCurrentness.CURRENT for _ in manifests)
        if evidence_currentness is None
        else evidence_currentness
    )
    if type(currentness) is not tuple or len(currentness) != len(manifests):
        raise _invalid("/evidence_currentness", DossierInputCode.WRONG_TYPE)
    bindings = tuple(
        EvidenceManifestCandidateBinding(
            item.slot,
            item.completeness,
            evidence_manifest_ref(item),
            currentness[index],
        )
        for index, item in enumerate(manifests)
    )
    by_slot = {item.slot: item.subject_bindings for item in manifests}
    d1 = by_slot[DOSSIER_SLOT_ORDER[0]]
    d2 = by_slot[DOSSIER_SLOT_ORDER[1]]
    d3 = by_slot[DOSSIER_SLOT_ORDER[2]]
    d4 = by_slot[DOSSIER_SLOT_ORDER[3]]
    d5 = by_slot[DOSSIER_SLOT_ORDER[4]]
    d7 = by_slot[DOSSIER_SLOT_ORDER[6]]
    d8 = by_slot[DOSSIER_SLOT_ORDER[7]]
    d9 = by_slot[DOSSIER_SLOT_ORDER[8]]
    if any(item is None for item in (d1, d2, d3, d4, d5, d7, d8, d9)):
        raise _invalid("/evidence_manifests", DossierInputCode.MISSING_EVIDENCE)
    required = (
        d1.physical_system_ref,
        d2.claim_scope_ref,
        d3.target_population_ref,
        d4.sampling_plan_ref,
        d5.generator_ref,
        d7.reference_policy_ref,
        d8.candidate_output_ref,
        d8.representation_ref,
        d9.measurement_contract_ref,
    )
    if any(item is None for item in required):
        raise _invalid("/evidence_manifests", DossierInputCode.MISSING_EVIDENCE)
    expected_subject_refs = (
        ("physical_system_ref", d1.physical_system_ref),
        ("claim_scope_ref", d2.claim_scope_ref),
        ("target_population_ref", d3.target_population_ref),
        ("sampling_plan_ref", d4.sampling_plan_ref),
        ("generator_ref", d5.generator_ref),
        ("reference_policy_ref", d7.reference_policy_ref),
        ("candidate_output_ref", d8.candidate_output_ref),
        ("representation_ref", d8.representation_ref),
        ("measurement_contract_ref", d9.measurement_contract_ref),
    )
    for manifest_index, item in enumerate(manifests):
        subject = item.subject_bindings
        if subject is None:
            raise _invalid(
                f"/evidence_manifests/{manifest_index}",
                DossierInputCode.MISSING_EVIDENCE,
            )
        for field_name, expected in expected_subject_refs:
            actual = getattr(subject, field_name)
            if actual is not None and actual != expected:
                raise _invalid(
                    f"/evidence_manifests/{manifest_index}/subject_bindings/{field_name}",
                    DossierInputCode.VERSION_MISMATCH,
                )
    shape_complete = (
        dossier_completeness(value) is EvidenceCompleteness.COMPLETE_REFERENCED
        and all(
            item.completeness is EvidenceCompleteness.COMPLETE_REFERENCED
            for item in manifests
        )
        and all(
            item.state is SignerBindingState.POPULATED_UNVERIFIED
            for item in value.signer_bindings
        )
    )
    return QualificationManifestCandidate(
        challenge,
        candidate_id,
        candidate_version,
        (
            QualificationCandidateState.COMPLETE_STRUCTURAL
            if shape_complete
            else QualificationCandidateState.INCOMPLETE
        ),
        dossier_ref(value),
        dossier_completeness(value),
        value.origin,
        dossier_currentness,
        d1.physical_system_ref,
        d2.claim_scope_ref,
        d3.target_population_ref,
        d4.sampling_plan_ref,
        d5.generator_ref,
        d7.reference_policy_ref,
        d8.candidate_output_ref,
        RepresentationBinding(
            RepresentationApplicability.APPLICABLE,
            (d8.representation_ref,),
        ),
        (d9.measurement_contract_ref,),
        bindings,
        value.signer_bindings,
        artifact_set,
        registry_slot_bindings,
        expected_registry_qualification_digest,
        supersedes,
    )


__all__ = (
    "EvidenceManifestCandidateBinding",
    "QualificationArtifactRef",
    "QualificationArtifactSet",
    "QualificationComparisonResult",
    "QualificationManifestCandidate",
    "RegistryQualificationSlotBinding",
    "RepresentationBinding",
    "SignerAuthorizationResult",
    "build_qualification_manifest_candidate",
    "compare_qualification_candidate",
    "dossier_completeness",
)
