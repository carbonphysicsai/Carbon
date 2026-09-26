"""Command line: ``python -m carbon.compute reconcile --root ROOT --runpod-key-file F``.

The reconciler runs on the controller host (or any operator machine holding a
copy of that host's store and the key file), never on a rented pod: it reads
only the store under ``--root`` and the provider API, and it never contacts a
pod. It refuses to start inside a RunPod pod (``RUNPOD_POD_ID`` set) and
refuses a root without an existing store, so it cannot silently reconcile
against an empty ledger.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from .capability import capability_summary
from .credentials import FileCredentialProvider
from .errors import ComputeError
from .reconcile import reconcile
from .runpod import RunPodAdapter, RunPodTransport, UrllibTransport
from .store import ComputeStore

__all__ = ["main"]


def main(
    argv: Sequence[str] | None = None,
    *,
    transport: RunPodTransport | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    env = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(prog="python -m carbon.compute")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("reconcile")
    rec.add_argument("--root", type=Path, required=True)
    rec.add_argument("--runpod-key-file", type=Path)
    cap = sub.add_parser("capabilities")
    cap.add_argument("--runpod-key-file", type=Path)
    args = parser.parse_args(argv)

    if args.command == "capabilities":
        print(json.dumps(capability_summary(runpod_key_file=args.runpod_key_file)))
        return 0

    if env.get("RUNPOD_POD_ID"):
        print(json.dumps({"refused": "reconciler_must_run_off_the_rented_pod"}))
        return 2
    if not (args.root / "compute.sqlite3").is_file():
        print(json.dumps({"refused": "no_compute_store_under_root"}))
        return 2
    store = ComputeStore(args.root)
    try:
        adapter = RunPodAdapter(
            FileCredentialProvider(args.runpod_key_file),
            transport if transport is not None else UrllibTransport(),
        )
        try:
            report = reconcile(store, adapter)
        except ComputeError as failure:
            print(json.dumps({"error": failure.as_dict()}))
            return 1
    finally:
        store.close()
    print(json.dumps(report.as_dict(), sort_keys=True))
    return 1 if report.failures else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
