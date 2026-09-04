"""Closed nominal types for the bounded development controller."""

from __future__ import annotations

from enum import StrEnum

SCHEMA_VERSION = "1.0"
PACKET_TYPE_PLAN = "iteration_plan"
PACKET_TYPE_EVIDENCE = "iteration_evidence"
PACKET_TYPE_DEVELOPER = "developer_result"


class Role(StrEnum):
    PLANNER = "PLANNER"
    DEVELOPER = "DEVELOPER"
    TESTER = "TESTER"


class SandboxMode(StrEnum):
    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"


class RequirementStatus(StrEnum):
    UNTESTED = "UNTESTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    BLOCKED_HUMAN = "BLOCKED_HUMAN"
    BLOCKED_INFRA = "BLOCKED_INFRA"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ControllerPhase(StrEnum):
    PLANNING = "PLANNING"
    DEVELOPING = "DEVELOPING"
    TESTING = "TESTING"
    PAUSED_HUMAN = "PAUSED_HUMAN"
    PAUSED_INFRA = "PAUSED_INFRA"
    FINAL_CANDIDATE_READY = "FINAL_CANDIDATE_READY"


TERMINAL_PHASES = frozenset(
    {
        ControllerPhase.PAUSED_HUMAN,
        ControllerPhase.PAUSED_INFRA,
        ControllerPhase.FINAL_CANDIDATE_READY,
    }
)

ACCEPTED_EVIDENCE_KINDS = frozenset(
    {
        "COMMAND",
        "STATIC_ANALYSIS",
        "TEST_RESULT",
    }
)

FORBIDDEN_AUTHORITY_WORDS = frozenset(
    {
        "APPROVED_FOR_MERGE",
        "LIVE_AUTHORIZED",
        "MERGE_AUTHORIZED",
        "PRODUCTION_QUALIFIED",
        "SCIENTIFICALLY_QUALIFIED",
        "SECURITY_QUALIFIED",
    }
)


class HarnessError(RuntimeError):
    """Base error for a fail-closed harness operation."""


class PacketValidationError(HarnessError):
    """A role packet is malformed or exceeds its authority."""


class IdentityMismatch(HarnessError):
    """An authority, candidate, manifest, or profile identity drifted."""


class ScopeViolation(HarnessError):
    """A role requested or changed material outside its bounded scope."""


class ExecutorUnavailable(HarnessError):
    """The requested executor surface cannot be verified or invoked."""


class PauseRequested(HarnessError):
    """An executor intentionally requires human or infrastructure action."""

    def __init__(self, phase: ControllerPhase, reason: str) -> None:
        if phase not in {
            ControllerPhase.PAUSED_HUMAN,
            ControllerPhase.PAUSED_INFRA,
        }:
            raise ValueError("pause phase must be PAUSED_HUMAN or PAUSED_INFRA")
        super().__init__(reason)
        self.phase = phase
        self.reason = reason
