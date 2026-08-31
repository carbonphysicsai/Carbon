"""Exact nominal references for B-02B construction artifacts."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import ClassVar, TypeAlias

from carbon.authoring.errors import AuthoringValidationError
from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_version_token,
)
from carbon.construction.errors import (
    ConstructionReferenceMismatchError,
    ConstructionValidationError,
)
from carbon.registry import ChallengeKey

CONSTRUCTION_SCHEMA_VERSION = "1.0"
CONSTRUCTION_CANONICALIZATION_PROFILE = "carbon_construction_canonical_v1"


def _invalid(code: str, message: str, path: str) -> ConstructionValidationError:
    return ConstructionValidationError(code, message, path=path)


def _challenge_key(value: object) -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.challenge_key_invalid",
            "challenge_key must be an exact valid A3 ChallengeKey",
            "/challenge_key",
        ) from exc


def _canonical_id(value: object, field: str) -> str:
    try:
        return validate_canonical_id(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.identifier_invalid",
            f"{field} must be an exact canonical identifier",
            f"/{field}",
        ) from exc


def _version(value: object, field: str) -> str:
    try:
        return validate_version_token(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.version_invalid",
            f"{field} must be an exact bounded version token",
            f"/{field}",
        ) from exc


def _digest(value: object) -> str:
    try:
        return validate_tagged_sha256(value, "content_digest")
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.digest_invalid",
            "content_digest must be canonical tagged SHA-256",
            "/content_digest",
        ) from exc


def _schema_and_profile(schema_version: object, profile: object) -> tuple[str, str]:
    schema = _version(schema_version, "schema_version")
    if schema != CONSTRUCTION_SCHEMA_VERSION:
        raise _invalid(
            "construction.schema_version_unsupported",
            "construction v1 supports only schema version 1.0",
            "/schema_version",
        )
    if type(profile) is not str or profile != CONSTRUCTION_CANONICALIZATION_PROFILE:
        raise _invalid(
            "construction.canonicalization_profile_invalid",
            "construction reference uses an unknown canonicalization profile",
            "/canonicalization_profile",
        )
    return schema, profile


@dataclass(frozen=True, slots=True)
class _AuthoredConstructionRefBase:
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    schema_version: str = CONSTRUCTION_SCHEMA_VERSION
    canonicalization_profile: str = CONSTRUCTION_CANONICALIZATION_PROFILE
    content_digest: str = ""

    OBJECT_KIND: ClassVar[str] = ""

    def __post_init__(self) -> None:
        expected = _AUTHORED_REF_TYPES_BY_KIND.get(self.OBJECT_KIND)
        if expected is None or type(self) is not expected:
            raise _invalid(
                "construction.reference_nominal_type_invalid",
                "long-lived construction ref has a wrong exact nominal type",
                "/object_kind",
            )
        schema, profile = _schema_and_profile(
            self.schema_version, self.canonicalization_profile
        )
        object.__setattr__(self, "challenge_key", _challenge_key(self.challenge_key))
        object.__setattr__(
            self, "object_id", _canonical_id(self.object_id, "object_id")
        )
        object.__setattr__(
            self, "object_version", _version(self.object_version, "object_version")
        )
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def object_kind(self) -> str:
        return self.OBJECT_KIND

    @property
    def ref_type(self) -> str:
        return f"{self.OBJECT_KIND}_ref"


@dataclass(frozen=True, slots=True)
class CandidateAssemblyContractRef(_AuthoredConstructionRefBase):
    OBJECT_KIND: ClassVar[str] = "candidate_assembly_contract"


@dataclass(frozen=True, slots=True)
class ParameterCatalogRef(_AuthoredConstructionRefBase):
    OBJECT_KIND: ClassVar[str] = "parameter_catalog"


_AUTHORED_REF_TYPES_BY_KIND: dict[str, type[_AuthoredConstructionRefBase]] = {
    ref_type.OBJECT_KIND: ref_type
    for ref_type in (CandidateAssemblyContractRef, ParameterCatalogRef)
}


@dataclass(frozen=True, slots=True)
class _ResolvedConstructionRefBase:
    challenge_key: ChallengeKey
    schema_version: str = CONSTRUCTION_SCHEMA_VERSION
    canonicalization_profile: str = CONSTRUCTION_CANONICALIZATION_PROFILE
    content_digest: str = ""

    OBJECT_KIND: ClassVar[str] = ""

    def __post_init__(self) -> None:
        expected = _RESOLVED_REF_TYPES_BY_KIND.get(self.OBJECT_KIND)
        if expected is None or type(self) is not expected:
            raise _invalid(
                "construction.reference_nominal_type_invalid",
                "resolved construction ref has a wrong exact nominal type",
                "/object_kind",
            )
        schema, profile = _schema_and_profile(
            self.schema_version, self.canonicalization_profile
        )
        object.__setattr__(self, "challenge_key", _challenge_key(self.challenge_key))
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def object_kind(self) -> str:
        return self.OBJECT_KIND

    @property
    def ref_type(self) -> str:
        return f"{self.OBJECT_KIND}_ref"


@dataclass(frozen=True, slots=True)
class TrainingSamplingPolicyRef(_ResolvedConstructionRefBase):
    OBJECT_KIND: ClassVar[str] = "resolved_training_sampling_policy"


@dataclass(frozen=True, slots=True)
class ResolvedConstructionPlanRef(_ResolvedConstructionRefBase):
    OBJECT_KIND: ClassVar[str] = "resolved_construction_plan"


_RESOLVED_REF_TYPES_BY_KIND: dict[str, type[_ResolvedConstructionRefBase]] = {
    ref_type.OBJECT_KIND: ref_type
    for ref_type in (TrainingSamplingPolicyRef, ResolvedConstructionPlanRef)
}

AuthoredConstructionRef: TypeAlias = CandidateAssemblyContractRef | ParameterCatalogRef
ResolvedConstructionRef: TypeAlias = (
    TrainingSamplingPolicyRef | ResolvedConstructionPlanRef
)
ConstructionRef: TypeAlias = AuthoredConstructionRef | ResolvedConstructionRef

AUTHORED_CONSTRUCTION_REF_TYPES = (
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
)
RESOLVED_CONSTRUCTION_REF_TYPES = (
    TrainingSamplingPolicyRef,
    ResolvedConstructionPlanRef,
)
CONSTRUCTION_REF_TYPES = (
    *AUTHORED_CONSTRUCTION_REF_TYPES,
    *RESOLVED_CONSTRUCTION_REF_TYPES,
)


def is_construction_ref(value: object) -> bool:
    """Return whether *value* has one exact closed construction ref type."""

    return any(type(value) is ref_type for ref_type in CONSTRUCTION_REF_TYPES)


def reconstruct_construction_ref(value: object) -> ConstructionRef:
    """Defensively reconstruct an exact construction ref without kind coercion."""

    if type(value) in AUTHORED_CONSTRUCTION_REF_TYPES:
        return type(value)(
            value.challenge_key,
            value.object_id,
            value.object_version,
            value.schema_version,
            value.canonicalization_profile,
            value.content_digest,
        )
    if type(value) in RESOLVED_CONSTRUCTION_REF_TYPES:
        return type(value)(
            value.challenge_key,
            value.schema_version,
            value.canonicalization_profile,
            value.content_digest,
        )
    raise _invalid(
        "construction.reference_type_invalid",
        "value is not an exact closed construction ref",
        "/ref_type",
    )


def reconstruct_authored_ref(value: object) -> AuthoredConstructionRef:
    """Defensively copy one exact long-lived construction reference."""

    copied = reconstruct_construction_ref(value)
    if type(copied) not in AUTHORED_CONSTRUCTION_REF_TYPES:
        raise _invalid(
            "construction.reference_type_mismatch",
            "reference is not a long-lived construction ref",
            "/ref_type",
        )
    return copied


def reconstruct_resolved_ref(value: object) -> ResolvedConstructionRef:
    """Defensively copy one exact digest-only construction reference."""

    copied = reconstruct_construction_ref(value)
    if type(copied) not in RESOLVED_CONSTRUCTION_REF_TYPES:
        raise _invalid(
            "construction.reference_type_mismatch",
            "reference is not a resolved construction ref",
            "/ref_type",
        )
    return copied


def tagged_sha256(payload: object) -> str:
    """Delegate to B-02A's exact tagged SHA-256 implementation."""

    from carbon.authoring.canonical import tagged_sha256 as authoring_tagged_sha256

    try:
        return authoring_tagged_sha256(payload)
    except ValueError as exc:
        raise _invalid(
            "construction.digest_payload_type_invalid",
            "digest input must be exact immutable bytes",
            "/canonical_bytes",
        ) from exc


def make_authored_ref(
    ref_type: type,
    *,
    canonical_bytes: object,
    challenge_key: object,
    object_id: object,
    object_version: object,
    schema_version: object = CONSTRUCTION_SCHEMA_VERSION,
    canonicalization_profile: object = CONSTRUCTION_CANONICALIZATION_PROFILE,
) -> AuthoredConstructionRef:
    """Create a nominal long-lived ref from a complete construction document."""

    if type(ref_type) is not type or ref_type not in AUTHORED_CONSTRUCTION_REF_TYPES:
        raise _invalid(
            "construction.reference_class_invalid",
            "ref_type must be an exact long-lived construction ref class",
            "/ref_type",
        )
    if type(canonical_bytes) is not bytes:
        raise _invalid(
            "construction.canonical_payload_type_invalid",
            "canonical document must be exact immutable bytes",
            "/canonical_bytes",
        )
    return ref_type(
        challenge_key,
        object_id,
        object_version,
        schema_version,
        canonicalization_profile,
        tagged_sha256(canonical_bytes),
    )


def make_resolved_ref(
    ref_type: type,
    *,
    canonical_bytes: object,
    challenge_key: object,
    schema_version: object = CONSTRUCTION_SCHEMA_VERSION,
    canonicalization_profile: object = CONSTRUCTION_CANONICALIZATION_PROFILE,
) -> ResolvedConstructionRef:
    """Create a nominal digest-only ref from a complete construction document."""

    if type(ref_type) is not type or ref_type not in RESOLVED_CONSTRUCTION_REF_TYPES:
        raise _invalid(
            "construction.reference_class_invalid",
            "ref_type must be an exact resolved construction ref class",
            "/ref_type",
        )
    if type(canonical_bytes) is not bytes:
        raise _invalid(
            "construction.canonical_payload_type_invalid",
            "canonical document must be exact immutable bytes",
            "/canonical_bytes",
        )
    return ref_type(
        challenge_key,
        schema_version,
        canonicalization_profile,
        tagged_sha256(canonical_bytes),
    )


def verify_construction_ref(
    expected: object,
    *,
    canonical_bytes: object,
    challenge_key: object,
    object_id: object | None = None,
    object_version: object | None = None,
) -> ConstructionRef:
    """Recompute and constant-time compare every exact reference field."""

    if type(canonical_bytes) is not bytes or not is_construction_ref(expected):
        raise ConstructionReferenceMismatchError(
            "construction.reference_mismatch",
            "reference or canonical bytes have a wrong exact type",
        )
    try:
        if type(expected) in AUTHORED_CONSTRUCTION_REF_TYPES:
            if object_id is None or object_version is None:
                raise ConstructionValidationError(
                    "construction.reference_metadata_missing",
                    "authored reference verification requires identity metadata",
                )
            recomputed: ConstructionRef = make_authored_ref(
                type(expected),
                canonical_bytes=canonical_bytes,
                challenge_key=challenge_key,
                object_id=object_id,
                object_version=object_version,
                schema_version=expected.schema_version,
                canonicalization_profile=expected.canonicalization_profile,
            )
        else:
            if object_id is not None or object_version is not None:
                raise ConstructionValidationError(
                    "construction.reference_metadata_forbidden",
                    "resolved references have no logical identity metadata",
                )
            recomputed = make_resolved_ref(
                type(expected),
                canonical_bytes=canonical_bytes,
                challenge_key=challenge_key,
                schema_version=expected.schema_version,
                canonicalization_profile=expected.canonicalization_profile,
            )
    except ConstructionValidationError as exc:
        raise ConstructionReferenceMismatchError(
            "construction.reference_mismatch",
            "reference metadata is invalid or differs from canonical bytes",
        ) from exc
    from carbon.construction.canonical import encode_construction_ref

    if type(recomputed) is not type(expected) or not hmac.compare_digest(
        encode_construction_ref(recomputed), encode_construction_ref(expected)
    ):
        raise ConstructionReferenceMismatchError(
            "construction.reference_mismatch",
            "recomputed reference does not exactly match the expected pin",
        )
    return reconstruct_construction_ref(expected)


__all__ = [
    "AUTHORED_CONSTRUCTION_REF_TYPES",
    "CONSTRUCTION_CANONICALIZATION_PROFILE",
    "CONSTRUCTION_REF_TYPES",
    "CONSTRUCTION_SCHEMA_VERSION",
    "RESOLVED_CONSTRUCTION_REF_TYPES",
    "AuthoredConstructionRef",
    "CandidateAssemblyContractRef",
    "ConstructionRef",
    "ParameterCatalogRef",
    "ResolvedConstructionPlanRef",
    "ResolvedConstructionRef",
    "TrainingSamplingPolicyRef",
    "is_construction_ref",
    "make_authored_ref",
    "make_resolved_ref",
    "reconstruct_authored_ref",
    "reconstruct_construction_ref",
    "reconstruct_resolved_ref",
    "tagged_sha256",
    "verify_construction_ref",
]
