"""Run one motor reference sweep: mesh once, solve every rotor step.

    python scripts/dev/motor/reference/run_sweep.py CASE.json OUTDIR

CASE.json holds the machine parameters (`carbon.motor.mesh`'s, in mm), plus:
- `length` (mm), `br` (T), `mur_m`, `mur_fe`, `turns` (per slot);
- `current_a` (amplitude) and `gamma_deg` (current angle; 0 puts the stator
  field 90 electrical degrees ahead of the rotor's d-axis);
- `steps`: the rotor steps to solve, each 360/n_gap mechanical degrees.

At step k (rotor angle theta = 2 pi k / n_gap) phase m in (A, B, C) carries
I cos(p theta - 120 deg + gamma - m 120 deg), p the pole pairs: the stator field
turns with the rotor. Writes `sweep.json` with each step's Maxwell-stress
torque, co-energy and phase flux linkages, and the run's cost.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.motor import getdp

IMAGE = os.environ.get("CARBON_MOTOR_IMAGE", "carbon-motor-reference:dev")
MESH = ROOT / "carbon" / "motor" / "mesh.py"


def currents(case, k):
    """Phase currents at step k, or at `current_step` for every step when the
    case sets it: currents frozen while the rotor moves, which is what the
    virtual-work torque dW'/dtheta needs."""
    k = case.get("current_step", k)
    theta = 2 * math.pi * k / case["n_gap"]
    pairs = case["poles"] // 2
    base = pairs * theta + math.radians(-120.0 + case["gamma_deg"])
    return [case["current_a"] * math.cos(base - m * 2 * math.pi / 3) for m in range(3)]


def docker(out, script, cpus=2):
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        str(cpus),
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{out.resolve()}:/w",
        "-w",
        "/w",
        IMAGE,
        "bash",
        "-c",
        script,
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def main(argv):
    case_path, outdir = Path(argv[0]), Path(argv[1])
    case = json.loads(case_path.read_text())
    if outdir.exists():
        raise SystemExit(f"{outdir} exists; refusing to overwrite")
    (outdir / "res").mkdir(parents=True)
    shutil.copy(MESH, outdir / "mesh.py")
    (outdir / "params.json").write_text(json.dumps(case, indent=1))
    start = time.monotonic()
    done = docker(outdir, "python3 mesh.py params.json . > log.mesh 2>&1")
    if done.returncode != 0:
        raise SystemExit("meshing failed: " + (outdir / "log.mesh").read_text()[-2000:])
    mesh_s = time.monotonic() - start
    record = json.loads((outdir / "mesh.json").read_text())
    params = {**case, "coil_area_mm2": record["areas"][str(getdp.REGIONS["coil0"])]}
    law = getdp.BRAUER if case.get("iron") == "brauer" else None
    (outdir / "machine.pro").write_text(getdp.pro_text(params, nonlinear=law))
    calls = []
    for k in case["steps"]:
        ia, ib, ic = currents(case, k)
        calls.append(
            f"getdp machine.pro -msh rotor_{k}.msh -setnumber STEP {k}"
            f" -setnumber IA {ia!r} -setnumber IB {ib!r} -setnumber IC {ic!r}"
            f" -solve MagSta -pos MagSta -v 2 >> log.getdp 2>&1"
        )
    start = time.monotonic()
    done = docker(outdir, " && ".join(calls))
    solve_s = time.monotonic() - start
    if done.returncode != 0:
        raise SystemExit("solve failed: " + (outdir / "log.getdp").read_text()[-3000:])

    def value(name, k):
        rows = (outdir / "res" / f"{name}_{k}.txt").read_text().split()
        return float(rows[-1])

    table = getdp.winding(case["slots"], case["poles"])
    area = params["coil_area_mm2"] * 1e-6
    steps = []
    for k in case["steps"]:
        coil = [
            float(line.split()[-1])
            for line in (outdir / "res" / f"coil_a_{k}.txt").read_text().splitlines()
            if line.strip()
        ]
        flux = {"A": 0.0, "B": 0.0, "C": 0.0}
        for (phase, sign), integral in zip(table, coil):
            flux[phase] += (
                sign * case["turns"] * case["length"] * 1e-3 * integral / area
            )
        steps.append(
            {
                "step": k,
                "angle_deg": 360.0 * k / case["n_gap"],
                "currents_a": currents(case, k),
                "torque_nm": value("torque", k),
                "coenergy_j": value("coenergy", k),
                "flux_linkage_wb": flux,
            }
        )
    result = {
        "case": case,
        "mesh": record,
        "cost": {"mesh_s": round(mesh_s, 2), "solve_s": round(solve_s, 2)},
        "steps": steps,
    }
    (outdir / "sweep.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result["cost"]))


if __name__ == "__main__":
    main(sys.argv[1:])
