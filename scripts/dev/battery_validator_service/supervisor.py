"""Supervise the intake and the validator daemon, or write systemd units for them.

`supervise` is for an operator host without systemd (a WSL distribution
without it enabled, for one). It takes the service's lock (one supervisor per
service), refuses to start unless the preflight is ready, and runs two
children from the repository root:

- `intake`: `python -m carbon.battery.intake serve --config <intake>`;
- `daemon`: `python -m carbon.battery.operate run --config <deployment>
  --every <run_every_s>`.

Restart policy, the same as the systemd units':
- a child that exits 2 refused its configuration. Restarting would only
  repeat the refusal, so the supervisor stops both and exits 2;
- any other exit is restarted after a backoff that doubles from 1 s up to
  60 s and resets once the child has run for 10 minutes;
- more than 5 restarts of one child within 10 minutes stops both, exit 1
  (`restart_limit`): something needs the operator.

SIGTERM or SIGINT stops both children (SIGTERM, then SIGKILL after the grace
period) and exits 0.

Logs are structured and owner-only under `<state_dir>/logs/`: the
supervisor's own events as JSON lines in `supervisor.jsonl`, and each child's
output (its own JSON lines) appended to `<child>.log`. The current state of
every child is `<state_dir>/supervisor-state.json`, read by `status`.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .service import (
    REPOSITORY,
    ServiceRefused,
    _intake,
    load_service,
    owner_only_directory,
    running,
)

STATE_SCHEMA = "carbon.battery.validator-supervisor.v1"
#: Engineering bounds, not scientific values.
BACKOFF_MIN_S, BACKOFF_MAX_S = 1.0, 60.0
STABLE_S = 600.0
RESTART_BURST, RESTART_WINDOW_S = 5, 600.0
STOP_GRACE_S = 45.0
REFUSED_EXIT = 2


def children(service, *, repository=REPOSITORY, python=None):
    """`{name: argv}` for the two supervised processes."""
    python = python or sys.executable
    intake_config = _intake(service, repository)
    return {
        "intake": [
            python,
            "-m",
            "carbon.battery.intake",
            "serve",
            "--config",
            str(service.intake_path),
        ],
        "daemon": [
            python,
            "-m",
            "carbon.battery.operate",
            "run",
            "--config",
            str(intake_config["deployment"]),
            "--every",
            repr(service.run_every_s),
        ],
    }


def _utc(at=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(at))


class Log:
    """The supervisor's JSON-lines log and its children's log files."""

    def __init__(self, service):
        self.folder = owner_only_directory(service.state_dir / "logs", create=True)
        self.path = self.folder / "supervisor.jsonl"

    def event(self, event, **fields):
        line = json.dumps(
            {"ts": _utc(), "service": "battery-validator-supervisor", "event": event}
            | fields,
            sort_keys=True,
        )
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as handle:
            handle.write(line + "\n")

    def child(self, name):
        fd = os.open(
            self.folder / (name + ".log"), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600
        )
        return os.fdopen(fd, "ab")


def _write_state(service, state):
    path = service.state_dir / "supervisor-state.json"
    partial = path.with_name(path.name + ".partial")
    fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(state, handle, sort_keys=True, indent=2)
    os.replace(partial, path)


def read_state(service):
    """The supervisor's last written state, or `not_running` when no
    supervisor holds the service's lock (a stale file is reported so)."""
    path = service.state_dir / "supervisor-state.json"
    if not running(service):
        return {"state": "not_running"}
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError):
        return {"state": "starting"}


class Child:
    """One supervised process and its restart accounting."""

    def __init__(self, name, argv):
        self.name, self.argv = name, argv
        self.process = None
        self.started = None
        self.restarts = []  # monotonic times
        self.backoff = BACKOFF_MIN_S
        self.due = 0.0
        self.last_exit = None

    def view(self):
        if self.process is None:
            state = "waiting"  # exited, its restart due
        else:
            state = "running" if self.process.poll() is None else "stopped"
        return {
            "state": state,
            "pid": self.process.pid if state == "running" else None,
            "restarts": len(self.restarts),
            "last_exit": self.last_exit,
        }


def supervise(
    path,
    *,
    repository=REPOSITORY,
    stop=None,
    preflight=None,
    commands=None,
    clock=time.monotonic,
    poll_s=0.5,
):
    """Run the service's two children until `stop`, a refusal or the restart
    limit. Returns the exit code: 0 stopped, 1 restart limit, 2 refused."""
    from .service import preflight as default_preflight

    service = load_service(path)
    owner_only_directory(service.state_dir, create=True)
    lock_fd = os.open(
        service.state_dir / "supervisor.lock", os.O_RDWR | os.O_CREAT, 0o600
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        raise ServiceRefused("supervisor_already_running") from None
    stop = threading.Event() if stop is None else stop
    log = Log(service)
    try:
        report = (preflight or default_preflight)(path, repository=repository)
        if not report["ready"]:
            refused = [c for c in report["checks"] if c["status"] == "refused"]
            log.event("preflight_refused", codes=[c["refused"] for c in refused])
            raise ServiceRefused(
                "preflight_not_ready", codes=[c["refused"] for c in refused]
            )
        argv = commands or children(service, repository=repository)
        kids = [Child(name, command) for name, command in argv.items()]
        log.event("started", children=sorted(argv))
        return _loop(service, kids, log, stop, clock, poll_s, repository)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _start(child, log, repository, clock):
    output = log.child(child.name)
    try:
        child.process = subprocess.Popen(
            child.argv,
            cwd=repository,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=output,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            start_new_session=True,
        )
    finally:
        output.close()
    child.started = clock()
    log.event("child_started", child=child.name, pid=child.process.pid)


def _stop_all(kids, log):
    for child in kids:
        if child.process is not None and child.process.poll() is None:
            child.process.send_signal(signal.SIGTERM)
    deadline = time.monotonic() + STOP_GRACE_S
    for child in kids:
        if child.process is None:
            continue
        try:
            child.process.wait(max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            child.process.kill()
            child.process.wait()
            log.event("child_killed", child=child.name)


def _loop(service, kids, log, stop, clock, poll_s, repository):
    def save(state):
        _write_state(
            service,
            {
                "schema": STATE_SCHEMA,
                "state": state,
                "pid": os.getpid(),
                "updated_utc": _utc(),
                "children": {child.name: child.view() for child in kids},
            },
        )

    for child in kids:
        _start(child, log, repository, clock)
    save("running")
    code = 0
    try:
        while not stop.is_set():
            for child in kids:
                if child.process is None:
                    if clock() >= child.due:
                        _start(child, log, repository, clock)
                        save("running")
                    continue
                exit_code = child.process.poll()
                if exit_code is None:
                    if clock() - child.started >= STABLE_S:
                        child.backoff = BACKOFF_MIN_S
                    continue
                child.last_exit, child.process = exit_code, None
                if exit_code == REFUSED_EXIT:
                    log.event("child_refused", child=child.name, exit=exit_code)
                    code = REFUSED_EXIT
                    return code
                now = clock()
                child.restarts = [
                    t for t in child.restarts if now - t < RESTART_WINDOW_S
                ]
                if len(child.restarts) >= RESTART_BURST:
                    log.event("restart_limit", child=child.name, exit=exit_code)
                    code = 1
                    return code
                child.restarts.append(now)
                child.due = now + child.backoff
                log.event(
                    "child_exited",
                    child=child.name,
                    exit=exit_code,
                    restart_in_s=child.backoff,
                )
                child.backoff = min(BACKOFF_MAX_S, child.backoff * 2)
                save("running")
            stop.wait(poll_s)
        log.event("stopping")
        return code
    finally:
        _stop_all(kids, log)
        save({0: "stopped", 1: "restart_limit", REFUSED_EXIT: "refused"}[code])
        log.event("stopped", code=code)


# --- systemd --------------------------------------------------------------------

UNIT = """\
[Unit]
Description={description}
After=network-online.target
StartLimitIntervalSec={window}
StartLimitBurst={burst}

[Service]
Type=simple
WorkingDirectory={repository}
Environment=PYTHONUNBUFFERED=1
ExecStartPre={python} -m scripts.dev.battery_validator_service preflight --config {service}
ExecStart={command}
Restart=on-failure
RestartSec={backoff}
RestartPreventExitStatus={refused}
TimeoutStopSec={grace}
UMask=0077
NoNewPrivileges=yes

[Install]
WantedBy=default.target
"""

UNIT_NAMES = {
    "intake": (
        "carbon-battery-intake.service",
        "Carbon battery validator intake (OD-7(b), DEVELOPMENT evidence)",
    ),
    "daemon": (
        "carbon-battery-validator.service",
        "Carbon battery validator daemon (DEVELOPMENT evidence, no weights)",
    ),
}


def units(path, out, *, repository=REPOSITORY, python=None):
    """Write `systemd --user` units for the two children into `out`.

    Writes files only, owner-only, never over an existing one; installing and
    enabling them is the operator's step (`systemctl --user`).
    """
    import shlex

    service = load_service(path)
    python = python or sys.executable
    out = owner_only_directory(out, create=True)
    if any((Path(out) / unit).exists() for unit, _ in UNIT_NAMES.values()):
        raise ServiceRefused(
            "unit_exists", next_step="remove or move the existing units first"
        )
    written = []
    for name, argv in children(service, repository=repository, python=python).items():
        unit, description = UNIT_NAMES[name]
        body = UNIT.format(
            description=description,
            window=int(RESTART_WINDOW_S),
            burst=RESTART_BURST,
            repository=repository,
            python=shlex.quote(python),
            service=shlex.quote(str(service.path)),
            command=shlex.join(argv),
            backoff=int(BACKOFF_MIN_S * 5),
            refused=REFUSED_EXIT,
            grace=int(STOP_GRACE_S),
        )
        target = Path(out) / unit
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(body)
        written.append(str(target))
    return {
        "units": written,
        "next_steps": [
            "copy the units to ~/.config/systemd/user/",
            "systemctl --user daemon-reload",
            "systemctl --user enable --now "
            + " ".join(unit for unit, _ in UNIT_NAMES.values()),
        ],
    }
