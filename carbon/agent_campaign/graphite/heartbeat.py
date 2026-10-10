"""GRAPHITE-LAUNCH-PREFLIGHT-01: a live Graphite run's heartbeat and its stall rule.

A live run writes `heartbeat.json` (`carbon.graphite.heartbeat.v1`) every
`INTERVAL_S` while it runs, read from the run's own files only:

- `alive` and `phase`: the run's state (`state.json`);
- `last_agent_call_at` and `last_event`: the newest research-loop event
  (`events.jsonl`);
- `pods`: launched, refused and settled, and `booked_usd`, the run's
  committed pod money (`experiment/pod-ledger.jsonl`);
- `last_error`: the state's recorded failure code, if any.

It is written beside the run, and also to `$CARBON_GRAPHITE_HEARTBEAT_DIR`
(`<run id>.json`) when that is set, so one shared directory shows every live
run. No key, prompt, recipe or hidden material is in it.

**Stall rule** (`status`): STALLED when the heartbeat is more than
`STALL_S` (15 minutes) old while the run is alive, or when every pod launch
so far was refused. Otherwise ALIVE, or FINISHED once the run is terminal.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
from pathlib import Path

SCHEMA = "carbon.graphite.heartbeat.v1"
NAME = "heartbeat.json"
SHARED_DIR_ENV = "CARBON_GRAPHITE_HEARTBEAT_DIR"
INTERVAL_S = 120
STALL_S = 15 * 60
TERMINAL = ("succeeded", "failed", "cancelled")
ALIVE, STALLED, FINISHED = "ALIVE", "STALLED", "FINISHED"


def _json(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        return None


def _last_event(run_dir):
    path = Path(run_dir) / "events.jsonl"
    try:
        lines = path.read_bytes().splitlines()
        mtime = path.stat().st_mtime
    except OSError:
        return None, None
    for line in reversed(lines):
        try:
            return mtime, json.loads(line).get("kind")
        except ValueError:
            continue
    return mtime, None


def _pods(run_dir, clock):
    from .experiment import PodLedger

    ledger = PodLedger(Path(run_dir) / "experiment" / "pod-ledger.jsonl", clock)
    try:
        pods = list(ledger.pods().values())
        settled, pending = ledger.committed()
    except (OSError, ValueError, KeyError):
        return {"launched": 0, "refused": 0, "settled": 0}, None
    return (
        {
            "launched": sum(1 for p in pods if p["launch"] == "created"),
            "refused": sum(1 for p in pods if p["launch"] == "refused"),
            "settled": sum(1 for p in pods if p["settled_usd"] is not None),
        },
        str(settled + pending),
    )


def snapshot(run_dir, run_id, *, clock=time.time):
    """The heartbeat document for the run in `run_dir`, now."""
    state = _json(Path(run_dir) / "state.json") or {}
    phase = state.get("state")
    last_at, last_event = _last_event(run_dir)
    pods, booked = _pods(run_dir, clock)
    failure = state.get("failure") if isinstance(state.get("failure"), dict) else {}
    return {
        "schema": SCHEMA,
        "run_id": run_id,
        "written_at": clock(),
        "alive": phase not in TERMINAL,
        "phase": phase,
        "last_agent_call_at": last_at,
        "last_event": last_event,
        "pods": pods,
        "booked_usd": booked,
        "last_error": failure.get("code"),
    }


def status(document, *, now=None, clock=time.time):
    """`(status, reason)` for a heartbeat document read at `now`."""
    now = clock() if now is None else now
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        return STALLED, "no readable heartbeat"
    if not document.get("alive"):
        return FINISHED, document.get("phase")
    pods = document.get("pods") or {}
    if pods.get("refused", 0) > 0 and pods.get("launched", 0) == 0:
        return STALLED, f"every pod launch was refused ({pods['refused']})"
    age = now - float(document.get("written_at") or 0)
    if age > STALL_S:
        return STALLED, f"no heartbeat for {int(age)} s"
    return ALIVE, None


def _write(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(document, sort_keys=True, indent=1))
    temporary.chmod(0o644)
    os.replace(temporary, path)


def write(run_dir, run_id, *, clock=time.time, environ=os.environ):
    """Write the heartbeat beside the run and, when set, to the shared
    directory. Returns the document, with its stall status."""
    document = snapshot(run_dir, run_id, clock=clock)
    document["status"], document["status_reason"] = status(
        document, now=document["written_at"]
    )
    _write(Path(run_dir) / NAME, document)
    shared = environ.get(SHARED_DIR_ENV)
    if shared:
        _write(Path(shared) / (run_id + ".json"), document)
    return document


def read(path, *, now=None, clock=time.time):
    """A heartbeat file as a reader sees it: the document with its status
    recomputed at `now` (an old file reads STALLED)."""
    document = _json(path) or {}
    document["status"], document["status_reason"] = status(
        document, now=now, clock=clock
    )
    return document


@contextlib.contextmanager
def beating(run_dir, run_id, *, interval=INTERVAL_S, clock=time.time):
    """Write the heartbeat every `interval` seconds while the block runs, and
    once more when it ends. A heartbeat failure never stops the run."""
    stop = threading.Event()

    def beat():
        while True:
            with contextlib.suppress(OSError):
                write(run_dir, run_id, clock=clock)
            if stop.wait(interval):
                return

    thread = threading.Thread(target=beat, name="graphite-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=10)
        with contextlib.suppress(OSError):
            write(run_dir, run_id, clock=clock)
