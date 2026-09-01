"""Closed canonical identity for the B-04 reference/truth runtime.

The codec wraps B-02A's audited primitive/ref codecs while owning a separate
domain header and a literal B-04 schema registry.  It never reflects over a
dataclass, accepts a caller registry, or infers a type from untrusted bytes.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from types import MappingProxyType
from typing import NamedTuple

from carbon.authoring.canonical import (
    CanonicalBytes,
    CanonicalRecord,
    CanonicalText,
    CanonicalTuple,
    CanonicalUnion,
    CanonicalValue,
    challenge_key_from_canonical,
    challenge_key_to_canonical,
    decode_value,
    encode_value,
    owner_ref_from_canonical,
    owner_ref_to_canonical,
    tagged_sha256,
    top_level_ref_from_canonical,
    top_level_ref_to_canonical,
)
from carbon.authoring.errors import AuthoringError
from carbon.authoring.primitives import MAX_CANONICAL_DOCUMENT_BYTES
from carbon.authoring.refs import is_owner_ref
from carbon.registry.model import ChallengeKey

from .errors import (
    ReferenceCanonicalDecodingError,
    ReferenceCanonicalEncodingError,
    ReferenceInputCode,
    ReferenceMismatchError,
    ReferenceValidationError,
)
from .refs import (
    REFERENCE_TRUTH_CANONICALIZATION_PROFILE,
    REFERENCE_TRUTH_DOCUMENT_HEADER,
    REFERENCE_TRUTH_REF_TYPES,
    REFERENCE_TRUTH_SCHEMA_VERSION,
    ReferenceTruthRef,
    reconstruct_reference_truth_ref,
    reference_truth_ref_from_canonical,
    reference_truth_ref_to_canonical,
)

REFERENCE_TRUTH_CANONICAL_OBJECT_KINDS = (
    "precomputed_reference_source_manifest",
    "reference_policy",
    "reference_policy_entry",
    "reference_composition",
    "primary_reference_request",
    "witness_reference_request",
    "primary_run_grant",
    "witness_run_grant",
    "reference_resolution_record",
    "reference_run_record",
    "reference_comparison_record",
    "reference_artifact",
    "fixture_reference_asset",
    "truth_asset_admission_grant_issuance_record",
    "truth_asset_admission_grant",
    "truth_asset_admission_decision_record",
    "truth_asset",
)

_CANONICAL_TYPE_OWNERS = MappingProxyType(
    {
        "precomputed_reference_source_manifest": (
            "carbon.evaluation.policy",
            "PrecomputedReferenceSourceManifest",
        ),
        "reference_policy": ("carbon.evaluation.policy", "ReferencePolicy"),
        "reference_policy_entry": (
            "carbon.evaluation.policy",
            "ReferencePolicyEntry",
        ),
        "reference_composition": (
            "carbon.evaluation.policy",
            "ReferenceComposition",
        ),
        "primary_reference_request": (
            "carbon.evaluation.execution",
            "PrimaryReferenceRequest",
        ),
        "witness_reference_request": (
            "carbon.evaluation.execution",
            "WitnessReferenceRequest",
        ),
        "primary_run_grant": ("carbon.evaluation.execution", "PrimaryRunGrant"),
        "witness_run_grant": ("carbon.evaluation.execution", "WitnessRunGrant"),
        "reference_resolution_record": (
            "carbon.evaluation.execution",
            "ReferenceResolutionRecord",
        ),
        "reference_run_record": (
            "carbon.evaluation.execution",
            "ReferenceRunRecord",
        ),
        "reference_comparison_record": (
            "carbon.evaluation.comparison",
            "ReferenceComparisonRecord",
        ),
        "reference_artifact": ("carbon.evaluation.assets", "ReferenceArtifact"),
        "fixture_reference_asset": (
            "carbon.evaluation.assets",
            "FixtureReferenceAsset",
        ),
        "truth_asset_admission_grant_issuance_record": (
            "carbon.evaluation.admission",
            "TruthAssetAdmissionGrantIssuanceRecord",
        ),
        "truth_asset_admission_grant": (
            "carbon.evaluation.admission",
            "TruthAssetAdmissionGrant",
        ),
        "truth_asset_admission_decision_record": (
            "carbon.evaluation.admission",
            "TruthAssetAdmissionDecisionRecord",
        ),
        "truth_asset": ("carbon.evaluation.admission", "TruthAsset"),
    }
)


class _FieldCodec(NamedTuple):
    kind: str
    argument: object = None
    set_like: bool = False


_TEXT = _FieldCodec("text")
_BYTES = _FieldCodec("bytes")
_BOOL = _FieldCodec("bool")
_CHALLENGE_KEY = _FieldCodec("challenge_key")
_EMPTY = _FieldCodec("empty")


class _TaggedVariant(NamedTuple):
    discriminator: Enum
    payload_codec: _FieldCodec


class _TaggedUnionCodec(NamedTuple):
    exact_type: type
    discriminator_field: str
    variants: tuple[_TaggedVariant, ...]


def _enum(enum_type: type[Enum]) -> _FieldCodec:
    if not isinstance(enum_type, type) or not issubclass(enum_type, Enum):
        raise TypeError("enum_type must be one exact Enum class")
    return _FieldCodec("enum", enum_type)


def _registered_enum_member(value: object, enum_type: type[Enum]) -> bool:
    """Require identity in the closed family before reading member metadata."""

    return type(value) is enum_type and any(value is member for member in enum_type)


def _owner(expected_kind: str) -> _FieldCodec:
    if type(expected_kind) is not str or not expected_kind:
        raise TypeError("owner kind must be nonempty text")
    return _FieldCodec("owner_ref", expected_kind)


def _top(expected_type: type) -> _FieldCodec:
    return _FieldCodec("top_ref", expected_type)


def _b04_ref(expected_type: type) -> _FieldCodec:
    if expected_type not in REFERENCE_TRUTH_REF_TYPES:
        raise TypeError("expected_type must be one exact B-04 ref class")
    return _FieldCodec("b04_ref", expected_type)


def _nested(expected_type: type) -> _FieldCodec:
    return _FieldCodec("nested", expected_type)


def _authoring(expected_type: type) -> _FieldCodec:
    return _FieldCodec("authoring", expected_type)


def _tuple_of(item: _FieldCodec, *, set_like: bool = False) -> _FieldCodec:
    if type(item) is not _FieldCodec:
        raise TypeError("tuple item must be one exact field codec")
    return _FieldCodec("tuple", item, set_like)


def _optional(item: _FieldCodec) -> _FieldCodec:
    if type(item) is not _FieldCodec:
        raise TypeError("optional item must be one exact field codec")
    return _FieldCodec("optional", item)


def _union(*expected_types: type) -> _FieldCodec:
    if not expected_types or any(type(item) is not type for item in expected_types):
        raise TypeError("closed union requires exact classes")
    return _FieldCodec("union", expected_types)


def _tagged_union(
    exact_type: type,
    discriminator_field: str,
    *variants: tuple[Enum, _FieldCodec],
) -> _FieldCodec:
    if (
        type(exact_type) is not type
        or discriminator_field not in {"kind", "tag"}
        or not variants
        or any(
            type(item) is not tuple
            or len(item) != 2
            or not isinstance(item[0], Enum)
            or type(item[1]) is not _FieldCodec
            for item in variants
        )
    ):
        raise TypeError("tagged union registry is invalid")
    normalized = tuple(_TaggedVariant(*item) for item in variants)
    if len({item.discriminator.value for item in normalized}) != len(normalized):
        raise ValueError("tagged union variants must be unique")
    return _FieldCodec(
        "tagged_union",
        _TaggedUnionCodec(exact_type, discriminator_field, normalized),
    )


@dataclass(frozen=True, slots=True)
class _Schema:
    record_type: str
    exact_type: type
    fields: tuple[tuple[str, _FieldCodec], ...]
    top_level: bool
    union_tag: str | None = None
    builder: Callable[..., object] | None = None
    content_digest_bound: bool = False


@dataclass(slots=True)
class _SchemaRegistryBuilder:
    top_by_type: dict[type, _Schema]
    top_by_kind: dict[str, _Schema]
    nested_by_type: dict[type, _Schema]
    nested_by_tag: dict[str, _Schema]


@dataclass(frozen=True, slots=True)
class _SchemaRegistry:
    top_by_type: Mapping[type, _Schema]
    top_by_kind: Mapping[str, _Schema]
    nested_by_type: Mapping[type, _Schema]
    nested_by_tag: Mapping[str, _Schema]


_SCHEMA_REGISTRY_LOCK = Lock()
_SCHEMA_REGISTRY: _SchemaRegistry | None = None


def _new_registry_builder() -> _SchemaRegistryBuilder:
    return _SchemaRegistryBuilder({}, {}, {}, {})


def _freeze_registry(builder: _SchemaRegistryBuilder) -> _SchemaRegistry:
    if tuple(builder.top_by_kind) != REFERENCE_TRUTH_CANONICAL_OBJECT_KINDS:
        raise RuntimeError("B-04 canonical registry is incomplete or out of order")
    if len(builder.top_by_type) != len(builder.top_by_kind):
        raise RuntimeError("B-04 canonical registry is not one-to-one")
    return _SchemaRegistry(
        MappingProxyType(dict(builder.top_by_type)),
        MappingProxyType(dict(builder.top_by_kind)),
        MappingProxyType(dict(builder.nested_by_type)),
        MappingProxyType(dict(builder.nested_by_tag)),
    )


def _validate_fields(
    fields: object,
) -> tuple[tuple[str, _FieldCodec], ...]:
    if type(fields) is not tuple or any(
        type(item) is not tuple
        or len(item) != 2
        or type(item[0]) is not str
        or not item[0]
        or type(item[1]) is not _FieldCodec
        for item in fields
    ):
        raise TypeError("canonical fields must be exact name/codec tuples")
    names = tuple(name for name, _ in fields)
    if len(names) != len(set(names)):
        raise ValueError("canonical field names must be unique")
    return fields


def _register_top(
    registry: _SchemaRegistryBuilder,
    exact_type: type,
    object_kind: str,
    fields: tuple[tuple[str, _FieldCodec], ...],
    *,
    builder: Callable[..., object] | None = None,
    content_digest_bound: bool = False,
) -> None:
    if type(exact_type) is not type:
        raise TypeError("canonical type must be one exact class")
    if _CANONICAL_TYPE_OWNERS.get(object_kind) != (
        exact_type.__module__,
        exact_type.__name__,
    ):
        raise ValueError("type is outside the closed B-04 owner registry")
    if exact_type in registry.top_by_type or object_kind in registry.top_by_kind:
        raise ValueError("canonical type is already registered")
    if type(content_digest_bound) is not bool or (
        content_digest_bound and builder is None
    ):
        raise ValueError("content-bound reconstruction requires one exact builder")
    schema = _Schema(
        object_kind,
        exact_type,
        _validate_fields(fields),
        True,
        builder=builder,
        content_digest_bound=content_digest_bound,
    )
    registry.top_by_type[exact_type] = schema
    registry.top_by_kind[object_kind] = schema


def _register_nested(
    registry: _SchemaRegistryBuilder,
    exact_type: type,
    record_type: str,
    fields: tuple[tuple[str, _FieldCodec], ...],
    *,
    union_tag: str | None = None,
    builder: Callable[..., object] | None = None,
) -> None:
    if type(exact_type) is not type or type(record_type) is not str or not record_type:
        raise TypeError("nested canonical registration is invalid")
    if exact_type in registry.nested_by_type:
        raise ValueError("nested canonical type is already registered")
    if union_tag is not None and (
        type(union_tag) is not str
        or not union_tag
        or union_tag in registry.nested_by_tag
    ):
        raise ValueError("nested union tag is invalid or duplicated")
    schema = _Schema(
        record_type,
        exact_type,
        _validate_fields(fields),
        False,
        union_tag,
        builder,
    )
    registry.nested_by_type[exact_type] = schema
    if union_tag is not None:
        registry.nested_by_tag[union_tag] = schema


def _encoding_error(path: str = "") -> ReferenceCanonicalEncodingError:
    return ReferenceCanonicalEncodingError(path=path)


def _decoding_error(path: str = "") -> ReferenceCanonicalDecodingError:
    return ReferenceCanonicalDecodingError(path=path)


def _encode_authoring(value: object, expected_type: type) -> CanonicalValue:
    if type(value) is not expected_type:
        raise _encoding_error()
    from carbon.authoring.evidence import EvidenceRoleBinding
    from carbon.authoring.model import EvidenceRole

    if expected_type is EvidenceRoleBinding:
        try:
            role = object.__getattribute__(value, "role")
        except (AttributeError, TypeError):
            raise _encoding_error() from None
        if not _registered_enum_member(role, EvidenceRole):
            raise _encoding_error()
    from carbon.authoring.model import _canonical_value

    try:
        result = _canonical_value(value)
    except (AuthoringError, TypeError, ValueError):
        raise _encoding_error() from None
    return result


def _decode_authoring(value: object, expected_type: type) -> object:
    from carbon.authoring.model import _decode_canonical_value, _decode_union

    try:
        result = (
            _decode_union(value, expected_type)
            if type(value) is CanonicalUnion
            else _decode_canonical_value(value)
        )
    except (AuthoringError, TypeError, ValueError):
        raise _decoding_error() from None
    if type(result) is not expected_type:
        raise _decoding_error()
    return result


def _encode_field(value: object, codec: _FieldCodec) -> CanonicalValue:
    kind = codec.kind
    try:
        if kind == "text" and type(value) is str:
            return CanonicalText(value)
        if kind == "bytes" and type(value) is bytes:
            return CanonicalBytes(value)
        if kind == "bool" and type(value) is bool:
            return value
        if kind == "empty" and value is None:
            return CanonicalRecord("empty_payload", ())
        if kind == "challenge_key":
            return challenge_key_to_canonical(value)
        if kind == "enum" and _registered_enum_member(value, codec.argument):
            return CanonicalUnion(value.name, CanonicalRecord("empty_payload", ()))
        if kind == "owner_ref" and is_owner_ref(value):
            if value.ref_kind != codec.argument:
                raise _encoding_error()
            return owner_ref_to_canonical(value)
        if kind == "top_ref" and type(value) is codec.argument:
            return top_level_ref_to_canonical(value)
        if kind == "b04_ref" and type(value) is codec.argument:
            return reference_truth_ref_to_canonical(value)
        if kind == "nested" and type(value) is codec.argument:
            return _nested_to_canonical(value)
        if kind == "authoring":
            return _encode_authoring(value, codec.argument)
        if kind == "tuple" and type(value) is tuple:
            return CanonicalTuple(
                tuple(_encode_field(item, codec.argument) for item in value),
                set_like=codec.set_like,
            )
        if kind == "optional":
            if value is None:
                return CanonicalUnion("ABSENT", CanonicalRecord("empty_payload", ()))
            return CanonicalUnion("PRESENT", _encode_field(value, codec.argument))
        if kind == "union":
            if type(value) not in codec.argument:
                raise _encoding_error()
            schema = _ensure_schemas().nested_by_type[type(value)]
            return CanonicalUnion(
                schema.union_tag or schema.record_type.upper(),
                _schema_record(value, schema),
            )
        if kind == "tagged_union":
            descriptor = codec.argument
            if type(value) is not descriptor.exact_type:
                raise _encoding_error()
            discriminator = object.__getattribute__(
                value, descriptor.discriminator_field
            )
            variants = tuple(
                item
                for item in descriptor.variants
                if discriminator is item.discriminator
            )
            if len(variants) != 1:
                raise _encoding_error()
            return CanonicalUnion(
                variants[0].discriminator.value,
                _encode_field(
                    object.__getattribute__(value, "value"), variants[0].payload_codec
                ),
            )
    except (AuthoringError, ReferenceValidationError, TypeError, ValueError) as exc:
        if type(exc) is ReferenceCanonicalEncodingError:
            raise
    raise _encoding_error()


def _decode_field(value: object, codec: _FieldCodec) -> object:
    kind = codec.kind
    try:
        if kind == "text" and type(value) is CanonicalText:
            return value.value
        if kind == "bytes" and type(value) is CanonicalBytes:
            return value.value
        if kind == "bool" and type(value) is bool:
            return value
        if kind == "empty":
            if (
                type(value) is CanonicalRecord
                and value.record_type == "empty_payload"
                and not value.fields
            ):
                return None
            raise _decoding_error()
        if kind == "challenge_key":
            return challenge_key_from_canonical(value)
        if kind == "enum" and type(value) is CanonicalUnion:
            if (
                type(value.payload) is not CanonicalRecord
                or value.payload.record_type != "empty_payload"
                or value.payload.fields
            ):
                raise _decoding_error()
            return codec.argument[value.tag]
        if kind == "owner_ref":
            return owner_ref_from_canonical(value, expected_kind=codec.argument)
        if kind == "top_ref":
            result = top_level_ref_from_canonical(value)
            if type(result) is not codec.argument:
                raise _decoding_error()
            return result
        if kind == "b04_ref":
            return reference_truth_ref_from_canonical(
                value, expected_type=codec.argument
            )
        if kind == "nested":
            return _nested_from_canonical(value, codec.argument)
        if kind == "authoring":
            return _decode_authoring(value, codec.argument)
        if kind == "tuple" and type(value) is CanonicalTuple:
            if codec.set_like:
                encoded_items = tuple(encode_value(item) for item in value.items)
                if len(set(encoded_items)) != len(
                    encoded_items
                ) or encoded_items != tuple(sorted(encoded_items)):
                    raise _decoding_error()
            return tuple(_decode_field(item, codec.argument) for item in value.items)
        if kind == "optional" and type(value) is CanonicalUnion:
            if value.tag == "ABSENT":
                if (
                    type(value.payload) is not CanonicalRecord
                    or value.payload.record_type != "empty_payload"
                    or value.payload.fields
                ):
                    raise _decoding_error()
                return None
            if value.tag == "PRESENT":
                return _decode_field(value.payload, codec.argument)
            raise _decoding_error()
        if kind == "union" and type(value) is CanonicalUnion:
            registry = _ensure_schemas()
            candidates = tuple(
                candidate
                for candidate in codec.argument
                if (
                    registry.nested_by_type[candidate].union_tag
                    or registry.nested_by_type[candidate].record_type.upper()
                )
                == value.tag
            )
            if len(candidates) != 1:
                raise _decoding_error()
            return _nested_from_canonical(value.payload, candidates[0])
        if kind == "tagged_union" and type(value) is CanonicalUnion:
            descriptor = codec.argument
            variants = tuple(
                item
                for item in descriptor.variants
                if item.discriminator.value == value.tag
            )
            if len(variants) != 1:
                raise _decoding_error()
            payload = _decode_field(value.payload, variants[0].payload_codec)
            return descriptor.exact_type(variants[0].discriminator, payload)
    except (
        AuthoringError,
        KeyError,
        ReferenceValidationError,
        TypeError,
        ValueError,
    ) as exc:
        if type(exc) is ReferenceCanonicalDecodingError:
            raise
    raise _decoding_error()


def _schema_record(value: object, schema: _Schema) -> CanonicalRecord:
    if type(value) is not schema.exact_type:
        raise _encoding_error()
    fields: list[tuple[str, CanonicalValue]] = []
    if schema.top_level:
        fields.extend(
            (
                (
                    "canonicalization_profile",
                    CanonicalText(REFERENCE_TRUTH_CANONICALIZATION_PROFILE),
                ),
                ("object_kind", CanonicalText(schema.record_type)),
                ("schema_version", CanonicalText(REFERENCE_TRUTH_SCHEMA_VERSION)),
            )
        )
    fields.extend(
        (name, _encode_field(object.__getattribute__(value, name), codec))
        for name, codec in schema.fields
    )
    return CanonicalRecord(schema.record_type, tuple(fields))


def _decode_schema_record(
    value: object,
    schema: _Schema,
    *,
    canonical_content_digest: str | None = None,
) -> object:
    if type(value) is not CanonicalRecord or value.record_type != schema.record_type:
        raise _decoding_error()
    prefix = (
        ("canonicalization_profile", "object_kind", "schema_version")
        if schema.top_level
        else ()
    )
    expected_names = tuple(
        sorted(prefix + tuple(name for name, _ in schema.fields), key=str.encode)
    )
    if tuple(name for name, _ in value.fields) != expected_names:
        raise _decoding_error()
    fields = value.field_map()
    if schema.top_level:
        identity = tuple(fields[name] for name in prefix)
        if (
            type(identity[0]) is not CanonicalText
            or identity[0].value != REFERENCE_TRUTH_CANONICALIZATION_PROFILE
            or type(identity[1]) is not CanonicalText
            or identity[1].value != schema.record_type
            or type(identity[2]) is not CanonicalText
            or identity[2].value != REFERENCE_TRUTH_SCHEMA_VERSION
        ):
            raise _decoding_error()
    kwargs = {name: _decode_field(fields[name], codec) for name, codec in schema.fields}
    if schema.content_digest_bound:
        if type(canonical_content_digest) is not str:
            raise _decoding_error()
        kwargs["_canonical_content_digest"] = canonical_content_digest
    try:
        result = (
            schema.builder(**kwargs)
            if schema.builder is not None
            else schema.exact_type(**kwargs)
        )
    except (ReferenceValidationError, TypeError, ValueError):
        raise _decoding_error() from None
    if type(result) is not schema.exact_type:
        raise _decoding_error()
    return result


def _nested_to_canonical(value: object) -> CanonicalRecord:
    schema = _ensure_schemas().nested_by_type.get(type(value))
    if schema is None:
        raise _encoding_error()
    return _schema_record(value, schema)


def _nested_from_canonical(value: object, expected_type: type) -> object:
    schema = _ensure_schemas().nested_by_type.get(expected_type)
    if schema is None:
        raise _decoding_error()
    return _decode_schema_record(value, schema)


def _ensure_schemas() -> _SchemaRegistry:
    """Build once, then atomically publish one immutable literal registry."""

    global _SCHEMA_REGISTRY
    registry = _SCHEMA_REGISTRY
    if registry is not None:
        return registry
    with _SCHEMA_REGISTRY_LOCK:
        registry = _SCHEMA_REGISTRY
        if registry is None:
            registry = _freeze_registry(_register_exact_v1_schemas())
            _SCHEMA_REGISTRY = registry
    return registry


def canonical_record(value: object) -> CanonicalRecord:
    schema = _ensure_schemas().top_by_type.get(type(value))
    if schema is None:
        raise _encoding_error()
    return _schema_record(value, schema)


def canonical_bytes(value: object) -> bytes:
    _ensure_schemas()
    try:
        document = REFERENCE_TRUTH_DOCUMENT_HEADER + encode_value(
            canonical_record(value)
        )
    except (AuthoringError, ReferenceValidationError, TypeError, ValueError) as exc:
        if type(exc) is ReferenceCanonicalEncodingError:
            raise
        raise _encoding_error() from None
    if len(document) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _encoding_error()
    return document


def decode_canonical_bytes(payload: object, expected_type: type) -> object:
    registry = _ensure_schemas()
    if type(payload) is not bytes:
        raise _decoding_error("/canonical_bytes")
    if type(expected_type) is not type or expected_type not in registry.top_by_type:
        raise TypeError("expected_type must be one exact B-04 record class")
    if len(payload) > MAX_CANONICAL_DOCUMENT_BYTES or not payload.startswith(
        REFERENCE_TRUTH_DOCUMENT_HEADER
    ):
        raise _decoding_error("/canonical_bytes")
    decode_failed = False
    trailing = False
    try:
        value = decode_value(payload[len(REFERENCE_TRUTH_DOCUMENT_HEADER) :])
    except AuthoringError as exc:
        decode_failed = True
        trailing = "trailing" in exc.code
        value = None
    if decode_failed:
        raise ReferenceCanonicalDecodingError(
            trailing=trailing,
            path="/canonical_bytes",
        )
    result = _decode_schema_record(
        value,
        registry.top_by_type[expected_type],
        canonical_content_digest=tagged_sha256(payload),
    )
    if not hmac.compare_digest(canonical_bytes(result), payload):
        raise _decoding_error("/canonical_bytes")
    return result


def canonical_content_digest(value: object) -> str:
    try:
        return tagged_sha256(canonical_bytes(value))
    except (AuthoringError, ReferenceValidationError):
        raise _encoding_error() from None


def record_ref(value: object) -> ReferenceTruthRef:
    schema = _ensure_schemas().top_by_type.get(type(value))
    if schema is None:
        raise _encoding_error()
    candidates = tuple(
        ref_type
        for ref_type in REFERENCE_TRUTH_REF_TYPES
        if ref_type.RECORD_TYPE == schema.record_type
    )
    if len(candidates) != 1:
        raise ReferenceMismatchError(path="/ref_type")
    try:
        challenge = object.__getattribute__(value, "challenge_key")
    except (AttributeError, TypeError):
        raise ReferenceValidationError(
            ReferenceInputCode.WRONG_TYPE,
            path="/challenge_key",
        ) from None
    if type(challenge) is not ChallengeKey:
        raise ReferenceValidationError(
            ReferenceInputCode.WRONG_TYPE,
            path="/challenge_key",
        )
    return candidates[0](challenge, canonical_content_digest(value))


def canonical_ref(value: object) -> ReferenceTruthRef:
    """Return the one nominal ref registered for an exact B-04 record."""

    return record_ref(value)


def _record_ref(value: object, expected_ref_type: type) -> ReferenceTruthRef:
    """Compatibility seam for protected record methods with an exact ref pin."""

    if expected_ref_type not in REFERENCE_TRUTH_REF_TYPES:
        raise TypeError("expected_ref_type must be one exact B-04 ref class")
    result = record_ref(value)
    if type(result) is not expected_ref_type:
        raise ReferenceMismatchError(path="/ref_type")
    return result


def verify_canonical_ref(value: object, ref: object) -> None:
    try:
        checked = reconstruct_reference_truth_ref(ref)
    except (AuthoringError, ReferenceValidationError, TypeError, ValueError):
        raise ReferenceValidationError(
            ReferenceInputCode.WRONG_TYPE,
            path="/ref",
        ) from None
    expected = record_ref(value)
    if type(expected) is not type(checked):
        raise ReferenceMismatchError(path="/ref_type")
    if expected.challenge_key != checked.challenge_key:
        raise ReferenceValidationError(
            ReferenceInputCode.CROSS_CHALLENGE,
            path="/challenge_key",
        )
    if not hmac.compare_digest(expected.content_digest, checked.content_digest):
        raise ReferenceMismatchError(path="/content_digest")


def _register_exact_v1_schemas() -> _SchemaRegistryBuilder:
    """Register the literal D11 subordinate and standalone field table."""

    registry = _new_registry_builder()

    def register_top(
        exact_type: type,
        object_kind: str,
        fields: tuple[tuple[str, _FieldCodec], ...],
        *,
        builder: Callable[..., object] | None = None,
        content_digest_bound: bool = False,
    ) -> None:
        _register_top(
            registry,
            exact_type,
            object_kind,
            fields,
            builder=builder,
            content_digest_bound=content_digest_bound,
        )

    def register_nested(
        exact_type: type,
        record_type: str,
        fields: tuple[tuple[str, _FieldCodec], ...],
        *,
        union_tag: str | None = None,
        builder: Callable[..., object] | None = None,
    ) -> None:
        _register_nested(
            registry,
            exact_type,
            record_type,
            fields,
            union_tag=union_tag,
            builder=builder,
        )

    from carbon.authoring.evidence import EvidenceRoleBinding
    from carbon.authoring.refs import (
        CandidateOutputContractRef,
        CanonicalChallengeCaseRef,
        InstanceDistributionContractRef,
        PhysicalSystemSpecRef,
        SamplingPlanRef,
    )

    from .admission import (
        TruthAsset,
        TruthAssetAdmissionDecisionRecord,
        TruthAssetAdmissionGrant,
        TruthAssetAdmissionGrantIssuanceRecord,
        _new_admission_decision,
        _new_admission_grant,
        _new_issuance_record,
        _reconstruct_admitted_truth_asset,
    )
    from .assets import (
        FixtureReferenceAsset,
        ReferenceArtifact,
        _new_fixture_reference_asset,
        _new_reference_artifact,
    )
    from .comparison import ReferenceComparisonRecord
    from .enums import (
        AdmissionArtifactAbsenceReason,
        AdmissionGrantIssuanceOutcome,
        AdmissionGrantIssuanceReason,
        BoundOrAbsentTag,
        ConditioningStatus,
        DependencyCategory,
        DependencyRelation,
        OptionalBindingTag,
        QualificationAbsenceReason,
        ReferenceArtifactOrigin,
        ReferenceAuthorityFunction,
        ReferenceAuthorityTargetKind,
        ReferenceComparisonOutcome,
        ReferenceComparisonReason,
        ReferenceCompositionKind,
        ReferenceExecutionTargetKind,
        ReferenceFailureReason,
        ReferenceGrantBindingKind,
        ReferenceIdentityKind,
        ReferenceRequestBindingKind,
        ReferenceRunOutcome,
        ReferenceSourceClass,
        ReferenceWitnessTargetKind,
        ResolutionOutcome,
        ResolutionReason,
        SupportApplicabilityStatus,
        TruthAssetAdmissionOutcome,
        TruthAssetAdmissionReason,
        UncertaintyComponentKind,
        UncertaintyStatus,
    )
    from .execution import (
        PrimaryReferenceRequest,
        PrimaryRunGrant,
        ReferenceResolutionRecord,
        ReferenceRunRecord,
        WitnessReferenceRequest,
        WitnessRunGrant,
    )
    from .model import (
        AdmissionArtifactBinding,
        AdmissionAttemptBinding,
        ArtifactContentBinding,
        ConditioningAssessment,
        DependencyDisclosure,
        OptionalBinding,
        PinnedReferenceIdentity,
        QualificationBinding,
        RealizedComponentBinding,
        ReferenceAuthorityTarget,
        ReferenceAuthorityTargetBinding,
        ReferenceExecutionTarget,
        ReferenceGrantBinding,
        ReferenceProvenance,
        ReferenceRequestBinding,
        ReferenceScopeBinding,
        ReferenceWitnessTarget,
        RunArtifactBinding,
        SupportApplicabilityAssessment,
        UncertaintyRepresentation,
    )
    from .policy import (
        PrecomputedReferenceSourceManifest,
        ReferenceComposition,
        ReferencePolicy,
        ReferencePolicyEntry,
    )
    from .refs import (
        PrecomputedReferenceSourceManifestRef,
        PrimaryReferenceRequestRef,
        PrimaryRunGrantRef,
        ReferenceArtifactRef,
        ReferenceComparisonRecordRef,
        ReferenceCompositionRef,
        ReferencePolicyEntryRef,
        ReferencePolicyRef,
        ReferenceResolutionRecordRef,
        ReferenceRunRecordRef,
        TruthAssetAdmissionDecisionRecordRef,
        TruthAssetAdmissionGrantIssuanceRecordRef,
        TruthAssetAdmissionGrantRef,
        TruthAssetRef,
        WitnessReferenceRequestRef,
        WitnessRunGrantRef,
    )

    # Exact direct-union codecs.  The payload remains the D11 payload itself;
    # no wrapper record, null coercion, or inferred tag is introduced.
    authority_target = _tagged_union(
        ReferenceAuthorityTarget,
        "kind",
        (
            ReferenceAuthorityTargetKind.SINGLE_PRIMARY_ENTRY,
            _b04_ref(ReferencePolicyEntryRef),
        ),
        (
            ReferenceAuthorityTargetKind.QUALIFIED_PRIMARY_COMPOSITION,
            _b04_ref(ReferenceCompositionRef),
        ),
    )
    witness_target = _tagged_union(
        ReferenceWitnessTarget,
        "kind",
        (
            ReferenceWitnessTargetKind.SINGLE_WITNESS_ENTRY,
            _b04_ref(ReferencePolicyEntryRef),
        ),
        (
            ReferenceWitnessTargetKind.QUALIFIED_WITNESS_COMPOSITION,
            _b04_ref(ReferenceCompositionRef),
        ),
    )
    execution_target = _tagged_union(
        ReferenceExecutionTarget,
        "kind",
        (ReferenceExecutionTargetKind.PRIMARY, authority_target),
        (ReferenceExecutionTargetKind.WITNESS, witness_target),
    )
    request_binding = _tagged_union(
        ReferenceRequestBinding,
        "kind",
        (
            ReferenceRequestBindingKind.PRIMARY,
            _b04_ref(PrimaryReferenceRequestRef),
        ),
        (
            ReferenceRequestBindingKind.WITNESS,
            _b04_ref(WitnessReferenceRequestRef),
        ),
    )
    grant_binding = _tagged_union(
        ReferenceGrantBinding,
        "kind",
        (ReferenceGrantBindingKind.PRIMARY, _b04_ref(PrimaryRunGrantRef)),
        (ReferenceGrantBindingKind.WITNESS, _b04_ref(WitnessRunGrantRef)),
        (ReferenceGrantBindingKind.ABSENT, _enum(ResolutionReason)),
    )
    authority_target_binding = _tagged_union(
        ReferenceAuthorityTargetBinding,
        "tag",
        (BoundOrAbsentTag.BOUND, authority_target),
        (BoundOrAbsentTag.ABSENT, _enum(ResolutionReason)),
    )
    run_artifact_binding = _tagged_union(
        RunArtifactBinding,
        "tag",
        (BoundOrAbsentTag.BOUND, _nested(ArtifactContentBinding)),
        (BoundOrAbsentTag.ABSENT, _enum(ReferenceFailureReason)),
    )
    admission_artifact_binding = _tagged_union(
        AdmissionArtifactBinding,
        "tag",
        (BoundOrAbsentTag.BOUND, _b04_ref(ReferenceArtifactRef)),
        (BoundOrAbsentTag.ABSENT, _enum(AdmissionArtifactAbsenceReason)),
    )
    qualification_binding = _tagged_union(
        QualificationBinding,
        "tag",
        (BoundOrAbsentTag.BOUND, _owner("qualification_evidence_bundle")),
        (BoundOrAbsentTag.ABSENT, _enum(QualificationAbsenceReason)),
    )

    register_nested(
        PinnedReferenceIdentity,
        "pinned_reference_identity",
        (
            ("challenge_key", _CHALLENGE_KEY),
            ("content_digest", _TEXT),
            ("identity_id", _TEXT),
            ("identity_kind", _enum(ReferenceIdentityKind)),
            ("identity_version", _TEXT),
        ),
    )
    register_nested(
        ReferenceScopeBinding,
        "reference_scope_binding",
        (
            ("candidate_output_contract_ref", _top(CandidateOutputContractRef)),
            ("claim_scope_ref", _owner("claim_scope")),
            ("evidence_campaign_ref", _owner("evidence_campaign")),
            (
                "evidence_population_refs",
                _tuple_of(_top(InstanceDistributionContractRef)),
            ),
            ("physical_system_ref", _top(PhysicalSystemSpecRef)),
            ("proposal_population_ref", _top(InstanceDistributionContractRef)),
            (
                "reference_fidelity_allocation_ref",
                _owner("reference_fidelity_allocation"),
            ),
            ("sampling_plan_ref", _top(SamplingPlanRef)),
            ("target_population_ref", _top(InstanceDistributionContractRef)),
            ("truth_target_ref", _owner("intended_estimand_or_reporting")),
        ),
    )
    register_nested(
        ArtifactContentBinding,
        "artifact_content_binding",
        (
            ("artifact_content_digest", _TEXT),
            ("artifact_descriptor_ref", _nested(PinnedReferenceIdentity)),
            ("artifact_origin", _enum(ReferenceArtifactOrigin)),
        ),
    )
    register_nested(
        SupportApplicabilityAssessment,
        "support_applicability_assessment",
        (
            (
                "applicability_evidence_refs",
                _tuple_of(_owner("applicability_evidence"), set_like=True),
            ),
            ("limitations", _tuple_of(_owner("restriction"), set_like=True)),
            ("method_ref", _nested(PinnedReferenceIdentity)),
            ("status", _enum(SupportApplicabilityStatus)),
            ("support_boundary_ref", _owner("support_boundary")),
        ),
    )
    register_nested(
        ConditioningAssessment,
        "conditioning_assessment",
        (
            (
                "evidence_refs",
                _tuple_of(_owner("sensitivity_analysis"), set_like=True),
            ),
            ("limitations", _tuple_of(_owner("restriction"), set_like=True)),
            ("method_ref", _nested(PinnedReferenceIdentity)),
            ("status", _enum(ConditioningStatus)),
        ),
    )
    register_nested(
        UncertaintyRepresentation,
        "uncertainty_representation",
        (
            (
                "component_kinds",
                _tuple_of(_enum(UncertaintyComponentKind), set_like=True),
            ),
            ("coverage_ref", _owner("coverage_qualification")),
            ("dependence_policy_ref", _owner("replication_dependence_policy")),
            ("estimand_ref", _owner("estimand_scope")),
            ("evidence_refs", _tuple_of(_owner("audit_evidence"), set_like=True)),
            ("limitations", _tuple_of(_owner("restriction"), set_like=True)),
            ("method_ref", _nested(PinnedReferenceIdentity)),
            ("representation_ref", _nested(PinnedReferenceIdentity)),
            ("status", _enum(UncertaintyStatus)),
            ("units_ref", _nested(PinnedReferenceIdentity)),
            (
                "use_restrictions",
                _tuple_of(_owner("permitted_use"), set_like=True),
            ),
        ),
    )
    register_nested(
        DependencyDisclosure,
        "dependency_disclosure",
        (
            ("category", _enum(DependencyCategory)),
            ("evidence_refs", _tuple_of(_owner("provenance"), set_like=True)),
            ("relation", _enum(DependencyRelation)),
        ),
    )
    register_nested(
        ReferenceProvenance,
        "reference_provenance",
        (
            (
                "dependency_disclosures",
                _tuple_of(_nested(DependencyDisclosure)),
            ),
            ("environment_ref", _nested(PinnedReferenceIdentity)),
            ("evidence_campaign_ref", _owner("evidence_campaign")),
            (
                "generated_or_copied_code_refs",
                _tuple_of(_owner("provenance"), set_like=True),
            ),
            ("implementation_ref", _nested(PinnedReferenceIdentity)),
            ("method_ref", _nested(PinnedReferenceIdentity)),
            ("provenance_refs", _tuple_of(_owner("provenance"), set_like=True)),
            (
                "reviewer_authority_refs",
                _tuple_of(_owner("authority_evidence"), set_like=True),
            ),
            ("rights_profile_ref", _owner("rights_profile")),
            ("source_ref", _nested(PinnedReferenceIdentity)),
        ),
    )
    register_nested(
        RealizedComponentBinding,
        "realized_component_binding",
        (
            ("configuration_ref", _nested(PinnedReferenceIdentity)),
            ("entry_ref", _b04_ref(ReferencePolicyEntryRef)),
            ("environment_ref", _nested(PinnedReferenceIdentity)),
            ("hardware_ref", _nested(PinnedReferenceIdentity)),
            ("implementation_ref", _nested(PinnedReferenceIdentity)),
            ("method_ref", _nested(PinnedReferenceIdentity)),
            ("precision_ref", _nested(PinnedReferenceIdentity)),
        ),
    )
    register_nested(
        AdmissionAttemptBinding,
        "admission_attempt_binding",
        (
            ("admission_authority_ref", _nested(PinnedReferenceIdentity)),
            ("answer_key_authority_target", authority_target),
            ("artifact_binding", admission_artifact_binding),
            ("case_ref", _top(CanonicalChallengeCaseRef)),
            (
                "comparison_refs",
                _tuple_of(_b04_ref(ReferenceComparisonRecordRef)),
            ),
            ("decision_profile_ref", _nested(PinnedReferenceIdentity)),
            ("disclosure_policy_ref", _owner("disclosure_policy")),
            ("primary_execution_target", authority_target),
            ("provenance_policy_ref", _owner("provenance")),
            ("qualification_binding", qualification_binding),
            ("rights_profile_ref", _owner("rights_profile")),
            ("run_ref", _b04_ref(ReferenceRunRecordRef)),
            (
                "use_restrictions",
                _tuple_of(_owner("permitted_use"), set_like=True),
            ),
            ("witness_targets", _tuple_of(witness_target)),
        ),
    )

    optional_manifest = _tagged_union(
        OptionalBinding,
        "tag",
        (OptionalBindingTag.ABSENT, _EMPTY),
        (
            OptionalBindingTag.PRESENT,
            _b04_ref(PrecomputedReferenceSourceManifestRef),
        ),
    )
    optional_policy = _tagged_union(
        OptionalBinding,
        "tag",
        (OptionalBindingTag.ABSENT, _EMPTY),
        (OptionalBindingTag.PRESENT, _b04_ref(ReferencePolicyRef)),
    )
    optional_truth_asset = _tagged_union(
        OptionalBinding,
        "tag",
        (OptionalBindingTag.ABSENT, _EMPTY),
        (OptionalBindingTag.PRESENT, _b04_ref(TruthAssetRef)),
    )
    optional_revocation = _tagged_union(
        OptionalBinding,
        "tag",
        (OptionalBindingTag.ABSENT, _EMPTY),
        (OptionalBindingTag.PRESENT, _owner("authoring_revocation")),
    )
    optional_failure_reason = _tagged_union(
        OptionalBinding,
        "tag",
        (OptionalBindingTag.ABSENT, _EMPTY),
        (OptionalBindingTag.PRESENT, _enum(ReferenceFailureReason)),
    )

    register_top(
        PrecomputedReferenceSourceManifest,
        "precomputed_reference_source_manifest",
        (
            ("artifact_schema_ref", _nested(PinnedReferenceIdentity)),
            ("challenge_key", _CHALLENGE_KEY),
            ("manifest_id", _TEXT),
            ("manifest_version", _TEXT),
            ("provenance_binding", _nested(ReferenceProvenance)),
            ("representation_ref", _nested(PinnedReferenceIdentity)),
            ("rights_profile_ref", _owner("rights_profile")),
            ("scope_binding", _nested(ReferenceScopeBinding)),
            ("source_class", _enum(ReferenceSourceClass)),
            ("source_corpus_digest", _TEXT),
            ("source_ref", _nested(PinnedReferenceIdentity)),
            ("supersedes", optional_manifest),
        ),
    )
    register_top(
        ReferencePolicy,
        "reference_policy",
        (
            ("answer_key_authority_target", authority_target_binding),
            ("applicability_policy_ref", _owner("applicability")),
            ("challenge_key", _CHALLENGE_KEY),
            ("comparison_policy_ref", _owner("semantic_equivalence")),
            (
                "composition_refs",
                _tuple_of(_b04_ref(ReferenceCompositionRef)),
            ),
            ("disclosure_policy_ref", _owner("disclosure_policy")),
            ("entry_refs", _tuple_of(_b04_ref(ReferencePolicyEntryRef))),
            ("fallback_policy_ref", _owner("restriction")),
            ("history_binding_ref", _owner("authoring_registration")),
            ("policy_id", _TEXT),
            ("policy_version", _TEXT),
            ("provenance_policy_ref", _owner("provenance")),
            (
                "qualification_policy_ref",
                _owner("reference_qualification_policy"),
            ),
            ("registered_witness_targets", _tuple_of(witness_target)),
            ("resource_policy_ref", _owner("reference_resource_limit")),
            ("revocation_binding_ref", optional_revocation),
            ("rights_profile_ref", _owner("rights_profile")),
            ("scope_binding", _nested(ReferenceScopeBinding)),
            ("supersedes", optional_policy),
            ("uncertainty_policy_ref", _owner("statistics_objective")),
        ),
    )
    register_top(
        ReferencePolicyEntry,
        "reference_policy_entry",
        (
            ("applicability_policy_ref", _owner("applicability")),
            ("artifact_schema_ref", _nested(PinnedReferenceIdentity)),
            ("authority_function", _enum(ReferenceAuthorityFunction)),
            ("challenge_key", _CHALLENGE_KEY),
            ("conditioning_policy_ref", _owner("sensitivity_analysis")),
            ("correlation_policy_ref", _owner("replication_dependence_policy")),
            ("dependency_constraints_ref", _nested(PinnedReferenceIdentity)),
            ("disclosure_policy_ref", _owner("disclosure_policy")),
            ("entry_id", _TEXT),
            ("entry_version", _TEXT),
            ("environment_constraints_ref", _nested(PinnedReferenceIdentity)),
            ("evidence_role_binding", _authoring(EvidenceRoleBinding)),
            ("expected_representation_ref", _nested(PinnedReferenceIdentity)),
            (
                "implementation_constraints_ref",
                _nested(PinnedReferenceIdentity),
            ),
            ("method_constraints_ref", _nested(PinnedReferenceIdentity)),
            ("policy_id", _TEXT),
            ("policy_version", _TEXT),
            ("precomputed_source_manifest_ref", optional_manifest),
            ("provenance_policy_ref", _owner("provenance")),
            (
                "qualification_policy_ref",
                _owner("reference_qualification_policy"),
            ),
            ("resource_policy_ref", _owner("reference_resource_limit")),
            ("rights_profile_ref", _owner("rights_profile")),
            ("scope_binding", _nested(ReferenceScopeBinding)),
            ("source_class", _enum(ReferenceSourceClass)),
            ("source_ref", _nested(PinnedReferenceIdentity)),
            ("support_boundary_ref", _owner("support_boundary")),
            ("uncertainty_policy_ref", _owner("statistics_objective")),
        ),
    )
    register_top(
        ReferenceComposition,
        "reference_composition",
        (
            ("applicability_policy_ref", _owner("applicability")),
            ("artifact_schema_ref", _nested(PinnedReferenceIdentity)),
            ("authority_function", _enum(ReferenceAuthorityFunction)),
            ("challenge_key", _CHALLENGE_KEY),
            ("combination_environment_ref", _nested(PinnedReferenceIdentity)),
            (
                "combination_implementation_ref",
                _nested(PinnedReferenceIdentity),
            ),
            ("combination_method_ref", _nested(PinnedReferenceIdentity)),
            ("composition_id", _TEXT),
            ("composition_kind", _enum(ReferenceCompositionKind)),
            ("composition_version", _TEXT),
            ("conditioning_policy_ref", _owner("sensitivity_analysis")),
            ("correlation_policy_ref", _owner("replication_dependence_policy")),
            ("disclosure_policy_ref", _owner("disclosure_policy")),
            ("expected_representation_ref", _nested(PinnedReferenceIdentity)),
            (
                "member_entry_refs",
                _tuple_of(_b04_ref(ReferencePolicyEntryRef)),
            ),
            ("policy_id", _TEXT),
            ("policy_version", _TEXT),
            ("provenance_policy_ref", _owner("provenance")),
            (
                "qualification_policy_ref",
                _owner("reference_qualification_policy"),
            ),
            ("resource_policy_ref", _owner("reference_resource_limit")),
            ("rights_profile_ref", _owner("rights_profile")),
            ("scope_binding", _nested(ReferenceScopeBinding)),
            ("uncertainty_policy_ref", _owner("statistics_objective")),
        ),
    )

    request_common = (
        ("answer_key_authority_target", authority_target),
        ("case_ref", _top(CanonicalChallengeCaseRef)),
        ("challenge_key", _CHALLENGE_KEY),
        ("disclosure_policy_ref", _owner("disclosure_policy")),
    )
    request_tail = (
        ("idempotency_ref", _nested(PinnedReferenceIdentity)),
        ("policy_ref", _b04_ref(ReferencePolicyRef)),
        ("representation_ref", _nested(PinnedReferenceIdentity)),
        ("request_id", _TEXT),
        ("request_version", _TEXT),
        ("requested_resource_policy_ref", _owner("reference_resource_limit")),
        ("scope_binding", _nested(ReferenceScopeBinding)),
    )
    register_top(
        PrimaryReferenceRequest,
        "primary_reference_request",
        request_common + (("execution_target", authority_target),) + request_tail,
    )
    register_top(
        WitnessReferenceRequest,
        "witness_reference_request",
        request_common + (("execution_target", witness_target),) + request_tail,
    )

    grant_common = (
        ("answer_key_authority_target", authority_target),
        ("authority_function", _enum(ReferenceAuthorityFunction)),
        ("capability_ref", _nested(PinnedReferenceIdentity)),
        ("case_ref", _top(CanonicalChallengeCaseRef)),
        ("challenge_key", _CHALLENGE_KEY),
        (
            "component_entry_refs",
            _tuple_of(_b04_ref(ReferencePolicyEntryRef)),
        ),
        ("configuration_ref", _nested(PinnedReferenceIdentity)),
        ("disclosure_policy_ref", _owner("disclosure_policy")),
        ("environment_ref", _nested(PinnedReferenceIdentity)),
        ("evidence_role_binding", _authoring(EvidenceRoleBinding)),
    )
    grant_tail = (
        ("grant_id", _TEXT),
        ("grant_version", _TEXT),
        ("hardware_ref", _nested(PinnedReferenceIdentity)),
        ("implementation_ref", _nested(PinnedReferenceIdentity)),
        ("issuance_token", _TEXT),
        ("issuer_ref", _nested(PinnedReferenceIdentity)),
        ("method_ref", _nested(PinnedReferenceIdentity)),
        ("policy_ref", _b04_ref(ReferencePolicyRef)),
        ("precision_ref", _nested(PinnedReferenceIdentity)),
        ("representation_ref", _nested(PinnedReferenceIdentity)),
    )
    grant_final = (
        ("resource_authorization_ref", _nested(PinnedReferenceIdentity)),
        ("scope_binding", _nested(ReferenceScopeBinding)),
        ("source_class", _enum(ReferenceSourceClass)),
    )
    register_top(
        PrimaryRunGrant,
        "primary_run_grant",
        grant_common
        + (("execution_target", authority_target),)
        + grant_tail
        + (("request_ref", _b04_ref(PrimaryReferenceRequestRef)),)
        + grant_final,
    )
    register_top(
        WitnessRunGrant,
        "witness_run_grant",
        grant_common
        + (("execution_target", witness_target),)
        + grant_tail
        + (("request_ref", _b04_ref(WitnessReferenceRequestRef)),)
        + grant_final,
    )
    register_top(
        ReferenceResolutionRecord,
        "reference_resolution_record",
        (
            ("answer_key_authority_target", authority_target),
            ("applicability_assessment", _nested(SupportApplicabilityAssessment)),
            ("authority_function", _enum(ReferenceAuthorityFunction)),
            ("case_ref", _top(CanonicalChallengeCaseRef)),
            ("challenge_key", _CHALLENGE_KEY),
            ("evidence_role_binding", _authoring(EvidenceRoleBinding)),
            ("execution_target", execution_target),
            ("grant_binding", grant_binding),
            ("outcome", _enum(ResolutionOutcome)),
            ("policy_ref", _b04_ref(ReferencePolicyRef)),
            ("qualification_binding", qualification_binding),
            ("reason", _enum(ResolutionReason)),
            ("request_binding", request_binding),
            ("resolution_id", _TEXT),
            ("resolution_version", _TEXT),
            ("resolver_ref", _nested(PinnedReferenceIdentity)),
            ("resource_policy_ref", _owner("reference_resource_limit")),
            ("scope_binding", _nested(ReferenceScopeBinding)),
            ("source_class", _enum(ReferenceSourceClass)),
        ),
    )
    register_top(
        ReferenceRunRecord,
        "reference_run_record",
        (
            ("answer_key_authority_target", authority_target),
            ("applicability_assessment", _nested(SupportApplicabilityAssessment)),
            ("artifact_binding", run_artifact_binding),
            ("authority_function", _enum(ReferenceAuthorityFunction)),
            ("case_ref", _top(CanonicalChallengeCaseRef)),
            ("challenge_key", _CHALLENGE_KEY),
            ("component_bindings", _tuple_of(_nested(RealizedComponentBinding))),
            ("conditioning_assessment", _nested(ConditioningAssessment)),
            ("configuration_ref", _nested(PinnedReferenceIdentity)),
            ("diagnostics_ref", _nested(PinnedReferenceIdentity)),
            ("environment_ref", _nested(PinnedReferenceIdentity)),
            ("evidence_role_binding", _authoring(EvidenceRoleBinding)),
            ("execution_target", execution_target),
            ("grant_binding", grant_binding),
            ("hardware_ref", _nested(PinnedReferenceIdentity)),
            ("implementation_ref", _nested(PinnedReferenceIdentity)),
            ("method_ref", _nested(PinnedReferenceIdentity)),
            ("outcome", _enum(ReferenceRunOutcome)),
            ("policy_ref", _b04_ref(ReferencePolicyRef)),
            ("precision_ref", _nested(PinnedReferenceIdentity)),
            ("provenance_binding", _nested(ReferenceProvenance)),
            ("reason", optional_failure_reason),
            ("representation_ref", _nested(PinnedReferenceIdentity)),
            ("request_binding", request_binding),
            ("resolution_ref", _b04_ref(ReferenceResolutionRecordRef)),
            ("resource_receipt_ref", _nested(PinnedReferenceIdentity)),
            ("run_id", _TEXT),
            ("run_version", _TEXT),
            ("scope_binding", _nested(ReferenceScopeBinding)),
            ("source_class", _enum(ReferenceSourceClass)),
            ("uncertainty_binding", _nested(UncertaintyRepresentation)),
        ),
    )
    register_top(
        ReferenceComparisonRecord,
        "reference_comparison_record",
        (
            ("answer_key_authority_target", authority_target),
            (
                "applicability_evidence_refs",
                _tuple_of(_owner("applicability_evidence"), set_like=True),
            ),
            ("case_ref", _top(CanonicalChallengeCaseRef)),
            ("challenge_key", _CHALLENGE_KEY),
            ("comparison_id", _TEXT),
            ("comparison_method_ref", _nested(PinnedReferenceIdentity)),
            ("comparison_policy_ref", _owner("semantic_equivalence")),
            ("comparison_version", _TEXT),
            (
                "dependency_disclosures",
                _tuple_of(_nested(DependencyDisclosure)),
            ),
            ("evidence_refs", _tuple_of(_owner("audit_evidence"), set_like=True)),
            ("outcome", _enum(ReferenceComparisonOutcome)),
            ("policy_ref", _b04_ref(ReferencePolicyRef)),
            (
                "primary_entry_refs",
                _tuple_of(_b04_ref(ReferencePolicyEntryRef)),
            ),
            ("primary_run_ref", _b04_ref(ReferenceRunRecordRef)),
            ("reason", _enum(ReferenceComparisonReason)),
            ("representation_ref", _nested(PinnedReferenceIdentity)),
            ("scope_binding", _nested(ReferenceScopeBinding)),
            ("uncertainty_treatment_ref", _nested(PinnedReferenceIdentity)),
            (
                "witness_entry_refs",
                _tuple_of(_b04_ref(ReferencePolicyEntryRef)),
            ),
            ("witness_run_ref", _b04_ref(ReferenceRunRecordRef)),
            ("witness_target", witness_target),
        ),
    )

    # Asset and positive-admission schemas are last in monotonic graph order.
    register_top(
        ReferenceArtifact,
        "reference_artifact",
        (
            ("applicability_assessment", _nested(SupportApplicabilityAssessment)),
            ("artifact_content_digest", _TEXT),
            ("artifact_descriptor_ref", _nested(PinnedReferenceIdentity)),
            ("artifact_id", _TEXT),
            ("artifact_origin", _enum(ReferenceArtifactOrigin)),
            ("artifact_version", _TEXT),
            ("case_ref", _top(CanonicalChallengeCaseRef)),
            ("challenge_key", _CHALLENGE_KEY),
            ("conditioning_assessment", _nested(ConditioningAssessment)),
            ("configuration_ref", _nested(PinnedReferenceIdentity)),
            ("environment_ref", _nested(PinnedReferenceIdentity)),
            ("execution_target", execution_target),
            ("hardware_ref", _nested(PinnedReferenceIdentity)),
            ("implementation_ref", _nested(PinnedReferenceIdentity)),
            ("method_ref", _nested(PinnedReferenceIdentity)),
            ("policy_ref", _b04_ref(ReferencePolicyRef)),
            ("precision_ref", _nested(PinnedReferenceIdentity)),
            ("provenance_binding", _nested(ReferenceProvenance)),
            ("representation_ref", _nested(PinnedReferenceIdentity)),
            ("run_ref", _b04_ref(ReferenceRunRecordRef)),
            ("scope_binding", _nested(ReferenceScopeBinding)),
            ("uncertainty_binding", _nested(UncertaintyRepresentation)),
        ),
        builder=_new_reference_artifact,
    )
    register_top(
        FixtureReferenceAsset,
        "fixture_reference_asset",
        (
            ("artifact_ref", _b04_ref(ReferenceArtifactRef)),
            ("case_ref", _top(CanonicalChallengeCaseRef)),
            ("challenge_key", _CHALLENGE_KEY),
            ("fixture_asset_id", _TEXT),
            ("fixture_asset_version", _TEXT),
            ("fixture_provenance_ref", _owner("fixture_registration")),
            ("live_eligible", _BOOL),
            ("payload_bytes", _BYTES),
            ("policy_ref", _b04_ref(ReferencePolicyRef)),
            ("run_ref", _b04_ref(ReferenceRunRecordRef)),
            ("scientific_qualification_eligible", _BOOL),
        ),
        builder=_new_fixture_reference_asset,
    )
    register_top(
        TruthAssetAdmissionGrantIssuanceRecord,
        "truth_asset_admission_grant_issuance_record",
        (
            ("attempt_binding", _nested(AdmissionAttemptBinding)),
            ("challenge_key", _CHALLENGE_KEY),
            ("issuance_id", _TEXT),
            ("issuance_token", _TEXT),
            ("issuance_version", _TEXT),
            ("issuer_ref", _nested(PinnedReferenceIdentity)),
            ("outcome", _enum(AdmissionGrantIssuanceOutcome)),
            ("reason", _enum(AdmissionGrantIssuanceReason)),
        ),
        builder=_new_issuance_record,
    )
    register_top(
        TruthAssetAdmissionGrant,
        "truth_asset_admission_grant",
        (
            ("attempt_binding", _nested(AdmissionAttemptBinding)),
            ("capability_ref", _nested(PinnedReferenceIdentity)),
            ("challenge_key", _CHALLENGE_KEY),
            ("grant_id", _TEXT),
            ("grant_version", _TEXT),
            (
                "issuance_record_ref",
                _b04_ref(TruthAssetAdmissionGrantIssuanceRecordRef),
            ),
            ("issuance_token", _TEXT),
            ("issuer_ref", _nested(PinnedReferenceIdentity)),
        ),
        builder=_new_admission_grant,
    )
    register_top(
        TruthAssetAdmissionDecisionRecord,
        "truth_asset_admission_decision_record",
        (
            ("admission_authority_ref", _nested(PinnedReferenceIdentity)),
            ("attempt_binding", _nested(AdmissionAttemptBinding)),
            ("challenge_key", _CHALLENGE_KEY),
            ("consumed_grant_receipt_ref", _nested(PinnedReferenceIdentity)),
            ("decision_id", _TEXT),
            ("decision_version", _TEXT),
            ("grant_ref", _b04_ref(TruthAssetAdmissionGrantRef)),
            (
                "issuance_record_ref",
                _b04_ref(TruthAssetAdmissionGrantIssuanceRecordRef),
            ),
            ("outcome", _enum(TruthAssetAdmissionOutcome)),
            ("reason", _enum(TruthAssetAdmissionReason)),
        ),
        builder=_new_admission_decision,
    )
    register_top(
        TruthAsset,
        "truth_asset",
        (
            (
                "admission_decision_ref",
                _b04_ref(TruthAssetAdmissionDecisionRecordRef),
            ),
            ("admission_grant_ref", _b04_ref(TruthAssetAdmissionGrantRef)),
            (
                "admission_issuance_record_ref",
                _b04_ref(TruthAssetAdmissionGrantIssuanceRecordRef),
            ),
            ("applicability_assessment", _nested(SupportApplicabilityAssessment)),
            ("artifact_ref", _b04_ref(ReferenceArtifactRef)),
            ("authority_function", _enum(ReferenceAuthorityFunction)),
            ("case_ref", _top(CanonicalChallengeCaseRef)),
            ("challenge_key", _CHALLENGE_KEY),
            (
                "comparison_refs",
                _tuple_of(_b04_ref(ReferenceComparisonRecordRef)),
            ),
            ("conditioning_assessment", _nested(ConditioningAssessment)),
            ("configuration_ref", _nested(PinnedReferenceIdentity)),
            (
                "dependency_disclosures",
                _tuple_of(_nested(DependencyDisclosure)),
            ),
            ("disclosure_policy_ref", _owner("disclosure_policy")),
            ("environment_ref", _nested(PinnedReferenceIdentity)),
            ("evidence_role_binding", _authoring(EvidenceRoleBinding)),
            ("execution_target", authority_target),
            ("hardware_ref", _nested(PinnedReferenceIdentity)),
            ("implementation_ref", _nested(PinnedReferenceIdentity)),
            ("known_limitations", _tuple_of(_owner("restriction"), set_like=True)),
            ("method_ref", _nested(PinnedReferenceIdentity)),
            ("policy_ref", _b04_ref(ReferencePolicyRef)),
            ("precision_ref", _nested(PinnedReferenceIdentity)),
            ("provenance_binding", _nested(ReferenceProvenance)),
            (
                "qualification_evidence_ref",
                _owner("qualification_evidence_bundle"),
            ),
            ("representation_ref", _nested(PinnedReferenceIdentity)),
            ("rights_profile_ref", _owner("rights_profile")),
            ("run_ref", _b04_ref(ReferenceRunRecordRef)),
            ("scope_binding", _nested(ReferenceScopeBinding)),
            ("source_class", _enum(ReferenceSourceClass)),
            ("supersedes", optional_truth_asset),
            ("truth_asset_id", _TEXT),
            ("truth_asset_version", _TEXT),
            ("uncertainty_binding", _nested(UncertaintyRepresentation)),
            (
                "use_restrictions",
                _tuple_of(_owner("permitted_use"), set_like=True),
            ),
        ),
        builder=_reconstruct_admitted_truth_asset,
        content_digest_bound=True,
    )
    return registry


__all__ = [
    "REFERENCE_TRUTH_CANONICAL_OBJECT_KINDS",
    "canonical_bytes",
    "canonical_content_digest",
    "canonical_record",
    "canonical_ref",
    "decode_canonical_bytes",
    "record_ref",
    "verify_canonical_ref",
]
