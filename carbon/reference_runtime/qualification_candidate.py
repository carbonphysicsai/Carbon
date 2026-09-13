"""D-03/D-04 prerequisite harness for public C-04 qualification candidates.

The harness records numerical observations and explicit shared dependencies.
It has no tolerance, admission, qualification, TruthAsset, or scoring output.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

import numpy as np

from carbon.evaluation.enums import ReferenceRunOutcome
from carbon.reference_runtime.model import (
    BurgersReferenceRequest,
    BurgersReferenceRole,
    BurgersReferenceRun,
    _cole_hopf,
    _finite_volume,
    _initial_values,
    compare_candidate_runs,
    execute_reference,
    runtime_environment_digest,
)

CAMPAIGN_SCHEMA = "carbon.c04.public-reference-candidate-campaign.v1"
CAMPAIGN_CELLS = tuple(range(12))


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def frozen_public_campaign_manifest() -> dict[str, object]:
    body: dict[str, object] = {
        "schema": CAMPAIGN_SCHEMA,
        "scope": "PUBLIC_QUALIFICATION_CANDIDATE_ONLY",
        "challenge": {"id": "burgers-dynamics-v1", "version": "1.0"},
        "case_coordinates": [
            {"role": "EVAL", "cell": cell, "ordinal": 0, "build": 0}
            for cell in CAMPAIGN_CELLS
        ],
        "case_count": 12,
        "query": {
            "spatial_points": 64,
            "time_over_characteristic_time": [0.0, 0.1, 0.25],
        },
        "roles": [role.value for role in BurgersReferenceRole],
        "environment_digest": runtime_environment_digest(),
        "scientific_tolerances": None,
        "scientifically_qualified": False,
        "protected_execution_eligible": False,
        "score_eligible": False,
    }
    body["manifest_digest"] = "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()
    return body


@dataclass(frozen=True, slots=True)
class QualificationCandidateObservation:
    case_digest: str
    request_digests: tuple[str, str, str]
    artifact_digests: tuple[str, str, str]
    initial_recovery_max_absolute: float
    periodic_closure_max_absolute: float
    cole_hopf_quadrature_change_max_absolute: float
    witness_spatial_refinement_change_max_absolute: float
    witness_mean_drift_max_absolute: float
    primary_witness_discrepancy_max_absolute: float
    primary_crosscheck_discrepancy_max_absolute: float
    minimum_cole_hopf_phi: float
    shared_dependencies: tuple[tuple[str, str], ...]
    decision: str = "EVIDENCE_ONLY_UNRESOLVED"
    scientific_tolerance: None = None
    scientifically_qualified: bool = False
    protected_execution_eligible: bool = False
    score_eligible: bool = False

    def __post_init__(self) -> None:
        metrics = (
            self.initial_recovery_max_absolute,
            self.periodic_closure_max_absolute,
            self.cole_hopf_quadrature_change_max_absolute,
            self.witness_spatial_refinement_change_max_absolute,
            self.witness_mean_drift_max_absolute,
            self.primary_witness_discrepancy_max_absolute,
            self.primary_crosscheck_discrepancy_max_absolute,
            self.minimum_cole_hopf_phi,
        )
        if (
            not self.case_digest.startswith("sha256:")
            or len(self.request_digests) != 3
            or len(set(self.request_digests)) != 3
            or len(self.artifact_digests) != 3
            or any(
                type(value) is not float or not math.isfinite(value)
                for value in metrics
            )
            or any(value < 0.0 for value in metrics[:-1])
            or self.minimum_cole_hopf_phi <= 0.0
            or self.decision != "EVIDENCE_ONLY_UNRESOLVED"
            or self.scientific_tolerance is not None
            or self.scientifically_qualified is not False
            or self.protected_execution_eligible is not False
            or self.score_eligible is not False
        ):
            raise ValueError("invalid qualification-candidate observation")

    def document(self) -> dict[str, object]:
        return {
            "case_digest": self.case_digest,
            "request_digests": list(self.request_digests),
            "artifact_digests": list(self.artifact_digests),
            "observations": {
                "initial_recovery_max_absolute": self.initial_recovery_max_absolute,
                "periodic_closure_max_absolute": self.periodic_closure_max_absolute,
                "cole_hopf_quadrature_change_max_absolute": self.cole_hopf_quadrature_change_max_absolute,
                "witness_spatial_refinement_change_max_absolute": self.witness_spatial_refinement_change_max_absolute,
                "witness_mean_drift_max_absolute": self.witness_mean_drift_max_absolute,
                "primary_witness_discrepancy_max_absolute": self.primary_witness_discrepancy_max_absolute,
                "primary_crosscheck_discrepancy_max_absolute": self.primary_crosscheck_discrepancy_max_absolute,
                "minimum_cole_hopf_phi": self.minimum_cole_hopf_phi,
            },
            "shared_dependencies": [list(item) for item in self.shared_dependencies],
            "decision": self.decision,
            "scientific_tolerance": None,
            "scientifically_qualified": False,
            "protected_execution_eligible": False,
            "score_eligible": False,
        }


def run_qualification_candidate_harness(
    primary_request: BurgersReferenceRequest,
    witness_request: BurgersReferenceRequest,
    crosscheck_request: BurgersReferenceRequest,
) -> tuple[QualificationCandidateObservation | None, tuple[BurgersReferenceRun, ...]]:
    """Execute the three fixed roles and retain evidence without judging it."""

    requests = (primary_request, witness_request, crosscheck_request)
    if (
        any(type(item) is not BurgersReferenceRequest for item in requests)
        or tuple(item.role for item in requests) != tuple(BurgersReferenceRole)
        or len({item.case_digest for item in requests}) != 1
        or len({item.spatial_points for item in requests}) != 1
        or len({item.requested_times for item in requests}) != 1
        or len({item.environment_digest for item in requests}) != 1
    ):
        raise ValueError("cross-bound qualification-candidate requests")
    runs = tuple(execute_reference(item) for item in requests)
    if any(item.outcome is not ReferenceRunOutcome.SUPPORTED for item in runs):
        return None, runs
    primary, witness, crosscheck = runs
    assert primary.artifact and witness.artifact and crosscheck.artifact
    primary_values = primary.artifact.array()
    witness_values = witness.artifact.array()
    crosscheck_values = crosscheck.artifact.array()
    fine_primary, _ = _cole_hopf(
        primary_request,
        internal_grid_points=min(
            4096, 2 * primary_request.settings.internal_grid_points
        ),
    )
    fine_witness, _ = _finite_volume(
        witness_request,
        internal_grid_points=min(
            4096, 2 * witness_request.settings.internal_grid_points
        ),
    )
    endpoints = _initial_values(
        primary_request,
        np.asarray([0.0, primary_request.domain_length], dtype=np.float64),
    )
    comparison = compare_candidate_runs(primary, witness)
    observation = QualificationCandidateObservation(
        case_digest=primary_request.case_digest,
        request_digests=tuple(item.request_digest for item in requests),
        artifact_digests=tuple(item.artifact.artifact_digest for item in runs),
        initial_recovery_max_absolute=float(
            dict(primary.diagnostics).get("initial_recovery_max_absolute", math.nan)
        ),
        periodic_closure_max_absolute=float(abs(endpoints[0] - endpoints[1])),
        cole_hopf_quadrature_change_max_absolute=float(
            np.max(np.abs(primary_values - fine_primary))
        ),
        witness_spatial_refinement_change_max_absolute=float(
            np.max(np.abs(witness_values - fine_witness))
        ),
        witness_mean_drift_max_absolute=float(
            dict(witness.diagnostics)["maximum_mean_drift"]
        ),
        primary_witness_discrepancy_max_absolute=float(
            comparison["maximum_absolute_discrepancy"]
        ),
        primary_crosscheck_discrepancy_max_absolute=float(
            np.max(np.abs(primary_values - crosscheck_values))
        ),
        minimum_cole_hopf_phi=float(dict(primary.diagnostics)["minimum_phi"]),
        shared_dependencies=(
            ("governing_equation", "SHARED"),
            ("case_authoring", "SHARED"),
            ("discretization", "DISTINCT"),
            ("transform", "PRIMARY_ONLY"),
            ("finite_volume_flux", "WITNESS_ONLY"),
            ("numpy_runtime", "SHARED"),
            ("implementation_module", "DISTINCT_WITHIN_ONE_REPOSITORY"),
            ("independent_human_review", "UNAVAILABLE"),
        ),
    )
    return observation, runs


__all__ = [
    "CAMPAIGN_CELLS",
    "CAMPAIGN_SCHEMA",
    "QualificationCandidateObservation",
    "frozen_public_campaign_manifest",
    "run_qualification_candidate_harness",
]
