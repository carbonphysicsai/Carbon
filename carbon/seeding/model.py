"""Typed, immutable values for Carbon's A4 seeding boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from carbon.registry import digest as registry_digest
from carbon.registry import model as registry_model

SEED_SCHEME_ID = "carbon.seed.hkdf-sha256.v1"
_SECRET_LENGTH = 32


class SeedValidationError(ValueError):
    """Stable, non-echoing validation failure for A4 values."""


class SeedDomain(str, Enum):
    """The complete A4 top-level seed-domain set."""

    MOCK = "mock"
    OFFICIAL_TRAIN = "official_train"
    OFFICIAL_EVAL = "official_eval"
    OFFICIAL_STRESS = "official_stress"
    REFERENCE = "reference"
    DOSSIER = "dossier"


class ContextKind(str, Enum):
    """Canonical context namespaces bound into every A4 document."""

    MOCK = "mock"
    OFFICIAL = "official"
    QUALIFICATION = "qualification"
    FIXTURE_OFFICIAL = "fixture_official"


def _copy_exact_32(value: object, field_name: str) -> bytes:
    if type(value) is not bytes or len(value) != _SECRET_LENGTH:
        raise SeedValidationError(f"{field_name} must be exactly 32 bytes")
    return memoryview(value).tobytes()


def _cannot_serialize(type_name: str) -> TypeError:
    return TypeError(f"{type_name} does not support generic serialization")


def _reject_deletion(value: object, name: str) -> None:
    del value, name
    raise AttributeError("A4 value is immutable")


def _reject_state(value: object) -> None:
    raise _cannot_serialize(type(value).__name__)


def _reject_reduce(value: object, protocol: int) -> None:
    del protocol
    raise _cannot_serialize(type(value).__name__)


def _require_uninitialized(value: object, slot_name: str) -> None:
    try:
        object.__getattribute__(value, slot_name)
    except AttributeError:
        return
    raise AttributeError("A4 value is immutable")


class OfficialEntropy:
    """Opaque provider-origin official entropy."""

    __slots__ = ("__material",)

    def __init__(self, value: object) -> None:
        _require_uninitialized(self, "_OfficialEntropy__material")
        object.__setattr__(
            self, "_OfficialEntropy__material", _copy_exact_32(value, "entropy")
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("OfficialEntropy is immutable")

    __delattr__ = _reject_deletion
    __getstate__ = _reject_state

    def __repr__(self) -> str:
        return "OfficialEntropy(<redacted>)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return type(other) is OfficialEntropy and self.__material == other.__material

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _cannot_serialize("OfficialEntropy")

    def _copy_bytes(self) -> bytes:
        return memoryview(self.__material).tobytes()


class MockEntropy:
    """Opaque entropy for the public/mock derivation namespace."""

    __slots__ = ("__material",)

    def __init__(self, value: object) -> None:
        _require_uninitialized(self, "_MockEntropy__material")
        object.__setattr__(
            self, "_MockEntropy__material", _copy_exact_32(value, "entropy")
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("MockEntropy is immutable")

    __delattr__ = _reject_deletion
    __getstate__ = _reject_state

    def __repr__(self) -> str:
        return "MockEntropy(<redacted>)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return type(other) is MockEntropy and self.__material == other.__material

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _cannot_serialize("MockEntropy")

    def _copy_bytes(self) -> bytes:
        return memoryview(self.__material).tobytes()


class QualificationEntropy:
    """Opaque entropy for reference and dossier derivation."""

    __slots__ = ("__material",)

    def __init__(self, value: object) -> None:
        _require_uninitialized(self, "_QualificationEntropy__material")
        object.__setattr__(
            self,
            "_QualificationEntropy__material",
            _copy_exact_32(value, "entropy"),
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("QualificationEntropy is immutable")

    __delattr__ = _reject_deletion
    __getstate__ = _reject_state

    def __repr__(self) -> str:
        return "QualificationEntropy(<redacted>)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is QualificationEntropy and self.__material == other.__material
        )

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _cannot_serialize("QualificationEntropy")

    def _copy_bytes(self) -> bytes:
        return memoryview(self.__material).tobytes()


class FixtureOfficialEntropy:
    """Opaque fixture entropy that cannot satisfy the official entropy type."""

    __slots__ = ("__material",)

    def __init__(self, value: object) -> None:
        _require_uninitialized(self, "_FixtureOfficialEntropy__material")
        object.__setattr__(
            self,
            "_FixtureOfficialEntropy__material",
            _copy_exact_32(value, "entropy"),
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("FixtureOfficialEntropy is immutable")

    __delattr__ = _reject_deletion
    __getstate__ = _reject_state

    def __repr__(self) -> str:
        return "FixtureOfficialEntropy(<redacted>)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is FixtureOfficialEntropy
            and self.__material == other.__material
        )

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _cannot_serialize("FixtureOfficialEntropy")

    def _copy_bytes(self) -> bytes:
        return memoryview(self.__material).tobytes()


class EvaluationBinding:
    """Opaque A7-or-later identity slot bound into A4 derivation."""

    __slots__ = ("__material",)

    def __init__(self, value: object) -> None:
        _require_uninitialized(self, "_EvaluationBinding__material")
        object.__setattr__(
            self,
            "_EvaluationBinding__material",
            _copy_exact_32(value, "evaluation binding"),
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("EvaluationBinding is immutable")

    __delattr__ = _reject_deletion
    __getstate__ = _reject_state

    def __repr__(self) -> str:
        return "EvaluationBinding(<redacted>)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return type(other) is EvaluationBinding and self.__material == other.__material

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _cannot_serialize("EvaluationBinding")

    def _copy_bytes(self) -> bytes:
        return memoryview(self.__material).tobytes()


class DerivedSeed:
    """Complete 32-byte derivation output for a single domain/role/draw."""

    __slots__ = ("__material",)

    def __init__(self, value: object) -> None:
        _require_uninitialized(self, "_DerivedSeed__material")
        object.__setattr__(
            self, "_DerivedSeed__material", _copy_exact_32(value, "derived seed")
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("DerivedSeed is immutable")

    __delattr__ = _reject_deletion
    __getstate__ = _reject_state

    def __repr__(self) -> str:
        return "DerivedSeed(<redacted>)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return type(other) is DerivedSeed and self.__material == other.__material

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _cannot_serialize("DerivedSeed")

    def as_backend_bytes(self) -> bytes:
        """Return a copy for a trusted later backend adapter."""
        return memoryview(self.__material).tobytes()


class _PrivateExamRoot:
    """Private 32-byte root used only while constructing a commitment."""

    __slots__ = ("__material",)

    def __init__(self, value: object) -> None:
        _require_uninitialized(self, "_PrivateExamRoot__material")
        object.__setattr__(
            self,
            "_PrivateExamRoot__material",
            _copy_exact_32(value, "private exam root"),
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("PrivateExamRoot is immutable")

    __delattr__ = _reject_deletion
    __getstate__ = _reject_state

    def __repr__(self) -> str:
        return "PrivateExamRoot(<redacted>)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return type(other) is _PrivateExamRoot and self.__material == other.__material

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _cannot_serialize("PrivateExamRoot")

    def _copy_bytes(self) -> bytes:
        return memoryview(self.__material).tobytes()


class RoleKey:
    """Canonical role beneath one ratified top-level seed domain."""

    __slots__ = ("__value",)

    def __init__(self, value: object) -> None:
        _require_uninitialized(self, "_RoleKey__value")
        if type(value) is not str:
            raise SeedValidationError("role_key must be an exact string")
        try:
            encoded = value.encode("ascii", errors="strict")
        except UnicodeEncodeError:
            encoded = b""
        if not encoded or len(encoded) > 64:
            raise SeedValidationError("role_key must be 1 to 64 ASCII bytes")
        try:
            validated = registry_model.validate_canonical_identifier(value, "role_key")
        except ValueError:
            validated = None
        if validated is None:
            raise SeedValidationError("role_key is not canonical")
        object.__setattr__(self, "_RoleKey__value", validated)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("RoleKey is immutable")

    __delattr__ = _reject_deletion

    @property
    def value(self) -> str:
        return self.__value

    def __str__(self) -> str:
        return self.__value

    def __repr__(self) -> str:
        return f"RoleKey({self.__value!r})"

    def __eq__(self, other: object) -> bool:
        return type(other) is RoleKey and self.__value == other.__value

    def __hash__(self) -> int:
        return hash((RoleKey, self.__value))


def _validated_version(value: object, field_name: str) -> str:
    try:
        validated = registry_model.validate_version(value)
    except ValueError:
        validated = None
    if validated is None:
        raise SeedValidationError(f"{field_name} is not a valid version")
    return validated


def _validated_digest(value: object, field_name: str) -> str:
    if not registry_digest.is_sha256_digest(value):
        raise SeedValidationError(f"{field_name} is not a tagged SHA-256 digest")
    assert type(value) is str
    return value


@dataclass(frozen=True, slots=True, repr=False, init=False)
class SeedPin:
    """Exact immutable challenge/generator/scoring/evaluation seed identity."""

    challenge_key: registry_model.ChallengeKey
    generator_version: str
    generator_digest: str
    scoring_version: str
    scoring_digest: str
    evaluation_binding: EvaluationBinding
    seed_scheme: str = field(default=SEED_SCHEME_ID, init=False)

    def __init__(
        self,
        challenge_key: registry_model.ChallengeKey,
        generator_version: str,
        generator_digest: str,
        scoring_version: str,
        scoring_digest: str,
        evaluation_binding: EvaluationBinding,
    ) -> None:
        _require_uninitialized(self, "challenge_key")
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "generator_version", generator_version)
        object.__setattr__(self, "generator_digest", generator_digest)
        object.__setattr__(self, "scoring_version", scoring_version)
        object.__setattr__(self, "scoring_digest", scoring_digest)
        object.__setattr__(self, "evaluation_binding", evaluation_binding)
        object.__setattr__(self, "seed_scheme", SEED_SCHEME_ID)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.challenge_key) is not registry_model.ChallengeKey:
            raise SeedValidationError("challenge_key must be an exact ChallengeKey")
        try:
            challenge_key = registry_model.ChallengeKey(
                self.challenge_key.challenge_id,
                self.challenge_key.version,
            )
        except (TypeError, ValueError):
            raise SeedValidationError("challenge_key is invalid") from None
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(
            self,
            "generator_version",
            _validated_version(self.generator_version, "generator_version"),
        )
        object.__setattr__(
            self,
            "generator_digest",
            _validated_digest(self.generator_digest, "generator_digest"),
        )
        object.__setattr__(
            self,
            "scoring_version",
            _validated_version(self.scoring_version, "scoring_version"),
        )
        object.__setattr__(
            self,
            "scoring_digest",
            _validated_digest(self.scoring_digest, "scoring_digest"),
        )
        if type(self.evaluation_binding) is not EvaluationBinding:
            raise SeedValidationError(
                "evaluation_binding must be an exact EvaluationBinding"
            )
        object.__setattr__(
            self,
            "evaluation_binding",
            EvaluationBinding(self.evaluation_binding._copy_bytes()),
        )

    def __repr__(self) -> str:
        return "SeedPin(<redacted>)"

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce

    def _copy(self) -> SeedPin:
        return SeedPin(
            self.challenge_key,
            self.generator_version,
            self.generator_digest,
            self.scoring_version,
            self.scoring_digest,
            self.evaluation_binding,
        )


@dataclass(frozen=True, slots=True, repr=False, init=False)
class MockContext:
    """Mock-only derivation context."""

    entropy: MockEntropy
    pin: SeedPin
    context_kind: ContextKind = field(default=ContextKind.MOCK, init=False)

    def __init__(self, entropy: MockEntropy, pin: SeedPin) -> None:
        _require_uninitialized(self, "entropy")
        object.__setattr__(self, "entropy", entropy)
        object.__setattr__(self, "pin", pin)
        object.__setattr__(self, "context_kind", ContextKind.MOCK)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.entropy) is not MockEntropy or type(self.pin) is not SeedPin:
            raise SeedValidationError("invalid mock context")
        object.__setattr__(self, "entropy", MockEntropy(self.entropy._copy_bytes()))
        object.__setattr__(self, "pin", self.pin._copy())

    def __repr__(self) -> str:
        return "MockContext(<redacted>)"

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True, repr=False, init=False)
class QualificationContext:
    """Reference/dossier-only derivation context."""

    entropy: QualificationEntropy
    pin: SeedPin
    context_kind: ContextKind = field(default=ContextKind.QUALIFICATION, init=False)

    def __init__(self, entropy: QualificationEntropy, pin: SeedPin) -> None:
        _require_uninitialized(self, "entropy")
        object.__setattr__(self, "entropy", entropy)
        object.__setattr__(self, "pin", pin)
        object.__setattr__(self, "context_kind", ContextKind.QUALIFICATION)
        self.__post_init__()

    def __post_init__(self) -> None:
        if (
            type(self.entropy) is not QualificationEntropy
            or type(self.pin) is not SeedPin
        ):
            raise SeedValidationError("invalid qualification context")
        object.__setattr__(
            self,
            "entropy",
            QualificationEntropy(self.entropy._copy_bytes()),
        )
        object.__setattr__(self, "pin", self.pin._copy())

    def __repr__(self) -> str:
        return "QualificationContext(<redacted>)"

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True, repr=False, init=False)
class OfficialContext:
    """Provider-acquired official context; direct construction is unsupported."""

    entropy: OfficialEntropy
    pin: SeedPin
    context_kind: ContextKind = field(default=ContextKind.OFFICIAL, init=False)

    def __init__(self, entropy: object, pin: object) -> None:
        del entropy, pin
        raise TypeError("OfficialContext must be acquired from a BeaconProvider")

    @classmethod
    def _from_observation(
        cls, entropy: OfficialEntropy, pin: SeedPin
    ) -> OfficialContext:
        if type(entropy) is not OfficialEntropy or type(pin) is not SeedPin:
            raise SeedValidationError("invalid official context")
        context = object.__new__(cls)
        object.__setattr__(context, "entropy", OfficialEntropy(entropy._copy_bytes()))
        object.__setattr__(context, "pin", pin._copy())
        object.__setattr__(context, "context_kind", ContextKind.OFFICIAL)
        return context

    def __repr__(self) -> str:
        return "OfficialContext(<redacted>)"

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


@dataclass(frozen=True, slots=True, repr=False, init=False)
class FixtureOfficialContext:
    """Fixture-only official-shaped context with immutable fixture provenance."""

    entropy: FixtureOfficialEntropy
    pin: SeedPin
    context_kind: ContextKind = field(default=ContextKind.FIXTURE_OFFICIAL, init=False)

    def __init__(self, entropy: object, pin: object) -> None:
        del entropy, pin
        raise TypeError(
            "FixtureOfficialContext must be acquired from a fixture provider"
        )

    @classmethod
    def _from_fixture(
        cls, entropy: FixtureOfficialEntropy, pin: SeedPin
    ) -> FixtureOfficialContext:
        if type(entropy) is not FixtureOfficialEntropy or type(pin) is not SeedPin:
            raise SeedValidationError("invalid fixture official context")
        context = object.__new__(cls)
        object.__setattr__(
            context,
            "entropy",
            FixtureOfficialEntropy(entropy._copy_bytes()),
        )
        object.__setattr__(context, "pin", pin._copy())
        object.__setattr__(context, "context_kind", ContextKind.FIXTURE_OFFICIAL)
        return context

    def __repr__(self) -> str:
        return "FixtureOfficialContext(<redacted>)"

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce


class ExamCommitment:
    """Opaque public tagged digest of a canonical A4 commitment document."""

    __slots__ = ("__value",)

    def __init__(self, value: object) -> None:
        _require_uninitialized(self, "_ExamCommitment__value")
        if not registry_digest.is_sha256_digest(value):
            raise SeedValidationError("exam commitment is not a tagged SHA-256 digest")
        assert type(value) is str
        object.__setattr__(self, "_ExamCommitment__value", value)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("ExamCommitment is immutable")

    __delattr__ = _reject_deletion

    @property
    def value(self) -> str:
        return self.__value

    def to_primitive(self) -> str:
        """Return the intentionally public tagged digest."""
        return self.__value

    def __str__(self) -> str:
        return self.__value

    def __repr__(self) -> str:
        return f"ExamCommitment({self.__value!r})"

    def __eq__(self, other: object) -> bool:
        return type(other) is ExamCommitment and self.__value == other.__value

    def __hash__(self) -> int:
        return hash((ExamCommitment, self.__value))


def _validate_projection_fields(
    commitment: object,
    challenge_id: object,
    challenge_version: object,
    generator_version: object,
    generator_digest: object,
    scoring_version: object,
    scoring_digest: object,
) -> None:
    if type(commitment) is not ExamCommitment:
        raise SeedValidationError("invalid exam commitment projection")
    try:
        registry_model.ChallengeKey(challenge_id, challenge_version)
    except (TypeError, ValueError):
        raise SeedValidationError("invalid public challenge projection") from None
    _validated_version(generator_version, "generator_version")
    _validated_digest(generator_digest, "generator_digest")
    _validated_version(scoring_version, "scoring_version")
    _validated_digest(scoring_digest, "scoring_digest")


@dataclass(frozen=True, slots=True, init=False)
class OfficialExamProjection:
    """Value-only public projection for provider-origin official contexts."""

    exam_commitment: ExamCommitment
    challenge_id: str
    challenge_version: str
    generator_version: str
    generator_digest: str
    scoring_version: str
    scoring_digest: str
    fixture: bool = field(default=False, init=False)

    def __init__(
        self,
        exam_commitment: object,
        challenge_id: object,
        challenge_version: object,
        generator_version: object,
        generator_digest: object,
        scoring_version: object,
        scoring_digest: object,
    ) -> None:
        del (
            exam_commitment,
            challenge_id,
            challenge_version,
            generator_version,
            generator_digest,
            scoring_version,
            scoring_digest,
        )
        raise TypeError(
            "OfficialExamProjection must be created from an official context"
        )

    @classmethod
    def _from_official_values(
        cls,
        exam_commitment: ExamCommitment,
        challenge_id: str,
        challenge_version: str,
        generator_version: str,
        generator_digest: str,
        scoring_version: str,
        scoring_digest: str,
    ) -> OfficialExamProjection:
        _validate_projection_fields(
            exam_commitment,
            challenge_id,
            challenge_version,
            generator_version,
            generator_digest,
            scoring_version,
            scoring_digest,
        )
        projection = object.__new__(cls)
        object.__setattr__(
            projection,
            "exam_commitment",
            ExamCommitment(exam_commitment.value),
        )
        object.__setattr__(projection, "challenge_id", challenge_id)
        object.__setattr__(projection, "challenge_version", challenge_version)
        object.__setattr__(projection, "generator_version", generator_version)
        object.__setattr__(projection, "generator_digest", generator_digest)
        object.__setattr__(projection, "scoring_version", scoring_version)
        object.__setattr__(projection, "scoring_digest", scoring_digest)
        object.__setattr__(projection, "fixture", False)
        return projection


@dataclass(frozen=True, slots=True, init=False)
class FixtureOfficialExamProjection:
    """Value-only public projection with immutable fixture identification."""

    exam_commitment: ExamCommitment
    challenge_id: str
    challenge_version: str
    generator_version: str
    generator_digest: str
    scoring_version: str
    scoring_digest: str
    fixture: bool = field(default=True, init=False)

    def __init__(
        self,
        exam_commitment: object,
        challenge_id: object,
        challenge_version: object,
        generator_version: object,
        generator_digest: object,
        scoring_version: object,
        scoring_digest: object,
    ) -> None:
        del (
            exam_commitment,
            challenge_id,
            challenge_version,
            generator_version,
            generator_digest,
            scoring_version,
            scoring_digest,
        )
        raise TypeError(
            "FixtureOfficialExamProjection must be created from a fixture context"
        )

    @classmethod
    def _from_fixture_values(
        cls,
        exam_commitment: ExamCommitment,
        challenge_id: str,
        challenge_version: str,
        generator_version: str,
        generator_digest: str,
        scoring_version: str,
        scoring_digest: str,
    ) -> FixtureOfficialExamProjection:
        _validate_projection_fields(
            exam_commitment,
            challenge_id,
            challenge_version,
            generator_version,
            generator_digest,
            scoring_version,
            scoring_digest,
        )
        projection = object.__new__(cls)
        object.__setattr__(
            projection,
            "exam_commitment",
            ExamCommitment(exam_commitment.value),
        )
        object.__setattr__(projection, "challenge_id", challenge_id)
        object.__setattr__(projection, "challenge_version", challenge_version)
        object.__setattr__(projection, "generator_version", generator_version)
        object.__setattr__(projection, "generator_digest", generator_digest)
        object.__setattr__(projection, "scoring_version", scoring_version)
        object.__setattr__(projection, "scoring_digest", scoring_digest)
        object.__setattr__(projection, "fixture", True)
        return projection


__all__ = (
    "SEED_SCHEME_ID",
    "ContextKind",
    "DerivedSeed",
    "EvaluationBinding",
    "ExamCommitment",
    "FixtureOfficialContext",
    "FixtureOfficialEntropy",
    "FixtureOfficialExamProjection",
    "MockContext",
    "MockEntropy",
    "OfficialContext",
    "OfficialEntropy",
    "OfficialExamProjection",
    "QualificationContext",
    "QualificationEntropy",
    "RoleKey",
    "SeedDomain",
    "SeedPin",
    "SeedValidationError",
)
