"""A wall stop on a REMOTE grading box (CV-Motor's ruling, board L12624, 16 Nov 2026): the candidate's (counted) only
when, read from records, (a) the box's own clock says the program was still running there and had run its whole wall,
(b) the box was quiet for the run (sampled ON the box: no other Carbon worker container on any of its lanes, no
foreign GPU compute), and (c) the link stayed healthy (every sample answered, the stop observed, the daemon up at the
stop). Anything else is Carbon's (FAILED_INFRA, never charged). Fakes only: no ssh, no docker, no container.
"""

from __future__ import annotations

import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import (
    grade_sequencer,
    host_quiet,
    lean_recipe,
)
from carbon.development_session import research_carrier as carrier
from carbon.reconstruction import grade_lanes, remote_lane
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

HOST = "ssh://carbon-grade@grader-2.example:2222"
LOCK = "/var/lib/carbon/locks"
OBSERVED = {
    "status": "OBSERVED",
    "state": {"running": True, "oom_killed": False, "exit_code": 0},
    "memory": None,
}
DIGEST = "a" * 64


def _remote(index=2):
    return grade_lanes.Lane(index, "0-3", LOCK, HOST, "/var/lib/carbon/doors")


# -- (a) + the link: the box's own clock -----------------------------------------------------------------------------------


def test_outside_a_remote_round_nothing_changes():
    assert remote_lane.wall_stop_observable(None) is True
    with grade_lanes.bound(grade_lanes.Lane(1, "4-7", LOCK)):
        assert remote_lane.wall_stop_observable(None) is True


def test_a_remote_wall_is_observable_only_by_the_boxs_own_clock(monkeypatch):
    monkeypatch.setattr(remote_lane, "link_up", lambda lane=None, **_: True)
    with grade_lanes.bound(_remote()):
        ok = remote_lane.wall_stop_observable(
            OBSERVED, box_seconds=lambda: 600.0, needed=599
        )
        assert ok is True
        # (a) the program ran less than its wall on the box (a fast controller clock or a stalled link): Carbon's
        assert not remote_lane.wall_stop_observable(
            OBSERVED, box_seconds=lambda: 598.9, needed=599
        )
        # (a) the program no longer runs there (it ended; only the link stalled) or its age cannot be read
        assert not remote_lane.wall_stop_observable(
            OBSERVED, box_seconds=lambda: None, needed=599
        )

        def broken():
            raise OSError("link")

        assert not remote_lane.wall_stop_observable(
            OBSERVED, box_seconds=broken, needed=599
        )
        # no box clock at all (a caller that cannot read one), or the stop not observed: Carbon's
        assert not remote_lane.wall_stop_observable(OBSERVED)
        assert not remote_lane.wall_stop_observable(
            {"status": "UNKNOWN"}, box_seconds=lambda: 600.0, needed=599
        )
        assert not remote_lane.wall_stop_observable(
            None, box_seconds=lambda: 600.0, needed=599
        )
    # (c) the daemon does not answer at the stop
    monkeypatch.setattr(remote_lane, "link_up", lambda lane=None, **_: False)
    with grade_lanes.bound(_remote()):
        assert not remote_lane.wall_stop_observable(
            OBSERVED, box_seconds=lambda: 600.0, needed=599
        )


class _Cli:
    """A Docker CLI whose ``exec`` of the box-clock read answers ``answer`` (bytes) or raises it."""

    def __init__(self, answer):
        self.answer, self.calls = answer, []

    slow = 0.0

    def run(self, argv, timeout=30):
        self.calls.append((list(argv), timeout))
        time.sleep(self.slow)
        if isinstance(self.answer, Exception):
            raise self.answer
        return SimpleNamespace(stdout=self.answer)


def _stop(cli, *, box=True, ran=10.2, timeout=10):
    """A stream timeout ``ran`` seconds after the program's exec (its controller deadline ``timeout``)."""
    error = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
    )
    return carrier._candidate_resource_stop(
        cli,
        error,
        container_name="carbon-d4-" + "1" * 24,
        launch_digest="sha256:" + "1" * 64,
        image_id="sha256:" + "2" * 64,
        program_started=time.monotonic() - ran,
        program_timeout=timeout,
        box_deadline=(time.monotonic() + 30) if box else None,
        setup_seconds=1,
        memory_limit_bytes=16 * 1024**3,
        deadline=time.monotonic() + 1,
        observation=OBSERVED,
    )


def test_the_carrier_counts_a_remote_wall_only_on_the_boxs_clock(monkeypatch):
    monkeypatch.setattr(remote_lane, "link_up", lambda lane=None, **_: True)
    with grade_lanes.bound(_remote()):
        cli = _Cli(
            b"10.100\n"
        )  # the program's exec ran its whole wall on the box (>= 10 - 1 at the stop)
        assert _stop(cli)[1] == carrier.CANDIDATE_WALL_LIMIT
        (argv, read_timeout), *_ = cli.calls
        assert argv == [
            "exec",
            "carbon-d4-" + "1" * 24,
            "/opt/carbon-worker/bin/python",
            "-I",
            "-c",
            carrier._BOX_PROGRAM_AGE,
        ]
        assert 0 < read_timeout <= 10
        assert (
            _stop(_Cli(b"8.900\n")) is None
        )  # short of its wall on the box at the stop
        # the time after the stop is taken off: a read 30 s late needs an age of 30 s more
        assert _stop(_Cli(b"10.100\n"), ran=40.2) is None
        assert _stop(_Cli(b"39.500\n"), ran=40.2)[1] == carrier.CANDIDATE_WALL_LIMIT
        # a slow read: everything up to its answer is taken off, so the link's delay never adds age
        slow = _Cli(b"11.000" + bytes([10]))
        slow.slow = 2.0
        assert _stop(slow) is None
        # an age longer than the controller saw since the exec (+1 s) is not this program's clock
        assert _stop(_Cli(b"12.000\n")) is None
        assert _stop(_Cli(b"none\n")) is None  # gone there, or ambiguous
        assert _stop(_Cli(b"garbage")) is None
        assert _stop(_Cli(WorkerFailure(WorkerCode.RUNTIME))) is None
        assert (
            _stop(_Cli(b"10.1"), box=False) is None
        )  # no box clock asked for: Carbon's
    # this host: unchanged, and the box is never asked
    local = _Cli(b"0.0")
    assert _stop(local)[1] == carrier.CANDIDATE_WALL_LIMIT
    assert local.calls == []


def test_the_carrier_asks_for_the_box_clock_at_the_program_stop():
    from pathlib import Path

    source = " ".join(Path(carrier.__file__).read_text(encoding="utf-8").split())
    assert "box_deadline=started + seconds - 30" in source


def _proc(tmp_path, uptime, processes, tck=100):
    """A fake ``/proc``: ``processes`` = {pid: (state, ppid, starttime ticks)}."""
    (tmp_path / "uptime").write_text(f"{uptime} 1.0\n")
    for pid, (state, ppid, start) in processes.items():
        (tmp_path / str(pid)).mkdir()
        fields = [state, str(ppid)] + ["0"] * 17 + [str(start)] + ["0"] * 10
        (tmp_path / str(pid) / "stat").write_text(
            f"{pid} (py thon) " + " ".join(fields) + "\n"
        )
    (tmp_path / "self").mkdir()


def _age(proc, me=99, tck=100):
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            carrier._BOX_PROGRAM_AGE,
            str(proc),
            str(me),
            str(tck),
        ],
        capture_output=True,
        timeout=30,
        check=True,
    )
    return done.stdout.decode().strip()


@pytest.mark.parametrize(
    "processes, expected",
    [
        # pid 1 (the container's init) and this read (99) are never the program; the one exec root is
        (
            {
                1: ("S", 0, 100),
                7: ("S", 0, 50000),
                8: ("R", 7, 50010),
                99: ("R", 0, 59990),
            },
            "100.000",
        ),
        # the program's children (ppid inside the container) are not exec roots
        ({1: ("S", 0, 100), 8: ("R", 7, 50010), 99: ("R", 0, 59990)}, "none"),
        # an exec root that has ended (zombie / dead) is not a live program
        ({1: ("S", 0, 100), 7: ("Z", 0, 50000), 99: ("R", 0, 59990)}, "none"),
        # two live exec roots: ambiguous, Carbon's
        (
            {
                1: ("S", 0, 100),
                7: ("S", 0, 50000),
                9: ("S", 0, 55000),
                99: ("R", 0, 59990),
            },
            "none",
        ),
    ],
)
def test_the_box_clock_read_finds_the_one_live_exec_root(tmp_path, processes, expected):
    _proc(tmp_path, 600.0, processes)
    assert _age(tmp_path) == expected


# -- (b) + (c): quiet, sampled on the box ----------------------------------------------------------------------------------


def _box_run(monkeypatch, outputs):
    calls = []

    def fake(argv, **kwargs):
        calls.append((argv, kwargs.get("env", {}).get("DOCKER_HOST")))
        key = argv[1] if argv[0] == "docker" else "ssh"
        stdout, code = outputs[key]
        return SimpleNamespace(returncode=code, stdout=stdout)

    monkeypatch.setattr(host_quiet.subprocess, "run", fake)
    monkeypatch.setattr(remote_lane.subprocess, "run", fake)
    return calls


def test_box_samples_are_read_on_the_box_through_its_daemon(monkeypatch):
    calls = _box_run(
        monkeypatch,
        {
            "ps": (b"c1 carbon-d4-x\nc2 carbon-d4-y\nc3 other\n", 0),
            "ssh": (b"carbon-no-nvidia-smi\n", 0),
        },
    )
    containers, gpu = host_quiet.box_counters(_remote())
    assert containers() == 2
    assert gpu() == 0  # a CPU box: no GPU to contend
    assert all(host == HOST for argv, host in calls if argv[0] == "docker")
    assert any(argv[0] == "ssh" for argv, _ in calls)


@pytest.mark.parametrize(
    "outputs, expected",
    [
        ({"ps": (b"", 0), "ssh": (b"", 255)}, None),  # the link failed: unknown
        ({"ps": (b"", 0), "ssh": (b"[N/A]\n", 0)}, None),
        ({"ps": (b"", 0), "ssh": (b"No devices were found\n", 0)}, 0),
        (
            {
                "ps": (b"c1 carbon-d4-x\n", 0),
                "ssh": (b"77\n", 0),
                "top": (b"PID\n77\n", 0),
            },
            0,
        ),
        (
            {
                "ps": (b"c1 carbon-d4-x\n", 0),
                "ssh": (b"78\n", 0),
                "top": (b"PID\n77\n", 0),
            },
            1,
        ),
        ({"ps": (b"", 1), "ssh": (b"78\n", 0)}, None),
    ],
)
def test_the_boxs_foreign_gpu_compute(monkeypatch, outputs, expected):
    _box_run(monkeypatch, outputs)
    assert host_quiet.box_foreign_gpu(_remote()) == expected


def test_an_unanswered_box_daemon_is_unknown(monkeypatch):
    _box_run(monkeypatch, {"ps": (b"", 255)})
    assert host_quiet.box_worker_containers(_remote()) is None


def _boxes(monkeypatch, containers, gpu=0):
    monkeypatch.setattr(
        host_quiet, "box_counters", lambda lane: (lambda: containers, lambda: gpu)
    )
    # a build round on a lane counts its OWN cores there (owner/Lead 17 Nov 2026), read on the box
    monkeypatch.setattr(
        host_quiet,
        "count_lane_containers",
        lambda cpuset, lane=None: containers if lane is not None else 9,
    )


def test_a_crown_rebuild_on_a_box_is_probed_on_the_box_and_needs_samples(monkeypatch):
    _boxes(monkeypatch, 1)
    token = host_quiet.activate(
        lock_held=True, containers=lambda: 5, gpu=lambda: 5, seconds=0.01
    )
    try:
        with grade_lanes.bound(_remote()):
            probe = host_quiet.start()
            time.sleep(0.1)
            # a stop sample of 1 = the rebuild's own container still there: as for a local rebuild, not quiet
            assert probe.verdict().quiet is False
            assert probe.require_samples is True
        _boxes(monkeypatch, 0)
        with grade_lanes.bound(_remote()):
            probe = host_quiet.start()
            time.sleep(0.1)
            verdict = probe.verdict()
            assert (
                verdict.quiet is True and verdict.samples >= 1
            )  # the local host's 5 never asked
            assert (
                host_quiet.start().verdict().quiet is False
            )  # no in-run sample: no heartbeat
    finally:
        host_quiet.deactivate(token)


def test_a_build_on_a_box_is_quiet_only_on_a_quiet_box(monkeypatch):
    monkeypatch.setattr(lean_recipe, "BUILD_PROBE_SECONDS", 0.01)
    monkeypatch.setattr(host_quiet, "worker_containers", lambda: ["c"] * 9)
    for containers, gpu, quiet in (
        (1, 0, True),
        (2, 0, False),
        (1, 1, False),
        (None, 0, False),
    ):
        _boxes(monkeypatch, containers, gpu)
        with (
            grade_lanes.bound(_remote()),
            lean_recipe._build_wall_guard(grade_sequencer.OwnerClaims()),
        ):
            time.sleep(0.1)
            assert carrier._build_wall_quiet() is quiet, (containers, gpu)
            # a build that runs on another lane than the one its probe watched is never quiet
            with grade_lanes.bound(_remote(index=3)):
                assert carrier._build_wall_quiet() is False


def test_a_remote_build_is_guarded_even_with_one_build_round(monkeypatch):
    # a lane door whose builds take no owner claims (one build round) still judges a remote build on its box
    monkeypatch.setattr(lean_recipe, "BUILD_PROBE_SECONDS", 0.01)
    for containers, quiet in ((1, True), (2, False)):
        _boxes(monkeypatch, containers)
        with grade_lanes.bound(_remote()), lean_recipe._build_wall_guard(None):
            assert carrier.BUILD_WALL_GUARD.get() is not None
            time.sleep(0.1)
            assert carrier._build_wall_quiet() is quiet
    with lean_recipe._build_wall_guard(
        None
    ):  # this host, one build round: no guard, as before
        assert carrier.BUILD_WALL_GUARD.get() is None
