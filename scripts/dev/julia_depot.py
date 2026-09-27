"""The authored-Julia depot: its key, reuse of a published one, and building.

    julia_depot.py key                 print today's depot digest (Julia inputs only)
    julia_depot.py adopt --root DIR    pull the locked published depot, if it is
                                       for today's inputs, and record it for reuse
    julia_depot.py build --root DIR    reuse or build the depot and print it

`adopt` never fails the caller for an absent or stale lock, or a failed pull:
the suite then builds the depot cold, exactly as it would without a registry.
A pulled depot that fails verification is not recorded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from carbon.development_session import julia_depot
from carbon.development_session import julia_depot_build as build
from carbon.reconstruction.worker.docker_runtime import DockerCLI


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("key", "adopt", "build"))
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    if args.command == "key":
        print(julia_depot.depot_digest())
        return 0
    if args.root is None:
        parser.error("--root is required")
    cli = DockerCLI()
    if args.command == "build":
        depot, how = build.build_depot(args.root, cli)
        print(json.dumps({"depot": depot.__dict__, "how": how}, sort_keys=True))
        return 0
    key = julia_depot.depot_digest()
    lock = build.read_lock()
    if lock is None:
        print(f"no published depot for {key}; it will be built cold")
        return 0
    try:
        cli.run(["pull", "--platform=linux/amd64", lock["image"]], timeout=3600)
        depot = build.adopt_depot(args.root, cli, lock["image"])
    except Exception as refused:  # noqa: BLE001 - absent or unverified: build cold
        print(
            f"published depot {lock['image']} not adopted ({type(refused).__name__});"
            " it will be built cold"
        )
        return 0
    print(
        json.dumps({"adopted": depot.__dict__, "from": lock["image"]}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
