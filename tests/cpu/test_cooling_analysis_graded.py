"""The graded heat-in analysis version: RR-14's corrected energy balance
reproduced from its committed evidence, and the face read checked on a
synthetic graded mesh (with 12-digit-ASCII-like jitter)."""

from __future__ import annotations

import itertools
import json
import math
import random
from pathlib import Path

import pytest

from carbon.cold_plate import analysis_graded as ag
from carbon.cold_plate import mesh_family as mf
from carbon.cold_plate.domain import FIXED, heat_flux

ROOT = Path(__file__).resolve().parents[2]
RR14 = ROOT / "docs/development/evidence/cooling-rr14-20261020"


@pytest.mark.parametrize("level", ["r2", "r2s2", "r4"])
def test_correct_reproduces_rr14s_reanalysis(level):
    counted = json.loads((RR14 / "cases" / level / "analysis.json").read_text())
    rows = json.loads((RR14 / "reanalysis.json").read_text())["levels"]
    row = rows[level]
    assert counted["outcome"] == "REFERENCE_INVALID"  # the uniform check's artefact
    fixed = ag.correct(counted, row["heat_in_uniform_w"], row["heat_in_actual_w"])
    assert fixed["checks"]["energy_balance_rel"] == pytest.approx(
        row["energy_balance_rel_corrected"], rel=1e-9, abs=1e-15
    )
    assert fixed["outcome"] == "OK" and fixed["reasons"] == []
    assert fixed["analysis_version"] == ag.ANALYSIS_VERSION
    assert fixed["outputs"] == counted["outputs"]  # nothing else changes


def _graded_case_dir(tmp_path, jitter=2e-13, nx_override=None):
    """A case dir whose solid polyMesh holds only the heated patch, laid out
    exactly as the family's x grading at r = 2 (blockMesh's section rounding)."""
    registered = json.loads((RR14 / "cases" / "r2" / "case.json").read_text())
    inputs = registered["inputs"]
    nx = registered["mesh"]["nx"]
    length = FIXED["footprint_mm"]
    g = mf.x_grading(
        length, nx, inputs["hotspot_center_mm"], inputs["hotspot_width_mm"]
    )
    sections = [
        tuple(map(float, s.strip("() ").split())) for s in g.strip("()").split(") (")
    ]
    counts = [round(fc * nx) for _, fc, _ in sections]
    counts[-1] += nx - sum(counts)
    xe, pos = [0.0], 0.0
    for (fl, _, _), n in zip(sections, counts, strict=True):
        xe += [(pos + fl * length * (k + 1) / n) * 1e-3 for k in range(n)]
        pos += fl * length
    half = (inputs["channel_width_mm"] + inputs["fin_width_mm"]) / 2 * 1e-3
    ny = 4
    rng = random.Random(1)
    ye = [half * j / ny for j in range(ny + 1)]
    pts = [(x + rng.uniform(-jitter, jitter), y, 0.0) for y in ye for x in xe]
    idx = lambda i, j: j * (nx + 1) + i
    fcs = [
        [idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)]
        for j in range(ny)
        for i in range(nx)
    ]
    d = tmp_path / "case"
    mesh = d / "constant" / "solid" / "polyMesh"
    mesh.mkdir(parents=True)
    head = "FoamFile\n{\n    format ascii;\n    class %s;\n}\n\n"
    (mesh / "points").write_text(
        head % "vectorField"
        + f"{len(pts)}\n(\n"
        + "".join(f"({x:.12g} {y:.12g} {z:.12g})\n" for x, y, z in pts)
        + ")\n"
    )
    (mesh / "faces").write_text(
        head % "faceList"
        + f"{len(fcs)}\n(\n"
        + "".join(f"4({' '.join(map(str, f))})\n" for f in fcs)
        + ")\n"
    )
    (mesh / "boundary").write_text(
        head % "polyBoundaryMesh"
        + "1\n(\n    heated\n    {\n        type wall;\n"
        + f"        nFaces {len(fcs)};\n        startFace 0;\n    }}\n)\n"
    )
    record = {**registered, "mesh": {**registered["mesh"], "nx": nx_override or nx}}
    exact = (
        sum(
            heat_flux(inputs, (a + b) / 2 * 1e3) * (b - a)
            for a, b in itertools.pairwise(xe)
        )
        * half
    )
    return d, record, exact


def test_heat_in_reads_the_actual_faces(tmp_path):
    d, record, exact = _graded_case_dir(tmp_path)
    uniform_w, faces_w = ag.heat_in(d, record)
    assert faces_w == pytest.approx(exact, rel=1e-9)
    # The uniform formula differs on this graded mesh, as RR-14 found.
    assert abs(uniform_w / faces_w - 1) > 1e-5


def test_a_mismatched_face_read_is_refused(tmp_path):
    d, record, _ = _graded_case_dir(tmp_path, nx_override=101)
    with pytest.raises(ValueError, match="nx"):
        ag.heat_in(d, record)


def test_a_failed_counted_analysis_passes_through_unchanged():
    failed = {"outcome": "REFERENCE_SOLVER_FAILED", "reasons": ["unreadable"]}
    assert ag.correct(failed, 1.0, 1.0) is failed
    assert math.isfinite(ag.COLUMN_TOLERANCE_M)
