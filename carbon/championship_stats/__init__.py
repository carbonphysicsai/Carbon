"""Pure, development-stage daily championship statistics.

The validator supplies registered policy, sealed paired cases and exact rebuilt
artifact identities. This package never loads cases or changes a live rule.
"""

from .core import (
    AlphaLedger,
    BoundedMixture,
    Contender,
    Evidence,
    PairedCase,
    PairedRound,
    confirm_noninferiority,
    confirmation_lower_bound,
    holm,
    select_winner,
)
from .rev5 import (
    BATTERY_REV5_TESTNET,
    Rev5Case,
    Rev5Contender,
    Rev5Outcome,
    Rev5Result,
    Rev5Rule,
    select_rev5_winner,
)

__all__ = [
    "BATTERY_REV5_TESTNET",
    "AlphaLedger",
    "BoundedMixture",
    "Contender",
    "Evidence",
    "PairedCase",
    "PairedRound",
    "Rev5Case",
    "Rev5Contender",
    "Rev5Outcome",
    "Rev5Result",
    "Rev5Rule",
    "confirm_noninferiority",
    "confirmation_lower_bound",
    "holm",
    "select_rev5_winner",
    "select_winner",
]
