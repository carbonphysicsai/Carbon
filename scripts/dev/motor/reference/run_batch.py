"""Run a batch of motor reference cases; every case ends as a typed record.

    python scripts/dev/motor/reference/run_batch.py PLAN.json --out DIR
        [--parallel 8] [--timeout-s 7200] [--keep all|failed|none]

PLAN.json is {"batch": NAME, "cases": [{"case_id", "kind", "inputs",
"options"?}]}; `inputs` are the eight Challenge inputs (`carbon.motor.domain`)
and `options` may set `n_gap` (a multiple of 1,440 keeps the angles) for a
refinement.

Each case meshes once and solves `ANGLE_STEPS + 1` rotor positions over one
15 degree period in one container: the pinned image, no network, two CPUs, a
hard wall limit (the case's own container is killed by name on timeout). The
extra position, at 15 degrees, is the periodicity check. Outcomes are the
readiness record's:

- `OK`: every position's Newton loop converged, the torque is finite, and
  the torque at 15 degrees repeats the torque at 0 within REFERENCE_CHECKS;
- `REFERENCE_INVALID`: the solve ran but a check failed;
- `REFERENCE_SOLVER_FAILED`: no readable torque;
- `REFERENCE_TIMEOUT`, `FAILED_INFRA`: as for the cold plate.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.motor import domain, getdp

IMAGE = os.environ.get("CARBON_MOTOR_IMAGE", "carbon-motor-reference:dev")
MESH = ROOT / "carbon" / "motor" / "mesh.py"
RECORD_SCHEMA = "carbon.motor.reference-record.v1"
#: Reference numerical checks, provisional DEVELOPMENT values: the torque at
#: 15 degrees must repeat the torque at 0 within this fraction of the
#: largest |torque| (rung M1 saw 1e-5 under load, 2e-6 in cogging), with a
#: floor of 1e-3 N m for near-zero torque curves.
REFERENCE_CHECKS = {"periodicity_rel": 1e-3, "periodicity_floor_nm": 1e-3}
DOCKER_START_FAILURES = {125, 126, 127}


def case_params(inputs, options):
    g = domain.geometry(inputs)
    n_gap = options.get("n_gap", domain.N_GAP)
    angle_steps = options.get("angle_steps", domain.ANGLE_STEPS)
    # Airgap nodes in one 15 degree period, and nodes per rotor position.
    period_nodes = n_gap * domain.PERIOD_DEG / 360.0
    if period_nodes != int(period_nodes) or int(period_nodes) % angle_steps:
        raise ValueError("the period must hold a whole number of positions")
    per = int(period_nodes) // angle_steps
    steps = [k * per for k in range(angle_steps + 1)]
    # A window of the first `positions` positions (a refinement study's
    # subset); it does not reach 15 degrees, so it has no periodicity check.
    if "positions" in options:
        steps = steps[: options["positions"]]
    f = domain.FIXED
    return {
        **g,
        "n_gap": n_gap,
        "h_max": options.get("h_max", g["h_max"]),
        "length": f["length"],
        "br": f["br"],
        "mur_m": f["mur_m"],
        "turns": f["turns"],
        "current_a": domain.current_amplitude_a(inputs),
        "gamma_deg": inputs["current_angle_deg"],
        "iron": "brauer",
        "steps": steps,
    }


def currents(p, k):
    theta = 2 * math.pi * k / p["n_gap"]
    base = p["poles"] // 2 * theta + math.radians(-120.0 + p["gamma_deg"])
    return [p["current_a"] * math.cos(base - m * 2 * math.pi / 3) for m in range(3)]


def solve(case_dir, p, name, cpus, timeout_s):
    calls = ["python3 mesh.py params.json . > log.mesh 2>&1"]
    for k in p["steps"]:
        ia, ib, ic = currents(p, k)
        calls.append(
            f"getdp machine.pro -msh rotor_{k}.msh -setnumber STEP {k}"
            f" -setnumber IA {ia!r} -setnumber IB {ib!r} -setnumber IC {ic!r}"
            f" -solve MagSta -pos MagSta -v 2 >> log.getdp 2>&1"
        )
    script = "set -e; " + "; ".join(calls[:1]) + "; " + " && ".join(calls[1:])
    # One BLAS/OpenMP thread: GetDP's OpenBLAS otherwise starts a thread per
    # host CPU inside a two-CPU container; under load a rotor position took
    # 3.2x longer (53.8 s against 16.7 s, measured during the pilot).
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
        "-e",
        "OMP_NUM_THREADS=1",
        "-e",
        "OPENBLAS_NUM_THREADS=1",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{case_dir.resolve()}:/w",
        "-w",
        "/w",
        IMAGE,
        "bash",
        "-c",
        script,
    ]
    start = time.monotonic()
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
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


def analyze(case_dir, p):
    torque = []
    for k in p["steps"]:
        path = case_dir / "res" / f"torque_{k}.txt"
        if not path.exists():
            return None, [f"no torque at step {k}"]
        torque.append(float(path.read_text().split()[-1]))
    log = (case_dir / "log.getdp").read_text()
    not_converged = log.count("did NOT converge")
    reasons = []
    if not all(math.isfinite(t) for t in torque):
        reasons.append("non-finite torque")
    if not_converged:
        reasons.append(f"{not_converged} rotor positions did not converge")
    full_period = abs(360.0 * p["steps"][-1] / p["n_gap"] - domain.PERIOD_DEG) < 1e-9
    periodicity = None
    curve = torque
    if full_period:
        scale = max(
            max(abs(t) for t in torque), REFERENCE_CHECKS["periodicity_floor_nm"]
        )
        periodicity = abs(torque[-1] - torque[0]) / scale
        if not periodicity <= REFERENCE_CHECKS["periodicity_rel"]:
            reasons.append(
                f"periodicity {periodicity:.3g} exceeds"
                f" {REFERENCE_CHECKS['periodicity_rel']:g}"
            )
        curve = torque[:-1]
    return {
        "outputs": {"torque_nm": curve},
        "derived": {
            "mean_nm": sum(curve) / len(curve),
            "ripple_pk_pk_nm": max(curve) - min(curve),
        },
        "checks": {"periodicity_rel": periodicity, "not_converged": not_converged},
    }, reasons


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
        if domain.validity(entry["inputs"]):
            raise ValueError("; ".join(domain.validity(entry["inputs"])))
        p = case_params(entry["inputs"], entry.get("options", {}))
        (case_dir / "res").mkdir(parents=True)
        shutil.copy(MESH, case_dir / "mesh.py")
        (case_dir / "params.json").write_text(json.dumps(p, indent=1))
        p_pro = {**p, "coil_area_mm2": domain.coil_area_mm2(entry["inputs"])}
        (case_dir / "machine.pro").write_text(
            getdp.pro_text(p_pro, nonlinear=getdp.BRAUER)
        )
    except FileExistsError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        record.update(status="FAILED_INFRA", reasons=[f"case not written: {exc}"])
        return _finish(record, out, lock, None, args)
    name = f"carbon-motor-{batch}-{case_id}"[:120]
    status, wall, detail = solve(case_dir, p, name, args.cpus, args.timeout_s)
    record.update(wall_s=round(wall, 1), run=detail, image=IMAGE)
    if status is not None:
        record.update(status=status, reasons=[detail])
        return _finish(record, out, lock, case_dir, args)
    result, reasons = analyze(case_dir, p)
    if result is None:
        record.update(status="REFERENCE_SOLVER_FAILED", reasons=reasons)
    else:
        record.update(
            status="REFERENCE_INVALID" if reasons else "OK", reasons=reasons, **result
        )
    mesh = case_dir / "mesh.json"
    if mesh.exists():
        record["mesh"] = json.loads(mesh.read_text())["steps"]["0"]
    return _finish(record, out, lock, case_dir, args)


def _finish(record, out, lock, case_dir, args):
    keep = args.keep == "all" or (args.keep == "failed" and record["status"] != "OK")
    if case_dir is not None and case_dir.exists() and not keep:
        shutil.rmtree(case_dir)
    elif case_dir is not None and case_dir.exists():
        for msh in case_dir.glob("rotor_*.msh"):
            msh.unlink()  # 60 meshes per case; mesh.py rebuilds them exactly
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
        f"{record['case_id']}: {record['status']} {record.get('wall_s', '-')} s "
        f"{'; '.join(record.get('reasons', []))}",
        flush=True,
    )
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=8)
    parser.add_argument("--cpus", type=float, default=2.0)
    parser.add_argument("--timeout-s", type=float, default=7200.0)
    parser.add_argument("--keep", choices=("all", "failed", "none"), default="all")
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text())
    ids = [c["case_id"] for c in plan["cases"]]
    if len(ids) != len(set(ids)):
        parser.error("case ids must be unique")
    args.out.mkdir(parents=True, exist_ok=True)
    args.out.chmod(0o700)
    if any((args.out / "cases" / i).exists() for i in ids):
        parser.error("a case directory exists; refusing to overwrite")
    (args.out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    lock = threading.Lock()
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        records = list(
            pool.map(
                lambda c: run_case(c, args.out, args, plan["batch"], lock),
                plan["cases"],
            )
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
