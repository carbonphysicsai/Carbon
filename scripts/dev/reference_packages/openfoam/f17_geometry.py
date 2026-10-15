"""f17 staggered-herringbone groove geometry: frozen convention, checks, STL.

Coordinates in micrometres: x axial [0, 10000], y across [0, 300], z up
[0, 100]; grooves are recessed into the floor, z in [-depth, 0]. The frozen
convention (`.agent/decisions/2026-10-15-F17-SCIENCE-VALUES-01.md`, G1-G6):

G1 A groove is a chevron: two arms of width 50 um measured normal to the arm,
   centrelines at +-45 deg to the axis meeting at an apex at y = 100 (first
   half-cycle) or y = 200 (mirrored half-cycle, y -> 300 - y). The apex points
   upstream; both arms run downstream to the clearance lines y = 10 and
   y = 290 (10 um before each sidewall), where they are cut parallel to the
   wall.
G2 The first groove's upstream tip is at x = 250 um. Apex spacing is the
   pitch p within a half-cycle; across a reversal it is p + 100 um (the apex
   jump), which keeps the arm family that continues through the reversal at
   its in-cycle normal spacing p/sqrt(2). Grooves are added while the
   footprint ends at or before x = 9750 um (250-um smooth inlet and outlet
   leads).
G3 Half-cycle of groove i is (i // reversal) % 2.
G4 Grooves never overlap: every pair keeps a web >= 20 um (the in-cycle web
   at the minimum pitch is 100/sqrt(2) - 50 = 20.7 um).
G5 Fluid volume = 300 x 100 x 10000 um^3 + depth x sum(groove areas).
G6 Inlet split at y = 150: inlet0 (y < 150) carries c = 0, inlet1 c = 1.

The STL is the watertight floor sheet (floor at z = 0 outside the grooves,
groove walls, groove bottoms at z = -depth), triangulated conformingly by a
slab decomposition, so snappyHexMesh separates the recesses from the solid.
"""

from __future__ import annotations

import hashlib
import math
from itertools import pairwise

L_UM, W_UM, H_UM = 10000.0, 300.0, 100.0
GROOVE_WIDTH_UM, CLEARANCE_UM, LEAD_UM = 50.0, 10.0, 250.0
APEX_Y_UM = (100.0, 200.0)
MIN_WEB_UM = 20.0
HALF = GROOVE_WIDTH_UM / 2 * math.sqrt(2)  # x offset of tip/notch from apex
REACH = W_UM - CLEARANCE_UM - APEX_Y_UM[0]  # long arm axial reach, 190 um
MARGIN_UM = 50.0  # floor sheet extends past the channel so snapping is clean
ROUND = 6


def _r(v):
    return round(v + 0.0, ROUND) + 0.0


def chevron(apex_x, apex_y):
    """Counter-clockwise hexagon of one groove footprint (G1)."""
    lo, hi, a = CLEARANCE_UM, W_UM - CLEARANCE_UM, HALF
    pts = [
        (apex_x - a, apex_y),  # upstream tip
        (apex_x + apex_y - lo - a, lo),  # low arm, upstream side at y=10
        (apex_x + apex_y - lo + a, lo),  # low arm, downstream side
        (apex_x + a, apex_y),  # notch
        (apex_x + hi - apex_y + a, hi),  # high arm, downstream side at y=290
        (apex_x + hi - apex_y - a, hi),  # high arm, upstream side
    ]
    return [(_r(x), _r(y)) for x, y in pts]


def grooves(depth_um, pitch_um, reversal):
    """Frozen groove list (G1-G3)."""
    out, x = [], LEAD_UM + HALF
    i = 0
    while True:
        half = (i // reversal) % 2
        if i:
            x += pitch_um + (100.0 if i % reversal == 0 else 0.0)
        if x - HALF + 2 * HALF + REACH > L_UM - LEAD_UM + 1e-9:
            break
        out.append(
            {
                "index": i,
                "half_cycle": half,
                "apex_x_um": _r(x),
                "apex_y_um": APEX_Y_UM[half],
                "polygon": chevron(x, APEX_Y_UM[half]),
            }
        )
        i += 1
    return out


def area(poly):
    return 0.5 * sum(
        x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1])
    )


def _seg_dist(p, q, a, b):
    def point_seg(pt, s0, s1):
        dx, dy = s1[0] - s0[0], s1[1] - s0[1]
        t = ((pt[0] - s0[0]) * dx + (pt[1] - s0[1]) * dy) / (dx * dx + dy * dy)
        t = min(1.0, max(0.0, t))
        return math.hypot(pt[0] - s0[0] - t * dx, pt[1] - s0[1] - t * dy)

    def cross(o, u, v):
        return (u[0] - o[0]) * (v[1] - o[1]) - (u[1] - o[1]) * (v[0] - o[0])

    d1, d2 = cross(a, b, p), cross(a, b, q)
    d3, d4 = cross(p, q, a), cross(p, q, b)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return 0.0
    return min(point_seg(p, a, b), point_seg(q, a, b), point_seg(a, p, q),
               point_seg(b, p, q))  # fmt: skip


def _inside(pt, poly):
    x, y, inside = pt[0], pt[1], False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def check(design):
    """G4/G5 checks; raises on any defect, returns the measured margins."""
    gs = grooves(**design)
    if not gs:
        raise ValueError("no groove fits the channel")
    min_web = math.inf
    for i, g in enumerate(gs):
        poly = g["polygon"]
        if area(poly) <= 0:
            raise ValueError("groove polygon is not counter-clockwise")
        ys = [y for _, y in poly]
        if min(ys) < CLEARANCE_UM - 1e-9 or max(ys) > W_UM - CLEARANCE_UM + 1e-9:
            raise ValueError("groove violates the sidewall clearance")
        for h in gs[i + 1 :]:
            other = h["polygon"]
            if min(x for x, _ in other) > max(x for x, _ in poly) + MIN_WEB_UM:
                break
            if any(_inside(p, other) for p in poly) or any(
                _inside(p, poly) for p in other
            ):
                raise ValueError("grooves overlap")
            web = min(
                _seg_dist(p, q, a, b)
                for p, q in zip(poly, poly[1:] + poly[:1])
                for a, b in zip(other, other[1:] + other[:1])
            )
            min_web = min(min_web, web)
    if min_web < MIN_WEB_UM:
        raise ValueError(f"groove web {min_web:.2f} um below {MIN_WEB_UM} um")
    last = max(x for x, _ in gs[-1]["polygon"])
    groove_area = sum(area(g["polygon"]) for g in gs)
    return {
        "grooves": len(gs),
        "half_cycles": sorted({g["half_cycle"] for g in gs}),
        "min_web_um": round(min_web, 4),
        "first_tip_x_um": gs[0]["polygon"][0][0],
        "last_footprint_end_x_um": last,
        "groove_area_um2": round(groove_area, 4),
        "fluid_volume_um3": round(
            L_UM * W_UM * H_UM + design["depth_um"] * groove_area, 3
        ),
    }


def _y_at(edge, x):
    (x0, y0), (x1, y1) = edge
    if x == x0:
        return y0
    if x == x1:
        return y1
    return _r(y0 + (y1 - y0) * (x - x0) / (x1 - x0))


def surface(design):
    """Triangles (z-up, normals into the fluid) of the watertight floor sheet."""
    depth = float(design["depth_um"])
    polys = [g["polygon"] for g in grooves(**design)]
    edges = []  # (p0, p1, is_bottom) with x0 < x1
    for poly in polys:
        for p, q in zip(poly, poly[1:] + poly[:1]):
            if p[0] == q[0]:
                raise ValueError("vertical groove edge is outside the convention")
            # counter-clockwise: an edge running +x has the groove above it
            edges.append((p, q, True) if p[0] < q[0] else (q, p, False))
    x_lo, x_hi = -MARGIN_UM, L_UM + MARGIN_UM
    y_lo, y_hi = -MARGIN_UM, W_UM + MARGIN_UM
    xs = sorted({x_lo, x_hi} | {p[0] for poly in polys for p in poly})
    line_pts = {x: set() for x in xs}
    for p0, p1, _ in edges:
        for x in xs:
            if p0[0] <= x <= p1[0]:
                line_pts[x].add(_y_at((p0, p1), x))
    for x in xs:
        line_pts[x] |= {y_lo, y_hi}
    tris = []

    def fan(ring, z):
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        c = (_r(cx), _r(cy), z)
        for a, b in zip(ring, ring[1:] + ring[:1]):
            tris.append((c, (a[0], a[1], z), (b[0], b[1], z)))

    for xl, xr in pairwise(xs):
        xm = 0.5 * (xl + xr)
        active = [
            (_y_at((p0, p1), xm), (p0, p1), bottom)
            for p0, p1, bottom in edges
            if p0[0] <= xl and p1[0] >= xr
        ]
        bounds = [(y_lo, None, False)] + sorted(active) + [(y_hi, None, None)]
        for (yb, eb, bottom), (yt, et, _) in pairwise(bounds):

            def ys(edge, x, flat):
                return flat if edge is None else _y_at(edge, x)

            bl, br = ys(eb, xl, y_lo), ys(eb, xr, y_lo)
            tl, tr = ys(et, xl, y_hi), ys(et, xr, y_hi)
            right = sorted(y for y in line_pts[xr] if br < y < tr)
            left = sorted((y for y in line_pts[xl] if bl < y < tl), reverse=True)
            ring = [(xl, bl), (xr, br)] + [(xr, y) for y in right]
            ring += [(xr, tr)] if tr != br else []
            ring += [(xl, tl)] if tl != bl else []
            ring += [(xl, y) for y in left]
            if len(ring) >= 3:
                fan(ring, -depth if bottom else 0.0)
    for p0, p1, bottom in edges:
        pts = sorted(
            {p0, p1} | {(x, _y_at((p0, p1), x)) for x in xs if p0[0] < x < p1[0]}
        )
        for a, b in pairwise(pts):
            # walk the wall in the polygon's own (counter-clockwise) direction
            a, b = (a, b) if bottom else (b, a)
            a0, b0, a1, b1 = (*a, -depth), (*b, -depth), (*a, 0.0), (*b, 0.0)
            tris.append((a0, b1, b0))
            tris.append((a0, a1, b1))
    return tris


def stl(design, name="bottom"):
    lines = [f"solid {name}"]
    for tri in surface(design):
        lines.append(" facet normal 0 0 0\n  outer loop")
        lines.extend(f"   vertex {x:.6f} {y:.6f} {z:.6f}" for x, y, z in tri)
        lines.append("  endloop\n endfacet")
    lines.append(f"endsolid {name}\n")
    return "\n".join(lines)


def feature_edges(design):
    """featureEdgeMesh text: groove outlines at both levels plus vertical corners."""
    depth = float(design["depth_um"])
    points, edges = [], []
    for g in grooves(**design):
        poly, base = g["polygon"], len(points)
        n = len(poly)
        points += [(x, y, 0.0) for x, y in poly] + [(x, y, -depth) for x, y in poly]
        for k in range(n):
            edges += [(base + k, base + (k + 1) % n)]
            edges += [(base + n + k, base + n + (k + 1) % n)]
            edges += [(base + k, base + n + k)]
    head = (
        "FoamFile { version 2.0; format ascii; class featureEdgeMesh; "
        "object bottom.eMesh; }\n"
    )
    body = f"{len(points)}\n(\n"
    body += "".join(f"({x:.6f} {y:.6f} {z:.6f})\n" for x, y, z in points)
    body += f")\n{len(edges)}\n(\n" + "".join(f"({a} {b})\n" for a, b in edges)
    return head + body + ")\n"


def surface_check(design):
    """Closed-sheet check: every interior STL edge is shared by exactly two
    triangles; only the outer rim (the floor sheet's margin border) is open."""
    count = {}
    tris = surface(design)
    area_floor = area_bottom = 0.0
    for tri in tris:
        for a, b in zip(tri, tri[1:] + tri[:1]):
            key = (min(a, b), max(a, b))
            count[key] = count.get(key, 0) + 1
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = tri
        nz = 0.5 * ((x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0))
        if z0 == z1 == z2 == 0.0:
            area_floor += nz
        elif z0 == z1 == z2:
            area_bottom += nz
    open_edges = [k for k, v in count.items() if v == 1]
    rim = all(
        (a[2] == b[2] == 0.0)
        and (
            {a[0], b[0]} <= {-MARGIN_UM, L_UM + MARGIN_UM}
            and a[0] == b[0]
            or {a[1], b[1]} <= {-MARGIN_UM, W_UM + MARGIN_UM}
            and a[1] == b[1]
        )
        for a, b in open_edges
    )
    if any(v > 2 for v in count.values()) or not rim:
        raise ValueError("floor sheet is not a conforming closed sheet")
    sheet = (L_UM + 2 * MARGIN_UM) * (W_UM + 2 * MARGIN_UM)
    groove_area = sum(area(g["polygon"]) for g in grooves(**design))
    if (
        abs(area_floor + area_bottom - sheet) > 1e-3
        or abs(area_bottom - groove_area) > 1e-3
    ):
        raise ValueError("floor/bottom areas do not tile the sheet")
    return {
        "triangles": len(tris),
        "open_rim_edges": len(open_edges),
        "floor_area_um2": round(area_floor, 3),
        "groove_bottom_area_um2": round(area_bottom, 3),
    }


def digest(text):
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()
