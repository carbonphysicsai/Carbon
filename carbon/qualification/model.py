"""Immutable Challenge-bound B-06 Validation Dossier records."""

from __future__ import annotations

from dataclasses import dataclass

from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_version_token,
)
from carbon.registry.model import ChallengeKey

from .enums import (
    DOSSIER_PRIMARY_EVIDENCE_CLASS,
    DOSSIER_SLOT_ORDER,
    REQUIRED_SIGNER_ROLE_ORDER,
    DossierSlot,
    EvidenceCompleteness,
    EvidenceRequirement,
    EvidenceSectionStatus,
    SignerArtifactKind,
    SignerBindingState,
    SignerRole,
    StructuralOrigin,
    effective_structural_origin,
)
from .errors import DossierInputCode, DossierValidationError
from .refs import (
    DOSSIER_CANONICALIZATION_PROFILE,
    DOSSIER_SCHEMA_VERSION,
    DossierEvidenceRef,
    SignerArtifactRef,
    ValidationDossierRef,
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
        return reconstruct_challenge_key(value)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.WRONG_TYPE) from None


def _identifier(value: object, path: str) -> str:
    return validate_dossier_identifier(value, path)


def _version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _same_challenge(value: ChallengeKey, expected: ChallengeKey, path: str) -> None:
    if value != expected:
        raise _invalid(path, DossierInputCode.CROSS_CHALLENGE)


def _copy_evidence(
    value: object, challenge_key: ChallengeKey, path: str
) -> DossierEvidenceRef:
    ref = _exact(value, DossierEvidenceRef, path)
    _same_challenge(ref.challenge_key, challenge_key, path)
    return DossierEvidenceRef(
        ref.challenge_key,
        ref.evidence_class,
        ref.evidence_id,
        ref.evidence_version,
        ref.content_digest,
        ref.origin,
    )


def _copy_artifact(
    value: object,
    challenge_key: ChallengeKey,
    role: SignerRole,
    kind: SignerArtifactKind,
    path: str,
) -> SignerArtifactRef:
    ref = _exact(value, SignerArtifactRef, path)
    _same_challenge(ref.challenge_key, challenge_key, path)
    if ref.signer_role is not role or ref.artifact_kind is not kind:
        raise _invalid(path, DossierInputCode.ROLE_CONFUSION)
    return SignerArtifactRef(
        ref.challenge_key,
        ref.signer_role,
        ref.artifact_kind,
        ref.artifact_id,
        ref.artifact_version,
        ref.content_digest,
        ref.origin,
    )


@dataclass(frozen=True, slots=True)
class DossierSection:
    """One structural evidence slot; status is a claim, never code approval."""

    challenge_key: ChallengeKey
    slot: DossierSlot
    requirement: EvidenceRequirement
    completeness: EvidenceCompleteness
    status: EvidenceSectionStatus
    evidence_refs: tuple[DossierEvidenceRef, ...] = ()
    rationale_ref: DossierEvidenceRef | None = None

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        _exact(self.slot, DossierSlot, "/slot")
        _exact(self.requirement, EvidenceRequirement, "/requirement")
        _exact(self.completeness, EvidenceCompleteness, "/completeness")
        _exact(self.status, EvidenceSectionStatus, "/status")
        if type(self.evidence_refs) is not tuple:
            raise _invalid("/evidence_refs", DossierInputCode.WRONG_TYPE)
        refs = tuple(
            _copy_evidence(ref, challenge, f"/evidence_refs/{index}")
            for index, ref in enumerate(self.evidence_refs)
        )
        identities = tuple(
            (ref.evidence_class, ref.evidence_id, ref.evidence_version) for ref in refs
        )
        if len(set(identities)) != len(identities):
            raise _invalid("/evidence_refs", DossierInputCode.DUPLICATE_IDENTITY)
        refs = tuple(
            sorted(
                refs,
                key=lambda ref: (
                    ref.evidence_class.value,
                    ref.evidence_id,
                    ref.evidence_version,
                    ref.content_digest,
                    ref.origin.value,
                ),
            )
        )
        rationale = (
            None
            if self.rationale_ref is None
            else _copy_evidence(self.rationale_ref, challenge, "/rationale_ref")
        )

        if self.completeness in (
            EvidenceCompleteness.INCOMPLETE_MISSING,
            EvidenceCompleteness.INCOMPLETE_PLACEHOLDER,
        ):
            if refs or self.status is not EvidenceSectionStatus.BLOCKED:
                raise _invalid("/completeness", DossierInputCode.MISSING_EVIDENCE)
        elif self.requirement is EvidenceRequirement.REQUIRED:
            primary = DOSSIER_PRIMARY_EVIDENCE_CLASS[self.slot]
            if not refs or not any(ref.evidence_class is primary for ref in refs):
                raise _invalid("/evidence_refs", DossierInputCode.SLOT_MISMATCH)

        if self.requirement is EvidenceRequirement.REQUIRED:
            if rationale is not None:
                raise _invalid("/rationale_ref", DossierInputCode.ROLE_CONFUSION)
        elif self.requirement is EvidenceRequirement.NOT_APPLICABLE_WITH_RATIONALE:
            if (
                rationale is None
                or self.status is not EvidenceSectionStatus.NOT_APPLICABLE
            ):
                raise _invalid("/rationale_ref", DossierInputCode.MISSING_EVIDENCE)
            if self.completeness is not EvidenceCompleteness.COMPLETE_REFERENCED:
                raise _invalid("/completeness", DossierInputCode.MISSING_EVIDENCE)
        elif self.requirement is EvidenceRequirement.DEFERRED_BLOCKING_LIVE and (
            rationale is None or self.status is not EvidenceSectionStatus.BLOCKED
        ):
            raise _invalid("/rationale_ref", DossierInputCode.MISSING_EVIDENCE)

        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "evidence_refs", refs)
        object.__setattr__(self, "rationale_ref", rationale)

    @property
    def fixture_derived(self) -> bool:
        return self.effective_origin is StructuralOrigin.FIXTURE_ONLY

    @property
    def effective_origin(self) -> StructuralOrigin:
        refs = self.evidence_refs + (
            () if self.rationale_ref is None else (self.rationale_ref,)
        )
        return effective_structural_origin(
            *(ref.origin for ref in refs), StructuralOrigin.REGISTERED_REFERENCE
        )


@dataclass(frozen=True, slots=True)
class SignerBinding:
    """Exact role artifacts with deliberately unverified authority state."""

    challenge_key: ChallengeKey
    signer_role: SignerRole
    state: SignerBindingState
    identity_ref: SignerArtifactRef | None = None
    signature_ref: SignerArtifactRef | None = None
    authorization_evidence_ref: SignerArtifactRef | None = None

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        role = _exact(self.signer_role, SignerRole, "/signer_role")
        _exact(self.state, SignerBindingState, "/state")
        if self.state is SignerBindingState.REQUIRED_MISSING:
            if any(
                value is not None
                for value in (
                    self.identity_ref,
                    self.signature_ref,
                    self.authorization_evidence_ref,
                )
            ):
                raise _invalid("/state", DossierInputCode.ROLE_CONFUSION)
            identity = signature = authorization = None
        else:
            identity = _copy_artifact(
                self.identity_ref,
                challenge,
                role,
                SignerArtifactKind.SIGNER_IDENTITY,
                "/identity_ref",
            )
            signature = _copy_artifact(
                self.signature_ref,
                challenge,
                role,
                SignerArtifactKind.SIGNATURE,
                "/signature_ref",
            )
            authorization = (
                None
                if self.authorization_evidence_ref is None
                else _copy_artifact(
                    self.authorization_evidence_ref,
                    challenge,
                    role,
                    SignerArtifactKind.AUTHORIZATION_EVIDENCE,
                    "/authorization_evidence_ref",
                )
            )
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "identity_ref", identity)
        object.__setattr__(self, "signature_ref", signature)
        object.__setattr__(self, "authorization_evidence_ref", authorization)

    @property
    def fixture_derived(self) -> bool:
        return self.effective_origin is StructuralOrigin.FIXTURE_ONLY

    @property
    def effective_origin(self) -> StructuralOrigin:
        refs = tuple(
            ref
            for ref in (
                self.identity_ref,
                self.signature_ref,
                self.authorization_evidence_ref,
            )
            if ref is not None
        )
        return effective_structural_origin(
            *(ref.origin for ref in refs), StructuralOrigin.REGISTERED_REFERENCE
        )


@dataclass(frozen=True, slots=True)
class ValidationDossier:
    """Exact D1–D12 layout with no qualification or activation operation."""

    challenge_key: ChallengeKey
    dossier_id: str
    dossier_version: str
    sections: tuple[DossierSection, ...]
    signer_bindings: tuple[SignerBinding, ...]
    origin: StructuralOrigin
    supersedes: ValidationDossierRef | None = None
    schema_version: str = DOSSIER_SCHEMA_VERSION
    canonicalization_profile: str = DOSSIER_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        challenge = _challenge(self.challenge_key)
        dossier_id = _identifier(self.dossier_id, "/dossier_id")
        dossier_version = _version(self.dossier_version, "/dossier_version")
        _exact(self.origin, StructuralOrigin, "/origin")
        if (
            self.schema_version != DOSSIER_SCHEMA_VERSION
            or type(self.schema_version) is not str
            or self.canonicalization_profile != DOSSIER_CANONICALIZATION_PROFILE
            or type(self.canonicalization_profile) is not str
        ):
            raise _invalid("/schema_version")
        if type(self.sections) is not tuple:
            raise _invalid("/sections", DossierInputCode.WRONG_TYPE)
        if type(self.signer_bindings) is not tuple:
            raise _invalid("/signer_bindings", DossierInputCode.WRONG_TYPE)
        sections: list[DossierSection] = []
        for index, section in enumerate(self.sections):
            item = _exact(section, DossierSection, f"/sections/{index}")
            _same_challenge(item.challenge_key, challenge, f"/sections/{index}")
            sections.append(item)
        if tuple(section.slot for section in sections) != DOSSIER_SLOT_ORDER:
            raise _invalid("/sections", DossierInputCode.SLOT_MISMATCH)
        bindings: list[SignerBinding] = []
        for index, binding in enumerate(self.signer_bindings):
            item = _exact(binding, SignerBinding, f"/signer_bindings/{index}")
            _same_challenge(item.challenge_key, challenge, f"/signer_bindings/{index}")
            bindings.append(item)
        if (
            tuple(binding.signer_role for binding in bindings)
            != REQUIRED_SIGNER_ROLE_ORDER
        ):
            raise _invalid("/signer_bindings", DossierInputCode.ROLE_CONFUSION)
        predecessor = self.supersedes
        if predecessor is not None:
            predecessor = _exact(predecessor, ValidationDossierRef, "/supersedes")
            _same_challenge(predecessor.challenge_key, challenge, "/supersedes")
            if predecessor.dossier_id != dossier_id:
                raise _invalid(
                    "/supersedes/dossier_id", DossierInputCode.ROLE_CONFUSION
                )
            if predecessor.dossier_version == dossier_version:
                raise _invalid(
                    "/supersedes/dossier_version", DossierInputCode.VERSION_MISMATCH
                )
            predecessor = ValidationDossierRef(
                predecessor.challenge_key,
                predecessor.dossier_id,
                predecessor.dossier_version,
                predecessor.content_digest,
                predecessor.origin,
                predecessor.schema_version,
                predecessor.canonicalization_profile,
            )
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "dossier_id", dossier_id)
        object.__setattr__(self, "dossier_version", dossier_version)
        object.__setattr__(self, "sections", tuple(sections))
        object.__setattr__(self, "signer_bindings", tuple(bindings))
        object.__setattr__(self, "supersedes", predecessor)

    @property
    def fixture_derived(self) -> bool:
        return self.effective_origin is StructuralOrigin.FIXTURE_ONLY

    @property
    def effective_origin(self) -> StructuralOrigin:
        return effective_structural_origin(
            self.origin,
            *(section.effective_origin for section in self.sections),
            *(binding.effective_origin for binding in self.signer_bindings),
            *(() if self.supersedes is None else (self.supersedes.origin,)),
        )


__all__ = (
    "DossierSection",
    "SignerBinding",
    "ValidationDossier",
)
