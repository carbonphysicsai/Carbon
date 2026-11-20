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
   builds wait in every sample across `RENT_MANY_S` (5 min), or any build waits across `RENT_ANY_S` (10 min), and
   in every sample of that window at most `GRADE_SHORT` tasks wait to grade (builds, not grading, are the bottleneck:
   owner, 19 Nov 2026; otherwise the tick logs ``grade_bound`` and rents nothing), no
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
   ``waiting_to_build > 0`` (Lead, 18 Nov 2026). The one exception is the daily cap (`over_day_budget`): the
   OLDEST box of this tool is reserved the rest of the UTC day, and a newer box drains (``day_budget``), newest
   first, once today's spend plus that reserve leaves it less than `DAY_MARGIN_H` of running; a rent needs
   `RENT_MIN_H` of room after the same reserve. Only when today's spend itself reaches ``max_usd_per_day`` does every
   box drain (``day_cap``): nothing is rented until 00:00Z, and a page goes out if builds wait.

Pages are ALERT lines in the door's pager outbox (``page_outbox``; the pager dedupes and sends them): a failed
bring-up, a failed release, the daily cap reached while builds wait. They name boxes, counts and USD only.

Every launch, failure and release is a line in ``<state_dir>/log.jsonl`` with its price, hours and cost. Instances
this tool did not launch (``name_prefix``) count toward the box and dollar caps but are never touched, unless ADOPTED
(``adopt <box> --ip <ip>``: a box already up on the door, e.g. carbon-a100, put under the same idle release; owner
17 Nov 2026, "I don't think we need an always on one"). ``tick --dry-run`` reads everything and changes nothing
(no rent, drain, release, state or log line): it prints what a tick would do. It decides nothing scientific and reads
no hidden value: the queue counts are public, and the box files are the door's own.

A Lium node (`LiumCli`, not in ``tick`` yet) is rented only after its operator passes the door's identity check
(``operator_check.py``: the node's SN51 hotkey, and that hotkey's owner coldkey, are not netuid-116 participants; fail
closed), LIUM_ADA_SWITCH_PLAN S2 (V2 third-party compute condition 4).
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import random
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
#: A box is added only while BUILDS are the bottleneck (owner "good fix", Lead 19 Nov 2026): the grade queue must be
#: short in every sample of the same window. GRADE_SHORT = the door's remote grade lanes (8 today: FSN1 + HEL1, 4 each):
#: a queue that one round of the lanes clears (~7.5 min at ~453 s per grade) means grading keeps up and more built
#: tasks would be graded soon; a longer one means a new box only moves tasks from the build queue to the grade queue
#: (19 Nov 13:0xZ: 31 waiting to build, 35 waiting to grade). An unreadable grade count never rents.
GRADE_SHORT = 8
#: Samples kept (2 h at the 5-minute timer).
KEEP_SAMPLES = 24
#: A bring-up that has not finished in this long is failed (gpu_box_up: under 20 min).
BRING_UP_LIMIT_S = 45 * 60
#: After a failed bring-up, no new rent for this long.
FAIL_BACKOFF_S = 30 * 60
#: The daily cap keeps the oldest box (owner INFRA-3, 20 Nov 2026: USD 65/day, up to 2 A100s). Draining every box at
#: the cap meant a 2nd A100 run from the morning (2 x USD 1.99/h) took the 1st down with it at ~16:20Z, leaving no
#: build box until 00:00Z. A newer box keeps at least DAY_MARGIN_H of budget for its drain (running builds finish:
#: A100 p90 353 s, plus a 5-min tick), and a rent needs RENT_MIN_H of room (~25 min cold start, then builds).
DAY_MARGIN_H = 0.5
RENT_MIN_H = 1.0
LAMBDA_API = "https://cloud.lambdalabs.com/api/v1"
LIUM_API = "https://lium.io/api"
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_REL_DIR = re.compile(r"[A-Za-z0-9._-][A-Za-z0-9._/-]{0,199}")
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
    #: where ``gpu_box_up door`` writes each box's ssh files for the door's watchdogs (``--ssh-boxes-dir``, relative to
    #: the door user's home: ``.ssh/config.d/carbon-boxes``); a released box's ``<name>.conf`` + ``.known_hosts`` are
    #: removed there. "" removes nothing
    door_ssh_boxes_dir: str = ""
    #: [[start_hour, end_hour], ...] UTC: keep one box warm inside a window (a hook; empty until 24 h+ of G7 data)
    prewarm_utc: tuple = ()
    #: the pool's provider. Only "lambda" runs today: a Lium pool (`LiumCli`) waits for the Lium pod bring-up and the
    #: owner's Lium build budget (codex-queue/reports/INFRA/LIUM_ADA_SWITCH_PLAN_20261119.md, S3 and O1)
    provider: str = "lambda"
    #: argv prefix run on the door for a Lium node's operator-identity check (LIUM_ADA_SWITCH_PLAN S2): the door
    #: python with bittensor, ``-I``, ``scripts/dev/operator_check.py`` of a door checkout, ``--network``,
    #: ``--endpoint``, ``--provider``, ``--genesis-hash``, ``--netuid 116``; each ``--hotkey`` is appended. Empty: no
    #: Lium node passes the check, so none is rented
    door_operator_check_args: tuple = ()

    @property
    def boxes_dir(self):
        return f"{self.door_host_root}/remote-gpu-build-boxes.d"


def load_config(path) -> Config:
    raw = json.loads(Path(path).read_text())
    raw.pop("_comment", None)
    for key in (
        "door_ssh_options",
        "door_phase_args",
        "regions",
        "door_operator_check_args",
    ):
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
    if config.door_ssh_boxes_dir and (
        not _REL_DIR.fullmatch(config.door_ssh_boxes_dir)
        or ".." in config.door_ssh_boxes_dir.split("/")
    ):
        raise SystemExit("door_ssh_boxes_dir: a plain path under the door user's home")
    if not config.name_prefix or not _NAME.fullmatch(
        config.name_prefix.rstrip("-") or "x"
    ):
        raise SystemExit("name_prefix")
    check = config.door_operator_check_args
    at = check.index("--netuid") + 1 if "--netuid" in check else len(check)
    if check and (
        any(type(a) is not str or not a or "\0" in a for a in check)
        or not check[at : at + 1]
        or not check[at].isdigit()
        or "--hotkey" in check
    ):
        raise SystemExit(
            "door_operator_check_args: [python, ..., operator_check.py, ..., --netuid, <n>], no --hotkey"
        )
    if config.provider != "lambda":
        # bring_up knows a Lambda VM only (port 22, apt, sudo); a Lium pod needs the pod-mode bring-up first
        raise SystemExit(
            "provider: only 'lambda' runs; a Lium pool waits for the pod bring-up and the owner's Lium build budget"
        )
    return config


# -- the policy (pure) ------------------------------------------------------------------------------------------------


def _window(samples, now, span):
    """The samples of the last ``span`` s, or None unless there is one per tick across it and the oldest is at least
    ``span`` ago (a gap in the timer never counts). The edge allows 90 s: the 5-minute timer fires every 360 s
    (systemd's default 1-min accuracy), so a 60 s edge dropped the older sample whenever a tick ran late.
    """
    window = [s for s in samples if now - s["t"] <= span + 90]
    if len(window) < 1 + span // 300 or now - min(s["t"] for s in window) < span - 60:
        return None
    return window


def _held(samples, now, span, least) -> bool:
    """Every sample of the last ``span`` s showed at least ``least`` builds waiting (`_window`; an unreadable queue
    never counts) AND at most `GRADE_SHORT` tasks waiting to grade (an unreadable grade count never counts).
    """
    window = _window(samples, now, span)
    if window is None:
        return False
    return all(
        s["waiting"] is not None
        and s["waiting"] >= least
        and s.get("grade") is not None
        and s["grade"] <= GRADE_SHORT
        for s in window
    )


def grade_bound(samples, now) -> bool:
    """Builds would want a box but the grade queue is the limit: `RENT_MANY` builds waited through `RENT_MANY_S` while
    a sample of that window showed more than `GRADE_SHORT` waiting to grade (or no readable count).
    """
    window = _window(samples, now, RENT_MANY_S)
    return (
        bool(window)
        and all(s["waiting"] is not None and s["waiting"] >= RENT_MANY for s in window)
        and not _held(samples, now, RENT_MANY_S, RENT_MANY)
    )


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


def _rest_of_day_h(now) -> float:
    return (86400 - now % 86400) / 3600


def _kept(state):
    """This tool's boxes that run on (being brought up or ACTIVE), oldest launch or adoption first."""
    return sorted(
        (record["launched"], name, record["price_usd_h"])
        for name, record in state["boxes"].items()
        if record["phase"] in ("UP", "ACTIVE")
    )


def day_reserve(state, now) -> float:
    """USD the boxes this tool runs on would cost to the end of the UTC day."""
    return _rest_of_day_h(now) * sum(price for _, _, price in _kept(state))


def over_day_budget(state, now, config) -> set:
    """Boxes to drain for the daily cap. At ``max_usd_per_day`` every one; below it, newest first, each newer box
    whose running leaves under `DAY_MARGIN_H` once today's spend and the rest of the day of every older box are paid.
    The oldest box drains only at the cap itself."""
    spent = spent_today(state, now)
    kept = _kept(state)
    if spent >= config.max_usd_per_day:
        return {name for _, name, _ in kept}
    over, reserve = set(), _rest_of_day_h(now) * kept[0][2] if kept else 0.0
    for _, name, price in kept[1:]:
        if spent + reserve + DAY_MARGIN_H * price > config.max_usd_per_day:
            over.add(name)
        else:
            reserve += _rest_of_day_h(now) * price
    return over


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


#: a Lium pod status as `Lambda`'s instance status (``active`` is the one `bring_up` waits for)
LIUM_STATUS = {"RUNNING": "active", "PENDING": "booting", "CREATING": "booting"}


class LiumError(RuntimeError):
    """A `lium` CLI call failed (non-zero exit or unreadable JSON); the message is the CLI's own reason line."""


#: a Lium node id as ``lium up`` takes it (uuid or huid); never a flag
_NODE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,63}")
#: SS58 shape (`carbon.chain.external_signer`)
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}")
OPERATOR_CHECK_SCHEMA = "carbon.operator-check.v1"


def parse_operator_check(returncode, stdout, hotkeys, netuid=None):
    """``{hotkey: refuse}`` from ``operator_check.py``'s v1 reply; `LiumError` when the reply is not one (non-zero
    exit, unreadable JSON, wrong schema or netuid, a hotkey missing or answered without a Boolean).
    """
    if returncode != 0:
        raise LiumError(f"operator check: exit {returncode}")
    try:
        reply = json.loads(stdout)
    except (ValueError, TypeError) as error:
        raise LiumError("operator check: unreadable JSON") from error
    if (
        type(reply) is not dict
        or reply.get("schema") != OPERATOR_CHECK_SCHEMA
        or (netuid is not None and reply.get("netuid") != netuid)
        or type(reply.get("results")) is not list
    ):
        raise LiumError("operator check: not a v1 reply")
    verdicts = {}
    for row in reply["results"]:
        if type(row) is not dict or type(row.get("refuse")) is not bool:
            raise LiumError("operator check: not a v1 reply")
        verdicts[row.get("hotkey")] = row["refuse"]
    if any(hotkey not in verdicts for hotkey in hotkeys):
        raise LiumError("operator check: a hotkey is unanswered")
    return {hotkey: verdicts[hotkey] for hotkey in hotkeys}


def door_operator_check(config, *, door=None):
    """The production ``operator_check`` of `LiumCli`: one door call of ``door_operator_check_args`` with every
    hotkey, its reply parsed (`parse_operator_check`). Unconfigured, it raises: no node passes.
    """

    def check(hotkeys):
        args = list(config.door_operator_check_args)
        if not args:
            raise LiumError("operator check: door_operator_check_args is not set")
        netuid = int(args[args.index("--netuid") + 1]) if "--netuid" in args else None
        for hotkey in hotkeys:
            args += ["--hotkey", hotkey]
        done = (door or _door)(config, args, timeout=180)
        return parse_operator_check(done.returncode, done.stdout, hotkeys, netuid)

    return check


class LiumCli:
    """Lium (Bittensor SN51) 1-GPU pods through the ``lium`` CLI's JSON mode, with `Lambda`'s interface (owner G15/G16:
    RTX 6000 Ada builds on Lium, Lambda the fallback; LIUM_ADA_SWITCH_PLAN S1). Not wired into `tick` yet: a Lium
    pool needs the pod-mode bring-up (S3) and the owner's Lium build budget (O1), and `load_config` refuses it.

    The CLI, not raw REST: its rent call carries an idempotency key and looks for a half-created pod before it ever
    re-sends, and it registers our ssh key. The API key goes to the CLI by environment (``LIUM_API_KEY``), never argv.

    - Only pods named with ``name_prefix`` are this pool's: the account also holds gate and exam pods, which this
      client never lists, counts or removes.
    - ``offer`` refuses (None) when the account balance would not cover ``min_runway_h`` hours of every pod on the
      account plus the new one: Lium deletes EVERY pod of an account whose balance reaches zero (1 Nov 2026).
    - ``launch`` rents ONE GPU of the cheapest node of ``gpu`` with at least ``min_cpus`` listed CPU threads, with a
      hard ``ttl`` and ``budget_usd`` (Lium cannot extend either). The listed threads are not the pod's quota (a 1-GPU
      slice of a 104-thread node had cgroup cpu.max = 51, 19 Nov 2026): the bring-up measures cpu.max.
    - A rent the CLI cannot confirm raises `LiumError`; a pod it did create carries the prefix, so it is listed and
      counts toward the caps, and its hard ``ttl``/``budget_usd`` bound what it costs.
    - ``offer`` picks a concrete node and ``launch`` rents exactly that node: a node is a candidate only with its SN51
      ``miner_hotkey`` (Lium's REST ``/executors``) and no ``frequent_rent_failures``, and is chosen only when
      ``operator_check`` says its operator is no netuid-116 participant (LIUM_ADA_SWITCH_PLAN S2, V2 third-party
      compute condition 4); a check that fails refuses every node.
    """

    def __init__(
        self,
        cli,
        key_file,
        *,
        name_prefix,
        gpu,
        min_cpus,
        ttl,
        budget_usd,
        template_id=None,
        min_runway_h=3.0,
        run=subprocess.run,
        opener=None,
        operator_check=None,
        rng=None,
    ):
        if not name_prefix or not _NAME.fullmatch(name_prefix.rstrip("-") or "x"):
            raise ValueError("name_prefix")
        self._cli, self._key_file, self._run = cli, key_file, run
        self.name_prefix, self.gpu, self.min_cpus = name_prefix, gpu, int(min_cpus)
        self.ttl, self.budget_usd, self.template_id = (
            ttl,
            float(budget_usd),
            template_id,
        )
        self.min_runway_h = float(min_runway_h)
        self._open = opener or urllib.request.urlopen
        #: ``(hotkeys) -> {hotkey: refuse}`` (`door_operator_check`); None refuses every node
        self._operator_check = operator_check
        #: why the last ``offer`` returned None ("no_node" / "operator" / "operator_check_failed" / "low_balance"),
        #: for the tick's log line
        self.refused = None
        #: ``offer(pick="random")``'s chooser (``.choice``); the OS's randomness unless a test injects one
        self._rng = rng or random.SystemRandom()
        #: the node the last passing ``offer`` chose, which ``launch`` rents (once), and that node's SN51 operator
        #: hotkey (the spot re-build control's ``exclude_hotkeys``, owner O3)
        self.node_id = None
        self.node_hotkey = None

    def _call(self, *args, timeout=300):
        env = {
            **os.environ,
            "LIUM_API_KEY": Path(self._key_file).read_text().strip(),
            "PYTHONIOENCODING": "utf-8",
        }
        done = self._run(
            [self._cli, *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
            check=False,
        )
        if done.returncode != 0:
            raise LiumError(
                ((done.stderr or done.stdout or "").strip().splitlines() or ["?"])[-1][
                    :200
                ]
            )
        try:
            return json.loads(done.stdout)
        except ValueError as error:
            raise LiumError(f"{args[0]}: unreadable JSON") from error

    def _executors(self):
        """Lium's REST node list (``GET /api/executors``): its rows carry each node's SN51 ``miner_hotkey``, which
        the CLI's ``ls`` does not print. The key goes in a header, never a URL."""
        request = urllib.request.Request(
            LIUM_API + "/executors",
            headers={
                "X-API-KEY": Path(self._key_file).read_text().strip(),
                "Accept": "application/json",
                "User-Agent": "carbon-gpu-pool/1",
            },
        )
        try:
            with self._open(request, timeout=60) as response:
                rows = json.loads(response.read())
        except (OSError, ValueError) as error:
            raise LiumError(f"executors: {type(error).__name__}") from error
        if not isinstance(rows, list):
            raise LiumError("executors: not a list")
        return rows

    def _pods(self):
        rows = self._call("ps", "--format", "json")
        return rows if isinstance(rows, list) else rows.get("pods", [])

    def instances(self):
        found = []
        for pod in self._pods():
            name = pod.get("name") or ""
            if not name.startswith(self.name_prefix):
                continue
            status = str(pod.get("status") or "").upper()
            found.append(
                {
                    "id": pod["id"],
                    "name": name,
                    "status": LIUM_STATUS.get(status, status.lower()),
                    "ip": pod.get("ip"),
                    "ssh_port": (pod.get("ports") or {}).get("22"),
                    "region": pod.get("huid"),
                    "type": pod.get("gpu_type"),
                    "price_usd_h": float(pod.get("price_per_hour") or 0),
                }
            )
        return found

    def runway_h(self, extra_usd_h=0.0):
        """Hours the account balance lasts at the burn of EVERY pod on it (pool or not) plus ``extra_usd_h``."""
        balance = float(self._call("balance", "--format", "json")["balance_usd"])
        burn = sum(float(p.get("price_per_hour") or 0) for p in self._pods())
        burn += extra_usd_h
        return float("inf") if burn <= 0 else balance / burn

    def offer(
        self, instance_type=None, regions=(), *, exclude_hotkeys=(), pick="cheapest"
    ):
        """``(price_usd_h, "lium")`` of a node with a free GPU of ``gpu``, at least ``min_cpus`` listed threads, a
        ``miner_hotkey`` not in ``exclude_hotkeys`` and no ``frequent_rent_failures``, whose operator
        ``operator_check`` passes; or None (``refused`` says why). ``pick``: the cheapest passing node, or ``random``
        (uniform among the passing nodes: the spot re-build control's second node from a different operator, owner
        O3). ``node_id``/``node_hotkey`` are the chosen node and its operator. ``instance_type``/``regions`` are
        `Lambda`'s and unused here.
        """
        if pick not in ("cheapest", "random"):
            raise ValueError("offer: pick is 'cheapest' or 'random'")
        excluded = set(exclude_hotkeys)
        self.refused, self.node_id, self.node_hotkey = None, None, None
        rows = self._call(
            "ls",
            "--format",
            "json",
            "--gpu",
            self.gpu,
            "--min-cpus",
            str(self.min_cpus),
        )
        listed = [
            (float(r["price_per_gpu_hour"]), str(r["id"]))
            for r in rows
            if int(r.get("available_gpu_count") or 0) >= 1
            and int(r.get("cpu_count") or 0) >= self.min_cpus
            and r.get("price_per_gpu_hour") is not None
            and _NODE_ID.fullmatch(str(r.get("id") or ""))
        ]
        if not listed:
            self.refused = "no_node"
            return None
        operators = {
            str(e.get("id")): e.get("miner_hotkey")
            for e in self._executors()
            if isinstance(e, dict) and not e.get("frequent_rent_failures")
        }
        candidates = sorted(
            (price, node, operators[node])
            for price, node in listed
            if isinstance(operators.get(node), str)
            and _SS58.fullmatch(operators[node])
            and operators[node] not in excluded
        )
        if not candidates:
            self.refused = "no_node"
            return None
        # one door call; operator_check.py takes at most 64 hotkeys (the cheapest candidates' operators)
        hotkeys = list(dict.fromkeys(hotkey for _, _, hotkey in candidates))[:64]
        try:
            if self._operator_check is None:
                raise LiumError("operator check: none configured")
            verdicts = dict(self._operator_check(hotkeys))
        # an unanswered check rents nothing (fail closed)
        except Exception:  # noqa: BLE001
            self.refused = "operator_check_failed"
            return None
        passing = [
            (price, node, hotkey)
            for price, node, hotkey in candidates
            if hotkey in hotkeys and verdicts.get(hotkey) is False
        ]
        if not passing:
            self.refused = "operator"
            return None
        price, node, hotkey = (
            self._rng.choice(passing) if pick == "random" else passing[0]
        )
        if self.runway_h(price) < self.min_runway_h:
            self.refused = "low_balance"
            return None
        self.node_id, self.node_hotkey = node, hotkey
        return (price, "lium")

    def launch(self, *, region=None, instance_type=None, ssh_key_name=None, name):
        """Rent ONE GPU of the node the last passing ``offer`` chose (``node_id``, used once); the new pod's id.
        ``region``/``instance_type``/``ssh_key_name`` are `Lambda`'s: the CLI's registered key opens the pod. Without
        a chosen node it raises: never a node the backend picks, whose operator nobody checked.
        """
        if not name.startswith(self.name_prefix) or not _NAME.fullmatch(name):
            raise ValueError("launch: the pod name must carry the pool's name_prefix")
        node, self.node_id = self.node_id, None
        if not node or not _NODE_ID.fullmatch(node):
            raise ValueError("launch: no node chosen by a passing offer")
        args = [
            "up",
            node,
            "--count",
            "1",
            "--name",
            name,
            "--ttl",
            self.ttl,
            "--budget",
            f"{self.budget_usd:g}",
            "--yes",
            "--no-ssh",
            "--json",
            "--timeout",
            "900",
        ]
        if self.template_id:
            args += ["--template_id", self.template_id]
        pod = self._call(*args, timeout=960)
        pod = pod.get("pod", pod) if isinstance(pod, dict) else {}
        if not pod.get("id"):
            raise LiumError("up: no pod id in the reply")
        return pod["id"]

    def terminate(self, instance_id):
        self._call("rm", str(instance_id), "--yes", "--name-only", "--format", "json")

    def restart(self, instance_id):
        # Lambda's restart is for the driver step of a VM; a Lium pod has no driver step
        raise LiumError("restart: not available for a Lium pod")


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
    """``(waiting_to_build or None, boxes, waiting_to_grade or None)`` read on the door (`DOOR_PROBE`, the public
    queue)."""
    probe = _door(
        config,
        ["python3", "-I", "-", config.door_host_root, config.boxes_dir],
        stdin=DOOR_PROBE.encode(),
    )
    boxes = json.loads(probe.stdout)["boxes"] if probe.returncode == 0 else None
    queue = _door(config, ["curl", "-sf", "--max-time", "20", config.door_queue_url])
    try:
        public = json.loads(queue.stdout)
    except (ValueError, TypeError):
        public = None

    def count(key):
        try:
            return int(public[key])
        except (KeyError, TypeError, ValueError):
            return None

    waiting = count("waiting_to_build")
    if type(public) is dict and public.get("door_state") == "draining":
        # a draining door builds nothing new: as unreadable (no idle clock, no drain, release or rent)
        waiting = None
    return waiting, boxes, count("waiting_to_grade")


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


def _forget_box_ssh(config, name):
    """The released box's ssh files on the door (``gpu_box_up``'s watchdog link) go with it. A failure is logged, not
    retried: a stale block is harmless (its own pinned key refuses any other host) and the next bring-up on a recycled
    address replaces it."""
    if not config.door_ssh_boxes_dir:
        return
    base = f"{config.door_ssh_boxes_dir}/{name}"
    if DRY[0]:
        log(config, action="would_remove_box_ssh", box=name)
        return
    try:
        ok = (
            _door(
                config, ["rm", "-f", f"{base}.conf", f"{base}.known_hosts"]
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        ok = False
    log(config, action="box_ssh_removed", box=name, ok=ok)


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
    _forget_box_ssh(config, name)
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
    waiting, boxes, grading = (door or read_door)(config)
    state["samples"] = (
        state["samples"] + [{"t": now, "waiting": waiting, "grade": grading}]
    )[-KEEP_SAMPLES:]
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
            _forget_box_ssh(config, name)
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
    over = over_day_budget(state, now, config)
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
                    ("day_cap" if at_day_cap else "day_budget")
                    if name in over
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
                and name not in over
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
    if why is None and grade_bound(state["samples"], now) and not bringing:
        # builds wait, but grading is the limit: a box would only move tasks into the grade queue (owner, 19 Nov)
        log(config, action="grade_bound", waiting=waiting, grading=grading)
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
        elif (
            spent + day_reserve(state, now) + offer[0] * RENT_MIN_H
            > config.max_usd_per_day
        ):
            # the boxes up keep running to 00:00Z; a new one needs its bring-up and some builds on top
            log(
                config,
                action="at_day_cap",
                waiting=waiting,
                rule=why,
                spent_usd=round(spent, 2),
                reserve_usd=round(day_reserve(state, now), 2),
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
                    "waiting_to_grade": grading,
                    "boxes_up": up,
                    "want_box": why,
                    "idle_box_up": idle_box,
                    "spent_today_usd": round(spent, 2),
                    "max_usd_per_day": config.max_usd_per_day,
                    "day_reserve_usd": round(day_reserve(state, now), 2),
                    "over_day_budget": sorted(over),
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
    _, boxes, _ = (door or read_door)(config)
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
            # the name right after the command: argparse refuses a "?" positional after an option ("unrecognized
            # arguments: <name>"), which left every rented box un-brought-up until the timeout (19 Nov 2026, 11:55Z)
            "bring-up",
            name,
            "--config",
            CONFIG_PATH[0],
        ],
        check=False,
    )


CONFIG_PATH = [""]


# -- bring-up (detached) ----------------------------------------------------------------------------------------------


def _fingerprint(line):
    """The SHA256 fingerprint (``ssh-keygen -l`` form) of an ed25519 key line: an ``ssh-keyscan`` line ``<host>
    ssh-ed25519 <base64>`` or a bare ``ssh-ed25519 <base64>``. The key is the field AFTER the type: reading field 1 of
    a keyscan line decoded the type name and crashed every bring-up 5 min in (``Incorrect padding``), so all three
    rents of 19-20 Nov timed out and were released while builds waited (20 Nov 2026, 02:1xZ).
    """
    fields = line.split()
    blob = base64.b64decode(fields[fields.index("ssh-ed25519") + 1])
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


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("tick", "bring-up", "status", "adopt"))
    parser.add_argument("name", nargs="?")
    parser.add_argument("--config", required=True)
    parser.add_argument("--ip", help="adopt: the box's address")
    parser.add_argument(
        "--dry-run", action="store_true", help="tick/adopt: print, change nothing"
    )
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
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
