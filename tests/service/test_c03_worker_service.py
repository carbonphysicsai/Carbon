"""Canonical Linux/Docker evidence for the bounded C-03 worker profile."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from c02_fixtures import compile_c02_plan

from carbon.execution import (
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionScope,
    ExecutionState,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    SubmissionId,
)
from carbon.reconstruction import (
    DevelopmentReconstructionWorker,
    PublicTrainingArchive,
    WorkerDisposition,
    build_development_worker_image,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import (
    development_replicate_digest,
    development_request_digest,
)
from carbon.registry import ChallengeKey
from carbon.resource_policy import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    BoundReconstructionReplicate,
    ReconstructionReplicateIdentity,
    ResearchResourcePolicyRef,
    ResourceClassRef,
)
from carbon.seeding import DerivedSeed, EvaluationBinding, SeedPin

REPOSITORY = Path(__file__).resolve().parents[2]


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args], check=check, capture_output=True, text=True, timeout=180
    )


@pytest.fixture(scope="module")
def worker_image() -> tuple[str, str]:
    if os.environ.get("CARBON_REQUIRE_DOCKER_TESTS") != "1":
        pytest.skip("C-03 service evidence runs only in the selected Docker lane")
    _run("info")
    return build_development_worker_image(REPOSITORY)


def _data() -> Trajectories:
    points = 16
    positions = np.arange(points, dtype=np.float64) / points
    initial = np.stack((np.sin(2 * np.pi * positions), np.cos(2 * np.pi * positions)))
    return Trajectories(
        initial,
        np.array([0.01, 0.02]),
        np.broadcast_to(np.array([0.05, 0.1]), (2, 2)).copy(),
        np.stack((initial * 0.98, initial * 0.96), axis=1),
        positions,
        "train",
        "c03_public_worker_fixture",
    )


def _binding(plan, image_id: str, profile_digest: str, index: int):
    key = ChallengeKey(plan.challenge_key.challenge_id, plan.challenge_key.version)
    return DurableExecutionBinding(
        handle=ExecutionAttemptHandle(
            submission_id=SubmissionId(
                str(uuid.UUID(f"62345678-1234-4234-8234-{index:012d}"))
            ),
            attempt_number=1,
            admission_kind=AdmissionKind.FIXTURE,
            seed_pin=SeedPin(
                challenge_key=key,
                generator_version="c03-public-train-v1",
                generator_digest="sha256:" + "1" * 64,
                scoring_version="c03-no-score-v1",
                scoring_digest="sha256:" + "2" * 64,
                evaluation_binding=EvaluationBinding(b"e" * 32),
            ),
            environment_pin=ExecutionEnvironmentPin(
                "carbon_c03_cpu_development_v1", image_id
            ),
        ),
        requester_identity=RequesterIdentity("c03-development-owner"),
        strategy_hash=plan.strategy_hash,
        scope=ExecutionScope.FIXTURE_DEVELOPMENT,
        resolved_plan_digest=plan.to_ref().content_digest,
        reconstruction_policy_digest=profile_digest,
        resource_policy_digest="sha256:" + "2" * 64,
        protected_evaluation_policy_digest="sha256:" + "4" * 64,
    )


def _replicate(plan, archive, request, execution_ref, seed, index):
    policy = ResearchResourcePolicyRef(
        plan.challenge_key,
        "c03_development_worker_policy",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        "sha256:" + "2" * 64,
    )
    resource = ResourceClassRef(
        plan.challenge_key,
        "c03_cpu_fixture",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        "sha256:" + "3" * 64,
    )
    placeholder = BoundReconstructionReplicate(
        ReconstructionReplicateIdentity(
            plan.challenge_key,
            plan.to_ref(),
            policy,
            resource,
            f"replica-{index}",
            "sha256:" + "0" * 64,
        )
    )
    digest = development_replicate_digest(
        binding=placeholder,
        execution_ref=execution_ref,
        randomness_digest="sha256:"
        + hashlib.sha256(seed.as_backend_bytes()).hexdigest(),
        training_data_digest=archive.content_digest,
        request_digest=development_request_digest(request),
    )
    return BoundReconstructionReplicate(
        replace(placeholder.replicate_identity, replicate_digest=digest)
    )


def test_c03_real_reconstruction_repeats_replay_and_envelope(
    tmp_path: Path, worker_image: tuple[str, str]
) -> None:
    image_id, revision = worker_image
    plan = compile_c02_plan(tmp_path / "plan", backbone="fno")
    profile_digest = compile_development_profile(plan).profile_digest
    data = _data()
    source = tmp_path / "public-train.npz"
    data.save(source)
    archive = PublicTrainingArchive.from_file(source, provenance="c03_public_fixture")
    request = {
        "initial": data.initial[:1],
        "viscosity": data.viscosity[:1],
        "requested_times": data.times[:1],
        "positions": data.positions,
    }
    queue = DurableExecutionQueue(tmp_path / "queue.sqlite3")
    worker = DevelopmentReconstructionWorker(
        queue,
        private_root=(tmp_path / "private").resolve(),
        image_id=image_id,
        source_revision=revision,
        repository=REPOSITORY,
    )
    outcomes = []
    for index in range(1, 4):
        binding = _binding(plan, image_id, profile_digest, index)
        queue.admit(binding)
        seed = DerivedSeed(bytes([index]) * 32)
        dispatch = worker.prepare(
            execution_ref=binding.ref,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            prediction_request=request,
            replicate_binding=_replicate(
                plan, archive, request, binding.ref, seed, index
            ),
        )
        result = worker.execute(dispatch)
        replay = worker.read_completed(dispatch)
        assert result.disposition is WorkerDisposition.COMPLETE
        assert replay.artifact_digest == result.artifact_digest
        assert replay.prediction_digest == result.prediction_digest
        status = queue.status(binding.ref, binding.requester_identity)
        assert status.state is ExecutionState.RUNNING
        assert status.partial_stage_count == 1
        outcomes.append(
            {
                "replica": index,
                "disposition": result.disposition.value,
                "artifact_digest": result.artifact_digest,
                "prediction_digest": result.prediction_digest,
                "observations": result.observations,
            }
        )

    inspect = json.loads(_run("image", "inspect", image_id).stdout)[0]
    assert inspect["Config"]["User"] == "10001:10001"
    assert len({item["artifact_digest"] for item in outcomes}) == 3
    assert all(item["disposition"] == "COMPLETE" for item in outcomes)
    evidence = {
        "schema": "carbon.c03.service-evidence.v1",
        "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
        "source_revision": revision,
        "image_id": image_id,
        "host": {
            "os": inspect["Os"],
            "architecture": inspect["Architecture"],
            "github_runner": os.environ.get("RUNNER_NAME"),
        },
        "repeat_scope": {
            "required": 3,
            "completed": 3,
            "selection": "NONE_ALL_OUTCOMES_RETAINED",
            "production_repeat_count": None,
        },
        "outcomes": outcomes,
    }
    artifact_dir = Path(os.environ.get("CARBON_ARTIFACT_DIR", ".carbon-artifacts"))
    destination = artifact_dir / "c03-worker" / "service-evidence.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")


def test_c03_cancellation_and_completed_worker_recovery(
    tmp_path: Path, worker_image: tuple[str, str]
) -> None:
    image_id, revision = worker_image
    plan = compile_c02_plan(tmp_path / "plan", backbone="fno")
    profile_digest = compile_development_profile(plan).profile_digest
    data = _data()
    source = tmp_path / "public-train.npz"
    data.save(source)
    archive = PublicTrainingArchive.from_file(source, provenance="c03_public_fixture")
    request = {
        "initial": data.initial[:1],
        "viscosity": data.viscosity[:1],
        "requested_times": data.times[:1],
        "positions": data.positions,
    }
    queue_path = tmp_path / "queue.sqlite3"
    queue = DurableExecutionQueue(queue_path)
    worker = DevelopmentReconstructionWorker(
        queue,
        private_root=(tmp_path / "private").resolve(),
        image_id=image_id,
        source_revision=revision,
        repository=REPOSITORY,
    )

    cancelled_binding = _binding(plan, image_id, profile_digest, 10)
    queue.admit(cancelled_binding)
    cancelled_seed = DerivedSeed(bytes([10]) * 32)
    cancelled_dispatch = worker.prepare(
        execution_ref=cancelled_binding.ref,
        plan=plan,
        training_archive=archive,
        derived_seed=cancelled_seed,
        prediction_request=request,
        replicate_binding=_replicate(
            plan,
            archive,
            request,
            cancelled_binding.ref,
            cancelled_seed,
            10,
        ),
    )
    cancelled = worker.execute(cancelled_dispatch, cancel=lambda: True)
    assert cancelled.disposition is WorkerDisposition.CANCELLED_NON_SCIENTIFIC
    assert cancelled.cleanup_complete is True
    assert (
        queue.status(cancelled_binding.ref, cancelled_binding.requester_identity).state
        is ExecutionState.CANCELLED
    )
    assert _run("inspect", cancelled_dispatch.container_id, check=False).returncode != 0

    recovery_binding = _binding(plan, image_id, profile_digest, 11)
    queue.admit(recovery_binding)
    recovery_seed = DerivedSeed(bytes([11]) * 32)
    recovery_dispatch = worker.prepare(
        execution_ref=recovery_binding.ref,
        plan=plan,
        training_archive=archive,
        derived_seed=recovery_seed,
        prediction_request=request,
        replicate_binding=_replicate(
            plan, archive, request, recovery_binding.ref, recovery_seed, 11
        ),
    )
    queue.mark_running(recovery_dispatch.claim)
    _run("start", recovery_dispatch.container_id)
    waited = _run("wait", recovery_dispatch.container_id)
    assert waited.stdout.strip() == "0"
    _run(
        "cp",
        f"{recovery_dispatch.container_id}:/output/.",
        str(recovery_dispatch.run_directory / "collected"),
    )
    _run("rm", "--force", recovery_dispatch.container_id)

    reopened = DurableExecutionQueue(queue_path)
    assert (
        reopened.status(recovery_binding.ref, recovery_binding.requester_identity).state
        is ExecutionState.RECONCILIATION_REQUIRED
    )
    recovered_worker = DevelopmentReconstructionWorker(
        reopened,
        private_root=(tmp_path / "private").resolve(),
        image_id=image_id,
        source_revision=revision,
        repository=REPOSITORY,
    )
    recovered = recovered_worker.recover_completed(recovery_dispatch)
    assert recovered.disposition is WorkerDisposition.COMPLETE
    assert (
        reopened.status(recovery_binding.ref, recovery_binding.requester_identity).state
        is ExecutionState.RUNNING
    )
    assert recovered_worker.read_completed(recovery_dispatch) == recovered


def test_c03_runtime_denies_network_and_host_filesystem(
    tmp_path: Path, worker_image: tuple[str, str]
) -> None:
    image_id, _ = worker_image
    sentinel = tmp_path / "host-secret-sentinel"
    sentinel.write_text("C03_PRIVATE_CANARY")
    program = f"""
import pathlib, socket
assert not pathlib.Path({str(sentinel)!r}).exists()
try:
    pathlib.Path('/etc/c03-write').write_text('no')
except OSError:
    pass
else:
    raise SystemExit(3)
interfaces = {{p.name for p in pathlib.Path('/sys/class/net').iterdir()}}
assert interfaces == {{'lo'}}, interfaces
s = socket.socket()
s.settimeout(0.2)
try:
    s.connect(('127.0.0.1', 9))
except OSError:
    pass
else:
    raise SystemExit(4)
"""
    result = _run(
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--entrypoint",
        "/opt/carbon/.venv/bin/python",
        image_id,
        "-I",
        "-c",
        program,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_c03_runtime_enforces_memory_pid_and_output_limits(
    worker_image: tuple[str, str],
) -> None:
    image_id, _ = worker_image
    memory = _run(
        "run",
        "--name",
        f"c03-memory-{uuid.uuid4().hex}",
        "--memory",
        "64m",
        "--memory-swap",
        "64m",
        "--entrypoint",
        "/opt/carbon/.venv/bin/python",
        image_id,
        "-I",
        "-c",
        "x=bytearray(256*1024*1024); print(len(x))",
        check=False,
    )
    name = memory.args[memory.args.index("--name") + 1]
    state = json.loads(_run("inspect", name).stdout)[0]["State"]
    _run("rm", "--force", name)
    assert memory.returncode != 0
    assert state["OOMKilled"] is True

    pid_program = """
import subprocess, sys, time
children=[]
failed=False
for _ in range(64):
    try: children.append(subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(2)']))
    except OSError: failed=True; break
for child in children: child.terminate()
for child in children: child.wait()
assert failed
"""
    pids = _run(
        "run",
        "--rm",
        "--pids-limit",
        "16",
        "--entrypoint",
        "/opt/carbon/.venv/bin/python",
        image_id,
        "-I",
        "-c",
        pid_program,
        check=False,
    )
    assert pids.returncode == 0, (pids.stdout, pids.stderr)

    output = _run(
        "run",
        "--rm",
        "--tmpfs",
        "/output:rw,noexec,nosuid,nodev,size=1048576",
        "--entrypoint",
        "/opt/carbon/.venv/bin/python",
        image_id,
        "-I",
        "-c",
        "open('/output/too-large','wb').write(b'x'*(2*1024*1024))",
        check=False,
    )
    assert output.returncode != 0
