"""Write a rung-4 straight-channel plate case from geometry parameters.

The case is the repeating cell of a plate with parallel straight channels:
half a channel and half a fin, between two symmetry planes, a heated base
and an adiabatic lid. Cross-section (y across, z up; x is the flow):

    z3 +-----------+-----------+   lid (adiabatic)
       |   solid   |   solid   |
    z2 +-----------+           |
       |   fluid   |   solid   |   channel: width wc (half shown), height hc
    z1 +-----------+           |
       |   solid   |   solid   |   base: thickness tb
     0 +-----------+-----------+   heated: uniform flux q
       0          y1          y2   y1 = wc/2, y2 = (wc + wf)/2
     symmetry                symmetry

Only geometry and mesh resolution are parameters here. The fluid and solid
properties, velocity and flux are verification choices fixed in the template
(see README), not a coolant or a plate material.
"""

import argparse
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template"
DEFAULTS = {  # millimetres; a verification geometry, not a product design
    "length": 50.0,
    "channel_width": 1.0,
    "channel_height": 2.0,
    "fin_width": 1.0,
    "base_thickness": 1.0,
    "lid_thickness": 0.5,
}
# Cells per segment at resolution 1: x, then y (channel, fin), then z
# (base, channel, lid). Resolution r multiplies every count by r.
CELLS = {"x": 50, "y": (5, 5), "z": (5, 10, 3)}


def block_mesh(g, r):
    xs = (0.0, g["length"])
    ys = (0.0, g["channel_width"] / 2, (g["channel_width"] + g["fin_width"]) / 2)
    z1 = g["base_thickness"]
    z2 = z1 + g["channel_height"]
    zs = (0.0, z1, z2, z2 + g["lid_thickness"])
    nx = round(CELLS["x"] * r)
    ny = [round(n * r) for n in CELLS["y"]]
    nz = [round(n * r) for n in CELLS["z"]]

    def v(i, j, k):
        return (k * len(ys) + j) * len(xs) + i

    vertices = [(x, y, z) for z in zs for y in ys for x in xs]
    blocks, patches = [], {
        "inlet": [],
        "outlet": [],
        "solidEnds": [],
        "heated": [],
        "lid": [],
        "symChannel": [],
        "symFin": [],
    }
    for k in range(3):
        for j in range(2):
            h = [
                v(0, j, k),
                v(1, j, k),
                v(1, j + 1, k),
                v(0, j + 1, k),
                v(0, j, k + 1),
                v(1, j, k + 1),
                v(1, j + 1, k + 1),
                v(0, j + 1, k + 1),
            ]
            zone = "fluid" if (j, k) == (0, 1) else "solid"
            blocks.append(
                f"hex ({' '.join(map(str, h))}) {zone} ({nx} {ny[j]} {nz[k]}) simpleGrading (1 1 1)"
            )
            face = {
                "xmin": (h[0], h[4], h[7], h[3]),
                "xmax": (h[1], h[2], h[6], h[5]),
                "ymin": (h[0], h[1], h[5], h[4]),
                "ymax": (h[3], h[7], h[6], h[2]),
                "zmin": (h[0], h[3], h[2], h[1]),
                "zmax": (h[4], h[5], h[6], h[7]),
            }
            patches["inlet" if zone == "fluid" else "solidEnds"].append(face["xmin"])
            patches["outlet" if zone == "fluid" else "solidEnds"].append(face["xmax"])
            if j == 0:
                patches["symChannel"].append(face["ymin"])
            else:
                patches["symFin"].append(face["ymax"])
            if k == 0:
                patches["heated"].append(face["zmin"])
            if k == 2:
                patches["lid"].append(face["zmax"])
    kinds = {
        "inlet": "patch",
        "outlet": "patch",
        "symChannel": "symmetry",
        "symFin": "symmetry",
    }
    fmt = lambda f: "(" + " ".join(map(str, f)) + ")"
    lines = [
        "FoamFile { version 2.0; format ascii; class dictionary; object blockMeshDict; }",
        "scale 0.001;  // millimetres",
        "vertices (",
        *[f"    ({x:.6g} {y:.6g} {z:.6g})" for x, y, z in vertices],
        ");",
        "blocks (",
        *["    " + b for b in blocks],
        ");",
        "boundary (",
        *[
            f"    {name} {{ type {kinds.get(name, 'wall')}; faces ({' '.join(map(fmt, faces))}); }}"
            for name, faces in patches.items()
        ],
        ");",
    ]
    cells = nx * (sum(ny) * sum(nz))
    return "\n".join(lines) + "\n", {"nx": nx, "ny": ny, "nz": nz, "cells": cells}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--resolution", type=float, default=1.0)
    parser.add_argument("--iterations", type=int, default=4000)
    for name, value in DEFAULTS.items():
        parser.add_argument("--" + name.replace("_", "-"), type=float, default=value)
    args = parser.parse_args(argv)
    geometry = {name: getattr(args, name) for name in DEFAULTS}
    if any(value <= 0 for value in geometry.values()) or args.resolution <= 0:
        parser.error("every dimension and the resolution must be positive")
    if args.out.exists():
        parser.error(f"{args.out} exists; refusing to overwrite")
    shutil.copytree(TEMPLATE, args.out)
    args.out.chmod(0o700)
    text, mesh = block_mesh(geometry, args.resolution)
    (args.out / "system" / "blockMeshDict").write_text(text)
    control = args.out / "system" / "controlDict"
    control.write_text(
        control.read_text()
        .replace("END_TIME", str(args.iterations))
        .replace("WRITE_INTERVAL", str(args.iterations // 2))
    )
    case = {
        "geometry_mm": geometry,
        "resolution": args.resolution,
        "iterations": args.iterations,
        "mesh": mesh,
    }
    (args.out / "case.json").write_text(json.dumps(case, indent=2) + "\n")
    print(json.dumps(case))


if __name__ == "__main__":
    main()
