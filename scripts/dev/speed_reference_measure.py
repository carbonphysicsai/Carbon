"""Measure the kit speed workload on the grading worker, once, for its registered row (owner pick 3, 15 Nov 2026).

Run on the grading host by its operator, under that host's own rules (no grade in flight, background jobs paused):

    python -m scripts.dev.speed_reference_measure --image-manifest <the receiver's inference worker image manifest> \
        --root <a new scratch folder> --worker-class "<host class, as the kit prints it>" [--runs 5]

It runs `speed_workload.measure` `--runs` times through the carrier (the grade's own timed inference program, the host's
own worker cpuset and resources), each in a fresh operation, in its own ledger under `--root`. It writes
`<root>/evidence.json` (every run's result, the host's load before and after, the time) and prints the candidate row
for `scripts/dev/miner_launchpad/speed_reference.json`: the median of the runs' per-call medians and start-ups, keyed by
the workload digest, with the evidence file's sha256. It registers nothing itself: the row enters by a reviewed values
commit. Public material only; it reads no pack, key, seed or hidden row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

#: The load average above which the measurement refuses to start (the grading host's pause rule for timed work).
LOAD_CEILING = 8.0


def _load():
    try:
        return list(os.getloadavg())
    except (AttributeError, OSError):
        return None


def candidate_row(results, *, worker_class, evidence_sha256, measured_utc):
    """`(workload_digest, row)` from the runs' results, refused when they name different workloads or images."""
    digests = {r["workload_digest"] for r in results}
    images = {r["image_id"] for r in results}
    if not results or len(digests) != 1 or len(images) != 1:
        raise ValueError("speed runs differ in workload or image")
    return digests.pop(), {
        "worker_class": worker_class,
        "image_id": images.pop(),
        "per_call_median_seconds": statistics.median(
            r["per_call_median_seconds"] for r in results
        ),
        "startup_seconds": statistics.median(r["startup_seconds"] for r in results),
        "runs": len(results),
        "measured_utc": measured_utc,
        "evidence_sha256": evidence_sha256,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--image-manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--worker-class", required=True)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)
    if not 1 <= args.runs <= 10:
        parser.error("--runs is 1..10 (one ledger: at most 16 trials)")
    root = args.root.resolve()
    if root.exists() and any(root.iterdir()):
        parser.error("--root must be a new or empty folder")
    load_before = _load()
    if load_before is not None and load_before[0] >= LOAD_CEILING:
        print(
            f"refused: load1 {load_before[0]:.1f} >= {LOAD_CEILING}; pause the host's background jobs first",
            file=sys.stderr,
        )
        return 2

    from carbon.development_session import speed_workload
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    image = load_image_identity(args.image_manifest)
    ledger = speed_workload.open_ledger(root / "ledger")
    started = time.time()
    results = []
    for index in range(args.runs):
        results.append(
            speed_workload.measure(
                ledger,
                owner=speed_workload.OWNER,
                identity=f"speed-ref-{int(started)}-{index}",
                inference_image=image,
            )
        )
        print(
            f"run {index + 1}/{args.runs}: {results[-1]['per_call_median_seconds'] * 1000:.2f} ms per call",
            file=sys.stderr,
        )
    measured_utc = time.strftime("%Y-%m-%d", time.gmtime(started))
    evidence = {
        "schema": "carbon.kit.speed-reference-evidence.v1",
        "worker_class": args.worker_class,
        "started_unix": started,
        "finished_unix": time.time(),
        "load_before": load_before,
        "load_after": _load(),
        "results": results,
    }
    body = json.dumps(evidence, sort_keys=True, indent=1).encode() + b"\n"
    (root / "evidence.json").write_bytes(body)
    digest, row = candidate_row(
        results,
        worker_class=args.worker_class,
        evidence_sha256="sha256:" + hashlib.sha256(body).hexdigest(),
        measured_utc=measured_utc,
    )
    print(json.dumps({digest: row}, sort_keys=True, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
