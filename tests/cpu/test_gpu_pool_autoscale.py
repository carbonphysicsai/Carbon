"""The on-demand A100 autoscaler (`scripts/dev/gpu_pool_autoscale.py`): rent when builds back up (policy v2: 3 waiting
through 5 min, or any through 10 min), drain then release a box idle 30 min, never past the owner's line (3 boxes,
USD 6/h) or the daily cap, every rent and release logged with cost, failures paged.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fcntl")

SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "dev" / "gpu_pool_autoscale.py"
)
spec = importlib.util.spec_from_file_location("gpu_pool_autoscale", SCRIPT)
scale = importlib.util.module_from_spec(spec)
sys.modules["gpu_pool_autoscale"] = scale
spec.loader.exec_module(scale)

T0 = 1_800_000_000.0
PRICE = 1.99


def _config(tmp_path, **overrides):
    values = {
        "lambda_key_file": str(tmp_path / "key"),
        "instance_type": "gpu_1x_a100_sxm4",
        "ssh_key_name": "Carbon Fresh Miner",
        "admin_key": "/k/admin",
        "device_kind": "NVIDIA A100-SXM4-40GB",
        "door_ssh": "carbon@door.example",
        "door_ssh_options": ("-i", "/k/door"),
        "door_ip": "198.51.100.2",
        "door_queue_url": "http://127.0.0.1:1/carbon/v1/queue/electric-motor-magnetics",
        "door_host_root": "/var/lib/carbon/accelerators",
        "door_phase_args": ("/door/carbon/scripts/dev/gpu_box_up.py",),
        "lane_pubkey": "/k/lane.pub",
        "box_up_script": "/vm/carbon/scripts/dev/gpu_box_up.py",
        "state_dir": str(tmp_path / "state"),
        "max_usd_per_day": 48.0,
        "page_outbox": "",
    }
    values.update(overrides)
    (tmp_path / "state").mkdir(exist_ok=True)
    return scale.Config(**values)


class _Client:
    def __init__(self, instances=(), capacity="us-east-1"):
        self.list = [dict(i) for i in instances]
        self.capacity = capacity
        self.launched, self.terminated = [], []

    def instances(self):
        return [dict(i) for i in self.list]

    def offer(self, instance_type, regions=()):
        return PRICE, self.capacity

    def launch(self, *, region, instance_type, ssh_key_name, name):
        assert (
            ssh_key_name == "Carbon Fresh Miner" and instance_type == "gpu_1x_a100_sxm4"
        )
        instance_id = f"i-{len(self.launched)}"
        self.launched.append(name)
        self.list.append(
            {
                "id": instance_id,
                "name": name,
                "status": "booting",
                "ip": None,
                "price_usd_h": PRICE,
            }
        )
        return instance_id

    def terminate(self, instance_id):
        self.terminated.append(instance_id)
        for item in self.list:
            if item["id"] == instance_id:
                item["status"] = "terminating"


def _ticks(
    config,
    client,
    waiting,
    *,
    boxes=None,
    start=T0,
    every=300,
    count=4,
    spawned=None,
    grading=0,
):
    state = None
    for k in range(count):
        state = scale.tick(
            config,
            client=client,
            door=lambda c: (waiting, {} if boxes is None else boxes, grading),
            now=start + k * every,
            spawn=lambda c, name: (spawned if spawned is not None else []).append(name),
        )
    return state


def _log(config):
    return [
        json.loads(line)
        for line in (Path(config.state_dir) / "log.jsonl").read_text().splitlines()
    ]


def _samples(*waiting, every=300, grade=0):
    return [
        {"t": T0 + k * every, "waiting": w, "grade": grade}
        for k, w in enumerate(waiting)
    ]


def test_rent_when_three_wait_five_minutes_or_any_waits_ten():
    end = lambda samples: samples[-1]["t"]
    s = _samples(3, 3)
    assert scale.want_box(s, end(s)) == "many"
    s = _samples(2, 3)
    assert scale.want_box(s, end(s)) is None  # only one sample at >= 3
    s = _samples(1, 2, 1)
    assert scale.want_box(s, end(s)) == "any"
    s = _samples(1, 0, 1)
    assert scale.want_box(s, end(s)) is None
    s = _samples(5, None, 5)
    assert scale.want_box(s, end(s)) is None  # an unreadable queue never counts
    # a gap in the timer is not five minutes of waiting
    s = [{"t": T0, "waiting": 9, "grade": 0}]
    assert scale.want_box(s, T0 + 300) is None
    # builds wait, but the grade queue is the limit (owner, 19 Nov 2026)
    s = _samples(31, 31, grade=scale.GRADE_SHORT + 1)
    assert scale.want_box(s, end(s)) is None and scale.grade_bound(s, end(s))
    s = _samples(31, 31, grade=scale.GRADE_SHORT)
    assert scale.want_box(s, end(s)) == "many" and not scale.grade_bound(s, end(s))


def test_three_builds_waiting_five_minutes_rents_one_box(tmp_path):
    config = _config(tmp_path)
    client, spawned = _Client(), []
    _ticks(config, client, 3, count=1, spawned=spawned)
    assert client.launched == []
    _ticks(config, client, 3, start=T0 + 300, count=1, spawned=spawned)
    assert len(client.launched) == 1 and spawned == client.launched
    rent = [e for e in _log(config) if e["action"] == "rent"]
    assert (
        rent[0]["price_usd_h"] == PRICE
        and rent[0]["rule"] == "many"
        and rent[0]["waiting"] == 3
    )
    # while it is brought up, no second rent
    _ticks(config, client, 80, start=T0 + 1200, count=4, spawned=spawned)
    assert len(client.launched) == 1


def test_a_backlog_that_dips_or_is_unreadable_rents_nothing(tmp_path):
    config = _config(tmp_path)
    client = _Client()
    for k, waiting in enumerate((40, 0, 40, 0, 40)):
        _ticks(config, client, waiting, start=T0 + 300 * k, count=1)
    assert client.launched == []
    _ticks(config, client, None, start=T0 + 1500, count=4)
    assert client.launched == []


def test_never_past_the_owners_line(tmp_path):
    config = _config(tmp_path)
    three = [
        {
            "id": f"x{k}",
            "name": f"other-{k}",
            "status": "active",
            "ip": "x",
            "price_usd_h": PRICE,
        }
        for k in range(3)
    ]
    client = _Client(three)
    _ticks(config, client, 200, count=5)
    assert client.launched == [] and any(e["action"] == "at_cap" for e in _log(config))
    # two boxes at USD 2.50/h: a third at 1.99 would pass USD 6/h
    dear = [
        {"id": f"y{k}", "name": "", "status": "active", "ip": "x", "price_usd_h": 2.5}
        for k in range(2)
    ]
    assert not scale.may_rent(dear, PRICE, config)
    assert scale.may_rent(dear[:1], PRICE, config)
    with pytest.raises(SystemExit):
        path = tmp_path / "c.json"
        raw = {
            k: list(v) if type(v) is tuple else v for k, v in config.__dict__.items()
        }
        path.write_text(json.dumps({**raw, "max_boxes": 4}))
        scale.load_config(path)


def _active_box(config, client, name="carbon-pool-a"):
    client.list.append(
        {
            "id": "i-a",
            "name": name,
            "status": "active",
            "ip": "203.0.113.7",
            "price_usd_h": PRICE,
        }
    )
    state = scale.load_state(config)
    state["boxes"][name] = {
        "id": "i-a",
        "launched": T0 - 7200,
        "price_usd_h": PRICE,
        "phase": "ACTIVE",
    }
    scale.save_state(config, state)
    return name


def test_a_released_box_takes_its_door_ssh_files_with_it(tmp_path, monkeypatch):
    """``gpu_box_up door`` writes each box's ssh block for the door's watchdogs; the release removes it (a recycled
    address must not keep an old block). With ``door_ssh_boxes_dir`` empty nothing is removed.
    """
    config = _config(tmp_path, door_ssh_boxes_dir=".ssh/config.d/carbon-boxes")
    client = _Client()
    name = _active_box(config, client)
    calls = []
    monkeypatch.setattr(scale, "_door", _recording_door(calls))
    idle = {
        name: {"file": True, "busy": False, "last": T0 - 3700, "admitted": T0 - 7200}
    }
    _ticks(config, client, 0, boxes=idle, count=1)
    assert ["rm"] not in [
        a[:1] for a, _ in calls
    ]  # drained only: its builds and watchdogs still run
    free = {name: dict(idle[name], file=False)}
    _ticks(config, client, 0, boxes=free, start=T0 + 300, count=1)
    assert client.terminated == ["i-a"]
    base = f".ssh/config.d/carbon-boxes/{name}"
    assert (["rm", "-f", f"{base}.conf", f"{base}.known_hosts"], None) in calls
    assert any(e["action"] == "box_ssh_removed" and e["ok"] for e in _log(config))


def test_the_door_ssh_boxes_dir_is_a_plain_path_under_the_door_home(tmp_path):
    config = _config(tmp_path)
    raw = {k: list(v) if type(v) is tuple else v for k, v in config.__dict__.items()}
    path = tmp_path / "c.json"
    for bad in ("/home/carbon/.ssh", "../x", ".ssh/../../x", ".ssh/a b"):
        path.write_text(json.dumps({**raw, "door_ssh_boxes_dir": bad}))
        with pytest.raises(SystemExit, match="door_ssh_boxes_dir"):
            scale.load_config(path)
    path.write_text(
        json.dumps({**raw, "door_ssh_boxes_dir": ".ssh/config.d/carbon-boxes"})
    )
    assert scale.load_config(path).door_ssh_boxes_dir == ".ssh/config.d/carbon-boxes"


def test_an_idle_box_is_drained_then_released_with_its_cost(tmp_path, monkeypatch):
    config = _config(tmp_path)
    client = _Client()
    name = _active_box(config, client)
    moved = []
    monkeypatch.setattr(
        scale,
        "_door",
        lambda c, argv, **k: moved.append(argv) or type("R", (), {"returncode": 0})(),
    )
    busy = {name: {"file": True, "busy": True, "last": T0, "admitted": T0 - 7200}}
    _ticks(config, client, 0, boxes=busy, count=1)
    assert moved == [] and client.terminated == []
    idle = {
        name: {"file": True, "busy": False, "last": T0 - 3700, "admitted": T0 - 7200}
    }
    _ticks(config, client, 0, boxes=idle, count=1)
    assert (
        moved and moved[0][0] == "mv" and moved[0][-1].endswith(f"{name}.json.drained")
    )
    assert client.terminated == []  # drained first, released on a later tick
    drained = {name: {"file": False, "busy": True, "last": T0, "admitted": T0 - 7200}}
    _ticks(config, client, 0, boxes=drained, start=T0 + 300, count=1)
    assert client.terminated == []  # a running build finishes first
    _ticks(
        config,
        client,
        0,
        boxes={name: dict(drained[name], busy=False)},
        start=T0 + 600,
        count=1,
    )
    assert client.terminated == ["i-a"]
    release = next(e for e in _log(config) if e["action"] == "release")
    assert release["why"] == "idle" and release["hours"] == pytest.approx(
        7800 / 3600, abs=1e-3
    )
    assert release["cost_usd"] == round(release["hours"] * PRICE, 2)


def test_a_box_it_did_not_launch_is_never_touched(tmp_path, monkeypatch):
    config = _config(tmp_path)
    client = _Client(
        [
            {
                "id": "i-lead",
                "name": "carbon-a100",
                "status": "active",
                "ip": "x",
                "price_usd_h": PRICE,
            }
        ]
    )
    monkeypatch.setattr(
        scale, "_door", lambda *a, **k: pytest.fail("touched a box it did not launch")
    )
    idle = {"carbon-a100": {"file": True, "busy": False, "last": 0.0, "admitted": 0.0}}
    _ticks(config, client, 0, boxes=idle, count=2)
    assert client.terminated == []


def test_a_failed_bring_up_releases_the_box_and_backs_off(tmp_path):
    config = _config(tmp_path)
    client = _Client()
    _ticks(config, client, 50, count=4)
    (name,) = client.launched
    state = scale.load_state(config)
    state["boxes"][name]["result"] = "FAILED"
    state["boxes"][name]["reason"] = "admin:driver"
    scale.save_state(config, state)
    _ticks(config, client, 50, start=T0 + 1200, count=1)
    assert client.terminated == ["i-0"]
    actions = [e["action"] for e in _log(config)]
    assert "bring_up_failed" in actions and "release" in actions
    # backed off: no new rent for FAIL_BACKOFF_S
    _ticks(config, client, 50, start=T0 + 1500, count=4)
    assert len(client.launched) == 1


def test_a_box_whose_file_appears_is_active(tmp_path):
    config = _config(tmp_path)
    client = _Client()
    _ticks(config, client, 50, count=4)
    (name,) = client.launched
    joined = {name: {"file": True, "busy": True, "last": T0, "admitted": T0}}
    state = _ticks(config, client, 50, boxes=joined, start=T0 + 1200, count=1)
    assert state["boxes"][name]["phase"] == "ACTIVE"


def test_the_door_probe_reads_slots_without_writing(tmp_path):
    """The probe runs on the door as the door user: box files, busy slots, newest slot activity; it changes nothing."""
    import fcntl
    import os
    import subprocess

    root = tmp_path / "acc"
    boxes = root / "remote-gpu-build-boxes.d"
    boxes.mkdir(parents=True)
    (boxes / "a100-1.json").write_text(json.dumps({"admitted_unix": 5}))
    (boxes / "a100-1.class-check.json").write_text("{}")
    slot = root / "remote-gpu-build" / "box-a100-1" / "slot-0"
    slot.mkdir(parents=True)
    (slot / "slot.lock").write_text("")
    (root / "remote-gpu-build" / "box-gone" / "slot-0").mkdir(parents=True)
    before = sorted(str(p) for p in root.rglob("*"))
    run = lambda: json.loads(
        subprocess.run(
            [sys.executable, "-I", "-", str(root), str(boxes)],
            input=scale.DOOR_PROBE.encode(),
            capture_output=True,
            check=True,
        ).stdout
    )
    out = run()
    assert set(out["boxes"]) == {"a100-1", "gone"}
    assert out["boxes"]["a100-1"]["file"] and not out["boxes"]["a100-1"]["busy"]
    assert (
        out["boxes"]["a100-1"]["admitted"] == 5
        and out["boxes"]["gone"]["file"] is False
    )
    fd = os.open(slot / "slot.lock", os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        assert run()["boxes"]["a100-1"]["busy"] is True
    finally:
        os.close(fd)
    assert sorted(str(p) for p in root.rglob("*")) == before


A100 = {
    "id": "i-a100",
    "name": "carbon-a100",
    "status": "active",
    "ip": "203.0.113.21",
    "type": "gpu_1x_a100_sxm4",
    "price_usd_h": PRICE,
}


def test_an_adopted_box_is_drained_and_released_after_an_idle_hour(
    tmp_path, monkeypatch
):
    """Owner 17 Nov 2026 ("I don't think we need an always on one"): carbon-a100, brought up by hand, is adopted and
    then released like a box this tool launched; hours and cost count from the adoption.
    """
    config = _config(tmp_path)
    client = _Client([A100])
    busy = {"carbon-a100": {"file": True, "busy": True, "last": T0, "admitted": 0.0}}
    scale.adopt(
        config,
        "carbon-a100",
        A100["ip"],
        client=client,
        door=lambda c: (0, busy, 0),
        now=T0,
    )
    record = scale.load_state(config)["boxes"]["carbon-a100"]
    assert (
        record["phase"] == "ACTIVE" and record["adopted"] and record["id"] == "i-a100"
    )
    moved = []
    monkeypatch.setattr(
        scale,
        "_door",
        lambda c, argv, **k: moved.append(argv) or type("R", (), {"returncode": 0})(),
    )
    _ticks(config, client, 0, boxes=busy, start=T0 + 300, count=1)
    assert moved == [] and client.terminated == []
    idle = {"carbon-a100": {"file": True, "busy": False, "last": T0, "admitted": 0.0}}
    _ticks(config, client, 0, boxes=idle, start=T0 + 3900, count=1)
    assert moved[0][-1].endswith("carbon-a100.json.drained")
    gone = {"carbon-a100": {"file": False, "busy": False, "last": T0, "admitted": 0.0}}
    _ticks(config, client, 0, boxes=gone, start=T0 + 4200, count=1)
    assert client.terminated == ["i-a100"]
    release = next(e for e in _log(config) if e["action"] == "release")
    assert release["hours"] == pytest.approx(4200 / 3600, abs=1e-3)


@pytest.mark.parametrize(
    "instances, boxes, ip",
    [
        ([A100], {}, A100["ip"]),  # no box file on the door
        ([A100], None, A100["ip"]),  # door unreadable
        ([], {"carbon-a100": {"file": True}}, A100["ip"]),  # no instance there
        ([dict(A100, status="booting")], {"carbon-a100": {"file": True}}, A100["ip"]),
        ([A100], {"carbon-a100": {"file": True}}, "203.0.113.99"),  # wrong address
    ],
)
def test_adopt_refuses_without_one_active_instance_and_its_box_file(
    tmp_path, instances, boxes, ip
):
    config = _config(tmp_path)
    with pytest.raises(SystemExit):
        scale.adopt(
            config,
            "carbon-a100",
            ip,
            client=_Client(instances),
            door=lambda c: (0, boxes, 0),
            now=T0,
        )
    assert scale.load_state(config)["boxes"] == {}


def test_a_dry_tick_changes_nothing(tmp_path, monkeypatch, capsys):
    """``tick --dry-run``: the would-be drain and rent are printed; no door write, no Lambda call that changes
    anything, no state or log file."""
    config = _config(tmp_path)
    client = _Client([A100])
    scale.adopt(
        config,
        "carbon-a100",
        A100["ip"],
        client=client,
        door=lambda c: (0, {"carbon-a100": {"file": True}}, 0),
        now=T0,
    )
    before = (Path(config.state_dir) / "state.json").read_text()
    log_before = (Path(config.state_dir) / "log.jsonl").read_text()
    monkeypatch.setattr(scale, "_door", lambda *a, **k: pytest.fail("door write"))
    monkeypatch.setattr(scale, "DRY", [True])
    idle = {"carbon-a100": {"file": True, "busy": False, "last": T0, "admitted": 0.0}}
    capsys.readouterr()
    _ticks(config, client, 0, boxes=idle, start=T0 + 3900, count=4)
    printed = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert {"would_drain"} <= {p.get("action") for p in printed}
    assert client.launched == [] and client.terminated == []
    assert (Path(config.state_dir) / "state.json").read_text() == before
    assert (Path(config.state_dir) / "log.jsonl").read_text() == log_before
    assert printed[-1]["dry"] and printed[-1]["waiting_to_build"] == 0


def test_no_rent_while_a_box_up_sits_idle_or_just_after_an_idle_release(
    tmp_path, monkeypatch
):
    """Owner C8 (no overpay): a long queue with a box up and all its slots free means the door, not the box count,
    holds the queue (the rs116c lane starvation, 17 Nov 2026 22:38Z): no rent. After that box is released idle, a new
    backlog rents again on the policy's own 5 minutes (policy v2: no idle-release backoff).
    """
    config = _config(tmp_path)
    client = _Client([A100])
    idle = {"carbon-a100": {"file": True, "busy": False, "last": T0, "admitted": 0.0}}
    scale.adopt(
        config,
        "carbon-a100",
        A100["ip"],
        client=client,
        door=lambda c: (80, idle, 0),
        now=T0,
    )
    monkeypatch.setattr(
        scale, "_door", lambda c, argv, **k: type("R", (), {"returncode": 0})()
    )
    _ticks(config, client, 80, boxes=idle, start=T0 + 300, count=14)
    # 65 min of backlog with the one box idle: no rent, and (Lead 18 Nov 2026) no drain while builds wait
    assert client.launched == [] and client.terminated == []
    assert scale.load_state(config)["boxes"]["carbon-a100"]["phase"] == "ACTIVE"
    held = T0 + 300 + 13 * 300
    _ticks(config, client, 0, boxes=idle, start=held + 3700, count=1)  # drained
    gone = {"carbon-a100": dict(idle["carbon-a100"], file=False)}
    released = held + 4000
    _ticks(config, client, 0, boxes=gone, start=released, count=1)
    assert client.terminated == ["i-a100"]
    _ticks(config, client, 80, boxes=gone, start=released + 300, count=1)
    assert client.launched == []
    _ticks(config, client, 80, boxes=gone, start=released + 600, count=1)
    assert len(client.launched) == 1
    # and a busy box up does not block a rent
    (tmp_path / "b").mkdir()
    config2 = _config(tmp_path / "b")
    busy = {"carbon-a100": {"file": True, "busy": True, "last": T0, "admitted": 0.0}}
    client2 = _Client([A100])
    _ticks(config2, client2, 80, boxes=busy, count=4)
    assert len(client2.launched) == 1


def test_an_unreadable_queue_drains_and_releases_nothing(tmp_path, monkeypatch):
    """V2 (17 Nov 2026): a tick that cannot read the door's queue (a switch window, a moved port) does nothing to the
    boxes: no rent, no drain, no release, even of a box idle for hours."""
    config = _config(tmp_path)
    client = _Client([A100])
    idle = {"carbon-a100": {"file": True, "busy": False, "last": 0.0, "admitted": 0.0}}
    scale.adopt(
        config,
        "carbon-a100",
        A100["ip"],
        client=client,
        door=lambda c: (0, idle, 0),
        now=T0,
    )
    monkeypatch.setattr(scale, "_door", lambda *a, **k: pytest.fail("door write"))
    _ticks(config, client, None, boxes=idle, start=T0 + 7200, count=4)
    gone = {"carbon-a100": dict(idle["carbon-a100"], file=False)}
    assert scale.load_state(config)["boxes"]["carbon-a100"]["phase"] == "ACTIVE"
    _ticks(config, client, None, boxes=gone, start=T0 + 9000, count=2)
    assert client.launched == [] and client.terminated == []


def _adopted(config, client, entry):
    scale.adopt(
        config,
        "carbon-a100",
        A100["ip"],
        client=client,
        door=lambda c: (0, {"carbon-a100": entry}, 0),
        now=T0,
    )


def test_a_box_file_put_back_with_an_old_admission_is_not_idle_while_builds_wait(
    tmp_path, monkeypatch
):
    """18 Nov 2026: a rollback restored carbon-a100's box file with its admission of an hour before and its slots idle
    since then; the next tick drained it (62.6 min "idle") and released it with builds queued. The idle clock runs only
    while the queue is readable and empty: a tick with the door down or builds waiting stamps the box held.
    """
    config = _config(tmp_path)
    client = _Client([A100])
    old = {"file": True, "busy": False, "last": T0, "admitted": T0}
    _adopted(config, client, old)
    moved = []
    monkeypatch.setattr(
        scale,
        "_door",
        lambda c, argv, **k: moved.append(argv) or type("R", (), {"returncode": 0})(),
    )
    # the door down (queue unreadable, file gone) for 50 min, then back with the OLD file and 9 builds waiting
    _ticks(config, client, None, boxes={}, start=T0 + 600, count=10)
    _ticks(config, client, 9, boxes={"carbon-a100": old}, start=T0 + 3900, count=3)
    assert moved == [] and client.terminated == []
    # the queue empties: the box is idle from the last tick that saw builds waiting, not from its admission
    last_held = T0 + 3900 + 2 * 300
    _ticks(
        config, client, 0, boxes={"carbon-a100": old}, start=last_held + 300, count=1
    )
    assert moved == []
    _ticks(
        config, client, 0, boxes={"carbon-a100": old}, start=last_held + 3700, count=1
    )
    assert moved[0][-1].endswith("carbon-a100.json.drained")


@pytest.mark.parametrize("other_box", [False, True])
def test_the_last_box_is_never_released_while_builds_wait(
    tmp_path, monkeypatch, other_box
):
    """Lead 18 Nov 2026: a draining box that is the door's last gets its file back when builds wait; with another box
    up it is released as before."""
    config = _config(tmp_path)
    client = _Client([A100])
    idle = {"file": True, "busy": False, "last": T0, "admitted": T0}
    _adopted(config, client, idle)
    moved = []
    monkeypatch.setattr(
        scale,
        "_door",
        lambda c, argv, **k: moved.append(argv) or type("R", (), {"returncode": 0})(),
    )
    _ticks(config, client, 0, boxes={"carbon-a100": idle}, start=T0 + 3900, count=1)
    assert scale.load_state(config)["boxes"]["carbon-a100"]["phase"] == "DRAINING"
    drained = {"carbon-a100": dict(idle, file=False)}
    if other_box:
        drained["a100-other"] = {"file": True, "busy": True, "last": T0, "admitted": T0}
    _ticks(config, client, 5, boxes=drained, start=T0 + 4200, count=1)
    record = scale.load_state(config)["boxes"].get("carbon-a100")
    if other_box:
        assert client.terminated == ["i-a100"] and record is None
    else:
        assert client.terminated == [] and record["phase"] == "ACTIVE"
        assert moved[-1][-2].endswith("carbon-a100.json.drained")
        assert moved[-1][-1].endswith("carbon-a100.json")
        assert any(e["action"] == "undrain" for e in _log(config))


def _recording_door(calls):
    def door(c, argv, **k):
        calls.append((argv, k.get("stdin")))
        return type("R", (), {"returncode": 0})()

    return door


def test_an_idle_box_is_released_after_30_minutes_not_before(tmp_path, monkeypatch):
    """Policy v2: the burst gaps on live 116 (p50 16.6 min) stay bridged; a box free for 30 min is drained."""
    config = _config(tmp_path)
    assert config.idle_release_s == 1800
    client = _Client([A100])
    calls = []
    _adopted(config, client, {"file": True, "busy": True, "last": T0, "admitted": T0})
    monkeypatch.setattr(scale, "_door", _recording_door(calls))
    idle = {"carbon-a100": {"file": True, "busy": False, "last": T0, "admitted": T0}}
    _ticks(config, client, 0, boxes=idle, start=T0 + 1740, count=1)
    assert calls == []
    _ticks(config, client, 0, boxes=idle, start=T0 + 1860, count=1)
    assert calls[0][0][-1].endswith("carbon-a100.json.drained")


def test_a_draining_door_is_read_as_unreadable(monkeypatch):
    """The idle clock counts only while the door is up AND undrained: a ``door_state`` of draining reads as no queue."""
    config = scale.Config(**_CFG_MIN)
    out = {"probe": json.dumps({"boxes": {}}).encode()}

    def door(c, argv, **k):
        stdout = out["probe"] if argv[0] == "python3" else out["queue"]
        return type("R", (), {"returncode": 0, "stdout": stdout})()

    monkeypatch.setattr(scale, "_door", door)
    out["queue"] = json.dumps(
        {"waiting_to_build": 4, "waiting_to_grade": 6, "door_state": "grading"}
    ).encode()
    assert scale.read_door(config) == (4, {}, 6)
    out["queue"] = json.dumps(
        {"waiting_to_build": 4, "waiting_to_grade": 6, "door_state": "draining"}
    ).encode()
    assert scale.read_door(config) == (None, {}, 6)
    # no grade count on the board: unreadable, so no rent (`_held`)
    out["queue"] = json.dumps({"waiting_to_build": 4, "door_state": "grading"}).encode()
    assert scale.read_door(config) == (4, {}, None)


_CFG_MIN = {
    "lambda_key_file": "/k/lambda",
    "instance_type": "gpu_1x_a100_sxm4",
    "ssh_key_name": "Carbon Fresh Miner",
    "admin_key": "/k/admin",
    "device_kind": "NVIDIA A100-SXM4-40GB",
    "door_ssh": "carbon@door.example",
    "door_ssh_options": (),
    "door_ip": "198.51.100.2",
    "door_queue_url": "http://127.0.0.1:1/q",
    "door_host_root": "/var/lib/carbon/accelerators",
    "door_phase_args": ("/door/gpu_box_up.py",),
    "lane_pubkey": "/k/lane.pub",
    "box_up_script": "/vm/gpu_box_up.py",
    "state_dir": "/nonexistent",
    "max_usd_per_day": 48.0,
}


def test_the_daily_cap_drains_releases_pages_once_and_rents_nothing(
    tmp_path, monkeypatch
):
    """Today's spend at ``max_usd_per_day``: every box of this tool drains (even the last one, builds waiting), is
    released once its builds finish, nothing is rented until 00:00Z, and one page goes out.
    """
    day0 = T0 - T0 % 86400
    config = _config(
        tmp_path, max_usd_per_day=10.0, page_outbox="ops-watch/outbox.jsonl"
    )
    client = _Client([A100])
    busy = {"file": True, "busy": True, "last": day0 + 3600, "admitted": day0}
    scale.adopt(
        config,
        "carbon-a100",
        A100["ip"],
        client=client,
        door=lambda c: (0, {"carbon-a100": busy}, 0),
        now=day0 + 3600,
    )
    calls = []
    monkeypatch.setattr(scale, "_door", _recording_door(calls))
    # 4 h at USD 1.99 = 7.96: under the cap, nothing happens
    _ticks(
        config,
        client,
        9,
        boxes={"carbon-a100": busy},
        start=day0 + 4 * 3600 + 3600,
        count=1,
    )
    assert calls == []
    # 5 h = 9.95; + 1 tick = over 10
    late = day0 + 6 * 3600 + 300
    _ticks(config, client, 9, boxes={"carbon-a100": busy}, start=late, count=3)
    moves = [a for a, _ in calls if a[0] == "mv"]
    pages = [json.loads(s) for a, s in calls if a[0] == "sh"]
    assert len(moves) == 1 and moves[0][-1].endswith("carbon-a100.json.drained")
    assert len(pages) == 1 and pages[0]["sev"] == "ALERT"
    assert pages[0]["key"] == "autoscale_day_cap:" + scale._day(late)
    assert "9 builds waiting" in pages[0]["text"]
    record = scale.load_state(config)["boxes"]["carbon-a100"]
    assert (
        record["phase"] == "DRAINING"
    )  # never undrained at the cap, builds waiting or not
    gone = {"carbon-a100": dict(busy, file=False, busy=False)}
    _ticks(config, client, 9, boxes=gone, start=late + 900, count=4)
    assert client.terminated == ["i-a100"] and client.launched == []
    assert any(e["action"] == "at_day_cap" for e in _log(config))
    release = next(e for e in _log(config) if e["action"] == "release")
    assert release["why"] == "day_cap"
    assert scale.load_state(config)["spent"][scale._day(late)] >= 10.0
    # the next UTC day starts from zero: the backlog rents again
    _ticks(config, client, 9, boxes={}, start=day0 + 86400 + 60, count=2)
    assert len(client.launched) == 1


def _two_boxes(tmp_path, monkeypatch, day_cap):
    """carbon-a100 adopted at 00:00Z and a 2nd box of this tool ACTIVE from 06:00Z, both busy, builds waiting."""
    day0 = T0 - T0 % 86400
    config = _config(tmp_path, max_usd_per_day=day_cap, max_boxes=2)
    second = dict(A100, id="i-b", name="carbon-pool-b", ip="203.0.113.22")
    client = _Client([A100, second])
    busy = {"file": True, "busy": True, "last": day0, "admitted": day0}
    scale.adopt(
        config,
        "carbon-a100",
        A100["ip"],
        client=client,
        door=lambda c: (0, {"carbon-a100": busy}, 0),
        now=day0,
    )
    state = scale.load_state(config)
    state["boxes"]["carbon-pool-b"] = {
        "id": "i-b",
        "launched": day0 + 6 * 3600,
        "price_usd_h": PRICE,
        "phase": "ACTIVE",
    }
    scale.save_state(config, state)
    calls = []
    monkeypatch.setattr(scale, "_door", _recording_door(calls))
    both = {"carbon-a100": busy, "carbon-pool-b": dict(busy)}
    return config, client, calls, both, day0


def test_the_daily_cap_drains_the_newest_box_and_keeps_the_oldest_all_day(
    tmp_path, monkeypatch
):
    """Owner INFRA-3 (20 Nov 2026, USD 65/day, up to 2 A100s): the 2nd box runs while today's spend plus carbon-a100's
    rest of the day leaves it DAY_MARGIN_H; then only it drains (no page). carbon-a100 builds to 00:00Z inside the cap,
    and the backlog rents no new box that day.
    """
    config, client, calls, both, day0 = _two_boxes(tmp_path, monkeypatch, 65.0)
    # at 14:00Z: spent 14 h + 8 h = 43.78, carbon-a100 to 00:00Z 19.90, + 0.5 h of the 2nd = 64.67 <= 65: kept
    _ticks(config, client, 30, boxes=both, start=day0 + 14 * 3600, count=1)
    assert calls == []
    # at 14:30Z: spent 14.5 h + 8.5 h = 45.77, carbon-a100 to 00:00Z 18.91, + 0.5 h of the 2nd = 65.67 > 65: drains
    late = day0 + 14 * 3600 + 1800
    state = scale.load_state(config)
    assert scale.over_day_budget(state, late, config) == {"carbon-pool-b"}
    _ticks(config, client, 30, boxes=both, start=late, count=1)
    moves = [a for a, _ in calls if a[0] == "mv"]
    assert len(moves) == 1 and moves[0][-1].endswith("carbon-pool-b.json.drained")
    assert not [a for a, _ in calls if a[0] == "sh"]  # no page: the cap is not reached
    gone = {
        "carbon-a100": both["carbon-a100"],
        "carbon-pool-b": dict(both["carbon-pool-b"], file=False, busy=False),
    }
    _ticks(config, client, 30, boxes=gone, start=late + 300, count=1)
    assert client.terminated == ["i-b"]
    release = next(e for e in _log(config) if e["action"] == "release")
    assert release["why"] == "day_budget"
    # carbon-a100 alone to 00:00Z stays inside the cap: never drained, and no new box is rented that day
    only = {"carbon-a100": both["carbon-a100"]}
    _ticks(config, client, 30, boxes=only, start=late + 600, count=4)
    _ticks(config, client, 30, boxes=only, start=day0 + 86400 - 400, count=1)
    assert client.launched == [] and client.terminated == ["i-b"]
    assert [a for a, _ in calls if a[0] == "mv"] == moves
    assert scale.load_state(config)["boxes"]["carbon-a100"]["phase"] == "ACTIVE"
    assert any(e["action"] == "at_day_cap" for e in _log(config))
    assert scale.spent_today(scale.load_state(config), day0 + 86400 - 1) <= 65.0


def test_the_day_reserve_lets_a_second_box_rent_only_where_the_cap_holds_both(
    tmp_path, monkeypatch
):
    """With carbon-a100 up all day (USD 47.76), a USD 48 cap rents no 2nd box; USD 65 rents one."""
    day0 = T0 - T0 % 86400
    for cap, rents in ((48.0, 0), (65.0, 1)):
        (tmp_path / str(cap)).mkdir()
        config = _config(tmp_path / str(cap), max_usd_per_day=cap, max_boxes=2)
        client = _Client([A100])
        busy = {"file": True, "busy": True, "last": day0, "admitted": day0}
        scale.adopt(
            config,
            "carbon-a100",
            A100["ip"],
            client=client,
            door=lambda c, busy=busy: (0, {"carbon-a100": busy}, 0),
            now=day0,
        )
        monkeypatch.setattr(scale, "_door", _recording_door([]))
        _ticks(
            config, client, 30, boxes={"carbon-a100": busy}, start=day0 + 3600, count=3
        )
        assert len(client.launched) == rents
        assert any(e["action"] == "at_day_cap" for e in _log(config)) == (not rents)


def test_over_day_budget_keeps_the_oldest_below_the_cap_and_drains_all_at_it(tmp_path):
    config = _config(tmp_path, max_usd_per_day=65.0, max_boxes=2)
    day0 = T0 - T0 % 86400
    state = {
        "boxes": {
            "old": {"launched": day0, "price_usd_h": PRICE, "phase": "ACTIVE"},
            "new": {"launched": day0 + 3600, "price_usd_h": PRICE, "phase": "ACTIVE"},
            "gone": {
                "launched": day0 + 12 * 3600,
                "price_usd_h": PRICE,
                "phase": "DRAINING",
            },
        },
        "spent": {},
    }
    assert scale.over_day_budget(state, day0 + 3600, config) == set()
    # 12:00Z: spent 12 h + 11 h = 45.77 < 65, but "old" to 00:00Z (23.88) leaves "new" no half hour
    assert scale.over_day_budget(state, day0 + 12 * 3600, config) == {"new"}
    state["spent"][scale._day(day0)] = 65.0
    assert scale.over_day_budget(state, day0 + 3600, config) == {"old", "new"}


def test_a_failed_bring_up_pages(tmp_path, monkeypatch):
    config = _config(tmp_path, page_outbox="ops-watch/outbox.jsonl")
    client = _Client()
    calls = []
    monkeypatch.setattr(scale, "_door", _recording_door(calls))
    _ticks(config, client, 50, count=2)
    (name,) = client.launched
    state = scale.load_state(config)
    state["boxes"][name].update(result="FAILED", reason="door:door_link_failed")
    scale.save_state(config, state)
    _ticks(config, client, 50, start=T0 + 900, count=1)
    ((argv, stdin),) = [c for c in calls if c[0][0] == "sh"]
    assert argv[-1] == 'cat >> "$HOME"/ops-watch/outbox.jsonl'
    line = json.loads(stdin)
    assert line["sev"] == "ALERT" and line["key"] == f"autoscale_bring_up_failed:{name}"
    assert "door:door_link_failed" in line["text"] and client.terminated == ["i-0"]


def test_the_prewarm_hook_keeps_one_box_inside_its_window(tmp_path, monkeypatch):
    """The hook (no window is configured yet): inside a ``prewarm_utc`` window one box is rented with no backlog and
    the last box is not released idle; outside it nothing changes."""
    hour = (T0 % 86400) // 3600
    config = _config(tmp_path, prewarm_utc=((hour, hour + 1),))
    assert scale.prewarm(config, T0) == 1 and scale.prewarm(config, T0 + 3600) == 0
    client = _Client()
    _ticks(config, client, 0, count=1)
    assert len(client.launched) == 1
    assert [e["rule"] for e in _log(config) if e["action"] == "rent"] == ["prewarm"]
    assert scale.prewarm(_config(tmp_path), T0) == 0


def test_config_refuses_a_missing_or_too_high_daily_cap(tmp_path):
    raw = {k: list(v) if type(v) is tuple else v for k, v in _CFG_MIN.items()}
    path = tmp_path / "c.json"
    for bad in (
        {"max_usd_per_day": None},
        {"max_usd_per_day": 145.0},
        {"prewarm_utc": [[5, 3]]},
    ):
        path.write_text(json.dumps({**raw, **bad}))
        with pytest.raises(SystemExit):
            scale.load_config(path)
    path.write_text(json.dumps({**raw, "prewarm_utc": [[6, 9]]}))
    assert scale.load_config(path).prewarm_utc == ((6, 9),)


def test_the_spawned_bring_up_command_parses(tmp_path, monkeypatch):
    """The detached bring-up's own command line must parse: a "?" name after ``--config`` did not (19 Nov 2026), so
    every box the autoscaler rented sat until the bring-up timeout."""
    seen = []
    monkeypatch.setattr(scale.subprocess, "run", lambda argv, **_: seen.append(argv))
    monkeypatch.setattr(scale, "CONFIG_PATH", [str(tmp_path / "config.json")])
    scale._spawn_bring_up(_config(tmp_path), "carbon-pool-11191155")
    argv = seen[0]
    script = argv.index(scale.os.path.abspath(scale.__file__))
    args = scale._parser().parse_args(argv[script + 1 :])
    assert args.command == "bring-up"
    assert args.name == "carbon-pool-11191155"
    assert args.config == str(tmp_path / "config.json")


def test_no_box_while_the_grade_queue_is_the_limit(tmp_path):
    """Builds wait, but more than GRADE_SHORT tasks wait to grade: a box would only move tasks into the grade queue."""
    config = _config(tmp_path)
    client = _Client()
    _ticks(config, client, 31, grading=35)
    assert client.launched == []
    assert "grade_bound" in [line["action"] for line in _log(config)]


def test_an_unreadable_grade_queue_never_rents(tmp_path):
    config = _config(tmp_path)
    client = _Client()
    _ticks(config, client, 31, grading=None)
    assert client.launched == []


def test_a_short_grade_queue_rents_at_the_six_minute_tick(tmp_path):
    """The 5-minute timer fires every 360 s (systemd's 1-min accuracy): two samples 360 s apart still hold."""
    config = _config(tmp_path)
    client = _Client()
    _ticks(config, client, 31, grading=scale.GRADE_SHORT, every=360, count=2)
    assert len(client.launched) == 1


#: a throwaway ed25519 public key made for this test (no private half kept) and its `ssh-keygen -lf` fingerprint
_TEST_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIManWiRHmMhNw1kEbOqy0SArUbLppCj81daXQv9iDAIW"
)
_TEST_FP = "SHA256:Ly3uqeEksDw8h+KyEKpCDf0a1gADf5fLx4l0rX7CU8g"


def test_the_host_key_fingerprint_reads_a_keyscan_line():
    """ssh-keyscan prints `<host> ssh-ed25519 <base64>`: the key is the field after the type (field 1 crashed every
    bring-up, 20 Nov 2026)."""
    assert scale._fingerprint("203.0.113.9 " + _TEST_KEY) == _TEST_FP
    assert (
        scale._fingerprint("[203.0.113.9]:20301 " + _TEST_KEY + " comment") == _TEST_FP
    )
    assert scale._fingerprint(_TEST_KEY) == _TEST_FP


def test_bring_up_pins_the_keyscan_host_key_and_runs_both_phases(tmp_path, monkeypatch):
    config = _config(tmp_path)
    (tmp_path / "key").write_text("k")
    state = {
        "samples": [],
        "boxes": {
            "carbon-pool-a": {
                "id": "i-1",
                "launched": T0,
                "phase": "UP",
                "price_usd_h": PRICE,
            }
        },
        "backoff_until": 0,
    }
    scale.save_state(config, state)
    client = _Client(
        [
            {
                "id": "i-1",
                "name": "carbon-pool-a",
                "status": "active",
                "ip": "203.0.113.9",
                "type": "gpu_1x_a100_sxm4",
                "price_usd_h": PRICE,
            }
        ]
    )
    runs = []

    class _Run:
        def __init__(self, stdout, returncode=0):
            self.stdout, self.returncode = stdout, returncode

    def run(argv, **_):
        runs.append(argv)
        if argv[0] == "ssh-keyscan":
            return _Run(
                "# 203.0.113.9:22 SSH-2.0-OpenSSH\n203.0.113.9 " + _TEST_KEY + "\n"
            )
        return _Run('{"status": "PASS"}\n')

    monkeypatch.setattr(
        scale, "_door", lambda config, argv, **_: _Run(b'{"status": "ADMITTED"}\n')
    )
    scale.bring_up(config, "carbon-pool-a", client=client, run=run, wait=lambda s: None)
    record = scale.load_state(config)["boxes"]["carbon-pool-a"]
    assert record["result"] == "ADMITTED"
    assert record["host_key_fingerprint"] == _TEST_FP
    admin = next(a for a in runs if "admin" in a)
    assert admin[admin.index("--host-key-fingerprint") + 1] == _TEST_FP


# -- the Lium client (LIUM_ADA_SWITCH_PLAN S1/S2; not wired into tick until the pod bring-up and the owner's budget) --


class _Done:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def _pod(name, status="RUNNING", price=0.79, pod_id=None):
    return {
        "id": pod_id or f"id-{name}",
        "name": name,
        "huid": "calm-fox-1a",
        "status": status,
        "gpu_type": "RTX6000",
        "price_per_hour": price,
        "ip": "203.0.113.7",
        "ports": {"22": 20050, "20000": 20000},
    }


def _hk(tag):
    """An SS58-shaped fake SN51 hotkey (``tag``: one base58 letter)."""
    return ("5Hk" + tag * 45)[:48]


def _node(price, available=1, cpus=31, gpus=1):
    return {
        "id": f"node-{round(price * 100)}-{cpus}",
        "huid": "noble-shark-59",
        "gpu_type": "RTX6000",
        "gpu_count": gpus,
        "available_gpu_count": available,
        "cpu_count": cpus,
        "price_per_gpu_hour": price,
    }


def _executor(node, hotkey=None, **extra):
    """Lium's REST row of a node (``GET /api/executors``)."""
    return {"id": node["id"], "miner_hotkey": hotkey or _hk("a"), **extra}


def _lium(
    tmp_path,
    *,
    pods=(),
    nodes=(),
    balance=86.0,
    fail=None,
    up=None,
    executors=None,
    refuse=(),
    **kw,
):
    calls = []
    (tmp_path / "lium_key").write_text("sk_test_never_in_argv\n")
    rest = [_executor(n) for n in nodes] if executors is None else list(executors)

    def opener(request, timeout):
        calls.append({"url": request.full_url, "headers": dict(request.header_items())})
        return io.BytesIO(json.dumps(rest).encode())

    def operator_check(hotkeys):
        calls.append({"operator_check": list(hotkeys)})
        return {h: h in refuse for h in hotkeys}

    def run(argv, **options):
        calls.append({"argv": list(argv), "env": options.get("env", {})})
        command = argv[1]
        if fail == command:
            return _Done(returncode=2, stderr="error\nNo GPUs available on that node")
        if command == "ps":
            return _Done(json.dumps(list(pods)))
        if command == "ls":
            return _Done(json.dumps(list(nodes)))
        if command == "balance":
            return _Done(json.dumps({"balance_usd": balance, "currency": "USD"}))
        if command == "up":
            return _Done(
                json.dumps(
                    up
                    if up is not None
                    else _pod(argv[argv.index("--name") + 1], pod_id="pod-new")
                )
            )
        if command == "rm":
            return _Done(json.dumps([{"id": argv[2]}]))
        return _Done(returncode=2, stderr="unknown")

    settings = {
        "name_prefix": "carbon-ada-",
        "gpu": "RTX6000",
        "min_cpus": 28,
        "ttl": "12h",
        "budget_usd": 10,
        "run": run,
        "opener": opener,
        "operator_check": operator_check,
    }
    settings.update(kw)
    return scale.LiumCli("lium", str(tmp_path / "lium_key"), **settings), calls


def test_lium_lists_only_its_own_pods_never_the_gate_or_exam_pods(tmp_path):
    client, _ = _lium(
        tmp_path,
        pods=[
            _pod("carbon-ada-11200101"),
            _pod("carbon-ada-11200102", status="PENDING"),
            _pod("claude-runner-gate-136"),
            _pod("claude-exam-rb-s4-box", price=1.59),
        ],
    )
    found = client.instances()
    assert [i["name"] for i in found] == ["carbon-ada-11200101", "carbon-ada-11200102"]
    assert [i["status"] for i in found] == ["active", "booting"]
    assert found[0]["ssh_port"] == 20050 and found[0]["price_usd_h"] == 0.79


def test_lium_offers_the_cheapest_free_node_with_enough_threads(tmp_path):
    client, calls = _lium(
        tmp_path,
        nodes=[
            _node(0.85),
            _node(0.79),
            _node(0.60, available=0),
            _node(0.50, cpus=16),
        ],
    )
    assert client.offer() == (0.79, "lium")
    assert client.node_id == "node-79-31"
    listed = calls[0]["argv"]
    assert listed[1:3] == ["ls", "--format"] and "--min-cpus" in listed


def test_lium_refuses_to_rent_when_the_balance_would_not_last_three_hours(tmp_path):
    """Lium deletes every pod of an account whose balance reaches zero: all pods' burn counts, not only the pool's."""
    pods = [
        _pod("claude-runner-gate-136", price=0.79),
        _pod("claude-exam-rb-s4-box", price=1.59),
    ]
    rich, _ = _lium(tmp_path, pods=pods, nodes=[_node(0.79)], balance=86.0)
    assert rich.offer() == (0.79, "lium")
    poor, _ = _lium(tmp_path, pods=pods, nodes=[_node(0.79)], balance=9.0)
    assert poor.offer() is None and poor.refused == "low_balance"
    empty, _ = _lium(tmp_path, nodes=[_node(0.79, available=0)])
    assert empty.offer() is None and empty.refused == "no_node"


def test_lium_launch_rents_one_gpu_of_the_offered_node_with_a_hard_ttl_and_budget(
    tmp_path,
):
    client, calls = _lium(tmp_path, nodes=[_node(0.79)], template_id="tpl-1")
    assert client.offer() == (0.79, "lium")
    assert client.launch(name="carbon-ada-11200103") == "pod-new"
    argv = calls[-1]["argv"]
    # the exact node the offer's operator check passed, never a node the backend picks
    assert argv[:3] == ["lium", "up", "node-79-31"]
    assert "--gpu" not in argv and "--min-cpus" not in argv
    for flag, value in (
        ("--count", "1"),
        ("--name", "carbon-ada-11200103"),
        ("--ttl", "12h"),
        ("--budget", "10"),
        ("--template_id", "tpl-1"),
    ):
        assert argv[argv.index(flag) + 1] == value
    assert {"--yes", "--no-ssh", "--json"} <= set(argv)


def test_lium_never_launches_a_pod_outside_its_prefix_and_never_puts_the_key_in_argv(
    tmp_path,
):
    client, calls = _lium(tmp_path, nodes=[_node(0.79)])
    with pytest.raises(ValueError):
        client.launch(name="claude-runner-gate-137")
    client.offer()
    client.terminate("pod-x")
    assert calls[-1]["argv"] == [
        "lium",
        "rm",
        "pod-x",
        "--yes",
        "--name-only",
        "--format",
        "json",
    ]
    for call in (c for c in calls if "argv" in c):
        assert "sk_test_never_in_argv" not in " ".join(call["argv"])
        assert call["env"]["LIUM_API_KEY"] == "sk_test_never_in_argv"


def test_lium_failures_raise_with_the_clis_reason(tmp_path):
    client, _ = _lium(tmp_path, nodes=[_node(0.79)], fail="up")
    client.offer()
    with pytest.raises(scale.LiumError, match="No GPUs available"):
        client.launch(name="carbon-ada-11200104")
    noid, _ = _lium(tmp_path, nodes=[_node(0.79)], up={"status": "RUNNING"})
    noid.offer()
    with pytest.raises(scale.LiumError, match="no pod id"):
        noid.launch(name="carbon-ada-11200105")
    with pytest.raises(scale.LiumError):
        client.restart("pod-x")


def test_config_refuses_a_lium_pool_until_its_bring_up_and_budget_exist(tmp_path):
    values = {
        k: (list(v) if isinstance(v, tuple) else v)
        for k, v in _config(tmp_path).__dict__.items()
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps({**values, "provider": "lium"}))
    with pytest.raises(SystemExit, match="only 'lambda' runs"):
        scale.load_config(path)
    path.write_text(json.dumps(values))
    assert scale.load_config(path).provider == "lambda"


# -- S2: the operator-identity check (V2 third-party compute condition 4) --


def test_lium_offers_the_cheapest_node_whose_operator_passes(tmp_path):
    nodes = [_node(0.85), _node(0.60), _node(0.79)]
    client, calls = _lium(
        tmp_path,
        nodes=nodes,
        executors=[
            _executor(nodes[0], _hk("c")),
            _executor(nodes[1], _hk("a")),
            _executor(nodes[2], _hk("b")),
        ],
        refuse={_hk("a")},
    )
    # the cheaper node's operator is a netuid-116 participant: skipped
    assert client.offer() == (0.79, "lium")
    assert client.node_id == "node-79-31" and client.refused is None
    checks = [c["operator_check"] for c in calls if "operator_check" in c]
    assert checks == [[_hk("a"), _hk("b"), _hk("c")]]  # one door call, cheapest first


def test_lium_rents_nothing_when_every_operator_is_refused(tmp_path):
    nodes = [_node(0.60), _node(0.79)]
    client, _ = _lium(
        tmp_path,
        nodes=nodes,
        executors=[_executor(nodes[0], _hk("a")), _executor(nodes[1], _hk("b"))],
        refuse={_hk("a"), _hk("b")},
    )
    assert client.offer() is None
    assert client.refused == "operator" and client.node_id is None
    with pytest.raises(ValueError, match="no node chosen"):
        client.launch(name="carbon-ada-11200106")


def test_lium_drops_a_node_without_an_operator_hotkey_or_with_frequent_rent_failures(
    tmp_path,
):
    nodes = [_node(0.50), _node(0.55), _node(0.60), _node(0.79)]
    client, calls = _lium(
        tmp_path,
        nodes=nodes,
        executors=[
            {"id": nodes[0]["id"]},
            _executor(nodes[1], "not-an-ss58"),
            _executor(nodes[2], _hk("c"), frequent_rent_failures=True),
            _executor(nodes[3], _hk("b")),
        ],
    )
    assert client.offer() == (0.79, "lium") and client.node_id == "node-79-31"
    checks = [c["operator_check"] for c in calls if "operator_check" in c]
    assert checks == [[_hk("b")]]
    unknown, _ = _lium(tmp_path, nodes=nodes[:1], executors=[{"id": nodes[0]["id"]}])
    assert unknown.offer() is None and unknown.refused == "no_node"


def test_lium_reads_executors_with_the_key_in_a_header_never_the_url(tmp_path):
    client, calls = _lium(tmp_path, nodes=[_node(0.79)])
    client.offer()
    (rest,) = [c for c in calls if "url" in c]
    assert rest["url"] == "https://lium.io/api/executors"
    assert rest["headers"]["X-api-key"] == "sk_test_never_in_argv"
    assert "sk_test" not in rest["url"]


def test_lium_offer_skips_an_excluded_operator(tmp_path):
    """The spot re-build control rents a second node from a DIFFERENT operator (owner O3)."""
    nodes = [_node(0.60), _node(0.79), _node(0.85)]
    client, calls = _lium(
        tmp_path,
        nodes=nodes,
        executors=[
            _executor(nodes[0], _hk("a")),
            _executor(nodes[1], _hk("a")),
            _executor(nodes[2], _hk("b")),
        ],
    )
    assert client.offer() == (0.60, "lium") and client.node_hotkey == _hk("a")
    assert client.offer(exclude_hotkeys=[client.node_hotkey]) == (0.85, "lium")
    assert client.node_id == "node-85-31" and client.node_hotkey == _hk("b")
    checks = [c["operator_check"] for c in calls if "operator_check" in c]
    assert checks[-1] == [_hk("b")]  # the excluded operator is not even checked
    assert client.offer(exclude_hotkeys={_hk("a"), _hk("b")}) is None
    assert client.refused == "no_node" and client.node_hotkey is None


def test_lium_random_pick_returns_only_a_passing_node(tmp_path):
    class _Rng:
        def __init__(self):
            self.seen = []

        def choice(self, options):
            self.seen.append(list(options))
            return options[-1]

    nodes = [_node(0.60), _node(0.70), _node(0.79), _node(0.85)]
    rng = _Rng()
    client, _ = _lium(
        tmp_path,
        nodes=nodes,
        executors=[
            _executor(nodes[0], _hk("a")),
            _executor(nodes[1], _hk("b")),
            _executor(nodes[2], _hk("c")),
            _executor(nodes[3], _hk("d")),
        ],
        refuse={_hk("b"), _hk("d")},
        rng=rng,
    )
    assert client.offer(pick="random") == (0.79, "lium")
    assert client.node_id == "node-79-31" and client.node_hotkey == _hk("c")
    (options,) = rng.seen
    # the chooser only ever sees passing nodes (the refused operators b and d are gone)
    assert [node for _, node, _ in options] == ["node-60-31", "node-79-31"]
    with pytest.raises(ValueError, match="pick"):
        client.offer(pick="priciest")


def _check_config(tmp_path, args=None):
    if args is None:
        args = (
            "/door/venv/bin/python",
            "-I",
            "/door/carbon/scripts/dev/operator_check.py",
            "--network",
            "finney",
            "--netuid",
            "116",
        )
    return _config(tmp_path, door_operator_check_args=tuple(args))


def _reply(hotkeys, refuse=(), netuid=116, **override):
    reply = {
        "schema": "carbon.operator-check.v1",
        "netuid": netuid,
        "finalized_block": 100,
        "block_hash": "0x" + "ab" * 32,
        "results": [
            {
                "hotkey": h,
                "owner_coldkey": None,
                "refuse": h in refuse,
                "why": "carbon_hotkey" if h in refuse else None,
            }
            for h in hotkeys
        ],
    }
    reply.update(override)
    return json.dumps(reply).encode()


def test_the_door_operator_check_runs_one_door_call_and_reads_its_v1_reply(tmp_path):
    seen = []

    def door(config, argv, timeout=120, **_):
        seen.append(list(argv))
        hotkeys = argv[argv.index("--hotkey") + 1 :: 2]
        return _Done(_reply(hotkeys, refuse={_hk("a")}))

    check = scale.door_operator_check(_check_config(tmp_path), door=door)
    assert check([_hk("a"), _hk("b")]) == {_hk("a"): True, _hk("b"): False}
    (argv,) = seen
    assert argv[:3] == [
        "/door/venv/bin/python",
        "-I",
        "/door/carbon/scripts/dev/operator_check.py",
    ]
    assert argv[-4:] == ["--hotkey", _hk("a"), "--hotkey", _hk("b")]


@pytest.mark.parametrize(
    "door_reply",
    [
        "raise",
        _Done(b"", returncode=1, stderr=b"operator_check: chain read failed"),
        _Done(b"not json"),
        _Done(_reply([_hk("b")], schema="carbon.operator-check.v0")),
        _Done(_reply([_hk("b")], netuid=567)),
        _Done(_reply([])),  # a hotkey unanswered
        _Done(
            json.dumps(
                {
                    "schema": "carbon.operator-check.v1",
                    "netuid": 116,
                    "results": [{"hotkey": _hk("b"), "refuse": "no"}],
                }
            ).encode()
        ),
    ],
)
def test_a_failed_operator_check_rents_nothing(tmp_path, door_reply):
    def door(config, argv, timeout=120, **_):
        if door_reply == "raise":
            raise TimeoutError("ssh")
        return door_reply

    nodes = [_node(0.79)]
    client, _ = _lium(
        tmp_path,
        nodes=nodes,
        executors=[_executor(nodes[0], _hk("b"))],
        operator_check=scale.door_operator_check(_check_config(tmp_path), door=door),
    )
    assert client.offer() is None
    assert client.refused == "operator_check_failed" and client.node_id is None
    with pytest.raises(ValueError):
        client.launch(name="carbon-ada-11200107")


def test_no_operator_check_configured_rents_nothing(tmp_path):
    unset, _ = _lium(tmp_path, nodes=[_node(0.79)], operator_check=None)
    assert unset.offer() is None and unset.refused == "operator_check_failed"
    empty, _ = _lium(
        tmp_path,
        nodes=[_node(0.79)],
        operator_check=scale.door_operator_check(_config(tmp_path)),
    )
    assert empty.offer() is None and empty.refused == "operator_check_failed"


def test_lium_launch_without_a_passing_offer_raises_and_a_node_is_rented_once(
    tmp_path,
):
    client, calls = _lium(tmp_path, nodes=[_node(0.79)])
    with pytest.raises(ValueError, match="no node chosen"):
        client.launch(name="carbon-ada-11200108")
    assert not [c for c in calls if c.get("argv", [None, None])[1] == "up"]
    client.offer()
    assert client.launch(name="carbon-ada-11200108") == "pod-new"
    with pytest.raises(ValueError, match="no node chosen"):
        client.launch(name="carbon-ada-11200109")


def test_config_checks_the_door_operator_check_args(tmp_path):
    values = {
        k: (list(v) if isinstance(v, tuple) else v)
        for k, v in _check_config(tmp_path).__dict__.items()
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(values))
    assert scale.load_config(path).door_operator_check_args[-2:] == ("--netuid", "116")
    good = values["door_operator_check_args"]
    for bad in (good[:-2], good[:-1], [*good, "--hotkey", _hk("a")], [*good, ""]):
        path.write_text(json.dumps({**values, "door_operator_check_args": bad}))
        with pytest.raises(SystemExit, match="door_operator_check_args"):
            scale.load_config(path)


def _write_config(tmp_path, config, **overrides):
    path = tmp_path / "pool.json"
    raw = {k: list(v) if type(v) is tuple else v for k, v in config.__dict__.items()}
    path.write_text(json.dumps({**raw, **overrides}))
    return path


def test_each_instance_type_has_its_own_owner_ceiling(tmp_path):
    """A6000 pool (G-LEAD-60: same pool rules as the A100) loads within 3 boxes and
    USD 6/h; an instance type without an owner line refuses to start; no config may
    exceed its type's ceiling."""
    config = _config(tmp_path)
    a6k = scale.load_config(
        _write_config(
            tmp_path,
            config,
            instance_type="gpu_1x_a6000",
            name_prefix="carbon-a6k-",
            max_boxes=3,
        )
    )
    assert a6k.instance_type == "gpu_1x_a6000" and a6k.max_boxes == 3
    for bad in (
        {"instance_type": "gpu_1x_a10"},
        {"instance_type": "gpu_1x_a6000", "max_boxes": 4},
        {"instance_type": "gpu_1x_a6000", "max_usd_per_hour": 6.5},
        {"count_scope": "everything"},
    ):
        with pytest.raises(SystemExit):
            scale.load_config(_write_config(tmp_path, config, **bad))


def _vm(ident, name, status="active", price=PRICE):
    return {"id": ident, "name": name, "status": status, "ip": "x", "price_usd_h": price}


def test_prefix_scope_counts_only_this_pools_boxes(tmp_path):
    """count_scope "account" (default) counts every instance on the account;
    "prefix" counts only this pool's boxes."""
    others = [
        _vm("a100", "carbon-pool-0101"),
        _vm("vm1", "rb20-r1", price=1.29),
        _vm("vm2", "rb20-hrb1-b2", price=1.29),
        _vm("old", "carbon-a6k-0", status="terminated", price=1.09),
    ]
    a6k = {"instance_type": "gpu_1x_a6000", "name_prefix": "carbon-a6k-"}
    account = _config(tmp_path, **a6k)
    assert account.count_scope == "account"
    assert not scale.may_rent(others, 1.09, account)  # 3 live on the account: at cap
    pool = _config(tmp_path, count_scope="prefix", **a6k)
    assert scale.may_rent(others, 1.09, pool)  # none of its own: room
    mine = [_vm(f"m{k}", f"carbon-a6k-{k}", price=1.09) for k in range(3)]
    assert not scale.may_rent(others + mine, 1.09, pool)  # 3 of its own: at its cap
    assert scale.may_rent(others + mine[:2], 1.09, pool)
