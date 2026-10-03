"""The miner's own GPU machine over SSH (OWNER-MINER-COMPUTE-LINK-ONLY-01).

No SSH connection is made and no Docker daemon is used. A fake `ssh` runs
the remote side locally, and the start and remove scripts run in real bash
with a fake `docker` on PATH. What is held:
- the ssh command line leaves keys, known hosts and host trust to the
  miner's own SSH: no `-i`, no `IdentitiesOnly`, no Carbon known-hosts file,
  no `accept-new`; the destination can never be read as an option;
- `run` returns the exit status and a bounded standard output, and a timeout
  or a missing client is a status, not an exception;
- the start script starts one container by image ID with a per-job name,
  `--rm`, the GPUs and the job port on the machine's loopback only; the job's
  environment goes through a temporary file that is deleted; nothing uses
  sudo; and Docker, the toolkit, Docker access and the image are each
  refused by their own code (90 to 93);
- the remove script touches only Carbon's `carbon-job-<24 hex>` containers;
- the worker image is streamed with `docker save | ssh docker load` and
  checked by image ID.

The fakes log only under each test's `tmp_path` and refuse to run without
`CARBON_FAKE_LOG`, so the module leaves nothing in the repository.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from carbon.compute import remote_machine as rm
from carbon.compute.remote_machine import (
    RemoteMachineError,
    SSHClient,
    published_port,
    remove_script,
    send_image,
    start_script,
)

IMAGE = "sha256:" + "9" * 64
NAME = "carbon-job-" + "0123456789abcdef01234567"
TOKEN = "f" * 64
ENV = (
    ("CARBON_JOB_TOKEN", TOKEN),
    ("CARBON_JOB_PORT", "8000"),
    ("JAX_PLATFORMS", "cuda"),
)
COMMAND = ("/opt/carbon-worker/bin/python", "-I", "-m", "carbon.compute.job_server")
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The fakes' exit status when `CARBON_FAKE_LOG` is empty: without it their
#: logs would land in the working directory (`.ssh`, `.env`, ...).
NO_FAKE_LOG = 99

#: A fake `docker`: it logs each call and answers from the environment. It
#: uses bash builtins only, so the tests control everything on PATH.
FAKE_DOCKER = r"""#!/bin/bash
log="${CARBON_FAKE_LOG:-}"
if [ -z "$log" ]; then
  printf 'fake docker: CARBON_FAKE_LOG is empty; set it under tmp_path\n' >&2
  exit 99
fi
printf '%s\n' "$*" >> "$log"
case "$1" in
  info)
    [ -z "${CARBON_FAKE_NO_ACCESS:-}" ] || exit 1
    exit 0 ;;
  image)
    if [ "$5" = "${CARBON_FAKE_IMAGE:-}" ]; then printf '%s\n' "$5"; exit 0; fi
    if [ -f "$log.loaded" ]; then
      read -r loaded < "$log.loaded"
      if [ "$loaded" = "IMAGE-TAR-$5" ]; then printf '%s\n' "$5"; exit 0; fi
    fi
    exit 1 ;;
  run)
    previous=""
    for argument in "$@"; do
      if [ "$previous" = "--env-file" ]; then
        printf '%s\n' "$argument" > "$log.envpath"
        while IFS= read -r line; do printf '%s\n' "$line" >> "$log.env"; done < "$argument"
      fi
      previous="$argument"
    done
    printf '%s\n' 4f3c2b1a; exit 0 ;;
  port)
    printf '127.0.0.1:49153\n'; exit 0 ;;
  rm)
    printf '%s\n' "$3" >> "$log.removed"; exit 0 ;;
  container)
    [ -n "${CARBON_FAKE_STILL_THERE:-}" ] && exit 0
    exit 1 ;;
  save)
    printf 'IMAGE-TAR-%s' "$2"; exit 0 ;;
  load)
    content=""
    IFS= read -r content || true
    if [ -n "${CARBON_FAKE_CORRUPT:-}" ]; then content="IMAGE-TAR-other"; fi
    printf '%s\n' "$content" > "$log.loaded"; exit 0 ;;
esac
exit 0
"""

#: A fake `ssh`: it logs its options, drops `-- DEST` and runs the remote
#: command here. With `-N` it is a port forward and just waits.
FAKE_SSH = r"""#!/bin/bash
if [ -z "${CARBON_FAKE_LOG:-}" ]; then
  printf 'fake ssh: CARBON_FAKE_LOG is empty; set it under tmp_path\n' >&2
  exit 99
fi
for argument in "$@"; do printf '%s\n' "$argument" >> "$CARBON_FAKE_LOG.ssh"; done
forward=""
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do
  [ "$1" = "-N" ] && forward=1
  shift
done
shift 2
if [ -n "$forward" ]; then exec sleep 30; fi
exec "$@"
"""


def _executable(path: Path, body: str) -> Path:
    path.write_text(body)
    path.chmod(0o755)
    return path


def _logged(path: Path, last: str) -> list[str]:
    """The fake's logged argv, once it has written all of it."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        lines = path.read_text().splitlines() if path.exists() else []
        if lines and lines[-1] == last:
            return lines
        time.sleep(0.05)
    raise AssertionError("the fake ssh did not log its arguments")


def _entries(place: Path) -> dict[str, int | None]:
    """Each entry's name, with a regular file's modification time."""
    return {
        entry.name: (
            entry.stat(follow_symlinks=False).st_mtime_ns
            if entry.is_file(follow_symlinks=False)
            else None
        )
        for entry in os.scandir(place)
    }


@pytest.fixture(scope="module", autouse=True)
def nothing_left_in_the_repository():
    """After the module, no file is new or changed in the repository root, or
    in a working directory inside the repository: the stray `.ssh` an empty
    `CARBON_FAKE_LOG` once left there is caught here."""
    cwd = Path.cwd().resolve()
    places = {REPO_ROOT}
    if cwd == REPO_ROOT or REPO_ROOT in cwd.parents:
        places.add(cwd)
    before = {place: _entries(place) for place in places}
    yield
    for place in places:
        stray = sorted(
            name
            for name, mtime in _entries(place).items()
            if name not in before[place] or before[place][name] != mtime
        )
        assert not stray, f"the module left {stray} in {place}"


@pytest.fixture(autouse=True)
def fake_log_under_tmp_path(tmp_path, monkeypatch):
    """Every fake started from the test's own environment logs to
    `tmp_path/log` and its siblings (`log.ssh`, `log.loaded`, ...)."""
    monkeypatch.setenv("CARBON_FAKE_LOG", str(tmp_path / "log"))


@pytest.fixture
def machine(tmp_path):
    """A directory of tools for the scripts, and a log of what they did."""
    tools = tmp_path / "tools"
    tools.mkdir()
    for name in ("mktemp", "rm"):
        (tools / name).symlink_to(shutil.which(name))
    temporary = tmp_path / "tmp"
    temporary.mkdir()
    log = tmp_path / "docker.log"
    return {"tools": tools, "tmp": temporary, "log": log}


def bash(script, machine, *, docker=True, toolkit=True, **env):
    if docker:
        _executable(machine["tools"] / "docker", FAKE_DOCKER)
    if toolkit:
        _executable(machine["tools"] / "nvidia-ctk", "#!/bin/bash\nexit 0\n")
    return subprocess.run(
        ["/bin/bash", "-s"],
        input=script.encode(),
        env={
            "PATH": str(machine["tools"]),
            "TMPDIR": str(machine["tmp"]),
            "CARBON_FAKE_LOG": str(machine["log"]),
            **env,
        },
        capture_output=True,
        check=False,
        timeout=60,
    )


def calls(machine):
    log = machine["log"]
    return log.read_text().splitlines() if log.exists() else []


def script():
    return start_script(image_id=IMAGE, name=NAME, env=ENV, command=COMMAND)


# --- the ssh command line ------------------------------------------------------


def test_the_ssh_command_leaves_keys_and_host_trust_to_the_miners_ssh():
    argv = SSHClient("miner@gpu-box", port=2222).command()
    assert argv == [
        "ssh",
        "-p",
        "2222",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "ServerAliveInterval=15",
        "--",
        "miner@gpu-box",
    ]
    joined = " ".join(argv)
    assert "-i" not in argv
    for forbidden in (
        "IdentityFile",
        "IdentitiesOnly",
        "UserKnownHostsFile",
        "StrictHostKeyChecking",
        "accept-new",
    ):
        assert forbidden not in joined
    # An alias keeps its own port from the miner's ssh config.
    assert SSHClient("gpu_box").command() == [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "ServerAliveInterval=15",
        "--",
        "gpu_box",
    ]


@pytest.mark.parametrize(
    "destination",
    ["gpu-box", "miner@10.0.0.5", "miner@gpu.example.org", "my_alias", "a.b-c"],
)
def test_a_destination_is_user_at_host_or_an_alias(destination):
    assert SSHClient(destination).destination == destination


@pytest.mark.parametrize(
    "destination",
    [
        "-oProxyCommand=touch /tmp/x",
        "miner@-oProxyCommand=x",
        "-p",
        "gpu box",
        "gpu;rm -rf ~",
        "miner@gpu:22",
        "a@b@c",
        "ssh://gpu-box",
        "",
        None,
        "$(id)",
    ],
)
def test_a_destination_that_could_be_an_option_or_more_is_refused(destination):
    with pytest.raises(ValueError, match="destination"):
        SSHClient(destination)


@pytest.mark.parametrize("port", [0, 65536, "22", -1, True])
def test_an_invalid_port_is_refused(port):
    with pytest.raises(ValueError, match="port"):
        SSHClient("gpu-box", port=port)


def test_run_returns_the_status_and_a_bounded_stdout(tmp_path):
    fake = _executable(tmp_path / "ssh-fake", FAKE_SSH)
    client = SSHClient("miner@gpu-box", binary=str(fake))
    assert client.run("printf hello; exit 3", timeout=30) == (3, b"hello")
    code, out = client.run("head -c 200000 /dev/zero", timeout=30)
    assert code == 0 and len(out) == rm.MAX_STDOUT_BYTES
    # The script travels on stdin; ssh's argv ends `-- DEST bash -s`.
    argv = (tmp_path / "log.ssh").read_text().splitlines()
    assert argv[-4:] == ["--", "miner@gpu-box", "bash", "-s"]


def test_a_run_that_outlasts_its_time_or_has_no_client_is_a_status(tmp_path):
    fake = _executable(tmp_path / "ssh-fake", FAKE_SSH)
    client = SSHClient("gpu-box", binary=str(fake))
    assert client.run("sleep 20", timeout=0.5) == (rm.TIMED_OUT, b"")
    missing = SSHClient("gpu-box", binary=str(tmp_path / "no-ssh"))
    assert missing.run("true", timeout=5) == (rm.NO_SSH_CLIENT, b"")


def test_a_tunnel_forwards_a_local_port_to_the_machines_loopback(tmp_path):
    fake = _executable(tmp_path / "ssh-fake", FAKE_SSH)
    client = SSHClient(
        "gpu-box",
        binary=str(fake),
        free_port=lambda: 41000,
        listening=lambda port: port == 41000,
        sleep=lambda _: None,
    )
    tunnel = client.tunnel(49153)
    try:
        assert tunnel.url == "http://127.0.0.1:41000"
        argv = _logged(tmp_path / "log.ssh", "gpu-box")
        assert "127.0.0.1:41000:127.0.0.1:49153" in argv
        assert "ExitOnForwardFailure=yes" in argv and "-N" in argv
        assert argv[-2:] == ["--", "gpu-box"]
    finally:
        tunnel.close()
    assert tunnel.process.poll() is not None


def test_a_forward_that_never_opens_is_refused_and_closed(tmp_path):
    fake = _executable(tmp_path / "ssh-fake", "#!/bin/bash\nexit 255\n")
    client = SSHClient(
        "gpu-box", binary=str(fake), listening=lambda _: False, sleep=lambda _: None
    )
    with pytest.raises(RemoteMachineError) as refused:
        client.tunnel(49153)
    assert refused.value.code == "ssh_forward_failed"


# --- the start script ----------------------------------------------------------------


def test_the_start_script_starts_one_named_container_on_loopback_by_image_id(machine):
    text = script()
    assert "sudo" not in text
    for forbidden in ("apt", "curl", "wget", "install", "pull"):
        assert forbidden not in text
    completed = bash(text, machine, CARBON_FAKE_IMAGE=IMAGE)
    assert completed.returncode == 0, completed.stderr
    assert published_port(completed.stdout) == 49153
    (run,) = [line for line in calls(machine) if line.startswith("run ")]
    assert run.startswith(f"run -d --rm --name {NAME} --gpus all -p 127.0.0.1::8000 ")
    assert f"--entrypoint {COMMAND[0]} {IMAGE} -I -m carbon.compute.job_server" in run
    # The token travels in the env file only, never on a command line.
    assert TOKEN not in run
    log = machine["log"]
    env_lines = Path(str(log) + ".env").read_text().splitlines()
    assert env_lines == [f"{k}={v}" for k, v in ENV]
    # The env file is gone, and nothing else was left behind.
    assert not Path(Path(str(log) + ".envpath").read_text().strip()).exists()
    assert list(machine["tmp"].iterdir()) == []
    assert calls(machine)[-1] == f"port {NAME} 8000/tcp"


@pytest.mark.parametrize(
    "setup,code",
    [
        ({"docker": False}, rm.NO_DOCKER),
        ({"toolkit": False}, rm.NO_NVIDIA_TOOLKIT),
        ({"CARBON_FAKE_NO_ACCESS": "1"}, rm.NO_DOCKER_ACCESS),
        ({"CARBON_FAKE_IMAGE": "sha256:" + "8" * 64}, rm.NO_WORKER_IMAGE),
    ],
)
def test_each_missing_prerequisite_is_refused_by_its_own_code(machine, setup, code):
    options = {"CARBON_FAKE_IMAGE": IMAGE, **setup}
    completed = bash(script(), machine, **options)
    assert completed.returncode == code
    assert not [line for line in calls(machine) if line.startswith("run ")]
    assert list(machine["tmp"].iterdir()) == []
    expected = {
        rm.NO_DOCKER: "no_docker",
        rm.NO_NVIDIA_TOOLKIT: "no_nvidia_container_toolkit",
        rm.NO_DOCKER_ACCESS: "no_docker_access",
        rm.NO_WORKER_IMAGE: "no_worker_image",
    }
    assert rm.failure_for(code).code == expected[code]
    assert "sudo password" in rm.failure_for(rm.NO_DOCKER_ACCESS).next_step


def test_the_start_script_takes_only_plain_values():
    with pytest.raises(ValueError, match="not plain"):
        start_script(
            image_id=IMAGE,
            name=NAME,
            env=(("CARBON_JOB_TOKEN", "x; rm -rf ~"),),
            command=COMMAND,
        )
    with pytest.raises(ValueError, match="image ID"):
        start_script(image_id="ubuntu:latest", name=NAME, env=ENV, command=COMMAND)
    with pytest.raises(ValueError, match="carbon-job"):
        start_script(image_id=IMAGE, name="worker", env=ENV, command=COMMAND)
    with pytest.raises(ValueError, match="start command"):
        start_script(image_id=IMAGE, name=NAME, env=ENV, command=("python", "$(id)"))


def test_an_unreadable_published_port_is_refused():
    for stdout in (b"", b"0.0.0.0:49153\n", b"127.0.0.1:1\n127.0.0.1:2\n"):
        with pytest.raises(RemoteMachineError, match="job_port_unreadable"):
            published_port(stdout)


# --- the remove script --------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "carbon-job",
        "carbon-job-" + "a" * 23,
        "carbon-job-" + "A" * 24,
        "carbon-job-" + "a" * 24 + "; docker rm -f $(docker ps -q)",
        "postgres",
        None,
    ],
)
def test_the_remove_script_refuses_any_container_carbon_did_not_name(name):
    with pytest.raises(ValueError, match="carbon-job"):
        remove_script(name)


def test_the_remove_script_removes_the_job_container_and_confirms(machine):
    completed = bash(remove_script(NAME), machine)
    assert completed.returncode == 0
    assert f"rm -f {NAME}" in calls(machine)
    still = bash(remove_script(NAME), machine, CARBON_FAKE_STILL_THERE="1")
    assert still.returncode == 1


# --- streaming the worker image ------------------------------------------------------------


def test_the_worker_image_is_streamed_and_checked_by_id(tmp_path, monkeypatch):
    fakes = tmp_path / "fakes"
    fakes.mkdir()
    docker = _executable(fakes / "docker", FAKE_DOCKER)
    ssh = _executable(fakes / "ssh", FAKE_SSH)
    monkeypatch.setenv("PATH", f"{fakes}:/usr/bin:/bin")
    client = SSHClient("miner@gpu-box", binary=str(ssh))
    assert send_image(client, IMAGE, docker=str(docker)) == "sent"
    assert (tmp_path / "log.loaded").read_text().strip() == f"IMAGE-TAR-{IMAGE}"
    assert f"save {IMAGE}" in (tmp_path / "log").read_text().splitlines()
    # Held by ID now: nothing is sent again.
    assert send_image(client, IMAGE, docker=str(docker)) == "present"
    assert (tmp_path / "log").read_text().splitlines().count(f"save {IMAGE}") == 1


def test_an_image_that_does_not_arrive_as_the_pinned_id_is_refused(
    tmp_path, monkeypatch
):
    fakes = tmp_path / "fakes"
    fakes.mkdir()
    docker = _executable(fakes / "docker", FAKE_DOCKER)
    ssh = _executable(fakes / "ssh", FAKE_SSH)
    monkeypatch.setenv("PATH", f"{fakes}:/usr/bin:/bin")
    monkeypatch.setenv("CARBON_FAKE_CORRUPT", "1")
    with pytest.raises(RemoteMachineError) as refused:
        send_image(SSHClient("gpu-box", binary=str(ssh)), IMAGE, docker=str(docker))
    assert refused.value.code == "worker_image_not_loaded"


# --- the fakes themselves ------------------------------------------------------------


@pytest.mark.parametrize(
    "body,argv",
    [
        (FAKE_SSH, ("--", "gpu-box", "true")),
        (FAKE_DOCKER, ("load",)),
        (FAKE_DOCKER, ("rm", "-f", NAME)),
    ],
)
@pytest.mark.parametrize("unset", [True, False])
def test_a_fake_without_a_log_refuses_and_writes_nothing(tmp_path, body, argv, unset):
    fake = _executable(tmp_path / "fake", body)
    work = tmp_path / "work"
    work.mkdir()
    completed = subprocess.run(
        [str(fake), *argv],
        cwd=work,
        env={"PATH": "/usr/bin:/bin", **({} if unset else {"CARBON_FAKE_LOG": ""})},
        input=b"",
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == NO_FAKE_LOG
    assert b"CARBON_FAKE_LOG is empty" in completed.stderr
    assert list(work.iterdir()) == []
