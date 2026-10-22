"""Cooling's sealed-exam reference runner under the family contract.

    CARBON_COOLING_IMAGE=<image> python3 cooling_exam_runner.py PLAN --out DIR \\
        [--parallel N] [--cpus C] [--timeout-s S] [--keep none|failed|all]

The counted batch runner (`run_batch`) unchanged, with two substitutions the
Validator decided for Cooling's sealed references (VALIDATOR_COOLING_RR14_DECISION
and VALIDATOR_MAINNET_RECAL_DECISIONS, 2026-10-20):
- every case is written on graded-hotspot-v1 at r = 2√2 (`mesh_family`); the plan
  names inputs only, never options, so no case can choose its own mesh;
- every solved case is judged by the graded heat-in analysis version
  (`analysis_graded`), so the energy check reads the faces the solver heated.

Statuses are run_batch's: OK and REFERENCE_INVALID from the analysis,
REFERENCE_SOLVER_FAILED, REFERENCE_TIMEOUT, and FAILED_INFRA (not terminal; the
family retries it). Each record's diagnostics carry the analysis version.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import analysis_graded, mesh_family, openfoam
from carbon.cold_plate.domain import INPUTS

RESOLUTION = 2 * math.sqrt(2)
OPTIONS = {"mesh_family": mesh_family.GRADED_HOTSPOT_V1, "resolution": RESOLUTION}
TERMINAL = ("OK", "REFERENCE_INVALID", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")


def check_plan(plan):
    cases = plan.get("cases") if type(plan) is dict else None
    if type(plan.get("batch")) is not str or type(cases) is not list or not cases:
        raise SystemExit("plan: batch and a non-empty case list are required")
    seen = set()
    for case in cases:
        inputs = case.get("inputs") if type(case) is dict else None
        if (
            type(case.get("case_id")) is not str
            or case["case_id"] in seen
            or "/" in case["case_id"]
            or "options" in case
            or type(inputs) is not dict
            or set(inputs) != set(INPUTS)
            or not all(type(v) in (int, float) for v in inputs.values())
        ):
            raise SystemExit("plan: malformed case (inputs only; options are fixed)")
        seen.add(case["case_id"])
    return cases


def family_plan(plan):
    """The plan run_batch runs: every case on the family at r = 2√2."""
    return {
        "batch": plan["batch"],
        "cases": [
            {
                "case_id": c["case_id"],
                "kind": c.get("kind", "ordinary"),
                "inputs": c["inputs"],
                "options": dict(OPTIONS),
            }
            for c in plan["cases"]
        ],
    }


def _patched_run_batch():
    """run_batch with its writer and analysis substituted; nothing else."""
    from scripts.dev.cold_plate.reference import run_batch

    writer = types.SimpleNamespace(
        **{k: getattr(openfoam, k) for k in dir(openfoam) if not k.startswith("__")}
    )
    writer.write_case = mesh_family.write_case
    run_batch.openfoam = writer
    run_batch.analysis = analysis_graded
    return run_batch


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cooling_exam_runner")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--cpus", type=float, default=2.0)
    parser.add_argument("--timeout-s", type=float, default=14400.0)
    parser.add_argument("--keep", choices=("none", "failed", "all"), default="none")
    args = parser.parse_args(argv)
    if os.environ.get("CARBON_COOLING_IMAGE") != openfoam.IMAGE:
        raise SystemExit("CARBON_COOLING_IMAGE must be the pinned Cooling image")
    plan = json.loads(args.plan.read_text())
    check_plan(plan)
    args.out.mkdir(parents=True, exist_ok=True)
    derived = args.out / "family-plan.json"
    if derived.exists():
        raise SystemExit(f"{derived} exists; refusing to overwrite")
    derived.write_text(json.dumps(family_plan(plan), indent=1) + "\n")
    run_batch = _patched_run_batch()
    return run_batch.main(
        [
            str(derived),
            "--out",
            str(args.out),
            "--parallel",
            str(args.parallel),
            "--cpus",
            str(args.cpus),
            "--timeout-s",
            str(args.timeout_s),
            "--keep",
            args.keep,
        ]
    )


if __name__ == "__main__":
    sys.exit(main())
