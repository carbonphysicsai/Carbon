"""Strict common values for the B-02A scientific-authoring contract."""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Callable
from typing import TypeAlias, TypeVar

from carbon.authoring.errors import AuthoringValidationError
from carbon.registry import (
    ChallengeKey,
    is_sha256_digest,
    validate_canonical_identifier,
    validate_version,
)

AUTHORING_SCHEMA_VERSION = "1.0"
CANONICALIZATION_PROFILE = "carbon_scientific_authoring_canonical_v1"
DERIVED_EVIDENCE_CANONICALIZATION_PROFILE = (
    "carbon_scientific_authoring_derived_evidence_v1"
)

MAX_CANONICAL_DOCUMENT_BYTES = 16_777_216
MAX_CANONICAL_PAYLOAD_BYTES = 65_535
MAX_CANONICAL_TUPLE_ITEMS = 65_535
MAX_CANONICAL_NESTING_DEPTH = 64

INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1
UINT64_MAX = 2**64 - 1

CanonicalId: TypeAlias = str
VersionToken: TypeAlias = str
TaggedSha256: TypeAlias = str
Utf8Text: TypeAlias = str
Int64: TypeAlias = int
UInt64: TypeAlias = int
PositiveUInt64: TypeAlias = int
FiniteFloat64: TypeAlias = float

_T = TypeVar("_T")


def _invalid(code: str, message: str, field_name: str) -> AuthoringValidationError:
    return AuthoringValidationError(code, message, path=f"/{field_name}")


def validate_canonical_id(value: object, field_name: str = "identifier") -> CanonicalId:
    """Validate the controlling A3 lowercase-ASCII identifier grammar."""
    if type(field_name) is not str or not field_name:
        raise TypeError("field_name must be a nonempty built-in string")
    try:
        return validate_canonical_identifier(value, field_name)
    except (TypeError, ValueError) as exc:
        raise _invalid(
            "authoring.identifier_invalid",
            f"{field_name} is not an exact canonical identifier",
            field_name,
        ) from exc


def validate_version_token(value: object, field_name: str = "version") -> VersionToken:
    """Validate the controlling A3 bounded path-safe version grammar."""
    if type(field_name) is not str or not field_name:
        raise TypeError("field_name must be a nonempty built-in string")
    try:
        return validate_version(value)
    except (TypeError, ValueError) as exc:
        raise _invalid(
            "authoring.version_invalid",
            f"{field_name} is not an exact bounded version token",
            field_name,
        ) from exc


def validate_tagged_sha256(
    value: object, field_name: str = "content_digest"
) -> TaggedSha256:
    """Validate A3's only supported tagged SHA-256 grammar."""
    if type(field_name) is not str or not field_name:
        raise TypeError("field_name must be a nonempty built-in string")
    if not is_sha256_digest(value):
        raise _invalid(
            "authoring.digest_invalid",
            f"{field_name} is not canonical tagged SHA-256",
            field_name,
        )
    return value


def validate_utf8_text(value: object, field_name: str = "text") -> Utf8Text:
    """Validate strict, pre-normalized NFC text without altering caller input."""
    if type(field_name) is not str or not field_name:
        raise TypeError("field_name must be a nonempty built-in string")
    if type(value) is not str:
        raise _invalid(
            "authoring.text_type_invalid",
            f"{field_name} must be an exact built-in string",
            field_name,
        )
    for character in value:
        codepoint = ord(character)
        if (
            codepoint <= 0x1F
            or 0x7F <= codepoint <= 0x9F
            or 0xD800 <= codepoint <= 0xDFFF
        ):
            raise _invalid(
                "authoring.text_codepoint_invalid",
                f"{field_name} contains a forbidden control or surrogate",
                field_name,
            )
    if unicodedata.normalize("NFC", value) != value:
        raise _invalid(
            "authoring.text_not_nfc",
            f"{field_name} must already be NFC normalized",
            field_name,
        )
    try:
        payload = value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise _invalid(
            "authoring.text_utf8_invalid",
            f"{field_name} is not strict UTF-8 text",
            field_name,
        ) from exc
    if len(payload) > MAX_CANONICAL_PAYLOAD_BYTES:
        raise _invalid(
            "authoring.text_too_large",
            f"{field_name} exceeds the canonical TEXT limit",
            field_name,
        )
    return value


def validate_exact_bool(value: object, field_name: str = "value") -> bool:
    """Require exact built-in Boolean, never an integer or subclass."""
    if type(value) is not bool:
        raise _invalid(
            "authoring.bool_type_invalid",
            f"{field_name} must be an exact built-in Boolean",
            field_name,
        )
    return value


def validate_int64(value: object, field_name: str = "value") -> Int64:
    """Require exact signed 64-bit built-in integer."""
    if type(value) is not int or not INT64_MIN <= value <= INT64_MAX:
        raise _invalid(
            "authoring.int64_invalid",
            f"{field_name} must be an exact signed 64-bit built-in integer",
            field_name,
        )
    return value


def validate_uint64(value: object, field_name: str = "value") -> UInt64:
    """Require exact unsigned 64-bit built-in integer."""
    if type(value) is not int or not 0 <= value <= UINT64_MAX:
        raise _invalid(
            "authoring.uint64_invalid",
            f"{field_name} must be an exact unsigned 64-bit built-in integer",
            field_name,
        )
    return value


def validate_positive_uint64(
    value: object, field_name: str = "value"
) -> PositiveUInt64:
    """Require exact nonzero unsigned 64-bit built-in integer."""
    validated = validate_uint64(value, field_name)
    if validated == 0:
        raise _invalid(
            "authoring.positive_uint64_invalid",
            f"{field_name} must be greater than zero",
            field_name,
        )
    return validated


def validate_finite_float64(value: object, field_name: str = "value") -> FiniteFloat64:
    """Require exact finite binary64 and reconstruct every zero as positive zero."""
    if type(value) is not float or not math.isfinite(value):
        raise _invalid(
            "authoring.float64_invalid",
            f"{field_name} must be an exact finite built-in float",
            field_name,
        )
    return 0.0 if value == 0.0 else value


def validate_exact_bytes(value: object, field_name: str = "bytes") -> bytes:
    """Require exact immutable bytes within the canonical payload bound."""
    if type(value) is not bytes:
        raise _invalid(
            "authoring.bytes_type_invalid",
            f"{field_name} must be exact immutable bytes",
            field_name,
        )
    if len(value) > MAX_CANONICAL_PAYLOAD_BYTES:
        raise _invalid(
            "authoring.bytes_too_large",
            f"{field_name} exceeds the canonical BYTES limit",
            field_name,
        )
    return bytes(value)


def validate_exact_document_bytes(
    value: object,
    field_name: str = "document_bytes",
) -> bytes:
    """Require exact immutable bytes within the complete-document bound."""
    if type(value) is not bytes:
        raise _invalid(
            "authoring.document_bytes_type_invalid",
            f"{field_name} must be exact immutable bytes",
            field_name,
        )
    if len(value) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _invalid(
            "authoring.document_bytes_too_large",
            f"{field_name} exceeds the canonical document limit",
            field_name,
        )
    return bytes(value)


def reconstruct_challenge_key(value: object) -> ChallengeKey:
    """Defensively reconstruct an exact A3 ChallengeKey from exact values."""
    if type(value) is not ChallengeKey:
        raise _invalid(
            "authoring.challenge_key_type_invalid",
            "challenge_key must be the exact A3 ChallengeKey type",
            "challenge_key",
        )
    challenge_id = object.__getattribute__(value, "challenge_id")
    version = object.__getattribute__(value, "version")
    if type(challenge_id) is not str or type(version) is not str:
        raise _invalid(
            "authoring.challenge_key_value_invalid",
            "challenge_key fields must be exact built-in strings",
            "challenge_key",
        )
    try:
        return ChallengeKey(challenge_id, version)
    except (TypeError, ValueError) as exc:
        raise _invalid(
            "authoring.challenge_key_value_invalid",
            "challenge_key does not satisfy the controlling A3 grammar",
            "challenge_key",
        ) from exc


def exact_tuple(
    value: object,
    *,
    field_name: str,
    item_validator: Callable[[object], _T] | None = None,
    item_type: type[_T] | None = None,
    nonempty: bool = False,
    unique: bool = False,
    max_items: int = MAX_CANONICAL_TUPLE_ITEMS,
) -> tuple[_T, ...]:
    """Validate and defensively reconstruct one bounded exact built-in tuple."""
    if type(value) is not tuple:
        raise _invalid(
            "authoring.tuple_type_invalid",
            f"{field_name} must be an exact built-in tuple",
            field_name,
        )
    if type(max_items) is not int or not 0 <= max_items <= MAX_CANONICAL_TUPLE_ITEMS:
        raise TypeError("max_items must be a bounded built-in integer")
    if len(value) > max_items or (nonempty and not value):
        raise _invalid(
            "authoring.tuple_size_invalid",
            f"{field_name} has an invalid item count",
            field_name,
        )
    if item_validator is not None and item_type is not None:
        raise TypeError("provide item_validator or item_type, not both")
    reconstructed: list[_T] = []
    for item in value:
        if item_validator is not None:
            reconstructed.append(item_validator(item))
        elif item_type is not None:
            if type(item) is not item_type:
                raise _invalid(
                    "authoring.tuple_item_type_invalid",
                    f"{field_name} contains a wrong exact item type",
                    field_name,
                )
            reconstructed.append(item)
        else:
            reconstructed.append(item)  # type: ignore[arg-type]
    result = tuple(reconstructed)
    if unique:
        try:
            unique_count = len(set(result))
        except TypeError as exc:
            raise _invalid(
                "authoring.tuple_item_unhashable",
                f"{field_name} contains an unhashable item",
                field_name,
            ) from exc
        if unique_count != len(result):
            raise _invalid(
                "authoring.tuple_duplicate",
                f"{field_name} contains duplicate semantic members",
                field_name,
            )
    return result
