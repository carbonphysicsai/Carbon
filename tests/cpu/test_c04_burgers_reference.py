from __future__ import annotations

import json
import math
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from carbon.evaluation.enums import ReferenceFailureReason, ReferenceRunOutcome
from carbon.generators.burgers_dynamics import (
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    evaluate_initial_field,
    generate_development_case,
)
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure
from carbon.reconstruction.worker.protocol import snapshot_output
from carbon.reference_runtime.controller import _snapshot_digest
from carbon.reference_runtime.model import (
    OUTPUT_SEMANTICS,
    POLICY_ID,
    SCOPE,
    BurgersReferenceArtifact,
    BurgersReferenceRequest,
    BurgersReferenceRole,
    BurgersReferenceRun,
    build_reference_request,
    compare_candidate_runs,
    decode_reference_request,
    execute_reference,
    reference_settings,
    runtime_environment_digest,
)
from carbon.reference_runtime.protocol import (
    ValidatedReferenceResult,
    load_staged_reference_request,
    run_staged_reference_worker,
    stage_reference_request,
    validate_reference_snapshot,
    validate_reference_snapshot_bounded,
)
from carbon.reference_runtime.qualification_candidate import (
    CAMPAIGN_CELLS,
    frozen_public_campaign_manifest,
    run_qualification_candidate_harness,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin

ENVIRONMENT_DIGEST = runtime_environment_digest()
ROOT = Path(__file__).resolve().parents[2]


def _context(material: bytes = b"c" * 32) -> MockContext:
    return MockContext(
        MockEntropy(material),
        SeedPin(
            ChallengeKey("burgers-dynamics-v1", "1.0"),
            "1.0",
            "sha256:" + "1" * 64,
            "1.0",
            "sha256:" + "2" * 64,
            EvaluationBinding(b"e" * 32),
        ),
    )


def _case(cell: int = 0):
    return generate_development_case(
        _context(), BurgersCaseCoordinates(PublicDevelopmentRole.EVAL, cell, 0)
    )


def _times(case) -> tuple[float, ...]:
    return (
        0.0,
        float(case.characteristic_time * 0.1),
        float(case.characteristic_time * 0.25),
    )


def _request(role: BurgersReferenceRole, *, cell: int = 0, points: int = 64):
    case = _case(cell)
    return build_reference_request(
        case,
        role,
        output_points=points,
        requested_times=_times(case),
        environment_digest=ENVIRONMENT_DIGEST,
    )


@pytest.mark.parametrize("role", tuple(BurgersReferenceRole))
def test_all_roles_execute_real_finite_numerics_without_authority(role) -> None:
    request = _request(role)
    run = execute_reference(request)
    assert run.outcome is ReferenceRunOutcome.SUPPORTED
    assert run.failure_reason is None
    assert run.artifact is not None
    assert run.artifact.shape == (3, 64)
    assert run.artifact.array().dtype == np.dtype("float64")
    assert np.isfinite(run.artifact.array()).all()
    assert run.scientifically_qualified is False
    assert run.protected_execution_eligible is False
    assert run.score_eligible is False


def test_primary_recovers_nonunit_physical_initial_state_and_request_order() -> None:
    length = 3.5
    points = tuple(length * index / 64 for index in range(64))
    request = BurgersReferenceRequest(
        case_digest="sha256:" + "3" * 64,
        role=BurgersReferenceRole.CANDIDATE_PRIMARY,
        spatial_points=points,
        requested_times=(0.0, 0.03, 0.07),
        domain_length=length,
        viscosity=0.08,
        mean=0.17,
        cosine_coefficients=(0.2, -0.04) + (0.0,) * 10,
        sine_coefficients=(0.11, 0.03) + (0.0,) * 10,
        environment_digest=ENVIRONMENT_DIGEST,
        settings=reference_settings(BurgersReferenceRole.CANDIDATE_PRIMARY, 64),
    )
    run = execute_reference(request)
    assert run.artifact is not None
    modes = np.arange(1, 13)
    phase = np.outer(np.asarray(points) * 2.0 * np.pi / length, modes)
    expected = (
        request.mean
        + np.cos(phase) @ np.asarray(request.cosine_coefficients)
        + np.sin(phase) @ np.asarray(request.sine_coefficients)
    )
    assert np.max(np.abs(run.artifact.array()[0] - expected)) < 2e-12
    assert run.artifact.output_semantics == OUTPUT_SEMANTICS


def test_conservative_witness_retains_periodic_mean_evidence() -> None:
    run = execute_reference(_request(BurgersReferenceRole.INDEPENDENT_WITNESS))
    assert run.artifact is not None
    diagnostic = dict(run.diagnostics)
    assert diagnostic["method"] == "periodic_finite_volume_rusanov_ssprk3"
    assert diagnostic["maximum_mean_drift"] < 1e-6
    values = run.artifact.array()
    assert np.isfinite(values).all()


def test_witness_spatial_refinement_is_retained_without_qualification_claim() -> None:
    coarse = execute_reference(
        _request(BurgersReferenceRole.INDEPENDENT_WITNESS, points=64)
    )
    fine = execute_reference(
        _request(BurgersReferenceRole.INDEPENDENT_WITNESS, points=128)
    )
    primary = execute_reference(
        _request(BurgersReferenceRole.CANDIDATE_PRIMARY, points=64)
    )
    assert coarse.artifact and fine.artifact and primary.artifact
    coarse_error = np.max(np.abs(coarse.artifact.array() - primary.artifact.array()))
    fine_on_coarse = fine.artifact.array()[:, ::2]
    fine_error = np.max(np.abs(fine_on_coarse - primary.artifact.array()))
    assert math.isfinite(float(coarse_error)) and math.isfinite(float(fine_error))
    assert dict(coarse.diagnostics)["steps"] != dict(fine.diagnostics)["steps"]
    assert coarse.scientifically_qualified is False


def test_primary_time_batch_invariance_for_exact_queries() -> None:
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    together = execute_reference(request)
    assert together.artifact is not None
    separately = []
    for value in request.requested_times:
        single = execute_reference(replace(request, requested_times=(value,)))
        assert single.artifact is not None
        separately.append(single.artifact.array()[0])
    assert np.array_equal(together.artifact.array(), np.asarray(separately))


def test_full_cache_identity_changes_for_every_material_binding() -> None:
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    variants = (
        replace(request, environment_digest="sha256:" + "4" * 64),
        replace(request, case_digest="sha256:" + "5" * 64),
        replace(request, requested_times=(0.0, request.requested_times[1])),
        replace(
            request,
            cosine_coefficients=(request.cosine_coefficients[0] + 0.001,)
            + request.cosine_coefficients[1:],
        ),
        _request(BurgersReferenceRole.INDEPENDENT_WITNESS),
    )
    assert (
        len({request.request_digest, *(item.request_digest for item in variants)}) == 6
    )
    assert "/" not in request.request_digest


def test_closed_decoder_rejects_relabeling_unknown_fields_and_method_mismatch() -> None:
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    assert decode_reference_request(request.document()) == request
    for mutate in ("eligible", "unknown", "method"):
        value = json.loads(json.dumps(request.document()))
        if mutate == "eligible":
            value["eligibility"]["protected_execution"] = True
        elif mutate == "unknown":
            value["caller_path"] = "/host/home"
        else:
            value["method"]["id"] = "fallback"
        with pytest.raises(ValueError):
            decode_reference_request(value)


def test_request_rejects_nonperiodic_grid_and_nonmonotonic_times() -> None:
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    with pytest.raises(ValueError):
        replace(request, spatial_points=(0.1,) + request.spatial_points[1:])
    with pytest.raises(ValueError):
        replace(request, requested_times=(0.1, 0.0))


def test_comparison_retains_unresolved_discrepancy_without_vote_or_tolerance() -> None:
    primary = execute_reference(_request(BurgersReferenceRole.CANDIDATE_PRIMARY))
    witness = execute_reference(_request(BurgersReferenceRole.INDEPENDENT_WITNESS))
    result = compare_candidate_runs(primary, witness)
    assert result["outcome"] == "UNRESOLVED_DISCREPANCY_EVIDENCE"
    assert result["scientific_tolerance"] is None
    assert result["truth_admitted"] is False
    assert "winner" not in result and "average" not in result


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        (
            ReferenceRunOutcome.UNSUPPORTED,
            ReferenceFailureReason.POLICY_ENTRY_UNSUPPORTED,
        ),
        (ReferenceRunOutcome.CANCELLED, ReferenceFailureReason.TRUSTED_CANCELLATION),
        (ReferenceRunOutcome.INFRASTRUCTURE_FAILURE, ReferenceFailureReason.TIMEOUT),
        (
            ReferenceRunOutcome.NUMERICAL_FAILURE,
            ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
        ),
        (
            ReferenceRunOutcome.UNCERTAINTY_UNRESOLVED,
            ReferenceFailureReason.UNCERTAINTY_EVIDENCE_UNRESOLVED,
        ),
    ],
)
def test_failure_outcomes_remain_typed_non_candidate(outcome, reason) -> None:
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    run = BurgersReferenceRun(
        request.request_digest,
        request.role,
        outcome,
        reason,
        None,
        (("cause", reason.value),),
    )
    assert run.artifact is None
    assert run.score_eligible is False


def test_outcome_reason_mismatch_rejects() -> None:
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    with pytest.raises(ValueError):
        BurgersReferenceRun(
            request.request_digest,
            request.role,
            ReferenceRunOutcome.CANCELLED,
            ReferenceFailureReason.TIMEOUT,
            None,
            (),
        )


def test_raw_artifact_round_trip_is_exact_and_nonfinite_rejects() -> None:
    run = execute_reference(_request(BurgersReferenceRole.CANDIDATE_PRIMARY))
    assert run.artifact is not None
    rebuilt = BurgersReferenceArtifact(
        run.artifact.request_digest, run.artifact.shape, bytes(run.artifact.payload)
    )
    assert rebuilt.artifact_digest == run.artifact.artifact_digest
    assert np.array_equal(rebuilt.array(), run.artifact.array())
    bad = bytearray(run.artifact.payload)
    bad[:8] = np.asarray([np.nan], dtype="<f8").tobytes()
    with pytest.raises(ValueError, match="nonfinite"):
        BurgersReferenceArtifact(
            run.artifact.request_digest, run.artifact.shape, bytes(bad)
        )


def test_validated_result_rejects_non_hex_artifact_identity() -> None:
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    with pytest.raises(ValueError, match="invalid validated reference result"):
        ValidatedReferenceResult(
            request.request_digest,
            request.role,
            ReferenceRunOutcome.SUPPORTED,
            None,
            "sha256:" + "z" * 64,
            8,
            (1, 1),
            (),
        )


def test_staging_worker_and_separate_validator_round_trip(tmp_path: Path) -> None:
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    stage, _ = stage_reference_request((tmp_path / "stages").resolve(), request)
    assert load_staged_reference_request(stage) == request
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    assert run_staged_reference_worker(stage, scratch) == 0
    result = validate_reference_snapshot(scratch / "output", request)
    bounded = validate_reference_snapshot_bounded(scratch / "output", stage)
    assert bounded == result
    assert result.outcome is ReferenceRunOutcome.SUPPORTED
    assert result.eligible_for_truth_or_score is False


def test_duplicate_json_symlink_and_changed_output_reject(tmp_path: Path) -> None:
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    stage, _ = stage_reference_request((tmp_path / "stages").resolve(), request)
    staged = stage / "reference-request.json"
    staged.chmod(0o600)
    staged.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
    with pytest.raises(WorkerFailure) as duplicate:
        load_staged_reference_request(stage)
    assert duplicate.value.code is WorkerCode.INVALID

    symlink_stage = tmp_path / "symlink-stage"
    symlink_stage.mkdir()
    os.symlink(staged, symlink_stage / "reference-request.json")
    with pytest.raises(WorkerFailure):
        load_staged_reference_request(symlink_stage)

    clean_stage, _ = stage_reference_request((tmp_path / "clean").resolve(), request)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    assert run_staged_reference_worker(clean_stage, scratch) == 0
    payload = scratch / "output" / "solution.f64le"
    payload.chmod(0o600)
    data = bytearray(payload.read_bytes())
    data[-1] ^= 1
    payload.write_bytes(data)
    with pytest.raises(WorkerFailure) as changed:
        validate_reference_snapshot(scratch / "output", request)
    assert changed.value.code is WorkerCode.OUTPUT


def test_retained_snapshot_identity_detects_valid_manifest_change(
    tmp_path: Path,
) -> None:
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    stage, _ = stage_reference_request((tmp_path / "stages").resolve(), request)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    assert run_staged_reference_worker(stage, scratch) == 0
    snapshot, expected = snapshot_output(
        scratch / "output",
        (tmp_path / "snapshots").resolve(),
        destination_name="a" * 64,
    )
    assert _snapshot_digest(snapshot) == expected

    manifest_path = snapshot / "result.json"
    manifest_path.chmod(0o600)
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest["diagnostics"].append(["tampered_but_well_typed", 1])
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    assert _snapshot_digest(snapshot) != expected


def test_generated_case_initial_values_match_primary_at_time_zero() -> None:
    case = _case(7)
    request = build_reference_request(
        case,
        BurgersReferenceRole.CANDIDATE_PRIMARY,
        output_points=64,
        requested_times=(0.0,),
        environment_digest=ENVIRONMENT_DIGEST,
    )
    run = execute_reference(request)
    assert run.artifact is not None
    expected = evaluate_initial_field(case, request.spatial_points)
    observed = float(np.max(np.abs(run.artifact.array()[0] - np.asarray(expected))))
    assert math.isfinite(observed)
    assert dict(run.diagnostics)["initial_recovery_max_absolute"] == pytest.approx(
        observed, rel=0.0, abs=np.finfo(float).eps
    )
    assert run.scientifically_qualified is False


def test_public_scope_and_method_independence_are_explicit() -> None:
    primary = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    witness = _request(BurgersReferenceRole.INDEPENDENT_WITNESS)
    crosscheck = _request(BurgersReferenceRole.DEVELOPMENT_CROSSCHECK)
    assert primary.document()["scope"] == SCOPE
    assert primary.document()["policy"]["id"] == POLICY_ID
    assert {primary.method_id, witness.method_id, crosscheck.method_id} == {
        "cole_hopf_fourier_quadrature",
        "periodic_finite_volume_rusanov_ssprk3",
        "dealiased_fourier_etdrk4",
    }
    assert primary.document()["method"]["evidence_kind"] == "SEMI_ANALYTIC"
    assert witness.document()["method"]["evidence_kind"] == "NUMERICAL"


def test_frozen_campaign_covers_one_public_case_per_registered_cell() -> None:
    manifest = frozen_public_campaign_manifest()
    tracked = json.loads(
        (ROOT / "docs/development/c04_public_reference_campaign_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert tracked == manifest
    assert CAMPAIGN_CELLS == tuple(range(12))
    assert manifest["case_count"] == 12
    assert [item["cell"] for item in manifest["case_coordinates"]] == list(range(12))
    assert manifest["scientific_tolerances"] is None
    assert manifest["scientifically_qualified"] is False
    assert manifest["protected_execution_eligible"] is False
    assert manifest["score_eligible"] is False
    assert manifest["manifest_digest"].startswith("sha256:")


@pytest.mark.parametrize("cell", CAMPAIGN_CELLS)
def test_d03_d04_prerequisite_harness_retains_unjudged_evidence(cell: int) -> None:
    requests = tuple(_request(role, cell=cell) for role in BurgersReferenceRole)
    observation, runs = run_qualification_candidate_harness(*requests)
    assert observation is not None
    assert len(runs) == 3
    assert all(run.outcome is ReferenceRunOutcome.SUPPORTED for run in runs)
    document = observation.document()
    assert document["decision"] == "EVIDENCE_ONLY_UNRESOLVED"
    assert document["scientific_tolerance"] is None
    assert document["scientifically_qualified"] is False
    assert document["protected_execution_eligible"] is False
    assert document["score_eligible"] is False
    assert dict(observation.shared_dependencies)["discretization"] == "DISTINCT"
    assert dict(observation.shared_dependencies)["independent_human_review"] == (
        "UNAVAILABLE"
    )
