"""Carbon's fixed practice on the miner's own remote GPU machine.

OWNER-MINER-COMPUTE-LINK-ONLY-01: Carbon connects to a machine the miner
runs and never starts, stops or bills it. `FakeRemote` stands in for the SSH
client: when the start script runs, it starts the real
`carbon.compute.job_server` in a thread on 127.0.0.1, with the token the
script carries, and answers with its port as `docker port` would. The
ledger, the durable job record, `RemoteJob` and battery practice scoring are
real. What these tests hold:
- one job container per trial, started by image ID with the job's token in
  its environment, reached through the tunnel, and removed afterwards;
- a failed job, or a machine that refuses the start, is infrastructure
  failure, and the container is still removed;
- the result says whether the removal was confirmed;
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
    NO_WORKER_IMAGE,
    RemoteMachineError,
    Tunnel,
)
from carbon.compute.remote_runner import START_COMMAND, RemoteRunner
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


class Process:
    """The tunnel's ssh process, as a fixture: it records being closed."""

    def __init__(self):
        self.closed = False

    def poll(self):
        return 0 if self.closed else None

    def terminate(self):
        self.closed = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.closed = True


class FakeRemote:
    """The miner's machine behind `SSHClient`'s `run` and `tunnel`."""

    def __init__(self, root, *, start_code=0, remove_code=0):
        self.root = root
        self.start_code, self.remove_code = start_code, remove_code
        self.started, self.removed, self.tunnels = [], [], []
        self.scripts = []

    def run(self, script, *, timeout):
        self.scripts.append(script)
        if "docker run" in script:
            name = re.search(r"--name (\S+)", script).group(1)
            self.started.append(name)
            if self.start_code:
                return self.start_code, b""
            env = dict(re.findall(r"printf '%s\\n' ([A-Z_]+)=(\S+)", script))
            return 0, f"127.0.0.1:{self._serve(env)}\n".encode()
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

    def tunnel(self, remote):
        # The forward is the identity here: the server already listens on
        # this machine's loopback.
        tunnel = Tunnel(Process(), remote)
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


def setup(tmp_path, *, job=fast_job, **remote):
    tmp_path.chmod(0o700)
    (tmp_path / "machine").mkdir()
    machine = FakeRemote(tmp_path / "machine", **remote)
    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(manifest())
    ledger.generation = CampaignControl(ledger).acquire()
    runner = RemoteRunner(
        machine=machine, image=gpu_worker(), clock=lambda: 100.0, job=job
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
    assert tunnel.process.closed
    # The job ran the staged program on the staged inputs.
    snapshot = ledger.root / result["operation"] / "snapshot"
    assert json.loads((snapshot / "predictions.json").read_bytes()) == {"sum": 6}
    assert result["remote"]["image"] == gpu_worker().image_id
    assert result["remote"]["job_transport"] == "ssh-tunnel"
    assert result["remote"]["container_removed"] is True
    assert result["remote"]["job"]["state"] == "DONE"
    assert result["official_eligible"] is False
    assert state(ledger) == ["SUCCEEDED"]
    # The container runs the pinned worker by ID, on the machine's loopback,
    # with the job server as its start command and the GPUs.
    start = machine.scripts[0]
    assert f" {gpu_worker().image_id} " in start
    assert "-p 127.0.0.1::8000" in start and "--gpus all" in start
    assert f"--entrypoint {START_COMMAND[0]}" in start


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
    assert call(runner, ledger)["remote"]["container_removed"] is False


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
        RemoteRunner(machine=object(), image=None)


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
    assert backend["job_transport"] == "ssh-tunnel"
    assert backend["container_removed"] is True
    assert backend["image"] == gpu_worker().image_id
    assert backend["purpose"] == "speed_only"
    assert "default_backend" in backend["observed"]
    assert result["summary"] and result["official_eligible"] is False
    assert machine.removed == machine.started and len(machine.started) == 1


def test_remote_practice_needs_the_pinned_gpu_worker(tmp_path):
    from carbon.battery.research import BatteryPractice

    runner, ledger, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="pinned GPU worker"):
        BatteryPractice(
            ledger=ledger, owner="miner", image=None, root=REPOSITORY, remote=runner
        )
