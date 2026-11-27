"""Treasury seam: keeps DisabledTreasury for burn-only paths and exports PinnedTreasurySink."""

from dataclasses import dataclass

from .core import RewardFailure
from .waterfall import PinnedTreasurySink

__all__ = ["DisabledTreasury", "PinnedTreasurySink"]


@dataclass(frozen=True)
class DisabledTreasury:
    """No enabling flag, destination, signer, deployment or liability erasure."""

    def new_allocation(self):
        return 0

    def enable(self):
        raise RewardFailure("OPTIONAL_TREASURY_NOT_IMPLEMENTED")
