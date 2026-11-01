"""CalculiX code verification for the F08 2.0 stress output: a patch test and a manufactured-solution (MMS) check.

On the pinned CalculiX image, a quadratic-tetrahedron (C3D10) solve must reproduce, EXACTLY (to solver precision), any
displacement field in its own interpolation space. This harness builds a box of C3D10 elements in pure Python (Kuhn
tetrahedra, midside nodes in ccx order), prescribes a manufactured displacement field on every boundary node, applies the
body force that field needs for equilibrium (uniform for a quadratic field, so one `*DLOAD ... GRAV` line), and compares
the solver's interior displacements and per-element MEAN stress with the analytic values:

- field degree 1: the classical PATCH TEST (constant stress, no body force);
- field degree 2: the MMS check (linear stress, uniform body force).

The mean of the four Gauss-point stresses of a C3D10 element equals the stress at the element centroid for a linear
stress field, so the check does not depend on the solver's integration-point numbering. Material values here are
arguments (test values), never registered ones. Nothing in this module runs a solve; `compare` takes the solver's .dat.

    python3 f08_mms_v2.py write OUTDIR [--n 2] [--degree 2]       # the case: mesh.inp, case.inp, expected.json
    python3 f08_mms_v2.py compare OUTDIR                          # after ccx: expected.json vs case.dat
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f08_deck_v2 as v2
import f08_proof as proof

#: Kuhn's split of a unit cube into six tetrahedra sharing the main diagonal (a conforming triangulation).
CUBE = [
    (0, 0, 0),
    (1, 0, 0),
    (1, 1, 0),
    (0, 1, 0),
    (0, 0, 1),
    (1, 0, 1),
    (1, 1, 1),
    (0, 1, 1),
]
KUHN = [
    (0, 1, 2, 6),
    (0, 2, 3, 6),
    (0, 3, 7, 6),
    (0, 7, 4, 6),
    (0, 4, 5, 6),
    (0, 5, 1, 6),
]
#: ccx C3D10 midside nodes 5..10 lie on corner edges (1-2), (2-3), (3-1), (1-4), (2-4), (3-4).
MIDSIDE = ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))
#: The default manufactured field's coefficients: u_i = sum_j A[i][j] x_j + sum_{j<=k} Q[i][(j,k)] x_j x_k (mm).
DEFAULT_A = (
    (1.0e-3, 2.0e-4, -1.0e-4),
    (3.0e-4, -5.0e-4, 2.0e-4),
    (-2.0e-4, 1.0e-4, 8.0e-4),
)
DEFAULT_Q = (
    {(0, 0): 4.0e-5, (1, 2): -3.0e-5},
    {(1, 1): 2.0e-5, (0, 2): 5.0e-5},
    {(2, 2): -4.0e-5, (0, 1): 1.0e-5},
)


class Refused(ValueError):
    pass


def _volume(coords, c):
    a, b, d, e = (coords[i] for i in c[:4])
    u = [b[k] - a[k] for k in range(3)]
    v = [d[k] - a[k] for k in range(3)]
    w = [e[k] - a[k] for k in range(3)]
    return (
        u[0] * (v[1] * w[2] - v[2] * w[1])
        - u[1] * (v[0] * w[2] - v[2] * w[0])
        + u[2] * (v[0] * w[1] - v[1] * w[0])
    ) / 6.0


def box_mesh(n, size=(10.0, 8.0, 6.0)):
    """A box of ``n`` x ``n`` x ``n`` cells, six C3D10 tetrahedra each: ``(coords, elements)``; node ids start at 1."""
    if n < 1:
        raise Refused("mesh_needs_a_cell")
    nodes, ids = {}, {}

    def node(point):
        key = tuple(round(x, 12) for x in point)
        if key not in ids:
            ids[key] = len(ids) + 1
            nodes[ids[key]] = key
        return ids[key]

    elements = []
    h = [size[k] / n for k in range(3)]
    for i, j, k in itertools.product(range(n), repeat=3):
        corners = [
            ((i + c[0]) * h[0], (j + c[1]) * h[1], (k + c[2]) * h[2]) for c in CUBE
        ]
        for tet in KUHN:
            pts = [corners[t] for t in tet]
            ids4 = [node(p) for p in pts]
            mids = [
                node(tuple((pts[a][m] + pts[b][m]) / 2.0 for m in range(3)))
                for a, b in MIDSIDE
            ]
            conn = ids4 + mids
            if _volume(nodes, conn) < 0:  # keep every element positively oriented
                conn[1], conn[2] = conn[2], conn[1]
                conn[4], conn[6], conn[8], conn[9] = (
                    conn[6],
                    conn[4],
                    conn[9],
                    conn[8],
                )
                # swapping corners 2 and 3 swaps edges (1-2)<->(1-3), (2-4)<->(3-4); (2-3) and (1-4) stay
            elements.append(conn)
    return nodes, elements


def on_boundary(point, size, tol=1e-9):
    return any(abs(point[k]) < tol or abs(point[k] - size[k]) < tol for k in range(3))


def field_u(x, a=DEFAULT_A, q=DEFAULT_Q):
    return [
        sum(a[i][j] * x[j] for j in range(3))
        + sum(c * x[j] * x[k] for (j, k), c in q[i].items())
        for i in range(3)
    ]


def field_grad(x, a=DEFAULT_A, q=DEFAULT_Q):
    """du_i/dx_j."""
    g = [[a[i][j] for j in range(3)] for i in range(3)]
    for i in range(3):
        for (j, k), c in q[i].items():
            g[i][j] += c * x[k]
            g[i][k] += c * x[j]
    return g


def sigma(x, young, nu, a=DEFAULT_A, q=DEFAULT_Q):
    """Cauchy stress (sxx, syy, szz, sxy, sxz, syz) of the field at ``x`` (isotropic linear elasticity)."""
    g = field_grad(x, a, q)
    eps = [[0.5 * (g[i][j] + g[j][i]) for j in range(3)] for i in range(3)]
    lam = young * nu / ((1 + nu) * (1 - 2 * nu))
    mu = young / (2 * (1 + nu))
    tr = eps[0][0] + eps[1][1] + eps[2][2]
    s = [[lam * tr * (i == j) + 2 * mu * eps[i][j] for j in range(3)] for i in range(3)]
    return [s[0][0], s[1][1], s[2][2], s[0][1], s[0][2], s[1][2]]


def body_force(young, nu, a=DEFAULT_A, q=DEFAULT_Q):
    """b_i = -d sigma_ij / d x_j: uniform for a quadratic field (sigma is linear), found by central differences on the
    exact linear stress (exact to rounding)."""
    h = 1.0
    out = []
    for i in range(3):
        total = 0.0
        for j in range(3):
            lo, hi = [0.0] * 3, [0.0] * 3
            hi[j], lo[j] = h, -h
            s_hi, s_lo = sigma(hi, young, nu, a, q), sigma(lo, young, nu, a, q)
            index = _tensor_index(i, j)
            total += (s_hi[index] - s_lo[index]) / (2 * h)
        out.append(-total)
    return out


def _tensor_index(i, j):
    return {
        (0, 0): 0,
        (1, 1): 1,
        (2, 2): 2,
        (0, 1): 3,
        (1, 0): 3,
        (0, 2): 4,
        (2, 0): 4,
        (1, 2): 5,
        (2, 1): 5,
    }[(i, j)]


def write_case(
    out, *, n=2, degree=2, young=70000.0, nu=0.33, rho=2.7e-9, size=(10.0, 8.0, 6.0)
):
    """Write mesh.inp, case.inp and expected.json for one verification case. ``degree`` 1 = patch test, 2 = MMS."""
    if degree not in (1, 2):
        raise Refused("degree_is_1_or_2")
    q = DEFAULT_Q if degree == 2 else ({}, {}, {})
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    nodes, elements = box_mesh(n, size)
    boundary = sorted(i for i, p in nodes.items() if on_boundary(p, size))
    lines = ["*NODE"] + [
        f"{i},{p[0]:.12g},{p[1]:.12g},{p[2]:.12g}" for i, p in sorted(nodes.items())
    ]
    lines.append("*ELEMENT,TYPE=C3D10,ELSET=EALL")
    lines += [f"{e}," + ",".join(map(str, c)) for e, c in enumerate(elements, 1)]
    (out / "mesh.inp").write_text("\n".join(lines) + "\n")
    bf = body_force(young, nu, DEFAULT_A, q)
    magnitude = math.sqrt(sum(x * x for x in bf))
    deck = [
        "*HEADING",
        f"f08 2.0 code verification degree={degree} n={n} tables=TEST_ONLY",
        "*INCLUDE,INPUT=mesh.inp",
        "*MATERIAL,NAME=TESTMAT",
        "*ELASTIC",
        f"{young},{nu}",
        "*DENSITY",
        f"{rho}",
        "*SOLID SECTION,ELSET=EALL,MATERIAL=TESTMAT",
        "*BOUNDARY",
    ]
    for i in boundary:
        u = field_u(nodes[i], DEFAULT_A, q)
        deck += [f"{i},{d + 1},{d + 1},{u[d]:.12g}" for d in range(3)]
    # the F08 2.0 PaStiX re-pin (f08_deck_v2.SOLVER): a versioned deck migration, every deck sha256 changes
    deck += ["*STEP", f"*STATIC,SOLVER={v2.SOLVER}"]
    if magnitude > 0:
        direction = [x / magnitude for x in bf]
        # body force density = rho * g * direction, so g = |b| / rho
        deck.append("*DLOAD")
        deck.append(
            f"EALL,GRAV,{magnitude / rho:.12g},{direction[0]:.12g},{direction[1]:.12g},{direction[2]:.12g}"
        )
    deck += ["*NODE PRINT,NSET=NALL", "U", "*EL PRINT,ELSET=EALL", "S", "*END STEP"]
    deck.insert(deck.index("*MATERIAL,NAME=TESTMAT"), "*NSET,NSET=NALL,GENERATE")
    deck.insert(deck.index("*MATERIAL,NAME=TESTMAT"), f"1,{len(nodes)},1")
    (out / "case.inp").write_text("\n".join(deck) + "\n")
    expected = {
        "degree": degree,
        "n": n,
        "young": young,
        "nu": nu,
        "interior": {
            str(i): field_u(p, DEFAULT_A, q)
            for i, p in nodes.items()
            if i not in set(boundary)
        },
        "mean_stress": {
            str(e): sigma(_centroid(nodes, c), young, nu, DEFAULT_A, q)
            for e, c in enumerate(elements, 1)
        },
        "body_force": bf,
        "tables": "TEST_ONLY",
    }
    (out / "expected.json").write_text(json.dumps(expected, sort_keys=True) + "\n")
    return {"nodes": len(nodes), "elements": len(elements), "boundary": len(boundary)}


def _centroid(nodes, conn):
    return [sum(nodes[i][k] for i in conn[:4]) / 4.0 for k in range(3)]


def compare(expected, dat_text, *, tol_u=1e-7, tol_s=1e-6):
    """The solver's interior displacements and per-element mean stress against ``expected`` (relative to the field's
    scale). Returns the worst errors and ``ok``; refuses a .dat without a displacement or stress block.
    """
    steps = proof.parse_dat(dat_text)
    if not steps or not steps[0]["events"]:
        raise Refused("no_displacement_block")
    displacements = steps[0]["events"][0][1]
    blocks = v2.parse_stress_blocks(dat_text)
    if not blocks:
        raise Refused("no_stress_block")
    scale_u = max(abs(c) for u in expected["interior"].values() for c in u) or 1.0
    worst_u = max(
        abs(displacements[int(i)][d] - u[d]) / scale_u
        for i, u in expected["interior"].items()
        for d in range(3)
    )
    by_element = {}
    for element, _ip, s in blocks[0]:
        by_element.setdefault(element, []).append(s)
    scale_s = max(abs(c) for s in expected["mean_stress"].values() for c in s) or 1.0
    worst_s = 0.0
    for element, truth in expected["mean_stress"].items():
        rows = by_element.get(int(element))
        if not rows:
            raise Refused("stress_element_missing")
        mean = [sum(r[k] for r in rows) / len(rows) for k in range(6)]
        worst_s = max(worst_s, max(abs(mean[k] - truth[k]) for k in range(6)) / scale_s)
    return {
        "worst_displacement_rel": worst_u,
        "worst_mean_stress_rel": worst_s,
        "ok": worst_u <= tol_u and worst_s <= tol_s,
        "degree": expected["degree"],
        "tables": expected["tables"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("out")
    w.add_argument("--n", type=int, default=2)
    w.add_argument("--degree", type=int, default=2)
    c = sub.add_parser("compare")
    c.add_argument("out")
    args = parser.parse_args(argv)
    if args.cmd == "write":
        print(json.dumps(write_case(args.out, n=args.n, degree=args.degree)))
        return 0
    out = Path(args.out)
    result = compare(
        json.loads((out / "expected.json").read_text()),
        (out / "case.dat").read_text(errors="replace"),
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
