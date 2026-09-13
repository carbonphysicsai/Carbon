"""C-05 Burgers measurement qualification-candidate runtime.

This module computes registered DEVELOPMENT observables over immutable frozen
candidate and reference fields.  It deliberately has no ScoreInput adapter:
scientific floors, uncertainty policy, and reference qualification remain
unresolved and therefore every result is ineligible for scoring.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise

import numpy as np

from carbon.generators.burgers_dynamics import BurgersDevelopmentCase
from carbon.reference_runtime.model import (
    MAX_POINTS,
    MAX_TIMES,
    OUTPUT_SEMANTICS,
    BurgersReferenceArtifact,
    BurgersReferenceRequest,
    BurgersReferenceRole,
    runtime_environment_digest,
)
from carbon.reference_runtime.model import (
    POLICY_ID as REFERENCE_POLICY_ID,
)
from carbon.reference_runtime.model import (
    POLICY_VERSION as REFERENCE_POLICY_VERSION,
)

SCHEMA = "carbon.c05.burgers-measurement.v1"
POLICY_ID = "carbon.burgers.measurement.candidate.v1"
POLICY_VERSION = "1.0"
SCOPE = "PUBLIC_QUALIFICATION_CANDIDATE_ONLY"
MEASUREMENT_OUTPUT_SEMANTICS = "RAW_UNCERTAINTY_BEARING_NO_SCORE_INPUT"
MEASUREMENT_IDS = (
    "field_phase_rms",
    "maximum_compression",
    "peak_dissipation",
    "energy_half_time",
)
PHYSICS_IDS = (
    "initial_condition",
    "periodicity",
    "conserved_mean",
    "maximum_principle",
    "energy_dissipation_balance",
    "weak_local_pde",
)


def measurement_contract_digest() -> str:
    """Identity of the exact unqualified C-05 operator contract."""

    return _digest(
        _canonical(
            {
                "schema": SCHEMA,
                "policy": {"id": POLICY_ID, "version": POLICY_VERSION},
                "measurements": list(MEASUREMENT_IDS),
                "physics": list(PHYSICS_IDS),
                "compression_extrema": "FOURFOLD_PERIODIC_TRIGONOMETRIC_DERIVATIVE",
                "energy": "HALF_INTEGRAL_SQUARED_FLUCTUATION",
                "dissipation": "VISCOSITY_INTEGRAL_SQUARED_SPECTRAL_GRADIENT",
                "half_time": "LINEAR_BRACKET_OR_RIGHT_CENSOR_AT_LAST_REQUESTED_TIME",
                "uncertainty_policy": None,
                "scientific_limits": None,
            }
        )
    )


def measurement_environment_digest() -> str:
    return _digest(
        _canonical(
            {
                "schema": "carbon.c05.measurement-environment.v1",
                "reference_runtime_environment": runtime_environment_digest(),
                "precision": "float64",
            }
        )
    )


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


def _valid_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _finite_tuple(
    value: object, name: str, *, maximum: int, minimum: int = 1
) -> tuple[float, ...]:
    if (
        type(value) is not tuple
        or not minimum <= len(value) <= maximum
        or any(type(item) is not float or not math.isfinite(item) for item in value)
    ):
        raise ValueError(f"invalid {name}")
    return tuple(value)


class MeasurementDisposition(str, Enum):
    COMPLETE_DEVELOPMENT_ONLY = "COMPLETE_DEVELOPMENT_ONLY"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID = "INVALID"
    REFERENCE_UNRESOLVED = "REFERENCE_UNRESOLVED"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    CANCELLED = "CANCELLED"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


class EvidenceDecision(str, Enum):
    UNRESOLVED_NO_QUALIFIED_LIMIT = "UNRESOLVED_NO_QUALIFIED_LIMIT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class FrozenFieldArtifact:
    """Exact finite float64 field artifact; paths are never identity."""

    binding_digest: str
    shape: tuple[int, int]
    payload: bytes
    role: str
    dtype: str = "<f8"
    output_semantics: str = OUTPUT_SEMANTICS

    def __post_init__(self) -> None:
        if (
            not _valid_digest(self.binding_digest)
            or type(self.shape) is not tuple
            or len(self.shape) != 2
            or any(type(item) is not int or item < 1 for item in self.shape)
            or self.shape[0] > MAX_TIMES
            or self.shape[1] > MAX_POINTS
            or type(self.payload) is not bytes
            or len(self.payload) != self.shape[0] * self.shape[1] * 8
            or self.role not in {"CANDIDATE_PREDICTION", "REFERENCE_PRIMARY"}
            or self.dtype != "<f8"
            or self.output_semantics != OUTPUT_SEMANTICS
        ):
            raise ValueError("invalid frozen field artifact")
        if not np.isfinite(np.frombuffer(self.payload, dtype="<f8")).all():
            raise ValueError("field artifact contains nonfinite values")

    @property
    def artifact_digest(self) -> str:
        return _digest(
            _canonical(
                {
                    "binding_digest": self.binding_digest,
                    "dtype": self.dtype,
                    "output_semantics": self.output_semantics,
                    "role": self.role,
                    "shape": list(self.shape),
                }
            )
            + b"\0"
            + self.payload
        )

    def array(self) -> np.ndarray:
        result = np.frombuffer(self.payload, dtype="<f8").reshape(self.shape).copy()
        result.setflags(write=False)
        return result


@dataclass(frozen=True, slots=True)
class BurgersMeasurementRequest:
    """Closed request binding every scientifically material input identity."""

    case_digest: str
    candidate_artifact_digest: str
    candidate_binding_digest: str
    candidate_source_digest: str
    candidate_environment_digest: str
    candidate_plan_digest: str
    candidate_replica_id: str
    reference_artifact_digest: str
    reference_request_digest: str
    reference_policy_digest: str
    reference_environment_digest: str
    measurement_contract_digest: str
    measurement_environment_digest: str
    spatial_points: tuple[float, ...]
    requested_times: tuple[float, ...]
    initial_values: tuple[float, ...]
    domain_length: float
    viscosity: float
    characteristic_time: float
    amplitude: float
    k_rms: float
    challenge_id: str = "burgers-dynamics-v1"
    challenge_version: str = "1.0"
    policy_id: str = POLICY_ID
    policy_version: str = POLICY_VERSION
    reference_role: BurgersReferenceRole = BurgersReferenceRole.CANDIDATE_PRIMARY
    precision: str = "float64"
    output_semantics: str = OUTPUT_SEMANTICS
    development_only: bool = True
    reference_scientifically_qualified: bool = False
    measurement_scientifically_qualified: bool = False
    score_eligible: bool = False

    def __post_init__(self) -> None:
        digests = (
            self.case_digest,
            self.candidate_artifact_digest,
            self.candidate_binding_digest,
            self.candidate_source_digest,
            self.candidate_environment_digest,
            self.candidate_plan_digest,
            self.reference_artifact_digest,
            self.reference_request_digest,
            self.reference_policy_digest,
            self.reference_environment_digest,
            self.measurement_contract_digest,
            self.measurement_environment_digest,
        )
        points = _finite_tuple(
            self.spatial_points, "spatial points", maximum=MAX_POINTS, minimum=32
        )
        times = _finite_tuple(
            self.requested_times, "requested times", maximum=MAX_TIMES, minimum=3
        )
        initial = _finite_tuple(
            self.initial_values,
            "initial values",
            maximum=MAX_POINTS,
            minimum=len(points),
        )
        scalars = (
            self.domain_length,
            self.viscosity,
            self.characteristic_time,
            self.amplitude,
            self.k_rms,
        )
        if (
            any(not _valid_digest(item) for item in digests)
            or type(self.candidate_replica_id) is not str
            or not self.candidate_replica_id.startswith("reconstruction-replica-")
            or self.challenge_id != "burgers-dynamics-v1"
            or self.challenge_version != "1.0"
            or self.policy_id != POLICY_ID
            or self.policy_version != POLICY_VERSION
            or self.reference_role is not BurgersReferenceRole.CANDIDATE_PRIMARY
            or self.precision != "float64"
            or self.output_semantics != OUTPUT_SEMANTICS
            or self.development_only is not True
            or self.reference_scientifically_qualified is not False
            or self.measurement_scientifically_qualified is not False
            or self.score_eligible is not False
            or any(
                type(item) is not float or not math.isfinite(item) for item in scalars
            )
            or any(item <= 0.0 for item in scalars)
            or times[0] != 0.0
            or any(right <= left for left, right in pairwise(times))
            or len(initial) != len(points)
        ):
            raise ValueError("invalid measurement request binding")
        expected = tuple(
            self.domain_length * i / len(points) for i in range(len(points))
        )
        if points != expected:
            raise ValueError("measurement requires the registered periodic grid")
        object.__setattr__(self, "spatial_points", points)
        object.__setattr__(self, "requested_times", times)
        object.__setattr__(self, "initial_values", initial)

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self.requested_times), len(self.spatial_points))

    @property
    def implementation_digest(self) -> str:
        return _digest(
            _canonical(
                {
                    "module": "carbon.measurement_runtime.model",
                    "operators": list(MEASUREMENT_IDS),
                    "physics": list(PHYSICS_IDS),
                    "version": "1.0",
                }
            )
        )

    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "scope": SCOPE,
            "challenge": {"id": self.challenge_id, "version": self.challenge_version},
            "case_digest": self.case_digest,
            "candidate": {
                "artifact_digest": self.candidate_artifact_digest,
                "binding_digest": self.candidate_binding_digest,
                "source_digest": self.candidate_source_digest,
                "environment_digest": self.candidate_environment_digest,
                "plan_digest": self.candidate_plan_digest,
                "replica_id": self.candidate_replica_id,
            },
            "reference": {
                "artifact_digest": self.reference_artifact_digest,
                "request_digest": self.reference_request_digest,
                "policy_digest": self.reference_policy_digest,
                "environment_digest": self.reference_environment_digest,
                "role": self.reference_role.value,
                "scientifically_qualified": False,
            },
            "measurement": {
                "policy_id": self.policy_id,
                "policy_version": self.policy_version,
                "contract_digest": self.measurement_contract_digest,
                "environment_digest": self.measurement_environment_digest,
                "implementation_digest": self.implementation_digest,
                "precision": self.precision,
                "operator_ids": list(MEASUREMENT_IDS),
                "physics_ids": list(PHYSICS_IDS),
                "scientific_limits": None,
                "uncertainty_policy": None,
                "scientifically_qualified": False,
            },
            "query": {
                "spatial_points": list(self.spatial_points),
                "requested_times": list(self.requested_times),
                "initial_values": list(self.initial_values),
                "domain_length": self.domain_length,
                "viscosity": self.viscosity,
                "characteristic_time": self.characteristic_time,
                "amplitude": self.amplitude,
                "k_rms": self.k_rms,
                "output_semantics": self.output_semantics,
            },
            "eligibility": {
                "development_only": True,
                "protected_execution": False,
                "reference_scientifically_qualified": False,
                "measurement_scientifically_qualified": False,
                "score": False,
            },
        }

    @property
    def request_digest(self) -> str:
        return _digest(_canonical(self.document()))


def build_measurement_request(
    case: BurgersDevelopmentCase,
    reference_request: BurgersReferenceRequest,
    reference_artifact: BurgersReferenceArtifact,
    candidate_artifact: FrozenFieldArtifact,
    *,
    candidate_source_digest: str,
    candidate_environment_digest: str,
    candidate_plan_digest: str,
    candidate_replica_id: str,
) -> BurgersMeasurementRequest:
    """Bind one public case, frozen prediction, and unqualified primary reference."""

    if (
        type(case) is not BurgersDevelopmentCase
        or not case.development_only
        or type(reference_request) is not BurgersReferenceRequest
        or reference_request.role is not BurgersReferenceRole.CANDIDATE_PRIMARY
        or type(reference_artifact) is not BurgersReferenceArtifact
        or type(candidate_artifact) is not FrozenFieldArtifact
        or candidate_artifact.role != "CANDIDATE_PREDICTION"
        or reference_artifact.request_digest != reference_request.request_digest
        or reference_artifact.shape != candidate_artifact.shape
        or reference_artifact.shape
        != (
            len(reference_request.requested_times),
            len(reference_request.spatial_points),
        )
    ):
        raise ValueError("invalid measurement construction inputs")
    initial = (
        case.mean
        + np.cos(
            np.outer(
                np.asarray(reference_request.spatial_points)
                * (2.0 * np.pi / reference_request.domain_length),
                np.arange(1, len(case.cosine_coefficients) + 1),
            )
        )
        @ np.asarray(case.cosine_coefficients)
        + np.sin(
            np.outer(
                np.asarray(reference_request.spatial_points)
                * (2.0 * np.pi / reference_request.domain_length),
                np.arange(1, len(case.sine_coefficients) + 1),
            )
        )
        @ np.asarray(case.sine_coefficients)
    )
    reference_field = FrozenFieldArtifact(
        reference_request.request_digest,
        reference_artifact.shape,
        reference_artifact.payload,
        "REFERENCE_PRIMARY",
    )
    return BurgersMeasurementRequest(
        case_digest=reference_request.case_digest,
        candidate_artifact_digest=candidate_artifact.artifact_digest,
        candidate_binding_digest=candidate_artifact.binding_digest,
        candidate_source_digest=candidate_source_digest,
        candidate_environment_digest=candidate_environment_digest,
        candidate_plan_digest=candidate_plan_digest,
        candidate_replica_id=candidate_replica_id,
        reference_artifact_digest=reference_field.artifact_digest,
        reference_request_digest=reference_request.request_digest,
        reference_policy_digest=_digest(
            _canonical(
                {
                    "id": REFERENCE_POLICY_ID,
                    "version": REFERENCE_POLICY_VERSION,
                }
            )
        ),
        reference_environment_digest=reference_request.environment_digest,
        measurement_contract_digest=measurement_contract_digest(),
        measurement_environment_digest=measurement_environment_digest(),
        spatial_points=reference_request.spatial_points,
        requested_times=reference_request.requested_times,
        initial_values=tuple(float(item) for item in initial),
        domain_length=reference_request.domain_length,
        viscosity=reference_request.viscosity,
        characteristic_time=float(case.characteristic_time),
        amplitude=float(case.amplitude),
        k_rms=float(case.k_rms),
    )


@dataclass(frozen=True, slots=True)
class MeasurementObservation:
    measurement_id: str
    candidate_value: float
    reference_value: float
    raw_absolute_error: float
    normalization_scale: float
    normalized_error: float
    uncertainty: None = None
    scientific_limit: None = None
    decision: EvidenceDecision = EvidenceDecision.UNRESOLVED_NO_QUALIFIED_LIMIT

    def __post_init__(self) -> None:
        values = (
            self.candidate_value,
            self.reference_value,
            self.raw_absolute_error,
            self.normalization_scale,
            self.normalized_error,
        )
        if (
            self.measurement_id not in MEASUREMENT_IDS
            or any(
                type(value) is not float or not math.isfinite(value) for value in values
            )
            or self.raw_absolute_error < 0.0
            or self.normalization_scale <= 0.0
            or self.normalized_error < 0.0
            or self.normalized_error
            != self.raw_absolute_error / self.normalization_scale
            or self.uncertainty is not None
            or self.scientific_limit is not None
            or self.decision is not EvidenceDecision.UNRESOLVED_NO_QUALIFIED_LIMIT
        ):
            raise ValueError("invalid measurement observation")

    def document(self) -> dict[str, object]:
        return {
            "measurement_id": self.measurement_id,
            "candidate_value": self.candidate_value,
            "reference_value": self.reference_value,
            "raw_absolute_error": self.raw_absolute_error,
            "normalization_scale": self.normalization_scale,
            "normalized_error": self.normalized_error,
            "uncertainty": None,
            "scientific_limit": None,
            "decision": self.decision.value,
        }


@dataclass(frozen=True, slots=True)
class PhysicsObservation:
    physics_id: str
    raw_defect: float
    normalization_scale: float
    normalized_defect: float
    uncertainty: None = None
    scientific_limit: None = None
    decision: EvidenceDecision = EvidenceDecision.UNRESOLVED_NO_QUALIFIED_LIMIT

    def __post_init__(self) -> None:
        values = (self.raw_defect, self.normalization_scale, self.normalized_defect)
        if (
            self.physics_id not in PHYSICS_IDS
            or any(
                type(value) is not float or not math.isfinite(value) for value in values
            )
            or self.raw_defect < 0.0
            or self.normalization_scale <= 0.0
            or self.normalized_defect < 0.0
            or self.normalized_defect != self.raw_defect / self.normalization_scale
            or self.uncertainty is not None
            or self.scientific_limit is not None
            or self.decision is not EvidenceDecision.UNRESOLVED_NO_QUALIFIED_LIMIT
        ):
            raise ValueError("invalid physics observation")

    def document(self) -> dict[str, object]:
        return {
            "physics_id": self.physics_id,
            "raw_defect": self.raw_defect,
            "normalization_scale": self.normalization_scale,
            "normalized_defect": self.normalized_defect,
            "uncertainty": None,
            "scientific_limit": None,
            "decision": self.decision.value,
        }


@dataclass(frozen=True, slots=True)
class BurgersMeasurementResult:
    request_digest: str
    disposition: MeasurementDisposition
    measurements: tuple[MeasurementObservation, ...]
    physics: tuple[PhysicsObservation, ...]
    diagnostics: tuple[tuple[str, float | int | str], ...]
    output_semantics: str = MEASUREMENT_OUTPUT_SEMANTICS
    score_input: None = None
    scientifically_qualified: bool = False
    protected_execution_eligible: bool = False
    score_eligible: bool = False

    def __post_init__(self) -> None:
        complete = self.disposition is MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY
        if (
            not _valid_digest(self.request_digest)
            or type(self.disposition) is not MeasurementDisposition
            or (
                complete
                and tuple(item.measurement_id for item in self.measurements)
                != MEASUREMENT_IDS
            )
            or (
                complete
                and tuple(item.physics_id for item in self.physics) != PHYSICS_IDS
            )
            or (not complete and (self.measurements or self.physics))
            or type(self.diagnostics) is not tuple
            or any(
                type(item) is not tuple
                or len(item) != 2
                or type(item[0]) is not str
                or type(item[1]) not in (float, int, str)
                or (type(item[1]) is float and not math.isfinite(item[1]))
                for item in self.diagnostics
            )
            or self.output_semantics != MEASUREMENT_OUTPUT_SEMANTICS
            or self.score_input is not None
            or self.scientifically_qualified is not False
            or self.protected_execution_eligible is not False
            or self.score_eligible is not False
        ):
            raise ValueError("invalid measurement result")

    @property
    def result_digest(self) -> str:
        return _digest(_canonical(self.document()))

    def document(self) -> dict[str, object]:
        return {
            "schema": "carbon.c05.burgers-measurement-result.v1",
            "scope": SCOPE,
            "request_digest": self.request_digest,
            "disposition": self.disposition.value,
            "measurements": [item.document() for item in self.measurements],
            "physics": [item.document() for item in self.physics],
            "diagnostics": [list(item) for item in self.diagnostics],
            "output_semantics": self.output_semantics,
            "score_input": None,
            "eligibility": {
                "scientifically_qualified": False,
                "protected_execution": False,
                "score": False,
            },
        }


def _spectral_derivatives(
    values: np.ndarray, length: float
) -> tuple[np.ndarray, np.ndarray]:
    count = values.shape[1]
    wave = 2.0 * np.pi * np.fft.fftfreq(count, d=length / count)
    coefficients = np.fft.fft(values, axis=1)
    first = np.fft.ifft(coefficients * (1j * wave), axis=1).real
    second = np.fft.ifft(coefficients * (-(wave**2)), axis=1).real
    return first, second


def _fourfold_compression(values: np.ndarray, length: float) -> float:
    count = values.shape[1]
    modes = np.fft.fftfreq(count) * count
    wave = 2.0 * np.pi * modes / length
    dense_x = np.arange(4 * count, dtype=np.float64) * length / (4 * count)
    basis = np.exp(1j * np.outer(dense_x, wave))
    maximum = 0.0
    for row in values:
        coefficients = np.fft.fft(row) / count
        if count % 2 == 0:
            coefficients[count // 2] = 0.0
        derivative = (basis @ (1j * wave * coefficients)).real
        maximum = max(maximum, float(np.max(-derivative)))
    return maximum


def _qois(
    values: np.ndarray, request: BurgersMeasurementRequest
) -> tuple[float, float, float, bool, tuple[float, ...]]:
    first, _ = _spectral_derivatives(values, request.domain_length)
    dx = request.domain_length / values.shape[1]
    mean = np.mean(values, axis=1)
    energy = 0.5 * dx * np.sum((values - mean[:, None]) ** 2, axis=1)
    dissipation = request.viscosity * dx * np.sum(first**2, axis=1)
    target = 0.5 * float(energy[0])
    crossing = None
    for index in range(1, len(energy)):
        if energy[index] <= target <= energy[index - 1]:
            left_t, right_t = request.requested_times[index - 1 : index + 1]
            left_e, right_e = float(energy[index - 1]), float(energy[index])
            fraction = (
                0.0 if left_e == right_e else (left_e - target) / (left_e - right_e)
            )
            crossing = left_t + fraction * (right_t - left_t)
            break
    censored = crossing is None
    half_time = request.requested_times[-1] if censored else float(crossing)
    return (
        _fourfold_compression(values, request.domain_length),
        float(np.max(dissipation)),
        float(half_time),
        censored,
        tuple(float(item) for item in energy),
    )


def execute_measurement(
    request: BurgersMeasurementRequest,
    candidate: FrozenFieldArtifact,
    reference: FrozenFieldArtifact,
) -> BurgersMeasurementResult:
    """Compute raw DEVELOPMENT evidence with all scientific decisions unresolved."""

    if (
        type(request) is not BurgersMeasurementRequest
        or type(candidate) is not FrozenFieldArtifact
        or type(reference) is not FrozenFieldArtifact
        or candidate.role != "CANDIDATE_PREDICTION"
        or reference.role != "REFERENCE_PRIMARY"
        or candidate.artifact_digest != request.candidate_artifact_digest
        or candidate.binding_digest != request.candidate_binding_digest
        or reference.artifact_digest != request.reference_artifact_digest
        or reference.binding_digest != request.reference_request_digest
        or candidate.shape != request.shape
        or reference.shape != request.shape
    ):
        raise ValueError("cross-bound measurement inputs")
    candidate_values = candidate.array()
    reference_values = reference.array()
    initial = np.asarray(request.initial_values, dtype=np.float64)
    initial_fluctuation_rms = float(np.sqrt(np.mean((initial - np.mean(initial)) ** 2)))
    if initial_fluctuation_rms <= 0.0:
        raise ValueError("initial fluctuation scale is zero")
    field_candidate = float(np.sqrt(np.mean(candidate_values**2)))
    field_reference = float(np.sqrt(np.mean(reference_values**2)))
    field_error = float(np.sqrt(np.mean((candidate_values - reference_values) ** 2)))
    candidate_qoi = _qois(candidate_values, request)
    reference_qoi = _qois(reference_values, request)
    energy_scale = 0.5 * request.domain_length * request.amplitude**2
    measurements = (
        MeasurementObservation(
            "field_phase_rms",
            field_candidate,
            field_reference,
            field_error,
            initial_fluctuation_rms,
            field_error / initial_fluctuation_rms,
        ),
        MeasurementObservation(
            "maximum_compression",
            candidate_qoi[0],
            reference_qoi[0],
            abs(candidate_qoi[0] - reference_qoi[0]),
            max(reference_qoi[0], request.amplitude * request.k_rms),
            abs(candidate_qoi[0] - reference_qoi[0])
            / max(reference_qoi[0], request.amplitude * request.k_rms),
        ),
        MeasurementObservation(
            "peak_dissipation",
            candidate_qoi[1],
            reference_qoi[1],
            abs(candidate_qoi[1] - reference_qoi[1]),
            max(reference_qoi[1], energy_scale / request.characteristic_time),
            abs(candidate_qoi[1] - reference_qoi[1])
            / max(reference_qoi[1], energy_scale / request.characteristic_time),
        ),
        MeasurementObservation(
            "energy_half_time",
            candidate_qoi[2],
            reference_qoi[2],
            abs(candidate_qoi[2] - reference_qoi[2]),
            request.characteristic_time,
            abs(candidate_qoi[2] - reference_qoi[2]) / request.characteristic_time,
        ),
    )
    candidate_first, candidate_second = _spectral_derivatives(
        candidate_values, request.domain_length
    )
    means = np.mean(candidate_values, axis=1)
    initial_min = float(np.min(initial))
    initial_max = float(np.max(initial))
    maximum_principle = max(
        0.0,
        float(np.max(candidate_values)) - initial_max,
        initial_min - float(np.min(candidate_values)),
    )
    energies = np.asarray(candidate_qoi[4])
    energy_increase = float(max(0.0, np.max(np.diff(energies))))
    residuals: list[np.ndarray] = []
    for index, dt in enumerate(np.diff(np.asarray(request.requested_times))):
        midpoint = 0.5 * (candidate_values[index + 1] + candidate_values[index])
        midpoint_first = 0.5 * (candidate_first[index + 1] + candidate_first[index])
        midpoint_second = 0.5 * (candidate_second[index + 1] + candidate_second[index])
        residuals.append(
            (candidate_values[index + 1] - candidate_values[index]) / dt
            + midpoint * midpoint_first
            - request.viscosity * midpoint_second
        )
    weak_residual = float(
        np.sqrt(np.mean(np.concatenate([item.ravel() for item in residuals]) ** 2))
    )
    time_scale = request.amplitude / request.characteristic_time
    endpoint_basis = np.exp(
        1j
        * np.outer(
            np.asarray([0.0, request.domain_length]),
            2.0
            * np.pi
            * np.fft.fftfreq(
                candidate_values.shape[1],
                d=request.domain_length / candidate_values.shape[1],
            ),
        )
    )
    closure = 0.0
    for row in candidate_values:
        endpoints = (endpoint_basis @ (np.fft.fft(row) / len(row))).real
        closure = max(closure, float(abs(endpoints[0] - endpoints[1])))
    physics = (
        PhysicsObservation(
            "initial_condition",
            float(np.max(np.abs(candidate_values[0] - initial))),
            request.amplitude,
            float(np.max(np.abs(candidate_values[0] - initial))) / request.amplitude,
        ),
        PhysicsObservation(
            "periodicity", closure, request.amplitude, closure / request.amplitude
        ),
        PhysicsObservation(
            "conserved_mean",
            float(np.max(np.abs(means - means[0]))),
            request.amplitude,
            float(np.max(np.abs(means - means[0]))) / request.amplitude,
        ),
        PhysicsObservation(
            "maximum_principle",
            maximum_principle,
            request.amplitude,
            maximum_principle / request.amplitude,
        ),
        PhysicsObservation(
            "energy_dissipation_balance",
            energy_increase,
            max(float(energies[0]), np.finfo(np.float64).tiny),
            energy_increase / max(float(energies[0]), np.finfo(np.float64).tiny),
        ),
        PhysicsObservation(
            "weak_local_pde",
            weak_residual,
            time_scale,
            weak_residual / time_scale,
        ),
    )
    return BurgersMeasurementResult(
        request.request_digest,
        MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY,
        measurements,
        physics,
        (
            ("candidate_half_time_censored", int(candidate_qoi[3])),
            ("reference_half_time_censored", int(reference_qoi[3])),
            ("requested_time_count", len(request.requested_times)),
            ("spatial_point_count", len(request.spatial_points)),
            ("score_input_emitted", 0),
        ),
    )


__all__ = [
    "MEASUREMENT_IDS",
    "MEASUREMENT_OUTPUT_SEMANTICS",
    "PHYSICS_IDS",
    "POLICY_ID",
    "POLICY_VERSION",
    "SCHEMA",
    "SCOPE",
    "BurgersMeasurementRequest",
    "BurgersMeasurementResult",
    "EvidenceDecision",
    "FrozenFieldArtifact",
    "MeasurementDisposition",
    "MeasurementObservation",
    "PhysicsObservation",
    "build_measurement_request",
    "execute_measurement",
    "measurement_contract_digest",
    "measurement_environment_digest",
]
