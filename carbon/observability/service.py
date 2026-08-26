"""Bounded in-process operational observability service."""

from __future__ import annotations

import threading

from .model import (
    BoundaryErrorEvent,
    DurationStage,
    MetricKind,
    ObservabilityEvent,
    ObservabilityResourceLimits,
    _copy_boundary_error_event,
    _copy_counter_metric,
    _copy_duration_stage,
    _copy_observability_event,
    _copy_resource_limits,
    _raise_integration_error,
    _raise_request_error,
    _raise_resource_error,
    _require_duration_ns,
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

    def _emit_admitted(self, event: ObservabilityEvent | BoundaryErrorEvent) -> None:
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

    def _increment_admitted(self, metric: MetricKind) -> None:
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

    def _observe_admitted(self, stage: DurationStage, duration_ns: int) -> None:
        failed = False
        try:
            method = self._metric_sink.observe_duration
            result = method(stage, duration_ns)
            if result is not None:
                failed = True
        except Exception:  # noqa: BLE001 - exact ordinary sink failure boundary
            failed = True
        if failed:
            _raise_integration_error()

    def emit_event(self, event: ObservabilityEvent | BoundaryErrorEvent) -> None:
        """Synchronously emit one positively reconstructed closed event."""

        if type(event) is ObservabilityEvent:
            owned_event: ObservabilityEvent | BoundaryErrorEvent = (
                _copy_observability_event(event)
            )
        elif type(event) is BoundaryErrorEvent:
            owned_event = _copy_boundary_error_event(event)
        else:
            _raise_request_error()
        if not self._admit():
            _raise_resource_error()
        try:
            self._emit_admitted(owned_event)
        finally:
            self._release()

    def increment_counter(self, metric: MetricKind) -> None:
        """Synchronously increment one closed counter by exactly one."""

        owned_metric = _copy_counter_metric(metric)
        if not self._admit():
            _raise_resource_error()
        try:
            self._increment_admitted(owned_metric)
        finally:
            self._release()

    def observe_duration(self, stage: DurationStage, duration_ns: int) -> None:
        """Synchronously observe caller-supplied nanoseconds for one stage."""

        owned_stage = _copy_duration_stage(stage)
        owned_duration = _require_duration_ns(duration_ns)
        if not self._admit():
            _raise_resource_error()
        try:
            self._observe_admitted(owned_stage, owned_duration)
        finally:
            self._release()
