"""Bounded in-process operational observability service."""

from __future__ import annotations

import threading

from .model import (
    BoundaryErrorEvent,
    BoundaryErrorSnapshot,
    CounterMetricSnapshot,
    DurationMetricSnapshot,
    DurationStage,
    MetricKind,
    ObservabilityEvent,
    ObservabilityResourceLimits,
    SubmissionEventSnapshot,
    _boundary_error_snapshot,
    _copy_resource_limits,
    _counter_metric_snapshot,
    _duration_metric_snapshot,
    _raise_integration_error,
    _raise_request_error,
    _raise_resource_error,
    _submission_event_snapshot,
)
from .providers import MetricSink, StructuredEventSink


class ObservabilityService:
    """Emit only the closed A11 events and metrics to injected sinks."""

    __slots__ = (
        "_active_call",
        "_capacity",
        "_event_sink",
        "_limits",
        "_metric_sink",
    )

    def __init__(
        self,
        event_sink: StructuredEventSink,
        metric_sink: MetricSink,
        resource_limits: ObservabilityResourceLimits,
    ) -> None:
        if (
            type(self) is not ObservabilityService
            or event_sink is None
            or metric_sink is None
        ):
            _raise_request_error()
        limits = _copy_resource_limits(resource_limits)
        self._event_sink = event_sink
        self._metric_sink = metric_sink
        self._limits = limits
        self._capacity = threading.BoundedSemaphore(limits.max_concurrent_calls)
        self._active_call = threading.local()

    def _admit(self) -> bool:
        try:
            active = self._active_call.active
        except AttributeError:
            active = False
        if active is True:
            return False
        if not self._capacity.acquire(blocking=False):
            return False
        self._active_call.active = True
        return True

    def _release(self) -> None:
        self._active_call.active = False
        self._capacity.release()

    def _emit_admitted(
        self,
        event: SubmissionEventSnapshot | BoundaryErrorSnapshot,
    ) -> None:
        failed = False
        try:
            method = self._event_sink.emit_event
            result = method(event)
            if result is not None:
                failed = True
        except Exception:  # noqa: BLE001 - exact ordinary sink failure boundary
            failed = True
        if failed:
            _raise_integration_error()

    def _increment_admitted(self, metric: CounterMetricSnapshot) -> None:
        failed = False
        try:
            method = self._metric_sink.increment_counter
            result = method(metric)
            if result is not None:
                failed = True
        except Exception:  # noqa: BLE001 - exact ordinary sink failure boundary
            failed = True
        if failed:
            _raise_integration_error()

    def _observe_admitted(self, metric: DurationMetricSnapshot) -> None:
        failed = False
        try:
            method = self._metric_sink.observe_duration
            result = method(metric)
            if result is not None:
                failed = True
        except Exception:  # noqa: BLE001 - exact ordinary sink failure boundary
            failed = True
        if failed:
            _raise_integration_error()

    def emit_event(self, event: ObservabilityEvent | BoundaryErrorEvent) -> None:
        """Synchronously emit one positively reconstructed closed event."""

        if type(event) is ObservabilityEvent:
            snapshot: SubmissionEventSnapshot | BoundaryErrorSnapshot = (
                _submission_event_snapshot(event)
            )
        elif type(event) is BoundaryErrorEvent:
            snapshot = _boundary_error_snapshot(event)
        else:
            _raise_request_error()
        if not self._admit():
            _raise_resource_error()
        try:
            self._emit_admitted(snapshot)
        finally:
            self._release()

    def increment_counter(self, metric: MetricKind) -> None:
        """Synchronously increment one closed counter by exactly one."""

        snapshot = _counter_metric_snapshot(metric)
        if not self._admit():
            _raise_resource_error()
        try:
            self._increment_admitted(snapshot)
        finally:
            self._release()

    def observe_duration(self, stage: DurationStage, duration_ns: int) -> None:
        """Synchronously observe caller-supplied nanoseconds for one stage."""

        snapshot = _duration_metric_snapshot(stage, duration_ns)
        if not self._admit():
            _raise_resource_error()
        try:
            self._observe_admitted(snapshot)
        finally:
            self._release()
