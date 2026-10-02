"""The miner's remote setup: one interface over every transport (LINKONLY-D5).

OWNER-MINER-COMPUTE-LINK-ONLY-01, as amended on 2026-10-02: the miner runs
any setup, and Carbon only connects to it. No SSH connection is made. The
`ssh-docker` scripts run in real bash with a fake `docker`; the
`ssh-container` scripts run in real bash with only a container's tools on
PATH, and start the real job server as a real process. What is held:
- the miner's choice is closed: two transports are built, `endpoint` is
  refused by name, and a destination can never be an option;
- both transports describe a trial with the same fields;
- setup's live check starts nothing: Docker, the toolkit, Docker without sudo
  and the image by ID on a machine; the worker runtime and its build identity
  in a container, any difference refused;
- a container job is one process in its own directory, on the container's
  loopback, its environment through a deleted file; stopping it stops only the
  processes whose environment names that directory, then removes it;
- the build identity Carbon reads is the one every worker image is built with.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import fields
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from remote_container_fixture import (
    LocalContainer,
    build_file,
    container,
    worker_python,
)

from carbon.compute import job_server, remote_container
from carbon.compute import remote_machine as rm
from carbon.compute.remote_job import RemoteJob
from carbon.compute.remote_machine import RemoteMachineError, published_port
from carbon.compute.remote_transport import (
    ENDPOINT_NOT_BUILT,
    SSH_CONTAINER,
    SSH_DOCKER,
    RemoteMachine,
    SSHContainer,
    SSHDocker,
    outcome,
    transport_for,
)
from carbon.reconstruction.worker.model import WorkerImageIdentity

NAME = "carbon-job-" + "0123456789abcdef01234567"
TOKEN = "f" * 64


def image(tag="9"):
    from test_battery_gpu_practice import gpu_image

    return gpu_image(tag)


@pytest.fixture(autouse=True)
def loopback_without_proxy(monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")


# --- the miner's choice -------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        {"transport": "ssh-docker", "destination": "miner@gpu-box"},
        {
            "transport": "ssh-container",
            "destination": "root@203.0.113.7",
            "port": 40122,
        },
        {"transport": "ssh-container", "destination": "my-pod"},
    ],
)
def test_a_remote_machine_is_a_transport_and_a_destination(value):
    machine = RemoteMachine.from_document(value)
    assert machine.document() == value


def test_the_endpoint_transport_is_refused_by_name():
    with pytest.raises(RemoteMachineError) as refused:
        RemoteMachine.from_document(
            {"transport": "endpoint", "destination": "https://x.example/job"}
        )
    assert refused.value.code == ENDPOINT_NOT_BUILT
    assert "ssh-container" in refused.value.next_step
    with pytest.raises(RemoteMachineError):
        RemoteMachine("endpoint", "gpu-box")


@pytest.mark.parametrize(
    "value",
    [
        None,
        {"transport": "ssh-docker"},
        {"transport": "rented-gpu", "destination": "gpu-box"},
        {"transport": "ssh-docker", "destination": "-oProxyCommand=x"},
        {"transport": "ssh-docker", "destination": "gpu-box", "port": "22"},
        {"transport": "ssh-docker", "destination": "gpu-box", "port": 0},
        {"transport": "ssh-docker", "destination": "gpu-box", "key": "/home/m/.ssh/id"},
    ],
)
def test_anything_else_is_refused(value):
    with pytest.raises(ValueError):
        RemoteMachine.from_document(value)


def test_each_transport_reaches_the_machine_with_the_miners_own_ssh():
    made = []

    class Client:
        def __init__(self, destination, *, port=None):
            made.append((destination, port))

    docker = transport_for(RemoteMachine(SSH_DOCKER, "gpu-box", 2222), ssh=Client)
    pod = transport_for(RemoteMachine(SSH_CONTAINER, "root@pod"), ssh=Client)
    assert isinstance(docker, SSHDocker) and isinstance(pod, SSHContainer)
    assert made == [("gpu-box", 2222), ("root@pod", None)]


def test_every_transport_records_the_same_fields():
    docker = SSHDocker(object()).describe(image())
    pod = SSHContainer(object()).describe(image())
    assert (
        set(docker)
        == set(pod)
        == {
            "transport",
            "image",
            "image_verified_by",
            "job_transport",
        }
    )
    assert (docker["image_verified_by"], pod["image_verified_by"]) == (
        "image-id",
        "build-identity",
    )
    assert docker["job_transport"] == pod["job_transport"] == "ssh-tunnel"
    assert outcome(pod, False) == {**pod, "cleanup": "unconfirmed"}


# --- ssh-docker: setup's live check -----------------------------------------------------


class LocalMachine:
    """`SSHClient.run` on this machine, with a fake docker on PATH."""

    def __init__(self, tmp_path, *, docker=True, toolkit=True, **env):
        from test_remote_machine import FAKE_DOCKER

        self.tools = tmp_path / "tools"
        self.tools.mkdir()
        if docker:
            (self.tools / "docker").write_text(FAKE_DOCKER)
            (self.tools / "docker").chmod(0o755)
        if toolkit:
            (self.tools / "nvidia-ctk").write_text("#!/bin/bash\nexit 0\n")
            (self.tools / "nvidia-ctk").chmod(0o755)
        self.env = {
            "PATH": str(self.tools),
            "CARBON_FAKE_LOG": str(tmp_path / "docker.log"),
            **env,
        }
        self.log = tmp_path / "docker.log"

    def run(self, script, *, timeout):
        completed = subprocess.run(
            ["/bin/bash", "-s"],
            input=script.encode(),
            env=self.env,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        return completed.returncode, completed.stdout


def test_the_machine_check_starts_nothing_and_reports_the_image(tmp_path):
    machine = LocalMachine(tmp_path, CARBON_FAKE_IMAGE=image().image_id)
    check = SSHDocker(machine).check(image())
    assert check == {
        "transport": "ssh-docker",
        "reached": True,
        "docker": "usable without sudo",
        "nvidia_container_toolkit": "present",
        "worker_image": "present",
        "image_verified_by": "image-id",
    }
    calls = machine.log.read_text().splitlines()
    assert not [c for c in calls if c.startswith(("run ", "rm ", "load", "pull"))]


def test_a_machine_without_the_image_is_told_to_send_it(tmp_path):
    check = SSHDocker(LocalMachine(tmp_path)).check(image())
    assert check["worker_image"] == "missing"


@pytest.mark.parametrize(
    "setup,code",
    [
        ({"docker": False}, "no_docker"),
        ({"toolkit": False}, "no_nvidia_container_toolkit"),
        ({"CARBON_FAKE_NO_ACCESS": "1"}, "no_docker_access"),
    ],
)
def test_a_machine_missing_a_prerequisite_is_refused_by_name(tmp_path, setup, code):
    with pytest.raises(RemoteMachineError) as refused:
        SSHDocker(LocalMachine(tmp_path, **setup)).check(image())
    assert refused.value.code == code


def test_an_unreachable_machine_is_named():
    class Unreachable:
        def run(self, script, *, timeout):
            return rm.SSH_FAILED, b""

    for transport in (SSHDocker(Unreachable()), SSHContainer(Unreachable())):
        with pytest.raises(RemoteMachineError) as refused:
            transport.check(image())
        assert refused.value.code == "ssh_unreachable"


# --- ssh-container: the worker's build identity -----------------------------------------------


def test_the_container_check_reads_the_pinned_build_identity(tmp_path):
    transport, ssh, _ = container(tmp_path, image())
    assert transport.check(image()) == {
        "transport": "ssh-container",
        "reached": True,
        "worker_runtime": "present",
        "build_identity": "matches the pinned GPU worker",
        "image_verified_by": "build-identity",
    }
    # One script ran, and it started nothing.
    (script,) = ssh.scripts
    assert "setsid" not in script and "mkdir" not in script


@pytest.mark.parametrize(
    "field", ["source_tree_digest", "wheel_digest", "lock_digest", "base_image_digest"]
)
def test_a_container_built_from_anything_else_is_refused(tmp_path, field):
    transport, _, _ = container(tmp_path, image(), **{field: "sha256:" + "7" * 64})
    with pytest.raises(RemoteMachineError) as refused:
        transport.check(image())
    assert refused.value.code == "worker_identity_mismatch"
    assert "push_worker_image.sh" in refused.value.next_step


def test_a_build_identity_with_extra_or_oversized_content_is_refused(tmp_path):
    transport, _, _ = container(tmp_path, image(), note="x")
    with pytest.raises(RemoteMachineError, match="worker_identity_mismatch"):
        transport.check(image())
    with pytest.raises(RemoteMachineError, match="worker_identity_mismatch"):
        remote_container.checked_identity(b"{" + b" " * 5000 + b"}", image())
    with pytest.raises(RemoteMachineError, match="worker_identity_mismatch"):
        remote_container.checked_identity(b"\xff", image())


def test_a_container_without_the_pinned_worker_is_told_to_start_from_it(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    transport = SSHContainer(
        LocalContainer(root),
        python=str(root / "no-python"),
        build_file=str(root / "no-build.json"),
    )
    with pytest.raises(RemoteMachineError) as refused:
        transport.check(image())
    assert refused.value.code == "no_worker_runtime"
    assert "pinned GPU worker image" in refused.value.next_step


# --- ssh-container: one job process -------------------------------------------------------------


def started(ssh, python, jobs, *, env=(("CARBON_JOB_TOKEN", TOKEN),), **options):
    script = remote_container.start_script(
        name=NAME,
        env=(
            *env,
            ("CARBON_JOB_SECONDS", "60"),
            ("CARBON_JOB_LIFETIME", "120"),
        ),
        command=(str(python), "-I", "-m", "carbon.compute.job_server"),
        root=str(jobs),
        **options,
    )
    return ssh.run(script, timeout=60)


def stopped(ssh, jobs, **options):
    code, _ = ssh.run(
        remote_container.stop_script(NAME, root=str(jobs), **options), timeout=60
    )
    return code


def job_pids(directory):
    """This machine's processes whose environment names the job directory."""
    marker = b"CARBON_JOB_ROOT=" + str(directory).encode()
    found = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                if marker in (entry / "environ").read_bytes().split(b"\0"):
                    found.append(int(entry.name))
            except OSError:
                continue
    return found


def test_a_job_process_serves_one_job_on_loopback_and_is_cleaned_up(tmp_path):
    _, ssh, python = container(tmp_path, image())
    jobs = tmp_path / "container" / "jobs"
    directory = jobs / NAME
    code, stdout = started(ssh, python, jobs)
    try:
        assert code == 0, stdout
        port = published_port(stdout)
        # Its directory is owner-only, and the environment file is gone.
        assert directory.stat().st_mode & 0o777 == 0o700
        assert not (directory / "env").exists()
        # The server listens on loopback only, in its own session.
        (pid,) = job_pids(directory)
        assert os.getsid(pid) == pid
        job = RemoteJob(f"http://127.0.0.1:{port}", TOKEN, sleep=lambda _: None)
        result, output = job.run(
            {"inputs.json": b"[1, 2]", "program.py": PROGRAM},
            ready_deadline=time.monotonic() + 30,
            run_deadline=time.monotonic() + 60,
        )
        assert result["state"] == "DONE"
        assert json.loads(output["predictions.json"]) == {"sum": 3}
    finally:
        assert stopped(ssh, jobs) == 0
    assert not directory.exists() and job_pids(directory) == []


PROGRAM = b"""
import json
from pathlib import Path
work = Path.cwd()
data = json.loads((work / "inputs.json").read_text())
(work.parent / "output" / "predictions.json").write_text(json.dumps({"sum": sum(data)}))
"""


def test_stopping_kills_a_process_that_ignores_the_request(tmp_path):
    _, ssh, _ = container(tmp_path, image())
    jobs = tmp_path / "container" / "jobs"
    stubborn = tmp_path / "stubborn"
    # A "server" that writes its port, then ignores SIGTERM.
    stubborn.write_text(
        "#!/bin/bash\ntrap '' TERM\necho 1 > \"$CARBON_JOB_PORT_FILE\"\n"
        "while :; do sleep 0.2; done\n"
    )
    stubborn.chmod(0o755)
    code, _ = started(ssh, stubborn, jobs)
    assert code == 0
    assert job_pids(jobs / NAME)
    assert stopped(ssh, jobs, grace_seconds=1) == 0
    assert job_pids(jobs / NAME) == [] and not (jobs / NAME).exists()


def test_stopping_leaves_every_other_process_alone(tmp_path):
    _, ssh, _ = container(tmp_path, image())
    jobs = tmp_path / "container" / "jobs"
    other = jobs / ("carbon-job-" + "f" * 24)
    bystander = subprocess.Popen(
        ["sleep", "30"], env={"CARBON_JOB_ROOT": str(other), "PATH": os.environ["PATH"]}
    )
    try:
        assert stopped(ssh, jobs) == 0
        assert bystander.poll() is None
    finally:
        bystander.send_signal(signal.SIGKILL)
        bystander.wait()


def test_a_job_whose_server_never_answers_is_refused_by_code(tmp_path):
    _, ssh, _ = container(tmp_path, image())
    jobs = tmp_path / "container" / "jobs"
    silent = tmp_path / "silent"
    silent.write_text("#!/bin/bash\nexec sleep 30\n")
    silent.chmod(0o755)
    code, _ = started(ssh, silent, jobs, wait_seconds=1)
    try:
        assert code == rm.JOB_SERVER_NOT_STARTED
        assert rm.failure_for(code).code == "job_server_not_started"
    finally:
        assert stopped(ssh, jobs) == 0


def test_an_existing_job_directory_is_never_reused(tmp_path):
    _, ssh, python = container(tmp_path, image())
    jobs = tmp_path / "container" / "jobs"
    (jobs / NAME).mkdir()
    code, _ = started(ssh, python, jobs)
    assert code == rm.JOB_DIRECTORY_PRESENT
    assert rm.failure_for(code).code == "job_directory_present"
    assert stopped(ssh, jobs) == 0


def test_a_container_without_the_workers_python_starts_nothing(tmp_path):
    _, ssh, _ = container(tmp_path, image())
    jobs = tmp_path / "container" / "jobs"
    code, _ = started(ssh, tmp_path / "absent", jobs)
    assert code == rm.NO_WORKER_RUNTIME and list(jobs.iterdir()) == []


def test_the_container_scripts_take_only_plain_values(tmp_path):
    command = ("/opt/carbon-worker/bin/python", "-I", "-m", "carbon.compute.job_server")
    with pytest.raises(ValueError, match="not plain"):
        remote_container.start_script(
            name=NAME, env=(("CARBON_JOB_TOKEN", "x; id"),), command=command
        )
    with pytest.raises(ValueError, match="where the job server listens"):
        remote_container.start_script(
            name=NAME, env=(("CARBON_JOB_BIND", "0.0.0.0"),), command=command
        )
    with pytest.raises(ValueError, match="carbon-job"):
        remote_container.stop_script("../../etc")
    with pytest.raises(ValueError, match="absolute path"):
        remote_container.job_directory(NAME, root="/tmp/../etc")
    with pytest.raises(ValueError, match="absolute path"):
        remote_container.identity_script(python="python; id")
    text = remote_container.start_script(
        name=NAME, env=(("CARBON_JOB_TOKEN", TOKEN),), command=command
    )
    assert "sudo" not in text
    for forbidden in ("apt", "curl", "wget", "pip", "install"):
        assert forbidden not in text
    # The token is written to the environment file, never into the command.
    assert TOKEN not in text.split("exec setsid", 1)[1]


# --- the job server's own side -----------------------------------------------------------


def test_the_job_server_binds_only_the_addresses_it_knows():
    with pytest.raises(ValueError, match="listens on"):
        job_server.serve(token=TOKEN, port=0, seconds=1, lifetime=1, bind="::")


def test_the_job_server_writes_its_port_whole(tmp_path):
    job_server.write_port(tmp_path / "port", 40123)
    assert (tmp_path / "port").read_text() == "40123\n"
    assert not (tmp_path / "port.staged").exists()


# --- the build identity every worker image carries ----------------------------------------------


def test_the_build_fields_are_the_pinned_manifest_without_its_image_id():
    manifest = {f.name for f in fields(WorkerImageIdentity)}
    assert set(remote_container.BUILD_FIELDS) == manifest - {
        "image_id",
        "config_digest",
    }


def test_every_worker_image_is_built_with_the_identity_carbon_reads():
    base = (REPOSITORY / ".devcontainer/Dockerfile.reconstruction-worker").read_text()
    written = re.search(r"printf '(\{\"schema\".*?\})\\n'", base).group(1)
    assert f'"schema":"{remote_container.BUILD_SCHEMA}"' in written
    for field in remote_container.BUILD_FIELDS:
        assert f'"{field}":' in written
    assert f"> {remote_container.BUILD_FILE}" in base
    # The GPU worker keeps that file, updating only its base, recipe and lock,
    # and its manifest is that file plus the image ID.
    gpu = (REPOSITORY / ".devcontainer/accelerators/Dockerfile").read_text()
    assert f'pathlib.Path("{remote_container.BUILD_FILE}")' in gpu
    updated = re.search(r"document\.update\((.*?)\)\n", gpu, re.DOTALL).group(1)
    assert set(re.findall(r"(\w+)=", updated)) == {
        "base_image_digest",
        "build_recipe_digest",
        "lock_digest",
    }
    script = (REPOSITORY / "scripts/dev/accelerator_worker_image.sh").read_text()
    assert f"{remote_container.BUILD_FILE}" in script
    assert '{**build, "schema": "carbon.c03.worker-image.v1"' in script


def test_a_build_file_from_the_pinned_manifest_matches_it(tmp_path):
    path = build_file(tmp_path, image())
    assert remote_container.checked_identity(path.read_bytes(), image())
    assert worker_python(tmp_path).stat().st_mode & 0o111
