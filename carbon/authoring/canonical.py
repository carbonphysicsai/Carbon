"""Closed, schema-local canonical bytes for B-02A authored identities."""

from __future__ import annotations

import hashlib
import hmac
import math
import re
import struct
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias

from carbon.authoring.errors import (
    AuthoringValidationError,
    CanonicalDecodingError,
    CanonicalEncodingError,
    ReferenceMismatchError,
)
from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
    DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
    MAX_CANONICAL_DOCUMENT_BYTES,
    MAX_CANONICAL_NESTING_DEPTH,
    MAX_CANONICAL_PAYLOAD_BYTES,
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_exact_bytes,
    validate_finite_float64,
    validate_int64,
    validate_uint64,
    validate_utf8_text,
    validate_version_token,
)
from carbon.authoring.refs import (
    OBJECT_KINDS,
    TOP_LEVEL_REF_TYPES,
    CanonicalChallengeCaseRef,
    ChallengeScope,
    GlobalScope,
    InstanceDistributionContractRef,
    TopLevelObjectRef,
    is_owner_ref,
    is_top_level_ref,
    owner_ref_type,
    reconstruct_top_level_ref,
)
from carbon.registry import ChallengeKey

_DOCUMENT_HEADER = b"carbon.scientific-authoring.canonical.v1\x00"
_DERIVED_HEADER = b"carbon.scientific-authoring.derived-evidence.v1\x00"
_UNION_TAG = re.compile(r"[A-Z][A-Z0-9_]*\Z", re.ASCII)

_TAG_NULL = 0x00
_TAG_FALSE = 0x01
_TAG_TRUE = 0x02
_TAG_INT64 = 0x03
_TAG_UINT64 = 0x04
_TAG_FLOAT64 = 0x05
_TAG_TEXT = 0x06
_TAG_BYTES = 0x07
_TAG_TUPLE = 0x08
_TAG_RECORD = 0x09
_TAG_UNION = 0x0A
_TAG_REF = 0x0B

DERIVED_DOCUMENT_RECORD_TYPES_V1 = (
    "canonical_case_disposition",
    "censoring_record",
    "realized_valid_evidence_record",
)

# Explicit schema hooks for v1 auxiliary/derived records.  This registry is
# deliberately literal: domain adapters consume it without dataclass
# reflection, annotation discovery, or field-name inference.
DERIVED_RECORD_FIELD_REGISTRY_V1 = MappingProxyType(
    {
        "protected_case_identity_projection": (
            "audit_evidence_refs",
            "case_ref",
            "intended_slot_ref",
            "issuance_ref",
            "payload_ref",
            "realized_stratum_binding",
            "replacement_linkage",
            "schema_version",
        ),
        "internal_case_identity_projection": (
            "case_ref",
            "evidence_campaign_binding",
            "issuance_ref",
            "primary_population_ref",
            "sampling_plan_binding",
            "schema_version",
            "service_scope_ref",
        ),
        "public_case_identity_projection": (
            "challenge_key",
            "disclosure_policy_ref",
            "issuance_ref",
            "opaque_public_handle",
            "public_fact_bindings",
            "schema_version",
        ),
        "case_evidence_binding": (
            "applicability_refs",
            "authoritative_case_ref",
            "claim_scope_ref",
            "disclosure_contract",
            "downstream_use_restrictions",
            "evidence_artifact_ref",
            "evidence_campaign_ref",
            "evidence_role",
            "policy_qualification_binding",
            "provenance_refs",
            "public_projection_binding",
            "query_observation_provenance",
            "role_population_ref",
        ),
        "replacement_decision": (
            "accounting_evidence_ref",
            "decision",
            "lineage_binding",
            "policy_binding",
            "sampling_plan_ref",
            "trigger_binding",
        ),
        "canonical_case_disposition": (
            "actor_policy_authority_ref",
            "attempt_commitment_binding",
            "audit_evidence_refs",
            "canonicalization_profile",
            "case_ref_binding",
            "case_state",
            "disclosure_contract",
            "downstream_use_restrictions",
            "evidence_scope",
            "intended_evidence_unit_ref",
            "primary_population_ref",
            "replacement_decision",
            "sampling_plan_ref",
            "schema_version",
            "state_payload",
        ),
        "censoring_record": (
            "accounting_binding",
            "actor_authority_ref",
            "audit_evidence_refs",
            "canonicalization_profile",
            "censoring_reason",
            "downstream_use_restrictions",
            "evidence_campaign_binding",
            "evidence_scope",
            "intended_evidence_unit_ref",
            "missingness_adjustment_binding",
            "population_ref",
            "query_observation_provenance",
            "replacement_decision",
            "sampling_plan_ref",
            "schema_version",
            "trigger_failure_binding",
        ),
        "realized_valid_evidence_record": (
            "accounting_evidence_ref",
            "canonicalization_profile",
            "censoring_policy_ref",
            "challenge_key",
            "complete_unit_manifest_ref",
            "construction_audit_refs",
            "construction_authority_ref",
            "denominator_policy_ref",
            "disclosure_contract",
            "disposition_refs",
            "distribution_conformance_evidence_ref",
            "downstream_use_restrictions",
            "evidence_scope",
            "evidence_weight_binding",
            "intended_estimand_or_reporting_ref",
            "missingness_adjustment_binding",
            "official_proposal_binding",
            "primary_population_ref",
            "sampling_plan_ref",
            "schema_version",
            "selection_population_ref",
            "sensitivity_analysis_binding",
            "target_population_binding",
        ),
    }
)


def _encoding_error(code: str, message: str) -> CanonicalEncodingError:
    return CanonicalEncodingError(code, message)


def _decoding_error(code: str, message: str) -> CanonicalDecodingError:
    return CanonicalDecodingError(code, message)


@dataclass(frozen=True, slots=True)
class CanonicalInt64:
    value: int

    def __post_init__(self) -> None:
        if type(self) is not CanonicalInt64:
            raise _encoding_error(
                "authoring.canonical_subclass_rejected",
                "canonical Int64 must have its exact nominal type",
            )
        object.__setattr__(self, "value", validate_int64(self.value))


@dataclass(frozen=True, slots=True)
class CanonicalUInt64:
    value: int

    def __post_init__(self) -> None:
        if type(self) is not CanonicalUInt64:
            raise _encoding_error(
                "authoring.canonical_subclass_rejected",
                "canonical UInt64 must have its exact nominal type",
            )
        object.__setattr__(self, "value", validate_uint64(self.value))


@dataclass(frozen=True, slots=True)
class CanonicalFloat64:
    value: float

    def __post_init__(self) -> None:
        if type(self) is not CanonicalFloat64:
            raise _encoding_error(
                "authoring.canonical_subclass_rejected",
                "canonical Float64 must have its exact nominal type",
            )
        object.__setattr__(self, "value", validate_finite_float64(self.value))


@dataclass(frozen=True, slots=True)
class CanonicalText:
    value: str

    def __post_init__(self) -> None:
        if type(self) is not CanonicalText:
            raise _encoding_error(
                "authoring.canonical_subclass_rejected",
                "canonical TEXT must have its exact nominal type",
            )
        object.__setattr__(self, "value", validate_utf8_text(self.value))


@dataclass(frozen=True, slots=True)
class CanonicalBytes:
    value: bytes

    def __post_init__(self) -> None:
        if type(self) is not CanonicalBytes:
            raise _encoding_error(
                "authoring.canonical_subclass_rejected",
                "canonical BYTES must have its exact nominal type",
            )
        object.__setattr__(self, "value", validate_exact_bytes(self.value))


def _is_value(value: object) -> bool:
    return type(value) in {
        bool,
        CanonicalInt64,
        CanonicalUInt64,
        CanonicalFloat64,
        CanonicalText,
        CanonicalBytes,
        CanonicalTuple,
        CanonicalRecord,
        CanonicalUnion,
        CanonicalNominalRef,
    }


@dataclass(frozen=True, slots=True)
class CanonicalTuple:
    items: tuple[object, ...]
    set_like: bool = False

    def __post_init__(self) -> None:
        if type(self) is not CanonicalTuple:
            raise _encoding_error(
                "authoring.canonical_subclass_rejected",
                "canonical tuple must have its exact nominal type",
            )
        if type(self.items) is not tuple:
            raise _encoding_error(
                "authoring.canonical_tuple_type_invalid",
                "canonical tuple items must be an exact built-in tuple",
            )
        if type(self.set_like) is not bool:
            raise _encoding_error(
                "authoring.canonical_tuple_mode_invalid",
                "canonical tuple set_like must be an exact Boolean",
            )
        if len(self.items) > MAX_CANONICAL_TUPLE_ITEMS:
            raise _encoding_error(
                "authoring.canonical_tuple_too_large",
                "canonical tuple exceeds the v1 item bound",
            )
        if any(not _is_value(item) for item in self.items):
            raise _encoding_error(
                "authoring.canonical_value_unknown",
                "canonical tuple contains a value outside the closed vocabulary",
            )
        owned = tuple(self.items)
        if self.set_like:
            encoded = tuple((_encode_value(item, 1), item) for item in owned)
            if len({payload for payload, _ in encoded}) != len(encoded):
                raise _encoding_error(
                    "authoring.canonical_set_duplicate",
                    "set-like canonical tuple contains duplicate semantic members",
                )
            owned = tuple(item for _, item in sorted(encoded, key=lambda pair: pair[0]))
        object.__setattr__(self, "items", owned)


@dataclass(frozen=True, slots=True)
class CanonicalRecord:
    record_type: str
    fields: tuple[tuple[str, object], ...]

    def __post_init__(self) -> None:
        if type(self) is not CanonicalRecord:
            raise _encoding_error(
                "authoring.canonical_subclass_rejected",
                "canonical record must have its exact nominal type",
            )
        try:
            record_type = validate_canonical_id(self.record_type, "record_type")
        except AuthoringValidationError as exc:
            raise _encoding_error(
                "authoring.canonical_record_type_invalid",
                "canonical record type is not a closed ASCII schema literal",
            ) from exc
        if type(self.fields) is not tuple:
            raise _encoding_error(
                "authoring.canonical_fields_type_invalid",
                "canonical record fields must be an exact built-in tuple",
            )
        if len(self.fields) > MAX_CANONICAL_TUPLE_ITEMS:
            raise _encoding_error(
                "authoring.canonical_fields_too_large",
                "canonical record exceeds the v1 field-count bound",
            )
        owned: list[tuple[str, object]] = []
        for field in self.fields:
            if type(field) is not tuple or len(field) != 2:
                raise _encoding_error(
                    "authoring.canonical_field_invalid",
                    "every canonical field must be an exact name/value pair",
                )
            name, value = field
            try:
                canonical_name = validate_canonical_id(name, "field_name")
            except AuthoringValidationError as exc:
                raise _encoding_error(
                    "authoring.canonical_field_name_invalid",
                    "canonical field name is not a closed ASCII schema literal",
                ) from exc
            if not _is_value(value):
                raise _encoding_error(
                    "authoring.canonical_value_unknown",
                    "canonical field contains a value outside the closed vocabulary",
                )
            owned.append((canonical_name, value))
        names = [name for name, _ in owned]
        if len(set(names)) != len(names):
            raise _encoding_error(
                "authoring.canonical_field_duplicate",
                "canonical record contains a duplicate field name",
            )
        if record_type == "empty_payload" and owned:
            raise _encoding_error(
                "authoring.canonical_empty_payload_invalid",
                "empty_payload is the exact zero-field record",
            )
        owned.sort(key=lambda pair: pair[0].encode("utf-8"))
        object.__setattr__(self, "record_type", record_type)
        object.__setattr__(self, "fields", tuple(owned))

    def field_map(self) -> MappingProxyType[str, object]:
        """Return an immutable convenience view; canonical order stays in fields."""
        return MappingProxyType(dict(self.fields))


@dataclass(frozen=True, slots=True)
class CanonicalUnion:
    tag: str
    payload: object

    def __post_init__(self) -> None:
        if type(self) is not CanonicalUnion:
            raise _encoding_error(
                "authoring.canonical_subclass_rejected",
                "canonical union must have its exact nominal type",
            )
        if type(self.tag) is not str or _UNION_TAG.fullmatch(self.tag) is None:
            raise _encoding_error(
                "authoring.canonical_union_tag_invalid",
                "canonical union tag is not a closed uppercase ASCII literal",
            )
        if not _is_value(self.payload):
            raise _encoding_error(
                "authoring.canonical_union_payload_invalid",
                "canonical union payload is outside the closed vocabulary",
            )


@dataclass(frozen=True, slots=True)
class CanonicalNominalRef:
    ref_type: str
    record: CanonicalRecord

    def __post_init__(self) -> None:
        if type(self) is not CanonicalNominalRef:
            raise _encoding_error(
                "authoring.canonical_subclass_rejected",
                "canonical nominal ref must have its exact nominal type",
            )
        try:
            ref_type = validate_canonical_id(self.ref_type, "ref_type")
        except AuthoringValidationError as exc:
            raise _encoding_error(
                "authoring.canonical_ref_type_invalid",
                "canonical ref type is not a closed ASCII schema literal",
            ) from exc
        if type(self.record) is not CanonicalRecord:
            raise _encoding_error(
                "authoring.canonical_ref_record_invalid",
                "canonical nominal ref requires an exact canonical record",
            )
        object.__setattr__(self, "ref_type", ref_type)


CanonicalValue: TypeAlias = (
    bool
    | CanonicalInt64
    | CanonicalUInt64
    | CanonicalFloat64
    | CanonicalText
    | CanonicalBytes
    | CanonicalTuple
    | CanonicalRecord
    | CanonicalUnion
    | CanonicalNominalRef
)


@dataclass(frozen=True, slots=True)
class DecodedCanonicalDocument:
    object_kind: str
    schema_version: str
    record: CanonicalRecord

    def __post_init__(self) -> None:
        if type(self) is not DecodedCanonicalDocument:
            raise _decoding_error(
                "authoring.decoded_document_subclass_rejected",
                "decoded document must have its exact nominal type",
            )


@dataclass(frozen=True, slots=True)
class DecodedDerivedDocument:
    record_type: str
    schema_version: str
    canonicalization_profile: str
    record: CanonicalRecord

    def __post_init__(self) -> None:
        if type(self) is not DecodedDerivedDocument:
            raise _decoding_error(
                "authoring.decoded_derived_document_subclass_rejected",
                "decoded derived document must have its exact nominal type",
            )


def _encode_text(value: object) -> bytes:
    try:
        text = validate_utf8_text(value)
    except AuthoringValidationError as exc:
        raise _encoding_error(
            "authoring.canonical_text_invalid", "TEXT value is not canonical"
        ) from exc
    payload = text.encode("utf-8", errors="strict")
    return bytes((_TAG_TEXT,)) + len(payload).to_bytes(4, "big") + payload


def _check_depth(depth: int, *, decoding: bool) -> None:
    if depth > MAX_CANONICAL_NESTING_DEPTH:
        if decoding:
            raise _decoding_error(
                "authoring.canonical_depth_exceeded",
                "canonical value exceeds the v1 nesting-depth bound",
            )
        raise _encoding_error(
            "authoring.canonical_depth_exceeded",
            "canonical value exceeds the v1 nesting-depth bound",
        )


def _encode_value(value: object, depth: int) -> bytes:
    _check_depth(depth, decoding=False)
    if type(value) is bool:
        return bytes((_TAG_TRUE if value else _TAG_FALSE,))
    if type(value) is CanonicalInt64:
        return bytes((_TAG_INT64,)) + value.value.to_bytes(8, "big", signed=True)
    if type(value) is CanonicalUInt64:
        return bytes((_TAG_UINT64,)) + value.value.to_bytes(8, "big", signed=False)
    if type(value) is CanonicalFloat64:
        canonical = validate_finite_float64(value.value)
        return bytes((_TAG_FLOAT64,)) + struct.pack(">d", canonical)
    if type(value) is CanonicalText:
        return _encode_text(value.value)
    if type(value) is CanonicalBytes:
        payload = validate_exact_bytes(value.value)
        return bytes((_TAG_BYTES,)) + len(payload).to_bytes(4, "big") + payload
    if type(value) is CanonicalTuple:
        chunks = [bytes((_TAG_TUPLE,)), len(value.items).to_bytes(4, "big")]
        chunks.extend(_encode_value(item, depth + 1) for item in value.items)
        return b"".join(chunks)
    if type(value) is CanonicalRecord:
        chunks = [bytes((_TAG_RECORD,)), _encode_text(value.record_type)]
        chunks.append(len(value.fields).to_bytes(4, "big"))
        for name, field_value in value.fields:
            chunks.append(_encode_text(name))
            chunks.append(_encode_value(field_value, depth + 1))
        return b"".join(chunks)
    if type(value) is CanonicalUnion:
        return (
            bytes((_TAG_UNION,))
            + _encode_text(value.tag)
            + _encode_value(value.payload, depth + 1)
        )
    if type(value) is CanonicalNominalRef:
        return (
            bytes((_TAG_REF,))
            + _encode_text(value.ref_type)
            + _encode_value(value.record, depth + 1)
        )
    raise _encoding_error(
        "authoring.canonical_value_unknown",
        "value is outside the closed canonical vocabulary",
    )


def encode_value(value: CanonicalValue) -> bytes:
    """Encode one closed canonical value without top-level document framing."""
    return _encode_value(value, 0)


class _Reader:
    __slots__ = ("_offset", "_payload")

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._offset = 0

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def remaining(self) -> int:
        return len(self._payload) - self._offset

    def take(self, count: int) -> bytes:
        if type(count) is not int or count < 0 or count > self.remaining:
            raise _decoding_error(
                "authoring.canonical_truncated",
                "canonical bytes end before a declared value is complete",
            )
        start = self._offset
        self._offset += count
        return self._payload[start : self._offset]

    def byte(self) -> int:
        return self.take(1)[0]

    def uint32(self) -> int:
        return int.from_bytes(self.take(4), "big", signed=False)


def _decode_text_body(reader: _Reader) -> CanonicalText:
    if reader.byte() != _TAG_TEXT:
        raise _decoding_error(
            "authoring.canonical_text_tag_invalid", "expected an exact TEXT value"
        )
    length = reader.uint32()
    if length > MAX_CANONICAL_PAYLOAD_BYTES:
        raise _decoding_error(
            "authoring.canonical_text_too_large",
            "declared TEXT length exceeds the v1 bound",
        )
    payload = reader.take(length)
    try:
        value = payload.decode("utf-8", errors="strict")
        return CanonicalText(value)
    except (UnicodeError, AuthoringValidationError) as exc:
        raise _decoding_error(
            "authoring.canonical_text_invalid",
            "TEXT bytes are not strict pre-normalized NFC Unicode",
        ) from exc


def _decode_value(reader: _Reader, depth: int) -> CanonicalValue:
    _check_depth(depth, decoding=True)
    tag = reader.byte()
    if tag == _TAG_NULL:
        raise _decoding_error(
            "authoring.canonical_null_forbidden",
            "the closed v1 schema has no null-bearing union payload",
        )
    if tag == _TAG_FALSE:
        return False
    if tag == _TAG_TRUE:
        return True
    if tag == _TAG_INT64:
        return CanonicalInt64(int.from_bytes(reader.take(8), "big", signed=True))
    if tag == _TAG_UINT64:
        return CanonicalUInt64(int.from_bytes(reader.take(8), "big", signed=False))
    if tag == _TAG_FLOAT64:
        raw = reader.take(8)
        value = struct.unpack(">d", raw)[0]
        if not math.isfinite(value):
            raise _decoding_error(
                "authoring.canonical_float_nonfinite",
                "canonical Float64 must be finite",
            )
        if value == 0.0 and raw != b"\x00" * 8:
            raise _decoding_error(
                "authoring.canonical_negative_zero",
                "canonical Float64 zero must use positive-zero bits",
            )
        return CanonicalFloat64(value)
    if tag == _TAG_TEXT:
        # Rewind the one tag byte for the common bounded TEXT decoder.
        reader._offset -= 1
        return _decode_text_body(reader)
    if tag == _TAG_BYTES:
        length = reader.uint32()
        if length > MAX_CANONICAL_PAYLOAD_BYTES:
            raise _decoding_error(
                "authoring.canonical_bytes_too_large",
                "declared BYTES length exceeds the v1 bound",
            )
        return CanonicalBytes(reader.take(length))
    if tag == _TAG_TUPLE:
        count = reader.uint32()
        if count > MAX_CANONICAL_TUPLE_ITEMS:
            raise _decoding_error(
                "authoring.canonical_tuple_too_large",
                "declared tuple count exceeds the v1 bound",
            )
        return CanonicalTuple(
            tuple(_decode_value(reader, depth + 1) for _ in range(count))
        )
    if tag == _TAG_RECORD:
        record_type = _decode_text_body(reader).value
        try:
            validate_canonical_id(record_type, "record_type")
        except AuthoringValidationError as exc:
            raise _decoding_error(
                "authoring.canonical_record_type_invalid",
                "decoded record type is not a canonical schema literal",
            ) from exc
        count = reader.uint32()
        if count > MAX_CANONICAL_TUPLE_ITEMS:
            raise _decoding_error(
                "authoring.canonical_fields_too_large",
                "declared record field count exceeds the v1 bound",
            )
        if record_type == "empty_payload" and count != 0:
            raise _decoding_error(
                "authoring.canonical_empty_payload_invalid",
                "empty_payload is the exact zero-field record",
            )
        fields: list[tuple[str, object]] = []
        previous_name_bytes: bytes | None = None
        for _ in range(count):
            name = _decode_text_body(reader).value
            try:
                validate_canonical_id(name, "field_name")
            except AuthoringValidationError as exc:
                raise _decoding_error(
                    "authoring.canonical_field_name_invalid",
                    "decoded field name is not a canonical schema literal",
                ) from exc
            name_bytes = name.encode("utf-8")
            if previous_name_bytes is not None and name_bytes <= previous_name_bytes:
                raise _decoding_error(
                    "authoring.canonical_field_order_invalid",
                    "record fields are duplicate or not in strict canonical order",
                )
            previous_name_bytes = name_bytes
            fields.append((name, _decode_value(reader, depth + 1)))
        return CanonicalRecord(record_type, tuple(fields))
    if tag == _TAG_UNION:
        union_tag = _decode_text_body(reader).value
        if _UNION_TAG.fullmatch(union_tag) is None:
            raise _decoding_error(
                "authoring.canonical_union_tag_invalid",
                "decoded union tag is not a closed uppercase ASCII literal",
            )
        return CanonicalUnion(union_tag, _decode_value(reader, depth + 1))
    if tag == _TAG_REF:
        ref_type = _decode_text_body(reader).value
        record = _decode_value(reader, depth + 1)
        if type(record) is not CanonicalRecord:
            raise _decoding_error(
                "authoring.canonical_ref_record_invalid",
                "nominal ref payload must be an exact canonical record",
            )
        return CanonicalNominalRef(ref_type, record)
    raise _decoding_error(
        "authoring.canonical_tag_unknown",
        "canonical bytes contain an unknown primitive tag",
    )


def decode_value(payload: object) -> CanonicalValue:
    """Decode exactly one bounded canonical value and reject trailing bytes."""
    if type(payload) is not bytes:
        raise _decoding_error(
            "authoring.canonical_payload_type_invalid",
            "canonical payload must be exact immutable bytes",
        )
    if len(payload) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _decoding_error(
            "authoring.canonical_payload_too_large",
            "canonical payload exceeds the v1 document bound",
        )
    reader = _Reader(payload)
    value = _decode_value(reader, 0)
    if reader.remaining:
        raise _decoding_error(
            "authoring.canonical_trailing_bytes",
            "canonical payload contains trailing bytes",
        )
    return value


def _required_text_field(record: CanonicalRecord, name: str) -> str:
    value = record.field_map().get(name)
    if type(value) is not CanonicalText:
        raise _encoding_error(
            "authoring.canonical_common_field_invalid",
            f"top-level field {name} must be exact canonical TEXT",
        )
    return value.value


def canonical_document(
    object_kind: object,
    schema_version: object,
    record: CanonicalRecord,
) -> bytes:
    """Frame one exact top-level authored identity document."""
    if type(object_kind) is not str or object_kind not in OBJECT_KINDS:
        raise _encoding_error(
            "authoring.object_kind_unknown",
            "object kind is not in the closed B-02A registry",
        )
    try:
        schema = validate_version_token(schema_version, "schema_version")
    except AuthoringValidationError as exc:
        raise _encoding_error(
            "authoring.schema_version_invalid", "schema version is not canonical"
        ) from exc
    if schema != AUTHORING_SCHEMA_VERSION:
        raise _encoding_error(
            "authoring.schema_version_unsupported",
            "the v1 authoring canonical profile supports only schema version 1.0",
        )
    if type(record) is not CanonicalRecord or record.record_type != object_kind:
        raise _encoding_error(
            "authoring.canonical_record_kind_mismatch",
            "top-level record type must equal the framed object kind",
        )
    if _required_text_field(record, "object_kind") != object_kind:
        raise _encoding_error(
            "authoring.canonical_record_kind_mismatch",
            "record object_kind does not equal the framing value",
        )
    if _required_text_field(record, "schema_version") != schema:
        raise _encoding_error(
            "authoring.canonical_schema_version_mismatch",
            "record schema_version does not equal the framing value",
        )
    if (
        _required_text_field(record, "canonicalization_profile")
        != CANONICALIZATION_PROFILE
    ):
        raise _encoding_error(
            "authoring.canonicalization_profile_invalid",
            "record canonicalization profile is not the v1 authoring profile",
        )
    document = (
        _DOCUMENT_HEADER
        + _encode_text(object_kind)
        + _encode_text(schema)
        + _encode_value(record, 0)
    )
    if len(document) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _encoding_error(
            "authoring.canonical_document_too_large",
            "canonical document exceeds the v1 byte bound",
        )
    return document


def derived_record_field_names(
    record_type: object,
    *,
    schema_version: object = AUTHORING_SCHEMA_VERSION,
) -> tuple[str, ...]:
    """Return exact v1 fields for one registered auxiliary/derived record."""
    try:
        version = validate_version_token(schema_version, "schema_version")
    except AuthoringValidationError as exc:
        raise _encoding_error(
            "authoring.schema_version_invalid",
            "derived schema version is not canonical",
        ) from exc
    if version != AUTHORING_SCHEMA_VERSION:
        raise _encoding_error(
            "authoring.schema_version_unsupported",
            "the v1 derived record registry supports only schema version 1.0",
        )
    if (
        type(record_type) is not str
        or record_type not in DERIVED_RECORD_FIELD_REGISTRY_V1
    ):
        raise _encoding_error(
            "authoring.derived_record_type_unknown",
            "record type is not in the explicit v1 derived record registry",
        )
    return tuple(DERIVED_RECORD_FIELD_REGISTRY_V1[record_type])


def validate_registered_derived_record(
    record: object,
    *,
    document_record: bool = False,
) -> CanonicalRecord:
    """Validate exact kind, version, profile, and fields without reflection."""
    if type(document_record) is not bool:
        raise TypeError("document_record must be an exact Boolean")
    if type(record) is not CanonicalRecord:
        raise _encoding_error(
            "authoring.derived_record_value_invalid",
            "derived record must be an exact canonical record",
        )
    expected_fields = derived_record_field_names(record.record_type)
    if document_record and record.record_type not in DERIVED_DOCUMENT_RECORD_TYPES_V1:
        raise _encoding_error(
            "authoring.derived_document_type_unknown",
            "only the three closed evidence records may use derived framing",
        )
    actual_fields = tuple(name for name, _ in record.fields)
    if actual_fields != expected_fields:
        raise _encoding_error(
            "authoring.derived_record_fields_invalid",
            "derived record has missing, unknown, or extra fields",
        )
    fields = record.field_map()
    if "schema_version" in fields:
        version = fields["schema_version"]
        if (
            type(version) is not CanonicalText
            or version.value != AUTHORING_SCHEMA_VERSION
        ):
            raise _encoding_error(
                "authoring.schema_version_unsupported",
                "registered v1 derived record must carry schema version 1.0",
            )
    if "canonicalization_profile" in fields:
        profile = fields["canonicalization_profile"]
        if (
            type(profile) is not CanonicalText
            or profile.value != DERIVED_EVIDENCE_CANONICALIZATION_PROFILE
        ):
            raise _encoding_error(
                "authoring.derived_profile_invalid",
                "derived evidence record has the wrong canonicalization profile",
            )
    return record


def canonical_derived_document(
    record_type: object,
    schema_version: object,
    record: CanonicalRecord,
) -> bytes:
    """Frame one v1 derived-evidence record without a self-referential digest."""
    if (
        type(record_type) is not str
        or record_type not in DERIVED_DOCUMENT_RECORD_TYPES_V1
    ):
        raise _encoding_error(
            "authoring.derived_record_type_unknown",
            "record type is not a closed v1 derived-evidence type",
        )
    try:
        schema = validate_version_token(schema_version, "schema_version")
    except AuthoringValidationError as exc:
        raise _encoding_error(
            "authoring.schema_version_invalid",
            "derived schema version is not canonical",
        ) from exc
    if schema != AUTHORING_SCHEMA_VERSION:
        raise _encoding_error(
            "authoring.schema_version_unsupported",
            "the v1 derived-evidence profile supports only schema version 1.0",
        )
    if type(record) is not CanonicalRecord or record.record_type != record_type:
        raise _encoding_error(
            "authoring.derived_record_type_mismatch",
            "derived record type does not equal the framing value",
        )
    validate_registered_derived_record(record, document_record=True)
    fields = record.field_map()
    embedded_schema = fields["schema_version"]
    embedded_profile = fields["canonicalization_profile"]
    if (
        type(embedded_schema) is not CanonicalText
        or embedded_schema.value != AUTHORING_SCHEMA_VERSION
    ):
        raise _encoding_error(
            "authoring.derived_schema_version_mismatch",
            "derived record schema_version does not equal the framing value",
        )
    if (
        type(embedded_profile) is not CanonicalText
        or embedded_profile.value != DERIVED_EVIDENCE_CANONICALIZATION_PROFILE
    ):
        raise _encoding_error(
            "authoring.derived_profile_invalid",
            "derived record has the wrong canonicalization profile",
        )
    document = (
        _DERIVED_HEADER
        + _encode_text(record_type)
        + _encode_text(schema)
        + _encode_value(record, 0)
    )
    if len(document) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _encoding_error(
            "authoring.canonical_document_too_large",
            "derived canonical document exceeds the v1 byte bound",
        )
    return document


def decode_derived_document(
    payload: object,
    *,
    expected_record_type: object | None = None,
    expected_schema_version: object = AUTHORING_SCHEMA_VERSION,
    expected_record_fields: tuple[str, ...] | None = None,
) -> DecodedDerivedDocument:
    """Decode one exact closed v1 derived-evidence document."""
    if type(payload) is not bytes:
        raise _decoding_error(
            "authoring.canonical_payload_type_invalid",
            "derived canonical document must be exact immutable bytes",
        )
    if len(payload) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _decoding_error(
            "authoring.canonical_document_too_large",
            "derived canonical document exceeds the v1 byte bound",
        )
    if not payload.startswith(_DERIVED_HEADER):
        raise _decoding_error(
            "authoring.derived_header_invalid",
            "derived document has the wrong domain-separation header",
        )
    try:
        expected_version = validate_version_token(
            expected_schema_version, "expected_schema_version"
        )
    except AuthoringValidationError as exc:
        raise _decoding_error(
            "authoring.expected_schema_version_invalid",
            "expected derived schema version is not canonical",
        ) from exc
    if expected_version != AUTHORING_SCHEMA_VERSION:
        raise _decoding_error(
            "authoring.schema_version_unsupported",
            "the v1 derived-evidence profile supports only schema version 1.0",
        )
    if expected_record_type is not None and (
        type(expected_record_type) is not str
        or expected_record_type not in DERIVED_DOCUMENT_RECORD_TYPES_V1
    ):
        raise _decoding_error(
            "authoring.expected_derived_record_type_invalid",
            "expected record type is not a closed derived-document type",
        )

    reader = _Reader(payload)
    reader.take(len(_DERIVED_HEADER))
    record_type = _decode_text_body(reader).value
    schema_version = _decode_text_body(reader).value
    if record_type not in DERIVED_DOCUMENT_RECORD_TYPES_V1:
        raise _decoding_error(
            "authoring.derived_record_type_unknown",
            "framed record type is not a closed v1 derived-document type",
        )
    if schema_version != AUTHORING_SCHEMA_VERSION:
        raise _decoding_error(
            "authoring.schema_version_unsupported",
            "framed derived schema version is not exact version 1.0",
        )
    if expected_record_type is not None and record_type != expected_record_type:
        raise _decoding_error(
            "authoring.expected_derived_record_type_mismatch",
            "derived document has a different record type than expected",
        )
    if schema_version != expected_version:
        raise _decoding_error(
            "authoring.expected_schema_version_mismatch",
            "derived document has a different schema version than expected",
        )

    record = _decode_value(reader, 0)
    if reader.remaining:
        raise _decoding_error(
            "authoring.canonical_trailing_bytes",
            "derived canonical document contains trailing bytes",
        )
    if type(record) is not CanonicalRecord or record.record_type != record_type:
        raise _decoding_error(
            "authoring.derived_record_type_mismatch",
            "derived record type does not equal the framing value",
        )
    try:
        validate_registered_derived_record(record, document_record=True)
    except CanonicalEncodingError as exc:
        raise _decoding_error(exc.code, str(exc)) from exc

    registered_fields = derived_record_field_names(record_type)
    if expected_record_fields is not None:
        if type(expected_record_fields) is not tuple or any(
            type(name) is not str for name in expected_record_fields
        ):
            raise TypeError(
                "expected_record_fields must be an exact tuple of built-in strings"
            )
        if expected_record_fields != registered_fields:
            raise _decoding_error(
                "authoring.expected_derived_fields_invalid",
                "expected fields do not equal the registered v1 field set",
            )

    fields = record.field_map()
    profile = fields["canonicalization_profile"]
    return DecodedDerivedDocument(
        record_type,
        schema_version,
        profile.value,
        record,
    )


def decode_document(
    payload: object,
    *,
    expected_object_kind: object | None = None,
    expected_schema_version: object | None = None,
    allowed_record_fields: tuple[str, ...] | None = None,
) -> DecodedCanonicalDocument:
    """Decode framing plus a closed top-level record; semantic adapters follow."""
    if type(payload) is not bytes:
        raise _decoding_error(
            "authoring.canonical_payload_type_invalid",
            "canonical document must be exact immutable bytes",
        )
    if len(payload) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _decoding_error(
            "authoring.canonical_document_too_large",
            "canonical document exceeds the v1 byte bound",
        )
    if not payload.startswith(_DOCUMENT_HEADER):
        raise _decoding_error(
            "authoring.canonical_header_invalid",
            "canonical document has the wrong domain-separation header",
        )
    reader = _Reader(payload)
    reader.take(len(_DOCUMENT_HEADER))
    object_kind = _decode_text_body(reader).value
    schema_version = _decode_text_body(reader).value
    if object_kind not in OBJECT_KINDS:
        raise _decoding_error(
            "authoring.object_kind_unknown",
            "framed object kind is not in the closed B-02A registry",
        )
    try:
        validate_version_token(schema_version, "schema_version")
    except AuthoringValidationError as exc:
        raise _decoding_error(
            "authoring.schema_version_invalid",
            "framed schema version is not canonical",
        ) from exc
    if schema_version != AUTHORING_SCHEMA_VERSION:
        raise _decoding_error(
            "authoring.schema_version_unsupported",
            "the v1 authoring canonical profile supports only schema version 1.0",
        )
    record = _decode_value(reader, 0)
    if reader.remaining:
        raise _decoding_error(
            "authoring.canonical_trailing_bytes",
            "canonical document contains trailing bytes",
        )
    if type(record) is not CanonicalRecord or record.record_type != object_kind:
        raise _decoding_error(
            "authoring.canonical_record_kind_mismatch",
            "top-level record type does not equal the framed object kind",
        )
    field_map = record.field_map()
    kind_value = field_map.get("object_kind")
    schema_value = field_map.get("schema_version")
    profile_value = field_map.get("canonicalization_profile")
    if type(kind_value) is not CanonicalText or kind_value.value != object_kind:
        raise _decoding_error(
            "authoring.canonical_record_kind_mismatch",
            "record object_kind does not equal the framing value",
        )
    if type(schema_value) is not CanonicalText or schema_value.value != schema_version:
        raise _decoding_error(
            "authoring.canonical_schema_version_mismatch",
            "record schema_version does not equal the framing value",
        )
    if (
        type(profile_value) is not CanonicalText
        or profile_value.value != CANONICALIZATION_PROFILE
    ):
        raise _decoding_error(
            "authoring.canonicalization_profile_invalid",
            "record canonicalization profile is not the v1 authoring profile",
        )
    if expected_object_kind is not None and (
        type(expected_object_kind) is not str or object_kind != expected_object_kind
    ):
        raise _decoding_error(
            "authoring.expected_object_kind_mismatch",
            "canonical document has a different object kind than expected",
        )
    if expected_schema_version is not None and (
        type(expected_schema_version) is not str
        or schema_version != expected_schema_version
    ):
        raise _decoding_error(
            "authoring.expected_schema_version_mismatch",
            "canonical document has a different schema version than expected",
        )
    if allowed_record_fields is not None:
        if type(allowed_record_fields) is not tuple or any(
            type(name) is not str for name in allowed_record_fields
        ):
            raise TypeError("allowed_record_fields must be an exact tuple of strings")
        if set(field_map) != set(allowed_record_fields):
            raise _decoding_error(
                "authoring.canonical_record_fields_invalid",
                "canonical record has missing, unknown, or extra fields",
            )
    return DecodedCanonicalDocument(object_kind, schema_version, record)


def tagged_sha256(payload: object) -> str:
    """Return A3's tagged SHA-256 for exact immutable bytes."""
    if type(payload) is not bytes:
        raise _encoding_error(
            "authoring.digest_payload_type_invalid",
            "digest input must be exact immutable bytes",
        )
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def challenge_key_to_canonical(value: object) -> CanonicalRecord:
    """Encode an exact reconstructed A3 ChallengeKey as its fixed record."""
    key = reconstruct_challenge_key(value)
    return CanonicalRecord(
        "challenge_key",
        (
            ("challenge_id", CanonicalText(key.challenge_id)),
            ("version", CanonicalText(key.version)),
        ),
    )


def challenge_key_from_canonical(value: object) -> ChallengeKey:
    """Reconstruct an A3 ChallengeKey from exactly its closed record."""
    if type(value) is not CanonicalRecord or value.record_type != "challenge_key":
        raise _decoding_error(
            "authoring.challenge_key_record_invalid",
            "challenge key must use its exact closed record",
        )
    fields = value.field_map()
    if set(fields) != {"challenge_id", "version"}:
        raise _decoding_error(
            "authoring.challenge_key_fields_invalid",
            "challenge key has missing, unknown, or extra fields",
        )
    challenge_id = fields["challenge_id"]
    version = fields["version"]
    if type(challenge_id) is not CanonicalText or type(version) is not CanonicalText:
        raise _decoding_error(
            "authoring.challenge_key_value_invalid",
            "challenge key fields must be canonical TEXT",
        )
    try:
        return ChallengeKey(challenge_id.value, version.value)
    except (TypeError, ValueError) as exc:
        raise _decoding_error(
            "authoring.challenge_key_value_invalid",
            "challenge key does not satisfy the controlling A3 grammar",
        ) from exc


def owner_scope_to_canonical(value: object) -> CanonicalUnion:
    """Encode the exact closed CHALLENGE/GLOBAL owner-scope union."""
    if type(value) is ChallengeScope:
        return CanonicalUnion(
            "CHALLENGE", challenge_key_to_canonical(value.challenge_key)
        )
    if type(value) is GlobalScope:
        return CanonicalUnion("GLOBAL", CanonicalRecord("empty_payload", ()))
    raise _encoding_error(
        "authoring.owner_scope_type_invalid",
        "owner scope must be an exact closed scope variant",
    )


def owner_scope_from_canonical(value: object) -> ChallengeScope | GlobalScope:
    """Reconstruct the exact closed owner-scope union."""
    if type(value) is not CanonicalUnion:
        raise _decoding_error(
            "authoring.owner_scope_union_invalid",
            "owner scope must be an exact canonical union",
        )
    if value.tag == "CHALLENGE":
        return ChallengeScope(challenge_key_from_canonical(value.payload))
    if (
        value.tag == "GLOBAL"
        and type(value.payload) is CanonicalRecord
        and value.payload.record_type == "empty_payload"
        and not value.payload.fields
    ):
        return GlobalScope()
    raise _decoding_error(
        "authoring.owner_scope_variant_invalid",
        "owner scope has an unknown tag or malformed payload",
    )


def owner_ref_to_canonical(value: object) -> CanonicalNominalRef:
    """Encode one exact nominal owner ref without relying on its Python name."""
    if not is_owner_ref(value):
        raise _encoding_error(
            "authoring.owner_ref_type_invalid",
            "value is not an exact closed owner-ref type",
        )
    return CanonicalNominalRef(
        value.ref_kind,
        CanonicalRecord(
            "owner_ref",
            (
                ("content_digest", CanonicalText(value.content_digest)),
                ("object_id", CanonicalText(value.object_id)),
                ("object_version", CanonicalText(value.object_version)),
                ("ref_kind", CanonicalText(value.ref_kind)),
                ("scope_binding", owner_scope_to_canonical(value.scope_binding)),
            ),
        ),
    )


def owner_ref_from_canonical(value: object, *, expected_kind: object) -> object:
    """Reconstruct one exact owner ref and reject kind/layout confusion."""
    expected_type = owner_ref_type(expected_kind)
    if (
        type(value) is not CanonicalNominalRef
        or value.ref_type != expected_kind
        or value.record.record_type != "owner_ref"
    ):
        raise _decoding_error(
            "authoring.owner_ref_kind_mismatch",
            "canonical owner ref has the wrong nominal kind",
        )
    fields = value.record.field_map()
    expected_fields = {
        "content_digest",
        "object_id",
        "object_version",
        "ref_kind",
        "scope_binding",
    }
    if set(fields) != expected_fields:
        raise _decoding_error(
            "authoring.owner_ref_fields_invalid",
            "owner ref has missing, unknown, or extra fields",
        )
    text_names = ("content_digest", "object_id", "object_version", "ref_kind")
    if any(type(fields[name]) is not CanonicalText for name in text_names):
        raise _decoding_error(
            "authoring.owner_ref_value_invalid",
            "owner ref scalar fields must be canonical TEXT",
        )
    if fields["ref_kind"].value != expected_kind:
        raise _decoding_error(
            "authoring.owner_ref_kind_mismatch",
            "embedded owner-ref kind does not match the nominal ref type",
        )
    try:
        return expected_type(
            owner_scope_from_canonical(fields["scope_binding"]),
            fields["object_id"].value,
            fields["object_version"].value,
            fields["content_digest"].value,
        )
    except AuthoringValidationError as exc:
        raise _decoding_error(
            "authoring.owner_ref_value_invalid",
            "owner ref contains malformed identity fields",
        ) from exc


def top_level_ref_to_canonical(value: object) -> CanonicalNominalRef:
    """Encode one of the six exact top-level refs."""
    if not is_top_level_ref(value):
        raise _encoding_error(
            "authoring.top_level_ref_type_invalid",
            "value is not an exact top-level authoring ref",
        )
    if value.schema_version != AUTHORING_SCHEMA_VERSION:
        raise _encoding_error(
            "authoring.schema_version_unsupported",
            "the v1 ref codec supports only authoring schema version 1.0",
        )
    fields: list[tuple[str, object]] = [
        ("canonicalization_profile", CanonicalText(value.canonicalization_profile)),
        ("challenge_key", challenge_key_to_canonical(value.challenge_key)),
        ("content_digest", CanonicalText(value.content_digest)),
        ("object_id", CanonicalText(value.object_id)),
        ("object_kind", CanonicalText(value.object_kind)),
        ("object_version", CanonicalText(value.object_version)),
        ("schema_version", CanonicalText(value.schema_version)),
    ]
    if type(value) is InstanceDistributionContractRef:
        fields.append(
            (
                "expected_population_role",
                CanonicalText(value.expected_population_role),
            )
        )
    elif type(value) is CanonicalChallengeCaseRef:
        fields.append(("disclosure_class", CanonicalText(value.disclosure_class)))
    return CanonicalNominalRef(
        value.ref_type, CanonicalRecord(value.ref_type, tuple(fields))
    )


def top_level_ref_from_canonical(value: object) -> TopLevelObjectRef:
    """Reconstruct one exact top-level ref from its closed canonical form."""
    if type(value) is not CanonicalNominalRef:
        raise _decoding_error(
            "authoring.top_level_ref_value_invalid",
            "top-level ref must be an exact canonical nominal ref",
        )
    candidate_types = tuple(
        ref_type
        for ref_type in TOP_LEVEL_REF_TYPES
        if f"{ref_type.OBJECT_KIND}_ref" == value.ref_type
    )
    if len(candidate_types) != 1 or value.record.record_type != value.ref_type:
        raise _decoding_error(
            "authoring.top_level_ref_kind_unknown",
            "top-level ref type is not in the closed six-type registry",
        )
    ref_type = candidate_types[0]
    fields = value.record.field_map()
    expected = {
        "canonicalization_profile",
        "challenge_key",
        "content_digest",
        "object_id",
        "object_kind",
        "object_version",
        "schema_version",
    }
    if ref_type is InstanceDistributionContractRef:
        expected.add("expected_population_role")
    if ref_type is CanonicalChallengeCaseRef:
        expected.add("disclosure_class")
    if set(fields) != expected:
        raise _decoding_error(
            "authoring.top_level_ref_fields_invalid",
            "top-level ref has missing, unknown, or extra fields",
        )
    text_names = expected - {"challenge_key"}
    if any(type(fields[name]) is not CanonicalText for name in text_names):
        raise _decoding_error(
            "authoring.top_level_ref_value_invalid",
            "top-level ref scalar fields must be canonical TEXT",
        )
    if fields["object_kind"].value != ref_type.OBJECT_KIND:
        raise _decoding_error(
            "authoring.top_level_ref_kind_mismatch",
            "embedded object kind does not match the nominal ref type",
        )
    if fields["schema_version"].value != AUTHORING_SCHEMA_VERSION:
        raise _decoding_error(
            "authoring.schema_version_unsupported",
            "the v1 ref codec supports only authoring schema version 1.0",
        )
    common: tuple[object, ...] = (
        challenge_key_from_canonical(fields["challenge_key"]),
        fields["object_id"].value,
        fields["object_version"].value,
        fields["schema_version"].value,
        fields["canonicalization_profile"].value,
        fields["content_digest"].value,
    )
    try:
        if ref_type is InstanceDistributionContractRef:
            return ref_type(*common, fields["expected_population_role"].value)
        if ref_type is CanonicalChallengeCaseRef:
            return ref_type(*common, fields["disclosure_class"].value)
        return ref_type(*common)
    except AuthoringValidationError as exc:
        raise _decoding_error(
            "authoring.top_level_ref_value_invalid",
            "top-level ref contains malformed identity fields",
        ) from exc


def encode_top_level_ref(value: object) -> bytes:
    """Encode one exact top-level ref as a standalone canonical value."""
    return encode_value(top_level_ref_to_canonical(value))


def decode_top_level_ref(payload: object) -> TopLevelObjectRef:
    """Decode one exact standalone top-level ref with trailing-byte rejection."""
    return top_level_ref_from_canonical(decode_value(payload))


def make_top_level_ref(
    ref_type: type,
    *,
    canonical_bytes: object,
    challenge_key: object,
    object_id: object,
    object_version: object,
    schema_version: object,
    canonicalization_profile: object,
    expected_population_role: object | None = None,
    disclosure_class: object | None = None,
) -> TopLevelObjectRef:
    """Create an exact content-addressed ref from already canonical bytes."""
    if type(ref_type) is not type or ref_type not in TOP_LEVEL_REF_TYPES:
        raise _encoding_error(
            "authoring.top_level_ref_class_invalid",
            "ref_type must be one of the six exact top-level ref classes",
        )
    if type(canonical_bytes) is not bytes:
        raise _encoding_error(
            "authoring.canonical_payload_type_invalid",
            "canonical document must be exact immutable bytes",
        )
    try:
        exact_schema_version = validate_version_token(schema_version, "schema_version")
    except AuthoringValidationError as exc:
        raise _encoding_error(
            "authoring.schema_version_invalid",
            "top-level ref schema version is not canonical",
        ) from exc
    if exact_schema_version != AUTHORING_SCHEMA_VERSION:
        raise _encoding_error(
            "authoring.schema_version_unsupported",
            "the v1 ref codec supports only authoring schema version 1.0",
        )
    common: tuple[object, ...] = (
        challenge_key,
        object_id,
        object_version,
        exact_schema_version,
        canonicalization_profile,
        tagged_sha256(canonical_bytes),
    )
    if ref_type is InstanceDistributionContractRef:
        if disclosure_class is not None:
            raise _encoding_error(
                "authoring.top_level_ref_extension_invalid",
                "distribution refs cannot contain case disclosure class",
            )
        return ref_type(*common, expected_population_role)
    if ref_type is CanonicalChallengeCaseRef:
        if expected_population_role is not None:
            raise _encoding_error(
                "authoring.top_level_ref_extension_invalid",
                "case refs cannot contain expected population role",
            )
        return ref_type(*common, disclosure_class)
    if expected_population_role is not None or disclosure_class is not None:
        raise _encoding_error(
            "authoring.top_level_ref_extension_invalid",
            "this top-level ref kind admits no extension field",
        )
    return ref_type(*common)


def verify_top_level_ref(
    expected: object,
    *,
    canonical_bytes: object,
    challenge_key: object,
    object_id: object,
    object_version: object,
    schema_version: object,
    canonicalization_profile: object,
    expected_population_role: object | None = None,
    disclosure_class: object | None = None,
) -> TopLevelObjectRef:
    """Recompute and compare every exact ref field, including nominal type."""
    if not is_top_level_ref(expected):
        raise ReferenceMismatchError(
            "authoring.reference_type_invalid",
            "expected reference is not an exact top-level authoring ref",
        )
    try:
        recomputed = make_top_level_ref(
            type(expected),
            canonical_bytes=canonical_bytes,
            challenge_key=challenge_key,
            object_id=object_id,
            object_version=object_version,
            schema_version=schema_version,
            canonicalization_profile=canonicalization_profile,
            expected_population_role=expected_population_role,
            disclosure_class=disclosure_class,
        )
    except (AuthoringValidationError, CanonicalEncodingError) as exc:
        raise ReferenceMismatchError(
            "authoring.reference_mismatch",
            "recomputed reference metadata is invalid or does not match the pin",
        ) from exc
    if type(recomputed) is not type(expected) or not hmac.compare_digest(
        encode_top_level_ref(recomputed), encode_top_level_ref(expected)
    ):
        raise ReferenceMismatchError(
            "authoring.reference_mismatch",
            "recomputed reference does not exactly match the expected pin",
        )
    return reconstruct_top_level_ref(expected)


__all__ = [
    "CANONICALIZATION_PROFILE",
    "DERIVED_DOCUMENT_RECORD_TYPES_V1",
    "DERIVED_EVIDENCE_CANONICALIZATION_PROFILE",
    "DERIVED_RECORD_FIELD_REGISTRY_V1",
    "CanonicalBytes",
    "CanonicalFloat64",
    "CanonicalInt64",
    "CanonicalNominalRef",
    "CanonicalRecord",
    "CanonicalText",
    "CanonicalTuple",
    "CanonicalUInt64",
    "CanonicalUnion",
    "CanonicalValue",
    "DecodedCanonicalDocument",
    "DecodedDerivedDocument",
    "canonical_derived_document",
    "canonical_document",
    "challenge_key_from_canonical",
    "challenge_key_to_canonical",
    "decode_derived_document",
    "decode_document",
    "decode_top_level_ref",
    "decode_value",
    "derived_record_field_names",
    "encode_top_level_ref",
    "encode_value",
    "make_top_level_ref",
    "owner_ref_from_canonical",
    "owner_ref_to_canonical",
    "owner_scope_from_canonical",
    "owner_scope_to_canonical",
    "tagged_sha256",
    "top_level_ref_from_canonical",
    "top_level_ref_to_canonical",
    "validate_registered_derived_record",
    "verify_top_level_ref",
]
