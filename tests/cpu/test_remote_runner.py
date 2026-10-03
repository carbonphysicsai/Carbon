"""Carbon's fixed practice on the miner's own remote setup.

OWNER-MINER-COMPUTE-LINK-ONLY-01: Carbon connects to a machine the miner
runs and never starts, stops or bills it. `FakeRemote` stands in for the SSH
client of an `ssh-docker` machine: when the start script runs, it starts the
real `carbon.compute.job_server` in a thread on 127.0.0.1, with the token the
script carries, and answers with its port as `docker port` would. The
`ssh-container` tests run the container's real scripts in bash, which start
the real job server as a process. The ledger, the durable job record,
`RemoteJob` and battery practice scoring are real. What these tests hold:
- one job per trial, started from the pinned worker with the job's token in
  its environment, reached through the tunnel, and cleaned up afterwards;
- a failed job, or a machine that refuses the start, is infrastructure
  failure, and the job is still cleaned up;
- every transport records the same fields, including whether the cleanup
  was confirmed;
- a replayed trial returns its result and starts nothing;
- battery practice through `BatteryPractice(remote=...)` records the
  `REMOTE_GPU` backend, what JAX observed, and is never official.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from carbon.compute import job_server
from carbon.compute.remote_job import RemoteJob, RemoteJobFailure
from carbon.compute.remote_machine import (
    CONTAINER_NAME,
    JOB_PORT,
    NO_WORKER_IMAGE,
    RemoteMachineError,
)
from carbon.compute.remote_runner import START_COMMAND, RemoteRunner, RemoteWorker
from carbon.compute.remote_transport import SSHDocker
from carbon.development_session.profile import canonical
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import CampaignLedger

PROGRAM = """
import json
from pathlib import Path
work = Path.cwd()
out = work.parent / "output"
data = json.loads((work / "inputs.json").read_text())
(out / "predictions.json").write_text(json.dumps({"sum": sum(data)}))
"""


#: Where the real start script says the job container listens: its address on
#: the job's private network, and the job port.
CONTAINER_ADDRESS = "172.30.0.2"


class FakeRemote:
    """The miner's machine behind `SSHClient`'s `run` and `tunnel`."""

    def __init__(self, root, *, start_code=0, remove_code=0):
        self.root = root
        self.start_code, self.remove_code = start_code, remove_code
        self.started, self.removed, self.tunnels = [], [], []
        self.scripts = []
        #: The job server's real local port, behind the container's address.
        self.served = None

    def run(self, script, *, timeout):
        self.scripts.append(script)
        if "docker run" in script:
            name = re.search(r"--name (\S+)", script).group(1)
            self.started.append(name)
            if self.start_code:
                return self.start_code, b""
            env = dict(re.findall(r"printf '%s\\n' ([A-Z_]+)=(\S+)", script))
            self.served = self._serve(env)
            return 0, f"{CONTAINER_ADDRESS}:{env['CARBON_JOB_PORT']}\n".encode()
        if "docker rm -f" in script:
            self.removed.append(re.search(r"docker rm -f (\S+)", script).group(1))
            return self.remove_code, b""
        raise AssertionError("an unexpected script ran on the machine")

    def _serve(self, env):
        """The container's job server, here as a thread on 127.0.0.1."""
        ready, port = threading.Event(), []

        def started(bound):
            port.append(bound)
            ready.set()

        threading.Thread(
            target=job_server.serve,
            kwargs={
                "token": env["CARBON_JOB_TOKEN"],
                "port": 0,
                "seconds": int(env["CARBON_JOB_SECONDS"]),
                "lifetime": 60,
                "root": self.root,
                "ready": started,
            },
            daemon=True,
        ).start()
        assert ready.wait(10)
        return port[0]

    def tunnel(self, remote, *, host="127.0.0.1"):
        # The forward targets the container's private address and job port.
        # Here the job server is a thread on this machine's loopback, and the
        # tunnel's Unix socket relays to it, as ssh's forward relays.
        assert (host, remote) == (CONTAINER_ADDRESS, JOB_PORT)
        from remote_container_fixture import local_tunnel

        tunnel = local_tunnel(self.served)
        self.tunnels.append(tunnel)
        return tunnel


def fast_job(url, token, **kwargs):
    return RemoteJob(url, token, sleep=lambda _: time.sleep(0.05), **kwargs)


def failing_job(url, token, **kwargs):
    class Failing:
        @staticmethod
        def clock():
            return 0.0

        def run(self, files, *, ready_deadline, run_deadline):
            raise RemoteJobFailure("run", "http 502")

    return Failing()


def gpu_worker(tag="9"):
    from test_battery_gpu_practice import gpu_image

    return gpu_image(tag)


def manifest():
    """A real frozen battery product manifest (the ledger's own fixture)."""
    from test_battery_research_images import IMAGES, IMPLEMENTATION, launch, runtime

    from carbon.battery import campaign as battery

    return battery.manifest_document(
        launch(runtime()),
        owner="miner",
        implementation=IMPLEMENTATION,
        images=list(IMAGES),
    )


@pytest.fixture(autouse=True)
def loopback_without_proxy(monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")


def worker(image=None):
    return RemoteWorker(image or gpu_worker(), (("JAX_PLATFORMS", "cuda"),))


def campaign_ledger(tmp_path):
    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(manifest())
    ledger.generation = CampaignControl(ledger).acquire()
    return ledger


def setup(tmp_path, *, job=fast_job, **remote):
    tmp_path.chmod(0o700)
    (tmp_path / "machine").mkdir()
    machine = FakeRemote(tmp_path / "machine", **remote)
    ledger = campaign_ledger(tmp_path)
    runner = RemoteRunner(
        transport=SSHDocker(machine), worker=worker(), clock=lambda: 100.0, job=job
    )
    return runner, ledger, machine


def call(runner, ledger, identity="trial-1", image=None):
    return runner(
        ledger,
        owner="miner",
        identity=identity,
        source=PROGRAM,
        files={"inputs.json": canonical([1, 2, 3])},
        image=image or gpu_worker(),
        seconds=120,
        provenance="BATTERY_PUBLIC_PRACTICE",
        extra_resources={},
    )


def state(ledger):
    with ledger.db() as db:
        return [row[0] for row in db.execute("SELECT state FROM operations")]


def test_a_trial_starts_one_container_runs_the_job_and_removes_it(tmp_path):
    runner, ledger, machine = setup(tmp_path)
    result = call(runner, ledger)
    (name,) = machine.started
    assert CONTAINER_NAME.fullmatch(name)
    assert machine.removed == [name]
    (tunnel,) = machine.tunnels
    # The job was reached through the tunnel's Unix socket, whose directory
    # is gone with it.
    assert tunnel.process.closed and not Path(tunnel.directory).exists()
    # The job ran the staged program on the staged inputs.
    snapshot = ledger.root / result["operation"] / "snapshot"
    assert json.loads((snapshot / "predictions.json").read_bytes()) == {"sum": 6}
    assert result["remote"] == {
        "transport": "ssh-docker",
        "image": gpu_worker().image_id,
        "image_verified_by": "image-id",
        "job_transport": "ssh-tunnel",
        "cleanup": "confirmed",
        "job": result["remote"]["job"],
    }
    assert result["remote"]["job"]["state"] == "DONE"
    assert result["official_eligible"] is False
    assert state(ledger) == ["SUCCEEDED"]
    # The container runs the pinned worker by ID, hardened, on its own
    # private network with nothing published, with the job server as its
    # start command and one GPU by UUID.
    start = machine.scripts[0]
    assert f" {gpu_worker().image_id} " in start
    assert "--network carbon-job-" in start and "network create --internal" in start
    assert "--read-only" in start and "--cap-drop ALL" in start
    assert "no-new-privileges" in start and '--gpus "device=$carbon_gpu"' in start
    assert "-p 127.0.0.1::" not in start and "--gpus all" not in start
    assert f"--entrypoint {START_COMMAND[0]}" in start
    # The Challenge's worker environment travels with the job's own.
    assert "JAX_PLATFORMS=cuda" in start and "CARBON_JOB_PORT=8000" in start


def test_the_job_record_is_owner_only_and_its_token_is_the_containers(tmp_path):
    runner, ledger, machine = setup(tmp_path)
    result = call(runner, ledger)
    record = ledger.root / result["operation"] / "remote-job.json"
    assert record.stat().st_mode & 0o777 == 0o600
    token = json.loads(record.read_bytes())["token"]
    assert f"CARBON_JOB_TOKEN={token}" in machine.scripts[0]
    # The token never reaches the result.
    assert token not in json.dumps(result)


def test_a_failed_job_is_infrastructure_and_its_container_is_still_removed(
    tmp_path,
):
    runner, ledger, machine = setup(tmp_path, job=failing_job)
    with pytest.raises(RemoteJobFailure):
        call(runner, ledger)
    assert machine.removed == machine.started and len(machine.removed) == 1
    assert machine.tunnels[0].process.closed
    assert state(ledger) == ["FAILED_INFRA"]


@pytest.mark.parametrize(
    "output",
    [
        b"\x1f\x8bnot a gzip stream",
        job_server.pack({"predictions.json": b"{}"}),
        job_server.pack({"carbon-job-result.json": b"[]"}),
    ],
)
def test_a_malformed_output_settles_the_trial_and_never_leaves_it_reserved(
    tmp_path, output
):
    """The 2026-10-03 review: a malformed archive (a tarfile or zlib error, a
    missing result) escaped the runner's handler and left the operation
    RESERVED. RemoteJob types it now, so the trial settles as infrastructure
    failure and its container is still removed."""
    seen = []

    def hostile(method, url, *, body, headers, timeout):
        path = url.rsplit("/", 1)[1]
        seen.append(path)
        if path == "status":
            state_now = "DONE" if "run" in seen else "WAITING"
            return 200, json.dumps({"state": state_now}).encode()
        return {"stage": (200, b""), "run": (202, b""), "output": (200, output)}[path]

    def job(url, token, **kwargs):
        return RemoteJob(
            "https://pod.example.org",
            token,
            transport=hostile,
            sleep=lambda _: None,
            **{k: v for k, v in kwargs.items() if k == "cancelled"},
        )

    runner, ledger, machine = setup(tmp_path, job=job)
    with pytest.raises(RemoteJobFailure) as failed:
        call(runner, ledger)
    assert failed.value.stage == "output"
    assert state(ledger) == ["FAILED_INFRA"]
    assert machine.removed == machine.started


def test_a_machine_that_refuses_the_start_is_named_and_still_cleaned(tmp_path):
    runner, ledger, machine = setup(tmp_path, start_code=NO_WORKER_IMAGE)
    with pytest.raises(RemoteMachineError) as refused:
        call(runner, ledger)
    assert refused.value.code == "no_worker_image"
    assert "pinned GPU worker" in refused.value.next_step
    # Removal is still asked for; no tunnel was opened.
    assert machine.removed == machine.started
    assert machine.tunnels == []
    assert state(ledger) == ["FAILED_INFRA"]


def test_an_unconfirmed_removal_is_recorded_as_such(tmp_path):
    runner, ledger, _ = setup(tmp_path, remove_code=1)
    assert call(runner, ledger)["remote"]["cleanup"] == "unconfirmed"


def test_a_replayed_trial_returns_its_result_and_starts_nothing(tmp_path):
    runner, ledger, machine = setup(tmp_path)
    first = call(runner, ledger)
    assert call(runner, ledger) == first
    assert len(machine.started) == 1


def test_practice_asking_for_another_worker_is_refused_before_anything(tmp_path):
    runner, ledger, machine = setup(tmp_path)
    with pytest.raises(ValueError, match="another worker"):
        call(runner, ledger, image=gpu_worker("8"))
    assert machine.scripts == [] and state(ledger) == []


def test_the_runner_needs_the_pinned_worker_by_id():
    with pytest.raises(ValueError, match="pinned image"):
        RemoteRunner(transport=object(), worker=None)
    with pytest.raises(ValueError, match="pinned image"):
        RemoteWorker(None)
    # The job's own variables are the runner's and the transport's.
    with pytest.raises(ValueError, match="not the Challenge's"):
        RemoteWorker(gpu_worker(), (("CARBON_JOB_PORT", "1"),))
    with pytest.raises(ValueError, match="not plain"):
        RemoteWorker(gpu_worker(), (("JAX_PLATFORMS", "cuda; id"),))


# --- a container the miner started from the pinned worker (ssh-container) -----------


def container_setup(tmp_path, **changed):
    from remote_container_fixture import container, local_worker

    tmp_path.chmod(0o700)
    transport, ssh, python = container(tmp_path, gpu_worker(), **changed)
    runner = RemoteRunner(
        transport=transport,
        worker=local_worker(gpu_worker(), python),
        clock=lambda: 100.0,
        job=fast_job,
    )
    return runner, campaign_ledger(tmp_path), ssh, tmp_path / "container" / "jobs"


def test_a_container_trial_runs_one_job_process_and_cleans_it_up(tmp_path):
    runner, ledger, ssh, jobs = container_setup(tmp_path)
    result = call(runner, ledger)
    snapshot = ledger.root / result["operation"] / "snapshot"
    assert json.loads((snapshot / "predictions.json").read_bytes()) == {"sum": 6}
    # The same record as a job container, verified by build identity.
    assert {k: v for k, v in result["remote"].items() if k != "job"} == {
        "transport": "ssh-container",
        "image": gpu_worker().image_id,
        "image_verified_by": "build-identity",
        "job_transport": "ssh-tunnel",
        "cleanup": "confirmed",
    }
    assert result["remote"]["job"]["state"] == "DONE"
    assert result["official_eligible"] is False and state(ledger) == ["SUCCEEDED"]
    # Identity first, then one start and one stop; the job's directory is gone.
    assert "worker-image-build.json" in ssh.scripts[0]
    assert "exec setsid" in ssh.scripts[1] and "kill -TERM" in ssh.scripts[2]
    assert len(ssh.scripts) == 3 and list(jobs.iterdir()) == []
    assert ssh.tunnels[0].process.closed
    # The token and the worker's environment never appear on a command line.
    record = json.loads(
        (ledger.root / result["operation"] / "remote-job.json").read_bytes()
    )
    start = ssh.scripts[1]
    assert f"CARBON_JOB_TOKEN={record['token']}" in start
    assert record["token"] not in start.split("exec setsid", 1)[1]


def test_a_container_holding_another_worker_is_refused_and_nothing_starts(tmp_path):
    runner, ledger, ssh, jobs = container_setup(
        tmp_path, wheel_digest="sha256:" + "7" * 64
    )
    with pytest.raises(RemoteMachineError) as refused:
        call(runner, ledger)
    assert refused.value.code == "worker_identity_mismatch"
    # Only the identity check and the cleanup ran; no job process started.
    assert len(ssh.scripts) == 2 and "setsid" not in "".join(ssh.scripts)
    assert state(ledger) == ["FAILED_INFRA"] and list(jobs.iterdir()) == []


def test_a_failed_container_job_is_infrastructure_and_still_cleaned(tmp_path):
    runner, ledger, ssh, jobs = container_setup(tmp_path)
    runner.job = failing_job
    with pytest.raises(RemoteJobFailure):
        call(runner, ledger)
    assert state(ledger) == ["FAILED_INFRA"]
    # The started server was stopped and its directory removed.
    assert "kill -TERM" in ssh.scripts[-1] and list(jobs.iterdir()) == []


# --- battery practice ---------------------------------------------------------------


def test_battery_practice_on_the_remote_machine_records_its_backend(tmp_path):
    from test_battery_validator_daemon import submission

    from carbon.battery.research import BatteryPractice

    runner, ledger, machine = setup(tmp_path)
    practice = BatteryPractice(
        ledger=ledger,
        owner="miner",
        image=None,
        root=REPOSITORY,
        gpu_image=gpu_worker(),
        remote=runner,
    )
    result = practice("task-remote", submission("hk", "knn", neighbours=8).strategy)
    backend = result["backend"]
    assert backend["kind"] == "REMOTE_GPU"
    assert backend["runner"] == "carbon.compute.remote_runner"
    assert backend["transport"] == "ssh-docker"
    assert backend["image_verified_by"] == "image-id"
    assert backend["job_transport"] == "ssh-tunnel"
    assert backend["cleanup"] == "confirmed"
    assert backend["image"] == gpu_worker().image_id
    assert backend["purpose"] == "speed_only"
    assert "default_backend" in backend["observed"]
    assert result["summary"] and result["official_eligible"] is False
    assert machine.removed == machine.started and len(machine.started) == 1


def test_battery_practice_in_the_miners_container_records_its_backend(tmp_path):
    from test_battery_validator_daemon import submission

    from carbon.battery.research import BatteryPractice

    runner, ledger, _ssh, jobs = container_setup(tmp_path)
    practice = BatteryPractice(
        ledger=ledger,
        owner="miner",
        image=None,
        root=REPOSITORY,
        gpu_image=gpu_worker(),
        remote=runner,
    )
    result = practice("task-container", submission("hk", "knn", neighbours=8).strategy)
    backend = result["backend"]
    assert backend["kind"] == "REMOTE_GPU"
    assert backend["transport"] == "ssh-container"
    assert backend["image_verified_by"] == "build-identity"
    assert backend["cleanup"] == "confirmed" and backend["purpose"] == "speed_only"
    assert "default_backend" in backend["observed"]
    assert result["summary"] and result["official_eligible"] is False
    assert list(jobs.iterdir()) == []


def test_remote_practice_needs_the_pinned_gpu_worker(tmp_path):
    from carbon.battery.research import BatteryPractice

    runner, ledger, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="pinned GPU worker"):
        BatteryPractice(
            ledger=ledger, owner="miner", image=None, root=REPOSITORY, remote=runner
        )
