"""Exact nominal references for B-05 measurement authoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, TypeAlias

from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_version_token,
)
from carbon.registry.model import ChallengeKey

from .enums import MeasurementDefinitionKind
from .errors import MeasurementInputCode, MeasurementValidationError

MEASUREMENT_SCHEMA_VERSION = "1.0"
MEASUREMENT_CANONICALIZATION_PROFILE = "carbon_measurement_canonical_v1"
MEASUREMENT_DOCUMENT_HEADER = b"carbon.measurement.canonical.v1\x00"


def _invalid(
    path: str, code: MeasurementInputCode = MeasurementInputCode.INVALID_VALUE
):
    return MeasurementValidationError(code, path=path)


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, MeasurementInputCode.WRONG_TYPE) from None


def _identifier(value: object, path: str) -> str:
    try:
        return validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _digest(value: object, path: str = "/content_digest") -> str:
    try:
        return validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path) from None


def _profile(schema: object, profile: object) -> tuple[str, str]:
    schema_value = _version(schema, "/schema_version")
    if (
        schema_value != MEASUREMENT_SCHEMA_VERSION
        or type(profile) is not str
        or profile != MEASUREMENT_CANONICALIZATION_PROFILE
    ):
        raise _invalid("/schema_version")
    return schema_value, profile


@dataclass(frozen=True, slots=True, repr=False)
class MeasurementDefinitionRef:
    challenge_key: ChallengeKey
    definition_kind: MeasurementDefinitionKind
    object_id: str
    object_version: str
    content_digest: str
    schema_version: str = MEASUREMENT_SCHEMA_VERSION
    canonicalization_profile: str = MEASUREMENT_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        if type(self) is not MeasurementDefinitionRef:
            raise _invalid("/ref_type", MeasurementInputCode.WRONG_TYPE)
        if type(self.definition_kind) is not MeasurementDefinitionKind:
            raise _invalid("/definition_kind", MeasurementInputCode.WRONG_TYPE)
        schema, profile = _profile(self.schema_version, self.canonicalization_profile)
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "object_id", _identifier(self.object_id, "/object_id"))
        object.__setattr__(
            self, "object_version", _version(self.object_version, "/object_version")
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)

    @property
    def ref_type(self) -> str:
        return "measurement_definition_ref"

    def __repr__(self) -> str:
        return "MeasurementDefinitionRef(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected measurement refs cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected measurement refs cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class _MeasurementTopLevelRef:
    challenge_key: ChallengeKey
    content_digest: str
    schema_version: str = MEASUREMENT_SCHEMA_VERSION
    canonicalization_profile: str = MEASUREMENT_CANONICALIZATION_PROFILE

    RECORD_TYPE: ClassVar[str] = ""

    def __post_init__(self) -> None:
        if type(self) not in MEASUREMENT_TOP_LEVEL_REF_TYPES:
            raise _invalid("/ref_type", MeasurementInputCode.WRONG_TYPE)
        schema, profile = _profile(self.schema_version, self.canonicalization_profile)
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
        raise TypeError("protected measurement refs cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected measurement refs cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class MeasurementContractRef(_MeasurementTopLevelRef):
    RECORD_TYPE: ClassVar[str] = "measurement_contract"


@dataclass(frozen=True, slots=True, repr=False)
class MeasurementQualificationEvidenceRef(_MeasurementTopLevelRef):
    RECORD_TYPE: ClassVar[str] = "measurement_qualification_evidence"


@dataclass(frozen=True, slots=True, repr=False)
class UncertaintyPolicyRef(_MeasurementTopLevelRef):
    RECORD_TYPE: ClassVar[str] = "uncertainty_policy"


@dataclass(frozen=True, slots=True, repr=False)
class ReconstructionEvidencePolicyRef(_MeasurementTopLevelRef):
    RECORD_TYPE: ClassVar[str] = "reconstruction_evidence_policy"


@dataclass(frozen=True, slots=True, repr=False)
class ScorePackAuthoringContractRef(_MeasurementTopLevelRef):
    RECORD_TYPE: ClassVar[str] = "score_pack_authoring_contract"


MEASUREMENT_TOP_LEVEL_REF_TYPES = (
    MeasurementContractRef,
    MeasurementQualificationEvidenceRef,
    UncertaintyPolicyRef,
    ReconstructionEvidencePolicyRef,
    ScorePackAuthoringContractRef,
)

MeasurementTopLevelRef: TypeAlias = (
    MeasurementContractRef
    | MeasurementQualificationEvidenceRef
    | UncertaintyPolicyRef
    | ReconstructionEvidencePolicyRef
    | ScorePackAuthoringContractRef
)


def reconstruct_measurement_ref(value: object) -> MeasurementTopLevelRef:
    if type(value) not in MEASUREMENT_TOP_LEVEL_REF_TYPES:
        raise _invalid("/ref_type", MeasurementInputCode.WRONG_TYPE)
    return type(value)(
        value.challenge_key,
        value.content_digest,
        value.schema_version,
        value.canonicalization_profile,
    )


__all__ = (
    "MEASUREMENT_CANONICALIZATION_PROFILE",
    "MEASUREMENT_DOCUMENT_HEADER",
    "MEASUREMENT_SCHEMA_VERSION",
    "MEASUREMENT_TOP_LEVEL_REF_TYPES",
    "MeasurementContractRef",
    "MeasurementDefinitionRef",
    "MeasurementQualificationEvidenceRef",
    "MeasurementTopLevelRef",
    "ReconstructionEvidencePolicyRef",
    "ScorePackAuthoringContractRef",
    "UncertaintyPolicyRef",
    "reconstruct_measurement_ref",
)
