"""The operator's commands for a battery validator deployment (M3).

    python -m carbon.battery.operate <command> --config DEPLOYMENT.json ...

Commands:
- ``status``: identities, pool, incumbent and batch counts;
- ``batches``: each batch's kind, state and reference completion;
- ``recover``: settle what a crash left mid-way (never dispatches work);
- ``prepare``: generate, commit and record one private batch from the root;
- ``solve``: run the truth service on a batch's reference jobs into an
  owner-only records file, then ingest it. Run it inside the pinned truth
  image (`truth.TRUTH_IMAGE`); it is CPU work;
- ``ingest``: ingest an existing records file for a batch;
- ``open``: open the pool once three screening batches are complete;
- ``run``: advance every queued submission and open finalist comparison;
- ``export``: write service-key-signed outcomes and the Phase A all-burn
  weight intent for the owner publisher. It sends nothing anywhere.

Every output is operator-private: it goes to this terminal or an owner-only
file. Nothing here prints a key, a seed or the root; `batches` names roles
and fingerprints, never cases.
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


def _solve(target, fingerprint, records, workers, timeout_s):
    from .truth import TruthService

    path = Path(records)
    if not path.exists():
        path.touch(mode=0o600)
    if path.stat().st_mode & 0o077:
        raise SystemExit("the records file must be owner-only")
    jobs = target.reference_jobs(fingerprint)
    summary = TruthService(path, workers=workers, timeout_s=timeout_s).run(jobs)
    with writer(target):
        complete = target.ingest_references(fingerprint, TruthService(path).records())
    return {"solve": summary, "complete": bool(complete)}


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
    for name in ("solve", "ingest"):
        command = sub.add_parser(name)
        command.add_argument("--config", required=True)
        command.add_argument("--batch", required=True)
        command.add_argument("--records", required=True)
        if name == "solve":
            command.add_argument("--workers", type=int, default=1)
            command.add_argument("--timeout-s", type=float, default=1200.0)
    export = sub.add_parser("export")
    export.add_argument("--config", required=True)
    export.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    readonly = args.command in ("status", "batches")
    try:
        load_config(args.config)
        target = validator(args.config, repository=REPOSITORY, readonly=readonly)
    except EvaluationUnavailable as unavailable:
        print(json.dumps({"unavailable": unavailable.code}))
        return 2
    if readonly:
        # Reads only: no start, no recovery, no lock - never touches a run
        # another process is executing.
        result = target.status() if args.command == "status" else _batches(target)
    elif args.command == "solve":
        # Solving takes hours and touches only the records file; the writer
        # lock is held for the ingest alone.
        result = _solve(target, args.batch, args.records, args.workers, args.timeout_s)
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
