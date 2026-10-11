"""f02 feature proof: the packet's four controls on the pinned Elmer image.

    python -m scripts.dev.reference_packages.elmer.f02_controls run --image ID --out DIR

1. equilibrium: zero source, starting at the coolant temperature; drift
   <= 0.05 C over 120 s.
2. slab step: the copper slab alone, 110 W stepped on at t = 0 over its whole
   top, Robin 2,500 W/m2K at 30 C below; top-centre rise against the exact
   series, error <= max(0.25 C, 1 % of the rise) at every 0.5 s sample.
3. slab pulse: the same slab with 20 W base and a 110 W, 5 s rectangle at
   20 s (superposed exact steps), same tolerance.
4. energy: the full stack, 110 W constant split 50/50; (in - stored - out)
   / in within 1 %.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.reference_packages.elmer import f02_deck as fd

COOL = {
    "coolant_c": 30.0,
    "h_w_m2_k": 2500.0,
    "initial_c": 30.0,
    "left_source_fraction": 0.5,
}
CONTROLS = {
    "equilibrium": (
        {**COOL, "waveform": "constant", "peak_w": 0.0, "on_time_s": 0.0},
        {"source": False},
    ),
    "slab_step": (
        {**COOL, "waveform": "constant", "peak_w": 110.0, "on_time_s": 0.0},
        {"slab": True},
    ),
    "slab_pulse": (
        {**COOL, "waveform": "rectangular", "peak_w": 110.0, "on_time_s": 5.0},
        {"slab": True},
    ),
    "energy": ({**COOL, "waveform": "constant", "peak_w": 110.0, "on_time_s": 0.0}, {}),
}


def run_elmer(image, case_dir, timeout_s=7200):
    cmd = [
        "docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp",
        "--cpus", "1", "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{Path(case_dir).resolve()}:/case", image,
        "bash", "-c", "ElmerSolver case.sif > solver.log 2>&1",
    ]  # fmt: skip
    start = time.monotonic()
    done = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout_s, check=False
    )
    return done.returncode, time.monotonic() - start


def _slab_reference(name, t):
    area = (2 * fd.LAYERS["copper"][0] * fd.MM) ** 2
    q = lambda w: w / area
    if name == "slab_step":
        return fd.slab_top_rise(q(110.0), 2500.0, t)
    return (
        fd.slab_top_rise(q(20.0), 2500.0, t)
        + fd.slab_top_rise(q(90.0), 2500.0, t - 20.0)
        - fd.slab_top_rise(q(90.0), 2500.0, t - 25.0)
    )


def score(name, case_dir):
    cols, rows = fd.read_scalars(case_dir)
    if name == "equilibrium":
        i_top = next(i for i, c in enumerate(cols) if c.startswith("boundary max"))
        drift = max(abs(r[i_top] - 303.15) for r in rows)
        return {"max_drift_c": drift, "pass": drift <= 0.05}
    if name == "energy":
        e = fd.energy_balance(case_dir)
        return {**e, "pass": abs(e["residual_rel"]) <= 0.01}
    i_pt = next(
        i for i, c in enumerate(cols) if c.startswith("value: temperature at node")
    )
    worst, worst_at, peak_rise = 0.0, None, 0.0
    for r in rows:
        t = r[0]
        if abs(t * 2 - round(t * 2)) > 1e-6:
            continue
        rise = r[i_pt] - 303.15
        exact = _slab_reference(name, t)
        peak_rise = max(peak_rise, exact)
        err = abs(rise - exact)
        if err > worst:
            worst, worst_at = err, t
    tolerance = max(0.25, 0.01 * peak_rise)
    return {"max_error_c": worst, "at_s": worst_at, "peak_rise_c": peak_rise,
            "tolerance_c": tolerance, "pass": worst <= tolerance}  # fmt: skip


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f02_controls")
    parser.add_argument("command", choices=("run",))
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    results = {}
    for name, (case, opts) in CONTROLS.items():
        case_dir = args.out / name
        if not (case_dir / "scalars.dat").exists():
            fd.write_case(case, case_dir, **opts)
            code, wall = run_elmer(args.image, case_dir)
        else:
            code, wall = 0, None
        results[name] = {
            "exit": code,
            "wall_s": wall,
            **(score(name, case_dir) if code == 0 else {"pass": False}),
        }
        print(name, json.dumps(results[name]), flush=True)
    (args.out / "controls.json").write_text(json.dumps(results, indent=1) + "\n")
    return 0 if all(r["pass"] for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
