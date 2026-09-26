"""Compare the solved channel with the closed-form laminar solution.

Fully developed plane Poiseuille flow between plates a gap H apart, mean
velocity U, kinematic viscosity nu:
  dp/dx = -12 nu U / H^2   (kinematic pressure)
  u_max = 1.5 U
Reported, not judged: this script sets no pass threshold.
"""

import json
import re
import sys
from pathlib import Path

NU, U, H = 1e-6, 0.1, 1e-3
EXPECTED_DPDX = -12 * NU * U / H**2
EXPECTED_UMAX = 1.5 * U
DEVELOPED = (0.060, 0.095)  # m; entrance length ~ 0.05 Re Dh = 20 mm


def internal_field(path):
    text = Path(path).read_text()
    body = text.split("internalField", 1)[1]
    count = int(re.search(r"\n(\d+)\n\(", body).group(1))
    start = body.index("(", body.index(str(count))) + 1
    items = re.findall(r"\(([^()]*)\)|([-+0-9.eE]+)", body[start:])
    values = []
    for vec, scalar in items:
        values.append(tuple(map(float, vec.split())) if vec else float(scalar))
        if len(values) == count:
            break
    return values


def main(case):
    case = Path(case)
    t = (case / "latestTime").read_text().split()[-1]
    c = internal_field(case / t / "C")
    p = internal_field(case / t / "p")
    u = internal_field(case / t / "U")
    lo, hi = DEVELOPED
    pts = [(x, pi) for (x, _, _), pi in zip(c, p) if lo <= x <= hi]
    n = len(pts)
    mx = sum(x for x, _ in pts) / n
    mp = sum(v for _, v in pts) / n
    slope = sum((x - mx) * (v - mp) for x, v in pts) / sum(
        (x - mx) ** 2 for x, _ in pts
    )
    xs = max(x for (x, _, _) in c if x <= hi)
    umax = max(v[0] for (x, _, _), v in zip(c, u) if abs(x - xs) < 1e-12)
    converged = "SIMPLE solution converged" in (case / "log.simpleFoam").read_text()
    result = {
        "run": json.loads((case / "run.json").read_text()),
        "iterations": int(t),
        "converged_to_residual_control": converged,
        "dpdx": slope,
        "dpdx_expected": EXPECTED_DPDX,
        "dpdx_rel_error": (slope - EXPECTED_DPDX) / EXPECTED_DPDX,
        "umax": umax,
        "umax_expected": EXPECTED_UMAX,
        "umax_rel_error": (umax - EXPECTED_UMAX) / EXPECTED_UMAX,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
