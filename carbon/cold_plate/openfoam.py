# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The cold plate reference: one Challenge case as an OpenFOAM case, and back.

`write_case` turns a case's nine inputs into a complete case directory for the
pinned image (`IMAGE`), to be run with `COMMANDS`; `analysis.analyze_case`
reads the solved case back. Every file is written from this module, so nothing
depends on a template outside the package.

**What it solves.** The repeating cell of the plate (half a channel and half a
fin between symmetry planes) with chtMultiRegionSimpleFoam: laminar,
steady, conjugate. It is the verification rungs' cell
(`scripts/dev/cold_plate/plate_channel/`) with three changes, each measured
there before use:
- PG25's viscosity, density and conductivity vary with temperature, from
  the pinned fits in `domain.PG25`; heat capacity is held at the inlet
  temperature (`FLUID_MODELS` says why);
- the heat flux follows the case's axial hot-spot map, written as an OpenFOAM
  `expression` in the face position (rung 7);
- the heat load is an input, which sets the flux and, with the flow per kW,
  the flow.
The mesh is the rungs' wall-graded mesh unchanged (rung 5b: grading 4 and
resolution 2 converge every local maximum).

**What it does not solve:** headers, manifolds, plate edges, spanwise heat-map
variation, the thermal interface (added after the solve, `domain`), buoyancy,
turbulence, boiling.

OpenFOAM is GPL-3.0. Carbon writes its input files and reads its output; it
runs only on an operator host, in the pinned image, without network.
"""

from __future__ import annotations

import json
from pathlib import Path

from .domain import FIXED, K0, PG25, check_inputs, derived, pg25

IMAGE = (
    "opencfd/openfoam-default@sha256:"
    "33fb575aa9980d2bc42fd58c75ae698c489293ba30c991380fe3f899c622f319"
)
#: The commands the image runs, in order, inside the case directory.
COMMANDS = (
    "blockMesh > log.blockMesh 2>&1",
    "checkMesh > log.checkMesh 2>&1",
    "splitMeshRegions -cellZones -overwrite > log.splitMeshRegions 2>&1",
    "rm -f 0/solid/U 0/solid/p_rgh",
    (
        "for r in fluid solid; do changeDictionary -region $r"
        " > log.changeDictionary.$r 2>&1; done"
    ),
    "chtMultiRegionSimpleFoam > log.chtMultiRegionSimpleFoam 2>&1",
    (
        "for r in fluid solid; do postProcess -region $r -func writeCellCentres"
        " > log.cellCentres.$r 2>&1; done"
    ),
    (
        "for r in fluid solid; do postProcess -region $r -func writeCellVolumes"
        " > log.cellVolumes.$r 2>&1; done"
    ),
    "foamListTimes > times",
)
#: The reference's mesh and iteration settings (rungs 5b and 6).
RESOLUTION = 2.0
WALL_GRADING = 4.0
ITERATIONS = 4000
#: Fluid models; viscosity varies in all three.
#: - `variable`, the reference: density and conductivity vary too; cp is
#:   held at its inlet value. cp varies about 3 % over 30-99 C, and letting it
#:   vary breaks exact energy conservation at the solid-fluid interface (rung
#:   7: the solver's own enthalpy flow falls 5e-4 to 9e-4 short of the heat
#:   in, shrinking with the mesh), which would cost the reference its exact
#:   energy check.
#: - `variable-cp`: every property varies. A diagnostic, to measure what
#:   holding cp costs; never a reference.
#: - `viscosity-only`: rho, cp and kappa held at the inlet temperature, as
#:   rungs 6d-6e did, so the package can be compared with them.
FLUID_MODELS = ("variable", "variable-cp", "viscosity-only")
CASE_SCHEMA = "carbon.cold-plate.openfoam-case.v1"

# Cells per segment at resolution 1: x, then y (channel, fin), then z (base,
# channel, lid). Resolution r multiplies every count by r. The rungs' values.
CELLS = {"x": 50, "y": (5, 5), "z": (5, 10, 3)}


def geometry_mm(case):
    return {
        "length": FIXED["footprint_mm"],
        "channel_width": case["channel_width_mm"],
        "channel_height": case["channel_depth_mm"],
        "fin_width": case["fin_width_mm"],
        "base_thickness": FIXED["base_mm"],
        "lid_thickness": FIXED["lid_mm"],
    }


def _y_grading(j, g):
    if g == 1.0:
        return "1"
    return f"{1 / g:.12g}" if j == 0 else f"{g:.12g}"


def _z_grading(k, g):
    if g == 1.0:
        return "1"
    if k == 0:
        return f"{1 / g:.12g}"
    if k == 2:
        return f"{g:.12g}"
    return f"((0.5 0.5 {g:.12g}) (0.5 0.5 {1 / g:.12g}))"


def block_mesh(g, r, grading):
    """The rungs' blockMeshDict, unchanged: wall-graded toward every
    solid-fluid wall, uniform along the flow."""
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
                f"hex ({' '.join(map(str, h))}) {zone} ({nx} {ny[j]} {nz[k]}) "
                f"simpleGrading (1 {_y_grading(j, grading)} {_z_grading(k, grading)})"
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

    def fmt(f):
        return "(" + " ".join(map(str, f)) + ")"

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
            f"    {name} {{ type {kinds.get(name, 'wall')}; "
            f"faces ({' '.join(map(fmt, faces))}); }}"
            for name, faces in patches.items()
        ],
        ");",
    ]
    cells = nx * (sum(ny) * sum(nz))
    return "\n".join(lines) + "\n", {"nx": nx, "ny": ny, "nz": nz, "cells": cells}


def _header(cls, obj):
    return f"FoamFile {{ version 2.0; format ascii; class {cls}; object {obj}; }}\n"


def _coeffs(values):
    padded = [*values, *[0.0] * (8 - len(values))]
    return " ".join(repr(float(c)) for c in padded)


def fluid_coefficients(model, t_in):
    """(rho, cp, kappa) coefficient lists for a fluid model; mu always varies.
    A held property is the degree-0 polynomial of its value at the inlet."""
    held = {n: (pg25(n, t_in),) for n in ("rho", "cp", "kappa")}
    varying = {n: PG25[n] for n in ("rho", "cp", "kappa")}
    if model == "variable":
        return varying["rho"], held["cp"], varying["kappa"]
    if model == "variable-cp":
        return varying["rho"], varying["cp"], varying["kappa"]
    return held["rho"], held["cp"], held["kappa"]


def _fluid_thermo(model, t_in):
    rho, cp, kappa = fluid_coefficients(model, t_in)
    return (
        _header("dictionary", "thermophysicalProperties") + "thermoType\n{\n"
        "    type            heRhoThermo;\n"
        "    mixture         pureMixture;\n"
        "    transport       polynomial;\n"
        "    thermo          hPolynomial;\n"
        "    equationOfState icoPolynomial;\n"
        "    specie          specie;\n"
        "    energy          sensibleEnthalpy;\n"
        "}\n"
        "mixture\n{\n"
        "    specie          { molWeight 18; }\n"
        f"    equationOfState {{ rhoCoeffs<8> ( {_coeffs(rho)} ); }}\n"
        f"    thermodynamics  {{ Hf 0; Sf 0; CpCoeffs<8> ( {_coeffs(cp)} ); }}\n"
        f"    transport       {{ muCoeffs<8> ( {_coeffs(PG25['mu'])} ); "
        f"kappaCoeffs<8> ( {_coeffs(kappa)} ); }}\n"
        "}\n"
    )


def _heat_flux_entry(case, d):
    """`q` for the heated patch: uniform for a ratio of 1, otherwise the map
    as an expression in the face centre's x (metres)."""
    q_avg = d["heat_flux_w_m2"]
    if d["hotspot_amplitude"] == 0.0:
        return f"q               uniform {q_avg!r};"
    return (
        "q\n"
        "            {\n"
        "                type        expression;\n"
        "                variables\n"
        "                (\n"
        f'                    "qavg = {q_avg!r}"\n'
        f'                    "amp = {d["hotspot_amplitude"]!r}"\n'
        f'                    "sbar = {d["hotspot_mean_shape"]!r}"\n'
        f'                    "xc = {case["hotspot_center_mm"] * 1e-3!r}"\n'
        f'                    "w = {case["hotspot_width_mm"] * 1e-3!r}"\n'
        "                );\n"
        "                expression\n"
        "                #{\n"
        "                    qavg*(1 + amp*exp(-0.5*sqr((pos().x() - xc)/w)))/sbar\n"
        "                #};\n"
        "            }"
    )


def files(
    case,
    *,
    resolution=RESOLUTION,
    grading=WALL_GRADING,
    iterations=ITERATIONS,
    fluid_model="variable",
):
    """Every file of the case, as {relative path: text}, and its record."""
    case = check_inputs(case)
    if fluid_model not in FLUID_MODELS:
        raise ValueError(f"fluid_model must be one of {FLUID_MODELS}")
    if resolution <= 0 or grading < 1 or iterations < 2:
        raise ValueError("resolution > 0, grading >= 1 and iterations >= 2")
    d = derived(case)
    t_in = K0 + case["inlet_c"]
    u_in = d["inlet_velocity_m_s"]
    mesh_text, mesh = block_mesh(geometry_mm(case), resolution, grading)
    calc = '    ".*" {{ type calculated; value uniform {v}; }}\n'
    sym = '    "sym.*" { type symmetry; }\n'

    def field(cls, obj, dims, value):
        return (
            _header(cls, obj)
            + f"dimensions      {dims};\n"
            + f"internalField   uniform {value};\n"
            + "boundaryField\n{\n"
            + calc.format(v=value)
            + sym
            + "}\n"
        )

    out = {
        "0/T": field("volScalarField", "T", "[0 0 0 1 0 0 0]", repr(t_in)),
        "0/U": field("volVectorField", "U", "[0 1 -1 0 0 0 0]", "(0 0 0)"),
        "0/p": field("volScalarField", "p", "[1 -1 -2 0 0 0 0]", "1e5"),
        "0/p_rgh": field("volScalarField", "p_rgh", "[1 -1 -2 0 0 0 0]", "1e5"),
        "constant/g": _header("uniformDimensionedVectorField", "g")
        + "dimensions      [0 1 -2 0 0 0 0];\nvalue           (0 0 0);  // no buoyancy\n",
        "constant/regionProperties": _header("dictionary", "regionProperties")
        + "regions\n(\n    fluid       (fluid)\n    solid       (solid)\n);\n",
        "constant/fluid/thermophysicalProperties": _fluid_thermo(fluid_model, t_in),
        "constant/fluid/turbulenceProperties": _header(
            "dictionary", "turbulenceProperties"
        )
        + "simulationType  laminar;\n",
        "constant/solid/thermophysicalProperties": _header(
            "dictionary", "thermophysicalProperties"
        )
        + "thermoType\n{\n"
        "    type            heSolidThermo;\n"
        "    mixture         pureMixture;\n"
        "    transport       constIso;\n"
        "    thermo          hConst;\n"
        "    equationOfState rhoConst;\n"
        "    specie          specie;\n"
        "    energy          sensibleEnthalpy;\n"
        "}\n"
        "mixture\n{\n"
        "    specie          { molWeight 50; }\n"
        f"    transport       {{ kappa {FIXED['copper_k_w_mk']!r}; }}\n"
        "    thermodynamics  { Hf 0; Cp 1000; }\n"
        "    equationOfState { rho 1000; }\n"
        "}\n",
        "system/blockMeshDict": mesh_text,
        "system/controlDict": _CONTROL.replace("END_TIME", str(iterations)).replace(
            "WRITE_INTERVAL", str(iterations // 2)
        ),
        "system/fvSchemes": _header("dictionary", "fvSchemes") + _PLAIN_SCHEMES,
        "system/fvSolution": _header("dictionary", "fvSolution") + "SIMPLE\n{\n}\n",
        "system/fluid/fvSchemes": _header("dictionary", "fvSchemes") + _FLUID_SCHEMES,
        "system/fluid/fvSolution": _header("dictionary", "fvSolution")
        + _FLUID_SOLUTION,
        "system/solid/fvSchemes": _header("dictionary", "fvSchemes") + _PLAIN_SCHEMES,
        "system/solid/fvSolution": _header("dictionary", "fvSolution")
        + _SOLID_SOLUTION,
        "system/fluid/changeDictionaryDict": _FLUID_CHANGE.replace(
            "U_IN", repr(u_in)
        ).replace("T_IN", repr(t_in)),
        "system/solid/changeDictionaryDict": _SOLID_CHANGE.replace(
            "Q_ENTRY", _heat_flux_entry(case, d)
        ).replace("T_IN", repr(t_in)),
    }
    record = {
        "schema": CASE_SCHEMA,
        "inputs": case,
        "derived": d,
        "fluid_model": fluid_model,
        "resolution": resolution,
        "wall_grading": grading,
        "iterations": iterations,
        "mesh": mesh,
        "image": IMAGE,
        "pg25": {k: list(v) for k, v in PG25.items()},
    }
    out["case.json"] = json.dumps(record, indent=2, sort_keys=True) + "\n"
    return out, record


def write_case(case, out, **options):
    """Write the case into `out`, which must not exist. Returns its record."""
    out = Path(out)
    if out.exists():
        raise FileExistsError(f"{out} exists; refusing to overwrite")
    texts, record = files(case, **options)
    for relative, text in texts.items():
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    out.chmod(0o700)
    return record


_CONTROL = """FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application     chtMultiRegionSimpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         END_TIME;
deltaT          1;
writeControl    timeStep;
writeInterval   WRITE_INTERVAL;  // half-way and final: the iteration check
purgeWrite      0;
writeFormat     ascii;
writePrecision  12;
timeFormat      general;
runTimeModifiable false;

flowSum
{
    type            surfaceFieldValue;
    libs            (fieldFunctionObjects);
    region          fluid;
    writeControl    writeTime;
    writeFields     false;
    regionType      patch;
    operation       sum;
    fields          (phi);
}
bulk
{
    $flowSum;
    operation       weightedAverage;
    weightField     phi;
    fields          (T);
}
meanPressure
{
    $flowSum;
    operation       areaAverage;
    fields          (p);
}
enthalpyFlow
{
    $flowSum;
    operation       weightedSum;
    weightField     phi;
    fields          (h);
}
functions
{
    massIn    { $flowSum;      name inlet; }
    massOut   { $flowSum;      name outlet; }
    bulkIn    { $bulk;         name inlet; }
    bulkOut   { $bulk;         name outlet; }
    pressIn   { $meanPressure; name inlet; }
    pressOut  { $meanPressure; name outlet; }
    enthalpyIn  { $enthalpyFlow; name inlet; }
    enthalpyOut { $enthalpyFlow; name outlet; }
}
"""
_PLAIN_SCHEMES = """ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes { default none; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
"""
_FLUID_SCHEMES = """ddtSchemes      { default steadyState; }
gradSchemes     { default Gauss linear; }
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,h)      bounded Gauss linearUpwind grad(h);
    div(phi,K)      bounded Gauss linear;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes     { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes        { default corrected; }
"""
_FLUID_SOLUTION = """solvers
{
    rho           { solver PCG; preconditioner DIC; tolerance 1e-9; relTol 0; }
    p_rgh         { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.01; }
    "(U|h)"       { solver PBiCGStab; preconditioner DILU; tolerance 1e-11; relTol 0.01; }
}
SIMPLE
{
    momentumPredictor   on;
    nNonOrthogonalCorrectors 0;
    pRefCell            0;
    pRefValue           1e5;
}
relaxationFactors
{
    fields    { rho 1.0; p_rgh 0.7; }
    equations { U 0.7; h 1.0; }
}
"""
_SOLID_SOLUTION = """solvers
{
    h { solver PCG; preconditioner DIC; tolerance 1e-11; relTol 0; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 0;
}
relaxationFactors { equations { h 1.0; } }
"""
_FLUID_CHANGE = """FoamFile { version 2.0; format ascii; class dictionary; object changeDictionaryDict; }
U
{
    internalField   uniform (U_IN 0 0);
    boundaryField
    {
        inlet         { type fixedValue; value uniform (U_IN 0 0); }
        outlet        { type zeroGradient; }
        "fluid_to_.*" { type noSlip; }
        "sym.*"       { type symmetry; }
    }
}
T
{
    internalField   uniform T_IN;
    boundaryField
    {
        inlet         { type fixedValue; value uniform T_IN; }
        outlet        { type zeroGradient; value uniform T_IN; }
        "fluid_to_.*"
        {
            type            compressible::turbulentTemperatureCoupledBaffleMixed;
            Tnbr            T;
            kappaMethod     fluidThermo;
            value           uniform T_IN;
        }
        "sym.*"       { type symmetry; }
    }
}
p_rgh
{
    internalField   uniform 1e5;
    boundaryField
    {
        inlet         { type fixedFluxPressure; value uniform 1e5; }
        outlet        { type fixedValue; value uniform 1e5; }
        "fluid_to_.*" { type fixedFluxPressure; value uniform 1e5; }
        "sym.*"       { type symmetry; }
    }
}
p
{
    internalField   uniform 1e5;
    boundaryField
    {
        ".*"    { type calculated; value uniform 1e5; }
        "sym.*" { type symmetry; }
    }
}
"""
_SOLID_CHANGE = """FoamFile { version 2.0; format ascii; class dictionary; object changeDictionaryDict; }
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
        "(solidEnds|lid|inlet|outlet)" { type zeroGradient; value uniform T_IN; }
        "solid_to_.*"
        {
            type            compressible::turbulentTemperatureCoupledBaffleMixed;
            Tnbr            T;
            kappaMethod     solidThermo;
            value           uniform T_IN;
        }
        "sym.*" { type symmetry; }
    }
}
p
{
    internalField   uniform 1e5;
    boundaryField
    {
        ".*"    { type calculated; value uniform 1e5; }
        "sym.*" { type symmetry; }
    }
}
"""
