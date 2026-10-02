# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Bounded A7 submission identity, lifecycle, and isolated fee ledger.

This package is fixture-capable and process-local.  It provides no durable
store, production payment claim, production execution path, or emission
authority.
"""

from .model import (
    AdmissionKind,
    AttemptEvent,
    AttemptEventKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    FeeEvent,
    FeeEventKind,
    FeeOperationContext,
    FeeOperationKey,
    FeePolicyKey,
    FixtureExecutionEnvelope,
    FixtureSubmissionPolicy,
    InitialRunStartResult,
    ProductionExecutionEnvelope,
    RequesterIdentity,
    StartDisposition,
    StrategyHash,
    SubmissionAdmissionError,
    SubmissionAuthorizationError,
    SubmissionConflictError,
    SubmissionId,
    SubmissionIntegrationError,
    SubmissionNotFoundError,
    SubmissionRequestError,
    SubmissionResourceError,
    SubmissionResourceLimits,
    SubmissionResourcePolicyError,
    SubmissionState,
    SubmissionStateError,
    SubmissionStatusView,
    SubmissionStoreError,
)
from .service import SubmissionService

__all__ = (
    "AdmissionKind",
    "AttemptEvent",
    "AttemptEventKind",
    "ExecutionAttemptHandle",
    "ExecutionEnvironmentPin",
    "FeeEvent",
    "FeeEventKind",
    "FeeOperationContext",
    "FeeOperationKey",
    "FeePolicyKey",
    "FixtureExecutionEnvelope",
    "FixtureSubmissionPolicy",
    "InitialRunStartResult",
    "ProductionExecutionEnvelope",
    "RequesterIdentity",
    "StartDisposition",
    "StrategyHash",
    "SubmissionAdmissionError",
    "SubmissionAuthorizationError",
    "SubmissionConflictError",
    "SubmissionId",
    "SubmissionIntegrationError",
    "SubmissionNotFoundError",
    "SubmissionRequestError",
    "SubmissionResourceError",
    "SubmissionResourceLimits",
    "SubmissionResourcePolicyError",
    "SubmissionService",
    "SubmissionState",
    "SubmissionStateError",
    "SubmissionStatusView",
    "SubmissionStoreError",
)
