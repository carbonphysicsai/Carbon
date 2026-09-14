"""Run the detached D-QUAL-PREP-01 public DEVELOPMENT readiness campaign.

This runner organizes observations.  It cannot select Wave D, qualify a
reference or measurement, set a scientific limit, or create ScoreInput.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np

from carbon.evaluation.enums import ReferenceRunOutcome
from carbon.generators.burgers_dynamics import (
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    generate_development_case,
)
from carbon.measurement_runtime.model import MEASUREMENT_IDS, PHYSICS_IDS
from carbon.measurement_runtime.qualification_candidate import (
    frozen_public_measurement_manifest,
)
from carbon.reference_runtime.model import (
    BurgersReferenceRequest,
    BurgersReferenceRole,
    _cole_hopf,
    _finite_volume,
    build_reference_request,
    execute_reference,
    runtime_environment_digest,
    runtime_environment_manifest,
)
from carbon.reference_runtime.qualification_candidate import (
    frozen_public_campaign_manifest,
    run_qualification_candidate_harness,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin

SCHEMA = "carbon.d-qual-prep-01.readiness.v1"
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROTOCOL = Path(__file__).with_name("protocol_v1.json")
OUTPUT_FILES = (
    "primary_reference_evidence.json",
    "witness_refinement_evidence.json",
    "independence_matrix.json",
    "measurement_floor_sensitivity.json",
    "generator_dependency.json",
    "workbench_projection_status.json",
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


def _context(protocol: dict[str, Any]) -> MockContext:
    source = protocol["public_case_source"]
    return MockContext(
        MockEntropy(bytes.fromhex(source["mock_entropy_hex"])),
        SeedPin(
            ChallengeKey("burgers-dynamics-v1", "1.0"),
            source["generator_version"],
            source["generator_digest"],
            source["score_pack_version"],
            source["score_pack_digest"],
            EvaluationBinding(bytes.fromhex(source["evaluation_binding_hex"])),
        ),
    )


def _case(protocol: dict[str, Any], cell: int):
    return generate_development_case(
        _context(protocol),
        BurgersCaseCoordinates(PublicDevelopmentRole.EVAL, cell, 0, 0),
    )


def _times(case: Any, ratios: list[float]) -> tuple[float, ...]:
    return tuple(float(case.characteristic_time * ratio) for ratio in ratios)


def _request(
    case: Any,
    role: BurgersReferenceRole,
    ratios: list[float],
    environment_digest: str,
) -> BurgersReferenceRequest:
    return build_reference_request(
        case,
        role,
        output_points=64,
        requested_times=_times(case, ratios),
        environment_digest=environment_digest,
    )


def _run_document(run: Any) -> dict[str, object]:
    return {
        "request_digest": run.request_digest,
        "role": run.role.value,
        "outcome": run.outcome.value,
        "failure_reason": (
            None if run.failure_reason is None else run.failure_reason.value
        ),
        "artifact_digest": (
            None if run.artifact is None else run.artifact.artifact_digest
        ),
        "diagnostics": [list(item) for item in run.diagnostics],
        "scientifically_qualified": False,
        "protected_execution_eligible": False,
        "score_eligible": False,
    }


def _primary_history(
    request: BurgersReferenceRequest, grids: list[int]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    previous: np.ndarray | None = None
    for grid in grids:
        try:
            values, diagnostics = _cole_hopf(request, internal_grid_points=grid)
            change = (
                None if previous is None else float(np.max(np.abs(values - previous)))
            )
            rows.append(
                {
                    "internal_grid_points": grid,
                    "outcome": "SUPPORTED",
                    "failure_reason": None,
                    "maximum_absolute_change_from_previous_grid": change,
                    "initial_recovery_max_absolute": float(
                        diagnostics["initial_recovery_max_absolute"]
                    ),
                    "minimum_stabilized_phi": float(diagnostics["minimum_phi"]),
                    "maximum_mean_drift": float(
                        max(abs(float(np.mean(row)) - request.mean) for row in values)
                    ),
                    "value_digest": _sha256_bytes(
                        np.asarray(values, dtype="<f8", order="C").tobytes(order="C")
                    ),
                }
            )
            previous = values
        except (FloatingPointError, ValueError) as error:
            rows.append(
                {
                    "internal_grid_points": grid,
                    "outcome": "NUMERICAL_FAILURE",
                    "failure_reason": type(error).__name__,
                    "maximum_absolute_change_from_previous_grid": None,
                    "initial_recovery_max_absolute": None,
                    "minimum_stabilized_phi": None,
                    "maximum_mean_drift": None,
                    "value_digest": None,
                }
            )
            previous = None
    return rows


def _witness_history(
    request: BurgersReferenceRequest, grids: list[int]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    previous: np.ndarray | None = None
    for grid in grids:
        try:
            values, diagnostics = _finite_volume(request, internal_grid_points=grid)
            change = (
                None if previous is None else float(np.max(np.abs(values - previous)))
            )
            rows.append(
                {
                    "internal_grid_points": grid,
                    "cfl": request.settings.cfl,
                    "outcome": "SUPPORTED",
                    "failure_reason": None,
                    "steps": int(diagnostics["steps"]),
                    "maximum_absolute_change_from_previous_grid": change,
                    "maximum_mean_drift": float(diagnostics["maximum_mean_drift"]),
                    "value_digest": _sha256_bytes(
                        np.asarray(values, dtype="<f8", order="C").tobytes(order="C")
                    ),
                }
            )
            previous = values
        except (FloatingPointError, ValueError) as error:
            rows.append(
                {
                    "internal_grid_points": grid,
                    "cfl": request.settings.cfl,
                    "outcome": "NUMERICAL_FAILURE",
                    "failure_reason": type(error).__name__,
                    "steps": None,
                    "maximum_absolute_change_from_previous_grid": None,
                    "maximum_mean_drift": None,
                    "value_digest": None,
                }
            )
            previous = None
    return rows


def _partition_sensitivity(
    case: Any,
    baseline_request: BurgersReferenceRequest,
    baseline_run: Any,
    ratios: list[float],
    environment_digest: str,
) -> dict[str, object]:
    refined = _request(
        case, BurgersReferenceRole.INDEPENDENT_WITNESS, ratios, environment_digest
    )
    run = execute_reference(refined)
    row: dict[str, object] = {
        "label": "REQUESTED_TIME_PARTITION_SENSITIVITY_NOT_CFL_REFINEMENT",
        "request_digest": refined.request_digest,
        "time_over_characteristic_time": ratios,
        "outcome": run.outcome.value,
        "failure_reason": (
            None if run.failure_reason is None else run.failure_reason.value
        ),
        "maximum_absolute_change_at_shared_times": None,
    }
    if (
        run.outcome is ReferenceRunOutcome.SUPPORTED
        and run.artifact is not None
        and baseline_run.outcome is ReferenceRunOutcome.SUPPORTED
        and baseline_run.artifact is not None
    ):
        refined_values = run.artifact.array()[[0, 2, 4]]
        row["maximum_absolute_change_at_shared_times"] = float(
            np.max(np.abs(refined_values - baseline_run.artifact.array()))
        )
        row["artifact_digest"] = run.artifact.artifact_digest
    else:
        row["artifact_digest"] = None
    return row


def _independence_matrix() -> dict[str, object]:
    rows = [
        (
            "mathematical_formulation",
            "PARTIALLY_SHARED",
            "Same Burgers PDE and periodic BC; Cole-Hopf transform versus direct conservative form.",
        ),
        (
            "discretization",
            "DISTINCT",
            "Fourier quadrature versus finite-volume Rusanov flux.",
        ),
        (
            "time_integration",
            "DISTINCT",
            "Analytic viscous Fourier evolution versus explicit SSPRK3.",
        ),
        (
            "representation",
            "DISTINCT",
            "Transformed Fourier representation versus conservative physical-grid cells.",
        ),
        (
            "code",
            "PARTIALLY_SHARED",
            "Separate functions and method paths in one module and repository.",
        ),
        (
            "libraries",
            "SHARED",
            "Both execute in Python/NumPy under the same dependency lock.",
        ),
        (
            "generator",
            "SHARED",
            "Both consume the same C-AUTH1 public DEVELOPMENT cases.",
        ),
        (
            "environment",
            "SHARED",
            "Both use the same C-04 environment identity and host run.",
        ),
        (
            "personnel",
            "UNKNOWN",
            "No independently owned implementation or review personnel record is retained.",
        ),
        (
            "validation_data",
            "SHARED",
            "Both are compared on the same frozen twelve-cell sample.",
        ),
    ]
    return {
        "schema": "carbon.d-qual-prep-01.independence-matrix.v1",
        "allowed_classes": ["DISTINCT", "SHARED", "PARTIALLY_SHARED", "UNKNOWN"],
        "rows": [
            {"dimension": dimension, "classification": classification, "basis": basis}
            for dimension, classification, basis in rows
        ],
        "independence_percentage": None,
        "scientifically_qualified": False,
    }


def _measurement_record(protocol: dict[str, Any]) -> dict[str, object]:
    manifest = frozen_public_measurement_manifest()
    observable_rows = []
    for measurement_id in MEASUREMENT_IDS:
        observable_rows.append(
            {
                "measurement_id": measurement_id,
                "strata": [
                    {"shape_family": family, "reynolds_regime": regime}
                    for family in ("harmonic", "localized_packet", "multiscale")
                    for regime in range(4)
                ],
                "numerical_reference_floor_candidate": None,
                "minimum_distinguishable_difference": None,
                "reference_resolution_sensitivity": None,
                "within_case_reconstruction_variation": None,
                "across_replica_variation": None,
                "across_case_variation": None,
                "paired_rank_reversal_evidence": None,
                "censoring_rule": (
                    "RIGHT_CENSOR_AT_LAST_REQUESTED_TIME"
                    if measurement_id == "energy_half_time"
                    else "NOT_APPLICABLE"
                ),
                "readiness_disposition": "BLOCKED_INPUT",
                "blocked_inputs": [
                    "D02_GENERATOR_CONFORMANCE_EVIDENCE",
                    "RETAINED_C05_3_REPLICA_BY_12_CASE_RESULT_MATRIX_FOR_BOTH_RECIPES",
                    "REFERENCE_SETTING_PERTURBATION_MEASUREMENT_MATRIX",
                ],
            }
        )
    return {
        "schema": "carbon.d-qual-prep-01.measurement-floor-sensitivity.v1",
        "accepted_c05_manifest_digest": manifest["manifest_digest"],
        "campaign_shape": {
            "recipes": manifest["recipes"],
            "replicas_per_recipe": manifest["replicas_per_recipe"],
            "cases": len(manifest["case_coordinates"]),
            "expected_distinct_results": 72,
            "retained_result_matrix_path": protocol["measurement_study"][
                "retained_result_matrix_path"
            ],
        },
        "observable_rows": observable_rows,
        "physics_diagnostics": list(PHYSICS_IDS),
        "empirically_estimable_if_matrix_is_supplied": [
            "WITHIN_CASE_ACROSS_RECONSTRUCTION_REPLICAS",
            "ACROSS_CASES_AFTER_REPLICA_MEAN",
            "PAIRED_REPLICA_BY_CASE_RANK_REVERSALS",
        ],
        "currently_estimable_from_retained_accepted_records": [],
        "unknown_components": [
            "REFERENCE_RESOLUTION_AND_SETTINGS_SENSITIVITY",
            "QUALIFIED_TARGET_POPULATION_VARIABILITY",
            "STRESS_POPULATION_VARIABILITY",
            "CENSORING_FREQUENCY_BY_STRATUM",
            "DECISION_RESOLUTION_TARGET",
            "REPEAT_SUFFICIENCY",
        ],
        "scientific_limits": None,
        "decision_resolution_target": None,
        "repeat_count_selected": None,
        "score_input": None,
        "readiness_disposition": "BLOCKED_INPUT",
        "scientifically_qualified": False,
        "score_eligible": False,
    }


def _generator_record() -> dict[str, object]:
    missing = [
        "SUPPORT_AND_EXCLUSION_ACCOUNTING",
        "MARGINAL_DISTRIBUTION_CONFORMANCE",
        "JOINT_DISTRIBUTION_CONFORMANCE",
        "CONDITIONAL_DISTRIBUTION_CONFORMANCE",
        "STRATUM_MASS_AND_COVERAGE",
        "DUPLICATE_RATE_AND_IDENTITY",
        "RETRY_AND_CENSORING_ACCOUNTING",
        "INTENDED_VERSUS_REALIZED_POPULATION",
        "EXACT_MANIFEST_SEED_EXCLUSION_FAILURE_WEIGHT_AND_COVERAGE_EVIDENCE",
    ]
    return {
        "schema": "carbon.d-qual-prep-01.generator-dependency.v1",
        "c07_state": "ACCEPTED_BOUNDED_DEVELOPMENT_ORCHESTRATION",
        "d02_state": "FUTURE_RESERVED_UNSELECTED_UNSTARTED",
        "populations": {
            "public_development_source_population": {
                "state": "DEFINED_NOT_QUALIFIED",
                "counts": {"TRAIN": 72, "EVAL": 48, "STRESS": 120},
            },
            "realized_readiness_sample": {
                "state": "OBSERVED",
                "count": 12,
                "coordinates": "EVAL cells 0-11, ordinal 0, build 0",
            },
            "qualified_target_population": {
                "state": "BLOCKED_INPUT",
                "definition": None,
                "qualification": None,
            },
            "stress_or_diagnostic_population": {
                "state": "DEFINED_NOT_SAMPLED_BY_ACCEPTED_C04_C05_CAMPAIGNS",
                "available_public_stress_count": 120,
                "realized_count": 0,
            },
        },
        "missing_d02_evidence": missing,
        "d05_readiness_disposition": "BLOCKED_INPUT",
        "d05_can_proceed_to_qualification": False,
        "scientifically_qualified": False,
    }


def _workbench_record() -> dict[str, object]:
    return {
        "schema": "carbon.d-qual-prep-01.workbench-projection-status.v1",
        "goal_workbench_04_expected_commit": "0ea0ad8116ae4d912e866d11c52d6775a37d9813",
        "observed_main_revision": "ed6047d03cf60db6ce52f03e63040d95c1ea78e4",
        "expected_commit_is_ancestor_of_observed_main": False,
        "projection_eligible": False,
        "status": "BLOCKED_INPUT",
        "blocked_input": "GOAL_WORKBENCH_04_NORMAL_REPOSITORY_MERGE",
        "import_record": None,
        "allowed_future_import_class": "DEVELOPMENT_QUALIFICATION_CANDIDATE_EVIDENCE",
        "required_future_disposition": "HUMAN_SCIENTIFIC_DECISION_REQUIRED",
        "can_mint_qualification": False,
        "can_activate_scoring": False,
    }


def build_records(protocol_path: Path = DEFAULT_PROTOCOL) -> dict[str, object]:
    protocol = json.loads(protocol_path.read_text(encoding="ascii"))
    if protocol["schema"] != "carbon.d-qual-prep-01.protocol.v1":
        raise ValueError("unexpected campaign protocol")
    if protocol["scientific_thresholds"] is not None:
        raise ValueError("readiness protocol must not contain scientific thresholds")
    c04_manifest = frozen_public_campaign_manifest()
    if (
        c04_manifest["manifest_digest"]
        != protocol["upstream_identities"]["c04_campaign_manifest_digest"]
    ):
        raise ValueError("C-04 campaign identity drift")
    c05_manifest = frozen_public_measurement_manifest()
    if (
        c05_manifest["manifest_digest"]
        != protocol["upstream_identities"]["c05_campaign_manifest_digest"]
    ):
        raise ValueError("C-05 campaign identity drift")

    environment_digest = runtime_environment_digest()
    if environment_digest != protocol["upstream_identities"]["c04_environment_digest"]:
        raise ValueError("reference environment identity drift")

    primary_cases: list[dict[str, object]] = []
    witness_cases: list[dict[str, object]] = []
    base_ratios = protocol["query"]["time_over_characteristic_time"]
    partition_ratios = protocol["query"][
        "witness_partition_time_over_characteristic_time"
    ]
    for coordinate in protocol["public_case_source"]["case_coordinates"]:
        cell = coordinate["cell"]
        case = _case(protocol, cell)
        requests = tuple(
            _request(case, role, base_ratios, environment_digest)
            for role in BurgersReferenceRole
        )
        observation, runs = run_qualification_candidate_harness(*requests)
        run_documents = [_run_document(run) for run in runs]
        case_common = {
            "cell": cell,
            "ordinal": 0,
            "build": 0,
            "source_role": "EVAL",
            "case_digest": requests[0].case_digest,
            "shape_family": case.shape_family,
            "reynolds_regime": case.reynolds_regime,
            "reynolds_number": float(case.reynolds_number),
            "viscosity": float(case.viscosity),
            "domain_length": float(requests[0].domain_length),
            "equation": "u_t + u*u_x = viscosity*u_xx",
            "boundary_condition": "PERIODIC",
            "requested_time_over_characteristic_time": base_ratios,
        }
        if observation is None:
            primary_cases.append(
                {
                    **case_common,
                    "readiness_disposition": "MORE_PUBLIC_EVIDENCE_NEEDED",
                    "base_runs": run_documents,
                    "convergence_history": [],
                    "observations": None,
                }
            )
            witness_cases.append(
                {
                    **case_common,
                    "readiness_disposition": "MORE_PUBLIC_EVIDENCE_NEEDED",
                    "base_runs": run_documents,
                    "spatial_refinement_history": [],
                    "target_partition_sensitivity": None,
                    "observations": None,
                }
            )
            continue
        observed = observation.document()["observations"]
        primary_cases.append(
            {
                **case_common,
                "method": requests[0].method_id,
                "request_digest": requests[0].request_digest,
                "implementation_digest": requests[0].implementation_digest,
                "settings": requests[0].settings.document(),
                "readiness_disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
                "base_run": run_documents[0],
                "observations": {
                    key: observed[key]
                    for key in (
                        "initial_recovery_max_absolute",
                        "periodic_closure_max_absolute",
                        "cole_hopf_quadrature_change_max_absolute",
                        "primary_crosscheck_discrepancy_max_absolute",
                        "minimum_cole_hopf_phi",
                    )
                },
                "convergence_history": _primary_history(
                    requests[0], protocol["primary_study"]["quadrature_grid_points"]
                ),
            }
        )
        witness_cases.append(
            {
                **case_common,
                "method": requests[1].method_id,
                "request_digest": requests[1].request_digest,
                "implementation_digest": requests[1].implementation_digest,
                "settings": requests[1].settings.document(),
                "readiness_disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
                "base_run": run_documents[1],
                "observations": {
                    key: observed[key]
                    for key in (
                        "witness_spatial_refinement_change_max_absolute",
                        "witness_mean_drift_max_absolute",
                        "primary_witness_discrepancy_max_absolute",
                    )
                },
                "spatial_refinement_history": _witness_history(
                    requests[1],
                    protocol["witness_study"]["spatial_internal_grid_points"],
                ),
                "target_partition_sensitivity": _partition_sensitivity(
                    case, requests[1], runs[1], partition_ratios, environment_digest
                ),
            }
        )

    primary = {
        "schema": "carbon.d-qual-prep-01.primary-reference-evidence.v1",
        "scope": protocol["scope"],
        "method": "cole_hopf_fourier_quadrature",
        "cases": primary_cases,
        "readiness_by_dimension": [
            {
                "dimension": "initial_condition_recovery",
                "disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
            },
            {
                "dimension": "periodic_closure",
                "disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
            },
            {
                "dimension": "quadrature_sensitivity",
                "disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
            },
            {
                "dimension": "conditioning",
                "disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
            },
            {
                "dimension": "mean_invariant",
                "disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
            },
            {
                "dimension": "precision_sensitivity",
                "disposition": "METHOD_OR_APPLICABILITY_GAP",
            },
            {
                "dimension": "alternate_transform_sensitivity",
                "disposition": "METHOD_OR_APPLICABILITY_GAP",
            },
            {
                "dimension": "valid_limiting_cases",
                "disposition": "MORE_PUBLIC_EVIDENCE_NEEDED",
            },
            {
                "dimension": "empirical_failure_boundary",
                "disposition": "MORE_PUBLIC_EVIDENCE_NEEDED",
            },
        ],
        "overall_readiness_disposition": "MORE_PUBLIC_EVIDENCE_NEEDED",
        "scientific_thresholds": None,
        "scientifically_qualified": False,
    }
    witness = {
        "schema": "carbon.d-qual-prep-01.witness-refinement-evidence.v1",
        "scope": protocol["scope"],
        "method": "periodic_finite_volume_rusanov_ssprk3",
        "cases": witness_cases,
        "readiness_by_dimension": [
            {
                "dimension": "spatial_refinement",
                "disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
            },
            {
                "dimension": "conservation",
                "disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
            },
            {
                "dimension": "primary_witness_discrepancy",
                "disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
            },
            {
                "dimension": "requested_time_partition_sensitivity",
                "disposition": "EVIDENCE_READY_FOR_HUMAN_REVIEW",
            },
            {
                "dimension": "controlled_cfl_time_refinement",
                "disposition": "METHOD_OR_APPLICABILITY_GAP",
            },
            {
                "dimension": "empirical_nonconvergence_boundary",
                "disposition": "MORE_PUBLIC_EVIDENCE_NEEDED",
            },
            {"dimension": "independent_personnel", "disposition": "BLOCKED_INPUT"},
        ],
        "overall_readiness_disposition": "MORE_PUBLIC_EVIDENCE_NEEDED",
        "scientific_thresholds": None,
        "scientifically_qualified": False,
    }
    return {
        "primary_reference_evidence.json": primary,
        "witness_refinement_evidence.json": witness,
        "independence_matrix.json": _independence_matrix(),
        "measurement_floor_sensitivity.json": _measurement_record(protocol),
        "generator_dependency.json": _generator_record(),
        "workbench_projection_status.json": _workbench_record(),
    }


def run_campaign(protocol_path: Path, output_directory: Path) -> dict[str, object]:
    records = build_records(protocol_path)
    output_directory.mkdir(parents=True, exist_ok=True)
    file_digests: dict[str, str] = {}
    for name in OUTPUT_FILES:
        _write_json(output_directory / name, records[name])
        file_digests[name] = _sha256_file(output_directory / name)
    source_files = (
        "carbon/generators/burgers_dynamics.py",
        "carbon/reference_runtime/model.py",
        "carbon/reference_runtime/qualification_candidate.py",
        "carbon/measurement_runtime/model.py",
        "carbon/measurement_runtime/qualification_candidate.py",
    )
    readiness = {
        "schema": SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT_DETACHED_READINESS_ONLY",
        "protocol_digest": _sha256_file(protocol_path),
        "source_revision": json.loads(protocol_path.read_text(encoding="ascii"))[
            "source_revision"
        ],
        "source_file_digests": {
            name: _sha256_file(ROOT / name) for name in source_files
        },
        "execution_environment": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "host_platform": platform.platform(),
            "machine": platform.machine(),
            "numpy": np.__version__,
            "c04_declared_environment": runtime_environment_manifest(),
            "c04_environment_digest": runtime_environment_digest(),
            "canonical_linux_execution": False,
            "evidence_role": "NATIVE_MACOS_DIAGNOSTIC",
        },
        "outputs": file_digests,
        "d03_readiness": "MORE_PUBLIC_EVIDENCE_NEEDED",
        "d04_readiness": "MORE_PUBLIC_EVIDENCE_NEEDED",
        "d05_readiness": "BLOCKED_INPUT",
        "d02_dependency": "BLOCKED_INPUT",
        "goal_workbench_04_merge": "PENDING",
        "workbench_projection": "INELIGIBLE_BLOCKED_INPUT",
        "cpes_changed": False,
        "cpes_variant_a": "DEVELOPMENT_BASELINE",
        "cpes_variant_b": "CONDITIONAL_RESEARCH",
        "unresolved_cpes_blockers": ["AT-09", "AT-16", "AT-19", "AT-22", "AT-30"],
        "final_recommendation": "WAIT_FOR_D02_GENERATOR_CONFORMANCE",
        "authority": {
            "wave_d_selected": False,
            "tickets_activated": [],
            "scientific_thresholds": None,
            "scientifically_qualified": False,
            "protected_execution_eligible": False,
            "score_input": None,
            "score_eligible": False,
            "reward_eligible": False,
            "network_eligible": False,
            "production_eligible": False,
            "live_eligible": False,
        },
    }
    _write_json(output_directory / "readiness_record.json", readiness)
    return readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    result = run_campaign(args.protocol.resolve(), args.output_dir.resolve())
    print(_canonical(result).decode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
