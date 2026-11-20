"""A door restart never cancels an in-flight remote GPU build (owner, 20 Nov 2026; live 116 01:52Z: ~22 builds cancelled
and re-run from zero). Head B of codex-queue/reports/DOOR_CODE/BUILD_REATTACH_DESIGN_20261120.md: a stopping receiver
leaves a task whose remote build program runs on (`DETACHABLE_FRONT`) RUNNING, and the next start adopts that op when
every condition holds (`adoptable`), else settles it as before. Real processes for the in-container scripts; fixture
doubles for the ledger, the box and the providers. The restart on a real box is the rehearsal named in the design.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_receiver
from carbon.development_session import research_carrier as carrier
from carbon.development_session import research_tasks
from carbon.development_session.profile import canonical, digest
from carbon.reconstruction import remote_gpu_build
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure
from carbon.research import DirectTaskStateV3

pytestmark = pytest.mark.skipif(os.name != "posix", reason="fork, pipes and /proc")

CAP = 1024**2 + 1
OWNER, IDENTITY = "5Owner", "rtsk_" + "a" * 64 + "~build"


def _boot(program):
    return (
        "import os,sys\n"
        f"os.execv(sys.executable,[sys.executable,'-I','-c',{program!r}])\n"
    )


def _front(boot, run, **kwargs):
    return subprocess.Popen(
        [sys.executable, "-I", "-c", carrier.DETACHABLE_FRONT, boot, str(run)]
        + [str(CAP), str(CAP)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )


def _wait(run):
    return subprocess.run(
        [sys.executable, "-I", "-c", carrier.DETACHABLE_WAIT, str(run)],
        capture_output=True,
        timeout=60,
        check=False,
    )


# -- the wait mode: what an adopting door reads ---------------------------------------------------------------------


def test_the_wait_mode_reads_exactly_what_the_front_end_relayed(tmp_path):
    run = tmp_path / "run"
    program = (
        "import sys\nsys.stdout.write('built');sys.stderr.write('note');sys.exit(3)"
    )
    front = _front(_boot(program), run)
    out, err = front.communicate(timeout=60)
    adopted = _wait(run)
    assert (
        (adopted.returncode, adopted.stdout, adopted.stderr)
        == (
            front.returncode,
            out,
            err,
        )
        == (3, b"built", b"note")
    )


def test_the_wait_mode_waits_for_a_program_that_still_runs(tmp_path):
    """The door that streamed it is gone (its streams closed); the next start's wait reads the result when it ends."""
    run = tmp_path / "run"
    program = "import sys,time\ntime.sleep(1.0)\nprint('done')\nsys.exit(4)"
    front = _front(_boot(program), run)
    front.stdout.close()
    front.stderr.close()
    while not (run / "front.pid").exists():
        time.sleep(0.05)
    adopted = _wait(run)
    assert front.wait(timeout=60) == 4
    assert (adopted.returncode, adopted.stdout) == (4, b"done\n")
    assert int((run / "front.pid").read_text()) == front.pid


def test_a_front_end_gone_without_a_status_is_read_as_lost_never_as_the_programs(
    tmp_path,
):
    run = tmp_path / "run"
    run.mkdir()
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    (run / "front.pid").write_text(str(dead.pid))
    adopted = _wait(run)
    assert adopted.returncode == 254
    assert carrier.PROGRAM_LOST in adopted.stderr


def test_an_adopted_op_runs_the_wait_mode_and_every_other_command_is_unchanged():
    assert carrier._program_command(
        "c1", "boot", detachable=True, maximum=10, adopting=True
    ) == [
        "exec",
        "c1",
        "/opt/carbon-worker/bin/python",
        "-I",
        "-c",
        carrier.DETACHABLE_WAIT,
        carrier.DETACHABLE_RUN_DIR,
    ]
    assert carrier._program_command("c1", "boot", detachable=False, maximum=10)[5] == (
        "boot"
    )


# -- the stop --------------------------------------------------------------------------------------------------------


def test_a_stream_cut_by_the_stop_is_detached_and_nothing_else_is(monkeypatch):
    monkeypatch.setattr(carrier, "_STOP_ANNOUNCE_SECONDS", 0.3)
    cut = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=-15\nstderr:\n")
    own = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\nstderr:\nboom")
    # no stop: a program's own failure is read at once, and a cut client without a stop is not a stop
    started = time.monotonic()
    assert carrier._detached_by_stop(own) is False
    assert time.monotonic() - started < 0.2
    assert carrier._detached_by_stop(cut) is False
    # the client died a moment before this process read its own signal: announced within the window
    threading.Timer(0.1, carrier.announce_stop).start()
    assert carrier._detached_by_stop(cut) is True
    # once announced, any failure of a detachable op is the stop's
    assert carrier._detached_by_stop(own) is True


def test_a_stopping_door_ends_only_its_own_clients_of_detachable_programs(tmp_path):
    name = "carbon-d4-" + "b" * 24
    sleeper = "import time\ntime.sleep(60)"
    program_client = subprocess.Popen([sys.executable, "-c", sleeper, "exec", name])
    other_client = subprocess.Popen([sys.executable, "-c", sleeper, "inspect", name])
    unrelated = subprocess.Popen([sys.executable, "-c", sleeper, "exec", "other"])
    try:
        carrier._LIVE_PROGRAMS.add(name)
        carrier.door_stopping()
        assert program_client.wait(timeout=10) == -15
        assert carrier._STOPPING.is_set()
        time.sleep(0.2)
        assert other_client.poll() is None and unrelated.poll() is None
    finally:
        for process in (program_client, other_client, unrelated):
            if process.poll() is None:
                process.kill()
                process.wait()


def test_a_client_that_outlives_its_sigterm_is_killed_within_the_release_window(
    tmp_path,
):
    """Live 116, 20 Nov 2026: one docker client outlived the receiver and systemd waited its 90 s stop timeout."""
    name = "carbon-d4-" + "c" * 24
    stubborn = (
        "import signal,sys,time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('ready', flush=True)\n"
        "time.sleep(60)"
    )
    client = subprocess.Popen(
        [sys.executable, "-c", stubborn, "exec", name], stdout=subprocess.PIPE
    )
    try:
        assert client.stdout.readline() == b"ready\n"
        carrier._LIVE_PROGRAMS.add(name)
        started = time.monotonic()
        carrier.door_stopping()
        assert client.wait(timeout=10) == -9
        assert time.monotonic() - started < carrier._STREAM_RELEASE_SECONDS + 3
    finally:
        if client.poll() is None:
            client.kill()
            client.wait()
        client.stdout.close()


def test_a_stopping_door_starts_no_remote_build_and_its_slot_wait_ends():
    carrier.announce_stop()
    with pytest.raises(carrier.Detached):
        carrier._raise_if_stopping()
    # never an error of the op: no `except Exception` reads it
    assert not issubclass(carrier.Detached, Exception)


# -- what a start may adopt --------------------------------------------------------------------------------------------


class _Ledger:
    def __init__(self, root, state="RESERVED"):
        self.root = root
        self.state = state

    def operation_state(self, identity, *, owner):
        return self.state if (identity, owner) == (IDENTITY, OWNER) else None


def _operation(tmp_path, *, detachable=True, started=True, left=600.0):
    request = {"provenance": "LIBRARY_BUILD", "program": "p"}
    launch = digest(
        canonical({"owner": OWNER, "identity": IDENTITY, "request": request})
    )
    name = "carbon-d4-" + launch[7:31]
    operation = tmp_path / ("operation-" + launch[7:])
    operation.mkdir()
    intent = {
        "launch": launch,
        "container": name,
        "request": request,
        "owner": OWNER,
        "identity": IDENTITY,
        "deadline_unix": time.time() + left,
        "remote_gpu_build": {
            "docker_host": "ssh://carbon@box",
            "stage_root": "/srv/stage",
            "lane": 0,
            "slot": 1,
            "box": "box-a",
        },
        **({"detachable_program": 1} if detachable else {}),
    }
    (operation / "intent.json").write_bytes(canonical(intent))
    if started:
        (operation / "program-started").write_bytes(b"")
    slot_dir = tmp_path / "slot-1"
    slot_dir.mkdir()
    (slot_dir / "active-allocation.json").write_text(
        json.dumps({"container_name": name, "launch_digest": launch})
    )
    binding = SimpleNamespace(
        gone=False, slot_dir=slot_dir, docker_host="ssh://carbon@box"
    )
    return name, binding


@pytest.fixture
def box(monkeypatch):
    running = set()
    monkeypatch.setattr(carrier, "_running_on_box", lambda binding: frozenset(running))
    # the fixture binding is not an `OpBinding`: its slot class is read as recorded (tested below on real bindings)
    monkeypatch.setattr(
        carrier.remote_gpu_build, "as_recorded", lambda binding, request: binding
    )
    return running


def test_a_start_adopts_an_op_only_when_every_condition_holds(
    tmp_path, monkeypatch, box
):
    name, binding = _operation(tmp_path)
    monkeypatch.setattr(carrier.remote_gpu_build, "recorded", lambda intent: binding)
    ledger = _Ledger(tmp_path)
    # its container is not running on its box: not adopted
    assert carrier.adoptable(ledger, owner=OWNER, identity=IDENTITY) is None
    box.add(name)
    assert carrier.adoptable(ledger, owner=OWNER, identity=IDENTITY) is binding
    assert carrier.program_runs_on(ledger, owner=OWNER, identity=IDENTITY) is True
    # registered: the settles of dead or previous runs leave it, its run adopts it, then it is forgotten
    assert carrier.register_adoptable(ledger, owner=OWNER, identity=IDENTITY) is None
    assert carrier._adoption(ledger, IDENTITY) is binding
    carrier.forget_adoption(ledger, IDENTITY)
    assert carrier._adoption(ledger, IDENTITY) is None
    # the op is no longer RESERVED
    assert (
        carrier.adoptable(
            _Ledger(tmp_path, "SUCCEEDED"), owner=OWNER, identity=IDENTITY
        )
        is None
    )
    # its box is gone for the door
    monkeypatch.setattr(
        carrier.remote_gpu_build,
        "recorded",
        lambda intent: SimpleNamespace(**{**vars(binding), "gone": True}),
    )
    assert carrier.adoption_check(ledger, owner=OWNER, identity=IDENTITY) == (
        None,
        "box_gone",
    )
    # its binding cannot give the request it reserved
    monkeypatch.setattr(carrier.remote_gpu_build, "recorded", lambda intent: binding)
    monkeypatch.setattr(
        carrier.remote_gpu_build, "as_recorded", lambda binding, request: None
    )
    assert carrier.adoption_check(ledger, owner=OWNER, identity=IDENTITY) == (
        None,
        "slot_class_differs",
    )


@pytest.mark.parametrize(
    "broken", ["not_detachable", "never_started", "deadline_near", "slot_names_another"]
)
def test_any_doubt_settles_the_op_as_before(tmp_path, monkeypatch, box, broken):
    name, binding = _operation(
        tmp_path,
        detachable=broken != "not_detachable",
        started=broken != "never_started",
        left=60.0 if broken == "deadline_near" else 600.0,
    )
    if broken == "slot_names_another":
        (binding.slot_dir / "active-allocation.json").write_text(
            json.dumps({"container_name": "carbon-d4-other", "launch_digest": "x"})
        )
    box.add(name)
    monkeypatch.setattr(carrier.remote_gpu_build, "recorded", lambda intent: binding)
    ledger = _Ledger(tmp_path)
    assert carrier.adoptable(ledger, owner=OWNER, identity=IDENTITY) is None
    assert carrier.register_adoptable(ledger, owner=OWNER, identity=IDENTITY) == {
        "not_detachable": "not_detachable",
        "never_started": "not_started",
        "deadline_near": "deadline_near",
        "slot_names_another": "slot_record_differs",
    }[broken]
    if broken in ("not_detachable", "never_started"):
        # a stopping door cancels it as before
        assert carrier.program_runs_on(ledger, owner=OWNER, identity=IDENTITY) is False


def _box_binding(*, slots=7, memory="capped", slot=1, device="sha256:" + "d" * 64):
    spec = remote_gpu_build.GpuBuildSpec(
        0,
        "ssh://carbon@box",
        "/srv/stage",
        remote_gpu_build.BOX_SLOT_CPUSETS,
        "box-a",
    )
    lane = remote_gpu_build.DoorLane(
        spec, slots, SimpleNamespace(digest=device), "/nowhere/box-a", memory
    )
    return remote_gpu_build.OpBinding(lane, slot)


@pytest.mark.parametrize("memory", ["shared", "capped"])
def test_an_adopted_binding_takes_the_slot_class_its_reservation_recorded(memory):
    """Live 116, 20 Nov 2026: the box's own record reads ``capped``, the pool's class was ``shared``, and both adopted
    builds ended in "operation replay conflict" at their re-reservation."""
    ran = _box_binding(memory=memory)
    request = {
        "accelerator": {
            "kind": "MINER_OWN_GPU",
            "device": "sha256:" + "d" * 64,
            **remote_gpu_build.request_fields(ran),
        }
    }
    want = remote_gpu_build.request_fields(ran)
    for read in (_box_binding(memory="capped"), _box_binding(memory="shared")):
        rebound = remote_gpu_build.as_recorded(read, request)
        assert rebound.lane.memory == memory and rebound.slot == read.slot
        assert rebound.slot_dir == read.slot_dir
        assert remote_gpu_build.request_fields(rebound) == want


def test_an_adopted_binding_that_cannot_give_its_request_is_refused():
    read = _box_binding()
    accelerator = {
        "device": "sha256:" + "d" * 64,
        **remote_gpu_build.request_fields(_box_binding(memory="shared")),
    }
    assert remote_gpu_build.as_recorded(read, {"accelerator": accelerator}) is not None
    # another device
    assert (
        remote_gpu_build.as_recorded(
            read, {"accelerator": {**accelerator, "device": "sha256:" + "e" * 64}}
        )
        is None
    )
    # a slot the recorded class has no room for
    assert (
        remote_gpu_build.as_recorded(
            _box_binding(slot=3),
            {"accelerator": {**accelerator, "remote_gpu_slots": 2}},
        )
        is None
    )
    # a memory record no class gives
    assert (
        remote_gpu_build.as_recorded(
            read, {"accelerator": {**accelerator, "slot_memory": {"fraction": "x"}}}
        )
        is None
    )
    # one slot: no class fields at all
    one = remote_gpu_build.as_recorded(
        _box_binding(slot=0), {"accelerator": {"device": accelerator["device"]}}
    )
    assert one.lane.slots == 1 and remote_gpu_build.request_fields(one) == {}
    assert remote_gpu_build.as_recorded(read, {}) is None
    assert remote_gpu_build.as_recorded(SimpleNamespace(), {"accelerator": {}}) is None


def test_the_box_is_listed_once_per_start(monkeypatch):
    calls = []

    class _Cli:
        def run(self, arguments, timeout):
            calls.append(arguments)
            return SimpleNamespace(stdout=b"carbon-d4-one\ncarbon-d4-two\n")

    monkeypatch.setattr(carrier.remote_gpu_build, "cli", lambda binding: _Cli())
    monkeypatch.setattr(
        carrier.remote_gpu_build,
        "bound",
        lambda binding: contextlib.nullcontext(binding),
    )
    binding = SimpleNamespace(docker_host="ssh://carbon@box")
    first = carrier._running_on_box(binding)
    second = carrier._running_on_box(binding)
    assert first == second == frozenset({"carbon-d4-one", "carbon-d4-two"})
    assert len(calls) == 1


# -- the task: left RUNNING at the stop, resumed at the start -----------------------------------------------------


class _Provider:
    def __init__(self, states, state=DirectTaskStateV3.RUNNING):
        self.owner = OWNER
        self.ledger = SimpleNamespace(
            operation_state=lambda child, owner: states.get(child),
            root=Path("/nowhere"),
        )
        self._lock = threading.RLock()
        self.task = SimpleNamespace(value="rtsk_" + "c" * 64)
        self._views = {self.task.value: SimpleNamespace(state=state, task_id=self.task)}
        self._children_ids = tuple(states)

    def _all_children(self, task_id):
        return self._children_ids

    def _probe_children(self, task_id):
        return ()


@pytest.mark.parametrize(
    ("states", "adopt", "resumed"),
    [
        ({"build": "RESERVED", "prep": "SUCCEEDED", "infer": None}, True, True),
        ({"build": "RESERVED"}, False, False),
        ({"build": "RESERVED", "prep": "FAILED_INFRA"}, True, False),
        ({"build": "RESERVED", "infer": "RESERVED"}, True, False),
        ({"build": "SUCCEEDED"}, True, False),
    ],
)
def test_a_running_task_is_resumed_only_with_one_adoptable_op_and_nothing_failed(
    monkeypatch, states, adopt, resumed
):
    asked, lines = [], []

    def register(ledger, owner, identity):
        asked.append(identity)
        return None if adopt else "not_running_on_box"

    monkeypatch.setattr(carrier, "register_adoptable", register)
    monkeypatch.setattr(
        research_tasks,
        "_log_build",
        lambda event, task_id, **fields: lines.append((event, task_id.value, fields)),
    )
    provider = _Provider(states)
    task = provider.task
    assert (
        research_tasks.DirectDevelopmentTasksV3._adopt_on_restore(provider, task)
        is resumed
    )
    assert research_tasks.DirectDevelopmentTasksV3.resumable(provider, task) is resumed
    if resumed:
        assert asked == ["build"]
    # one journal line per RUNNING task a start finds: resumed, or settled and why
    [(event, logged, fields)] = lines
    assert (event, logged) == ("build_adoption", task.value)
    assert fields["decision"] == ("resume" if resumed else "settle")
    assert (fields["reason"] is None) is resumed


@pytest.mark.parametrize(("runs_on", "left"), [(True, True), (False, False)])
def test_a_stopping_door_leaves_a_running_build_whose_program_runs_on(
    monkeypatch, runs_on, left
):
    monkeypatch.setattr(
        carrier, "program_runs_on", lambda ledger, owner, identity: runs_on
    )
    lines = []
    monkeypatch.setattr(
        research_tasks,
        "_log_build",
        lambda event, task_id, **fields: lines.append((event, task_id.value)),
    )
    provider = _Provider({"build": "RESERVED", "prep": "SUCCEEDED"})
    task = provider.task
    for _ in range(2):
        assert (
            research_tasks.DirectDevelopmentTasksV3.detached_build(provider, task)
            is left
        )
    assert research_tasks.DirectDevelopmentTasksV3.detached(provider, task) is left
    # one journal line per build the stop leaves running, however often it is asked
    assert lines == ([("build_left_running", task.value)] if left else [])
    # a QUEUED task is never left (it holds nothing; kept QUEUED by the stop as before)
    queued = _Provider({"build": "RESERVED"}, state=DirectTaskStateV3.QUEUED)
    assert (
        research_tasks.DirectDevelopmentTasksV3.detached_build(queued, queued.task)
        is False
    )


def test_the_stop_cancels_every_running_task_except_one_left_for_the_next_start(
    monkeypatch, tmp_path
):
    announced, recorded = [], []
    monkeypatch.setattr(carrier, "door_stopping", lambda: announced.append(True))
    monkeypatch.setattr(
        direct_receiver,
        "_record_stop_cancelled",
        lambda root, tasks: recorded.extend(tasks),
    )

    class _Owner:
        def __init__(self, task, left):
            self._lock = threading.RLock()
            self.task = SimpleNamespace(value=task)
            self._views = {
                task: SimpleNamespace(
                    state=DirectTaskStateV3.RUNNING, task_id=self.task
                )
            }
            self.left = left
            self.cancelled = []

        def detached_build(self, task_id):
            return self.left

        def cancel_observed_task(self, task_id, key):
            self.cancelled.append(task_id.value)

    kept, cancelled = _Owner("rtsk_kept", True), _Owner("rtsk_cut", False)
    door = SimpleNamespace(
        _lock=threading.RLock(),
        _providers={"a": kept, "b": cancelled},
        _closing=False,
        discovery=SimpleNamespace(info=SimpleNamespace(challenge_key="k")),
        root=tmp_path / "owners",
    )
    direct_receiver.OwnerProviders.cancel(door)
    assert announced == [True]  # the stop is announced before any task is looked at
    assert kept.cancelled == [] and cancelled.cancelled == ["rtsk_cut"]
    # both are in the stop's record: one the next start cannot adopt re-runs at its place as before
    assert sorted(recorded) == ["rtsk_cut", "rtsk_kept"]


def test_the_close_accepts_a_task_left_for_the_next_start_and_nothing_else(monkeypatch):
    class _Owner:
        def __init__(self, left):
            self.task = SimpleNamespace(value="rtsk_x")
            self._views = {"rtsk_x": SimpleNamespace(task_id=self.task)}
            self.left = left
            self.closed = False
            self.ledger = SimpleNamespace(generation=1)

        def requires_reconciliation(self, task_id):
            return True

        def detached(self, task_id):
            return self.left

        def close(self):
            self.closed = True

    class _Control:
        def settled(self, generation, **kwargs):
            return "RECONCILIATION_REQUIRED"

    left = _Owner(True)
    door = SimpleNamespace(_providers={"a": left}, _controls={"a": _Control()})
    direct_receiver.OwnerProviders.close(door)
    assert left.closed
    held = SimpleNamespace(_providers={"a": _Owner(False)}, _controls={})
    with pytest.raises(direct_receiver.ReceiverUnavailable):
        direct_receiver.OwnerProviders.close(held)


def test_a_second_cancel_of_the_same_stop_neither_cancels_nor_relists_a_left_task(
    monkeypatch, tmp_path
):
    """Live 116, 20 Nov 2026: `serve` cancels at the stop and its last step cancels again; the left task was listed in
    the stop's record twice."""
    recorded = []
    monkeypatch.setattr(carrier, "door_stopping", lambda: None)
    monkeypatch.setattr(
        direct_receiver,
        "_record_stop_cancelled",
        lambda root, tasks: recorded.append(list(tasks)),
    )

    class _Owner:
        def __init__(self):
            self._lock = threading.RLock()
            self.task = SimpleNamespace(value="rtsk_kept")
            self._views = {
                "rtsk_kept": SimpleNamespace(
                    state=DirectTaskStateV3.RUNNING, task_id=self.task
                )
            }
            self.left = set()
            self.cancelled = []

        def detached_build(self, task_id):
            self.left.add(task_id.value)
            return True

        def detached(self, task_id):
            return task_id.value in self.left

        def cancel_observed_task(self, task_id, key):
            self.cancelled.append(task_id.value)

    owner = _Owner()
    door = SimpleNamespace(
        _lock=threading.RLock(),
        _providers={"a": owner},
        _closing=False,
        discovery=SimpleNamespace(info=SimpleNamespace(challenge_key="k")),
        root=tmp_path / "owners",
    )
    direct_receiver.OwnerProviders.cancel(door)
    direct_receiver.OwnerProviders.cancel(door)
    assert recorded == [["rtsk_kept"], []]
    assert owner.cancelled == []


def test_a_resumed_build_logs_how_its_task_ended(monkeypatch):
    lines = []
    monkeypatch.setattr(
        research_tasks,
        "_log_build",
        lambda event, task_id, **fields: lines.append((event, task_id.value, fields)),
    )

    class _Tasks:
        def __init__(self, raises):
            self._lock = threading.RLock()
            self.raises = raises
            self._views = {}

        def run_queued_task(self, task_id, *, resume):
            assert resume is True
            self._views[task_id.value] = SimpleNamespace(
                state=DirectTaskStateV3.SUCCEEDED
            )
            if self.raises:
                raise WorkerFailure(WorkerCode.UNAVAILABLE)
            return "done"

    task = SimpleNamespace(value="rtsk_" + "d" * 64)
    resume = research_tasks.DirectDevelopmentTasksV3.resume_task
    assert resume(_Tasks(False), task) == "done"
    with pytest.raises(WorkerFailure):
        resume(_Tasks(True), task)
    state = DirectTaskStateV3.SUCCEEDED.value
    assert lines == [
        ("build_resumed", task.value, {"state": state, "failure": None}),
        ("build_resumed", task.value, {"state": state, "failure": "WorkerFailure"}),
    ]
