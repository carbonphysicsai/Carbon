"""f13 power-balance diagnosis (Test Lead 2026-10-08, overnight item 4).

    python3 f13_power_probe.py OUTDIR EVIDENCE.json [--parallel N]

The #787 triage found a power residual up to 4.7 % on the offset-neck
nominal geometry (straight duct and coaxial cases <= 0.34 %). Hypothesis:
the offset neck excites non-planar content that is evanescent in the 25 mm
port (decay length about 14-17 mm over 500-2500 Hz) but not yet decayed at
the 10 mm port stub. That content (a) meets a plane-wave impedance condition
that is only exact for plane waves and (b) adds |p|^2 to the transmitted
integral without carrying power. Test: the offset geometries and a coaxial
control at stubs 10 and 60 mm, a 50 Hz scan on the 8 mm mesh, reporting the
residual with the |p|^2 observer and with the plane-wave (mean-pressure)
observer. Diagnosis only; local free CPU at reduced shares.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f13_deck as deck

ELMER = "sha256:8bcd864dd60be0a80be9769c1a95c67db76eca9e718212f63dd0460cf3a08fc6"
LABELS = ("nominal", "large-offset", "clearance-boundary", "small-coaxial")
STUBS = (10.0, 60.0)
SOLVE = (
    "ElmerGrid 14 2 mesh.msh -autoclean -out mesh > grid.log 2>&1 && "
    "ElmerSolver case.sif > solver.log 2>&1; rc=$?; times > times.txt; exit $rc"
)


def _docker(image, workdir, command, cpus="1"):
    return subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--cpus", cpus, "--cpu-shares", "512",
         "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{Path(workdir).resolve()}:/w", "-w", "/w",
         image, "bash", "-c", command],
        capture_output=True, text=True, check=False,
    )  # fmt: skip


def one(out, label, stub):
    d = Path(out) / f"{label}-stub{stub:g}"
    deck.write_case(deck.panel_case(label), d, h_mm=8.0, step_hz=50.0, stub_mm=stub)
    t0 = time.monotonic()
    mesh = _docker(deck.MESH_IMAGE, d, "python3 make_mesh.py")
    solve = _docker(ELMER, d, SOLVE) if mesh.returncode == 0 else mesh
    wall = time.monotonic() - t0
    if solve.returncode != 0:
        return {
            "label": label,
            "stub_mm": stub,
            "status": "FAILED",
            "wall_s": round(wall, 1),
        }
    rows = deck.observe(d)
    worst = max(rows, key=lambda r: abs(r["residual"]))
    worst_plane = max(rows, key=lambda r: abs(r["residual_plane"]))
    times = (d / "times.txt").read_text().split("\n")
    return {"label": label, "stub_mm": stub, "status": "OK", "wall_s": round(wall, 1),
            "children_cpu": times[1].strip() if len(times) > 1 else None,
            "nodes": json.loads((d / "groups.json").read_text())["nodes"], "frequencies": len(rows),
            "max_abs_residual": abs(worst["residual"]), "at_hz": worst["f_hz"],
            "max_abs_residual_plane": abs(worst_plane["residual_plane"]), "plane_at_hz": worst_plane["f_hz"],
            "curve": [{k: r[k] for k in ("f_hz", "residual", "residual_plane", "tl_db")} for r in rows]}  # fmt: skip


def main(out, evidence, parallel=3):
    jobs = [(label, stub) for label in LABELS for stub in STUBS]
    with ThreadPoolExecutor(parallel) as pool:
        rows = list(pool.map(lambda j: one(out, *j), jobs))
    doc = {"schema": "carbon.f13-power-probe.v1", "image": ELMER, "mesh_image": deck.MESH_IMAGE,
           "h_mm": 8.0, "step_hz": 50.0, "runs": rows}  # fmt: skip
    Path(evidence).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    for r in rows:
        print(
            r["label"],
            r["stub_mm"],
            r["status"],
            r.get("max_abs_residual"),
            r.get("max_abs_residual_plane"),
        )
    return doc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="f13_power_probe")
    parser.add_argument("out", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--parallel", type=int, default=3)
    args = parser.parse_args()
    main(args.out, args.evidence, args.parallel)
