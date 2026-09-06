"""Strict canonical bytes for the B-07S v2 wire profile."""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass, fields
from enum import Enum
from types import UnionType
from typing import Annotated, Union, get_args, get_origin, get_type_hints

from carbon.authoring.refs import TOP_LEVEL_REF_TYPES
from carbon.construction.refs import CONSTRUCTION_REF_TYPES
from carbon.fees import StrategyHash
from carbon.measurement.refs import MEASUREMENT_TOP_LEVEL_REF_TYPES
from carbon.registry import ChallengeKey
from carbon.resource_policy.refs import RESOURCE_POLICY_REF_TYPES

from .errors import (
    ErrorDetail,
    ResearchServiceError,
    ResearchServiceErrorCode,
)
from .model import (
    WIRE_RECORD_NAMES_BY_TYPE,
    WIRE_RECORD_TYPES_BY_NAME,
    ActivePriorSelector,
    AvailablePriorAvailability,
    CounterevidenceEntries,
    CounterevidenceNoneFound,
    ExactPriorSelector,
    FixturePriorAuthorization,
    ForbiddenControlField,
    NoPriorAvailability,
    NoPriorSelector,
    PairedPracticeTaskSpec,
    PracticeTaskSpec,
    PublicPriorAuthorization,
    ReconstructionRehearsalSpec,
    ResourceCalibrationTaskSpec,
    ServiceCall,
    ServiceReply,
)
from .refs import RESEARCH_DOCUMENT_HEADER, RESEARCH_REF_TYPES

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

MAX_CALL_REPLY_BYTES = 1_048_576
MAX_RESOURCE_BYTES = 8_388_608
MAX_DEPTH = 32
MAX_TUPLE_ITEMS = 4_096
MAX_TEXT_BYTES = 16_384

_DOMAIN_REF_TYPES = (
    *TOP_LEVEL_REF_TYPES,
    *CONSTRUCTION_REF_TYPES,
    *RESOURCE_POLICY_REF_TYPES,
    *MEASUREMENT_TOP_LEVEL_REF_TYPES,
)
_REF_TYPES = (*_DOMAIN_REF_TYPES, *RESEARCH_REF_TYPES)


def _ref_name(value_or_type: object) -> str:
    if isinstance(value_or_type, type):
        ref_type = value_or_type
        sample_name = getattr(ref_type, "REF_TYPE", "")
        if sample_name:
            return sample_name
        object_kind = getattr(ref_type, "OBJECT_KIND", "")
        if object_kind:
            return f"{object_kind}_ref"
        record_type = getattr(ref_type, "RECORD_TYPE", "")
        if record_type:
            return f"{record_type}_ref"
        explicit = {
            "PriorChannelRef": "prior_channel_ref",
            "PriorPackRef": "prior_pack_ref",
            "PriorIndexSnapshotRef": "prior_index_snapshot_ref",
            "PriorPublicationReceiptRef": "prior_publication_receipt_ref",
            "ResearchReceiptRef": "research_receipt_ref",
            "TestOnlyPriorAuthorizationReceiptRef": "test_only_prior_authorization_receipt_ref",
        }
        if ref_type.__name__ in explicit:
            return explicit[ref_type.__name__]
        return _snake(ref_type.__name__)
    return value_or_type.ref_type


_REF_BY_NAME = {_ref_name(ref_type): ref_type for ref_type in _REF_TYPES}

_UNION_TAG_BY_TYPE = {
    NoPriorAvailability: "NO_PRIOR",
    AvailablePriorAvailability: "AVAILABLE",
    ExactPriorSelector: "EXACT",
    ActivePriorSelector: "ACTIVE",
    NoPriorSelector: "NONE",
    ReconstructionRehearsalSpec: "RECONSTRUCTION_REHEARSAL",
    PracticeTaskSpec: "PRACTICE",
    PairedPracticeTaskSpec: "PAIRED_PRACTICE",
    ResourceCalibrationTaskSpec: "RESOURCE_CALIBRATION",
    PublicPriorAuthorization: "PUBLIC",
    FixturePriorAuthorization: "FIXTURE",
    CounterevidenceEntries: "ENTRIES",
    CounterevidenceNoneFound: "NONE_FOUND",
    ResearchServiceError: "ERROR",
}


def _snake(name: str) -> str:
    output: list[str] = []
    for index, character in enumerate(name):
        if character.isupper() and index and not name[index - 1].isupper():
            output.append("_")
        output.append(character.lower())
    return "".join(output)


class CanonicalWireError(ValueError):
    """Stable internal decoding classification consumed by the adapter."""

    def __init__(self, code: ResearchServiceErrorCode) -> None:
        self.code = code
        super().__init__("Canonical research wire data is invalid.")


@dataclass(frozen=True, slots=True)
class _Record:
    name: str
    fields: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class _TaggedUnion:
    tag: str
    payload: object


@dataclass(frozen=True, slots=True)
class _NominalRef:
    name: str
    record: _Record


@dataclass(frozen=True, slots=True)
class _UInt64:
    value: int


def _text(value: str) -> bytes:
    if type(value) is not str:
        raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
    try:
        payload = value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise CanonicalWireError(
            ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
        ) from None
    if len(payload) > MAX_TEXT_BYTES:
        raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    return bytes((_TAG_TEXT,)) + len(payload).to_bytes(4, "big") + payload


def _is_optional(annotation: object) -> bool:
    origin = get_origin(annotation)
    return origin in (Union, UnionType) and type(None) in get_args(annotation)


def _encode_json(value: object, depth: int) -> bytes:
    if value is None:
        return _encode_union("NULL", _Record("empty_payload", ()), depth)
    kind = type(value)
    if kind is bool:
        return _encode_union("BOOLEAN", value, depth)
    if kind is int:
        return _encode_union("INTEGER", value, depth)
    if kind is float:
        return _encode_union("NUMBER", value, depth)
    if kind is str:
        return _encode_union("TEXT", value, depth)
    if kind is list:
        return _encode_union("ARRAY", tuple(value), depth)
    if kind is dict:
        items = list(dict.items(value))
        if any(type(key) is not str for key, _ in items):
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        items.sort(key=lambda item: item[0].encode("utf-8", errors="strict"))
        members = tuple(
            _Record("json_member", (("key", key), ("value", child)))
            for key, child in items
        )
        return _encode_union("OBJECT", members, depth)
    raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)


def _encode_union(
    tag: str, payload: object, depth: int, expected: object = object
) -> bytes:
    return bytes((_TAG_UNION,)) + _text(tag) + _encode(payload, expected, depth + 1)


def _record_fields(value: object) -> tuple[tuple[str, object, object], ...]:
    if type(value) is ChallengeKey:
        return (
            ("challenge_id", value.challenge_id, str),
            ("version", value.version, str),
        )
    if type(value) is StrategyHash:
        return (("value", value.value, str),)
    hints = get_type_hints(type(value), include_extras=True)
    return tuple(
        (field.name, getattr(value, field.name), hints.get(field.name, object))
        for field in fields(value)
    )


def _record_name(value: object) -> str:
    if type(value) is ChallengeKey:
        return "challenge_key"
    if type(value) is StrategyHash:
        return "strategy_hash"
    if type(value) is ResearchServiceError:
        return "research_service_error"
    if type(value) is ErrorDetail:
        return "error_detail"
    try:
        return WIRE_RECORD_NAMES_BY_TYPE[type(value)]
    except KeyError:
        raise CanonicalWireError(
            ResearchServiceErrorCode.REQUEST_TYPE_INVALID
        ) from None


def _encode_record(value: object, depth: int) -> bytes:
    return _encode_record_node(
        _record_name(value),
        _record_fields(value),
        depth,
    )


def _encode_record_node(
    name: str,
    members: tuple[tuple[str, object, object], ...],
    depth: int,
) -> bytes:
    if depth > MAX_DEPTH:
        raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    chunks = [bytes((_TAG_RECORD,)), _text(name), len(members).to_bytes(4, "big")]
    for field_name, value, annotation in members:
        if type(value) is str:
            encoded_length = len(value.encode("utf-8", errors="strict"))
            if (
                field_name
                in {
                    "namespace",
                    "operation",
                    "schema_version",
                    "canonicalization_profile",
                    "challenge_version",
                    "version",
                    "object_id",
                    "object_version",
                    "channel",
                    "prior_id",
                    "prior_version",
                    "builder_version",
                    "authorization_id",
                }
                and encoded_length > 128
            ):
                raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
            if field_name == "challenge_id" and encoded_length > 256:
                raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
        chunks.append(_text(field_name))
        chunks.append(_encode(value, annotation, depth + 1))
    return b"".join(chunks)


def _encode(value: object, expected: object, depth: int) -> bytes:
    if depth > MAX_DEPTH:
        raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    origin = get_origin(expected)
    args = get_args(expected)
    if origin is Annotated:
        marker = args[1]
        if type(value) is not int:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        if marker == "uint64":
            if not 0 <= value <= (1 << 64) - 1:
                raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
            return bytes((_TAG_UINT64,)) + value.to_bytes(8, "big")
        expected = int
    if _is_optional(expected):
        if value is None:
            return _encode_union("NONE", _Record("empty_payload", ()), depth)
        member = next(member for member in args if member is not type(None))
        return _encode_union("SOME", value, depth, member)
    if origin in (Union, UnionType):
        if value is None:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        tag = _UNION_TAG_BY_TYPE.get(type(value), _snake(type(value).__name__).upper())
        return _encode_union(tag, value, depth, type(value))
    if origin is dict or (type(value) is dict and expected is object):
        return _encode_json(value, depth)
    if origin is tuple:
        if type(value) is not tuple or len(value) > MAX_TUPLE_ITEMS:
            raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
        member_type = args[0]
        return (
            bytes((_TAG_TUPLE,))
            + len(value).to_bytes(4, "big")
            + b"".join(_encode(item, member_type, depth + 1) for item in value)
        )
    if expected is object and type(value) in (tuple, list):
        if len(value) > MAX_TUPLE_ITEMS:
            raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
        return (
            bytes((_TAG_TUPLE,))
            + len(value).to_bytes(4, "big")
            + b"".join(_encode(item, object, depth + 1) for item in value)
        )
    if type(value) is bool:
        return bytes((_TAG_TRUE if value else _TAG_FALSE,))
    if type(value) is int:
        if not -(1 << 63) <= value <= (1 << 63) - 1:
            raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
        return bytes((_TAG_INT64,)) + value.to_bytes(8, "big", signed=True)
    if type(value) is float:
        if not math.isfinite(value):
            raise CanonicalWireError(
                ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
            )
        return bytes((_TAG_FLOAT64,)) + struct.pack(
            ">d", 0.0 if value == 0.0 else value
        )
    if type(value) is str:
        return _text(value)
    if type(value) is bytes:
        if len(value) > MAX_RESOURCE_BYTES:
            raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
        return bytes((_TAG_BYTES,)) + len(value).to_bytes(4, "big") + value
    if isinstance(value, Enum):
        if type(value.value) is not str:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        return _text(value.value)
    if type(value) in _REF_TYPES:
        name = _ref_name(value)
        fields_with_types = _record_fields(value)
        return (
            bytes((_TAG_REF,))
            + _text(name)
            + _encode_record_node(name, fields_with_types, depth + 1)
        )
    if isinstance(value, _Record):
        members = tuple((name, item, object) for name, item in value.fields)
        return _encode_record_node(value.name, members, depth)
    if type(value) in WIRE_RECORD_NAMES_BY_TYPE or type(value) in (
        ChallengeKey,
        StrategyHash,
        ErrorDetail,
        ResearchServiceError,
    ):
        return _encode_record(value, depth)
    raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)


def canonical_bytes(value: object) -> bytes:
    """Encode one exact public v2 value under the ratified document header."""

    payload = RESEARCH_DOCUMENT_HEADER + _encode(value, type(value), 0)
    limit = (
        MAX_CALL_REPLY_BYTES
        if type(value) in (ServiceCall, ServiceReply)
        else MAX_RESOURCE_BYTES
    )
    if len(payload) > limit:
        raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    return payload


def canonical_digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


class _Reader:
    __slots__ = ("offset", "payload")

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0

    def take(self, count: int) -> bytes:
        if (
            type(count) is not int
            or count < 0
            or count > len(self.payload) - self.offset
        ):
            raise CanonicalWireError(
                ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
            )
        start = self.offset
        self.offset += count
        return self.payload[start : self.offset]

    def byte(self) -> int:
        return self.take(1)[0]

    def uint32(self) -> int:
        return int.from_bytes(self.take(4), "big")


def _read_text(reader: _Reader, tag_already_read: bool = False) -> str:
    if not tag_already_read and reader.byte() != _TAG_TEXT:
        raise CanonicalWireError(ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID)
    length = reader.uint32()
    if length > MAX_TEXT_BYTES:
        raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    try:
        return reader.take(length).decode("utf-8", errors="strict")
    except UnicodeError:
        raise CanonicalWireError(
            ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
        ) from None


def _parse(reader: _Reader, depth: int = 0) -> object:
    if depth > MAX_DEPTH:
        raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    tag = reader.byte()
    if tag == _TAG_FALSE:
        return False
    if tag == _TAG_TRUE:
        return True
    if tag == _TAG_INT64:
        return int.from_bytes(reader.take(8), "big", signed=True)
    if tag == _TAG_UINT64:
        return _UInt64(int.from_bytes(reader.take(8), "big"))
    if tag == _TAG_FLOAT64:
        raw = reader.take(8)
        value = struct.unpack(">d", raw)[0]
        if not math.isfinite(value) or (value == 0.0 and raw != b"\x00" * 8):
            raise CanonicalWireError(
                ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
            )
        return value
    if tag == _TAG_TEXT:
        return _read_text(reader, True)
    if tag == _TAG_BYTES:
        length = reader.uint32()
        if length > MAX_RESOURCE_BYTES:
            raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
        return reader.take(length)
    if tag == _TAG_TUPLE:
        count = reader.uint32()
        if count > MAX_TUPLE_ITEMS:
            raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
        return tuple(_parse(reader, depth + 1) for _ in range(count))
    if tag == _TAG_RECORD:
        name = _read_text(reader)
        count = reader.uint32()
        if count > MAX_TUPLE_ITEMS:
            raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
        members: list[tuple[str, object]] = []
        seen: set[str] = set()
        for _ in range(count):
            field_name = _read_text(reader)
            if field_name in seen:
                raise CanonicalWireError(
                    ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
                )
            seen.add(field_name)
            members.append((field_name, _parse(reader, depth + 1)))
        return _Record(name, tuple(members))
    if tag == _TAG_UNION:
        return _TaggedUnion(_read_text(reader), _parse(reader, depth + 1))
    if tag == _TAG_REF:
        name = _read_text(reader)
        record = _parse(reader, depth + 1)
        if type(record) is not _Record:
            raise CanonicalWireError(
                ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
            )
        return _NominalRef(name, record)
    raise CanonicalWireError(ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID)


def _decode_json(node: object, depth: int = 0) -> object:
    if depth > MAX_DEPTH or type(node) is not _TaggedUnion:
        raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
    if node.tag == "NULL" and node.payload == _Record("empty_payload", ()):
        return None
    if node.tag == "BOOLEAN" and type(node.payload) is bool:
        return node.payload
    if node.tag == "INTEGER" and type(node.payload) is int:
        return node.payload
    if node.tag == "NUMBER" and type(node.payload) is float:
        return node.payload
    if node.tag == "TEXT" and type(node.payload) is str:
        return node.payload
    if node.tag == "ARRAY" and type(node.payload) is tuple:
        return [_decode_json(item, depth + 1) for item in node.payload]
    if node.tag == "OBJECT" and type(node.payload) is tuple:
        output: dict[str, object] = {}
        previous: bytes | None = None
        for item in node.payload:
            if (
                type(item) is not _Record
                or item.name != "json_member"
                or tuple(name for name, _ in item.fields) != ("key", "value")
            ):
                raise CanonicalWireError(
                    ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
                )
            key, child = item.fields[0][1], item.fields[1][1]
            if type(key) is not str or key in output:
                raise CanonicalWireError(
                    ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
                )
            encoded_key = key.encode("utf-8")
            if previous is not None and encoded_key <= previous:
                raise CanonicalWireError(
                    ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
                )
            previous = encoded_key
            output[key] = _decode_json(child, depth + 1)
        return output
    raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)


def _construct(node: object, expected: object) -> object:
    origin = get_origin(expected)
    args = get_args(expected)
    if origin is Annotated:
        marker = args[1]
        if marker == "uint64":
            if type(node) is not _UInt64:
                raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
            return node.value
        expected = int
    if _is_optional(expected):
        if type(node) is not _TaggedUnion:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        if node.tag == "NONE" and node.payload == _Record("empty_payload", ()):
            return None
        if node.tag != "SOME":
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        member = next(member for member in args if member is not type(None))
        return _construct(node.payload, member)
    if origin in (Union, UnionType):
        if type(node) is not _TaggedUnion:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        for member in args:
            tag = _UNION_TAG_BY_TYPE.get(
                member, _snake(getattr(member, "__name__", "")).upper()
            )
            if node.tag == tag:
                return _construct(node.payload, member)
        raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
    if origin is dict:
        value = _decode_json(node)
        if type(value) is not dict:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        return value
    if origin is tuple:
        if type(node) is not tuple:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        return tuple(_construct(item, args[0]) for item in node)
    if expected is object:
        if type(node) is _Record:
            target = {
                "challenge_key": ChallengeKey,
                "strategy_hash": StrategyHash,
                "error_detail": ErrorDetail,
                "research_service_error": ResearchServiceError,
                **WIRE_RECORD_TYPES_BY_NAME,
            }.get(node.name)
            if target is None:
                raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
            return _construct(node, target)
        if type(node) is _NominalRef:
            target = _REF_BY_NAME.get(node.name)
            if target is None:
                raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
            return _construct(node, target)
        return _decode_json(node)
    if isinstance(expected, type) and issubclass(expected, Enum):
        if type(node) is not str:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        try:
            return expected(node)
        except ValueError:
            raise CanonicalWireError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            ) from None
    if expected is bool:
        if type(node) is not bool:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        return node
    if expected is int:
        if type(node) is not int:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        return node
    if expected is float:
        if type(node) is not float:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        return node
    if expected is str:
        if type(node) is not str:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        return node
    if expected is bytes:
        if type(node) is not bytes:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        return node
    if expected in _REF_TYPES:
        if type(node) is not _NominalRef or node.name != _ref_name(expected):
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        record = node.record
        expected_name = _ref_name(expected)
        if record.name != expected_name:
            raise CanonicalWireError(
                ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
            )
        return _construct_record(record, expected)
    if (
        expected in (ChallengeKey, StrategyHash, ErrorDetail, ResearchServiceError)
        or expected in WIRE_RECORD_NAMES_BY_TYPE
    ):
        if type(node) is not _Record:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        expected_name = (
            "challenge_key"
            if expected is ChallengeKey
            else (
                "strategy_hash"
                if expected is StrategyHash
                else (
                    "error_detail"
                    if expected is ErrorDetail
                    else (
                        "research_service_error"
                        if expected is ResearchServiceError
                        else WIRE_RECORD_NAMES_BY_TYPE[expected]
                    )
                )
            )
        )
        if node.name != expected_name:
            raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)
        return _construct_record(node, expected)
    raise CanonicalWireError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)


def _construct_record(node: _Record, target: type[object]) -> object:
    if target is ChallengeKey:
        expected_fields = (("challenge_id", str), ("version", str))
    elif target is StrategyHash:
        expected_fields = (("value", str),)
    else:
        hints = get_type_hints(target, include_extras=True)
        expected_fields = tuple(
            (field.name, hints.get(field.name, object)) for field in fields(target)
        )
    names = tuple(name for name, _ in node.fields)
    expected_names = tuple(name for name, _ in expected_fields)
    if set(names) != set(expected_names):
        extras = set(names) - set(expected_names)
        normalized = {
            "".join(
                character for character in name.casefold() if character not in "-_ "
            )
            for name in extras
        }
        if normalized & {
            "context",
            "executioncontext",
            "provider",
            "mode",
            "evidenceclass",
            "qualificationlabel",
        }:
            code = ResearchServiceErrorCode.CONTEXT_SELECTION_FORBIDDEN
        elif normalized & {
            "rawdata",
            "customdata",
            "dataset",
            "datapath",
            "filesystempath",
            "path",
            "uri",
            "url",
            "seed",
            "seeds",
            "officialseed",
            "p",
            "q",
            "w",
            "stressset",
            "reference",
            "truth",
            "gate",
            "scorer",
            "credential",
            "credentials",
            "key",
            "privatekey",
            "signingkey",
            "listener",
            "address",
            "port",
        }:
            code = ResearchServiceErrorCode.FORBIDDEN_SCIENTIFIC_CONTROL
        else:
            code = (
                ResearchServiceErrorCode.UNKNOWN_FIELD
                if extras
                else ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID
            )
        raise CanonicalWireError(code)
    if names != expected_names:
        raise CanonicalWireError(ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID)
    kwargs = {
        name: _construct(raw, annotation)
        for (name, raw), (_, annotation) in zip(
            node.fields, expected_fields, strict=True
        )
    }
    try:
        return target(**kwargs)
    except ForbiddenControlField:
        raise CanonicalWireError(
            ResearchServiceErrorCode.FORBIDDEN_SCIENTIFIC_CONTROL
        ) from None
    except (AttributeError, TypeError, ValueError, UnicodeError):
        raise CanonicalWireError(
            ResearchServiceErrorCode.REQUEST_TYPE_INVALID
        ) from None


def load_canonical(payload: object, expected_type: type[object]) -> object:
    """Decode exactly one canonical v2 document into an exact nominal value."""

    if type(payload) is not bytes or not isinstance(expected_type, type):
        raise CanonicalWireError(ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID)
    limit = (
        MAX_CALL_REPLY_BYTES
        if expected_type in (ServiceCall, ServiceReply)
        else MAX_RESOURCE_BYTES
    )
    if len(payload) > limit:
        raise CanonicalWireError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    if not payload.startswith(RESEARCH_DOCUMENT_HEADER):
        raise CanonicalWireError(ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID)
    reader = _Reader(payload[len(RESEARCH_DOCUMENT_HEADER) :])
    node = _parse(reader)
    if reader.offset != len(reader.payload):
        raise CanonicalWireError(ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID)
    value = _construct(node, expected_type)
    if canonical_bytes(value) != payload:
        raise CanonicalWireError(ResearchServiceErrorCode.CANONICAL_ENCODING_INVALID)
    return value


def verify_resource_ref(resource: object, reference: object) -> None:
    if type(reference) not in (type(resource.to_ref()),):
        raise CanonicalWireError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
    if resource.to_ref() != reference:
        raise CanonicalWireError(ResearchServiceErrorCode.REFERENCE_MISMATCH)


__all__ = (
    "MAX_CALL_REPLY_BYTES",
    "MAX_DEPTH",
    "MAX_RESOURCE_BYTES",
    "MAX_TEXT_BYTES",
    "MAX_TUPLE_ITEMS",
    "CanonicalWireError",
    "canonical_bytes",
    "canonical_digest",
    "load_canonical",
    "verify_resource_ref",
)
