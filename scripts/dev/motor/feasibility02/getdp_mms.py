"""PROVISIONAL code verification (MMS) for the pinned GetDP image, as the
motor deck uses it (Form1P / BF_PerpendicularEdge nodal A_z, first-order
triangles, Newton with JacNL for nonlinear nu). Owner-approved process step
2026-10-10; replace with packets Codex's spec when it lands.

    python -m scripts.dev.motor.feasibility02.getdp_mms IMAGE OUTDIR EVIDENCE.json

Unit square, A = sin(pi x) sin(pi y) (A = 0 on the boundary), source js_z:
- linear nu = 1:            J = 2 pi^2 A
- nonlinear nu = 1 + c s,   s = |grad A|^2 = |b|^2, c = 0.5:
    J = 2 pi^2 A (1 + 2 c s) - 4 c pi^2 gx gy cos(pi x) cos(pi y)
  with gx = pi cos(pi x) sin(pi y), gy = pi sin(pi x) cos(pi y)
  (derived by hand; checked here against a finite-difference divergence).
Structured meshes n = 8, 16, 32, 64; nodal max and RMS error; expected
order 2; package check: finest-pair order within 0.3 of 2.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import subprocess
import sys
from pathlib import Path

C = 0.5
EXPECTED, TOL = 2.0, 0.3


def exact(x, y):
    return math.sin(math.pi * x) * math.sin(math.pi * y)


def source(x, y, nonlinear):
    a = exact(x, y)
    if not nonlinear:
        return 2 * math.pi**2 * a
    gx = math.pi * math.cos(math.pi * x) * math.sin(math.pi * y)
    gy = math.pi * math.sin(math.pi * x) * math.cos(math.pi * y)
    s = gx * gx + gy * gy
    return 2 * math.pi**2 * a * (
        1 + 2 * C * s
    ) - 4 * C * math.pi**2 * gx * gy * math.cos(math.pi * x) * math.cos(math.pi * y)


def check_source(nonlinear, h=1e-5):
    """-div(nu(|grad A|^2) grad A) by central differences vs the closed form."""

    def flux(x, y):
        gx = (exact(x + h, y) - exact(x - h, y)) / (2 * h)
        gy = (exact(x, y + h) - exact(x, y - h)) / (2 * h)
        nu = 1 + C * (gx * gx + gy * gy) if nonlinear else 1.0
        return nu * gx, nu * gy

    worst = 0.0
    for x, y in ((0.3, 0.4), (0.7, 0.2), (0.55, 0.85)):
        k = 1e-3
        div = (flux(x + k, y)[0] - flux(x - k, y)[0]) / (2 * k) + (
            flux(x, y + k)[1] - flux(x, y - k)[1]
        ) / (2 * k)
        worst = max(
            worst, abs(-div - source(x, y, nonlinear)) / abs(source(x, y, nonlinear))
        )
    return worst


MESH = """import gmsh
gmsh.initialize(["-nt", "1"]); gmsh.option.setNumber("General.Terminal", 0)
n = {n}
g = gmsh.model.geo
p = [g.addPoint(0, 0, 0), g.addPoint(1, 0, 0), g.addPoint(1, 1, 0), g.addPoint(0, 1, 0)]
l = [g.addLine(p[i], p[(i + 1) % 4]) for i in range(4)]
s = g.addPlaneSurface([g.addCurveLoop(l)])
g.synchronize()
for c in l:
    gmsh.model.mesh.setTransfiniteCurve(c, n + 1)
gmsh.model.mesh.setTransfiniteSurface(s)
gmsh.model.addPhysicalGroup(2, [s], 1); gmsh.model.addPhysicalGroup(1, l, 2)
gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
gmsh.model.mesh.generate(2); gmsh.write("square.msh"); gmsh.finalize()
"""


def pro(n, nonlinear):
    gx = "(Pi*Cos[Pi*X[]]*Sin[Pi*Y[]])"
    gy = "(Pi*Sin[Pi*X[]]*Cos[Pi*Y[]])"
    a = "(Sin[Pi*X[]]*Sin[Pi*Y[]])"
    if nonlinear:
        s = f"({gx}^2+{gy}^2)"
        j = f"2*Pi^2*{a}*(1+2*{C!r}*{s}) - 4*{C!r}*Pi^2*{gx}*{gy}*Cos[Pi*X[]]*Cos[Pi*Y[]]"
        law = f"  nu[] = 1 + {C!r}*SquNorm[$1];\n  dhdb[] = 2*{C!r}*SquDyadicProduct[$1];\n"
        eq_nl = "    Galerkin { JacNL[ dhdb[{d a}] * Dof{d a}, {d a} ]; In Domain; Jacobian Vol; Integration I1; }\n"
        res = "Operation { IterativeLoop[60, 1e-12, 1] { GenerateJac[S]; SolveJac[S]; } SaveSolution[S]; }"
    else:
        j = f"2*Pi^2*{a}"
        law, eq_nl = "  nu[] = 1;\n", ""
        res = "Operation { Generate[S]; Solve[S]; SaveSolution[S]; }"
    step = 1.0 / n
    return f"""Group {{ Domain = Region[1]; Bnd = Region[2]; }}
Function {{
{law}  js[] = Vector[0, 0, {j}];
}}
Constraint {{ {{ Name A; Case {{ {{ Region Bnd; Value 0.; }} }} }} }}
FunctionSpace {{ {{ Name Hcurl_a; Type Form1P; BasisFunction {{ {{ Name se; NameOfCoef ae; Function BF_PerpendicularEdge; Support Domain; Entity NodesOf[All]; }} }}
  Constraint {{ {{ NameOfCoef ae; EntityType NodesOf; NameOfConstraint A; }} }} }} }}
Jacobian {{ {{ Name Vol; Case {{ {{ Region All; Jacobian Vol; }} }} }} }}
Integration {{ {{ Name I1; Case {{ {{ Type Gauss; Case {{ {{ GeoElement Triangle; NumberOfPoints 6; }} {{ GeoElement Line; NumberOfPoints 4; }} }} }} }} }} }}
Formulation {{ {{ Name MS; Type FemEquation; Quantity {{ {{ Name a; Type Local; NameOfSpace Hcurl_a; }} }}
  Equation {{
    Galerkin {{ [ nu[{{d a}}] * Dof{{d a}}, {{d a}} ]; In Domain; Jacobian Vol; Integration I1; }}
{eq_nl}    Galerkin {{ [ -js[], {{a}} ]; In Domain; Jacobian Vol; Integration I1; }}
  }} }} }}
Resolution {{ {{ Name MS; System {{ {{ Name S; NameOfFormulation MS; }} }} {res} }} }}
PostProcessing {{ {{ Name MS; NameOfFormulation MS; Quantity {{ {{ Name az; Value {{ Local {{ [ CompZ[{{a}}] ]; In Domain; Jacobian Vol; }} }} }} }} }} }}
PostOperation {{ {{ Name MS; NameOfPostProcessing MS; Operation {{
  Print[ az, OnGrid {{$A, $B, 0}} {{ 0:1:{step!r}, 0:1:{step!r}, 0 }}, Format Table, File "az.txt" ];
}} }} }}
"""


def run(image, out, n, nonlinear):
    d = Path(out) / f"{'nl' if nonlinear else 'lin'}-n{n}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "mesh.py").write_text(MESH.format(n=n))
    (d / "mms.pro").write_text(pro(n, nonlinear))
    cmd = "python3 mesh.py && getdp mms.pro -msh square.msh -solve MS -pos MS > getdp.log 2>&1"
    rc = subprocess.run(["docker", "run", "--rm", "--network", "none", "--cpus", "1", "--user", f"{os.getuid()}:{os.getgid()}",
                         "-v", f"{d.resolve()}:/w", "-w", "/w", image, "bash", "-c", cmd], check=False).returncode  # fmt: skip
    if rc != 0:
        raise RuntimeError(
            f"{d.name}: exit {rc}: {(d / 'getdp.log').read_text()[-800:] if (d / 'getdp.log').exists() else ''}"
        )
    errors = []
    for line in (d / "az.txt").read_text().splitlines():
        v = line.split()
        if len(v) >= 4:
            x, y, az = (
                float(v[2]),
                float(v[3]),
                float(v[-1]),
            )  # Table: type, id, x y z, x y z, value
            errors.append(az - exact(x, y))
    return (
        max(abs(e) for e in errors),
        math.sqrt(sum(e * e for e in errors) / len(errors)),
        len(errors),
    )


def main(image, out, evidence):
    doc = {"schema": "carbon.reference-package.mms.v1", "status": "PROVISIONAL (self-derived; replace with packets Codex's spec)",
           "image": image, "solver": "GetDP Form1P/BF_PerpendicularEdge, P1 triangles, Newton (JacNL) for nonlinear nu",
           "solution": "A = sin(pi x) sin(pi y) on the unit square", "expected_order": EXPECTED, "tolerance": TOL, "cases": {}}  # fmt: skip
    passed = True
    for nonlinear in (False, True):
        name = "nonlinear_nu_1_plus_0.5b2" if nonlinear else "linear_nu_1"
        rows = [(n, *run(image, out, n, nonlinear)) for n in (8, 16, 32, 64)]
        orders = [{"pair": f"{a[0]}->{b[0]}", "max": math.log2(a[1] / b[1]), "rms": math.log2(a[2] / b[2])}
                  for a, b in itertools.pairwise(rows)]  # fmt: skip
        ok = all(abs(orders[-1][k] - EXPECTED) <= TOL for k in ("max", "rms"))
        passed &= ok
        doc["cases"][name] = {"source_check_rel": check_source(nonlinear),
                              "errors": [{"n": n, "max": m, "rms": r, "points": p} for n, m, r, p in rows],
                              "orders": orders, "pass": ok}  # fmt: skip
    doc["pass"] = passed
    Path(evidence).write_text(json.dumps(doc, indent=1) + "\n")
    print(
        json.dumps(
            {
                k: (v["orders"][-1], v["pass"], v["source_check_rel"])
                for k, v in doc["cases"].items()
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main(*sys.argv[1:4])
