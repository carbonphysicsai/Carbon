"""Prospective fixed-device worker contracts; no accelerator is initialized."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_c03_worker_contract import _fixture, _image, _sha

from carbon.development_session.profile import canonical
from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker.controller import IsolatedReconstructionController
from carbon.reconstruction.worker.docker_runtime import create_arguments
from carbon.reconstruction.worker.model import (
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
)


def _profile():
    return DevelopmentWorkerProfile(
        _sha("2"),
        _sha("3"),
        "carbon.c03.cuda.development.v1",
        "1.0",
        GPU_PROFILE.profile_id,
        _sha("4"),
        AcceleratorRole.MINER_RESEARCH.value,
    )


@pytest.fixture
def host_grant(tmp_path, monkeypatch):
    root = tmp_path / "host"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    image = replace(_image(), lock_digest=GPU_PROFILE.environment_lock_digest)
    document = {
        "schema": runtime.GRANT_SCHEMA,
        "status": "APPROVED",
        "authority": "SYNTHETIC_TEST_ONLY",
        "grant_id": "nonproduction-fixture",
        "host_root": str(root),
        "controller_root": str(tmp_path / "controller"),
        "principal": "fixture-principal",
        "roles": [AcceleratorRole.MINER_RESEARCH.value],
        "device_uuid": GPU_PROFILE.device_uuid,
        "execution_profile_digest": GPU_PROFILE.digest,
        "image_id": image.image_id,
        "resource_policy_digest": _sha("2"),
        "resource_class_digest": _sha("3"),
        "expires_unix": 2000,
        "allocation": "EXCLUSIVE_SINGLE_DEVICE",
        "cleanup": "EXACT_GRANT_OWNED_CONTAINERS_AND_DEVICE_RELEASE",
        "host_use": "DEDICATED_NO_DISPLAY_OR_OTHER_COMPUTE",
    }
    path = root / "grant.json"
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    options = {
        "principal": "fixture-principal",
        "state_root": tmp_path / "controller",
        "image": image,
        "role": AcceleratorRole.MINER_RESEARCH,
        "now": 1000.0,
        "dispatch": True,
    }
    return path, document, options


def test_private_host_grant_is_revocable_and_not_relocatable(host_grant):
    path, document, options = host_grant
    grant = runtime.AcceleratorHostAdmission.load()
    grant.verify(**options)
    for change in (
        {"principal": "other"},
        {"state_root": path.parent / "other"},
        {"role": AcceleratorRole.VALIDATOR_RECONSTRUCTION},
        {"image": _image()},
    ):
        with pytest.raises(WorkerFailure):
            grant.verify(**{**options, **change})
    path.write_bytes(canonical({**document, "status": "REVOKED"}))
    with pytest.raises(WorkerFailure):
        grant.verify(**options)


@pytest.mark.parametrize("expiry", [999, 1000, 1599, True, "2000"])
def test_expiry_reserves_full_dispatched_deadline(host_grant, expiry):
    path, document, options = host_grant
    path.write_bytes(canonical({**document, "expires_unix": expiry}))
    with pytest.raises(WorkerFailure):
        runtime.AcceleratorHostAdmission.load().verify(**options)


def test_exclusive_lease_is_shared_across_clients_and_released(host_grant):
    first = runtime.AcceleratorHostAdmission.load()
    second = runtime.AcceleratorHostAdmission.load()
    with first.exclusive_lease():
        with pytest.raises(WorkerFailure) as busy, second.exclusive_lease():
            pytest.fail("second client acquired the fixed device")
        assert busy.value.code is WorkerCode.CONFLICT
    with second.exclusive_lease():
        pass


def test_quarantine_survives_new_admission_object(host_grant):
    path, _, options = host_grant
    (path.parent / "device-quarantined").write_text("UNRECONCILED")
    with pytest.raises(WorkerFailure) as error:
        runtime.AcceleratorHostAdmission.load().verify(**options)
    assert error.value.code is WorkerCode.QUARANTINED


def test_allocation_intent_survives_controller_loss_and_only_exact_cleanup_clears_it(
    host_grant, monkeypatch
):
    runtime.mark_device_allocation(container_name="fixture", launch_digest=_sha("1"))
    with pytest.raises(WorkerFailure):
        runtime.reject_existing_device_containers(cli=SimpleNamespace())
    assert runtime.owns_device_allocation(
        container_name="fixture", launch_digest=_sha("1")
    )
    assert not runtime.owns_device_allocation(
        container_name="other", launch_digest=_sha("1")
    )
    with pytest.raises(WorkerFailure):
        runtime.finish_device_allocation(
            container_name="other", launch_digest=_sha("1")
        )
    monkeypatch.setattr(runtime, "verify_device_release", lambda: None)
    runtime.finish_device_allocation(container_name="fixture", launch_digest=_sha("1"))
    assert not (host_grant[0].parent / "active-allocation.json").exists()


def test_watchdog_reconciles_removed_container_before_releasing_device_intent(
    host_grant, monkeypatch
):
    from carbon.reconstruction.worker.docker_runtime import remove_exact_container

    runtime.mark_device_allocation(container_name="fixture", launch_digest=_sha("1"))
    observed = []

    def absent(command):
        raise WorkerFailure(WorkerCode.UNAVAILABLE)

    def query(command, **kwargs):
        observed.append(command)
        return SimpleNamespace(stdout=b"")

    monkeypatch.setattr(
        runtime, "verify_device_release", lambda: observed.append("device-release")
    )
    remove_exact_container(
        cli=SimpleNamespace(json=absent, run=query),
        container_name="fixture",
        launch_digest=_sha("1"),
    )
    assert observed[0][0] == "ps"
    assert observed[-1] == "device-release"
    assert not (host_grant[0].parent / "active-allocation.json").exists()


def test_device_requests_are_exact_and_cpu_remains_without_devices(tmp_path):
    options = {
        "container_name": "fixture",
        "image_id": _image().image_id,
        "input_directory": tmp_path,
        "cpuset": "0,1",
        "launch_digest": _sha("1"),
    }
    cpu = create_arguments(
        **options, worker_profile=DevelopmentWorkerProfile(_sha("2"), _sha("3"))
    )
    gpu = create_arguments(**options, worker_profile=_profile())
    assert "--gpus" not in cpu and "--runtime" not in cpu
    assert "device=" + GPU_PROFILE.device_uuid in gpu
    assert "JAX_PLATFORMS=cuda" in gpu
    assert "JAX_PLATFORMS=cpu" not in gpu
    assert "--network" in gpu and gpu[gpu.index("--network") + 1] == "none"
    assert runtime.device_request()["DeviceIDs"] == [GPU_PROFILE.device_uuid]
    assert _profile().body["schema"] == "carbon.c03.development-worker-profile.v2"


class MetadataCLI:
    def __init__(self, runtimes=None, labels=None):
        self.runtimes = runtimes if runtimes is not None else {"nvidia": {}}
        self.labels = (
            labels
            if labels is not None
            else {
                "org.opencontainers.image.carbon.accelerator.profile": GPU_PROFILE.digest,
                "org.opencontainers.image.carbon.accelerator.environment": GPU_PROFILE.environment_lock_digest,
            }
        )

    def json(self, command):
        if command[0] == "info":
            return {"Runtimes": self.runtimes}
        return {"Config": {"Labels": self.labels}}


def test_image_lock_labels_and_toolkit_are_all_required(host_grant):
    _, _, options = host_grant
    runtime.verify_image_and_toolkit(cli=MetadataCLI(), image=options["image"])
    for cli in (MetadataCLI(runtimes={}), MetadataCLI(labels={})):
        with pytest.raises(WorkerFailure):
            runtime.verify_image_and_toolkit(cli=cli, image=options["image"])


@pytest.mark.parametrize("change", ["uuid", "display", "driver", "compute"])
def test_observation_rejects_other_gpu_display_driver_and_foreign_compute(change):
    row = (
        f"{GPU_PROFILE.device_uuid}, {GPU_PROFILE.device_kind}, 581.95, 6144, Disabled"
    )
    row = row.replace(GPU_PROFILE.device_uuid, "GPU-other") if change == "uuid" else row
    row = row.replace("Disabled", "Enabled") if change == "display" else row
    row = row.replace("581.95", "580.00") if change == "driver" else row

    def run(command, **kwargs):
        output = (
            (b"123, GPU-foreign" if change == "compute" else b"")
            if "--query-compute-apps=pid,gpu_uuid" in command
            else row.encode()
        )
        return SimpleNamespace(stdout=output)

    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(
            cli=SimpleNamespace(run=run), container_name="fixture"
        )


def test_failed_release_quarantines_shared_slot(host_grant, monkeypatch):
    from carbon.reconstruction.worker import docker_runtime

    monkeypatch.setattr(Path, "is_file", lambda self: True)
    monkeypatch.setattr(
        docker_runtime,
        "_bounded_capture",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b"123, GPU-busy"),
    )
    with pytest.raises(WorkerFailure) as error:
        runtime.verify_device_release()
    assert error.value.code is WorkerCode.CLEANUP
    assert (host_grant[0].parent / "device-quarantined").is_file()


def _gpu_fixture(tmp_path, monkeypatch):
    import c02_fixtures
    import test_c03_worker_contract

    from carbon.reconstruction.accelerators import accelerator_dependency_specs

    original = c02_fixtures.compile_c02_plan
    monkeypatch.setattr(c02_fixtures, "ENVIRONMENT_ID", GPU_PROFILE.profile_id)
    monkeypatch.setattr(c02_fixtures, "ENVIRONMENT_VERSION", "1.0")
    monkeypatch.setattr(
        c02_fixtures,
        "DEPENDENCY_SPECS",
        c02_fixtures.DEPENDENCY_SPECS + accelerator_dependency_specs(GPU_PROFILE),
    )
    monkeypatch.setattr(
        test_c03_worker_contract,
        "compile_c02_plan",
        lambda *a, **k: original(*a, **k, environment_digest=GPU_PROFILE.digest),
    )
    return _fixture(tmp_path)


def test_closed_gpu_protocol_roundtrip_and_cpu_request_schema(tmp_path, monkeypatch):
    from carbon.reconstruction.worker.protocol import load_worker_request, stage_request

    claimed, repeat, replica, plan, archive, seed, _ = _gpu_fixture(
        tmp_path, monkeypatch
    )
    stage, _ = stage_request(
        stage_root=tmp_path / "staging",
        claimed=claimed,
        repeat_plan=repeat,
        replica=replica,
        plan=plan,
        training_archive=archive,
        derived_seed=seed,
        worker_profile=_profile(),
    )
    _, loaded_plan, _, _, _ = load_worker_request(stage)
    request = json.loads((stage / "request.json").read_bytes())
    assert request["schema"] == "carbon.c03.worker-request.v2"
    assert request["accelerator"]["role"] == AcceleratorRole.MINER_RESEARCH.value
    assert loaded_plan.to_ref() == plan.to_ref()


def test_controller_routes_only_matching_private_grant_under_exclusive_lease(
    host_grant, tmp_path, monkeypatch
):
    import time

    claimed, repeat, replica, plan, archive, seed, _ = _gpu_fixture(
        tmp_path, monkeypatch
    )
    path, document, options = host_grant
    document.update(
        principal=claimed.binding.requester_identity.value,
        expires_unix=time.time() + 1000,
    )
    path.write_bytes(canonical(document))
    controller = object.__new__(IsolatedReconstructionController)
    controller.state_root = options["state_root"]
    controller.image = options["image"]
    controller.cli = MetadataCLI()
    controller.cli.run = lambda *args, **kwargs: SimpleNamespace(stdout=b"")
    observed = []

    def execute_bound(**kwargs):
        observed.append(kwargs["worker_profile"])
        assert kwargs["cancelled"]() is False
        with (
            pytest.raises(WorkerFailure),
            runtime.AcceleratorHostAdmission.load().exclusive_lease(),
        ):
            pytest.fail("controller released the device lease before dispatch")
        return "mocked-existing-worker-boundary"

    controller._execute_bound = execute_bound
    request = {
        "claimed": claimed,
        "repeat_plan": repeat,
        "replica": replica,
        "plan": plan,
        "training_archive": archive,
        "derived_seed": seed,
    }
    with pytest.raises(WorkerFailure):
        controller.execute(**request, accelerator_role="MINER_RESEARCH")
    assert not observed
    assert (
        controller.execute(**request, accelerator_role=AcceleratorRole.MINER_RESEARCH)
        == "mocked-existing-worker-boundary"
    )
    assert observed[0].accelerator_profile_id == GPU_PROFILE.profile_id
    path.unlink()
    with pytest.raises(WorkerFailure):
        controller.execute(**request, accelerator_role=AcceleratorRole.MINER_RESEARCH)
    assert len(observed) == 1


def test_cancellation_requires_boolean_and_never_silently_ignores_stop():
    for callback, code in (
        (lambda: True, WorkerCode.CANCELLED),
        (lambda: "false", WorkerCode.INVALID),
    ):
        with pytest.raises(WorkerFailure) as error:
            IsolatedReconstructionController._check_cancelled(callback)
        assert error.value.code is code
