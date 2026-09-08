"""Deterministic synthetic fixture semantics with no runtime authority."""

from .physics import (
    FIXTURE_CURRICULUM_SURFACE_ID,
    FIXTURE_FEATURE_SURFACE_ID,
    FIXTURE_HELDOUT_OBSERVATIONS,
    FIXTURE_SAMPLING_SURFACE_ID,
    FIXTURE_TRAINING_OBSERVATIONS,
    FIXTURE_TRANSFER_OBSERVATIONS,
    FixtureModelConfiguration,
    construct_fixture_model,
    evaluate_fixture_reference,
)

__all__ = (
    "FIXTURE_CURRICULUM_SURFACE_ID",
    "FIXTURE_FEATURE_SURFACE_ID",
    "FIXTURE_HELDOUT_OBSERVATIONS",
    "FIXTURE_SAMPLING_SURFACE_ID",
    "FIXTURE_TRAINING_OBSERVATIONS",
    "FIXTURE_TRANSFER_OBSERVATIONS",
    "FixtureModelConfiguration",
    "construct_fixture_model",
    "evaluate_fixture_reference",
)
