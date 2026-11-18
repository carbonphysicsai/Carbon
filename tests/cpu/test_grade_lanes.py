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
    """The owner's row (typed 15 Nov 17:02 CST, Deploy-B): two lanes for Motor 1.8 and no other version. Remote lanes:
    PROPOSED 8 = two 5950X boxes x 4 lanes (OWNER-5950X-GRADING-CLASS-01; CV-Motor/V2 to confirm).
    """
    document = json.loads(grade_lanes.REGISTRY.read_bytes())
    assert document == {
        "schema": grade_lanes.SCHEMA,
        "rows": {"electric-motor-magnetics 1.8": {"lanes": 2, "remote_lanes": 8}},
    }
    assert grade_lanes.registered_lanes("electric-motor-magnetics", "1.8") == 2
    assert grade_lanes.registered_lanes("electric-motor-magnetics", "1.7") == 1
    assert grade_lanes.registered_remote_lanes("electric-motor-magnetics", "1.8") == 8
    assert grade_lanes.registered_remote_lanes("electric-motor-magnetics", "1.7") == 0
    assert 8 <= grade_lanes.MAX_REMOTE_LANES
    assert grade_lanes.REGISTRY.read_bytes().count(b"\r") == 0


def test_every_lane_lock_is_one_the_receipt_worker_tests():
    # every lane, a remote one's too (`grade_lanes.ALL_LANES`)
    names = {grade_lanes.lane_lock_name(i) for i in range(grade_lanes.ALL_LANES)}
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
    assert (
        resolve_cpuset(logical_cpus=8, root=tmp_path, count=3) == "0,1,2"
    )  # the record's, narrowed
    with grade_lanes.bound(grade_lanes.Lane(1, "4-7", str(tmp_path))):
        assert resolve_cpuset(logical_cpus=8, root=tmp_path, count=4) == "4-7"
        # today's count gets exactly 2 of the lane's cores (V2, 18 Nov: a default worker is created with --cpus 2 and the
        # kernel check holds that quota to the cpuset's size, so the whole 4-core lane would refuse it); never refused
        assert resolve_cpuset(logical_cpus=8, root=tmp_path, count=2) == "4,5"
        # switch 5: a sized worker of fewer CPUs than the lane runs on exactly its own count of the lane's cores, the
        # lowest (the kernel check holds its quota to that); more CPUs than the lane, or cores the host lacks: refused
        assert resolve_cpuset(logical_cpus=8, root=tmp_path, count=3) == "4,5,6"
        with pytest.raises(WorkerFailure):
            resolve_cpuset(logical_cpus=8, root=tmp_path, count=5)
        with pytest.raises(WorkerFailure):
            resolve_cpuset(logical_cpus=6, root=tmp_path, count=4)
    assert grade_lanes.current() is None


def test_a_default_worker_gets_exactly_its_count_and_fewer_cores_never_refuse_it():
    """V2 (18 Nov): a container's --cpus is its profile's count and the kernel check holds that quota to the cpuset's
    size, so the cores are narrowed to the count; at today's count a smaller set is returned as given, never refused.
    """
    from carbon.reconstruction.host_execution import _fitted
    from carbon.reconstruction.worker.model import CPU_COUNT

    assert _fitted("4-7", logical_cpus=8, count=CPU_COUNT) == ",".join(
        str(core) for core in range(4, 4 + CPU_COUNT)
    )
    assert _fitted("5", logical_cpus=8, count=CPU_COUNT) == "5"
    assert _fitted("4-7", logical_cpus=8, count=4) == "4-7"
    with pytest.raises(WorkerFailure):
        _fitted("4-5", logical_cpus=8, count=4)


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


def _in_round(work, entered, leave, seen, kind="grade"):
    with work.taking(kind, has_work=lambda: True):
        seen.append((grade_lanes.current(), work._lane))
        entered.set()
        leave.wait(10)


def _start_round(work, kind="grade"):
    entered, leave, seen = threading.Event(), threading.Event(), []
    thread = threading.Thread(
        target=_in_round, args=(work, entered, leave, seen, kind), daemon=True
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
    # a two-lane round keeps its lane on the round itself (parallel rounds), never on the door's shared lock object
    assert (lane_a.index, lane_a.cpuset) == (0, "0-3") and held_a is None
    assert (lane_b.index, lane_b.cpuset) == (1, "4-7") and held_b is None
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


# -- one door, a round per lane (parallel rounds, owner's order 16 Nov) ---------------------------------------------------


def test_one_two_lane_door_runs_two_grade_rounds_at_once_one_per_lane(host, tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    work = _WorkLock(host, state_dir=state, poll_s=POLL, lanes=LANES)
    first = _start_round(work)
    assert first[0].wait(5)
    second = _start_round(work)
    assert second[0].wait(5)
    lanes = sorted(round_[2][0][0].index for round_ in (first, second))
    assert lanes == [0, 1]
    # a third round of the same door waits: both lanes are held
    third = _start_round(work)
    assert not third[0].wait(0.5)
    # the door's in-flight record names its OLDEST live round while any runs (a drain sees busy)
    record = json.loads((state / INFLIGHT_NAME).read_text())
    assert record["lane"] == first[2][0][0].index
    first[1].set()
    first[3].join(5)
    assert third[0].wait(5)  # the freed lane goes to the waiting round
    assert third[2][0][0].index == first[2][0][0].index
    assert (state / INFLIGHT_NAME).exists()
    for round_ in (second, third):
        round_[1].set()
        round_[3].join(5)
    assert not (state / INFLIGHT_NAME).exists()
    assert not receipt_job.grading_busy(host)
    for name in ("lane-0", "lane-1"):
        assert not (host / f"official-grading.{name}.holder").exists()


def test_without_owner_claims_rounds_of_another_kind_still_never_overlap(
    host, tmp_path
):
    """A door whose rounds take no owners keeps the old rule: a build round never runs beside a grade round."""
    work = _WorkLock(host, poll_s=POLL, lanes=LANES)
    grade = _start_round(work, "grade")
    assert grade[0].wait(5)
    advance = _start_round(work, "advance")
    assert not advance[0].wait(0.5)
    grade[1].set()
    grade[3].join(5)
    assert advance[0].wait(5)
    advance[1].set()
    advance[3].join(5)


def test_a_build_round_and_a_grade_round_run_at_once_each_on_its_own_lane(
    host, tmp_path
):
    """A19 (Lead, 16 Nov 2026): a build (advance) round runs beside a grade round of the same door, each on a lane."""
    work = _WorkLock(host, poll_s=POLL, lanes=LANES)
    work.overlap_kinds = (
        True  # a door whose rounds take owners (`grade_sequencer.OwnerClaims`)
    )
    grade = _start_round(work, "grade")
    assert grade[0].wait(5)
    advance = _start_round(work, "advance")
    assert advance[0].wait(5)
    assert sorted(r[2][0][0].index for r in (grade, advance)) == [0, 1]
    for round_ in (grade, advance):
        round_[1].set()
        round_[3].join(5)


def test_a_waiting_build_round_is_not_starved_by_new_grade_rounds(host):
    """Both lanes grading, a build round waits: the next free lane goes to the build, not to a NEW grade round."""
    work = _WorkLock(host, poll_s=POLL, lanes=LANES)
    work.overlap_kinds = (
        True  # a door whose rounds take owners (`grade_sequencer.OwnerClaims`)
    )
    grades = [_start_round(work, "grade") for _ in range(2)]
    for grade in grades:
        assert grade[0].wait(5)
    advance = _start_round(work, "advance")
    time.sleep(0.2)  # the build round now waits for a lane
    late = _start_round(work, "grade")
    assert not late[0].wait(0.3)
    grades[0][1].set()
    grades[0][3].join(5)
    assert advance[0].wait(5)  # the freed lane went to the waiting build
    assert not late[0].wait(0.3)
    grades[1][1].set()
    grades[1][3].join(5)
    assert late[0].wait(5)
    for round_ in (advance, late):
        round_[1].set()
        round_[3].join(5)


def test_a_waiting_grade_round_is_not_starved_by_new_build_rounds(host):
    work = _WorkLock(host, poll_s=POLL, lanes=LANES)
    work.overlap_kinds = (
        True  # a door whose rounds take owners (`grade_sequencer.OwnerClaims`)
    )
    builds = [_start_round(work, "advance") for _ in range(2)]
    for build in builds:
        assert build[0].wait(5)
    grade = _start_round(work, "grade")
    time.sleep(0.2)
    late = _start_round(work, "advance")
    assert not late[0].wait(0.3)
    builds[0][1].set()
    builds[0][3].join(5)
    assert grade[0].wait(5)
    assert not late[0].wait(0.3)
    builds[1][1].set()
    builds[1][3].join(5)
    assert late[0].wait(5)
    for round_ in (grade, late):
        round_[1].set()
        round_[3].join(5)


def test_a_one_lane_door_still_runs_one_round_at_a_time(host):
    work = _WorkLock(host, poll_s=POLL)
    first = _start_round(work)
    assert first[0].wait(5)
    second = _start_round(work)
    assert not second[0].wait(0.5)
    first[1].set()
    first[3].join(5)
    assert second[0].wait(5)
    second[1].set()
    second[3].join(5)


def test_a_draining_door_gives_up_a_round_waiting_for_a_slot(host, tmp_path):
    from carbon.challenge_validator.direct_intake import DRAIN_NAME, WorkDeclined

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    work = _WorkLock(host, state_dir=state, poll_s=POLL, lanes=LANES)
    rounds = [_start_round(work) for _ in range(2)]
    for round_ in rounds:
        assert round_[0].wait(5)
    (state / DRAIN_NAME).touch()
    with pytest.raises(WorkDeclined), work.taking("grade"):
        pass
    for round_ in rounds:
        round_[1].set()
        round_[3].join(5)


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


# -- no timing gate (owner, 17 Nov 2026: lane core pinning is the timing protection) ----------------------------------


def test_there_is_no_host_or_box_timing_gate():
    """Each lane times its candidate on its own pinned cores: no lock, no wish list, no hold any lane waits on."""
    for gone in (
        "TIMING_LOCK",
        "TIMING_WANTED_DIR",
        "BOX_TIMING_LOCK",
        "BOX_TIMING_WANTED_DIR",
        "timing_gate",
        "timing_wanted",
        "container_hold",
        "hold_gate",
        "TimingGateBusy",
        "gate_wait_meter",
        "watch_holds",
    ):
        assert not hasattr(grade_lanes, gone), gone


def test_a_timing_stage_is_only_marked_by_its_carrier_identity():
    """The single-design speed calls without a registered ceiling keep their timing identity (their grade's session is
    closed first); the in-lane run is not one. Neither takes a gate. Renaming either in `_speed_stage` must fail here.
    """
    from pathlib import Path

    import carbon.challenge_validator.lean_recipe_retention as retention

    source = Path(retention.__file__).read_text(encoding="utf-8")
    body = source[source.index("def _speed_stage(") :]
    body = body[: body.index("\ndef ", 1)]
    flat = body.replace("\n", "").replace(" ", "")
    assert 'timed("single-call-"+name)' in flat
    assert 'f"{SPEED_LANE_PREFIX}{name}-r{k}"' in flat
    assert "alone" not in flat  # no solo rerun
    assert not grade_lanes.is_timing_identity(retention.SPEED_LANE_PREFIX + "x-r0")
    assert grade_lanes.is_timing_identity("single-call-" + "0" * 64)
    assert not grade_lanes.is_timing_identity("graded-" + "0" * 64)
    assert not grade_lanes.is_timing_identity(None)
    assert not grade_lanes.timing_requested()
    with grade_lanes.timing_exclusive():
        assert grade_lanes.timing_requested()
    assert not grade_lanes.timing_requested()


def test_a_remote_only_door_takes_only_its_remote_lanes_at_their_usual_places(host):
    """A door's own remote record with ``"only": true`` (a scratch door's re-grades on a remote box): its rounds take
    its remote lanes alone, at the places they have beside the local lanes (2, 3), so lock names and holder records
    never collide with a live door's local lanes 0 and 1."""
    from carbon.reconstruction import remote_lane

    remote = remote_lane.RemoteSpec("ssh://carbon-grade@box.example", "0-3", "/srv/gb")
    work = _WorkLock(
        host,
        poll_s=POLL,
        lanes=(
            *LANES,
            remote,
            remote_lane.RemoteSpec("ssh://carbon-grade@box.example", "4-7", "/srv/gb"),
        ),
        remote_only=True,
    )
    assert work._usable == (2, 3) and work._parallel
    rounds = [_start_round(work) for _ in range(2)]
    for round_ in rounds:
        assert round_[0].wait(5)
    assert sorted(r[2][0][0].index for r in rounds) == [2, 3]
    assert all(r[2][0][0].docker_host for r in rounds)
    third = _start_round(work)
    assert not third[0].wait(0.5)  # the local lanes are never taken
    for round_ in (*rounds, third):
        round_[1].set()
        round_[3].join(5)


def test_a_remote_only_record_with_one_lane_keeps_every_lane():
    from carbon.reconstruction import remote_lane

    one = remote_lane.RemoteSpec("ssh://carbon-grade@box.example", "0-3", "/srv/gb")
    work = _WorkLock(None, lanes=(*LANES, one), remote_only=True)
    assert work._usable == (0, 1, 2)
