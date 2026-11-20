"""A100 build slots 7 -> 4 (Lead pick (A), 20 Nov 2026; V2 12:41:12Z conditions): the per-slot envelope is unchanged,
and the restart that applies it waits until no build holds a slot the new count drops (`slots_held_from`).
"""

from __future__ import annotations

import fcntl
import json
import os
from types import SimpleNamespace

import pytest

from carbon.reconstruction import remote_gpu_build as rgb

pytestmark = pytest.mark.skipif(os.name != "posix", reason="flock")


def test_the_new_count_keeps_each_slots_envelope():
    row = rgb.values_row("electric-motor-magnetics", "1.8")
    assert row["slots"] == 4 and row["memory"] == "shared"
    # the 4 slots are the first 4 of the 7 four-core cpusets a box is set up with: each build sees the same cores
    assert rgb.BOX_SLOT_CPUSETS[: row["slots"]] == ("0-3", "4-7", "8-11", "12-15")
    assert rgb.LEGACY_BOX_SLOT_CPUSETS == rgb.BOX_SLOT_CPUSETS[:4]


def test_held_from_names_every_slot_still_in_use_above_the_new_count(
    tmp_path, monkeypatch
):
    for slot in range(7):
        (tmp_path / f"slot-{slot}").mkdir()
    (tmp_path / "slot-4" / "active-allocation.json").write_text("{}")  # a lost record
    fd = os.open(tmp_path / "slot-5" / "slot.lock", os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)  # a live build
    (tmp_path / "slot-6" / "slot.lock").write_text("")  # free
    (tmp_path / "slot-1" / "active-allocation.json").write_text("{}")  # kept: below
    lane = SimpleNamespace(
        spec=SimpleNamespace(name="carbon-a100"), lane_dir=str(tmp_path)
    )
    monkeypatch.setattr(rgb, "door_pool", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(rgb, "boxes", lambda pool: (lane,))
    try:
        assert rgb.slots_held_from("c", "v", 4) == {"carbon-a100": [4, 5]}
    finally:
        os.close(fd)
    assert rgb.slots_held_from("c", "v", 4) == {"carbon-a100": [4]}


def test_held_from_prints_one_json_line(monkeypatch, capsys):
    monkeypatch.setattr(rgb, "slots_held_from", lambda c, v, first: {"box": [5]})
    assert rgb.main(["held-from", "4", "c", "v"]) == 0
    assert json.loads(capsys.readouterr().out) == {"held": {"box": [5]}, "in_flight": 1}
    assert rgb.main(["held-from", "x", "c", "v"]) == 2
