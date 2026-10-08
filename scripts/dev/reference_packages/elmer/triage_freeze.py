"""Freeze #787's f02 and f13 triage decks (REFERENCE-PACKAGES-01).

    python -m scripts.dev.reference_packages.elmer.triage_freeze --out DIR

Writes every deck of the two families' public panels (#787
reference-route-panels.json) into DIR/<family>/<case>/, meshes the f13
geometries with the pinned Gmsh image, and writes DIR/manifest.json: per
case the launch command, the files' sha256 and the reservation it uses.
The triage host receives DIR as one archive; nothing is generated there.

f02 (#787 reservations: 8 primary, 16 mesh and time, 4 controls, 2 steady
baselines, 1 cold repeat): every public case at mesh 1 / dt 1, then mesh 2
and dt 0.5 for each; the packet's four controls; the 20 W steady baselines
of the two cooling/split regimes in the panel; the first primary case again.

f13 (8 primary sweeps, 2 fine sweeps, 2 controls, 1 cold repeat, 3 separate
frequency smokes): every public geometry over 500-2500 Hz at 10 Hz on the
8 mm mesh (direct solver, OpenBLAS on the 8 granted CPUs). The two fine
sweeps are #787's two witnesses, split so each fits the 2 h case limit:
the frequency witness (clearance-boundary at 5 Hz, 401 points, 8 mm) and
the mesh witness (large-offset on the 4 mm mesh, iterative solver, every
100 Hz, 21 points). Then the straight-duct and coaxial-chamber controls,
the first primary again, and three single-frequency launches of the first
primary for scan parity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.reference_packages.elmer import f02_controls as f02c
from scripts.dev.reference_packages.elmer import f02_deck as f02
from scripts.dev.reference_packages.elmer import f13_deck as f13

PANELS = json.loads(f02.PANELS.read_text())["families"]
SOLVE = "ElmerSolver case.sif > solver.log 2>&1"
F13_SOLVE = (
    "export OPENBLAS_NUM_THREADS=8; "
    "ElmerGrid 14 2 mesh.msh -autoclean -out mesh > grid.log 2>&1 && " + SOLVE
)
ITERATIVE = """  Linear System Solver = Iterative
  Linear System Iterative Method = BiCGStabl
  BiCGStabl Polynomial Degree = 4
  Linear System Preconditioning = ILU2
  Linear System Convergence Tolerance = 1e-10
  Linear System Max Iterations = 4000
  Linear System Abort Not Converged = True"""
DIRECT = """  Linear System Solver = Direct
  Linear System Direct Method = Umfpack"""


def _digest(case_dir):
    files = sorted(p for p in Path(case_dir).rglob("*") if p.is_file())
    return {
        str(p.relative_to(case_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }


def _mesh_f13(case_dir):
    cmd = ["docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
           "-v", f"{Path(case_dir).resolve()}:/w", "-w", "/w", f13.MESH_IMAGE, "python3", "make_mesh.py"]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True)


def freeze(out):
    out = Path(out)
    entries = []

    def add(family, name, reservation, command, case_dir):
        entries.append({"family": family, "case": name, "reservation": reservation,
                        "command": command, "files": _digest(case_dir)})  # fmt: skip

    # f02
    labels = [c["label"] for c in PANELS["f02"]["public_cases"]]
    for label in labels:
        case = f02.panel_case(label)
        for tag, level, dt, reservation in (
            ("primary", 1, 1.0, "primary"),
            ("mesh2", 2, 1.0, "mesh_and_time"),
            ("dt0.5", 1, 0.5, "mesh_and_time"),
        ):
            d = out / "f02" / f"{label}-{tag}"
            f02.write_case(case, d, level, dt)
            add("f02", d.name, reservation, SOLVE, d)
    for name, (case, opts) in f02c.CONTROLS.items():
        d = out / "f02" / f"control-{name}"
        f02.write_case(case, d, **opts)
        add("f02", d.name, "controls", SOLVE, d)
    regimes = {
        (c[0], c[1], c[3])
        for c in (x["parameters"] for x in PANELS["f02"]["public_cases"])
    }
    for coolant, h, split in sorted(regimes):
        case = {"coolant_c": coolant, "h_w_m2_k": h, "initial_c": coolant, "left_source_fraction": split,
                "waveform": "constant", "peak_w": f02.BASE_W, "on_time_s": 0.0}  # fmt: skip
        d = out / "f02" / f"steady-{coolant:g}C-{h:g}-{split:g}"
        f02.write_case(case, d, steady=True)
        add("f02", d.name, "steady_baselines", SOLVE, d)
    d = out / "f02" / f"{labels[0]}-cold-repeat"
    f02.write_case(f02.panel_case(labels[0]), d)
    add("f02", d.name, "cold_repeat", SOLVE, d)

    # f13
    f13_labels = [c["label"] for c in PANELS["f13"]["public_cases"]]
    fine = PANELS["f13"]["refinement_witness_labels"]
    plan = [(lb, "primary", 8.0, 10.0, None, "primary_sweeps") for lb in f13_labels]
    del fine  # #787 names clearance-boundary and large-offset; split below
    plan += [("clearance-boundary", "freq5hz", 8.0, 5.0, None, "fine_sweeps")]
    plan += [("large-offset", "mesh4mm", 4.0, 100.0, None, "fine_sweeps")]
    plan += [(f13_labels[0], "cold-repeat", 8.0, 10.0, None, "cold_repeat")]
    plan += [(f13_labels[0], f"single-{f:g}", 8.0, None, [f], "separate_frequency_smoke")
             for f in (1000.0, 1500.0, 2000.0)]  # fmt: skip
    controls = {
        "control-duct": {"radius1_mm": 25.0, "length1_mm": 100.0, "neck_length_mm": 0,
                         "radius2_mm": 0, "length2_mm": 0, "neck_offset_mm": 0},
        "control-chamber": {"radius1_mm": 62.5, "length1_mm": 75.0, "neck_length_mm": 0,
                            "radius2_mm": 0, "length2_mm": 0, "neck_offset_mm": 0},
    }  # fmt: skip
    for label, tag, h, step, freqs, reservation in plan:
        d = out / "f13" / f"{label}-{tag}"
        f13.write_case(
            f13.panel_case(label), d, h_mm=h, step_hz=step or 10.0, freqs=freqs
        )
        if tag == "mesh4mm":
            sif = (d / "case.sif").read_text().replace(DIRECT, ITERATIVE)
            (d / "case.sif").write_text(sif)
        _mesh_f13(d)
        add("f13", d.name, reservation, F13_SOLVE, d)
    for name, geometry in controls.items():
        d = out / "f13" / name
        f13.write_case(geometry, d, h_mm=8.0, step_hz=10.0)
        _mesh_f13(d)
        add("f13", d.name, "controls", F13_SOLVE, d)

    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "ticket": "REFERENCE-PACKAGES-01",
        "grant": "OWNER-REFERENCE-ROUTE-TRIAGE-GRANT-01",
        "image": "sha256:8bcd864dd60be0a80be9769c1a95c67db76eca9e718212f63dd0460cf3a08fc6",
        "mesh_image_f13": f13.MESH_IMAGE,
        "cases": entries,
        "counts": {
            fam: {r: sum(1 for e in entries if e["family"] == fam and e["reservation"] == r)
                  for r in sorted({e["reservation"] for e in entries if e["family"] == fam})}
            for fam in ("f02", "f13")
        },  # fmt: skip
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest["counts"]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="triage_freeze")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(freeze(args.out), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
