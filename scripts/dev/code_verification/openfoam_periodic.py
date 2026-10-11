"""CPU periodic scalar transport analytic check; Data Collection executes.

Prescribed velocity, not a flow-solver verification or f17 adequacy claim.
"""

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path


def header(name, kind="dictionary"):
    return f"FoamFile {{ version 2.0; format ascii; class {kind}; object {name}; }}\n"


def dictionaries(n):
    if n not in (16, 32, 64):
        raise ValueError("registered scalar ladder required")
    mesh = header("blockMeshDict") + """scale 1;
vertices ((0 0 0)(1 0 0)(1 .1 0)(0 .1 0)(0 0 .1)(1 0 .1)(1 .1 .1)(0 .1 .1));
blocks (hex (0 1 2 3 4 5 6 7) (N 1 1) simpleGrading (1 1 1));
edges ();
boundary (
 left {type cyclic; neighbourPatch right; faces ((0 4 7 3));}
 right {type cyclic; neighbourPatch left; faces ((1 2 6 5));}
 walls {type patch; faces ((0 1 5 4)(3 7 6 2));}
 frontBack {type empty; faces ((0 3 2 1)(4 5 6 7));}
);
mergePatchPairs ();
""".replace("(N 1 1)", f"({n} 1 1)")
    bc = """boundaryField {
 left {type cyclic;} right {type cyclic;}
 walls {type zeroGradient;} frontBack {type empty;}
}
"""
    values = [1 + 0.2 * math.sin(2 * math.pi * (i + 0.5) / n) for i in range(n)]
    scalar = (
        header("T", "volScalarField")
        + "dimensions [0 0 0 0 0 0 0];\n"
        + f"internalField nonuniform List<scalar>\n{n}\n(\n"
        + "\n".join(f"{x:.17g}" for x in values)
        + "\n);\n"
        + bc
    )
    return {
        "system/blockMeshDict": mesh,
        "system/controlDict": header("controlDict")
        + """application scalarTransportFoam;
startFrom startTime; startTime 0; stopAt endTime; endTime .125;
deltaT .0001220703125; writeControl timeStep; writeInterval 1024;
purgeWrite 0; writeFormat ascii; writePrecision 16;
timeFormat general; timePrecision 12; runTimeModifiable false;
""",
        "system/fvSchemes": header("fvSchemes")
        + """ddtSchemes {default backward;}
gradSchemes {default Gauss linear;}
divSchemes {default none; div(phi,T) Gauss linear;}
laplacianSchemes {default Gauss linear corrected;}
interpolationSchemes {default linear;}
snGradSchemes {default corrected;}
""",
        "system/fvSolution": header("fvSolution")
        + """solvers {
 T {solver PBiCGStab; preconditioner DILU; tolerance 1e-12; relTol 0;}
}
SIMPLE {nNonOrthogonalCorrectors 0;}
""",
        "constant/transportProperties": header("transportProperties")
        + "DT [0 2 -1 0 0 0 0] .01;\n",
        "0/U": header("U", "volVectorField")
        + "dimensions [0 1 -1 0 0 0 0];\ninternalField uniform (1 0 0);\n"
        + bc,
        "0/T": scalar,
    }


def scalar_values(text, n):
    match = re.search(
        r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^)]+)\)\s*;", text
    )
    if match is None or int(match[1]) != n:
        raise ValueError("complete native nonuniform scalar output required")
    values = [float(x) for x in match[2].split()]
    if len(values) != n or not all(math.isfinite(x) for x in values):
        raise ValueError("finite full native field required")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--spec-digest", required=True)
    args = parser.parse_args()
    args.work.mkdir(exist_ok=False)
    rows, raw = [], []
    for n in (16, 32, 64):
        directory = args.work / f"n{n}"
        directory.mkdir()
        for name, contents in dictionaries(n).items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        for command in (["blockMesh"], ["scalarTransportFoam"]):
            result = subprocess.run(
                command, cwd=directory, capture_output=True, timeout=180, check=False
            )
            (directory / (command[0] + ".log")).write_bytes(
                result.stdout + result.stderr
            )
            if result.returncode:
                raise RuntimeError("native scalar verification failed")
        field = (directory / "0.125/T").read_bytes()
        rows.append(
            {
                "h": 1 / n,
                "t": 0.125,
                "points": [[(i + 0.5) / n] for i in range(n)],
                "values": scalar_values(field.decode(), n),
                "weights": [1 / n] * n,
            }
        )
        raw.append("sha256:" + hashlib.sha256(field).hexdigest())
    report = {
        "schema": "carbon.code-verification.fields.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "kind": "openfoam-periodic",
        "family": "f17",
        "image_digest": args.image_digest,
        "spec_digest": args.spec_digest,
        "adapter_digest": "sha256:"
        + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
        "raw_outputs": raw,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
