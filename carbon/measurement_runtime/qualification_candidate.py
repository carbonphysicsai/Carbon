"""D-05 prerequisite harness over C-05 public DEVELOPMENT measurements.

The harness separates reconstruction and finite-case variability and measures
paired rank stability.  It cannot qualify a measurement, choose a threshold,
or declare that three reconstruction replicas are scientifically sufficient.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

import numpy as np

from .model import MEASUREMENT_IDS, BurgersMeasurementResult, MeasurementDisposition

CAMPAIGN_SCHEMA = "carbon.c05.public-measurement-candidate-campaign.v1"
RECIPE_IDS = ("carbon_jax_lab_fno", "foundax_fno")
REPLICA_COUNT = 3
CASE_COUNT = 12


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def frozen_public_measurement_manifest() -> dict[str, object]:
    body: dict[str, object] = {
        "schema": CAMPAIGN_SCHEMA,
        "scope": "PUBLIC_QUALIFICATION_CANDIDATE_ONLY",
        "challenge": {"id": "burgers-dynamics-v1", "version": "1.0"},
        "reference_campaign": "carbon.c04.public-reference-candidate-campaign.v1",
        "recipes": list(RECIPE_IDS),
        "replicas_per_recipe": REPLICA_COUNT,
        "case_coordinates": [
            {"role": "EVAL", "cell": cell, "ordinal": 0, "build": 0}
            for cell in range(CASE_COUNT)
        ],
        "measurement_ids": list(MEASUREMENT_IDS),
        "variance_separation": [
            "WITHIN_CASE_ACROSS_RECONSTRUCTION_REPLICAS",
            "ACROSS_CASES_AFTER_REPLICA_MEAN",
        ],
        "rank_stability": "PAIRED_REPLICA_BY_CASE_LOWER_NORMALIZED_ERROR",
        "decision_resolution_target": {
            "state": "HUMAN_INPUT",
            "owner": "D-05_MEASUREMENT_QUALIFICATION",
            "required_value": "MAXIMUM_ACCEPTABLE_PAIRED_RANK_REVERSAL_RATE_AND_INTERVAL_RULE",
        },
        "scientific_limits": None,
        "reference_floor": None,
        "measurement_floor": None,
        "alternative_replica_count": None,
        "scientifically_qualified": False,
        "protected_execution_eligible": False,
        "score_eligible": False,
    }
    body["manifest_digest"] = "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()
    return body


@dataclass(frozen=True, slots=True)
class MetricVariabilityObservation:
    measurement_id: str
    recipe_id: str
    reconstruction_standard_deviation: float
    finite_case_standard_deviation: float
    observed_mean: float

    def __post_init__(self) -> None:
        values = (
            self.reconstruction_standard_deviation,
            self.finite_case_standard_deviation,
            self.observed_mean,
        )
        if (
            self.measurement_id not in MEASUREMENT_IDS
            or self.recipe_id not in RECIPE_IDS
            or any(
                type(value) is not float or not math.isfinite(value) for value in values
            )
            or self.reconstruction_standard_deviation < 0.0
            or self.finite_case_standard_deviation < 0.0
            or self.observed_mean < 0.0
        ):
            raise ValueError("invalid metric variability observation")

    def document(self) -> dict[str, object]:
        return {
            "measurement_id": self.measurement_id,
            "recipe_id": self.recipe_id,
            "reconstruction_standard_deviation": self.reconstruction_standard_deviation,
            "finite_case_standard_deviation": self.finite_case_standard_deviation,
            "observed_mean": self.observed_mean,
        }


@dataclass(frozen=True, slots=True)
class MeasurementCalibrationCandidate:
    manifest_digest: str
    observations: tuple[MetricVariabilityObservation, ...]
    paired_comparisons: int
    rank_reversals: int
    rank_reversal_fraction: float
    recommendation: str = "KEEP_PROFILE_INELIGIBLE_PENDING_D05_TARGET_AND_FLOORS"
    alternative_replica_count: None = None
    scientifically_qualified: bool = False
    score_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not self.manifest_digest.startswith("sha256:")
            or len(self.observations) != len(RECIPE_IDS) * len(MEASUREMENT_IDS)
            or type(self.paired_comparisons) is not int
            or self.paired_comparisons <= 0
            or type(self.rank_reversals) is not int
            or not 0 <= self.rank_reversals <= self.paired_comparisons
            or type(self.rank_reversal_fraction) is not float
            or not math.isfinite(self.rank_reversal_fraction)
            or self.rank_reversal_fraction
            != self.rank_reversals / self.paired_comparisons
            or self.recommendation
            != "KEEP_PROFILE_INELIGIBLE_PENDING_D05_TARGET_AND_FLOORS"
            or self.alternative_replica_count is not None
            or self.scientifically_qualified is not False
            or self.score_eligible is not False
        ):
            raise ValueError("invalid measurement calibration candidate")

    def document(self) -> dict[str, object]:
        return {
            "manifest_digest": self.manifest_digest,
            "observations": [item.document() for item in self.observations],
            "rank_stability": {
                "paired_comparisons": self.paired_comparisons,
                "rank_reversals": self.rank_reversals,
                "rank_reversal_fraction": self.rank_reversal_fraction,
            },
            "recommendation": self.recommendation,
            "alternative_replica_count": None,
            "limitations": [
                "TWELVE_PUBLIC_CASES_ARE_COVERAGE_NOT_TAIL_EVIDENCE",
                "THREE_REPLICAS_ARE_OWNER_SELECTED_NOT_SCIENTIFICALLY_SUFFICIENT",
                "REFERENCE_AND_MEASUREMENT_FLOORS_UNAVAILABLE",
                "DECISION_RESOLUTION_TARGET_UNAVAILABLE",
                "NO_PROTECTED_POPULATION_EVIDENCE",
            ],
            "scientifically_qualified": False,
            "score_eligible": False,
        }


def run_measurement_calibration_candidate(
    results: dict[str, tuple[tuple[BurgersMeasurementResult, ...], ...]],
) -> MeasurementCalibrationCandidate:
    """Measure variance components without selecting a scientific decision rule."""

    if type(results) is not dict or set(results) != set(RECIPE_IDS):
        raise ValueError("calibration requires both exact recipe identities")
    arrays: dict[str, np.ndarray] = {}
    observations: list[MetricVariabilityObservation] = []
    for recipe in RECIPE_IDS:
        replicas = results[recipe]
        if (
            type(replicas) is not tuple
            or len(replicas) != REPLICA_COUNT
            or any(
                type(cases) is not tuple or len(cases) != CASE_COUNT
                for cases in replicas
            )
        ):
            raise ValueError("calibration requires the frozen 3 by 12 matrix")
        request_digests = []
        values = np.empty((REPLICA_COUNT, CASE_COUNT, len(MEASUREMENT_IDS)))
        for replica_index, cases in enumerate(replicas):
            for case_index, result in enumerate(cases):
                if (
                    type(result) is not BurgersMeasurementResult
                    or result.disposition
                    is not MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY
                    or result.score_eligible is not False
                ):
                    raise ValueError("invalid calibration result")
                request_digests.append(result.request_digest)
                values[replica_index, case_index] = [
                    item.normalized_error for item in result.measurements
                ]
        if len(set(request_digests)) != REPLICA_COUNT * CASE_COUNT:
            raise ValueError("replica/case evidence identities are not distinct")
        arrays[recipe] = values
        for metric_index, metric_id in enumerate(MEASUREMENT_IDS):
            metric = values[:, :, metric_index]
            within = np.std(metric, axis=0, ddof=1)
            case_means = np.mean(metric, axis=0)
            observations.append(
                MetricVariabilityObservation(
                    metric_id,
                    recipe,
                    float(np.sqrt(np.mean(within**2))),
                    float(np.std(case_means, ddof=1)),
                    float(np.mean(metric)),
                )
            )
    left = arrays[RECIPE_IDS[0]]
    right = arrays[RECIPE_IDS[1]]
    mean_direction = np.sign(np.mean(left - right, axis=0))
    directions = np.sign(left - right)
    comparable = mean_direction[None, :, :] != 0
    reversals = np.logical_and(comparable, directions != mean_direction[None, :, :])
    paired = int(np.sum(np.broadcast_to(comparable, directions.shape)))
    reversed_count = int(np.sum(reversals))
    if paired == 0:
        raise ValueError("rank stability is unresolved because every pair is tied")
    manifest = frozen_public_measurement_manifest()
    return MeasurementCalibrationCandidate(
        manifest["manifest_digest"],
        tuple(observations),
        paired,
        reversed_count,
        float(reversed_count / paired),
    )


__all__ = [
    "CAMPAIGN_SCHEMA",
    "CASE_COUNT",
    "RECIPE_IDS",
    "REPLICA_COUNT",
    "MeasurementCalibrationCandidate",
    "MetricVariabilityObservation",
    "frozen_public_measurement_manifest",
    "run_measurement_calibration_candidate",
]
