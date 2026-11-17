"""The on-demand A100 autoscaler (`scripts/dev/gpu_pool_autoscale.py`): rent when builds back up, drain then release a
box idle more than an hour, never past the owner's line (3 boxes, USD 6/h), every rent and release logged with cost.
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


def test_n_is_one_box_hour_of_builds_per_box_up():
    assert scale.threshold(0) == scale.BUILDS_PER_BOX_HOUR == 12
    assert scale.threshold(2) == 24


def test_a_backlog_above_n_for_15_minutes_rents_one_box(tmp_path):
    config = _config(tmp_path)
    client, spawned = _Client(), []
    _ticks(config, client, 13, count=3, spawned=spawned)
    # three samples over 10 minutes: not yet 15 minutes
    assert client.launched == []
    _ticks(config, client, 13, start=T0 + 900, count=1, spawned=spawned)
    assert len(client.launched) == 1 and spawned == client.launched
    rent = [e for e in _log(config) if e["action"] == "rent"]
    assert (
        rent[0]["price_usd_h"] == PRICE
        and rent[0]["n"] == 12
        and rent[0]["waiting"] == 13
    )
    # while it is brought up, no second rent
    _ticks(config, client, 80, start=T0 + 1200, count=4, spawned=spawned)
    assert len(client.launched) == 1


def test_a_backlog_that_dips_or_is_unreadable_rents_nothing(tmp_path):
    config = _config(tmp_path)
    client = _Client()
    for k, waiting in enumerate((40, 40, 5, 40, 40)):
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
    _ticks(config, client, 99, boxes=idle, start=T0 + 3900, count=4)
    printed = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert {"would_drain"} <= {p.get("action") for p in printed}
    assert client.launched == [] and client.terminated == []
    assert (Path(config.state_dir) / "state.json").read_text() == before
    assert (Path(config.state_dir) / "log.jsonl").read_text() == log_before
    assert printed[-1]["dry"] and printed[-1]["waiting_to_build"] == 99
