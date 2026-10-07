"""Cooling improved-cell feasibility (#758 at 1ac5acfa). DEVELOPMENT.

    python -m scripts.dev.cold_plate.feasibility02 plan --out PLAN.json
    python -m scripts.dev.cold_plate.feasibility02 run PLAN.json --out DIR [--parallel 4]

The registered periodic-cell reference (`carbon.cold_plate.openfoam`, its
pinned image, checks and analysis) on #758's first straight-channel grammar:
channel width 0.2-1.0 mm, fin 0.2-0.5 mm, depth 3-6 mm, base 0.5-1.0 mm,
the 0.5 mm lid and 30 x 30 mm footprint kept. The registered module's bounds
and base thickness are widened for writing and analysing each case only,
one case at a time (`variant`); the registered Challenge is unchanged.

Each record adds the packet's thermal observer (round1 cooling packet
section 6): max over the heated face of T(x, y) + R_TIM q(x), with the
location of the maximum, and the cell's hydraulic power (dp x flow). The
cell has perfect flow distribution and no headers: a cell pass is
necessary, not sufficient, for the full plate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import analysis, domain, openfoam
from scripts.dev.cold_plate.reference import run_batch

GRAMMAR = {
    "channel_width_mm": (0.2, 1.0),
    "fin_width_mm": (0.2, 0.5),
    "channel_depth_mm": (3.0, 6.0),
    "base_mm": (0.5, 1.0),
}
WIDE_BOUNDS = {"channel_width_mm": (0.2, 1.0), "channel_depth_mm": (1.0, 6.0)}
#: The warm service strata (round1 cooling packet, section 3) at the
#: largest flow the 3 L/min cap allows at 1,500 W (2.0 L/min/kW).
STRATA = {
    "warm_uniform": {"inlet_c": 45.0, "heat_load_w": 1500.0, "hotspot_ratio": 1.0,
                     "hotspot_center_mm": 15.0, "hotspot_width_mm": 2.5, "flow": 1.0},
    "warm_central_hotspot": {"inlet_c": 45.0, "heat_load_w": 1500.0, "hotspot_ratio": 3.0,
                             "hotspot_center_mm": 15.0, "hotspot_width_mm": 2.5, "flow": 1.0},
    "warm_outlet_hotspot": {"inlet_c": 45.0, "heat_load_w": 1500.0, "hotspot_ratio": 3.0,
                            "hotspot_center_mm": 25.0, "hotspot_width_mm": 2.5, "flow": 1.0},
    "reduced_flow_outlet_hotspot": {"inlet_c": 45.0, "heat_load_w": 1500.0,
                                    "hotspot_ratio": 3.0, "hotspot_center_mm": 25.0,
                                    "hotspot_width_mm": 2.5, "flow": 0.625},
}  # fmt: skip
FLOW_LPM_PER_KW = 2.0


@contextmanager
def variant(base_mm):
    bounds, base = dict(domain.INPUT_BOUNDS), domain.FIXED["base_mm"]
    domain.INPUT_BOUNDS.update(WIDE_BOUNDS)
    domain.FIXED["base_mm"] = base_mm
    try:
        yield
    finally:
        domain.INPUT_BOUNDS.clear()
        domain.INPUT_BOUNDS.update(bounds)
        domain.FIXED["base_mm"] = base


def designs():
    """24 public uniform draws over the grammar, then 8 frozen corners that
    favour heat transfer (narrow, thin-finned, deep) at both base limits."""
    seed = int.from_bytes(hashlib.sha256(b"COOLING-FEAS02-CELL").digest()[:8], "big")
    rng = random.Random(seed)
    out = [
        {"design_id": f"u{i:02d}", **{k: rng.uniform(*v) for k, v in GRAMMAR.items()}}
        for i in range(24)
    ]
    i = 0
    for w in (0.2, 0.4):
        for f in (0.2, 0.35):
            for b in (0.5, 1.0):
                out.append(
                    {
                        "design_id": f"c{i}",
                        "channel_width_mm": w,
                        "fin_width_mm": f,
                        "channel_depth_mm": 6.0,
                        "base_mm": b,
                    }
                )
                i += 1
    return out


def plan(out):
    cases = []
    for d in designs():
        for name, s in STRATA.items():
            inputs = {
                "channel_width_mm": d["channel_width_mm"],
                "fin_width_mm": d["fin_width_mm"],
                "channel_depth_mm": d["channel_depth_mm"],
                "flow_lpm_per_kw": FLOW_LPM_PER_KW * s["flow"],
                **{k: v for k, v in s.items() if k != "flow"},
            }
            cases.append(
                {
                    "case_id": f"{d['design_id']}-{name}",
                    "design_id": d["design_id"],
                    "stratum": name,
                    "base_mm": d["base_mm"],
                    "inputs": inputs,
                }
            )
    document = {"batch": "cooling-feas02-cell", "pr": "#758 @ 1ac5acfa", "cases": cases}
    Path(out).write_text(json.dumps(document, indent=1) + "\n")
    return len(cases)


def tim_observer(case_dir, inputs):
    """max over heated-face cells of T + R_TIM q(x), and where it is."""
    times = sorted(
        (t for t in (case_dir / "times").read_text().split() if t != "0"), key=float
    )
    t = times[-1]
    cells = list(
        zip(
            analysis.internal_field(case_dir / t / "solid" / "C"),
            analysis.internal_field(case_dir / t / "solid" / "T"),
        )
    )
    k_s = domain.FIXED["copper_k_w_mk"]
    z0 = min(c[0][2] for c in cells)
    best = None
    for (x, y, z), temp in cells:
        if abs(z - z0) > 1e-12:
            continue
        q = domain.heat_flux(inputs, x * 1e3)
        face = temp + q * z0 / k_s
        value = face + domain.TIM_RESISTANCE_M2K_W * q
        if best is None or value > best[0]:
            best = (value, x, y, face)
    return {
        "tim_interface_peak_c": best[0] - domain.K0,
        "at_x_mm": best[1] * 1e3,
        "at_y_mm": best[2] * 1e3,
        "heated_face_c_there": best[3] - domain.K0,
    }


def run(plan_path, out, parallel, cpus, timeout_s):
    document = json.loads(Path(plan_path).read_text())
    out = Path(out)
    (out / "cases").mkdir(parents=True, exist_ok=True)
    records = out / "records.jsonl"
    done = set()
    if records.exists():
        done = {json.loads(x)["case_id"] for x in records.read_text().splitlines()}
    todo = [c for c in document["cases"] if c["case_id"] not in done]
    written = []
    for case in todo:  # one case at a time under the widened variant
        case_dir = out / "cases" / case["case_id"]
        if case_dir.exists():
            continue
        with variant(case["base_mm"]):
            openfoam.write_case(case["inputs"], case_dir)
        written.append(case)
    lock = threading.Lock()

    def one(case):
        case_dir = out / "cases" / case["case_id"]
        name = f"carbon-cfeas-{case['case_id']}"[:120]
        status, wall, detail = run_batch.solve(case_dir, name, cpus, timeout_s)
        with lock:
            record = {**case, "wall_s": round(wall, 1), "cpus": cpus, "run": detail}
            if status is None:
                with variant(case["base_mm"]):
                    result = analysis.analyze_case(case_dir)
                    status = result["outcome"]
                    record.update(
                        reasons=result["reasons"],
                        outputs=result.get("outputs"),
                        checks=result.get("checks"),
                        diagnostics=result.get("diagnostics"),
                        derived=result["case"]["derived"],
                        mesh=result["case"]["mesh"],
                    )
                    if result.get("outputs"):
                        record["observer"] = tim_observer(case_dir, case["inputs"])
                        dp = result["outputs"]["pressure_drop_pa"]
                        record["observer"]["hydraulic_power_w"] = (
                            dp * result["case"]["derived"]["flow_m3_s"]
                        )
            else:
                record["reasons"] = [detail]
            record.update(status=status, image=openfoam.IMAGE)
            with records.open("a") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
            print(case["case_id"], status, record["wall_s"], flush=True)

    with ThreadPoolExecutor(parallel) as pool:
        list(pool.map(one, written))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cooling feasibility02")
    parser.add_argument("command", choices=("plan", "run"))
    parser.add_argument("plan", type=Path, nargs="?")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--cpus", type=int, default=1)
    parser.add_argument("--timeout-s", type=int, default=14400)
    args = parser.parse_args(argv)
    if args.command == "plan":
        print(plan(args.out))
    else:
        run(args.plan, args.out, args.parallel, args.cpus, args.timeout_s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
