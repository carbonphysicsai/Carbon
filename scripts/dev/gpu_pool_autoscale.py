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
2. **Scale up** (policy v2, Lead 18 Nov 2026; values from live 116's data, see `RENT_MANY`). When `RENT_MANY`
   builds wait in every sample across `RENT_MANY_S` (5 min), or any build waits across `RENT_ANY_S` (10 min), no
   box up has all its slots free (then the door, not the box count, holds the queue), nothing is being brought up,
   no bring-up failed in the last `FAIL_BACKOFF_S`, the account holds fewer than ``max_boxes`` instances, one more
   keeps the hourly total within ``max_usd_per_hour`` and today's spend leaves room under ``max_usd_per_day``: launch
   ONE instance, then bring it up (`bring_up`, detached): pin its host key, ``gpu_box_up.py admin`` here with the
   admin key, ``gpu_box_up.py door`` on the door with the lane key (whose door_link step proves the door's own build
   wrapper reaches the box before it is ADMITTED). A failed bring-up terminates the instance at once (never paid for
   idle) and pages. Inside a ``prewarm_utc`` window one box is kept up (a hook; no window is set yet).
3. **Scale down.** A box THIS tool launched or adopted whose slots have all been free for more than
   ``idle_release_s`` (30 min) is drained first (its box file renamed ``<name>.json.drained``); once no slot is busy
   it is terminated. The idle clock runs only while the door can use the box: a tick whose queue is unreadable (the
   door down, restarting or moved), whose ``door_state`` is ``draining``, or that shows ``waiting_to_build > 0``
   stamps every box ``held_at`` = now, and idle counts from the latest of that stamp, the box's last busy slot and
   its admission. A box file put back with an old admission time therefore does not start out idle (carbon-a100 was
   released 18 Nov 2026 13:51Z, 6 min after a rollback restored its file, with builds queued). The LAST box is never
   drained or released while builds wait: a draining last box gets its file back (``undrain``) when a tick sees
   ``waiting_to_build > 0`` (Lead, 18 Nov 2026). The one exception is the daily cap: once today's spend reaches
   ``max_usd_per_day`` every box of this tool drains and is released, nothing is rented until 00:00Z, and a page
   goes out if builds wait.

Pages are ALERT lines in the door's pager outbox (``page_outbox``; the pager dedupes and sends them): a failed
bring-up, a failed release, the daily cap reached while builds wait. They name boxes, counts and USD only.

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

#: Policy v2 (Lead 18 Nov 2026, owner "yea something like that"), set from live 116's own data, 17 Nov 00:03Z -
#: 18 Nov 20:55Z (550 build ops, read-only from the door's ledgers): one 7-slot A100 finishes up to 64-66 builds in
#: its busiest hour (the old N = 12 builds/box-hour was 5x low, so a backlog the box could clear in minutes rented and
#: a real one waited 15 min); A100 build wall p50 156 s, p90 353 s; local CPU p50 104 s. Builds arrive in bursts:
#: split at 10 idle min, 57 bursts, size p50 5 / p90 20, gaps p50 16.6 min / p90 81 min. Cold start (the replacement
#: A100, 18 Nov): rent 14:37Z -> admin PASS 14:46Z -> door phase 790 s -> ADMITTED 15:01:50Z, about 25 min.
#: Rent when RENT_MANY builds wait through RENT_MANY_S, or any build waits through RENT_ANY_S: a build that waits that
#: long found every local lane and box slot full (the door builds on the CPU first when no box is free).
RENT_MANY = 3
RENT_MANY_S = 300
RENT_ANY_S = 600
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
    #: the burst gaps above: p50 16.6 min is bridged, the long gaps (p90 81 min) are not paid for
    idle_release_s: int = 1800
    regions: tuple = ()
    #: USD per UTC day over this tool's boxes (launched or adopted); no default: the owner/Lead sets it
    max_usd_per_day: float | None = None
    #: the door's pager outbox (relative to the door user's home); "" pages nothing
    page_outbox: str = "ops-watch/outbox.jsonl"
    #: [[start_hour, end_hour], ...] UTC: keep one box warm inside a window (a hook; empty until 24 h+ of G7 data)
    prewarm_utc: tuple = ()

    @property
    def boxes_dir(self):
        return f"{self.door_host_root}/remote-gpu-build-boxes.d"


def load_config(path) -> Config:
    raw = json.loads(Path(path).read_text())
    raw.pop("_comment", None)
    for key in ("door_ssh_options", "door_phase_args", "regions"):
        if key in raw:
            raw[key] = tuple(raw[key])
    if "prewarm_utc" in raw:
        raw["prewarm_utc"] = tuple(tuple(w) for w in raw["prewarm_utc"])
    config = Config(**raw)
    if not (0 < config.max_boxes <= 3) or not (0 < config.max_usd_per_hour <= 6.0):
        # the owner's line is the ceiling; a config may only lower it
        raise SystemExit("config exceeds the owner's line (<= 3 boxes, <= USD 6/h)")
    if config.max_usd_per_day is None or not (
        0 < config.max_usd_per_day <= 24 * config.max_usd_per_hour
    ):
        raise SystemExit(
            "max_usd_per_day: set by the owner/Lead, at most 24 x max_usd_per_hour"
        )
    if any(len(w) != 2 or not (0 <= w[0] < w[1] <= 24) for w in config.prewarm_utc):
        raise SystemExit(
            "prewarm_utc: [[start_hour, end_hour], ...], 0 <= start < end <= 24"
        )
    if not config.name_prefix or not _NAME.fullmatch(
        config.name_prefix.rstrip("-") or "x"
    ):
        raise SystemExit("name_prefix")
    return config


# -- the policy (pure) ------------------------------------------------------------------------------------------------


def _held(samples, now, span, least) -> bool:
    """Every sample of the last ``span`` s showed at least ``least`` builds waiting, with one sample per 5-minute tick
    across it and the oldest at least ``span`` ago (a gap in the timer, or an unreadable queue, never counts).
    """
    window = [s for s in samples if now - s["t"] <= span + 60]
    if len(window) < 1 + span // 300 or now - min(s["t"] for s in window) < span - 60:
        return False
    return all(s["waiting"] is not None and s["waiting"] >= least for s in window)


def want_box(samples, now) -> str | None:
    """Why one more box is wanted: ``many`` (`RENT_MANY` builds waited through `RENT_MANY_S`), ``any`` (a build waited
    through `RENT_ANY_S`), else None."""
    if _held(samples, now, RENT_MANY_S, RENT_MANY):
        return "many"
    if _held(samples, now, RENT_ANY_S, 1):
        return "any"
    return None


def prewarm(config, now) -> int:
    """Boxes to keep warm now: 1 inside a `Config.prewarm_utc` window, else 0 (the hook; no window is set yet)."""
    hour = (now % 86400) / 3600
    return int(any(start <= hour < end for start, end in config.prewarm_utc))


def _day(now):
    return time.strftime("%Y-%m-%d", time.gmtime(now))


def _cost_today(record, now) -> float:
    """USD the box has cost since the UTC day began (its launch or adoption, if later)."""
    start = max(record["launched"], now - now % 86400)
    return max(0.0, now - start) / 3600 * record["price_usd_h"]


def spent_today(state, now) -> float:
    """USD this tool's boxes cost today: the released ones (``state["spent"]``) and the ones it holds now."""
    closed = state.get("spent", {}).get(_day(now), 0.0)
    return closed + sum(_cost_today(r, now) for r in state["boxes"].values())


def _close_cost(state, record, now):
    spent = state.setdefault("spent", {})
    spent[_day(now)] = round(spent.get(_day(now), 0.0) + _cost_today(record, now), 4)
    for day in sorted(spent)[:-7]:
        spent.pop(day)


def may_rent(instances, price_usd_h, config) -> bool:
    """Within the owner's line after one more: at most ``max_boxes`` instances and ``max_usd_per_hour`` in total."""
    live = [i for i in instances if i["status"] not in ("terminated", "terminating")]
    if len(live) + 1 > config.max_boxes:
        return False
    total = sum(i["price_usd_h"] for i in live) + price_usd_h
    return total <= config.max_usd_per_hour + 1e-9


def idle_for(entry, now, record=None) -> float:
    """Seconds since the box last had a busy slot (its newest slot activity, else its admission), and since this tool
    last saw the door unable to use it or builds waiting (``record["held_at"]``)."""
    if entry.get("busy"):
        return 0.0
    return now - max(
        entry.get("last") or 0.0,
        entry.get("admitted") or 0.0,
        (record or {}).get("held_at") or 0.0,
    )


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
        public = json.loads(queue.stdout)
        waiting = int(public["waiting_to_build"])
        if public.get("door_state") == "draining":
            # a draining door builds nothing new: as unreadable (no idle clock, no drain, release or rent)
            waiting = None
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


def page(config, state, key, text, *, now, once=False):
    """An ALERT line in the door's pager outbox (`carbon_pager` reads it, dedupes per ``key`` and sends it). The text
    carries box names, counts and USD only. ``once``: at most one line per key (kept in ``state["paged"]``).
    """
    if not config.page_outbox or (once and key in state.get("paged", {})):
        return
    line = {
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "key": key,
        "sev": "ALERT",
        "text": text,
        "to": "Lead, Compute",
        "ts": int(now),
    }
    if DRY[0]:
        log(config, action="would_page", key=key, text=text)
        return
    sent = _door(
        config,
        ["sh", "-c", f'cat >> "$HOME"/{shlex.quote(config.page_outbox)}'],
        stdin=(json.dumps(line, sort_keys=True) + "\n").encode(),
    )
    log(config, action="page", key=key, ok=sent.returncode == 0)
    if sent.returncode == 0 and once:
        paged = state.setdefault("paged", {})
        paged[key] = int(now)
        for old in sorted(paged, key=paged.get)[:-20]:
            paged.pop(old)


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
        page(
            config,
            state,
            f"autoscale_release_failed:{name}",
            f"GPU POOL: release of {name} failed ({type(error).__name__}); still paid, the next tick retries",
            now=now,
        )
        return
    _close_cost(state, record, now)
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


# -- one tick ---------------------------------------------------------------------------------------------------------


def _drain(config, name, record, why, **fields):
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
        record["drain_why"] = why
        log(config, action="drain", box=name, id=record["id"], why=why, **fields)


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
    if waiting is None or waiting > 0:
        # the door cannot use an idle box now (down, restarting, draining, moved) or builds wait for one: not idle
        for record in ours.values():
            record["held_at"] = now

    # a box we launched that the account no longer has: gone (logged once)
    for name, record in list(ours.items()):
        if record["id"] not in by_id or by_id[record["id"]]["status"] in (
            "terminated",
        ):
            _close_cost(state, record, now)
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
                reason = record.get("reason", "timeout")
                log(
                    config,
                    action="bring_up_failed",
                    box=name,
                    id=record["id"],
                    reason=reason,
                )
                page(
                    config,
                    state,
                    f"autoscale_bring_up_failed:{name}",
                    f"GPU POOL: bring-up of {name} failed ({reason}); released, no new rent for "
                    f"{FAIL_BACKOFF_S // 60} min; builds waiting {waiting}",
                    now=now,
                )
                _released(config, state, name, record, client, now, "bring_up_failed")

    spent = spent_today(state, now)
    at_day_cap = spent >= config.max_usd_per_day
    if at_day_cap and waiting:
        page(
            config,
            state,
            f"autoscale_day_cap:{_day(now)}",
            f"GPU POOL: daily cap USD {config.max_usd_per_day:g} reached (spent {spent:.2f}) with {waiting} builds "
            "waiting; no rent until 00:00Z, boxes drain",
            now=now,
            once=True,
        )

    if boxes is not None and waiting is not None:
        # an unreadable queue or a draining door (a switch, the door down or moved) changes nothing: no drain, no
        # release (V2, 17 Nov 2026); a failed bring-up above is still released (never paid for idle)
        filed = [n for n, e in boxes.items() if e.get("file")]
        for name, record in list(ours.items()):
            entry = boxes.get(name)
            if record["phase"] == "ACTIVE" and entry is not None and entry.get("file"):
                idle = idle_for(entry, now, record)
                why = (
                    "day_cap"
                    if at_day_cap
                    else (
                        "idle"
                        if idle > config.idle_release_s
                        and len(filed) > prewarm(config, now)
                        else None
                    )
                )
                if why and DRY[0]:
                    log(
                        config,
                        action="would_drain",
                        box=name,
                        id=record["id"],
                        why=why,
                        idle_min=round(idle / 60, 1),
                    )
                elif why:
                    _drain(config, name, record, why, idle_min=round(idle / 60, 1))
                    if record["phase"] == "DRAINING":
                        filed.remove(name)
            elif (
                record["phase"] == "DRAINING"
                and waiting > 0
                and not at_day_cap
                and not any(
                    e.get("file") for other, e in boxes.items() if other != name
                )
            ):
                # the last box while builds wait: never released; its box file goes back (Lead, 18 Nov 2026)
                if DRY[0]:
                    log(config, action="would_undrain", box=name, id=record["id"])
                else:
                    back = _door(
                        config,
                        [
                            "mv",
                            "-n",
                            f"{config.boxes_dir}/{name}.json.drained",
                            f"{config.boxes_dir}/{name}.json",
                        ],
                    )
                    if back.returncode == 0:
                        record["phase"] = "ACTIVE"
                        log(
                            config,
                            action="undrain",
                            box=name,
                            id=record["id"],
                            waiting=waiting,
                        )
            elif record["phase"] == "DRAINING" and (
                entry is None or not entry.get("busy")
            ):
                _released(
                    config,
                    state,
                    name,
                    record,
                    client,
                    now,
                    record.get("drain_why", "idle"),
                )

    # scale up
    up = sum(1 for r in ours.values() if r["phase"] == "ACTIVE")
    up += sum(
        1 for name, e in (boxes or {}).items() if e.get("file") and name not in ours
    )
    bringing = any(r["phase"] == "UP" for r in ours.values())
    # a box up with every slot free while builds wait: more boxes would sit free too (the door holds the queue)
    idle_box = any(e.get("file") and not e.get("busy") for e in (boxes or {}).values())
    why = want_box(state["samples"], now)
    if why is None and waiting is not None and up < prewarm(config, now):
        why = "prewarm"
    if (
        boxes is not None
        and why is not None
        and not bringing
        and not (idle_box and why != "prewarm")
        and now >= state.get("backoff_until", 0)
    ):
        offer = client.offer(config.instance_type, config.regions)
        if offer is None or offer[1] is None:
            log(config, action="no_capacity", waiting=waiting, rule=why)
        elif not may_rent(instances, offer[0], config):
            log(
                config,
                action="at_cap",
                waiting=waiting,
                rule=why,
                instances=len(instances),
            )
        elif spent + offer[0] / 2 > config.max_usd_per_day:
            # a new box costs at least its ~25 min bring-up and the first builds
            log(
                config,
                action="at_day_cap",
                waiting=waiting,
                rule=why,
                spent_usd=round(spent, 2),
            )
        elif DRY[0]:
            log(
                config,
                action="would_rent",
                price_usd_h=offer[0],
                region=offer[1],
                waiting=waiting,
                rule=why,
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
                rule=why,
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
                    "boxes_up": up,
                    "want_box": why,
                    "idle_box_up": idle_box,
                    "spent_today_usd": round(spent, 2),
                    "max_usd_per_day": config.max_usd_per_day,
                    "backoff_until": state.get("backoff_until", 0),
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
