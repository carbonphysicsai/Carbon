"""Cooling's graded-hotspot-v1 mesh family (RR-PACKS-14; Validator decisions
VALIDATOR_COOLING_RR14_DECISION_20261020 and VALIDATOR_MAINNET_RECAL_DECISIONS_20261020).

The counted case writer (`openfoam.files`) is unchanged and bound by earlier
freezes; this module substitutes only its block mesh for a case written with
`mesh_family="graded-hotspot-v1"`, exactly as RR-14's reviewed wrapper did
(`family_run.py`), so every other file, solver setting and the analysis stay
the counted ones. Against the counted family (CELLS x 50, y (5, 5), z (5, 10, 3)
at r = 1, wall grading g):
- base (k = 0, the heated solid under the die): 10 cells at r = 1 instead of 5,
  graded fine toward both faces ((0.5 0.5 g)(0.5 0.5 1/g)), as the channel
  block already is; the counted family grades it 1/g only, coarsest at the
  heated face where the die peak is read;
- flow direction (x): the same nx = 50 r, redistributed: half in the window
  [xc - 2w, xc + 2w] around the case's hot spot (clipped to the plate), half
  over the outer segments in proportion to their length; uniform within each.

Its x faces are non-uniform, so its references need the graded heat-in energy
check (`analysis_graded`), not the counted uniform one.

DEVELOPMENT only: no qualification, LIVE or reward authority.
"""

from __future__ import annotations

import threading

from . import openfoam

GRADED_HOTSPOT_V1 = "graded-hotspot-v1"
MESH_FAMILIES = (GRADED_HOTSPOT_V1,)
#: openfoam.CELLS and openfoam.block_mesh are module globals; one family build
#: at a time.
_LOCK = threading.Lock()


def x_grading(length, nx, centre, width):
    """Multi-section uniform grading: half the cells in the hot-spot window."""
    a, b = max(0.0, centre - 2 * width), min(length, centre + 2 * width)
    segments = [(a, "outer"), (b - a, "window"), (length - b, "outer")]
    outer = sum(s for s, kind in segments if kind == "outer")
    sections = []
    for size, kind in segments:
        if size <= 0:
            continue
        share = 0.5 if kind == "window" else 0.5 * size / outer
        sections.append((size / length, share))
    total = sum(share for _, share in sections)  # 1 unless a segment vanished
    body = " ".join(f"({lf:.12g} {share / total:.12g} 1)" for lf, share in sections)
    return f"({body})"


def _family_block_mesh(original_block_mesh, g, r, grading, centre, width):
    """The counted blockMeshDict with the two family changes applied. Called
    with _LOCK held."""
    saved = dict(openfoam.CELLS)
    openfoam.CELLS["z"] = (10,) + tuple(saved["z"][1:])
    try:
        text, mesh = original_block_mesh(g, r, grading)
    finally:
        openfoam.CELLS.clear()
        openfoam.CELLS.update(saved)
    base = f"{1 / grading:.12g}" if grading != 1.0 else "1"
    both = f"((0.5 0.5 {grading:.12g}) (0.5 0.5 {1 / grading:.12g}))"
    xg = x_grading(g["length"], mesh["nx"], centre, width)
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("hex (") and "simpleGrading (1 " in line:
            head, grade = line.split("simpleGrading (1 ", 1)
            y, z = grade[:-1].split(" ", 1)
            if " ((" not in grade and z == base and grading != 1.0:
                z = both  # the base block: fine toward both faces
            line = f"{head}simpleGrading ({xg} {y} {z})"
        lines.append(line)
    if grading != 1.0 and sum(both in line for line in lines) != 4:
        raise ValueError("graded-hotspot-v1: base blocks not found exactly as expected")
    mesh = {**mesh, "family": GRADED_HOTSPOT_V1, "x_grading": xg}
    return "\n".join(lines) + "\n", mesh


def files(case, *, mesh_family=None, **options):
    """`openfoam.files`, with the named mesh family's block mesh substituted."""
    if mesh_family is None:
        return openfoam.files(case, **options)
    if mesh_family not in MESH_FAMILIES:
        raise ValueError(f"unknown mesh_family {mesh_family!r}")
    centre, width = case["hotspot_center_mm"], case["hotspot_width_mm"]
    with _LOCK:
        original = openfoam.block_mesh

        def block_mesh(g, r, grading):
            return _family_block_mesh(original, g, r, grading, centre, width)

        openfoam.block_mesh = block_mesh
        try:
            texts, record = openfoam.files(case, **options)
        finally:
            openfoam.block_mesh = original
    record["mesh_family"] = GRADED_HOTSPOT_V1
    return texts, record


def write_case(case, out, *, mesh_family=None, **options):
    """`openfoam.write_case` for the named family (or the counted one)."""
    from pathlib import Path

    out = Path(out)
    if out.exists():
        raise FileExistsError(f"{out} exists; refusing to overwrite")
    texts, record = files(case, mesh_family=mesh_family, **options)
    for relative, text in texts.items():
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    out.chmod(0o700)
    return record


__all__ = ["GRADED_HOTSPOT_V1", "MESH_FAMILIES", "files", "write_case", "x_grading"]
