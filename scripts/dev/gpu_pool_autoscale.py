#!/usr/bin/env python3
"""On-demand A100 build boxes: rent one when the door's builds back up, release one that sits idle (Compute Ops).

Owner's standing line (Compute Ops, 16 Nov 2026): "rent and release Lambda A100 40GB boxes on demand for GPU builds,
up to 3 boxes and USD 6/h total, following TE3's bring-up and class check; release any box idle more than 1 h". The
door side is `carbon.reconstruction.remote_gpu_build`'s box pool: a box joins when ``gpu_box_up.py door`` writes its
box file on PASS, and drains when that file is gone (running builds finish); with no box up, graphs build on the CPU.

One ``tick`` per run (a host timer runs it every 5 minutes; nothing here loops or sleeps):

1. **Read.** The door's PUBLIC queue (``GET /carbon/v1/queue/<challenge>``: ``waiting_to_build``) and, read-only on
   the door, each box file and whether any of the box's slots is busy, and when one last was (`DOOR_PROBE`). The
   Lambda account's instances and the instance type's live price.
2. **Scale up.** When ``waiting_to_build > N`` in every sample of the last `UP_WINDOW_S` (15 min, at least 3
   samples), N = `BUILDS_PER_BOX_HOUR` x max(1, boxes up) (the measured hourly builds of one box: the queue is more
   than the boxes up can clear in an hour), no box up has all its slots free (then the door, not the box count, holds
   the queue), no box was released idle in the last ``idle_release_s``, nothing is being brought up, the account holds fewer than ``max_boxes``
   instances and one more keeps the hourly total within ``max_usd_per_hour``: launch ONE instance, then bring it up
   (`bring_up`, detached): pin its host key, ``gpu_box_up.py admin`` here with the admin key, ``gpu_box_up.py door``
   on the door with the lane key. A failed bring-up terminates the instance at once (never paid for idle).
3. **Scale down.** A box THIS tool launched whose slots have all been free for more than ``idle_release_s`` (1 h)
   is drained first (its box file renamed ``<name>.json.drained``); once no slot is busy it is terminated.

Every launch, failure and release is a line in ``<state_dir>/log.jsonl`` with its price, hours and cost. Instances
this tool did not launch (``name_prefix``) count toward the box and dollar caps but are never touched, unless ADOPTED
(``adopt <box> --ip <ip>``: a box already up on the door, e.g. carbon-a100, put under the same idle release; owner
17 Nov 2026, "I don't think we need an always on one"). ``tick --dry-run`` reads everything and changes nothing
(no rent, drain, release, state or log line): it prints what a tick would do. It decides nothing scientific and reads
no hidden value: the queue counts are public, and the box files are the door's own.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

#: One A100 box's measured builds per hour (HEALTH 17 Nov 2026 13:38Z: 12 in the last 60 min, all on the one A100,
#: 4 slots). An operational value: re-measure it as the per-box rate changes. That hour was starved (builds waited on
#: 2 grade lanes), so 12 is a floor: to be replaced from the door journal's build rate after switch 3 (owner C8).
BUILDS_PER_BOX_HOUR = 12
#: How long the queue must stay above N before a box is rented (the brief: 15 min).
UP_WINDOW_S = 900
MIN_UP_SAMPLES = 3
#: Samples kept (2 h at the 5-minute timer).
KEEP_SAMPLES = 24
#: A bring-up that has not finished in this long is failed (gpu_box_up: under 20 min).
BRING_UP_LIMIT_S = 45 * 60
#: After a failed bring-up, no new rent for this long.
FAIL_BACKOFF_S = 30 * 60
LAMBDA_API = "https://cloud.lambdalabs.com/api/v1"
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
#: ``tick --dry-run``: no rent, drain, release, state write or log-file line (printed only, marked ``dry``).
DRY = [False]

#: Run on the door as the door user (`python3 -I -`, stdin): read-only. Prints one JSON line: each box file's name and
#: admitted time, and per box directory whether a slot is busy now and the newest slot activity (directory mtimes: a
#: slot's records are created and removed in its directory, so its mtime moves with every op).
DOOR_PROBE = r"""
import fcntl, json, os, sys, time
root, boxes = sys.argv[1], sys.argv[2]
out = {"boxes": {}, "now": time.time()}
try:
    names = sorted(os.listdir(boxes))
except OSError:
    names = []
for name in names:
    if not name.endswith(".json") or "." in name[:-5]:
        continue
    box = name[:-5]
    entry = {"file": True, "busy": False, "last": 0.0}
    try:
        with open(os.path.join(boxes, name), "rb") as handle:
            document = json.load(handle)
        entry["admitted"] = float(document.get("admitted_unix") or 0)
    except (OSError, ValueError, TypeError):
        entry["admitted"] = 0.0
    out["boxes"][box] = entry
pool = os.path.join(root, "remote-gpu-build")
try:
    dirs = [n[4:] for n in os.listdir(pool) if n.startswith("box-")]
except OSError:
    dirs = []
for box in dirs:
    out["boxes"].setdefault(box, {"file": False, "busy": False, "last": 0.0, "admitted": 0.0})
for box, entry in out["boxes"].items():
    directory = os.path.join(root, "remote-gpu-build", "box-" + box)
    try:
        slots = [s for s in os.listdir(directory) if s.startswith("slot-")]
    except OSError:
        slots = []
    for slot in slots:
        path = os.path.join(directory, slot)
        try:
            entry["last"] = max(entry["last"], os.stat(path).st_mtime)
        except OSError:
            continue
        if os.path.exists(os.path.join(path, "active-allocation.json")):
            entry["busy"] = True
            continue
        try:
            fd = os.open(os.path.join(path, "slot.lock"), os.O_RDWR)
        except OSError:
            continue
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
        except BlockingIOError:
            entry["busy"] = True
        finally:
            os.close(fd)
print(json.dumps(out))
"""


@dataclass(frozen=True)
class Config:
    lambda_key_file: str
    instance_type: str
    ssh_key_name: str
    admin_key: str
    device_kind: str
    door_ssh: str
    door_ssh_options: tuple
    door_ip: str
    door_queue_url: str
    door_host_root: str
    door_phase_args: tuple
    lane_pubkey: str
    box_up_script: str
    state_dir: str
    name_prefix: str = "carbon-pool-"
    max_boxes: int = 3
    max_usd_per_hour: float = 6.0
    idle_release_s: int = 3600
    regions: tuple = ()

    @property
    def boxes_dir(self):
        return f"{self.door_host_root}/remote-gpu-build-boxes.d"


def load_config(path) -> Config:
    raw = json.loads(Path(path).read_text())
    raw.pop("_comment", None)
    for key in ("door_ssh_options", "door_phase_args", "regions"):
        if key in raw:
            raw[key] = tuple(raw[key])
    config = Config(**raw)
    if not (0 < config.max_boxes <= 3) or not (0 < config.max_usd_per_hour <= 6.0):
        # the owner's line is the ceiling; a config may only lower it
        raise SystemExit("config exceeds the owner's line (<= 3 boxes, <= USD 6/h)")
    if not config.name_prefix or not _NAME.fullmatch(
        config.name_prefix.rstrip("-") or "x"
    ):
        raise SystemExit("name_prefix")
    return config


# -- the policy (pure) ------------------------------------------------------------------------------------------------


def threshold(boxes_up: int) -> int:
    """N: more waiting builds than the boxes up clear in an hour (one box's rate when none is up)."""
    return BUILDS_PER_BOX_HOUR * max(1, boxes_up)


def want_box(samples, now, boxes_up) -> bool:
    """Whether the queue stayed above N for the whole window: every sample of the last `UP_WINDOW_S`, at least
    `MIN_UP_SAMPLES` of them, and the oldest at least the window ago (so a gap in the timer never counts as 15 min).
    """
    n = threshold(boxes_up)
    window = [s for s in samples if now - s["t"] <= UP_WINDOW_S + 60]
    if (
        len(window) < MIN_UP_SAMPLES
        or now - min(s["t"] for s in window) < UP_WINDOW_S - 60
    ):
        return False
    return all(s["waiting"] is not None and s["waiting"] > n for s in window)


def may_rent(instances, price_usd_h, config) -> bool:
    """Within the owner's line after one more: at most ``max_boxes`` instances and ``max_usd_per_hour`` in total."""
    live = [i for i in instances if i["status"] not in ("terminated", "terminating")]
    if len(live) + 1 > config.max_boxes:
        return False
    total = sum(i["price_usd_h"] for i in live) + price_usd_h
    return total <= config.max_usd_per_hour + 1e-9


def idle_for(entry, now) -> float:
    """Seconds since the box last had a busy slot (its newest slot activity, else its admission)."""
    if entry.get("busy"):
        return 0.0
    return now - max(entry.get("last") or 0.0, entry.get("admitted") or 0.0)


# -- the outside world ------------------------------------------------------------------------------------------------


class Lambda:
    def __init__(self, key_file, opener=None):
        self._key = Path(key_file).read_text().strip()
        self._open = opener or urllib.request.urlopen

    def _call(self, method, path, body=None):
        request = urllib.request.Request(
            LAMBDA_API + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": "Basic "
                + base64.b64encode(f"{self._key}:".encode()).decode(),
                "Content-Type": "application/json",
                "User-Agent": "carbon-gpu-pool/1",
            },
        )
        with self._open(request, timeout=60) as response:
            return json.loads(response.read())

    def instances(self):
        found = []
        for item in self._call("GET", "/instances")["data"]:
            found.append(
                {
                    "id": item["id"],
                    "name": item.get("name") or "",
                    "status": item["status"],
                    "ip": item.get("ip"),
                    "region": (item.get("region") or {}).get("name"),
                    "type": item["instance_type"]["name"],
                    "price_usd_h": item["instance_type"]["price_cents_per_hour"] / 100,
                }
            )
        return found

    def offer(self, instance_type, regions=()):
        """The type's live price and a region with capacity now (in ``regions`` order when given), or None."""
        entry = self._call("GET", "/instance-types")["data"].get(instance_type)
        if entry is None:
            return None
        price = entry["instance_type"]["price_cents_per_hour"] / 100
        available = [
            r["name"] for r in entry.get("regions_with_capacity_available", [])
        ]
        ordered = [r for r in regions if r in available] or available
        return (price, ordered[0]) if ordered else (price, None)

    def launch(self, *, region, instance_type, ssh_key_name, name):
        body = {
            "region_name": region,
            "instance_type_name": instance_type,
            "ssh_key_names": [ssh_key_name],
            "quantity": 1,
            "name": name,
        }
        return self._call("POST", "/instance-operations/launch", body)["data"][
            "instance_ids"
        ][0]

    def terminate(self, instance_id):
        self._call(
            "POST", "/instance-operations/terminate", {"instance_ids": [instance_id]}
        )

    def restart(self, instance_id):
        self._call(
            "POST", "/instance-operations/restart", {"instance_ids": [instance_id]}
        )


def _door(config, argv, *, stdin=None, timeout=120):
    return subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            *config.door_ssh_options,
            config.door_ssh,
            shlex.join(argv),
        ],
        input=stdin,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def read_door(config):
    """``(waiting_to_build or None, boxes)`` read on the door (`DOOR_PROBE`, the public queue)."""
    probe = _door(
        config,
        ["python3", "-I", "-", config.door_host_root, config.boxes_dir],
        stdin=DOOR_PROBE.encode(),
    )
    boxes = json.loads(probe.stdout)["boxes"] if probe.returncode == 0 else None
    queue = _door(config, ["curl", "-sf", "--max-time", "20", config.door_queue_url])
    try:
        waiting = int(json.loads(queue.stdout)["waiting_to_build"])
    except (ValueError, KeyError, TypeError):
        waiting = None
    return waiting, boxes


# -- state and log ----------------------------------------------------------------------------------------------------


def _state_path(config):
    return Path(config.state_dir) / "state.json"


def load_state(config):
    try:
        return json.loads(_state_path(config).read_text())
    except (OSError, ValueError):
        return {"samples": [], "boxes": {}, "backoff_until": 0}


def save_state(config, state):
    if DRY[0]:
        return
    path = _state_path(config)
    temporary = path.with_name(f".state.{os.getpid()}")
    temporary.write_text(json.dumps(state, sort_keys=True, indent=1) + "\n")
    os.replace(temporary, path)


def log(config, **fields):
    fields = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **fields}
    if DRY[0]:
        print(json.dumps({**fields, "dry": True}, sort_keys=True))
        return
    with open(Path(config.state_dir) / "log.jsonl", "a") as handle:
        handle.write(json.dumps(fields, sort_keys=True) + "\n")
    print(json.dumps(fields, sort_keys=True))


def _hours(record, now):
    return round((now - record["launched"]) / 3600, 3)


def _released(config, state, name, record, client, now, why):
    if DRY[0]:
        log(config, action="would_release", box=name, id=record["id"], why=why)
        return
    try:
        client.terminate(record["id"])
    except Exception as error:  # noqa: BLE001 - logged; the next tick retries
        log(
            config,
            action="release_failed",
            box=name,
            id=record["id"],
            error=type(error).__name__,
        )
        return
    hours = _hours(record, now)
    log(
        config,
        action="release",
        box=name,
        id=record["id"],
        why=why,
        price_usd_h=record["price_usd_h"],
        hours=hours,
        cost_usd=round(hours * record["price_usd_h"], 2),
    )
    state["boxes"].pop(name, None)
    if why == "idle":
        # a box just sat idle a whole idle period with builds waiting: boxes were not what held the queue (owner C8,
        # no overpay), so the next rent waits one more idle period of backlog
        state["backoff_until"] = max(
            state.get("backoff_until", 0), now + config.idle_release_s
        )


# -- one tick ---------------------------------------------------------------------------------------------------------


def tick(config, *, client=None, door=None, now=None, spawn=None):
    now = time.time() if now is None else now
    client = client or Lambda(config.lambda_key_file)
    state = load_state(config)
    waiting, boxes = (door or read_door)(config)
    state["samples"] = (state["samples"] + [{"t": now, "waiting": waiting}])[
        -KEEP_SAMPLES:
    ]
    instances = client.instances()
    by_id = {i["id"]: i for i in instances}
    ours = state["boxes"]

    # a box we launched that the account no longer has: gone (logged once)
    for name, record in list(ours.items()):
        if record["id"] not in by_id or by_id[record["id"]]["status"] in (
            "terminated",
        ):
            hours = _hours(record, now)
            log(
                config,
                action="gone",
                box=name,
                id=record["id"],
                hours=hours,
                cost_usd=round(hours * record["price_usd_h"], 2),
            )
            ours.pop(name)

    # bring-ups: done, failed or stuck
    for name, record in list(ours.items()):
        if record["phase"] == "UP":
            if boxes is not None and boxes.get(name, {}).get("file"):
                record["phase"] = "ACTIVE"
                log(
                    config,
                    action="active",
                    box=name,
                    id=record["id"],
                    minutes=round((now - record["launched"]) / 60, 1),
                )
            elif (
                record.get("result") == "FAILED"
                or now - record["launched"] > BRING_UP_LIMIT_S
            ):
                state["backoff_until"] = now + FAIL_BACKOFF_S
                log(
                    config,
                    action="bring_up_failed",
                    box=name,
                    id=record["id"],
                    reason=record.get("reason", "timeout"),
                )
                _released(config, state, name, record, client, now, "bring_up_failed")

    if boxes is not None:
        # scale down: idle > idle_release_s -> drain (rename the box file), then release once no slot is busy
        for name, record in list(ours.items()):
            entry = boxes.get(name)
            if record["phase"] == "ACTIVE" and entry is not None and entry.get("file"):
                if idle_for(entry, now) > config.idle_release_s and DRY[0]:
                    log(
                        config,
                        action="would_drain",
                        box=name,
                        id=record["id"],
                        idle_min=round(idle_for(entry, now) / 60, 1),
                    )
                elif idle_for(entry, now) > config.idle_release_s:
                    moved = _door(
                        config,
                        [
                            "mv",
                            "-n",
                            f"{config.boxes_dir}/{name}.json",
                            f"{config.boxes_dir}/{name}.json.drained",
                        ],
                    )
                    if moved.returncode == 0:
                        record["phase"] = "DRAINING"
                        log(
                            config,
                            action="drain",
                            box=name,
                            id=record["id"],
                            idle_min=round(idle_for(entry, now) / 60, 1),
                        )
            elif record["phase"] == "DRAINING" and (
                entry is None or not entry.get("busy")
            ):
                _released(config, state, name, record, client, now, "idle")

    # scale up
    up = sum(1 for r in ours.values() if r["phase"] == "ACTIVE")
    up += sum(
        1 for name, e in (boxes or {}).items() if e.get("file") and name not in ours
    )
    bringing = any(r["phase"] == "UP" for r in ours.values())
    # a box up with every slot free: more boxes would sit free too (the door, not box count, holds the queue)
    idle_box = any(e.get("file") and not e.get("busy") for e in (boxes or {}).values())
    if (
        boxes is not None
        and not bringing
        and not idle_box
        and now >= state.get("backoff_until", 0)
        and want_box(state["samples"], now, up)
    ):
        offer = client.offer(config.instance_type, config.regions)
        if offer is None or offer[1] is None:
            log(config, action="no_capacity", waiting=waiting, n=threshold(up))
        elif not may_rent(instances, offer[0], config):
            log(
                config,
                action="at_cap",
                waiting=waiting,
                n=threshold(up),
                instances=len(instances),
            )
        elif DRY[0]:
            log(
                config,
                action="would_rent",
                price_usd_h=offer[0],
                region=offer[1],
                waiting=waiting,
                n=threshold(up),
            )
        else:
            price, region = offer
            name = f"{config.name_prefix}{time.strftime('%m%d%H%M', time.gmtime(now))}"
            instance_id = client.launch(
                region=region,
                instance_type=config.instance_type,
                ssh_key_name=config.ssh_key_name,
                name=name,
            )
            ours[name] = {
                "id": instance_id,
                "launched": now,
                "price_usd_h": price,
                "region": region,
                "phase": "UP",
            }
            log(
                config,
                action="rent",
                box=name,
                id=instance_id,
                region=region,
                price_usd_h=price,
                waiting=waiting,
                n=threshold(up),
            )
            save_state(config, state)
            (spawn or _spawn_bring_up)(config, name)
    save_state(config, state)
    if DRY[0]:
        print(
            json.dumps(
                {
                    "dry": True,
                    "waiting_to_build": waiting,
                    "n": threshold(up),
                    "boxes_up": up,
                    "want_box": want_box(state["samples"], now, up),
                    "idle_box_up": idle_box,
                    "backoff_until": state.get("backoff_until", 0),
                    "samples_in_window": len(
                        [
                            x
                            for x in state["samples"]
                            if now - x["t"] <= UP_WINDOW_S + 60
                        ]
                    ),
                    "door_boxes": boxes,
                    "ours": ours,
                    "account_instances": [
                        {k: i[k] for k in ("name", "status", "type", "price_usd_h")}
                        for i in instances
                    ],
                },
                sort_keys=True,
            )
        )
    return state


def adopt(config, name, ip, *, client=None, door=None, now=None):
    """Put a box already up on the door under this tool's idle release: the account's active instance at ``ip`` whose
    box file ``name`` is on the door is recorded ACTIVE (hours and cost count from now). Refused if the name is taken,
    the box file is absent, or no single active instance has that address."""
    now = time.time() if now is None else now
    client = client or Lambda(config.lambda_key_file)
    if not _NAME.fullmatch(name):
        raise SystemExit("adopt: bad box name")
    state = load_state(config)
    if name in state["boxes"]:
        raise SystemExit(f"adopt: {name} is already this tool's")
    _, boxes = (door or read_door)(config)
    if boxes is None or not boxes.get(name, {}).get("file"):
        raise SystemExit(f"adopt: no box file {name}.json on the door")
    found = [i for i in client.instances() if i["ip"] == ip and i["status"] == "active"]
    if len(found) != 1:
        raise SystemExit(f"adopt: {len(found)} active instances at {ip}")
    instance = found[0]
    state["boxes"][name] = {
        "id": instance["id"],
        "launched": now,
        "price_usd_h": instance["price_usd_h"],
        "region": instance.get("region"),
        "ip": ip,
        "phase": "ACTIVE",
        "adopted": True,
    }
    log(
        config,
        action="adopt",
        box=name,
        id=instance["id"],
        ip=ip,
        price_usd_h=instance["price_usd_h"],
        idle_min=round(idle_for(boxes[name], now) / 60, 1),
    )
    save_state(config, state)
    return state


def _spawn_bring_up(config, name):
    subprocess.run(
        [
            "systemd-run",
            "--user",
            "--collect",
            f"--unit=carbon-pool-up-{name}",
            sys.executable,
            "-I",
            os.path.abspath(__file__),
            "bring-up",
            "--config",
            CONFIG_PATH[0],
            name,
        ],
        check=False,
    )


CONFIG_PATH = [""]


# -- bring-up (detached) ----------------------------------------------------------------------------------------------


def _fingerprint(line):
    blob = base64.b64decode(line.split()[1])
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip(
        "="
    )


def _set_result(config, name, **fields):
    with open(Path(config.state_dir) / "lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state(config)
        if name in state["boxes"]:
            state["boxes"][name].update(fields)
            save_state(config, state)


def bring_up(config, name, *, client=None, run=subprocess.run, wait=time.sleep):
    """Wait for the instance, pin its host key (first contact over the IP the provider's API returned), run the
    admin phase here and the door phase on the door. Any failure records FAILED (the next tick releases the box).
    """
    client = client or Lambda(config.lambda_key_file)
    record = load_state(config)["boxes"][name]
    deadline = time.time() + BRING_UP_LIMIT_S - 60
    ip = None
    while time.time() < deadline:
        found = {i["id"]: i for i in client.instances()}.get(record["id"])
        if found and found["status"] == "active" and found["ip"]:
            ip = found["ip"]
            break
        wait(20)
    if ip is None:
        return _set_result(config, name, result="FAILED", reason="not_active")
    key = None
    while time.time() < deadline and key is None:
        scan = run(
            ["ssh-keyscan", "-T", "10", "-t", "ed25519", ip],
            capture_output=True,
            text=True,
            check=False,
        )
        lines = [line for line in scan.stdout.splitlines() if " ssh-ed25519 " in line]
        key = lines[0] if len(lines) == 1 else None
        if key is None:
            wait(15)
    if key is None:
        return _set_result(config, name, result="FAILED", reason="host_key")
    fingerprint = _fingerprint(key)
    _set_result(config, name, ip=ip, host_key_fingerprint=fingerprint)
    common = [
        "--ip",
        ip,
        "--host-key-fingerprint",
        fingerprint,
        "--device-kind",
        config.device_kind,
        "--door-ip",
        config.door_ip,
    ]
    summary = Path(config.state_dir) / f"{name}.admin.json"
    for attempt in (1, 2):
        admin = run(
            [
                sys.executable,
                "-I",
                config.box_up_script,
                "admin",
                *common,
                "--lane-pubkey",
                config.lane_pubkey,
                "--ssh-key",
                config.admin_key,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=1800,
        )
        summary.write_text(admin.stdout)
        if admin.returncode == 0:
            break
        if attempt == 1 and "driver_upgrade_needs_reboot" in admin.stdout:
            client.restart(record["id"])
            wait(180)
            continue
        return _set_result(
            config, name, result="FAILED", reason="admin:" + _reason(admin.stdout)
        )
    copied = _door(
        config,
        ["sh", "-c", f"umask 077; cat > ~/.carbon-pool-{name}.admin.json"],
        stdin=summary.read_bytes(),
    )
    if copied.returncode != 0:
        return _set_result(config, name, result="FAILED", reason="admin_summary_copy")
    door = _door(
        config,
        [
            "python3",
            "-I",
            *config.door_phase_args[:1],
            "door",
            *common,
            *config.door_phase_args[1:],
            "--box-name",
            name,
            "--provider",
            "lambda",
            "--boxes-dir",
            config.boxes_dir,
            "--admin-summary",
            f".carbon-pool-{name}.admin.json",
        ],
        timeout=1800,
    )
    (Path(config.state_dir) / f"{name}.door.json").write_bytes(door.stdout)
    if door.returncode != 0:
        return _set_result(
            config,
            name,
            result="FAILED",
            reason="door:" + _reason(door.stdout.decode(errors="replace")),
        )
    return _set_result(config, name, result="ADMITTED")


def _reason(output):
    for line in reversed(output.splitlines()):
        try:
            return str(
                json.loads(line).get("reason") or json.loads(line).get("status")
            )[:120]
        except (ValueError, AttributeError):
            continue
    return "unknown"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("tick", "bring-up", "status", "adopt"))
    parser.add_argument("name", nargs="?")
    parser.add_argument("--config", required=True)
    parser.add_argument("--ip", help="adopt: the box's address")
    parser.add_argument(
        "--dry-run", action="store_true", help="tick/adopt: print, change nothing"
    )
    args = parser.parse_args(argv)
    DRY[0] = args.dry_run
    CONFIG_PATH[0] = os.path.abspath(args.config)
    config = load_config(args.config)
    Path(config.state_dir).mkdir(mode=0o700, parents=True, exist_ok=True)
    if args.command == "bring-up":
        bring_up(config, args.name)
        return 0
    if args.command == "status":
        print(json.dumps(load_state(config), indent=1, sort_keys=True))
        return 0
    with open(Path(config.state_dir) / "lock", "a") as lock:
        if args.command == "adopt":
            if not args.name or not args.ip:
                raise SystemExit("adopt <box> --ip <ip>")
            fcntl.flock(lock, fcntl.LOCK_EX)
            adopt(config, args.name, args.ip)
            return 0
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0  # another tick is running
        tick(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
