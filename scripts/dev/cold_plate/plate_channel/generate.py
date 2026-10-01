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

Geometry and mesh resolution are parameters. Fluid and solid properties,
inlet velocity and temperature and the base flux come from a named property
set: `verification` (rungs 3-4: not a coolant or a plate material) or
`design` (the provisional design basis, ../DESIGN_BASIS.md).
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
# Constant properties, SI units. `design` is PG25 at 40 C (CoolProp 6.8.0,
# INCOMP::MPG[0.25]) on copper C11000, at the nominal point of the design
# basis: 1 kW over a 30 x 30 mm footprint, 1.5 L/min per kW through 50
# channels of 0.3 x 2 mm. Its velocity assumes that nominal channel geometry.
PROPERTY_SETS = {
    "verification": {
        "rho_f": 1000.0,
        "cp_f": 4181.0,
        "mu_f": 1e-3,
        "pr_f": 1.0,
        "k_s": 10.0,
        "u_in": 0.1,
        "t_in": 300.0,
        "q_flux": 1e4,
    },
    "design": {
        "rho_f": 1009.91,
        "cp_f": 3968.6,
        "mu_f": 1.3530e-3,
        "pr_f": 11.05,
        "k_s": 391.0,
        "u_in": 1.5e-3 / 60 / (50 * 0.3e-3 * 2e-3),
        "t_in": 313.15,
        "q_flux": 1000 / 0.03**2,
    },
}
# The design set at the inlet-temperature range's ends (DESIGN_BASIS.md
# section 2), same source and convention: constant properties at the inlet
# temperature; only the fluid and the inlet temperature change.
for _name, _t_c, _rho, _cp, _mu, _pr in (
    ("design-30C", 30.0, 1014.90, 3944.6, 1.7761e-3, 14.69),
    ("design-45C", 45.0, 1007.21, 3980.6, 1.1993e-3, 9.74),
):
    PROPERTY_SETS[_name] = {
        **PROPERTY_SETS["design"],
        "rho_f": _rho,
        "cp_f": _cp,
        "mu_f": _mu,
        "pr_f": _pr,
        "t_in": 273.15 + _t_c,
    }
#: Rung 6d: PG25 viscosity as a polynomial in T (kelvin), mu = sum c_i T^i
#: (Pa s), least-squares over CoolProp 6.8.0 INCOMP::MPG[0.25] at 2 bar, 1 K
#: steps over 30-50 C only (DESIGN_BASIS.md section 1). Maximum relative
#: residual in 30-50 C: 1.6e-5. Outside that range it is an extrapolation.
MU_POLYNOMIAL = (
    2.2138268571145154,
    -0.026510771069392616,
    0.0001196248034665941,
    -2.408213659063999e-07,
    1.823829766797535e-10,
)
#: The fluid template's `const` lines, and their polynomial forms. OpenFOAM
#: v2512 accepts `polynomial` transport only with `hPolynomial` thermo and a
#: polynomial equation of state, so c_p and rho become degree-0 polynomials:
#: the same constants. Only mu varies.
_POLYNOMIAL_LINES = (
    ("    transport       const;\n", "    transport       polynomial;\n"),
    ("    thermo          hConst;\n", "    thermo          hPolynomial;\n"),
    ("    equationOfState rhoConst;\n", "    equationOfState icoPolynomial;\n"),
    (
        "    equationOfState { rho RHO_F; }\n",
        "    equationOfState { rhoCoeffs<8> ( RHO_F 0 0 0 0 0 0 0 ); }\n",
    ),
    (
        "    thermodynamics  { Cp CP_F; Hf 0; }\n",
        "    thermodynamics  { Hf 0; Sf 0; CpCoeffs<8> ( CP_F 0 0 0 0 0 0 0 ); }\n",
    ),
)
_CONST_MIXTURE = "    transport       { mu MU_F; Pr PR_F; }\n"


def polynomial_transport(text, properties):
    """The fluid's constant viscosity replaced by a polynomial in T.

    Only viscosity varies. Conductivity is held at the constant-property
    value of the same set, k = mu c_p / Pr at the inlet temperature, so the
    rung changes one thing."""
    for old, new in (*_POLYNOMIAL_LINES, (_CONST_MIXTURE, None)):
        if old not in text:
            raise ValueError("fluid thermophysicalProperties is not the const template")
    for old, new in _POLYNOMIAL_LINES:
        text = text.replace(old, new)
    pad = lambda c: " ".join(repr(float(x)) for x in (*c, *[0.0] * (8 - len(c))))
    kappa = properties["mu_f"] * properties["cp_f"] / properties["pr_f"]
    return text.replace(
        _CONST_MIXTURE,
        f"    transport       {{ muCoeffs<8> ( {pad(MU_POLYNOMIAL)} ); "
        f"kappaCoeffs<8> ( {pad((kappa,))} ); }}\n",
    )


#: The design point's footprint and heat load (DESIGN_BASIS.md section 2).
FOOTPRINT_M, HEAT_LOAD_W = 0.03, 1000.0


def design_inlet_velocity(geometry_mm, flow_lpm_per_kw):
    """Mean channel velocity when the design flow is shared equally by the
    whole number of channel-plus-fin periods that fit across the footprint.
    The cell stays a periodic unit; the flux per footprint area is unchanged."""
    period = (geometry_mm["channel_width"] + geometry_mm["fin_width"]) * 1e-3
    channels = int(FOOTPRINT_M // period + 1e-9)
    if channels < 1:
        raise ValueError("no channel fits across the footprint")
    area = geometry_mm["channel_width"] * geometry_mm["channel_height"] * 1e-6
    flow = HEAT_LOAD_W / 1000 * flow_lpm_per_kw / 60000
    return flow / (channels * area), channels


TOKENS = {
    "RHO_F": "rho_f",
    "CP_F": "cp_f",
    "MU_F": "mu_f",
    "PR_F": "pr_f",
    "K_S": "k_s",
    "U_IN": "u_in",
    "T_IN": "t_in",
    "Q_FLUX": "q_flux",
}
# Cells per segment at resolution 1: x, then y (channel, fin), then z
# (base, channel, lid). Resolution r multiplies every count by r.
CELLS = {"x": 50, "y": (5, 5), "z": (5, 10, 3)}


def _y_grading(j, g):
    """Across the width: fine toward the channel wall at y1 in both columns
    (column 0 ends there, column 1 starts there). Blocks in one column share
    y-edges, so the grading is per column."""
    if g == 1.0:
        return "1"
    return f"{1 / g:.12g}" if j == 0 else f"{g:.12g}"


def _z_grading(k, g):
    """Through the height: fine toward both channel walls. The base row ends
    at the channel floor, the lid row starts at its ceiling, and the channel
    row is fine at both ends. Blocks in one row share z-edges."""
    if g == 1.0:
        return "1"
    if k == 0:
        return f"{1 / g:.12g}"
    if k == 2:
        return f"{g:.12g}"
    return f"((0.5 0.5 {g:.12g}) (0.5 0.5 {1 / g:.12g}))"


def block_mesh(g, r, grading=1.0):
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
                f"hex ({' '.join(map(str, h))}) {zone} ({nx} {ny[j]} {nz[k]}) simpleGrading (1 {_y_grading(j, grading)} {_z_grading(k, grading)})"
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
    parser.add_argument(
        "--wall-grading",
        type=float,
        default=1.0,
        help="largest-to-smallest cell ratio toward each solid-fluid wall; 1 is uniform",
    )
    parser.add_argument("--iterations", type=int, default=4000)
    parser.add_argument(
        "--properties", choices=sorted(PROPERTY_SETS), default="verification"
    )
    parser.add_argument(
        "--flow-lpm-per-kw",
        type=float,
        default=None,
        help="design set only: coolant flow per kW (design basis range 1.25-2.0); "
        "the inlet velocity is derived from it and the geometry",
    )
    parser.add_argument(
        "--viscosity",
        choices=("constant", "polynomial"),
        default="constant",
        help="design sets only: 'polynomial' makes PG25 viscosity vary with "
        "temperature (rung 6d); conductivity stays constant",
    )
    for name, value in DEFAULTS.items():
        parser.add_argument("--" + name.replace("_", "-"), type=float, default=value)
    args = parser.parse_args(argv)
    geometry = {name: getattr(args, name) for name in DEFAULTS}
    if (
        any(value <= 0 for value in geometry.values())
        or args.resolution <= 0
        or args.wall_grading < 1
    ):
        parser.error("every dimension and the resolution must be positive")
    if args.viscosity == "polynomial" and not args.properties.startswith("design"):
        parser.error("--viscosity polynomial is a design-set option (PG25)")
    if args.out.exists():
        parser.error(f"{args.out} exists; refusing to overwrite")
    shutil.copytree(TEMPLATE, args.out)
    properties = dict(PROPERTY_SETS[args.properties])
    channels = None
    if args.flow_lpm_per_kw is not None:
        if not args.properties.startswith("design") or args.flow_lpm_per_kw <= 0:
            parser.error("--flow-lpm-per-kw is a positive design-set option")
        properties["u_in"], channels = design_inlet_velocity(
            geometry, args.flow_lpm_per_kw
        )
    fluid_thermo = args.out / "constant" / "fluid" / "thermophysicalProperties"
    if args.viscosity == "polynomial":
        fluid_thermo.write_text(
            polynomial_transport(fluid_thermo.read_text(), properties)
        )
    for path in args.out.rglob("*"):
        if path.is_file():
            text = path.read_text()
            for token, name in TOKENS.items():
                text = text.replace(token, repr(properties[name]))
            path.write_text(text)
    args.out.chmod(0o700)
    text, mesh = block_mesh(geometry, args.resolution, args.wall_grading)
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
        "wall_grading": args.wall_grading,
        "property_set": args.properties,
        "properties": properties,
        "flow_lpm_per_kw": args.flow_lpm_per_kw,
        "channels_across_footprint": channels,
        "iterations": args.iterations,
        "mesh": mesh,
    }
    if args.viscosity == "polynomial":
        case["viscosity"] = {"model": "polynomial", "mu_coeffs": MU_POLYNOMIAL}
    (args.out / "case.json").write_text(json.dumps(case, indent=2) + "\n")
    print(json.dumps(case))


if __name__ == "__main__":
    main()
