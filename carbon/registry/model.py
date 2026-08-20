"""Immutable data model for exact-version Carbon challenge records."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

LIFECYCLE_STATES = ("draft", "fixture", "live")
QUALIFICATION_MODES = ("production", "fixture")
REQUIRED_QUALIFICATION_STATES = (
    ("generator_envelope", "APPROVED"),
    ("generator_validation", "PASSED"),
    ("dossier_level_1", "APPROVED"),
    ("score_pack", "APPROVED"),
    ("mock_incompleteness", "APPROVED"),
    ("train_backend", "QUALIFIED"),
    ("launch_bar", "SIGNED"),
    ("mcp_readiness", "SIGNED"),
)
REQUIRED_QUALIFICATION_SLOTS = tuple(slot for slot, _ in REQUIRED_QUALIFICATION_STATES)

_CANONICAL_IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*\Z", re.ASCII)
_VERSION_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*\Z", re.ASCII)
_MAX_VERSION_LENGTH = 64
_MAX_PROFILE_ID_LENGTH = 128


def _require_exact_string(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field_name} must be a string")
    return value


def validate_challenge_id(value: object) -> str:
    """Return a valid canonical challenge family identifier without normalizing."""
    challenge_id = _require_exact_string(value, "challenge_id")
    if _CANONICAL_IDENTIFIER.fullmatch(challenge_id) is None:
        raise ValueError("challenge_id is not canonical")
    return challenge_id


def validate_version(value: object) -> str:
    """Return a bounded path-safe ASCII version token without normalizing."""
    version = _require_exact_string(value, "version")
    if len(version) > _MAX_VERSION_LENGTH or _VERSION_TOKEN.fullmatch(version) is None:
        raise ValueError("version is not a bounded canonical token")
    return version


def validate_canonical_identifier(value: object, field_name: str) -> str:
    """Validate an A2-compatible canonical identifier without importing A2."""
    identifier = _require_exact_string(value, field_name)
    if _CANONICAL_IDENTIFIER.fullmatch(identifier) is None:
        raise ValueError(f"{field_name} is not canonical")
    return identifier


def _validate_profile_id(value: object) -> str:
    profile_id = _require_exact_string(value, "backend_profile_id")
    if (
        len(profile_id) > _MAX_PROFILE_ID_LENGTH
        or _VERSION_TOKEN.fullmatch(profile_id) is None
    ):
        raise ValueError("backend_profile_id is not a bounded canonical token")
    return profile_id


@dataclass(frozen=True, slots=True, order=True)
class ChallengeKey:
    """Immutable identity of one scientific challenge contract."""

    challenge_id: str
    version: str

    def __post_init__(self) -> None:
        validate_challenge_id(self.challenge_id)
        validate_version(self.version)


@dataclass(frozen=True, slots=True)
class ArtifactBinding:
    """Expected digest and trusted-root-relative path for one artifact."""

    path: str | None = None
    digest: str | None = None

    def __post_init__(self) -> None:
        if self.path is not None:
            _require_exact_string(self.path, "artifact path")
        if self.digest is not None:
            _require_exact_string(self.digest, "artifact digest")


@dataclass(frozen=True, slots=True)
class QualificationEvidence:
    """Human-owned state and reference bound to a declared artifact."""

    state: str | None = None
    artifact_id: str | None = None
    reference: str | None = None
    backend_profile_ids: tuple[str, ...] = ()
    receipt_schema_version: str | None = None

    def __post_init__(self) -> None:
        if self.state is not None:
            _require_exact_string(self.state, "qualification state")
        if self.artifact_id is not None:
            _require_exact_string(self.artifact_id, "artifact_id")
        if self.reference is not None:
            _require_exact_string(self.reference, "qualification reference")
        if type(self.backend_profile_ids) is not tuple:
            raise TypeError("backend_profile_ids must be a tuple")
        if len(set(self.backend_profile_ids)) != len(self.backend_profile_ids):
            raise ValueError("backend_profile_ids contains a duplicate")
        for profile_id in self.backend_profile_ids:
            _validate_profile_id(profile_id)
        if self.receipt_schema_version is not None:
            validate_version(self.receipt_schema_version)


@dataclass(frozen=True, slots=True)
class QualificationManifest:
    """Exact-version qualification structure; scientific judgment stays human-owned."""

    challenge_id: str | None = None
    challenge_version: str | None = None
    mode: str | None = None
    slots: Mapping[str, QualificationEvidence | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.challenge_id is not None:
            _require_exact_string(self.challenge_id, "manifest challenge_id")
        if self.challenge_version is not None:
            _require_exact_string(self.challenge_version, "manifest challenge_version")
        if self.mode is not None:
            _require_exact_string(self.mode, "qualification mode")
        if not isinstance(self.slots, Mapping):
            raise TypeError("qualification slots must be a mapping")

        copied: dict[str, QualificationEvidence | None] = {}
        for slot, evidence in self.slots.items():
            if type(slot) is not str or slot not in REQUIRED_QUALIFICATION_SLOTS:
                raise ValueError("qualification contains an unknown slot")
            if evidence is not None and not isinstance(evidence, QualificationEvidence):
                raise TypeError("qualification slot has an invalid value")
            if (
                evidence is not None
                and slot != "train_backend"
                and evidence.backend_profile_ids
            ):
                raise ValueError(
                    "backend profile bindings belong only to train_backend"
                )
            if (
                evidence is not None
                and slot != "mcp_readiness"
                and evidence.receipt_schema_version is not None
            ):
                raise ValueError("receipt schema binding belongs only to mcp_readiness")
            copied[slot] = evidence
        object.__setattr__(self, "slots", MappingProxyType(copied))


@dataclass(frozen=True, slots=True)
class ChallengeRecord:
    """Immutable stored record for one :class:`ChallengeKey`."""

    challenge_id: str
    version: str
    fixture_origin: bool = field(kw_only=True)
    status: str = "draft"
    allowed_backbones: tuple[str, ...] = ()
    artifacts: Mapping[str, ArtifactBinding] = field(default_factory=dict)
    qualification: QualificationManifest | None = None
    receipt_schema_version: str | None = None
    required_backend_profile_id: str | None = None
    allowed_backend_profile_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_challenge_id(self.challenge_id)
        validate_version(self.version)
        if type(self.fixture_origin) is not bool:
            raise TypeError("fixture_origin must be a boolean")
        if type(self.status) is not str or self.status not in LIFECYCLE_STATES:
            raise ValueError("status is not a supported lifecycle state")

        if type(self.allowed_backbones) is not tuple:
            raise TypeError("allowed_backbones must be a tuple")
        backbones = self.allowed_backbones
        if len(set(backbones)) != len(backbones):
            raise ValueError("allowed_backbones contains a duplicate")
        for backbone in backbones:
            validate_canonical_identifier(backbone, "backbone")
        object.__setattr__(self, "allowed_backbones", backbones)

        if not isinstance(self.artifacts, Mapping):
            raise TypeError("artifacts must be a mapping")
        artifacts: dict[str, ArtifactBinding] = {}
        for artifact_id, binding in self.artifacts.items():
            validate_canonical_identifier(artifact_id, "artifact_id")
            if not isinstance(binding, ArtifactBinding):
                raise TypeError("artifact binding has an invalid value")
            artifacts[artifact_id] = binding
        object.__setattr__(self, "artifacts", MappingProxyType(artifacts))

        if self.qualification is not None and not isinstance(
            self.qualification, QualificationManifest
        ):
            raise TypeError("qualification must be a QualificationManifest")
        if not self.fixture_origin and (
            self.status == "fixture"
            or (self.qualification is not None and self.qualification.mode == "fixture")
        ):
            raise ValueError("fixture-labelled records must declare fixture_origin")

        if self.receipt_schema_version is not None:
            validate_version(self.receipt_schema_version)
        if self.required_backend_profile_id is not None:
            _validate_profile_id(self.required_backend_profile_id)

        if type(self.allowed_backend_profile_ids) is not tuple:
            raise TypeError("allowed_backend_profile_ids must be a tuple")
        profiles = self.allowed_backend_profile_ids
        if len(set(profiles)) != len(profiles):
            raise ValueError("allowed_backend_profile_ids contains a duplicate")
        for profile_id in profiles:
            _validate_profile_id(profile_id)
        object.__setattr__(self, "allowed_backend_profile_ids", profiles)

    @property
    def key(self) -> ChallengeKey:
        """Return the exact immutable identity represented by this record."""
        return ChallengeKey(self.challenge_id, self.version)
