"""Role-explicit Burgers reference algorithms for C-04 DEVELOPMENT evidence.

The numerical implementations in this module are qualification candidates.  A
successful run is deliberately incapable of creating a ``TruthAsset``, score,
or protected-execution admission.  B-04 continues to own those authority
records; D-03 and D-04 own scientific qualification of the methods below.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise

import numpy as np

from carbon.evaluation.enums import (
    RUN_OUTCOME_REASON_COMPATIBILITY,
    ReferenceFailureReason,
    ReferenceRunOutcome,
)
from carbon.generators.burgers_dynamics import (
    DOMAIN_LENGTH,
    MODE_COUNT,
    BurgersDevelopmentCase,
    canonical_public_case_bytes,
)

SCHEMA = "carbon.c04.burgers-reference.v1"
POLICY_ID = "carbon.burgers.reference.candidate.v1"
POLICY_VERSION = "1.0"
SCOPE = "PUBLIC_QUALIFICATION_CANDIDATE_ONLY"
OUTPUT_SEMANTICS = "POINT_VALUE_U_T_X_REQUEST_ORDER_FLOAT64"
MAX_POINTS = 1024
MAX_TIMES = 256
MAX_STEPS = 200_000
LOCK_DIGEST = "sha256:9de64d6c5ca9a0a73d141ca403de1d2bee8bb85e68cd7ea20195b163a7c2cf11"
RUNTIME_DEPENDENCIES = (
    ("jax", "0.10.2"),
    ("jaxlib", "0.10.2"),
    ("numpy", "2.4.6"),
    ("scipy", "1.17.1"),
    ("optax", "0.2.8"),
    ("chex", "0.1.92"),
    ("equinox", "0.13.8"),
    ("einops", "0.8.2"),
    ("foundax", "0.2.0"),
    ("PyYAML", "6.0.3"),
)


class BurgersReferenceRole(str, Enum):
    CANDIDATE_PRIMARY = "CANDIDATE_PRIMARY"
    INDEPENDENT_WITNESS = "INDEPENDENT_WITNESS"
    DEVELOPMENT_CROSSCHECK = "DEVELOPMENT_CROSSCHECK"


_METHODS = {
    BurgersReferenceRole.CANDIDATE_PRIMARY: (
        "cole_hopf_fourier_quadrature",
        "1.0",
        "SEMI_ANALYTIC",
    ),
    BurgersReferenceRole.INDEPENDENT_WITNESS: (
        "periodic_finite_volume_rusanov_ssprk3",
        "1.0",
        "NUMERICAL",
    ),
    BurgersReferenceRole.DEVELOPMENT_CROSSCHECK: (
        "dealiased_fourier_etdrk4",
        "1.0",
        "NUMERICAL",
    ),
}


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _finite_float(value: object, name: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError(f"invalid {name}")
    return value


def _finite_tuple(
    value: object,
    name: str,
    *,
    maximum: int,
    minimum_items: int = 1,
) -> tuple[float, ...]:
    if (
        type(value) is not tuple
        or not minimum_items <= len(value) <= maximum
        or any(type(item) is not float or not math.isfinite(item) for item in value)
    ):
        raise ValueError(f"invalid {name}")
    return tuple(value)


def runtime_environment_manifest() -> dict[str, object]:
    """Return and verify the already-pinned C-03 CPU science environment."""

    observed: list[dict[str, str]] = []
    for distribution, expected in RUNTIME_DEPENDENCIES:
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = "UNAVAILABLE"
        if version != expected:
            raise RuntimeError("C-04 runtime dependency identity mismatch")
        observed.append({"distribution": distribution, "version": version})
    return {
        "schema": "carbon.c04.reference-environment.v1",
        "lock_digest": LOCK_DIGEST,
        "python": "3.11",
        "platform": "linux-x86_64-cpu",
        "dependencies": observed,
    }


def runtime_environment_digest() -> str:
    return _digest(_canonical(runtime_environment_manifest()))


@dataclass(frozen=True, slots=True)
class BurgersReferenceSettings:
    internal_grid_points: int
    cfl: float
    contour_points: int
    maximum_steps: int = MAX_STEPS

    def __post_init__(self) -> None:
        if (
            type(self.internal_grid_points) is not int
            or self.internal_grid_points < 64
            or self.internal_grid_points > 4096
            or self.internal_grid_points & (self.internal_grid_points - 1)
            or type(self.cfl) is not float
            or not 0.0 < self.cfl <= 0.5
            or type(self.contour_points) is not int
            or self.contour_points not in (0, 32)
            or self.maximum_steps != MAX_STEPS
        ):
            raise ValueError("invalid numerical settings")

    def document(self) -> dict[str, object]:
        return {
            "cfl": self.cfl,
            "contour_points": self.contour_points,
            "internal_grid_points": self.internal_grid_points,
            "maximum_steps": self.maximum_steps,
        }


def reference_settings(
    role: BurgersReferenceRole, output_points: int
) -> BurgersReferenceSettings:
    """Return the closed C-04 DEVELOPMENT settings for one nominal role."""

    if type(role) is not BurgersReferenceRole or type(output_points) is not int:
        raise ValueError("invalid settings request")
    if not 32 <= output_points <= MAX_POINTS or output_points & (output_points - 1):
        raise ValueError("output grid must be a supported power of two")
    grid = max(256, output_points)
    if role is BurgersReferenceRole.CANDIDATE_PRIMARY:
        return BurgersReferenceSettings(max(1024, 4 * grid), 0.25, 0)
    if role is BurgersReferenceRole.INDEPENDENT_WITNESS:
        return BurgersReferenceSettings(max(256, 4 * output_points), 0.35, 0)
    if role is BurgersReferenceRole.DEVELOPMENT_CROSSCHECK:
        return BurgersReferenceSettings(max(256, 2 * output_points), 0.25, 32)
    raise ValueError("unsupported reference role")


@dataclass(frozen=True, slots=True)
class BurgersReferenceRequest:
    case_digest: str
    role: BurgersReferenceRole
    spatial_points: tuple[float, ...]
    requested_times: tuple[float, ...]
    domain_length: float
    viscosity: float
    mean: float
    cosine_coefficients: tuple[float, ...]
    sine_coefficients: tuple[float, ...]
    environment_digest: str
    settings: BurgersReferenceSettings
    challenge_id: str = "burgers-dynamics-v1"
    challenge_version: str = "1.0"
    policy_id: str = POLICY_ID
    policy_version: str = POLICY_VERSION
    precision: str = "float64"
    output_semantics: str = OUTPUT_SEMANTICS
    development_only: bool = True
    protected_execution_eligible: bool = False
    score_eligible: bool = False

    def __post_init__(self) -> None:
        points = _finite_tuple(
            self.spatial_points, "spatial points", maximum=MAX_POINTS, minimum_items=32
        )
        times = _finite_tuple(
            self.requested_times, "requested times", maximum=MAX_TIMES
        )
        if (
            self.challenge_id != "burgers-dynamics-v1"
            or self.challenge_version != "1.0"
            or self.policy_id != POLICY_ID
            or self.policy_version != POLICY_VERSION
            or type(self.role) is not BurgersReferenceRole
            or self.precision != "float64"
            or self.output_semantics != OUTPUT_SEMANTICS
            or self.development_only is not True
            or self.protected_execution_eligible is not False
            or self.score_eligible is not False
            or type(self.settings) is not BurgersReferenceSettings
            or self.settings != reference_settings(self.role, len(points))
            or not self.case_digest.startswith("sha256:")
            or len(self.case_digest) != 71
            or not self.environment_digest.startswith("sha256:")
            or len(self.environment_digest) != 71
        ):
            raise ValueError("invalid reference request binding")
        length = _finite_float(self.domain_length, "domain length")
        viscosity = _finite_float(self.viscosity, "viscosity")
        _finite_float(self.mean, "mean")
        cosine = _finite_tuple(
            self.cosine_coefficients,
            "cosine coefficients",
            maximum=MODE_COUNT,
            minimum_items=MODE_COUNT,
        )
        sine = _finite_tuple(
            self.sine_coefficients,
            "sine coefficients",
            maximum=MODE_COUNT,
            minimum_items=MODE_COUNT,
        )
        if (
            length <= 0.0
            or viscosity <= 0.0
            or times[0] < 0.0
            or any(right <= left for left, right in pairwise(times))
            or any(point < 0.0 or point >= length for point in points)
        ):
            raise ValueError("reference request is outside implemented support")
        expected_points = tuple(
            length * index / len(points) for index in range(len(points))
        )
        if points != expected_points:
            raise ValueError("only the registered periodic spatial grid is supported")
        object.__setattr__(self, "spatial_points", points)
        object.__setattr__(self, "requested_times", times)
        object.__setattr__(self, "cosine_coefficients", cosine)
        object.__setattr__(self, "sine_coefficients", sine)

    @property
    def method_id(self) -> str:
        return _METHODS[self.role][0]

    @property
    def implementation_digest(self) -> str:
        return _digest(
            _canonical(
                {
                    "method": self.method_id,
                    "version": _METHODS[self.role][1],
                    "source": "carbon.reference_runtime.model",
                }
            )
        )

    @property
    def numerical_settings_digest(self) -> str:
        return _digest(_canonical(self.settings.document()))

    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "scope": SCOPE,
            "challenge": {
                "id": self.challenge_id,
                "version": self.challenge_version,
            },
            "case_digest": self.case_digest,
            "policy": {"id": self.policy_id, "version": self.policy_version},
            "role": self.role.value,
            "method": {
                "evidence_kind": _METHODS[self.role][2],
                "id": self.method_id,
                "version": _METHODS[self.role][1],
                "implementation_digest": self.implementation_digest,
                "environment_digest": self.environment_digest,
                "precision": self.precision,
                "settings": self.settings.document(),
                "settings_digest": self.numerical_settings_digest,
            },
            "query": {
                "cosine_coefficients": list(self.cosine_coefficients),
                "domain_length": self.domain_length,
                "mean": self.mean,
                "output_semantics": self.output_semantics,
                "requested_times": list(self.requested_times),
                "sine_coefficients": list(self.sine_coefficients),
                "spatial_points": list(self.spatial_points),
                "viscosity": self.viscosity,
            },
            "eligibility": {
                "development_only": True,
                "protected_execution": False,
                "score": False,
                "scientifically_qualified": False,
            },
        }

    @property
    def request_digest(self) -> str:
        """Full cache identity; transport paths are deliberately absent."""

        return _digest(_canonical(self.document()))


def build_reference_request(
    case: BurgersDevelopmentCase,
    role: BurgersReferenceRole,
    *,
    output_points: int,
    requested_times: tuple[float, ...],
    environment_digest: str,
) -> BurgersReferenceRequest:
    if type(case) is not BurgersDevelopmentCase or not case.development_only:
        raise ValueError("only an exact public DEVELOPMENT case is accepted")
    points = tuple(
        DOMAIN_LENGTH * index / output_points for index in range(output_points)
    )
    return BurgersReferenceRequest(
        case_digest=_digest(canonical_public_case_bytes(case)),
        role=role,
        spatial_points=points,
        requested_times=requested_times,
        domain_length=DOMAIN_LENGTH,
        viscosity=float(case.viscosity),
        mean=float(case.mean),
        cosine_coefficients=tuple(float(value) for value in case.cosine_coefficients),
        sine_coefficients=tuple(float(value) for value in case.sine_coefficients),
        environment_digest=environment_digest,
        settings=reference_settings(role, output_points),
    )


def decode_reference_request(document: object) -> BurgersReferenceRequest:
    """Reconstruct the exact closed request document; unknown fields reject."""

    if type(document) is not dict or set(document) != {
        "schema",
        "scope",
        "challenge",
        "case_digest",
        "policy",
        "role",
        "method",
        "query",
        "eligibility",
    }:
        raise ValueError("invalid reference request document")
    challenge = document["challenge"]
    policy = document["policy"]
    method = document["method"]
    query = document["query"]
    eligibility = document["eligibility"]
    if (
        document["schema"] != SCHEMA
        or document["scope"] != SCOPE
        or type(challenge) is not dict
        or set(challenge) != {"id", "version"}
        or type(policy) is not dict
        or set(policy) != {"id", "version"}
        or type(method) is not dict
        or set(method)
        != {
            "evidence_kind",
            "id",
            "version",
            "implementation_digest",
            "environment_digest",
            "precision",
            "settings",
            "settings_digest",
        }
        or type(query) is not dict
        or set(query)
        != {
            "cosine_coefficients",
            "domain_length",
            "mean",
            "output_semantics",
            "requested_times",
            "sine_coefficients",
            "spatial_points",
            "viscosity",
        }
        or eligibility
        != {
            "development_only": True,
            "protected_execution": False,
            "score": False,
            "scientifically_qualified": False,
        }
    ):
        raise ValueError("invalid reference request document")
    try:
        role = BurgersReferenceRole(document["role"])
        settings_value = method["settings"]
        if type(settings_value) is not dict or set(settings_value) != {
            "cfl",
            "contour_points",
            "internal_grid_points",
            "maximum_steps",
        }:
            raise ValueError
        settings = BurgersReferenceSettings(
            settings_value["internal_grid_points"],
            settings_value["cfl"],
            settings_value["contour_points"],
            settings_value["maximum_steps"],
        )
        result = BurgersReferenceRequest(
            case_digest=document["case_digest"],
            role=role,
            spatial_points=tuple(query["spatial_points"]),
            requested_times=tuple(query["requested_times"]),
            domain_length=query["domain_length"],
            viscosity=query["viscosity"],
            mean=query["mean"],
            cosine_coefficients=tuple(query["cosine_coefficients"]),
            sine_coefficients=tuple(query["sine_coefficients"]),
            environment_digest=method["environment_digest"],
            settings=settings,
            challenge_id=challenge["id"],
            challenge_version=challenge["version"],
            policy_id=policy["id"],
            policy_version=policy["version"],
            precision=method["precision"],
            output_semantics=query["output_semantics"],
        )
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid reference request document") from None
    expected = _METHODS[role]
    if (
        method["id"] != expected[0]
        or method["version"] != expected[1]
        or method["evidence_kind"] != expected[2]
        or method["implementation_digest"] != result.implementation_digest
        or method["settings_digest"] != result.numerical_settings_digest
        or result.document() != document
    ):
        raise ValueError("reference request identity mismatch")
    return result


@dataclass(frozen=True, slots=True)
class BurgersReferenceArtifact:
    request_digest: str
    shape: tuple[int, int]
    payload: bytes
    dtype: str = "<f8"
    output_semantics: str = OUTPUT_SEMANTICS

    def __post_init__(self) -> None:
        if (
            type(self.request_digest) is not str
            or not self.request_digest.startswith("sha256:")
            or type(self.shape) is not tuple
            or len(self.shape) != 2
            or any(type(item) is not int or item < 1 for item in self.shape)
            or self.shape[0] > MAX_TIMES
            or self.shape[1] > MAX_POINTS
            or type(self.payload) is not bytes
            or len(self.payload) != self.shape[0] * self.shape[1] * 8
            or self.dtype != "<f8"
            or self.output_semantics != OUTPUT_SEMANTICS
        ):
            raise ValueError("invalid reference artifact")
        array = np.frombuffer(self.payload, dtype="<f8")
        if not np.isfinite(array).all():
            raise ValueError("reference artifact contains nonfinite values")

    @property
    def artifact_digest(self) -> str:
        metadata = _canonical(
            {
                "dtype": self.dtype,
                "output_semantics": self.output_semantics,
                "request_digest": self.request_digest,
                "shape": list(self.shape),
            }
        )
        return _digest(metadata + b"\0" + self.payload)

    def array(self) -> np.ndarray:
        value = np.frombuffer(self.payload, dtype="<f8").reshape(self.shape).copy()
        value.setflags(write=False)
        return value


@dataclass(frozen=True, slots=True)
class BurgersReferenceRun:
    request_digest: str
    role: BurgersReferenceRole
    outcome: ReferenceRunOutcome
    failure_reason: ReferenceFailureReason | None
    artifact: BurgersReferenceArtifact | None
    diagnostics: tuple[tuple[str, float | int | str], ...]
    scientifically_qualified: bool = False
    protected_execution_eligible: bool = False
    score_eligible: bool = False

    def __post_init__(self) -> None:
        supported = self.outcome is ReferenceRunOutcome.SUPPORTED
        if (
            type(self.role) is not BurgersReferenceRole
            or type(self.outcome) is not ReferenceRunOutcome
            or (supported and self.failure_reason is not None)
            or (
                not supported
                and type(self.failure_reason) is not ReferenceFailureReason
            )
            or (
                self.failure_reason is not None
                and self.failure_reason
                not in RUN_OUTCOME_REASON_COMPATIBILITY[self.outcome]
            )
            or (supported and type(self.artifact) is not BurgersReferenceArtifact)
            or (not supported and self.artifact is not None)
            or (
                self.artifact is not None
                and self.artifact.request_digest != self.request_digest
            )
            or type(self.diagnostics) is not tuple
            or any(
                type(item) is not tuple
                or len(item) != 2
                or type(item[0]) is not str
                or type(item[1]) not in (float, int, str)
                for item in self.diagnostics
            )
            or self.scientifically_qualified is not False
            or self.protected_execution_eligible is not False
            or self.score_eligible is not False
        ):
            raise ValueError("invalid reference run")


def _initial_values(request: BurgersReferenceRequest, points: np.ndarray) -> np.ndarray:
    modes = np.arange(1, MODE_COUNT + 1, dtype=np.float64)
    phase = np.outer(points * (2.0 * np.pi / request.domain_length), modes)
    return (
        request.mean
        + np.cos(phase) @ np.asarray(request.cosine_coefficients)
        + np.sin(phase) @ np.asarray(request.sine_coefficients)
    )


def _cole_hopf(
    request: BurgersReferenceRequest, *, internal_grid_points: int | None = None
) -> tuple[np.ndarray, dict[str, float | int | str]]:
    n = (
        request.settings.internal_grid_points
        if internal_grid_points is None
        else internal_grid_points
    )
    if type(n) is not int or n < 64 or n > 4096 or n & (n - 1):
        raise ValueError("invalid Cole-Hopf qualification grid")
    length = request.domain_length
    x_work = np.arange(n, dtype=np.float64) * length / n
    modes = np.arange(1, MODE_COUNT + 1, dtype=np.float64)
    wave = 2.0 * np.pi * modes / length
    phase = np.outer(x_work, wave)
    potential = -np.cos(phase) @ (np.asarray(request.sine_coefficients) / wave)
    potential += np.sin(phase) @ (np.asarray(request.cosine_coefficients) / wave)
    exponent = -potential / (2.0 * request.viscosity)
    exponent -= np.max(exponent)
    phi_hat = np.fft.fft(np.exp(exponent))
    k = 2.0 * np.pi * np.fft.fftfreq(n, d=length / n)
    query_x = np.asarray(request.spatial_points)
    basis = np.exp(1j * np.outer(query_x, k)) / n
    outputs: list[np.ndarray] = []
    minimum_phi = math.inf
    for time_value in request.requested_times:
        evolved = phi_hat * np.exp(
            -request.viscosity * k * k * time_value - 1j * k * request.mean * time_value
        )
        phi = (basis @ evolved).real
        derivative = (basis @ (1j * k * evolved)).real
        minimum_phi = min(minimum_phi, float(np.min(phi)))
        if (
            not np.isfinite(phi).all()
            or not np.isfinite(derivative).all()
            or np.any(phi <= 0.0)
        ):
            raise FloatingPointError("Cole-Hopf conditioning unresolved")
        outputs.append(request.mean - 2.0 * request.viscosity * derivative / phi)
    output_array = np.asarray(outputs, dtype=np.float64)
    diagnostics: dict[str, float | int | str] = {
        "minimum_phi": minimum_phi,
        "quadrature_points": n,
        "method": request.method_id,
    }
    if request.requested_times[0] == 0.0:
        diagnostics["initial_recovery_max_absolute"] = float(
            np.max(np.abs(output_array[0] - _initial_values(request, query_x)))
        )
    return output_array, diagnostics


def _finite_volume(
    request: BurgersReferenceRequest, *, internal_grid_points: int | None = None
) -> tuple[np.ndarray, dict[str, float | int | str]]:
    n = (
        request.settings.internal_grid_points
        if internal_grid_points is None
        else internal_grid_points
    )
    if type(n) is not int or n < 64 or n > 4096 or n & (n - 1):
        raise ValueError("invalid witness qualification grid")
    if n % len(request.spatial_points):
        raise ValueError("witness output grid must divide conservative cells")
    output_stride = n // len(request.spatial_points)
    dx = request.domain_length / n
    internal_points = np.arange(n, dtype=np.float64) * request.domain_length / n
    state = _initial_values(request, internal_points)
    outputs: list[np.ndarray] = []
    current = 0.0
    steps = 0
    initial_mean = float(np.mean(state))

    def rhs(value: np.ndarray) -> np.ndarray:
        right = np.roll(value, -1)
        speed = np.maximum(np.abs(value), np.abs(right))
        flux = 0.25 * (value * value + right * right) - 0.5 * speed * (right - value)
        conservative = -(flux - np.roll(flux, 1)) / dx
        diffusion = (
            request.viscosity * (right - 2.0 * value + np.roll(value, 1)) / (dx * dx)
        )
        return conservative + diffusion

    for target in request.requested_times:
        while current < target:
            remaining = target - current
            rate = float(np.max(np.abs(state))) / dx + 2.0 * request.viscosity / (
                dx * dx
            )
            dt = min(remaining, request.settings.cfl / max(rate, np.finfo(float).tiny))
            first = state + dt * rhs(state)
            second = 0.75 * state + 0.25 * (first + dt * rhs(first))
            state = (state + 2.0 * (second + dt * rhs(second))) / 3.0
            current += dt
            steps += 1
            if steps > request.settings.maximum_steps or not np.isfinite(state).all():
                raise FloatingPointError("conservative witness did not converge")
        outputs.append(state[::output_stride].copy())
    return np.asarray(outputs, dtype=np.float64), {
        "initial_mean": initial_mean,
        "maximum_mean_drift": float(
            max(abs(float(np.mean(value)) - initial_mean) for value in outputs)
        ),
        "method": request.method_id,
        "steps": steps,
    }


def _etdrk4_coefficients(linear: np.ndarray, dt: float, contour_points: int):
    exponential = np.exp(dt * linear)
    half = np.exp(dt * linear / 2.0)
    roots = np.exp(1j * np.pi * (np.arange(contour_points) + 0.5) / contour_points)
    lr = dt * linear[:, None] + roots[None, :]
    q = dt * np.mean((np.exp(lr / 2.0) - 1.0) / lr, axis=1).real
    f1 = (
        dt
        * np.mean(
            (-4.0 - lr + np.exp(lr) * (4.0 - 3.0 * lr + lr * lr)) / lr**3,
            axis=1,
        ).real
    )
    f2 = (
        dt
        * np.mean(
            (2.0 + lr + np.exp(lr) * (-2.0 + lr)) / lr**3,
            axis=1,
        ).real
    )
    f3 = (
        dt
        * np.mean(
            (-4.0 - 3.0 * lr - lr * lr + np.exp(lr) * (4.0 - lr)) / lr**3,
            axis=1,
        ).real
    )
    return exponential, half, q, f1, f2, f3


def _etdrk4(
    request: BurgersReferenceRequest,
) -> tuple[np.ndarray, dict[str, float | int | str]]:
    n = request.settings.internal_grid_points
    if n % len(request.spatial_points):
        raise ValueError("cross-check output grid must divide Fourier cells")
    output_stride = n // len(request.spatial_points)
    dx = request.domain_length / n
    k = 2.0 * np.pi * np.fft.fftfreq(n, d=dx)
    linear = -request.viscosity * k * k
    frequencies = np.fft.fftfreq(n) * n
    keep = np.abs(frequencies) < n / 3
    internal_points = np.arange(n, dtype=np.float64) * request.domain_length / n
    spectrum = np.fft.fft(_initial_values(request, internal_points))
    outputs: list[np.ndarray] = []
    current = 0.0
    steps = 0

    def nonlinear(value: np.ndarray) -> np.ndarray:
        physical = np.fft.ifft(value * keep).real
        return -0.5j * k * np.fft.fft(physical * physical) * keep

    for target in request.requested_times:
        while current < target:
            state = np.fft.ifft(spectrum).real
            advective_dt = dx / max(float(np.max(np.abs(state))), np.finfo(float).tiny)
            diffusive_dt = dx * dx / max(request.viscosity, np.finfo(float).tiny)
            dt = min(
                target - current, request.settings.cfl * min(advective_dt, diffusive_dt)
            )
            e, e2, q, f1, f2, f3 = _etdrk4_coefficients(
                linear, dt, request.settings.contour_points
            )
            nv = nonlinear(spectrum)
            a = e2 * spectrum + q * nv
            na = nonlinear(a)
            b = e2 * spectrum + q * na
            nb = nonlinear(b)
            c = e2 * a + q * (2.0 * nb - nv)
            nc = nonlinear(c)
            spectrum = e * spectrum + f1 * nv + 2.0 * f2 * (na + nb) + f3 * nc
            spectrum *= keep
            current += dt
            steps += 1
            if (
                steps > request.settings.maximum_steps
                or not np.isfinite(spectrum).all()
            ):
                raise FloatingPointError("ETDRK4 cross-check did not converge")
        outputs.append(np.fft.ifft(spectrum).real[::output_stride].copy())
    return np.asarray(outputs, dtype=np.float64), {
        "method": request.method_id,
        "steps": steps,
    }


def execute_reference(request: BurgersReferenceRequest) -> BurgersReferenceRun:
    """Execute one exact candidate method without admission or fallback."""

    if type(request) is not BurgersReferenceRequest:
        raise TypeError("request must be an exact BurgersReferenceRequest")
    try:
        observed_environment = runtime_environment_digest()
    except RuntimeError:
        observed_environment = None
    if request.environment_digest != observed_environment:
        return BurgersReferenceRun(
            request_digest=request.request_digest,
            role=request.role,
            outcome=ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
            failure_reason=ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH,
            artifact=None,
            diagnostics=(("environment", "MISMATCH_OR_UNAVAILABLE"),),
        )
    try:
        if request.role is BurgersReferenceRole.CANDIDATE_PRIMARY:
            values, diagnostics = _cole_hopf(request)
        elif request.role is BurgersReferenceRole.INDEPENDENT_WITNESS:
            values, diagnostics = _finite_volume(request)
        elif request.role is BurgersReferenceRole.DEVELOPMENT_CROSSCHECK:
            values, diagnostics = _etdrk4(request)
        else:  # pragma: no cover - enum is closed and exact above.
            raise ValueError("unsupported role")
        expected = (len(request.requested_times), len(request.spatial_points))
        if (
            values.shape != expected
            or values.dtype != np.float64
            or not np.isfinite(values).all()
        ):
            raise FloatingPointError("invalid numerical result")
        payload = np.asarray(values, dtype="<f8", order="C").tobytes(order="C")
        artifact = BurgersReferenceArtifact(request.request_digest, expected, payload)
        return BurgersReferenceRun(
            request_digest=request.request_digest,
            role=request.role,
            outcome=ReferenceRunOutcome.SUPPORTED,
            failure_reason=None,
            artifact=artifact,
            diagnostics=tuple(sorted(diagnostics.items())),
        )
    except FloatingPointError:
        return BurgersReferenceRun(
            request_digest=request.request_digest,
            role=request.role,
            outcome=ReferenceRunOutcome.NUMERICAL_FAILURE,
            failure_reason=ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
            artifact=None,
            diagnostics=(("method", request.method_id),),
        )


def compare_candidate_runs(
    primary: BurgersReferenceRun,
    witness: BurgersReferenceRun,
) -> dict[str, object]:
    """Return discrepancy evidence only; never decide agreement or truth."""

    if (
        type(primary) is not BurgersReferenceRun
        or type(witness) is not BurgersReferenceRun
        or primary.role is not BurgersReferenceRole.CANDIDATE_PRIMARY
        or witness.role is not BurgersReferenceRole.INDEPENDENT_WITNESS
        or primary.outcome is not ReferenceRunOutcome.SUPPORTED
        or witness.outcome is not ReferenceRunOutcome.SUPPORTED
        or primary.artifact is None
        or witness.artifact is None
        or primary.artifact.shape != witness.artifact.shape
    ):
        return {
            "outcome": "COMPARISON_INDETERMINATE",
            "reason": "PRIMARY_OR_WITNESS_NOT_SUPPORTED_OR_CROSS_BOUND",
            "truth_admitted": False,
        }
    difference = primary.artifact.array() - witness.artifact.array()
    return {
        "outcome": "UNRESOLVED_DISCREPANCY_EVIDENCE",
        "maximum_absolute_discrepancy": float(np.max(np.abs(difference))),
        "rms_discrepancy": float(np.sqrt(np.mean(difference * difference))),
        "scientific_tolerance": None,
        "truth_admitted": False,
    }


__all__ = [
    "MAX_POINTS",
    "MAX_STEPS",
    "MAX_TIMES",
    "OUTPUT_SEMANTICS",
    "POLICY_ID",
    "SCHEMA",
    "SCOPE",
    "BurgersReferenceArtifact",
    "BurgersReferenceRequest",
    "BurgersReferenceRole",
    "BurgersReferenceRun",
    "BurgersReferenceSettings",
    "build_reference_request",
    "compare_candidate_runs",
    "decode_reference_request",
    "execute_reference",
    "reference_settings",
    "runtime_environment_digest",
    "runtime_environment_manifest",
]
