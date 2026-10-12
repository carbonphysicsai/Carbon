"""PUBLIC-DEV-DECISIONS-01 on one RunPod CPU pod, unattended.

    python -m scripts.dev.battery.public_dev_pod_phase solve --out OUT

The pod bootstrap (`scripts/dev/exam_design/runpod/bootstrap.py`) fetches the
hash-pinned code at CODE_REF, installs the locked battery overlay, runs this
phase and serves OUT. At PROBE_DEADLINE it terminates the pod: that is the hard
stop. Everything here is public.

1. **Draw** the 110 public questions and check `jobs.json` against the
   registered sha256. The phase refuses on a mismatch.
2. **Dry pass.** Solve the first WORKERS jobs and take their mean wall time.
3. **Size the run.** Project each question's standard cost as
   35 x mean / WORKERS, times TAIL. Reserve REFINE_SHARE for refinement. Keep
   the first N questions whose projection fits PDD_SOLVE_BUDGET_S, counted
   from the phase's start (at most 110).
4. **Standard pass** on those N questions, then REF-RESOLVE-01's refine jobs
   for them. Refinement stops at the budget, and what is solved is kept.
5. **Return** to OUT: contract, jobs, refine jobs, records, logs and a
   summary. Nothing is left only on the pod.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.battery import public_dev_questions as pdq
from scripts.dev.battery import score_proof_questions as spq

QUESTIONS, PER_QUESTION = 110, 35
JOBS_SHA256 = "803b3c400a8f9f8e0b4f7674e0a275d6a2b9bb0044372756e16a5074873b92ff"
TAIL, REFINE_SHARE = 1.15, 0.15


def _solve(jobs_path, records, workers, timeout_s=None):
    cmd = [sys.executable, "-m", "carbon.battery.truth_env", "solve", "--jobs", str(jobs_path),
           "--records", str(records), "--workers", str(workers)]  # fmt: skip
    try:
        return subprocess.run(cmd, cwd=ROOT, timeout=timeout_s, check=False).returncode
    except subprocess.TimeoutExpired:
        return "BUDGET_REACHED"


def _wall(records, case_ids):
    walls = [
        r["wall_s"]
        for r in spq._records(records.parent)
        if r["case_id"] in case_ids and "wall_s" in r
    ]
    return sum(walls) / len(walls) if walls else None


def size(mean_wall_s, workers, remaining_s):
    """Questions whose projected standard plus refine time fits."""
    per_question = PER_QUESTION * mean_wall_s / workers * TAIL
    return max(
        0, min(QUESTIONS, int(remaining_s / (per_question * (1 + REFINE_SHARE))))
    )


def solve(out):
    started = time.monotonic()
    budget = float(os.environ.get("PDD_SOLVE_BUDGET_S", "13800"))
    workers = int(os.environ.get("PDD_WORKERS", "30"))
    work = Path("/tmp/pdd")
    summary = {
        "schema": "carbon.public-dev-decisions.pod-summary.v1",
        "workers": workers,
        "budget_s": budget,
    }
    drawn = pdq.draw(work, QUESTIONS)
    summary["draw"] = drawn
    if drawn["jobs_sha256"] != JOBS_SHA256:
        raise SystemExit("refused: the drawn jobs differ from the registered ones")
    jobs_file = json.loads((work / "jobs.json").read_bytes())
    dry = {"fingerprint": jobs_file["fingerprint"], "jobs": jobs_file["jobs"][:workers]}
    (work / "dry.json").write_bytes(spq._canonical(dry))
    summary["dry_exit"] = _solve(work / "dry.json", work / "records.jsonl", workers)
    mean = _wall(work / "records.jsonl", {j["case_id"] for j in dry["jobs"]})
    summary["dry_mean_wall_s"] = mean
    if mean is None:
        raise SystemExit("refused: the dry pass returned no timed record")
    n = size(mean, workers, budget - (time.monotonic() - started))
    summary["questions_solved"] = n
    keep = {f"D-{k:04d}" for k in range(n)}
    jobs_file["jobs"] = [
        j for j in jobs_file["jobs"] if j["case_id"].split(":")[1] in keep
    ]
    (work / "jobs.json").write_bytes(spq._canonical(jobs_file))
    summary["standard_exit"] = _solve(
        work / "jobs.json", work / "records.jsonl", workers
    )
    summary["refine"] = pdq.refine(work)
    left = budget - (time.monotonic() - started)
    summary["refine_exit"] = (
        _solve(work / "jobs.json", work / "records.jsonl", workers, timeout_s=left)
        if left > 60
        else "BUDGET_REACHED"
    )
    summary["elapsed_s"] = time.monotonic() - started
    # a refine pass stopped at the budget may leave one partial last line
    lines = (work / "records.jsonl").read_text().splitlines()
    whole = []
    for line in lines:
        try:
            json.loads(line)
        except ValueError:
            continue
        whole.append(line)
    summary["partial_lines_dropped"] = len(lines) - len(whole)
    (work / "records.jsonl").write_text("".join(x + "\n" for x in whole))
    records = spq._records(work)
    summary["records"] = len(records)
    summary["statuses"] = {
        s: sum(r.get("status") == s for r in records)
        for s in {r.get("status") for r in records}
    }
    for name in (
        "contract.json",
        "jobs.json",
        "refine-jobs.json",
        "records.jsonl",
        "dry.json",
    ):
        if (work / name).exists():
            shutil.copyfile(work / name, Path(out) / name)
    (Path(out) / "summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {k: summary[k] for k in ("questions_solved", "records", "elapsed_s")}
        )
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="public_dev_pod_phase")
    parser.add_argument("phase", choices=("solve",))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    return solve(args.out)


if __name__ == "__main__":
    sys.exit(main())
