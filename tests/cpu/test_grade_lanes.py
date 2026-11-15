"""Two grade lanes per grading host (owner 15 Nov 2026; `carbon.reconstruction.grade_lanes`).

Fail closed to one lane: a door grades in two-lane mode only with a values row, a v2 host record of disjoint lanes and
no SMT sibling shared across lanes; a one-lane door holds every lane (today's single host lock). A two-lane round holds
one lane, is pinned to its cores, and never runs beside a door that does not know about lanes. Timing stages wait for
every other lane container to end, and no lane container starts while one waits."""

from __future__ import annotations

import fcntl
import json
import os
import threading
import time

import pytest

from carbon.backbone_catalog import receipt_job
from carbon.challenge_validator.direct_intake import INFLIGHT_NAME, _WorkLock
from carbon.development_session.profile import canonical
from carbon.reconstruction import grade_lanes
from carbon.reconstruction.host_execution import (
    HOST_EXECUTION_RECORD,
    HOST_EXECUTION_SCHEMA,
    HOST_EXECUTION_SCHEMA_V2,
    HostExecutionRecord,
    resolve_cpuset,
)
from carbon.reconstruction.worker.model import MEMORY_BYTES, WorkerFailure

POLL = 0.02
LANES = ("0-3", "4-7")


def _registry(tmp_path, rows):
    path = tmp_path / "grade_lanes.json"
    path.write_text(json.dumps({"schema": grade_lanes.SCHEMA, "rows": rows}))
    return path


def _record(root, **document):
    body = {
        "schema": HOST_EXECUTION_SCHEMA_V2,
        "cpuset": "0-3",
        "memory_bytes": MEMORY_BYTES,
        "lanes": list(LANES),
        **document,
    }
    path = root / HOST_EXECUTION_RECORD
    path.write_bytes(canonical(body))
    os.chmod(path, 0o600)
    return root


def _sysfs(root, siblings, offline=()):
    """A fake /sys/devices/system/cpu: ``siblings`` maps core -> its thread_siblings_list."""
    for core, value in siblings.items():
        topology = root / f"cpu{core}" / "topology"
        topology.mkdir(parents=True)
        (topology / "thread_siblings_list").write_text(value + "\n")
        if core:
            (root / f"cpu{core}" / "online").write_text(
                "0\n" if core in offline else "1\n"
            )
    return root


def _no_smt(root):
    return _sysfs(root, {core: str(core) for core in range(8)})


# -- the values row -----------------------------------------------------------------------------------------------------


def test_the_values_row_allows_two_lanes_and_anything_else_is_one(tmp_path):
    key = ("electric-motor-magnetics", "1.8")
    assert grade_lanes.registered_lanes(*key, path=tmp_path / "absent.json") == 1
    assert grade_lanes.registered_lanes(*key, path=_registry(tmp_path, {})) == 1
    two = _registry(tmp_path, {"electric-motor-magnetics 1.8": {"lanes": 2}})
    assert grade_lanes.registered_lanes(*key, path=two) == 2
    assert (
        grade_lanes.registered_lanes("electric-motor-magnetics", "1.7", path=two) == 1
    )
    for row in (
        {"lanes": 3},
        {"lanes": "2"},
        {"lanes": True},
        {"lanes": 2, "x": 1},
        [2],
    ):
        path = _registry(tmp_path, {"electric-motor-magnetics 1.8": row})
        assert grade_lanes.registered_lanes(*key, path=path) == 1, row
    wrong = tmp_path / "wrong.json"
    wrong.write_text(
        json.dumps(
            {"schema": "other", "rows": {"electric-motor-magnetics 1.8": {"lanes": 2}}}
        )
    )
    assert grade_lanes.registered_lanes(*key, path=wrong) == 1
    garbage = tmp_path / "garbage.json"
    garbage.write_text("{")
    assert grade_lanes.registered_lanes(*key, path=garbage) == 1


def test_the_shipped_values_file_enables_two_lanes_for_motor_18_only():
    """The owner's row (typed 15 Nov 17:02 CST, Deploy-B): two lanes for Motor 1.8 and no other version."""
    document = json.loads(grade_lanes.REGISTRY.read_bytes())
    assert document == {
        "schema": grade_lanes.SCHEMA,
        "rows": {"electric-motor-magnetics 1.8": {"lanes": 2}},
    }
    assert grade_lanes.registered_lanes("electric-motor-magnetics", "1.8") == 2
    assert grade_lanes.registered_lanes("electric-motor-magnetics", "1.7") == 1
    assert grade_lanes.REGISTRY.read_bytes().count(b"\r") == 0


def test_every_lane_lock_is_one_the_receipt_worker_tests():
    names = {grade_lanes.lane_lock_name(i) for i in range(grade_lanes.MAX_LANES)}
    assert names == {receipt_job.GRADING_LOCK, *receipt_job.LANE_LOCKS}
    assert grade_lanes.lane_lock_name(0) == receipt_job.GRADING_LOCK


# -- the host record ----------------------------------------------------------------------------------------------------


def test_a_v2_record_lists_disjoint_lanes_of_one_size(tmp_path):
    record = HostExecutionRecord.load(_record(tmp_path))
    assert record.lanes == LANES and record.cpuset == "0-3"
    v1 = tmp_path / "v1"
    v1.mkdir(mode=0o700)
    (v1 / HOST_EXECUTION_RECORD).write_bytes(
        canonical(
            {
                "schema": HOST_EXECUTION_SCHEMA,
                "cpuset": "0-3",
                "memory_bytes": MEMORY_BYTES,
            }
        )
    )
    os.chmod(v1 / HOST_EXECUTION_RECORD, 0o600)
    assert HostExecutionRecord.load(v1).lanes == ()


@pytest.mark.parametrize(
    "lanes",
    [
        ["0-3", "3-6"],
        ["0-3", "4-6"],
        ["0-3"],
        ["0-3", "x"],
        "0-3,4-7",
        [["0-3"], ["4-7"]],
    ],
)
def test_overlapping_unequal_single_or_malformed_lanes_are_refused(tmp_path, lanes):
    _record(tmp_path, lanes=lanes)
    with pytest.raises(WorkerFailure):
        HostExecutionRecord.load(tmp_path)


def test_a_v1_record_with_lanes_or_a_v2_record_without_them_is_refused(tmp_path):
    _record(tmp_path, schema=HOST_EXECUTION_SCHEMA)
    with pytest.raises(WorkerFailure):
        HostExecutionRecord.load(tmp_path)
    (tmp_path / HOST_EXECUTION_RECORD).write_bytes(
        canonical(
            {
                "schema": HOST_EXECUTION_SCHEMA_V2,
                "cpuset": "0-3",
                "memory_bytes": MEMORY_BYTES,
            }
        )
    )
    with pytest.raises(WorkerFailure):
        HostExecutionRecord.load(tmp_path)


# -- SMT siblings (F1) --------------------------------------------------------------------------------------------------


def test_lanes_need_their_smt_siblings_inside_them(tmp_path):
    assert grade_lanes.siblings_inside(LANES, sys_cpu=_no_smt(tmp_path / "a"))
    # SMT pairs inside each lane: fine
    paired = {
        0: "0-1",
        1: "0-1",
        2: "2-3",
        3: "2-3",
        4: "4-5",
        5: "4-5",
        6: "6-7",
        7: "6-7",
    }
    assert grade_lanes.siblings_inside(LANES, sys_cpu=_sysfs(tmp_path / "b", paired))
    # core 3's sibling is core 4, in the other lane: refused
    across = {**{c: str(c) for c in range(8)}, 3: "3-4", 4: "3-4"}
    assert not grade_lanes.siblings_inside(
        LANES, sys_cpu=_sysfs(tmp_path / "c", across)
    )
    # a core missing, offline, or unreadable is not proof
    assert not grade_lanes.siblings_inside(
        LANES, sys_cpu=_sysfs(tmp_path / "d", {c: str(c) for c in range(7)})
    )
    assert not grade_lanes.siblings_inside(
        LANES,
        sys_cpu=_sysfs(tmp_path / "e", {c: str(c) for c in range(8)}, offline=(5,)),
    )
    broken = _no_smt(tmp_path / "f")
    (broken / "cpu6" / "topology" / "thread_siblings_list").write_text("junk")
    assert not grade_lanes.siblings_inside(LANES, sys_cpu=broken)


def test_a_door_gets_two_lanes_only_when_row_record_and_topology_all_agree(tmp_path):
    key = ("electric-motor-magnetics", "1.8")
    row = _registry(tmp_path, {"electric-motor-magnetics 1.8": {"lanes": 2}})
    host = tmp_path / "host"
    host.mkdir(mode=0o700)
    _record(host)
    sys_cpu = _no_smt(tmp_path / "sys")
    assert (
        grade_lanes.door_lanes(*key, registry=row, host_root=host, sys_cpu=sys_cpu)
        == LANES
    )
    # no row
    assert (
        grade_lanes.door_lanes(
            *key, registry=_registry(tmp_path, {}), host_root=host, sys_cpu=sys_cpu
        )
        == ()
    )
    # no v2 record
    bare = tmp_path / "bare"
    bare.mkdir(mode=0o700)
    assert (
        grade_lanes.door_lanes(*key, registry=row, host_root=bare, sys_cpu=sys_cpu)
        == ()
    )
    # shared SMT sibling
    across = _sysfs(
        tmp_path / "across", {**{c: str(c) for c in range(8)}, 3: "3-4", 4: "3-4"}
    )
    assert (
        grade_lanes.door_lanes(*key, registry=row, host_root=host, sys_cpu=across) == ()
    )
    # a broken record never raises out of here: one lane
    (host / HOST_EXECUTION_RECORD).write_text("{")
    assert (
        grade_lanes.door_lanes(*key, registry=row, host_root=host, sys_cpu=sys_cpu)
        == ()
    )


# -- per-lane cores -----------------------------------------------------------------------------------------------------


def test_a_bound_lane_decides_the_cores_and_never_falls_back(tmp_path):
    _record(tmp_path)
    assert resolve_cpuset(logical_cpus=8, root=tmp_path, count=4) == "0-3"
    with grade_lanes.bound(grade_lanes.Lane(1, "4-7", str(tmp_path))):
        assert resolve_cpuset(logical_cpus=8, root=tmp_path, count=4) == "4-7"
        # a lane of the wrong size, or cores this host does not have: refused, never trimmed or replaced
        with pytest.raises(WorkerFailure):
            resolve_cpuset(logical_cpus=8, root=tmp_path, count=2)
        with pytest.raises(WorkerFailure):
            resolve_cpuset(logical_cpus=6, root=tmp_path, count=4)
    assert grade_lanes.current() is None


# -- the host lock ------------------------------------------------------------------------------------------------------


@pytest.fixture
def host(tmp_path):
    path = tmp_path / "host"
    path.mkdir(mode=0o700)
    return path


def _held(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(fd)
    return False


def _in_round(work, entered, leave, seen):
    with work.taking("grade", has_work=lambda: True):
        seen.append((grade_lanes.current(), work._lane))
        entered.set()
        leave.wait(10)


def _start_round(work):
    entered, leave, seen = threading.Event(), threading.Event(), []
    thread = threading.Thread(
        target=_in_round, args=(work, entered, leave, seen), daemon=True
    )
    thread.start()
    return entered, leave, seen, thread


def test_a_one_lane_door_holds_every_lane_and_its_record_is_unchanged(host, tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    entered, leave, seen, thread = _start_round(work)
    assert entered.wait(5)
    assert _held(host / receipt_job.GRADING_LOCK) and _held(
        host / grade_lanes.lane_lock_name(1)
    )
    assert receipt_job.grading_busy(host)
    record = json.loads((state / INFLIGHT_NAME).read_text())
    assert set(record) == {"schema", "kind", "pid", "pid_start", "since_ns"}
    assert seen == [(None, None)]
    # a two-lane door finds no free lane beside it
    other = _WorkLock(host, poll_s=POLL, lanes=LANES)
    assert other._try_host() is False and other._fds == []
    leave.set()
    thread.join(5)
    assert not _held(host / receipt_job.GRADING_LOCK)
    assert not _held(host / grade_lanes.lane_lock_name(1))
    assert not receipt_job.grading_busy(host)


def test_two_two_lane_doors_grade_at_once_each_on_its_own_lane(host, tmp_path):
    states = []
    works = []
    for name in ("a", "b"):
        state = tmp_path / name
        state.mkdir(mode=0o700)
        states.append(state)
        works.append(_WorkLock(host, state_dir=state, poll_s=POLL, lanes=LANES))
    first = _start_round(works[0])
    assert first[0].wait(5)
    second = _start_round(works[1])
    assert second[0].wait(5)
    (lane_a, held_a), (lane_b, held_b) = first[2][0], second[2][0]
    assert (lane_a.index, lane_a.cpuset) == (0, "0-3") and held_a == lane_a
    assert (lane_b.index, lane_b.cpuset) == (1, "4-7") and held_b == lane_b
    for state, lane in zip(states, (lane_a, lane_b)):
        record = json.loads((state / INFLIGHT_NAME).read_text())
        assert (record["lane"], record["cpuset"]) == (lane.index, lane.cpuset)
    # a third two-lane door waits: both lanes held
    third = _WorkLock(host, poll_s=POLL, lanes=LANES)
    assert third._try_host() is False
    # a one-lane door cannot take the host either
    assert _WorkLock(host, poll_s=POLL)._try_host() is False
    assert receipt_job.grading_busy(host)
    first[1].set()
    first[3].join(5)
    # lane 1 still held: the host is still grading, and a one-lane door still waits for it
    assert receipt_job.grading_busy(host)
    assert _WorkLock(host, poll_s=POLL)._try_host() is False
    second[1].set()
    second[3].join(5)
    assert not receipt_job.grading_busy(host)
    for name in ("lane-0", "lane-1"):
        assert not (host / f"official-grading.{name}.holder").exists()


def test_a_two_lane_round_never_runs_beside_a_door_that_does_not_know_about_lanes(host):
    """An older build holds the host lock (lane 0) and writes no holder record: lane 1 is not taken beside it."""
    old = os.open(host / receipt_job.GRADING_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(old, fcntl.LOCK_EX)
    try:
        work = _WorkLock(host, poll_s=POLL, lanes=LANES)
        assert work._try_host() is False
        assert work._fds == [] and not _held(host / grade_lanes.lane_lock_name(1))
    finally:
        fcntl.flock(old, fcntl.LOCK_UN)
        os.close(old)
    work = _WorkLock(host, poll_s=POLL, lanes=LANES)
    assert work._try_host() is True and work._lane.index == 0
    work._release_host()


def test_a_stale_holder_record_of_a_dead_process_is_not_two_lane_mode(host):
    (host / "official-grading.lane-0.holder").write_text(
        f"999999999-1-{grade_lanes.TWO_LANE_MODE}"
    )
    assert grade_lanes.held_in_two_lane_mode(host, 0) is False
    grade_lanes.write_holder(host, 0, grade_lanes.TWO_LANE_MODE)
    assert grade_lanes.held_in_two_lane_mode(host, 0) is True
    grade_lanes.write_holder(host, 0, grade_lanes.ONE_LANE_MODE)
    assert grade_lanes.held_in_two_lane_mode(host, 0) is False


# -- the timing gate (F3) -----------------------------------------------------------------------------------------------


def test_outside_a_lane_bound_round_a_container_takes_no_gate(host):
    with grade_lanes.container_hold() as lane:
        assert lane is None
    assert not (host / grade_lanes.TIMING_LOCK).exists()


def _container(lane, *, exclusive, started, leave, log):
    def run():
        with grade_lanes.bound(lane):
            if exclusive:
                with (
                    grade_lanes.timing_exclusive(),
                    grade_lanes.container_hold(poll_s=POLL),
                ):
                    log.append(("start", lane.index, "timing", time.monotonic()))
                    started.set()
                    leave.wait(10)
            else:
                with grade_lanes.container_hold(poll_s=POLL):
                    log.append(("start", lane.index, "shared", time.monotonic()))
                    started.set()
                    leave.wait(10)
        log.append(("end", lane.index, exclusive, time.monotonic()))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_lane_containers_share_and_a_timing_stage_waits_for_the_neighbour_to_end(host):
    lane0, lane1 = (
        grade_lanes.Lane(i, cpus, str(host)) for i, cpus in enumerate(LANES)
    )
    log = []
    a_started, a_leave = threading.Event(), threading.Event()
    b_started, b_leave = threading.Event(), threading.Event()
    a = _container(lane0, exclusive=False, started=a_started, leave=a_leave, log=log)
    assert a_started.wait(5)
    b = _container(lane1, exclusive=False, started=b_started, leave=b_leave, log=log)
    assert b_started.wait(5)  # two ordinary containers run at once
    b_leave.set()
    b.join(5)
    # lane 1's speed stage: waits while lane 0's container runs
    t_started, t_leave = threading.Event(), threading.Event()
    t = _container(lane1, exclusive=True, started=t_started, leave=t_leave, log=log)
    assert not t_started.wait(0.3)
    assert any(p.is_file() for p in (host / grade_lanes.TIMING_WANTED_DIR).iterdir())
    # while it waits, lane 0's NEXT container does not start
    a_leave.set()
    a.join(5)
    n_started, n_leave = threading.Event(), threading.Event()
    n = _container(lane0, exclusive=False, started=n_started, leave=n_leave, log=log)
    assert t_started.wait(5)
    assert not n_started.wait(0.3)
    t_leave.set()
    t.join(5)
    assert n_started.wait(5)  # it starts once the timing stage is done
    n_leave.set()
    n.join(5)
    assert list((host / grade_lanes.TIMING_WANTED_DIR).iterdir()) == []
    timing_start = next(e[3] for e in log if e[:3] == ("start", 1, "timing"))
    lane0_first_end = next(e[3] for e in log if e[:2] == ("end", 0))
    assert timing_start >= lane0_first_end


def test_a_timing_wish_of_a_dead_process_holds_nobody_back(host):
    wanted = host / grade_lanes.TIMING_WANTED_DIR
    wanted.mkdir()
    (wanted / "999999999-1-1").touch()
    lane = grade_lanes.Lane(0, "0-3", str(host))
    started, leave, log = threading.Event(), threading.Event(), []
    thread = _container(lane, exclusive=False, started=started, leave=leave, log=log)
    assert started.wait(5)
    leave.set()
    thread.join(5)


def test_the_speed_stage_is_a_timing_stage_by_its_carrier_identity(host):
    """No grading file outside the carrier carries a lane line: the single-design speed calls are recognised by the
    identity `lean_recipe_retention._single_call_raw` gives its operation. Renaming it there must fail here.
    """
    from pathlib import Path

    import carbon.challenge_validator.lean_recipe_retention as retention

    source = Path(retention.__file__).read_text(encoding="utf-8")
    body = source[source.index("def _single_call_raw(") :]
    body = body[: body.index("\ndef ", 1)]
    assert 'identity="single-call-"' in body.replace("\n", "").replace(" ", "")
    assert grade_lanes.is_timing_identity("single-call-" + "0" * 64)
    assert not grade_lanes.is_timing_identity("graded-" + "0" * 64)
    assert not grade_lanes.is_timing_identity(None)
    # an exclusive hold by identity waits for the neighbour's container like `timing_exclusive`
    lane0, lane1 = (
        grade_lanes.Lane(i, cpus, str(host)) for i, cpus in enumerate(LANES)
    )
    started, leave, log = threading.Event(), threading.Event(), []
    neighbour = _container(
        lane0, exclusive=False, started=started, leave=leave, log=log
    )
    assert started.wait(5)
    done = threading.Event()

    def speed():
        with (
            grade_lanes.bound(lane1),
            grade_lanes.container_hold(identity="single-call-x", poll_s=POLL),
        ):
            done.set()

    thread = threading.Thread(target=speed, daemon=True)
    thread.start()
    assert not done.wait(0.3)
    leave.set()
    neighbour.join(5)
    assert done.wait(5)
    thread.join(5)
