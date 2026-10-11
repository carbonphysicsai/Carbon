"""Native CPU fixed/free axial rod frequency ladder; Data Collection executes.

Analytic modes verify a subset of f08's modal route, not its full geometry.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

CORNERS = (
    (0, 0, 0),
    (2, 0, 0),
    (2, 2, 0),
    (0, 2, 0),
    (0, 0, 2),
    (2, 0, 2),
    (2, 2, 2),
    (0, 2, 2),
)
MIDS = (
    (1, 0, 0),
    (2, 1, 0),
    (1, 2, 0),
    (0, 1, 0),
    (1, 0, 2),
    (2, 1, 2),
    (1, 2, 2),
    (0, 1, 2),
    (0, 0, 1),
    (2, 0, 1),
    (2, 2, 1),
    (0, 2, 1),
)


def deck(n):
    if n not in (4, 8, 16):
        raise ValueError("registered rod refinement required")
    elements = [
        tuple((2 * i + a, b, c) for a, b, c in CORNERS + MIDS) for i in range(n)
    ]
    keys = sorted({point for element in elements for point in element})
    nodes = {point: i + 1 for i, point in enumerate(keys)}
    lines = ["*HEADING", "dimensionless axial code-verification rod", "*NODE"]
    lines += [f"{nodes[p]},{p[0]/(2*n)},{p[1]*0.05},{p[2]*0.05}" for p in keys]
    lines.append("*ELEMENT,TYPE=C3D20R,ELSET=ALL")
    for e, element in enumerate(elements, 1):
        ids = [str(nodes[p]) for p in element]
        lines += [f"{e}," + ",".join(ids[:15]) + ",", ",".join(ids[15:])]
    lines += ["*NSET,NSET=ROOT"] + [str(nodes[p]) for p in keys if p[0] == 0]
    lines += [
        "*NSET,NSET=NALL,GENERATE",
        f"1,{len(nodes)},1",
        "*BOUNDARY",
        "NALL,2,3",
        "ROOT,1,1",
        "*MATERIAL,NAME=UNIT",
        "*ELASTIC",
        "1.,0.",
        "*DENSITY",
        "1.",
        "*SOLID SECTION,ELSET=ALL,MATERIAL=UNIT",
        "*STEP",
        "*FREQUENCY",
        "3",
        "*END STEP",
    ]
    return "\n".join(lines) + "\n"


def frequencies(text):
    marker = "E I G E N V A L U E   O U T P U T"
    if text.count(marker) != 1:
        raise ValueError("one native eigenvalue table required")
    num = r"[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?"
    rows = re.findall(
        rf"^\s*([123])\s+({num})\s+({num})\s+({num})\s+({num})\s*$",
        text.split(marker)[1],
        re.MULTILINE,
    )
    if [int(r[0]) for r in rows] != [1, 2, 3]:
        raise ValueError("three ordered complete native frequencies required")
    return [float(r[3]) for r in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--spec-digest", required=True)
    args = parser.parse_args()
    args.work.mkdir(exist_ok=False)
    rows, raw = [], []
    for n in (4, 8, 16):
        directory = args.work / f"n{n}"
        directory.mkdir()
        (directory / "rod.inp").write_text(deck(n))
        done = subprocess.run(
            ["ccx", "-i", "rod"],
            cwd=directory,
            capture_output=True,
            timeout=120,
            check=False,
        )
        (directory / "solver.log").write_bytes(done.stdout + done.stderr)
        if done.returncode:
            raise RuntimeError("native rod verification failed")
        dat = (directory / "rod.dat").read_bytes()
        rows.append(
            {
                "h": 1 / n,
                "t": 0,
                "points": [[0], [1], [2]],
                "values": frequencies(dat.decode()),
                "weights": [1, 1, 1],
            }
        )
        raw.append("sha256:" + hashlib.sha256(dat).hexdigest())
    report = {
        "schema": "carbon.code-verification.fields.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "kind": "calculix-rod-mode",
        "family": "f08",
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
