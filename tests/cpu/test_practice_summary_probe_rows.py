"""F08 1.5 and F02 2.4 practice ended FAILED_INFRA after a successful build and inference
(TR2, rc42, 32 GB host): their practice grid carries public-seeded probe rows, which have no
reference, and the practice summary scored them all: F08's reference has NaN there
(`f08_practice_error_nonfinite`) and F02's records have no `rung_peaks_c`
(`KeyError`). The error is now reported on the exposed cells only; the probes still reach
the dual feedback, which grades them as the exam does.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from carbon.challenge_kit import physical_material
from carbon.direct_campaign import practice as practice_module
from carbon.direct_campaign.spec import SPECS
from carbon.scoring import probe_design

CASES = [
    ("f08-ribbed-bracket", "1.5"),
    ("f02", "2.4"),
    ("f08-ribbed-bracket", "1.4"),
    ("f02", "2.3"),
]


def _rows(material, spec):
    """A plausible prediction for every practice row: the reference where there is one."""
    reference = np.asarray(material["practice_reference"], dtype=np.float64)
    if spec.prefix == "f02":
        from carbon.challenge_kit import physical_pack

        bank = physical_pack.development_bank(spec.challenge_id, material["version"])
        reference = np.asarray(
            [
                [float(r["rung_peaks_c"]["primary"])] if "rung_peaks_c" in r else [0.0]
                for r in bank["reference_records"]
            ]
        )
    return np.where(np.isfinite(reference), reference, 0.0).astype(np.float32).astype(np.float64)


@pytest.mark.parametrize(("challenge", "version"), CASES)
def test_the_practice_summary_scores_the_exposed_cells_and_not_the_probe_rows(
    challenge, version
):
    material = {**physical_material.bundle_material(challenge, version), "version": version}
    spec = SPECS[challenge]
    ids = list(material["practice_case_ids"])
    cells = [c for c in ids if not probe_design.is_probe_id(c)]
    rows = _rows(material, spec)
    assert rows.shape == tuple(material["expected_output_shape"])
    out = practice_module.summary(spec, version, material["interface_document"], rows, material)
    assert math.isfinite(out["score"]) and out["status"] == "aggregate_on_registered_scale"
    assert out["n_scored"] == len(cells) > 0
    assert out["n_cases"] == len(ids)
    # A dev-grid version has probes (so fewer scored than rows); an older one has none.
    has_probes = version in ("1.5", "2.4")
    assert (out["n_scored"] < out["n_cases"]) is has_probes


def test_a_probe_row_can_hold_anything_without_moving_the_error():
    material = physical_material.bundle_material("f08-ribbed-bracket", "1.5")
    spec = SPECS["f08-ribbed-bracket"]
    rows = _rows({**material, "version": "1.5"}, spec)
    base = practice_module.summary(spec, "1.5", material["interface_document"], rows, material)
    probes = [i for i, c in enumerate(material["practice_case_ids"]) if probe_design.is_probe_id(c)]
    assert probes
    changed = rows.copy()
    changed[probes] = 1.0e6
    again = practice_module.summary(spec, "1.5", material["interface_document"], changed, material)
    assert again["score"] == base["score"]
