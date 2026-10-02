# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Bounded process-local card store and miner-facing disclosure boundary.

This package provides no durable persistence, production authentication, LIVE
activation, or production-qualification claim.
"""

from .model import (
    CardAuthorizationError,
    CardConflictError,
    CardNotFoundError,
    CardProjectionError,
    CardRecordKey,
    CardRequestError,
    CardStoreError,
    CardWriteDisposition,
    EvaluationCard,
    EvaluationComponentScores,
    EvaluationGateResult,
    RequesterAuthorizationKey,
)
from .store import CardStore

__all__ = (
    "CardAuthorizationError",
    "CardConflictError",
    "CardNotFoundError",
    "CardProjectionError",
    "CardRecordKey",
    "CardRequestError",
    "CardStore",
    "CardStoreError",
    "CardWriteDisposition",
    "EvaluationCard",
    "EvaluationComponentScores",
    "EvaluationGateResult",
    "RequesterAuthorizationKey",
)
