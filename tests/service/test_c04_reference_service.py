"""Required Docker-backed C-04 public qualification-candidate evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from carbon.evaluation.enums import ReferenceFailureReason, ReferenceRunOutcome
from carbon.generators.burgers_dynamics import (
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    generate_development_case,
)
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.reconstruction.worker.model import DevelopmentWorkerProfile
from carbon.reference_runtime.controller import (
    IsolatedBurgersReferenceController,
)
from carbon.reference_runtime.model import (
    BurgersReferenceRole,
    build_reference_request,
    runtime_environment_digest,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin


def _sha(character: str) -> str:
    return "sha256:" + character * 64


def _request(role: BurgersReferenceRole, *, cell: int = 0):
    context = MockContext(
        MockEntropy(b"c" * 32),
        SeedPin(
            ChallengeKey("burgers-dynamics-v1", "1.0"),
            "1.0",
            _sha("1"),
            "1.0",
            _sha("2"),
            EvaluationBinding(b"e" * 32),
        ),
    )
    case = generate_development_case(
        context, BurgersCaseCoordinates(PublicDevelopmentRole.EVAL, cell, 0)
    )
    return build_reference_request(
        case,
        role,
        output_points=64,
        requested_times=(
            0.0,
            float(0.1 * case.characteristic_time),
            float(0.25 * case.characteristic_time),
        ),
        environment_digest=runtime_environment_digest(),
    )


def _trace(kind: str, **details: object) -> None:
    target = os.environ.get("CARBON_C03_TRACE_PATH")
    if not target:
        return
    with Path(target).open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "schema": "carbon.c04.development-service-trace.v1",
                    "kind": kind,
                    "scientifically_qualified": False,
                    "protected_execution_eligible": False,
                    **details,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )


@pytest.mark.parametrize("role", tuple(BurgersReferenceRole))
def test_role_explicit_reference_runs_under_verified_worker_controls(
    tmp_path: Path, role: BurgersReferenceRole
) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest, "required service lane must supply the exact image manifest"
    image = load_image_identity(Path(manifest))
    request = _request(role)
    controller = IsolatedBurgersReferenceController(
        state_root=(tmp_path / "reference-state").resolve(),
        image=image,
        worker_profile=DevelopmentWorkerProfile(_sha("2"), _sha("3")),
    )
    isolated = controller.execute(request)
    assert isolated.result.outcome is ReferenceRunOutcome.SUPPORTED
    assert isolated.result.artifact_digest is not None
    assert isolated.result.shape == (3, 64)
    assert isolated.result.eligible_for_truth_or_score is False
    assert isolated.controls["process"] == {
        "CapEff": "0000000000000000",
        "NoNewPrivs": "1",
        "Seccomp": "2",
    }
    assert isolated.controls["cgroup_v2"]["memory.swap.max"] == "0"
    assert isolated.resources["memory"]["peak_bytes"] is not None
    assert isolated.resources["cpu"]["usage_usec"] > 0
    assert isolated.resources["output_snapshot"]["observed_members"] == 2
    assert not (isolated.snapshot_path / "truth-asset.json").exists()
    _trace(
        role.value.lower(),
        image_id=image.image_id,
        launch_digest=isolated.launch_digest,
        artifact_digest=isolated.result.artifact_digest,
        controls_digest=isolated.controls_digest,
        snapshot_digest=isolated.snapshot_digest,
        timings_seconds=isolated.timings,
        resources=isolated.resources,
    )


def test_exact_replay_has_no_second_container_effect(tmp_path: Path) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest
    image = load_image_identity(Path(manifest))
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    controller = IsolatedBurgersReferenceController(
        state_root=(tmp_path / "reference-state").resolve(),
        image=image,
        worker_profile=DevelopmentWorkerProfile(_sha("2"), _sha("3")),
    )
    first = controller.execute(request)
    replay = controller.execute(request)
    assert replay.result == first.result
    assert replay.controls == {"retained_exact_replay": True}
    journals = tuple((tmp_path / "reference-state" / "launches").glob("*.json"))
    assert len(journals) == 1
    assert json.loads(journals[0].read_text())["state"] == (
        "ASSOCIATED_DEVELOPMENT_ONLY"
    )
    _trace(
        "exact_replay",
        image_id=image.image_id,
        launch_digest=first.launch_digest,
        artifact_digest=first.result.artifact_digest,
        new_execution_effects=1,
        replay_execution_effects=0,
    )


def test_environment_mismatch_is_typed_before_numerical_output(tmp_path: Path) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest
    image = load_image_identity(Path(manifest))
    request = _request(BurgersReferenceRole.CANDIDATE_PRIMARY)
    from dataclasses import replace

    request = replace(request, environment_digest=_sha("9"))
    isolated = IsolatedBurgersReferenceController(
        state_root=(tmp_path / "reference-state").resolve(),
        image=image,
        worker_profile=DevelopmentWorkerProfile(_sha("2"), _sha("3")),
    ).execute(request)
    assert (
        isolated.result.outcome is ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE
    )
    assert (
        isolated.result.failure_reason
        is ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH
    )
    assert isolated.result.artifact_digest is None
    assert isolated.resources["output_snapshot"]["observed_members"] == 1
    _trace(
        "environment_mismatch",
        image_id=image.image_id,
        launch_digest=isolated.launch_digest,
        outcome=isolated.result.outcome.value,
        artifact_digest=None,
    )


def test_frozen_twelve_cell_campaign_runs_serially_in_isolation(tmp_path: Path) -> None:
    manifest_path = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest_path
    image = load_image_identity(Path(manifest_path))
    profile = DevelopmentWorkerProfile(_sha("2"), _sha("3"))
    outcomes: list[dict[str, object]] = []
    for cell in range(12):
        cell_digests = []
        for role in BurgersReferenceRole:
            request = _request(role, cell=cell)
            isolated = IsolatedBurgersReferenceController(
                state_root=(tmp_path / f"cell-{cell}-{role.value}").resolve(),
                image=image,
                worker_profile=profile,
            ).execute(request)
            assert isolated.result.outcome is ReferenceRunOutcome.SUPPORTED
            assert isolated.result.artifact_digest is not None
            assert isolated.result.eligible_for_truth_or_score is False
            cell_digests.append(isolated.result.artifact_digest)
        outcomes.append({"cell": cell, "artifact_digests": cell_digests})
    assert [item["cell"] for item in outcomes] == list(range(12))
    assert (
        len({digest for item in outcomes for digest in item["artifact_digests"]}) == 36
    )
    _trace(
        "twelve_cell_public_campaign",
        image_id=image.image_id,
        case_count=12,
        role_run_count=36,
        serial_worker_concurrency=1,
        outcomes=outcomes,
    )
