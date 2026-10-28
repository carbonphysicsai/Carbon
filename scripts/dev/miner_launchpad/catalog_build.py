"""The backbone catalog installed in the background, with progress the page
shows (M1 E2E E2).

A newcomer's first practice waited about 40 minutes for a separate
`python -m scripts.dev.catalog_install` they had to know to run. Now it is
started for them, in the background, and runs once:
- by the installer, after an update whose runner profile it rewrote, when
  entries are missing for the current construction parents (R7-1);
- by the shared setup operation, once a confirmed Review or recheck leaves
  a usable runner profile, through either MCP or the Control Center page;
- on the page's own one-click retry (`POST /api/v1/page/catalog_install`).
The catalog installer is owner-run (`scripts/dev/catalog_install.py`), and
no miner path imports it; this module only starts it as a separate process.
Reading status or choosing compute does not start an install.

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
#: What `catalog_install --report` wrote: the entries it skipped and why.
REPORT = "catalog-build-report.json"
#: Each skipped entry's reason, in words, and the one next step.
SKIP_WORDS = {
    "wheel_missing": "its pinned wheel {wheel} could not be fetched",
    "wheelhouse_missing": "its pinned wheels could not be fetched",
    "install_failed": "its install failed ({detail})",
}
SKIP_NEXT = (
    "If this machine is offline, connect it, then install the catalog again "
    "(the page's button, or this job again): it fetches the missing wheels "
    "first and installs only what is missing. An install that failed is "
    "explained in its log."
)
LOCK = "catalog-build.lock"
#: What a newcomer is told up front: the one measurement there is, the full
#: catalog on Carbon's test machine (M1 E2E round 6, 2026-10-22).
DURATION = (
    "about 40 minutes for the whole catalog on Carbon's test machine; each "
    "Challenge can practise a catalog backbone as soon as its entry is ready"
)
REPOSITORY = Path(__file__).resolve().parents[3]


def start_or_status(state_dir) -> dict:
    """Try the maintained background start; a launch failure keeps setup saved.

    Status remains measured from the job and catalog. It never reports a
    successful start solely because Review persisted the profile.
    """
    try:
        return start(state_dir)
    except (OSError, ValueError):
        return status(state_dir)


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
    skipped = [
        {
            "catalog_id": str(item.get("catalog_id")),
            "reason": str(item.get("reason")),
            "words": str(item.get("catalog_id"))
            + ": "
            + SKIP_WORDS.get(str(item.get("reason")), "it was skipped").format(
                wheel=item.get("wheel", "?"), detail=item.get("detail", "see its log")
            ),
        }
        for item in (record.get("skipped") or [])
        if type(item) is dict
    ]
    note = None
    if state == "INCOMPLETE" and skipped:
        note = (
            "Installed every entry it could; not installed: "
            + "; ".join(item["words"] for item in skipped)
            + ". "
            + SKIP_NEXT
        )
    elif state == "STOPPED":
        note = (
            "It stopped with an error before finishing; its log says why. "
            "Install the catalog again to continue where it stopped."
        )
    if record.get("wheels") == "unavailable" and state != "COMPLETE":
        note = (note + " " if note else "") + (
            "The catalog's pinned wheels could not be fetched this time."
        )
    return {
        "schema": SCHEMA,
        "state": state,
        "note": note,
        # The entries the last run skipped, each with its reason code and
        # the same in words (M1 E2E R10-1).
        "skipped": skipped,
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


def stage_twins(
    state_dir, gpu_runtimes, *, python=sys.executable, spawn=subprocess.Popen
):
    """Stage the catalog's GPU twins' material in the background for the
    GPU workers setup has just added (`gpu_runtimes`, the runtimes they
    serve), so practice's GPU build finds it (M1 E2E S4: only the CPU build
    was staged). Inert: `catalog_install --gpu-twins-only` copies pinned
    bytes and wheels already in the host's wheelhouse; it builds, fetches
    and runs nothing. Needs no runner profile (setup's compute check comes
    before Review). Returns whether it started."""
    if not gpu_runtimes:
        return False
    root = _setup_dir(state_dir)
    from scripts.dev.miner_launchpad.environment_setup import _private_dir

    _private_dir(root)
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
                "scripts.dev.catalog_install",
                "--state-dir",
                str(state_dir),
                "--gpu-twins-only",
            ],
            cwd=str(REPOSITORY),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            start_new_session=True,
        )
    finally:
        os.close(log)
    return True


def _fetch_wheels(state_dir) -> bool:
    """The catalog's pinned wheels, fetched into the host's wheelhouse by
    exact name and version and kept only with their pinned sha256
    (`scripts.dev.catalog_wheelhouse`); a wheelhouse built for an earlier
    catalog is brought up to date. False, with one plain line, when they
    cannot be (offline, or a file differs from its pin): the entries that
    need them are then skipped and the rest install (M1 E2E R10-1)."""
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "scripts.dev.catalog_wheelhouse"],
        cwd=str(REPOSITORY),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return True
    reason = (completed.stderr.strip().splitlines() or ["no reason given"])[-1]
    print(
        "Could not fetch the catalog's pinned wheels (" + reason[:200] + "); "
        "the entries that need them are skipped and the rest install.",
        flush=True,
    )
    return False


def _install(state_dir) -> int:
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "scripts.dev.catalog_install",
            "--state-dir",
            str(state_dir),
            "--report",
            str(_setup_dir(state_dir) / REPORT),
        ],
        cwd=str(REPOSITORY),
        check=False,
    ).returncode


def run(state_dir, *, install=_install, fetch=_fetch_wheels, clock=time.time) -> int:
    """The job itself: hold the lock, fetch the pinned wheels, install every
    entry it can, and record how it ended and what it skipped."""
    root = _setup_dir(state_dir)
    fd = _lock(root)
    if fd is None:
        return 0  # another job is installing it
    try:
        before = status(state_dir)["installed"]
        _save(state_dir, {"started_at": clock(), "installed_at_start": before})
        (root / REPORT).unlink(missing_ok=True)
        wheels = "fetched" if fetch(state_dir) else "unavailable"
        code = install(state_dir)
        try:
            report = json.loads((root / REPORT).read_bytes())
        except (OSError, ValueError):
            report = {}
        skipped = report.get("skipped") if type(report) is dict else None
        record = _record(state_dir) or {}
        _save(
            state_dir,
            {
                **record,
                "ended_at": clock(),
                "exit_code": code,
                "wheels": wheels,
                "skipped": skipped if type(skipped) is list else [],
            },
        )
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
