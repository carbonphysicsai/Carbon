"""Fail-closed LIVE qualification and activation for challenge records."""

from __future__ import annotations

import hmac
from dataclasses import dataclass, replace

from carbon.registry.digest import (
    ArtifactAccessError,
    digest_artifact,
    is_sha256_digest,
)
from carbon.registry.model import (
    REQUIRED_QUALIFICATION_STATES,
    ChallengeKey,
    ChallengeRecord,
    QualificationEvidence,
    validate_canonical_identifier,
)
from carbon.registry.store import RegistryError, RegistryStore

_PLACEHOLDERS = frozenset(
    {
        "BLOCKED_FOR_LIVE_UNTIL_SET",
        "HUMAN_INPUT",
        "PLACEHOLDER",
        "TODO",
        "TODO(sciml)",
        "FIXTURE",
        "fixture",
    }
)


@dataclass(frozen=True, slots=True)
class EligibilityReason:
    """One stable, safe, machine-readable reason a LIVE gate failed."""

    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class LiveEligibility:
    """Immutable diagnostic result from a complete LIVE gate assessment."""

    eligible: bool
    reasons: tuple[EligibilityReason, ...]


class LiveActivationError(RegistryError):
    """Checked LIVE transition failure that preserves diagnostic reasons."""

    def __init__(self, eligibility: LiveEligibility) -> None:
        self.eligibility = eligibility
        super().__init__(
            "activation.ineligible",
            "/status",
            "Challenge record is not eligible for LIVE activation.",
        )


def _reason(code: str, path: str, message: str) -> EligibilityReason:
    return EligibilityReason(code=code, path=path, message=message)


def _is_empty(value: str | None) -> bool:
    return value is None or not value.strip()


def _is_placeholder(value: str | None) -> bool:
    return value is not None and value.strip() in _PLACEHOLDERS


class ChallengeRegistry(RegistryStore):
    """Configured file store plus exact-version LIVE and compatibility APIs."""

    def assess_live_eligibility(
        self,
        challenge_id: str,
        version: str,
        *,
        fixture_mode: bool = False,
    ) -> LiveEligibility:
        """Diagnose production or explicit-fixture eligibility for one exact key."""
        if type(fixture_mode) is not bool:
            return LiveEligibility(
                eligible=False,
                reasons=(
                    _reason(
                        "assessment.fixture_mode_invalid",
                        "/fixture_mode",
                        "fixture_mode must be a boolean.",
                    ),
                ),
            )
        try:
            record = self.load(challenge_id, version)
        except RegistryError as exc:
            return LiveEligibility(
                eligible=False,
                reasons=(_reason(exc.code, exc.path, str(exc)),),
            )
        return self._assess_record(record, fixture_mode=fixture_mode)

    def _assess_record(
        self, record: ChallengeRecord, *, fixture_mode: bool
    ) -> LiveEligibility:
        reasons: list[EligibilityReason] = []
        manifest = record.qualification

        # 1. Record and exact-identity errors.
        if not fixture_mode and _is_placeholder(record.version):
            reasons.append(
                _reason(
                    "record.version_placeholder",
                    "/version",
                    "Placeholder challenge version is blocked from production.",
                )
            )
        if manifest is None:
            reasons.append(
                _reason(
                    "qualification.missing",
                    "/qualification",
                    "Qualification manifest is missing.",
                )
            )
        else:
            if manifest.challenge_id is None:
                reasons.append(
                    _reason(
                        "qualification.challenge_id_missing",
                        "/qualification/challenge_id",
                        "Qualification challenge identity is missing.",
                    )
                )
            elif manifest.challenge_id != record.challenge_id:
                reasons.append(
                    _reason(
                        "qualification.challenge_id_mismatch",
                        "/qualification/challenge_id",
                        "Qualification is bound to a different challenge.",
                    )
                )
            if manifest.challenge_version is None:
                reasons.append(
                    _reason(
                        "qualification.challenge_version_missing",
                        "/qualification/challenge_version",
                        "Qualification challenge version is missing.",
                    )
                )
            elif manifest.challenge_version != record.version:
                reasons.append(
                    _reason(
                        "qualification.challenge_version_mismatch",
                        "/qualification/challenge_version",
                        "Qualification is bound to a different challenge version.",
                    )
                )

        # 2. Lifecycle and qualification-mode errors.
        if fixture_mode:
            if record.status != "fixture":
                reasons.append(
                    _reason(
                        "lifecycle.fixture_status_required",
                        "/status",
                        "Fixture assessment requires fixture lifecycle status.",
                    )
                )
            if manifest is not None and manifest.mode != "fixture":
                reasons.append(
                    _reason(
                        "qualification.fixture_mode_required",
                        "/qualification/mode",
                        "Fixture assessment requires fixture qualification mode.",
                    )
                )
        else:
            if record.status == "fixture":
                reasons.append(
                    _reason(
                        "lifecycle.fixture_blocked",
                        "/status",
                        "Fixture lifecycle status is blocked from production.",
                    )
                )
            if manifest is not None:
                if manifest.mode == "fixture":
                    reasons.append(
                        _reason(
                            "qualification.fixture_mode_blocked",
                            "/qualification/mode",
                            "Fixture qualification is blocked from production.",
                        )
                    )
                elif manifest.mode != "production":
                    reasons.append(
                        _reason(
                            "qualification.production_mode_required",
                            "/qualification/mode",
                            "Production qualification mode is required.",
                        )
                    )

        if manifest is not None:
            # 3. Required slots, always in the canonical eight-slot order.
            for slot, expected_state in REQUIRED_QUALIFICATION_STATES:
                slot_path = f"/qualification/slots/{slot}"
                if slot not in manifest.slots:
                    reasons.append(
                        _reason(
                            "qualification.slot_missing",
                            slot_path,
                            "Required qualification slot is missing.",
                        )
                    )
                    continue
                evidence = manifest.slots[slot]
                if evidence is None:
                    reasons.append(
                        _reason(
                            "qualification.slot_null",
                            slot_path,
                            "Required qualification slot is null.",
                        )
                    )
                    continue
                state_path = f"{slot_path}/state"
                if _is_empty(evidence.state):
                    reasons.append(
                        _reason(
                            "qualification.state_missing",
                            state_path,
                            "Required qualification state is missing.",
                        )
                    )
                elif _is_placeholder(evidence.state):
                    reasons.append(
                        _reason(
                            "qualification.state_placeholder",
                            state_path,
                            "Placeholder qualification state is not sufficient.",
                        )
                    )
                elif evidence.state != expected_state:
                    reasons.append(
                        _reason(
                            "qualification.state_mismatch",
                            state_path,
                            "Qualification state does not match the required state.",
                        )
                    )

            # 4a. Artifact IDs and human references in canonical slot order.
            for slot, _ in REQUIRED_QUALIFICATION_STATES:
                evidence = manifest.slots.get(slot)
                if not isinstance(evidence, QualificationEvidence):
                    continue
                slot_path = f"/qualification/slots/{slot}"
                if _is_empty(evidence.artifact_id):
                    reasons.append(
                        _reason(
                            "qualification.artifact_id_missing",
                            f"{slot_path}/artifact_id",
                            "Qualification artifact identifier is missing.",
                        )
                    )
                elif evidence.artifact_id not in record.artifacts:
                    reasons.append(
                        _reason(
                            "qualification.artifact_unknown",
                            f"{slot_path}/artifact_id",
                            "Qualification references an unknown artifact.",
                        )
                    )

                if _is_empty(evidence.reference):
                    reasons.append(
                        _reason(
                            "qualification.reference_missing",
                            f"{slot_path}/reference",
                            "Human-owned qualification reference is missing.",
                        )
                    )
                elif _is_placeholder(evidence.reference):
                    reasons.append(
                        _reason(
                            "qualification.reference_placeholder",
                            f"{slot_path}/reference",
                            "Placeholder qualification reference is not sufficient.",
                        )
                    )

            # 4b. Reserved evidence bindings are structural, not approvals.
            required_profile = record.required_backend_profile_id
            allowed_profiles = record.allowed_backend_profile_ids
            train_backend = manifest.slots.get("train_backend")
            mcp_readiness = manifest.slots.get("mcp_readiness")

            if allowed_profiles and required_profile is None:
                reasons.append(
                    _reason(
                        "backend_profile.required_missing",
                        "/required_backend_profile_id",
                        "A required backend profile must select the exact allowed set.",
                    )
                )
            elif (
                required_profile is not None
                and required_profile not in allowed_profiles
            ):
                reasons.append(
                    _reason(
                        "backend_profile.required_not_allowed",
                        "/required_backend_profile_id",
                        "Required backend profile is not in the exact allowed set.",
                    )
                )

            for index, profile_id in enumerate(allowed_profiles):
                if not fixture_mode and _is_placeholder(profile_id):
                    reasons.append(
                        _reason(
                            "backend_profile.placeholder",
                            f"/allowed_backend_profile_ids/{index}",
                            "Placeholder backend profile is blocked from production.",
                        )
                    )
            if not fixture_mode and _is_placeholder(required_profile):
                reasons.append(
                    _reason(
                        "backend_profile.placeholder",
                        "/required_backend_profile_id",
                        "Placeholder backend profile is blocked from production.",
                    )
                )

            evidence_profiles = (
                train_backend.backend_profile_ids
                if isinstance(train_backend, QualificationEvidence)
                else ()
            )
            if evidence_profiles != allowed_profiles:
                reasons.append(
                    _reason(
                        "backend_profile.binding_mismatch",
                        "/qualification/slots/train_backend/backend_profile_ids",
                        "Backend profile evidence does not match the record binding.",
                    )
                )
            for index, profile_id in enumerate(evidence_profiles):
                if not fixture_mode and _is_placeholder(profile_id):
                    reasons.append(
                        _reason(
                            "backend_profile.evidence_placeholder",
                            (
                                "/qualification/slots/train_backend/"
                                f"backend_profile_ids/{index}"
                            ),
                            "Placeholder backend evidence is blocked from production.",
                        )
                    )

            receipt_version = record.receipt_schema_version
            evidence_receipt_version = (
                mcp_readiness.receipt_schema_version
                if isinstance(mcp_readiness, QualificationEvidence)
                else None
            )
            if evidence_receipt_version != receipt_version:
                reasons.append(
                    _reason(
                        "receipt_schema.binding_mismatch",
                        (
                            "/qualification/slots/mcp_readiness/"
                            "receipt_schema_version"
                        ),
                        "Receipt schema evidence does not match the record binding.",
                    )
                )
            if not fixture_mode and _is_placeholder(receipt_version):
                reasons.append(
                    _reason(
                        "receipt_schema.placeholder",
                        "/receipt_schema_version",
                        "Placeholder receipt schema is blocked from production.",
                    )
                )
            if not fixture_mode and _is_placeholder(evidence_receipt_version):
                reasons.append(
                    _reason(
                        "receipt_schema.evidence_placeholder",
                        (
                            "/qualification/slots/mcp_readiness/"
                            "receipt_schema_version"
                        ),
                        "Placeholder receipt evidence is blocked from production.",
                    )
                )

        # 5. Every declared binding is checked in deterministic artifact-id order.
        for artifact_id in sorted(record.artifacts):
            binding = record.artifacts[artifact_id]
            artifact_path = f"/artifacts/{artifact_id}"
            actual_digest: str | None = None
            if _is_empty(binding.path):
                reasons.append(
                    _reason(
                        "artifact.path_missing",
                        f"{artifact_path}/path",
                        "Artifact path is missing.",
                    )
                )
            else:
                try:
                    actual_digest = digest_artifact(self.artifact_root, binding.path)
                except ArtifactAccessError as exc:
                    reasons.append(_reason(exc.code, f"{artifact_path}/path", str(exc)))

            if _is_empty(binding.digest):
                reasons.append(
                    _reason(
                        "artifact.digest_missing",
                        f"{artifact_path}/digest",
                        "Expected artifact digest is missing.",
                    )
                )
            elif not is_sha256_digest(binding.digest):
                reasons.append(
                    _reason(
                        "artifact.digest_invalid",
                        f"{artifact_path}/digest",
                        "Expected artifact digest is not canonical tagged SHA-256.",
                    )
                )
            elif actual_digest is not None and not hmac.compare_digest(
                actual_digest, binding.digest
            ):
                reasons.append(
                    _reason(
                        "artifact.digest_mismatch",
                        f"{artifact_path}/digest",
                        "Actual artifact bytes do not match the expected digest.",
                    )
                )

        return LiveEligibility(eligible=not reasons, reasons=tuple(reasons))

    def can_go_live(
        self,
        challenge_id: str,
        version: str,
        *,
        fixture_mode: bool = False,
    ) -> bool:
        """Return the diagnostic gate result as a convenience boolean."""
        return self.assess_live_eligibility(
            challenge_id, version, fixture_mode=fixture_mode
        ).eligible

    def is_effectively_live(self, challenge_id: str, version: str) -> bool:
        """Revalidate stored LIVE state and all bound artifact bytes every time."""
        try:
            record = self.load(challenge_id, version)
        except RegistryError:
            return False
        return (
            record.status == "live"
            and self._assess_record(record, fixture_mode=False).eligible
        )

    def activate_live(self, challenge_id: str, version: str) -> ChallengeRecord:
        """Atomically persist LIVE only after a complete production assessment."""
        try:
            key = ChallengeKey(challenge_id, version)
        except ValueError as exc:
            raise RegistryError(
                "record.identity_invalid", "", "Challenge identity is invalid."
            ) from exc
        with self._key_lock(key):
            record = self.load(challenge_id, version)
            if record.status != "draft":
                eligibility = LiveEligibility(
                    eligible=False,
                    reasons=(
                        _reason(
                            "lifecycle.activation_source_invalid",
                            "/status",
                            "LIVE activation requires draft source status.",
                        ),
                    ),
                )
                raise LiveActivationError(eligibility)

            eligibility = self._assess_record(record, fixture_mode=False)
            if not eligibility.eligible:
                raise LiveActivationError(eligibility)
            activated = replace(record, status="live")
            self._atomic_write(activated)
            return activated

    def is_backbone_allowed(
        self, challenge_id: str, version: str, backbone: str
    ) -> bool:
        """Check exact-key declarative compatibility without importing a backend."""
        try:
            validate_canonical_identifier(backbone, "backbone")
        except ValueError as exc:
            raise RegistryError(
                "backbone.identifier_invalid", "", "Backbone identifier is invalid."
            ) from exc
        return backbone in self.load(challenge_id, version).allowed_backbones
