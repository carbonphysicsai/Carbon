"""Exercise shared control verification and real allocation state, no GPU/daemon."""

from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace

import accelerator_host
import pytest
from scripted_docker import ScriptedDocker
from test_accelerator_worker import _profile
from test_c03_worker_contract import _image, _sha
from test_fixed_practice_failure_diagnostics import harness as _diagnostic_harness

from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.accelerators import (
    AcceleratorRole,
    miner_lane_assurance,
    validator_self_service_assurance,
)
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker import docker_runtime as docker
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    MINER_HOST_AUTHORITY,
    STRICT_HOST_GRANT_AUTHORITY,
    RequestDerivedWorkerProfile,
    WorkerCode,
    WorkerFailure,
)

harness = _diagnostic_harness


@pytest.fixture
def installed(tmp_path, monkeypatch):
    root = tmp_path / "host"
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    accelerator_host.install(root)
    return root, runtime.host_device()


def self_service(record, role=AcceleratorRole.MINER_RESEARCH):
    return replace(
        _profile(),
        accelerator_authority=MINER_HOST_AUTHORITY,
        accelerator_grant_digest=record.digest,
        accelerator_role=role.value,
    )


def controls(tmp_path, record, profile, *, display="Disabled"):
    options = {
        "container_name": "fixture",
        "image_id": _image().image_id,
        "input_directory": tmp_path,
        "cpuset": "0,1",
        "launch_digest": _sha("1"),
        "worker_profile": profile,
    }
    scripted = ScriptedDocker(image=_image())
    scripted.create_arguments = docker.create_arguments(**options)
    document = scripted.json(["inspect", "fixture"])
    calls = []
    identity = [
        record.device_uuid,
        record.device_kind,
        record.driver_version,
        str(record.device_memory_mib),
        display,
    ]

    def run(arguments, **kwargs):
        calls.append(arguments)
        if "/usr/bin/nvidia-smi" in arguments:
            if "--query-gpu=driver_model.current" in arguments:
                return SimpleNamespace(stdout=b"WDDM\n", returncode=0)
            assert (
                "--query-gpu=uuid,name,driver_version,memory.total,display_active"
                in arguments
            )
            return SimpleNamespace(
                stdout=(", ".join(identity) + "\n").encode(), returncode=0
            )
        return scripted.run(arguments, **kwargs)

    return SimpleNamespace(
        options=options,
        document=document,
        identity=identity,
        calls=calls,
        cli=SimpleNamespace(json=lambda _: document, run=run),
    )


@pytest.mark.parametrize("role", list(AcceleratorRole))
@pytest.mark.parametrize(
    "display,observed", [("Enabled", True), ("Disabled", False), ("N/A", None)]
)
def test_registered_self_service_roles_keep_cpu_controls_without_strict_claims(
    installed, tmp_path, monkeypatch, role, display, observed
):
    _, record = installed
    profile = self_service(record, role)
    probe = controls(tmp_path, record, profile, display=display)
    monkeypatch.setattr(
        runtime,
        "inspect_gpu_device",
        lambda **_: pytest.fail("strict observation used"),
    )
    _, evidence = docker.inspect_effective_controls(cli=probe.cli, **probe.options)
    observation = evidence["accelerator"]
    assert observation["observation_mode"] == "SELF_SERVICE_HOST"
    assert observation["host_record_digest"] == record.digest
    assert observation["display_active"] is observed
    assert observation["other_compute_processes"] is None
    assert observation["official_eligible"] is False
    expected = (
        miner_lane_assurance()
        if role is AcceleratorRole.MINER_RESEARCH
        else validator_self_service_assurance()
    )
    assert observation["assurance"] == expected
    assert observation["assurance"]["strict_equivalent"] is False
    assert observation["assurance"]["validator_grade"] is False
    assert evidence["process"]["Seccomp"] == "2"
    with pytest.raises(WorkerFailure):
        runtime.require_strict_observation(observation)
    assert all(
        not any("query-compute-apps" in arg or "driver_model" in arg for arg in call)
        for call in probe.calls
    )
    labels = probe.document["Config"]["Labels"]
    assert labels[docker.SELF_SERVICE_RECORD_LABEL] == record.digest
    assert docker.STRICT_GRANT_LABEL not in labels
    assert docker.LOCAL_APPROVAL_LABEL not in labels


@pytest.mark.parametrize(
    "field,value",
    [
        ("ReadonlyRootfs", False),
        ("NetworkMode", "host"),
        ("Privileged", True),
        ("Memory", 1),
        ("MemorySwap", -1),
        ("PidsLimit", 0),
        ("CpusetCpus", "2,3"),
        ("CapDrop", []),
        ("SecurityOpt", []),
        ("DeviceRequests", []),
    ],
)
def test_self_service_never_bypasses_shared_containment(
    installed, tmp_path, field, value
):
    _, record = installed
    probe = controls(tmp_path, record, self_service(record))
    probe.document["HostConfig"][field] = value
    with pytest.raises(WorkerFailure) as caught:
        docker.inspect_effective_controls(cli=probe.cli, **probe.options)
    assert caught.value.code is WorkerCode.POLICY
    assert caught.value.private_diagnostic == b""


@pytest.mark.parametrize(
    "field,value,predicate",
    [
        ("Memory", 1, "MEMORY"),
        ("DeviceRequests", [], "DEVICE_REQUESTS"),
        ("NetworkMode", "host", "NETWORK"),
    ],
)
def test_fixed_practice_diagnoses_first_guard_without_relaxing_it(
    installed, tmp_path, field, value, predicate
):
    _, record = installed
    probe = controls(tmp_path, record, self_service(record))
    probe.document["HostConfig"][field] = value
    with pytest.raises(WorkerFailure) as caught:
        docker.inspect_effective_controls(
            cli=probe.cli, diagnose_policy=True, **probe.options
        )
    assert caught.value.code is WorkerCode.POLICY
    assert docker.controls_predicate(caught.value) == predicate
    assert caught.value.private_diagnostic.endswith(predicate.encode("ascii"))


def test_fixed_practice_diagnoses_gpu_label_and_nested_observer(
    installed, tmp_path, monkeypatch
):
    _, record = installed
    probe = controls(tmp_path, record, self_service(record))
    probe.document["Config"]["Labels"]["carbon.accelerator.device"] = "wrong"
    with pytest.raises(WorkerFailure) as label_error:
        docker.inspect_effective_controls(
            cli=probe.cli, diagnose_policy=True, **probe.options
        )
    assert docker.controls_predicate(label_error.value) == "GPU_DEVICE_LABEL"
    probe.document["Config"]["Labels"]["carbon.accelerator.device"] = record.device_uuid

    original = WorkerFailure(WorkerCode.POLICY)

    def refuse(**_):
        raise original

    monkeypatch.setattr(runtime, "inspect_self_service_device", refuse)
    with pytest.raises(WorkerFailure) as nested_error:
        docker.inspect_effective_controls(
            cli=probe.cli, diagnose_policy=True, **probe.options
        )
    assert docker.controls_predicate(nested_error.value) == "GPU_DEVICE_OBSERVATION"
    with pytest.raises(WorkerFailure) as default_error:
        docker.inspect_effective_controls(cli=probe.cli, **probe.options)
    assert default_error.value is original


@pytest.mark.parametrize(
    "label", [docker.STRICT_GRANT_LABEL, docker.LOCAL_APPROVAL_LABEL]
)
def test_dual_authority_labels_cannot_downgrade_or_impersonate(
    installed, tmp_path, label
):
    _, record = installed
    probe = controls(tmp_path, record, self_service(record))
    probe.document["Config"]["Labels"][label] = _sha("8")
    with pytest.raises(WorkerFailure):
        docker.inspect_effective_controls(cli=probe.cli, **probe.options)


@pytest.mark.parametrize(
    "label",
    [docker.SELF_SERVICE_RECORD_LABEL, "org.opencontainers.image.carbon.c03.policy"],
)
def test_self_service_labels_bind_exact_host_and_complete_profile(
    installed, tmp_path, label
):
    _, record = installed
    probe = controls(tmp_path, record, self_service(record))
    probe.document["Config"]["Labels"][label] = _sha("8")
    with pytest.raises(WorkerFailure):
        docker.inspect_effective_controls(cli=probe.cli, **probe.options)


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_observed_device_identity_mismatch_refuses(installed, tmp_path, index):
    _, record = installed
    probe = controls(tmp_path, record, self_service(record))
    probe.identity[index] = "different"
    with pytest.raises(WorkerFailure) as caught:
        docker.inspect_effective_controls(cli=probe.cli, **probe.options)
    assert caught.value.code is WorkerCode.POLICY


def test_stale_host_record_and_request_derived_profile_do_not_admit(
    installed, tmp_path
):
    _, record = installed
    profile = self_service(record)
    probe = controls(
        tmp_path, record, replace(profile, accelerator_grant_digest=_sha("9"))
    )
    with pytest.raises(WorkerFailure):
        docker.inspect_effective_controls(cli=probe.cli, **probe.options)
    with pytest.raises(WorkerFailure):
        runtime.inspect_self_service_device(
            cli=probe.cli,
            container_name="fixture",
            worker_profile=RequestDerivedWorkerProfile.of(profile),
        )


def test_strict_unestablished_enumeration_cannot_fall_back(
    installed, tmp_path, monkeypatch
):
    _, record = installed
    probe = controls(tmp_path, record, _profile())
    monkeypatch.setattr(
        runtime,
        "inspect_self_service_device",
        lambda **_: pytest.fail("strict downgraded"),
    )
    with pytest.raises(WorkerFailure) as caught:
        docker.inspect_effective_controls(cli=probe.cli, **probe.options)
    assert caught.value.code is WorkerCode.POLICY
    assert any("--query-gpu=driver_model.current" in call for call in probe.calls)


@pytest.mark.parametrize(
    "authority", [STRICT_HOST_GRANT_AUTHORITY, LOCAL_DEVELOPMENT_AUTHORITY]
)
def test_other_authorities_reject_self_service_label(installed, tmp_path, authority):
    _, record = installed
    profile = replace(
        _profile(),
        accelerator_authority=authority,
        accelerator_plan_digest=(
            _sha("9") if authority == LOCAL_DEVELOPMENT_AUTHORITY else None
        ),
    )
    probe = controls(tmp_path, record, profile)
    probe.document["Config"]["Labels"][docker.SELF_SERVICE_RECORD_LABEL] = record.digest
    with pytest.raises(WorkerFailure):
        docker.inspect_effective_controls(cli=probe.cli, **probe.options)


def test_local_approval_observation_keeps_its_own_plan(
    installed, tmp_path, monkeypatch
):
    _, record = installed
    profile = replace(
        _profile(),
        accelerator_authority=LOCAL_DEVELOPMENT_AUTHORITY,
        accelerator_plan_digest=_sha("9"),
    )
    probe = controls(tmp_path, record, profile)
    seen = []

    def local(**kwargs):
        seen.append(kwargs["development_plan_digest"])
        return {"observation_mode": runtime.OBSERVATION_MODE_DEVELOPMENT}

    monkeypatch.setattr(runtime, "inspect_gpu_device", local)
    monkeypatch.setattr(
        runtime,
        "inspect_self_service_device",
        lambda **_: pytest.fail("approval downgraded"),
    )
    _, evidence = docker.inspect_effective_controls(cli=probe.cli, **probe.options)
    assert seen == [_sha("9")]
    assert (
        evidence["accelerator"]["observation_mode"]
        == runtime.OBSERVATION_MODE_DEVELOPMENT
    )


def cleanup_cli(record):
    removed = []

    def run(arguments, **kwargs):
        removed.append(arguments[0])
        return SimpleNamespace(
            stdout=b"", returncode=1 if arguments[0] == "inspect" else 0
        )

    return (
        SimpleNamespace(
            json=lambda _: {
                "Config": {
                    "Labels": {
                        "org.opencontainers.image.carbon.c03.launch": _sha("1"),
                        "carbon.accelerator.device": record.device_uuid,
                        docker.SELF_SERVICE_RECORD_LABEL: record.digest,
                    }
                }
            },
            run=run,
        ),
        removed,
    )


def test_owned_self_service_allocation_finishes_without_strict_release(
    installed, monkeypatch
):
    root, record = installed
    runtime.mark_device_allocation(
        container_name="fixture",
        launch_digest=_sha("1"),
        authority=MINER_HOST_AUTHORITY,
    )
    monkeypatch.setattr(
        runtime, "verify_device_release", lambda: pytest.fail("whole-device claim")
    )
    cli, commands = cleanup_cli(record)
    docker.remove_exact_container(
        cli=cli, container_name="fixture", launch_digest=_sha("1")
    )
    assert commands[:3] == ["stop", "kill", "rm"]
    assert not (root / "active-allocation.json").exists()
    assert not (root / "device-quarantined").exists()


def test_missing_record_is_not_discharged_by_a_self_service_label(installed):
    _, record = installed
    cli, _ = cleanup_cli(record)
    with pytest.raises(WorkerFailure) as caught:
        docker.remove_exact_container(
            cli=cli, container_name="fixture", launch_digest=_sha("1")
        )
    assert caught.value.code is WorkerCode.CLEANUP


def test_self_service_label_cannot_downgrade_owned_strict_allocation(
    installed, monkeypatch
):
    _, record = installed
    runtime.mark_device_allocation(
        container_name="fixture",
        launch_digest=_sha("1"),
        authority=STRICT_HOST_GRANT_AUTHORITY,
    )
    seen = []
    monkeypatch.setattr(
        runtime, "verify_device_release", lambda: seen.append("strict verification")
    )
    cli, _ = cleanup_cli(record)
    docker.remove_exact_container(
        cli=cli, container_name="fixture", launch_digest=_sha("1")
    )
    assert seen == ["strict verification"]


@pytest.mark.parametrize("corrupt", [False, True])
def test_foreign_or_malformed_allocation_is_never_completed(installed, corrupt):
    root, record = installed
    runtime.mark_device_allocation(
        container_name="foreign",
        launch_digest=_sha("7"),
        authority=MINER_HOST_AUTHORITY,
    )
    path = root / "active-allocation.json"
    if corrupt:
        path.write_bytes(b"not-json")
    original = path.read_bytes()
    cli, _ = cleanup_cli(record)
    with pytest.raises(WorkerFailure):
        docker.remove_exact_container(
            cli=cli, container_name="fixture", launch_digest=_sha("1")
        )
    assert path.read_bytes() == original


@pytest.mark.parametrize("create_fails", [False, True])
def test_fixed_practice_records_allocation_before_create_and_releases_slot(
    harness, installed, monkeypatch, create_fails
):
    root, record = installed
    profile = self_service(record)
    state = {"slot": False, "created": False, "removed": False, "checked": False}
    events = []

    @contextmanager
    def slot():
        state["slot"] = True
        events.append("slot acquired")
        try:
            yield
        finally:
            state["slot"] = False
            events.append("slot released")

    base_cli = carrier.DockerCLI
    original_remove = docker.remove_exact_container

    class CLI(base_cli):
        def run(self, arguments, **kwargs):
            if arguments[0] == "create":
                allocation = runtime._allocation_document()
                assert allocation["authority"] == MINER_HOST_AUTHORITY
                assert state["slot"] is True
                state["checked"] = True
                state["created"] = True
            elif arguments[0] == "rm":
                state["removed"] = True
            if arguments[0] in ("stop", "kill", "rm", "inspect"):
                return SimpleNamespace(
                    stdout=b"", returncode=1 if arguments[0] == "inspect" else 0
                )
            return super().run(arguments, **kwargs)

        def json(self, arguments):
            allocation = runtime._allocation_document()
            if not state["created"] or state["removed"]:
                raise WorkerFailure(WorkerCode.UNAVAILABLE)
            return {
                "Config": {
                    "Labels": {
                        "org.opencontainers.image.carbon.c03.launch": allocation[
                            "launch_digest"
                        ],
                        "carbon.accelerator.device": record.device_uuid,
                        docker.SELF_SERVICE_RECORD_LABEL: record.digest,
                    }
                }
            }

    monkeypatch.setattr(carrier, "DockerCLI", CLI)
    monkeypatch.setattr(carrier, "_gpu_device", lambda: record)
    monkeypatch.setattr(carrier, "_gpu_pins", lambda *args: ("fixture", "p", "l"))
    monkeypatch.setattr(carrier, "_check_gpu_host", lambda *args: None)
    monkeypatch.setattr(carrier, "_worker_profile", lambda *args: profile)
    monkeypatch.setattr(runtime, "shared_host_lease", slot)
    monkeypatch.setattr(
        runtime, "reject_existing_device_containers", lambda **kwargs: None
    )
    monkeypatch.setattr(carrier, "remove_exact_container", original_remove)
    monkeypatch.setattr(
        runtime, "verify_device_release", lambda: pytest.fail("strict release reached")
    )

    def inspect(**kwargs):
        assert state["slot"] is False
        return _sha("8"), {}

    monkeypatch.setattr(carrier, "inspect_effective_controls", inspect)
    if create_fails:
        original = WorkerFailure(WorkerCode.RUNTIME)
        harness.fail_stage, harness.error = "CREATE", original
        with pytest.raises(WorkerFailure) as caught:
            harness.run(accelerator=carrier.MINER_GPU)
        assert caught.value is original
    else:
        assert (
            harness.run(accelerator=carrier.MINER_GPU)["schema"]
            == "carbon.autoresearch.worker-result.v1"
        )
    assert state["checked"] and state["removed"]
    assert state["slot"] is False
    assert events == ["slot acquired", "slot released"]
    assert not (root / "active-allocation.json").exists()
    assert not (root / "device-quarantined").exists()


def test_fixed_practice_mark_failure_releases_locks_without_creating_or_removing(
    harness, installed, monkeypatch
):
    _, record = installed
    state = {"held": False}

    @contextmanager
    def slot():
        state["held"] = True
        try:
            yield
        finally:
            state["held"] = False

    original = WorkerFailure(WorkerCode.CONFLICT)

    def refuse(**kwargs):
        assert state["held"]
        raise original

    monkeypatch.setattr(carrier, "_gpu_device", lambda: record)
    monkeypatch.setattr(carrier, "_gpu_pins", lambda *args: ("fixture", "p", "l"))
    monkeypatch.setattr(carrier, "_check_gpu_host", lambda *args: None)
    monkeypatch.setattr(carrier, "_worker_profile", lambda *args: self_service(record))
    monkeypatch.setattr(runtime, "shared_host_lease", slot)
    monkeypatch.setattr(
        runtime, "reject_existing_device_containers", lambda **kwargs: None
    )
    monkeypatch.setattr(runtime, "mark_device_allocation", refuse)
    with pytest.raises(WorkerFailure) as caught:
        harness.run(accelerator=carrier.MINER_GPU)
    assert caught.value is original
    assert not state["held"]
    assert "CREATE" not in harness.events and "CLEANUP" not in harness.events
    assert harness.ledger.operation_state("public-task", owner="alice") == "RESERVED"
