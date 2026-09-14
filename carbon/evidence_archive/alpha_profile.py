"""Fail-closed C-EA1 profile preparation for Carbon alpha evidence.

The existing :class:`EvidenceArchive` remains closed to its accepted synthetic
profile.  This module records and checks the separately versioned operating
targets selected by OWNER-C1-BURGERS-ALPHA-01, but deliberately exposes no
real archive acknowledgement or C-EA2 eligibility path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Any

from .model import (
    ArchiveCode,
    ArchiveFailure,
    ArtifactRequirement,
    ArtifactRule,
    ExecutionDisposition,
    canonical_bytes,
    content_digest,
    validate_token,
)
from .storage import (
    CATALOGUE_SCHEMA_VERSION,
    JOURNAL_SCHEMA_VERSION,
    KeyMaterial,
    ObjectStore,
    PostgresCatalogue,
    decrypt_artifact,
    derive_object_key,
    encrypt_artifact,
)

ALPHA_PROFILE_SCHEMA = "carbon.evidence-archive.alpha-profile.v1"
ALPHA_PROFILE_ID = "carbon.alpha-evidence-archive.private.v1"
ALPHA_PREFLIGHT_SCHEMA = "carbon.evidence-archive.alpha-preflight.v1"
ALPHA_DEPLOYMENT_CONFIG_SCHEMA = "carbon.evidence-archive.alpha-deployment.v1"
ALPHA_PREFLIGHT_TENANT_ID = "carbon-alpha-archive-preflight"
ALPHA_PREFLIGHT_PREFIX = b"CARBON_CEA1_ALPHA_PREFLIGHT_V1\n"

ALPHA_DURABILITY_POLICY_REF = "policy:carbon.alpha-single-host-loss.v1"
ALPHA_CAPTURE_POLICY_REF = "policy:carbon.alpha-burgers-evidence.v1"
ALPHA_CUSTODY_POLICY_REF = "policy:carbon.alpha-private-custody.v1"
ALPHA_RETENTION_POLICY_REF = "policy:carbon.alpha-retention.v1"
ALPHA_USE_POLICY_REF = "policy:carbon.alpha-audit-testnet-use.v1"

ALPHA_MAX_ACTIVE_EVALUATIONS = 1
ALPHA_LOGICAL_QUOTA_BYTES = 20 * 1024**3
ALPHA_MINIMUM_RETENTION_DAYS = 90
ALPHA_RESTORE_TARGET_SECONDS = 24 * 60 * 60
MAX_DEPLOYMENT_CONFIG_BYTES = 64 * 1024


class AlphaNamedUse(StrEnum):
    INTERNAL_AUDIT = "INTERNAL_AUDIT"
    NON_PAYING_TESTNET_EVIDENCE = "NON_PAYING_TESTNET_EVIDENCE"


class AlphaCapacityDisposition(StrEnum):
    RESERVED = "RESERVED"
    BACKPRESSURE = "BACKPRESSURE"


class AlphaPreparationStatus(StrEnum):
    MISSING_EXTERNAL_INPUTS = "MISSING_EXTERNAL_INPUTS"
    ACTIVATION_IMPLEMENTATION_REQUIRED = "ACTIVATION_IMPLEMENTATION_REQUIRED"


class AlphaExternalInput(StrEnum):
    TENANT_ID = "tenant_id"
    PROVIDER_ID = "provider_id"
    PROJECT_ID = "project_id"
    REGION_ID = "region_id"
    CATALOGUE_SERVICE_REF = "catalogue_service_ref"
    CATALOGUE_RECOVERY_REF = "catalogue_recovery_ref"
    OBJECT_STORE_REF = "object_store_ref"
    OBJECT_VERSIONING_POLICY_REF = "object_versioning_policy_ref"
    OBJECT_RECOVERY_REF = "object_recovery_ref"
    JOURNAL_RECOVERY_REF = "journal_recovery_ref"
    CUSTODY_PRINCIPALS_REF = "custody_principals_ref"
    KEY_SERVICE_REF = "key_service_ref"
    KEY_VERSION_REF = "key_version_ref"
    DEPLOYMENT_IDENTITY = "deployment_identity"
    COST_ESTIMATE_REF = "cost_estimate_ref"
    RECOVERY_TEST_EVIDENCE_REF = "recovery_test_evidence_ref"
    SECURITY_ACCEPTANCE_REF = "security_acceptance_ref"
    DEPLOYMENT_AUTHORIZATION_REF = "deployment_authorization_ref"


@dataclass(frozen=True, slots=True)
class AlphaCapacityAssessment:
    disposition: AlphaCapacityDisposition
    active_evaluations_after: int
    reserved_bytes_after: int

    def __post_init__(self) -> None:
        if (
            type(self.disposition) is not AlphaCapacityDisposition
            or type(self.active_evaluations_after) is not int
            or type(self.reserved_bytes_after) is not int
            or self.active_evaluations_after < 0
            or self.reserved_bytes_after < 0
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)


@dataclass(frozen=True, slots=True)
class AlphaCapacityPolicy:
    max_active_evaluations: int = ALPHA_MAX_ACTIVE_EVALUATIONS
    logical_quota_bytes: int = ALPHA_LOGICAL_QUOTA_BYTES

    def __post_init__(self) -> None:
        if (
            self.max_active_evaluations != ALPHA_MAX_ACTIVE_EVALUATIONS
            or self.logical_quota_bytes != ALPHA_LOGICAL_QUOTA_BYTES
        ):
            raise ArchiveFailure(ArchiveCode.DENIED)

    def assess(
        self,
        *,
        active_evaluations: int,
        reserved_bytes: int,
        declared_bytes: int,
    ) -> AlphaCapacityAssessment:
        values = (active_evaluations, reserved_bytes, declared_bytes)
        if any(type(value) is not int for value in values):
            raise ArchiveFailure(ArchiveCode.INVALID)
        if (
            active_evaluations < 0
            or reserved_bytes < 0
            or declared_bytes < 1
            or active_evaluations > self.max_active_evaluations
            or reserved_bytes > self.logical_quota_bytes
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)
        projected_active = active_evaluations + 1
        projected_bytes = reserved_bytes + declared_bytes
        disposition = (
            AlphaCapacityDisposition.RESERVED
            if projected_active <= self.max_active_evaluations
            and projected_bytes <= self.logical_quota_bytes
            else AlphaCapacityDisposition.BACKPRESSURE
        )
        return AlphaCapacityAssessment(
            disposition,
            projected_active,
            projected_bytes,
        )


@dataclass(frozen=True, slots=True)
class AlphaRetentionPolicy:
    minimum_retention_days: int = ALPHA_MINIMUM_RETENTION_DAYS
    retain_until_receipt_obligations_close: bool = True
    retain_until_review_obligations_close: bool = True
    retain_until_dispute_obligations_close: bool = True

    def __post_init__(self) -> None:
        if (
            self.minimum_retention_days != ALPHA_MINIMUM_RETENTION_DAYS
            or self.retain_until_receipt_obligations_close is not True
            or self.retain_until_review_obligations_close is not True
            or self.retain_until_dispute_obligations_close is not True
        ):
            raise ArchiveFailure(ArchiveCode.DENIED)

    def earliest_deletion_epoch_seconds(
        self,
        *,
        last_eligible_use_epoch_seconds: int | None,
        receipt_obligation_open: bool,
        review_obligation_open: bool,
        dispute_obligation_open: bool,
    ) -> int | None:
        flags = (
            receipt_obligation_open,
            review_obligation_open,
            dispute_obligation_open,
        )
        if any(type(value) is not bool for value in flags):
            raise ArchiveFailure(ArchiveCode.INVALID)
        if last_eligible_use_epoch_seconds is not None and (
            type(last_eligible_use_epoch_seconds) is not int
            or last_eligible_use_epoch_seconds < 0
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)
        if last_eligible_use_epoch_seconds is None or any(flags):
            return None
        return last_eligible_use_epoch_seconds + self.minimum_retention_days * 86400


def _alpha_artifact_rules() -> tuple[ArtifactRule, ...]:
    terminal = (
        ExecutionDisposition.INTERRUPTED,
        ExecutionDisposition.CANCELLED,
        ExecutionDisposition.EARLY_STOPPED,
        ExecutionDisposition.COMPLETED,
    )
    completed = (
        ExecutionDisposition.EARLY_STOPPED,
        ExecutionDisposition.COMPLETED,
    )
    return (
        ArtifactRule("source_binding", ArtifactRequirement.REQUIRED, terminal),
        ArtifactRule("construction_plan", ArtifactRequirement.REQUIRED, terminal),
        ArtifactRule("runtime_manifest", ArtifactRequirement.REQUIRED, terminal),
        ArtifactRule("attempt_journal", ArtifactRequirement.REQUIRED, terminal),
        ArtifactRule("outcome_account", ArtifactRequirement.REQUIRED, terminal),
        ArtifactRule("checkpoint_index", ArtifactRequirement.REQUIRED, terminal),
        ArtifactRule("evidence_manifest", ArtifactRequirement.REQUIRED, terminal),
        ArtifactRule(
            "reconstruction_artifact", ArtifactRequirement.REQUIRED, completed
        ),
        ArtifactRule("reference_measurement", ArtifactRequirement.REQUIRED, completed),
        ArtifactRule("signed_receipt", ArtifactRequirement.REQUIRED, completed),
        ArtifactRule("bounded_diagnostics", ArtifactRequirement.OPTIONAL_DEBUG),
        ArtifactRule("derived_summary", ArtifactRequirement.REBUILDABLE_DERIVATIVE),
    )


@dataclass(frozen=True, slots=True)
class AlphaArchiveProfile:
    schema_version: str = ALPHA_PROFILE_SCHEMA
    profile_id: str = ALPHA_PROFILE_ID
    durability_policy_ref: str = ALPHA_DURABILITY_POLICY_REF
    capture_policy_ref: str = ALPHA_CAPTURE_POLICY_REF
    custody_policy_ref: str = ALPHA_CUSTODY_POLICY_REF
    retention_policy_ref: str = ALPHA_RETENTION_POLICY_REF
    use_policy_ref: str = ALPHA_USE_POLICY_REF
    named_uses: tuple[AlphaNamedUse, ...] = (
        AlphaNamedUse.INTERNAL_AUDIT,
        AlphaNamedUse.NON_PAYING_TESTNET_EVIDENCE,
    )
    artifact_rules: tuple[ArtifactRule, ...] = _alpha_artifact_rules()
    capacity: AlphaCapacityPolicy = AlphaCapacityPolicy()
    retention: AlphaRetentionPolicy = AlphaRetentionPolicy()
    restore_target_seconds: int = ALPHA_RESTORE_TARGET_SECONDS
    single_host_loss_target: bool = True
    correlated_provider_region_loss_excluded: bool = True
    multi_region_availability_excluded: bool = True
    acknowledgement_implemented: bool = False

    def __post_init__(self) -> None:
        fixed = (
            self.schema_version == ALPHA_PROFILE_SCHEMA
            and self.profile_id == ALPHA_PROFILE_ID
            and self.durability_policy_ref == ALPHA_DURABILITY_POLICY_REF
            and self.capture_policy_ref == ALPHA_CAPTURE_POLICY_REF
            and self.custody_policy_ref == ALPHA_CUSTODY_POLICY_REF
            and self.retention_policy_ref == ALPHA_RETENTION_POLICY_REF
            and self.use_policy_ref == ALPHA_USE_POLICY_REF
            and self.named_uses
            == (
                AlphaNamedUse.INTERNAL_AUDIT,
                AlphaNamedUse.NON_PAYING_TESTNET_EVIDENCE,
            )
            and self.artifact_rules == _alpha_artifact_rules()
            and type(self.capacity) is AlphaCapacityPolicy
            and type(self.retention) is AlphaRetentionPolicy
            and self.restore_target_seconds == ALPHA_RESTORE_TARGET_SECONDS
            and self.single_host_loss_target is True
            and self.correlated_provider_region_loss_excluded is True
            and self.multi_region_availability_excluded is True
            and self.acknowledgement_implemented is False
        )
        if not fixed:
            raise ArchiveFailure(ArchiveCode.DENIED)

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "policy_refs": {
                "capture": self.capture_policy_ref,
                "custody": self.custody_policy_ref,
                "durability": self.durability_policy_ref,
                "retention": self.retention_policy_ref,
                "use": self.use_policy_ref,
            },
            "named_uses": [value.value for value in self.named_uses],
            "capacity": {
                "logical_quota_bytes": self.capacity.logical_quota_bytes,
                "max_active_evaluations": self.capacity.max_active_evaluations,
            },
            "retention": {
                "minimum_retention_days": self.retention.minimum_retention_days,
                "retain_until_dispute_obligations_close": True,
                "retain_until_receipt_obligations_close": True,
                "retain_until_review_obligations_close": True,
            },
            "recovery": {
                "restore_target_seconds": self.restore_target_seconds,
                "single_host_loss_target": True,
                "correlated_provider_region_loss_excluded": True,
                "multi_region_availability_excluded": True,
            },
            "artifact_rules": [
                {
                    "name": rule.name,
                    "requirement": rule.requirement.value,
                    "required_for": [value.value for value in rule.required_for],
                }
                for rule in self.artifact_rules
            ],
            "acknowledgement_implemented": False,
        }

    @property
    def digest(self) -> str:
        return content_digest(
            "carbon.evidence-archive.alpha-profile.v1",
            canonical_bytes(self.payload()),
        )


@dataclass(frozen=True, slots=True)
class AlphaDeploymentConfiguration:
    tenant_id: str | None = None
    provider_id: str | None = None
    project_id: str | None = None
    region_id: str | None = None
    catalogue_service_ref: str | None = None
    catalogue_recovery_ref: str | None = None
    object_store_ref: str | None = None
    object_versioning_policy_ref: str | None = None
    object_recovery_ref: str | None = None
    journal_recovery_ref: str | None = None
    custody_principals_ref: str | None = None
    key_service_ref: str | None = None
    key_version_ref: str | None = None
    deployment_identity: str | None = None
    cost_estimate_ref: str | None = None
    recovery_test_evidence_ref: str | None = None
    security_acceptance_ref: str | None = None
    deployment_authorization_ref: str | None = None

    def __post_init__(self) -> None:
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            if value is not None:
                object.__setattr__(
                    self,
                    descriptor.name,
                    validate_token(value, maximum=256),
                )

    @property
    def missing_inputs(self) -> tuple[AlphaExternalInput, ...]:
        return tuple(
            value for value in AlphaExternalInput if getattr(self, value.value) is None
        )

    def document(self) -> dict[str, str | None]:
        return {
            descriptor.name: getattr(self, descriptor.name)
            for descriptor in fields(self)
        }


@dataclass(frozen=True, slots=True)
class AlphaDeploymentReadiness:
    schema_version: str
    profile_id: str
    profile_digest: str
    status: AlphaPreparationStatus
    missing_external_inputs: tuple[AlphaExternalInput, ...]
    isolated_preflight_passed: bool
    eligible_for_real_acknowledgement: bool = False
    eligible_for_c_ea2: bool = False

    def __post_init__(self) -> None:
        if (
            self.schema_version != ALPHA_DEPLOYMENT_CONFIG_SCHEMA
            or self.profile_id != ALPHA_PROFILE_ID
            or type(self.status) is not AlphaPreparationStatus
            or type(self.missing_external_inputs) is not tuple
            or any(
                type(value) is not AlphaExternalInput
                for value in self.missing_external_inputs
            )
            or type(self.isolated_preflight_passed) is not bool
            or self.eligible_for_real_acknowledgement is not False
            or self.eligible_for_c_ea2 is not False
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)

    def public_document(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "profile_digest": self.profile_digest,
            "status": self.status.value,
            "missing_external_inputs": [
                value.value for value in self.missing_external_inputs
            ],
            "isolated_preflight_passed": self.isolated_preflight_passed,
            "eligible_for_real_acknowledgement": False,
            "eligible_for_c_ea2": False,
        }


@dataclass(frozen=True, slots=True)
class AlphaPreflightReport:
    schema_version: str
    profile_digest: str
    catalogue_schema_version: str
    journal_schema_version: str
    probe_ref: str
    catalogue_schema_verified: bool
    object_round_trip_verified: bool
    encryption_round_trip_verified: bool
    capacity_policy_verified: bool
    isolated_non_secret_test_only: bool = True
    eligible_for_real_acknowledgement: bool = False
    eligible_for_c_ea2: bool = False

    def __post_init__(self) -> None:
        if (
            self.schema_version != ALPHA_PREFLIGHT_SCHEMA
            or self.catalogue_schema_version != CATALOGUE_SCHEMA_VERSION
            or self.journal_schema_version != JOURNAL_SCHEMA_VERSION
            or any(
                value is not True
                for value in (
                    self.catalogue_schema_verified,
                    self.object_round_trip_verified,
                    self.encryption_round_trip_verified,
                    self.capacity_policy_verified,
                    self.isolated_non_secret_test_only,
                )
            )
            or self.eligible_for_real_acknowledgement is not False
            or self.eligible_for_c_ea2 is not False
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)


def assess_alpha_deployment(
    configuration: AlphaDeploymentConfiguration,
    *,
    isolated_preflight_passed: bool,
) -> AlphaDeploymentReadiness:
    if (
        type(configuration) is not AlphaDeploymentConfiguration
        or type(isolated_preflight_passed) is not bool
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    missing = configuration.missing_inputs
    status = (
        AlphaPreparationStatus.MISSING_EXTERNAL_INPUTS
        if missing
        else AlphaPreparationStatus.ACTIVATION_IMPLEMENTATION_REQUIRED
    )
    profile = AlphaArchiveProfile()
    return AlphaDeploymentReadiness(
        ALPHA_DEPLOYMENT_CONFIG_SCHEMA,
        profile.profile_id,
        profile.digest,
        status,
        missing,
        isolated_preflight_passed,
    )


def parse_alpha_deployment_configuration(
    payload: bytes,
) -> AlphaDeploymentConfiguration:
    if (
        type(payload) is not bytes
        or not 1 <= len(payload) <= MAX_DEPLOYMENT_CONFIG_BYTES
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)

    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ArchiveFailure(ArchiveCode.INVALID)
            result[key] = value
        return result

    try:
        document = json.loads(payload, object_pairs_hook=closed_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ArchiveFailure):
        raise ArchiveFailure(ArchiveCode.INVALID) from None
    expected = {value.value for value in AlphaExternalInput}
    if type(document) is not dict or set(document) != expected:
        raise ArchiveFailure(ArchiveCode.INVALID)
    if any(value is not None and type(value) is not str for value in document.values()):
        raise ArchiveFailure(ArchiveCode.INVALID)
    return AlphaDeploymentConfiguration(**document)


def run_isolated_alpha_preflight(
    catalogue: PostgresCatalogue,
    objects: ObjectStore,
    key: KeyMaterial,
    *,
    probe_id: str,
) -> AlphaPreflightReport:
    """Exercise reusable adapters without creating an archive entry or ack."""

    if type(catalogue) is not PostgresCatalogue or type(key) is not KeyMaterial:
        raise ArchiveFailure(ArchiveCode.DENIED)
    probe_id = validate_token(probe_id)
    if getattr(objects, "tenant_id", None) != ALPHA_PREFLIGHT_TENANT_ID:
        raise ArchiveFailure(ArchiveCode.DENIED)

    catalogue.verify_schema()
    profile = AlphaArchiveProfile()
    capacity = profile.capacity.assess(
        active_evaluations=0,
        reserved_bytes=0,
        declared_bytes=profile.capacity.logical_quota_bytes,
    )
    if capacity.disposition is not AlphaCapacityDisposition.RESERVED:
        raise ArchiveFailure(ArchiveCode.CAPACITY)

    payload = ALPHA_PREFLIGHT_PREFIX + canonical_bytes(
        {"probe_id": probe_id, "profile_digest": profile.digest}
    )
    probe_ref = content_digest("carbon.evidence-archive.alpha-probe.v1", payload)
    artifact_digest = content_digest("carbon.evidence-artifact.v1", payload)
    envelope = encrypt_artifact(
        payload,
        entry_id=probe_ref,
        artifact_name="preflight_canary",
        plaintext_digest=artifact_digest,
        key=key,
    )
    object_key = derive_object_key(
        ALPHA_PREFLIGHT_TENANT_ID,
        probe_ref,
        "preflight_canary",
        artifact_digest,
    )
    objects.put_immutable(object_key, envelope.ciphertext)
    persisted = objects.get(object_key)
    if persisted != envelope.ciphertext:
        raise ArchiveFailure(ArchiveCode.INTEGRITY)
    restored = decrypt_artifact(
        envelope,
        entry_id=probe_ref,
        artifact_name="preflight_canary",
        plaintext_digest=artifact_digest,
        key=key,
    )
    if restored != payload or object_key not in objects.list_keys(
        ALPHA_PREFLIGHT_TENANT_ID
    ):
        raise ArchiveFailure(ArchiveCode.INTEGRITY)
    return AlphaPreflightReport(
        ALPHA_PREFLIGHT_SCHEMA,
        profile.digest,
        CATALOGUE_SCHEMA_VERSION,
        JOURNAL_SCHEMA_VERSION,
        probe_ref,
        True,
        True,
        True,
        True,
    )
