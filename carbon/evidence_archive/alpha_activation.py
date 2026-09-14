"""Fail-closed activation predicates for C-EA1's provider-backed alpha archive.

This module can describe and verify a rehearsal package.  It cannot issue an
``ArchiveAcknowledgement`` and therefore cannot satisfy C-EA2 by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .alpha_profile import (
    ALPHA_DEPLOYMENT_CONFIG_SCHEMA,
    AlphaArchiveProfile,
    AlphaDeploymentConfiguration,
)
from .model import ArchiveCode, ArchiveFailure, validate_digest, validate_token

ALPHA_ACTIVATION_SCHEMA = "carbon.evidence-archive.alpha-activation.v1"
ALPHA_DEPLOYMENT_MANIFEST_SCHEMA = "carbon.evidence-archive.deployment-manifest.v1"


class AlphaActivationPredicate(StrEnum):
    WELL_FORMED_CONFIGURATION = "WELL_FORMED_CONFIGURATION"
    PROVISIONED_SERVICE_IDENTITY = "PROVISIONED_SERVICE_IDENTITY"
    AUTHENTICATED_AUTHORIZATION = "AUTHENTICATED_AUTHORIZATION"
    RECOVERABLE_OBJECTS = "RECOVERABLE_OBJECTS"
    RECOVERABLE_CATALOGUE = "RECOVERABLE_CATALOGUE"
    RECOVERABLE_JOURNAL = "RECOVERABLE_JOURNAL"
    RECOVERABLE_KEY_VERSION = "RECOVERABLE_KEY_VERSION"
    CAPACITY_RESERVATION = "CAPACITY_RESERVATION"
    INTEGRITY_VERIFICATION = "INTEGRITY_VERIFICATION"
    CURRENT_PERMITTED_USE = "CURRENT_PERMITTED_USE"
    RECOVERY_REHEARSAL = "RECOVERY_REHEARSAL"
    SECURITY_ACCEPTANCE = "SECURITY_ACCEPTANCE"
    DEPLOYMENT_AUTHORIZATION = "DEPLOYMENT_AUTHORIZATION"


class AlphaActivationStatus(StrEnum):
    MISSING_CONFIGURATION = "MISSING_CONFIGURATION"
    REHEARSAL_REQUIRED = "REHEARSAL_REQUIRED"
    EXTERNAL_ACCEPTANCE_REQUIRED = "EXTERNAL_ACCEPTANCE_REQUIRED"
    ACKNOWLEDGEMENT_IMPLEMENTATION_REQUIRED = "ACKNOWLEDGEMENT_IMPLEMENTATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class AlphaPredicateEvidence:
    predicate: AlphaActivationPredicate
    evidence_ref: str
    observed: bool

    def __post_init__(self) -> None:
        if (
            type(self.predicate) is not AlphaActivationPredicate
            or validate_token(self.evidence_ref, maximum=256) != self.evidence_ref
            or type(self.observed) is not bool
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)


@dataclass(frozen=True, slots=True)
class AlphaActivationEvidence:
    profile_digest: str
    provider_profile_id: str
    deployment_manifest_digest: str
    predicates: tuple[AlphaPredicateEvidence, ...]

    def __post_init__(self) -> None:
        if (
            validate_digest(self.profile_digest) != self.profile_digest
            or validate_token(self.provider_profile_id, maximum=128)
            != self.provider_profile_id
            or validate_digest(self.deployment_manifest_digest)
            != self.deployment_manifest_digest
            or type(self.predicates) is not tuple
            or any(
                type(value) is not AlphaPredicateEvidence for value in self.predicates
            )
            or len({value.predicate for value in self.predicates})
            != len(self.predicates)
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)

    def observed(self) -> frozenset[AlphaActivationPredicate]:
        return frozenset(value.predicate for value in self.predicates if value.observed)


@dataclass(frozen=True, slots=True)
class AlphaActivationReadiness:
    schema_version: str
    profile_digest: str
    provider_profile_id: str
    deployment_manifest_digest: str
    status: AlphaActivationStatus
    missing_predicates: tuple[AlphaActivationPredicate, ...]
    eligible_for_real_acknowledgement: bool = False
    eligible_for_c_ea2: bool = False

    def __post_init__(self) -> None:
        if (
            self.schema_version != ALPHA_ACTIVATION_SCHEMA
            or type(self.status) is not AlphaActivationStatus
            or type(self.missing_predicates) is not tuple
            or any(
                type(value) is not AlphaActivationPredicate
                for value in self.missing_predicates
            )
            or self.eligible_for_real_acknowledgement is not False
            or self.eligible_for_c_ea2 is not False
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)

    def public_document(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profile_digest": self.profile_digest,
            "provider_profile_id": self.provider_profile_id,
            "deployment_manifest_digest": self.deployment_manifest_digest,
            "status": self.status.value,
            "missing_predicates": [value.value for value in self.missing_predicates],
            "eligible_for_real_acknowledgement": False,
            "eligible_for_c_ea2": False,
        }


def assess_alpha_activation(
    configuration: AlphaDeploymentConfiguration,
    evidence: AlphaActivationEvidence,
) -> AlphaActivationReadiness:
    if (
        type(configuration) is not AlphaDeploymentConfiguration
        or type(evidence) is not AlphaActivationEvidence
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    profile = AlphaArchiveProfile()
    if evidence.profile_digest != profile.digest:
        raise ArchiveFailure(ArchiveCode.CONFLICT)
    observed = evidence.observed()
    missing = tuple(
        value for value in AlphaActivationPredicate if value not in observed
    )
    if configuration.missing_inputs:
        status = AlphaActivationStatus.MISSING_CONFIGURATION
    elif AlphaActivationPredicate.RECOVERY_REHEARSAL in missing:
        status = AlphaActivationStatus.REHEARSAL_REQUIRED
    elif {
        AlphaActivationPredicate.SECURITY_ACCEPTANCE,
        AlphaActivationPredicate.DEPLOYMENT_AUTHORIZATION,
    } & set(missing):
        status = AlphaActivationStatus.EXTERNAL_ACCEPTANCE_REQUIRED
    else:
        status = AlphaActivationStatus.ACKNOWLEDGEMENT_IMPLEMENTATION_REQUIRED
    return AlphaActivationReadiness(
        ALPHA_ACTIVATION_SCHEMA,
        profile.digest,
        evidence.provider_profile_id,
        evidence.deployment_manifest_digest,
        status,
        missing,
    )


def activation_contract_document() -> dict[str, object]:
    """Return the permanent, non-activating predicate contract."""

    return {
        "schema_version": ALPHA_DEPLOYMENT_CONFIG_SCHEMA,
        "activation_schema": ALPHA_ACTIVATION_SCHEMA,
        "predicates": [value.value for value in AlphaActivationPredicate],
        "eligible_for_real_acknowledgement": False,
        "eligible_for_c_ea2": False,
        "reason": "provider deployment, observed recovery, security acceptance, and an authorized acknowledgement issuer remain external",
    }
