# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Disabled optional follow-up seam; burn-only requires no reserve state."""

from dataclasses import dataclass

from .core import RewardFailure


@dataclass(frozen=True)
class DisabledTreasury:
    """No enabling flag, destination, signer, deployment or liability erasure."""

    def new_allocation(self):
        return 0

    def enable(self):
        raise RewardFailure("OPTIONAL_TREASURY_NOT_IMPLEMENTED")
