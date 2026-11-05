#!/usr/bin/env python3
"""Drain ONE door before a code switch, without holding it (MAINNET_UPDATE_ARCHITECTURE s2.4 Step A).

    python3 -I -B scripts/dev/release/door_drain.py start  STATE_DIR
    python3 -I -B scripts/dev/release/door_drain.py status STATE_DIR
    python3 -I -B scripts/dev/release/door_drain.py wait   STATE_DIR --timeout SECONDS
    python3 -I -B scripts/dev/release/door_drain.py clear  STATE_DIR

``start`` writes the door's DRAINING flag (``STATE_DIR/draining``). The receiver keeps serving every route and
keeps admitting submissions; it starts no new construction or grade round (`direct_intake._WorkLock` reads the flag
before every attempt), and lets the one it is running finish on its own code.

``status``/``wait`` read THIS door's in-flight record (``work-inflight.json``), never the host's grading lock:
another door grading is not this door being busy (the 4 Nov lesson: Burst Thermal waited > 1 h for a host-wide idle
while Motor graded). The door is IDLE when DRAINING is set and, read twice ``READ_GAP_S`` apart, it has no in-flight
record held by a live process (pid + process start time; a record whose process is gone is stale, never busy).

``wait`` returns IDLE (exit 0) or, at its timeout, TIMED_OUT (exit 3) leaving DRAINING set; the caller decides to
``clear`` (abort the switch: the door takes work again, nothing was stopped or lost) or wait longer. A door still
having worker containers is the caller's second check (``docker ps`` by the door's names), not done here.

Writes only the flag file (atomically, owner-only). Never touches a lock, a task, a marker or a store.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

DRAIN_NAME = "draining"
INFLIGHT_NAME = "work-inflight.json"
WAIT_NAME = "work-wait.json"
READ_GAP_S = 2.0
POLL_S = 5.0


def _process_start(pid):
    try:
        with open(f"/proc/{pid}/stat", "rb") as handle:
            return int(handle.read().rsplit(b")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _state(state_dir) -> Path:
    path = Path(state_dir)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise SystemExit(json.dumps({"state": "REFUSED", "code": "state_dir_invalid"}))
    return path


def start(state_dir) -> dict:
    root = _state(state_dir)
    flag = root / DRAIN_NAME
    if not flag.exists():
        staged = root / f".{DRAIN_NAME}.{os.getpid()}"
        with open(staged, "w", encoding="utf-8") as handle:
            json.dump({"since_ns": time.time_ns()}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(staged, 0o600)
        os.replace(staged, flag)
    return {"state": "DRAINING", **read_once(root)}


def clear(state_dir) -> dict:
    root = _state(state_dir)
    (root / DRAIN_NAME).unlink(missing_ok=True)
    return {"state": "NOT_DRAINING"}


def read_once(root: Path) -> dict:
    """``busy`` is True only for an in-flight record whose process (pid + start) is alive now."""
    draining = (root / DRAIN_NAME).exists()
    record = None
    try:
        record = json.loads((root / INFLIGHT_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        # Unreadable or mid-replace: count as busy, read again later (never idle on doubt).
        return {"draining": draining, "busy": True, "inflight": "UNREADABLE"}
    busy = False
    if type(record) is dict:
        pid, started = record.get("pid"), record.get("pid_start")
        alive = type(pid) is int and _process_start(pid) is not None
        busy = alive and (started is None or _process_start(pid) == started)
    waiting = (root / WAIT_NAME).exists()
    return {
        "draining": draining,
        "busy": busy,
        "inflight": (
            None
            if record is None
            else {"kind": record.get("kind"), "since_ns": record.get("since_ns")}
        ),
        "stale_record": record is not None and not busy,
        "waiting_for_host": waiting,
    }


def status(state_dir, *, gap=READ_GAP_S, sleep=time.sleep) -> dict:
    root = _state(state_dir)
    first = read_once(root)
    sleep(gap)
    second = read_once(root)
    idle = (
        first["draining"]
        and second["draining"]
        and not first["busy"]
        and not second["busy"]
    )
    return {
        "state": "IDLE" if idle else ("BUSY" if second["draining"] else "NOT_DRAINING"),
        "read": second,
    }


def wait(
    state_dir,
    timeout,
    *,
    gap=READ_GAP_S,
    poll=POLL_S,
    sleep=time.sleep,
    clock=time.monotonic,
) -> dict:
    root = _state(state_dir)
    if not (root / DRAIN_NAME).exists():
        return {"state": "NOT_DRAINING"}
    started = clock()
    while True:
        result = status(root, gap=gap, sleep=sleep)
        if result["state"] != "BUSY":
            result["waited_s"] = round(clock() - started, 3)
            return result
        if clock() - started >= timeout:
            return {
                "state": "TIMED_OUT",
                "waited_s": round(clock() - started, 3),
                "read": result["read"],
            }
        sleep(poll)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="door_drain.py")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "status", "clear"):
        sub.add_parser(name).add_argument("state_dir", type=Path)
    w = sub.add_parser("wait")
    w.add_argument("state_dir", type=Path)
    w.add_argument("--timeout", type=float, required=True)
    args = parser.parse_args(argv)
    if args.command == "start":
        result = start(args.state_dir)
    elif args.command == "clear":
        result = clear(args.state_dir)
    elif args.command == "status":
        result = status(args.state_dir)
    else:
        result = wait(args.state_dir, args.timeout)
    print(json.dumps(result, sort_keys=True))
    return {"IDLE": 0, "TIMED_OUT": 3}.get(
        result["state"], 0 if args.command != "wait" else 4
    )


if __name__ == "__main__":
    sys.exit(main())
