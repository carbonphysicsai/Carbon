"""Stateless RFC 5869 derivation for the separate A4 seed contexts."""

from __future__ import annotations

import hashlib
import hmac

from .encoding import _encode_seed_info
from .model import (
    ContextKind,
    DerivedSeed,
    FixtureOfficialContext,
    FixtureOfficialEntropy,
    MockContext,
    MockEntropy,
    OfficialContext,
    OfficialEntropy,
    QualificationContext,
    QualificationEntropy,
    RoleKey,
    SeedDomain,
    SeedPin,
    SeedValidationError,
)

HKDF_SALT = b"carbon/a4-seeding/hkdf-sha256/v1"
_HASH_LENGTH = hashlib.sha256().digest_size
_MAX_HKDF_OUTPUT = 255 * _HASH_LENGTH


def _invalid_hkdf() -> SeedValidationError:
    return SeedValidationError("invalid HKDF-SHA-256 input")


def _hkdf_extract(salt: object, ikm: object) -> bytes:
    """Return RFC 5869 HKDF-Extract for exact byte inputs."""
    if type(salt) is not bytes or type(ikm) is not bytes:
        raise _invalid_hkdf()
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: object, info: object, length: object) -> bytes:
    """Return bounded RFC 5869 HKDF-Expand output using SHA-256."""
    if (
        type(prk) is not bytes
        or len(prk) < _HASH_LENGTH
        or type(info) is not bytes
        or type(length) is not int
        or length < 0
        or length > _MAX_HKDF_OUTPUT
    ):
        raise _invalid_hkdf()

    output = bytearray()
    previous = b""
    for counter in range(1, (length + _HASH_LENGTH - 1) // _HASH_LENGTH + 1):
        previous = hmac.new(
            prk,
            previous + info + bytes((counter,)),
            hashlib.sha256,
        ).digest()
        output.extend(previous)
    return bytes(output[:length])


def _context_material(
    context: object,
) -> tuple[
    ContextKind,
    SeedPin,
    bytes,
]:
    if type(context) is MockContext:
        expected_kind = ContextKind.MOCK
        expected_entropy_type = MockEntropy
    elif type(context) is OfficialContext:
        expected_kind = ContextKind.OFFICIAL
        expected_entropy_type = OfficialEntropy
    elif type(context) is QualificationContext:
        expected_kind = ContextKind.QUALIFICATION
        expected_entropy_type = QualificationEntropy
    elif type(context) is FixtureOfficialContext:
        expected_kind = ContextKind.FIXTURE_OFFICIAL
        expected_entropy_type = FixtureOfficialEntropy
    else:
        raise SeedValidationError("invalid seed derivation context")

    if (
        context.context_kind is not expected_kind
        or type(context.entropy) is not expected_entropy_type
        or type(context.pin) is not SeedPin
    ):
        raise SeedValidationError("invalid seed derivation context")
    entropy = context.entropy._copy_bytes()
    return context.context_kind, context.pin, entropy


def _extract_context_prk(context: object) -> bytes:
    """Extract a PRK from one exact typed context without retaining its entropy."""
    _, _, entropy = _context_material(context)
    return _hkdf_extract(HKDF_SALT, entropy)


def _expand_seed(prk: object, info: object) -> DerivedSeed:
    """Retain one complete 32-byte role-separated A4 output."""
    return DerivedSeed(_hkdf_expand(prk, info, _HASH_LENGTH))


def _derive_context_seed(
    context: object,
    domain: object,
    role_key: object,
    draw_index: object,
) -> DerivedSeed:
    context_kind, pin, _ = _context_material(context)
    info = _encode_seed_info(
        context_kind,
        pin,
        domain,
        role_key,
        draw_index,
    )
    return _expand_seed(_extract_context_prk(context), info)


def derive_mock_seed(
    context: MockContext,
    role_key: RoleKey,
    draw_index: int,
) -> DerivedSeed:
    """Derive within the mock-only namespace."""
    if type(context) is not MockContext or type(role_key) is not RoleKey:
        raise SeedValidationError("invalid mock seed derivation request")
    return _derive_context_seed(context, SeedDomain.MOCK, role_key, draw_index)


def derive_official_seed(
    context: OfficialContext,
    domain: SeedDomain,
    role_key: RoleKey,
    draw_index: int,
) -> DerivedSeed:
    """Derive one provider-origin official train, eval, or stress seed."""
    if (
        type(context) is not OfficialContext
        or type(domain) is not SeedDomain
        or domain
        not in {
            SeedDomain.OFFICIAL_TRAIN,
            SeedDomain.OFFICIAL_EVAL,
            SeedDomain.OFFICIAL_STRESS,
        }
        or type(role_key) is not RoleKey
    ):
        raise SeedValidationError("invalid official seed derivation request")
    return _derive_context_seed(context, domain, role_key, draw_index)


def derive_fixture_official_seed(
    context: FixtureOfficialContext,
    domain: SeedDomain,
    role_key: RoleKey,
    draw_index: int,
) -> DerivedSeed:
    """Derive an official-shaped seed in the non-emission fixture namespace."""
    if (
        type(context) is not FixtureOfficialContext
        or type(domain) is not SeedDomain
        or domain
        not in {
            SeedDomain.OFFICIAL_TRAIN,
            SeedDomain.OFFICIAL_EVAL,
            SeedDomain.OFFICIAL_STRESS,
        }
        or type(role_key) is not RoleKey
    ):
        raise SeedValidationError("invalid fixture seed derivation request")
    return _derive_context_seed(context, domain, role_key, draw_index)


def derive_qualification_seed(
    context: QualificationContext,
    domain: SeedDomain,
    role_key: RoleKey,
    draw_index: int,
) -> DerivedSeed:
    """Derive only within the reference or dossier qualification namespace."""
    if (
        type(context) is not QualificationContext
        or type(domain) is not SeedDomain
        or domain not in {SeedDomain.REFERENCE, SeedDomain.DOSSIER}
        or type(role_key) is not RoleKey
    ):
        raise SeedValidationError("invalid qualification seed derivation request")
    return _derive_context_seed(context, domain, role_key, draw_index)


__all__ = (
    "HKDF_SALT",
    "derive_fixture_official_seed",
    "derive_mock_seed",
    "derive_official_seed",
    "derive_qualification_seed",
)
