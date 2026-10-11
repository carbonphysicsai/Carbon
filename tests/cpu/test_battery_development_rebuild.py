"""One dispatch for battery's development rebuilds: every level routes through
`development_rebuild`, and Level 0 passes through untouched."""

from __future__ import annotations

import pytest

from carbon.battery import development_rebuild as dr
from carbon.battery import level2_worker, level3_worker

NUMERICS = {
    "schema": level3_worker.SCHEMA,
    "routine": "bfgs",
    "line_search": "none",
    "lane": "CPU_ONLY_DEV",
}
SPECTRAL = {
    "schema": level2_worker.SCHEMA,
    "interpretation": "specmuon-carbon-v1",
    "lane": "CPU_ONLY_DEV",
}


def test_level_0_passes_through_untouched():
    assert dr.record(None) is None and dr.record({}) is None
    assert dr.stage(None, "PROGRAM", {"a": b"1"}, level1_program=lambda: 1 / 0) == (
        "PROGRAM",
        {"a": b"1"},
        None,
    )
    assert dr.rebuild_label(None) is None


@pytest.mark.parametrize(
    ("reconstruction", "level"),
    [
        ({level3_worker.QUASI_NEWTON: {"routine": "bfgs"}}, dr.LEVEL3),
        ({level3_worker.LINE_SEARCH: {"line_search": "none"}}, dr.LEVEL3),
        (
            {level2_worker.SPECTRAL: {"muon_spectral": True, "interpretation": "x"}},
            dr.LEVEL2,
        ),
    ],
)
def test_each_level_is_found_and_never_rebuilt_as_level_0(reconstruction, level):
    found = dr.record(reconstruction)
    assert dr.kind(found) == level
    assert dr.rebuild_label(found) == "rebuild: CPU-verified only"


def test_defaults_and_off_switches_are_level_0():
    assert dr.record({level3_worker.QUASI_NEWTON: {"routine": "lbfgs"}}) is None
    assert dr.record({level2_worker.SPECTRAL: {"muon_spectral": False}}) is None


@pytest.mark.parametrize(
    ("found", "trainer"), [(NUMERICS, dr.LEVEL3), (SPECTRAL, dr.LEVEL2)]
)
def test_levels_2_and_3_replace_the_base_programs_build_line(found, trainer):
    base = 'try:\n    model = recipes.build(recipe["family"], recipe["settings"])\n'
    program, files, kind = dr.stage(found, base, {}, level1_program=lambda: 1 / 0)
    assert kind == trainer and "recipes.build(" not in program
    assert 'raise ImportError("' in program and files
