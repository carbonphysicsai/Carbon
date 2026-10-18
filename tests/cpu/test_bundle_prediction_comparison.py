"""Pure-data parity diagnostics; no construction or model run."""

import numpy as np
import pytest

from carbon.development_session.bundle_prediction_comparison import (
    compare_native_lowered_predictions,
)


def _identity() -> dict[str, str]:
    return {
        "recipe_digest": "sha256:" + "1" * 64,
        "state_digest": "sha256:" + "2" * 64,
        "probe_digest": "sha256:" + "3" * 64,
    }


def _compare(native, lowered, *, native_identity=None, lowered_identity=None):
    return compare_native_lowered_predictions(
        native=native,
        lowered=lowered,
        native_identity=_identity() if native_identity is None else native_identity,
        lowered_identity=(
            _identity() if lowered_identity is None else lowered_identity
        ),
    )


def test_exact_native_and_lowered_values_report_observation_only():
    values = np.array([[1.0, -2.0]], dtype=np.float32)
    result = _compare(values, values.copy())
    assert result["exact_equal"] is True
    assert result["mismatch_count"] == 0
    assert result["max_abs_delta"] == result["mean_abs_delta"] == 0.0
    assert "pass" not in result and "qualified" not in result


def test_lowering_discrepancy_is_visible_without_a_tolerance():
    native = np.array([[1.0, 2.0]], dtype=np.float32)
    lowered = np.array([[1.5, 2.0]], dtype=np.float32)
    result = _compare(native, lowered)
    assert result["exact_equal"] is False
    assert result["mismatch_count"] == 1
    assert result["max_abs_delta"] == 0.5
    assert result["mean_abs_delta"] == 0.25


@pytest.mark.parametrize("field", ["recipe_digest", "state_digest", "probe_digest"])
def test_identity_mismatch_refuses_comparison(field):
    altered = _identity()
    altered[field] = "sha256:" + "4" * 64
    with pytest.raises(ValueError, match="recipe, state or probe differs"):
        _compare(np.array([1.0]), np.array([1.0]), lowered_identity=altered)


@pytest.mark.parametrize(
    "native,lowered",
    [
        (np.array([1.0]), np.array([[1.0]])),
        (np.array([np.nan]), np.array([0.0])),
        (np.array([1.0 + 0j]), np.array([1.0 + 0j])),
        (np.array([], dtype=np.float64), np.array([], dtype=np.float64)),
    ],
)
def test_noncomparable_predictions_refuse(native, lowered):
    with pytest.raises(ValueError):
        _compare(native, lowered)


def test_integer_delta_retains_single_unit_at_large_magnitude():
    native = np.array([2**60], dtype=np.int64)
    lowered = np.array([2**60 + 1], dtype=np.int64)
    result = _compare(native, lowered)
    assert result["max_abs_delta"] == 1.0
