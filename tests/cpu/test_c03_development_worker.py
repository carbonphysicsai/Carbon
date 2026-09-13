from __future__ import annotations

import hashlib
import json
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
    ExecutionCode,
    ExecutionFailure,
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
    ReconstructionFailure,
    compile_development_profile,
    load_development_worker_profile,
    verify_profile_sources,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
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

IMAGE = "sha256:" + "a" * 64
REVISION = "b" * 40


def _data() -> Trajectories:
    points = 16
    positions = np.arange(points, dtype=np.float64) / points
    initial = np.stack((np.sin(2 * np.pi * positions), np.cos(2 * np.pi * positions)))
    times = np.broadcast_to(np.array([0.05, 0.1]), (2, 2)).copy()
    return Trajectories(
        initial,
        np.array([0.01, 0.02]),
        times,
        np.stack((initial * 0.98, initial * 0.96), axis=1),
        positions,
        "train",
        "c03_public_worker_fixture",
    )


def _binding(plan, profile_digest: str) -> DurableExecutionBinding:
    key = ChallengeKey(plan.challenge_key.challenge_id, plan.challenge_key.version)
    return DurableExecutionBinding(
        handle=ExecutionAttemptHandle(
            submission_id=SubmissionId("12345678-1234-4234-8234-123456789abc"),
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
                "carbon_c03_cpu_development_v1", IMAGE
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


def _replicate(plan, archive, request, execution_ref, seed):
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
            "replica-1",
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


class _FakeWorker(DevelopmentReconstructionWorker):
    def __init__(self, *args, **kwargs):
        self.commands: list[tuple[str, ...]] = []
        self.mount_source = ""
        super().__init__(*args, **kwargs)

    def _command(self, *args: str, **kwargs):
        del kwargs
        self.commands.append(args)
        if args[:2] == ("image", "inspect"):
            value = [
                {
                    "Id": IMAGE,
                    "Os": "linux",
                    "Architecture": "amd64",
                    "Config": {
                        "User": "10001:10001",
                        "Labels": {
                            "org.opencontainers.image.carbon.worker-profile": "carbon_c03_cpu_development_v1",
                            "org.opencontainers.image.carbon.source-revision": REVISION,
                            "org.opencontainers.image.carbon.security-state": "REVIEWABLE_NOT_SECURITY_ACCEPTED",
                        },
                    },
                }
            ]
            return subprocess.CompletedProcess(args, 0, json.dumps(value), "")
        if args[0] == "create":
            mount = args[args.index("--mount") + 1]
            self.mount_source = mount.split(",source=", 1)[1].split(",target=", 1)[0]
            return subprocess.CompletedProcess(args, 0, "c" * 64 + "\n", "")
        if args[:1] == ("inspect",):
            limits = self.profile.limits
            value = [
                {
                    "Config": {"User": "10001:10001"},
                    "HostConfig": {
                        "ReadonlyRootfs": True,
                        "NetworkMode": "none",
                        "Privileged": False,
                        "CapDrop": ["ALL"],
                        "SecurityOpt": ["no-new-privileges:true"],
                        "NanoCpus": 1_000_000_000,
                        "Memory": limits.memory_bytes,
                        "MemorySwap": limits.memory_bytes,
                        "PidsLimit": limits.pids,
                        "PublishAllPorts": False,
                        "PortBindings": {},
                        "Devices": [],
                        "LogConfig": {
                            "Type": "local",
                            "Config": {"max-file": "1", "max-size": "16k"},
                        },
                        "Tmpfs": {
                            "/output": f"rw,noexec,nosuid,nodev,size={limits.output_bytes}",
                            "/scratch": f"rw,noexec,nosuid,nodev,size={limits.scratch_bytes}",
                        },
                        "Ulimits": [
                            {
                                "Name": "nofile",
                                "Hard": limits.open_files,
                                "Soft": limits.open_files,
                            }
                        ],
                    },
                    "Mounts": [
                        {
                            "Type": "bind",
                            "Source": self.mount_source,
                            "Destination": "/input",
                            "RW": False,
                        }
                    ],
                }
            ]
            return subprocess.CompletedProcess(args, 0, json.dumps(value), "")
        if args[:2] == ("rm", "--force"):
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(args)


class _EnvelopeRejectingWorker(_FakeWorker):
    def _verify_container_envelope(self, container_id, input_directory) -> None:
        del container_id, input_directory
        raise ReconstructionFailure("reconstruction.worker.envelope_mismatch")


def test_worker_profile_is_finite_public_only_and_source_pinned() -> None:
    profile = load_development_worker_profile()
    verify_profile_sources(profile, Path.cwd())

    assert profile.raw["protected_workloads_enabled"] is False
    assert profile.raw["security_state"] == "REVIEWABLE_NOT_SECURITY_ACCEPTED"
    assert profile.raw["network"] == {
        "docker_mode": "none",
        "downloads": False,
        "online_logging": False,
    }
    assert profile.limits.cpu_time_seconds is None
    assert profile.limits.swap_bytes == 0
    assert profile.raw["claims"]["production_repeat_count"] is None
    assert profile.raw["source"]["optional_carbon_jax_research_v0_2"] == (
        "ABSENT_UNVERIFIED_NOT_A_BLOCKER"
    )


@pytest.mark.parametrize(
    ("image_id", "revision", "code"),
    (
        ("sha256:" + "G" * 64, REVISION, "reconstruction.worker.image_invalid"),
        (IMAGE, "Z" * 40, "reconstruction.worker.source_invalid"),
    ),
)
def test_worker_rejects_noncanonical_image_and_source_identities(
    tmp_path: Path, image_id: str, revision: str, code: str
) -> None:
    with pytest.raises(ReconstructionFailure) as caught:
        _FakeWorker(
            DurableExecutionQueue(tmp_path / "queue.sqlite3"),
            private_root=tmp_path / "private",
            image_id=image_id,
            source_revision=revision,
            repository=Path.cwd(),
        )
    assert caught.value.code == code


def test_prepared_dispatch_binds_exact_c01_attempt_and_enforcement_argv(
    tmp_path: Path,
) -> None:
    plan = compile_c02_plan(tmp_path / "plan", backbone="fno")
    profile_digest = compile_development_profile(plan).profile_digest
    queue_path = tmp_path / "queue.sqlite3"
    queue = DurableExecutionQueue(queue_path)
    binding = _binding(plan, profile_digest)
    queue.admit(binding)
    source = tmp_path / "train.npz"
    data = _data()
    data.save(source)
    archive = PublicTrainingArchive.from_file(source, provenance="c03_public_fixture")
    values = iter(
        (
            uuid.UUID("00000000-0000-4000-8000-000000000001"),
            uuid.UUID("00000000-0000-4000-8000-000000000002"),
        )
    )
    worker = _FakeWorker(
        queue,
        private_root=tmp_path / "private",
        image_id=IMAGE,
        source_revision=REVISION,
        repository=Path.cwd(),
        id_factory=lambda: next(values),
    )
    assert worker.private_root.stat().st_mode & 0o077 == 0
    request = {
        "initial": data.initial[:1],
        "viscosity": data.viscosity[:1],
        "requested_times": data.times[:1],
        "positions": data.positions,
    }
    dispatch = worker.prepare(
        execution_ref=binding.ref,
        plan=plan,
        training_archive=archive,
        derived_seed=DerivedSeed(bytes(range(32))),
        prediction_request=request,
        replicate_binding=_replicate(
            plan, archive, request, binding.ref, DerivedSeed(bytes(range(32)))
        ),
    )

    create = next(command for command in worker.commands if command[0] == "create")
    assert "none" == create[create.index("--network") + 1]
    assert "ALL" == create[create.index("--cap-drop") + 1]
    assert "no-new-privileges:true" == create[create.index("--security-opt") + 1]
    assert "local" == create[create.index("--log-driver") + 1]
    assert "max-size=16k" in create
    assert "max-file=1" in create
    assert "--read-only" in create
    assert "--memory" in create and "--pids-limit" in create and "--ulimit" in create
    assert create[-1] == IMAGE
    assert (
        queue.status(binding.ref, binding.requester_identity).state
        is ExecutionState.DISPATCHING
    )
    staged = json.loads((dispatch.run_directory / "input/request.json").read_text())
    assert staged["plan_digest"] == plan.to_ref().content_digest
    assert staged["randomness_hex"] == bytes(range(32)).hex()
    assert (
        "solution"
        not in np.load(dispatch.run_directory / "input/prediction-request.npz").files
    )


def test_binding_mismatch_rejects_before_claim_or_container(tmp_path: Path) -> None:
    plan = compile_c02_plan(tmp_path / "plan", backbone="fno")
    queue = DurableExecutionQueue(tmp_path / "queue.sqlite3")
    binding = _binding(plan, "sha256:" + "9" * 64)
    queue.admit(binding)
    source = tmp_path / "train.npz"
    data = _data()
    data.save(source)
    worker = _FakeWorker(
        queue,
        private_root=tmp_path / "private",
        image_id=IMAGE,
        source_revision=REVISION,
        repository=Path.cwd(),
    )

    with pytest.raises(ReconstructionFailure) as caught:
        archive = PublicTrainingArchive.from_file(
            source, provenance="c03_public_fixture"
        )
        request = {
            "initial": data.initial[:1],
            "viscosity": data.viscosity[:1],
            "requested_times": data.times[:1],
            "positions": data.positions,
        }
        seed = DerivedSeed(bytes(range(32)))
        worker.prepare(
            execution_ref=binding.ref,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            prediction_request=request,
            replicate_binding=_replicate(plan, archive, request, binding.ref, seed),
        )

    assert caught.value.code == "reconstruction.worker.binding_mismatch"
    assert (
        queue.status(binding.ref, binding.requester_identity).state
        is ExecutionState.QUEUED
    )
    assert not any(command[0] == "create" for command in worker.commands)


def test_preclaim_envelope_rejection_cleans_staging_and_leaves_attempt_queued(
    tmp_path: Path,
) -> None:
    plan = compile_c02_plan(tmp_path / "plan", backbone="fno")
    queue = DurableExecutionQueue(tmp_path / "queue.sqlite3")
    binding = _binding(plan, compile_development_profile(plan).profile_digest)
    queue.admit(binding)
    source = tmp_path / "train.npz"
    data = _data()
    data.save(source)
    archive = PublicTrainingArchive.from_file(source, provenance="c03_public_fixture")
    request = {
        "initial": data.initial[:1],
        "viscosity": data.viscosity[:1],
        "requested_times": data.times[:1],
        "positions": data.positions,
    }
    seed = DerivedSeed(bytes(range(32)))
    worker = _EnvelopeRejectingWorker(
        queue,
        private_root=tmp_path / "private",
        image_id=IMAGE,
        source_revision=REVISION,
        repository=Path.cwd(),
        id_factory=lambda: uuid.UUID("00000000-0000-4000-8000-000000000001"),
    )

    with pytest.raises(ReconstructionFailure) as caught:
        worker.prepare(
            execution_ref=binding.ref,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            prediction_request=request,
            replicate_binding=_replicate(plan, archive, request, binding.ref, seed),
        )

    assert caught.value.code == "reconstruction.worker.envelope_mismatch"
    assert (
        queue.status(binding.ref, binding.requester_identity).state
        is ExecutionState.QUEUED
    )
    assert not worker._run_directory(binding.ref).exists()
    assert any(command[:2] == ("rm", "--force") for command in worker.commands)


def test_claim_cancellation_is_terminal_and_not_retryable(tmp_path: Path) -> None:
    plan = compile_c02_plan(tmp_path / "plan", backbone="fno")
    queue = DurableExecutionQueue(tmp_path / "queue.sqlite3")
    binding = _binding(plan, compile_development_profile(plan).profile_digest)
    queue.admit(binding)
    claimed = queue.claim(binding.ref, "c03-development-worker", claim_id="claim-1")
    queue.mark_running(claimed.claim)
    queue.cancel_claim(claimed.claim)

    assert (
        queue.status(binding.ref, binding.requester_identity).state
        is ExecutionState.CANCELLED
    )
    with pytest.raises(ExecutionFailure) as caught:
        queue.admit(
            DurableExecutionBinding(
                handle=ExecutionAttemptHandle(
                    submission_id=binding.handle.submission_id,
                    attempt_number=2,
                    admission_kind=AdmissionKind.FIXTURE,
                    seed_pin=binding.handle.seed_pin,
                    environment_pin=binding.handle.environment_pin,
                ),
                requester_identity=binding.requester_identity,
                strategy_hash=binding.strategy_hash,
                scope=binding.scope,
                resolved_plan_digest=binding.resolved_plan_digest,
                reconstruction_policy_digest=binding.reconstruction_policy_digest,
                resource_policy_digest=binding.resource_policy_digest,
                protected_evaluation_policy_digest=binding.protected_evaluation_policy_digest,
            )
        )
    assert caught.value.code is ExecutionCode.CONFLICT
