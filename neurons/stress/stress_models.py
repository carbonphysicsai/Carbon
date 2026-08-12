# neurons/stress/stress_models.py

"""
Core data models for Carbon's hidden stress test system.

Follows the design in docs/STRESS_TEST_DESIGN.md
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class StressSource(Enum):
    """Source of a stress test variant."""
    PROCEDURAL = "procedural"
    WELL = "well"
    ADVERSARIAL = "adversarial"   # Future use


@dataclass
class StressVariant:
    """
    A single stress test case within a StressTestSet.
    """
    variant_id: str
    source: StressSource
    parameters: Dict[str, Any]
    well_dataset: Optional[str] = None
    difficulty: float = 0.5          # 0.0 = easy, 1.0 = very hard
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not (0.0 <= self.difficulty <= 1.0):
            raise ValueError("difficulty must be between 0.0 and 1.0")


@dataclass
class StressTestSet:
    """
    Complete hidden stress test set for one challenge.
    This is what gets generated per challenge and stored validator-private.
    """
    challenge_id: str
    seed: int
    physics_class: str
    variants: List[StressVariant]
    difficulty_level: float
    total_variants: int
    generation_config: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.total_variants != len(self.variants):
            raise ValueError("total_variants must match len(variants)")
