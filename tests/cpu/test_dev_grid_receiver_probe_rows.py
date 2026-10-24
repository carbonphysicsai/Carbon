"""The receiver's snapshot of a dev-grid version's practice bank accepts the
bank's probe rows, which have no reference, and nothing else without one
(Validator, 2026-10-24): a wholly NaN reference row is allowed only where the
row's case id is a probe-cohort id; every other row must be wholly finite, so
a cell that lost its reference still refuses."""

import numpy as np
import pytest

from carbon.challenge_kit import physical_material
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.scoring import dev_grid, probe_design

KEYS = sorted(dev_grid.GRID_KINDS)
REFUSED = "direct public practice bytes or case IDs differ"


def _material(key):
    material = dict(physical_material.bundle_material(*key))
    material["practice_reference"] = material["practice_reference"].copy()
    return material


def _rows(material):
    ids = material["practice_case_ids"]
    probe = [i for i, c in enumerate(ids) if probe_design.is_probe_id(c)]
    cells = [i for i, c in enumerate(ids) if not probe_design.is_probe_id(c)]
    return probe, cells


@pytest.mark.parametrize("key", KEYS)
def test_the_bank_with_its_probe_rows_is_accepted(key):
    material = _material(key)
    probe, cells = _rows(material)
    reference = material["practice_reference"]
    assert probe and all(np.isnan(reference[i]).all() for i in probe)
    assert cells and all(np.isfinite(reference[i]).all() for i in cells)
    DirectFixtureDiscovery(material, task_admission=True)


@pytest.mark.parametrize("key", KEYS)
def test_a_cell_that_lost_its_reference_refuses(key):
    material = _material(key)
    _, cells = _rows(material)
    material["practice_reference"][cells[0]] = np.nan
    with pytest.raises(ValueError, match=REFUSED):
        DirectFixtureDiscovery(material, task_admission=True)


@pytest.mark.parametrize("key", KEYS)
def test_a_partly_missing_reference_refuses_in_a_cell_and_in_a_probe(key):
    for which in (0, 1):
        material = _material(key)
        rows = _rows(material)[which]
        material["practice_reference"][rows[0]][0] = np.nan
        if which == 1:
            # A cell's row with one missing value.
            pass
        else:
            # A probe row is wholly NaN or wholly finite: one finite value in
            # an otherwise NaN probe row is neither.
            material["practice_reference"][rows[0]][:] = np.nan
            material["practice_reference"][rows[0]][0] = 1.0
        # A one-column bank (F02) leaves such a probe row wholly finite, which
        # the registered-fixture comparison then refuses.
        with pytest.raises(ValueError, match="direct public"):
            DirectFixtureDiscovery(material, task_admission=True)


def test_only_a_probe_id_names_a_probe_row():
    assert probe_design.is_probe_id("probe-03-d3m")
    assert not probe_design.is_probe_id("decision-d03-rep-01")
    assert not probe_design.is_probe_id(None)
    assert not probe_design.is_probe_id(b"probe-00-base")
