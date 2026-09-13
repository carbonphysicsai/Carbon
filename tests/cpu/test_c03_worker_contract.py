"""C-03 closed protocol, policy, staging, and durable-launch tests."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sqlite3
import sys
import threading
import time
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from c02_fixtures import compile_c02_plan

from carbon.execution import (
    ClaimedExecution,
    DurableExecutionBinding,
    DurableExecutionQueue,
    DurableWorkerLaunchStore,
    ExecutionAttemptRef,
    ExecutionCode,
    ExecutionFailure,
    ExecutionScope,
    QueueClaim,
    WorkerLaunchBinding,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    SubmissionId,
)
from carbon.reconstruction.model import PublicTrainingArchive
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import (
    DevelopmentReplica,
    development_replicate_digest,
    freeze_development_repeat_plan,
)
from carbon.reconstruction.worker.controller import IsolatedReconstructionController
from carbon.reconstruction.worker.docker_runtime import (
    _bounded_capture,
    create_arguments,
)
from carbon.reconstruction.worker.model import (
    MEMORY_BYTES,
    OUTPUT_BYTES,
    OUTPUT_MEMBERS,
    PRODUCTIVE_DEADLINE_SECONDS,
    SCRATCH_BYTES,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
    WorkerLaunchState,
    WorkerTiming,
)
from carbon.reconstruction.worker.protocol import (
    _audit_zip,
    decode_output_stream,
    load_worker_request,
    snapshot_output,
    stage_request,
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


def _sha(character: str) -> str:
    return "sha256:" + character * 64


def test_worker_failure_keeps_bounded_private_diagnostic_out_of_public_error() -> None:
    failure = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"private-path" * (1024**2)
    )

    assert str(failure) == "Development reconstruction worker operation failed."
    assert "private-path" not in str(failure)
    assert len(failure.private_diagnostic) == 1024**2


def _fixture(tmp_path: Path):
    plan = compile_c02_plan(tmp_path, backbone="fno")
    profile = compile_development_profile(plan)
    execution = ExecutionAttemptRef(
        SubmissionId("12345678-1234-4234-8234-123456789012"), 1
    )
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
    source = tmp_path / "public-train.npz"
    source.write_bytes(b"public synthetic TRAIN bytes")
    archive = PublicTrainingArchive.from_file(source, provenance="c03_public_fixture")
    seed = DerivedSeed(bytes(range(32)))
    randomness_digest = "sha256:" + hashlib.sha256(seed.as_backend_bytes()).hexdigest()
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
    replicate_digest = development_replicate_digest(
        binding=placeholder,
        execution_ref=execution,
        randomness_digest=randomness_digest,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
    )
    replica = DevelopmentReplica(
        BoundReconstructionReplicate(
            replace(placeholder.replicate_identity, replicate_digest=replicate_digest)
        ),
        execution,
        randomness_digest,
    )
    repeat = freeze_development_repeat_plan(
        plan_id="c03-development-repeat",
        construction_plan_digest=plan.to_ref().content_digest,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
        replicas=(replica,),
    )
    handle = ExecutionAttemptHandle(
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
    )
    binding = DurableExecutionBinding(
        handle,
        RequesterIdentity("development-requester-v1"),
        plan.strategy_hash,
        ExecutionScope.FIXTURE_DEVELOPMENT,
        plan.to_ref().content_digest,
        profile.profile_digest,
        policy.content_digest,
        _sha("6"),
    )
    claim = QueueClaim(execution, "claim-1", "c03-worker-pool")
    return (
        ClaimedExecution(claim, binding),
        repeat,
        replica,
        plan,
        archive,
        seed,
        DevelopmentWorkerProfile(policy.content_digest, resource.content_digest),
    )


def _image() -> WorkerImageIdentity:
    return WorkerImageIdentity(*(_sha(character) for character in "aabcdef0"))


def test_selected_profile_is_exact_development_envelope() -> None:
    profile = DevelopmentWorkerProfile(_sha("1"), _sha("2"))

    assert profile.body["scope"] == "UNQUALIFIED_PUBLIC_DEVELOPMENT"
    assert profile.body["concurrency"] == 1
    assert profile.body["memory"] == {"bytes": MEMORY_BYTES, "swap_bytes": 0}
    assert profile.body["scratch"]["bytes"] == SCRATCH_BYTES
    assert profile.body["output"]["bytes"] == OUTPUT_BYTES
    assert profile.body["deadline_seconds"] == PRODUCTIVE_DEADLINE_SECONDS
    assert profile.body["accelerators"] == "NOT_APPLICABLE"
    assert profile.body["security"]["seccomp"] == "docker-default"


def test_docker_argv_has_fixed_security_and_no_caller_command(tmp_path: Path) -> None:
    profile = DevelopmentWorkerProfile(_sha("1"), _sha("2"))
    arguments = create_arguments(
        container_name="carbon-c03-fixture",
        image_id=_sha("a"),
        input_directory=tmp_path,
        cpuset="0,1",
        launch_digest=_sha("b"),
        worker_profile=profile,
    )
    rendered = " ".join(arguments)

    for expected in (
        "--network none",
        "--ipc private",
        "--read-only",
        "--cap-drop ALL",
        "no-new-privileges=true",
        "--pids-limit 256",
        f"--memory {MEMORY_BYTES}",
        f"--memory-swap {MEMORY_BYTES}",
        "--cpus 2",
        "--cpuset-cpus 0,1",
        "--restart no",
        "--log-driver local",
        "--log-opt max-size=1m",
        "--log-opt max-file=1",
        "--log-opt compress=false",
    ):
        assert expected in rendered
    assert arguments[-1] == _sha("a")
    assert "--privileged" not in arguments
    assert "--pid" not in arguments
    assert "--device" not in arguments
    assert "--entrypoint" not in arguments
    assert "--volume" not in arguments


def test_zip_permission_bits_without_a_file_type_are_regular(tmp_path: Path) -> None:
    archive_path = tmp_path / "permission-only.zip"
    member = zipfile.ZipInfo("array.npy")
    member.external_attr = 0o600 << 16
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(member, b"bounded")

    assert _audit_zip(archive_path, expanded_limit=1024) == len(b"bounded")


def test_worker_entry_path_has_no_scoring_archive_reward_or_network_authority() -> None:
    root = Path(__file__).resolve().parents[2]
    runtime_files = (
        root / "carbon/reconstruction/worker/entrypoint.py",
        root / "carbon/reconstruction/worker/exporter.py",
        root / "carbon/reconstruction/worker/protocol.py",
    )
    imports: set[str] = set()
    for path in runtime_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
    assert not any(
        name.startswith(
            (
                "carbon.archive",
                "carbon.evidence_archive",
                "carbon.network",
                "carbon.rewards",
                "carbon.scoring",
                "docker",
                "requests",
            )
        )
        for name in imports
    )


def test_stage_is_one_snapshot_and_worker_redecodes_authority(tmp_path: Path) -> None:
    claimed, repeat, replica, plan, archive, seed, profile = _fixture(tmp_path)
    stage, digest = stage_request(
        stage_root=(tmp_path / "state").resolve(),
        claimed=claimed,
        repeat_plan=repeat,
        replica=replica,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        worker_profile=profile,
    )
    ref, decoded, staged_archive, staged_seed, split = load_worker_request(stage)

    assert digest.startswith("sha256:")
    assert ref == replica.execution_ref
    assert decoded.to_ref() == plan.to_ref()
    assert staged_archive.content_digest == archive.content_digest
    assert staged_seed == seed
    assert split is None
    assert {item.name for item in stage.iterdir()} == {
        "request.json",
        "plan.bin",
        "train.npz",
        "derived-seed.bin",
    }


def test_stage_rejects_cross_attempt_and_policy_mismatch(tmp_path: Path) -> None:
    claimed, repeat, replica, plan, archive, seed, profile = _fixture(tmp_path)
    wrong = replace(
        replica,
        execution_ref=ExecutionAttemptRef(replica.execution_ref.submission_id, 2),
    )

    with pytest.raises(WorkerFailure) as captured:
        stage_request(
            stage_root=(tmp_path / "state").resolve(),
            claimed=claimed,
            repeat_plan=repeat,
            replica=wrong,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            worker_profile=profile,
        )

    assert captured.value.code is WorkerCode.POLICY

    production = replace(
        claimed,
        binding=replace(
            claimed.binding,
            handle=replace(
                claimed.binding.handle,
                admission_kind=AdmissionKind.PRODUCTION,
            ),
            scope=ExecutionScope.REAL_PATH_NON_LIVE,
        ),
    )
    with pytest.raises(WorkerFailure) as captured:
        stage_request(
            stage_root=(tmp_path / "production-state").resolve(),
            claimed=production,
            repeat_plan=repeat,
            replica=replica,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            worker_profile=profile,
        )
    assert captured.value.code is WorkerCode.POLICY


def test_output_snapshot_rejects_symlinks_and_special_authority(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "artifact").mkdir()
    (source / "artifact" / "payload").symlink_to(tmp_path / "host-secret")

    with pytest.raises(WorkerFailure) as captured:
        snapshot_output(source, tmp_path / "snapshots")

    assert captured.value.code is WorkerCode.OUTPUT


def test_output_snapshot_caps_members_and_seals_late_writes(tmp_path: Path) -> None:
    overflowing = tmp_path / "overflowing"
    overflowing.mkdir()
    for index in range(OUTPUT_MEMBERS + 1):
        (overflowing / f"member-{index:04d}").write_bytes(b"x")

    with pytest.raises(WorkerFailure) as captured:
        snapshot_output(overflowing, tmp_path / "overflow-snapshots")
    assert captured.value.code is WorkerCode.OUTPUT

    source = tmp_path / "source-late"
    source.mkdir()
    payload = source / "payload"
    payload.write_bytes(b"accepted-snapshot")
    snapshot, digest = snapshot_output(
        source,
        tmp_path / "snapshots",
        destination_name="a" * 64,
    )
    payload.write_bytes(b"late-worker-write")

    assert digest.startswith("sha256:")
    assert (snapshot / "payload").read_bytes() == b"accepted-snapshot"
    assert (snapshot / "payload").stat().st_mode & 0o222 == 0


def test_closed_output_stream_decodes_exact_bytes_and_rejects_traversal(
    tmp_path: Path,
) -> None:
    def line(value: object) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"

    source = tmp_path / "valid.stream"
    source.write_bytes(
        line({"schema": "carbon.c03.output-stream.v1"})
        + line({"path": "artifact/value.bin", "size": 3})
        + b"abc"
        + line({"bytes": 3, "end": True, "members": 1})
    )
    destination = tmp_path / "decoded"

    decode_output_stream(source, destination)

    assert (destination / "artifact/value.bin").read_bytes() == b"abc"

    hostile = tmp_path / "hostile.stream"
    hostile.write_bytes(
        line({"schema": "carbon.c03.output-stream.v1"})
        + line({"path": "../host", "size": 1})
        + b"x"
        + line({"bytes": 1, "end": True, "members": 1})
    )
    rejected = tmp_path / "rejected"
    with pytest.raises(WorkerFailure) as captured:
        decode_output_stream(hostile, rejected)

    assert captured.value.code is WorkerCode.OUTPUT
    assert not rejected.exists()


def test_durable_launch_intent_converges_and_conflicts_fail_closed(
    tmp_path: Path,
) -> None:
    claimed, _, replica, plan, archive, _, profile = _fixture(tmp_path)
    now = float(time.time())
    timing = WorkerTiming(now, now + PRODUCTIVE_DEADLINE_SECONDS, 1.0, "boot-fixture")
    binding = WorkerLaunchBinding(
        claimed.claim,
        replica.binding.replicate_identity.replicate_id,
        replica.binding.replicate_identity.replicate_digest,
        plan.to_ref().content_digest,
        compile_development_profile(plan).profile_digest,
        archive.content_digest,
        replica.randomness_digest,
        _sha("8"),
        profile,
        _image(),
        timing,
        "linux-ci-host",
        "carbon-c03-fixture",
    )
    store = DurableWorkerLaunchStore(tmp_path / "launch.sqlite3")
    barrier = threading.Barrier(3)
    states: list[WorkerLaunchState] = []

    def reserve() -> None:
        barrier.wait()
        states.append(store.record_intent(binding).state)

    threads = [threading.Thread(target=reserve) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert states == [WorkerLaunchState.INTENT_RECORDED] * 2
    assert (
        store.raw_status(binding.execution_id)["launch_digest"] == binding.launch_digest
    )
    create_claims: list[bool] = []
    barrier = threading.Barrier(3)

    def claim_create() -> None:
        barrier.wait()
        create_claims.append(store.claim_create(binding))

    threads = [threading.Thread(target=claim_create) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert sorted(create_claims) == [False, True]
    assert (
        store.raw_status(binding.execution_id)["state"]
        == WorkerLaunchState.CREATING.value
    )
    with pytest.raises(WorkerFailure) as captured:
        store.record_intent(replace(binding, stage_digest=_sha("9")))
    assert captured.value.code is WorkerCode.CONFLICT
    assert store.reconciliation_targets() == (
        {
            "execution_id": binding.execution_id,
            "launch_digest": binding.launch_digest,
            "container_name": binding.container_name,
            "state": WorkerLaunchState.CREATING.value,
            "host_id": binding.host_id,
            "boot_id": binding.timing.boot_id,
            "productive_deadline_unix": binding.timing.productive_deadline_unix,
        },
    )
    observation = {
        "schema": "carbon.c03.resource-observation.v1",
        "memory": {"peak_bytes": 1234},
    }
    store.transition(
        binding,
        WorkerLaunchState.RECONCILIATION_REQUIRED,
        terminal_code=WorkerCode.CLEANUP.value,
        resource_observation=observation,
    )
    assert (
        store.record_operator_cleanup(
            execution_id=binding.execution_id,
            launch_digest=binding.launch_digest,
            cleaned=False,
        )
        is WorkerLaunchState.QUARANTINED
    )
    assert store.all_statuses() == (
        {
            "execution_id": binding.execution_id,
            "launch_digest": binding.launch_digest,
            "state": WorkerLaunchState.QUARANTINED.value,
            "container_id": None,
            "effective_controls_digest": None,
            "output_snapshot_digest": None,
            "terminal_code": WorkerCode.CLEANUP.value,
            "resource_observation": observation,
        },
    )
    with sqlite3.connect(store.path) as database:
        database.execute(
            "UPDATE c03_launch_v1 SET resource_observation_json='[1]' "
            "WHERE execution_id=?",
            (binding.execution_id,),
        )
    with pytest.raises(WorkerFailure) as captured:
        store.all_statuses()
    assert captured.value.code is WorkerCode.UNAVAILABLE


def test_controller_capture_enforces_cap_during_receipt_and_reaps_writer() -> None:
    command = [
        sys.executable,
        "-c",
        "import os,time;os.write(1,b'x'*65536);time.sleep(5)",
    ]
    started = time.monotonic()
    with pytest.raises(WorkerFailure) as captured:
        _bounded_capture(
            command,
            environment=dict(os.environ),
            timeout=3,
            maximum=4096,
        )

    assert captured.value.code is WorkerCode.RUNTIME
    assert time.monotonic() - started < 2
    assert len(captured.value.private_diagnostic) <= 1024**2


def test_c03_failed_infrastructure_cannot_mint_successor_attempt(
    tmp_path: Path,
) -> None:
    claimed, _, _, _, _, _, _ = _fixture(tmp_path)
    queue = DurableExecutionQueue(tmp_path / "terminal-queue.sqlite3")
    queue.admit(claimed.binding)
    active = queue.claim(claimed.claim.ref, "c03-worker", claim_id="terminal-claim")
    queue.mark_running(active.claim)
    queue.fail_infrastructure(active.claim)

    successor = replace(
        claimed.binding,
        handle=replace(claimed.binding.handle, attempt_number=2),
    )
    with pytest.raises(ExecutionFailure) as captured:
        queue.admit(successor)

    assert captured.value.code is ExecutionCode.CONFLICT


def test_live_wait_uses_same_boot_monotonic_deadline(monkeypatch) -> None:
    now = float(time.time())
    timing = WorkerTiming(now, now + PRODUCTIVE_DEADLINE_SECONDS, 10.0, "boot")

    class NoCLI:
        def run(self, *args, **kwargs):  # pragma: no cover - must not be reached
            raise AssertionError("deadline should fire before a Docker call")

    controller = object.__new__(IsolatedReconstructionController)
    controller.cli = NoCLI()
    monkeypatch.setattr(time, "monotonic", lambda: 611.0)
    monkeypatch.setattr(time, "time", lambda: 0.0)

    with pytest.raises(WorkerFailure) as captured:
        controller._wait_file("carbon-c03-fixture", "/scratch/ready", timing)

    assert captured.value.code is WorkerCode.DEADLINE


def test_request_json_duplicate_fields_fail_closed(tmp_path: Path) -> None:
    claimed, repeat, replica, plan, archive, seed, profile = _fixture(tmp_path)
    stage, _ = stage_request(
        stage_root=(tmp_path / "state").resolve(),
        claimed=claimed,
        repeat_plan=repeat,
        replica=replica,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        worker_profile=profile,
    )
    request = stage / "request.json"
    payload = request.read_text(encoding="utf-8")
    request.chmod(0o600)
    request.write_text(
        payload.replace('"schema":', '"schema":"duplicate","schema":', 1),
        encoding="utf-8",
    )

    with pytest.raises(WorkerFailure) as captured:
        load_worker_request(stage)

    assert captured.value.code is WorkerCode.INVALID


def test_owner_doctor_is_read_only_and_all_delivery_commands_are_fixed() -> None:
    script = (
        Path(__file__).resolve().parents[2] / "scripts/dev/c03_worker.sh"
    ).read_text(encoding="utf-8")
    doctor_branch = script.split("  doctor)", 1)[1].split("    ;;", 1)[0]
    assert "c03_worker_image.sh" not in doctor_branch
    assert 'operator doctor "${manifest}"' in script
    assert 'CARBON_C03_TRACE_PATH="${smoke_root}/c03-smoke-traces.jsonl"' in script
    assert 'CARBON_C03_JUNIT_PATH="${smoke_root}/c03-smoke-junit.xml"' in script
    assert 'operator status "${state_root}"' in script
    assert 'operator reconcile "${state_root}"' in script
