"""Mesh one surface-mounted PM machine cross-section, exactly rotated.

DEVELOPMENT variant for CHALLENGE-CUSTOMER-FEASIBILITY-02 (#758 at
1ac5acfa): a copy of `carbon/motor/mesh.py` whose only change is an optional
double-layer slot (`layers: 2`), split on the slot's centre line into two
coil sides (tags 201 + 2k for the lower-angle side of slot k, 202 + 2k for
the higher). With `layers` absent or 1 it meshes exactly as the original.

Runs inside the motor reference image (`python3` with Gmsh's API on the
path); it imports nothing from Carbon so its exact bytes can be staged there.

    python3 mesh.py PARAMS.json OUTDIR

**Exact rotation, no remeshing noise.** The rotor (shaft, yoke, magnets and
the inner half of the airgap) and the stator (the outer half of the airgap,
slot openings, coils and iron) are meshed once each, separately. Both halves
meet on a circle at mid-airgap carrying `n_gap` uniformly spaced nodes. For a
rotor angle of k steps of 2 pi / n_gap, the rotor's nodes are rotated and its
circle nodes are identified with the stator's, shifted by k. Every rotor angle
therefore has the same two meshes, rigidly moved: torque ripple cannot be
remeshing noise. Rotor angles must be whole steps; `steps` lists them.

Output: `rotor_<k>.msh` (Gmsh 2.2 ASCII, in metres) for each k in `steps`,
and `mesh.json` with the region tags, areas (mm^2) and counts GetDP's input
needs. Parameters are in millimetres.

Regions (physical tags):
  1 shaft (non-magnetic)  2 rotor iron  3 rotor airgap half (an annulus)
  4 air between the magnets
  101.. magnets, one per pole, counter-clockwise from the first pole
  11 stator iron  13 stator airgap half  14 slot openings (air)
  201.. coils, one per slot, counter-clockwise from the first slot
  1000 the stator's outer circle (line; a = 0)
"""

import json
import math
import sys

import gmsh

SHAFT, ROTOR_FE, ROTOR_GAP, ROTOR_AIR = 1, 2, 3, 4
STATOR_FE, STATOR_GAP, SLOT_AIR = 11, 13, 14
MAGNET0, COIL0, OUTER = 101, 201, 1000


def _polygon(occ, points):
    tags = [occ.addPoint(x, y, 0) for x, y in points]
    lines = [occ.addLine(tags[i], tags[(i + 1) % len(tags)]) for i in range(len(tags))]
    return occ.addPlaneSurface([occ.addCurveLoop(lines)])


def _arc_ring(occ, r_in, r_out, a0, a1):
    """The annular sector between radii and angles, as one surface."""
    c = occ.addPoint(0, 0, 0)
    p = [
        occ.addPoint(r_in * math.cos(a0), r_in * math.sin(a0), 0),
        occ.addPoint(r_out * math.cos(a0), r_out * math.sin(a0), 0),
        occ.addPoint(r_out * math.cos(a1), r_out * math.sin(a1), 0),
        occ.addPoint(r_in * math.cos(a1), r_in * math.sin(a1), 0),
    ]
    curves = [
        occ.addLine(p[0], p[1]),
        occ.addCircleArc(p[1], c, p[2]),
        occ.addLine(p[2], p[3]),
        occ.addCircleArc(p[3], c, p[0]),
    ]
    return occ.addPlaneSurface([occ.addCurveLoop(curves)])


def _uniform_circle(occ, radius, n_gap):
    """A full circle starting at angle 0, to carry n_gap uniform nodes."""
    return occ.addCircle(0, 0, 0, radius)


def _fragment(inputs):
    """Fragment labelled shapes; each output surface gets the label of the
    most specific input containing it (the first in `inputs` order whose
    shape it came from). `inputs` is [(label, (dim, tag))], most specific
    first. Labels never depend on Gmsh's entity numbering or on a surface's
    centre of mass, which for a ring is the origin."""
    occ = gmsh.model.occ
    shapes = [shape for _, shape in inputs]
    _, mapping = occ.fragment(shapes[-1:], shapes[:-1])
    occ.synchronize()
    # fragment's map lists objects first, then tools: re-align to `inputs`.
    ordered = [*mapping[1:], mapping[0]]
    groups = {}
    labelled = set()
    for (label, shape), pieces in zip(inputs, ordered):
        if shape[0] != 2:
            continue
        for dim, tag in pieces:
            if dim == 2 and tag not in labelled:
                labelled.add(tag)
                groups.setdefault(label, []).append(tag)
    missing = {t for _, t in gmsh.model.getEntities(2)} - labelled
    if missing:
        raise RuntimeError(f"surfaces without a region: {sorted(missing)}")
    return groups


def _mesh_rotor(p):
    gmsh.model.add("rotor")
    occ = gmsh.model.occ
    poles = p["poles"]
    pitch = 2 * math.pi / poles
    r_mid = p["r_ro"] + p["gap"] / 2
    r_m = p["r_ro"] - p["h_m"]
    half = p["embrace"] * pitch / 2
    inputs = [(SHAFT, (2, occ.addDisk(0, 0, 0, p["r_shaft"], p["r_shaft"])))]
    inputs.append((ROTOR_FE, (2, occ.addDisk(0, 0, 0, r_m, r_m))))
    for k in range(poles):
        centre = (k + 0.5) * pitch
        magnet = _arc_ring(occ, r_m, p["r_ro"], centre - half, centre + half)
        inputs.append((MAGNET0 + k, (2, magnet)))
    # Air between the magnets, below the rotor surface: kept apart from the
    # airgap, so the airgap is an exact annulus (Arkkio's torque needs one).
    inputs.append((ROTOR_AIR, (2, occ.addDisk(0, 0, 0, p["r_ro"], p["r_ro"]))))
    inputs.append((None, (1, _uniform_circle(occ, r_mid, p["n_gap"]))))
    inputs.append((ROTOR_GAP, (2, occ.addDisk(0, 0, 0, r_mid, r_mid))))
    occ.synchronize()
    groups = _fragment(inputs)
    return _finish(groups, r_mid, p, outer_line=False)


def _slot_polygons(p, k):
    """The slot opening (air) and the coil (slot body) of slot k as point
    lists. Teeth have parallel sides of width tooth_w; the opening is a
    radial-sided gap of slot_open_deg through the tooth tips."""
    slots = p["slots"]
    pitch = 2 * math.pi / slots
    centre = (k + 0.5) * pitch
    half_open = math.radians(p["slot_open_deg"]) / 2
    r_si = p["r_si"]
    r_tip = r_si + p["tip_h"]
    r_body = r_tip + p["wedge_h"]
    r_bottom = p["r_sb"]
    w = p["tooth_w"] / 2

    def tooth_edge_point(r, side):
        # The tooth beside this slot on `side` (+1 counter-clockwise) has its
        # centreline at centre + side*pitch/2. Its edge facing the slot lies
        # at perpendicular distance w from that centreline.
        a = centre + side * pitch / 2
        s = math.asin(min(1.0, w / r))
        b = a - side * s
        return r * math.cos(b), r * math.sin(b)

    def at(r, angle):
        return r * math.cos(angle), r * math.sin(angle)

    opening = [
        at(r_si, centre - half_open),
        at(r_tip, centre - half_open),
        at(r_tip, centre + half_open),
        at(r_si, centre + half_open),
    ]
    wedge = [
        at(r_tip, centre - half_open),
        tooth_edge_point(r_body, -1),
        tooth_edge_point(r_body, +1),
        at(r_tip, centre + half_open),
    ]
    coil = [
        tooth_edge_point(r_body, -1),
        tooth_edge_point(r_bottom, -1),
        tooth_edge_point(r_bottom, +1),
        tooth_edge_point(r_body, +1),
    ]
    if p.get("layers", 1) == 2:
        # Split on the centre line: the chord midpoints lie on it by symmetry.
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = coil
        bottom = ((x1 + x2) / 2, (y1 + y2) / 2)
        body = ((x0 + x3) / 2, (y0 + y3) / 2)
        return (
            opening,
            wedge,
            [[coil[0], coil[1], bottom, body], [body, bottom, coil[2], coil[3]]],
        )
    return opening, wedge, [coil]


def _mesh_stator(p):
    gmsh.model.add("stator")
    occ = gmsh.model.occ
    r_mid = p["r_ro"] + p["gap"] / 2
    inputs = []
    for k in range(p["slots"]):
        _opening, wedge, sides = _slot_polygons(p, k)
        for i, coil in enumerate(sides):
            inputs.append((COIL0 + len(sides) * k + i, (2, _polygon(occ, coil))))
        # The opening is bounded by true arcs, so it takes nothing from the
        # airgap annulus below the bore.
        centre = (k + 0.5) * 2 * math.pi / p["slots"]
        half_open = math.radians(p["slot_open_deg"]) / 2
        r_tip = p["r_si"] + p["tip_h"]
        arc = _arc_ring(occ, p["r_si"], r_tip, centre - half_open, centre + half_open)
        inputs.append((SLOT_AIR, (2, arc)))
        inputs.append((SLOT_AIR, (2, _polygon(occ, wedge))))
    inputs.append((None, (1, _uniform_circle(occ, r_mid, p["n_gap"]))))
    inputs.append((STATOR_GAP, (2, occ.addDisk(0, 0, 0, p["r_si"], p["r_si"]))))
    # The stator iron: everything out to the outer radius not claimed above.
    inputs.append((STATOR_FE, (2, occ.addDisk(0, 0, 0, p["r_so"], p["r_so"]))))
    occ.synchronize()
    groups = _fragment(inputs)
    # The disk below mid-airgap belongs to the rotor's half: remove it.
    # OCC pads bounding boxes, so compare against the midpoint between the
    # mid-airgap circle and the bore, never against r_mid itself.
    r_cut = (r_mid + p["r_si"]) / 2
    inner = [
        tag
        for tag in groups.get(STATOR_GAP, [])
        if gmsh.model.getBoundingBox(2, tag)[3] < r_cut
    ]
    if len(inner) != 1:
        raise RuntimeError(f"expected one inner disk below mid-airgap, got {inner}")
    groups[STATOR_GAP].remove(inner[0])
    gmsh.model.occ.remove([(2, inner[0])])
    gmsh.model.occ.synchronize()
    return _finish(groups, r_mid, p, outer_line=True)


def _finish(groups, r_mid, p, outer_line):
    for tag, members in groups.items():
        gmsh.model.addPhysicalGroup(2, members, tag)
    # A full circle is one closed curve; its points all lie at one radius.
    # OCC pads bounding boxes, so radii are compared on the curve itself.
    circle = None
    outer = []
    for dim, tag in gmsh.model.getEntities(1):
        # Gmsh 4.15's OCC kernel reports a full circle as "Ellipse"; the
        # constant-radius test below is what establishes a circle.
        if gmsh.model.getType(dim, tag) not in ("Circle", "Ellipse"):
            continue
        lo, hi = gmsh.model.getParametrizationBounds(dim, tag)
        span = hi[0] - lo[0]
        samples = [lo[0] + span * i / 8 for i in range(9)]
        xyz = gmsh.model.getValue(dim, tag, samples)
        radii = [math.hypot(xyz[3 * i], xyz[3 * i + 1]) for i in range(9)]
        full = abs(span - 2 * math.pi) < 1e-9
        if full and max(abs(r - r_mid) for r in radii) < 1e-9 * r_mid:
            circle = tag
        if outer_line and max(abs(r - p["r_so"]) for r in radii) < 1e-9 * p["r_so"]:
            outer.append(tag)
    if circle is None:
        raise RuntimeError("the mid-airgap circle was not found")
    gmsh.model.mesh.setTransfiniteCurve(circle, p["n_gap"] + 1)
    if outer:
        gmsh.model.addPhysicalGroup(1, outer, OUTER)
    h_gap = 2 * math.pi * r_mid / p["n_gap"]
    gmsh.option.setNumber("Mesh.MeshSizeMin", h_gap)
    gmsh.option.setNumber("Mesh.MeshSizeMax", p["h_max"])
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 24)
    gmsh.option.setNumber("Mesh.Algorithm", 6)
    gmsh.option.setNumber("General.NumThreads", 1)
    gmsh.option.setNumber("Mesh.RandomSeed", 1)
    field = gmsh.model.mesh.field
    dist = field.add("Distance")
    field.setNumbers(dist, "CurvesList", [circle])
    # The default samples a curve at 20 points, which leaves the airgap
    # coarse between them; sample it as finely as its own nodes.
    field.setNumber(dist, "Sampling", 4 * p["n_gap"])
    thr = field.add("Threshold")
    field.setNumber(thr, "InField", dist)
    field.setNumber(thr, "SizeMin", h_gap)
    field.setNumber(thr, "SizeMax", p["h_max"])
    field.setNumber(thr, "DistMin", p["gap"])
    field.setNumber(thr, "DistMax", p["gap"] * 12)
    field.setAsBackgroundMesh(thr)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.model.mesh.generate(2)
    return _extract(circle, groups, outer)


def _extract(circle, groups, outer):
    """Nodes, triangles by region, the outer line, and the circle's nodes."""
    tags, coords, _ = gmsh.model.mesh.getNodes()
    nodes = {int(t): (coords[3 * i], coords[3 * i + 1]) for i, t in enumerate(tags)}
    triangles = []
    for region, members in groups.items():
        for entity in members:
            types, _, node_tags = gmsh.model.mesh.getElements(2, entity)
            for etype, conn in zip(types, node_tags):
                if etype != 2:
                    raise RuntimeError(f"unexpected element type {etype}")
                for i in range(0, len(conn), 3):
                    triangles.append(
                        (region, entity, tuple(int(n) for n in conn[i : i + 3]))
                    )
    lines = []
    for entity in outer:
        types, _, node_tags = gmsh.model.mesh.getElements(1, entity)
        for etype, conn in zip(types, node_tags):
            for i in range(0, len(conn), 2):
                lines.append((OUTER, entity, (int(conn[i]), int(conn[i + 1]))))
    ctags, _, _ = gmsh.model.mesh.getNodes(1, circle, includeBoundary=True)
    # A closed curve lists its one end node twice (as start and end).
    circle = list(dict.fromkeys(int(t) for t in ctags))
    return {"nodes": nodes, "triangles": triangles, "lines": lines, "circle": circle}


def _circle_index(xy, n_gap):
    angle = math.atan2(xy[1], xy[0]) % (2 * math.pi)
    k = round(angle / (2 * math.pi / n_gap)) % n_gap
    error = abs(angle - k * 2 * math.pi / n_gap)
    return k, min(error, 2 * math.pi - error)


def _write(path, stator, rotor, k, n_gap):
    """One merged mesh with the rotor turned k steps, in Gmsh 2.2 ASCII."""
    theta = 2 * math.pi * k / n_gap
    c, s = math.cos(theta), math.sin(theta)
    stator_circle = {}
    for tag in stator["circle"]:
        index, err = _circle_index(stator["nodes"][tag], n_gap)
        if err > 1e-9:
            raise RuntimeError("stator circle node is not on the uniform grid")
        stator_circle[index] = tag
    if len(stator_circle) != n_gap:
        raise RuntimeError(f"stator circle has {len(stator_circle)} nodes, not {n_gap}")
    nodes = dict(stator["nodes"])
    offset = max(nodes) + 1
    remap = {}
    rotor_circle = set(rotor["circle"])
    for tag, (x, y) in rotor["nodes"].items():
        xr, yr = c * x - s * y, s * x + c * y
        if tag in rotor_circle:
            index, err = _circle_index((x, y), n_gap)
            if err > 1e-9:
                raise RuntimeError("rotor circle node is not on the uniform grid")
            remap[tag] = stator_circle[(index + k) % n_gap]
        else:
            remap[tag] = offset + tag
            nodes[offset + tag] = (xr, yr)
    elements = []
    for region, entity, conn in stator["triangles"]:
        elements.append((2, region, entity, conn))
    for region, entity, conn in rotor["triangles"]:
        elements.append((2, region, 100000 + entity, tuple(remap[n] for n in conn)))
    for region, entity, conn in stator["lines"]:
        elements.append((1, region, entity, conn))
    with open(path, "w") as handle:
        handle.write("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$Nodes\n")
        handle.write(f"{len(nodes)}\n")
        for tag in sorted(nodes):
            x, y = nodes[tag]
            handle.write(f"{tag} {x * 1e-3!r} {y * 1e-3!r} 0\n")  # metres
        handle.write("$EndNodes\n$Elements\n")
        handle.write(f"{len(elements)}\n")
        for number, (etype, region, entity, conn) in enumerate(elements, 1):
            gmsh_type = 2 if etype == 2 else 1
            handle.write(
                f"{number} {gmsh_type} 2 {region} {entity} {' '.join(map(str, conn))}\n"
            )
        handle.write("$EndElements\n")
    return len(nodes), len(elements)


def main(argv):
    params_path, outdir = argv
    with open(params_path) as handle:
        p = json.load(handle)
    gmsh.initialize(["-nt", "1"])
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        rotor = _mesh_rotor(p)
        stator = _mesh_stator(p)
    finally:
        gmsh.finalize()
    if len(rotor["circle"]) != p["n_gap"] or len(stator["circle"]) != p["n_gap"]:
        raise RuntimeError(
            f"circle nodes: rotor {len(rotor['circle'])}, stator "
            f"{len(stator['circle'])}, expected {p['n_gap']} each"
        )
    record = {"n_gap": p["n_gap"], "steps": {}, "areas": {}}
    for k in p["steps"]:
        count = _write(f"{outdir}/rotor_{k}.msh", stator, rotor, k, p["n_gap"])
        record["steps"][str(k)] = {"nodes": count[0], "elements": count[1]}

    # Region areas in the unrotated mesh, for current density and checks.
    def area(tri, nodes):
        (x1, y1), (x2, y2), (x3, y3) = (nodes[n] for n in tri)
        return abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2

    for half in (rotor, stator):
        for region, _, conn in half["triangles"]:
            record["areas"][str(region)] = record["areas"].get(str(region), 0.0) + area(
                conn, half["nodes"]
            )
    with open(f"{outdir}/mesh.json", "w") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1:])
