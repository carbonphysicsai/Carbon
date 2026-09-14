from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from carbon.generators.burgers_dynamics import (
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    generate_development_case,
)
from carbon.measurement_runtime.model import (
    MEASUREMENT_IDS,
    PHYSICS_IDS,
    BurgersMeasurementResult,
    EvidenceDecision,
    FrozenFieldArtifact,
    MeasurementDisposition,
    build_measurement_request,
    execute_measurement,
)
from carbon.measurement_runtime.protocol import (
    decode_measurement_request,
    load_staged_measurement,
    run_staged_measurement_worker,
    stage_measurement_request,
    validate_measurement_snapshot,
)
from carbon.measurement_runtime.qualification_candidate import (
    CASE_COUNT,
    RECIPE_IDS,
    REPLICA_COUNT,
    frozen_public_measurement_manifest,
    run_measurement_calibration_candidate,
)
from carbon.reconstruction.worker.model import WorkerFailure
from carbon.reference_runtime.model import (
    BurgersReferenceRole,
    build_reference_request,
    execute_reference,
    runtime_environment_digest,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin


def _sha(character: str) -> str:
    return "sha256:" + character * 64


def _inputs(*, cell: int = 2, perturbation: float = 0.0):
    context = MockContext(
        MockEntropy(b"m" * 32),
        SeedPin(
            ChallengeKey("burgers-dynamics-v1", "1.0"),
            "1.0",
            _sha("1"),
            "1.0",
            _sha("2"),
            EvaluationBinding(b"q" * 32),
        ),
    )
    case = generate_development_case(
        context, BurgersCaseCoordinates(PublicDevelopmentRole.EVAL, cell, 0)
    )
    reference_request = build_reference_request(
        case,
        BurgersReferenceRole.CANDIDATE_PRIMARY,
        output_points=64,
        requested_times=(
            0.0,
            float(0.1 * case.characteristic_time),
            float(0.25 * case.characteristic_time),
            float(0.5 * case.characteristic_time),
            float(case.characteristic_time),
            float(2.0 * case.characteristic_time),
            float(4.0 * case.characteristic_time),
        ),
        environment_digest=runtime_environment_digest(),
    )
    reference_run = execute_reference(reference_request)
    assert reference_run.artifact is not None
    values = reference_run.artifact.array()
    if perturbation:
        points = np.asarray(reference_request.spatial_points)
        values = values + perturbation * np.sin(points)[None, :]
    candidate = FrozenFieldArtifact(
        _sha("a"),
        values.shape,
        np.asarray(values, dtype="<f8").tobytes(order="C"),
        "CANDIDATE_PREDICTION",
    )
    request = build_measurement_request(
        case,
        reference_request,
        reference_run.artifact,
        candidate,
        candidate_source_digest=_sha("b"),
        candidate_environment_digest=_sha("c"),
        candidate_plan_digest=_sha("d"),
        candidate_replica_id="reconstruction-replica-0",
    )
    reference = FrozenFieldArtifact(
        reference_request.request_digest,
        reference_run.artifact.shape,
        reference_run.artifact.payload,
        "REFERENCE_PRIMARY",
    )
    return case, request, candidate, reference


def test_real_measurements_are_exactly_bound_and_never_score_eligible() -> None:
    case, request, candidate, reference = _inputs(perturbation=1e-4)
    result = execute_measurement(request, candidate, reference)

    assert result.disposition is MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY
    assert tuple(item.measurement_id for item in result.measurements) == MEASUREMENT_IDS
    assert tuple(item.physics_id for item in result.physics) == PHYSICS_IDS
    assert all(item.raw_absolute_error >= 0.0 for item in result.measurements)
    assert all(item.normalized_error >= 0.0 for item in result.measurements)
    assert all(
        item.decision is EvidenceDecision.UNRESOLVED_NO_QUALIFIED_LIMIT
        for item in result.measurements
    )
    assert all(
        item.decision is EvidenceDecision.UNRESOLVED_NO_QUALIFIED_LIMIT
        for item in result.physics
    )
    assert result.score_input is None
    assert result.score_eligible is False
    assert result.scientifically_qualified is False
    assert request.domain_length != 1.0
    assert request.viscosity == case.viscosity
    assert request.measurement_contract_digest.startswith("sha256:")


def test_identical_candidate_retains_raw_zero_errors_without_inventing_pass() -> None:
    _, request, candidate, reference = _inputs()
    result = execute_measurement(request, candidate, reference)

    assert [item.raw_absolute_error for item in result.measurements] == [0.0] * 4
    assert all(
        item.decision is EvidenceDecision.UNRESOLVED_NO_QUALIFIED_LIMIT
        for item in result.measurements
    )
    assert all(item.scientific_limit is None for item in result.measurements)


def test_closed_request_round_trip_and_every_identity_affects_digest() -> None:
    _, request, _, _ = _inputs()
    document = request.document()
    assert decode_measurement_request(document) == request
    assert decode_measurement_request(json.loads(json.dumps(document))) == request
    changed = replace(request, candidate_plan_digest=_sha("e"))
    assert changed.request_digest != request.request_digest
    with pytest.raises(ValueError):
        decode_measurement_request({**document, "approved": True})
    laundering = json.loads(json.dumps(document))
    laundering["eligibility"]["score"] = True
    with pytest.raises(ValueError):
        decode_measurement_request(laundering)


def test_staging_is_read_only_and_cross_artifact_rejects(tmp_path: Path) -> None:
    _, request, candidate, reference = _inputs()
    stage, stage_digest = stage_measurement_request(
        (tmp_path / "staging").resolve(), request, candidate, reference
    )
    assert stage_digest.startswith("sha256:")
    loaded = load_staged_measurement(stage)
    assert loaded == (request, candidate, reference)
    assert all(not (member.stat().st_mode & 0o222) for member in stage.iterdir())
    wrong_candidate = replace(candidate, binding_digest=_sha("f"))
    with pytest.raises(WorkerFailure):
        stage_measurement_request(
            (tmp_path / "other").resolve(), request, wrong_candidate, reference
        )


def test_worker_snapshot_round_trip_and_late_or_unknown_output_rejects(
    tmp_path: Path,
) -> None:
    _, request, candidate, reference = _inputs(perturbation=1e-5)
    stage, _ = stage_measurement_request(
        (tmp_path / "staging").resolve(), request, candidate, reference
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    assert run_staged_measurement_worker(stage, scratch) == 0
    result = validate_measurement_snapshot(scratch / "output", stage)
    assert type(result) is BurgersMeasurementResult
    assert result.score_eligible is False
    # Test-only negative control: remove the worker's write guard, then prove
    # that a newly added member cannot pass controller validation.
    (scratch / "output").chmod(0o700)
    (scratch / "output" / "late-write").write_bytes(b"late")
    with pytest.raises(WorkerFailure):
        validate_measurement_snapshot(scratch / "output", stage)


@pytest.mark.parametrize("target", ["candidate", "reference"])
def test_nonfinite_or_changed_artifact_cannot_enter_measurement(target: str) -> None:
    _, request, candidate, reference = _inputs()
    selected = candidate if target == "candidate" else reference
    payload = bytearray(selected.payload)
    payload[:8] = np.asarray([np.nan], dtype="<f8").tobytes()
    with pytest.raises(ValueError):
        replace(selected, payload=bytes(payload))
    changed = bytearray(selected.payload)
    changed[8:16] = np.asarray([123.0], dtype="<f8").tobytes()
    changed_artifact = replace(selected, payload=bytes(changed))
    with pytest.raises(ValueError):
        execute_measurement(
            request,
            changed_artifact if target == "candidate" else candidate,
            changed_artifact if target == "reference" else reference,
        )


def test_candidate_specific_commercial_or_reward_fields_are_not_in_protocol() -> None:
    _, request, _, _ = _inputs()
    serialized = json.dumps(request.document(), sort_keys=True)
    for forbidden in (
        "payment",
        "product",
        "novelty",
        "practice",
        "forecast",
        "reward",
        "rank",
        "wallet",
        "customer",
    ):
        assert forbidden not in serialized.lower()


def test_d05_prerequisite_harness_separates_variability_and_stays_ineligible() -> None:
    _, request, candidate, reference = _inputs(perturbation=1e-5)
    base = execute_measurement(request, candidate, reference)
    matrices = {}
    for recipe_index, recipe in enumerate(RECIPE_IDS):
        replicas = []
        for replica in range(REPLICA_COUNT):
            cases = []
            for case in range(CASE_COUNT):
                observations = tuple(
                    replace(
                        item,
                        raw_absolute_error=float(
                            item.normalized_error
                            + 0.001 * recipe_index
                            + 0.0001 * replica
                            + 0.00001 * case
                            + 0.000001 * metric
                        ),
                        normalization_scale=1.0,
                        normalized_error=float(
                            item.normalized_error
                            + 0.001 * recipe_index
                            + 0.0001 * replica
                            + 0.00001 * case
                            + 0.000001 * metric
                        ),
                    )
                    for metric, item in enumerate(base.measurements)
                )
                digest = (
                    "sha256:"
                    + hashlib.sha256(
                        f"{recipe}:{replica}:{case}".encode("ascii")
                    ).hexdigest()
                )
                cases.append(
                    replace(base, request_digest=digest, measurements=observations)
                )
            replicas.append(tuple(cases))
        matrices[recipe] = tuple(replicas)
    result = run_measurement_calibration_candidate(matrices)
    manifest = frozen_public_measurement_manifest()

    assert manifest["replicas_per_recipe"] == 3
    assert len(manifest["case_coordinates"]) == 12
    assert manifest["decision_resolution_target"]["state"] == "HUMAN_INPUT"
    assert len(result.observations) == 8
    assert result.paired_comparisons > 0
    assert 0.0 <= result.rank_reversal_fraction <= 1.0
    assert result.alternative_replica_count is None
    assert result.scientifically_qualified is False
    assert result.score_eligible is False
    assert result.recommendation == (
        "KEEP_PROFILE_INELIGIBLE_PENDING_D05_TARGET_AND_FLOORS"
    )


def test_frozen_campaign_file_matches_code_manifest() -> None:
    path = Path("docs/development/c05_public_measurement_campaign_v1.json")
    assert json.loads(path.read_text(encoding="utf-8")) == (
        frozen_public_measurement_manifest()
    )
