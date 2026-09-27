"""Compare the solved conjugate case with closed-form fully developed values.

A channel of gap H between two solid slabs of thickness t. Each slab's outer
face takes a uniform heat flux q, which in fully developed flow crosses the
slab by conduction and enters the fluid:
  solid drop  T_outer - T_interface = q t / k_s        (1D conduction)
  Nusselt     Nu = q (2H) / (k_f (T_w - T_b)) = 140/17  (Shah & London)
  energy      dT_b/dx = 2 q / (rho c_p U H)
  interface   the solid- and fluid-side interface temperatures agree
Reported, not judged: this script sets no pass threshold.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

Q, T_SLAB, H, U = 1e4, 0.5e-3, 1e-3, 0.1
K_S = 10.0
RHO, CP, MU, PR = 1000.0, 4181.0, 1e-3, 1.0
K_F = MU * CP / PR
EXPECTED = {
    "solid_drop_K": Q * T_SLAB / K_S,
    "nusselt": 140 / 17,
    "dTb_dx": 2 * Q / (RHO * CP * U * H),
}
DEVELOPED = (0.060, 0.095)


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


def columns(case, t, region, fields):
    c = internal_field(case / t / region / "C")
    data = [internal_field(case / t / region / f) for f in fields]
    out = defaultdict(list)
    for i, (x, y, _) in enumerate(c):
        out[round(x, 12)].append((y, *[d[i] for d in data]))
    return {x: sorted(v) for x, v in out.items()}


def slope(points):
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    return sum((x - mx) * (y - my) for x, y in points) / sum(
        (x - mx) ** 2 for x, _ in points
    )


def last_initial(log, field):
    found = re.findall(rf"Solving for {field}, Initial residual = ([-+0-9.eE]+)", log)
    return float(found[-1]) if found else None


def main(case):
    case = Path(case)
    t = (case / "latestTime").read_text().split()[-1]
    fluid = columns(case, t, "fluid", ("U", "T"))
    bottom = columns(case, t, "solidBottom", ("T",))
    top = columns(case, t, "solidTop", ("T",))
    lo, hi = DEVELOPED
    nus, drops, gaps, bulk = [], [], [], []
    for x in sorted(fluid):
        if not lo <= x <= hi:
            continue
        cells = fluid[x]
        dyf = cells[1][0] - cells[0][0]
        tb = sum(u[0] * tt for _, u, tt in cells) / sum(u[0] for _, u, _ in cells)
        tw_f_bottom = cells[0][2] + Q * (dyf / 2) / K_F
        tw_f_top = cells[-1][2] + Q * (dyf / 2) / K_F
        nus.append(Q * 2 * H / (K_F * ((tw_f_bottom + tw_f_top) / 2 - tb)))
        bulk.append((x, tb))
        for slab, outer_first, tw_f in (
            (bottom, True, tw_f_bottom),
            (top, False, tw_f_top),
        ):
            s = slab[x]
            dys = s[1][0] - s[0][0]
            outer_cell, inner_cell = (s[0], s[-1]) if outer_first else (s[-1], s[0])
            t_outer = outer_cell[1] + Q * (dys / 2) / K_S
            t_inner = inner_cell[1] - Q * (dys / 2) / K_S
            drops.append(t_outer - t_inner)
            gaps.append(t_inner - tw_f)
    log = (case / "log.chtMultiRegionSimpleFoam").read_text()
    result = {
        "run": json.loads((case / "run.json").read_text()),
        "iterations": int(float(t)),
        "last_initial_residual": {
            f: last_initial(log, f) for f in ("h", "Ux", "p_rgh")
        },
        "columns": len(nus),
        "solid_drop_K": sum(drops) / len(drops),
        "solid_drop_expected_K": EXPECTED["solid_drop_K"],
        "solid_drop_rel_error": sum(drops) / len(drops) / EXPECTED["solid_drop_K"] - 1,
        "nusselt": sum(nus) / len(nus),
        "nusselt_expected": EXPECTED["nusselt"],
        "nusselt_rel_error": sum(nus) / len(nus) / EXPECTED["nusselt"] - 1,
        "interface_gap_K_max_abs": max(abs(g) for g in gaps),
        "dTb_dx": slope(bulk),
        "dTb_dx_expected": EXPECTED["dTb_dx"],
        "dTb_dx_rel_error": slope(bulk) / EXPECTED["dTb_dx"] - 1,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
