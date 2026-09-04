"""Executor-agnostic role invocation seam plus deterministic test/manual adapters."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .identity import digest_value
from .models import ControllerPhase, PauseRequested, Role, SandboxMode


@dataclass(frozen=True)
class RoleInvocation:
    role: Role
    sandbox: SandboxMode
    workspace: Path
    prompt: str
    output_schema: Path
    context_paths: tuple[str, ...]
    iteration: int
    fresh: bool = True


class Executor(Protocol):
    def executor_id(self) -> str: ...

    def profile_digest(self, role: Role) -> str: ...

    def execute(self, invocation: RoleInvocation) -> Mapping[str, Any]: ...


class ScriptedExecutor:
    """Deterministic response queues used for controller acceptance tests."""

    def __init__(
        self,
        responses: Mapping[
            Role,
            Sequence[Mapping[str, Any] | Callable[[RoleInvocation], Mapping[str, Any]]],
        ],
        *,
        hooks: Mapping[Role, Callable[[RoleInvocation], None]] | None = None,
        identity: str = "carbon-hoh-scripted-v1",
    ) -> None:
        self._responses = {
            role: deque(item if callable(item) else dict(item) for item in items)
            for role, items in responses.items()
        }
        self._hooks = dict(hooks or {})
        self._identity = identity
        self.invocations: list[RoleInvocation] = []

    def executor_id(self) -> str:
        return self._identity

    def profile_digest(self, role: Role) -> str:
        return digest_value(
            {
                "executor": self._identity,
                "role": role.value,
                "fresh_invocations": True,
                "schema_version": "1.0",
            }
        )

    def execute(self, invocation: RoleInvocation) -> Mapping[str, Any]:
        self.invocations.append(invocation)
        hook = self._hooks.get(invocation.role)
        if hook is not None:
            hook(invocation)
        queue = self._responses.get(invocation.role, deque())
        if not queue:
            raise PauseRequested(
                ControllerPhase.PAUSED_INFRA,
                f"no scripted response remains for {invocation.role.value}",
            )
        response = queue.popleft()
        return response(invocation) if callable(response) else response


class ManualExecutor:
    """Explicit pause adapter for externally supplied, human-reviewed packets."""

    def __init__(
        self,
        identity: str = "carbon-hoh-manual-v1",
        *,
        packet: Mapping[str, Any] | None = None,
    ) -> None:
        self._identity = identity
        self._packet = dict(packet) if packet is not None else None
        self._consumed = False

    def executor_id(self) -> str:
        return self._identity

    def profile_digest(self, role: Role) -> str:
        return digest_value(
            {
                "executor": self._identity,
                "role": role.value,
                "manual_packet_required": True,
                "schema_version": "1.0",
            }
        )

    def execute(self, invocation: RoleInvocation) -> Mapping[str, Any]:
        if self._packet is not None and not self._consumed:
            self._consumed = True
            return dict(self._packet)
        raise PauseRequested(
            ControllerPhase.PAUSED_HUMAN,
            f"manual {invocation.role.value} packet required for iteration "
            f"{invocation.iteration}",
        )
