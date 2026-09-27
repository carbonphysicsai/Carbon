"""Compare the solved heated channel with the closed-form laminar solution.

Fully developed plane Poiseuille flow between plates a gap H apart, both
walls heated with the same uniform flux, written as a wall-normal gradient
G = q''/k:
  Nu = h (2H) / k = 140 / 17                   (Shah & London)
  dTb/dx = 2 DT G / (U H)                      (energy balance)
where h = q'' / (Tw - Tb), so Nu = G (2H) / (Tw - Tb).

Reported, not judged: this script sets no pass threshold.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

NU, DT, U, H, G = 1e-6, 1e-6, 0.1, 1e-3, 1000.0
EXPECTED_NU = 140 / 17
EXPECTED_DTB_DX = 2 * DT * G / (U * H)
DEVELOPED = (0.060, 0.095)  # m; thermal entrance ~ 0.05 Re Pr (2H) = 20 mm


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


def slope(points):
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    return sum((x - mx) * (y - my) for x, y in points) / sum(
        (x - mx) ** 2 for x, _ in points
    )


def main(case):
    case = Path(case)
    flow = (case / "flowTime").read_text().split()[-1]
    last = (case / "latestTime").read_text().split()[-1]
    c = internal_field(case / last / "C")
    u = internal_field(case / flow / "U")
    t = internal_field(case / last / "T")
    columns = defaultdict(list)
    for (x, y, _), ui, ti in zip(c, u, t):
        columns[round(x, 12)].append((y, ui[0], ti))
    lo, hi = DEVELOPED
    nus, bulk = [], []
    for x in sorted(columns):
        if not lo <= x <= hi:
            continue
        cells = sorted(columns[x])
        dy = cells[1][0] - cells[0][0]
        tb = sum(ux * ti for _, ux, ti in cells) / sum(ux for _, ux, _ in cells)
        tw = ((cells[0][2] + G * dy / 2) + (cells[-1][2] + G * dy / 2)) / 2
        nus.append(G * 2 * H / (tw - tb))
        bulk.append((x, tb))
    nu = sum(nus) / len(nus)
    dtb = slope(bulk)
    flow_log = (case / "log.simpleFoam").read_text()
    t_log = (case / "log.scalarTransportFoam").read_text()
    t_initial = re.findall(r"Solving for T, Initial residual = ([-+0-9.eE]+)", t_log)
    result = {
        "run": json.loads((case / "run.json").read_text()),
        "flow_converged_to_residual_control": "SIMPLE solution converged" in flow_log,
        "temperature_iterations": len(t_initial),
        "temperature_last_initial_residual": float(t_initial[-1]),
        "columns": len(nus),
        "nusselt": nu,
        "nusselt_expected": EXPECTED_NU,
        "nusselt_rel_error": (nu - EXPECTED_NU) / EXPECTED_NU,
        "nusselt_spread_over_columns": max(nus) - min(nus),
        "dTb_dx": dtb,
        "dTb_dx_expected": EXPECTED_DTB_DX,
        "dTb_dx_rel_error": (dtb - EXPECTED_DTB_DX) / EXPECTED_DTB_DX,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
