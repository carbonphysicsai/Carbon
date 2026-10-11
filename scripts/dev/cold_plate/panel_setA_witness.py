"""Set-A repeating-cell 3D coupled witnesses (registry
cooling-feasibility-02/panel-setA-registry.json).

    python -m scripts.dev.cold_plate.panel_setA_witness run --out DIR --parallel 6

One conjugate solve per witness: the registered periodic cell with the
3 mm lid (region `spreader`, isotropic k 3,000) stacked under its heated
face, joined through the TIM2 contact (R2'' as a thermal-contact layer on
the spreader side of the coupled interface), the raw die map applied to the
lid's bottom. Reports the lid-side TIM2 interface peak (the spreader's top
face, extrapolated from its two top cell layers) against the composed
2D-lid + cell result of the matching base job.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import analysis, domain, openfoam
from scripts.dev.cold_plate import feasibility02 as cf
from scripts.dev.cold_plate import panel_setA as pa
from scripts.dev.cold_plate.reference import run_batch

LID_CELLS = 16
TIM2_T = 25e-6  # m; kappa = t / R2 keeps R2'' exact
WITNESSES = [("w0.2-d6", "warm_outlet_band"), ("w0.3-d6", "warm_outlet_band"), ("w0.5-d6", "warm_outlet_band"),
             ("w0.2-d3", "warm_central_band"), ("w0.3-d3", "warm_central_band"), ("w0.5-d3", "warm_central_band")]  # fmt: skip
COMMANDS = tuple(
    c.replace("for r in fluid solid;", "for r in fluid solid spreader;").replace(
        "rm -f 0/solid/U 0/solid/p_rgh",
        "rm -f 0/solid/U 0/solid/p_rgh 0/spreader/U 0/spreader/p_rgh",
    )
    for c in openfoam.COMMANDS
)


def block_mesh_with_lid(g, r, grading):
    text, mesh = openfoam_block_mesh(g, r, grading)
    return text, mesh


def openfoam_block_mesh(g, r, grading):
    """The registered blockMeshDict with one more row below z = 0: the lid
    (zone `spreader`) across the channel and fin columns; the heated patch
    moves to the lid's bottom."""
    xs = (0.0, g["length"])
    ys = (0.0, g["channel_width"] / 2, (g["channel_width"] + g["fin_width"]) / 2)
    z1 = g["base_thickness"]
    z2 = z1 + g["channel_height"]
    zs = (-pa.LID_T_MM, 0.0, z1, z2, z2 + g["lid_thickness"])
    nx = round(openfoam.CELLS["x"] * r)
    ny = [round(n * r) for n in openfoam.CELLS["y"]]
    nz = [LID_CELLS] + [round(n * r) for n in openfoam.CELLS["z"]]

    def v(i, j, k):
        return (k * len(ys) + j) * len(xs) + i

    vertices = [(x, y, z) for z in zs for y in ys for x in xs]
    blocks = []
    patches = {"inlet": [], "outlet": [], "solidEnds": [], "spreaderEnds": [], "heated": [],
               "lid": [], "symChannel": [], "symFin": []}  # fmt: skip
    for k in range(4):
        for j in range(2):
            h = [v(0, j, k), v(1, j, k), v(1, j + 1, k), v(0, j + 1, k),
                 v(0, j, k + 1), v(1, j, k + 1), v(1, j + 1, k + 1), v(0, j + 1, k + 1)]  # fmt: skip
            zone = "spreader" if k == 0 else ("fluid" if (j, k) == (0, 2) else "solid")
            zg = "1" if k == 0 else openfoam._z_grading(k - 1, grading)
            blocks.append(
                f"hex ({' '.join(map(str, h))}) {zone} ({nx} {ny[j]} {nz[k]}) "
                f"simpleGrading (1 {openfoam._y_grading(j, grading)} {zg})"
            )
            face = {"xmin": (h[0], h[4], h[7], h[3]), "xmax": (h[1], h[2], h[6], h[5]),
                    "ymin": (h[0], h[1], h[5], h[4]), "ymax": (h[3], h[7], h[6], h[2]),
                    "zmin": (h[0], h[3], h[2], h[1]), "zmax": (h[4], h[5], h[6], h[7])}  # fmt: skip
            ends = (
                "spreaderEnds"
                if zone == "spreader"
                else ("inlet" if zone == "fluid" else "solidEnds")
            )
            patches[ends].append(face["xmin"])
            patches["outlet" if zone == "fluid" else ends].append(face["xmax"])
            patches["symChannel" if j == 0 else "symFin"].append(
                face["ymin"] if j == 0 else face["ymax"]
            )
            if k == 0:
                patches["heated"].append(face["zmin"])
            if k == 3:
                patches["lid"].append(face["zmax"])
    kinds = {
        "inlet": "patch",
        "outlet": "patch",
        "symChannel": "symmetry",
        "symFin": "symmetry",
    }

    def fmt(f):
        return "(" + " ".join(map(str, f)) + ")"

    lines = [
        "FoamFile { version 2.0; format ascii; class dictionary; object blockMeshDict; }",
        "scale 0.001;", "vertices (", *[f"    ({x:.6g} {y:.6g} {z:.6g})" for x, y, z in vertices], ");",
        "blocks (", *["    " + b for b in blocks], ");", "boundary (",
        *[f"    {n} {{ type {kinds.get(n, 'wall')}; faces ({' '.join(map(fmt, f))}); }}" for n, f in patches.items()],
        ");",
    ]  # fmt: skip
    return "\n".join(lines) + "\n", {
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "cells": nx * sum(ny) * sum(nz),
    }


SOLID_CHANGE = """FoamFile { version 2.0; format ascii; class dictionary; object changeDictionaryDict; }
T
{
    internalField   uniform T_IN;
    boundaryField
    {
        "(solidEnds|lid|inlet|outlet)" { type zeroGradient; value uniform T_IN; }
        solid_to_fluid
        {
            type            compressible::turbulentTemperatureCoupledBaffleMixed;
            Tnbr            T;
            kappaMethod     solidThermo;
            value           uniform T_IN;
        }
        solid_to_spreader
        {
            type            compressible::turbulentTemperatureRadCoupledMixed;
            Tnbr            T;
            kappaMethod     solidThermo;
            thicknessLayers ( TIM2_T );
            kappaLayers     ( TIM2_K );
            value           uniform T_IN;
        }
        "sym.*" { type symmetry; }
    }
}
p { internalField uniform 1e5; boundaryField { ".*" { type calculated; value uniform 1e5; } "sym.*" { type symmetry; } } }
"""
SPREADER_CHANGE = """FoamFile { version 2.0; format ascii; class dictionary; object changeDictionaryDict; }
T
{
    internalField   uniform T_IN;
    boundaryField
    {
        heated
        {
            type            externalWallHeatFluxTemperature;
            mode            flux;
            Q_ENTRY
            kappaMethod     solidThermo;
            value           uniform T_IN;
        }
        spreaderEnds { type zeroGradient; value uniform T_IN; }
        spreader_to_solid
        {
            type            compressible::turbulentTemperatureRadCoupledMixed;
            Tnbr            T;
            kappaMethod     solidThermo;
            thicknessLayers ( TIM2_T );
            kappaLayers     ( TIM2_K );
            value           uniform T_IN;
        }
        "sym.*" { type symmetry; }
    }
}
p { internalField uniform 1e5; boundaryField { ".*" { type calculated; value uniform 1e5; } "sym.*" { type symmetry; } } }
"""


def spreader_thermo():
    base = openfoam.files.__globals__["_header"](
        "dictionary", "thermophysicalProperties"
    )
    return base + (
        "thermoType\n{\n    type heSolidThermo; mixture pureMixture; transport constIso;\n"
        "    thermo hConst; equationOfState rhoConst; specie specie; energy sensibleEnthalpy;\n}\n"
        "mixture\n{\n    specie { molWeight 50; }\n"
        f"    transport {{ kappa {pa.LID_K!r}; }}\n"
        "    thermodynamics { Hf 0; Cp 1000; }\n    equationOfState { rho 1000; }\n}\n"
    )


def raw_entry(q_raw):
    a0, an = pa.cosine(q_raw, pa.CELL_MODES)
    terms = " + ".join(
        f"({float(c)!r})*cos({(i + 1) * math.pi / pa.L!r}*pos().x())"
        for i, c in enumerate(an)
    )
    return (
        "q\n            {\n                type        expression;\n"
        f"                expression  #{{ {float(a0)!r} + {terms} #}};\n            }}"
    ), (a0, an)


@contextlib.contextmanager
def witness_deck(q_raw):
    entry, (a0, an) = raw_entry(q_raw)

    def flux(case, x_mm):
        return float(pa.series(a0, an, x_mm * 1e-3)[0])

    saved = (
        openfoam.block_mesh,
        openfoam.COMMANDS,
        domain.heat_flux,
        analysis.heat_flux,
    )
    openfoam.block_mesh = openfoam_block_mesh
    openfoam.COMMANDS = COMMANDS
    domain.heat_flux = flux
    analysis.heat_flux = flux
    try:
        yield entry
    finally:
        openfoam.block_mesh, openfoam.COMMANDS, domain.heat_flux, analysis.heat_flux = (
            saved
        )


def write(case_dir, design, ctx, q_raw):
    inputs = pa.cell_inputs(design, ctx)
    t_in = domain.K0 + ctx["inlet_c"]
    with cf.variant(design["base_mm"]), witness_deck(q_raw) as entry:
        texts, _record = openfoam.files(inputs)
        texts["constant/regionProperties"] = texts["constant/regionProperties"].replace(
            "solid       (solid)", "solid       (solid spreader)"
        )
        texts["constant/spreader/thermophysicalProperties"] = spreader_thermo()
        texts["system/spreader/fvSchemes"] = texts["system/solid/fvSchemes"]
        texts["system/spreader/fvSolution"] = texts["system/solid/fvSolution"]
        texts["system/solid/changeDictionaryDict"] = (
            SOLID_CHANGE.replace("T_IN", repr(t_in))
            .replace("TIM2_T", repr(TIM2_T)).replace("TIM2_K", repr(TIM2_T / pa.R2))
        )  # fmt: skip
        texts["system/spreader/changeDictionaryDict"] = (
            SPREADER_CHANGE.replace("Q_ENTRY", entry).replace("T_IN", repr(t_in))
            .replace("TIM2_T", repr(TIM2_T)).replace("TIM2_K", repr(TIM2_T / pa.R2))
        )  # fmt: skip
        for rel, text in texts.items():
            p = case_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
    return inputs


def interface_peak(case_dir):
    times = sorted(
        (t for t in (case_dir / "times").read_text().split() if t != "0"), key=float
    )
    t = times[-1]
    cells = list(
        zip(
            analysis.internal_field(case_dir / t / "spreader" / "C"),
            analysis.internal_field(case_dir / t / "spreader" / "T"),
        )
    )
    zs = sorted({round(c[0][2], 12) for c in cells})
    z1, z2 = zs[-1], zs[-2]  # top layer and the one below
    top = {
        (round(c[0][0], 12), round(c[0][1], 12)): c[1]
        for c in cells
        if round(c[0][2], 12) == z1
    }
    below = {
        (round(c[0][0], 12), round(c[0][1], 12)): c[1]
        for c in cells
        if round(c[0][2], 12) == z2
    }
    face_z = 0.0  # the TIM2 plane (the spreader's top face)
    vals = {
        key: top[key] + (top[key] - below[key]) * (face_z - z1) / (z1 - z2)
        for key in top
    }
    key = max(vals, key=vals.get)
    return vals[key] - domain.K0, key[0] * 1e3


def run_one(args):
    design_id, context, out = args
    design, ctx = pa.DESIGNS[design_id], pa.CONTEXTS[context]
    case_dir = Path(out) / f"witness-{design_id}-{context}"
    q_raw = pa.raw_map(ctx)
    write(case_dir, design, ctx, q_raw)
    with witness_deck(q_raw):
        status, wall, detail = run_batch.solve(
            case_dir, f"carbon-setA-witness-{design_id}-{context}"[:100], 1, 21600
        )
    rec = {
        "design": design_id,
        "context": context,
        "status": status or "RAN",
        "wall_s": round(wall, 1),
        "run": detail,
    }
    if status is None:
        try:
            peak, at = interface_peak(case_dir)
            rec.update(interface_peak_c=peak, at_mm=at)
        except Exception as exc:  # noqa: BLE001
            rec.update(error=repr(exc)[:300])
    (case_dir / "witness.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps(rec), flush=True)
    return rec


def main(argv=None):
    parser = argparse.ArgumentParser(prog="panel_setA_witness")
    parser.add_argument("command", choices=("run", "one"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=6)
    parser.add_argument("--index", type=int, default=0)
    args = parser.parse_args(argv)
    if args.command == "one":
        d, c = WITNESSES[args.index]
        run_one((d, c, args.out))
    else:
        with ProcessPoolExecutor(args.parallel) as pool:
            list(pool.map(run_one, [(d, c, args.out) for d, c in WITNESSES]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
