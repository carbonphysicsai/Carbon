"""Deterministic synthetic fixture semantics with no runtime authority."""

from .physics import (
    FIXTURE_HELDOUT_OBSERVATIONS,
    FIXTURE_TRAINING_OBSERVATIONS,
    construct_fixture_model,
    evaluate_fixture_reference,
)

__all__ = (
    "FIXTURE_HELDOUT_OBSERVATIONS",
    "FIXTURE_TRAINING_OBSERVATIONS",
    "construct_fixture_model",
    "evaluate_fixture_reference",
)
