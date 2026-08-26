"""Structural sinks for bounded in-process operational observability."""

from __future__ import annotations

from typing import Protocol

from .model import (
    BoundaryErrorEvent,
    DurationStage,
    MetricKind,
    ObservabilityEvent,
)


class StructuredEventSink(Protocol):
    """Accept one exact immutable structured observability event."""

    def emit_event(
        self,
        event: ObservabilityEvent | BoundaryErrorEvent,
        /,
    ) -> None: ...


class MetricSink(Protocol):
    """Accept one counter increment or one caller-supplied duration."""

    def increment_counter(
        self,
        metric: MetricKind,
        /,
    ) -> None: ...

    def observe_duration(
        self,
        stage: DurationStage,
        duration_ns: int,
        /,
    ) -> None: ...
