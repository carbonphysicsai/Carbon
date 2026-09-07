"""Exact nominal references for the B-E1 fixture harness."""

from __future__ import annotations

from dataclasses import dataclass

from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_version_token,
)
from carbon.registry import ChallengeKey

from .enums import ReproducibilityRefKind
from .errors import ReproducibilityErrorCode, ReproducibilityValidationError

REPRODUCIBILITY_SCHEMA_VERSION = "1.0"
REPRODUCIBILITY_CANONICALIZATION_PROFILE = "carbon_reproducibility_canonical_v1"
REPRODUCIBILITY_DOCUMENT_HEADER = b"carbon.reproducibility.canonical.v1\x00"


def _invalid(path: str, code: ReproducibilityErrorCode):
    return ReproducibilityValidationError(code, path=path)


@dataclass(frozen=True, slots=True, repr=False)
class ReproducibilityRef:
    challenge_key: ChallengeKey
    ref_kind: ReproducibilityRefKind
    object_id: str
    object_version: str
    content_digest: str
    schema_version: str = REPRODUCIBILITY_SCHEMA_VERSION
    canonicalization_profile: str = REPRODUCIBILITY_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        if type(self) is not ReproducibilityRef:
            raise _invalid("/ref_type", ReproducibilityErrorCode.WRONG_TYPE)
        if type(self.ref_kind) is not ReproducibilityRefKind:
            raise _invalid("/ref_kind", ReproducibilityErrorCode.WRONG_TYPE)
        try:
            challenge = reconstruct_challenge_key(self.challenge_key)
            object_id = validate_canonical_id(self.object_id, "object_id")
            version = validate_version_token(self.object_version, "object_version")
            digest = validate_tagged_sha256(self.content_digest, "content_digest")
        except (AttributeError, TypeError, ValueError):
            raise _invalid(
                "/reference", ReproducibilityErrorCode.INVALID_VALUE
            ) from None
        if (
            self.schema_version != REPRODUCIBILITY_SCHEMA_VERSION
            or self.canonicalization_profile != REPRODUCIBILITY_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version", ReproducibilityErrorCode.INVALID_VALUE)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "object_id", object_id)
        object.__setattr__(self, "object_version", version)
        object.__setattr__(self, "content_digest", digest)

    def __repr__(self) -> str:
        return "ReproducibilityRef(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected reproducibility refs cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected reproducibility refs cannot be pickled")
