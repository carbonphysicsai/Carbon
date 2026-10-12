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

__all__ = [
    "AlphaLedger",
    "BoundedMixture",
    "Contender",
    "Evidence",
    "PairedCase",
    "PairedRound",
    "confirm_noninferiority",
    "confirmation_lower_bound",
    "holm",
    "select_winner",
]
