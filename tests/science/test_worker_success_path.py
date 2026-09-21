"""The terminal success path: a run that actually reaches ASSOCIATED.

Every other lifecycle test covers reaching RUNNING and each way a run can end
short of success. The success path was uncovered, and the stated reason was that
reaching ASSOCIATED needs a genuine trained checkpoint the bounded native
validator accepts, "which no fixture can fabricate".

That is true, and it is why nothing is fabricated here. The artifact this run
exports is produced by the real `reconstruct()` - a real training on public TRAIN
data - and the validator that accepts it is the real one, running in its own
resource-bounded subprocess. The validator is not stubbed, no digest is written
by hand, and no check is relaxed to let the artifact through. If the trained
bytes did not match the staged request's plan, archive and seed, validation would
refuse them, which is the point.

What is still replaced is what leaves this process: the container CLI, and
`spawn_watchdog`. The container does not run the training - it could not, in a
test - so the artifact it "exports" is the one trained here under the same
identities the request carries.

This is the CPU lane. Reaching ASSOCIATED under a GPU profile additionally
requires the device, and remains uncovered until an authorized attempt runs.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import scripted_docker
from c02_fixtures import compile_c02_plan

from carbon.execution import (
    ClaimedExecution,
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionAttemptRef,
    ExecutionScope,
    QueueClaim,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    SubmissionId,
)
from carbon.reconstruction import (
    DevelopmentReplica,
    PublicTrainingArchive,
    ReconstructionStatus,
    development_replicate_digest,
    freeze_development_repeat_plan,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.service import reconstruct
from carbon.reconstruction.worker.controller import IsolatedReconstructionController
from carbon.reconstruction.worker.model import (
    WorkerImageIdentity,
    WorkerLaunchState,
)
from carbon.resource_policy import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    BoundReconstructionReplicate,
    ReconstructionReplicateIdentity,
    ResearchResourcePolicyRef,
    ResourceClassRef,
)
from carbon.seeding import DerivedSeed, EvaluationBinding, SeedPin

SCOPE = "UNQUALIFIED_PUBLIC_DEVELOPMENT"


def _sha(character: str) -> str:
    return "sha256:" + hashlib.sha256(character.encode()).hexdigest()


def _data() -> Trajectories:
    points = 16
    positions = np.arange(points, dtype=np.float64) / points
    initial = np.stack(
        (
            np.sin(2 * np.pi * positions),
            np.cos(2 * np.pi * positions),
            np.sin(4 * np.pi * positions) * 0.5,
            np.cos(4 * np.pi * positions) * 0.5,
        )
    )
    times = np.broadcast_to(np.array([0.05, 0.1]), (4, 2)).copy()
    solution = np.stack((initial * 0.98, initial * 0.96), axis=1)
    return Trajectories(
        initial,
        np.array([0.01, 0.02, 0.015, 0.025]),
        times,
        solution,
        positions,
        "train",
        "carbon_c02_science_fixture",
    )


def _line(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _stream(members: dict[str, bytes]) -> bytes:
    """One complete worker output stream, in the encoding the decoder accepts."""
    payload = _line({"schema": "carbon.c03.output-stream.v1"})
    total = 0
    for name, data in members.items():
        payload += _line({"path": name, "size": len(data)}) + data
        total += len(data)
    return payload + _line({"bytes": total, "end": True, "members": len(members)})


def _artifact_members(artifact: Path) -> dict[str, bytes]:
    """Every file of a real trained artifact, exactly as trained."""
    return {
        f"artifact/{item.relative_to(artifact).as_posix()}": item.read_bytes()
        for item in sorted(artifact.rglob("*"))
        if item.is_file()
    }


@pytest.fixture
def trained(tmp_path: Path):
    """A real CPU training, and the durable execution that matches it."""
    source = tmp_path / "public-train.npz"
    _data().save(source)
    archive = PublicTrainingArchive.from_file(source, provenance="c03_success_fixture")
    plan = compile_c02_plan(tmp_path, backbone="fno")
    profile = compile_development_profile(plan)
    execution = ExecutionAttemptRef(
        SubmissionId(str(uuid.UUID("12345678-1234-4234-8234-123456789012"))), 1
    )
    seed = DerivedSeed(bytes(range(32)))
    randomness_digest = "sha256:" + hashlib.sha256(seed.as_backend_bytes()).hexdigest()

    # The real training. Its bytes are what the run exports, and they satisfy
    # the validator only because they were produced from these exact identities.
    receipt = reconstruct(
        execution_ref=execution,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=tmp_path / "trained-artifact",
    )
    assert receipt.status is ReconstructionStatus.COMPLETE

    policy = ResearchResourcePolicyRef(
        plan.challenge_key,
        "c03_development_policy",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _sha("2"),
    )
    resource = ResourceClassRef(
        plan.challenge_key,
        "c03_linux_cpu_class",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _sha("3"),
    )
    request_digest = _sha("9")
    placeholder = BoundReconstructionReplicate(
        ReconstructionReplicateIdentity(
            plan.challenge_key,
            plan.to_ref(),
            policy,
            resource,
            "replica-1",
            _sha("0"),
        )
    )
    replica = DevelopmentReplica(
        BoundReconstructionReplicate(
            replace(
                placeholder.replicate_identity,
                replicate_digest=development_replicate_digest(
                    binding=placeholder,
                    execution_ref=execution,
                    randomness_digest=randomness_digest,
                    training_data_digest=archive.content_digest,
                    request_digest=request_digest,
                ),
            )
        ),
        execution,
        randomness_digest,
    )
    repeat = freeze_development_repeat_plan(
        plan_id="c03-success-repeat",
        construction_plan_digest=plan.to_ref().content_digest,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
        replicas=(replica,),
    )
    binding = DurableExecutionBinding(
        ExecutionAttemptHandle(
            submission_id=execution.submission_id,
            attempt_number=execution.attempt_number,
            admission_kind=AdmissionKind.FIXTURE,
            seed_pin=SeedPin(
                plan.challenge_key,
                "development-generator-v1",
                _sha("4"),
                "development-score-v1",
                _sha("5"),
                EvaluationBinding(b"d" * 32),
            ),
            environment_pin=ExecutionEnvironmentPin(
                profile.profile_id, profile.environment_digest
            ),
        ),
        RequesterIdentity("development-requester-v1"),
        plan.strategy_hash,
        ExecutionScope.FIXTURE_DEVELOPMENT,
        plan.to_ref().content_digest,
        profile.profile_digest,
        policy.content_digest,
        _sha("6"),
    )

    result = {
        "schema": "carbon.c03.worker-result.v1",
        "scope": SCOPE,
        "artifact_digest": receipt.artifact_digest,
        "checkpoint_digest": receipt.checkpoint_digest,
        "execution_id": receipt.execution_id,
        "plan_digest": receipt.plan_digest,
        "profile_digest": receipt.profile_digest,
        "training_data_digest": receipt.training_data_digest,
        "randomness_digest": receipt.randomness_digest,
        "status": receipt.status.value,
        "completed_steps": receipt.completed_steps,
    }
    members = {"result.json": _line(result).rstrip(b"\n")}
    members.update(_artifact_members(tmp_path / "trained-artifact"))

    return {
        "claimed": ClaimedExecution(QueueClaim(execution, "claim-1", "pool"), binding),
        "repeat": repeat,
        "replica": replica,
        "plan": plan,
        "archive": archive,
        "seed": seed,
        "receipt": receipt,
        "exporter": _stream(members),
        "members": members,
    }


def _controller(tmp_path: Path, trained, monkeypatch, *, exporter):
    from carbon.reconstruction.worker import docker_runtime

    spawned = []
    monkeypatch.setattr(
        docker_runtime, "spawn_watchdog", lambda **kwargs: spawned.append(kwargs)
    )
    monkeypatch.setattr(
        "carbon.reconstruction.worker.controller.spawn_watchdog",
        lambda **kwargs: spawned.append(kwargs),
        raising=False,
    )
    image = WorkerImageIdentity(*(_sha(character) for character in "aabcdef0"))
    queue = DurableExecutionQueue(tmp_path / "queue.sqlite3")
    queue.admit(trained["claimed"].binding)
    active = queue.claim(
        trained["claimed"].claim.ref, "c03-worker", claim_id="success-claim"
    )
    claimed = ClaimedExecution(active.claim, trained["claimed"].binding)
    cli = scripted_docker.ScriptedDocker(image=image, exporter=exporter)
    state_root = (tmp_path / "controller").resolve()
    controller = IsolatedReconstructionController(
        state_root=state_root, execution_queue=queue, image=image, cli=cli
    )
    return controller, claimed, cli


# A refused artifact fails after the container has already been removed, and
# the controller then tries to observe that container's resources one last time
# for the failure record. A real CLI answers with an error, which the controller
# already handles as UNAVAILABLE_AT_FAILURE; the scripted one raises its own
# type instead. Both mean the run was refused, and neither is the claim under
# test, so both are accepted here rather than asserting on fixture plumbing.
REFUSED = (scripted_docker.Removed,)


def _run(controller, claimed, trained):
    return controller.execute(
        claimed=claimed,
        repeat_plan=trained["repeat"],
        replica=trained["replica"],
        plan=trained["plan"],
        training_archive=trained["archive"],
        derived_seed=trained["seed"],
    )


def test_a_real_trained_artifact_reaches_associated(tmp_path, trained, monkeypatch):
    """The path that was uncovered, end to end through the real validator."""
    controller, claimed, cli = _controller(
        tmp_path, trained, monkeypatch, exporter=trained["exporter"]
    )

    result = _run(controller, claimed, trained)

    assert result.receipt.status is ReconstructionStatus.COMPLETE
    assert result.receipt.artifact_digest == trained["receipt"].artifact_digest
    assert result.receipt.checkpoint_digest == trained["receipt"].checkpoint_digest

    execution_id = (
        f"{claimed.claim.ref.submission_id.value}:{claimed.claim.ref.attempt_number}"
    )
    status = controller.store.raw_status(execution_id)
    assert status["state"] == WorkerLaunchState.ASSOCIATED.value
    assert cli.removed, "a successful run still removes its own container"


def test_the_validator_is_not_taking_the_artifact_on_trust(
    tmp_path, trained, monkeypatch
):
    """The counterpart: tamper with the trained weights and it must refuse.

    Without this, the test above would pass just as happily against a validator
    that accepted anything, and would establish nothing.
    """
    from carbon.reconstruction.worker.model import WorkerFailure

    members = dict(trained["members"])
    weights = "artifact/checkpoint/state.npz"
    assert weights in members, "the trained artifact should carry its weights"
    members[weights] = members[weights] + b"tampered"

    controller, claimed, _ = _controller(
        tmp_path, trained, monkeypatch, exporter=_stream(members)
    )
    with pytest.raises((WorkerFailure, *REFUSED)):
        _run(controller, claimed, trained)

    execution_id = (
        f"{claimed.claim.ref.submission_id.value}:{claimed.claim.ref.attempt_number}"
    )
    status = controller.store.raw_status(execution_id)
    assert status["state"] != WorkerLaunchState.ASSOCIATED.value


def test_a_result_claiming_a_digest_the_artifact_does_not_have_is_refused(
    tmp_path, trained, monkeypatch
):
    """A truthful-looking result record cannot stand in for truthful bytes."""
    from carbon.reconstruction.worker.model import WorkerFailure

    members = dict(trained["members"])
    result = json.loads(members["result.json"])
    result["checkpoint_digest"] = _sha("forged")
    members["result.json"] = _line(result).rstrip(b"\n")

    controller, claimed, _ = _controller(
        tmp_path, trained, monkeypatch, exporter=_stream(members)
    )
    with pytest.raises((WorkerFailure, *REFUSED)):
        _run(controller, claimed, trained)

    execution_id = (
        f"{claimed.claim.ref.submission_id.value}:{claimed.claim.ref.attempt_number}"
    )
    assert (
        controller.store.raw_status(execution_id)["state"]
        != WorkerLaunchState.ASSOCIATED.value
    )
