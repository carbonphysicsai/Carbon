"""Owner D6 (17 Nov 2026): a Ryzen (REMOTE grade lane) round's speed stage runs ON its box. Every op of a remote round,
its timed speed calls included, goes to the lane's daemon (timed by the container's own monotonic clock: the box's), on
the lane's pinned cores there. Owner, 17 Nov 2026: no timing gate on the host or the box (lane pinning is the
protection), so no box lane waits for another.
"""

from __future__ import annotations

import pytest

from carbon.reconstruction import grade_lanes, remote_lane

pytest.importorskip("fcntl")

BOX_A = "ssh://carbon-grade@fsn1.example"


def _lane(lock_dir, index, host=None, cpuset="0-3"):
    return grade_lanes.Lane(
        index, cpuset, lock_dir, host, None if host is None else "/home/carbon"
    )


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
