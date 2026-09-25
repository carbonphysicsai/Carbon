"""The operator's commands for a battery validator deployment (M3).

    python -m carbon.battery.operate <command> --config DEPLOYMENT.json ...

Commands:
- ``status``: identities, pool, incumbent and batch counts;
- ``batches``: each batch's kind, state and reference completion;
- ``recover``: settle what a crash left mid-way (never dispatches work);
- ``prepare``: generate, commit and record one private batch from the root;
- ``jobs``: write one batch's reference jobs to an owner-only file for the
  truth container (read-only on the validator);
- ``ingest``: ingest the truth container's records file for a batch;
- ``open``: open the pool once three screening batches are complete;
- ``run``: advance every queued submission and open finalist comparison;
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
import sys
from pathlib import Path

from .deployment import EvaluationUnavailable, load_config, validator, writer

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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.operate")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "batches", "recover", "open", "run"):
        sub.add_parser(name).add_argument("--config", required=True)
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
