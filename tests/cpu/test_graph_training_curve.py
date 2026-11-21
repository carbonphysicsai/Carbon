"""DATA D2: trainer v3 records each fit's training curve (the loss value every step already computes), bounded, on public
TRAIN only, without changing what it trains; a v2-trainer fit record keeps its bytes.

The bit-for-bit claim for the default path is `test_graph_trainer_v3.test_every_default_reproduces_the_v2_trainer_bit_for_bit`
(v2 takes `jax.grad`, v3 now `value_and_grad`: the members must stay identical).
"""

import json
import math

import pytest

from carbon.development_session import physical_graph_trainer_v3 as trainer3


def _member(curve, polish=None):
    return {"curve": curve, "polish_curve": polish}


def test_the_curve_keeps_every_step_up_to_the_point_cap_and_the_last_step():
    block = trainer3.curve_block([_member([float(i) for i in range(10)])])
    assert block["schema"] == trainer3.CURVE_SCHEMA
    assert block["stride"] == 1
    assert block["members"] == [[float(i) for i in range(10)]]
    assert block["polish"] == [None]
    long = [float(i) for i in range(1001)]
    block = trainer3.curve_block([_member(long)])
    stride = block["stride"]
    assert stride == math.ceil(1001 / trainer3.CURVE_POINTS)
    points = block["members"][0]
    assert points[0] == 0.0 and points[-1] == 1000.0  # the last step always kept
    assert len(points) <= trainer3.CURVE_POINTS + 1


def test_values_are_seven_significant_digits_and_a_non_finite_step_is_a_gap():
    block = trainer3.curve_block(
        [_member([1.23456789, float("nan"), float("inf"), 2.0])]
    )
    assert block["members"][0] == [1.234568, None, None, 2.0]
    json.dumps(block, allow_nan=False)  # the receipt is written with allow_nan=False


def test_the_polish_curve_rides_beside_the_main_curve():
    block = trainer3.curve_block([_member([3.0, 2.0], [1.0, 0.5, 0.25])])
    assert block["polish"] == [[1.0, 0.5, 0.25]]


def test_the_block_stays_within_its_byte_cap_however_many_members():
    members = [_member([1.0 / (i + 1) for i in range(512)]) for _ in range(40)]
    block = trainer3.curve_block(members)
    size = len(json.dumps(block, sort_keys=True, separators=(",", ":")))
    assert size <= trainer3.CURVE_BYTES_MAX
    assert len(block["members"]) == 40
    assert all(
        row[-1] == pytest.approx(1.0 / 512, rel=1e-6) for row in block["members"]
    )


def test_a_v3_fit_records_its_curve_and_a_v2_fit_record_has_no_curve_key(monkeypatch):
    pytest.importorskip("jax")
    pytest.importorskip("optax")
    import test_graph_trainer_v3 as v3_tests

    _model, fitted_v2, _ = v3_tests.fit({})
    assert "curve" not in fitted_v2
    monkeypatch.setitem(v3_tests.adapter.SPECS, v3_tests.KEY, v3_tests.v3_spec())
    model, fitted, _ = v3_tests.fit({})
    curve = fitted["curve"]
    assert curve["schema"] == trainer3.CURVE_SCHEMA
    assert len(curve["members"]) == len(model.settings["ensemble"])
    assert all(len(row) == 24 for row in curve["members"])  # 24 steps, stride 1
    assert all(v is not None and v >= 0 for row in curve["members"] for v in row)
    assert curve["polish"] == [None] * len(curve["members"])


def test_polish_and_microbatch_paths_record_too(monkeypatch):
    pytest.importorskip("jax")
    pytest.importorskip("optax")
    import test_graph_trainer_v3 as v3_tests

    monkeypatch.setitem(v3_tests.adapter.SPECS, v3_tests.KEY, v3_tests.v3_spec())
    _m, polished, _ = v3_tests.fit({"steps": 40, "polish_steps": 8})
    assert [len(row) for row in polished["curve"]["members"]] == [32]
    assert [len(row) for row in polished["curve"]["polish"]] == [8]
    _m, micro, _ = v3_tests.fit({"microbatches": 2, "batch_size": 4})
    assert [len(row) for row in micro["curve"]["members"]] == [24]
