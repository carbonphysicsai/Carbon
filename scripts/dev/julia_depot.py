"""The authored-Julia depot: its key, reuse of a published one, and building.

    julia_depot.py key                 print today's depot digest (Julia inputs only)
    julia_depot.py adopt --root DIR    pull the locked published depot, if it is
                                       for today's inputs, and record it for reuse
    julia_depot.py build --root DIR    reuse or build the depot and print it

Optional `adopt` permits an absent/stale/failed published depot for explicit
operator builds. --require-published refuses service acceptance on that path.
A pulled depot that fails verification is not recorded.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from carbon.development_session import julia_depot
from carbon.development_session import julia_depot_build as build
from carbon.reconstruction.worker.docker_runtime import DockerCLI
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

ADOPTION_STAGES = frozenset(
    {"lock", "pull", "image_inspect", "tree_digest", "binding", "record"}
)


class AdoptionFailed(Exception):
    """A closed, value-free adoption failure; raw diagnostics stay private."""


def _phase(root, stage, operation):
    if stage not in ADOPTION_STAGES:
        raise AdoptionFailed("unknown adoption stage")
    started = time.monotonic()
    code = None
    try:
        result = operation()
    except Exception as failure:  # noqa: BLE001 - only closed codes survive
        if isinstance(failure, WorkerFailure):
            code = (
                failure.code.value
                if isinstance(failure.code, WorkerCode)
                else "unexpected_failure"
            )
        elif isinstance(failure, build.TreeReadFailure):
            code = (
                failure.code
                if failure.code in {"tree_read_deadline", "tree_read_failed"}
                else "unexpected_failure"
            )
        elif isinstance(failure, ValueError):
            code = "identity_refused"
        elif isinstance(failure, OSError):
            code = "filesystem_unavailable"
        else:
            code = "unexpected_failure"
    event = {
        "schema": "carbon.julia.depot.adoption.v1",
        "stage": stage,
        "status": "failed" if code else "success",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "code": code,
    }
    print(json.dumps(event, sort_keys=True), flush=True)
    try:
        build._record(root, how="adoption_stage", **event)
    except OSError:
        print(
            json.dumps(
                {
                    **event,
                    "stage": "record",
                    "status": "failed",
                    "code": "report_unavailable",
                }
            ),
            flush=True,
        )
        raise AdoptionFailed("adoption report unavailable") from None
    if code:
        raise AdoptionFailed("published depot adoption failed") from None
    return result


def _not_adopted(message):
    """Say so, and under GitHub Actions raise an annotation: a depot that is
    never adopted would otherwise hide as a green, merely slow, job."""
    print(message)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning title=Julia depot not adopted::{message}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("key", "adopt", "build"))
    parser.add_argument("--root", type=Path)
    parser.add_argument(
        "--require-published",
        action="store_true",
        help="fail before service acceptance if exact published depot adoption fails",
    )
    args = parser.parse_args(argv)
    if args.command == "key":
        print(julia_depot.depot_digest())
        return 0
    if args.root is None:
        parser.error("--root is required")
    if args.command == "build":
        cli = DockerCLI()
        depot, how = build.build_depot(args.root, cli)
        print(json.dumps({"depot": depot.__dict__, "how": how}, sort_keys=True))
        return 0
    key = julia_depot.depot_digest()
    try:
        lock = _phase(args.root, "lock", build.read_lock)
    except AdoptionFailed:
        # A malformed/unreadable lock remains a refusal even in optional mode.
        return 2
    if lock is None:
        print(
            json.dumps(
                {
                    "schema": "carbon.julia.depot.adoption.v1",
                    "stage": "lock",
                    "status": "failed",
                    "elapsed_seconds": 0,
                    "code": "published_depot_unavailable",
                }
            ),
            flush=True,
        )
        _not_adopted(
            f"no published depot for {key}; "
            + (
                "service acceptance refused"
                if args.require_published
                else "explicit build route remains available"
            )
        )
        return 2 if args.require_published else 0
    cli = DockerCLI()
    try:
        # Quiet progress cannot overflow the bounded controller response cap.
        # The immutable reference and existing finite pull timeout are retained.
        _phase(
            args.root,
            "pull",
            lambda: cli.run(
                ["pull", "--quiet", "--platform=linux/amd64", lock["image"]],
                timeout=3600,
            ),
        )
        depot = build.adopt_depot(
            args.root,
            cli,
            lock["image"],
            stage=lambda name, operation: _phase(args.root, name, operation),
        )
    except AdoptionFailed:
        _not_adopted(
            f"published depot {lock['image']} not adopted "
            + (
                "; service acceptance refused"
                if args.require_published
                else "; explicit build route remains available"
            )
        )
        return 2 if args.require_published else 0
    print(
        json.dumps({"adopted": depot.__dict__, "from": lock["image"]}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
