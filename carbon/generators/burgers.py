"""Fixed, structural-only Burgers fixture values for B-03.

This module deliberately implements no Burgers solver, reference answer,
measurement, score, target-population law, or production configuration.  Its
only numeric operation is the contract's small, exactly representable latent
codec from one A4 ``DerivedSeed`` to eight protected initial values.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import final

from carbon.authoring.cases import CanonicalChallengeCase
from carbon.authoring.errors import AuthoringError
from carbon.authoring.loading import (
    AuthoringGraphOrigin,
    GraphOriginTag,
    LoadedAuthoringArtifact,
    compose_authoring_graph_origin,
    load_authoring_bytes,
)
from carbon.authoring.model import ApplicabilityBinding
from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_finite_float64,
    validate_int64,
    validate_tagged_sha256,
    validate_uint64,
)
from carbon.authoring.refs import (
    CanonicalChallengeCaseRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    SamplingPlanRef,
    require_owner_ref,
)
from carbon.registry.model import ChallengeKey
from carbon.seeding.model import DerivedSeed

from .errors import GeneratorInputCode, GeneratorValidationError
from .refs import (
    BurgersFixtureConfigurationRef,
    PhysicalPayloadFingerprintRef,
    reconstruct_generator_ref,
)

BURGERS_FIXTURE_CONFIGURATION_ID = "b03_burgers_structural_fixture"
BURGERS_FIXTURE_CONFIGURATION_VERSION = "1.0"
BURGERS_FIXTURE_BOUNDARY_SHAPE = "PERIODIC_1D"
BURGERS_FIXTURE_PERIOD = 1.0
BURGERS_FIXTURE_GRID_POINTS = 8
BURGERS_FIXTURE_VISCOSITY = 1.0
BURGERS_FIXTURE_LATENT_CODEC_ID = "carbon.b03.burgers.fixture-latent.v1"
BURGERS_FIXTURE_BASIS_1 = (0, 1, 1, 0, -1, -1, 0, 0)
BURGERS_FIXTURE_BASIS_2 = (1, 1, 0, -1, -1, 0, 1, 0)

_CONFIGURATION_TOKEN = object()
_PRODUCTION_INPUTS_TOKEN = object()
_PROTECTED_PAYLOAD_TOKEN = object()
_FINGERPRINT_TOKEN = object()
_DEGENERACY_TOKEN = object()
_PAYLOAD_FACTS_TOKEN = object()
_VALIDATED_CASE_FACTS_TOKEN = object()
_GENERATED_ARTIFACT_TOKEN = object()


def _wrong(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.WRONG_TYPE, path=path)


def _invalid(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.INVALID_VALUE, path=path)


def _cross_challenge(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.CROSS_CHALLENGE, path=path)


def _stale(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.STALE_BINDING, path=path)


def _incomplete(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.INCOMPLETE_BINDING, path=path)


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        result = reconstruct_challenge_key(value)
    except (AuthoringError, TypeError, ValueError):
        pass
    else:
        return result
    raise _wrong(path)


def _uint64(value: object, path: str) -> int:
    try:
        result = validate_uint64(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    else:
        return result
    raise _invalid(path)


def _int64(value: object, path: str) -> int:
    try:
        result = validate_int64(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    else:
        return result
    raise _invalid(path)


def _float64(value: object, path: str) -> float:
    try:
        result = validate_finite_float64(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    else:
        return result
    raise _invalid(path)


def _digest(value: object, path: str) -> str:
    try:
        result = validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    else:
        return result
    raise _invalid(path)


def _configuration_ref(
    value: object,
    path: str = "/fixture_configuration_ref",
) -> BurgersFixtureConfigurationRef:
    if type(value) is not BurgersFixtureConfigurationRef:
        raise _wrong(path)
    try:
        copied = reconstruct_generator_ref(value)
    except (GeneratorValidationError, TypeError, ValueError):
        copied = None
    if copied is None:
        raise _wrong(path)
    if type(copied) is not BurgersFixtureConfigurationRef:
        raise _wrong(path)
    return copied


def _fingerprint_ref(
    value: object,
    path: str = "/physical_payload_fingerprint_ref",
) -> PhysicalPayloadFingerprintRef:
    if type(value) is not PhysicalPayloadFingerprintRef:
        raise _wrong(path)
    try:
        copied = reconstruct_generator_ref(value)
    except (GeneratorValidationError, TypeError, ValueError):
        copied = None
    if copied is None:
        raise _wrong(path)
    if type(copied) is not PhysicalPayloadFingerprintRef:
        raise _wrong(path)
    return copied


def _owner_ref(
    value: object,
    *,
    kind: str,
    path: str,
    challenge_key: ChallengeKey | None = None,
) -> object:
    try:
        copied = require_owner_ref(value, kind)
    except (AuthoringError, TypeError, ValueError):
        copied = None
    if copied is None:
        raise _wrong(path)
    scope = object.__getattribute__(copied, "scope_binding")
    if type(scope) is not ChallengeScope:
        raise _cross_challenge(path)
    if challenge_key is not None and scope.challenge_key != challenge_key:
        raise _cross_challenge(path)
    return copied


def _protected_repr(type_name: str) -> str:
    return f"{type_name}(<protected>)"


def _reject_pickle(message: str) -> None:
    raise TypeError(message)


@final
@dataclass(frozen=True, slots=True, init=False)
class BurgersFixtureConfiguration:
    """The one challenge-neutral B-03 v1 structural fixture recipe."""

    configuration_id: str
    configuration_version: str
    boundary_shape: str
    period: float
    grid_points: int
    viscosity: float
    latent_codec_id: str
    basis_1: tuple[int, ...]
    basis_2: tuple[int, ...]

    def __init__(self, *, _token: object) -> None:
        if (
            type(self) is not BurgersFixtureConfiguration
            or _token is not _CONFIGURATION_TOKEN
        ):
            raise _wrong("/fixture_configuration")
        object.__setattr__(self, "configuration_id", BURGERS_FIXTURE_CONFIGURATION_ID)
        object.__setattr__(
            self,
            "configuration_version",
            BURGERS_FIXTURE_CONFIGURATION_VERSION,
        )
        object.__setattr__(self, "boundary_shape", BURGERS_FIXTURE_BOUNDARY_SHAPE)
        object.__setattr__(self, "period", BURGERS_FIXTURE_PERIOD)
        object.__setattr__(self, "grid_points", BURGERS_FIXTURE_GRID_POINTS)
        object.__setattr__(self, "viscosity", BURGERS_FIXTURE_VISCOSITY)
        object.__setattr__(self, "latent_codec_id", BURGERS_FIXTURE_LATENT_CODEC_ID)
        object.__setattr__(self, "basis_1", BURGERS_FIXTURE_BASIS_1)
        object.__setattr__(self, "basis_2", BURGERS_FIXTURE_BASIS_2)

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(
        self,
        challenge_key: ChallengeKey,
    ) -> BurgersFixtureConfigurationRef:
        from .canonical import _record_ref

        ref = _record_ref(
            self,
            BurgersFixtureConfigurationRef,
            challenge_key=_challenge(challenge_key),
        )
        if type(ref) is not BurgersFixtureConfigurationRef:
            raise _wrong("/fixture_configuration_ref")
        return ref


_BURGERS_FIXTURE_CONFIGURATION = BurgersFixtureConfiguration(
    _token=_CONFIGURATION_TOKEN
)


def burgers_fixture_configuration() -> BurgersFixtureConfiguration:
    """Return the immutable, challenge-neutral v1 fixture recipe."""

    return _BURGERS_FIXTURE_CONFIGURATION


def burgers_fixture_configuration_ref(
    challenge_key: ChallengeKey,
) -> BurgersFixtureConfigurationRef:
    """Bind the fixed v1 recipe identity to one exact Challenge."""

    return _BURGERS_FIXTURE_CONFIGURATION.to_ref(challenge_key)


class ProductionInputAvailability(str, Enum):
    """Closed availability marker for deliberately unratified real inputs."""

    HUMAN_INPUT_REQUIRED = "HUMAN_INPUT_REQUIRED"


@final
@dataclass(frozen=True, slots=True, init=False)
class BurgersProductionInputsUnavailable:
    """Fixed fail-closed report; it is not a configuration or a case."""

    primary_population_law: ProductionInputAvailability
    selection_population_law: ProductionInputAvailability
    selection_density_or_mass: ProductionInputAvailability
    importance_weight: ProductionInputAvailability
    viscosity: ProductionInputAvailability
    parameter_ranges: ProductionInputAvailability
    forcing_law: ProductionInputAvailability
    initial_condition_law: ProductionInputAvailability
    grid_specification: ProductionInputAvailability
    horizon_specification: ProductionInputAvailability
    stratification: ProductionInputAvailability
    exclusions: ProductionInputAvailability
    conformance_estimands: ProductionInputAvailability
    conformance_thresholds: ProductionInputAvailability
    qualification_evidence: ProductionInputAvailability

    def __init__(self, *, _token: object) -> None:
        if (
            type(self) is not BurgersProductionInputsUnavailable
            or _token is not _PRODUCTION_INPUTS_TOKEN
        ):
            raise _wrong("/production_inputs")
        unavailable = ProductionInputAvailability.HUMAN_INPUT_REQUIRED
        for name in (
            "primary_population_law",
            "selection_population_law",
            "selection_density_or_mass",
            "importance_weight",
            "viscosity",
            "parameter_ranges",
            "forcing_law",
            "initial_condition_law",
            "grid_specification",
            "horizon_specification",
            "stratification",
            "exclusions",
            "conformance_estimands",
            "conformance_thresholds",
            "qualification_evidence",
        ):
            object.__setattr__(self, name, unavailable)


_BURGERS_PRODUCTION_INPUTS_UNAVAILABLE = BurgersProductionInputsUnavailable(
    _token=_PRODUCTION_INPUTS_TOKEN
)


def burgers_production_inputs_unavailable() -> BurgersProductionInputsUnavailable:
    """Return the immutable report for every unratified production input."""

    return _BURGERS_PRODUCTION_INPUTS_UNAVAILABLE


def _decode_burgers_fixture_configuration(
    *,
    configuration_id: object,
    configuration_version: object,
    boundary_shape: object,
    period: object,
    grid_points: object,
    viscosity: object,
    latent_codec_id: object,
    basis_1: object,
    basis_2: object,
) -> BurgersFixtureConfiguration:
    """Accept canonical bytes only when they name the one fixed v1 recipe."""

    if (
        type(configuration_id) is not str
        or type(configuration_version) is not str
        or type(boundary_shape) is not str
        or type(period) is not float
        or type(grid_points) is not int
        or type(viscosity) is not float
        or type(latent_codec_id) is not str
        or type(basis_1) is not tuple
        or any(type(item) is not int for item in basis_1)
        or type(basis_2) is not tuple
        or any(type(item) is not int for item in basis_2)
    ):
        raise _invalid("/fixture_configuration")
    expected = _BURGERS_FIXTURE_CONFIGURATION
    actual = (
        configuration_id,
        configuration_version,
        boundary_shape,
        period,
        grid_points,
        viscosity,
        latent_codec_id,
        basis_1,
        basis_2,
    )
    fixed = (
        expected.configuration_id,
        expected.configuration_version,
        expected.boundary_shape,
        expected.period,
        expected.grid_points,
        expected.viscosity,
        expected.latent_codec_id,
        expected.basis_1,
        expected.basis_2,
    )
    if actual != fixed:
        raise _invalid("/fixture_configuration")
    return expected


def _initial_values(value: object) -> tuple[float, ...]:
    if type(value) is not tuple or len(value) != BURGERS_FIXTURE_GRID_POINTS:
        raise _invalid("/initial_values")
    checked = tuple(
        _float64(item, f"/initial_values/{index}") for index, item in enumerate(value)
    )

    # The only structurally valid payloads lie on the exact v1 codec lattice.
    scaled_n2 = checked[0] * 4096.0
    scaled_n1 = checked[2] * 4096.0
    if not scaled_n1.is_integer() or not scaled_n2.is_integer():
        raise _invalid("/initial_values")
    n1 = int(scaled_n1)
    n2 = int(scaled_n2)
    if not -1000 <= n1 <= 1000 or not -1000 <= n2 <= 1000:
        raise _invalid("/initial_values")
    expected = tuple(
        (n1 * basis_1 + n2 * basis_2) / 4096.0
        for basis_1, basis_2 in zip(
            BURGERS_FIXTURE_BASIS_1,
            BURGERS_FIXTURE_BASIS_2,
            strict=True,
        )
    )
    if checked != expected:
        raise _invalid("/initial_values")
    return checked


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class ProtectedBurgersFixturePayload:
    """Protected fixture input; never a reference answer or candidate output."""

    fixture_configuration_ref: BurgersFixtureConfigurationRef
    period: float
    grid_points: int
    viscosity: float
    initial_values: tuple[float, ...]

    def __init__(
        self,
        *,
        fixture_configuration_ref: object,
        period: object,
        grid_points: object,
        viscosity: object,
        initial_values: object,
        _token: object,
    ) -> None:
        if (
            type(self) is not ProtectedBurgersFixturePayload
            or _token is not _PROTECTED_PAYLOAD_TOKEN
        ):
            raise _wrong("/protected_payload")
        configuration_ref = _configuration_ref(fixture_configuration_ref)
        if configuration_ref != burgers_fixture_configuration_ref(
            configuration_ref.challenge_key
        ):
            raise _stale("/fixture_configuration_ref")
        checked_period = _float64(period, "/period")
        checked_points = _uint64(grid_points, "/grid_points")
        checked_viscosity = _float64(viscosity, "/viscosity")
        if (
            checked_period != BURGERS_FIXTURE_PERIOD
            or checked_points != BURGERS_FIXTURE_GRID_POINTS
            or checked_viscosity != BURGERS_FIXTURE_VISCOSITY
        ):
            raise _invalid("/protected_payload")
        object.__setattr__(self, "fixture_configuration_ref", configuration_ref)
        object.__setattr__(self, "period", checked_period)
        object.__setattr__(self, "grid_points", checked_points)
        object.__setattr__(self, "viscosity", checked_viscosity)
        object.__setattr__(self, "initial_values", _initial_values(initial_values))

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def __repr__(self) -> str:
        return _protected_repr(type(self).__name__)

    __str__ = __repr__

    def __reduce__(self):
        _reject_pickle("protected Burgers fixture payloads cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        _reject_pickle("protected Burgers fixture payloads cannot be pickled")


def _new_protected_payload(
    *,
    fixture_configuration_ref: object,
    period: object,
    grid_points: object,
    viscosity: object,
    initial_values: object,
) -> ProtectedBurgersFixturePayload:
    return ProtectedBurgersFixturePayload(
        fixture_configuration_ref=fixture_configuration_ref,
        period=period,
        grid_points=grid_points,
        viscosity=viscosity,
        initial_values=initial_values,
        _token=_PROTECTED_PAYLOAD_TOKEN,
    )


def _materialize_burgers_fixture_payload(
    seed: DerivedSeed,
    *,
    fixture_configuration_ref: BurgersFixtureConfigurationRef,
) -> ProtectedBurgersFixturePayload:
    """Privately map one exact A4 derived seed to the fixed fixture lattice."""

    if type(seed) is not DerivedSeed:
        raise _wrong("/derived_seed")
    configuration_ref = _configuration_ref(fixture_configuration_ref)
    expected_configuration_ref = burgers_fixture_configuration_ref(
        configuration_ref.challenge_key
    )
    if configuration_ref != expected_configuration_ref:
        raise _stale("/fixture_configuration_ref")

    material = seed.as_backend_bytes()
    if type(material) is not bytes or len(material) != 32:
        raise _invalid("/derived_seed")
    w1 = int.from_bytes(material[0:8], "big", signed=False)
    w2 = int.from_bytes(material[8:16], "big", signed=False)
    del material

    n1 = (w1 % 2001) - 1000
    n2 = (w2 % 2001) - 1000
    del w1, w2
    initial_values = tuple(
        (n1 * basis_1 + n2 * basis_2) / 4096.0
        for basis_1, basis_2 in zip(
            BURGERS_FIXTURE_BASIS_1,
            BURGERS_FIXTURE_BASIS_2,
            strict=True,
        )
    )
    del n1, n2
    return _new_protected_payload(
        fixture_configuration_ref=configuration_ref,
        period=BURGERS_FIXTURE_PERIOD,
        grid_points=BURGERS_FIXTURE_GRID_POINTS,
        viscosity=BURGERS_FIXTURE_VISCOSITY,
        initial_values=initial_values,
    )


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class PhysicalPayloadFingerprint:
    """Attempt-independent protected identity for one physical fixture payload."""

    challenge_key: ChallengeKey
    case_representation_ref: object
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    protected_payload_digest: str

    def __init__(
        self,
        *,
        challenge_key: object,
        case_representation_ref: object,
        fixture_configuration_ref: object,
        protected_payload_digest: object,
        _token: object,
    ) -> None:
        if (
            type(self) is not PhysicalPayloadFingerprint
            or _token is not _FINGERPRINT_TOKEN
        ):
            raise _wrong("/physical_payload_fingerprint")
        key = _challenge(challenge_key)
        representation_ref = _owner_ref(
            case_representation_ref,
            kind="representation",
            path="/case_representation_ref",
            challenge_key=key,
        )
        configuration_ref = _configuration_ref(fixture_configuration_ref)
        if configuration_ref.challenge_key != key:
            raise _cross_challenge("/fixture_configuration_ref")
        if configuration_ref != burgers_fixture_configuration_ref(key):
            raise _stale("/fixture_configuration_ref")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "case_representation_ref", representation_ref)
        object.__setattr__(self, "fixture_configuration_ref", configuration_ref)
        object.__setattr__(
            self,
            "protected_payload_digest",
            _digest(protected_payload_digest, "/protected_payload_digest"),
        )

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> PhysicalPayloadFingerprintRef:
        from .canonical import _record_ref

        ref = _record_ref(self, PhysicalPayloadFingerprintRef)
        if type(ref) is not PhysicalPayloadFingerprintRef:
            raise _wrong("/physical_payload_fingerprint_ref")
        return ref

    def __repr__(self) -> str:
        return _protected_repr(type(self).__name__)

    __str__ = __repr__

    def __reduce__(self):
        _reject_pickle("physical payload fingerprints cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        _reject_pickle("physical payload fingerprints cannot be pickled")


def _new_physical_payload_fingerprint(
    *,
    challenge_key: object,
    case_representation_ref: object,
    fixture_configuration_ref: object,
    protected_payload_digest: object,
) -> PhysicalPayloadFingerprint:
    return PhysicalPayloadFingerprint(
        challenge_key=challenge_key,
        case_representation_ref=case_representation_ref,
        fixture_configuration_ref=fixture_configuration_ref,
        protected_payload_digest=protected_payload_digest,
        _token=_FINGERPRINT_TOKEN,
    )


def build_physical_payload_fingerprint(
    *,
    challenge_key: ChallengeKey,
    case_representation_ref: object,
    fixture_configuration_ref: BurgersFixtureConfigurationRef,
    protected_payload: ProtectedBurgersFixturePayload,
) -> PhysicalPayloadFingerprint:
    """Derive the protected physical identity from full canonical payload bytes."""

    if type(protected_payload) is not ProtectedBurgersFixturePayload:
        raise _wrong("/protected_payload")
    key = _challenge(challenge_key)
    configuration_ref = _configuration_ref(fixture_configuration_ref)
    if configuration_ref.challenge_key != key:
        raise _cross_challenge("/fixture_configuration_ref")
    if configuration_ref != burgers_fixture_configuration_ref(key):
        raise _stale("/fixture_configuration_ref")
    if protected_payload.fixture_configuration_ref != configuration_ref:
        raise _stale("/protected_payload/fixture_configuration_ref")
    from .canonical import canonical_content_digest

    return _new_physical_payload_fingerprint(
        challenge_key=key,
        case_representation_ref=case_representation_ref,
        fixture_configuration_ref=configuration_ref,
        protected_payload_digest=canonical_content_digest(protected_payload),
    )


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class FixtureDegeneracyFacts:
    """Payload-local mechanical observations, never acceptance criteria."""

    distinct_initial_value_count: int
    all_initial_values_zero: bool
    all_initial_values_identical: bool

    def __init__(
        self,
        *,
        distinct_initial_value_count: object,
        all_initial_values_zero: object,
        all_initial_values_identical: object,
        _token: object,
    ) -> None:
        if type(self) is not FixtureDegeneracyFacts or _token is not _DEGENERACY_TOKEN:
            raise _wrong("/degeneracy_facts")
        distinct = _uint64(
            distinct_initial_value_count,
            "/distinct_initial_value_count",
        )
        if not 1 <= distinct <= BURGERS_FIXTURE_GRID_POINTS:
            raise _invalid("/distinct_initial_value_count")
        if type(all_initial_values_zero) is not bool:
            raise _wrong("/all_initial_values_zero")
        if type(all_initial_values_identical) is not bool:
            raise _wrong("/all_initial_values_identical")
        if all_initial_values_identical != (distinct == 1):
            raise _invalid("/all_initial_values_identical")
        if all_initial_values_zero and not all_initial_values_identical:
            raise _invalid("/all_initial_values_zero")
        object.__setattr__(self, "distinct_initial_value_count", distinct)
        object.__setattr__(self, "all_initial_values_zero", all_initial_values_zero)
        object.__setattr__(
            self,
            "all_initial_values_identical",
            all_initial_values_identical,
        )

    def __repr__(self) -> str:
        return "FixtureDegeneracyFacts(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("protected degeneracy facts cannot be pickled")


def _fixture_degeneracy_facts(
    initial_values: tuple[float, ...],
) -> FixtureDegeneracyFacts:
    checked = _initial_values(initial_values)
    distinct = len(set(checked))
    return FixtureDegeneracyFacts(
        distinct_initial_value_count=distinct,
        all_initial_values_zero=all(value == 0.0 for value in checked),
        all_initial_values_identical=distinct == 1,
        _token=_DEGENERACY_TOKEN,
    )


def _new_fixture_degeneracy_facts(
    *,
    distinct_initial_value_count: object,
    all_initial_values_zero: object,
    all_initial_values_identical: object,
) -> FixtureDegeneracyFacts:
    return FixtureDegeneracyFacts(
        distinct_initial_value_count=distinct_initial_value_count,
        all_initial_values_zero=all_initial_values_zero,
        all_initial_values_identical=all_initial_values_identical,
        _token=_DEGENERACY_TOKEN,
    )


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class FixturePayloadFacts:
    """Fixed-order, fact-only summary of a protected fixture payload."""

    protected_payload_ref: object
    physical_payload_fingerprint: PhysicalPayloadFingerprint
    physical_payload_fingerprint_ref: PhysicalPayloadFingerprintRef
    fixture_configuration_ref: BurgersFixtureConfigurationRef
    spatial_point_count: int
    time_point_count: int
    initial_value_count: int
    degeneracy_facts: FixtureDegeneracyFacts

    def __init__(
        self,
        *,
        protected_payload_ref: object,
        physical_payload_fingerprint: object,
        physical_payload_fingerprint_ref: object,
        fixture_configuration_ref: object,
        spatial_point_count: object,
        time_point_count: object,
        initial_value_count: object,
        degeneracy_facts: object,
        _token: object,
    ) -> None:
        if type(self) is not FixturePayloadFacts or _token is not _PAYLOAD_FACTS_TOKEN:
            raise _wrong("/fixture_payload_facts")
        if type(physical_payload_fingerprint) is not PhysicalPayloadFingerprint:
            raise _wrong("/physical_payload_fingerprint")
        fingerprint = physical_payload_fingerprint
        fingerprint_ref = _fingerprint_ref(physical_payload_fingerprint_ref)
        if fingerprint.to_ref() != fingerprint_ref:
            raise _stale("/physical_payload_fingerprint_ref")
        key = fingerprint.challenge_key
        payload_ref = _owner_ref(
            protected_payload_ref,
            kind="protected_case_payload",
            path="/protected_payload_ref",
            challenge_key=key,
        )
        configuration_ref = _configuration_ref(fixture_configuration_ref)
        if configuration_ref.challenge_key != key:
            raise _cross_challenge("/fixture_configuration_ref")
        if configuration_ref != burgers_fixture_configuration_ref(key):
            raise _stale("/fixture_configuration_ref")
        if fingerprint.fixture_configuration_ref != configuration_ref:
            raise _stale("/fixture_configuration_ref")
        spatial_count = _uint64(spatial_point_count, "/spatial_point_count")
        time_count = _uint64(time_point_count, "/time_point_count")
        initial_count = _uint64(initial_value_count, "/initial_value_count")
        if (
            spatial_count != BURGERS_FIXTURE_GRID_POINTS
            or time_count != 1
            or initial_count != BURGERS_FIXTURE_GRID_POINTS
        ):
            raise _invalid("/fixture_payload_facts")
        if type(degeneracy_facts) is not FixtureDegeneracyFacts:
            raise _wrong("/degeneracy_facts")
        if degeneracy_facts.distinct_initial_value_count > initial_count:
            raise _invalid("/degeneracy_facts/distinct_initial_value_count")
        object.__setattr__(self, "protected_payload_ref", payload_ref)
        object.__setattr__(self, "physical_payload_fingerprint", fingerprint)
        object.__setattr__(self, "physical_payload_fingerprint_ref", fingerprint_ref)
        object.__setattr__(self, "fixture_configuration_ref", configuration_ref)
        object.__setattr__(self, "spatial_point_count", spatial_count)
        object.__setattr__(self, "time_point_count", time_count)
        object.__setattr__(self, "initial_value_count", initial_count)
        object.__setattr__(self, "degeneracy_facts", degeneracy_facts)

    def __repr__(self) -> str:
        return _protected_repr(type(self).__name__)

    __str__ = __repr__

    def __reduce__(self):
        _reject_pickle("fixture payload facts cannot be pickled")


def _new_fixture_payload_facts(
    *,
    protected_payload_ref: object,
    physical_payload_fingerprint: object,
    physical_payload_fingerprint_ref: object,
    fixture_configuration_ref: object,
    spatial_point_count: object,
    time_point_count: object,
    initial_value_count: object,
    degeneracy_facts: object,
) -> FixturePayloadFacts:
    return FixturePayloadFacts(
        protected_payload_ref=protected_payload_ref,
        physical_payload_fingerprint=physical_payload_fingerprint,
        physical_payload_fingerprint_ref=physical_payload_fingerprint_ref,
        fixture_configuration_ref=fixture_configuration_ref,
        spatial_point_count=spatial_point_count,
        time_point_count=time_point_count,
        initial_value_count=initial_value_count,
        degeneracy_facts=degeneracy_facts,
        _token=_PAYLOAD_FACTS_TOKEN,
    )


def build_fixture_payload_facts(
    *,
    protected_payload: ProtectedBurgersFixturePayload,
    protected_payload_ref: object,
    physical_payload_fingerprint: PhysicalPayloadFingerprint,
    physical_payload_fingerprint_ref: PhysicalPayloadFingerprintRef,
) -> FixturePayloadFacts:
    """Derive all payload counts and degeneracy observations without thresholds."""

    if type(protected_payload) is not ProtectedBurgersFixturePayload:
        raise _wrong("/protected_payload")
    if type(physical_payload_fingerprint) is not PhysicalPayloadFingerprint:
        raise _wrong("/physical_payload_fingerprint")
    key = physical_payload_fingerprint.challenge_key
    payload_ref = _owner_ref(
        protected_payload_ref,
        kind="protected_case_payload",
        path="/protected_payload_ref",
        challenge_key=key,
    )
    if (
        protected_payload.fixture_configuration_ref
        != physical_payload_fingerprint.fixture_configuration_ref
    ):
        raise _stale("/protected_payload/fixture_configuration_ref")
    from .canonical import canonical_content_digest

    payload_digest = canonical_content_digest(protected_payload)
    if payload_ref.content_digest != payload_digest:
        raise _stale("/protected_payload_ref")
    if payload_digest != physical_payload_fingerprint.protected_payload_digest:
        raise _stale("/physical_payload_fingerprint/protected_payload_digest")
    return _new_fixture_payload_facts(
        protected_payload_ref=payload_ref,
        physical_payload_fingerprint=physical_payload_fingerprint,
        physical_payload_fingerprint_ref=physical_payload_fingerprint_ref,
        fixture_configuration_ref=protected_payload.fixture_configuration_ref,
        spatial_point_count=protected_payload.grid_points,
        time_point_count=1,
        initial_value_count=len(protected_payload.initial_values),
        degeneracy_facts=_fixture_degeneracy_facts(protected_payload.initial_values),
    )


def _reconstruct_loaded_artifact(
    value: object,
    *,
    path: str,
) -> LoadedAuthoringArtifact:
    """Reload one protected authoring artifact from its exact verified bytes."""

    if type(value) is not LoadedAuthoringArtifact:
        raise _wrong(path)
    failed = False
    reconstructed = None
    try:
        reconstructed = load_authoring_bytes(
            value.expected_ref,
            value.verified_bytes,
            origin=value.origin,
            origin_evidence_ref=value.origin_evidence_ref,
            source_provenance_refs=value.source_provenance_refs,
            audit_evidence_refs=value.audit_evidence_refs,
            qualification_evidence=value.qualification_evidence,
        )
    except (AttributeError, AuthoringError, TypeError, ValueError):
        failed = True
    if failed or reconstructed is None or reconstructed != value:
        raise _stale(path)
    return reconstructed


def _reconstruct_graph_origin(
    value: object,
    *,
    loaded_case: LoadedAuthoringArtifact,
    loaded_dependencies: tuple[LoadedAuthoringArtifact, ...],
) -> AuthoringGraphOrigin:
    """Recompose the complete graph origin and reject any shallow forgery."""

    if type(value) is not AuthoringGraphOrigin:
        raise _wrong("/graph_origin")
    failed = False
    reconstructed = None
    try:
        reconstructed = compose_authoring_graph_origin(
            root=loaded_case,
            dependencies=loaded_dependencies,
            expected_dependency_refs=tuple(
                item.expected_ref for item in loaded_dependencies
            ),
            composition_audit_ref=value.composition_audit_ref,
            registered_authority=None,
        )
    except (AttributeError, AuthoringError, TypeError, ValueError):
        failed = True
    if failed or reconstructed is None or reconstructed != value:
        raise _stale("/graph_origin")
    return reconstructed


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class GeneratedFixtureArtifact:
    """Protected validated-case milestone with structural origin evidence."""

    case: CanonicalChallengeCase
    case_ref: CanonicalChallengeCaseRef
    loaded_case: LoadedAuthoringArtifact
    loaded_dependencies: tuple[LoadedAuthoringArtifact, ...]
    graph_origin: AuthoringGraphOrigin

    def __init__(
        self,
        *,
        case: object,
        case_ref: object,
        loaded_case: object,
        loaded_dependencies: object,
        graph_origin: object,
        _token: object,
    ) -> None:
        if (
            type(self) is not GeneratedFixtureArtifact
            or _token is not _GENERATED_ARTIFACT_TOKEN
        ):
            raise _wrong("/generated_fixture_artifact")
        if type(case) is not CanonicalChallengeCase:
            raise _wrong("/case")
        if type(case_ref) is not CanonicalChallengeCaseRef:
            raise _wrong("/case_ref")
        if case.to_ref() != case_ref:
            raise _stale("/case_ref")
        checked_loaded_case = _reconstruct_loaded_artifact(
            loaded_case,
            path="/loaded_case",
        )
        if (
            checked_loaded_case.expected_ref != case_ref
            or checked_loaded_case.recomputed_ref != case_ref
            or checked_loaded_case.authored_object != case
            or checked_loaded_case.verified_bytes != case.canonical_bytes()
        ):
            raise _stale("/loaded_case")
        if type(loaded_dependencies) is not tuple or not loaded_dependencies:
            raise _incomplete("/loaded_dependencies")
        checked_dependencies = tuple(
            _reconstruct_loaded_artifact(
                item,
                path=f"/loaded_dependencies/{index}",
            )
            for index, item in enumerate(loaded_dependencies)
        )
        checked_graph_origin = _reconstruct_graph_origin(
            graph_origin,
            loaded_case=checked_loaded_case,
            loaded_dependencies=checked_dependencies,
        )
        if checked_graph_origin.graph_origin is not GraphOriginTag.FIXTURE_DERIVED:
            raise _invalid("/graph_origin/graph_origin")
        if checked_graph_origin.root_ref != case_ref:
            raise _stale("/graph_origin/root_ref")
        dependency_refs = tuple(item.expected_ref for item in checked_dependencies)
        if dependency_refs != checked_graph_origin.dependency_refs or any(
            item.recomputed_ref != item.expected_ref for item in checked_dependencies
        ):
            raise _incomplete("/loaded_dependencies")
        expected_origin_evidence = (
            checked_loaded_case.origin_evidence_ref,
            *(item.origin_evidence_ref for item in checked_dependencies),
        )
        if (
            len(set(expected_origin_evidence)) != len(expected_origin_evidence)
            or len(expected_origin_evidence)
            != len(checked_graph_origin.origin_evidence_refs)
            or set(expected_origin_evidence)
            != set(checked_graph_origin.origin_evidence_refs)
        ):
            raise _incomplete("/graph_origin/origin_evidence_refs")
        key = case_ref.challenge_key
        for index, evidence_ref in enumerate(checked_graph_origin.origin_evidence_refs):
            _owner_ref(
                evidence_ref,
                kind="authoring_origin_evidence",
                path=f"/graph_origin/origin_evidence_refs/{index}",
                challenge_key=key,
            )
        _owner_ref(
            checked_graph_origin.composition_audit_ref,
            kind="origin_composition_audit",
            path="/graph_origin/composition_audit_ref",
            challenge_key=key,
        )
        object.__setattr__(self, "case", case)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "loaded_case", checked_loaded_case)
        object.__setattr__(self, "loaded_dependencies", checked_dependencies)
        object.__setattr__(self, "graph_origin", checked_graph_origin)

    def __repr__(self) -> str:
        return _protected_repr(type(self).__name__)

    __str__ = __repr__

    def __reduce__(self):
        _reject_pickle("generated fixture artifacts cannot be pickled")


def build_generated_fixture_artifact(
    *,
    case: CanonicalChallengeCase,
    case_ref: CanonicalChallengeCaseRef,
    loaded_case: LoadedAuthoringArtifact,
    loaded_dependencies: tuple[LoadedAuthoringArtifact, ...],
    graph_origin: AuthoringGraphOrigin,
) -> GeneratedFixtureArtifact:
    """Bind an exact loaded case to its complete fixture-derived graph."""

    return GeneratedFixtureArtifact(
        case=case,
        case_ref=case_ref,
        loaded_case=loaded_case,
        loaded_dependencies=loaded_dependencies,
        graph_origin=graph_origin,
        _token=_GENERATED_ARTIFACT_TOKEN,
    )


@final
@dataclass(frozen=True, slots=True, init=False, repr=False)
class ValidatedCaseFacts:
    """Fact-only identity extracted from one validated generated artifact."""

    case_ref: CanonicalChallengeCaseRef
    representation_ref: object
    physical_payload_ref: object
    primary_population_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    graph_origin: GraphOriginTag
    origin_evidence_refs: tuple[object, ...]
    composition_audit_ref: object

    def __init__(
        self,
        *,
        case_ref: object,
        representation_ref: object,
        physical_payload_ref: object,
        primary_population_ref: object,
        sampling_plan_ref: object,
        graph_origin: object,
        origin_evidence_refs: object,
        composition_audit_ref: object,
        _token: object,
    ) -> None:
        if (
            type(self) is not ValidatedCaseFacts
            or _token is not _VALIDATED_CASE_FACTS_TOKEN
        ):
            raise _wrong("/validated_case_facts")
        if type(case_ref) is not CanonicalChallengeCaseRef:
            raise _wrong("/case_ref")
        key = case_ref.challenge_key
        representation = _owner_ref(
            representation_ref,
            kind="representation",
            path="/representation_ref",
            challenge_key=key,
        )
        payload_ref = _owner_ref(
            physical_payload_ref,
            kind="protected_case_payload",
            path="/physical_payload_ref",
            challenge_key=key,
        )
        if type(primary_population_ref) is not InstanceDistributionContractRef:
            raise _wrong("/primary_population_ref")
        if primary_population_ref.challenge_key != key:
            raise _cross_challenge("/primary_population_ref")
        if type(sampling_plan_ref) is not SamplingPlanRef:
            raise _wrong("/sampling_plan_ref")
        if sampling_plan_ref.challenge_key != key:
            raise _cross_challenge("/sampling_plan_ref")
        if type(graph_origin) is not GraphOriginTag:
            raise _wrong("/graph_origin")
        if graph_origin is not GraphOriginTag.FIXTURE_DERIVED:
            raise _invalid("/graph_origin")
        if type(origin_evidence_refs) is not tuple or not origin_evidence_refs:
            raise _incomplete("/origin_evidence_refs")
        evidence = tuple(
            _owner_ref(
                item,
                kind="authoring_origin_evidence",
                path=f"/origin_evidence_refs/{index}",
                challenge_key=key,
            )
            for index, item in enumerate(origin_evidence_refs)
        )
        if len(set(evidence)) != len(evidence):
            raise _invalid("/origin_evidence_refs")
        audit = _owner_ref(
            composition_audit_ref,
            kind="origin_composition_audit",
            path="/composition_audit_ref",
            challenge_key=key,
        )
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "representation_ref", representation)
        object.__setattr__(self, "physical_payload_ref", payload_ref)
        object.__setattr__(self, "primary_population_ref", primary_population_ref)
        object.__setattr__(self, "sampling_plan_ref", sampling_plan_ref)
        object.__setattr__(self, "graph_origin", graph_origin)
        object.__setattr__(self, "origin_evidence_refs", evidence)
        object.__setattr__(self, "composition_audit_ref", audit)

    def __repr__(self) -> str:
        return _protected_repr(type(self).__name__)

    __str__ = __repr__

    def __reduce__(self):
        _reject_pickle("validated case facts cannot be pickled")


def _new_validated_case_facts(
    *,
    case_ref: object,
    representation_ref: object,
    physical_payload_ref: object,
    primary_population_ref: object,
    sampling_plan_ref: object,
    graph_origin: object,
    origin_evidence_refs: object,
    composition_audit_ref: object,
) -> ValidatedCaseFacts:
    return ValidatedCaseFacts(
        case_ref=case_ref,
        representation_ref=representation_ref,
        physical_payload_ref=physical_payload_ref,
        primary_population_ref=primary_population_ref,
        sampling_plan_ref=sampling_plan_ref,
        graph_origin=graph_origin,
        origin_evidence_refs=origin_evidence_refs,
        composition_audit_ref=composition_audit_ref,
        _token=_VALIDATED_CASE_FACTS_TOKEN,
    )


def build_validated_case_facts(
    artifact: GeneratedFixtureArtifact,
) -> ValidatedCaseFacts:
    """Derive the closed validated-case fact set from the protected artifact."""

    if type(artifact) is not GeneratedFixtureArtifact:
        raise _wrong("/artifact")
    case = artifact.case
    sampling_binding = case.sampling_plan_binding
    if (
        type(sampling_binding) is not ApplicabilityBinding
        or not sampling_binding.is_bound
        or type(sampling_binding.value) is not SamplingPlanRef
    ):
        raise _incomplete("/case/sampling_plan_binding")
    origin = artifact.graph_origin
    return _new_validated_case_facts(
        case_ref=artifact.case_ref,
        representation_ref=case.case_representation_ref,
        physical_payload_ref=case.physical_payload_ref,
        primary_population_ref=case.primary_population_ref,
        sampling_plan_ref=sampling_binding.value,
        graph_origin=origin.graph_origin,
        origin_evidence_refs=origin.origin_evidence_refs,
        composition_audit_ref=origin.composition_audit_ref,
    )


# Canonical registration is explicit and closed.  Importing these private
# schema primitives here avoids either dataclass reflection or a reverse
# import from the canonical foundation into this owning module.
from .canonical import (
    _BOOL,
    _CHALLENGE_KEY,
    _FLOAT64,
    _INT64,
    _TEXT,
    _UINT64,
    _enum,
    _generator_ref,
    _nested,
    _owner,
    _record,
    _register_canonical_type,
    _register_nested_canonical_type,
    _top_ref,
    _tuple_of,
)

_register_canonical_type(
    BurgersFixtureConfiguration,
    object_kind="burgers_fixture_configuration",
    fields=(
        ("configuration_id", _TEXT),
        ("configuration_version", _TEXT),
        ("boundary_shape", _TEXT),
        ("period", _FLOAT64),
        ("grid_points", _UINT64),
        ("viscosity", _FLOAT64),
        ("latent_codec_id", _TEXT),
        ("basis_1", _tuple_of(_INT64)),
        ("basis_2", _tuple_of(_INT64)),
    ),
    builder=_decode_burgers_fixture_configuration,
)

_register_canonical_type(
    ProtectedBurgersFixturePayload,
    object_kind="protected_fixture_payload",
    fields=(
        (
            "fixture_configuration_ref",
            _generator_ref(BurgersFixtureConfigurationRef),
        ),
        ("period", _FLOAT64),
        ("grid_points", _UINT64),
        ("viscosity", _FLOAT64),
        ("initial_values", _tuple_of(_FLOAT64)),
    ),
    builder=_new_protected_payload,
)

_register_canonical_type(
    PhysicalPayloadFingerprint,
    object_kind="physical_payload_fingerprint",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("case_representation_ref", _owner("representation")),
        (
            "fixture_configuration_ref",
            _generator_ref(BurgersFixtureConfigurationRef),
        ),
        ("protected_payload_digest", _TEXT),
    ),
    builder=_new_physical_payload_fingerprint,
)

_register_nested_canonical_type(
    FixtureDegeneracyFacts,
    record_type="fixture_degeneracy_facts",
    fields=(
        ("distinct_initial_value_count", _UINT64),
        ("all_initial_values_zero", _BOOL),
        ("all_initial_values_identical", _BOOL),
    ),
    builder=_new_fixture_degeneracy_facts,
)

_register_nested_canonical_type(
    FixturePayloadFacts,
    record_type="fixture_payload_facts",
    fields=(
        ("protected_payload_ref", _owner("protected_case_payload")),
        (
            "physical_payload_fingerprint",
            _record(PhysicalPayloadFingerprint),
        ),
        (
            "physical_payload_fingerprint_ref",
            _generator_ref(PhysicalPayloadFingerprintRef),
        ),
        (
            "fixture_configuration_ref",
            _generator_ref(BurgersFixtureConfigurationRef),
        ),
        ("spatial_point_count", _UINT64),
        ("time_point_count", _UINT64),
        ("initial_value_count", _UINT64),
        ("degeneracy_facts", _nested(FixtureDegeneracyFacts)),
    ),
    builder=_new_fixture_payload_facts,
)

_register_nested_canonical_type(
    ValidatedCaseFacts,
    record_type="validated_case_facts",
    fields=(
        ("case_ref", _top_ref(CanonicalChallengeCaseRef)),
        ("representation_ref", _owner("representation")),
        ("physical_payload_ref", _owner("protected_case_payload")),
        (
            "primary_population_ref",
            _top_ref(InstanceDistributionContractRef),
        ),
        ("sampling_plan_ref", _top_ref(SamplingPlanRef)),
        ("graph_origin", _enum(GraphOriginTag)),
        (
            "origin_evidence_refs",
            _tuple_of(_owner("authoring_origin_evidence"), set_like=True),
        ),
        ("composition_audit_ref", _owner("origin_composition_audit")),
    ),
    builder=_new_validated_case_facts,
)


# The explicit module exposes safe fixed-fixture descriptors.  Protected
# payloads, facts, artifacts, and trusted builders remain available only by
# explicit import from this module and never become package-root conveniences.
__all__ = (
    "BurgersFixtureConfiguration",
    "BurgersFixtureConfigurationRef",
    "BurgersProductionInputsUnavailable",
    "ProductionInputAvailability",
    "burgers_fixture_configuration",
    "burgers_fixture_configuration_ref",
    "burgers_production_inputs_unavailable",
)
