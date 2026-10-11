"""Headless CPU Form1P magnetostatic MMS; Data Collection executes, not Codex.

Uses motor's BF_PerpendicularEdge, so A_z L2 order is 2 and flux L2 order 1.
This does NOT verify saturation, magnet remanence, skew or the torque observer.
"""

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

GEO = """SetFactory(\"OpenCASCADE\");
Rectangle(1) = {{0,0,0,1,1}};
Physical Surface(1) = {{1}};
Physical Curve(2) = Boundary{{ Surface{{1}}; }};
Mesh.MshFileVersion = 2.2;
Mesh.CharacteristicLengthMin = {h};
Mesh.CharacteristicLengthMax = {h};
"""

PRO = """Group { Domain=Region[1]; Outer=Region[2]; }
Function { js[] = Vector[0,0,2*Pi^2*Sin[Pi*X[]]*Sin[Pi*Y[]]]; }
Constraint { {Name A; Case {{Region Outer; Value 0.;}}} }
FunctionSpace { {Name Hcurl_a; Type Form1P;
 BasisFunction {{Name se; NameOfCoef ae; Function BF_PerpendicularEdge;
 Support Domain; Entity NodesOf[All];}}
 Constraint {{NameOfCoef ae; EntityType NodesOf; NameOfConstraint A;}}} }
Jacobian {{Name Vol; Case {{Region All; Jacobian Vol;}}}}
Integration {{Name I1; Case {{Type Gauss; Case {
 {GeoElement Triangle; NumberOfPoints 3;}
 {GeoElement Line; NumberOfPoints 2;}}}}}}
Formulation {{Name MagSta; Type FemEquation;
 Quantity {{Name a; Type Local; NameOfSpace Hcurl_a;}}
 Equation {
 Galerkin {[Dof{d a},{d a}]; In Domain; Jacobian Vol; Integration I1;}
 Galerkin {[-js[],{a}]; In Domain; Jacobian Vol; Integration I1;}
 }}}
Resolution {{Name MagSta; System {{Name S; NameOfFormulation MagSta;}}
 Operation {Generate[S]; Solve[S]; SaveSolution[S];}}}
PostProcessing {{Name MagSta; NameOfFormulation MagSta; Quantity {
 {Name a; Value {Local {[CompZ[{a}]]; In Domain; Jacobian Vol;}}}
 {Name b; Value {Local {[{d a}]; In Domain; Jacobian Vol;}}}
 }}}
PostOperation {{Name Fields; NameOfPostProcessing MagSta; Operation {
 Print[a, OnElementsOf Domain, File "a.pos"];
 Print[b, OnElementsOf Domain, File "b.pos"];
 }}}
"""


def samples(text, components):
    token = "ST" if components == 1 else "VT"
    entries = re.findall(token + r"\(([^)]+)\)\{([^}]+)\}", text)
    if not entries:
        raise ValueError("missing native triangle field output")
    points, values, weights = [], [], []
    barycentric = ((2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6), (1 / 6, 1 / 6, 2 / 3))
    for coordinates, field in entries:
        xyz = [float(v) for v in coordinates.split(",")]
        numbers = [float(v) for v in field.split(",")]
        if (
            len(xyz) != 9
            or len(numbers) != 3 * components
            or not all(math.isfinite(v) for v in (*xyz, *numbers))
        ):
            raise ValueError("native field shape/nonfinite refusal")
        x = xyz[0::3]
        y = xyz[1::3]
        area = abs((x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0])) / 2
        if area <= 0:
            raise ValueError("degenerate triangle")
        for b in barycentric:
            points.append(
                [sum(a * v for a, v in zip(b, x)), sum(a * v for a, v in zip(b, y))]
            )
            value = [
                sum(b[i] * numbers[i * components + j] for i in range(3))
                for j in range(components)
            ]
            values.append(value[0] if components == 1 else value)
            weights.append(area / 3)
    if abs(sum(weights) - 1) > 1e-7:
        raise ValueError("export must cover the unit square, not a partial field")
    return points, values, weights


def run_rung(directory, n):
    directory.mkdir()
    (directory / "mesh.geo").write_text(GEO.format(h=1 / n))
    (directory / "case.pro").write_text(PRO)
    for command in (
        ["gmsh", "mesh.geo", "-2", "-format", "msh2", "-o", "mesh.msh"],
        ["getdp", "case.pro", "-msh", "mesh.msh", "-solve", "MagSta", "-pos", "Fields"],
    ):
        completed = subprocess.run(
            command, cwd=directory, capture_output=True, timeout=120, check=False
        )
        (directory / ("gmsh.log" if command[0] == "gmsh" else "getdp.log")).write_bytes(
            completed.stdout + completed.stderr
        )
        if completed.returncode:
            raise RuntimeError("native reference verification command failed")
    raw = (directory / "a.pos").read_bytes()
    p, v, w = samples(raw.decode(), 1)
    field = {"h": 1 / n, "t": 0, "points": p, "values": v, "weights": w}
    # Keep the native flux output; a separate order-1 diagnostic is mandatory.
    bp, bv, bw = samples((directory / "b.pos").read_text(), 3)
    flux_error = (
        sum(
            weight
            * (
                (b[0] - math.pi * math.sin(math.pi * x) * math.cos(math.pi * y)) ** 2
                + (b[1] + math.pi * math.cos(math.pi * x) * math.sin(math.pi * y)) ** 2
                + b[2] ** 2
            )
            for (x, y), b, weight in zip(bp, bv, bw, strict=True)
        )
        ** 0.5
    )
    return field, "sha256:" + hashlib.sha256(raw).hexdigest(), flux_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--spec-digest", required=True)
    args = parser.parse_args()
    for command, expected in (
        (["getdp", "--version"], "3.5.0"),
        (["gmsh", "--version"], "4.15.2"),
    ):
        result = subprocess.run(command, capture_output=True, timeout=10, check=True)
        if expected not in (result.stdout + result.stderr).decode():
            raise RuntimeError("wrong solver version; re-pin prospectively")
    args.work.mkdir(exist_ok=False)
    rows, raw, flux = [], [], []
    for n in (8, 16, 32):
        field, pin, error = run_rung(args.work / f"n{n}", n)
        rows.append(field)
        raw.append(pin)
        flux.append({"h": 1 / n, "l2_error": error})
    report = {
        "schema": "carbon.code-verification.fields.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "kind": "getdp-a",
        "family": "motor",
        "image_digest": args.image_digest,
        "spec_digest": args.spec_digest,
        "adapter_digest": "sha256:"
        + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
        "raw_outputs": raw,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    args.output.with_suffix(".flux.json").write_text(
        json.dumps(
            {
                "image_digest": args.image_digest,
                "rows": flux,
                "expected_order": 1,
                "recommended_order_band": [0.7, 1.3],
                "accepted_pass": None,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
