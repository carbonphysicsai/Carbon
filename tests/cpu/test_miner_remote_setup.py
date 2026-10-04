"""Setup and launch on the miner's own remote machine or container.

OWNER-MINER-COMPUTE-LINK-ONLY-01, as amended on 2026-10-02: the miner runs
any setup, and Carbon only connects to it (LINKONLY-D5 to D9). These tests
drive the real setup, profile validator, prelaunch review, runner preflight
and battery campaign door; the live checks are fixtures or a fixture SSH
client, and nothing is reached. What is held:
- setup offers "your own remote machine or container" with the two built
  transports, and the endpoint transport with why it is not built;
- its live check uses only the miner's SSH and starts nothing; refusals name
  the field;
- sending the worker is its own step, for `ssh-docker` only, with consent to
  the exact destination and image;
- the profile carries `remote_machine` (where) and the runtime `remote_gpu`
  (how, beside `gpu_research`); each needs the other;
- both campaign doors build the runner from the frozen runtime and the
  profile's machine, and refuse a profile whose transport differs.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_gpu_practice import (
    BATTERY_REF,
    gpu_host,  # noqa: F401 - fixture
    gpu_image,
    install,
    record_bytes,
    with_gpu,
)
from test_battery_research_images import (
    host,  # noqa: F401 - fixture
    launch,
)
from test_miner_inference_providers import HOTKEY, Checks, Onboarding

from carbon.battery import campaign as battery
from carbon.compute import remote_machine as rm
from carbon.compute.remote_route import remote_scope
from carbon.compute.remote_runner import RemoteRunner
from carbon.compute.remote_transport import SSHContainer, SSHDocker
from carbon.development_session import battery_gpu as gpu
from carbon.development_session.profile import canonical
from carbon.development_session.research_ledger import CampaignLedger
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
from scripts.dev.miner_launchpad import runner
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.environment_setup import (
    GRAPHITE,
    REMOTE,
    EnvironmentSetup,
    LiveChecks,
    SetupRefused,
    choices,
)

MACHINE = {"transport": "ssh-docker", "destination": "miner@gpu-box", "port": 2222}
POD = {"transport": "ssh-container", "destination": "root@pod-1"}


class RemoteChecks(Checks):
    """Fixture live checks, with the miner's remote setup reached by fixture."""

    def __init__(self, *, worker_image="missing"):
        super().__init__()
        self.worker_image = worker_image
        self.sent = []

    def remote(self, manifest, machine, campaign):
        self.calls.append(("remote", str(manifest), machine.document()))
        image = gpu_image()
        check = {"transport": machine.transport, "reached": True}
        if machine.transport == "ssh-docker":
            check["worker_image"] = self.worker_image
        return {
            "scope": campaign.gpu_scope(image),
            "remote_scope": remote_scope(
                campaign.key.challenge_id, image, machine.transport
            ),
            "check": check,
        }

    def send_worker(self, manifest, machine, image_id):
        self.sent.append((machine.destination, machine.port, image_id))
        return "sent"


def setup_with(tmp_path, checks):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    home = tmp_path / "miner"
    home.mkdir(mode=0o700)
    for name in ("worker.json", "analysis.json", "operator.json", "gpu.json"):
        (home / name).write_text("{}")
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
    request = {
        "choice": REMOTE,
        "image_manifest": str(home / "worker.json"),
        "analysis_image_manifest": str(home / "analysis.json"),
        "gpu_image_manifest": str(home / "gpu.json"),
        "challenge": BATTERY_REF,
    }
    return setup, home, request


def consent(machine=MACHINE, image=None):
    send = {
        "destination": machine["destination"],
        "image": image or gpu_image().image_id,
    }
    if "port" in machine:
        send["port"] = machine["port"]
    return {"send": send}


# --- what setup offers ---------------------------------------------------------------


def test_setup_offers_the_miners_own_remote_machine_or_container():
    offered = {c["id"]: c for c in choices()["compute"]}
    remote = offered[REMOTE]
    assert remote["default"] is False and remote["needs_remote"] is True
    assert remote["needs_gpu_image"] is True and "speed only" in remote["note"]
    assert "never starts, stops or" in remote["cost_basis"]
    assert remote["guide"] == "docs/development/MINER_REMOTE_SETUP.md"
    assert [c["id"] for c in remote["for_challenges"]] == [BATTERY_CHALLENGE]
    transports = {t["id"]: t for t in remote["transports"]}
    assert [t["id"] for t in remote["transports"]] == [
        "ssh-docker",
        "ssh-container",
        "endpoint",
    ]
    assert (
        transports["ssh-docker"]["available"]
        and transports["ssh-docker"]["send_worker"]
    )
    assert transports["ssh-container"]["available"]
    assert not transports["ssh-container"]["send_worker"]
    assert transports["endpoint"] == {
        "id": "endpoint",
        "available": False,
        "display_name": "A job endpoint you expose",
        "reason": "endpoint_transport_not_built",
        "next_step": transports["endpoint"]["next_step"],
    }
    # Nothing asks for a provider key or a sudo password.
    text = json.dumps(remote).lower()
    assert "password" not in text and "api key" not in text


# --- the setup flow -------------------------------------------------------------------


def test_an_ssh_docker_machine_is_checked_sent_its_worker_and_profiled(tmp_path):
    checks = RemoteChecks()
    setup, home, request = setup_with(tmp_path, checks)
    state = setup.compute({**request, "remote": MACHINE})
    compute = state["steps"]["compute"]
    assert compute["choice"] == REMOTE and compute["remote_machine"] == MACHINE
    check = compute["check"]
    assert check["remote"]["worker_image"] == "missing"
    assert check["next_step"] == "send your worker"
    assert "speed only" in check["note"]
    # Consent is to the exact destination and image; nothing else sends.
    for refused in (
        True,
        {"send": True},
        consent({"destination": "other@box", "port": 2222}),
        consent(image="sha256:" + "8" * 64),
        consent({"destination": "miner@gpu-box"}),
    ):
        with pytest.raises(SetupRefused) as no:
            setup.send_worker({"consent": refused})
        assert no.value.field == "consent"
    assert checks.sent == []
    state = setup.send_worker({"consent": consent()})
    assert checks.sent == [("miner@gpu-box", 2222, gpu_image().image_id)]
    check = state["steps"]["compute"]["check"]
    assert check["remote"]["worker_image"] == "present" and check["worker"] == "sent"
    assert "next_step" not in check
    setup.agent({"choice": GRAPHITE, "operator_config": str(home / "operator.json")})
    setup.review({"confirm": True})
    cfg = runner.validated_profile(json.loads(setup.profile_path.read_bytes()))
    assert cfg["remote_machine"] == MACHINE
    assert cfg["gpu_image"] == str(home / "gpu.json")
    assert cfg["runtime"]["gpu_research"] == [gpu.gpu_scope(gpu_image())]
    assert cfg["runtime"]["remote_gpu"] == [
        remote_scope(BATTERY_CHALLENGE, gpu_image(), "ssh-docker")
    ]
    # The destination is the profile's, never the runtime a campaign freezes.
    assert "gpu-box" not in json.dumps(cfg["runtime"])
    # The prelaunch review says where practice runs, without the address.
    from scripts.dev.miner_launchpad.prelaunch import review

    execution = review(cfg)["execution"]
    assert execution["backend"] == "cuda"
    assert execution["remote"]["transport"] == "ssh-docker"
    assert "gpu-box" not in json.dumps(review(cfg))


def test_a_container_setup_has_no_send_step(tmp_path):
    checks = RemoteChecks()
    setup, _, request = setup_with(tmp_path, checks)
    state = setup.compute({**request, "remote": POD})
    check = state["steps"]["compute"]["check"]
    assert "next_step" not in check
    assert state["steps"]["compute"]["remote_machine"] == POD
    with pytest.raises(SetupRefused) as refused:
        setup.send_worker({"consent": consent(POD)})
    assert (refused.value.field, refused.value.code) == (
        "transport",
        "send_worker_is_for_ssh_docker",
    )
    assert checks.sent == []


def test_sending_needs_a_checked_remote_step(tmp_path):
    setup, _, _ = setup_with(tmp_path, RemoteChecks())
    with pytest.raises(SetupRefused) as refused:
        setup.send_worker({"consent": consent()})
    assert (refused.value.field, refused.value.code) == ("compute", "step_not_checked")


@pytest.mark.parametrize(
    "remote,field,code",
    [
        (
            {"transport": "endpoint", "destination": "https://x.example/job"},
            "transport",
            "endpoint_transport_not_built",
        ),
        ({"transport": "rented-gpu", "destination": "gpu-box"}, "transport", None),
        (
            {"transport": "ssh-docker", "destination": "-oProxyCommand=x"},
            "destination",
            None,
        ),
        (
            {"transport": "ssh-docker", "destination": "gpu-box", "port": 0},
            "port",
            None,
        ),
        ({"transport": "ssh-docker"}, "destination", "field_required"),
        (
            {"transport": "ssh-docker", "destination": "gpu-box", "key": "/k"},
            "key",
            "unknown_field",
        ),
    ],
)
def test_a_remote_setup_that_cannot_run_is_refused_by_field(
    tmp_path, remote, field, code
):
    checks = RemoteChecks()
    setup, _, request = setup_with(tmp_path, checks)
    with pytest.raises(SetupRefused) as refused:
        setup.compute({**request, "remote": remote})
    assert refused.value.field == field
    if code is not None:
        assert refused.value.code == code
    assert not [c for c in checks.calls if c[0] == "remote"]


def test_the_remote_choice_needs_its_setup_and_no_other_choice_takes_one(tmp_path):
    setup, _, request = setup_with(tmp_path, RemoteChecks())
    with pytest.raises(SetupRefused) as refused:
        setup.compute(request)
    assert (refused.value.field, refused.value.code) == ("remote", "field_required")
    cpu = {
        k: v for k, v in request.items() if k not in ("gpu_image_manifest", "challenge")
    }
    with pytest.raises(SetupRefused) as refused:
        setup.compute({**cpu, "choice": "this-machine-cpu", "remote": MACHINE})
    assert (refused.value.field, refused.value.code) == (
        "remote",
        "remote_is_for_the_remote_choice",
    )


# --- the live check, with the miner's own SSH ---------------------------------------------


class Machine:
    """A fixture ssh client: answers each script with a fixed status."""

    def __init__(self, destination, *, port=None, status=0):
        self.reached = (destination, port)
        self.status = status
        self.scripts = []

    def run(self, script, *, timeout):
        self.scripts.append(script)
        return self.status, b""


def live(tmp_path, status=0):
    manifest = tmp_path / "gpu.json"
    manifest.write_bytes(record_bytes(gpu_image()))
    clients = []

    def ssh(destination, *, port=None):
        client = Machine(destination, port=port, status=status)
        clients.append(client)
        return client

    return LiveChecks(ssh=ssh), manifest, clients


def campaign():
    from carbon.challenge_registry.campaigns import campaign_for

    return campaign_for(BATTERY_REF)


def test_the_live_check_reaches_the_machine_and_starts_nothing(tmp_path):
    from carbon.compute.remote_transport import RemoteMachine

    checks, manifest, clients = live(tmp_path)
    found = checks.remote(manifest, RemoteMachine(**MACHINE), campaign())
    assert found["check"]["worker_image"] == "present"
    assert found["remote_scope"] == remote_scope(
        BATTERY_CHALLENGE, gpu_image(), "ssh-docker"
    )
    ((script,),) = [c.scripts for c in clients]
    assert "docker run" not in script and "docker info" in script
    assert clients[0].reached == ("miner@gpu-box", 2222)


@pytest.mark.parametrize(
    "status,field,code",
    [
        (rm.SSH_FAILED, "destination", "ssh_unreachable"),
        (rm.TIMED_OUT, "destination", "ssh_timed_out"),
        (rm.NO_DOCKER_ACCESS, "remote", "no_docker_access"),
        (rm.NO_NVIDIA_TOOLKIT, "remote", "no_nvidia_container_toolkit"),
    ],
)
def test_a_live_check_refusal_names_its_field_and_next_step(
    tmp_path, status, field, code
):
    from carbon.compute.remote_transport import RemoteMachine

    checks, manifest, _ = live(tmp_path, status)
    with pytest.raises(SetupRefused) as refused:
        checks.remote(manifest, RemoteMachine(**MACHINE), campaign())
    assert (refused.value.field, refused.value.code) == (field, code)
    assert refused.value.next_step


def test_the_live_check_needs_the_pinned_gpu_worker(tmp_path):
    from carbon.compute.remote_transport import RemoteMachine

    checks, _, clients = live(tmp_path)
    cpu = tmp_path / "cpu.json"
    cpu.write_bytes(record_bytes(gpu_image(lock="sha256:" + "c" * 64)))
    with pytest.raises(SetupRefused) as refused:
        checks.remote(cpu, RemoteMachine(**POD), campaign())
    assert (refused.value.field, refused.value.code) == (
        "gpu_image_manifest",
        "gpu_image_unverified",
    )
    assert clients == []
    # Sending refuses an image rebuilt since the check.
    manifest = tmp_path / "gpu.json"
    with pytest.raises(SetupRefused) as refused:
        checks.send_worker(manifest, RemoteMachine(**MACHINE), "sha256:" + "8" * 64)
    assert refused.value.code == "gpu_image_changed_since_the_check"


# --- the profile ---------------------------------------------------------------------


def profile(tmp_path, runtime, **extra):
    from test_miner_launchpad_environment_setup import REVISION, RUNTIME

    paths = {
        name: str(tmp_path / name)
        for name in (
            "image_manifest",
            "analysis_image_manifest",
            "api_key_file",
            "miner_public",
            "quarantine_journal",
            "miner_network",
        )
    }
    return {
        "schema": runner.PROFILE_SCHEMA,
        "profile_id": "p",
        "principal": HOTKEY,
        "enabled": True,
        "paths": paths,
        "accepted_revision": REVISION,
        "campaigns_root": str(tmp_path / "campaigns"),
        "runtime": {**RUNTIME, **runtime},
        **extra,
    }


def remote_runtime(transport="ssh-docker"):
    return {
        "gpu_research": [gpu.gpu_scope(gpu_image())],
        "remote_gpu": [remote_scope(BATTERY_CHALLENGE, gpu_image(), transport)],
    }


def test_a_profile_declares_remote_practice_with_its_machine_and_only_then(tmp_path):
    good = profile(
        tmp_path, remote_runtime(), gpu_image="/g.json", remote_machine=MACHINE
    )
    assert runner.validated_profile(good)["remote_machine"] == MACHINE
    for bad in (
        profile(tmp_path, remote_runtime(), gpu_image="/g.json"),
        profile(
            tmp_path,
            {"gpu_research": [gpu.gpu_scope(gpu_image())]},
            gpu_image="/g.json",
            remote_machine=MACHINE,
        ),
        profile(
            tmp_path,
            remote_runtime(),
            gpu_image="/g.json",
            remote_machine={**MACHINE, "identity_file": "/k"},
        ),
    ):
        with pytest.raises(ValueError):
            runner.validated_profile(bad)
    with pytest.raises(Rejected) as refused:
        runner.validated_profile(
            profile(
                tmp_path,
                remote_runtime(),
                gpu_image="/g.json",
                remote_machine={"transport": "endpoint", "destination": "x"},
            )
        )
    assert refused.value.code == "endpoint_transport_not_built"


def test_the_runner_reads_remote_practice_from_the_profile(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    cfg = profile(
        tmp_path,
        remote_runtime("ssh-container"),
        gpu_image="/g.json",
        remote_machine=POD,
    )
    path = tmp_path / "profile.json"
    path.write_bytes(canonical(cfg))
    path.chmod(0o600)
    adapter = runner.RunnerAdapter(
        tmp_path / "runs.sqlite3",
        configuration=path,
        registration=lambda cfg: None,
    )
    assert adapter.configured()["runtime"]["remote_gpu"][0]["transport"] == (
        "ssh-container"
    )
    assert adapter.preflight()["compute"] == "remote-gpu:ssh-container"
    args = runner.campaign_args(cfg, root=tmp_path)
    assert args.remote_machine == POD
    # A remote scope that is not exactly the route's is refused before launch.
    broken = json.loads(path.read_text())
    broken["runtime"]["remote_gpu"][0]["official_eligible"] = True
    path.write_bytes(canonical(broken))
    with pytest.raises(Rejected) as refused:
        adapter.configured()
    assert refused.value.code == "research_runtime_interface_unavailable"


# --- the campaign doors -------------------------------------------------------------


def prepare(fixture, command, declared=None, machine=None):
    """`prepare_battery` with the host fixture, and the profile's machine."""
    public = fixture.root.parent / "miner-public.json"
    args = SimpleNamespace(
        root=fixture.root,
        command=command,
        accepted_revision="fixture",
        image_manifest=public,
        analysis_image_manifest=public,
        operator_config=public,
        miner_public=public,
        agent_policy=None,
        remote_machine=machine,
        **({} if declared is None else {"product": launch(declared)}),
    )
    return asyncio.run(
        battery.prepare_battery(
            args, ledger=CampaignLedger(fixture.root), campaign=None
        )
    )


def with_remote(image, transport="ssh-container"):
    return {
        **with_gpu(image),
        "remote_gpu": [remote_scope(BATTERY_CHALLENGE, image, transport)],
    }


def test_a_battery_campaign_freezes_remote_practice_and_composes_its_runner(
    gpu_host,  # noqa: F811 - the fixture above
):
    image = gpu_image()
    install(gpu_host.root, image)
    prepare(gpu_host, "run", with_remote(image), machine=POD)
    frozen = json.loads((gpu_host.root / "campaign-manifest.json").read_bytes())
    assert frozen["runtime"] == with_remote(image)
    assert "pod-1" not in json.dumps(frozen)
    remote = gpu_host.composed[-1]["remote"]
    assert isinstance(remote, RemoteRunner)
    assert isinstance(remote.transport, SSHContainer)
    assert remote.transport.ssh.destination == "root@pod-1"
    assert remote.worker.environment == (("JAX_PLATFORMS", "cuda"),)
    # A resume reads the machine from the profile again: a new address works.
    prepare(gpu_host, "resume", machine={**POD, "destination": "root@pod-2"})
    assert gpu_host.composed[-1]["remote"].transport.ssh.destination == "root@pod-2"
    # Another transport, or no machine, is refused before anything is reached.
    with pytest.raises(ValueError, match="another transport"):
        prepare(gpu_host, "resume", machine=MACHINE)
    with pytest.raises(ValueError, match="remote_machine"):
        prepare(gpu_host, "resume", machine=None)


def test_a_gpu_campaign_without_remote_practice_composes_none(
    gpu_host,  # noqa: F811 - the fixture above
):
    image = gpu_image()
    install(gpu_host.root, image)
    prepare(gpu_host, "run", with_gpu(image), machine=POD)
    assert gpu_host.composed[-1]["remote"] is None


def test_an_attach_re_checks_the_frozen_remote_scope():
    from test_battery_research_images import IMAGES, IMPLEMENTATION, frozen_manifest

    image = gpu_image()
    manifest = frozen_manifest(with_remote(image))
    battery.check_attached(
        manifest, implementation=IMPLEMENTATION, images=IMAGES, gpu_image=image
    )
    changed = frozen_manifest(with_remote(image))
    changed["runtime"]["remote_gpu"][0]["image_verified_by"] = "image-id"
    with pytest.raises(ValueError):
        battery.check_attached(
            changed, implementation=IMPLEMENTATION, images=IMAGES, gpu_image=image
        )


def test_the_standard_cli_door_builds_the_runner_from_the_profile(tmp_path):
    from carbon.miner_mcp import standard_cli

    tmp_path.chmod(0o700)
    install(tmp_path, gpu_image())
    manifest = {
        "challenge": BATTERY_REF,
        "runtime": with_remote(gpu_image(), "ssh-docker"),
    }

    def loaded(machine):
        return standard_cli.OperatorProfile(
            tmp_path / "p.json",
            {"remote_machine": machine} if machine else {},
            "c" * 32,
            tmp_path,
            manifest,
        )

    built = standard_cli._remote(loaded(MACHINE))
    assert isinstance(built.transport, SSHDocker)
    assert built.transport.ssh.destination == "miner@gpu-box"
    with pytest.raises(ValueError, match="another transport"):
        standard_cli._remote(loaded(POD))
    manifest["runtime"] = with_gpu(gpu_image())
    assert standard_cli._remote(loaded(None)) is None
