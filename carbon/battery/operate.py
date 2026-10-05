"""The operator's commands for a battery validator deployment (M3).

    python -m carbon.battery.operate <command> --config DEPLOYMENT.json ...

Commands:
- ``init``: create the private root and commit it, with the seed pin, to the
  seed journal, once (an existing root and binding are kept);
- ``status``: identities, pool, incumbent and batch counts;
- ``batches``: each batch's kind, state and reference completion;
- ``recover``: settle what a crash left mid-way (never dispatches work);
- ``prepare``: generate, commit and record one private batch from the root;
- ``jobs``: write one batch's reference jobs to an owner-only file for the
  truth container (read-only on the validator);
- ``ingest``: ingest the truth container's records file for a batch;
- ``open``: open the pool once three screening batches are complete;
- ``run``: advance every queued submission and open finalist comparison.
  With ``--every SECONDS`` it is the long-lived validator daemon a service
  supervises (LP-PROD-G): one pass per period, each under the writer lock
  for its own duration only, one JSON line per pass, and SIGTERM ends it
  once the pass in flight returns (a supervisor that stops waiting first
  cuts the pass off, and its run is retried as infrastructure). With
  ``--heartbeat PATH`` it also keeps an owner-only heartbeat there, and
  holds ``PATH.lock`` while it lives, so a service's status and restore
  see it however it was started (`run_every`);
- ``upgrade``: carry the deployment over to this checkout's contract,
  recipe implementation and images in place (OWNER-BATTERY-CARRYOVER-01).
  The incumbent, retained models, scores and pool stay; a recipe admitted
  under an earlier contract is recompiled under the current one, and each
  recompile is recorded. A changed exam rule, public material or seed pin is
  refused: those still need a new deployment. The binding it writes is the
  one a writable start makes (`serving_identities`), pinned images included;
- ``truth-materialize`` / ``truth-verify``: build the PyBaMM overlay from its
  hash-locked wheels and verify the pinned version inside the pinned image,
  with no network (`truth_env`). The solve itself runs in that image
  (`truth_env.solve_command`) and refuses without the pinned version; it
  sees only the jobs and records files, never the validator state;
- ``export``: write service-key-signed outcomes and the Phase A all-burn
  weight intent for the owner publisher. It sends nothing anywhere.

Every output is operator-private: it goes to this terminal or an owner-only
file. Nothing here prints a key, a seed or the root; `batches` names roles
and fingerprints, never cases. Only `jobs` writes cases, to an owner-only
file for the truth container.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import stat
import sys
import threading
import time
from pathlib import Path

from .deployment import (
    EvaluationUnavailable,
    load_config,
    rule_for,
    validator,
    writer,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def _write_private(path, value):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")


def _batches(target):
    with target.store.db() as db:
        rows = db.execute(
            "SELECT fingerprint, kind, role, sequence, state, references_state"
            " FROM batches ORDER BY sequence"
        ).fetchall()
    return [
        dict(
            zip(
                ("fingerprint", "kind", "role", "sequence", "state", "references"),
                row,
                strict=True,
            )
        )
        for row in rows
    ]


def _jobs(target, fingerprint, out):
    """Write one batch's reference jobs for the truth container.

    The file holds private case ids and inputs: it is created owner-only and
    only the truth container reads it. The container never sees the
    validator state, the private root or the journal.
    """
    jobs = target.reference_jobs(fingerprint)
    _write_private(out, {"fingerprint": fingerprint, "jobs": jobs})
    return {"fingerprint": fingerprint, "jobs": len(jobs), "file": str(out)}


def _export(target, out):
    from .signing import all_burn_intent

    if target.service_key is None:
        raise SystemExit("export needs a service_key in the deployment")
    out = Path(out)
    out.mkdir(mode=0o700)
    with target.store.db() as db:
        ids = [r[0] for r in db.execute("SELECT submission_id FROM submissions")]
    for sid in ids:
        _write_private(out / (sid + ".json"), target.signed_outcome(sid))
    with target.store.db() as db:
        finals = [
            r[0]
            for r in db.execute("SELECT final_id FROM finals WHERE state='DECIDED'")
        ]
    for final_id in finals:
        _write_private(out / (final_id + ".json"), target.signed_final(final_id))
    pool = target.store.pool()
    intent = target.service_key.sign(
        "weight_intent",
        all_burn_intent(
            pool_version=None if pool is None else pool["version"],
            reason="Phase A: all emission burned (OD-4a)",
        ),
    )
    _write_private(out / "weight-intent.json", intent)
    return {
        "outcomes": len(ids),
        "finals": len(finals),
        "weight_intent": "ALL_BURN",
        "directory": str(out),
    }


def init(config_path, *, repository=REPOSITORY):
    """Create a deployment's private root and commit it to the seed journal,
    once. An existing valid root is kept; a journal already bound to this
    root is reported, never rewritten; a journal bound to another root is
    refused. Prints only public values: the root commitment and the pin."""
    from . import seeds
    from .daemon import rule_digest
    from .deployment import _owner_only_directory

    config = load_config(config_path)
    root_path = Path(config["private_root"])
    journal_path = Path(config["journal"])
    for parent in {root_path.parent, journal_path.parent}:
        _owner_only_directory(parent)
    journal = seeds.SeedJournal(journal_path)
    bound = any(e["kind"] == "root" for e in journal._entries())
    created_root = not root_path.exists()
    if created_root and bound:
        # The committed root is missing: never replace it with a new one.
        raise EvaluationUnavailable("evaluation_journal_other_root")
    try:
        root = (
            seeds.PrivateRoot.create(root_path)
            if created_root
            else seeds.PrivateRoot.load(root_path)
        )
    except ValueError:
        # Not a regular, owner-only, 32-byte file: kept as is, never replaced.
        raise EvaluationUnavailable("evaluation_root_refused") from None
    if not journal_path.exists():
        os.close(os.open(journal_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    if os.stat(journal_path).st_mode & 0o077:
        raise EvaluationUnavailable("evaluation_journal_not_owner_only")
    try:
        pin, committed = journal.root_pin(root), False
    except ValueError:
        if bound:
            raise EvaluationUnavailable("evaluation_journal_other_root") from None
        pin = seeds.seed_pin(
            seeds.generator_digest(repository), rule_digest(rule_for(config))
        )
        journal.commit_root(root, pin)
        committed = True
    return {
        "root_created": created_root,
        "root_committed": committed,
        "root_commitment": root.commitment(),
        "seed_pin": pin,
    }


CARRY_OVER_DECISION = "OWNER-BATTERY-CARRYOVER-01"


def serving_identities(config_path, *, repository=REPOSITORY):
    """The identities a writable start of this deployment binds.

    Computed without starting, recovering, locking or reaching Docker. A
    read-only build runs `DirectBackend`, because it never evaluates, so its
    own `identities()` name the trusted in-process backend. A carrier
    deployment serves through its pinned worker images instead: this names
    them exactly as `CarrierBackend` does. `upgrade` binds this and the
    service preflight compares it with the stored binding, so neither ever
    writes or expects the read-only backend for a carrier deployment (which
    would make every later start refuse `identities_changed`).

    Raises `EvaluationUnavailable("evaluation_config_image")` for a manifest
    that cannot be read as a pinned worker image identity.
    """
    from .worker import CarrierBackend

    config = load_config(config_path)
    identities = validator(
        config_path, repository=repository, readonly=True
    ).identities()
    if config["backend"] == "carrier":
        from carbon.reconstruction.worker.docker_runtime import load_image_identity
        from carbon.reconstruction.worker.model import WorkerFailure

        try:
            image = load_image_identity(Path(config["image_manifest"]))
            torch_image = (
                load_image_identity(Path(config["torch_image_manifest"]))
                if config.get("torch_image_manifest")
                else None
            )
        except WorkerFailure:
            raise EvaluationUnavailable("evaluation_config_image") from None
        carrier = CarrierBackend(None, image, torch_image=torch_image, root=repository)
        identities["backend"] = dict(carrier.identity)
    return identities


def upgrade(config_path):
    """Rebind a deployment to this checkout's identities, in place."""
    from .pool_store import StateError

    load_config(config_path)
    target = validator(config_path, repository=REPOSITORY, readonly=True)
    identities = serving_identities(config_path)
    with writer(target):
        try:
            result = target.store.rebind(identities, decision=CARRY_OVER_DECISION)
        except StateError as refused:
            raise EvaluationUnavailable("upgrade_" + refused.code) from None
    return {**result, "decision": CARRY_OVER_DECISION}


#: `run --every` refuses a shorter period: an engineering bound, so a
#: misconfigured service cannot spin on the deployment's writer lock.
MIN_EVERY_S = 5.0
DAEMON_SERVICE = "battery-validator-daemon"
HEARTBEAT_SCHEMA = "carbon.battery.validator-daemon-heartbeat.v1"
#: A status probe holds a daemon's liveness lock for an instant, so a
#: starting daemon retries it this often, this far apart (engineering values).
LOCK_TRIES, LOCK_RETRY_S = 40, 0.05

#: The exit codes of the long-lived commands (`run --every` and the intake's
#: `serve`) as a supervisor reads them (LP-PROD-G). `REFUSED_EXIT` is never
#: restarted, since a restart would only repeat the refusal;
#: `INFRASTRUCTURE_EXIT` is, after a backoff and within a restart limit.
REFUSED_EXIT, INFRASTRUCTURE_EXIT = 2, 1
#: The refusals that name a configuration or its files, by prefix or code.
#: Every other `EvaluationUnavailable` is the host's state - above all
#: `evaluation_host_unavailable`, which a carrier start raises while Docker
#: is down or still starting after a reboot - and so is a code this list does
#: not know: a wrong guess then costs a bounded number of restarts, never a
#: service left down by a passing outage.
CONFIGURATION_PREFIXES = (
    "evaluation_config_",
    "evaluation_input_",
    "evaluation_journal_",
    "evaluation_root_",
    "evaluation_work_",
)
CONFIGURATION_CODES = frozenset(
    {
        "evaluation_identities_changed",
        "evaluation_identities_not_carryable",
        "evaluation_not_bound",
        "evaluation_readonly",
        "evaluation_rule_mismatch",
        "evaluation_state_not_owner_only",
        "run_every_too_short",
        "run_heartbeat_not_owner_only",
        "run_daemon_already_running",
    }
)


def exit_code(code):
    """The exit code a long-lived command ends with when refused by `code`:
    `REFUSED_EXIT` for a configuration, `INFRASTRUCTURE_EXIT` otherwise."""
    if code in CONFIGURATION_CODES or code.startswith(CONFIGURATION_PREFIXES):
        return REFUSED_EXIT
    return INFRASTRUCTURE_EXIT


def _line(out, event, **fields):
    """One structured log line: UTC time, service, event and counts only."""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "service": DAEMON_SERVICE,
        "event": event,
        **fields,
    }
    print(json.dumps(record, sort_keys=True), file=out, flush=True)


def _heartbeat_lock(heartbeat):
    """Hold `<heartbeat>.lock` for the daemon's life and return its fd.

    It is the signal a service's `status` and `restore` read to see the
    daemon running, whether a supervisor or a systemd unit started it. The
    heartbeat's directory must be owner-only. A probe holds the lock shared
    for an instant, so it is retried briefly; a lock still held belongs to
    another daemon on the same heartbeat (`run_daemon_already_running`).
    """
    folder = Path(heartbeat).parent
    try:
        info = os.lstat(folder)
    except OSError:
        info = None
    if info is None or not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise EvaluationUnavailable("run_heartbeat_not_owner_only")
    fd = os.open(
        str(heartbeat) + ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    for _ in range(LOCK_TRIES):
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            time.sleep(LOCK_RETRY_S)
        else:
            return fd
    os.close(fd)
    raise EvaluationUnavailable("run_daemon_already_running")


def _beat(heartbeat, state, out):
    """Replace the heartbeat, owner-only and whole: the pid, times and counts,
    nothing else. A write that fails is logged by type; the daemon goes on."""
    if heartbeat is None:
        return
    path = Path(heartbeat)
    partial = path.with_name("." + path.name + ".partial")
    record = {
        "schema": HEARTBEAT_SCHEMA,
        "pid": os.getpid(),
        "updated_unix": time.time(),
        **state,
    }
    try:
        fd = os.open(
            partial,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(fd, "w") as handle:
            json.dump(record, handle, sort_keys=True)
        os.replace(partial, path)
    except OSError as failure:
        _line(out, "heartbeat_failed", type=type(failure).__name__)


def _pass(config_path, target, repository, out):
    """One pass: build the deployment if it is not built yet, then one `run`.
    Returns `(target, how the pass ended)`: `ok`, `failed` or `unavailable`."""
    if target is None:
        try:
            target = validator(config_path, repository=repository)
        except EvaluationUnavailable as unavailable:
            if exit_code(unavailable.code) == REFUSED_EXIT:
                raise
            _line(out, "pass_unavailable", code=unavailable.code)
            return None, "unavailable"
    try:
        with writer(target):
            advanced = target.run_pending()
            status = target.status()
    except Exception as failure:  # noqa: BLE001 - infrastructure, retried
        _line(out, "pass_failed", type=type(failure).__name__)
        return target, "failed"
    pool = status["pool"]
    _line(
        out,
        "pass",
        advanced=len(advanced),
        pending=status["pending"],
        open_finals=status["open_finals"],
        pool=None if pool is None else pool["status"],
    )
    return target, "ok"


def run_every(
    config_path,
    every,
    *,
    stop=None,
    out=None,
    repository=REPOSITORY,
    heartbeat=None,
):
    """`run`, long-lived: advance the queue once per `every` seconds.

    Each pass is exactly one `run` (`run_pending` under the writer lock, held
    for that pass only), so the intake's worker, a campaign's submit and
    every operator command interleave with it. An exception inside a pass is
    infrastructure: its type is logged, never its content, and the next pass
    retries.

    The deployment is built by the first pass. A build refused for the
    host's state (`evaluation_host_unavailable`: Docker down or still
    starting) is retried by the next pass, each logged `pass_unavailable`:
    an outage is waited out, never a reason to exit. A refusal of the
    configuration (`exit_code` gives `REFUSED_EXIT`) propagates, and the
    caller exits 2 so a supervisor does not restart into it.

    With `heartbeat` (a path in an owner-only directory) the daemon holds
    `<heartbeat>.lock` while it lives and replaces the heartbeat at start,
    when each pass starts and ends, and at stop: pid, period, passes, whether
    a pass is running, and how the last one ended. Returns the number of
    passes made once `stop` is set.
    """
    out = sys.stdout if out is None else out
    stop = threading.Event() if stop is None else stop
    if not every >= MIN_EVERY_S:
        raise EvaluationUnavailable("run_every_too_short")
    load_config(config_path)
    lock = None if heartbeat is None else _heartbeat_lock(heartbeat)
    state = {
        "every_s": every,
        "passes": 0,
        "in_pass": False,
        "last_pass": None,
        "last_pass_unix": None,
        "stopped": False,
    }
    try:
        _line(out, "started", every_s=every)
        _beat(heartbeat, state, out)
        target = None
        while not stop.is_set():
            state.update(in_pass=True, pass_started_unix=time.time())
            _beat(heartbeat, state, out)
            target, ended = _pass(config_path, target, repository, out)
            state["passes"] += 1
            state.update(in_pass=False, last_pass=ended, last_pass_unix=time.time())
            _beat(heartbeat, state, out)
            stop.wait(every)
        _line(out, "stopped", passes=state["passes"])
        state["stopped"] = True
        _beat(heartbeat, state, out)
        return state["passes"]
    finally:
        if lock is not None:
            os.close(lock)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.operate")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "status", "batches", "recover", "open", "upgrade"):
        sub.add_parser(name).add_argument("--config", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", required=True)
    run.add_argument(
        "--every",
        type=float,
        help="stay running: one pass every SECONDS (at least 5) until SIGTERM",
    )
    run.add_argument(
        "--heartbeat",
        help="with --every: keep a heartbeat at PATH (owner-only directory)",
    )
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--config", required=True)
    prepare.add_argument("--role", required=True)
    prepare.add_argument("--kind", choices=("screening", "finalist"), required=True)
    prepare.add_argument("--count", type=int)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--config", required=True)
    ingest.add_argument("--batch", required=True)
    ingest.add_argument("--records", required=True)
    jobs = sub.add_parser("jobs")
    jobs.add_argument("--config", required=True)
    jobs.add_argument("--batch", required=True)
    jobs.add_argument("--out", required=True)
    materialize = sub.add_parser("truth-materialize")
    materialize.add_argument("--target", required=True)
    materialize.add_argument("--wheels-dir")
    sub.add_parser("truth-verify").add_argument("--target", required=True)
    export = sub.add_parser("export")
    export.add_argument("--config", required=True)
    export.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command in ("truth-materialize", "truth-verify"):
        from .truth_env import TruthEnvironmentError, materialize, verify

        try:
            result = (
                materialize(
                    args.target, repository=REPOSITORY, wheels_dir=args.wheels_dir
                )
                if args.command == "truth-materialize"
                else verify(args.target, repository=REPOSITORY)
            )
        except TruthEnvironmentError as refused:
            print(json.dumps({"refused": str(refused)}))
            return 2
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0

    if args.command == "run" and args.heartbeat is not None and args.every is None:
        parser.error("--heartbeat needs --every")
    if args.command == "run" and args.every is not None:
        stop = threading.Event()
        for number in (signal.SIGTERM, signal.SIGINT):
            signal.signal(number, lambda *_: stop.set())
        try:
            run_every(args.config, args.every, stop=stop, heartbeat=args.heartbeat)
        except EvaluationUnavailable as unavailable:
            # A configuration refusal exits 2 and is never restarted; any
            # other code is the host's state, exit 1, restarted after backoff.
            print(json.dumps({"unavailable": unavailable.code}))
            return exit_code(unavailable.code)
        return 0
    if args.command == "upgrade":
        try:
            result = upgrade(args.config)
        except EvaluationUnavailable as unavailable:
            print(json.dumps({"unavailable": unavailable.code}))
            return 2
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    if args.command == "init":
        try:
            result = init(args.config)
        except EvaluationUnavailable as unavailable:
            print(json.dumps({"unavailable": unavailable.code}))
            return 2
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    readonly = args.command in ("status", "batches", "jobs")
    try:
        load_config(args.config)
        target = validator(args.config, repository=REPOSITORY, readonly=readonly)
    except EvaluationUnavailable as unavailable:
        print(json.dumps({"unavailable": unavailable.code}))
        return 2
    if readonly and args.command != "jobs":
        # Reads only: no start, no recovery, no lock - never touches a run
        # another process is executing.
        result = target.status() if args.command == "status" else _batches(target)
    elif args.command == "jobs":
        result = _jobs(target, args.batch, args.out)
    else:
        from .pool_store import StateError

        try:
            with writer(target):
                result = _mutate(target, args)
        except StateError as refused:
            # A refused operator step (a reserved or sealed seed role, for
            # one) is named, never a traceback, and changes nothing.
            print(json.dumps({"refused": refused.code}))
            return 2
    print(json.dumps(result, sort_keys=True, indent=2, default=str))
    return 0


def _mutate(target, args):
    if args.command == "recover":
        target.recover()
        result = target.status()
    elif args.command == "prepare":
        result = {
            "fingerprint": target.prepare_batch(
                args.role, kind=args.kind, count=args.count
            )
        }
    elif args.command == "ingest":
        from .truth import TruthService

        result = {
            "complete": bool(
                target.ingest_references(
                    args.batch, TruthService(args.records).records()
                )
            )
        }
    elif args.command == "open":
        result = target.open_pool()
    elif args.command == "run":
        result = {"advanced": len(target.run_pending()), "status": target.status()}
    else:
        result = _export(target, args.out)
    return result


if __name__ == "__main__":
    sys.exit(main())
