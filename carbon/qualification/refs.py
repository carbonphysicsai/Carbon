"""Exact nominal references for the B-06 Validation Dossier foundation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_version_token,
)
from carbon.registry.model import ChallengeKey

from .enums import (
    DossierEvidenceClass,
    SignerArtifactKind,
    SignerRole,
    StructuralOrigin,
)
from .errors import DossierInputCode, DossierValidationError

if TYPE_CHECKING:
    from .enums import DossierSlot

DOSSIER_SCHEMA_VERSION = "1.0"
DOSSIER_CANONICALIZATION_PROFILE = "carbon_validation_dossier_canonical_v1"
DOSSIER_DOCUMENT_HEADER = b"carbon.qualification.validation-dossier.canonical.v1\x00"
EVIDENCE_MANIFEST_SCHEMA_VERSION = "1.0"
EVIDENCE_MANIFEST_CANONICALIZATION_PROFILE = (
    "carbon_dossier_evidence_manifest_canonical_v1"
)
EVIDENCE_MANIFEST_DOCUMENT_HEADER = (
    b"carbon.qualification.evidence-manifest.canonical.v1\x00"
)
QUALIFICATION_CANDIDATE_SCHEMA_VERSION = "1.0"
QUALIFICATION_CANDIDATE_CANONICALIZATION_PROFILE = (
    "carbon_qualification_manifest_candidate_canonical_v1"
)
QUALIFICATION_CANDIDATE_DOCUMENT_HEADER = (
    b"carbon.qualification.manifest-candidate.canonical.v1\x00"
)
A3_QUALIFICATION_SNAPSHOT_DOCUMENT_HEADER = (
    b"carbon.qualification.a3-manifest-snapshot.canonical.v1\x00"
)

_PLACEHOLDER_IDS = frozenset({"none", "placeholder", "tbd", "todo", "unknown", "unset"})


def _invalid(path: str, code: DossierInputCode = DossierInputCode.INVALID_VALUE):
    return DossierValidationError(code, path=path)


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, DossierInputCode.WRONG_TYPE) from None


def _identifier(value: object, path: str) -> str:
    try:
        result = validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None
    if result in _PLACEHOLDER_IDS or result.startswith("placeholder-"):
        raise _invalid(path, DossierInputCode.PLACEHOLDER_EVIDENCE)
    return result


def _version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _digest(value: object, path: str = "/content_digest") -> str:
    try:
        return validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _profile(schema: object, profile: object) -> tuple[str, str]:
    schema_value = _version(schema, "/schema_version")
    if (
        schema_value != DOSSIER_SCHEMA_VERSION
        or type(profile) is not str
        or profile != DOSSIER_CANONICALIZATION_PROFILE
    ):
        raise _invalid("/schema_version")
    return schema_value, profile


class _ProtectedRef:
    def __repr__(self) -> str:
        return f"{type(self).__name__}(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected Dossier refs cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected Dossier refs cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class DossierEvidenceRef(_ProtectedRef):
    challenge_key: ChallengeKey
    evidence_class: DossierEvidenceClass
    evidence_id: str
    evidence_version: str
    content_digest: str
    origin: StructuralOrigin

    def __post_init__(self) -> None:
        if type(self) is not DossierEvidenceRef:
            raise _invalid("/ref_type", DossierInputCode.WRONG_TYPE)
        if type(self.evidence_class) is not DossierEvidenceClass:
            raise _invalid("/evidence_class", DossierInputCode.WRONG_TYPE)
        if type(self.origin) is not StructuralOrigin:
            raise _invalid("/origin", DossierInputCode.WRONG_TYPE)
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(
            self, "evidence_id", _identifier(self.evidence_id, "/evidence_id")
        )
        object.__setattr__(
            self,
            "evidence_version",
            _version(self.evidence_version, "/evidence_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def ref_type(self) -> str:
        return "dossier_evidence_ref"


@dataclass(frozen=True, slots=True, repr=False)
class SignerArtifactRef(_ProtectedRef):
    challenge_key: ChallengeKey
    signer_role: SignerRole
    artifact_kind: SignerArtifactKind
    artifact_id: str
    artifact_version: str
    content_digest: str
    origin: StructuralOrigin

    def __post_init__(self) -> None:
        if type(self) is not SignerArtifactRef:
            raise _invalid("/ref_type", DossierInputCode.WRONG_TYPE)
        if type(self.signer_role) is not SignerRole:
            raise _invalid("/signer_role", DossierInputCode.WRONG_TYPE)
        if type(self.artifact_kind) is not SignerArtifactKind:
            raise _invalid("/artifact_kind", DossierInputCode.WRONG_TYPE)
        if type(self.origin) is not StructuralOrigin:
            raise _invalid("/origin", DossierInputCode.WRONG_TYPE)
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(
            self, "artifact_id", _identifier(self.artifact_id, "/artifact_id")
        )
        object.__setattr__(
            self,
            "artifact_version",
            _version(self.artifact_version, "/artifact_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def ref_type(self) -> str:
        return "signer_artifact_ref"


@dataclass(frozen=True, slots=True, repr=False)
class ValidationDossierRef(_ProtectedRef):
    challenge_key: ChallengeKey
    dossier_id: str
    dossier_version: str
    content_digest: str
    schema_version: str = DOSSIER_SCHEMA_VERSION
    canonicalization_profile: str = DOSSIER_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        if type(self) is not ValidationDossierRef:
            raise _invalid("/ref_type", DossierInputCode.WRONG_TYPE)
        schema, profile = _profile(self.schema_version, self.canonicalization_profile)
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(
            self, "dossier_id", _identifier(self.dossier_id, "/dossier_id")
        )
        object.__setattr__(
            self, "dossier_version", _version(self.dossier_version, "/dossier_version")
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)

    @property
    def ref_type(self) -> str:
        return "validation_dossier_ref"


@dataclass(frozen=True, slots=True, repr=False)
class DossierEvidenceManifestRef(_ProtectedRef):
    challenge_key: ChallengeKey
    slot: DossierSlot
    manifest_id: str
    manifest_version: str
    content_digest: str
    origin: StructuralOrigin
    schema_version: str = EVIDENCE_MANIFEST_SCHEMA_VERSION
    canonicalization_profile: str = EVIDENCE_MANIFEST_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        from .enums import DossierSlot, StructuralOrigin

        if type(self) is not DossierEvidenceManifestRef:
            raise _invalid("/ref_type", DossierInputCode.WRONG_TYPE)
        if type(self.slot) is not DossierSlot:
            raise _invalid("/slot", DossierInputCode.WRONG_TYPE)
        if type(self.origin) is not StructuralOrigin:
            raise _invalid("/origin", DossierInputCode.WRONG_TYPE)
        schema_value = _version(self.schema_version, "/schema_version")
        if (
            schema_value != EVIDENCE_MANIFEST_SCHEMA_VERSION
            or type(self.canonicalization_profile) is not str
            or self.canonicalization_profile
            != EVIDENCE_MANIFEST_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(
            self, "manifest_id", _identifier(self.manifest_id, "/manifest_id")
        )
        object.__setattr__(
            self,
            "manifest_version",
            _version(self.manifest_version, "/manifest_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        object.__setattr__(self, "schema_version", schema_value)

    @property
    def ref_type(self) -> str:
        return "dossier_evidence_manifest_ref"


@dataclass(frozen=True, slots=True, repr=False)
class QualificationManifestCandidateRef(_ProtectedRef):
    challenge_key: ChallengeKey
    candidate_id: str
    candidate_version: str
    content_digest: str
    schema_version: str = QUALIFICATION_CANDIDATE_SCHEMA_VERSION
    canonicalization_profile: str = QUALIFICATION_CANDIDATE_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        if type(self) is not QualificationManifestCandidateRef:
            raise _invalid("/ref_type", DossierInputCode.WRONG_TYPE)
        schema_value = _version(self.schema_version, "/schema_version")
        if (
            schema_value != QUALIFICATION_CANDIDATE_SCHEMA_VERSION
            or type(self.canonicalization_profile) is not str
            or self.canonicalization_profile
            != QUALIFICATION_CANDIDATE_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version")
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(
            self, "candidate_id", _identifier(self.candidate_id, "/candidate_id")
        )
        object.__setattr__(
            self,
            "candidate_version",
            _version(self.candidate_version, "/candidate_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        object.__setattr__(self, "schema_version", schema_value)

    @property
    def ref_type(self) -> str:
        return "qualification_manifest_candidate_ref"


__all__ = (
    "A3_QUALIFICATION_SNAPSHOT_DOCUMENT_HEADER",
    "DOSSIER_CANONICALIZATION_PROFILE",
    "DOSSIER_DOCUMENT_HEADER",
    "DOSSIER_SCHEMA_VERSION",
    "EVIDENCE_MANIFEST_CANONICALIZATION_PROFILE",
    "EVIDENCE_MANIFEST_DOCUMENT_HEADER",
    "EVIDENCE_MANIFEST_SCHEMA_VERSION",
    "QUALIFICATION_CANDIDATE_CANONICALIZATION_PROFILE",
    "QUALIFICATION_CANDIDATE_DOCUMENT_HEADER",
    "QUALIFICATION_CANDIDATE_SCHEMA_VERSION",
    "DossierEvidenceManifestRef",
    "DossierEvidenceRef",
    "QualificationManifestCandidateRef",
    "SignerArtifactRef",
    "ValidationDossierRef",
)
