"""Constant accounting v4 under allowlist v8 (owner 2026-10-25: B' counts integer
and bool constants by the bits their range needs; "check for other places we're
over counting bits": every constant is charged what it really stores, never more
than four bytes a value; the 16 KiB cap for fitted values is unchanged).

Claims tested:
- floats are charged their real item size (float16 and bfloat16 two bytes,
  float32 four, float64 four as in v3), complex numbers their two components,
  bool one bit, an integer the bits its actual range needs, read from the values
  (a wide-range int64 table counts at its full width);
- identical copies count once, and the cap total is the same 16 KiB;
- allowlist v8 is measured this way and v7 (accounting v3) is not;
- the lowering tool's pre-check follows the version's accounting.
"""

import numpy as np
import pytest

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph

CAP = allowlist_module.CAPS["constant_bytes"]
V7 = allowlist_module.load(allowlist_module.V7_PATH)
V8 = allowlist_module.load(allowlist_module.V8_PATH)


def _constant(array, value=0):
    return {"value": value, **graph.encode_array(np.asarray(array))}


def _bytes(array):
    return graph.constant_info_bytes([_constant(array)])


@pytest.mark.parametrize(
    "dtype,per_value",
    [
        ("float16", 2),
        ("bfloat16", 2),
        ("float32", 4),
        ("float64", 4),
        ("complex64", 8),
        ("complex128", 8),
    ],
)
def test_a_float_is_charged_its_real_size_never_more_than_four_bytes(dtype, per_value):
    import ml_dtypes

    np_dtype = ml_dtypes.bfloat16 if dtype == "bfloat16" else np.dtype(dtype)
    array = np.arange(1, 101, dtype=np.float32).astype(np_dtype)
    assert _bytes(array) == 100 * per_value


def test_integers_are_charged_the_bits_their_range_needs():
    assert _bytes(np.zeros(1000, np.int32)) == 125  # a constant: one bit each
    assert _bytes(np.arange(256, dtype=np.int32)) == 256  # 0..255: 8 bits
    assert _bytes(np.arange(8, dtype=np.int64).repeat(512)) == 4096 * 3 // 8
    wide = np.array([0, 1 << 40] * 50, dtype=np.int64)  # 41 bits at full width
    assert _bytes(wide) == -(-100 * 41 // 8)
    assert _bytes(np.zeros(0, np.int32)) == 0


def test_bool_is_one_bit_and_identical_copies_count_once():
    assert _bytes(np.ones(8192, bool)) == 1024
    twice = [_constant(np.arange(256, dtype=np.int32), 0)] * 2
    assert graph.constant_info_bytes(twice) == 256


def test_the_cap_total_is_unchanged_and_holds_what_each_dtype_really_stores():
    holds = {
        np.float16: CAP // 2,
        np.float32: CAP // 4,
        np.float64: CAP // 4,
    }
    for dtype, count in holds.items():
        assert _bytes(np.arange(count).astype(dtype)) <= CAP
        assert _bytes(np.arange(count + 1).astype(dtype)) > CAP
    # 16384 values in [0, 255]: the information of 4096 float32 values.
    assert _bytes(np.arange(CAP).astype(np.int32) % 256) == CAP
    assert _bytes(np.arange(CAP + 1).astype(np.int32) % 256) > CAP


def test_v8_is_measured_by_information_and_v7_is_not():
    constants = [_constant(np.arange(16384, dtype=np.int32) % 256)]
    doc_measure = {
        "constant_value_bytes": graph.VALUE_BYTES
        * graph.unique_constant_values(constants),
        "constant_info_bytes": graph.constant_info_bytes(constants),
    }
    assert allowlist_module.accounting_for(V8)[0] == "level4-constant-accounting-v4"
    assert allowlist_module.accounting_for(V7)[0] == "level4-constant-accounting-v3"
    _, measured_v8 = allowlist_module.accounting_for(V8)
    _, measured_v7 = allowlist_module.accounting_for(V7)
    caps = {"constant_bytes": allowlist_module.caps_for(V8)["constant_bytes"]}
    assert (
        allowlist_module.check_caps(doc_measure, caps, measured_v8)["constant_bytes"]
        == "pass"
    )
    assert (
        allowlist_module.check_caps(doc_measure, caps, measured_v7)["constant_bytes"]
        == "refuse"
    )


def test_the_lowering_precheck_measures_like_the_validator():
    from carbon.level4.tooling import lower_torch

    class Builder:
        def __init__(self, allowlist, constants):
            self.allowlist = allowlist
            self.constants = constants

    held = [_constant(np.arange(1000, dtype=np.int32) % 256)]
    # 4,000 more indices below 256 are 4,000 bytes: fine under v4, 16,000 under v3.
    assert not lower_torch._constants_over(Builder(V8, held), 4000, bits=8)
    assert lower_torch._constants_over(Builder(V7, held), 4000, bits=8)
    assert lower_torch._constants_over(Builder(V8, held), 20000, bits=8)
