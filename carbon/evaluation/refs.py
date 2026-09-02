"""Exact protected nominal refs for the B-04 reference/truth profile."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, TypeAlias

from carbon.authoring.canonical import (
    CanonicalNominalRef,
    CanonicalRecord,
    CanonicalText,
    challenge_key_from_canonical,
    challenge_key_to_canonical,
    decode_value,
    encode_value,
)
from carbon.authoring.errors import AuthoringError
from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_tagged_sha256,
    validate_version_token,
)
from carbon.registry.model import ChallengeKey

from .errors import (
    ReferenceCanonicalDecodingError,
    ReferenceInputCode,
    ReferenceValidationError,
)

REFERENCE_TRUTH_SCHEMA_VERSION = "1.0"
REFERENCE_TRUTH_CANONICALIZATION_PROFILE = "carbon_reference_truth_canonical_v1"
REFERENCE_TRUTH_DOCUMENT_HEADER = b"carbon.reference-truth.canonical.v1\x00"


def _wrong(code: ReferenceInputCode, path: str) -> ReferenceValidationError:
    return ReferenceValidationError(code, path=path)


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AttributeError, AuthoringError, TypeError, ValueError):
        raise _wrong(ReferenceInputCode.WRONG_TYPE, path) from None


def _digest(value: object, path: str = "/content_digest") -> str:
    try:
        return validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        raise _wrong(ReferenceInputCode.INVALID_VALUE, path) from None


def _schema_profile(schema: object, profile: object) -> tuple[str, str]:
    try:
        checked_schema = validate_version_token(schema, "schema_version")
    except (AuthoringError, TypeError, ValueError):
        raise _wrong(ReferenceInputCode.INVALID_VALUE, "/schema_version") from None
    if (
        checked_schema != REFERENCE_TRUTH_SCHEMA_VERSION
        or type(profile) is not str
        or profile != REFERENCE_TRUTH_CANONICALIZATION_PROFILE
    ):
        raise _wrong(ReferenceInputCode.INVALID_VALUE, "/schema_version")
    return checked_schema, profile


@dataclass(frozen=True, slots=True, repr=False)
class _ReferenceTruthRefBase:
    challenge_key: ChallengeKey
    content_digest: str
    schema_version: str = REFERENCE_TRUTH_SCHEMA_VERSION
    canonicalization_profile: str = REFERENCE_TRUTH_CANONICALIZATION_PROFILE

    RECORD_TYPE: ClassVar[str] = ""

    def __post_init__(self) -> None:
        expected = _REF_TYPES_BY_RECORD_TYPE.get(self.RECORD_TYPE)
        if expected is None or type(self) is not expected:
            raise _wrong(ReferenceInputCode.WRONG_TYPE, "/ref_type")
        schema, profile = _schema_profile(
            self.schema_version, self.canonicalization_profile
        )
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)

    @property
    def record_type(self) -> str:
        return self.RECORD_TYPE

    @property
    def ref_type(self) -> str:
        return f"{self.RECORD_TYPE}_ref"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected reference refs cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected reference refs cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class PrecomputedReferenceSourceManifestRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "precomputed_reference_source_manifest"


@dataclass(frozen=True, slots=True, repr=False)
class ReferencePolicyRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "reference_policy"


@dataclass(frozen=True, slots=True, repr=False)
class ReferencePolicyEntryRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "reference_policy_entry"


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceCompositionRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "reference_composition"


@dataclass(frozen=True, slots=True, repr=False)
class PrimaryReferenceRequestRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "primary_reference_request"


@dataclass(frozen=True, slots=True, repr=False)
class WitnessReferenceRequestRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "witness_reference_request"


@dataclass(frozen=True, slots=True, repr=False)
class PrimaryRunGrantRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "primary_run_grant"


@dataclass(frozen=True, slots=True, repr=False)
class WitnessRunGrantRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "witness_run_grant"


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceResolutionRecordRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "reference_resolution_record"


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceRunRecordRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "reference_run_record"


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceComparisonRecordRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "reference_comparison_record"


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceArtifactRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "reference_artifact"


@dataclass(frozen=True, slots=True, repr=False)
class FixtureReferenceAssetRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "fixture_reference_asset"


@dataclass(frozen=True, slots=True, repr=False)
class TruthAssetAdmissionGrantIssuanceRecordRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "truth_asset_admission_grant_issuance_record"


@dataclass(frozen=True, slots=True, repr=False)
class TruthAssetAdmissionGrantRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "truth_asset_admission_grant"


@dataclass(frozen=True, slots=True, repr=False)
class TruthAssetAdmissionDecisionRecordRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "truth_asset_admission_decision_record"


@dataclass(frozen=True, slots=True, repr=False)
class TruthAssetRef(_ReferenceTruthRefBase):
    RECORD_TYPE: ClassVar[str] = "truth_asset"


REFERENCE_TRUTH_REF_TYPES = (
    PrecomputedReferenceSourceManifestRef,
    ReferencePolicyRef,
    ReferencePolicyEntryRef,
    ReferenceCompositionRef,
    PrimaryReferenceRequestRef,
    WitnessReferenceRequestRef,
    PrimaryRunGrantRef,
    WitnessRunGrantRef,
    ReferenceResolutionRecordRef,
    ReferenceRunRecordRef,
    ReferenceComparisonRecordRef,
    ReferenceArtifactRef,
    FixtureReferenceAssetRef,
    TruthAssetAdmissionGrantIssuanceRecordRef,
    TruthAssetAdmissionGrantRef,
    TruthAssetAdmissionDecisionRecordRef,
    TruthAssetRef,
)

_REF_TYPES_BY_RECORD_TYPE = MappingProxyType(
    {ref_type.RECORD_TYPE: ref_type for ref_type in REFERENCE_TRUTH_REF_TYPES}
)

ReferenceTruthRef: TypeAlias = (
    PrecomputedReferenceSourceManifestRef
    | ReferencePolicyRef
    | ReferencePolicyEntryRef
    | ReferenceCompositionRef
    | PrimaryReferenceRequestRef
    | WitnessReferenceRequestRef
    | PrimaryRunGrantRef
    | WitnessRunGrantRef
    | ReferenceResolutionRecordRef
    | ReferenceRunRecordRef
    | ReferenceComparisonRecordRef
    | ReferenceArtifactRef
    | FixtureReferenceAssetRef
    | TruthAssetAdmissionGrantIssuanceRecordRef
    | TruthAssetAdmissionGrantRef
    | TruthAssetAdmissionDecisionRecordRef
    | TruthAssetRef
)


def is_reference_truth_ref(value: object) -> bool:
    return type(value) in REFERENCE_TRUTH_REF_TYPES


def reconstruct_reference_truth_ref(value: object) -> ReferenceTruthRef:
    if not is_reference_truth_ref(value):
        raise _wrong(ReferenceInputCode.WRONG_TYPE, "/ref_type")
    try:
        return type(value)(
            object.__getattribute__(value, "challenge_key"),
            object.__getattribute__(value, "content_digest"),
            object.__getattribute__(value, "schema_version"),
            object.__getattribute__(value, "canonicalization_profile"),
        )
    except ReferenceValidationError:
        raise
    except (AttributeError, TypeError, ValueError):
        raise _wrong(ReferenceInputCode.WRONG_TYPE, "/ref_type") from None


def require_reference_truth_ref(
    value: object,
    expected_type: type,
    *,
    challenge_key: ChallengeKey | None = None,
    path: str = "/ref",
) -> ReferenceTruthRef:
    if (
        type(expected_type) is not type
        or expected_type not in REFERENCE_TRUTH_REF_TYPES
        or type(value) is not expected_type
    ):
        raise _wrong(ReferenceInputCode.WRONG_TYPE, path)
    result = reconstruct_reference_truth_ref(value)
    if challenge_key is not None and result.challenge_key != _challenge(challenge_key):
        raise _wrong(ReferenceInputCode.CROSS_CHALLENGE, path)
    return result


def reference_truth_ref_to_canonical(value: object) -> CanonicalNominalRef:
    ref = reconstruct_reference_truth_ref(value)
    return CanonicalNominalRef(
        ref.ref_type,
        CanonicalRecord(
            ref.ref_type,
            (
                (
                    "canonicalization_profile",
                    CanonicalText(ref.canonicalization_profile),
                ),
                ("challenge_key", challenge_key_to_canonical(ref.challenge_key)),
                ("content_digest", CanonicalText(ref.content_digest)),
                ("record_type", CanonicalText(ref.record_type)),
                ("schema_version", CanonicalText(ref.schema_version)),
            ),
        ),
    )


def reference_truth_ref_from_canonical(
    value: object,
    *,
    expected_type: type | None = None,
) -> ReferenceTruthRef:
    if type(value) is not CanonicalNominalRef:
        raise ReferenceCanonicalDecodingError(path="/ref")
    if expected_type is not None and (
        type(expected_type) is not type
        or expected_type not in REFERENCE_TRUTH_REF_TYPES
    ):
        raise TypeError("expected_type must be an exact reference-truth ref class")
    try:
        ref_name = object.__getattribute__(value, "ref_type")
        record = object.__getattribute__(value, "record")
        candidates = tuple(
            ref_type
            for ref_type in REFERENCE_TRUTH_REF_TYPES
            if f"{ref_type.RECORD_TYPE}_ref" == ref_name
        )
        if expected_type is not None:
            candidates = tuple(item for item in candidates if item is expected_type)
        if (
            len(candidates) != 1
            or type(record) is not CanonicalRecord
            or object.__getattribute__(record, "record_type") != ref_name
        ):
            raise ReferenceCanonicalDecodingError(path="/ref")
        fields = record.field_map()
        if set(fields) != {
            "canonicalization_profile",
            "challenge_key",
            "content_digest",
            "record_type",
            "schema_version",
        }:
            raise ReferenceCanonicalDecodingError(path="/ref")

        def text_field(name: str) -> str:
            item = fields[name]
            if type(item) is not CanonicalText:
                raise ReferenceCanonicalDecodingError(path=f"/ref/{name}")
            return object.__getattribute__(item, "value")

        ref_type = candidates[0]
        if text_field("record_type") != ref_type.RECORD_TYPE:
            raise ReferenceCanonicalDecodingError(path="/ref/record_type")
        result = None
        try:
            result = ref_type(
                challenge_key_from_canonical(fields["challenge_key"]),
                text_field("content_digest"),
                text_field("schema_version"),
                text_field("canonicalization_profile"),
            )
        except (AuthoringError, ReferenceValidationError, TypeError, ValueError):
            pass
        if result is None:
            raise ReferenceCanonicalDecodingError(path="/ref")
        if not hmac.compare_digest(
            encode_value(reference_truth_ref_to_canonical(result)), encode_value(value)
        ):
            raise ReferenceCanonicalDecodingError(path="/ref")
        return result
    except ReferenceCanonicalDecodingError:
        raise
    except Exception:  # noqa: BLE001 - normalize hostile canonical carrier behavior.
        raise ReferenceCanonicalDecodingError(path="/ref") from None


def encode_reference_truth_ref(value: object) -> bytes:
    try:
        return encode_value(reference_truth_ref_to_canonical(value))
    except Exception:  # noqa: BLE001 - public hostile-input boundary.
        raise _wrong(ReferenceInputCode.INVALID_VALUE, "/ref") from None


def decode_reference_truth_ref(
    payload: object,
    expected_type: type | None = None,
) -> ReferenceTruthRef:
    if type(payload) is not bytes:
        raise _wrong(ReferenceInputCode.WRONG_TYPE, "/canonical_bytes")
    decode_failed = False
    trailing = False
    try:
        value = decode_value(payload)
    except AuthoringError as exc:
        decode_failed = True
        trailing = "trailing" in exc.code
        value = None
    if decode_failed:
        raise ReferenceCanonicalDecodingError(
            trailing=trailing,
            path="/canonical_bytes",
        )
    return reference_truth_ref_from_canonical(value, expected_type=expected_type)


__all__ = [
    "REFERENCE_TRUTH_CANONICALIZATION_PROFILE",
    "REFERENCE_TRUTH_DOCUMENT_HEADER",
    "REFERENCE_TRUTH_REF_TYPES",
    "REFERENCE_TRUTH_SCHEMA_VERSION",
    "FixtureReferenceAssetRef",
    "PrecomputedReferenceSourceManifestRef",
    "PrimaryReferenceRequestRef",
    "PrimaryRunGrantRef",
    "ReferenceArtifactRef",
    "ReferenceComparisonRecordRef",
    "ReferenceCompositionRef",
    "ReferencePolicyEntryRef",
    "ReferencePolicyRef",
    "ReferenceResolutionRecordRef",
    "ReferenceRunRecordRef",
    "ReferenceTruthRef",
    "TruthAssetAdmissionDecisionRecordRef",
    "TruthAssetAdmissionGrantIssuanceRecordRef",
    "TruthAssetAdmissionGrantRef",
    "TruthAssetRef",
    "WitnessReferenceRequestRef",
    "WitnessRunGrantRef",
    "decode_reference_truth_ref",
    "encode_reference_truth_ref",
    "is_reference_truth_ref",
    "reconstruct_reference_truth_ref",
    "reference_truth_ref_from_canonical",
    "reference_truth_ref_to_canonical",
    "require_reference_truth_ref",
]
