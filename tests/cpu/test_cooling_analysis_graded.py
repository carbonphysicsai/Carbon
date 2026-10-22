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


#: A cell drawn from the sealed law with the recorded public seed 20261022
#: (SEALED_COOLING_DIAG_20261022): continuous inputs, unlike RR-14's fixtures.
LAW_CELL = {
    "channel_width_mm": 0.24227953683919978,
    "fin_width_mm": 0.3043113354034113,
    "channel_depth_mm": 1.1141021707895193,
    "flow_lpm_per_kw": 1.8752906972352945,
    "inlet_c": 40.0696090505744,
    "heat_load_w": 1417.6574458320997,
    "hotspot_ratio": 1.0787758787628,
    "hotspot_center_mm": 21.3896504457261,
    "hotspot_width_mm": 2.612777634836104,
}


def _graded_case_dir(tmp_path, jitter=2e-13, nx_override=None, inputs=None, written=False):
    """A case dir whose solid polyMesh holds only the heated patch, laid out
    exactly as the family's x grading at r = 2 (blockMesh's section rounding)."""
    registered = json.loads((RR14 / "cases" / "r2" / "case.json").read_text())
    inputs = inputs or registered["inputs"]
    registered = {**registered, "inputs": inputs}
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
    if written:  # the mesh as openfoam.block_mesh writes it: vertices at 6 digits
        half = float(f"{half * 1e3:.6g}") * 1e-3
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


def test_the_real_writers_vertices_are_what_the_guard_expects():
    """The guard's written half cell is read from what the case writer emits,
    for round fixtures and for a continuous law draw."""
    import re

    for inputs in (
        json.loads((RR14 / "cases" / "r2" / "case.json").read_text())["inputs"],
        LAW_CELL,
    ):
        texts, _record = mf.files(
            inputs, mesh_family=mf.GRADED_HOTSPOT_V1, resolution=2 * math.sqrt(2)
        )
        ys = {
            float(m.group(1))
            for m in re.finditer(
                r"^\s+\(\S+ (\S+) \S+\)$", texts["system/blockMeshDict"], re.M
            )
        }
        exact = (inputs["channel_width_mm"] + inputs["fin_width_mm"]) / 2
        assert max(ys) == float(f"{exact:.6g}")
        assert (max(ys) == exact) == (inputs is not LAW_CELL)  # only the fixture is exact


def test_a_continuous_inputs_mesh_at_written_precision_passes(tmp_path):
    """The failure on 30 of 32 sealed cases: the heated area is the written
    (6-digit) half cell, which the exact-input check refused."""
    from carbon.cold_plate.domain import FIXED  # noqa: F401 - the footprint is 30 mm

    d, record, _ = _graded_case_dir(tmp_path, inputs=LAW_CELL, written=True)
    uniform_w, faces_w = ag.heat_in(d, record)
    assert faces_w > 0 and uniform_w > 0


def test_the_tolerance_still_refuses_a_wrong_area(tmp_path):
    """The area check is not loosened: a mesh 1e-6 off the written geometry fails."""
    d, record, _ = _graded_case_dir(tmp_path, inputs=LAW_CELL, written=False)
    with pytest.raises(ValueError, match="footprint"):
        ag.heat_in(d, record)  # exact-half-cell mesh vs written expectation: ~1e-6 apart
