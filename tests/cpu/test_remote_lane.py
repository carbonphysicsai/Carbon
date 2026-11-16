"""A grade lane on another machine (`carbon.reconstruction.remote_lane`; owner's order Sun 15 Nov 2026 via the Lead):
the round's worker containers go to the lane's ssh docker daemon, its inputs are mirrored to the same path there, the
speed stage stays on the grading host, and a link fault is Carbon's (FAILED_INFRA), never the candidate's. No ssh, no
docker: every process boundary is faked.
"""

from __future__ import annotations

import io
import json
import os
import tarfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.reconstruction import grade_lanes, remote_lane
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

HOST = "ssh://carbon-grade@grader-2.example:2222"
ROOT = "/var/lib/carbon/doors"
LOCK = "/var/lib/carbon/locks"


def _remote(index=2, cpuset="0-3"):
    return grade_lanes.Lane(index, cpuset, LOCK, HOST, ROOT)


def _record(tmp_path, lanes):
    (tmp_path / remote_lane.RECORD).write_text(
        json.dumps({"schema": remote_lane.SCHEMA, "lanes": lanes}), encoding="utf-8"
    )
    return tmp_path


# -- configuration ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["ssh://carbon@10.0.0.2", "ssh://carbon-grade@grader-2.example:2222"],
)
def test_a_plain_ssh_daemon_address_parses(value):
    user, host, port = remote_lane.parse_docker_host(value)
    assert user.startswith("carbon") and host and 1 <= port <= 65535


@pytest.mark.parametrize(
    "value",
    [
        "tcp://10.0.0.2:2375",
        "ssh://10.0.0.2",
        "ssh://carbon@host:0",
        "ssh://carbon@host:70000",
        "ssh://carbon@host -oProxyCommand=x",
        "ssh://carbon@host/path",
        None,
    ],
)
def test_anything_else_is_refused(value):
    with pytest.raises(ValueError):
        remote_lane.parse_docker_host(value)


def test_no_record_is_no_remote_lane_and_a_good_record_loads(tmp_path):
    assert remote_lane.load(tmp_path) == ()
    entry = {"docker_host": HOST, "cpuset": "0-3", "stage_root": ROOT}
    assert remote_lane.load(_record(tmp_path, [entry])) == (
        remote_lane.RemoteSpec(HOST, "0-3", ROOT),
    )


@pytest.mark.parametrize(
    "lanes",
    [
        [],
        [{"docker_host": HOST, "cpuset": "0-3"}],
        [{"docker_host": HOST, "cpuset": "0-3", "stage_root": "relative"}],
        [{"docker_host": HOST, "cpuset": "0-3", "stage_root": "/"}],
        [{"docker_host": HOST, "cpuset": "0-3", "stage_root": "/var/../etc"}],
        [{"docker_host": HOST, "cpuset": "3-0", "stage_root": ROOT}],
        [{"docker_host": "tcp://x:1", "cpuset": "0-3", "stage_root": ROOT}],
        [{"docker_host": HOST, "cpuset": "0-3", "stage_root": ROOT}] * 2,
    ],
)
def test_a_broken_record_raises(tmp_path, lanes):
    with pytest.raises(ValueError):
        remote_lane.load(_record(tmp_path, lanes))


def _values(tmp_path, row):
    path = tmp_path / "grade_lanes.json"
    path.write_text(
        json.dumps({"schema": grade_lanes.SCHEMA, "rows": {"m 1.8": row}}),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "row, lanes, remote",
    [
        ({"lanes": 2}, 2, 0),
        ({"lanes": 2, "remote_lanes": 1}, 2, 1),
        ({"lanes": 2, "remote_lanes": 2}, 1, 0),
        ({"lanes": 2, "remote_lanes": True}, 1, 0),
        ({"lanes": 2, "remote_lanes": 1, "x": 1}, 1, 0),
    ],
)
def test_the_values_row_may_ask_for_one_remote_lane(tmp_path, row, lanes, remote):
    path = _values(tmp_path, row)
    assert grade_lanes.registered_lanes("m", "1.8", path=path) == lanes
    assert grade_lanes.registered_remote_lanes("m", "1.8", path=path) == remote


def test_the_shipped_values_file_asks_for_no_remote_lane():
    assert grade_lanes.registered_remote_lanes("electric-motor-magnetics", "1.8") == 0


def test_a_remote_lane_needs_the_row_two_lane_mode_and_the_record(
    tmp_path, monkeypatch
):
    entry = {"docker_host": HOST, "cpuset": "0-3", "stage_root": ROOT}
    host_root = _record(tmp_path, [entry])
    asked = _values(tmp_path, {"lanes": 2, "remote_lanes": 1})
    local = ("0-3", "4-7")
    monkeypatch.setattr(grade_lanes, "door_lanes", lambda *a, **k: local)
    found = grade_lanes.door_remote_lanes(
        "m", "1.8", registry=asked, host_root=host_root
    )
    assert found == (remote_lane.RemoteSpec(HOST, "0-3", ROOT),)
    # no remote_lanes in the row
    plain = _values(tmp_path, {"lanes": 2})
    assert (
        grade_lanes.door_remote_lanes("m", "1.8", registry=plain, host_root=host_root)
        == ()
    )
    # one-lane mode
    monkeypatch.setattr(grade_lanes, "door_lanes", lambda *a, **k: ())
    assert (
        grade_lanes.door_remote_lanes("m", "1.8", registry=asked, host_root=host_root)
        == ()
    )
    # no record
    monkeypatch.setattr(grade_lanes, "door_lanes", lambda *a, **k: local)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert (
        grade_lanes.door_remote_lanes("m", "1.8", registry=asked, host_root=empty) == ()
    )


def test_every_lane_lock_includes_the_remote_one():
    assert grade_lanes.ALL_LANES == grade_lanes.MAX_LANES + grade_lanes.MAX_REMOTE_LANES
    assert grade_lanes.lane_lock_name(grade_lanes.MAX_LANES) == (
        "official-grading.lane-2.lock"
    )


# -- the docker calls of a remote round ---------------------------------------------------------------------------------


def test_a_remote_round_sends_docker_to_the_lanes_daemon_with_home_only(monkeypatch):
    monkeypatch.setenv("HOME", "/home/door")
    monkeypatch.setenv("DOCKER_CONTEXT", "elsewhere")
    with grade_lanes.bound(_remote()):
        assert remote_lane.docker_host() == HOST
        assert remote_lane.current_environment() == {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "DOCKER_HOST": HOST,
            "HOME": "/home/door",
        }
    assert remote_lane.docker_host() is None
    local = remote_lane.current_environment()
    assert "DOCKER_HOST" not in local and local["DOCKER_CONTEXT"] == "elsewhere"
    assert "HOME" not in local


def test_a_local_lane_is_unchanged():
    with grade_lanes.bound(grade_lanes.Lane(1, "4-7", LOCK)):
        assert remote_lane.current() is None
        assert remote_lane.docker_host() is None


def test_the_docker_cli_keeps_the_daemon_it_was_made_for(monkeypatch):
    from carbon.reconstruction.worker import docker_runtime

    seen = []

    def capture(command, *, environment, timeout, maximum, **_):
        seen.append(environment)
        import subprocess

        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(docker_runtime, "_bounded_capture", capture)
    monkeypatch.setattr(
        docker_runtime.DockerCLI, "load_installed_aliases", lambda self: None
    )
    with grade_lanes.bound(_remote()):
        remote = docker_runtime.DockerCLI()
    local = docker_runtime.DockerCLI()
    remote.run(["ps"])
    local.run(["ps"])
    assert seen[0]["DOCKER_HOST"] == HOST
    assert seen[1].get("DOCKER_HOST") != HOST


def test_the_watchdog_and_reaper_inherit_the_rounds_daemon(monkeypatch):
    from carbon.reconstruction.worker import docker_runtime

    started = []
    monkeypatch.setattr(
        docker_runtime.subprocess,
        "Popen",
        lambda *a, **k: started.append(k["env"]) or SimpleNamespace(),
    )
    with grade_lanes.bound(_remote()):
        docker_runtime.spawn_watchdog(
            container_name="carbon-d4-" + "1" * 24,
            launch_digest="sha256:" + "1" * 64,
            deadline_unix=time.time() + 60,
        )
    assert started[0]["DOCKER_HOST"] == HOST


# -- the speed stage stays here ------------------------------------------------------------------------------------------


def _host_record(cpuset="0-3"):
    return SimpleNamespace(cpuset=cpuset)


def test_a_timing_container_of_a_remote_round_runs_here_under_the_same_gate(
    monkeypatch,
):
    from carbon.reconstruction import host_execution

    monkeypatch.setattr(
        host_execution.HostExecutionRecord,
        "load",
        classmethod(lambda cls, root: _host_record("4-7")),
    )
    with grade_lanes.bound(_remote(cpuset="0-15")):
        with remote_lane.local_for("single-call-" + "a" * 16):
            twin = grade_lanes.current()
            assert twin.docker_host is None and remote_lane.docker_host() is None
            assert (twin.index, twin.lock_dir, twin.cpuset) == (2, LOCK, "4-7")
        with grade_lanes.timing_exclusive(), remote_lane.local_for("anything"):
            assert remote_lane.docker_host() is None
        with remote_lane.local_for("grade-op-1"):
            assert remote_lane.docker_host() == HOST
        assert remote_lane.docker_host() == HOST


def test_a_remote_timing_stage_with_no_local_cores_refuses_as_carbons(monkeypatch):
    from carbon.reconstruction import host_execution

    monkeypatch.setattr(
        host_execution.HostExecutionRecord, "load", classmethod(lambda cls, root: None)
    )
    with (
        grade_lanes.bound(_remote()),
        pytest.raises(remote_lane.RemoteLaneDown) as caught,
        remote_lane.local_for("single-call-x"),
    ):
        pass
    assert caught.value.code is WorkerCode.UNAVAILABLE


# -- inputs on the remote machine ----------------------------------------------------------------------------------------


class _Process:
    def __init__(self, command, returncode=0, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.stdin = None
        self.returncode = returncode
        self.sent = b""

    def communicate(self, timeout=None):
        return b"", b"boom" if self.returncode else b""

    def kill(self):
        pass

    def wait(self):
        return self.returncode


def _fake_ssh(monkeypatch, returncode=0):
    calls = []

    class Stdin(io.BytesIO):
        def close(self):
            calls[-1].sent = self.getvalue()
            super().close()

    def popen(command, **kwargs):
        process = _Process(command, returncode, **kwargs)
        if kwargs.get("stdin") == remote_lane.subprocess.PIPE:
            process.stdin = Stdin()
        calls.append(process)
        return process

    monkeypatch.setattr(remote_lane.subprocess, "Popen", popen)
    return calls


@pytest.mark.skipif(os.name != "posix", reason="a POSIX stage path")
def test_mirror_sends_the_directory_to_the_same_path_there(monkeypatch, tmp_path):
    calls = _fake_ssh(monkeypatch)
    stage = tmp_path / "input"
    stage.mkdir()
    (stage / "a.json").write_bytes(b"{}")
    (stage / "overlay").mkdir()
    (stage / "overlay" / "b.bin").write_bytes(b"\x00\x01")
    lane = grade_lanes.Lane(2, "0-3", LOCK, HOST, str(tmp_path))
    remote_lane.mirror(stage, lane)
    (call,) = calls
    assert call.command[:-1] == [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-p",
        "2222",
        "carbon-grade@grader-2.example",
        "--",
    ]
    assert str(stage) in call.command[-1] and "find" in call.command[-1]
    assert call.kwargs["env"]["DOCKER_HOST"] == HOST
    with tarfile.open(fileobj=io.BytesIO(call.sent)) as archive:
        names = {member.name: member for member in archive.getmembers()}
        assert set(names) == {"a.json", "overlay", "overlay/b.bin"}
        assert archive.extractfile(names["overlay/b.bin"]).read() == b"\x00\x01"


def test_nothing_outside_the_stage_root_is_written_or_removed(monkeypatch, tmp_path):
    calls = _fake_ssh(monkeypatch)
    lane = grade_lanes.Lane(2, "0-3", LOCK, HOST, "/var/lib/carbon/doors")
    for path in ("/etc", "/var/lib/carbon/doors", "/var/lib/carbon/doorsX/a"):
        with pytest.raises(remote_lane.RemoteLaneDown):
            remote_lane.discard(Path(path), lane)
    assert calls == []


def test_a_failed_mirror_or_discard_is_carbons(monkeypatch, tmp_path):
    _fake_ssh(monkeypatch, returncode=255)
    stage = tmp_path / "input"
    stage.mkdir()
    lane = grade_lanes.Lane(2, "0-3", LOCK, HOST, str(tmp_path))
    for act in (remote_lane.mirror, remote_lane.discard):
        with pytest.raises(remote_lane.RemoteLaneDown) as caught:
            act(stage, lane)
        assert isinstance(caught.value, WorkerFailure)
        assert caught.value.code is WorkerCode.UNAVAILABLE


def test_outside_a_remote_round_nothing_is_sent(monkeypatch, tmp_path):
    calls = _fake_ssh(monkeypatch)
    remote_lane.mirror(tmp_path)
    remote_lane.discard(tmp_path)
    with grade_lanes.bound(grade_lanes.Lane(1, "4-7", LOCK)):
        remote_lane.mirror(tmp_path)
    assert calls == []


# -- a stalled link is never the candidate's wall -------------------------------------------------------------------------


def test_a_remote_wall_stop_needs_an_observed_container_and_a_live_link(monkeypatch):
    assert remote_lane.wall_stop_observable(None) is True  # this host: unchanged
    with grade_lanes.bound(_remote()):
        monkeypatch.setattr(remote_lane, "link_up", lambda *a, **k: True)
        assert remote_lane.wall_stop_observable({"status": "OBSERVED"}) is True
        assert remote_lane.wall_stop_observable({"status": "UNKNOWN"}) is False
        assert remote_lane.wall_stop_observable(None) is False
        monkeypatch.setattr(remote_lane, "link_up", lambda *a, **k: False)
        assert remote_lane.wall_stop_observable({"status": "OBSERVED"}) is False


def test_the_carriers_wall_stop_is_carbons_when_the_remote_link_is_down(monkeypatch):
    from carbon.development_session import research_carrier as carrier

    observed = {
        "status": "OBSERVED",
        "state": {"running": True, "oom_killed": False, "exit_code": None},
        "memory": None,
    }
    error = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
    )

    def stop():
        return carrier._candidate_resource_stop(
            SimpleNamespace(),
            error,
            container_name="carbon-d4-" + "1" * 24,
            launch_digest="sha256:" + "1" * 64,
            image_id="sha256:" + "2" * 64,
            program_started=time.monotonic() - 100,
            program_timeout=10,
            setup_seconds=1,
            memory_limit_bytes=16 * 1024**3,
            deadline=time.monotonic() + 1,
            observation=observed,
        )

    assert stop()[1] == carrier.CANDIDATE_WALL_LIMIT  # this host: unchanged
    with grade_lanes.bound(_remote()):
        monkeypatch.setattr(remote_lane, "link_up", lambda *a, **k: False)
        assert stop() is None
        monkeypatch.setattr(remote_lane, "link_up", lambda *a, **k: True)
        assert stop()[1] == carrier.CANDIDATE_WALL_LIMIT


# -- the watchdog of a remote container ----------------------------------------------------------------------------------


def test_the_remote_watchdog_rides_out_a_link_fault_and_stops_on_absence(monkeypatch):
    import subprocess

    from carbon.reconstruction.worker import watchdog

    monkeypatch.setenv("DOCKER_HOST", HOST)
    answers = [
        WorkerFailure(WorkerCode.UNAVAILABLE),  # ssh down
        subprocess.CompletedProcess([], 1, b"", b"error during connect"),  # transport
        subprocess.CompletedProcess([], 0, b"[]", b""),  # still there
        subprocess.CompletedProcess([], 1, b"", b"Error: No such object: x"),  # gone
    ]

    class CLI:
        def run(self, arguments, timeout=None, accepted=(0,)):
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

    monkeypatch.setattr(watchdog, "DockerCLI", CLI)
    monkeypatch.setattr(watchdog.time, "sleep", lambda s: None)
    code = watchdog.main(
        ["carbon-d4-" + "1" * 24, "sha256:" + "1" * 64, str(time.time() + 600)]
    )
    assert code == 0 and answers == []


def test_the_local_watchdog_is_unchanged(monkeypatch):
    import subprocess

    from carbon.reconstruction.worker import watchdog

    monkeypatch.delenv("DOCKER_HOST", raising=False)

    class CLI:
        def run(self, arguments, timeout=None, accepted=(0,)):
            return subprocess.CompletedProcess([], 1, b"", b"error during connect")

    monkeypatch.setattr(watchdog, "DockerCLI", CLI)
    assert (
        watchdog.main(
            ["carbon-d4-" + "1" * 24, "sha256:" + "1" * 64, str(time.time() + 600)]
        )
        == 0
    )
