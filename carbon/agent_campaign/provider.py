# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The provider-independent research-agent adapter contract.

These are **proposed Carbon-side operations**, not endpoints any vendor is
claimed to expose. A concrete adapter maps them onto a provider's documented
lifecycle controls, or refuses (`ProviderUnavailable`) when those controls are
not verified. The controller (`controller.py`) owns dispatch, spending,
stopping and evidence; an adapter only relays.

Everything a provider returns is untrusted data. Status, events and artifacts
are recorded and scanned; they never carry instructions the controller obeys.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol

SCHEMA = "carbon.agent-campaign.provider.v1"


class IntegrationMode(str, Enum):
    """The handoff's four integration modes, chosen from verified capability."""

    DIRECT_MCP = "direct_mcp"
    TOOL_ADAPTER = "documented_tool_adapter"
    ARTIFACT_HANDOFF = "repository_artifact_handoff"
    UNAVAILABLE = "unavailable"


class RunState(str, Enum):
    """A provider run's state as the provider reports it."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    #: The provider cannot say. The controller stops dispatch on it.
    UNKNOWN = "unknown"


TERMINAL = frozenset({RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED})


class ProviderError(RuntimeError):
    """A provider call failed in a way the controller must record."""


class ProviderTimeout(ProviderError):
    """The call's outcome is unknown: it may or may not have taken effect."""


class ProviderUnavailable(ProviderError):
    """The provider's controls are not verified; nothing was sent."""


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def money(value) -> Decimal:
    """A non-negative amount from a decimal string or int; never a float."""
    if type(value) is bool or type(value) not in (str, int, Decimal):
        raise ValueError("an amount is a decimal string, never a float")
    try:
        amount = Decimal(value)
    except ArithmeticError:
        raise ValueError("an amount is a decimal string") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError("an amount is finite and non-negative")
    return amount


def identifier(value, what="identifier") -> str:
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError(what + " is 1-128 characters of [A-Za-z0-9._:-]")
    return value


def digest_text(value, what="digest") -> str:
    if type(value) is not str or not _DIGEST.fullmatch(value):
        raise ValueError(what + " is sha256:<64 hex>")
    return value


@dataclass(frozen=True)
class Capabilities:
    """What an adapter can do, and whether each item is verified.

    `verified` is the adapter's own statement of evidence, not a vendor claim;
    a capability that is not verified is treated as absent.
    """

    provider: str
    mode: IntegrationMode
    verified: bool
    supports_idempotent_start: bool
    supports_cancel: bool
    reports_worker_termination: bool
    reports_usage: bool
    basis: str

    def __post_init__(self):
        identifier(self.provider, "provider")
        if type(self.mode) is not IntegrationMode:
            raise TypeError("exact IntegrationMode required")
        if self.mode is IntegrationMode.UNAVAILABLE and self.verified:
            raise ValueError("an unavailable provider verifies nothing")

    @property
    def dispatchable(self) -> bool:
        """Every control the controller needs is present and verified."""
        return (
            self.verified
            and self.mode is not IntegrationMode.UNAVAILABLE
            and self.supports_idempotent_start
            and self.supports_cancel
            and self.reports_worker_termination
            and self.reports_usage
        )


@dataclass(frozen=True)
class TaskSpec:
    """One task for the agent. References and digests only: no secret values,
    and no protected material (the controller checks the workspace role)."""

    campaign_id: str
    role: str
    workspace_id: str
    credential_ref: str
    profile_digest: str
    instructions_digest: str
    max_runtime_s: int

    def __post_init__(self):
        for name in ("campaign_id", "role", "workspace_id", "credential_ref"):
            identifier(getattr(self, name), name)
        digest_text(self.profile_digest, "profile_digest")
        digest_text(self.instructions_digest, "instructions_digest")
        if type(self.max_runtime_s) is not int or self.max_runtime_s <= 0:
            raise ValueError("max_runtime_s is a positive integer")


@dataclass(frozen=True)
class RunHandle:
    provider_run_id: str
    worker_ids: tuple[str, ...]

    def __post_init__(self):
        identifier(self.provider_run_id, "provider_run_id")
        if type(self.worker_ids) is not tuple:
            raise TypeError("worker_ids is a tuple")
        for worker in self.worker_ids:
            identifier(worker, "worker id")


@dataclass(frozen=True)
class RunStatus:
    state: RunState
    worker_ids: tuple[str, ...]
    #: True only when the provider confirms every worker has stopped; None
    #: when it cannot say. Never inferred from a terminal state.
    workers_terminated: bool | None

    def __post_init__(self):
        if type(self.state) is not RunState:
            raise TypeError("exact RunState required")
        if self.workers_terminated not in (True, False, None):
            raise TypeError("workers_terminated is True, False or None")


@dataclass(frozen=True)
class Usage:
    """Spend as the provider reports it. `known` False means the provider
    cannot state it; the controller then stops dispatch."""

    known: bool
    settled: Decimal | None
    pending: Decimal | None
    units: str

    def __post_init__(self):
        if self.known and (self.settled is None or self.pending is None):
            raise ValueError("known usage states settled and pending amounts")
        for amount in (self.settled, self.pending):
            if amount is not None:
                money(amount)


@dataclass(frozen=True)
class Artifact:
    """An exported file. `body` is untrusted bytes."""

    name: str
    body: bytes

    def __post_init__(self):
        identifier(self.name.replace("/", "_"), "artifact name")
        if type(self.body) is not bytes:
            raise TypeError("artifact body is bytes")

    @property
    def sha256(self) -> str:
        return "sha256:" + hashlib.sha256(self.body).hexdigest()


class ResearchAgentProvider(Protocol):
    """The proposed Carbon-side operations an adapter implements."""

    def capabilities(self) -> Capabilities: ...

    def start(self, spec: TaskSpec, idempotency_key: str) -> RunHandle: ...

    def find(self, idempotency_key: str) -> RunHandle | None: ...

    def status(self, provider_run_id: str) -> RunStatus: ...

    def events(self, provider_run_id: str, after: int) -> list[dict]: ...

    def artifacts(self, provider_run_id: str) -> list[Artifact]: ...

    def cancel(self, provider_run_id: str) -> None: ...

    def usage(self, provider_run_id: str) -> Usage: ...
