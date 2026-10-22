"""Cooling's graded-hotspot-v1 mesh family in code: the counted writer is
unchanged, and the family reproduces RR-PACKS-14's executed cases exactly."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from carbon.cold_plate import mesh_family as mf
from carbon.cold_plate import openfoam

ROOT = Path(__file__).resolve().parents[2]
RR14 = ROOT / "docs/development/evidence/cooling-rr14-20261020/cases"
LEVELS = (("r2", 2.0), ("r2s2", 2 * math.sqrt(2)), ("r4", 4.0))


def _inputs():
    return json.loads((RR14 / "r2" / "case.json").read_text())["inputs"]


def test_without_a_family_the_counted_writer_is_unchanged():
    case = _inputs()
    assert mf.files(case, resolution=2.0) == openfoam.files(case, resolution=2.0)


@pytest.mark.parametrize(("level", "r"), LEVELS)
def test_the_family_reproduces_rr14s_executed_cases(level, r):
    """RR-14 ran the family through the reviewed wrapper; the in-code family
    writes the same case.json (inputs, mesh record, x grading, cells)."""
    registered = json.loads((RR14 / level / "case.json").read_text())
    texts, record = mf.files(
        registered["inputs"], mesh_family=mf.GRADED_HOTSPOT_V1, resolution=r
    )
    assert json.loads(texts["case.json"]) == registered
    assert record["mesh_family"] == mf.GRADED_HOTSPOT_V1


def test_only_the_block_mesh_and_case_record_differ_from_the_counted_case():
    case = _inputs()
    texts, _ = mf.files(case, mesh_family=mf.GRADED_HOTSPOT_V1, resolution=2.0)
    counted, _ = openfoam.files(case, resolution=2.0)
    assert set(texts) == set(counted)
    assert sorted(k for k in texts if texts[k] != counted[k]) == [
        "case.json",
        "system/blockMeshDict",
    ]


def test_the_counted_globals_are_restored_and_unknown_families_refused():
    before_cells, before_block_mesh = dict(openfoam.CELLS), openfoam.block_mesh
    mf.files(_inputs(), mesh_family=mf.GRADED_HOTSPOT_V1, resolution=2.0)
    assert openfoam.CELLS == before_cells
    assert openfoam.block_mesh is before_block_mesh
    with pytest.raises(ValueError):
        mf.files(_inputs(), mesh_family="graded-hotspot-v9", resolution=2.0)


def test_write_case_refuses_to_overwrite(tmp_path):
    out = tmp_path / "case"
    mf.write_case(_inputs(), out, mesh_family=mf.GRADED_HOTSPOT_V1, resolution=2.0)
    assert (out / "system" / "blockMeshDict").is_file()
    with pytest.raises(FileExistsError):
        mf.write_case(_inputs(), out, mesh_family=mf.GRADED_HOTSPOT_V1)
