"""C-MLP-03 slice 3: battery practice on the miner's own GPU.

The battery GPU path is the CPU practice with one difference, where the worker
runs: the pinned GPU worker image, the host's installed device record and
`JAX_PLATFORMS=cuda`, on the miner lane. These tests hold that:
- the scope is battery's own, bound to the pinned GPU worker, and says it is
  for speed only (no score, never official);
- a campaign freezes it and an attach re-checks it against the installed
  record; any other GPU scope is refused;
- practice runs Carbon's fixed program on the GPU worker, records what JAX
  actually ran on, and scores exactly as on the CPU;
- the carrier binds the device record into the request and builds the miner
  lane's GPU container (device, runtime, `JAX_PLATFORMS=cuda`);
- setup detects the GPU, installs the device record, and the profile carries
  the GPU image and scope through to a launch.

Fixtures stand in for Docker, nvidia-smi and the device; the scope, record,
ledger, practice scoring and profile checks are real. A real GPU run is the
slice's acceptance and needs a GPU host. Engineering evidence only.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_research_images import (
    IMAGES,
    IMPLEMENTATION,
    frozen_manifest,
    host,  # noqa: F401 - fixture
    runtime,
)
from test_battery_validator_daemon import submission
from test_miner_inference_providers import (
    HOTKEY,
    Checks,
    Onboarding,
)

from carbon.battery import campaign as battery
from carbon.battery.practice import PROGRAM
from carbon.development_session import battery_gpu as gpu
from carbon.development_session import research_carrier
from carbon.development_session.profile import canonical
from carbon.reconstruction import onboarding
from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.host_inventory import HostDeviceRecord
from carbon.reconstruction.worker.model import (
    MINER_HOST_AUTHORITY,
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
)
from scripts.dev.miner_launchpad import runner
from scripts.dev.miner_launchpad.environment_setup import (
    AUTONOMOUS,
    LOCAL_CPU,
    LOCAL_GPU,
    EnvironmentSetup,
    LiveChecks,
    SetupRefused,
)

UUID = "GPU-31e88d04-75ff-89b2-9160-4b923dd7eb81"
OBSERVED = {
    "devices": [
        {
            "device_uuid": UUID,
            "device_kind": "NVIDIA GeForce RTX 4090",
            "driver_version": "580.65",
            "driver_model": "N/A",
            "compute_capability": "8.9",
            "device_memory_mib": "24564",
            "display_active": "Disabled",
        }
    ],
    "source": "/usr/bin/nvidia-smi",
}


def gpu_image(tag="9", *, lock=None):
    value = "sha256:" + tag * 64
    return WorkerImageIdentity(
        image_id=value,
        config_digest=value,
        source_tree_digest="sha256:" + "a" * 64,
        wheel_digest="sha256:" + "b" * 64,
        lock_digest=lock or GPU_PROFILE.environment_lock_digest,
        base_image_digest="sha256:" + "1" * 64,
        build_recipe_digest="sha256:" + "d" * 64,
        entrypoint_digest="sha256:" + "e" * 64,
    )


def record_bytes(image):
    return canonical({"schema": "carbon.c03.worker-image.v1", **asdict(image)})


def install(root, image):
    """What the runner's `install_research_images` puts in a campaign root."""
    path = root / gpu.GPU_IMAGE_RECORD
    path.unlink(missing_ok=True)
    path.write_bytes(record_bytes(image))
    path.chmod(0o600)


def device(root=None):
    document = onboarding.build_host_record(
        observed=OBSERVED,
        record_id="this-machine",
        provider="own-machine",
        platform="LINUX_BARE_METAL",
        container_runtime="DOCKER_ENGINE",
        provenance="fixture observation",
        now=1.0,
    )
    if root is None:
        from carbon.reconstruction.host_inventory import tagged_sha256

        return HostDeviceRecord(document, tagged_sha256(canonical(document)))
    onboarding.install_record(root, document, name="host-device.json")
    return HostDeviceRecord.load(root)


# --- the scope ----------------------------------------------------------------


def test_the_scope_binds_the_pinned_gpu_worker_and_is_for_speed_only():
    image = gpu_image()
    scope = gpu.gpu_scope(image)
    assert scope["schema"] == gpu.SCOPE_SCHEMA
    assert scope["image"] == image.image_id
    assert scope["profile_digest"] == GPU_PROFILE.digest
    assert scope["jax_platforms"] == "cuda"
    assert scope["backends"] == ["jax"]
    assert (scope["purpose"], scope["score"], scope["official_eligible"]) == (
        "speed_only",
        None,
        False,
    )
    assert gpu.declared_scope({"gpu_research": [scope]}) == [scope]
    # A worker that is not the pinned GPU image has no GPU scope.
    with pytest.raises(ValueError, match="GPU worker image"):
        gpu.gpu_scope(gpu_image(lock="sha256:" + "c" * 64))


def test_burgers_gpu_scope_and_malformed_scopes_are_not_battery_s():
    from carbon.development_session.gpu_research import SCHEMA

    for scopes in (
        [{"schema": SCHEMA, "official_eligible": False, "score": None}],
        [{**gpu.gpu_scope(gpu_image()), "official_eligible": True}],
        [{**gpu.gpu_scope(gpu_image()), "purpose": "evaluation"}],
        [],
        "not a list",
    ):
        with pytest.raises(ValueError, match="battery GPU practice scope"):
            gpu.declared_scope({"gpu_research": scopes})


def test_the_cpu_program_is_unchanged_and_the_gpu_one_records_its_backend():
    # The GPU program is the CPU one plus an observation, so no existing CPU
    # practice identity moves and the GPU one states what JAX ran on.
    assert gpu.GPU_PROGRAM.startswith(PROGRAM)
    added = gpu.GPU_PROGRAM[len(PROGRAM) :]
    assert "runtime.json" in added and "default_backend" in added


# --- the campaign -------------------------------------------------------------


def with_gpu(image):
    return {**runtime(), "gpu_research": [gpu.gpu_scope(image)]}


@pytest.fixture
def gpu_host(host, monkeypatch):  # noqa: F811 - the fixture above
    """The battery campaign host, whose image loader reads GPU records for real."""
    from carbon.reconstruction.worker import docker_runtime

    cpu = docker_runtime.load_image_identity

    def load(path):
        # The host fixture stubs the CPU worker's identity; a GPU record is
        # read with the real parser so its scope is recomputed for real.
        if Path(path).name == gpu.GPU_IMAGE_RECORD:
            return WorkerImageIdentity(
                **{
                    k: v
                    for k, v in json.loads(Path(path).read_bytes()).items()
                    if k != "schema"
                }
            )
        return cpu(path)

    monkeypatch.setattr(docker_runtime, "load_image_identity", load)
    return host


def test_a_battery_campaign_freezes_its_gpu_practice_scope(gpu_host):
    image = gpu_image()
    install(gpu_host.root, image)
    prepared = gpu_host.prepare("run", with_gpu(image))
    frozen = json.loads((gpu_host.root / "campaign-manifest.json").read_bytes())
    assert frozen["runtime"] == with_gpu(image)
    assert prepared.manifest["runtime"]["gpu_research"][0]["purpose"] == "speed_only"
    assert gpu_host.composed[-1]["gpu_image"] == image
    gpu_host.prepare("resume")
    assert gpu_host.composed[-1]["gpu_image"] == image
    # Specimen: the installed record now names another GPU image, so the frozen
    # scope no longer describes this host and the resume is refused.
    install(gpu_host.root, gpu_image("8"))
    with pytest.raises(ValueError, match="differs from the declared scope"):
        gpu_host.prepare("resume")


def test_a_cpu_campaign_composes_no_gpu(gpu_host):
    install(gpu_host.root, gpu_image())
    gpu_host.prepare("run", runtime())
    assert gpu_host.composed[-1]["gpu_image"] is None


def test_a_declared_gpu_scope_without_its_record_is_refused(gpu_host):
    with pytest.raises((ValueError, FileNotFoundError)):
        gpu_host.prepare("run", with_gpu(gpu_image()))
    assert not (gpu_host.root / "campaign-manifest.json").exists()


def test_an_attach_rechecks_the_gpu_scope_exactly():
    image = gpu_image()
    manifest = frozen_manifest(with_gpu(image))
    battery.check_attached(
        manifest, implementation=IMPLEMENTATION, images=IMAGES, gpu_image=image
    )
    for host_image in (gpu_image("8"), None):
        with pytest.raises(ValueError, match="runtime|GPU"):
            battery.check_attached(
                manifest,
                implementation=IMPLEMENTATION,
                images=IMAGES,
                gpu_image=host_image,
            )


def test_the_registry_offers_battery_gpu_practice_as_its_own_profile():
    from carbon.challenge_registry import resolve
    from carbon.challenge_registry.registry import GPU_RESEARCH
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    _, profile = resolve(BATTERY_CHALLENGE, entry_version(), GPU_RESEARCH)
    assert "speed only" in profile.summary
    assert {"gpu_worker_image", "host_device_record"} <= set(profile.requirements)


def entry_version():
    from carbon.battery.challenge import CHALLENGE

    return CHALLENGE.version


# --- practice -----------------------------------------------------------------


def practice(tmp_path, *, gpu_image_, seen):
    import battery_subprocess_runner as stand_in

    from carbon.battery.research import BatteryPractice
    from carbon.development_session.research_control import CampaignControl
    from carbon.development_session.research_ledger import CampaignLedger

    tmp_path.chmod(0o700)
    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(_manifest())
    ledger.generation = CampaignControl(ledger).acquire()

    def run(ledger_, *, accelerator=None, **kwargs):
        # The stand-in runs the same program in a subprocess. It cannot bind a
        # device; what it shows is what practice asks the carrier for.
        seen.append({"accelerator": accelerator, **kwargs})
        return stand_in.run(ledger_, **kwargs)

    return BatteryPractice(
        ledger=ledger,
        owner="miner-requester",
        image=SimpleNamespace(image_id="sha256:" + "1" * 64),
        root=REPOSITORY,
        runner=run,
        gpu_image=gpu_image_,
        device=device(),
    )


def _manifest():
    from test_battery_research_images import launch

    return battery.manifest_document(
        launch(runtime()),
        owner="miner-requester",
        implementation=IMPLEMENTATION,
        images=list(IMAGES),
    )


def test_gpu_practice_runs_the_fixed_program_on_the_gpu_worker_and_records_it(
    tmp_path,
):
    image, seen = gpu_image(), []
    practise = practice(tmp_path, gpu_image_=image, seen=seen)
    strategy = submission("hk", "knn", neighbours=8).strategy
    result = practise("task-gpu-1", strategy)
    asked = seen[0]
    assert asked["accelerator"] == research_carrier.MINER_GPU
    assert asked["image"] is image
    assert asked["source"] == gpu.GPU_PROGRAM
    backend = result["backend"]
    assert backend["kind"] == "ISOLATED_CARRIER_GPU"
    assert backend["jax_platforms"] == "cuda"
    assert backend["image"] == image.image_id
    assert backend["device_record_digest"] == device().digest
    assert backend["purpose"] == "speed_only" and "speed only" in backend["note"]
    # What JAX actually ran on is recorded as observed. This stand-in has no
    # GPU, so it says cpu: the record states the backend, it never assumes it.
    assert backend["observed"]["default_backend"] == "cpu"
    assert result["official_eligible"] is False and result["final_exam"] is False
    assert result["summary"]


def test_a_pytorch_recipe_is_refused_before_any_gpu_run(tmp_path):
    seen = []
    practise = practice(tmp_path, gpu_image_=gpu_image(), seen=seen)
    strategy = submission(
        "hk", "mlp", backend="pytorch", width=16, depth=1, steps=32
    ).strategy
    with pytest.raises(ValueError, match="GPU practice serves JAX recipes only"):
        practise("task-gpu-2", strategy)
    assert seen == []


def test_practice_refuses_a_gpu_image_that_is_not_the_pinned_one(tmp_path):
    with pytest.raises(ValueError, match="GPU worker image"):
        practice(tmp_path, gpu_image_=gpu_image(lock="sha256:" + "c" * 64), seen=[])


# --- the carrier --------------------------------------------------------------


def test_the_gpu_worker_profile_is_the_miner_lane_on_the_recorded_device(
    tmp_path, monkeypatch
):
    from carbon.reconstruction.worker import accelerator_runtime, docker_runtime

    record = device()
    profile = research_carrier._worker_profile(record)
    assert profile.accelerator_authority == MINER_HOST_AUTHORITY
    assert profile.accelerator_role == "MINER_RESEARCH"
    assert profile.accelerator_device_uuid == UUID
    assert profile.accelerator_grant_digest == record.digest
    cpu = research_carrier._worker_profile(None)
    assert cpu.accelerator_profile_id is None
    monkeypatch.setattr(accelerator_runtime, "host_device", lambda: record)
    stage = tmp_path / "input"
    stage.mkdir()
    arguments = docker_runtime.create_arguments(
        container_name="carbon-d4-fixture",
        image_id=gpu_image().image_id,
        input_directory=stage,
        cpuset="0,1",
        launch_digest="sha256:" + "f" * 64,
        worker_profile=profile,
    )
    assert "--gpus" in arguments and f"device={UUID}" in arguments
    assert "JAX_PLATFORMS=cuda" in arguments
    assert "JAX_PLATFORMS=cpu" not in arguments


class Stop(Exception):
    pass


def test_the_carrier_binds_the_device_record_into_the_gpu_request(
    tmp_path, monkeypatch
):
    record, requests = device(), []
    monkeypatch.setattr(research_carrier, "_gpu_device", lambda: record)

    def reserve(identity, **kwargs):
        requests.append(kwargs["request"])
        raise Stop

    ledger = SimpleNamespace(root=tmp_path, reserve=reserve)
    call = {
        "owner": "o",
        "identity": "t",
        "source": "print(1)",
        "files": {},
        "image": SimpleNamespace(image_id=gpu_image().image_id),
        "seconds": 60,
        "provenance": "BATTERY_PUBLIC_PRACTICE",
        "extra_resources": {},
    }
    for accelerator in (None, research_carrier.MINER_GPU):
        with pytest.raises(Stop):
            research_carrier._run_locked(ledger, accelerator=accelerator, **call)
    cpu, on_gpu = requests
    # A CPU run's request is exactly what it was; the GPU run's names the
    # device record, so a replaced record is a different request.
    assert "accelerator" not in cpu
    assert on_gpu["accelerator"] == {
        "kind": research_carrier.MINER_GPU,
        "profile": GPU_PROFILE.profile_id,
        "device": record.digest,
    }
    # Only Carbon's fixed practice may ask for the GPU: never a miner-authored
    # script, and never an accelerator the carrier does not know.
    for provenance, accelerator in (
        ("MINER_SELF_REPORTED", research_carrier.MINER_GPU),
        ("BATTERY_PUBLIC_PRACTICE", "ANY_GPU"),
    ):
        with pytest.raises(ValueError, match="unsupported accelerator"):
            research_carrier._run_locked(
                ledger, accelerator=accelerator, **{**call, "provenance": provenance}
            )


def test_without_a_device_record_the_gpu_run_fails_closed(monkeypatch, tmp_path):
    from carbon.reconstruction.worker import accelerator_runtime

    def missing():
        raise WorkerFailure(WorkerCode.UNAVAILABLE)

    monkeypatch.setattr(accelerator_runtime, "host_device", missing)
    with pytest.raises(ValueError, match="no GPU device record"):
        research_carrier._gpu_device()


# --- setup --------------------------------------------------------------------


class GpuChecks(Checks):
    def __init__(self, image):
        super().__init__()
        self.image = image

    def gpu(self, manifest):
        self.calls.append(("gpu", str(manifest)))
        return {
            "scope": gpu.gpu_scope(self.image),
            "device_kind": "NVIDIA GeForce RTX 4090",
            "record_digest": device().digest,
        }


def gpu_setup(tmp_path):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    home = tmp_path / "miner"
    home.mkdir(mode=0o700)
    for name in ("worker.json", "analysis.json", "operator.json", "gpu.json"):
        (home / name).write_text("{}")
    checks = GpuChecks(gpu_image())
    setup = EnvironmentSetup(root, onboarding=Onboarding(), checks=checks)
    setup.begin({"address": HOTKEY})
    inference = {"provider_id": "engy-chat", "model_id": "deepseek-v4-flash-0731"}
    quote = setup.quote(inference)
    setup.inference(
        {
            **inference,
            "key": "sk-fixture",
            "consent": {"max_cost_nano": quote["max_cost_nano"]},
        }
    )
    paths = {
        "image_manifest": str(home / "worker.json"),
        "analysis_image_manifest": str(home / "analysis.json"),
    }
    return setup, checks, home, paths


def test_setup_on_this_machine_s_gpu_carries_the_scope_to_the_profile(tmp_path):
    setup, _, home, paths = gpu_setup(tmp_path)
    state = setup.compute(
        {"choice": LOCAL_GPU, **paths, "gpu_image_manifest": str(home / "gpu.json")}
    )
    check = state["steps"]["compute"]["check"]
    assert check["gpu"] == "NVIDIA GeForce RTX 4090"
    assert "speed only" in check["note"]
    setup.agent({"choice": AUTONOMOUS, "operator_config": str(home / "operator.json")})
    setup.review({"confirm": True})
    cfg = runner.validated_profile(json.loads(setup.profile_path.read_bytes()))
    assert cfg["gpu_image"] == str(home / "gpu.json")
    assert cfg["runtime"]["gpu_research"] == [gpu.gpu_scope(gpu_image())]
    # The prelaunch review shows a GPU campaign, not a CPU fallback.
    from scripts.dev.miner_launchpad.prelaunch import review

    assert review(cfg)["execution"]["backend"] == "cuda"


def test_the_gpu_choice_needs_its_image_and_the_cpu_choice_takes_none(tmp_path):
    setup, _, home, paths = gpu_setup(tmp_path)
    with pytest.raises(SetupRefused) as refused:
        setup.compute({"choice": LOCAL_GPU, **paths})
    assert (refused.value.field, refused.value.code) == (
        "gpu_image_manifest",
        "field_required",
    )
    with pytest.raises(SetupRefused) as refused:
        setup.compute(
            {"choice": LOCAL_CPU, **paths, "gpu_image_manifest": str(home / "gpu.json")}
        )
    assert refused.value.field == "gpu_image_manifest"
    with pytest.raises(SetupRefused) as refused:
        setup.compute(
            {
                "choice": LOCAL_GPU,
                **paths,
                "gpu_image_manifest": str(home / "absent.json"),
            }
        )
    assert (
        refused.value.code,
        "accelerator_worker_image.sh" in refused.value.next_step,
    ) == (
        "image_not_built",
        True,
    )


class FakeCLI:
    def json(self, arguments):
        assert arguments[0] == "info"
        return {"OperatingSystem": "Ubuntu 24.04", "Runtimes": {"nvidia": {}}}


@pytest.fixture
def live(tmp_path, monkeypatch):
    """LiveChecks.gpu against fixture nvidia-smi, Docker and device runtime."""
    from carbon.reconstruction.worker import accelerator_runtime, docker_runtime

    manifest = tmp_path / "gpu.json"
    manifest.write_bytes(record_bytes(gpu_image()))
    monkeypatch.setattr(onboarding, "observe_local_device", lambda **_: OBSERVED)
    monkeypatch.setattr(onboarding, "detect_platform", lambda: "LINUX_BARE_METAL")
    monkeypatch.setattr(docker_runtime, "DockerCLI", FakeCLI)
    toolkit = []
    monkeypatch.setattr(
        accelerator_runtime,
        "verify_image_and_toolkit",
        lambda *, cli, image: toolkit.append(image.image_id),
    )
    monkeypatch.setattr(onboarding, "doctor_report", lambda **_: {"findings": []})
    host_root = tmp_path / "accelerators"
    return SimpleNamespace(
        checks=LiveChecks(host_root=host_root),
        manifest=manifest,
        root=host_root,
        toolkit=toolkit,
    )


def test_the_live_gpu_check_detects_installs_the_record_and_verifies(live):
    found = live.checks.gpu(live.manifest)
    assert found["device_kind"] == "NVIDIA GeForce RTX 4090"
    assert found["scope"] == gpu.gpu_scope(gpu_image())
    installed = HostDeviceRecord.load(live.root)
    assert installed.device_uuid == UUID
    assert installed.provider == "own-machine"
    assert (live.root / "host-device.json").stat().st_mode & 0o777 == 0o600
    assert live.toolkit == [gpu_image().image_id]
    # A second check keeps the installed record of the same device.
    before = (live.root / "host-device.json").read_bytes()
    live.checks.gpu(live.manifest)
    assert (live.root / "host-device.json").read_bytes() == before


def test_the_live_gpu_check_refuses_by_field(live, monkeypatch, tmp_path):
    wrong = tmp_path / "cpu-worker.json"
    wrong.write_bytes(record_bytes(gpu_image(lock="sha256:" + "c" * 64)))
    with pytest.raises(SetupRefused) as refused:
        live.checks.gpu(wrong)
    assert (refused.value.field, refused.value.code) == (
        "gpu_image_manifest",
        "gpu_image_unverified",
    )

    def no_gpu(**_):
        raise WorkerFailure(WorkerCode.UNAVAILABLE)

    monkeypatch.setattr(onboarding, "observe_local_device", no_gpu)
    with pytest.raises(SetupRefused) as refused:
        live.checks.gpu(live.manifest)
    assert (refused.value.field, refused.value.code) == ("gpu", "gpu_not_detected")


def test_a_host_record_setup_cannot_write_names_the_command(live, tmp_path):
    blocked = tmp_path / "a-file"
    blocked.write_text("")
    checks = LiveChecks(host_root=blocked / "accelerators")
    with pytest.raises(SetupRefused) as refused:
        checks.gpu(live.manifest)
    assert refused.value.code == "host_device_record_not_writable"
    assert "carbon_accelerator.py prepare" in refused.value.next_step


def test_a_host_the_miner_lane_cannot_use_is_refused_with_its_blockers(
    live, monkeypatch
):
    monkeypatch.setattr(
        onboarding,
        "doctor_report",
        lambda **_: {
            "findings": [
                {"check": "container_device_runtime", "state": "BLOCKED"},
                {"check": "display_output", "state": "BLOCKED"},
            ]
        },
    )
    with pytest.raises(SetupRefused) as refused:
        live.checks.gpu(live.manifest)
    # Only what the miner lane requires blocks; a display on the GPU does not.
    assert refused.value.code == "gpu_host_not_ready:container_device_runtime"
