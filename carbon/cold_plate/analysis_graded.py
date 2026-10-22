"""The cold plate's analysis for non-uniform axial meshes (graded-hotspot-v1):
the counted analysis with its energy check's heat-in taken from the faces the
solver actually heated (VALIDATOR_COOLING_RR14_DECISION_20261020 §1: a new
analysis version, never an in-place edit of the counted `analysis`).

The counted check builds the heat the solver applied as the heat map at
uniform axial face centres, (i + 0.5) L / nx, which is exact only for the
counted uniform family. Here it is the map at each `heated` face centre of the
solid region's polyMesh (the solver's `pos()`), times that face's area, and

    corrected energy_balance_rel = (1 + counted rel) * heat_in_uniform
                                   / heat_in_faces - 1,

since the counted rel is energy_out / heat_in_uniform - 1. Everything else is
the counted analysis's, unchanged; only the energy reason is replaced. This is
RR-14's Validator-approved re-analysis (`reanalyse.py`, run on the VM: corrected
5.1e-9, -1.2e-8, -4.5e-8 at r = 2, 2√2, 4).

DEVELOPMENT only: no qualification, LIVE or reward authority.
"""

from __future__ import annotations

import itertools
import json
import math
import re
from pathlib import Path

from . import analysis
from .domain import FIXED, heat_flux

ANALYSIS_VERSION = "carbon.cold-plate.graded-heat-in.v1"
#: Centres closer than this (m) are one axial column: 12-digit ASCII points
#: put one column's centres up to ~1e-13 m apart; columns are >= ~5e-5 m apart.
COLUMN_TOLERANCE_M = 1e-9


def _body(path):
    text = Path(path).read_text()
    header, rest = text.split("}", 1)
    if "binary" in header:
        raise ValueError(f"{path}: binary polyMesh; ASCII only")
    rest = re.sub(r"//.*", "", rest)
    m = re.search(r"(\d+)\s*\(", rest)
    if m is None:
        raise ValueError(f"{path}: no list")
    return int(m.group(1)), rest[m.end() : rest.rindex(")")]


def _points(path):
    n, body = _body(path)
    found = re.findall(r"\(\s*([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*\)", body)
    if len(found) != n:
        raise ValueError(f"{path}: {len(found)} points, header says {n}")
    return [tuple(map(float, p)) for p in found]


def _faces(path):
    n, body = _body(path)
    found = re.findall(r"(\d+)\s*\(([0-9\s]+)\)", body)
    if len(found) != n:
        raise ValueError(f"{path}: {len(found)} faces, header says {n}")
    out = []
    for size, ids in found:
        ids = [int(i) for i in ids.split()]
        if len(ids) != int(size):
            raise ValueError(f"{path}: malformed face")
        out.append(ids)
    return out


def _patch(path, name):
    m = re.search(rf"\b{name}\s*\{{([^}}]*)\}}", Path(path).read_text())
    if m is None:
        raise ValueError(f"{path}: no patch {name}")
    body = m.group(1)
    return (
        int(re.search(r"startFace\s+(\d+)", body).group(1)),
        int(re.search(r"nFaces\s+(\d+)", body).group(1)),
    )


def centre_and_area(vertices):
    """OpenFOAM's face centre and area magnitude (triangle fan about the
    vertex average); exact for the planar quads blockMesh writes."""
    k = len(vertices)
    avg = [sum(v[i] for v in vertices) / k for i in range(3)]
    total, centre = 0.0, [0.0, 0.0, 0.0]
    for a, b in zip(vertices, vertices[1:] + vertices[:1], strict=True):
        u = [b[i] - a[i] for i in range(3)]
        w = [avg[i] - a[i] for i in range(3)]
        cross = (
            u[1] * w[2] - u[2] * w[1],
            u[2] * w[0] - u[0] * w[2],
            u[0] * w[1] - u[1] * w[0],
        )
        area = 0.5 * math.sqrt(sum(c * c for c in cross))
        tri = [(a[i] + b[i] + avg[i]) / 3 for i in range(3)]
        total += area
        centre = [centre[i] + area * tri[i] for i in range(3)]
    return [c / total for c in centre], total


def _columns(xs, tol=COLUMN_TOLERANCE_M):
    xs = sorted(xs)
    return 1 + sum(b - a > tol for a, b in itertools.pairwise(xs)) if xs else 0


def heat_in(case_dir, record):
    """(heat_in_uniform_w, heat_in_faces_w): the counted formula, and the map
    on the solver's actual heated faces. Refuses a mesh read whose heated area
    or axial columns do not match the case (ValueError)."""
    inputs = record["inputs"]
    mesh = Path(case_dir) / "constant" / "solid" / "polyMesh"
    points, faces = _points(mesh / "points"), _faces(mesh / "faces")
    start, n = _patch(mesh / "boundary", "heated")
    length = FIXED["footprint_mm"] * 1e-3
    half_cell = (inputs["channel_width_mm"] + inputs["fin_width_mm"]) / 2 * 1e-3
    # The solver meshed the geometry as `openfoam.block_mesh` wrote it: vertices
    # at 6 significant digits (`{y:.6g}`), so the heated patch spans the written
    # half cell, not the exact one. Comparing with the exact value passed only
    # round-number inputs and refused every continuous draw (VALIDATOR_COOLING_
    # SEALED_STOP_20261022). The 1e-9 tolerance is unchanged.
    written_half_cell = float(f"{half_cell * 1e3:.6g}") * 1e-3
    faces_w, area_sum, xs = 0.0, 0.0, []
    for face in faces[start : start + n]:
        centre, area = centre_and_area([points[i] for i in face])
        faces_w += heat_flux(inputs, centre[0] * 1e3) * area
        area_sum += area
        xs.append(centre[0])
    nx = record["mesh"]["nx"]
    if abs(area_sum / (length * written_half_cell) - 1) > 1e-9 or _columns(xs) != nx:
        raise ValueError("heated faces do not match the case's footprint and nx")
    # The counted formula, verbatim (analysis.at_time).
    uniform_w = (
        sum(
            heat_flux(inputs, (i + 0.5) * FIXED["footprint_mm"] / nx) for i in range(nx)
        )
        / nx
        * length
        * half_cell
    )
    return uniform_w, faces_w


def correct(result, heat_in_uniform_w, heat_in_faces_w):
    """The counted result with its energy check recomputed on the faces."""
    if result.get("outcome") not in ("OK", "REFERENCE_INVALID"):
        return result
    counted = result["checks"]["energy_balance_rel"]
    energy = {
        "energy_balance_rel_uniform": counted,
        "heat_in_uniform_w": heat_in_uniform_w,
        "heat_in_faces_w": heat_in_faces_w,
    }
    rel = (1 + counted) * heat_in_uniform_w / heat_in_faces_w - 1
    limit = analysis.REFERENCE_CHECKS["energy_balance_rel"]
    reasons = [r for r in result["reasons"] if not r.startswith("energy_balance_rel")]
    if abs(rel) > limit:
        reasons.append(f"energy_balance_rel={rel:.3g} exceeds {limit:g}")
    return {
        **result,
        "analysis_version": ANALYSIS_VERSION,
        "outcome": "REFERENCE_INVALID" if reasons else "OK",
        "reasons": reasons,
        "checks": {**result["checks"], "energy_balance_rel": rel},
        "energy_balance": energy,
        # Also in diagnostics, which the reference runner copies into each
        # record, so every record states the analysis version that judged it.
        "diagnostics": {
            **(result.get("diagnostics") or {}),
            "analysis_version": ANALYSIS_VERSION,
            "energy_balance": energy,
        },
    }


def analyze_case(case_dir):
    """The counted analysis, corrected for the case's actual heated faces."""
    result = analysis.analyze_case(case_dir)
    if result.get("outcome") not in ("OK", "REFERENCE_INVALID"):
        return result
    record = json.loads((Path(case_dir) / "case.json").read_text())
    try:
        uniform_w, faces_w = heat_in(case_dir, record)
    except (OSError, ValueError, KeyError) as exc:
        return {
            **result,
            "analysis_version": ANALYSIS_VERSION,
            "outcome": "REFERENCE_SOLVER_FAILED",
            "reasons": [f"heated faces unreadable: {type(exc).__name__}: {exc}"],
        }
    return correct(result, uniform_w, faces_w)


__all__ = ["ANALYSIS_VERSION", "analyze_case", "correct", "heat_in"]
