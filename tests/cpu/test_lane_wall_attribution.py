"""V2's ruling (17 Nov 2026): a LOCAL lane's wall stop is judged on its OWN cores (the registered 2-lane regime).

Live 116 (3326c78b): 3 of 4 grades settled since the flip were FAILED_INFRA wall stops, because the quiet check counted
every Carbon worker container on the host (`count_worker_containers`), and with two lanes the other lane's container is
nearly always there. A local lane's wall stop is now the candidate's when (a) every in-run and stop sample saw no Carbon
container on ITS OWN cpuset but its own (`count_lane_containers`); (b) it still holds the lane it started on; (c) its
program got the full wall (the carrier's own setup budget: only then is the stop the candidate's observation, gate
waits credited since 53437133); (d) no foreign GPU. A neighbour on OTHER cores is accepted (V2: the owner's 2-lane
regime; the per-call speed gate stays EXCLUSIVE). Any failed condition or unreadable sample: ours (FAILED_INFRA).
"""

from __future__ import annotations

import json
import subprocess

import pytest
from test_auto_grade import A, _miner_failure, _row, _wall_setup

from carbon.challenge_validator import auto_grade
from carbon.reconstruction import grade_lanes

LANE = grade_lanes.Lane(0, "0-3", "/var/lib/carbon/locks")


def _wall():
    from carbon.reconstruction.worker.model import WorkerCode

    return _miner_failure(WorkerCode.DEADLINE.value, "WORKER_WALL_LIMIT_REACHED")


def _lane_grader(tmp_path, *, own, gpu=lambda: 0, failure=None):
    grader, cap, ident, ledger = _wall_setup(
        tmp_path,
        failure or _wall(),
        containers=lambda: 3,  # the other lane (and a build) run on OTHER cores: host-wide never quiet
    )
    grader.lane_containers = own
    grader.gpu = gpu
    return grader, cap, ident, ledger


def _logged(tmp_path):
    return json.loads(
        (tmp_path / "auto-grade" / "wall-stops.jsonl").read_text().splitlines()[-1]
    )


def test_a_wall_stop_alone_on_its_own_cores_is_the_candidates(tmp_path):
    asked = []

    def own(cpuset):
        asked.append(cpuset)
        return 1  # its own container only (0 at the stop: it was removed)

    grader, _cap, _ident, _ledger = _lane_grader(
        tmp_path, own=lambda c: 0 if len(asked) > 3 else own(c)
    )
    with grade_lanes.bound(LANE):
        assert grader.run_once() == (A, "CANDIDATE_FAILED")
    assert set(asked) == {"0-3"}
    assert _logged(tmp_path)["counted"] is True


@pytest.mark.parametrize(
    ("own", "why"),
    [
        (lambda cpuset: 2, "(a) another Carbon container on ITS OWN cores"),
        (lambda cpuset: None, "(a) its cores could not be read"),
    ],
)
def test_a_wall_stop_beside_a_container_on_its_own_cores_is_ours(tmp_path, own, why):
    grader, cap, ident, ledger = _lane_grader(tmp_path, own=own)
    with grade_lanes.bound(LANE):
        assert grader.run_once() == (A, "FAILED"), why
    assert _row(ledger) == [("RELEASED", "FAILED_INFRA")]
    assert cap.released_on_infra(**ident)


def test_a_wall_stop_whose_lane_changed_under_it_is_ours(tmp_path):
    """(b) it must still hold the lane it started on."""
    calls = []
    grader, _cap, _ident, ledger = _lane_grader(
        tmp_path, own=lambda c: calls.append(1) or (1 if len(calls) < 4 else 0)
    )
    real = grader.intake.retain_result

    def moved(submission_id, **kwargs):
        grade_lanes.bind(grade_lanes.Lane(1, "4-7", LANE.lock_dir))
        return real(submission_id, **kwargs)

    grader.intake.retain_result = moved
    with grade_lanes.bound(LANE):
        assert grader.run_once() == (A, "FAILED")
    assert _row(ledger) == [("RELEASED", "FAILED_INFRA")]


def test_a_stop_that_was_not_the_programs_full_wall_is_ours(tmp_path):
    """(c) the carrier names a stop the candidate's wall only when the program started within its setup budget and ran
    its whole allowance; any other stop (a late start, a host fault) is not that observation: ours.
    """
    from carbon.reconstruction.worker.model import WorkerCode

    late = _miner_failure(WorkerCode.DEADLINE.value, "RUNTIME_DEADLINE_HOST")
    grader, _cap, _ident, ledger = _lane_grader(tmp_path, own=lambda c: 0, failure=late)
    with grade_lanes.bound(LANE):
        assert grader.run_once() == (A, "FAILED")
    assert _row(ledger) == [("RELEASED", "FAILED_INFRA")]


def test_a_wall_stop_beside_foreign_gpu_work_is_ours(tmp_path):
    """(d) no foreign GPU compute, as before."""
    grader, _cap, _ident, ledger = _lane_grader(
        tmp_path, own=lambda c: 0, gpu=lambda: 1
    )
    with grade_lanes.bound(LANE):
        assert grader.run_once() == (A, "FAILED")
    assert _row(ledger) == [("RELEASED", "FAILED_INFRA")]


def test_a_one_lane_door_still_reads_the_whole_host(tmp_path):
    grader, _cap, _ident, _ledger = _lane_grader(
        tmp_path, own=lambda c: pytest.fail("a one-lane door has no lane cores")
    )
    assert grader.run_once() == (
        A,
        "FAILED",
    )  # 3 containers host-wide: not quiet, as before


class _Docker:
    def __init__(self, names, cpusets, inspect_rc=0):
        self.names, self.cpusets, self.inspect_rc = names, cpusets, inspect_rc

    def __call__(self, argv, **kwargs):
        if argv[1] == "ps":
            out = "\n".join(self.names)
            return subprocess.CompletedProcess(argv, 0, out.encode(), b"")
        out = "\n".join(self.cpusets)
        return subprocess.CompletedProcess(argv, self.inspect_rc, out.encode(), b"")


def test_the_lane_count_reads_each_containers_own_cores(monkeypatch):
    names = ["carbon-d4-a", "carbon-d4-b", "carbon-d4-s-c", "carbon-d4-d"]
    monkeypatch.setattr(subprocess, "run", _Docker(names, ["0-3", "4-7", "", "2-5"]))
    # its own (0-3), an unpinned one (may run anywhere), and one sharing cores 2-3; never the other lane's 4-7
    assert auto_grade.count_lane_containers("0-3") == 3
    monkeypatch.setattr(subprocess, "run", _Docker([], []))
    assert auto_grade.count_lane_containers("0-3") == 0
    monkeypatch.setattr(subprocess, "run", _Docker(names[:1], ["0-3"], inspect_rc=1))
    assert auto_grade.count_lane_containers("0-3") is None  # unreadable: never quiet


def test_a_container_still_on_its_cores_at_the_stop_is_ours_and_the_log_names_the_lane(
    tmp_path,
):
    """In-run samples fine, but a container still on its own cores at the stop (its own was removed before the stop
    sample): ours. The wall-stop log names the rule that read the containers and the lane.
    """
    calls = []
    grader, _cap, _ident, ledger = _lane_grader(
        tmp_path, own=lambda c: calls.append(1) or 1
    )
    with grade_lanes.bound(LANE):
        assert grader.run_once() == (A, "FAILED")
    assert _row(ledger) == [("RELEASED", "FAILED_INFRA")]
    logged = _logged(tmp_path)
    assert logged["stop_worker_containers"] == 1 and logged["counted"] is False
    assert (logged["scope"], logged["lane"], logged["cpuset"]) == ("lane", 0, "0-3")


def test_the_host_rule_is_named_on_a_one_lane_door(tmp_path):
    grader, _cap, _ident, _ledger = _lane_grader(tmp_path, own=lambda c: 0)
    grader.run_once()
    logged = _logged(tmp_path)
    assert logged["scope"] == "host" and "lane" not in logged
