"""Structural sinks for bounded in-process operational observability."""

from __future__ import annotations

from typing import Protocol

from .model import (
    BoundaryErrorSnapshot,
    CounterMetricSnapshot,
    DurationMetricSnapshot,
    SubmissionEventSnapshot,
)


class StructuredEventSink(Protocol):
    """Accept one exact immutable structured observability event."""

    def emit_event(
        self,
        event: SubmissionEventSnapshot | BoundaryErrorSnapshot,
        /,
    ) -> None: ...


class MetricSink(Protocol):
    """Accept one counter increment or one caller-supplied duration."""

    def increment_counter(
        self,
        metric: CounterMetricSnapshot,
        /,
    ) -> None: ...

    def observe_duration(
        self,
        metric: DurationMetricSnapshot,
        /,
    ) -> None: ...
