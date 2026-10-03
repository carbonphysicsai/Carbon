"""The miner's own GPU machine over SSH (OWNER-MINER-COMPUTE-LINK-ONLY-01).

No SSH connection is made and no Docker daemon is used. A fake `ssh` runs
the remote side locally, and the start and remove scripts run in real bash
with a fake `docker` on PATH. What is held:
- the ssh command line leaves keys, known hosts and host trust to the
  miner's own SSH: no `-i`, no `IdentitiesOnly`, no Carbon known-hosts file,
  no `accept-new`; the destination can never be read as an option;
- `run` returns the exit status and a bounded standard output, and a timeout
  or a missing client is a status, not an exception;
- a tunnel opens no local TCP port: ssh forwards an owner-only Unix socket in
  a new 0700 directory, removed on close; a socket that is not this user's,
  or a link in its place, is refused; the forward ends only at a loopback or
  private IPv4 address; and a hostile local listener never hears the job;
- the start script starts one hardened container by image ID with a
  per-job name and `--rm`: on its own `--internal` network, with no port
  published on the machine, a read-only root and one tmpfs scratch, every
  capability dropped, `no-new-privileges` and exactly one GPU by UUID (the
  2026-10-03 security review of the GPU code cell). It prints the
  container's private address for the SSH forward. The job's environment
  goes through a temporary file that is deleted; nothing uses sudo; and
  Docker, the toolkit, Docker access, the image, the GPU, the network and
  the container are each refused by their own code (90 to 93, 97 to 99);
- the remove script touches only Carbon's `carbon-job-<24 hex>` container
  and network;
- the worker image is streamed with `docker save | ssh docker load` and
  checked by image ID.

The fakes log only under each test's `tmp_path` and refuse to run without
`CARBON_FAKE_LOG`, so the module leaves nothing in the repository.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from carbon.compute import job_server
from carbon.compute import remote_machine as rm
from carbon.compute.remote_job import TUNNEL_URL, RemoteJob, new_token
from carbon.compute.remote_machine import (
    JobEndpoint,
    RemoteMachineError,
    SSHClient,
    checked_forward_host,
    job_endpoint,
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
GPU = "GPU-31e88d04-75ff-89b2-9160-4b923dd7eb81"
#: What the fake `nvidia-smi` lists: two GPUs; the job gets the first only.
FAKE_NVIDIA_SMI = f"""#!/bin/bash
printf '%s\\n' "${{CARBON_FAKE_GPUS-{GPU} GPU-0000aaaa-bbbb-cccc-dddd-eeeeffff0000}}" | {{
  read -r -a gpus; for gpu in "${{gpus[@]}}"; do printf ' %s\\n' "$gpu"; done
}}
"""
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
    [ -z "${CARBON_FAKE_RUN_FAILS:-}" ] || exit 125
    printf '%s\n' 4f3c2b1a; exit 0 ;;
  network)
    case "$2" in
      create) [ -z "${CARBON_FAKE_NO_NETWORK:-}" ] || exit 1; exit 0 ;;
      inspect) [ -n "${CARBON_FAKE_NETWORK_STILL_THERE:-}" ] && exit 0; exit 1 ;;
    esac
    exit 0 ;;
  inspect)
    printf '172.30.0.2\n'; exit 0 ;;
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


def bash(script, machine, *, docker=True, toolkit=True, gpu=True, **env):
    if docker:
        _executable(machine["tools"] / "docker", FAKE_DOCKER)
    if toolkit:
        _executable(machine["tools"] / "nvidia-ctk", "#!/bin/bash\nexit 0\n")
    if gpu:
        _executable(machine["tools"] / "nvidia-smi", FAKE_NVIDIA_SMI)
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


# --- the tunnel ------------------------------------------------------------------------

#: A fake `ssh` for a forward: it logs its argv, then serves the `-L` socket
#: and relays each connection to `host:port`, as ssh relays it to the
#: machine. `CARBON_FAKE_FORWARD` makes it misbehave: `link` puts a link in
#: the socket's place, `open` lets others enter the socket's directory.
FAKE_FORWARD = r"""
import os, socket, sys, threading

arguments = sys.argv[1:]
log_base = os.environ.get("CARBON_FAKE_LOG", "")
if not log_base:
    sys.stderr.write("fake ssh: CARBON_FAKE_LOG is empty; set it under tmp_path\n")
    sys.exit(99)
with open(log_base + ".ssh", "a") as log:
    log.write("".join(argument + "\n" for argument in arguments))
path, host, port = arguments[arguments.index("-L") + 1].rsplit(":", 2)
mode = os.environ.get("CARBON_FAKE_FORWARD", "")
bound = path
if mode == "link":
    bound = os.path.join(os.path.dirname(path), "elsewhere.sock")
if mode == "open":
    os.chmod(os.path.dirname(path), 0o755)
listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
listener.bind(bound)
listener.listen()
if mode == "link":
    os.symlink(bound, path)


def pump(source, sink):
    try:
        while chunk := source.recv(65536):
            sink.sendall(chunk)
    except OSError:
        pass
    finally:
        try:
            sink.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def relay(client):
    with client, socket.create_connection((host, int(port))) as upstream:
        back = threading.Thread(target=pump, args=(upstream, client))
        back.start()
        pump(client, upstream)
        back.join()


while True:
    client, _ = listener.accept()
    threading.Thread(target=relay, args=(client,), daemon=True).start()
"""

PROGRAM = b"""
import json
from pathlib import Path
work = Path.cwd()
data = json.loads((work / "inputs.json").read_text())
(work.parent / "output" / "predictions.json").write_text(json.dumps({"sum": sum(data)}))
"""


@pytest.fixture
def short_tmp(monkeypatch):
    """A short temporary directory for tunnels: a socket's path is bounded."""
    root = Path(tempfile.mkdtemp(prefix="carbon-test-"))
    monkeypatch.setattr(tempfile, "tempdir", str(root))
    yield root
    shutil.rmtree(root, ignore_errors=True)


def forwarding(tmp_path, monkeypatch, mode=""):
    """An SSH client whose `ssh` is FAKE_FORWARD; its forwards are recorded.
    It logs where every fake does (`fake_log_under_tmp_path`)."""
    monkeypatch.setenv("CARBON_FAKE_FORWARD", mode)
    fake = _executable(tmp_path / "ssh-forward", f"#!{sys.executable}\n" + FAKE_FORWARD)
    client = SSHClient("gpu-box", binary=str(fake), sleep=lambda _: time.sleep(0.1))
    client.forwards = []
    forward = client.forward

    def recorded(*args, **kwargs):
        client.forwards.append(forward(*args, **kwargs))
        return client.forwards[-1]

    client.forward = recorded
    return client


def serving(root):
    """The job's server, in a thread on this machine's loopback: its port
    and token."""
    token, ready, port = new_token(), threading.Event(), []

    def started(bound):
        port.append(bound)
        ready.set()

    threading.Thread(
        target=job_server.serve,
        kwargs={
            "token": token,
            "port": 0,
            "seconds": 30,
            "lifetime": 60,
            "root": root,
            "ready": started,
        },
        daemon=True,
    ).start()
    assert ready.wait(10)
    return port[0], token


def test_a_tunnel_forwards_an_owner_only_socket_to_the_machine(
    tmp_path, short_tmp, monkeypatch
):
    client = forwarding(tmp_path, monkeypatch)
    tunnel = client.tunnel(49153, host="172.30.0.2", attempts=100)
    directory = Path(tunnel.directory)
    try:
        assert tunnel.url == TUNNEL_URL
        assert directory.parent == short_tmp
        # A new directory only this user may enter, holding ssh's socket.
        found = os.lstat(directory)
        assert stat.S_IMODE(found.st_mode) == 0o700 and found.st_uid == os.getuid()
        assert stat.S_ISSOCK(os.lstat(tunnel.path).st_mode)
        argv = _logged(tmp_path / "log.ssh", "gpu-box")
        assert argv[argv.index("-L") + 1] == f"{tunnel.path}:172.30.0.2:49153"
        for option in (
            "ExitOnForwardFailure=yes",
            "StreamLocalBindUnlink=yes",
            "StreamLocalBindMask=0177",
        ):
            assert option in argv
        assert "-N" in argv and argv[-2:] == ["--", "gpu-box"]
    finally:
        tunnel.close()
    # Closing stops ssh and removes the socket and its directory.
    assert tunnel.process.poll() is not None and not directory.exists()


def test_a_hostile_listener_on_a_local_port_never_hears_the_job(
    tmp_path, short_tmp, monkeypatch
):
    """Another local user holds a TCP port first. The tunnel opens none, so
    every request, token and all, goes to the tunnel's own socket."""
    port, token = serving(tmp_path)
    hostile = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    hostile.bind(("127.0.0.1", 0))
    hostile.listen()
    hostile.setblocking(False)
    connected = []
    connect = socket.socket.connect

    def recording(self, address):
        connected.append((self.family, address))
        return connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", recording)
    tunnel = forwarding(tmp_path, monkeypatch).tunnel(port, attempts=100)
    try:
        job = RemoteJob(
            tunnel.url, token, transport=tunnel.transport, sleep=lambda _: None
        )
        result, files = job.run(
            {"program.py": PROGRAM, "inputs.json": b"[1, 2]"},
            ready_deadline=job.clock() + 10,
            run_deadline=job.clock() + 30,
        )
    finally:
        tunnel.close()
    assert result["state"] == "DONE" and json.loads(files["predictions.json"]) == {
        "sum": 3
    }
    # The controller connected only to the tunnel's socket, never over TCP.
    assert connected and set(connected) == {(socket.AF_UNIX, tunnel.path)}
    with pytest.raises(BlockingIOError):
        hostile.accept()
    # Nor can a job be aimed at that port.
    with pytest.raises(ValueError, match="https"):
        RemoteJob(f"http://127.0.0.1:{hostile.getsockname()[1]}", token)
    hostile.close()


def _not_ours(monkeypatch):
    """Make the tunnel's socket look like another user's."""
    lstat = os.lstat

    def foreign(path, *args, **kwargs):
        found = lstat(path, *args, **kwargs)
        if os.fspath(path).endswith("/" + rm.TUNNEL_SOCKET):
            values = list(found[:10])
            values[4] = found.st_uid + 1
            return os.stat_result(values)
        return found

    monkeypatch.setattr(os, "lstat", foreign)


@pytest.mark.parametrize("mode", ["link", "open", "foreign"])
def test_a_socket_that_is_not_this_users_own_is_refused(
    tmp_path, short_tmp, monkeypatch, mode
):
    client = forwarding(tmp_path, monkeypatch, "" if mode == "foreign" else mode)
    if mode == "foreign":
        _not_ours(monkeypatch)
    with pytest.raises(RemoteMachineError) as refused:
        client.tunnel(49153, attempts=100)
    assert refused.value.code == "tunnel_socket_refused"
    # The forward was stopped and nothing is left in the socket's place.
    (process,) = client.forwards
    assert process.poll() is not None
    assert not any(os.path.lexists(d / rm.TUNNEL_SOCKET) for d in short_tmp.iterdir())


@pytest.mark.parametrize(
    "host",
    [
        "8.8.8.8",
        "203.0.113.7",
        "0.0.0.0",
        "169.254.169.254",
        "100.64.0.1",
        "172.32.0.1",
        "192.0.2.1",
        "255.255.255.255",
        "gpu-box",
        "localhost",
        "::1",
        "127.1",
        "010.0.0.1",
        " 10.0.0.1",
        "",
        None,
        167772161,
    ],
)
def test_a_forward_ends_only_at_a_loopback_or_private_ipv4_address(tmp_path, host):
    client = SSHClient("gpu-box", binary=str(tmp_path / "never-run"))
    with pytest.raises(ValueError, match="loopback or private"):
        client.tunnel(49153, host=host)
    with pytest.raises(ValueError, match="loopback or private"):
        client.forward("/tmp/carbon-tunnel-x/job.sock", 49153, host=host)


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "127.0.0.53",
        "10.0.0.5",
        "172.16.0.1",
        "172.31.255.254",
        "192.168.1.20",
    ],
)
def test_a_forward_may_end_at_the_loopback_or_a_private_address(host):
    assert checked_forward_host(host) == host


def test_without_unix_sockets_the_tunnel_is_refused_and_never_uses_tcp(
    tmp_path, short_tmp, monkeypatch
):
    monkeypatch.delattr(socket, "AF_UNIX")
    with pytest.raises(RemoteMachineError) as refused:
        SSHClient("gpu-box", binary=str(tmp_path / "never-run")).tunnel(49153)
    assert refused.value.code == "no_unix_sockets"
    assert list(short_tmp.iterdir()) == []


def test_a_socket_path_too_long_for_a_socket_is_refused(
    tmp_path, short_tmp, monkeypatch
):
    long = short_tmp / ("d" * 100)
    long.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(long))
    with pytest.raises(RemoteMachineError) as refused:
        SSHClient("gpu-box", binary=str(tmp_path / "never-run")).tunnel(49153)
    assert refused.value.code == "tunnel_socket_unusable"
    assert list(long.iterdir()) == []


def test_a_forward_that_never_opens_is_refused_and_closed(tmp_path, short_tmp):
    fake = _executable(tmp_path / "ssh-fake", "#!/bin/bash\nexit 255\n")
    client = SSHClient("gpu-box", binary=str(fake), sleep=lambda _: time.sleep(0.1))
    with pytest.raises(RemoteMachineError) as refused:
        client.tunnel(49153, attempts=100)
    assert refused.value.code == "ssh_forward_failed"
    # Its private directory is gone too.
    assert list(short_tmp.iterdir()) == []


# --- the start script ----------------------------------------------------------------


def test_the_start_script_starts_one_hardened_container_on_its_own_network(machine):
    text = script()
    assert "sudo" not in text
    for forbidden in ("apt", "curl", "wget", "install", "pull"):
        assert forbidden not in text
    completed = bash(text, machine, CARBON_FAKE_IMAGE=IMAGE)
    assert completed.returncode == 0, completed.stderr
    # The SSH forward targets the container's private address and job port.
    assert job_endpoint(completed.stdout) == JobEndpoint("172.30.0.2", 8000)
    made = calls(machine)
    assert f"network create --internal {NAME}" in made
    (run,) = [line for line in made if line.startswith("run ")]
    assert made.index(f"network create --internal {NAME}") < made.index(run)
    assert run.startswith(
        f"run -d --rm --name {NAME} --network {NAME} --read-only "
        "--tmpfs /scratch:rw,nosuid,nodev,exec,uid=65532,gid=65532,mode=0700 "
        "--cap-drop ALL --security-opt no-new-privileges "
        f"--gpus device={GPU} "
    )
    # Exactly one GPU, the first the driver lists; nothing published on the
    # machine, so no port, and never all GPUs.
    assert "--gpus all" not in run and " -p " not in run and "--publish" not in run
    assert "--privileged" not in run and "--cap-add" not in run
    assert f"--entrypoint {COMMAND[0]} {IMAGE} -I -m carbon.compute.job_server" in run
    # The token travels in the env file only, never on a command line.
    assert TOKEN not in run
    log = machine["log"]
    env_lines = Path(str(log) + ".env").read_text().splitlines()
    assert env_lines == [f"{k}={v}" for k, v in (*rm.JOB_SCRATCH_ENV, *ENV)]
    # The env file is gone, and nothing else was left behind.
    assert not Path(Path(str(log) + ".envpath").read_text().strip()).exists()
    assert list(machine["tmp"].iterdir()) == []
    assert made[-1].startswith("inspect --format") and made[-1].endswith(NAME)


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


@pytest.mark.parametrize(
    "setup",
    [
        {"gpu": False},
        {"CARBON_FAKE_GPUS": ""},
        {"CARBON_FAKE_GPUS": "GPU-$(id)"},
        {"CARBON_FAKE_GPUS": "all"},
        {"CARBON_FAKE_GPUS": "GPU-short"},
    ],
)
def test_no_gpu_listed_by_uuid_is_refused_before_anything_starts(machine, setup):
    completed = bash(script(), machine, CARBON_FAKE_IMAGE=IMAGE, **setup)
    assert completed.returncode == rm.NO_GPU_DEVICE
    made = calls(machine)
    assert not [c for c in made if c.startswith(("run ", "network "))]
    assert list(machine["tmp"].iterdir()) == []
    assert rm.failure_for(rm.NO_GPU_DEVICE).code == "no_gpu_device"


def test_a_network_or_container_that_cannot_start_is_refused_and_left_clean(machine):
    no_network = bash(
        script(), machine, CARBON_FAKE_IMAGE=IMAGE, CARBON_FAKE_NO_NETWORK="1"
    )
    assert no_network.returncode == rm.JOB_NETWORK_UNAVAILABLE
    assert not [c for c in calls(machine) if c.startswith("run ")]
    assert rm.failure_for(rm.JOB_NETWORK_UNAVAILABLE).code == "job_network_unavailable"
    machine["log"].unlink()
    no_run = bash(script(), machine, CARBON_FAKE_IMAGE=IMAGE, CARBON_FAKE_RUN_FAILS="1")
    assert no_run.returncode == rm.JOB_CONTAINER_NOT_STARTED
    # The job's network is removed with the container that never started.
    assert calls(machine)[-1] == f"network rm {NAME}"
    assert list(machine["tmp"].iterdir()) == []
    assert (
        rm.failure_for(rm.JOB_CONTAINER_NOT_STARTED).code == "job_container_not_started"
    )


@pytest.mark.parametrize(
    "stdout",
    [
        b"",
        b"8.8.8.8:8000\n",
        b"0.0.0.0:8000\n",
        b"169.254.169.254:8000\n",
        b"172.30.0.2:8000\n172.30.0.3:8000\n",
        b"999.1.1.1:8000\n",
        b"172.30.0.2:0\n",
        b"gpu-box:8000\n",
    ],
)
def test_a_job_endpoint_is_one_private_or_loopback_address(stdout):
    with pytest.raises(RemoteMachineError, match="job_port_unreadable"):
        job_endpoint(stdout)
    assert job_endpoint(b"127.0.0.1:41234\n") == JobEndpoint("127.0.0.1", 41234)


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


def test_the_remove_script_removes_the_job_container_and_network_and_confirms(machine):
    completed = bash(remove_script(NAME), machine)
    assert completed.returncode == 0
    assert f"rm -f {NAME}" in calls(machine)
    assert f"network rm {NAME}" in calls(machine)
    still = bash(remove_script(NAME), machine, CARBON_FAKE_STILL_THERE="1")
    assert still.returncode == 1
    network = bash(remove_script(NAME), machine, CARBON_FAKE_NETWORK_STILL_THERE="1")
    assert network.returncode == 1


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
        (
            f"#!{sys.executable}\n" + FAKE_FORWARD,
            ("-N", "-L", "/nonexistent/job.sock:127.0.0.1:8000", "--", "gpu-box"),
        ),
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
