"""OWNER G-LEAD-10 (20 Nov 2026): Carbon's one rebuild of a proven Carbon-side build failure takes its slot only on a
healthy box, one with at most `remote_gpu_build.HEALTHY_MAX_LIVE` builds running, its own included; it waits (never a
failure) while the box is busier. Every other op takes a slot exactly as before."""

from __future__ import annotations

import fcntl
import os
from types import SimpleNamespace

import pytest

from carbon.reconstruction import remote_gpu_build as rgb

pytestmark = pytest.mark.skipif(os.name != "posix", reason="flock")


class _Stop(Exception):
    pass


@pytest.fixture(autouse=True)
def _reset():
    yield
    rgb.set_healthy_only(None)


def test_live_count_is_the_slots_a_live_op_holds(tmp_path):
    lane = SimpleNamespace(slots=3, lane_dir=str(tmp_path))
    held = []
    for slot in range(3):
        (tmp_path / f"slot-{slot}").mkdir()
    for slot in (0, 2):
        fd = os.open(tmp_path / f"slot-{slot}" / "slot.lock", os.O_RDWR | os.O_CREAT)
        fcntl.flock(fd, fcntl.LOCK_EX)
        held.append(fd)
    try:
        # held by another open file description: the probe's own try fails
        assert rgb._live_count(lane) == 2
    finally:
        for fd in held:
            os.close(fd)
    assert rgb._live_count(lane) == 0


def test_the_healthy_only_predicate_never_raises():
    assert rgb._healthy_only("direct-x-build") is False  # none registered
    rgb.set_healthy_only(lambda identity: identity == "direct-x-build")
    assert rgb._healthy_only("direct-x-build") is True
    assert rgb._healthy_only("direct-y-build") is False

    def broken(identity):
        raise OSError("unreadable")

    rgb.set_healthy_only(broken)
    assert rgb._healthy_only("direct-x-build") is False


def _take(monkeypatch, live, identity):
    lane = SimpleNamespace(spec=SimpleNamespace(name="box"), slots=7)
    monkeypatch.setattr(rgb, "_candidates", lambda offer, shadow: [lane])
    monkeypatch.setattr(rgb, "_free_slots", lambda lane: 7 - live)
    monkeypatch.setattr(rgb, "_live_count", lambda lane: live)
    monkeypatch.setattr(rgb, "_live_ops", lambda lane: live > 0)
    taken = []
    monkeypatch.setattr(
        rgb, "_try_lane", lambda offer, lane, held, shadow: taken.append(lane) or "slot"
    )

    def check():
        raise _Stop()

    try:
        result = rgb._take(
            SimpleNamespace(fixed=object()),
            identity,
            held=None,
            check=check,
            pause=lambda seconds: None,
            poll=1,
            deadline=0,
        )
    except _Stop:
        result = "waited"
    return result, taken


def test_a_rebuild_waits_while_its_box_runs_four_builds(monkeypatch):
    rgb.set_healthy_only(lambda identity: identity == "direct-r-build")
    assert _take(monkeypatch, rgb.HEALTHY_MAX_LIVE, "direct-r-build") == ("waited", [])
    result, taken = _take(monkeypatch, rgb.HEALTHY_MAX_LIVE - 1, "direct-r-build")
    assert result == "slot" and len(taken) == 1


def test_any_other_op_takes_a_slot_as_before(monkeypatch):
    rgb.set_healthy_only(lambda identity: identity == "direct-r-build")
    result, taken = _take(monkeypatch, 6, "direct-other-build")
    assert result == "slot" and len(taken) == 1
