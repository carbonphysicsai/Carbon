"""F08's exam inputs: one bracket geometry on the registered lattice.

The names and order are the public interface's
(`carbon.challenge_kit.f08_public`) and the structures registration's
(`carbon.challenge_pipeline.structures_readiness.FIELDS`); a test pins them
equal. The decision limit is the registered worst dynamic compliance.
"""

from __future__ import annotations

INPUTS = (
    "length_mm",
    "width_mm",
    "thickness_mm",
    "rib_height_mm",
    "rib_thickness_mm",
    "relief_length_mm",
)
LIMIT_MM_PER_N = 0.15
