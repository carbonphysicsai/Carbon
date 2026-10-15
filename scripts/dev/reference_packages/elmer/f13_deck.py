"""f13 silencer decks for the pinned Elmer image (REFERENCE-PACKAGES-01).

    python -m scripts.dev.reference_packages.elmer.f13_deck case LABEL --out DIR [--h-mm 8] [--step-hz 10]

The packet's geometry (round1/f13-compressor-silencer.md, requirements.json),
along z: inlet stub (r 25 mm, 10 mm) | chamber 1 (r1, L1) | neck (r 20 mm,
length Ln, centred at x = offset) | chamber 2 (r2, L2) | outlet stub (r 25 mm,
10 mm), coaxial ports. Rigid walls, air rho 1.2, c 343, no loss, no flow.

Mesh: Gmsh (OpenCASCADE fuse, second-order tetrahedra), run in the pinned
motor reference image, which carries Gmsh 4.15's Python API; ElmerGrid
converts it. Ports: the packet's matched plane-wave condition rho c (Elmer
`Wave Impedance = c`) on both port planes, and at the inlet a unit-power
incident plane wave A (`Wave Flux 2 = 2 k A`, since dp/dn = 2ikA - ikp there).
One ElmerSolver process scans every frequency ("Scanning Loops"), saving the
port integrals after each frequency.

Observers per frequency: incident power 1 W by construction; reflected power
from the inlet's mean complex pressure minus A; transmitted power from the
outlet's integral of |p|^2 / (2 rho c); TL = -10 log10(P_trans / P_inc) and
the power residual 1 - P_ref - P_trans.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RHO, C = 1.2, 343.0
R_PORT, STUB, R_NECK = 25.0, 60.0, 20.0
#: f13-deck.v2 (2026-10-10): 60 mm port stubs. v1 used 10 mm, where offset
#: necks leave evanescent non-planar content at the port planes (power
#: residual 4.7-11.2 %); at 60 mm every probed geometry closes to <= 0.02 %
#: (f13-power-probe.json). Transmission loss is plane-position invariant in
#: the uniform matched port (coaxial control: |dTL| <= 0.037 dB), so the
#: observable keeps the panel's definition. Frozen v1 decks keep 10 mm.
DECK_VERSION = "f13-deck.v2"
S_PORT = math.pi * (R_PORT * 1e-3) ** 2
AMPLITUDE = math.sqrt(2 * RHO * C / S_PORT)  # unit incident power
PANELS = Path(
    ROOT, "docs/development/challenge_pipeline/round1/reference-route-panels.json"
)
MESH_IMAGE = (
    "ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:"
    "599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05"
)


def panel_case(label):
    d = json.loads(PANELS.read_text())["families"]["f13"]
    row = next(c for c in d["public_cases"] if c["label"] == label)
    return dict(zip(d["panel_fields"], row["parameters"]))


def gmsh_script(case, h_mm, stub_mm=STUB):
    """A Python script for the mesher image: builds the fused solid and
    writes mesh.msh (v2.2, second order) and groups.json."""
    return f"""
import json, gmsh
gmsh.initialize(["-nt", "1"])
gmsh.option.setNumber("General.Terminal", 0)
occ = gmsh.model.occ
case = {json.dumps(case)}
z = 0.0
parts = []
def cyl(x, r, length):
    global z
    tag = occ.addCylinder(x, 0, z, 0, 0, length, r)
    z += length
    return (3, tag)
parts.append(cyl(0, {R_PORT}, {stub_mm}))
parts.append(cyl(0, case["radius1_mm"], case["length1_mm"]))
if case.get("neck_length_mm", 0) > 0:
    parts.append(cyl(case["neck_offset_mm"], {R_NECK}, case["neck_length_mm"]))
if case.get("radius2_mm", 0) > 0:
    parts.append(cyl(0, case["radius2_mm"], case["length2_mm"]))
parts.append(cyl(0, {R_PORT}, {stub_mm}))
length = z
if len(parts) > 1:
    fused, _ = occ.fuse([parts[0]], parts[1:])
else:
    fused = parts
occ.removeAllDuplicates()
occ.synchronize()
vols = [t for d, t in gmsh.model.getEntities(3)]
inlet, outlet, walls = [], [], []
for d, t in gmsh.model.getEntities(2):
    x0, y0, z0, x1, y1, z1 = gmsh.model.getBoundingBox(d, t)
    if abs(z1) < 1e-6 and abs(z0) < 1e-6:
        inlet.append(t)
    elif abs(z0 - length) < 1e-6 and abs(z1 - length) < 1e-6:
        outlet.append(t)
    else:
        walls.append(t)
gmsh.model.addPhysicalGroup(3, vols, 1)
gmsh.model.addPhysicalGroup(2, inlet, 1)
gmsh.model.addPhysicalGroup(2, outlet, 2)
gmsh.model.addPhysicalGroup(2, walls, 3)
gmsh.option.setNumber("Mesh.MeshSizeMax", {h_mm})
gmsh.option.setNumber("Mesh.MeshSizeMin", {h_mm} / 4)
gmsh.option.setNumber("Mesh.ElementOrder", 2)
gmsh.option.setNumber("Mesh.SecondOrderLinear", 0)
gmsh.option.setNumber("Mesh.Algorithm3D", 1)
gmsh.option.setNumber("Mesh.RandomSeed", 1)
gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
gmsh.option.setNumber("Mesh.ScalingFactor", 0.001)
gmsh.model.mesh.generate(3)
gmsh.write("mesh.msh")
json.dump({{"length_mm": length, "inlet": inlet, "outlet": outlet, "walls": len(walls),
           "volumes": len(vols), "nodes": len(gmsh.model.mesh.getNodes()[0])}}, open("groups.json", "w"))
gmsh.finalize()
"""


def frequencies(step_hz, band=(500.0, 2500.0)):
    n = round((band[1] - band[0]) / step_hz)
    return [band[0] + i * step_hz for i in range(n + 1)]


#: Linear solvers. v1 and the first v2 probes used UMFPACK ("direct"). Since
#: 2026-10-15 the default is BiCGStabl(4) + ILU2 to residual 1e-10: on the
#: nominal 8 mm deck it reproduces UMFPACK's TL to 1e-6 dB at 4.6x less CPU
#: and 5.6x less memory (f13-proof-v2.json solver_parity), and it is the
#: only route that fits the 4 mm mesh on a 15 GB host. A non-converged
#: system aborts the run (no silent partial curve).
SOLVERS = {
    "direct": """  Linear System Solver = Direct
  Linear System Direct Method = Umfpack""",
    "iterative": """  Linear System Solver = Iterative
  Linear System Iterative Method = BiCGStabl
  BiCGStabl Polynomial Degree = 4
  Linear System Preconditioning = ILU2
  Linear System Convergence Tolerance = 1e-10
  Linear System Max Iterations = 4000
  Linear System Abort Not Converged = True""",
    "iterative_complex": """  Linear System Solver = Iterative
  Linear System Iterative Method = BiCGStabl
  BiCGStabl Polynomial Degree = 4
  Linear System Preconditioning = ILU2
  Linear System Complex = Logical True
  Linear System Convergence Tolerance = 1e-10
  Linear System Max Iterations = 4000
  Linear System Abort Not Converged = True""",
    "idrs": """  Linear System Solver = Iterative
  Linear System Iterative Method = IDRS
  Idrs Parameter = 6
  Linear System Preconditioning = ILU2
  Linear System Convergence Tolerance = 1e-10
  Linear System Max Iterations = 4000
  Linear System Abort Not Converged = True""",
}


def sif(freqs, solver="iterative"):
    table = "\n".join(f"      {i + 1} {f!r}" for i, f in enumerate(freqs))
    flux = "\n".join(
        f"      {i + 1} {2 * (2 * math.pi * f / C) * AMPLITUDE!r}"
        for i, f in enumerate(freqs)
    )
    return f"""! f13 deck: REFERENCE-PACKAGES-01, generated by f13_deck.py
Header
  Mesh DB "." "mesh"
End
Simulation
  Max Output Level = 3
  Coordinate System = Cartesian 3D
  Simulation Type = Steady State
  Steady State Max Iterations = 1
End
Body 1
  Equation = 1
  Material = 1
  Body Force = 1
End
Body Force 1
  Pabs2 = Variable Pressure 1, Pressure 2
    Real MATC "tx(0)^2+tx(1)^2"
End
Material 1
  Density = {RHO!r}
  Sound Speed = {C!r}
End
Equation 1
  Active Solvers(1) = 1
End
Solver 1
  Equation = Helmholtz
  Variable = Pressure[Pressure 1:1 Pressure 2:1]
  Variable Dofs = 2
  Procedure = "HelmholtzSolve" "HelmholtzSolver"
  Scanning Loops = {len(freqs)}
  Post Solvers = 2
  Frequency = Variable scan
    Real
{table}
    End
{SOLVERS[solver]}
  Nonlinear System Max Iterations = 1
  Steady State Convergence Tolerance = 1e-9
  Nonlinear Update Exported Variables = Logical True
  Exported Variable 1 = Pabs2
End
Solver 2
  Exec Solver = never
  Equation = SaveScalars
  Procedure = "SaveData" "SaveScalars"
  Filename = ports.dat
  Variable 1 = scan
  Variable 2 = Pressure 1
  Operator 2 = boundary int
  Variable 3 = Pressure 2
  Operator 3 = boundary int
  Variable 4 = Pabs2
  Operator 4 = boundary int
End
Boundary Condition 1
  Target Boundaries(1) = 1
  Name = "inlet"
  Wave Impedance 1 = Real {C!r}
  Wave Flux 2 = Variable scan
    Real
{flux}
    End
  Save Scalars = Logical True
End
Boundary Condition 2
  Target Boundaries(1) = 2
  Name = "outlet"
  Wave Impedance 1 = Real {C!r}
  Save Scalars = Logical True
End
Boundary Condition 3
  Target Boundaries(1) = 3
  Name = "walls"
End
"""


def write_case(
    case, out, h_mm=8.0, step_hz=10.0, freqs=None, stub_mm=STUB, solver="iterative"
):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "make_mesh.py").write_text(gmsh_script(case, h_mm, stub_mm))
    freqs = freqs or frequencies(step_hz)
    (out / "case.sif").write_text(sif(freqs, solver))
    (out / "ELMERSOLVER_STARTINFO").write_text("case.sif\n1\n")
    meta = {"case": case, "h_mm": h_mm, "frequencies_hz": freqs, "amplitude_pa": AMPLITUDE,
            "port_area_m2": S_PORT, "stub_mm": stub_mm, "solver": solver, "deck_version": DECK_VERSION, "rho": RHO, "c": C, "mesh_image": MESH_IMAGE}  # fmt: skip
    (out / "deck.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


#: The observer's explicit column map (f13-panel-planes.v1): SaveScalars
#: names one "boundary int" column per variable and saved BC, inlet (bc 1)
#: then outlet (bc 2), the variable named on the inlet column only.
COLUMNS = {
    "frequency": "res: frequency",
    "in_real": "boundary int: pressure 1 over bc 1",
    "out_real": "boundary int:  over bc 2",
    "in_imag": "boundary int: pressure 2 over bc 1",
    "out_imag": "boundary int:  over bc 2",
    "in_abs2": "boundary int: pabs2 over bc 1",
    "out_abs2": "boundary int:  over bc 2",
}


def column_map(names_text):
    """{quantity: (1-based index, exact name)} from ports.dat.names, by order:
    each outlet column must directly follow its inlet column."""
    entries = {}
    for line in names_text.splitlines():
        m = re.match(r"^\s*(\d+):\s*(.*?)\s*$", line)
        if m:
            entries[int(m[1])] = m[2]
    out = {}
    for key, inlet in (("real", COLUMNS["in_real"]), ("imag", COLUMNS["in_imag"]),
                       ("abs2", COLUMNS["in_abs2"])):  # fmt: skip
        hits = [i for i, n in entries.items() if n == inlet]
        if len(hits) != 1 or entries.get(hits[0] + 1) != COLUMNS["out_real"]:
            raise ValueError(f"port integral columns not found: {key}")
        out[f"in_{key}"] = (hits[0], entries[hits[0]])
        out[f"out_{key}"] = (hits[0] + 1, entries[hits[0] + 1])
    hits = [i for i, n in entries.items() if n == COLUMNS["frequency"]]
    if len(hits) != 1:
        raise ValueError("frequency column not found")
    out["frequency"] = (hits[0], COLUMNS["frequency"])
    return out


def port_integrals(case_dir):
    """Rows {f_hz, in_real, in_imag, out_real, out_imag, in_abs2, out_abs2}
    (SI integrals over the port planes) in solve order, by the explicit map."""
    cols = column_map(Path(case_dir, "ports.dat.names").read_text())
    rows = []
    for line in Path(case_dir, "ports.dat").read_text().splitlines():
        if not line.strip():
            continue
        v = [float(x) for x in line.split()]
        row = {k: v[i - 1] for k, (i, _) in cols.items()}
        row["f_hz"] = row.pop("frequency")
        rows.append(row)
    return rows


def observe(case_dir):
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    names = Path(case_dir, "ports.dat.names").read_text().splitlines()
    cols = [n.split(":", 1)[1].strip() for n in names if re.match(r"^\s*\d+:", n)]
    rows = [
        list(map(float, x.split()))
        for x in Path(case_dir, "ports.dat").read_text().splitlines()
        if x.strip()
    ]

    # SaveScalars lists, per variable, one "boundary int" column per saved
    # BC in order (inlet bc 1, outlet bc 2), naming the variable only once.
    ints = [i for i, c in enumerate(cols) if c.startswith("boundary int")]
    if len(ints) != 6:
        raise ValueError(f"expected 6 port integrals, found {len(ints)}")
    i_p1, i_p2, i_a2 = ints[0:2], ints[2:4], ints[4:6]
    i_freq = next(i for i, c in enumerate(cols) if c.startswith("res: frequency"))
    a, s = meta["amplitude_pa"], meta["port_area_m2"]
    out = []
    for r in rows:
        f = r[i_freq]
        mean_in = complex(r[i_p1[0]], r[i_p2[0]]) / s
        b = mean_in - a
        p_ref = abs(b) ** 2 * s / (2 * RHO * C)
        p_tr = r[i_a2[1]] / (2 * RHO * C)
        # The outlet's plane-wave (mean-pressure) power: evanescent non-planar
        # content carries no power but adds to the |p|^2 integral.
        mean_out = complex(r[i_p1[1]], r[i_p2[1]]) / s
        p_tr_plane = abs(mean_out) ** 2 * s / (2 * RHO * C)
        out.append({"f_hz": f, "p_ref_w": p_ref, "p_trans_w": p_tr,
                    "tl_db": -10 * math.log10(p_tr) if p_tr > 0 else None,
                    "residual": 1 - p_ref - p_tr, "p_trans_plane_w": p_tr_plane,
                    "residual_plane": 1 - p_ref - p_tr_plane})  # fmt: skip
    return out


def chamber_tl(f, r_chamber, length):
    """Single coaxial expansion chamber, plane-wave transfer matrix."""
    m = (r_chamber / R_PORT) ** 2
    k = 2 * math.pi * f / C
    return 10 * math.log10(
        1 + 0.25 * (m - 1 / m) ** 2 * math.sin(k * length * 1e-3) ** 2
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f13_deck")
    parser.add_argument("command", choices=("case",))
    parser.add_argument("label")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--h-mm", type=float, default=8.0)
    parser.add_argument("--step-hz", type=float, default=10.0)
    args = parser.parse_args(argv)
    meta = write_case(panel_case(args.label), args.out, args.h_mm, args.step_hz)
    print(json.dumps({k: meta[k] for k in ("case", "h_mm")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
