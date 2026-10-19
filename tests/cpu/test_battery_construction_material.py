"""The shared construction tensor codec preserves Battery's existing material."""

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import challenge, construction_kit, construction_material, domain

ROOT = Path(__file__).resolve().parents[2]


def _train():
    return (ROOT / challenge.TRAIN_V1_PATH).read_bytes()


def test_fixed_train_keeps_original_byte_identity_and_raw_tensor_order():
    raw = _train()
    train = construction_material.decode_train(raw)
    inputs, targets = construction_material.train_tensors(raw)
    assert construction_kit.construction_kit()["train_digest"] == (
        "sha256:" + hashlib.sha256(raw).hexdigest()
    )
    assert len(train.case_ids) == challenge.TRAIN_V1_CASES == 400
    assert inputs.shape == (400, len(domain.INPUTS))
    assert targets.shape == (400, construction_material.OUTPUT_WIDTH)
    assert inputs.dtype == np.dtype(float)
    np.testing.assert_array_equal(inputs, train.x)
    g = domain.GRID_POINTS
    np.testing.assert_array_equal(targets[:, :g], train.v)
    np.testing.assert_array_equal(targets[:, g : 2 * g], train.t)
    np.testing.assert_array_equal(targets[:, 2 * g], train.eta)
    np.testing.assert_array_equal(targets[:, 2 * g + 1 :], train.q)
    records = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    assert train.case_ids == tuple(row["case_id"] for row in records)
    assert inputs[0].tolist() == [records[0]["inputs"][k] for k in domain.INPUTS]
    assert targets[0, 0] == records[0]["outputs"]["voltage_v"][0]
    assert targets[0, 2 * g] == records[0]["outputs"]["plating_margin_v"]


def test_derived_or_changed_train_bytes_cannot_replace_original_pin():
    raw = _train()
    for other in (gzip.decompress(raw), raw[:-1], bytearray(raw)):
        with pytest.raises(challenge.MaterialMismatch, match="pinned digest"):
            construction_material.decode_train(other)


@pytest.mark.parametrize("defect", ["role", "status", "count", "shape", "missing"])
def test_train_record_failures_remain_typed_after_byte_verification(
    monkeypatch, defect
):
    records = [json.loads(line) for line in gzip.decompress(_train()).splitlines()]
    if defect == "role":
        records[0]["role"] = "practice"
    elif defect == "status":
        records[0]["status"] = "FAILED_INFRA"
    elif defect == "count":
        records.pop()
    elif defect == "shape":
        records[0]["outputs"]["voltage_v"].pop()
    else:
        del records[0]["outputs"]
    raw = gzip.compress(b"\n".join(json.dumps(row).encode() for row in records))
    # Exercise decoder error branches; normal calls still require the real pin.
    monkeypatch.setattr(challenge, "TRAIN_V1_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(challenge.MaterialMismatch):
        construction_material.decode_train(raw)


def _cases():
    return [
        {
            "case_id": "case-a",
            "inputs": {"soc0": 0.2, "t_amb_c": 20.0, "c2": 0.4, "c1": 1.0},
        },
        {
            "case_id": "case-b",
            "inputs": {"c1": 1.5, "c2": 0.6, "t_amb_c": 30.0, "soc0": 0.3},
        },
    ]


def test_case_input_conversion_keeps_record_and_published_column_order():
    np.testing.assert_array_equal(
        construction_material.case_inputs(_cases()),
        [[1.0, 0.4, 20.0, 0.2], [1.5, 0.6, 30.0, 0.3]],
    )


@pytest.mark.parametrize("defect", ["duplicate", "label", "nonfinite", "bounds"])
def test_case_input_conversion_refuses_malformed_input_only_cases(defect):
    cases = _cases()
    if defect == "duplicate":
        cases[1]["case_id"] = cases[0]["case_id"]
    elif defect == "label":
        cases[0]["outputs"] = {}
    else:
        cases[0]["inputs"]["c1"] = float("nan") if defect == "nonfinite" else 4.0
    with pytest.raises(challenge.MaterialMismatch):
        construction_material.case_inputs(cases)


def test_flat_output_conversion_roundtrips_every_raw_train_output():
    train = construction_material.decode_train(_train())
    _, values = construction_material.train_tensors(_train())
    predictions = construction_material.output_predictions(values, train.case_ids)
    for index, case in enumerate(train.case_ids):
        assert predictions[case] == {
            "voltage_v": train.v[index].tolist(),
            "temperature_c": train.t[index].tolist(),
            "plating_margin_v": float(train.eta[index]),
            "capacity_ah": train.q[index].tolist(),
        }


@pytest.mark.parametrize("defect", ["width", "nonfinite", "duplicate", "count"])
def test_flat_output_conversion_refuses_shape_value_and_identity_drift(defect):
    width = construction_material.OUTPUT_WIDTH
    values = np.zeros((2, width))
    ids = ["case-a", "case-b"]
    if defect == "width":
        values = values[:, :-1]
    elif defect == "nonfinite":
        values[0, 0] = np.inf
    elif defect == "duplicate":
        ids[1] = ids[0]
    else:
        ids.pop()
    with pytest.raises(challenge.MaterialMismatch):
        construction_material.output_predictions(values, ids)
