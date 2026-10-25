"""Retention keeps a finite public fixture: a development grid's reference-less probe rows are left out of it."""

from __future__ import annotations

import io

import numpy as np
import pytest

from carbon.challenge_kit import physical_material
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session.bundle_construction_worker import _tensors

DEV_GRID_VERSIONS = (
    ("chip-cold-plate", "1.4"),
    ("f08-ribbed-bracket", "1.5"),
    ("electric-motor-magnetics", "1.4"),
    ("f02", "2.4"),
)


def _load(raw):
    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        return {k: np.asarray(data[k]) for k in data.files}


def test_a_version_with_every_reference_present_keeps_its_exact_bytes():
    inputs = np.arange(12, dtype=np.float64).reshape(4, 3)
    targets = np.arange(8, dtype=np.float64).reshape(4, 2)
    material = {"practice_inputs": inputs, "practice_reference": targets}
    assert retention._fixture_tensors(material) == _tensors(
        inputs=inputs, targets=targets
    )


def test_probe_rows_without_a_reference_are_left_out_of_the_fixture():
    inputs = np.arange(12, dtype=np.float64).reshape(4, 3)
    targets = np.arange(8, dtype=np.float64).reshape(4, 2)
    targets[[1, 3]] = np.nan
    fixture = _load(
        retention._fixture_tensors(
            {"practice_inputs": inputs, "practice_reference": targets}
        )
    )
    assert np.array_equal(fixture["inputs"], inputs[[0, 2]])
    assert np.array_equal(fixture["targets"], targets[[0, 2]])
    assert np.isfinite(fixture["targets"]).all()


def test_a_partly_missing_reference_row_is_a_broken_reference_not_a_probe():
    inputs = np.zeros((3, 2))
    targets = np.ones((3, 2))
    targets[1, 0] = np.nan
    with pytest.raises(retention.RetentionUnavailable) as raised:
        retention._fixture_tensors(
            {"practice_inputs": inputs, "practice_reference": targets}
        )
    assert str(raised.value) == "practice_reference_partly_missing"
    with pytest.raises(retention.RetentionUnavailable):
        retention._fixture_tensors(
            {"practice_inputs": inputs, "practice_reference": np.full((3, 2), np.nan)}
        )


@pytest.mark.parametrize(("challenge_id", "version"), DEV_GRID_VERSIONS)
def test_the_real_development_grid_fixture_retains(challenge_id, version):
    material = physical_material.bundle_material(challenge_id, version)
    targets = material["practice_reference"]
    assert not np.isfinite(targets).all()  # the probe rows: the bug this pins
    fixture = _load(retention._fixture_tensors(material))
    present = np.isfinite(targets).all(axis=1)
    assert present.any() and not present.all()
    assert len(fixture["targets"]) == int(present.sum())
    assert np.isfinite(fixture["targets"]).all()
    assert np.array_equal(fixture["inputs"], material["practice_inputs"][present])
    # the inputs file the inference receipt is checked against still holds every row
    assert len(_load(_tensors(inputs=material["practice_inputs"]))["inputs"]) == len(
        targets
    )
