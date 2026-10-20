"""F02's reference runner under the family contract (OWNER-F02-F08-EXAM-DRAW-01).

    CARBON_F02_IMAGE=<image> python3 f02_exam_runner.py PLAN --out DIR \\
        [--parallel N] [--timeout-s S] [--keep none|failed|all]

PLAN is {"batch", "kind", "cases": [{"case_id", "inputs": {"peak_w",
"on_time_s"}}]}. Each case is solved as the development exam's references
were (RR-PACKS-04): the cold context, three rungs (primary, mesh2, dt0.5)
written by `f02_deck.write_case`, solved by ElmerSolver in the pinned image
with `f02_readiness.run`'s exact isolation, and judged by `f02_readiness.judge`
(B1-B5 under F02-SCIENCE-VALUES-01, unchanged). The context's B6/B7 baselines
were accepted once for this context (RR-PACKS-04, B10) and are not re-solved.

One record per case in DIR/records.jsonl, statuses:
- OK: every rung solved and B1-B5 pass at both refinements;
- REFERENCE_INVALID: every rung solved, a band fails;
- REFERENCE_SOLVER_FAILED: the solver ended in error without stopping from
  outside;
- REFERENCE_TIMEOUT: a rung exceeded the case timeout;
- FAILED_INFRA (not terminal, so the family retries): the container could not
  start, or a solve was stopped from outside (a signal, or exit 120).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import f02_deck as deck
import f02_readiness as readiness

RECORD_SCHEMA = "carbon.f02.exam-reference-record.v1"
CONTEXT = "c30-i40-s0.5-rectangular"
BASE_PANEL = "cool-rect-low"  # the cold panel case the exam actions vary
RUNGS = (("primary", 1, 1.0), ("mesh2", 2, 1.0), ("dt0.5", 1, 0.5))
OBSERVED = (
    "peak_top_c",
    "extra_energy_j",
    "first_95c_crossing_s",
    "peak_time_s",
    "recovery_s",
)
TERMINAL = ("OK", "REFERENCE_INVALID", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")
DOCKER_START_FAILURES = {125, 126, 127}


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
            or set(inputs) != {"peak_w", "on_time_s"}
            or not all(type(v) in (int, float) for v in inputs.values())
        ):
            raise SystemExit("plan: malformed case")
        seen.add(case["case_id"])
    return cases


def physical_case(inputs):
    """The development exam's own construction (`f02_cold_pilot`): the cold
    panel case with the schedule replaced. It reproduces RR-PACKS-04's
    registered decks byte for byte; building through the menu context does
    not (its float context values change the deck text and mesh)."""
    return dict(
        deck.panel_case(BASE_PANEL),
        peak_w=float(inputs["peak_w"]),
        on_time_s=float(inputs["on_time_s"]),
    )


def build(cases, decks):
    """Three frozen rung decks per case, with the readiness manifest."""
    entries = []
    for case in cases:
        physical = physical_case(case["inputs"])
        for tag, level, dt in RUNGS:
            name = f"{case['case_id']}-{tag}"
            meta = deck.write_case(physical, decks / "f02" / name, level, dt)
            files = readiness._hashes(decks / "f02" / name)
            reservation = "primary" if tag == "primary" else "mesh_and_time"
            entries.append(readiness.entry_for(name, reservation, files, meta))
    readiness._write_manifest(
        decks, "f02-exam-batch", entries, {"scope": "SEALED_EXAM_BATCH"}
    )
    return entries


def solve(entry, decks, image, timeout_s):
    """One rung, exactly as `f02_readiness.run` solves it, with the family's
    timeout. Returns (outcome, exit code or None, wall s)."""
    d = decks / "f02" / entry["case"]
    tag = entry["case"].rsplit("-", 1)[-1]
    memory = readiness.MEMORY.get(tag, readiness.DEFAULT_MEMORY)
    name = f"carbon-f02x-{entry['case']}"[:100]
    cmd = ["docker", "run", "--rm", "--name", name, "--network", "none",
           "--read-only", "--tmpfs", "/tmp", "--cpus", "1", "--memory", memory,
           "--memory-swap", memory, "--pids-limit", "16",
           "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{d.resolve()}:/case",
           "-w", "/case", image, "bash", "-c",
           f"{entry['command']}; {readiness.ACCOUNT}"]  # fmt: skip
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
        return "TIMEOUT", None, time.monotonic() - t0
    except OSError:
        return "INFRA", None, time.monotonic() - t0
    return "EXITED", proc.returncode, time.monotonic() - t0


def classify(runs, row):
    """A case's status from its rung runs ({tag: (outcome, exit, solved)}) and
    its readiness rung row (or None). Pure, so it is tested without a solver."""
    if any(outcome == "INFRA" for outcome, _, _ in runs.values()) or any(
        outcome == "EXITED"
        and code is not None
        and (code in DOCKER_START_FAILURES or code >= 128 or code < 0 or code == 120)
        for outcome, code, _ in runs.values()
    ):
        return "FAILED_INFRA", ["a rung's container could not start or was stopped"]
    if any(outcome == "TIMEOUT" for outcome, _, _ in runs.values()):
        return "REFERENCE_TIMEOUT", ["a rung exceeded the case timeout"]
    if any(code != 0 or not solved for _, code, solved in runs.values()):
        return "REFERENCE_SOLVER_FAILED", ["a rung ended in error or wrote no result"]
    if row is None or row.get("pass") is None:
        return "REFERENCE_SOLVER_FAILED", ["no rung comparison"]
    return ("OK", []) if row["pass"] else ("REFERENCE_INVALID", ["B1-B5 failed"])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f02_exam_runner")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--timeout-s", type=float, default=7200.0)
    parser.add_argument("--keep", choices=("none", "failed", "all"), default="none")
    args = parser.parse_args(argv)
    image = os.environ.get("CARBON_F02_IMAGE")
    if image != readiness.IMAGE:
        raise SystemExit("CARBON_F02_IMAGE must be the pinned F02 image")
    plan = json.loads(args.plan.read_text())
    cases = check_plan(plan)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    decks = out / "decks"
    if decks.exists():
        raise SystemExit(f"{decks} exists; refusing to overwrite")
    entries = build(cases, decks)
    runs = {}
    with ThreadPoolExecutor(max(1, args.parallel)) as pool:
        for entry, result in zip(
            entries,
            pool.map(lambda e: solve(e, decks, image, args.timeout_s), entries),
            strict=True,
        ):
            runs[entry["case"]] = result
    judgement = readiness.judge(decks, out / "judgement.json")
    records = out / "records.jsonl"
    for case in cases:
        cid = case["case_id"]
        rungs = {}
        for tag, _, _ in RUNGS:
            name = f"{cid}-{tag}"
            outcome, code, _wall = runs[name]
            solved = (readiness._solved_dir(decks, name) / "scalars.dat").is_file()
            rungs[tag] = (outcome, code, solved)
        row = judgement["rung_comparisons"].get(cid)
        status, reasons = classify(rungs, row)
        record = {
            "schema": RECORD_SCHEMA,
            "batch": plan["batch"],
            "case_id": cid,
            "kind": plan.get("kind"),
            "inputs": case["inputs"],
            "image": image,
            "status": status,
            "reasons": reasons,
            "wall_s": round(sum(runs[f"{cid}-{t}"][2] for t, _, _ in RUNGS), 1),
            "rungs": {
                t: {"outcome": o, "exit": c, "wall_s": round(runs[f"{cid}-{t}"][2], 3)}
                for t, (o, c, _) in rungs.items()
            },
        }
        if status in ("OK", "REFERENCE_INVALID"):
            primary = judgement["observables"][f"{cid}-primary"]
            # The development bank's record content (physical_pack._f02_bank),
            # so a sealed batch becomes a private pack in the same format.
            record["outputs"] = {k: primary[k] for k in OBSERVED}
            record["rung_peaks_c"] = {
                tag: judgement["observables"][f"{cid}-{tag}"]["peak_top_c"]
                for tag, _, _ in RUNGS
            }
            record["rung_comparison"] = row
        with records.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        keep = args.keep == "all" or (args.keep == "failed" and status != "OK")
        if not keep:
            for tag, _, _ in RUNGS:
                shutil.rmtree(decks / "f02" / f"{cid}-{tag}", ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
