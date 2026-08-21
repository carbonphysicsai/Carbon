"""Canonical, schema-local binary documents for A4 seed derivation."""

from __future__ import annotations

from collections.abc import Callable

from carbon.registry import digest as registry_digest
from carbon.registry import model as registry_model

from .model import (
    SEED_SCHEME_ID,
    ContextKind,
    EvaluationBinding,
    RoleKey,
    SeedDomain,
    SeedPin,
    SeedValidationError,
    _PrivateExamRoot,
)

SEED_INFO_HEADER = b"carbon.seed.info.v1"
EXAM_ROOT_INFO_HEADER = b"carbon.exam-root.info.v1"
EXAM_COMMITMENT_HEADER = b"carbon.exam-commitment.v1"

_SEED_INFO_TAGS = tuple(range(0x01, 0x0D))
_EXAM_ROOT_INFO_TAGS = tuple(range(0x01, 0x0A))
_EXAM_COMMITMENT_TAGS = tuple(range(0x01, 0x0B))
_MAX_UINT64 = (1 << 64) - 1


class CanonicalEncodingError(SeedValidationError):
    """Stable, non-echoing failure for an invalid canonical A4 document."""


def _invalid(document_name: str) -> CanonicalEncodingError:
    return CanonicalEncodingError(f"invalid canonical {document_name} document")


def _ascii_payload(value: object, document_name: str) -> bytes:
    if type(value) is not str:
        raise _invalid(document_name)
    try:
        return value.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        raise _invalid(document_name) from None


def _tlv(tag: int, payload: bytes) -> bytes:
    return bytes((tag,)) + len(payload).to_bytes(4, "big") + payload


def _validated_common_payloads(
    context_kind: object,
    pin: object,
    document_name: str,
) -> tuple[bytes, ...]:
    if type(context_kind) is not ContextKind or type(pin) is not SeedPin:
        raise _invalid(document_name)

    challenge_key = pin.challenge_key
    if type(challenge_key) is not registry_model.ChallengeKey:
        raise _invalid(document_name)
    try:
        validated_key = registry_model.ChallengeKey(
            challenge_key.challenge_id,
            challenge_key.version,
        )
        generator_version = registry_model.validate_version(pin.generator_version)
        scoring_version = registry_model.validate_version(pin.scoring_version)
    except (TypeError, ValueError):
        raise _invalid(document_name) from None

    if (
        pin.seed_scheme != SEED_SCHEME_ID
        or not registry_digest.is_sha256_digest(pin.generator_digest)
        or not registry_digest.is_sha256_digest(pin.scoring_digest)
        or type(pin.evaluation_binding) is not EvaluationBinding
    ):
        raise _invalid(document_name)

    return (
        _ascii_payload(context_kind.value, document_name),
        _ascii_payload(pin.seed_scheme, document_name),
        _ascii_payload(validated_key.challenge_id, document_name),
        _ascii_payload(validated_key.version, document_name),
        _ascii_payload(generator_version, document_name),
        _ascii_payload(pin.generator_digest, document_name),
        _ascii_payload(scoring_version, document_name),
        _ascii_payload(pin.scoring_digest, document_name),
        pin.evaluation_binding._copy_bytes(),
    )


def _encode_fields(header: bytes, payloads: tuple[bytes, ...]) -> bytes:
    return header + b"".join(
        _tlv(tag, payload) for tag, payload in enumerate(payloads, start=1)
    )


def _valid_context_domain(context_kind: ContextKind, domain: SeedDomain) -> bool:
    if context_kind is ContextKind.MOCK:
        return domain is SeedDomain.MOCK
    if context_kind in {ContextKind.OFFICIAL, ContextKind.FIXTURE_OFFICIAL}:
        return domain in {
            SeedDomain.OFFICIAL_TRAIN,
            SeedDomain.OFFICIAL_EVAL,
            SeedDomain.OFFICIAL_STRESS,
        }
    if context_kind is ContextKind.QUALIFICATION:
        return domain in {SeedDomain.REFERENCE, SeedDomain.DOSSIER}
    return False


def _encode_seed_info(
    context_kind: ContextKind,
    pin: SeedPin,
    domain: SeedDomain,
    role_key: RoleKey,
    draw_index: int,
) -> bytes:
    """Encode one fully bound seed Expand document."""
    document_name = "seed-info"
    common = _validated_common_payloads(context_kind, pin, document_name)
    if (
        type(domain) is not SeedDomain
        or type(role_key) is not RoleKey
        or type(draw_index) is not int
        or draw_index < 0
        or draw_index > _MAX_UINT64
        or not _valid_context_domain(context_kind, domain)
    ):
        raise _invalid(document_name)

    payloads = common + (
        _ascii_payload(domain.value, document_name),
        _ascii_payload(role_key.value, document_name),
        draw_index.to_bytes(8, "big"),
    )
    document = _encode_fields(SEED_INFO_HEADER, payloads)
    _validate_seed_info(document)
    return document


def _encode_exam_root_info(context_kind: ContextKind, pin: SeedPin) -> bytes:
    """Encode the independent private-exam-root Expand document."""
    document_name = "exam-root-info"
    payloads = _validated_common_payloads(context_kind, pin, document_name)
    document = _encode_fields(EXAM_ROOT_INFO_HEADER, payloads)
    _validate_exam_root_info(document)
    return document


def _encode_exam_commitment_document(
    context_kind: ContextKind,
    pin: SeedPin,
    private_exam_root: _PrivateExamRoot,
) -> bytes:
    """Encode the preimage for the intentionally public exam commitment."""
    document_name = "exam-commitment"
    common = _validated_common_payloads(context_kind, pin, document_name)
    if type(private_exam_root) is not _PrivateExamRoot:
        raise _invalid(document_name)
    document = _encode_fields(
        EXAM_COMMITMENT_HEADER,
        common + (private_exam_root._copy_bytes(),),
    )
    _validate_exam_commitment_document(document)
    return document


def _parse_fields(
    document: object,
    header: bytes,
    expected_tags: tuple[int, ...],
    document_name: str,
) -> tuple[bytes, ...]:
    if type(document) is not bytes or not document.startswith(header):
        raise _invalid(document_name)

    offset = len(header)
    payloads: list[bytes] = []
    for expected_tag in expected_tags:
        field_header_end = offset + 5
        if field_header_end > len(document):
            raise _invalid(document_name)
        if document[offset] != expected_tag:
            raise _invalid(document_name)
        payload_length = int.from_bytes(document[offset + 1 : field_header_end], "big")
        payload_end = field_header_end + payload_length
        if payload_end > len(document):
            raise _invalid(document_name)
        payloads.append(document[field_header_end:payload_end])
        offset = payload_end

    if offset != len(document):
        raise _invalid(document_name)
    return tuple(payloads)


def _decode_ascii(payload: bytes, document_name: str) -> str:
    try:
        return payload.decode("ascii", errors="strict")
    except UnicodeDecodeError:
        raise _invalid(document_name) from None


def _validate_common_payloads(
    payloads: tuple[bytes, ...],
    document_name: str,
) -> ContextKind:
    if len(payloads) != 9:
        raise _invalid(document_name)
    try:
        context_kind = ContextKind(_decode_ascii(payloads[0], document_name))
        scheme = _decode_ascii(payloads[1], document_name)
        challenge_id = _decode_ascii(payloads[2], document_name)
        challenge_version = _decode_ascii(payloads[3], document_name)
        generator_version = _decode_ascii(payloads[4], document_name)
        generator_digest = _decode_ascii(payloads[5], document_name)
        scoring_version = _decode_ascii(payloads[6], document_name)
        scoring_digest = _decode_ascii(payloads[7], document_name)

        registry_model.ChallengeKey(challenge_id, challenge_version)
        registry_model.validate_version(generator_version)
        registry_model.validate_version(scoring_version)
    except (TypeError, ValueError):
        raise _invalid(document_name) from None

    if (
        scheme != SEED_SCHEME_ID
        or not registry_digest.is_sha256_digest(generator_digest)
        or not registry_digest.is_sha256_digest(scoring_digest)
        or len(payloads[8]) != 32
    ):
        raise _invalid(document_name)
    return context_kind


def _validate_document(
    document: object,
    header: bytes,
    expected_tags: tuple[int, ...],
    document_name: str,
    validate_payloads: Callable[[tuple[bytes, ...]], None],
) -> None:
    try:
        payloads = _parse_fields(document, header, expected_tags, document_name)
        validate_payloads(payloads)
    except CanonicalEncodingError:
        raise
    except (AttributeError, IndexError, OverflowError, TypeError, ValueError):
        raise _invalid(document_name) from None


def _validate_seed_info(document: object) -> None:
    """Reject any noncanonical seed-info document without echoing its data."""
    document_name = "seed-info"

    def validate_payloads(payloads: tuple[bytes, ...]) -> None:
        context_kind = _validate_common_payloads(payloads[:9], document_name)
        if len(payloads[11]) != 8:
            raise _invalid(document_name)
        domain = SeedDomain(_decode_ascii(payloads[9], document_name))
        RoleKey(_decode_ascii(payloads[10], document_name))
        int.from_bytes(payloads[11], "big")
        if not _valid_context_domain(context_kind, domain):
            raise _invalid(document_name)

    _validate_document(
        document,
        SEED_INFO_HEADER,
        _SEED_INFO_TAGS,
        document_name,
        validate_payloads,
    )


def _validate_exam_root_info(document: object) -> None:
    """Reject any noncanonical private-exam-root Expand document."""
    document_name = "exam-root-info"

    def validate_payloads(payloads: tuple[bytes, ...]) -> None:
        _validate_common_payloads(payloads, document_name)

    _validate_document(
        document,
        EXAM_ROOT_INFO_HEADER,
        _EXAM_ROOT_INFO_TAGS,
        document_name,
        validate_payloads,
    )


def _validate_exam_commitment_document(document: object) -> None:
    """Reject any noncanonical exam-commitment preimage document."""
    document_name = "exam-commitment"

    def validate_payloads(payloads: tuple[bytes, ...]) -> None:
        _validate_common_payloads(payloads[:9], document_name)
        if len(payloads[9]) != 32:
            raise _invalid(document_name)

    _validate_document(
        document,
        EXAM_COMMITMENT_HEADER,
        _EXAM_COMMITMENT_TAGS,
        document_name,
        validate_payloads,
    )


__all__ = (
    "EXAM_COMMITMENT_HEADER",
    "EXAM_ROOT_INFO_HEADER",
    "SEED_INFO_HEADER",
    "CanonicalEncodingError",
)
