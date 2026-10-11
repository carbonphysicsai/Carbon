"""Headless CPU acoustic MMS, reusing #1030's unit-cube mesh generator.

Linear hex arm verifies HelmholtzSolve, not f13's quadratic-tetra mesh/ports.
Data Collection runs this after #1030 merges; no package builder here.
"""

import argparse
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

SIF = """Header
 Mesh DB "." "mesh"
End
Simulation
 Coordinate System = Cartesian 3D
 Simulation Type = Steady State
 Steady State Max Iterations = 1
 Frequency = {frequency}
End
Body 1
 Equation = 1
 Material = 1
 Body Force = 1
End
Equation 1
 Active Solvers(2) = 1 2
End
Material 1
 Density = 1.0
 Sound Speed = 1.0
End
Body Force 1
 Pressure Source 1 = Variable Coordinate 1, Coordinate 2, Coordinate 3
  Real MATC "(3*pi^2-1)*sin(pi*tx(0))*sin(pi*tx(1))*sin(pi*tx(2))"
 Pressure Source 2 = Variable Coordinate 1, Coordinate 2, Coordinate 3
  Real MATC "0.5*(3*pi^2-1)*sin(pi*tx(0))*sin(pi*tx(1))*sin(pi*tx(2))"
End
Solver 1
 Equation = Helmholtz
 Procedure = "HelmholtzSolve" "HelmholtzSolver"
 Variable = Pressure[Pressure 1:1 Pressure 2:1]
 Variable Dofs = 2
 Linear System Solver = Direct
 Linear System Direct Method = Umfpack
 Nonlinear System Max Iterations = 1
End
Solver 2
 Exec Solver = After Simulation
 Equation = ResultOutput
 Procedure = "ResultOutputSolve" "ResultOutputSolver"
 Output File Name = final
 Vtu Format = Logical True
 Ascii Output = Logical True
End
Boundary Condition 1
 Target Boundaries(1) = 1
 Pressure 1 = 0.0
 Pressure 2 = 0.0
End
"""


def read_fields(path):
    root = ET.parse(path).getroot()
    points = root.find(".//Points/DataArray")
    if points is None or points.attrib.get("format", "ascii") != "ascii":
        raise ValueError("explicit native ASCII points required")
    coordinates = list(map(float, points.text.split()))
    if len(coordinates) % 3:
        raise ValueError("complete native coordinates required")
    xyz = [coordinates[i : i + 3] for i in range(0, len(coordinates), 3)]
    fields = {}
    for node in root.findall(".//PointData/DataArray"):
        name = node.attrib.get("Name", "").lower()
        if name not in ("pressure", "pressure 1", "pressure 2"):
            continue
        if node.attrib.get("format", "ascii") != "ascii":
            raise ValueError("explicit native ASCII field required")
        values = list(map(float, node.text.split()))
        if name == "pressure" and node.attrib.get("NumberOfComponents") == "2":
            fields["real"], fields["imag"] = values[0::2], values[1::2]
        elif name == "pressure 1":
            fields["real"] = values
        elif name == "pressure 2":
            fields["imag"] = values
    if set(fields) != {"real", "imag"} or any(
        len(v) != len(xyz) for v in fields.values()
    ):
        raise ValueError("complete complex native pressure required")
    return xyz, fields


def main():
    from scripts.dev.reference_packages.elmer.mms_heat import write_mesh

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--spec-digest", required=True)
    args = parser.parse_args()
    args.work.mkdir(exist_ok=False)
    rows, raw, imag = [], [], []
    for n in (8, 16, 32):
        directory = args.work / f"n{n}"
        write_mesh(directory, n)
        (directory / "case.sif").write_text(SIF.format(frequency=1 / (2 * math.pi)))
        result = subprocess.run(
            ["ElmerSolver", "case.sif"],
            cwd=directory,
            capture_output=True,
            timeout=120,
            check=False,
        )
        (directory / "solver.log").write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("native Helmholtz verification failed")
        outputs = list(directory.glob("final*.vtu"))
        if len(outputs) != 1:
            raise ValueError("one native final field required")
        xyz, fields = read_fields(outputs[0])
        rows.append(
            {
                "h": 1 / n,
                "t": 0,
                "points": xyz,
                "values": fields["real"],
                "weights": [1] * len(xyz),
            }
        )
        raw.append("sha256:" + hashlib.sha256(outputs[0].read_bytes()).hexdigest())
        imag.append(
            {
                "h": 1 / n,
                "l2_error": math.sqrt(
                    sum(
                        (v - 0.5 * math.prod(math.sin(math.pi * x) for x in p)) ** 2
                        for p, v in zip(xyz, fields["imag"], strict=True)
                    )
                    / len(xyz)
                ),
            }
        )
    report = {
        "schema": "carbon.code-verification.fields.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "kind": "elmer-helmholtz",
        "family": "f13",
        "image_digest": args.image_digest,
        "spec_digest": args.spec_digest,
        "adapter_digest": "sha256:"
        + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
        "raw_outputs": raw,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    args.output.with_suffix(".imag.json").write_text(
        json.dumps(
            {
                "rows": imag,
                "accepted_pass": None,
                "scope": "linear hex complex-field code verification; quadratic tetra and ports remain separate",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
