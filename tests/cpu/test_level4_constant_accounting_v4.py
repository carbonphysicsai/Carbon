"""Constant accounting v4 (B', owner pick; Validator
VALIDATOR_GRAPH_OPS_V8_RULINGS_20261025 section 3), served with allowlist v8.

The cap is the same 16 KiB. An integer constant is charged the bits its *actual range*
needs, a bool one bit, a fitted float four bytes a value: a small-range structure table
(exponents, connectivity, one-hot indices) costs what it holds, and the information a
graph can carry in constants is bounded as before. The range comes from the values, not
the declared dtype. Every earlier allowlist keeps accounting v3.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, validate

HERE = Path(allowlist_module.__file__).parent
V7 = allowlist_module.load(HERE / "allowlist_v7.json")
V8 = allowlist_module.load(HERE / "allowlist_v8.json")
CAP = 16 * 1024


def _doc(allowlist, *arrays):
    constants = [
        {"value": 1 + i, **graph.encode_array(np.asarray(a))}
        for i, a in enumerate(arrays)
    ]
    return {
        "schema": graph.SCHEMA,
        "allowlist": allowlist.version,
        "role": "forward",
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": [
                    {"value": 0, "name": "inputs/x", "dtype": "float32", "shape": [2]}
                ],
                "constants": constants,
                "nodes": [],
                "outputs": [0],
            }
        },
    }


def _info(*arrays):
    return graph.measure(_doc(V8, *arrays))["constant_info_bytes"]


def test_v8_is_measured_under_v4_and_every_earlier_version_under_v3():
    assert allowlist_module.accounting_for(V8)[0] == "level4-constant-accounting-v4"
    assert allowlist_module.accounting_for(V7)[0] == allowlist_module.CONSTANT_ACCOUNTING
    assert allowlist_module.accounting_for("level4-allowlist-v6")[1] == (
        allowlist_module.MEASURED_AS
    )
    assert allowlist_module.accounting_for(None)[1] == allowlist_module.MEASURED_AS


def test_bits_by_actual_range():
    assert _info(np.zeros(8, np.bool_)) == 1  # one bit a value
    assert _info(np.arange(256, dtype=np.int32) % 4) == 64  # 2 bits x 256
    assert _info(np.arange(1024, dtype=np.int64) % 64) == 768  # 6 bits x 1024
    assert _info(np.arange(256, dtype=np.int32)) == 256  # 8 bits x 256
    assert _info(np.full(100, 7, np.int32)) == 13  # one bit a value, never zero
    assert _info(np.arange(10, dtype=np.float32)) == 40  # fitted floats: 4 bytes
    assert _info(np.arange(10, dtype=np.float64)) == 40  # float64 is not charged double
    assert _info(np.zeros(0, np.int32)) == 0


def test_the_declared_dtype_does_not_set_the_price_the_values_do():
    narrow = np.arange(2000, dtype=np.int32) % 8  # int32 holding 3-bit values
    wide = narrow.astype(np.int64) * (2**28)  # int64 holding 31-bit values
    assert _info(narrow) == 750
    assert _info(wide) == 2000 * 31 // 8  # 31 bits a value, from the values themselves
    assert _info(wide) > 10 * _info(narrow)


def test_a_wide_range_integer_table_counts_at_its_full_width():
    """Quantised weights smuggled as integers cost what they carry: 4096 values spanning
    30 bits are 15360 bytes, and a few more refuse."""
    rng = np.random.default_rng(0)
    table = rng.integers(0, 2**30, size=4096).astype(np.int32)
    assert _info(table) == 4096 * 30 // 8
    assert validate.validate(_doc(V8, table), V8, role="forward")["status"] == "admitted"
    over = rng.integers(0, 2**30, size=4400).astype(np.int32)
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(_doc(V8, over), V8, role="forward")
    assert refused.value.code == "cap_exceeded" and "constant_bytes" in refused.value.where


def test_a_small_range_structure_table_fits_far_more_than_v3_allowed():
    """The miner's case: exponent or connectivity tables. 16 384 values in 0..255 fit
    under v8; under v3 (v7) only 4096 values of any dtype did."""
    table = np.random.default_rng(1).integers(0, 256, size=16 * 1024).astype(np.int32)
    assert _info(table) == CAP
    assert validate.validate(_doc(V8, table), V8, role="forward")["status"] == "admitted"
    bigger = np.append(table, 255).astype(np.int32)
    with pytest.raises(graph.GraphRefused):
        validate.validate(_doc(V8, bigger), V8, role="forward")
    # v7 is unchanged: 4096 values is its ceiling, whatever they are.
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(_doc(V7, table), V7, role="forward")
    assert refused.value.code == "cap_exceeded"


def test_fitted_floats_keep_their_four_bytes_a_value():
    floats = np.linspace(0, 1, 4096, dtype=np.float32)
    assert _info(floats) == CAP
    assert validate.validate(_doc(V8, floats), V8, role="forward")["status"] == "admitted"
    with pytest.raises(graph.GraphRefused):
        validate.validate(
            _doc(V8, np.linspace(0, 1, 4097, dtype=np.float32)), V8, role="forward"
        )


def test_integer_valued_floats_are_not_a_cheaper_way_in():
    """Disguising a table as float costs more, never less."""
    table = (np.arange(8192) % 4).astype(np.float32)
    assert _info(table) == 8192 * 4
    assert _info(table.astype(np.int32)) == 8192 * 2 // 8


def test_identical_copies_still_count_once():
    table = (np.arange(1000) % 16).astype(np.int32)
    assert _info(table, table.copy()) == _info(table)


def test_the_verdict_names_its_accounting():
    verdict = validate.validate(_doc(V8, np.arange(8, dtype=np.int32)), V8, role="forward")
    assert verdict["constant_accounting"] == "level4-constant-accounting-v4"
    verdict = validate.validate(_doc(V7, np.arange(8, dtype=np.int32)), V7, role="forward")
    assert verdict["constant_accounting"] == allowlist_module.CONSTANT_ACCOUNTING
