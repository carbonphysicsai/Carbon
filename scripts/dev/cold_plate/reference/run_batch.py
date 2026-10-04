"""Run a batch of cold plate reference cases; every case ends as a typed record.

    python -m scripts.dev.cold_plate.reference.run_batch PLAN.json --out DIR
        [--parallel 4] [--cpus 2] [--timeout-s 3600] [--keep all|failed|none]

PLAN.json is {"batch": NAME, "cases": [{"case_id", "kind", "inputs",
"options"?}]}, where `inputs` are the nine Challenge inputs and `options` may set
`resolution`, `wall_grading`, `iterations` or `fluid_model`
(`carbon.cold_plate.openfoam.files`).

Each case is written by `carbon.cold_plate.openfoam`, solved in the pinned
image with no network, capped at `--cpus` CPUs, under a hard wall limit, and
read back by `carbon.cold_plate.analysis`. Its record's `status` is one of the
readiness outcomes (`carbon.challenge_readiness.record.OUTCOMES`):

- `OK` and `REFERENCE_INVALID` come from the analysis;
- `REFERENCE_SOLVER_FAILED` when the run leaves nothing readable;
- `REFERENCE_TIMEOUT` when the wall limit is reached; the case's own container
  is killed by its unique name, and no other container is touched;
- `FAILED_INFRA` when the case could not be started at all (writing it, or
  docker itself), never a reference result.

Records append to `DIR/records.jsonl` as each case ends; `DIR/progress.json`
is rewritten. A case whose directory exists is refused, never overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import analysis, openfoam

RECORD_SCHEMA = "carbon.cold-plate.reference-record.v1"
#: docker exits with these when it could not run the container at all.
DOCKER_START_FAILURES = {125, 126, 127}


def host_info():
    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }
    try:
        info["cpu_model"] = next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        )
    except (OSError, StopIteration):
        pass
    return info


#: Set by --native: the description of the environment the cases run in
#: directly (a pod started from the pinned image), recorded on every case.
NATIVE = None


def run_native(command, cwd, timeout_s, env=None):
    """Run a case's commands directly in this environment: a pod started from
    the pinned reference environment, where no container can be launched.
    The case gets its own process group, so a timeout kills all of it and
    nothing else. Returns (exit code, or None on timeout; wall s; stderr tail)."""
    start = time.monotonic()
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        _, err = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return None, time.monotonic() - start, ""
    return proc.returncode, time.monotonic() - start, (err or "")[-2000:]


def solve(case_dir, name, cpus, timeout_s):
    """Run the pinned commands in a fresh container, or directly under
    --native. Returns (status, wall_s, detail); status is None when the
    commands finished (well or badly)."""
    if NATIVE:
        script = "set -e; " + "; ".join(openfoam.COMMANDS)
        try:
            code, wall, _ = run_native(["bash", "-lc", script], case_dir, timeout_s)
        except OSError as exc:
            return "FAILED_INFRA", 0.0, f"native: {exc}"
        if code is None:
            return "REFERENCE_TIMEOUT", wall, f"wall limit {timeout_s} s"
        return None, wall, f"exit {code}"
    script = "set -e; cd /case; " + "; ".join(openfoam.COMMANDS)
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        "none",
        "--cpus",
        str(cpus),
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{case_dir.resolve()}:/case",
        openfoam.IMAGE,
        "bash",
        "-lc",
        script,
    ]
    start = time.monotonic()
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["docker", "kill", name], capture_output=True, text=True, check=False
        )
        return (
            "REFERENCE_TIMEOUT",
            time.monotonic() - start,
            f"wall limit {timeout_s} s",
        )
    except OSError as exc:
        return "FAILED_INFRA", time.monotonic() - start, f"docker: {exc}"
    wall = time.monotonic() - start
    if done.returncode in DOCKER_START_FAILURES:
        return "FAILED_INFRA", wall, done.stderr.strip()[-2000:]
    return None, wall, f"exit {done.returncode}"


def run_case(entry, out, args, batch, lock):
    case_id = entry["case_id"]
    case_dir = out / "cases" / case_id
    record = {
        "schema": RECORD_SCHEMA,
        "batch": batch,
        "case_id": case_id,
        "kind": entry.get("kind", "ordinary"),
        "inputs": entry["inputs"],
        "options": entry.get("options", {}),
    }
    try:
        openfoam.write_case(entry["inputs"], case_dir, **entry.get("options", {}))
    except FileExistsError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        record.update(status="FAILED_INFRA", reasons=[f"case not written: {exc}"])
        return _finish(record, out, lock, None, args)
    name = f"carbon-cold-plate-{batch}-{case_id}"[:120]
    status, wall, detail = solve(case_dir, name, args.cpus, args.timeout_s)
    record["wall_s"] = round(wall, 1)
    record["run"] = detail
    if status is not None:
        record.update(status=status, reasons=[detail])
        return _finish(record, out, lock, case_dir, args)
    result = analysis.analyze_case(case_dir)
    (case_dir / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    record.update(
        status=result["outcome"],
        reasons=result["reasons"],
        outputs=result.get("outputs"),
        checks=result.get("checks"),
        diagnostics=result.get("diagnostics"),
        derived=result["case"]["derived"],
        mesh=result["case"]["mesh"],
        image=openfoam.IMAGE,
        **({"execution": NATIVE} if NATIVE else {}),
    )
    return _finish(record, out, lock, case_dir, args)


def _finish(record, out, lock, case_dir, args):
    keep = args.keep == "all" or (args.keep == "failed" and record["status"] != "OK")
    if case_dir is not None and case_dir.exists() and not keep:
        shutil.rmtree(case_dir)
    with lock:
        with (out / "records.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        counts = {}
        for line in (out / "records.jsonl").read_text().splitlines():
            status = json.loads(line)["status"]
            counts[status] = counts.get(status, 0) + 1
        (out / "progress.json").write_text(
            json.dumps({"done": sum(counts.values()), "counts": counts}) + "\n"
        )
    print(
        f"{record['case_id']}: {record['status']} "
        f"{record.get('wall_s', '-')} s {'; '.join(record.get('reasons', []))}",
        flush=True,
    )
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--cpus", type=float, default=2.0)
    parser.add_argument("--timeout-s", type=float, default=3600.0)
    parser.add_argument("--keep", choices=("all", "failed", "none"), default="all")
    parser.add_argument(
        "--native",
        metavar="ENVIRONMENT",
        help="run each case directly in this environment, described for the record "
        "(a pod started from the pinned image); no container is launched",
    )
    args = parser.parse_args(argv)
    global NATIVE
    NATIVE = args.native
    plan = json.loads(args.plan.read_text())
    cases = plan["cases"]
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        parser.error("case ids must be unique")
    args.out.mkdir(parents=True, exist_ok=True)
    args.out.chmod(0o700)
    if any((args.out / "cases" / i).exists() for i in ids):
        parser.error("a case directory exists; refusing to overwrite")
    (args.out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (args.out / "host.json").write_text(
        json.dumps(
            {
                **host_info(),
                "parallel": args.parallel,
                "cpus": args.cpus,
                "timeout_s": args.timeout_s,
                "keep": args.keep,
                "solver_image": openfoam.IMAGE,
            }
        )
        + "\n"
    )
    lock = threading.Lock()
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        records = list(
            pool.map(lambda c: run_case(c, args.out, args, plan["batch"], lock), cases)
        )
    summary = {
        "batch": plan["batch"],
        "cases": len(records),
        "wall_s": round(time.monotonic() - start, 1),
        "counts": {
            s: sum(1 for r in records if r["status"] == s)
            for s in sorted({r["status"] for r in records})
        },
    }
    (args.out / "DONE.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
