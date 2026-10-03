"""Run one public challenge pool batch inside a RunPod CPU pod.

    python -m scripts.dev.challenge_pools.pod_phase {cold-plate|motor} --out OUT

The pod bootstrap (`scripts/dev/exam_design/runpod/bootstrap.py`) fetches the
hash-pinned code and runs this as its phase. PHASE_CONFIG names a plan
committed in the repository and the worker count. Each case then runs natively
(`run_batch.py --native`) in an environment set up as the pinned reference is:
- the cold plate's OpenFOAM image itself;
- the motor image's Dockerfile steps, replayed on its pinned base.

Only public plans run here. A plan that carries a private-root commitment, or
names a private batch, is refused before anything runs: hidden evaluation
cases never leave the owner's host (invariant 1).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
#: The batch runner for each pool and its per-case wall limit (s).
RUNNERS = {
    "cold-plate": ("scripts/dev/cold_plate/reference/run_batch.py", 7200),
    "motor": ("scripts/dev/motor/reference/run_batch.py", 14400),
}


def public_plan(path):
    """The plan, refused if it is anything but a public pool plan."""
    plan = json.loads(Path(path).read_text())
    if "root_commitment" in plan or "private" in str(plan.get("batch", "")):
        raise SystemExit("refusing: a private pool never runs on rented compute")
    return plan


def command(kind, plan_path, out, workers, environment):
    script, timeout_s = RUNNERS[kind]
    return [
        sys.executable,
        str(ROOT / script),
        str(plan_path),
        "--out",
        str(out),
        "--parallel",
        str(workers),
        "--timeout-s",
        str(timeout_s),
        "--keep",
        "none",
        "--native",
        environment,
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kind", choices=sorted(RUNNERS))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(os.environ.get("PHASE_CONFIG", "{}"))
    plan_path = ROOT / config["plan_path"]
    public_plan(plan_path)
    workers = int(config.get("max_workers") or os.cpu_count() or 1)
    environment = os.environ.get("CARBON_REFERENCE_ENV", "native")
    return subprocess.run(
        command(args.kind, plan_path, args.out, workers, environment),
        cwd=ROOT,
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
