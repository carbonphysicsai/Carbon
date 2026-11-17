"""Owner D6 (17 Nov 2026): a Ryzen (REMOTE grade lane) round's speed stage runs ON its box, under the box's own timing gate.

It used to be rebound to the grading host (`remote_lane.local_for`, removed): every remote round's speed stage then took
the host's ONE timing gate EXCLUSIVE, so 8 Ryzen lanes queued on GPUYard (474-532 s waits). Now:

- every op of a remote round, its timed speed calls included, goes to the lane's daemon (timed by the container's own
  monotonic clock: the box's);
- the timing gate is per machine (`grade_lanes.timing_gate`): the host's for a local lane, one per box for a remote lane,
  shared by that box's lanes; SHARED for each container, EXCLUSIVE for a timing stage, as before;
- the speed run's quiet is read ON the box (`host_quiet.box_counters`, in-run samples required: a healthy link);
- an upload to a box still holds THIS host's gate SHARED (its CPU and link), never a hold a speed probe watches.
"""

from __future__ import annotations

import threading

import pytest

from carbon.reconstruction import grade_lanes, remote_lane

pytest.importorskip("fcntl")

POLL = 0.02
BOX_A = "ssh://carbon-grade@fsn1.example"
BOX_B = "ssh://carbon-grade@hel1.example"


@pytest.fixture
def lock_dir(tmp_path):
    path = tmp_path / "locks"
    path.mkdir(mode=0o700)
    return str(path)


def _lane(lock_dir, index, host=None, cpuset="0-3"):
    return grade_lanes.Lane(
        index, cpuset, lock_dir, host, None if host is None else "/home/carbon"
    )


class _Hold:
    """A container hold on its own thread: entered, then held until told to go."""

    def __init__(self, lane, identity):
        self.entered, self.leave = threading.Event(), threading.Event()
        self.thread = threading.Thread(
            target=self._run, args=(lane, identity), daemon=True
        )
        self.thread.start()

    def _run(self, lane, identity):
        with (
            grade_lanes.bound(lane),
            grade_lanes.container_hold(identity=identity, poll_s=POLL),
        ):
            self.entered.set()
            assert self.leave.wait(10)

    def end(self):
        self.leave.set()
        self.thread.join(5)


def test_each_machine_has_its_own_timing_gate(lock_dir):
    host = grade_lanes.timing_gate(_lane(lock_dir, 0))
    a1 = grade_lanes.timing_gate(_lane(lock_dir, 2, BOX_A))
    a2 = grade_lanes.timing_gate(_lane(lock_dir, 4, BOX_A, "4-7"))
    b = grade_lanes.timing_gate(_lane(lock_dir, 3, BOX_B))
    assert host[0].name == grade_lanes.TIMING_LOCK
    assert a1 == a2  # the lanes of one box share its gate
    assert len({host, a1, b}) == 3


def test_a_box_timing_stage_waits_only_for_its_own_box(lock_dir):
    """A speed stage on box A waits for box A's other lane container, never for box B's or the grading host's."""
    neighbours = [
        _Hold(_lane(lock_dir, 4, BOX_A, "4-7"), "grade-op-a"),
        _Hold(_lane(lock_dir, 3, BOX_B), "grade-op-b"),
        _Hold(_lane(lock_dir, 0), "grade-op-host"),
    ]
    for hold in neighbours:
        assert hold.entered.wait(5)
    timing = _Hold(_lane(lock_dir, 2, BOX_A), "single-call-x")
    assert not timing.entered.wait(0.3)  # box A's neighbour still runs
    neighbours[1].end()
    neighbours[2].end()
    assert not timing.entered.wait(0.3)  # other machines never mattered
    neighbours[0].end()
    assert timing.entered.wait(5)
    # and while it runs, a host or box-B container starts at once; box A's next waits
    other = _Hold(_lane(lock_dir, 3, BOX_B), "grade-op-b2")
    local = _Hold(_lane(lock_dir, 1, cpuset="4-7"), "grade-op-host2")
    same = _Hold(_lane(lock_dir, 4, BOX_A, "4-7"), "grade-op-a2")
    assert other.entered.wait(5) and local.entered.wait(5)
    assert not same.entered.wait(0.3)
    timing.end()
    assert same.entered.wait(5)
    for hold in (other, local, same):
        hold.end()


def test_eight_box_speed_stages_on_two_boxes_never_queue_on_the_host(lock_dir):
    """A host timing stage holding the host gate EXCLUSIVE no longer stops any box's speed stage."""
    host_timing = _Hold(_lane(lock_dir, 0), "single-call-host")
    assert host_timing.entered.wait(5)
    stages = [
        _Hold(_lane(lock_dir, 2 + n, (BOX_A, BOX_B)[n % 2]), f"speed-lane-{n}")
        for n in range(8)
    ]
    for stage in stages:
        assert stage.entered.wait(5)  # in-lane runs: SHARED on their own box's gate
    for hold in (*stages, host_timing):
        hold.end()


def test_a_remote_rounds_timed_op_runs_on_its_box(monkeypatch):
    """The carrier sends every op of a remote round to the box: a single-call speed op and a measured query included."""
    from carbon.development_session import research_carrier

    seen = []
    monkeypatch.setattr(
        research_carrier,
        "_run_supervised",
        lambda ledger, **k: seen.append(remote_lane.docker_host()) or "ok",
    )
    lane = _lane("/var/lib/carbon/locks", 2, BOX_A)
    with grade_lanes.bound(lane):
        research_carrier._run(None, identity="single-call-" + "a" * 16, provenance="X")
        research_carrier._run(
            None,
            identity="grade-op-1",
            provenance="X",
            files={"control.json": b'{"measure_query": true}'},
        )
        research_carrier._run(None, identity="grade-op-2", provenance="X")
    assert seen == [BOX_A, BOX_A, BOX_A]


def test_the_speed_probe_of_a_remote_round_reads_the_box(monkeypatch):
    from carbon.challenge_validator import host_quiet, lean_recipe_retention

    asked = []

    def box_counters(lane):
        asked.append(lane.docker_host)
        return (lambda: 1), (lambda: 0)

    monkeypatch.setattr(host_quiet, "box_counters", box_counters)
    monkeypatch.setattr(
        host_quiet,
        "worker_containers",
        lambda: pytest.fail("a remote speed run never reads this host"),
    )
    with grade_lanes.bound(_lane("/var/lib/carbon/locks", 2, BOX_A)):
        probe = lean_recipe_retention._speed_probe()
    try:
        assert asked == [BOX_A] and probe.require_samples
    finally:
        probe._stop.set()


def test_an_upload_to_a_box_holds_both_gates_shared_and_still_goes_to_the_box(lock_dir):
    """Review of the first version: binding this host's twin around an upload made `remote_lane.mirror` see no remote
    round and copy nothing. The gates are now held WITHOUT a change of the round's binding (`grade_lanes.hold_gate`):
    the upload still targets the box, waits for this host's timing stage AND the box's, takes neither EXCLUSIVE, and no
    speed probe sees its holds."""
    from carbon.development_session import research_carrier

    box_lane = _lane(lock_dir, 2, BOX_A)
    for timing_lane in (_lane(lock_dir, 0), _lane(lock_dir, 4, BOX_A, "4-7")):
        seen, targets, done = [], [], threading.Event()
        timing = _Hold(timing_lane, "single-call-t")
        assert timing.entered.wait(5)

        def upload(seen=seen, targets=targets, done=done):
            with (
                grade_lanes.watch_holds(lambda event, ident: seen.append(ident)),
                grade_lanes.bound(box_lane),
                research_carrier._transfer_gates("single-call-op", box=True),
            ):
                targets.append(remote_lane.current())
            done.set()

        threading.Thread(target=upload, daemon=True).start()
        assert not done.wait(
            0.3
        )  # this host's, then the box's, timing stage: the upload waits
        timing.end()
        assert done.wait(5)
        assert targets == [
            box_lane
        ]  # the round's binding is intact: the upload goes to the box
        assert seen == []
    # SHARED, never EXCLUSIVE, even for a timing op's upload: a neighbour container on the box runs beside it
    neighbour = _Hold(_lane(lock_dir, 4, BOX_A, "4-7"), "grade-op-n")
    assert neighbour.entered.wait(5)
    with (
        grade_lanes.bound(box_lane),
        research_carrier._transfer_gates("single-call-op", box=True),
    ):
        pass
    neighbour.end()
    with research_carrier._transfer_gates("x", box=True):  # outside a round: nothing
        pass


def test_a_box_export_waits_for_this_hosts_timing_stage_within_its_budget(lock_dir):
    import time

    from carbon.development_session import research_carrier

    timing = _Hold(_lane(lock_dir, 0), "single-call-h")
    assert timing.entered.wait(5)
    with grade_lanes.bound(_lane(lock_dir, 2, BOX_A)):
        with (
            pytest.raises(remote_lane.RemoteLaneDown) as raised,
            research_carrier._remote_box_transfer(
                True,
                "grade-op",
                time.monotonic() + 0.2,
                b"remote_lane_export_timing_gate_busy",
            ),
        ):
            pytest.fail("an export beside this host's timing stage")
        assert raised.value.private_diagnostic == b"remote_lane_export_timing_gate_busy"
        timing.end()
        with research_carrier._remote_box_transfer(
            True, "grade-op", time.monotonic() + 5
        ):
            assert (
                remote_lane.current().docker_host == BOX_A
            )  # the stream reads the box


def test_one_box_has_one_gate_however_its_address_is_spelled(lock_dir):
    spelled = (
        "ssh://carbon-grade@FSN1.example",
        "ssh://carbon-grade@fsn1.example:22",
        "ssh://root@fsn1.example",
    )
    gates = {grade_lanes.timing_gate(_lane(lock_dir, 2, host)) for host in spelled}
    assert len(gates) == 1
    assert (
        grade_lanes.timing_gate(
            _lane(lock_dir, 2, "ssh://carbon-grade@fsn1.example:2222")
        )
        not in gates
    )


# -- the op clock never pays for a gate wait (rehearsal 17 Nov: 1 stream timeout, 2 wall stops, 1 subset_repeat_incomplete)


def test_a_holds_wait_for_the_gate_is_metered_for_its_op(lock_dir):
    """Every one of the rehearsal's failures was an op whose budget ran while it waited for a timing gate: the graded
    stream (`stream_to_file` timeout = what is left of the op's budget), the two wall stops (the program's budget), and the
    subset repeat (`subset_repeat_incomplete`: its op failed the same way). A wait is now metered per op
    (`grade_lanes.gate_wait_meter`) and added back to the op's clock (`research_carrier._credit_gate_waits`).
    """
    import time

    timing = _Hold(_lane(lock_dir, 2, BOX_A), "single-call-t")
    assert timing.entered.wait(5)
    waits = []

    def neighbour():
        with (
            grade_lanes.gate_wait_meter() as meter,
            grade_lanes.bound(_lane(lock_dir, 4, BOX_A, "4-7")),
            grade_lanes.container_hold(identity="grade-op", poll_s=POLL),
        ):
            waits.append(grade_lanes.gate_waits())
            assert meter == [waits[0]]

    thread = threading.Thread(target=neighbour, daemon=True)
    thread.start()
    time.sleep(0.4)
    timing.end()
    thread.join(5)
    assert waits and waits[0] >= 0.35
    assert grade_lanes.gate_waits() == 0.0  # outside an op's meter: nothing


def test_the_op_clock_moves_on_by_the_metered_waits_once():
    from carbon.development_session import research_carrier

    with grade_lanes.gate_wait_meter() as meter:
        assert research_carrier._credit_gate_waits(100.0, 5000.0, 0.0) == (
            100.0,
            5000.0,
            0.0,
        )
        meter.append(30.0)
        clock = research_carrier._credit_gate_waits(100.0, 5000.0, 0.0)
        assert clock == (130.0, 5030.0, 30.0)
        assert research_carrier._credit_gate_waits(*clock) == clock  # never twice
        meter.append(12.5)
        assert research_carrier._credit_gate_waits(*clock) == (142.5, 5042.5, 42.5)


def test_the_credit_comes_before_the_watchdog_and_the_programs_budget():
    """The op's watchdog, its program budget and every later deadline (streams, export) read the moved clock."""
    import inspect

    from carbon.development_session import research_carrier

    source = inspect.getsource(research_carrier._run_locked)
    credit = "_credit_gate_waits("
    watchdog = '_fixed_practice_stage(operation, provenance, "WATCHDOG")'
    program = '_fixed_practice_stage(operation, provenance, "PROGRAM")'
    assert source.count(credit) == 2
    first = source.index(credit)
    second = source.index(credit, first + 1)
    assert first < source.index(watchdog) < second < source.index(program)
    supervised = inspect.getsource(research_carrier._run_supervised)
    assert "gate_wait_meter()" in supervised


def test_a_session_ops_credit_never_carries_it_past_its_sessions_life():
    from carbon.development_session import research_carrier

    with grade_lanes.gate_wait_meter() as meter:
        meter.append(500.0)  # a long wait behind a timing stage
        # the session's life leaves room for 200 s of it only: the op still ends inside the session
        clock = research_carrier._credit_gate_waits(
            10.0, 1000.0, 0.0, ends_by_unix=1200.0
        )
        assert clock == (210.0, 1200.0, 200.0)
        # no room at all: no credit (the op runs on its own clock, as before)
        assert research_carrier._credit_gate_waits(
            10.0, 1000.0, 0.0, ends_by_unix=900.0
        ) == (10.0, 1000.0, 0.0)


def test_a_transfer_hold_is_shared_even_inside_a_timing_stage(lock_dir):
    neighbour = _Hold(_lane(lock_dir, 0), "grade-op-n")
    assert neighbour.entered.wait(5)  # SHARED on this host's gate
    with grade_lanes.timing_exclusive():
        # EXCLUSIVE would wait for the neighbour for good: SHARED enters at once
        with grade_lanes.hold_gate(_lane(lock_dir, 1, cpuset="4-7"), identity="x"):
            assert not grade_lanes.timing_requested()
        assert (
            grade_lanes.timing_requested()
        )  # the stage's own flag is back after the hold
    neighbour.end()


def test_a_local_sessions_upload_takes_no_second_hold_of_its_own_gate():
    """Re-review: on a LOCAL lane a live session holds this host's gate for its life; a second hold of it for an upload
    that copies nothing could wait behind a timing stage that waits for the first (a deadlock). Only a remote round's
    session upload takes the gates."""
    import inspect

    from carbon.development_session import research_carrier

    source = inspect.getsource(research_carrier._run_locked)
    i = source.index("remote_lane.mirror(session.input)")
    guard = source[max(0, i - 400) : i]
    assert "_transfer_gates(identity, box=not session.live)" in guard
    assert "if remote_lane.current() is not None" in guard
    assert "else nullcontext()" in guard
