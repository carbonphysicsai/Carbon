"""Exact nominal references for B-02C resource-policy artifacts."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import ClassVar, TypeAlias

from carbon.authoring.canonical import (
    CanonicalNominalRef,
    CanonicalRecord,
    CanonicalText,
    challenge_key_from_canonical,
    challenge_key_to_canonical,
    decode_value,
    encode_value,
    tagged_sha256,
)
from carbon.authoring.errors import AuthoringError
from carbon.authoring.primitives import (
    MAX_CANONICAL_PAYLOAD_BYTES,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_version_token,
)
from carbon.registry import ChallengeKey

from .errors import (
    ResourcePolicyCanonicalDecodingError,
    ResourcePolicyInputCode,
    ResourcePolicyInputRejected,
    ResourcePolicyReferenceMismatchError,
)

RESOURCE_POLICY_SCHEMA_VERSION = "1.0"
RESOURCE_POLICY_CANONICALIZATION_PROFILE = "carbon_resource_policy_canonical_v1"


def _wrong(code: ResourcePolicyInputCode, path: str) -> ResourcePolicyInputRejected:
    return ResourcePolicyInputRejected(code, path=path)


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _wrong(ResourcePolicyInputCode.WRONG_TYPE, path) from exc


def _identifier(value: object, path: str) -> str:
    try:
        checked = validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _wrong(ResourcePolicyInputCode.INVALID_VALUE, path) from exc
    if len(checked.encode("ascii")) > MAX_CANONICAL_PAYLOAD_BYTES:
        raise _wrong(ResourcePolicyInputCode.INVALID_VALUE, path)
    return checked


def _version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _wrong(ResourcePolicyInputCode.INVALID_VALUE, path) from exc


def _digest(value: object, path: str = "/content_digest") -> str:
    try:
        return validate_tagged_sha256(value, "content_digest")
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _wrong(ResourcePolicyInputCode.INVALID_VALUE, path) from exc


def _schema_profile(schema: object, profile: object) -> tuple[str, str]:
    validated = _version(schema, "/schema_version")
    if (
        validated != RESOURCE_POLICY_SCHEMA_VERSION
        or type(profile) is not str
        or profile != RESOURCE_POLICY_CANONICALIZATION_PROFILE
    ):
        raise _wrong(ResourcePolicyInputCode.INVALID_VALUE, "/schema_version")
    return validated, profile


@dataclass(frozen=True, slots=True)
class _AuthoredResourcePolicyRefBase:
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    schema_version: str = RESOURCE_POLICY_SCHEMA_VERSION
    canonicalization_profile: str = RESOURCE_POLICY_CANONICALIZATION_PROFILE
    content_digest: str = ""

    OBJECT_KIND: ClassVar[str] = ""

    def __post_init__(self) -> None:
        expected = _AUTHORED_TYPES_BY_KIND.get(self.OBJECT_KIND)
        if expected is None or type(self) is not expected:
            raise _wrong(ResourcePolicyInputCode.WRONG_TYPE, "/ref_type")
        schema, profile = _schema_profile(
            self.schema_version, self.canonicalization_profile
        )
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "object_id", _identifier(self.object_id, "/object_id"))
        object.__setattr__(
            self,
            "object_version",
            _version(self.object_version, "/object_version"),
        )
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def ref_type(self) -> str:
        return f"{self.OBJECT_KIND}_ref"


@dataclass(frozen=True, slots=True)
class ResourceClassRef(_AuthoredResourcePolicyRefBase):
    OBJECT_KIND: ClassVar[str] = "resource_class"


@dataclass(frozen=True, slots=True)
class ResearchResourcePolicyRef(_AuthoredResourcePolicyRefBase):
    OBJECT_KIND: ClassVar[str] = "research_resource_policy"


AUTHORED_RESOURCE_POLICY_REF_TYPES = (ResourceClassRef, ResearchResourcePolicyRef)
_AUTHORED_TYPES_BY_KIND = {
    ref_type.OBJECT_KIND: ref_type for ref_type in AUTHORED_RESOURCE_POLICY_REF_TYPES
}


@dataclass(frozen=True, slots=True)
class _ResolvedResourcePolicyRefBase:
    challenge_key: ChallengeKey
    schema_version: str = RESOURCE_POLICY_SCHEMA_VERSION
    canonicalization_profile: str = RESOURCE_POLICY_CANONICALIZATION_PROFILE
    content_digest: str = ""

    OBJECT_KIND: ClassVar[str] = ""

    def __post_init__(self) -> None:
        expected = _RESOLVED_TYPES_BY_KIND.get(self.OBJECT_KIND)
        if expected is None or type(self) is not expected:
            raise _wrong(ResourcePolicyInputCode.WRONG_TYPE, "/ref_type")
        schema, profile = _schema_profile(
            self.schema_version, self.canonicalization_profile
        )
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def ref_type(self) -> str:
        return f"{self.OBJECT_KIND}_ref"


@dataclass(frozen=True, slots=True)
class StaticResourceAssessmentRef(_ResolvedResourcePolicyRefBase):
    OBJECT_KIND: ClassVar[str] = "static_resource_assessment"


@dataclass(frozen=True, slots=True)
class FixtureResourceDecisionRef(_ResolvedResourcePolicyRefBase):
    OBJECT_KIND: ClassVar[str] = "fixture_resource_decision"


@dataclass(frozen=True, slots=True)
class ResourceCancellationRecordRef(_ResolvedResourcePolicyRefBase):
    OBJECT_KIND: ClassVar[str] = "resource_cancellation_record"


@dataclass(frozen=True, slots=True)
class ObservedResourceReceiptRef(_ResolvedResourcePolicyRefBase):
    OBJECT_KIND: ClassVar[str] = "observed_resource_receipt"


RESOLVED_RESOURCE_POLICY_REF_TYPES = (
    StaticResourceAssessmentRef,
    FixtureResourceDecisionRef,
    ResourceCancellationRecordRef,
    ObservedResourceReceiptRef,
)
_RESOLVED_TYPES_BY_KIND = {
    ref_type.OBJECT_KIND: ref_type for ref_type in RESOLVED_RESOURCE_POLICY_REF_TYPES
}

RESOURCE_POLICY_REF_TYPES = (
    *AUTHORED_RESOURCE_POLICY_REF_TYPES,
    *RESOLVED_RESOURCE_POLICY_REF_TYPES,
)
ResourcePolicyRef: TypeAlias = (
    ResourceClassRef
    | ResearchResourcePolicyRef
    | StaticResourceAssessmentRef
    | FixtureResourceDecisionRef
    | ResourceCancellationRecordRef
    | ObservedResourceReceiptRef
)


def is_resource_policy_ref(value: object) -> bool:
    return type(value) in RESOURCE_POLICY_REF_TYPES


def reconstruct_resource_policy_ref(value: object) -> ResourcePolicyRef:
    if not is_resource_policy_ref(value):
        raise _wrong(ResourcePolicyInputCode.WRONG_TYPE, "/ref_type")
    if type(value) in AUTHORED_RESOURCE_POLICY_REF_TYPES:
        return type(value)(
            value.challenge_key,
            value.object_id,
            value.object_version,
            value.schema_version,
            value.canonicalization_profile,
            value.content_digest,
        )
    return type(value)(
        value.challenge_key,
        value.schema_version,
        value.canonicalization_profile,
        value.content_digest,
    )


def resource_policy_ref_to_canonical(value: object) -> CanonicalNominalRef:
    ref = reconstruct_resource_policy_ref(value)
    fields: list[tuple[str, object]] = [
        (
            "canonicalization_profile",
            CanonicalText(ref.canonicalization_profile),
        ),
        ("challenge_key", challenge_key_to_canonical(ref.challenge_key)),
        ("content_digest", CanonicalText(ref.content_digest)),
    ]
    if type(ref) in AUTHORED_RESOURCE_POLICY_REF_TYPES:
        fields.extend(
            (
                ("object_id", CanonicalText(ref.object_id)),
                ("object_version", CanonicalText(ref.object_version)),
            )
        )
    fields.append(("schema_version", CanonicalText(ref.schema_version)))
    return CanonicalNominalRef(
        ref.ref_type,
        CanonicalRecord(ref.ref_type, tuple(fields)),
    )


def resource_policy_ref_from_canonical(
    value: object,
    *,
    expected_type: type | None = None,
) -> ResourcePolicyRef:
    if type(value) is not CanonicalNominalRef:
        raise ResourcePolicyCanonicalDecodingError()
    candidates = tuple(
        ref_type
        for ref_type in RESOURCE_POLICY_REF_TYPES
        if f"{ref_type.OBJECT_KIND}_ref" == value.ref_type
    )
    if expected_type is not None:
        if (
            type(expected_type) is not type
            or expected_type not in RESOURCE_POLICY_REF_TYPES
        ):
            raise TypeError("expected_type must be an exact resource-policy ref class")
        candidates = tuple(item for item in candidates if item is expected_type)
    if len(candidates) != 1 or value.record.record_type != value.ref_type:
        raise ResourcePolicyCanonicalDecodingError()
    ref_type = candidates[0]
    fields = value.record.field_map()
    expected_fields = {
        "canonicalization_profile",
        "challenge_key",
        "content_digest",
        "schema_version",
    }
    if ref_type in AUTHORED_RESOURCE_POLICY_REF_TYPES:
        expected_fields.update(("object_id", "object_version"))
    if set(fields) != expected_fields:
        raise ResourcePolicyCanonicalDecodingError()

    def text(name: str) -> str:
        item = fields[name]
        if type(item) is not CanonicalText:
            raise ResourcePolicyCanonicalDecodingError()
        return item.value

    try:
        common = (
            challenge_key_from_canonical(fields["challenge_key"]),
            text("schema_version"),
            text("canonicalization_profile"),
            text("content_digest"),
        )
        if ref_type in AUTHORED_RESOURCE_POLICY_REF_TYPES:
            result = ref_type(
                common[0],
                text("object_id"),
                text("object_version"),
                *common[1:],
            )
        else:
            result = ref_type(*common)
    except (AuthoringError, ResourcePolicyInputRejected, TypeError, ValueError) as exc:
        raise ResourcePolicyCanonicalDecodingError() from exc
    if not hmac.compare_digest(
        encode_value(resource_policy_ref_to_canonical(result)), encode_value(value)
    ):
        raise ResourcePolicyCanonicalDecodingError()
    return result


def encode_resource_policy_ref(value: object) -> bytes:
    try:
        return encode_value(resource_policy_ref_to_canonical(value))
    except (AuthoringError, ResourcePolicyInputRejected) as exc:
        raise ResourcePolicyInputRejected(
            ResourcePolicyInputCode.INVALID_VALUE, path="/ref"
        ) from exc


def decode_resource_policy_ref(
    payload: object,
    expected_type: type | None = None,
) -> ResourcePolicyRef:
    if type(payload) is not bytes:
        raise _wrong(ResourcePolicyInputCode.WRONG_TYPE, "/canonical_bytes")
    try:
        canonical = decode_value(payload)
    except AuthoringError as exc:
        trailing = "trailing" in exc.code
        raise ResourcePolicyCanonicalDecodingError(trailing=trailing) from exc
    return resource_policy_ref_from_canonical(canonical, expected_type=expected_type)


def _make_resource_policy_ref(
    ref_type: type,
    *,
    canonical_bytes: object,
    challenge_key: object,
    object_id: object | None = None,
    object_version: object | None = None,
) -> ResourcePolicyRef:
    if type(ref_type) is not type or ref_type not in RESOURCE_POLICY_REF_TYPES:
        raise _wrong(ResourcePolicyInputCode.WRONG_TYPE, "/ref_type")
    if type(canonical_bytes) is not bytes:
        raise _wrong(ResourcePolicyInputCode.WRONG_TYPE, "/canonical_bytes")
    key = _challenge(challenge_key)
    try:
        digest = tagged_sha256(canonical_bytes)
    except (AuthoringError, TypeError, ValueError) as exc:
        raise _wrong(ResourcePolicyInputCode.INVALID_VALUE, "/canonical_bytes") from exc
    if ref_type in AUTHORED_RESOURCE_POLICY_REF_TYPES:
        if object_id is None or object_version is None:
            raise _wrong(ResourcePolicyInputCode.INVALID_VALUE, "/object_id")
        return ref_type(
            key,
            object_id,
            object_version,
            RESOURCE_POLICY_SCHEMA_VERSION,
            RESOURCE_POLICY_CANONICALIZATION_PROFILE,
            digest,
        )
    if object_id is not None or object_version is not None:
        raise _wrong(ResourcePolicyInputCode.INVALID_VALUE, "/object_id")
    return ref_type(
        key,
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        digest,
    )


def verify_resource_policy_ref(
    expected: object,
    *,
    canonical_bytes: object,
    challenge_key: object,
    object_id: object | None = None,
    object_version: object | None = None,
) -> ResourcePolicyRef:
    if not is_resource_policy_ref(expected) or type(canonical_bytes) is not bytes:
        raise ResourcePolicyReferenceMismatchError(path="/ref")
    try:
        recomputed = _make_resource_policy_ref(
            type(expected),
            canonical_bytes=canonical_bytes,
            challenge_key=challenge_key,
            object_id=object_id,
            object_version=object_version,
        )
    except ResourcePolicyInputRejected as exc:
        raise ResourcePolicyReferenceMismatchError(path="/ref") from exc
    if type(recomputed) is not type(expected) or not hmac.compare_digest(
        encode_resource_policy_ref(recomputed), encode_resource_policy_ref(expected)
    ):
        raise ResourcePolicyReferenceMismatchError(path="/ref")
    return reconstruct_resource_policy_ref(expected)


__all__ = [
    "AUTHORED_RESOURCE_POLICY_REF_TYPES",
    "RESOLVED_RESOURCE_POLICY_REF_TYPES",
    "RESOURCE_POLICY_CANONICALIZATION_PROFILE",
    "RESOURCE_POLICY_REF_TYPES",
    "RESOURCE_POLICY_SCHEMA_VERSION",
    "FixtureResourceDecisionRef",
    "ObservedResourceReceiptRef",
    "ResearchResourcePolicyRef",
    "ResourceCancellationRecordRef",
    "ResourceClassRef",
    "ResourcePolicyRef",
    "StaticResourceAssessmentRef",
    "decode_resource_policy_ref",
    "encode_resource_policy_ref",
    "is_resource_policy_ref",
    "reconstruct_resource_policy_ref",
    "resource_policy_ref_from_canonical",
    "resource_policy_ref_to_canonical",
    "verify_resource_policy_ref",
]
