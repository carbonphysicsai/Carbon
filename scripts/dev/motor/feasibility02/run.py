"""Motor customer feasibility runner (#758 at 1ac5acfa). DEVELOPMENT.

    python -m scripts.dev.motor.feasibility02.run PLAN.json --out DIR [--parallel 8]

PLAN is {"batch", "cases": [{case_id, topology, design | geometry, j_a_mm2,
gamma_deg, options}]}. Each case meshes once (`mesh2.py`) and solves every
rotor position of its window in one container of the pinned motor reference
image, with the registered GetDP deck (`carbon.motor.getdp`) given this
topology's winding table. Records carry the full torque curve, co-energy,
the periodicity check, Newton convergence, the zero-current virtual-work
cross-check and resources. Outcomes: OK, REFERENCE_INVALID,
REFERENCE_SOLVER_FAILED, REFERENCE_TIMEOUT, FAILED_INFRA, INVALID_INPUT.
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

from carbon.motor import getdp
from scripts.dev.motor.feasibility02 import topology as tp

IMAGE = os.environ.get("CARBON_MOTOR_IMAGE", "carbon-motor-reference:main-75330721")
MESH = Path(__file__).with_name("mesh2.py")
SCHEMA = "carbon.motor.feasibility02-record.v1"
PERIODICITY_REL, PERIODICITY_FLOOR_NM = 1e-3, 1e-3
DEFAULTS = {"n_gap": 1440, "h_max": 1.0}


def window_deg(topology):
    """One loaded torque period: 360 / (6 p) mechanical degrees (12 for
    10p/12s, 15 for 8p/24s), which also holds whole cogging periods."""
    return 360.0 / (6 * topology["poles"] // 2)


def params(case):
    topology = tp.TOPOLOGIES[case["topology"]]
    options = {**DEFAULTS, **case.get("options", {})}
    g = case.get("geometry") or tp.geometry(topology, case["design"])
    n_gap = options["n_gap"]
    window = options.get("window_deg", window_deg(topology))
    steps_per = n_gap * window / 360.0
    if abs(steps_per - round(steps_per)) > 1e-9:
        raise ValueError("the window must be a whole number of gap steps")
    stride = options.get("stride", 1)
    steps = list(range(0, round(steps_per) + 1, stride))
    if "positions" in options:
        steps = steps[: options["positions"]]
    if case.get("geometry"):
        area = case["coil_area_mm2"]
    else:
        area = tp.coil_side_area_mm2(topology, case["design"])
    return {
        **g,
        "layers": topology["layers"],
        "n_gap": n_gap,
        "h_max": options["h_max"],
        "length": tp.FIXED["length"],
        "br": tp.FIXED["br"],
        "mur_m": tp.FIXED["mur_m"],
        "turns": 1,
        "coil_area_mm2": area,
        "current_a": case["j_a_mm2"] * area,
        "gamma_deg": case["gamma_deg"],
        "alpha0_deg": case.get("alpha0_deg", tp.current_offset_deg(topology)),
        "window_deg": window,
        "steps": steps,
        "iron": "brauer",
    }


def pro_text(p, table):
    original = getdp.winding
    getdp.winding = lambda slots, poles: table
    try:
        return getdp.pro_text({**p, "slots": len(table)}, nonlinear=getdp.BRAUER)
    finally:
        getdp.winding = original


def currents(p, k):
    theta = 2 * math.pi * k / p["n_gap"]
    base = p["poles"] // 2 * theta + math.radians(p["alpha0_deg"] + p["gamma_deg"])
    return [p["current_a"] * math.cos(base - m * 2 * math.pi / 3) for m in range(3)]


def solve(case_dir, p, name, cpus, timeout_s):
    calls = ["python3 mesh.py params.json . > log.mesh 2>&1"]
    for k in p["steps"]:
        ia, ib, ic = currents(p, k)
        calls.append(
            f"getdp machine.pro -msh rotor_{k}.msh -setnumber STEP {k}"
            f" -setnumber IA {ia!r} -setnumber IB {ib!r} -setnumber IC {ic!r}"
            f" -solve MagSta -pos MagSta -v 2 >> log.getdp 2>&1 && rm -f rotor_{k}.msh"
        )
    script = "set -e; " + "; ".join(calls[:1]) + "; " + " && ".join(calls[1:])
    command = [
        "docker", "run", "--rm", "--name", name, "--network", "none",
        "--cpus", str(cpus), "-e", "OMP_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{case_dir.resolve()}:/w", "-w", "/w", IMAGE, "bash", "-c", script,
    ]  # fmt: skip
    start = time.monotonic()
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
        return "REFERENCE_TIMEOUT", time.monotonic() - start, f"wall {timeout_s} s"
    except OSError as exc:
        return "FAILED_INFRA", time.monotonic() - start, f"docker: {exc}"
    wall = time.monotonic() - start
    if done.returncode in (125, 126, 127):
        return "FAILED_INFRA", wall, done.stderr.strip()[-2000:]
    return None, wall, f"exit {done.returncode}"


def _series(case_dir, p, name):
    out = []
    for k in p["steps"]:
        path = case_dir / "res" / f"{name}_{k}.txt"
        if not path.exists():
            return None
        out.append(float(path.read_text().split()[-1]))
    return out


def analyze(case_dir, p, j):
    torque = _series(case_dir, p, "torque")
    if torque is None:
        return None, ["missing torque"]
    coenergy = _series(case_dir, p, "coenergy")
    log = (case_dir / "log.getdp").read_text()
    not_converged = log.count("did NOT converge")
    reasons = []
    if not all(math.isfinite(t) for t in torque):
        reasons.append("non-finite torque")
    if not_converged:
        reasons.append(f"{not_converged} rotor positions did not converge")
    step_deg = 360.0 * (p["steps"][1] - p["steps"][0]) / p["n_gap"]
    full = abs(step_deg * (len(p["steps"]) - 1) - p["window_deg"]) < 1e-9
    periodicity, curve = None, torque
    if full:
        # The torque one period on must repeat within 1e-3 of the largest
        # |torque|, or within 1e-3 N m absolute for a near-zero (cogging)
        # curve, where exact-rotation meshes still differ by discretization.
        periodicity = abs(torque[-1] - torque[0])
        tolerance = max(
            PERIODICITY_REL * max(abs(t) for t in torque), PERIODICITY_FLOOR_NM
        )
        if periodicity > tolerance:
            reasons.append(f"periodicity {periodicity:.3g} N m > {tolerance:.3g}")
        curve = torque[:-1]
    checks = {"periodicity_abs_nm": periodicity, "not_converged": not_converged}
    if j == 0 and coenergy and len(coenergy) >= 3:
        # Zero current: torque = dW'/dtheta (virtual work), centred.
        h = math.radians(step_deg)
        vw = [
            (coenergy[i + 1] - coenergy[i - 1]) / (2 * h)
            for i in range(1, len(coenergy) - 1)
        ]
        checks["virtual_work_max_abs_diff_nm"] = max(
            abs(a - b) for a, b in zip(vw, torque[1:-1])
        )
    return {
        "outputs": {
            "torque_nm": curve,
            "angle_deg": [step_deg * i for i in range(len(curve))],
            "coenergy_j": coenergy[: len(curve)] if coenergy else None,
        },
        "derived": tp.metrics(curve),
        "checks": checks,
    }, reasons


def run_case(case, out, args, batch, lock):
    case_dir = out / "cases" / case["case_id"]
    record = {
        "schema": SCHEMA,
        "batch": batch,
        "pr": "#758 @ 1ac5acfa",
        **{k: case.get(k) for k in ("case_id", "topology", "design", "geometry")},
        "j_a_mm2": case["j_a_mm2"],
        "gamma_deg": case["gamma_deg"],
        "options": case.get("options", {}),
        "image": IMAGE,
    }
    topology = tp.TOPOLOGIES[case["topology"]]
    if case.get("design") and tp.validity(topology, case["design"]):
        record.update(
            status="INVALID_INPUT", reasons=tp.validity(topology, case["design"])
        )
        return _write(record, out, lock)
    try:
        p = params(case)
        (case_dir / "res").mkdir(parents=True)
        shutil.copy(MESH, case_dir / "mesh.py")
        (case_dir / "params.json").write_text(json.dumps(p, indent=1))
        (case_dir / "machine.pro").write_text(pro_text(p, tp.winding_table(topology)))
    except (OSError, ValueError, TypeError) as exc:
        record.update(status="FAILED_INFRA", reasons=[f"case not written: {exc}"])
        return _write(record, out, lock)
    record["alpha0_deg"] = p["alpha0_deg"]
    record["coil_area_mm2"] = p["coil_area_mm2"]
    name = f"carbon-mfeas-{case['case_id']}"[:120]
    started = time.time()
    status, wall, detail = solve(case_dir, p, name, args.cpus, args.timeout_s)
    record.update(
        wall_s=round(wall, 1),
        cpus=args.cpus,
        positions=len(p["steps"]),
        started_unix=round(started),
        run=detail,
    )
    if status is None:
        result, reasons = analyze(case_dir, p, case["j_a_mm2"])
        if result is None:
            status = "REFERENCE_SOLVER_FAILED"
        else:
            status = "REFERENCE_INVALID" if reasons else "OK"
            record.update(result)
        record["reasons"] = reasons
    else:
        record["reasons"] = [detail]
    record["status"] = status
    mesh = case_dir / "mesh.json"
    if mesh.exists():
        m = json.loads(mesh.read_text())
        record["mesh"] = m["steps"].get("0")
        record["mesh_areas_mm2"] = m.get("areas")
    for f in case_dir.glob("rotor_*.msh"):
        f.unlink()
    return _write(record, out, lock)


def _write(record, out, lock):
    with lock, (out / "records.jsonl").open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(record["case_id"], record["status"], record.get("wall_s"), flush=True)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(prog="feasibility02.run")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--cpus", type=int, default=2)
    parser.add_argument("--timeout-s", type=int, default=14400)
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    done = set()
    if (args.out / "records.jsonl").exists():
        done = {
            json.loads(x)["case_id"]
            for x in (args.out / "records.jsonl").read_text().splitlines()
            if x.strip()
        }
    todo = [c for c in plan["cases"] if c["case_id"] not in done]
    for c in todo:
        stale = args.out / "cases" / c["case_id"]
        if stale.exists():
            shutil.rmtree(stale)
    lock = threading.Lock()
    with ThreadPoolExecutor(args.parallel) as pool:
        list(pool.map(lambda c: run_case(c, args.out, args, plan["batch"], lock), todo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
