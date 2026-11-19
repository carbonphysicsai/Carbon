"""The on-demand A100 autoscaler (`scripts/dev/gpu_pool_autoscale.py`): rent when builds back up (policy v2: 3 waiting
through 5 min, or any through 10 min), drain then release a box idle 30 min, never past the owner's line (3 boxes,
USD 6/h) or the daily cap, every rent and release logged with cost, failures paged.
"""

from __future__ import annotations

import importlib.util
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
    config, client, waiting, *, boxes=None, start=T0, every=300, count=4, spawned=None
):
    state = None
    for k in range(count):
        state = scale.tick(
            config,
            client=client,
            door=lambda c: (waiting, {} if boxes is None else boxes),
            now=start + k * every,
            spawn=lambda c, name: (spawned if spawned is not None else []).append(name),
        )
    return state


def _log(config):
    return [
        json.loads(line)
        for line in (Path(config.state_dir) / "log.jsonl").read_text().splitlines()
    ]


def _samples(*waiting, every=300):
    return [{"t": T0 + k * every, "waiting": w} for k, w in enumerate(waiting)]


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
    s = [{"t": T0, "waiting": 9}]
    assert scale.want_box(s, T0 + 300) is None


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
        door=lambda c: (0, busy),
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
            door=lambda c: (0, boxes),
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
        door=lambda c: (0, {"carbon-a100": {"file": True}}),
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
        door=lambda c: (80, idle),
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
        door=lambda c: (0, idle),
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
        door=lambda c: (0, {"carbon-a100": entry}),
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
    out["queue"] = json.dumps({"waiting_to_build": 4, "door_state": "grading"}).encode()
    assert scale.read_door(config) == (4, {})
    out["queue"] = json.dumps(
        {"waiting_to_build": 4, "door_state": "draining"}
    ).encode()
    assert scale.read_door(config) == (None, {})


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
        door=lambda c: (0, {"carbon-a100": busy}),
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
    monkeypatch.setitem(scale.CONFIG_PATH, 0, str(tmp_path / "config.json"))
    scale._spawn_bring_up(_config(tmp_path), "carbon-pool-11191155")
    argv = seen[0]
    script = argv.index(scale.os.path.abspath(scale.__file__))
    args = scale._parser().parse_args(argv[script + 1 :])
    assert args.command == "bring-up"
    assert args.name == "carbon-pool-11191155"
    assert args.config == str(tmp_path / "config.json")
