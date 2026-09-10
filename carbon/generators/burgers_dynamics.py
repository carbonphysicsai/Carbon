"""Deterministic public-development cases for Burgers Dynamics V1.

This is a law-preserving generator only.  It accepts an already derived mock
seed and cannot obtain official entropy, reference answers, measurements, or
registration authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

from carbon.seeding.derive import derive_mock_seed
from carbon.seeding.model import DerivedSeed, MockContext, RoleKey

DOMAIN_LENGTH: Final = 2.0 * math.pi
MODE_COUNT: Final = 12
SHAPE_FAMILIES: Final = ("harmonic", "localized_packet", "multiscale")
REYNOLDS_EDGES: Final = (0.5, 1.0, 2.0, 4.0, 8.0)
CANDIDATE_PAYLOAD_KEYS: Final = frozenset(
    {"domain_length", "initial_field", "requested_times", "viscosity"}
)
_ROLE_KEYS: Final = {
    "TRAIN": RoleKey("burgers-dynamics-public-train"),
    "EVAL": RoleKey("burgers-dynamics-public-eval"),
    "STRESS": RoleKey("burgers-dynamics-public-stress"),
}


class PublicDevelopmentRole(str, Enum):
    TRAIN = "TRAIN"
    EVAL = "EVAL"
    STRESS = "STRESS"


class BurgersDevelopmentError(ValueError):
    """Non-echoing validation failure at the public-development boundary."""


@dataclass(frozen=True, slots=True)
class BurgersCaseCoordinates:
    role: PublicDevelopmentRole
    cell: int
    ordinal: int
    build: int = 0

    def __post_init__(self) -> None:
        if type(self.role) is not PublicDevelopmentRole:
            raise BurgersDevelopmentError("invalid role")
        if type(self.cell) is not int or not 0 <= self.cell < 12:
            raise BurgersDevelopmentError("invalid cell")
        if type(self.ordinal) is not int or self.ordinal < 0:
            raise BurgersDevelopmentError("invalid ordinal")
        if type(self.build) is not int or self.build < 0:
            raise BurgersDevelopmentError("invalid build")
        limits = {
            PublicDevelopmentRole.TRAIN: (2, 3),
            PublicDevelopmentRole.EVAL: (1, 4),
            PublicDevelopmentRole.STRESS: (1, 10),
        }
        builds, ordinals = limits[self.role]
        if self.build >= builds or self.ordinal >= ordinals:
            raise BurgersDevelopmentError("coordinates exceed the development plan")
        if self.role is not PublicDevelopmentRole.TRAIN and self.build != 0:
            raise BurgersDevelopmentError("build is reserved for TRAIN")

    @property
    def draw_index(self) -> int:
        return self.build * 120 + self.cell * 10 + self.ordinal


@dataclass(frozen=True, slots=True)
class BurgersDevelopmentCase:
    parent_id: str
    coordinates: BurgersCaseCoordinates
    shape_family: str
    reynolds_regime: int
    amplitude: float
    mean: float
    k_rms: float
    reynolds_number: float
    viscosity: float
    characteristic_time: float
    horizon: float
    cosine_coefficients: tuple[float, ...]
    sine_coefficients: tuple[float, ...]
    development_only: bool = field(default=True, init=False)
    protected_evaluation_eligible: bool = field(default=False, init=False)

    def public_record(self) -> dict[str, object]:
        return {
            "amplitude": self.amplitude,
            "build": self.coordinates.build,
            "cell": self.coordinates.cell,
            "characteristic_time": self.characteristic_time,
            "cosine_coefficients": list(self.cosine_coefficients),
            "development_only": True,
            "horizon": self.horizon,
            "k_rms": self.k_rms,
            "mean": self.mean,
            "ordinal": self.coordinates.ordinal,
            "parent_id": self.parent_id,
            "protected_evaluation_eligible": False,
            "reynolds_number": self.reynolds_number,
            "reynolds_regime": self.reynolds_regime,
            "role": self.coordinates.role.value,
            "shape_family": self.shape_family,
            "sine_coefficients": list(self.sine_coefficients),
            "viscosity": self.viscosity,
        }


@dataclass(frozen=True, slots=True)
class CandidateQuery:
    initial_field: tuple[float, ...]
    viscosity: float
    requested_times: tuple[float, ...]
    domain_length: float = DOMAIN_LENGTH

    def payload(self) -> dict[str, object]:
        return {
            "domain_length": self.domain_length,
            "initial_field": list(self.initial_field),
            "requested_times": list(self.requested_times),
            "viscosity": self.viscosity,
        }


class _HashStream:
    def __init__(self, seed: bytes) -> None:
        self._seed = seed
        self._counter = 0

    def unit(self) -> float:
        block = hashlib.sha256(
            b"carbon.burgers.public-prng.v1\0"
            + self._seed
            + self._counter.to_bytes(8, "big")
        ).digest()
        self._counter += 1
        return int.from_bytes(block[:8], "big") / 2**64

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.unit()

    def integer(self, low: int, high: int) -> int:
        return low + min(int(self.unit() * (high - low)), high - low - 1)


def _localized_coefficients(
    carrier: int, kappa: float
) -> tuple[list[float], list[float]]:
    samples = 4_096
    cosine: list[float] = []
    sine: list[float] = []
    for mode in range(1, MODE_COUNT + 1):
        real = 0.0
        imaginary = 0.0
        for index in range(samples):
            x = DOMAIN_LENGTH * index / samples
            field = math.exp(kappa * (math.cos(x) - 1.0)) * math.sin(carrier * x)
            real += field * math.cos(mode * x)
            imaginary -= field * math.sin(mode * x)
        cosine.append(2.0 * real / samples)
        sine.append(-2.0 * imaginary / samples)
    return cosine, sine


def _translate(
    cosine: list[float], sine: list[float], translation: float
) -> tuple[list[float], list[float]]:
    translated_cosine: list[float] = []
    translated_sine: list[float] = []
    for index, (cosine_value, sine_value) in enumerate(
        zip(cosine, sine, strict=True), start=1
    ):
        phase = index * translation
        translated_cosine.append(
            cosine_value * math.cos(phase) - sine_value * math.sin(phase)
        )
        translated_sine.append(
            cosine_value * math.sin(phase) + sine_value * math.cos(phase)
        )
    return translated_cosine, translated_sine


def _shape_coefficients(
    family: str, stream: _HashStream
) -> tuple[list[float], list[float]]:
    cosine = [0.0] * MODE_COUNT
    sine = [0.0] * MODE_COUNT
    if family == "harmonic":
        carrier = stream.integer(1, 4)
        ratio = stream.uniform(0.1, 0.3)
        phase = stream.uniform(0.0, DOMAIN_LENGTH)
        sine[carrier - 1] = 1.0
        cosine[2 * carrier - 1] = ratio * math.sin(phase)
        sine[2 * carrier - 1] = ratio * math.cos(phase)
    elif family == "localized_packet":
        carrier = stream.integer(3, 6)
        kappa = stream.uniform(2.0, 5.0)
        cosine, sine = _localized_coefficients(carrier, kappa)
    elif family == "multiscale":
        exponent = stream.uniform(0.8, 1.6)
        for mode in range(1, MODE_COUNT + 1):
            magnitude = mode ** (-exponent) * stream.uniform(0.5, 1.5)
            phase = stream.uniform(0.0, DOMAIN_LENGTH)
            cosine[mode - 1] = magnitude * math.sin(phase)
            sine[mode - 1] = magnitude * math.cos(phase)
    else:
        raise BurgersDevelopmentError("unsupported shape family")
    return _translate(cosine, sine, stream.uniform(0.0, DOMAIN_LENGTH))


def _generate_from_mock_seed(
    seed: DerivedSeed, coordinates: BurgersCaseCoordinates
) -> BurgersDevelopmentCase:
    if type(seed) is not DerivedSeed or type(coordinates) is not BurgersCaseCoordinates:
        raise BurgersDevelopmentError("invalid generation request")
    seed_bytes = seed.as_backend_bytes()
    stream = _HashStream(seed_bytes)
    family = SHAPE_FAMILIES[coordinates.cell // 4]
    regime = coordinates.cell % 4
    cosine, sine = _shape_coefficients(family, stream)
    amplitude = stream.uniform(0.15, 0.35)
    mean = amplitude * stream.uniform(-1.0, 1.0)
    fluctuation_rms = math.sqrt(
        sum(a * a + b * b for a, b in zip(cosine, sine, strict=True)) / 2.0
    )
    if not math.isfinite(fluctuation_rms) or fluctuation_rms <= 0.0:
        raise BurgersDevelopmentError("degenerate generated field")
    scale = amplitude / fluctuation_rms
    cosine = [value * scale for value in cosine]
    sine = [value * scale for value in sine]
    coefficient_energy = sum(a * a + b * b for a, b in zip(cosine, sine, strict=True))
    derivative_energy = sum(
        mode * mode * (cosine[mode - 1] ** 2 + sine[mode - 1] ** 2)
        for mode in range(1, MODE_COUNT + 1)
    )
    k_rms = math.sqrt(derivative_energy / coefficient_energy)
    low = REYNOLDS_EDGES[regime]
    high = REYNOLDS_EDGES[regime + 1]
    reynolds = math.exp(stream.uniform(math.log(low), math.log(high)))
    viscosity = amplitude / (reynolds * k_rms)
    characteristic_time = min(1.0 / (amplitude * k_rms), 1.0 / (viscosity * k_rms**2))
    parent_id = (
        "sha256:"
        + hashlib.sha256(b"carbon.burgers.public-parent.v1\0" + seed_bytes).hexdigest()
    )
    return BurgersDevelopmentCase(
        parent_id=parent_id,
        coordinates=coordinates,
        shape_family=family,
        reynolds_regime=regime,
        amplitude=amplitude,
        mean=mean,
        k_rms=k_rms,
        reynolds_number=reynolds,
        viscosity=viscosity,
        characteristic_time=characteristic_time,
        horizon=4.0 * characteristic_time,
        cosine_coefficients=tuple(cosine),
        sine_coefficients=tuple(sine),
    )


def generate_development_case(
    context: MockContext, coordinates: BurgersCaseCoordinates
) -> BurgersDevelopmentCase:
    """Generate one bounded case exclusively in A4's mock namespace."""

    if (
        type(context) is not MockContext
        or type(coordinates) is not BurgersCaseCoordinates
    ):
        raise BurgersDevelopmentError("public development requires exact mock inputs")
    if context.pin.challenge_key.challenge_id != "burgers-dynamics-v1":
        raise BurgersDevelopmentError("cross-challenge mock context")
    seed = derive_mock_seed(
        context,
        _ROLE_KEYS[coordinates.role.value],
        coordinates.draw_index,
    )
    return _generate_from_mock_seed(seed, coordinates)


def public_development_coordinates() -> tuple[BurgersCaseCoordinates, ...]:
    """Return the bounded 72 TRAIN, 48 EVAL, and 120 STRESS plan."""

    coordinates: list[BurgersCaseCoordinates] = []
    for build in range(2):
        coordinates.extend(
            BurgersCaseCoordinates(PublicDevelopmentRole.TRAIN, cell, ordinal, build)
            for cell in range(12)
            for ordinal in range(3)
        )
    coordinates.extend(
        BurgersCaseCoordinates(PublicDevelopmentRole.EVAL, cell, ordinal)
        for cell in range(12)
        for ordinal in range(4)
    )
    coordinates.extend(
        BurgersCaseCoordinates(PublicDevelopmentRole.STRESS, cell, ordinal)
        for cell in range(12)
        for ordinal in range(10)
    )
    return tuple(coordinates)


def evaluate_initial_field(
    case: BurgersDevelopmentCase, points: tuple[float, ...]
) -> tuple[float, ...]:
    """Evaluate the declared 12-mode trigonometric field at exact points."""

    if type(case) is not BurgersDevelopmentCase or type(points) is not tuple:
        raise BurgersDevelopmentError("invalid point query")
    if not points or any(
        type(point) is not float or not math.isfinite(point) for point in points
    ):
        raise BurgersDevelopmentError("invalid point query")
    values: list[float] = []
    for point in points:
        values.append(
            case.mean
            + sum(
                case.cosine_coefficients[mode - 1] * math.cos(mode * point)
                + case.sine_coefficients[mode - 1] * math.sin(mode * point)
                for mode in range(1, MODE_COUNT + 1)
            )
        )
    return tuple(values)


def requested_times(
    case: BurgersDevelopmentCase, intervals_per_phase: int = 16
) -> tuple[float, ...]:
    if (
        type(case) is not BurgersDevelopmentCase
        or type(intervals_per_phase) is not int
        or intervals_per_phase < 2
        or intervals_per_phase % 2 != 0
    ):
        raise BurgersDevelopmentError("invalid phase-time plan")
    tc = case.characteristic_time
    windows = ((0.0, 0.25), (0.25, 1.0), (1.0, 4.0))
    values: list[float] = []
    for window_index, (start, stop) in enumerate(windows):
        first = 0 if window_index == 0 else 1
        values.extend(
            tc * (start + (stop - start) * index / intervals_per_phase)
            for index in range(first, intervals_per_phase + 1)
        )
    return tuple(values)


def candidate_query(
    case: BurgersDevelopmentCase,
    *,
    grid_points: int = 256,
    intervals_per_phase: int = 16,
) -> CandidateQuery:
    if type(grid_points) is not int or grid_points < 32:
        raise BurgersDevelopmentError("invalid candidate grid")
    points = tuple(DOMAIN_LENGTH * index / grid_points for index in range(grid_points))
    return CandidateQuery(
        initial_field=evaluate_initial_field(case, points),
        viscosity=case.viscosity,
        requested_times=requested_times(case, intervals_per_phase),
    )


def canonical_public_case_bytes(case: BurgersDevelopmentCase) -> bytes:
    if type(case) is not BurgersDevelopmentCase:
        raise BurgersDevelopmentError("invalid case")
    return (
        json.dumps(
            case.public_record(),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


__all__ = (
    "CANDIDATE_PAYLOAD_KEYS",
    "DOMAIN_LENGTH",
    "MODE_COUNT",
    "REYNOLDS_EDGES",
    "SHAPE_FAMILIES",
    "BurgersCaseCoordinates",
    "BurgersDevelopmentCase",
    "BurgersDevelopmentError",
    "CandidateQuery",
    "PublicDevelopmentRole",
    "candidate_query",
    "canonical_public_case_bytes",
    "evaluate_initial_field",
    "generate_development_case",
    "public_development_coordinates",
    "requested_times",
)
