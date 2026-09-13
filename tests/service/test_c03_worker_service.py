"""Required Linux/Docker evidence for C-03's DEVELOPMENT worker."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import time
import uuid
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from c02_fixtures import compile_c02_plan

from carbon.execution import (
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionAttemptRef,
    ExecutionScope,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    SubmissionId,
)
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction.model import PublicTrainingArchive, ReconstructionStatus
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import (
    DevelopmentReplica,
    development_replicate_digest,
    development_request_digest,
    freeze_development_repeat_plan,
)
from carbon.reconstruction.service import predict, reconstruct
from carbon.reconstruction.worker.controller import IsolatedReconstructionController
from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    create_arguments,
    load_image_identity,
    remove_exact_container,
)
from carbon.reconstruction.worker.model import (
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
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


def _sanitized_docker_diagnostic(value: bytes) -> str:
    """Expose only synthetic CI mechanics; retain no checkout path or digest."""

    text = value.decode("utf-8", "replace")
    text = text.replace(str(Path.cwd()), "<checkout>")
    text = re.sub(r"sha256:[0-9a-f]{64}", "<sha256>", text)
    text = re.sub(r"\b[0-9a-f]{64}\b", "<container-id>", text)
    return text[:4096]


@pytest.fixture(autouse=True)
def _retain_failed_docker_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make a bounded, sanitized Docker failure visible in this service lane."""

    original = DockerCLI.run

    def observed(self, arguments, **kwargs):
        try:
            return original(self, arguments, **kwargs)
        except WorkerFailure as error:
            if error.private_diagnostic:
                diagnostic = _sanitized_docker_diagnostic(error.private_diagnostic)
                _record_trace(
                    "docker_runtime_diagnostic",
                    "failed",
                    operation=arguments[0] if arguments else "missing",
                    diagnostic=diagnostic,
                )
                print(f"C-03 private synthetic diagnostic:\n{diagnostic}", flush=True)
            raise

    monkeypatch.setattr(DockerCLI, "run", observed)


def _record_trace(kind: str, disposition: str, **details: object) -> None:
    """Retain a sanitized service observation without public TRAIN bytes or keys."""

    target = os.environ.get("CARBON_C03_TRACE_PATH")
    if not target:
        return
    record = {
        "schema": "carbon.c03.development-service-trace.v1",
        "kind": kind,
        "disposition": disposition,
        **details,
    }
    with Path(target).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
        stream.write("\n")


def _sha(character: str) -> str:
    return "sha256:" + character * 64


def _data(points: int) -> Trajectories:
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
        f"carbon_c03_public_{points}_fixture",
    )


def _case(tmp_path: Path, *, foundax: bool, points: int):
    plan = compile_c02_plan(tmp_path, foundax=foundax)
    profile = compile_development_profile(plan)
    data = _data(points)
    train_path = tmp_path / "train.npz"
    data.save(train_path)
    archive = PublicTrainingArchive.from_file(
        train_path, provenance=f"c03_public_{points}_fixture"
    )
    seed = DerivedSeed(bytes(range(32)))
    randomness = "sha256:" + hashlib.sha256(seed.as_backend_bytes()).hexdigest()
    execution = ExecutionAttemptRef(SubmissionId(str(uuid.uuid4())), 1)
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
        "c03_linux_x86_64_cpu",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _sha("3"),
    )
    request = {
        "initial": data.initial[:1],
        "viscosity": data.viscosity[:1],
        "requested_times": data.times[:1, ::-1],
        "positions": data.positions,
    }
    request_digest = development_request_digest(request)
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
    replicate_digest = development_replicate_digest(
        binding=placeholder,
        execution_ref=execution,
        randomness_digest=randomness,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
    )
    replica = DevelopmentReplica(
        BoundReconstructionReplicate(
            replace(placeholder.replicate_identity, replicate_digest=replicate_digest)
        ),
        execution,
        randomness,
    )
    repeat = freeze_development_repeat_plan(
        plan_id="c03-service-repeat",
        construction_plan_digest=plan.to_ref().content_digest,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
        replicas=(replica,),
    )
    queue = DurableExecutionQueue(tmp_path / "execution.sqlite3")
    queue.admit(
        DurableExecutionBinding(
            ExecutionAttemptHandle(
                execution.submission_id,
                execution.attempt_number,
                AdmissionKind.FIXTURE,
                SeedPin(
                    plan.challenge_key,
                    "development-generator-v1",
                    _sha("4"),
                    "development-score-v1",
                    _sha("5"),
                    EvaluationBinding(b"d" * 32),
                ),
                ExecutionEnvironmentPin(profile.profile_id, profile.environment_digest),
            ),
            RequesterIdentity("c03-service-fixture"),
            plan.strategy_hash,
            ExecutionScope.FIXTURE_DEVELOPMENT,
            plan.to_ref().content_digest,
            profile.profile_digest,
            policy.content_digest,
            _sha("6"),
        )
    )
    claimed = queue.claim(execution, "c03-worker-pool", claim_id="c03-service-claim")
    return data, plan, archive, seed, request, repeat, replica, queue, claimed


@pytest.mark.parametrize(("foundax", "points"), ((False, 16), (True, 512)))
def test_real_jax_path_is_isolated_validated_and_numerically_identical(
    tmp_path: Path, foundax: bool, points: int
) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest, "required service lane must supply the exact image manifest"
    image = load_image_identity(Path(manifest))
    _, plan, archive, seed, request, repeat, replica, queue, claimed = _case(
        tmp_path, foundax=foundax, points=points
    )
    controller = IsolatedReconstructionController(
        state_root=(tmp_path / "worker-state").resolve(),
        execution_queue=queue,
        image=image,
    )

    isolated = controller.execute(
        claimed=claimed,
        repeat_plan=repeat,
        replica=replica,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
    )
    assert isolated.receipt.status is ReconstructionStatus.COMPLETE
    if platform.system() == "Linux" and platform.machine() == "x86_64":
        direct = reconstruct(
            execution_ref=replica.execution_ref,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            artifact_path=(tmp_path / "direct-artifact").resolve(),
        )
        prediction, prediction_receipt = predict(
            isolated.receipt,
            initial=request["initial"],
            viscosity=request["viscosity"],
            requested_times=request["requested_times"],
            positions=request["positions"],
        )
        assert isolated.receipt.checkpoint_digest == direct.checkpoint_digest
        assert prediction.shape == (1, 2, points)
        assert prediction.dtype == np.dtype("float32")
        assert np.isfinite(prediction).all()
        assert prediction_receipt.artifact_digest == isolated.receipt.artifact_digest
    assert isolated.effective_controls["process"] == {
        "CapEff": "0000000000000000",
        "NoNewPrivs": "1",
        "Seccomp": "2",
    }
    assert isolated.effective_controls["cgroup_v2"]["memory.swap.max"] == "0"
    assert (
        queue.partials(claimed.claim)[0].artifact_digest
        == isolated.receipt.artifact_digest
    )
    replay = controller.execute(
        claimed=claimed,
        repeat_plan=repeat,
        replica=replica,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
    )
    assert replay.receipt.artifact_digest == isolated.receipt.artifact_digest
    assert replay.effective_controls == {"retained_exact_replay": True}
    assert len(queue.partials(claimed.claim)) == 1
    _record_trace(
        "foundax_fno" if foundax else "lab_fno",
        "complete",
        image_id=image.image_id,
        launch_digest=isolated.launch_digest,
        controls_digest=isolated.effective_controls_digest,
        snapshot_digest=isolated.output_snapshot_digest,
        artifact_digest=isolated.receipt.artifact_digest,
        checkpoint_digest=isolated.receipt.checkpoint_digest,
        points=points,
        timings_seconds=isolated.timings,
        effective_controls=isolated.effective_controls,
        exact_replay=True,
        accepted_partials=1,
    )


def _probe_arguments(
    tmp_path: Path,
    image_id: str,
    probe: list[str],
    *,
    network: str = "none",
    memory: int | None = None,
    pids: int | None = None,
    scratch: int | None = None,
    inodes: int | None = None,
) -> list[str]:
    input_directory = tmp_path / "probe-input"
    input_directory.mkdir(exist_ok=True)
    input_directory.chmod(0o555)
    profile = DevelopmentWorkerProfile(_sha("2"), _sha("3"))
    arguments = create_arguments(
        container_name="carbon-c03-probe-" + uuid.uuid4().hex[:12],
        image_id=image_id,
        input_directory=input_directory,
        cpuset="0,1",
        launch_digest=_sha("a"),
        worker_profile=profile,
    )
    arguments[0:1] = ["run", "--rm"]
    arguments[arguments.index("none")] = network
    if memory is not None:
        arguments[arguments.index(str(4 * 1024**3))] = str(memory)
        second = arguments.index(str(4 * 1024**3))
        arguments[second] = str(memory)
    if pids is not None:
        arguments[arguments.index("256")] = str(pids)
    if scratch is not None or inodes is not None:
        index = arguments.index("--tmpfs") + 1
        value = arguments[index]
        if scratch is not None:
            value = value.replace("size=528482304", f"size={scratch}")
        if inodes is not None:
            value = value.replace("nr_inodes=8192", f"nr_inodes={inodes}")
        arguments[index] = value
    image_index = len(arguments) - 1
    arguments[image_index:image_index] = [
        "--entrypoint",
        "/opt/carbon-worker/bin/python",
    ]
    arguments.extend(["-I", "-m", "carbon.reconstruction.worker.probes", *probe])
    return arguments


def test_network_filesystem_pid_memory_and_scratch_enforcement(tmp_path: Path) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest
    image = load_image_identity(Path(manifest))
    cli = DockerCLI()

    paths = cli.run(_probe_arguments(tmp_path, image.image_id, ["paths"]), timeout=20)
    assert paths.returncode == 0

    pids = cli.run(
        _probe_arguments(tmp_path, image.image_id, ["pids", "64"], pids=32),
        timeout=30,
    )
    assert pids.returncode == 0

    scratch_bytes = cli.run(
        _probe_arguments(
            tmp_path,
            image.image_id,
            ["scratch-bytes", str(24 * 1024**2)],
            scratch=16 * 1024**2,
        ),
        timeout=30,
    )
    assert scratch_bytes.returncode == 0

    scratch_inodes = cli.run(
        _probe_arguments(
            tmp_path,
            image.image_id,
            ["scratch-inodes", "256"],
            scratch=16 * 1024**2,
            inodes=64,
        ),
        timeout=30,
    )
    assert scratch_inodes.returncode == 0

    # The bounded negative control removes only the memory ceiling for the same
    # finite allocation target: capped execution is killed/denied, while the
    # deliberately larger disposable subprofile reaches the probe sentinel.
    capped = cli.run(
        _probe_arguments(
            tmp_path,
            image.image_id,
            ["memory", str(128 * 1024**2)],
            memory=64 * 1024**2,
        ),
        timeout=30,
        accepted=(0, 12, 137),
    )
    assert capped.returncode in (0, 137)
    negative = cli.run(
        _probe_arguments(
            tmp_path,
            image.image_id,
            ["memory", str(128 * 1024**2)],
            memory=256 * 1024**2,
        ),
        timeout=30,
        accepted=(12,),
    )
    assert negative.returncode == 12
    _record_trace(
        "resource_enforcement",
        "rejected_as_bounded",
        image_id=image.image_id,
        pid_probe=pids.returncode,
        scratch_bytes_probe=scratch_bytes.returncode,
        scratch_inodes_probe=scratch_inodes.returncode,
        memory_capped_probe=capped.returncode,
        memory_negative_control=negative.returncode,
    )


def test_isolated_partial_checkpoint_continuation_matches_uninterrupted(
    tmp_path: Path,
) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest
    image = load_image_identity(Path(manifest))
    _, plan, archive, seed, _, repeat, replica, queue, claimed = _case(
        tmp_path, foundax=False, points=16
    )

    class LoseOneCreateResponse(DockerCLI):
        lost = False

        def run(self, arguments, **kwargs):
            result = super().run(arguments, **kwargs)
            if arguments and arguments[0] == "create" and not self.lost:
                self.lost = True
                raise WorkerFailure(WorkerCode.UNAVAILABLE)
            return result

    controller = IsolatedReconstructionController(
        state_root=(tmp_path / "worker-state").resolve(),
        execution_queue=queue,
        image=image,
        cli=LoseOneCreateResponse(),
    )
    continued = controller.execute(
        claimed=claimed,
        repeat_plan=repeat,
        replica=replica,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        continuation_split_step=1,
    )
    direct = reconstruct(
        execution_ref=replica.execution_ref,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        artifact_path=(tmp_path / "direct-uninterrupted").resolve(),
    )

    assert continued.receipt.status is ReconstructionStatus.COMPLETE
    assert continued.receipt.checkpoint_digest == direct.checkpoint_digest
    _record_trace(
        "continuation_create_response_loss",
        "reconciled_complete",
        image_id=image.image_id,
        launch_digest=continued.launch_digest,
        controls_digest=continued.effective_controls_digest,
        checkpoint_digest=continued.receipt.checkpoint_digest,
        timings_seconds=continued.timings,
        create_response_lost=True,
    )


def test_network_none_denies_controlled_canary_and_negative_control_detects_it(
    tmp_path: Path,
) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest
    image = load_image_identity(Path(manifest))
    cli = DockerCLI()
    network = "carbon-c03-canary-" + uuid.uuid4().hex[:12]
    canary = "carbon-c03-canary-" + uuid.uuid4().hex[:12]
    cli.run(["network", "create", network])
    try:
        cli.run(
            [
                "run",
                "--detach",
                "--name",
                canary,
                "--network",
                network,
                "--entrypoint",
                "/opt/carbon-worker/bin/python",
                image.image_id,
                "-I",
                "-m",
                "http.server",
                "8080",
            ]
        )
        canary_ip = (
            cli.run(
                [
                    "inspect",
                    canary,
                    "--format",
                    "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                ]
            )
            .stdout.decode("ascii")
            .strip()
        )
        connected = None
        for _ in range(30):
            connected = cli.run(
                _probe_arguments(
                    tmp_path,
                    image.image_id,
                    ["connect", canary_ip, "8080"],
                    network=network,
                ),
                timeout=20,
                accepted=(0, 10),
            )
            if connected.returncode == 0:
                break
            time.sleep(0.1)
        assert connected is not None
        assert connected.returncode == 0
        denied = cli.run(
            _probe_arguments(tmp_path, image.image_id, ["connect", canary_ip, "8080"]),
            timeout=20,
            accepted=(10,),
        )
        assert denied.returncode == 10
        dns_denied = cli.run(
            _probe_arguments(tmp_path, image.image_id, ["connect", canary, "8080"]),
            timeout=20,
            accepted=(10,),
        )
        assert dns_denied.returncode == 10
        _record_trace(
            "network_canary",
            "denied",
            image_id=image.image_id,
            connected_negative_control=connected.returncode,
            network_none_probe=denied.returncode,
            dns_probe=dns_denied.returncode,
        )
    finally:
        cli.run(["rm", "--force", canary], accepted=(0, 1))
        cli.run(["network", "rm", network], accepted=(0, 1))


def test_external_timeout_reaps_blocked_worker(tmp_path: Path) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest
    image = load_image_identity(Path(manifest))
    cli = DockerCLI()
    arguments = _probe_arguments(tmp_path, image.image_id, ["blocked", "30"])
    arguments[0:2] = ["create"]
    name = arguments[arguments.index("--name") + 1]
    launch_digest = _sha("a")
    created = cli.run(arguments)
    assert created.stdout.strip()
    cli.run(["start", name])
    started = time.monotonic()
    remove_exact_container(cli=cli, container_name=name, launch_digest=launch_digest)
    cleanup_seconds = time.monotonic() - started
    assert cleanup_seconds < 30
    assert cli.run(["inspect", name], accepted=(0, 1)).returncode == 1
    _record_trace(
        "blocked_worker_timeout",
        "cancelled",
        image_id=image.image_id,
        cleanup_seconds=cleanup_seconds,
        container_absent=True,
    )


def test_descendant_cannot_survive_exact_container_termination(tmp_path: Path) -> None:
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest
    image = load_image_identity(Path(manifest))
    cli = DockerCLI()
    arguments = _probe_arguments(
        tmp_path, image.image_id, ["descendant", "/scratch/parent-ready"]
    )
    arguments[0:2] = ["create"]
    name = arguments[arguments.index("--name") + 1]
    launch_digest = _sha("a")
    cli.run(arguments)
    cli.run(["start", name])
    for _ in range(50):
        ready = cli.run(
            ["exec", name, "/usr/bin/test", "-f", "/scratch/parent-ready"],
            accepted=(0, 1),
        )
        if ready.returncode == 0:
            break
        time.sleep(0.1)
    assert ready.returncode == 0
    remove_exact_container(cli=cli, container_name=name, launch_digest=launch_digest)
    time.sleep(3.5)
    assert cli.run(["inspect", name], accepted=(0, 1)).returncode == 1
    _record_trace(
        "descendant_cleanup",
        "cancelled",
        image_id=image.image_id,
        descendant_ready=True,
        container_absent=True,
    )
