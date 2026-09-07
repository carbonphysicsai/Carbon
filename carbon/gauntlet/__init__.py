"""B-E4 fixture-engineering gauntlet with no qualification authority."""

from .harness import (
    AgentDriver,
    AgentSession,
    GauntletPreflightError,
    validate_experiment_matrix,
    validate_integrity_matrix,
)
from .model import *
from .shadow import HeldoutToyShadowCases

__all__ = (
    "AgentDriver",
    "AgentSession",
    "GauntletPreflightError",
    "HeldoutToyShadowCases",
    "validate_experiment_matrix",
    "validate_integrity_matrix",
)
