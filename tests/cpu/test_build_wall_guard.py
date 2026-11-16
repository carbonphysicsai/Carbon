"""A build beside other rounds (A19 parallel build rounds; Validator-2's F-A19): its wall stop is the candidate's only
when its host was QUIET for it (no other Carbon worker container, no foreign GPU compute), as for grades; a build on a
remote lane is never quiet; a door with one build loop is unchanged. Fakes only: no container runs here.
"""

from __future__ import annotations

import time

from carbon.challenge_validator import grade_sequencer, host_quiet, lean_recipe
from carbon.development_session import research_carrier
from carbon.reconstruction import grade_lanes


def _hosts(monkeypatch, containers, gpu=0):
    monkeypatch.setattr(host_quiet, "worker_containers", lambda: ["c"] * containers)
    monkeypatch.setattr(host_quiet, "foreign_gpu_compute", lambda: gpu)
    monkeypatch.setattr(lean_recipe, "BUILD_PROBE_SECONDS", 0.01)


def test_one_build_loop_has_no_guard():
    with lean_recipe._build_wall_guard(None):
        assert research_carrier.BUILD_WALL_GUARD.get() is None
        assert research_carrier._build_wall_quiet() is True


def test_a_build_alone_on_its_host_is_quiet(monkeypatch):
    _hosts(monkeypatch, 1)
    with lean_recipe._build_wall_guard(grade_sequencer.OwnerClaims()):
        time.sleep(0.1)
        assert research_carrier._build_wall_quiet() is True
    assert research_carrier.BUILD_WALL_GUARD.get() is None


def test_a_build_beside_another_container_or_gpu_work_is_not(monkeypatch):
    for containers, gpu in ((2, 0), (1, 1)):
        _hosts(monkeypatch, containers, gpu)
        with lean_recipe._build_wall_guard(grade_sequencer.OwnerClaims()):
            time.sleep(0.1)
            assert research_carrier._build_wall_quiet() is False


def test_a_build_with_no_sample_yet_is_not_quiet(monkeypatch):
    _hosts(monkeypatch, 1)
    monkeypatch.setattr(lean_recipe, "BUILD_PROBE_SECONDS", 60.0)
    with lean_recipe._build_wall_guard(grade_sequencer.OwnerClaims()):
        assert research_carrier._build_wall_quiet() is False


def test_a_build_on_a_remote_lane_is_never_quiet(monkeypatch):
    _hosts(monkeypatch, 1)
    lane = grade_lanes.Lane(2, "0-3", "/locks", "ssh://u@box.example", "/srv/gb")
    with (
        grade_lanes.bound(lane),
        lean_recipe._build_wall_guard(grade_sequencer.OwnerClaims()),
    ):
        time.sleep(0.1)
        assert research_carrier._build_wall_quiet() is False
