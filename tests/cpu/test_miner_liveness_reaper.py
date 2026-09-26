"""An unbounded miner run is removed when its controller dies, and only then.

The miner lane has no Carbon time limit, so no deadline watchdog guards it.
The liveness reaper removes the exact container - name and launch label -
once the owning controller process is gone, and never while it lives. The
Docker CLI is a fake that models containers by name and launch label and
runs the real `remove_exact_container` against them; the controller's
identity is either a scripted fake or a real child process.
"""

import json
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from carbon.development_session import miner_container, research_carrier
from carbon.reconstruction.worker import accelerator_runtime, liveness_reaper
from carbon.reconstruction.worker.liveness_reaper import (
    LAUNCH_LABEL,
    main,
    process_identity,
    watch,
)
from carbon.reconstruction.worker.model import WorkerFailure

NAME = "carbon-d4-" + "a" * 24
LAUNCH = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64


class FakeDocker:
    """Containers by name -> launch label. Records every mutating command."""

    def __init__(self, containers=None, *, unanswering=False):
        self.containers = dict(containers or {})
        self.mutations = []
        self.unanswering = unanswering

    def run(self, arguments, *, timeout=30, accepted=(0,)):
        verb, target = arguments[0], arguments[1] if len(arguments) > 1 else None
        if verb == "inspect":
            if self.unanswering:
                return SimpleNamespace(
                    returncode=1, stdout=b"", stderr=b"Cannot connect to the daemon"
                )
            if target not in self.containers:
                return SimpleNamespace(
                    returncode=1, stdout=b"", stderr=b"Error: No such object: x"
                )
            return SimpleNamespace(
                returncode=0,
                stdout=self.containers[target].encode() + b"\n",
                stderr=b"",
            )
        if verb in {"stop", "kill", "rm"}:
            self.mutations.append((verb, arguments[-1]))
            if verb == "rm":
                self.containers.pop(arguments[-1], None)
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        if verb == "ps":
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        raise AssertionError(arguments)

    def json(self, arguments, *, timeout=30):
        if arguments[1] not in self.containers:
            raise WorkerFailure("absent")
        return {"Config": {"Labels": {LAUNCH_LABEL: self.containers[arguments[1]]}}}


@pytest.fixture(autouse=True)
def no_accelerator(monkeypatch):
    monkeypatch.setattr(accelerator_runtime, "_allocation_document", lambda: None)


class Controller:
    """A controller identity that is alive for `alive_polls` polls, then gone."""

    def __init__(self, alive_polls, cli):
        self.remaining, self.cli, self.seen = alive_polls, cli, []

    def identify(self, pid):
        return "start:1" if self.remaining > 0 else None

    def sleep(self, _seconds):
        # Every poll while alive, the container is still there.
        self.seen.append(NAME in self.cli.containers)
        self.remaining -= 1


def test_the_container_is_removed_once_the_controller_is_gone():
    cli = FakeDocker({NAME: LAUNCH})
    controller = Controller(5, cli)
    code = watch(
        NAME,
        LAUNCH,
        4242,
        "start:1",
        cli=cli,
        identify=controller.identify,
        sleep=controller.sleep,
    )
    assert code == 0
    assert controller.seen == [True] * 5
    assert NAME not in cli.containers and ("rm", NAME) in cli.mutations


def test_nothing_is_removed_while_the_controller_lives():
    class Enough(Exception):
        pass

    cli = FakeDocker({NAME: LAUNCH})
    polls = []

    def sleep(_seconds):
        polls.append(1)
        if len(polls) == 200:
            raise Enough

    with pytest.raises(Enough):
        watch(
            NAME,
            LAUNCH,
            4242,
            "start:1",
            cli=cli,
            identify=lambda _: "start:1",
            sleep=sleep,
        )
    assert cli.mutations == [] and cli.containers == {NAME: LAUNCH}


def test_a_reused_pid_is_not_the_controller():
    """The same pid started at another time is another process: the owner
    is gone, and the container goes."""
    cli = FakeDocker({NAME: LAUNCH})
    assert (
        watch(
            NAME,
            LAUNCH,
            4242,
            "start:1",
            cli=cli,
            identify=lambda _: "start:999",
            sleep=lambda _: None,
        )
        == 0
    )
    assert NAME not in cli.containers


def test_a_container_under_another_launch_label_is_never_removed():
    cli = FakeDocker({NAME: OTHER})
    assert (
        watch(
            NAME,
            LAUNCH,
            4242,
            "start:1",
            cli=cli,
            identify=lambda _: None,
            sleep=lambda _: None,
        )
        == 0
    )
    assert cli.mutations == [] and cli.containers == {NAME: OTHER}
    # Specimen: the same dead controller, the matching label, and it goes.
    cli = FakeDocker({NAME: LAUNCH})
    assert (
        watch(
            NAME,
            LAUNCH,
            4242,
            "start:1",
            cli=cli,
            identify=lambda _: None,
            sleep=lambda _: None,
        )
        == 0
    )
    assert NAME not in cli.containers


def test_the_removal_itself_refuses_another_launchs_container():
    """Below the reaper's own check: remove_exact_container compares the
    label again, so a container relabelled between the two is kept."""
    cli = FakeDocker({NAME: LAUNCH})
    original = cli.json

    def relabelled(arguments, *, timeout=30):
        cli.containers[NAME] = OTHER
        return original(arguments, timeout=timeout)

    cli.json = relabelled
    assert (
        watch(
            NAME,
            LAUNCH,
            4242,
            "start:1",
            cli=cli,
            identify=lambda _: None,
            sleep=lambda _: None,
        )
        == 3
    )
    assert cli.mutations == [] and cli.containers == {NAME: OTHER}


def test_a_finished_run_ends_the_reaper_without_touching_anything():
    cli = FakeDocker({})
    assert (
        watch(
            NAME,
            LAUNCH,
            4242,
            "start:1",
            cli=cli,
            identify=lambda _: None,
            sleep=lambda _: None,
        )
        == 0
    )
    assert cli.mutations == []


def test_an_unanswering_runtime_is_not_absence():
    """A daemon that cannot answer has not shown the container gone, and has
    not shown whose it is: keep watching, remove nothing."""

    class Enough(Exception):
        pass

    cli = FakeDocker({NAME: LAUNCH}, unanswering=True)
    polls = []

    def sleep(_seconds):
        polls.append(1)
        if len(polls) == 3:
            raise Enough

    with pytest.raises(Enough):
        watch(
            NAME, LAUNCH, 4242, "start:1", cli=cli, identify=lambda _: None, sleep=sleep
        )
    assert cli.mutations == []


def test_bad_arguments_are_refused():
    assert main([]) == 2
    assert main(["bad name!", LAUNCH, "1", "x"]) == 2
    assert main([NAME, "not-a-digest", "1", "x"]) == 2
    assert main([NAME, LAUNCH, "pid", "x"]) == 2


def test_a_real_process_identity_is_stable_and_ends_with_the_process():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        identity = process_identity(child.pid)
        assert identity is not None and process_identity(child.pid) == identity
        assert identity != process_identity(0) and process_identity(0) is None
        child.kill()
        # Exited but not yet reaped: a zombie is gone, not alive.
        deadline = time.monotonic() + 10
        while process_identity(child.pid) is not None:
            assert time.monotonic() < deadline
            time.sleep(0.05)
    finally:
        child.kill()
        child.wait()
    assert process_identity(child.pid) is None


def test_the_guard_is_this_process_and_a_foreign_guard_is_refused():
    guard = liveness_reaper.controller_guard()
    assert guard["kind"] == "CONTROLLER_LIVENESS"
    assert guard["identity"] == process_identity(guard["pid"])
    with pytest.raises(WorkerFailure):
        liveness_reaper.spawn_liveness_reaper(
            container_name=NAME,
            launch_digest=LAUNCH,
            guard={**guard, "identity": "start:someone-else"},
        )


@pytest.mark.parametrize("seconds", [None, 3600])
def test_the_miner_lane_records_and_starts_its_guard(tmp_path, monkeypatch, seconds):
    spawned = []
    monkeypatch.setattr(research_carrier, "_check_cancel", lambda *_: None)
    monkeypatch.setattr(
        miner_container, "MinerResearchLaunch", lambda *a: SimpleNamespace()
    )
    monkeypatch.setattr(miner_container, "prepare_scratch", lambda d: d)
    monkeypatch.setattr(miner_container, "create_arguments", lambda _: ["create"])
    monkeypatch.setattr(
        liveness_reaper,
        "spawn_liveness_reaper",
        lambda **kw: spawned.append(("liveness", kw)),
    )
    monkeypatch.setattr(
        research_carrier,
        "spawn_watchdog",
        lambda **kw: spawned.append(("deadline", kw)),
    )

    class Lane(FakeDocker):
        def run(self, arguments, *, timeout=30, accepted=(0,)):
            if arguments == ["create"]:
                self.containers[NAME] = LAUNCH
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
            if arguments[0] == "start":
                # Every run starts guarded: the guard is up before start.
                assert spawned
                raise RuntimeError("stop the fixture here")
            return super().run(arguments, timeout=timeout, accepted=accepted)

    cli = Lane()
    operation = tmp_path / "operation"
    operation.mkdir()
    with pytest.raises(RuntimeError, match="stop the fixture"):
        research_carrier._run_miner_lane(
            None,
            owner="miner",
            identity="op-1",
            operation=operation,
            stage=None,
            name=NAME,
            cli=cli,
            image=SimpleNamespace(image_id="sha256:" + "c" * 64),
            launch=LAUNCH,
            request={},
            seconds=seconds,
            started=time.monotonic(),
            started_unix=int(time.time()),
            bootstrap="",
            output_validator=None,
            provenance="fixture",
            resources={},
        )
    intent = json.loads((operation / "intent.json").read_bytes())
    assert NAME not in cli.containers  # the lane's own cleanup still ran
    if seconds is None:
        guard = liveness_reaper.controller_guard()
        assert intent["deadline_unix"] is None and intent["reaper"] == guard
        assert spawned == [
            (
                "liveness",
                {"container_name": NAME, "launch_digest": LAUNCH, "guard": guard},
            )
        ]
    else:
        assert intent["reaper"] == {"kind": "DEADLINE"}
        assert [kind for kind, _ in spawned] == ["deadline"]
