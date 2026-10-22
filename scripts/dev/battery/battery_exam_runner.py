"""Battery's reference runner under the family contract (VALIDATOR_BATTERY_SEALED_RULINGS_20261022).

    CARBON_BATTERY_SEALED_IMAGE=<id> python battery_exam_runner.py \\
        PLAN --out DIR [--parallel N] [--timeout-s S] [--keep none|failed|all]

Runs INSIDE the pinned truth image over the PyBaMM overlay (PYTHONPATH
/carbon:/overlay; see the payload's in-image driver). PLAN is
{"batch", "kind", "cases": [{"case_id", "inputs": {c1, c2, t_amb_c, soc0}}]}.
Each case is solved twice, one fresh process each (clean peak memory):
1. the standard 30-cycle reference, `truth.reference_solver` unchanged (mesh 20);
2. the cycle-1 plating margin at mesh 160, rtol 1e-6
   (`plating_convergence.solve` unchanged, the D3 re-reference).
The label is the pinned v2 reader's (`battery_sealed_hidden.plating_label`).

One record per case in DIR/records.jsonl, statuses:
- OK: both solves OK, a finite label;
- REFERENCE_SOLVER_FAILED: a solve ended in a typed solver failure;
- REFERENCE_TIMEOUT: a solve passed the per-solve timeout;
- FAILED_INFRA (not terminal, so the family retries): a solve was killed from
  outside (memory), could not start, or wrote nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECORD_SCHEMA = "carbon.battery.sealed-reference-record.v1"
INPUTS = ("c1", "c2", "t_amb_c", "soc0")
MESH = 160
TERMINAL = ("OK", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")


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
            or type(inputs) is not dict
            or set(inputs) != set(INPUTS)
            or not all(type(v) in (int, float) for v in inputs.values())
        ):
            raise SystemExit("plan: malformed case")
        seen.add(case["case_id"])
    return cases


def child(kind, case_path, out_path):
    """One solve in this process; writes its record. Run in a fresh process."""
    import resource

    case = json.loads(Path(case_path).read_text())
    if kind == "standard":
        from carbon.battery import truth

        job = {"case_id": case["case_id"], **case["inputs"]}
        record = truth.reference_solver(job)
    else:
        from scripts.dev.battery import plating_convergence as pc

        flat = {"case_id": case["case_id"], **case["inputs"]}
        job = {"case": 0, "mesh": MESH, "rtol": 1e-6, "period_s": None, "cycles": 1}
        record = pc.solve(flat, job)
        if record.get("status") != "OK":
            record["status"] = "REFERENCE_SOLVER_FAILED"
    record["maxrss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    Path(out_path).write_text(json.dumps(record, sort_keys=True, allow_nan=False))
    return 0 if record.get("status") == "OK" else 3


def run_solve(kind, case, timeout_s, scratch):
    """One solve in a fresh process: (outcome, record). Outcome is "done",
    "timeout" or "infra"."""
    case_path = scratch / f"{kind}-case.json"
    out_path = scratch / f"{kind}-out.json"
    case_path.write_text(json.dumps(case))
    command = [sys.executable, str(Path(__file__).resolve()), "--child", kind,
               str(case_path), str(out_path)]  # fmt: skip
    try:
        completed = subprocess.run(command, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return "timeout", None
    except OSError:
        return "infra", None
    if not out_path.is_file():
        # killed from outside (memory, a signal) or crashed before writing
        return "infra", None
    record = json.loads(out_path.read_text())
    return ("done" if completed.returncode in (0, 3) else "infra"), record


def record_for(plan, case, standard, plating, image, lock_sha):
    """A case's record from its two (outcome, record) results. Pure."""
    base = {
        "schema": RECORD_SCHEMA,
        "batch": plan["batch"],
        "case_id": case["case_id"],
        "kind": plan.get("kind"),
        "inputs": case["inputs"],
        "image": image,
        "overlay_lock_sha256": lock_sha,
    }
    outcomes = (standard[0], plating[0])
    if "infra" in outcomes:
        return {**base, "status": "FAILED_INFRA", "reasons": ["a solve was stopped"]}
    if "timeout" in outcomes:
        return {**base, "status": "REFERENCE_TIMEOUT", "reasons": ["a solve timed out"]}
    std, pl = standard[1], plating[1]
    if std.get("status") != "OK" or pl.get("status") != "OK":
        return {**base, "status": "REFERENCE_SOLVER_FAILED", "reasons": ["a solve failed"]}
    from carbon.challenge_validator import battery_sealed_hidden as hidden

    m160 = pl["plating_margin_v"]
    label = hidden.plating_label(std["outputs"]["plating_margin_v"], m160)
    return {
        **base,
        "status": "OK",
        "reasons": [],
        "outputs": std["outputs"],
        "diagnostics": std.get("diagnostics"),
        "plating_margin_m160_v": m160,
        "plating": label,
        "solves": {
            "standard": {"wall_s": std.get("wall_s"), "maxrss_mb": std["maxrss_mb"]},
            "m160": {"wall_s": pl.get("wall_s"), "maxrss_mb": pl["maxrss_mb"]},
        },
    }


def solve_case(plan, case, timeout_s, image, lock_sha, keep):
    with tempfile.TemporaryDirectory(prefix="battery-sealed-") as name:
        scratch = Path(name)
        standard = run_solve("standard", case, timeout_s, scratch)
        # mesh 160 only after a standard OK: no wasted memory-heavy solve
        plating = (
            run_solve("m160", case, timeout_s, scratch)
            if standard[0] == "done" and standard[1].get("status") == "OK"
            else ("skipped", None)
        )
        if plating[0] == "skipped":
            plating = ("done", {"status": "REFERENCE_SOLVER_FAILED"}) if standard[0] == "done" else standard
        return record_for(plan, case, standard, plating, image, lock_sha)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["--child"]:
        return child(*argv[1:4])
    parser = argparse.ArgumentParser(prog="battery_exam_runner")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--timeout-s", type=float, default=7200.0)
    parser.add_argument("--keep", choices=("none", "failed", "all"), default="none")
    args = parser.parse_args(argv)
    from carbon.challenge_validator import battery_sealed_hidden as hidden

    image = os.environ.get("CARBON_BATTERY_SEALED_IMAGE")
    if image != hidden.SOLVER_IMAGE:
        raise SystemExit("CARBON_BATTERY_SEALED_IMAGE must be the pinned truth image")
    from carbon.battery import truth_env

    truth_env.require_truth_runtime(str(ROOT))
    lock_sha = hidden.overlay_lock_sha256(ROOT)
    plan = json.loads(args.plan.read_text())
    cases = check_plan(plan)
    args.out.mkdir(parents=True, exist_ok=True)
    records = args.out / "records.jsonl"
    with ThreadPoolExecutor(max(1, args.parallel)) as pool:
        for record in pool.map(
            lambda c: solve_case(plan, c, args.timeout_s, image, lock_sha, args.keep),
            cases,
        ):
            with records.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
