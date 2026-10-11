"""Smoke the pinned CalculiX image on upstream ccx 2.23 tests with no
network and a read-only root (REFERENCE-PACKAGES-01):

    beamf    eigenfrequencies of a beam (*FREQUENCY)
    beamdy8  steady-state dynamics with modal damping (*STEADY STATE DYNAMICS)
    beamdy9  the same family, another load/damping case

A test passes when every number in its .dat matches the upstream .dat.ref
within a relative 1e-4 (absolute floor 1e-8 times the file's largest
magnitude), the tolerance style of ccx's own compare script.

    python3 smoke.py IMAGE TEST_ARCHIVE OUTDIR
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path

TESTS = ("beamf", "beamdy8", "beamdy9")
NUMBER = re.compile(r"[-+]?\d*\.\d+(?:[EeDd][-+]?\d+)?|[-+]?\d+[EeDd][-+]?\d+")


def numbers(text):
    return [float(x.replace("D", "E").replace("d", "e")) for x in NUMBER.findall(text)]


def compare(dat, ref):
    a, b = numbers(dat), numbers(ref)
    if len(a) != len(b):
        return {"pass": False, "why": f"{len(a)} numbers vs {len(b)} in the reference"}
    scale = max((abs(x) for x in b), default=1.0)
    worst = 0.0
    for x, y in zip(a, b):
        diff = abs(x - y) / max(abs(y), 1e-8 * scale)
        worst = max(worst, diff)
    return {"pass": worst <= 1e-4, "max_rel_diff": worst, "numbers": len(a)}


def main(image, archive, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    with tarfile.open(archive) as tar:
        for name in TESTS:
            case = out / name
            case.mkdir(exist_ok=True)
            for suffix in (".inp", ".dat.ref"):
                member = f"./CalculiX/ccx_2.23/test/{name}{suffix}"
                (case / f"{name}{suffix}").write_bytes(tar.extractfile(member).read())
            start = time.monotonic()
            done = subprocess.run(
                ["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp", "--cpus", "1",
                 "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{case.resolve()}:/case", image,
                 "bash", "-c", f"ccx -i {name} > ccx.log 2>&1"],
                capture_output=True, text=True, check=False,
            )  # fmt: skip
            wall = time.monotonic() - start
            dat = case / f"{name}.dat"
            row = {"test": name, "exit": done.returncode, "wall_s": round(wall, 2)}
            if dat.exists():
                row.update(
                    compare(
                        dat.read_text(errors="replace"),
                        (case / f"{name}.dat.ref").read_text(errors="replace"),
                    )
                )
            else:
                row.update({"pass": False, "why": "no .dat written"})
            results.append(row)
            print(json.dumps(row), flush=True)
    return results


if __name__ == "__main__":
    main(*sys.argv[1:4])
