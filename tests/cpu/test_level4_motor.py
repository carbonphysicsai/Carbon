"""Level 4 E6 (development only): a second Challenge through `carbon.level4`.

Motor's adapter (`carbon/motor/level4.py`) is the only Challenge-specific
code; the shared package is unchanged. Motor has no gradient-trained family:
its Level 0 kernel ridge prediction is lowered to a graph whose parameters
Carbon's own closed-form fit supplies.

Claims tested:

1. The graph path (submission, verify, G4 with motor's interface and a
   padded batch, Carbon's fit at G6, G7 through motor's practice exam
   unchanged) gives motor's native predictions to float64 rounding, every
   case's gate decision identical, and no non-finite case.
2. It is NOT bit-identical (numpy against XLA), as for battery's kNN; the
   bounds below are test bounds, not tolerances anyone chose.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module


def test_e6_motor_through_the_shared_gates():
    from carbon.motor import level4 as motor

    result = motor.graph_equivalence(allowlist_module.load(), max_bytes=1 << 26)
    assert result["status"] == "admitted"  # under the owner's caps
    assert result["batch"] == motor.BATCH
    assert result["case_states_identical"]
    assert result["nonfinite_cases"] == []
    assert result["max_abs_prediction_difference"] < 1e-8
    assert result["score_difference"] < 1e-9
    assert result["inference_cost"]["rule"] == allowlist_module.HUMAN_INPUT
