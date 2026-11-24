"""S6c (21 Nov 2026): a docker call to a GPU build BOX opens its own ssh connection through the box's wrapper, so every
bound on such a call gets `remote_gpu_build.BOX_LINK_SECONDS` more; a call on this host keeps its bound exactly, and so
does every program or export STREAM: its bound is the op's wall, which must end before the op's watchdog does.
"""

from __future__ import annotations

import inspect
import re
import subprocess
from types import SimpleNamespace

import pytest

from carbon.development_session import research_carrier as carrier
from carbon.reconstruction import remote_gpu_build
from carbon.reconstruction.worker import docker_runtime
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure


def _box_binding(tmp_path):
    spec = SimpleNamespace(
        local=False, docker_host="ssh://carbon@203.0.113.7", stage_root="/home/carbon"
    )
    lane = SimpleNamespace(spec=spec)
    return SimpleNamespace(lane=lane, docker_host=spec.docker_host)


def test_a_box_call_gets_the_link_allowance_and_a_local_one_does_not(
    tmp_path, monkeypatch
):
    seen = []

    def capture(command, *, environment, timeout, maximum, cwd=None):
        seen.append(timeout)
        return subprocess.CompletedProcess(command, 0, b"{}", b"")

    monkeypatch.setattr(docker_runtime, "_bounded_capture", capture)
    monkeypatch.setattr(remote_gpu_build, "wrapper", lambda lane: tmp_path / "docker")
    box = remote_gpu_build.cli(_box_binding(tmp_path))
    box.run(["exec", "c", "/bin/cat", "/sys/fs/cgroup/pids.max"], timeout=10)
    box.json(["inspect", "c"], timeout=30)
    assert seen == [
        10 + remote_gpu_build.BOX_LINK_SECONDS,
        30 + remote_gpu_build.BOX_LINK_SECONDS,
    ]
    seen.clear()
    docker_runtime.DockerCLI().run(["ps"], timeout=10)
    assert seen == [10]
    local = SimpleNamespace(lane=SimpleNamespace(spec=SimpleNamespace(local=True)))
    assert (
        remote_gpu_build.cli(local) is None
    )  # a local slot lane: this host's own CLI, its bounds as they are


# -- a stream's bound is the op's wall (live-ops 7142, 24 Nov 2026) ----------------------------------------------------------------


def test_a_box_stream_keeps_its_bound_exactly(tmp_path, monkeypatch):
    seen = []

    def stream(self, arguments, destination, *, maximum, timeout):
        seen.append((arguments, maximum, timeout))
        return 7

    monkeypatch.setattr(docker_runtime.DockerCLI, "stream_to_file", stream)
    monkeypatch.setattr(remote_gpu_build, "wrapper", lambda lane: tmp_path / "docker")
    box = remote_gpu_build.cli(_box_binding(tmp_path))
    assert box.stream_to_file(["exec"], tmp_path / "x", maximum=5, timeout=903) == 7
    assert seen == [(["exec"], 5, 903)]


def test_the_program_s_wall_ends_before_its_watchdog_does_with_any_call_allowance():
    """The carrier's own numbers: the stream ends at ``seconds - 45``, the watchdog acts at ``seconds - 30``. An allowance
    on the stream as large as the one a call gets would end it after the watchdog."""
    text = inspect.getsource(carrier._run_locked)
    (program,) = re.findall(
        r"program_timeout = max\(1, seconds - (\d+) - \(program_started", text
    )
    watchdogs = set(
        re.findall(r"deadline_unix=float\(started_unix \+ seconds - (\d+)\)", text)
    )
    assert watchdogs == {"30"}
    gap = int(program) - 30
    assert gap == 15 and remote_gpu_build.BOX_LINK_SECONDS > gap


# -- the op's own failure is kept when its watchdog removed the container first ------------------------------------------------------


NAME, LAUNCH = "carbon-d4-" + "a" * 24, "sha256:" + "a" * 64


class _Cli:
    def __init__(self, listed=b"", failing=False):
        self.listed, self.failing, self.asked = listed, failing, []

    def run(self, arguments, *, timeout=30, accepted=(0,)):
        self.asked.append(arguments)
        if self.failing:
            raise WorkerFailure(WorkerCode.RUNTIME)
        return subprocess.CompletedProcess(arguments, 0, self.listed, b"")


@pytest.fixture
def box(tmp_path, monkeypatch):
    slot = tmp_path / "slot-0"
    slot.mkdir()
    binding = SimpleNamespace(slot_dir=slot)
    monkeypatch.setattr(remote_gpu_build, "remote_box", lambda: binding)
    return slot


def _refuse(monkeypatch, code=WorkerCode.CLEANUP):
    def remove(**kwargs):
        raise WorkerFailure(code)

    monkeypatch.setattr(carrier, "remove_exact_container", remove)


def test_a_container_its_watchdog_already_removed_keeps_the_op_s_own_failure(
    box, monkeypatch
):
    _refuse(monkeypatch)
    cli = _Cli()
    carrier._remove_own_container(cli, NAME, LAUNCH)
    assert cli.asked == [["ps", "-aq", "--filter", "name=^" + NAME + "$"]]
    # so the failure on its way out is the one raised, as a `finally` sees it
    with pytest.raises(WorkerFailure) as caught:
        try:
            raise WorkerFailure(
                WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
            )
        finally:
            carrier._remove_own_container(cli, NAME, LAUNCH)
    assert caught.value.private_diagnostic == b"stream command timed out"


def test_anything_uncertain_is_still_refused(box, monkeypatch):
    _refuse(monkeypatch)
    for cli in (_Cli(listed=b"0123456789ab\n"), _Cli(failing=True)):
        with pytest.raises(WorkerFailure) as caught:
            carrier._remove_own_container(cli, NAME, LAUNCH)
        assert caught.value.code is WorkerCode.CLEANUP
    # the slot's record is still there: nothing finished it
    (box / "active-allocation.json").write_bytes(b"{}")
    cli = _Cli()
    with pytest.raises(WorkerFailure):
        carrier._remove_own_container(cli, NAME, LAUNCH)
    assert cli.asked == []
    # another failure is never read as one of these
    (box / "active-allocation.json").unlink()
    _refuse(monkeypatch, WorkerCode.RUNTIME)
    with pytest.raises(WorkerFailure) as caught:
        carrier._remove_own_container(_Cli(), NAME, LAUNCH)
    assert caught.value.code is WorkerCode.RUNTIME


def test_a_launch_on_this_host_is_never_read_this_way(monkeypatch):
    monkeypatch.setattr(remote_gpu_build, "remote_box", lambda: None)
    _refuse(monkeypatch)
    cli = _Cli()
    with pytest.raises(WorkerFailure) as caught:
        carrier._remove_own_container(cli, NAME, LAUNCH)
    assert caught.value.code is WorkerCode.CLEANUP and cli.asked == []


def test_a_clean_removal_asks_nothing_more(monkeypatch):
    removed = []
    monkeypatch.setattr(
        carrier, "remove_exact_container", lambda **kwargs: removed.append(kwargs)
    )
    cli = _Cli()
    carrier._remove_own_container(cli, NAME, LAUNCH)
    assert removed == [{"cli": cli, "container_name": NAME, "launch_digest": LAUNCH}]
    assert cli.asked == []
