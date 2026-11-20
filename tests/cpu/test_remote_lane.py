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
        [{"docker_host": HOST, "cpuset": "0-3", "stage_root": ROOT}]
        * (remote_lane.MAX_REMOTE_LANES + 1),
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
        ({"lanes": 2, "remote_lanes": 8}, 2, 8),
        ({"lanes": 2, "remote_lanes": 9}, 1, 0),
        ({"lanes": 2, "remote_lanes": True}, 1, 0),
        ({"lanes": 2, "remote_lanes": 1, "x": 1}, 1, 0),
    ],
)
def test_the_values_row_may_ask_for_one_remote_lane(tmp_path, row, lanes, remote):
    path = _values(tmp_path, row)
    assert grade_lanes.registered_lanes("m", "1.8", path=path) == lanes
    assert grade_lanes.registered_remote_lanes("m", "1.8", path=path) == remote


def test_the_shipped_values_file_asks_for_the_two_box_remote_lanes():
    # PROPOSED: two 5950X boxes x 4 lanes (OWNER-5950X-GRADING-CLASS-01; CV-Motor/V2 to confirm); no other version
    assert grade_lanes.registered_remote_lanes("electric-motor-magnetics", "1.8") == 8
    assert grade_lanes.registered_remote_lanes("electric-motor-magnetics", "1.7") == 0
    assert 8 == remote_lane.MAX_REMOTE_LANES


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


#: A stand-in for ``ssh ... -- 'sh -c <script>'``: a REAL child process (real pipes, so the upload's threading is
#: exercised), which records its argv and stdin, writes a line to stderr, and exits with ``CODE``.
_CHILD = (
    "import sys, pathlib\n"
    "out = pathlib.Path(sys.argv[1])\n"
    "(out / 'argv').write_text('\\n'.join(sys.argv[3:]))\n"
    "(out / 'stdin').write_bytes(sys.stdin.buffer.read())\n"
    "sys.stderr.write('remote said no\\n')\n"
    "raise SystemExit(int(sys.argv[2]))\n"
)


def _child_ssh(monkeypatch, tmp_path, code=0, *, hang=False):
    import sys

    record = tmp_path / "child"
    record.mkdir(exist_ok=True)
    program = _CHILD if not hang else "import time; time.sleep(30)"
    monkeypatch.setattr(
        remote_lane,
        "_ssh",
        lambda lane: [sys.executable, "-c", program, str(record), str(code)],
    )
    return record


def test_the_ssh_command_is_fixed_and_bounded():
    assert remote_lane._ssh(_remote()) == [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=10",
        "-o",
        "ServerAliveCountMax=3",
        "-p",
        "2222",
        "carbon-grade@grader-2.example",
        "--",
    ]


@pytest.mark.skipif(os.name != "posix", reason="a POSIX stage path")
def test_mirror_streams_the_directory_to_the_same_path_there(monkeypatch, tmp_path):
    stage = tmp_path / "input"
    stage.mkdir()
    (stage / "a.json").write_bytes(b"{}")
    (stage / "overlay").mkdir()
    (stage / "overlay" / "b.bin").write_bytes(
        b"\x00\x01" * 300_000
    )  # more than one pipe buffer
    record = _child_ssh(monkeypatch, tmp_path)
    remote_lane.mirror(stage, grade_lanes.Lane(2, "0-3", LOCK, HOST, str(tmp_path)))
    script = (record / "argv").read_text()
    assert str(stage) in script and "chmod -R u+w" in script and "find" in script
    with tarfile.open(fileobj=io.BytesIO((record / "stdin").read_bytes())) as archive:
        names = {member.name: member for member in archive.getmembers()}
        assert set(names) == {"a.json", "overlay", "overlay/b.bin"}
        assert (
            archive.extractfile(names["overlay/b.bin"]).read() == b"\x00\x01" * 300_000
        )


def test_nothing_outside_the_stage_root_is_written_or_removed(monkeypatch, tmp_path):
    record = _child_ssh(monkeypatch, tmp_path)
    lane = grade_lanes.Lane(2, "0-3", LOCK, HOST, "/var/lib/carbon/doors")
    for path in ("/etc", "/var/lib/carbon/doors", "/var/lib/carbon/doorsX/a"):
        with pytest.raises(remote_lane.RemoteLaneDown):
            remote_lane.discard(Path(path), lane)
    assert not (record / "argv").exists()


@pytest.mark.skipif(os.name != "posix", reason="a POSIX stage path")
def test_a_failed_mirror_or_discard_is_carbons(monkeypatch, tmp_path):
    _child_ssh(monkeypatch, tmp_path, code=255)
    stage = tmp_path / "input"
    stage.mkdir()
    lane = grade_lanes.Lane(2, "0-3", LOCK, HOST, str(tmp_path))
    for act in (remote_lane.mirror, remote_lane.discard):
        with pytest.raises(remote_lane.RemoteLaneDown) as caught:
            act(stage, lane)
        assert isinstance(caught.value, WorkerFailure)
        assert caught.value.code is WorkerCode.UNAVAILABLE
        assert b"exit=255" in caught.value.private_diagnostic
        assert b"remote said no" in caught.value.private_diagnostic


def test_a_large_upload_through_a_real_pipe_completes(monkeypatch, tmp_path):
    record = _child_ssh(monkeypatch, tmp_path)
    body = (
        b"" * 3_000_000
    )  # several pipe buffers: the writer and the reader must overlap
    remote_lane._run(_remote(), "true", feed=lambda stream: stream.write(body))
    assert (record / "stdin").read_bytes() == body


def test_a_stalled_link_is_killed_at_the_deadline(monkeypatch, tmp_path):
    _child_ssh(monkeypatch, tmp_path, hang=True)
    stage = tmp_path / "input"
    stage.mkdir()
    (stage / "big.bin").write_bytes(
        b"\x00" * 4_000_000
    )  # the child never reads: the writer blocks
    lane = grade_lanes.Lane(2, "0-3", LOCK, HOST, str(tmp_path))
    monkeypatch.setattr(remote_lane, "SSH_SECONDS", 1)
    began = time.monotonic()
    with pytest.raises(remote_lane.RemoteLaneDown) as caught:
        remote_lane._run(
            lane,
            "true",
            feed=lambda stream: stream.write(b"\x00" * 4_000_000),
            timeout=1,
        )
    assert time.monotonic() - began < 15
    assert b"timeout" in caught.value.private_diagnostic


def test_outside_a_remote_round_nothing_is_sent(monkeypatch, tmp_path):
    record = _child_ssh(monkeypatch, tmp_path)
    remote_lane.mirror(tmp_path)
    remote_lane.discard(tmp_path)
    with grade_lanes.bound(grade_lanes.Lane(1, "4-7", LOCK)):
        remote_lane.mirror(tmp_path)
    assert not (record / "argv").exists()


# -- a stalled link is never the candidate's wall: no box clock, Carbon's (L12624: test_remote_wall_stop) -------------


def test_a_remote_wall_stop_without_the_boxs_clock_is_never_the_candidates():
    assert remote_lane.wall_stop_observable(None) is True  # this host: unchanged
    with grade_lanes.bound(_remote()):
        assert remote_lane.wall_stop_observable({"status": "OBSERVED"}) is False
        assert remote_lane.wall_stop_observable(None) is False
    with grade_lanes.bound(grade_lanes.Lane(1, "4-7", LOCK)):
        assert remote_lane.wall_stop_observable(None) is True


def test_the_carriers_wall_stop_on_a_remote_lane_without_a_box_clock_is_carbons():
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
        assert stop() is None


def test_a_remote_ops_inputs_are_discarded_on_every_exit(monkeypatch, tmp_path):
    from carbon.development_session import research_carrier as carrier

    gone = []
    monkeypatch.setattr(
        remote_lane, "discard", lambda stage, lane=None: gone.append(stage)
    )
    with pytest.raises(RuntimeError), carrier._remote_inputs_discarded(tmp_path):
        raise RuntimeError("cleanup failed")
    with carrier._remote_inputs_discarded(None):
        pass
    assert gone == [tmp_path]


# -- recovery uses the daemon the intent recorded -----------------------------------------------------------------------


def test_an_intent_records_the_remote_daemon_and_recovery_reads_it(monkeypatch):
    from carbon.reconstruction.worker import docker_runtime

    monkeypatch.setattr(
        docker_runtime.DockerCLI, "load_installed_aliases", lambda self: None
    )
    assert remote_lane.intent_fields() == {}
    with grade_lanes.bound(_remote()):
        fields = remote_lane.intent_fields()
    assert fields == {"remote": {"docker_host": HOST, "stage_root": ROOT}}
    spec = remote_lane.recorded(fields)
    assert spec == remote_lane.RemoteSpec(HOST, "", ROOT)
    assert remote_lane.cli_for(spec).docker_host == HOST
    assert remote_lane.cli_for(None).docker_host is None
    assert remote_lane.recorded({}) is None
    for bad in (
        {"remote": {"docker_host": HOST}},
        {"remote": {"docker_host": "tcp://x:1", "stage_root": ROOT}},
        {"remote": {"docker_host": HOST, "stage_root": "/"}},
    ):
        with pytest.raises(ValueError):
            remote_lane.recorded(bad)


def test_a_timed_control_of_a_remote_round_stays_here(monkeypatch):
    from carbon.reconstruction import host_execution

    monkeypatch.setattr(
        host_execution.HostExecutionRecord,
        "load",
        classmethod(lambda cls, root: _host_record("4-7")),
    )
    with grade_lanes.bound(_remote()):
        with remote_lane.local_for("grade-op-1", timed=True):
            assert remote_lane.docker_host() is None
            assert grade_lanes.timing_requested()  # the gate is taken EXCLUSIVE
        with remote_lane.local_for("grade-op-1", timed=False):
            assert remote_lane.docker_host() == HOST


def test_the_carrier_counts_a_measured_query_as_timed():
    from carbon.development_session import research_carrier as carrier

    assert carrier._timed_control({"control.json": b'{"measure_query": true}'})
    assert not carrier._timed_control({"control.json": b"{}"})
    assert not carrier._timed_control(None)


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


def test_the_remote_watchdog_reads_the_remote_daemons_lowercase_absence(monkeypatch):
    """Live 116, 19 Nov 2026: the remote lanes' docker prints a lowercase absence line; the watchdog must stop on it
    at once (it used to poll inspect until its deadline)."""
    import subprocess

    from carbon.reconstruction.worker import watchdog

    assert watchdog._says_absent(b"error: no such object: carbon-d4-x")
    assert watchdog._says_absent(b"Error: No such container: carbon-d4-x")
    assert watchdog._says_absent(b"Error response from daemon: No such object: x")
    assert not watchdog._says_absent(b"error during connect")
    assert not watchdog._says_absent(None)
    monkeypatch.setenv("DOCKER_HOST", HOST)
    calls = []

    class CLI:
        def run(self, arguments, timeout=None, accepted=(0,)):
            calls.append(arguments)
            return subprocess.CompletedProcess(
                [], 1, b"", b"error: no such object: carbon-d4-" + b"1" * 24
            )

    monkeypatch.setattr(watchdog, "DockerCLI", CLI)
    monkeypatch.setattr(
        watchdog.time, "sleep", lambda s: pytest.fail("polled again after absence")
    )
    code = watchdog.main(
        ["carbon-d4-" + "1" * 24, "sha256:" + "1" * 64, str(time.time() + 600)]
    )
    assert code == 0 and len(calls) == 1


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


def test_the_remote_reaper_rides_out_a_link_fault(monkeypatch):
    import subprocess

    from carbon.reconstruction.worker import liveness_reaper

    monkeypatch.setenv("DOCKER_HOST", HOST)
    answers = [
        WorkerFailure(WorkerCode.UNAVAILABLE),  # inspect: link down -> keep watching
        subprocess.CompletedProcess([], 1, b"", b"Error: No such object: x"),  # gone
    ]

    class CLI:
        def run(self, arguments, timeout=None, accepted=(0,)):
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

    code = liveness_reaper.watch(
        "carbon-d4-" + "1" * 24,
        "sha256:" + "1" * 64,
        1,
        "proc-start:1",
        cli=CLI(),
        identify=lambda pid: "proc-start:1",
        sleep=lambda s: None,
    )
    assert code == 0 and answers == []


def test_the_local_reaper_still_raises_on_a_runtime_fault(monkeypatch):
    from carbon.reconstruction.worker import liveness_reaper

    monkeypatch.delenv("DOCKER_HOST", raising=False)

    class CLI:
        def run(self, arguments, timeout=None, accepted=(0,)):
            raise WorkerFailure(WorkerCode.UNAVAILABLE)

    with pytest.raises(WorkerFailure):
        liveness_reaper.watch(
            "carbon-d4-" + "1" * 24,
            "sha256:" + "1" * 64,
            1,
            "proc-start:1",
            cli=CLI(),
            identify=lambda pid: "proc-start:1",
            sleep=lambda s: None,
        )


def test_the_remote_watchdog_retries_removal_after_its_deadline(monkeypatch):
    from carbon.reconstruction.worker import watchdog

    monkeypatch.setenv("DOCKER_HOST", HOST)
    tries = []

    def remove(**kwargs):
        tries.append(1)
        if len(tries) < 3:
            raise WorkerFailure(WorkerCode.UNAVAILABLE)

    monkeypatch.setattr(watchdog, "remove_exact_container", remove)
    monkeypatch.setattr(watchdog, "DockerCLI", lambda: SimpleNamespace())
    monkeypatch.setattr(watchdog.time, "sleep", lambda s: None)
    assert (
        watchdog.main(
            ["carbon-d4-" + "1" * 24, "sha256:" + "1" * 64, str(time.time() - 1)]
        )
        == 0
    )
    assert len(tries) == 3


# -- a door's OWN record: a scratch door on the remote boxes (Lead, 16 Nov 2026: the Ryzen re-grades) -----------------------


def test_a_door_record_gives_that_door_its_remote_lanes_without_a_values_row(
    tmp_path, monkeypatch
):
    entry = {"docker_host": HOST, "cpuset": "0-3", "stage_root": ROOT}
    door = tmp_path / "scratch-door"
    door.mkdir()
    _record(door, [entry, {**entry, "cpuset": "4-7"}])
    plain = _values(tmp_path, {"lanes": 2})  # no remote_lanes in the values row
    monkeypatch.setattr(grade_lanes, "door_lanes", lambda *a, **k: ("0-3", "4-7"))
    empty_host = tmp_path / "host"
    empty_host.mkdir()
    found = grade_lanes.door_remote_lanes(
        "m", "1.8", registry=plain, host_root=empty_host, state_root=door
    )
    assert [spec.cpuset for spec in found] == ["0-3", "4-7"]
    # another door (no record of its own) sees none of them
    other = tmp_path / "live-door"
    other.mkdir()
    assert (
        grade_lanes.door_remote_lanes(
            "m", "1.8", registry=plain, host_root=empty_host, state_root=other
        )
        == ()
    )


def test_the_record_s_only_flag(tmp_path):
    entry = {"docker_host": HOST, "cpuset": "0-3", "stage_root": ROOT}
    (tmp_path / remote_lane.RECORD).write_text(
        json.dumps({"schema": remote_lane.SCHEMA, "lanes": [entry], "only": True}),
        encoding="utf-8",
    )
    specs, only = remote_lane.load_record(tmp_path)
    assert only is True and len(specs) == 1
    assert grade_lanes.door_remote_only(tmp_path) is True
    assert grade_lanes.door_remote_only(None) is False
    (tmp_path / remote_lane.RECORD).write_text(
        json.dumps({"schema": remote_lane.SCHEMA, "lanes": [entry], "only": "yes"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="remote_lane_record"):
        remote_lane.load_record(tmp_path)
    assert grade_lanes.door_remote_only(tmp_path) is False


def test_a_rebuild_on_a_remote_lane_is_never_quiet():
    """Its neighbours on the remote machine are invisible to this host's `docker ps`: a failure there is Carbon's."""
    from carbon.challenge_validator import host_quiet

    token = host_quiet.activate(
        lock_held=True, containers=lambda: 1, gpu=lambda: 0, seconds=1
    )
    try:
        with grade_lanes.bound(_remote()):
            verdict = host_quiet.finish(host_quiet.start())
    finally:
        host_quiet.deactivate(token)
    assert verdict.quiet is False


def test_the_receipt_worker_tests_every_lane_lock():
    from carbon.backbone_catalog import receipt_job

    assert {
        f"official-grading.lane-{i}.lock" for i in range(1, grade_lanes.ALL_LANES)
    } == set(receipt_job.LANE_LOCKS)


def test_a_door_whose_state_root_is_the_host_root_has_no_record_of_its_own(
    tmp_path, monkeypatch
):
    entry = {"docker_host": HOST, "cpuset": "0-3", "stage_root": ROOT}
    _record(tmp_path, [entry])
    plain = _values(
        tmp_path, {"lanes": 2}
    )  # no remote_lanes: the host's record needs it
    monkeypatch.setattr(grade_lanes, "door_lanes", lambda *a, **k: ("0-3", "4-7"))
    assert (
        grade_lanes.door_remote_lanes(
            "m", "1.8", registry=plain, host_root=tmp_path, state_root=tmp_path
        )
        == ()
    )
