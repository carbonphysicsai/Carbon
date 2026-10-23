"""The backbone catalog installed in the background, with progress the page
shows (M1 E2E E2).

A newcomer's first practice waited about 40 minutes for a separate
`python -m scripts.dev.catalog_install` they had to know to run. Now it is
started for them, in the background, and runs once:
- by the installer, after an update whose runner profile it rewrote, when
  entries are missing for the current construction parents (R7-1);
- by the Control Center page, once Review writes the runner profile there,
  and on the page's own one-click retry (`POST /api/v1/page/catalog_install`).
Never from an MCP tool or a setup operation: the catalog installer is
owner-run (`scripts/dev/catalog_install.py`), and no miner path imports it;
this module only starts it as a separate process.

**One at a time.** The job holds an exclusive lock on `catalog-build.lock`
in setup's owner-only directory while it runs, so a second start, from the
page or the installer, reports the running one instead. Its output goes to
an owner-only `catalog-build.log`; `catalog-build.json` records when it
started and how it ended.

**Progress** is read from the files practice itself resolves
(`catalog_state.progress`): how many entries are installed for the current
parents, per Challenge version. A Challenge version practises a catalog
backbone as soon as that entry is installed, before the rest finish.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "carbon.launchpad.catalog-build.v1"
RECORD = "catalog-build.json"
LOG = "catalog-build.log"
LOCK = "catalog-build.lock"
#: What a newcomer is told up front: the one measurement there is, the full
#: catalog on Carbon's test machine (M1 E2E round 6, 2026-10-22).
DURATION = (
    "about 40 minutes for the whole catalog on Carbon's test machine; each "
    "Challenge can practise a catalog backbone as soon as its entry is ready"
)
REPOSITORY = Path(__file__).resolve().parents[3]


def _setup_dir(state_dir) -> Path:
    return Path(state_dir) / "environment"


def _profile(state_dir) -> dict | None:
    try:
        cfg = json.loads((_setup_dir(state_dir) / "runner-profile.json").read_bytes())
    except (OSError, ValueError):
        return None
    return cfg if type(cfg) is dict else None


def _lock(root: Path):
    """The job lock's descriptor, held; None when a running job holds it."""
    import fcntl

    from scripts.dev.miner_launchpad.environment_setup import _private_dir

    _private_dir(root)
    fd = os.open(
        root / LOCK, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    except BaseException:
        os.close(fd)
        raise
    return fd


def running(state_dir) -> bool:
    root = _setup_dir(state_dir)
    if not (root / LOCK).exists():
        return False
    fd = _lock(root)
    if fd is None:
        return True
    os.close(fd)
    return False


def _record(state_dir) -> dict | None:
    try:
        value = json.loads((_setup_dir(state_dir) / RECORD).read_bytes())
    except (OSError, ValueError):
        return None
    return value if type(value) is dict else None


def _save(state_dir, record) -> None:
    from scripts.dev.miner_launchpad.environment_setup import write_private

    write_private(
        _setup_dir(state_dir) / RECORD, json.dumps(record, sort_keys=True).encode()
    )


def status(state_dir, clock=time.time) -> dict:
    """Where the catalog stands for this install: {state, installed, total,
    challenges, started_at, ended_at, exit_code, estimate_seconds, duration,
    log}. `state` is NO_PROFILE (Review first), RUNNING, COMPLETE,
    INCOMPLETE (not running, entries missing: start it again) or STOPPED
    (it ended with an error; its log says why)."""
    from scripts.dev.miner_launchpad import catalog_state

    cfg = _profile(state_dir)
    record = _record(state_dir) or {}
    found = catalog_state.progress(cfg) if cfg is not None else None
    found = found or {"total": 0, "installed": 0, "challenges": []}
    active = running(state_dir)
    if cfg is None:
        state = "NO_PROFILE"
    elif active:
        state = "RUNNING"
    elif found["installed"] >= found["total"]:
        state = "COMPLETE"
    elif record.get("exit_code") not in (None, 0):
        state = "STOPPED"
    else:
        state = "INCOMPLETE"
    estimate = None
    started, before = record.get("started_at"), record.get("installed_at_start")
    if active and type(started) in (int, float) and type(before) is int:
        made = found["installed"] - before
        if made > 0:
            per = (clock() - started) / made
            estimate = int(per * (found["total"] - found["installed"]))
    note = None
    if state == "INCOMPLETE" and record.get("exit_code") == 0:
        # It ran to the end and skipped some: an entry with pinned wheels
        # needs the wheelhouse first (`catalog_install`'s own message).
        note = (
            "some entries were skipped; its log names why (an entry with "
            "pinned wheels needs python -m scripts.dev.catalog_wheelhouse first)"
        )
    return {
        "schema": SCHEMA,
        "state": state,
        "note": note,
        "installed": found["installed"],
        "total": found["total"],
        "challenges": found["challenges"],
        "started_at": started,
        "ended_at": record.get("ended_at"),
        "exit_code": record.get("exit_code"),
        # Measured as it runs, once an entry has finished; None before.
        "estimate_seconds": estimate,
        "duration": DURATION,
        "log": str(_setup_dir(state_dir) / LOG),
    }


def start(state_dir, *, python=sys.executable, spawn=subprocess.Popen) -> dict:
    """Start the job in the background unless it runs or nothing is missing;
    the status either way. Needs the runner profile Review writes."""
    if _profile(state_dir) is None:
        return status(state_dir)
    if running(state_dir):
        return status(state_dir)
    now = status(state_dir)
    if now["installed"] >= now["total"]:
        return now  # nothing missing, or nothing this install serves
    root = _setup_dir(state_dir)
    log = os.open(
        root / LOG,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        spawn(
            [
                python,
                "-B",
                "-m",
                "scripts.dev.miner_launchpad.catalog_build",
                "run",
                "--state-dir",
                str(state_dir),
            ],
            cwd=str(REPOSITORY),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            # Its own session: closing the page or the installer's terminal
            # does not stop it half way.
            start_new_session=True,
        )
    finally:
        os.close(log)
    return {**now, "state": "RUNNING"}


def run(state_dir, *, install=None, clock=time.time) -> int:
    """The job itself: hold the lock, install every entry, record the end."""
    root = _setup_dir(state_dir)
    fd = _lock(root)
    if fd is None:
        return 0  # another job is installing it
    try:
        before = status(state_dir)["installed"]
        _save(state_dir, {"started_at": clock(), "installed_at_start": before})
        if install is None:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "scripts.dev.catalog_install",
                    "--state-dir",
                    str(state_dir),
                ],
                cwd=str(REPOSITORY),
                check=False,
            )
            code = completed.returncode
        else:
            code = install(state_dir)
        record = _record(state_dir) or {}
        _save(state_dir, {**record, "ended_at": clock(), "exit_code": code})
        return code
    finally:
        os.close(fd)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("start", "run", "status"))
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        return run(args.state_dir)
    result = (
        start(args.state_dir) if args.command == "start" else status(args.state_dir)
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
