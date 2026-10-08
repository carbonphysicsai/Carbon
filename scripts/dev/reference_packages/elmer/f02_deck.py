"""f02 burst-thermal decks for the pinned Elmer image (REFERENCE-PACKAGES-01).

    python -m scripts.dev.reference_packages.elmer.f02_deck case LABEL --out DIR [--mesh 2] [--dt-scale 0.5]

The packet's stack (round1/f02-burst-thermal.md, requirements.json): silicon
20 x 20 x 0.5 mm on TIM 20 x 20 x 0.2 mm on copper 30 x 30 x 2 mm, centred,
perfect contact, Robin cooling on the whole underside, every other exposed
face insulated. Two 8 x 8 mm patches on the die top at x = -5 and +5 mm carry
the power split (left takes the larger share). Base 20 W throughout; the burst
starts at 20 s; rectangular, ramp and two-pulse waveforms; horizon 120 s.

The mesh is a structured hexahedral grid written directly as an Elmer mesh
database (no external mesher): x and y breakpoints at every layer and patch
edge, graded z layers. Time steps are aligned with every source event and
finer through the burst; the die-top maximum is recorded at every solver
step, so the peak search is over every step, not 0.5 s samples. The 1D slab
control (`slab=True`) is the copper layer alone with uniform flux over its
whole top, compared with the exact series (`slab_top_rise`).
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MM = 1e-3
LAYERS = {  # name: (half side mm, thickness mm, k, rho, cp)
    "copper": (15.0, 2.0, 390.0, 8960.0, 385.0),
    "tim": (10.0, 0.2, 5.0, 2500.0, 1000.0),
    "die": (10.0, 0.5, 130.0, 2330.0, 700.0),
}
NAMES = ("copper", "tim", "die")
PATCH_HALF, PATCH_X = 4.0, 5.0
HORIZON_S, BURST_START_S, BASE_W = 120.0, 20.0, 20.0
LIMIT_C = 95.0
PANELS = Path(
    ROOT, "docs/development/challenge_pipeline/round1/reference-route-panels.json"
)


def panel_case(label):
    d = json.loads(PANELS.read_text())["families"]["f02"]
    row = next(c for c in d["public_cases"] if c["label"] == label)
    return dict(zip(d["panel_fields"], row["parameters"]))


# --- mesh ----------------------------------------------------------------------------


def _axis(breaks, size):
    pts = [breaks[0]]
    for a, b in itertools.pairwise(breaks):
        n = max(1, math.ceil((b - a) / size - 1e-9))
        pts += [a + (b - a) * i / n for i in range(1, n + 1)]
    return pts


def _graded(t, n, ratio):
    """n cells over thickness t, geometric, finest at both ends."""
    w = [ratio ** min(i, n - 1 - i) for i in range(n)]
    s = sum(w)
    out, acc = [0.0], 0.0
    for x in w:
        acc += x
        out.append(t * acc / s)
    return out


def mesh(level=1, slab=False):
    """Nodes (mm), hexes (body, 8 node ids) and boundary quads (bc, parent,
    4 node ids). level 2 halves every cell size."""
    h = 1.0 / level
    if slab:
        xb, yb = [-15.0, 15.0], [-15.0, 15.0]
        xs, ys = _axis(xb, 7.5), _axis(yb, 7.5)
        layers = (("copper", 12 * level),)
    else:
        xb = [-15.0, -10.0, -9.0, -1.0, 1.0, 9.0, 10.0, 15.0]
        yb = [-15.0, -10.0, -4.0, 4.0, 10.0, 15.0]
        xs, ys = _axis(xb, h), _axis(yb, h)
        layers = (("copper", 6 * level), ("tim", 2 * level), ("die", 4 * level))
    zs, z0 = [], 0.0
    for name, n in layers:
        t = LAYERS[name][1]
        part = [z0 + z for z in _graded(t, n, 1.3)]
        zs += part if not zs else part[1:]
        z0 += t
    nx, ny, nz = len(xs), len(ys), len(zs)

    def nid(i, j, k):
        return 1 + i + nx * (j + ny * k)

    z_cu = LAYERS["copper"][1]
    z_tim = z_cu + LAYERS["tim"][1]
    hexes, owner = [], {}
    for k in range(nz - 1):
        zc = (zs[k] + zs[k + 1]) / 2
        for j in range(ny - 1):
            yc = (ys[j] + ys[j + 1]) / 2
            for i in range(nx - 1):
                xc = (xs[i] + xs[i + 1]) / 2
                if zc < z_cu:
                    body = 1
                elif abs(xc) < 10 and abs(yc) < 10:
                    body = 2 if zc < z_tim else 3
                else:
                    continue
                ids = [nid(i, j, k), nid(i + 1, j, k), nid(i + 1, j + 1, k), nid(i, j + 1, k),
                       nid(i, j, k + 1), nid(i + 1, j, k + 1), nid(i + 1, j + 1, k + 1), nid(i, j + 1, k + 1)]  # fmt: skip
                hexes.append((body, ids))
                owner[(i, j, k)] = len(hexes)
    quads, top = [], nz - 1
    for j in range(ny - 1):
        yc = (ys[j] + ys[j + 1]) / 2
        for i in range(nx - 1):
            xc = (xs[i] + xs[i + 1]) / 2
            quads.append(
                (
                    1,
                    owner[(i, j, 0)],
                    [
                        nid(i, j, 0),
                        nid(i + 1, j, 0),
                        nid(i + 1, j + 1, 0),
                        nid(i, j + 1, 0),
                    ],
                )
            )
            if (i, j, top - 1) not in owner:
                continue
            if slab or abs(yc) < PATCH_HALF and abs(xc + PATCH_X) < PATCH_HALF:
                bc = 2
            elif abs(yc) < PATCH_HALF and abs(xc - PATCH_X) < PATCH_HALF:
                bc = 3
            else:
                bc = 4
            quads.append((bc, owner[(i, j, top - 1)],
                          [nid(i, j, top), nid(i + 1, j, top), nid(i + 1, j + 1, top), nid(i, j + 1, top)]))  # fmt: skip
    used = {n for _b, ids in hexes for n in ids}
    nodes = {
        nid(i, j, k): (xs[i], ys[j], zs[k])
        for k in range(nz)
        for j in range(ny)
        for i in range(nx)
        if nid(i, j, k) in used
    }
    return nodes, hexes, quads


def write_mesh(out, level=1, slab=False):
    nodes, hexes, quads = mesh(level, slab)
    renum = {old: new for new, old in enumerate(sorted(nodes), start=1)}
    out = Path(out) / "mesh"
    out.mkdir(parents=True, exist_ok=True)
    (out / "mesh.header").write_text(
        f"{len(nodes)} {len(hexes)} {len(quads)}\n2\n808 {len(hexes)}\n404 {len(quads)}\n"
    )
    with (out / "mesh.nodes").open("w") as f:
        for old, (x, y, z) in sorted(nodes.items()):
            f.write(f"{renum[old]} -1 {x * MM!r} {y * MM!r} {z * MM!r}\n")
    with (out / "mesh.elements").open("w") as f:
        for e, (body, ids) in enumerate(hexes, start=1):
            f.write(f"{e} {body} 808 " + " ".join(str(renum[n]) for n in ids) + "\n")
    with (out / "mesh.boundary").open("w") as f:
        for b, (bc, parent, ids) in enumerate(quads, start=1):
            f.write(
                f"{b} {bc} {parent} 0 404 "
                + " ".join(str(renum[n]) for n in ids)
                + "\n"
            )
    return {
        "nodes": len(nodes),
        "hexes": len(hexes),
        "boundary_quads": len(quads),
        "level": level,
    }


# --- power schedule and time steps -----------------------------------------------


def schedule(case):
    """Piecewise-linear total power (t, W) knots; rectangles are steps."""
    peak, d, w = case["peak_w"], case["on_time_s"], case["waveform"]
    t0, eps = BURST_START_S, 1e-6
    if w == "rectangular":
        return [(0, BASE_W), (t0, BASE_W), (t0 + eps, peak), (t0 + d, peak),
                (t0 + d + eps, BASE_W), (HORIZON_S, BASE_W)]  # fmt: skip
    if w == "ramp":
        return [
            (0, BASE_W),
            (t0, BASE_W),
            (t0 + d, peak),
            (t0 + d + eps, BASE_W),
            (HORIZON_S, BASE_W),
        ]
    if w == "two-pulse":
        a = t0 + d / 2
        b = a + 10.0
        return [(0, BASE_W), (t0, BASE_W), (t0 + eps, peak), (a, peak), (a + eps, BASE_W), (b, BASE_W),
                (b + eps, peak), (b + d / 2, peak), (b + d / 2 + eps, BASE_W), (HORIZON_S, BASE_W)]  # fmt: skip
    if w == "constant":
        return [(0, peak), (HORIZON_S, peak)]
    raise ValueError(w)


def time_steps(case, scale=1.0):
    """(sizes, intervals): 0.1 s before the burst, 0.02 s from the burst to
    10 s after its last event, 0.1 s after; every event lands on a step
    boundary. `scale` 0.5 halves every step (the time witness)."""
    events = sorted({round(t, 6) for t, _ in schedule(case) if 0 < t < HORIZON_S})
    end = (max(events) + 10.0) if events else BURST_START_S + 10.0
    plan = [(BURST_START_S, 0.1), (end, 0.02), (HORIZON_S, 0.1)]
    sizes, intervals, t = [], [], 0.0
    for stop, dt in plan:
        for s in [e for e in events if t < e < stop] + [stop]:
            span = s - t
            n = max(1, round(span / (dt * scale)))
            sizes.append(span / n)
            intervals.append(n)
            t = s
    return sizes, intervals


# --- solver input ----------------------------------------------------------------


def _table(points):
    return "\n".join(f"      {t!r} {v!r}" for t, v in points)


def _bc(index, name, target, flux=None, robin=None):
    lines = [
        f"Boundary Condition {index}",
        f"  Target Boundaries(1) = {target}",
        f'  Name = "{name}"',
    ]
    if robin is not None:
        lines += [
            f"  Heat Transfer Coefficient = {robin[0]!r}",
            f"  External Temperature = {robin[1]!r}",
        ]
    if flux is not None:
        lines += ["  Heat Flux = Variable Time", "    Real", _table(flux), "    End"]
    lines += ["  Save Scalars = Logical True", "End", ""]
    return "\n".join(lines)


def sif(case, sizes, intervals, *, steady=False, source=True, direct=False, slab=False):
    sched = schedule(case) if source else [(0, 0.0), (HORIZON_S, 0.0)]
    if steady:
        p = BASE_W if source else 0.0
        sched = [(0, p), (HORIZON_S, p)]
    h, tc = case["h_w_m2_k"], case["coolant_c"] + 273.15
    bcs = _bc(1, "underside", 1, robin=(h, tc))
    if slab:
        area = (2 * LAYERS["copper"][0] * MM) ** 2
        bcs += _bc(2, "slab top", 2, flux=[(t, p / area) for t, p in sched])
        points, npoints, bodies = f"0.0 0.0 {LAYERS['copper'][1] * MM!r}", 1, (1,)
    else:
        left = case["left_source_fraction"]
        area = (2 * PATCH_HALF * MM) ** 2
        bcs += _bc(2, "left patch", 2, flux=[(t, left * p / area) for t, p in sched])
        bcs += _bc(
            3, "right patch", 3, flux=[(t, (1 - left) * p / area) for t, p in sched]
        )
        bcs += _bc(4, "die top", 4)
        z = 2.7 * MM
        points = f"{-PATCH_X * MM!r} 0.0 {z!r} {PATCH_X * MM!r} 0.0 {z!r}"
        npoints, bodies = 2, (1, 2, 3)
    bodies_text = "".join(
        f"Body {b}\n  Equation = 1\n  Material = {b}\n  Initial Condition = 1\nEnd\n"
        for b in bodies
    )
    mats = "".join(
        f'Material {i}\n  Name = "{n}"\n  Heat Conductivity = {LAYERS[n][2]!r}\n'
        f"  Density = {LAYERS[n][3]!r}\n  Heat Capacity = {LAYERS[n][4]!r}\nEnd\n"
        for i, n in enumerate(NAMES, start=1)
    )
    timing = (
        ""
        if steady
        else "  Timestepping Method = BDF\n  BDF Order = 2\n"
        f"  Timestep Sizes({len(sizes)}) = {' '.join(repr(s) for s in sizes)}\n"
        f"  Timestep Intervals({len(intervals)}) = {' '.join(str(n) for n in intervals)}\n"
    )
    linear = "Direct" if direct else "Iterative"
    return f"""! f02 deck: REFERENCE-PACKAGES-01, generated by f02_deck.py
Header
  Mesh DB "." "mesh"
End
Simulation
  Max Output Level = 3
  Coordinate System = Cartesian 3D
  Simulation Type = {"Steady State" if steady else "Transient"}
{timing}  Steady State Max Iterations = 1
End
{bodies_text}Initial Condition 1
  Temperature = {case['initial_c'] + 273.15!r}
End
{mats}Equation 1
  Active Solvers(1) = 1
End
Solver 1
  Equation = Heat Equation
  Variable = Temperature
  Procedure = "HeatSolve" "HeatSolver"
  Linear System Solver = {linear}
  Linear System Direct Method = Umfpack
  Linear System Iterative Method = CG
  Linear System Preconditioning = ILU0
  Linear System Convergence Tolerance = 1e-12
  Linear System Max Iterations = 5000
  Linear System Abort Not Converged = True
  Steady State Convergence Tolerance = 1e-9
  Nonlinear System Max Iterations = 1
End
Solver 2
  Exec Solver = After Timestep
  Equation = SaveScalars
  Procedure = "SaveData" "SaveScalars"
  Filename = scalars.dat
  Variable 1 = Time
  Variable 2 = Temperature
  Operator 2 = boundary max
  Variable 3 = Temperature
  Operator 3 = boundary int
  Save Coordinates({npoints},3) = {points}
End
Solver 3
  Exec Solver = After Simulation
  Equation = ResultOutput
  Procedure = "ResultOutputSolve" "ResultOutputSolver"
  Output File Name = final
  Vtu Format = Logical True
  Ascii Output = Logical True
  Single Precision = Logical False
End
{bcs}"""


def write_case(
    case,
    out,
    level=1,
    dt_scale=1.0,
    steady=False,
    source=True,
    direct=False,
    slab=False,
):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    info = write_mesh(out, level, slab)
    sizes, intervals = time_steps(case, dt_scale)
    (out / "case.sif").write_text(
        sif(
            case,
            sizes,
            intervals,
            steady=steady,
            source=source,
            direct=direct,
            slab=slab,
        )
    )
    (out / "ELMERSOLVER_STARTINFO").write_text("case.sif\n1\n")
    meta = {"case": case, "mesh": info, "steps": 1 if steady else sum(intervals),
            "dt_scale": dt_scale, "schedule_w": schedule(case), "steady": steady,
            "source": source, "slab": slab,
            "linear_solver": "umfpack" if direct else "cg-ilu0-1e-12"}  # fmt: skip
    (out / "deck.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


# --- observers ---------------------------------------------------------------------


def read_scalars(case_dir):
    text = Path(case_dir, "scalars.dat").read_text()
    rows = [list(map(float, x.split())) for x in text.splitlines() if x.strip()]
    names = Path(case_dir, "scalars.dat.names").read_text().splitlines()
    cols = [n.split(":", 1)[1].strip() for n in names if re.match(r"^\s*\d+:", n)]
    return cols, rows


def observe(case_dir, baseline_top_c=None):
    """Peak die-top temperature over every solver step and its time, the
    first 95 C crossing (interpolated) or NOT_REACHED, extra energy above
    20 W, recovery to within 1 C of a 20 W steady baseline (when supplied),
    and the 0.5 s samples of the die-top maximum and patch centres."""
    cols, rows = read_scalars(case_dir)
    i_top = next(i for i, c in enumerate(cols) if c.startswith("boundary max"))
    i_pts = [
        i for i, c in enumerate(cols) if c.startswith("value: temperature at node")
    ]
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    t = [r[0] for r in rows]
    top = [r[i_top] - 273.15 for r in rows]
    i_peak = max(range(len(top)), key=top.__getitem__)
    crossing = "NOT_REACHED"
    prev_t, prev_v = 0.0, meta["case"]["initial_c"]
    for ti, vi in zip(t, top):
        if vi >= LIMIT_C > prev_v:
            crossing = prev_t + (LIMIT_C - prev_v) / (vi - prev_v) * (ti - prev_t)
            break
        prev_t, prev_v = ti, vi
    sched = meta["schedule_w"]
    energy = sum(
        (b - a) * ((pa + pb) / 2 - BASE_W)
        for (a, pa), (b, pb) in itertools.pairwise(sched)
    )
    recovery = None
    if baseline_top_c is not None:
        last_event = max(x for x, _ in sched if x < HORIZON_S)
        recovery = next(
            (
                ti
                for ti, vi in zip(t, top)
                if ti > last_event and abs(vi - baseline_top_c) <= 1.0
            ),
            "NOT_RECOVERED",
        )
    samples = [i for i, ti in enumerate(t) if abs(ti * 2 - round(ti * 2)) < 1e-6]
    return {
        "peak_top_c": top[i_peak],
        "peak_time_s": t[i_peak],
        "first_95c_crossing_s": crossing,
        "extra_energy_j": energy,
        "recovery_s": recovery,
        "steps": len(t),
        "top_max_c_at_0p5s": [[t[i], top[i]] for i in samples],
        "patch_centres_c_at_0p5s": [
            [t[i], *(rows[i][j] - 273.15 for j in i_pts)] for i in samples
        ],
    }


def _vtu_arrays(case_dir):
    vtu = next(Path(case_dir).rglob("final*.vtu")).read_text()

    def block(pattern):
        return re.search(pattern, vtu, re.DOTALL).group(1).split()

    pts = block(r"<Points>\s*<DataArray[^>]*>(.*?)</DataArray>")
    xyz = [tuple(map(float, pts[i : i + 3])) for i in range(0, len(pts), 3)]
    temp = [float(x) for x in block(r'Name="[Tt]emperature"[^>]*>(.*?)</DataArray>')]
    flat = [int(x) for x in block(r'Name="connectivity"[^>]*>(.*?)</DataArray>')]
    offsets = [int(x) for x in block(r'Name="offsets"[^>]*>(.*?)</DataArray>')]
    types = [int(x) for x in block(r'Name="types"[^>]*>(.*?)</DataArray>')]
    # Keep the hexahedra (VTK type 12); Elmer also writes boundary quads.
    conn, start = [], 0
    for end, kind in zip(offsets, types):
        if kind == 12:
            conn += flat[start:end]
        start = end
    # The layers are flat slabs, so an element's material follows from its
    # centroid height (the VTU carries no body ids).
    z_cu = LAYERS["copper"][1] * MM
    z_tim = z_cu + LAYERS["tim"][1] * MM
    body = []
    for e in range(len(conn) // 8):
        zc = sum(xyz[i][2] for i in conn[8 * e : 8 * e + 8]) / 8
        body.append(1 if zc < z_cu else (2 if zc < z_tim else 3))
    return xyz, temp, conn, body


def stored_energy_j(case_dir):
    """Sum over hexes of rho cp (mean nodal T - T0) x volume, from the final
    ASCII VTU (axis-aligned boxes: exact for trilinear elements)."""
    xyz, temp, conn, body = _vtu_arrays(case_dir)
    t0 = (
        json.loads(Path(case_dir, "deck.json").read_text())["case"]["initial_c"]
        + 273.15
    )
    total = 0.0
    for e, b in enumerate(body):
        ids = conn[8 * e : 8 * e + 8]
        span = [
            max(xyz[i][a] for i in ids) - min(xyz[i][a] for i in ids) for a in range(3)
        ]
        _h, _t, _k, rho, cp = LAYERS[NAMES[b - 1]]
        total += (
            rho
            * cp
            * span[0]
            * span[1]
            * span[2]
            * (sum(temp[i] for i in ids) / 8 - t0)
        )
    return total


def energy_balance(case_dir):
    """(heat in - stored - Robin out) / heat in over the whole run; the
    Robin loss uses each step's end value, as the BDF load does."""
    cols, rows = read_scalars(case_dir)
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    h, tc = meta["case"]["h_w_m2_k"], meta["case"]["coolant_c"] + 273.15
    i_bottom = next(
        i
        for i, c in enumerate(cols)
        if c.startswith("boundary int") and c.endswith("bc 1")
    )
    area = (2 * LAYERS["copper"][0] * MM) ** 2
    out, prev = 0.0, 0.0
    for r in rows:
        out += (r[0] - prev) * h * (r[i_bottom] - tc * area)
        prev = r[0]
    sched = meta["schedule_w"] if meta["source"] else [(0, 0.0), (HORIZON_S, 0.0)]
    heat_in = sum(
        (b - a) * (pa + pb) / 2 for (a, pa), (b, pb) in itertools.pairwise(sched)
    )
    stored = stored_energy_j(case_dir)
    return {
        "heat_in_j": heat_in,
        "stored_j": stored,
        "robin_out_j": out,
        "residual_rel": (heat_in - stored - out) / heat_in if heat_in else None,
    }


# --- analytic slab control -----------------------------------------------------------


def slab_top_rise(q, h, t, *, k=390.0, rho=8960.0, cp=385.0, length=2e-3, terms=80):
    """Top-surface rise of a slab, initially at the coolant temperature, with
    uniform flux q stepped on at t = 0 on top and Robin h below: the exact
    eigenfunction series (lam tan(lam L) = h/k, X = cos(lam u), u from the
    top)."""
    if t <= 0:
        return 0.0
    alpha, ratio = k / (rho * cp), h / k

    def root(n):
        lo, hi = n * math.pi / length + 1e-12, (n + 0.5) * math.pi / length - 1e-12
        for _ in range(200):
            mid = (lo + hi) / 2
            if mid * math.tan(mid * length) > ratio:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    total = q / h + q * length / k
    for n in range(terms):
        lam = root(n)
        s, c = math.sin(lam * length), math.cos(lam * length)
        # integral of theta_s(u) cos(lam u) over [0, L], theta_s = q/h + q (L - u)/k
        integral = (q / h + q * length / k) * s / lam - (q / k) * (
            (c - 1) / lam**2 + length * s / lam
        )
        norm = length / 2 + math.sin(2 * lam * length) / (4 * lam)
        total += -(integral / norm) * math.exp(-(lam**2) * alpha * t)
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f02_deck")
    parser.add_argument("command", choices=("case",))
    parser.add_argument("label")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mesh", type=int, default=1)
    parser.add_argument("--dt-scale", type=float, default=1.0)
    parser.add_argument("--steady", action="store_true")
    parser.add_argument("--direct", action="store_true")
    args = parser.parse_args(argv)
    case = panel_case(args.label)
    meta = write_case(
        case, args.out, args.mesh, args.dt_scale, args.steady, direct=args.direct
    )
    print(json.dumps(meta["mesh"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
