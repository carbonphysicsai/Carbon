"""F08's reference runner under the family contract (OWNER-F02-F08-EXAM-DRAW-01).

    CARBON_F08_SOLVERS=<id> CARBON_F08_NATIVE_GMSH=1 python3 f08_exam_runner.py \\
        PLAN --out DIR [--parallel N] [--timeout-s S] [--keep none|failed|all]

PLAN is {"batch", "kind", "cases": [{"case_id", "inputs": {the six lattice
inputs}}]}. Each case is solved as the 1.1/1.2 exam ladder's references were
(RR-PACKS-07, `f08_near_feasible`): decks at h = 3, 2.25 and 1.7 mm written by
`f08_deck.write_case` (48 modes, the bank command), solved natively by
`bulk_run.run_native` with RR-PACKS-07's per-case limits (one pinned core,
9 GiB resident), observed by `f08_deck.observe` and judged by
`f08_deck.convergence` (V1-V9 under F08-SCIENCE-VALUES-01, unchanged). The
reference rung is h = 1.7 mm.

The solver identity is RR-PACKS-07's verified build: the ccx and gmsh binaries'
SHA-256 in `rr07-pod-environment.json` (pinned here by its own SHA-256), whose
f08_verify (MMS and rod) passed in that run. The runner refuses a host whose
binaries differ, so a rebuilt solver needs its own verification first.

One record per case in DIR/records.jsonl, statuses:
- OK: every rung solved, every rung comparison PASS, asymptotic, and the
  reference rung's mode ladder PASS;
- REFERENCE_INVALID: every rung solved and observed, a verdict fails;
- REFERENCE_SOLVER_FAILED: a rung ended in error, wrote no output, or its
  output could not be observed;
- REFERENCE_TIMEOUT: a rung exceeded the case timeout;
- FAILED_INFRA (not terminal, so the family retries): a rung could not start,
  was stopped from outside, or passed the resident-memory limit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for path in (HERE, HERE.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

RECORD_SCHEMA = "carbon.f08.exam-reference-record.v1"
INPUTS = (
    "length_mm",
    "width_mm",
    "thickness_mm",
    "rib_height_mm",
    "rib_thickness_mm",
    "relief_length_mm",
)
RUNGS = (3.0, 2.25, 1.7)
REFERENCE_RUNG = 1.7
MODES = 48
MEMORY_BYTES = 9 * 2**30  # RR-PACKS-07's f08 case limit
ENVIRONMENT = (
    "docs/development/evidence/f08-near-limit-public-20261020/rr07-pod-environment.json",
    "5c16f95d2c5db972d50757e493f0218ce5a7c50adb52764d4e4449d053cac463",
)
REGISTRATION = (
    "docs/development/challenge_pipeline/structures-readiness/registration.json"
)
TERMINAL = ("OK", "REFERENCE_INVALID", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")
OBSERVED = (
    "static_tip_mm_per_n",
    "worst_dynamic_mm_per_n",
    "mass_kg",
    "cad_mass_kg",
    "modes",
    "mode_ladder",
    "in_band_modes_hz",
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def pinned_solvers():
    """RR-PACKS-07's verified native solvers ({kind, solvers}), from the
    SHA-256-pinned environment record."""
    raw = (ROOT / ENVIRONMENT[0]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ENVIRONMENT[1]:
        raise SystemExit("the pinned F08 environment record differs")
    environment = json.loads(raw)
    return {"kind": environment["kind"], "solvers": environment["solvers"]}


def solvers_id(solvers=None):
    """The family's image identity: the digest of the pinned solver binaries."""
    return (
        "sha256:" + hashlib.sha256(_canonical(solvers or pinned_solvers())).hexdigest()
    )


def check_host(solvers):
    """Every pinned binary is present on this host with its pinned SHA-256."""
    for name, pin in solvers["solvers"].items():
        path = Path(pin["path"])
        if not path.is_file():
            raise SystemExit(f"{name} is not at its pinned path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
            raise SystemExit(f"{name} differs from the verified build")


def check_plan(plan):
    from carbon.challenge_pipeline import structures_readiness as s

    registration = json.loads((ROOT / REGISTRATION).read_text(encoding="utf-8"))
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
        try:
            s.action(registration, dict(inputs))
        except ValueError:
            raise SystemExit("plan: a case is not a valid lattice geometry") from None
        seen.add(case["case_id"])
    return cases


def rung_name(case_id, h):
    return f"{case_id}-h{h:g}"


def build(cases, decks):
    """Three frozen rung decks per case; {rung name: (case_id, h, files)}."""
    import f08_deck as deck
    import f08_freeze as freeze_mod

    built = {}
    for case in cases:
        action = {name: float(case["inputs"][name]) for name in INPUTS}
        for h in RUNGS:
            name = rung_name(case["case_id"], h)
            directory = decks / "f08" / name
            deck.write_case(action, directory, h, MODES)
            built[name] = (case["case_id"], h, freeze_mod._digest(directory))
    return built


def solve(directory, timeout_s, cores):
    """One rung, as RR-PACKS-07's native bulk executor ran it. Returns its
    run_native result, or {"stop_reason": "infra"} if it could not start."""
    import bulk_run
    import f08_deck as deck

    core = cores.get()
    try:
        with (
            (directory / "run.out").open("wb") as out,
            (directory / "run.err").open("wb") as err,
        ):
            return bulk_run.run_native(
                ["bash", "-c", deck.BANK_COMMAND],
                directory,
                bulk_run.native_env({}, directory),
                timeout_s,
                threading.Event(),
                rss_limit_bytes=MEMORY_BYTES,
                cpus={core},
                stdout=out,
                stderr=err,
            )
    except OSError:
        return {"stop_reason": "infra", "exit": None, "wall_s": 0.0}
    finally:
        cores.put(core)


def classify(runs, observed, verdict):
    """A case's status from its rung runs ({h: run_native result}), observations
    ({h: observed or None}) and convergence verdict (or None). Pure."""
    reasons = {run.get("stop_reason") for run in runs.values()}
    if reasons & {"infra", "cancel", "memory"} or any(
        run.get("stop_reason") == "exit"
        and run.get("exit") is not None
        and (run["exit"] == 120 or run["exit"] >= 128 or run["exit"] < 0)
        for run in runs.values()
    ):
        return "FAILED_INFRA", ["a rung could not start, was stopped or passed memory"]
    if "timeout" in reasons:
        return "REFERENCE_TIMEOUT", ["a rung exceeded the case timeout"]
    if any(run.get("exit") != 0 for run in runs.values()):
        return "REFERENCE_SOLVER_FAILED", ["a rung ended in error"]
    if any(observed.get(h) is None for h in RUNGS) or verdict is None:
        return "REFERENCE_SOLVER_FAILED", ["a rung wrote no observable output"]
    passed = (
        verdict.get("asymptotic_ok") is True
        and all(r.get("verdict") == "PASS" for r in verdict.get("rungs", {}).values())
        and len(verdict.get("rungs", {})) == len(RUNGS) - 1
        and observed[REFERENCE_RUNG]["mode_ladder"]["verdict"] == "PASS"
    )
    return ("OK", []) if passed else ("REFERENCE_INVALID", ["a V1-V9 verdict failed"])


def _observe(directory):
    import f08_deck as deck

    if not (directory / "case.dat").is_file():
        return None
    try:
        return deck.observe(directory)
    except (KeyError, IndexError, ValueError):
        return None


def record_for(plan, case, runs, observed, verdict, image, solvers):
    cid = case["case_id"]
    status, reasons = classify(runs, observed, verdict)
    record = {
        "schema": RECORD_SCHEMA,
        "batch": plan["batch"],
        "case_id": cid,
        "kind": plan.get("kind"),
        "inputs": case["inputs"],
        "image": image,
        "status": status,
        "reasons": reasons,
        "rungs": {
            f"h{h:g}": {
                "stop_reason": runs[h].get("stop_reason"),
                "exit": runs[h].get("exit"),
                "wall_s": runs[h].get("wall_s"),
                "rusage_cpu_s": runs[h].get("rusage_cpu_s"),
                "sampled_group_rss_peak_bytes": runs[h].get(
                    "sampled_group_rss_peak_bytes"
                ),
            }
            for h in RUNGS
        },
    }
    if status in ("OK", "REFERENCE_INVALID"):
        reference = observed[REFERENCE_RUNG]
        record["solvers"] = solvers
        record["reference_rung_h_mm"] = REFERENCE_RUNG
        record["outputs"] = {k: reference[k] for k in OBSERVED}
        record["damping"] = {
            zeta: {k: values[k] for k in ("worst_mm_per_n", "worst_hz")}
            for zeta, values in reference["damping"].items()
        }
        record["rung_worst_dynamic_mm_per_n"] = {
            f"h{h:g}": observed[h]["worst_dynamic_mm_per_n"] for h in RUNGS
        }
        record["convergence"] = verdict
    return record


def main(argv=None):
    import f08_deck as deck

    parser = argparse.ArgumentParser(prog="f08_exam_runner")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--timeout-s", type=float, default=5400.0)
    parser.add_argument("--keep", choices=("none", "failed", "all"), default="none")
    args = parser.parse_args(argv)
    solvers = pinned_solvers()
    image = os.environ.get("CARBON_F08_SOLVERS")
    if image != solvers_id(solvers):
        raise SystemExit("CARBON_F08_SOLVERS must be the pinned F08 solver identity")
    if os.environ.get("CARBON_F08_NATIVE_GMSH") != "1":
        raise SystemExit("CARBON_F08_NATIVE_GMSH=1 is required (the verified build)")
    check_host(solvers)
    plan = json.loads(args.plan.read_text())
    cases = check_plan(plan)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    decks = out / "decks"
    if decks.exists():
        raise SystemExit(f"{decks} exists; refusing to overwrite")
    built = build(cases, decks)
    cores = queue.Queue()
    available = sorted(os.sched_getaffinity(0))
    for core in available[: max(1, min(args.parallel, len(available)))]:
        cores.put(core)
    names = list(built)
    with ThreadPoolExecutor(cores.qsize()) as pool:
        results = dict(
            zip(
                names,
                pool.map(
                    lambda n: solve(decks / "f08" / n, args.timeout_s, cores), names
                ),
                strict=True,
            )
        )
    lock = threading.Lock()
    records = out / "records.jsonl"
    for case in cases:
        cid = case["case_id"]
        runs = {h: results[rung_name(cid, h)] for h in RUNGS}
        observed = {h: _observe(decks / "f08" / rung_name(cid, h)) for h in RUNGS}
        verdict = None
        if all(observed[h] is not None for h in RUNGS):
            try:
                verdict = deck.convergence(observed)
            except (KeyError, IndexError, ValueError):
                verdict = None
        record = record_for(plan, case, runs, observed, verdict, image, solvers)
        with lock, records.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        keep = args.keep == "all" or (
            args.keep == "failed" and record["status"] != "OK"
        )
        if not keep:
            for h in RUNGS:
                shutil.rmtree(decks / "f08" / rung_name(cid, h), ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
