"""Dependency-free exact-version challenge registry and checked LIVE gate."""

from carbon.registry.digest import (
    ArtifactAccessError,
    is_sha256_digest,
    read_verified_artifact_bytes,
)
from carbon.registry.gate import (
    ChallengeRegistry,
    EligibilityReason,
    LiveActivationError,
    LiveEligibility,
    ScientificAuthoringVerifier,
)
from carbon.registry.model import (
    LIFECYCLE_STATES,
    QUALIFICATION_MODES,
    QUALIFICATION_PLACEHOLDER_VALUES,
    REQUIRED_QUALIFICATION_SLOTS,
    REQUIRED_QUALIFICATION_STATES,
    ArtifactBinding,
    ChallengeKey,
    ChallengeRecord,
    QualificationEvidence,
    QualificationManifest,
    ScientificAuthoringEligibility,
    ScientificAuthoringGraphOrigin,
    ScientificAuthoringReason,
    qualification_value_is_missing,
    qualification_value_is_placeholder,
    validate_canonical_identifier,
    validate_version,
)
from carbon.registry.store import RegistryError, serialize_record

__all__ = (
    "LIFECYCLE_STATES",
    "QUALIFICATION_MODES",
    "QUALIFICATION_PLACEHOLDER_VALUES",
    "REQUIRED_QUALIFICATION_SLOTS",
    "REQUIRED_QUALIFICATION_STATES",
    "ArtifactAccessError",
    "ArtifactBinding",
    "ChallengeKey",
    "ChallengeRecord",
    "ChallengeRegistry",
    "EligibilityReason",
    "LiveActivationError",
    "LiveEligibility",
    "QualificationEvidence",
    "QualificationManifest",
    "RegistryError",
    "ScientificAuthoringEligibility",
    "ScientificAuthoringGraphOrigin",
    "ScientificAuthoringReason",
    "ScientificAuthoringVerifier",
    "is_sha256_digest",
    "qualification_value_is_missing",
    "qualification_value_is_placeholder",
    "read_verified_artifact_bytes",
    "serialize_record",
    "validate_canonical_identifier",
    "validate_version",
)
