"""Structured compute errors.

Every failure states what failed, whether the provider operation ran, whether
billable resources may still exist, whether retrying the same call is safe, and
what to do next. Messages are built only from Carbon-authored text, typed
fields and HTTP status codes: provider response bodies and transport exception
text are never copied in, because either can echo request headers.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ComputeError", "Execution"]


class Execution(StrEnum):
    """Whether the failed operation reached the provider."""

    NOT_EXECUTED = "not_executed"
    EXECUTED = "executed"
    MAY_HAVE_EXECUTED = "may_have_executed"


class ComputeError(Exception):
    """A typed, credential-free compute failure."""

    def __init__(
        self,
        *,
        operation: str,
        failed: str,
        execution: Execution,
        resources_may_remain: bool,
        retry_safe: bool,
        next_action: str,
        http_status: int | None = None,
    ) -> None:
        self.operation = operation
        self.failed = failed
        self.execution = Execution(execution)
        self.resources_may_remain = bool(resources_may_remain)
        self.retry_safe = bool(retry_safe)
        self.next_action = next_action
        self.http_status = http_status
        super().__init__(self._message())

    def _message(self) -> str:
        status = "" if self.http_status is None else f" (HTTP {self.http_status})"
        return (
            f"{self.operation}: {self.failed}{status}; execution={self.execution}; "
            f"resources_may_remain={self.resources_may_remain}; "
            f"retry_safe={self.retry_safe}; next={self.next_action}"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "failed": self.failed,
            "execution": str(self.execution),
            "resources_may_remain": self.resources_may_remain,
            "retry_safe": self.retry_safe,
            "next_action": self.next_action,
            "http_status": self.http_status,
        }
