"""Required Docker-backed C-05 public measurement evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from carbon.generators.burgers_dynamics import (
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    generate_development_case,
)
from carbon.measurement_runtime.controller import (
    IsolatedBurgersMeasurementController,
)
from carbon.measurement_runtime.model import (
    FrozenFieldArtifact,
    MeasurementDisposition,
    build_measurement_request,
)
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.reconstruction.worker.model import DevelopmentWorkerProfile
from carbon.reference_runtime.controller import IsolatedBurgersReferenceController
from carbon.reference_runtime.model import (
    BurgersReferenceArtifact,
    BurgersReferenceRole,
    build_reference_request,
    runtime_environment_digest,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin


def _sha(character: str) -> str:
    return "sha256:" + character * 64


def _trace(kind: str, **details: object) -> None:
    target = os.environ.get("CARBON_C03_TRACE_PATH")
    if not target:
        return
    with Path(target).open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "schema": "carbon.c05.development-service-trace.v1",
                    "kind": kind,
                    "scientifically_qualified": False,
                    "protected_execution_eligible": False,
                    "score_eligible": False,
                    **details,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )


def _case():
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
    return generate_development_case(
        context, BurgersCaseCoordinates(PublicDevelopmentRole.EVAL, 5, 0)
    )


def test_reference_then_measurement_run_in_distinct_verified_workers(
    tmp_path: Path,
) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest, "required service lane must supply the exact image manifest"
    image = load_image_identity(Path(manifest))
    profile = DevelopmentWorkerProfile(_sha("2"), _sha("3"))
    case = _case()
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
    reference_run = IsolatedBurgersReferenceController(
        state_root=(tmp_path / "reference-state").resolve(),
        image=image,
        worker_profile=profile,
    ).execute(reference_request)
    assert reference_run.result.artifact_digest is not None
    payload = (reference_run.snapshot_path / "solution.f64le").read_bytes()
    reference_artifact = BurgersReferenceArtifact(
        reference_request.request_digest,
        (len(reference_request.requested_times), len(reference_request.spatial_points)),
        payload,
    )
    assert reference_artifact.artifact_digest == reference_run.result.artifact_digest
    values = reference_artifact.array()
    perturbation = 1e-5 * np.sin(np.asarray(reference_request.spatial_points))[None, :]
    candidate = FrozenFieldArtifact(
        _sha("a"),
        values.shape,
        np.asarray(values + perturbation, dtype="<f8").tobytes(order="C"),
        "CANDIDATE_PREDICTION",
    )
    request = build_measurement_request(
        case,
        reference_request,
        reference_artifact,
        candidate,
        candidate_source_digest=_sha("b"),
        candidate_environment_digest=_sha("c"),
        candidate_plan_digest=_sha("d"),
        candidate_replica_id="reconstruction-replica-0",
    )
    controller = IsolatedBurgersMeasurementController(
        state_root=(tmp_path / "measurement-state").resolve(),
        image=image,
        worker_profile=profile,
    )
    isolated = controller.execute(
        request,
        candidate,
        FrozenFieldArtifact(
            reference_request.request_digest,
            reference_artifact.shape,
            reference_artifact.payload,
            "REFERENCE_PRIMARY",
        ),
    )
    assert (
        isolated.result.disposition is MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY
    )
    assert isolated.result.score_input is None
    assert isolated.result.score_eligible is False
    assert isolated.controls["process"] == {
        "CapEff": "0000000000000000",
        "NoNewPrivs": "1",
        "Seccomp": "2",
    }
    assert isolated.controls["cgroup_v2"]["memory.swap.max"] == "0"
    assert isolated.resources["memory"]["peak_bytes"] is not None
    assert isolated.resources["cpu"]["usage_usec"] > 0
    assert isolated.resources["output_snapshot"]["observed_members"] == 1
    assert not (isolated.snapshot_path / "score-input.json").exists()
    replay = controller.execute(
        request,
        candidate,
        FrozenFieldArtifact(
            reference_request.request_digest,
            reference_artifact.shape,
            reference_artifact.payload,
            "REFERENCE_PRIMARY",
        ),
    )
    assert replay.result == isolated.result
    assert replay.controls == {"retained_exact_replay": True}
    _trace(
        "separate_reference_measurement_and_exact_replay",
        image_id=image.image_id,
        reference_launch_digest=reference_run.launch_digest,
        measurement_launch_digest=isolated.launch_digest,
        reference_artifact_digest=reference_artifact.artifact_digest,
        candidate_artifact_digest=candidate.artifact_digest,
        measurement_result_digest=isolated.result.result_digest,
        new_measurement_effects=1,
        replay_measurement_effects=0,
        timings_seconds=isolated.timings,
        resources=isolated.resources,
    )
