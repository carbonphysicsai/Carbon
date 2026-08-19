"""Hydrogen Emission Mechanics.

Implements a clean 75/25 model following Bittensor best practices:
- 75% Breakthrough Bounties (event-driven, high-value)
- 25% Decaying Top-2 Stipend (via standard Yuma Consensus)

Everything is calculated per challenge.
"""

from .mechanics import (
    calculate_breakthrough_bounty,
    calculate_top2_stipend,
    update_leaderboard,
    is_breakthrough,
)

__all__ = [
    "calculate_breakthrough_bounty",
    "calculate_top2_stipend",
    "update_leaderboard",
    "is_breakthrough",
]
