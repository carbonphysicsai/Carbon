"""Exact, finite C-02 receipt value regressions without importing JAX."""

from __future__ import annotations

from pathlib import Path

import pytest

from carbon.reconstruction.model import (
    PredictionReceipt,
    ReconstructionFailure,
    ReconstructionReceipt,
    ReconstructionStatus,
)

_DIGEST = "sha256:" + "1" * 64


def _reconstruction(**changes: object) -> ReconstructionReceipt:
    values: dict[str, object] = {
        "artifact_path": Path("/tmp/c02-receipt-fixture"),
        "artifact_digest": _DIGEST,
        "execution_id": "fixture:1",
        "plan_digest": _DIGEST,
        "profile_digest": _DIGEST,
        "training_data_digest": _DIGEST,
        "randomness_digest": _DIGEST,
        "checkpoint_digest": _DIGEST,
        "status": ReconstructionStatus.COMPLETE,
        "completed_steps": 1,
        "compile_seconds": 0.0,
        "train_execution_seconds": 0.0,
    }
    values.update(changes)
    return ReconstructionReceipt(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
@pytest.mark.parametrize("field", ("compile_seconds", "train_execution_seconds"))
def test_reconstruction_receipt_rejects_nonfinite_timing(
    field: str, value: float
) -> None:
    with pytest.raises(ReconstructionFailure, match="rejected"):
        _reconstruction(**{field: value})


@pytest.mark.parametrize("value", (True, False, 1.0, "1"))
def test_reconstruction_receipt_does_not_coerce_counters(value: object) -> None:
    with pytest.raises(ReconstructionFailure, match="rejected"):
        _reconstruction(completed_steps=value)


@pytest.mark.parametrize(
    ("status", "steps"),
    (
        (ReconstructionStatus.COMPLETE, 0),
        (ReconstructionStatus.RECONCILIATION_REQUIRED, 1),
    ),
)
def test_reconstruction_receipt_rejects_impossible_status_step_pairs(
    status: ReconstructionStatus, steps: int
) -> None:
    with pytest.raises(ReconstructionFailure, match="rejected"):
        _reconstruction(status=status, completed_steps=steps)


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_prediction_receipt_rejects_nonfinite_timing(value: float) -> None:
    with pytest.raises(ReconstructionFailure, match="rejected"):
        PredictionReceipt(_DIGEST, _DIGEST, _DIGEST, 1, 1, 1, value)


@pytest.mark.parametrize("value", (True, False, 1.0, "1"))
def test_prediction_receipt_does_not_coerce_counters(value: object) -> None:
    with pytest.raises(ReconstructionFailure, match="rejected"):
        PredictionReceipt(_DIGEST, _DIGEST, _DIGEST, value, 1, 1, 0.0)  # type: ignore[arg-type]
