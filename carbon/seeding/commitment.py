"""Private exam-root derivation and value-only public A4 commitments."""

from __future__ import annotations

import hashlib

from carbon.seeding.derive import _extract_context_prk, _hkdf_expand
from carbon.seeding.encoding import (
    _encode_exam_commitment_document,
    _encode_exam_root_info,
)
from carbon.seeding.model import (
    ExamCommitment,
    FixtureOfficialContext,
    FixtureOfficialExamProjection,
    OfficialContext,
    OfficialExamProjection,
    SeedValidationError,
    _PrivateExamRoot,
)

_EXAM_ROOT_LENGTH = 32


def _derive_private_exam_root(context: object) -> _PrivateExamRoot:
    if type(context) not in (OfficialContext, FixtureOfficialContext):
        del context
        raise SeedValidationError("invalid context for exam-root derivation")

    prk = _extract_context_prk(context)
    info = _encode_exam_root_info(context.context_kind, context.pin)
    return _PrivateExamRoot(_hkdf_expand(prk, info, _EXAM_ROOT_LENGTH))


def _build_exam_commitment(context: object) -> ExamCommitment:
    if type(context) not in (OfficialContext, FixtureOfficialContext):
        del context
        raise SeedValidationError("invalid context for exam commitment")

    private_root = _derive_private_exam_root(context)
    document = _encode_exam_commitment_document(
        context.context_kind,
        context.pin,
        private_root,
    )
    tagged_digest = f"sha256:{hashlib.sha256(document).hexdigest()}"
    return ExamCommitment(tagged_digest)


def create_official_exam_projection(
    context: OfficialContext,
) -> OfficialExamProjection:
    """Create a provider-origin public projection with no private references."""
    if type(context) is not OfficialContext:
        del context
        raise SeedValidationError("official projection requires an official context")

    pin = context.pin
    commitment = _build_exam_commitment(context)
    return OfficialExamProjection._from_official_values(
        exam_commitment=commitment,
        challenge_id=pin.challenge_key.challenge_id,
        challenge_version=pin.challenge_key.version,
        generator_version=pin.generator_version,
        generator_digest=pin.generator_digest,
        scoring_version=pin.scoring_version,
        scoring_digest=pin.scoring_digest,
    )


def create_fixture_official_exam_projection(
    context: FixtureOfficialContext,
) -> FixtureOfficialExamProjection:
    """Create an unmistakably fixture-labelled value-only public projection."""
    if type(context) is not FixtureOfficialContext:
        del context
        raise SeedValidationError(
            "fixture projection requires a fixture-official context"
        )

    pin = context.pin
    commitment = _build_exam_commitment(context)
    return FixtureOfficialExamProjection._from_fixture_values(
        exam_commitment=commitment,
        challenge_id=pin.challenge_key.challenge_id,
        challenge_version=pin.challenge_key.version,
        generator_version=pin.generator_version,
        generator_digest=pin.generator_digest,
        scoring_version=pin.scoring_version,
        scoring_digest=pin.scoring_digest,
    )


def serialize_exam_projection(projection: object) -> dict[str, object]:
    """Return the explicit JSON-safe public allow-list for an A4 projection."""
    if type(projection) not in (
        OfficialExamProjection,
        FixtureOfficialExamProjection,
    ):
        del projection
        raise SeedValidationError("unsupported exam projection")

    return {
        "exam_commitment": projection.exam_commitment.to_primitive(),
        "challenge_id": projection.challenge_id,
        "challenge_version": projection.challenge_version,
        "generator_version": projection.generator_version,
        "generator_digest": projection.generator_digest,
        "scoring_version": projection.scoring_version,
        "scoring_digest": projection.scoring_digest,
        "fixture": projection.fixture,
    }


__all__ = (
    "create_fixture_official_exam_projection",
    "create_official_exam_projection",
    "serialize_exam_projection",
)
