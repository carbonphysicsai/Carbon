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
  after the pass in flight;
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
import json
import os
import signal
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


def _line(out, event, **fields):
    """One structured log line: UTC time, service, event and counts only."""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "service": DAEMON_SERVICE,
        "event": event,
        **fields,
    }
    print(json.dumps(record, sort_keys=True), file=out, flush=True)


def run_every(config_path, every, *, stop=None, out=None, repository=REPOSITORY):
    """`run`, long-lived: advance the queue once per `every` seconds.

    Each pass is exactly one `run` (`run_pending` under the writer lock, held
    for that pass only), so the intake's worker, a campaign's submit and
    every operator command interleave with it. An exception inside a pass is
    infrastructure: its type is logged, never its content, and the next pass
    retries. A deployment that cannot be built is a configuration state:
    `EvaluationUnavailable` propagates, and the caller exits 2 so a
    supervisor does not restart into the same refusal. Returns the number of
    passes made once `stop` is set.
    """
    out = sys.stdout if out is None else out
    stop = threading.Event() if stop is None else stop
    if not every >= MIN_EVERY_S:
        raise EvaluationUnavailable("run_every_too_short")
    load_config(config_path)
    target = validator(config_path, repository=repository)
    _line(out, "started", every_s=every)
    passes = 0
    while not stop.is_set():
        try:
            with writer(target):
                advanced = target.run_pending()
                status = target.status()
        except Exception as failure:  # noqa: BLE001 - infrastructure, retried
            _line(out, "pass_failed", type=type(failure).__name__)
        else:
            pool = status["pool"]
            _line(
                out,
                "pass",
                advanced=len(advanced),
                pending=status["pending"],
                open_finals=status["open_finals"],
                pool=None if pool is None else pool["status"],
            )
        passes += 1
        stop.wait(every)
    _line(out, "stopped", passes=passes)
    return passes


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

    if args.command == "run" and args.every is not None:
        stop = threading.Event()
        for number in (signal.SIGTERM, signal.SIGINT):
            signal.signal(number, lambda *_: stop.set())
        try:
            run_every(args.config, args.every, stop=stop)
        except EvaluationUnavailable as unavailable:
            print(json.dumps({"unavailable": unavailable.code}))
            return 2
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
        with writer(target):
            result = _mutate(target, args)
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
