"""Setup's "Build the GPU worker" action, from the Control Center page (S15a).

The owner, 2026-10-21: "whatever makes it easiest for miners". A GPU route
with no GPU worker manifest offers one button. It runs the installer's own
GPU build on the miner's machine, as a background job. These tests drive the
real `GpuWorkerBuild`, the real controller and setup, with a fixture runner
and a fixture host probe. No Docker runs and nothing is built. What is held:
- a GPU route with no manifest is offered the build; one with a manifest is not;
- the build runs `install_miner.sh`'s exact GPU build call, on consent to that
  command, one at a time, and its status shows progress;
- it refuses, before anything runs, with no Docker, no NVIDIA driver (this
  machine's GPU route) or too little disk, and an ended build names why;
- once built, setup finds the manifest and the compute check reads it;
- only the page's door starts it: no setup operation, MCP tool, status call
  or agent door can.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import sys
import threading
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from scripts.dev.miner_launchpad import gpu_worker_build as gwb

TOKEN = "t" * 40
MANIFEST = ".carbon-artifacts/accelerator-worker-image.json"


class Probe:
    """A fixture host: what `HostProbe` would read, as each test sets it."""

    def __init__(self, *, docker=True, reachable=True, driver=True, free=100):
        self.docker, self.reachable, self.driver, self.free = (
            docker,
            reachable,
            driver,
            free,
        )
        self.root = "/var/lib/docker"

    def which(self, name):
        found = {"docker": self.docker, "nvidia-smi": self.driver}[name]
        return "/usr/bin/" + name if found else None

    def docker_reachable(self):
        return self.reachable

    def docker_root(self):
        return self.root

    def free_gib(self, path):
        assert path == self.root
        return self.free


class Process:
    def __init__(self, code, gate=None):
        self.code, self.gate = code, gate

    def wait(self):
        if self.gate is not None:
            self.gate.wait(10)
        return self.code


class Runner:
    """A fixture build: records the call, writes output, and writes the
    manifest on success, as the script does."""

    def __init__(self, *, code=0, output=b"", manifest=True, gate=None):
        self.code, self.output, self.manifest, self.gate = code, output, manifest, gate
        self.calls = []

    def __call__(self, command, *, cwd, log_fd, lock_fd):
        self.calls.append((list(command), cwd))
        os.write(log_fd, self.output)
        if self.code == 0 and self.manifest:
            path = Path(command[1])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"image_id": "sha256:" + "e" * 64}))
        return Process(self.code, self.gate)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "checkout"
    (root / "scripts/dev").mkdir(parents=True)
    return root


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    return root


def build(state, repo, **kwargs):
    runner = kwargs.pop("runner", None) or Runner()
    probe = kwargs.pop("probe", None) or Probe()
    action = gwb.GpuWorkerBuild(state, repo=repo, probe=probe, runner=runner)
    return action, runner, probe


def consent(action, route="remote-machine"):
    return {"route": route, "consent": {"build": {"command": action.command_text()}}}


def finished(action):
    if action.thread is not None:
        action.thread.join(10)
    return action.status()


# --- the offer and the command ----------------------------------------------------


def test_a_gpu_route_with_no_manifest_is_offered_the_installers_build(state, repo):
    action, _, _ = build(state, repo)
    offer = action.status()
    assert offer["offered"] is True and offer["state"] == "idle"
    assert offer["routes"] == ["this-machine-gpu", "remote-machine"]
    assert offer["driver_needed_for"] == ["this-machine-gpu"]
    # The command is the installer's own GPU build call, with this checkout's
    # paths: its script, and the manifest it writes where setup looks.
    assert action.command() == [
        str(repo / "scripts/dev/accelerator_worker_image.sh"),
        str(repo / MANIFEST),
    ]
    installer = (REPOSITORY / "scripts/install_miner.sh").read_text()
    assert 'artifacts="${repo_root}/.carbon-artifacts"' in installer
    assert (
        './scripts/dev/accelerator_worker_image.sh "${artifacts}/'
        'accelerator-worker-image.json"' in installer
    )
    from scripts.dev.miner_launchpad.installed import GPU_DEFAULT

    assert GPU_DEFAULT == MANIFEST
    # The disk it asks for is the installer's GPU reserve.
    assert re.search(r"^GPU_GIB=(\d+)$", installer, re.MULTILINE).group(1) == str(
        gwb.GPU_BUILD_GIB
    )
    # With a manifest there, nothing is offered.
    (repo / MANIFEST).parent.mkdir(parents=True)
    (repo / MANIFEST).write_text("{}")
    assert action.status()["offered"] is False


def test_the_build_runs_on_consent_in_the_background_and_shows_progress(state, repo):
    gate = threading.Event()
    runner = Runner(
        output=b"#7 [ 3/12] RUN pip install\n#8 [ 4/12] COPY <b>x</b>\n", gate=gate
    )
    action, _, _ = build(state, repo, runner=runner)
    started = action.start(consent(action))
    assert runner.calls == [(action.command(), str(repo))]
    assert started["state"] == "running" and started["offered"] is False
    assert started["step"] == "4/12"
    # Plain text, the last line as written.
    assert started["last_line"] == "#8 [ 4/12] COPY <b>x</b>"
    # One at a time.
    with pytest.raises(Exception) as refused:
        action.start(consent(action))
    assert refused.value.code == "gpu_build_running"
    assert len(runner.calls) == 1
    gate.set()
    done = finished(action)
    assert done["state"] == "built" and "outcome" not in done
    assert done["offered"] is False


@pytest.mark.parametrize(
    "request_value,code",
    [
        ({"route": "remote-machine"}, "closed_setup_request_required"),
        (
            {"route": "this-machine-cpu", "consent": None},
            "gpu_build_is_for_a_gpu_route",
        ),
        (
            {"route": "remote-machine", "consent": {"build": {"command": "rm -rf /"}}},
            "consent_must_name_the_command",
        ),
        ({"route": "remote-machine", "consent": True}, "consent_must_name_the_command"),
    ],
)
def test_only_consent_to_the_exact_command_starts_it(state, repo, request_value, code):
    action, runner, _ = build(state, repo)
    with pytest.raises(Exception) as refused:
        action.start(request_value)
    assert refused.value.code == code and refused.value.next_step
    assert runner.calls == []


# --- refusals name the exact failure --------------------------------------------------


@pytest.mark.parametrize(
    "probe,route,field,code",
    [
        (Probe(docker=False), "remote-machine", "docker", "docker_not_installed"),
        (Probe(reachable=False), "remote-machine", "docker", "docker_unreachable"),
        (Probe(driver=False), "this-machine-gpu", "gpu", "nvidia_driver_not_found"),
        (Probe(free=5), "remote-machine", "disk", "gpu_build_disk_full"),
    ],
)
def test_it_refuses_before_anything_runs(state, repo, probe, route, field, code):
    action, runner, _ = build(state, repo, probe=probe)
    with pytest.raises(Exception) as refused:
        action.start(consent(action, route))
    assert (refused.value.field, refused.value.code) == (field, code)
    assert refused.value.next_step
    assert runner.calls == [] and action.status()["state"] == "idle"
    if code == "gpu_build_disk_full":
        assert "needs 12 GiB free" in refused.value.next_step
        assert "5 GiB are free" in refused.value.next_step
        assert "docker system df" in refused.value.next_step


def test_a_remote_route_needs_no_gpu_on_this_machine(state, repo):
    """The script builds images only; the installer's driver check is for
    this machine's GPU (`--gpu`)."""
    action, runner, _ = build(state, repo, probe=Probe(driver=False))
    action.start(consent(action, "remote-machine"))
    assert finished(action)["state"] == "built" and len(runner.calls) == 1


def test_an_already_built_worker_is_not_built_again(state, repo):
    action, runner, _ = build(state, repo)
    (repo / MANIFEST).parent.mkdir(parents=True)
    (repo / MANIFEST).write_text("{}")
    with pytest.raises(Exception) as refused:
        action.start(consent(action))
    assert refused.value.code == "gpu_worker_already_built"
    assert runner.calls == []


@pytest.mark.parametrize(
    "output,code",
    [
        (b"write /var/lib/docker/x: no space left on device\n", "gpu_build_disk_full"),
        (
            b"Cannot connect to the Docker daemon at unix:///var/run/docker.sock\n",
            "docker_unreachable",
        ),
        (b"ERROR: failed to solve\n", "gpu_build_failed"),
    ],
)
def test_an_ended_build_names_why(state, repo, output, code):
    action, _, _ = build(state, repo, runner=Runner(code=1, output=output))
    action.start(consent(action))
    done = finished(action)
    assert done["state"] == "failed"
    assert done["outcome"]["code"] == code and done["outcome"]["exit_code"] == 1
    assert done["outcome"]["next_step"]
    # A failed build can be started again.
    assert done["offered"] is True


def test_a_build_that_wrote_no_manifest_is_not_built(state, repo):
    action, _, _ = build(state, repo, runner=Runner(manifest=False))
    action.start(consent(action))
    done = finished(action)
    assert done["state"] == "failed"
    assert done["outcome"]["code"] == "gpu_build_wrote_no_manifest"


def test_a_build_the_controller_lost_reads_as_interrupted(state, repo):
    """A Control Center restart forgets its watcher; the record says it."""
    action, _, _ = build(state, repo, runner=Runner(manifest=False))
    action.start(consent(action))
    finished(action)
    record = json.loads((state / "environment" / gwb.RECORD).read_text())
    for key in ("finished_at", "exit_code", "outcome"):
        record.pop(key)
    (state / "environment" / gwb.RECORD).write_text(json.dumps(record))
    later = gwb.GpuWorkerBuild(state, repo=repo, probe=Probe(), runner=Runner())
    status = later.status()
    assert status["state"] == "interrupted"
    assert status["outcome"]["code"] == "gpu_build_interrupted"


# --- once built, the compute check reads it ------------------------------------------


def test_once_built_setup_finds_the_manifest_and_compute_checks_it(
    tmp_path, repo, monkeypatch
):
    from test_miner_remote_setup import MACHINE, RemoteChecks, setup_with

    from scripts.dev.miner_launchpad import environment_setup

    monkeypatch.setattr(environment_setup, "REPO", repo)
    checks = RemoteChecks()
    setup, _, request = setup_with(tmp_path, checks)
    images = setup.state()["images"]["gpu_image_manifest"]
    assert images["path"] is None
    action, _, _ = build(setup.root.parent, repo)
    action.start(consent(action))
    assert finished(action)["state"] == "built"
    found = setup.state()["images"]["gpu_image_manifest"]
    assert found == {
        "path": str(repo / MANIFEST),
        "found_by": "accelerator_worker_image.sh",
        "build": found["build"],
    }
    setup.compute({**request, "gpu_image_manifest": found["path"], "remote": MACHINE})
    assert ("remote", str(repo / MANIFEST), MACHINE) in checks.calls


# --- only the page's door ---------------------------------------------------------------


def test_no_setup_operation_mcp_tool_or_status_call_can_start_it(tmp_path, state):
    from test_miner_launchpad_environment_setup import Checks, Onboarding

    from scripts.dev.miner_launchpad import operations, setup_operations
    from scripts.dev.miner_launchpad.environment_setup import EnvironmentSetup

    names = set(setup_operations.SETUP_OPERATIONS)
    # `test_gpu` (OWNER-TEST-MY-GPU-01) is the miner's consent-gated per-framework
    # GPU check, not a build: it runs one synthetic matmul and builds nothing.
    assert {n for n in names if "build" in n or "gpu" in n} == {"test_gpu"}
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    # `perform` calls setup's method of the operation's name: there is none.
    assert not any(hasattr(setup, n) for n in ("gpu_worker_build", "build_gpu_worker"))
    with pytest.raises(KeyError):
        setup_operations.perform(setup, "gpu_worker_build", {}, door="mcp")
    # Neither door's status names it, nor the operations table.
    for door in (setup_operations.MCP, setup_operations.HTTP):
        text = json.dumps(setup_operations.status(setup, door=door))
        assert "gpu_worker_build" not in text and "gpu_build" not in text
    assert "gpu_worker_build" not in json.dumps(operations.describe())
    # Only the page's controller holds it: no MCP door, tool door or agent
    # module imports it.
    imports = re.compile(r"gpu_worker_build import|import gpu_worker_build")
    importers = sorted(
        path.relative_to(REPOSITORY).as_posix()
        for root in ("carbon", "scripts")
        for path in (REPOSITORY / root).rglob("*.py")
        if imports.search(path.read_text(encoding="utf-8", errors="ignore"))
    )
    assert importers == ["scripts/dev/miner_launchpad/controller.py"]


def test_no_mcp_setup_tool_builds(state):
    pytest.importorskip("mcp")
    from test_miner_launchpad_environment_setup import Checks, Onboarding

    from carbon.miner_mcp.mcp_setup import make_setup_tools
    from scripts.dev.miner_launchpad.environment_setup import EnvironmentSetup
    from scripts.dev.miner_launchpad.setup_operations import OPEN, REGISTERED

    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    tools = [
        tool.name
        for tier in (OPEN, REGISTERED)
        for tool in make_setup_tools(setup, tier=tier)
    ]
    assert tools and not [n for n in tools if "build" in n]


@pytest.fixture
def server(tmp_path, state, repo):
    from test_miner_launchpad_environment_setup import Checks, Onboarding

    from scripts.dev.miner_launchpad import controller as launchpad

    action, runner, _ = build(state, repo)
    served = launchpad.Server(
        launchpad.Controller(tmp_path / "runs.sqlite3"),
        TOKEN,
        port=0,
        onboarding=Onboarding(),
        state_dir=state,
        setup_checks=Checks(),
        gpu_build=action,
    )
    served.runner_calls = runner.calls
    thread = threading.Thread(target=served.serve_forever, daemon=True)
    thread.start()
    yield served
    served.shutdown()


def call(server, method, path, body=None, token=TOKEN):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
    headers = {"Host": server.authority}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=data, headers=headers)
    response = connection.getresponse()
    return response.status, json.loads(response.read())


def test_the_page_door_offers_starts_and_reports_it(server):
    from scripts.dev.miner_launchpad.controller import GPU_BUILD_ROUTE

    status, document = call(server, "GET", "/api/v1/setup")
    assert status == 200 and document["gpu_build"]["offered"] is True
    command = document["gpu_build"]["command"]
    # The setup steps' route has no such step, and the status route (the
    # agent's loop) does not carry it.
    status, body = call(server, "POST", "/api/v1/setup/gpu_worker_build", {"x": 1})
    assert (status, body["error"]) == (404, "unknown_setup_step")
    status, body = call(server, "GET", "/api/v1/setup/status")
    assert status == 200 and "gpu_build" not in json.dumps(body)
    request = {"route": "remote-machine", "consent": {"build": {"command": command}}}
    # The page's session token is required.
    status, body = call(server, "POST", GPU_BUILD_ROUTE, request, token=None)
    assert (status, body["error"]) == (401, "authentication_required")
    status, body = call(
        server, "POST", GPU_BUILD_ROUTE, {**request, "consent": {"build": {}}}
    )
    assert (status, body["error"], body["field"]) == (
        409,
        "consent_must_name_the_command",
        "consent",
    )
    assert body["next_step"]
    assert server.runner_calls == []
    status, body = call(server, "POST", GPU_BUILD_ROUTE, request)
    assert status == 200 and body["state"] in ("running", "built")
    assert server.runner_calls == [
        (server.gpu_build.command(), str(server.gpu_build.repo))
    ]
    server.gpu_build.thread.join(10)
    status, document = call(server, "GET", "/api/v1/setup")
    assert document["gpu_build"]["state"] == "built"
    assert document["gpu_build"]["offered"] is False
