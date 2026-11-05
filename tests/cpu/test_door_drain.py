"""Per-door drain (MAINNET_UPDATE_ARCHITECTURE s2.4 Step A; Validator 17:19 conditions).

A door never blocks on the host's grading lock: it polls, gives up the round on stop or DRAINING, takes the host
lock only when it has something to grade, and keeps an atomic in-flight record a deploy reads instead of the host
lock. The host lock stays the one grading mutex (one grade per host at a time)."""

from __future__ import annotations

import fcntl
import json
import os
import threading
import time

import pytest

from carbon.backbone_catalog import receipt_job
from carbon.challenge_validator import crown_pause_sweep, direct_intake
from carbon.challenge_validator.direct_intake import (
    DRAIN_NAME,
    INFLIGHT_NAME,
    WAIT_NAME,
    _WorkLock,
)
from scripts.dev.release import door_drain

POLL = 0.05


@pytest.fixture
def dirs(tmp_path):
    host = tmp_path / "host"
    state = tmp_path / "state"
    for d in (host, state):
        d.mkdir(mode=0o700)
    return host, state


def _hold_host(host):
    """Another door (or the Deploy Engineer's grade_lock.py) holding the host's grading lock."""
    fd = os.open(host / receipt_job.GRADING_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release(fd):
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


class Grader:
    def __init__(self, work=True, seen=None, during=None):
        self.work, self.seen, self.during = (
            work,
            seen if seen is not None else [],
            during,
        )

    def has_work(self):
        return self.work

    def run_once(self):
        self.seen.append(time.monotonic())
        if self.during is not None:
            self.during()


def _loop(grader, stop, work):
    thread = threading.Thread(
        target=direct_intake._grade_loop, args=(grader, stop, work), daemon=True
    )
    thread.start()
    return thread


def test_draining_is_read_before_every_attempt_with_a_planted_pending_task(
    dirs, monkeypatch
):
    host, state = dirs
    monkeypatch.setattr(direct_intake, "_backoff_s", lambda n: POLL)
    (state / DRAIN_NAME).write_text("{}")
    stop = threading.Event()
    grader = Grader(work=True)
    work = _WorkLock(host, state_dir=state, stop=stop, poll_s=POLL)
    with (
        pytest.raises(direct_intake.WorkDeclined, match="draining"),
        work.taking("grade", has_work=grader.has_work),
    ):
        pytest.fail("work taken while draining")
    assert receipt_job.grading_busy(host) is False
    (state / DRAIN_NAME).unlink()
    with work.taking("grade", has_work=grader.has_work):
        assert receipt_job.grading_busy(host) is True
        assert json.loads((state / INFLIGHT_NAME).read_text())["kind"] == "grade"
    assert (
        not (state / INFLIGHT_NAME).exists() and receipt_job.grading_busy(host) is False
    )


def test_a_door_waiting_on_another_doors_grade_holds_nothing_and_stops_promptly(dirs):
    host, state = dirs
    fd = _hold_host(host)
    stop = threading.Event()
    grader = Grader(work=True)
    work = _WorkLock(host, state_dir=state, stop=stop, poll_s=POLL)
    thread = _loop(grader, stop, work)
    try:
        deadline = time.monotonic() + 5
        while not (state / WAIT_NAME).exists() and time.monotonic() < deadline:
            time.sleep(POLL)
        assert (
            state / WAIT_NAME
        ).exists()  # the starvation-alert input: waiting since when
        assert not (
            state / INFLIGHT_NAME
        ).exists()  # waiting is not in flight: the deploy sees this door idle
        assert door_drain.read_once(state)["busy"] is False
        stop.set()  # SIGTERM while waiting: the loop ends, no work starts after stop
        thread.join(2)
        assert not thread.is_alive() and grader.seen == []
        assert not (state / WAIT_NAME).exists()
    finally:
        stop.set()
        _release(fd)


def test_the_host_lock_stays_the_one_grading_mutex(dirs):
    host, state = dirs
    fd = _hold_host(host)
    stop = threading.Event()
    seen = []
    busy = []
    grader = Grader(
        work=True,
        seen=seen,
        during=lambda: busy.append(door_drain.read_once(state)["busy"]),
    )
    thread = _loop(
        grader, stop, _WorkLock(host, state_dir=state, stop=stop, poll_s=POLL)
    )
    try:
        time.sleep(10 * POLL)
        assert seen == []  # no grade while another holds the host lock
        _release(fd)
        fd = None
        deadline = time.monotonic() + 5
        while not seen and time.monotonic() < deadline:
            time.sleep(POLL)
        assert seen and busy[0] is True  # in flight, by this live process
    finally:
        stop.set()
        thread.join(2)
        if fd is not None:
            _release(fd)


def test_an_idle_door_never_takes_the_host_lock(dirs, monkeypatch):
    host, state = dirs
    calls = []
    real = _WorkLock._try_host
    monkeypatch.setattr(
        _WorkLock, "_try_host", lambda self: calls.append(1) or real(self)
    )
    stop = threading.Event()
    work = _WorkLock(host, state_dir=state, stop=stop, poll_s=POLL)
    with (
        pytest.raises(direct_intake.WorkDeclined, match="idle"),
        work.taking("grade", has_work=lambda: False),
    ):
        pass
    assert calls == [] and not (state / WAIT_NAME).exists()


def test_a_record_left_by_a_crash_is_set_aside_at_start_never_trusted(dirs):
    host, state = dirs
    (state / INFLIGHT_NAME).write_text(
        json.dumps({"pid": 1, "pid_start": 1, "kind": "grade"})
    )
    (state / WAIT_NAME).write_text("{}")
    _WorkLock(host, state_dir=state)
    assert not (state / INFLIGHT_NAME).exists() and not (state / WAIT_NAME).exists()
    names = sorted(p.name for p in state.iterdir())
    assert [n.split(".stale-")[0] for n in names] == [INFLIGHT_NAME, WAIT_NAME]


def test_the_in_flight_record_is_written_atomically(dirs, monkeypatch):
    host, state = dirs
    replaced = []
    real = os.replace
    monkeypatch.setattr(
        direct_intake.os, "replace", lambda a, b: replaced.append(str(b)) or real(a, b)
    )
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    with work.taking("advance"):
        assert str(state / INFLIGHT_NAME) in replaced
        assert not [
            p for p in state.iterdir() if p.name.startswith(".")
        ]  # no staging file left


def test_a_failed_round_releases_both_locks_and_the_record(dirs):
    host, state = dirs
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    with pytest.raises(RuntimeError), work.taking("grade"):
        raise RuntimeError("grade failed")
    assert (
        receipt_job.grading_busy(host) is False and not (state / INFLIGHT_NAME).exists()
    )
    with work.taking("grade"):  # the door's own lock was released too
        pass


def test_snapshot_refresh_never_waits_on_the_host_lock(dirs):
    """Validator 17:19 (1): skipping work rounds never starves the registration snapshot: the refresher is its own
    thread and takes no work lock, so snapshots stay fresh while every work round is declined.
    """
    import asyncio

    from carbon.battery.intake import refresher

    host, state = dirs
    fd = _hold_host(host)
    (state / DRAIN_NAME).write_text("{}")
    added = []

    class Window:
        def add(self, snapshot):
            added.append(snapshot)

    class Reader:
        async def capture(self, context):
            await asyncio.sleep(0)
            return object()

    stop = threading.Event()
    thread = threading.Thread(
        target=refresher,
        args=(Window(), None),
        kwargs={"reader": Reader(), "period": POLL, "stop": stop},
    )
    thread.start()
    try:
        time.sleep(10 * POLL)
    finally:
        stop.set()
        thread.join(2)
        _release(fd)
    assert len(added) >= 3
    import inspect

    source = inspect.getsource(direct_intake.serve_loopback)
    refresh_args = source[
        source.index("target=refresher") : source.index("target=_advance_loop")
    ]
    assert "work" not in refresh_args


def test_door_drain_tool_reads_this_door_only(dirs):
    host, state = dirs
    fd = _hold_host(host)  # another door grades: this door is still idle
    try:
        door_drain.start(state)
        assert door_drain.status(state, gap=0)["state"] == "IDLE"
        # a live in-flight record (this test process) = busy; a dead one = stale, not busy
        (state / INFLIGHT_NAME).write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "pid_start": direct_intake._process_start(os.getpid()),
                }
            )
        )
        assert door_drain.status(state, gap=0)["state"] == "BUSY"
        (state / INFLIGHT_NAME).write_text(
            json.dumps({"pid": 2**22 + 7, "pid_start": 5})
        )
        read = door_drain.status(state, gap=0)
        assert read["state"] == "IDLE" and read["read"]["stale_record"] is True
        (state / INFLIGHT_NAME).write_text(
            json.dumps({"pid": os.getpid(), "pid_start": 1})
        )
        assert (
            door_drain.status(state, gap=0)["state"] == "IDLE"
        )  # pid reused by another process
        (state / INFLIGHT_NAME).write_text("{not json")
        assert door_drain.status(state, gap=0)["state"] == "BUSY"  # doubt is never idle
        (state / INFLIGHT_NAME).write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "pid_start": direct_intake._process_start(os.getpid()),
                }
            )
        )
        ticks = iter(range(100))
        timed = door_drain.wait(
            state, 3, gap=0, poll=0, sleep=lambda s: None, clock=lambda: next(ticks)
        )
        assert timed["state"] == "TIMED_OUT" and (state / DRAIN_NAME).exists()
        assert (
            door_drain.clear(state) == {"state": "NOT_DRAINING"}
            and not (state / DRAIN_NAME).exists()
        )
    finally:
        _release(fd)


# --- self-review fixes ---------------------------------------------------------------------------------------------

BUSY_DOOR = r"""
import sys, threading, time
sys.path[:0] = sys.argv[3:]
from carbon.challenge_validator.direct_intake import _WorkLock
work = _WorkLock(sys.argv[1], poll_s=0.05)
end = time.monotonic() + float(sys.argv[2])
while time.monotonic() < end:  # back-to-back grade rounds, each holding the host lock 0.2 s
    with work.taking("grade", has_work=lambda: True):
        time.sleep(0.2)
"""


def test_a_waiting_door_gets_the_host_lock_between_a_busy_doors_rounds(dirs, tmp_path):
    """Fairness: a door polling every WORK_POLL_S is never shut out by another door's back-to-back rounds."""
    import subprocess
    import sys

    host, state = dirs
    script = tmp_path / "busy.py"
    script.write_text(BUSY_DOOR)
    busy = subprocess.Popen(
        [sys.executable, str(script), str(host), "90", *sys.path], env={**os.environ}
    )
    try:
        deadline = (
            time.monotonic() + 60
        )  # the busy door's interpreter imports carbon first
        while not receipt_job.grading_busy(host) and time.monotonic() < deadline:
            assert busy.poll() is None, "the busy door exited"
            time.sleep(0.01)
        assert receipt_job.grading_busy(host)
        work = _WorkLock(host, state_dir=state, poll_s=POLL)
        started = time.monotonic()
        with work.taking("grade", has_work=lambda: True):
            waited = time.monotonic() - started
        assert (
            waited < 3.0
        )  # a few of the busy door's rounds at most, not its whole backlog
    finally:
        busy.kill()
        busy.wait()


def test_drain_set_after_the_in_flight_record_declines_and_removes_it(
    dirs, monkeypatch
):
    """The window between the last check and the record is closed: the record goes first, then the check."""
    host, state = dirs
    real = direct_intake._write_record

    def then_drain(path, body):
        real(path, body)
        if path.name == INFLIGHT_NAME:
            (state / DRAIN_NAME).write_text(
                "{}"
            )  # the deploy's drain lands right after the record

    monkeypatch.setattr(direct_intake, "_write_record", then_drain)
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    with (
        pytest.raises(direct_intake.WorkDeclined, match="draining"),
        work.taking("grade"),
    ):
        pytest.fail("a round started after DRAINING")
    assert (
        not (state / INFLIGHT_NAME).exists() and receipt_job.grading_busy(host) is False
    )


def test_an_advance_round_never_looks_like_a_starving_door(dirs):
    host, state = dirs
    fd = _hold_host(host)
    stop = threading.Event()
    work = _WorkLock(host, state_dir=state, stop=stop, poll_s=POLL)
    thread = threading.Thread(
        target=lambda: pytest.raises(
            direct_intake.WorkDeclined, work.taking("advance").__enter__
        ),
        daemon=True,
    )
    thread.start()
    time.sleep(6 * POLL)
    assert not (state / WAIT_NAME).exists()
    assert not (host / direct_intake.WAITING_DIR).exists() or not list(
        (host / direct_intake.WAITING_DIR).iterdir()
    )
    stop.set()
    thread.join(2)
    _release(fd)


def test_the_old_with_form_is_per_thread(dirs):
    host, state = dirs
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    errors = []

    def use():
        try:
            for _ in range(20):
                with work:
                    time.sleep(0.001)
        except Exception as failure:  # noqa: BLE001
            errors.append(failure)

    threads = [threading.Thread(target=use) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert errors == [] and receipt_job.grading_busy(host) is False


def test_leftover_temp_files_are_removed_and_old_stale_records_trimmed(dirs):
    host, state = dirs
    (state / f".{INFLIGHT_NAME}.123.456").write_text("half")
    for n in range(8):
        (state / f"{INFLIGHT_NAME}.stale-{1000 + n}").write_text("{}")
    _WorkLock(host, state_dir=state)
    names = sorted(p.name for p in state.iterdir())
    assert not [n for n in names if n.startswith(".")]
    assert names == [f"{INFLIGHT_NAME}.stale-{1000 + n}" for n in range(3, 8)]


class _Pool:
    def __init__(self, path, records, attempts=(0, 0), now=10**6, incumbent=None):
        self.path, self._records, self._attempts = path, records, attempts
        self._now, self._incumbent = now, incumbent
        # this process has watched the store since time 0, so a planted attempt is ITS failure (spaced as before);
        # an attempt from an earlier process is the separate test below
        crown_pause_sweep._FIRST_SEEN[str(path)] = 0

    def paused_crowns(self, kind=None):
        assert kind == "pack"
        return list(self._records)

    def incumbent(self):
        return self._incumbent

    def crown_pause_attempts(self, submission_id, key):
        return self._attempts

    def clock(self):
        return self._now


def _grader(tmp_path, pending=(), pool=None, *, started=True):
    from types import SimpleNamespace

    from carbon.challenge_validator.auto_grade import AutoGrader

    grader = object.__new__(AutoGrader)
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(
            discovery=SimpleNamespace(evaluation_pack_digest="EXAM"),
            challenge_id="motor",
        )
    )
    grader.pending = lambda: list(pending)
    grader._pool = lambda: pool
    if started:
        grader._stranded_filed = True  # the once-per-start filing round has run
    return grader


def test_has_work_follows_the_crown_sweeps_own_gates(tmp_path):
    from carbon.challenge_validator import crown_pause_sweep, operator_pause

    pool_dir = tmp_path / "pool"
    pool_dir.mkdir(mode=0o700)
    record = {"submission_id": "rtsk_x", "evaluation_key": "k", "exam": "EXAM"}
    assert _grader(tmp_path, pending=["rtsk_a"]).has_work() is True
    assert _grader(tmp_path).has_work() is False
    assert _grader(tmp_path, pool=_Pool(pool_dir / "p.sqlite3", [])).has_work() is False
    due = _Pool(pool_dir / "p.sqlite3", [record])
    assert _grader(tmp_path, pool=due).has_work() is True
    spaced = _Pool(pool_dir / "p.sqlite3", [record], attempts=(1, 10**6 - 5))
    assert (
        _grader(tmp_path, pool=spaced).has_work() is False
    )  # inside its one-epoch retry spacing
    later = _Pool(
        pool_dir / "p.sqlite3",
        [record],
        attempts=(1, 10**6 - crown_pause_sweep.RETRY_SECONDS - 1),
    )
    assert _grader(tmp_path, pool=later).has_work() is True
    flag = operator_pause.flag_path(pool_dir)
    flag.write_text('{"crowns_paused": true, "weights_paused": false}')
    os.chmod(flag, 0o600)
    assert (
        _grader(tmp_path, pool=due).has_work() is False
    )  # the operator's pause: the sweep does nothing


class _UpkeepPool(_Pool):
    """A pool with the king's upkeep readers (`king_upkeep`): ``awaiting`` records wait for the king's regrade."""

    def __init__(
        self, path, records, *, awaiting=(), upkeep=(0, 0), bodies=(), mean=None, **kw
    ):
        super().__init__(path, records, incumbent={"model_id": "rtsk_king"}, **kw)
        self._awaiting, self._upkeep, self._bodies, self._mean = (
            set(awaiting),
            upkeep,
            list(bodies),
            mean,
        )

    def awaits_incumbent_regrade(self, record):
        return record["submission_id"] in self._awaiting

    def king_upkeep_attempts(self, king, exam, step):
        return self._upkeep

    def private_evaluation_bodies(self):
        return list(self._bodies)

    def crown_mean(self, king, key):
        return self._mean

    def crown_average_unstable(self, king, key):
        return False


def test_a_round_always_runs_once_after_a_start(tmp_path):
    """The first round files the challengers stranded while the king could not be met (`king_upkeep.file_stranded`),
    ahead of any new grade: an idle door must still run it, or the replay waits for the next submission.
    """
    assert _grader(tmp_path, started=False).has_work() is True
    assert _grader(tmp_path).has_work() is False


def test_a_record_waiting_for_the_kings_regrade_runs_a_round_only_when_the_regrade_is_due(
    tmp_path,
):
    pool_dir = tmp_path / "pool"
    pool_dir.mkdir(mode=0o700)
    waiting = {"submission_id": "rtsk_w", "evaluation_key": "k", "exam": "EXAM"}
    due = _UpkeepPool(pool_dir / "p.sqlite3", [waiting], awaiting=["rtsk_w"])
    assert _grader(tmp_path, pool=due).has_work() is True  # the king's regrade is due
    # the regrade failed this epoch: retried once an epoch, so no round (and no host lock) until then
    spaced = _UpkeepPool(
        pool_dir / "p.sqlite3", [waiting], awaiting=["rtsk_w"], upkeep=(1, 10**6 - 5)
    )
    assert _grader(tmp_path, pool=spaced).has_work() is False
    # a decidable record behind the waiting one still runs the sweep
    other = {"submission_id": "rtsk_o", "evaluation_key": "k2", "exam": "EXAM"}
    behind = _UpkeepPool(
        pool_dir / "p.sqlite3",
        [waiting, other],
        awaiting=["rtsk_w"],
        upkeep=(1, 10**6 - 5),
    )
    assert _grader(tmp_path, pool=behind).has_work() is True


def test_a_due_crown_re_measure_runs_a_round_on_an_idle_door(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from carbon.challenge_validator import crown_average

    pool_dir = tmp_path / "pool"
    pool_dir.mkdir(mode=0o700)
    king_eval = {
        "submission_id": "rtsk_king",
        "evaluation_key": "kk",
        "evidence": {"evaluation_pack_digest": "EXAM"},
    }
    rule = SimpleNamespace(margin_for=lambda challenge: 0.01)
    monkeypatch.setattr(
        crown_average, "ACTIVE", SimpleNamespace(rule=rule), raising=False
    )
    unmeasured = _UpkeepPool(pool_dir / "p.sqlite3", [], bodies=[king_eval])
    assert _grader(tmp_path, pool=unmeasured).has_work() is True
    measured = _UpkeepPool(pool_dir / "p.sqlite3", [], bodies=[king_eval], mean=0.5)
    assert _grader(tmp_path, pool=measured).has_work() is False
    unregistered = SimpleNamespace(
        rule=SimpleNamespace(margin_for=lambda challenge: None)
    )
    monkeypatch.setattr(crown_average, "ACTIVE", unregistered, raising=False)
    assert (
        _grader(tmp_path, pool=unmeasured).has_work() is False
    )  # averaging off: nothing to measure
    monkeypatch.setattr(crown_average, "ACTIVE", None, raising=False)
    assert _grader(tmp_path, pool=unmeasured).has_work() is False


def test_upkeep_due_and_step_agree(tmp_path):
    """`due` is `step`'s own plan: when it says nothing is due, `step` does nothing."""
    from types import SimpleNamespace

    from carbon.challenge_validator import king_upkeep

    pool_dir = tmp_path / "pool"
    pool_dir.mkdir(mode=0o700)
    intake = SimpleNamespace(
        adapter=SimpleNamespace(
            discovery=SimpleNamespace(evaluation_pack_digest="EXAM")
        )
    )
    waiting = {"submission_id": "rtsk_w", "evaluation_key": "k", "exam": "EXAM"}
    spaced = _UpkeepPool(
        pool_dir / "p.sqlite3", [waiting], awaiting=["rtsk_w"], upkeep=(1, 10**6 - 5)
    )
    assert king_upkeep.due(spaced, intake) is False
    assert (
        king_upkeep.step(
            spaced, intake, root=tmp_path, artifacts=tmp_path, entries=tmp_path
        )
        is None
    )
    broken = SimpleNamespace(king_upkeep_attempts=None, incumbent=lambda: 1 / 0)
    assert king_upkeep.due(broken, intake) is True  # doubt runs the round


def test_a_failure_from_before_this_process_started_is_retried_on_the_first_round(
    tmp_path,
):
    """Lead 5 Nov: after a switch the first round tries again at once; only this process's own failures are spaced."""
    pool_dir = tmp_path / "pool"
    pool_dir.mkdir(mode=0o700)
    record = {"submission_id": "rtsk_r", "evaluation_key": "k", "exam": "EXAM"}
    earlier = _Pool(pool_dir / "e.sqlite3", [record], attempts=(1, 10**6 - 5))
    crown_pause_sweep._FIRST_SEEN.pop(
        str(earlier.path)
    )  # this process has never looked at it
    assert (
        crown_pause_sweep.spaced(earlier, 1, 10**6 - 5) is False
    )  # filed before this process: due now
    assert _grader(tmp_path, pool=earlier).has_work() is True
    mine = _Pool(pool_dir / "m.sqlite3", [record], attempts=(1, 10**6 - 5))
    assert (
        crown_pause_sweep.spaced(mine, 1, 10**6 - 5) is True
    )  # this process's own failure: spaced
