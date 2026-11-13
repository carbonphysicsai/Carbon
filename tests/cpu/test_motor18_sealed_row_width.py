"""Motor 1.8's sealed bank is as wide as its model row (13 Nov, G-R #2: saved_prediction_shape).

The 1.8 model answers with a 240-wide row (torque, then the phase flux linkages A, B, C), but `motor_sealed_pack.sealed_bank` built every
Motor bank's references as the torque slice (60 wide). The producer reads ONE width from the bank for the registered output shape,
the reference rows and its check of every answer, so the pack registered ``[n, 60]`` while the graded predictions were ``[n, 240]``, and
the grade stopped in `bundle_benchmark_core._flat_tensor` after custody passed. The 1.8 bank's references are now 240 wide: the sealed
torque truth in the first 60 columns, structural zeros beyond (no measure reads them). Every other version keeps 60. Synthetic fixtures
only; nothing here is a production value.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_motor18_pool_pack_e2e import (  # noqa: F401  (fixtures and the synthetic build inputs)
    MOTOR,
    VERSION,
    _documents,
    _material,
    batch,
    pool_pack,
    registered,
)

from carbon.challenge_kit import motor_sealed_pack as pack
from carbon.motor.domain import ANGLE_STEPS
from carbon.scoring import sealed_batch_source as source


def test_the_model_row_width_is_set_for_1_8_only():
    from carbon.motor import row18

    assert pack._model_row_width("1.8") == row18.WIDTH == 4 * ANGLE_STEPS
    for version in ("1.1", "1.2", "1.5", "1.6"):
        assert pack._model_row_width(version) is None


def test_a_1_8_sealed_bank_has_240_wide_references_with_the_torque_first(
    batch,  # noqa: F811
):
    document, records = batch
    narrow = pack.grid_bank(document, records, version="1.6")
    wide = pack.grid_bank(document, records, version="1.8")
    assert narrow["references"].shape[1] == ANGLE_STEPS
    assert wide["references"].shape[1] == 4 * ANGLE_STEPS
    assert wide["references"].shape[0] == narrow["references"].shape[0]
    cells = [c.startswith("decision") for c in wide["cohorts"]]
    present = np.asarray(
        wide.get("reference_present")
        or [not np.isnan(r).all() for r in wide["references"]]
    )
    # the sealed torque truth is unchanged, the rest is zero on every referenced row; unreferenced rows stay NaN
    for i, has in enumerate(present):
        if has:
            assert np.array_equal(
                wide["references"][i][:ANGLE_STEPS],
                narrow["references"][i][:ANGLE_STEPS],
            )
            assert not wide["references"][i][ANGLE_STEPS:].any()
        else:
            assert np.isnan(wide["references"][i]).all()
    assert any(cells)
    assert wide["references"].flags.writeable is False


def test_the_registered_output_shape_of_a_1_8_pool_pack_is_the_models_width(
    batch,  # noqa: F811
    tmp_path,
    registered,  # noqa: F811
):
    menus, key, _shas = registered
    document, records = batch
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / source.SEALED_BATCH_FILE).write_bytes(
        source.batch_bytes(document, records)
    )
    out = tmp_path / "out"
    record = pool_pack.build(
        challenge=MOTOR,
        version=VERSION,
        batch_dir=plain,
        out_dir=out,
        inference_image_id="sha256:" + "1" * 64,
        material=_material(),
        menu_dir=menus,
        crown_key_file=key,
        documents=_documents(),
    )
    rows = record["rows"]["total"]
    registration = json.loads(
        (out / "pack" / "private" / "source_registration.json").read_bytes()
    )["benchmark_registration"]
    assert registration["output"]["shape"] == [rows, 4 * ANGLE_STEPS]
    assert registration["output"]["size"] == rows * 4 * ANGLE_STEPS
    reference_rows = json.loads(
        (out / "pack" / "private" / "reference_rows.json").read_bytes()
    )
    assert len(reference_rows[0]["outputs"]) == rows * 4 * ANGLE_STEPS
