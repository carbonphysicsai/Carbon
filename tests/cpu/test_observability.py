"""CPU acceptance tests for bounded Wave-A operational observability."""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import inspect
import os
import pickle
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import get_type_hints

import pytest

from carbon import observability
from carbon.fees import SubmissionId, SubmissionState
from carbon.leaderboard import (
    LeaderboardError,
    LeaderboardIntegrationError,
    LeaderboardRequestError,
    LeaderboardResourceError,
    LeaderboardUnavailableError,
)
from carbon.mcp import (
    McpChallengeUnavailableError,
    McpIntegrationError,
    McpQueryBudgetError,
    McpRequestError,
    McpResourceError,
    McpSubmissionUnavailableError,
    McpToolUnavailableError,
)
from carbon.observability import (
    BoundaryErrorEvent,
    BoundaryErrorKind,
    BoundaryErrorSnapshot,
    CounterMetricSnapshot,
    DurationMetricSnapshot,
    DurationStage,
    EventKind,
    MetricKind,
    MetricSink,
    ObservabilityError,
    ObservabilityEvent,
    ObservabilityIntegrationError,
    ObservabilityRequestError,
    ObservabilityResourceError,
    ObservabilityResourceLimits,
    ObservabilityService,
    StructuredEventSink,
    SubmissionEventSnapshot,
)
from carbon.scoring import ScoreStatus

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY_ROOT = REPOSITORY_ROOT / "carbon" / "observability"
U64_MAX = (1 << 64) - 1
SUBMISSION_ID_TEXT = "00000000-0000-4000-8000-000000000001"
PUBLIC_EXPORTS = (
    "EventKind",
    "MetricKind",
    "DurationStage",
    "BoundaryErrorKind",
    "ObservabilityEvent",
    "BoundaryErrorEvent",
    "ObservabilityResourceLimits",
    "SubmissionEventSnapshot",
    "BoundaryErrorSnapshot",
    "CounterMetricSnapshot",
    "DurationMetricSnapshot",
    "StructuredEventSink",
    "MetricSink",
    "ObservabilityService",
    "ObservabilityError",
    "ObservabilityRequestError",
    "ObservabilityResourceError",
    "ObservabilityIntegrationError",
)
ENUM_CONTRACTS = (
    (
        EventKind,
        (
            ("SUBMIT", "SUBMIT"),
            ("SCORE", "SCORE"),
            ("REJECT", "REJECT"),
            ("FAILED_STRATEGY", "FAILED_STRATEGY"),
            ("FAILED_INFRA", "FAILED_INFRA"),
        ),
    ),
    (
        MetricKind,
        (
            ("SUBMIT_COUNT", "SUBMIT_COUNT"),
            ("SCORE_COUNT", "SCORE_COUNT"),
            ("REJECT_COUNT", "REJECT_COUNT"),
            ("FAILED_INFRA_COUNT", "FAILED_INFRA_COUNT"),
            ("STAGE_DURATION_NS", "STAGE_DURATION_NS"),
        ),
    ),
    (DurationStage, (("SUBMIT", "SUBMIT"), ("SCORE", "SCORE"))),
    (
        BoundaryErrorKind,
        (
            ("MCP_REQUEST", "mcp.request.invalid"),
            ("MCP_RESOURCE", "mcp.resource_limit_exceeded"),
            ("MCP_TOOL_UNAVAILABLE", "mcp.tool_unavailable"),
            ("MCP_CHALLENGE_UNAVAILABLE", "mcp.challenge_unavailable"),
            ("MCP_SUBMISSION_UNAVAILABLE", "mcp.submission_unavailable"),
            ("MCP_QUERY_BUDGET", "mcp.query_budget_exceeded"),
            ("MCP_INTEGRATION", "mcp.integration_failure"),
            ("LEADERBOARD_REQUEST", "leaderboard.request.invalid"),
            ("LEADERBOARD_RESOURCE", "leaderboard.resource.exhausted"),
            ("LEADERBOARD_UNAVAILABLE", "leaderboard.fixture.unavailable"),
            ("LEADERBOARD_INTEGRATION", "leaderboard.integration.failed"),
        ),
    ),
)
VALID_EVENT_ROWS = (
    (EventKind.SUBMIT, SubmissionState.RECEIVED, None),
    (EventKind.SCORE, SubmissionState.SCORED, ScoreStatus.SCORED),
    (
        EventKind.SCORE,
        SubmissionState.SCORED,
        ScoreStatus.MANDATORY_GATE_FAILED,
    ),
    (EventKind.REJECT, SubmissionState.REJECTED, None),
    (EventKind.FAILED_STRATEGY, SubmissionState.FAILED_STRATEGY, None),
    (EventKind.FAILED_INFRA, SubmissionState.FAILED_INFRA, None),
)
VALID_EVENT_ROW_SET = frozenset(VALID_EVENT_ROWS)
VALID_SNAPSHOT_EVENT_ROWS = (
    ("SUBMIT", "RECEIVED", None),
    ("SCORE", "SCORED", "SCORED"),
    ("SCORE", "SCORED", "MANDATORY_GATE_FAILED"),
    ("REJECT", "REJECTED", None),
    ("FAILED_STRATEGY", "FAILED_STRATEGY", None),
    ("FAILED_INFRA", "FAILED_INFRA", None),
)
ALL_EVENT_ROWS = tuple(
    (kind, state, status)
    for kind in EventKind
    for state in SubmissionState
    for status in (None, *tuple(ScoreStatus))
)
INCREMENTABLE_METRICS = (
    MetricKind.SUBMIT_COUNT,
    MetricKind.SCORE_COUNT,
    MetricKind.REJECT_COUNT,
    MetricKind.FAILED_INFRA_COUNT,
)
ERROR_CONTRACTS = (
    (
        ObservabilityRequestError,
        "observability.request.invalid",
        "Observability request is invalid.",
    ),
    (
        ObservabilityResourceError,
        "observability.resource.exhausted",
        "Observability resource limit was exceeded.",
    ),
    (
        ObservabilityIntegrationError,
        "observability.integration.failed",
        "Observability sink failed.",
    ),
)
OWNER_ERROR_KINDS = {
    McpRequestError: BoundaryErrorKind.MCP_REQUEST,
    McpResourceError: BoundaryErrorKind.MCP_RESOURCE,
    McpToolUnavailableError: BoundaryErrorKind.MCP_TOOL_UNAVAILABLE,
    McpChallengeUnavailableError: BoundaryErrorKind.MCP_CHALLENGE_UNAVAILABLE,
    McpSubmissionUnavailableError: BoundaryErrorKind.MCP_SUBMISSION_UNAVAILABLE,
    McpQueryBudgetError: BoundaryErrorKind.MCP_QUERY_BUDGET,
    McpIntegrationError: BoundaryErrorKind.MCP_INTEGRATION,
    LeaderboardRequestError: BoundaryErrorKind.LEADERBOARD_REQUEST,
    LeaderboardResourceError: BoundaryErrorKind.LEADERBOARD_RESOURCE,
    LeaderboardUnavailableError: BoundaryErrorKind.LEADERBOARD_UNAVAILABLE,
    LeaderboardIntegrationError: BoundaryErrorKind.LEADERBOARD_INTEGRATION,
}
OWNER_ERROR_MESSAGES = {
    McpRequestError: "MCP request is invalid.",
    McpResourceError: "MCP resource limit was exceeded.",
    McpToolUnavailableError: "MCP tool is unavailable.",
    McpChallengeUnavailableError: "Challenge is unavailable.",
    McpSubmissionUnavailableError: "Submission is unavailable.",
    McpQueryBudgetError: "MCP query budget was exceeded.",
    McpIntegrationError: "MCP integration failed.",
    LeaderboardRequestError: "Leaderboard request is invalid.",
    LeaderboardResourceError: "Leaderboard resource limit was exceeded.",
    LeaderboardUnavailableError: "Fixture leaderboard is unavailable.",
    LeaderboardIntegrationError: "Leaderboard provider response is invalid.",
}


class _IntegerSubclass(int):
    pass


class _StringSubclass(str):
    pass


class _Hostile:
    def __repr__(self) -> str:
        raise AssertionError("hostile repr was invoked")

    def __str__(self) -> str:
        raise AssertionError("hostile str was invoked")

    def __eq__(self, other: object) -> bool:
        del other
        raise AssertionError("hostile equality was invoked")

    def __hash__(self) -> int:
        raise AssertionError("hostile hashing was invoked")

    def __iter__(self):  # type: ignore[no-untyped-def]
        raise AssertionError("hostile iteration was invoked")


class _DescriptorLookalike:
    @property
    def kind(self) -> object:
        raise AssertionError("lookalike descriptor was invoked")


class _RecordingEventSink:
    """Test-local structural sink; it deliberately subclasses no Protocol."""

    def __init__(self) -> None:
        self.events: list[SubmissionEventSnapshot | BoundaryErrorSnapshot] = []

    def emit_event(
        self,
        event: SubmissionEventSnapshot | BoundaryErrorSnapshot,
        /,
    ) -> None:
        self.events.append(event)


class _RecordingMetricSink:
    """Test-local structural sink; it deliberately subclasses no Protocol."""

    def __init__(self) -> None:
        self.counters: list[CounterMetricSnapshot] = []
        self.durations: list[DurationMetricSnapshot] = []

    def increment_counter(self, metric: CounterMetricSnapshot, /) -> None:
        self.counters.append(metric)

    def observe_duration(self, metric: DurationMetricSnapshot, /) -> None:
        self.durations.append(metric)


def _submission_id() -> SubmissionId:
    return SubmissionId(SUBMISSION_ID_TEXT)


def _event(
    kind: EventKind = EventKind.SUBMIT,
    state: SubmissionState = SubmissionState.RECEIVED,
    status: ScoreStatus | None = None,
    submission_id: SubmissionId | None = None,
) -> ObservabilityEvent:
    return ObservabilityEvent(
        kind,
        _submission_id() if submission_id is None else submission_id,
        state,
        status,
    )


def _service(
    event_sink: object | None = None,
    metric_sink: object | None = None,
    *,
    capacity: int = 1,
) -> tuple[ObservabilityService, object, object]:
    selected_event_sink = _RecordingEventSink() if event_sink is None else event_sink
    selected_metric_sink = (
        _RecordingMetricSink() if metric_sink is None else metric_sink
    )
    service = ObservabilityService(
        selected_event_sink,
        selected_metric_sink,
        ObservabilityResourceLimits(capacity),
    )
    return service, selected_event_sink, selected_metric_sink


def _forge_enum(enum_type: type[Enum], member: Enum) -> Enum:
    forged = str.__new__(enum_type, member.value)
    object.__setattr__(forged, "_name_", member.name)
    object.__setattr__(forged, "_value_", member.value)
    return forged


def _forge_value(value_type: type[object], **fields: object) -> object:
    value = object.__new__(value_type)
    for name, item in fields.items():
        object.__setattr__(value, name, item)
    return value


def _map_owner_error(error: Exception) -> BoundaryErrorEvent | None:
    """Test-local trusted composition; production A11 owns no such mapping."""

    error_type = type(error)
    error_kind = OWNER_ERROR_KINDS.get(error_type)
    expected_message = OWNER_ERROR_MESSAGES.get(error_type)
    if error_kind is None or expected_message is None:
        return None
    try:
        args = BaseException.__getattribute__(error, "args")
        payload = BaseException.__getattribute__(error, "__dict__")
        cause = BaseException.__getattribute__(error, "__cause__")
        context = BaseException.__getattribute__(error, "__context__")
    except Exception:  # noqa: BLE001 - test-local exact owner validation
        return None
    if (
        type(args) is not tuple
        or args != (expected_message,)
        or type(payload) is not dict
        or payload
        or cause is not None
        or context is not None
    ):
        return None
    return BoundaryErrorEvent(error_kind)


def _assert_fixed_integration_error(error: ObservabilityIntegrationError) -> None:
    assert type(error) is ObservabilityIntegrationError
    assert error.code == "observability.integration.failed"
    assert str(error) == "Observability sink failed."
    assert error.args == ("Observability sink failed.",)
    assert error.__cause__ is None
    assert error.__context__ is None


def _assert_dataclass_apis_are_blocked(
    value: object,
    *,
    forbidden_text: str | None = None,
) -> None:
    """Prove stdlib dataclass traversal cannot return or echo this value."""

    assert dataclasses.is_dataclass(value) is False
    assert dataclasses.is_dataclass(type(value)) is False
    for operation in (
        dataclasses.asdict,
        dataclasses.astuple,
        dataclasses.replace,
    ):
        sentinel = object()
        result: object = sentinel
        with pytest.raises(TypeError) as raised:
            result = operation(value)  # type: ignore[arg-type]
        if forbidden_text is not None:
            assert forbidden_text not in str(raised.value)
            assert forbidden_text not in repr(raised.value)
            assert forbidden_text not in raised.value.args
        assert result is sentinel


def test_exact_package_files_exports_and_root_namespace() -> None:
    assert tuple(path.name for path in sorted(OBSERVABILITY_ROOT.glob("*.py"))) == (
        "__init__.py",
        "model.py",
        "providers.py",
        "service.py",
    )
    assert observability.__all__ == PUBLIC_EXPORTS
    assert (
        tuple(name for name in vars(observability) if not name.startswith("_"))
        == PUBLIC_EXPORTS
    )
    assert tuple(getattr(observability, name).__name__ for name in PUBLIC_EXPORTS) == (
        PUBLIC_EXPORTS
    )
    for owner_name in ("SubmissionId", "SubmissionState", "ScoreStatus"):
        assert owner_name not in vars(observability)


def test_public_vocabulary_adds_no_second_owner_or_deferred_authority() -> None:
    enum_types = tuple(
        value
        for value in vars(observability).values()
        if inspect.isclass(value)
        and issubclass(value, Enum)
        and value.__module__.startswith("carbon.observability")
    )
    assert enum_types == (EventKind, MetricKind, DurationStage, BoundaryErrorKind)
    for omitted in (
        "DUPLICATE",
        "PACK_NOT_READY",
        "PUBLISHED",
        "CANCELLED",
        "RETRYABLE_INFRA",
        "REFERENCE_FAILED",
        "GENERATOR_FAILED",
        "RECONSTRUCTION_FAILED",
        "FAILED_STRATEGY_COUNT",
        "BOUNDARY_ERROR_COUNT",
    ):
        assert not hasattr(EventKind, omitted)
        assert not hasattr(MetricKind, omitted)
        assert not hasattr(DurationStage, omitted)

    public_text = " ".join(PUBLIC_EXPORTS).lower()
    for authority in (
        "audit",
        "challengehealth",
        "evidence",
        "frontier",
        "lifecycle",
        "productqualification",
        "provenance",
        "receipt",
        "settlement",
        "treasury",
        "weight",
        "emission",
    ):
        assert authority not in public_text


@pytest.mark.parametrize(("enum_type", "members"), ENUM_CONTRACTS)
def test_enums_have_exact_direct_string_contract(
    enum_type: type[Enum], members: tuple[tuple[str, str], ...]
) -> None:
    assert enum_type.__bases__ == (str, Enum)
    assert tuple(enum_type.__members__) == tuple(name for name, _ in members)
    assert tuple((member.name, member.value) for member in enum_type) == members
    assert len(enum_type.__members__) == len(tuple(enum_type))
    for name, value in members:
        member = enum_type.__members__[name]
        assert type(member.value) is str
        assert enum_type(value) is member
    with pytest.raises(ValueError):
        enum_type("unratified")


def test_models_have_exact_fields_and_are_frozen_slotted_safe_values() -> None:
    values_and_contracts = (
        (
            _event(),
            ("kind", "submission_id", "submission_state", "score_status"),
            "ObservabilityEvent(<private>)",
        ),
        (
            BoundaryErrorEvent(BoundaryErrorKind.MCP_REQUEST),
            ("error_kind",),
            "BoundaryErrorEvent(<private>)",
        ),
        (
            ObservabilityResourceLimits(1),
            ("max_concurrent_calls",),
            "ObservabilityResourceLimits(<private>)",
        ),
        (
            SubmissionEventSnapshot(
                "SUBMIT",
                SUBMISSION_ID_TEXT,
                "RECEIVED",
                None,
            ),
            ("kind", "submission_id", "submission_state", "score_status"),
            "SubmissionEventSnapshot(<private>)",
        ),
        (
            BoundaryErrorSnapshot("mcp.request.invalid"),
            ("error_code",),
            "BoundaryErrorSnapshot(<private>)",
        ),
        (
            CounterMetricSnapshot("SUBMIT_COUNT"),
            ("metric_name",),
            "CounterMetricSnapshot(<private>)",
        ),
        (
            DurationMetricSnapshot("SUBMIT", 0),
            ("stage", "duration_ns"),
            "DurationMetricSnapshot(<private>)",
        ),
    )
    for value, expected_fields, expected_repr in values_and_contracts:
        value_type = type(value)
        assert tuple(value_type.__slots__) == expected_fields
        assert tuple(value_type.__annotations__) == expected_fields
        signature = inspect.signature(value_type)
        assert tuple(signature.parameters) == expected_fields
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            and parameter.default is inspect.Parameter.empty
            for parameter in signature.parameters.values()
        )
        assert {name for name in dir(value) if not name.startswith("_")} == set(
            expected_fields
        )
        assert not hasattr(value_type, "__dataclass_fields__")
        assert not hasattr(value_type, "__dataclass_params__")
        assert not hasattr(value, "__dict__")
        assert repr(value) == expected_repr

        original_values = tuple(
            object.__getattribute__(value, name) for name in expected_fields
        )
        for name in expected_fields:
            with pytest.raises(AttributeError):
                setattr(value, name, None)
            with pytest.raises(AttributeError):
                delattr(value, name)
        with pytest.raises(AttributeError):
            value.extra_public_field = None  # type: ignore[attr-defined]
        assert (
            tuple(object.__getattribute__(value, name) for name in expected_fields)
            == original_values
        )

    assert SUBMISSION_ID_TEXT not in repr(values_and_contracts[0][0])
    assert "submission_id" not in repr(values_and_contracts[1][0]).lower()
    assert "message" not in repr(values_and_contracts[1][0]).lower()


def test_manual_nominals_reject_reinitialization_and_partial_initialization() -> None:
    event = _event()
    boundary = BoundaryErrorEvent(BoundaryErrorKind.MCP_REQUEST)
    limits = ObservabilityResourceLimits(1)
    event_values = tuple(
        object.__getattribute__(event, name) for name in type(event).__slots__
    )
    boundary_value = object.__getattribute__(boundary, "error_kind")
    limits_value = object.__getattribute__(limits, "max_concurrent_calls")

    reinitializations: tuple[
        tuple[Callable[[], None], object, tuple[object, ...]], ...
    ] = (
        (
            lambda: ObservabilityEvent.__init__(
                event,
                EventKind.REJECT,
                SubmissionId("12345678-1234-4234-9234-123456789abc"),
                SubmissionState.REJECTED,
                None,
            ),
            event,
            event_values,
        ),
        (
            lambda: BoundaryErrorEvent.__init__(
                boundary,
                BoundaryErrorKind.LEADERBOARD_INTEGRATION,
            ),
            boundary,
            (boundary_value,),
        ),
        (
            lambda: ObservabilityResourceLimits.__init__(limits, 2),
            limits,
            (limits_value,),
        ),
    )
    for operation, value, expected_values in reinitializations:
        with pytest.raises(ObservabilityRequestError) as raised:
            operation()
        assert raised.value.__cause__ is None
        assert raised.value.__context__ is None
        assert (
            tuple(
                object.__getattribute__(value, name) for name in type(value).__slots__
            )
            == expected_values
        )

    partial = object.__new__(ObservabilityEvent)
    object.__setattr__(partial, "score_status", None)
    with pytest.raises(ObservabilityRequestError) as raised:
        ObservabilityEvent.__init__(
            partial,
            EventKind.SUBMIT,
            _submission_id(),
            SubmissionState.RECEIVED,
            None,
        )
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert not hasattr(partial, "kind")
    assert not hasattr(partial, "submission_id")
    assert not hasattr(partial, "submission_state")
    assert object.__getattribute__(partial, "score_status") is None


def test_values_reject_generic_traversal_copy_and_serialization_paths() -> None:
    values_and_forbidden_text = (
        (_event(), SUBMISSION_ID_TEXT),
        (BoundaryErrorEvent(BoundaryErrorKind.LEADERBOARD_INTEGRATION), None),
        (ObservabilityResourceLimits(U64_MAX), None),
        (
            SubmissionEventSnapshot(
                "SUBMIT",
                SUBMISSION_ID_TEXT,
                "RECEIVED",
                None,
            ),
            SUBMISSION_ID_TEXT,
        ),
        (BoundaryErrorSnapshot("leaderboard.integration.failed"), None),
        (CounterMetricSnapshot("FAILED_INFRA_COUNT"), None),
        (DurationMetricSnapshot("SCORE", U64_MAX), None),
    )
    for value, forbidden_text in values_and_forbidden_text:
        _assert_dataclass_apis_are_blocked(
            value,
            forbidden_text=forbidden_text,
        )
        with pytest.raises(TypeError):
            copy.copy(value)
        with pytest.raises(TypeError):
            copy.deepcopy(value)
        with pytest.raises(TypeError):
            pickle.dumps(value)


@pytest.mark.parametrize(
    ("kind", "submission_state", "score_status"),
    VALID_SNAPSHOT_EVENT_ROWS,
)
def test_submission_snapshots_support_every_exact_direct_constructor_row(
    kind: str,
    submission_state: str,
    score_status: str | None,
) -> None:
    snapshot = SubmissionEventSnapshot(
        kind,
        SUBMISSION_ID_TEXT,
        submission_state,
        score_status,
    )
    assert (
        snapshot.kind,
        snapshot.submission_id,
        snapshot.submission_state,
        snapshot.score_status,
    ) == (kind, SUBMISSION_ID_TEXT, submission_state, score_status)
    assert all(
        value is None or type(value) in (str, int)
        for value in (
            snapshot.kind,
            snapshot.submission_id,
            snapshot.submission_state,
            snapshot.score_status,
        )
    )


def test_snapshot_direct_constructors_are_closed_and_exact() -> None:
    boundary_literals = tuple(value for _, value in ENUM_CONTRACTS[3][1])
    for literal in boundary_literals:
        snapshot = BoundaryErrorSnapshot(literal)
        assert type(snapshot.error_code) is str
        assert snapshot.error_code == literal

    for literal in (
        "SUBMIT_COUNT",
        "SCORE_COUNT",
        "REJECT_COUNT",
        "FAILED_INFRA_COUNT",
    ):
        snapshot = CounterMetricSnapshot(literal)
        assert type(snapshot.metric_name) is str
        assert snapshot.metric_name == literal

    for stage in ("SUBMIT", "SCORE"):
        for duration_ns in (0, 1, U64_MAX):
            snapshot = DurationMetricSnapshot(stage, duration_ns)
            assert type(snapshot.stage) is str
            assert type(snapshot.duration_ns) is int
            assert (snapshot.stage, snapshot.duration_ns) == (stage, duration_ns)


def test_submission_snapshot_matrix_and_constructor_inputs_fail_closed() -> None:
    valid = frozenset(VALID_SNAPSHOT_EVENT_ROWS)
    for kind in (
        "SUBMIT",
        "SCORE",
        "REJECT",
        "FAILED_STRATEGY",
        "FAILED_INFRA",
        "UNRATIFIED",
    ):
        for state in (
            "RECEIVED",
            "SCORED",
            "REJECTED",
            "FAILED_STRATEGY",
            "FAILED_INFRA",
            "CANCELLED",
        ):
            for status in (None, "SCORED", "MANDATORY_GATE_FAILED", "PACK_NOT_READY"):
                if (kind, state, status) in valid:
                    continue
                with pytest.raises(ObservabilityRequestError):
                    SubmissionEventSnapshot(
                        kind,
                        SUBMISSION_ID_TEXT,
                        state,
                        status,
                    )

    invalid_calls: tuple[Callable[[], object], ...] = (
        lambda: SubmissionEventSnapshot(  # type: ignore[arg-type]
            EventKind.SUBMIT,
            SUBMISSION_ID_TEXT,
            "RECEIVED",
            None,
        ),
        lambda: SubmissionEventSnapshot(
            _StringSubclass("SUBMIT"),
            SUBMISSION_ID_TEXT,
            "RECEIVED",
            None,
        ),
        lambda: SubmissionEventSnapshot(
            "SUBMIT",
            _StringSubclass(SUBMISSION_ID_TEXT),
            "RECEIVED",
            None,
        ),
        lambda: SubmissionEventSnapshot(
            "SUBMIT",
            "12345678-1234-4234-9234-123456789ABC",
            "RECEIVED",
            None,
        ),
        lambda: SubmissionEventSnapshot(
            "SUBMIT",
            "00000000-0000-1000-8000-000000000001",
            "RECEIVED",
            None,
        ),
        lambda: SubmissionEventSnapshot("SUBMIT", "invalid", "RECEIVED", None),
        lambda: BoundaryErrorSnapshot(_StringSubclass("mcp.request.invalid")),
        lambda: BoundaryErrorSnapshot("unratified"),
        lambda: CounterMetricSnapshot(_StringSubclass("SUBMIT_COUNT")),
        lambda: CounterMetricSnapshot("STAGE_DURATION_NS"),
        lambda: DurationMetricSnapshot(_StringSubclass("SUBMIT"), 0),
        lambda: DurationMetricSnapshot("SUBMIT", False),
        lambda: DurationMetricSnapshot("SUBMIT", _IntegerSubclass(1)),
        lambda: DurationMetricSnapshot("SUBMIT", -1),
        lambda: DurationMetricSnapshot("SUBMIT", U64_MAX + 1),
    )
    for operation in invalid_calls:
        with pytest.raises(ObservabilityRequestError):
            operation()

    with pytest.raises(TypeError):
        BoundaryErrorSnapshot()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        CounterMetricSnapshot("SUBMIT_COUNT", "extra")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        DurationMetricSnapshot(stage="SUBMIT", duration_ns=0, extra=True)  # type: ignore[call-arg]


def test_snapshots_reject_reentry_partial_and_alternate_initialization() -> None:
    submission = SubmissionEventSnapshot(
        "SUBMIT",
        SUBMISSION_ID_TEXT,
        "RECEIVED",
        None,
    )
    boundary = BoundaryErrorSnapshot("mcp.request.invalid")
    counter = CounterMetricSnapshot("SUBMIT_COUNT")
    duration = DurationMetricSnapshot("SUBMIT", 0)
    snapshots_and_reentry: tuple[tuple[object, Callable[[], None]], ...] = (
        (
            submission,
            lambda: SubmissionEventSnapshot.__init__(
                submission,
                "REJECT",
                SUBMISSION_ID_TEXT,
                "REJECTED",
                None,
            ),
        ),
        (
            boundary,
            lambda: BoundaryErrorSnapshot.__init__(
                boundary,
                "leaderboard.integration.failed",
            ),
        ),
        (
            counter,
            lambda: CounterMetricSnapshot.__init__(
                counter,
                "SCORE_COUNT",
            ),
        ),
        (
            duration,
            lambda: DurationMetricSnapshot.__init__(
                duration,
                "SCORE",
                1,
            ),
        ),
    )
    for _, operation in snapshots_and_reentry:
        with pytest.raises(ObservabilityRequestError):
            operation()

    alternate = object.__new__(BoundaryErrorSnapshot)
    with pytest.raises(ObservabilityRequestError):
        BoundaryErrorSnapshot.__init__(alternate, "mcp.request.invalid")

    partial = DurationMetricSnapshot.__new__(DurationMetricSnapshot, "SUBMIT", 0)
    object.__setattr__(partial, "duration_ns", 0)
    with pytest.raises(ObservabilityRequestError):
        DurationMetricSnapshot.__init__(partial, "SUBMIT", 0)
    object.__delattr__(partial, "duration_ns")
    with pytest.raises(ObservabilityRequestError):
        DurationMetricSnapshot.__init__(partial, "SUBMIT", 0)


def test_failed_snapshot_initialization_permanently_rejects_reentry() -> None:
    cases: tuple[
        tuple[type[object], tuple[object, ...], tuple[object, ...], str], ...
    ] = (
        (
            SubmissionEventSnapshot,
            ("SUBMIT", SUBMISSION_ID_TEXT, "RECEIVED", None),
            ("INVALID", SUBMISSION_ID_TEXT, "RECEIVED", None),
            "kind",
        ),
        (
            BoundaryErrorSnapshot,
            ("mcp.request.invalid",),
            ("invalid",),
            "error_code",
        ),
        (
            CounterMetricSnapshot,
            ("SUBMIT_COUNT",),
            ("INVALID",),
            "metric_name",
        ),
        (
            DurationMetricSnapshot,
            ("SUBMIT", 0),
            ("INVALID_STAGE", 0),
            "stage",
        ),
    )
    for snapshot_type, valid_args, invalid_args, first_field in cases:
        snapshot = snapshot_type.__new__(snapshot_type, *valid_args)
        with pytest.raises(ObservabilityRequestError):
            snapshot_type.__init__(snapshot, *invalid_args)
        with pytest.raises(AttributeError):
            object.__getattribute__(snapshot, first_field)
        with pytest.raises(ObservabilityRequestError):
            snapshot_type.__init__(snapshot, *valid_args)


def test_service_rejects_all_snapshot_classes_as_request_values() -> None:
    snapshots = (
        SubmissionEventSnapshot(
            "SUBMIT",
            SUBMISSION_ID_TEXT,
            "RECEIVED",
            None,
        ),
        BoundaryErrorSnapshot("mcp.request.invalid"),
        CounterMetricSnapshot("SUBMIT_COUNT"),
        DurationMetricSnapshot("SUBMIT", 0),
    )
    service, event_sink, metric_sink = _service()
    for snapshot in snapshots:
        with pytest.raises(ObservabilityRequestError):
            service.emit_event(snapshot)  # type: ignore[arg-type]
        with pytest.raises(ObservabilityRequestError):
            service.increment_counter(snapshot)  # type: ignore[arg-type]
        with pytest.raises(ObservabilityRequestError):
            service.observe_duration(snapshot, 0)  # type: ignore[arg-type]
    assert isinstance(event_sink, _RecordingEventSink)
    assert isinstance(metric_sink, _RecordingMetricSink)
    assert event_sink.events == []
    assert metric_sink.counters == [] and metric_sink.durations == []


@pytest.mark.parametrize(("error_type", "code", "message"), ERROR_CONTRACTS)
def test_errors_have_exact_fixed_immutable_nonserializable_payloads(
    error_type: type[ObservabilityError], code: str, message: str
) -> None:
    error = error_type()
    assert error_type.__bases__ == (ObservabilityError,)
    assert type(error) is error_type
    assert error.code == code
    assert error.message == message
    assert str(error) == message
    assert error.args == (message,)
    assert not hasattr(error, "__dict__")
    with pytest.raises(TypeError):
        error_type("private diagnostic")  # type: ignore[call-arg]
    for name, value in (
        ("code", "changed"),
        ("message", "changed"),
        ("args", ("changed",)),
        ("payload", _Hostile()),
    ):
        with pytest.raises(AttributeError):
            setattr(error, name, value)
    with pytest.raises(TypeError):
        copy.copy(error)
    with pytest.raises(TypeError):
        copy.deepcopy(error)
    with pytest.raises(TypeError):
        pickle.dumps(error)

    try:
        raise error
    except error_type as raised:
        assert raised.__traceback__ is not None
        assert raised.__cause__ is None
        assert raised.__context__ is None


def test_error_base_and_concrete_hierarchy_are_exact() -> None:
    assert ObservabilityError.__bases__ == (Exception,)
    exception_types = {
        value
        for value in vars(observability).values()
        if inspect.isclass(value)
        and issubclass(value, Exception)
        and value.__module__.startswith("carbon.observability")
    }
    assert exception_types == {
        ObservabilityError,
        ObservabilityRequestError,
        ObservabilityResourceError,
        ObservabilityIntegrationError,
    }


@pytest.mark.parametrize(("kind", "state", "status"), ALL_EVENT_ROWS)
def test_submission_event_matrix_is_exhaustive(
    kind: EventKind, state: SubmissionState, status: ScoreStatus | None
) -> None:
    values = (kind, state, status)
    if values in VALID_EVENT_ROW_SET:
        event = _event(kind, state, status)
        assert (event.kind, event.submission_state, event.score_status) == values
        return
    with pytest.raises(ObservabilityRequestError):
        _event(kind, state, status)


@pytest.mark.parametrize(
    "invalid_id",
    (
        None,
        SUBMISSION_ID_TEXT,
        _Hostile(),
        _forge_value(SubmissionId, value="not-a-canonical-uuid-v4"),
    ),
)
def test_submission_event_rejects_missing_wrong_and_malformed_ids(
    invalid_id: object,
) -> None:
    with pytest.raises(ObservabilityRequestError):
        ObservabilityEvent(
            EventKind.SUBMIT,
            invalid_id,  # type: ignore[arg-type]
            SubmissionState.RECEIVED,
            None,
        )


def test_all_constructible_nominals_and_service_reject_subclasses() -> None:
    class SubmissionIdSubclass(SubmissionId):
        pass

    class EventSubclass(ObservabilityEvent):
        __slots__ = ()

    class BoundarySubclass(BoundaryErrorEvent):
        __slots__ = ()

    class LimitsSubclass(ObservabilityResourceLimits):
        __slots__ = ()

    class SubmissionSnapshotSubclass(SubmissionEventSnapshot):
        __slots__ = ()

    class BoundarySnapshotSubclass(BoundaryErrorSnapshot):
        __slots__ = ()

    class CounterSnapshotSubclass(CounterMetricSnapshot):
        __slots__ = ()

    class DurationSnapshotSubclass(DurationMetricSnapshot):
        __slots__ = ()

    class ServiceSubclass(ObservabilityService):
        __slots__ = ()

    subclass_id = SubmissionIdSubclass(SUBMISSION_ID_TEXT)
    with pytest.raises(ObservabilityRequestError):
        _event(submission_id=subclass_id)
    with pytest.raises(ObservabilityRequestError):
        EventSubclass(
            EventKind.SUBMIT,
            _submission_id(),
            SubmissionState.RECEIVED,
            None,
        )
    with pytest.raises(ObservabilityRequestError):
        BoundarySubclass(BoundaryErrorKind.MCP_REQUEST)
    with pytest.raises(ObservabilityRequestError):
        LimitsSubclass(1)
    with pytest.raises(ObservabilityRequestError):
        SubmissionSnapshotSubclass(
            "SUBMIT",
            SUBMISSION_ID_TEXT,
            "RECEIVED",
            None,
        )
    with pytest.raises(ObservabilityRequestError):
        BoundarySnapshotSubclass("mcp.request.invalid")
    with pytest.raises(ObservabilityRequestError):
        CounterSnapshotSubclass("SUBMIT_COUNT")
    with pytest.raises(ObservabilityRequestError):
        DurationSnapshotSubclass("SUBMIT", 0)
    with pytest.raises(ObservabilityRequestError):
        ServiceSubclass(
            _RecordingEventSink(),
            _RecordingMetricSink(),
            ObservabilityResourceLimits(1),
        )

    forged = _forge_value(
        EventSubclass,
        kind=EventKind.SUBMIT,
        submission_id=_submission_id(),
        submission_state=SubmissionState.RECEIVED,
        score_status=None,
    )
    service, event_sink, _ = _service()
    with pytest.raises(ObservabilityRequestError):
        service.emit_event(forged)  # type: ignore[arg-type]
    assert isinstance(event_sink, _RecordingEventSink)
    assert event_sink.events == []


@pytest.mark.parametrize(
    ("field_name", "forged"),
    (
        ("kind", _forge_enum(EventKind, EventKind.SUBMIT)),
        ("submission_state", _forge_enum(SubmissionState, SubmissionState.RECEIVED)),
        ("score_status", _forge_enum(ScoreStatus, ScoreStatus.SCORED)),
    ),
)
def test_event_rejects_forged_exact_enum_instances(
    field_name: str, forged: object
) -> None:
    values: dict[str, object] = {
        "kind": EventKind.SUBMIT,
        "submission_id": _submission_id(),
        "submission_state": SubmissionState.RECEIVED,
        "score_status": None,
    }
    values[field_name] = forged
    if field_name == "score_status":
        values["kind"] = EventKind.SCORE
        values["submission_state"] = SubmissionState.SCORED
    with pytest.raises(ObservabilityRequestError):
        ObservabilityEvent(**values)  # type: ignore[arg-type]


def test_unbound_uuid_is_shape_valid_but_carries_no_provenance() -> None:
    unbound = SubmissionId("12345678-1234-4234-9234-123456789abc")
    event = ObservabilityEvent(
        EventKind.SUBMIT,
        unbound,
        SubmissionState.RECEIVED,
        None,
    )
    assert event.submission_id.value == unbound.value
    assert event.submission_id is not unbound
    field_names = tuple(type(event).__annotations__)
    assert field_names == (
        "kind",
        "submission_id",
        "submission_state",
        "score_status",
    )
    assert not any(
        token in field_name
        for field_name in field_names
        for token in (
            "authenticated",
            "evidence",
            "exists",
            "provenance",
            "receipt",
            "record",
            "transition",
        )
    )


def test_event_construction_and_service_make_fresh_owned_copies() -> None:
    caller_id = _submission_id()
    caller_event = _event(submission_id=caller_id)
    service, sink, _ = _service()
    assert service.emit_event(caller_event) is None
    assert isinstance(sink, _RecordingEventSink)
    retained = sink.events[0]
    assert type(retained) is SubmissionEventSnapshot
    assert retained is not caller_event
    assert caller_event.submission_id is not caller_id
    assert retained.submission_id == SUBMISSION_ID_TEXT
    assert type(retained.submission_id) is str

    object.__setattr__(caller_event, "kind", EventKind.REJECT)
    object.__setattr__(caller_event.submission_id, "value", "tampered")
    assert retained.kind == "SUBMIT"
    assert retained.submission_id == SUBMISSION_ID_TEXT


@pytest.mark.parametrize(
    ("request_row", "snapshot_row"),
    tuple(zip(VALID_EVENT_ROWS, VALID_SNAPSHOT_EVENT_ROWS, strict=True)),
)
def test_every_valid_event_request_maps_to_one_exact_fresh_snapshot(
    request_row: tuple[EventKind, SubmissionState, ScoreStatus | None],
    snapshot_row: tuple[str, str, str | None],
) -> None:
    service, sink, _ = _service()
    request = _event(*request_row)
    assert service.emit_event(request) is None
    assert service.emit_event(request) is None
    assert isinstance(sink, _RecordingEventSink)
    first, second = sink.events
    assert type(first) is SubmissionEventSnapshot
    assert type(second) is SubmissionEventSnapshot
    assert first is not second
    expected_kind, expected_state, expected_status = snapshot_row
    assert (
        first.kind,
        first.submission_id,
        first.submission_state,
        first.score_status,
    ) == (expected_kind, SUBMISSION_ID_TEXT, expected_state, expected_status)
    assert all(
        item is None or type(item) in (str, int)
        for item in (
            first.kind,
            first.submission_id,
            first.submission_state,
            first.score_status,
        )
    )


def test_enum_canary_attributes_never_cross_the_snapshot_boundary() -> None:
    members = (
        EventKind.SCORE,
        SubmissionState.SCORED,
        ScoreStatus.SCORED,
        BoundaryErrorKind.MCP_REQUEST,
        MetricKind.SUBMIT_COUNT,
        DurationStage.SUBMIT,
    )
    canaries = tuple(_Hostile() for _ in members)
    original_identity = tuple(
        (
            object.__getattribute__(member, "_name_"),
            object.__getattribute__(member, "_value_"),
        )
        for member in members
    )
    try:
        for member, canary in zip(members, canaries, strict=True):
            object.__setattr__(member, "a11_canary", canary)
        service, event_sink, metric_sink = _service()
        assert (
            service.emit_event(
                _event(EventKind.SCORE, SubmissionState.SCORED, ScoreStatus.SCORED)
            )
            is None
        )
        assert (
            service.emit_event(BoundaryErrorEvent(BoundaryErrorKind.MCP_REQUEST))
            is None
        )
        assert service.increment_counter(MetricKind.SUBMIT_COUNT) is None
        assert service.observe_duration(DurationStage.SUBMIT, 1) is None
    finally:
        for member in members:
            object.__delattr__(member, "a11_canary")

    assert isinstance(event_sink, _RecordingEventSink)
    assert isinstance(metric_sink, _RecordingMetricSink)
    snapshots = (
        *event_sink.events,
        *metric_sink.counters,
        *metric_sink.durations,
    )
    assert len({id(snapshot) for snapshot in snapshots}) == len(snapshots)
    assert all(not hasattr(snapshot, "a11_canary") for snapshot in snapshots)
    assert (
        tuple(
            (
                object.__getattribute__(member, "_name_"),
                object.__getattribute__(member, "_value_"),
            )
            for member in members
        )
        == original_identity
    )


def test_boundary_event_is_exact_closed_one_field_value() -> None:
    event = BoundaryErrorEvent(BoundaryErrorKind.MCP_QUERY_BUDGET)
    assert event.error_kind is BoundaryErrorKind.MCP_QUERY_BUDGET
    assert tuple(type(event).__annotations__) == ("error_kind",)
    for prohibited in (
        "cause",
        "challenge",
        "context",
        "cursor",
        "draw",
        "exception",
        "message",
        "payload",
        "provider",
        "requester",
        "seed",
        "submission_id",
        "traceback",
    ):
        assert not hasattr(event, prohibited)

    with pytest.raises(ObservabilityRequestError):
        BoundaryErrorEvent(_forge_enum(BoundaryErrorKind, event.error_kind))  # type: ignore[arg-type]
    for invalid in (None, event.error_kind.value, _Hostile(), {"error_kind": "x"}):
        with pytest.raises(ObservabilityRequestError):
            BoundaryErrorEvent(invalid)  # type: ignore[arg-type]


@pytest.mark.parametrize(("owner_error_type", "expected"), OWNER_ERROR_KINDS.items())
def test_test_local_owner_error_mapping_is_exact(
    owner_error_type: type[Exception], expected: BoundaryErrorKind
) -> None:
    event = _map_owner_error(owner_error_type())
    assert type(event) is BoundaryErrorEvent
    assert event.error_kind is expected
    service, sink, _ = _service()
    assert service.emit_event(event) is None
    assert isinstance(sink, _RecordingEventSink)
    assert len(sink.events) == 1
    snapshot = sink.events[0]
    assert type(snapshot) is BoundaryErrorSnapshot
    assert snapshot.error_code == expected.value
    assert type(snapshot.error_code) is str


def test_test_local_owner_mapping_rejects_raw_base_subclass_and_lookalike_errors() -> (
    None
):
    class ProviderError(RuntimeError):
        pass

    class McpRequestSubclass(McpRequestError):
        pass

    class LeaderboardRequestSubclass(LeaderboardRequestError):
        pass

    class CodeLookalike(RuntimeError):
        @property
        def code(self) -> str:
            raise AssertionError("arbitrary code inspection was attempted")

    unknowns = (
        ProviderError("raw private provider failure"),
        LeaderboardError(),
        McpRequestSubclass(),
        LeaderboardRequestSubclass(),
        CodeLookalike("mcp.request.invalid"),
        RuntimeError("reference/generator/reconstruction/retry"),
    )
    assert all(_map_owner_error(error) is None for error in unknowns)

    service, sink, _ = _service()
    with pytest.raises(ObservabilityRequestError):
        service.emit_event(unknowns[0])  # type: ignore[arg-type]
    assert isinstance(sink, _RecordingEventSink)
    assert sink.events == []


def test_test_local_owner_mapping_rejects_exact_classes_with_payloads() -> None:
    changed_args = McpRequestError()
    BaseException.__setattr__(changed_args, "args", ("private diagnostic",))
    payload = LeaderboardIntegrationError()
    BaseException.__getattribute__(payload, "__dict__")["private"] = _Hostile()
    chained = McpIntegrationError()
    BaseException.__setattr__(
        chained,
        "__cause__",
        RuntimeError("private provider cause"),
    )

    assert type(changed_args) is McpRequestError
    assert type(payload) is LeaderboardIntegrationError
    assert type(chained) is McpIntegrationError
    assert _map_owner_error(changed_args) is None
    assert _map_owner_error(payload) is None
    assert _map_owner_error(chained) is None


def test_closed_boundary_event_does_not_authenticate_an_owner_error() -> None:
    event = BoundaryErrorEvent(BoundaryErrorKind.LEADERBOARD_UNAVAILABLE)
    assert event.error_kind is BoundaryErrorKind.LEADERBOARD_UNAVAILABLE
    assert not any(
        hasattr(event, name)
        for name in ("owner_error", "occurred", "authenticated", "provider")
    )


@pytest.mark.parametrize("metric", INCREMENTABLE_METRICS)
def test_exact_four_counters_increment_once(metric: MetricKind) -> None:
    service, _, sink = _service()
    assert service.increment_counter(metric) is None
    assert isinstance(sink, _RecordingMetricSink)
    assert len(sink.counters) == 1
    assert type(sink.counters[0]) is CounterMetricSnapshot
    assert sink.counters[0].metric_name == metric.value


@pytest.mark.parametrize(
    "metric",
    (
        MetricKind.STAGE_DURATION_NS,
        None,
        "SUBMIT_COUNT",
        _Hostile(),
        _forge_enum(MetricKind, MetricKind.SUBMIT_COUNT),
    ),
)
def test_counter_rejects_duration_dynamic_and_forged_metrics(metric: object) -> None:
    service, _, sink = _service()
    with pytest.raises(ObservabilityRequestError):
        service.increment_counter(metric)  # type: ignore[arg-type]
    assert isinstance(sink, _RecordingMetricSink)
    assert sink.counters == []


@pytest.mark.parametrize("stage", tuple(DurationStage))
@pytest.mark.parametrize("duration_ns", (0, 1, U64_MAX))
def test_duration_accepts_exact_stages_and_u64_bounds(
    stage: DurationStage, duration_ns: int
) -> None:
    service, _, sink = _service()
    assert service.observe_duration(stage, duration_ns) is None
    assert isinstance(sink, _RecordingMetricSink)
    assert len(sink.durations) == 1
    assert type(sink.durations[0]) is DurationMetricSnapshot
    assert sink.durations[0].stage == stage.value
    assert sink.durations[0].duration_ns == duration_ns


@pytest.mark.parametrize(
    ("stage", "duration_ns"),
    (
        (None, 0),
        ("SUBMIT", 0),
        (_Hostile(), 0),
        (_forge_enum(DurationStage, DurationStage.SUBMIT), 0),
        (DurationStage.SUBMIT, None),
        (DurationStage.SUBMIT, False),
        (DurationStage.SUBMIT, -1),
        (DurationStage.SUBMIT, U64_MAX + 1),
        (DurationStage.SUBMIT, 1.0),
        (DurationStage.SUBMIT, _IntegerSubclass(1)),
        (DurationStage.SUBMIT, _Hostile()),
    ),
)
def test_duration_rejects_wrong_stage_and_non_exact_u64(
    stage: object, duration_ns: object
) -> None:
    service, _, sink = _service()
    with pytest.raises(ObservabilityRequestError):
        service.observe_duration(  # type: ignore[arg-type]
            stage,
            duration_ns,
        )
    assert isinstance(sink, _RecordingMetricSink)
    assert sink.durations == []


def test_service_constructor_and_public_operations_are_exact() -> None:
    signature = inspect.signature(ObservabilityService)
    assert tuple(signature.parameters) == (
        "event_sink",
        "metric_sink",
        "resource_limits",
    )
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )
    assert tuple(
        name
        for name, value in vars(ObservabilityService).items()
        if not name.startswith("_") and inspect.isfunction(value)
    ) == ("emit_event", "increment_counter", "observe_duration")

    service, event_sink, metric_sink = _service()
    assert service.emit_event(_event()) is None
    assert service.emit_event(BoundaryErrorEvent(BoundaryErrorKind.MCP_REQUEST)) is None
    assert service.increment_counter(MetricKind.SUBMIT_COUNT) is None
    assert service.observe_duration(DurationStage.SCORE, 0) is None
    assert isinstance(event_sink, _RecordingEventSink)
    assert isinstance(metric_sink, _RecordingMetricSink)
    assert len(event_sink.events) == 2
    assert [metric.metric_name for metric in metric_sink.counters] == ["SUBMIT_COUNT"]
    assert [(metric.stage, metric.duration_ns) for metric in metric_sink.durations] == [
        ("SCORE", 0)
    ]


def test_service_rejects_none_sinks_and_invalid_resource_policy() -> None:
    limits = ObservabilityResourceLimits(1)
    for event_sink, metric_sink, resource_limits in (
        (None, _RecordingMetricSink(), limits),
        (_RecordingEventSink(), None, limits),
        (_RecordingEventSink(), _RecordingMetricSink(), None),
        (_RecordingEventSink(), _RecordingMetricSink(), _Hostile()),
    ):
        with pytest.raises(ObservabilityRequestError):
            ObservabilityService(  # type: ignore[arg-type]
                event_sink,
                metric_sink,
                resource_limits,
            )


@pytest.mark.parametrize(
    "maximum",
    (None, False, 0, -1, U64_MAX + 1, 1.0, "1", _IntegerSubclass(1), _Hostile()),
)
def test_resource_limits_require_positive_exact_u64(maximum: object) -> None:
    with pytest.raises(ObservabilityRequestError):
        ObservabilityResourceLimits(maximum)  # type: ignore[arg-type]


def test_service_copies_resource_limits_and_does_not_inspect_sink_methods_at_init() -> (
    None
):
    class ExplosiveDescriptor:
        def __get__(self, instance: object, owner: type[object]) -> object:
            del instance, owner
            raise ValueError("private descriptor diagnostic")

    class DeferredEventSink:
        emit_event = ExplosiveDescriptor()

    limits = ObservabilityResourceLimits(1)
    service = ObservabilityService(DeferredEventSink(), _RecordingMetricSink(), limits)
    object.__setattr__(limits, "max_concurrent_calls", 0)
    assert service.increment_counter(MetricKind.SUBMIT_COUNT) is None
    with pytest.raises(ObservabilityIntegrationError) as raised:
        service.emit_event(_event())
    _assert_fixed_integration_error(raised.value)


def test_service_and_sink_owned_values_block_dataclass_traversal() -> None:
    event_sink = _RecordingEventSink()
    metric_sink = _RecordingMetricSink()
    caller_event = _event()
    caller_boundary = BoundaryErrorEvent(BoundaryErrorKind.MCP_REQUEST)
    caller_limits = ObservabilityResourceLimits(1)
    service = ObservabilityService(event_sink, metric_sink, caller_limits)

    assert service.emit_event(caller_event) is None
    assert service.emit_event(caller_boundary) is None
    assert len(event_sink.events) == 2
    sink_event, sink_boundary = event_sink.events
    assert type(sink_event) is SubmissionEventSnapshot
    assert type(sink_boundary) is BoundaryErrorSnapshot
    assert sink_event is not caller_event
    assert sink_boundary is not caller_boundary

    owned_limits = object.__getattribute__(service, "_limits")
    assert type(owned_limits) is ObservabilityResourceLimits
    assert owned_limits is not caller_limits
    _assert_dataclass_apis_are_blocked(
        sink_event,
        forbidden_text=SUBMISSION_ID_TEXT,
    )
    _assert_dataclass_apis_are_blocked(sink_boundary)
    _assert_dataclass_apis_are_blocked(owned_limits)


def test_protocols_have_exact_positional_only_structural_signatures() -> None:
    event_signature = inspect.signature(StructuredEventSink.emit_event)
    counter_signature = inspect.signature(MetricSink.increment_counter)
    duration_signature = inspect.signature(MetricSink.observe_duration)
    assert tuple(event_signature.parameters) == ("self", "event")
    assert tuple(counter_signature.parameters) == ("self", "metric")
    assert tuple(duration_signature.parameters) == ("self", "metric")
    for signature in (event_signature, counter_signature, duration_signature):
        parameters = tuple(signature.parameters.values())[1:]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_ONLY
            for parameter in parameters
        )
        assert signature.return_annotation in (None, "None")

    event_hints = get_type_hints(StructuredEventSink.emit_event)
    counter_hints = get_type_hints(MetricSink.increment_counter)
    duration_hints = get_type_hints(MetricSink.observe_duration)
    assert event_hints == {
        "event": SubmissionEventSnapshot | BoundaryErrorSnapshot,
        "return": type(None),
    }
    assert counter_hints == {
        "metric": CounterMetricSnapshot,
        "return": type(None),
    }
    assert duration_hints == {
        "metric": DurationMetricSnapshot,
        "return": type(None),
    }

    event_sink = _RecordingEventSink()
    metric_sink = _RecordingMetricSink()
    assert StructuredEventSink not in type(event_sink).__mro__
    assert MetricSink not in type(metric_sink).__mro__
    with pytest.raises(TypeError):
        isinstance(event_sink, StructuredEventSink)
    with pytest.raises(TypeError):
        isinstance(metric_sink, MetricSink)


@pytest.mark.parametrize("invalid", (_Hostile(), _DescriptorLookalike(), {}, [], ()))
def test_outer_validation_does_not_traverse_or_render_unknown_shapes(
    invalid: object,
) -> None:
    service, event_sink, _ = _service()
    with pytest.raises(ObservabilityRequestError):
        service.emit_event(invalid)  # type: ignore[arg-type]
    assert isinstance(event_sink, _RecordingEventSink)
    assert event_sink.events == []


def test_cyclic_aliased_and_hostile_mappings_are_rejected_without_traversal() -> None:
    class HostileMapping(dict[object, object]):
        def __iter__(self):  # type: ignore[no-untyped-def]
            raise AssertionError("mapping iteration was invoked")

        def __getitem__(self, key: object) -> object:
            del key
            raise AssertionError("mapping lookup was invoked")

        def items(self):  # type: ignore[no-untyped-def]
            raise AssertionError("mapping items were invoked")

        def keys(self):  # type: ignore[no-untyped-def]
            raise AssertionError("mapping keys were invoked")

        def values(self):  # type: ignore[no-untyped-def]
            raise AssertionError("mapping values were invoked")

    hostile = _Hostile()
    mapping = HostileMapping()
    dict.__setitem__(mapping, "alias_one", hostile)
    dict.__setitem__(mapping, "alias_two", hostile)
    dict.__setitem__(mapping, "cycle", mapping)
    cycle: list[object] = []
    cycle.append(cycle)

    service, event_sink, _ = _service()
    for invalid in (mapping, cycle):
        with pytest.raises(ObservabilityRequestError):
            service.emit_event(invalid)  # type: ignore[arg-type]
    assert isinstance(event_sink, _RecordingEventSink)
    assert event_sink.events == []


def test_forbidden_material_has_no_positive_construction_path() -> None:
    forbidden_payload = {
        name: _Hostile()
        for name in (
            "artifact",
            "backend_exception",
            "checkpoint",
            "command",
            "credential",
            "cursor",
            "customer",
            "diagnostic",
            "draw_id",
            "environment",
            "fee",
            "gate",
            "hotkey",
            "margin",
            "mock_result",
            "nonce",
            "parameter",
            "payment",
            "provider",
            "query_history",
            "rank",
            "receipt_id",
            "requester",
            "result_id",
            "reward",
            "score",
            "seed",
            "stack_trace",
            "strategy",
            "stress",
            "wallet",
            "weight",
        )
    }
    service, event_sink, metric_sink = _service()
    with pytest.raises(ObservabilityRequestError) as raised:
        service.emit_event(forbidden_payload)  # type: ignore[arg-type]
    assert type(raised.value) is ObservabilityRequestError
    assert raised.value.args == ("Observability request is invalid.",)
    assert isinstance(event_sink, _RecordingEventSink)
    assert isinstance(metric_sink, _RecordingMetricSink)
    assert event_sink.events == []
    assert metric_sink.counters == [] and metric_sink.durations == []


def test_unknown_fields_free_text_labels_and_generic_operations_are_absent() -> None:
    with pytest.raises(TypeError):
        ObservabilityEvent(  # type: ignore[call-arg]
            kind=EventKind.SUBMIT,
            submission_id=_submission_id(),
            submission_state=SubmissionState.RECEIVED,
            score_status=None,
            message="secret\r\nconfusable-\N{CYRILLIC SMALL LETTER A}",
        )
    with pytest.raises(TypeError):
        BoundaryErrorEvent(  # type: ignore[call-arg]
            BoundaryErrorKind.MCP_REQUEST,
            exception=RuntimeError("secret"),
        )

    service, _, sink = _service()
    for name in (
        "batch",
        "decrement",
        "emit",
        "export",
        "flush",
        "gauge",
        "histogram",
        "log",
        "metric",
        "queue",
        "record",
        "reset",
        "retry",
        "serialize",
        "set_sink",
    ):
        assert not hasattr(service, name)
    with pytest.raises(TypeError):
        service.increment_counter(MetricKind.SUBMIT_COUNT, 2)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        service.observe_duration(  # type: ignore[call-arg]
            DurationStage.SUBMIT,
            1,
            {"submission_id": SUBMISSION_ID_TEXT},
        )
    assert isinstance(sink, _RecordingMetricSink)
    assert sink.counters == [] and sink.durations == []
    assert not hasattr(MetricKind, "FAILED_STRATEGY_COUNT")


def test_caller_mutation_race_cannot_change_the_sink_safe_copy() -> None:
    entered = threading.Event()
    release = threading.Event()
    received: list[SubmissionEventSnapshot] = []

    class BlockingSink:
        def emit_event(
            self,
            event: SubmissionEventSnapshot | BoundaryErrorSnapshot,
            /,
        ) -> None:
            assert type(event) is SubmissionEventSnapshot
            received.append(event)
            entered.set()
            assert release.wait(5)

    caller_event = _event()
    service, _, _ = _service(event_sink=BlockingSink())
    failures: list[BaseException] = []

    def invoke() -> None:
        try:
            service.emit_event(caller_event)
        except BaseException as error:  # noqa: BLE001 - record thread failures
            failures.append(error)

    thread = threading.Thread(target=invoke)
    thread.start()
    assert entered.wait(5)
    object.__setattr__(caller_event, "kind", EventKind.REJECT)
    object.__setattr__(caller_event.submission_id, "value", "x" * 10_000)
    assert received[0].kind == "SUBMIT"
    assert received[0].submission_id == SUBMISSION_ID_TEXT
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert failures == []


def test_sink_mutation_of_owned_argument_cannot_change_the_caller_event() -> None:
    caller_event = _event()
    received: list[SubmissionEventSnapshot] = []

    class MutatingSink:
        def emit_event(
            self,
            event: SubmissionEventSnapshot | BoundaryErrorSnapshot,
            /,
        ) -> None:
            assert type(event) is SubmissionEventSnapshot
            received.append(event)
            object.__setattr__(event, "kind", "REJECT")
            object.__setattr__(event, "submission_id", "sink-tampered")

    service, _, _ = _service(event_sink=MutatingSink())
    assert service.emit_event(caller_event) is None
    assert received[0] is not caller_event
    assert caller_event.kind is EventKind.SUBMIT
    assert caller_event.submission_id.value == SUBMISSION_ID_TEXT


def test_retained_snapshot_mutation_cannot_affect_later_or_other_service_calls() -> (
    None
):
    retained: list[SubmissionEventSnapshot] = []

    class RetainingSink:
        def emit_event(
            self,
            event: SubmissionEventSnapshot | BoundaryErrorSnapshot,
            /,
        ) -> None:
            assert type(event) is SubmissionEventSnapshot
            retained.append(event)

    first_service, _, _ = _service(event_sink=RetainingSink())
    second_service, second_sink, _ = _service()
    request = _event()
    assert first_service.emit_event(request) is None
    first = retained[0]
    object.__setattr__(first, "kind", "REJECT")
    object.__setattr__(first, "submission_id", "mutated-retained-snapshot")
    assert first_service.emit_event(request) is None
    assert second_service.emit_event(request) is None

    later = retained[1]
    assert later is not first
    assert (later.kind, later.submission_id) == ("SUBMIT", SUBMISSION_ID_TEXT)
    assert isinstance(second_sink, _RecordingEventSink)
    other = second_sink.events[0]
    assert type(other) is SubmissionEventSnapshot
    assert other is not first and other is not later
    assert (other.kind, other.submission_id) == ("SUBMIT", SUBMISSION_ID_TEXT)
    assert request.kind is EventKind.SUBMIT
    assert request.submission_id.value == SUBMISSION_ID_TEXT


def test_normal_snapshot_mutation_is_rejected_without_affecting_the_operation() -> None:
    attempts: list[type[BaseException]] = []

    class MutationAttemptSink:
        def emit_event(
            self,
            event: SubmissionEventSnapshot | BoundaryErrorSnapshot,
            /,
        ) -> None:
            for operation in (
                lambda: setattr(event, "kind", "REJECT"),
                lambda: delattr(event, "kind"),
            ):
                try:
                    operation()
                except BaseException as error:  # noqa: BLE001 - test records type
                    attempts.append(type(error))

    service, _, _ = _service(event_sink=MutationAttemptSink())
    request = _event()
    assert service.emit_event(request) is None
    assert attempts == [AttributeError, AttributeError]
    assert request.kind is EventKind.SUBMIT
    assert request.submission_id.value == SUBMISSION_ID_TEXT


def test_concurrent_operations_receive_distinct_isolated_snapshots() -> None:
    entered = threading.Barrier(3)
    release = threading.Event()
    snapshots: list[SubmissionEventSnapshot] = []
    guard = threading.Lock()

    class ConcurrentSink:
        def emit_event(
            self,
            event: SubmissionEventSnapshot | BoundaryErrorSnapshot,
            /,
        ) -> None:
            assert type(event) is SubmissionEventSnapshot
            with guard:
                snapshots.append(event)
            entered.wait(5)
            assert release.wait(5)

    service, _, _ = _service(event_sink=ConcurrentSink(), capacity=2)
    failures: list[BaseException] = []

    def invoke() -> None:
        try:
            service.emit_event(_event())
        except BaseException as error:  # noqa: BLE001 - record thread failures
            failures.append(error)

    threads = (threading.Thread(target=invoke), threading.Thread(target=invoke))
    for thread in threads:
        thread.start()
    entered.wait(5)
    assert len(snapshots) == 2
    assert snapshots[0] is not snapshots[1]
    object.__setattr__(snapshots[0], "kind", "REJECT")
    assert snapshots[1].kind == "SUBMIT"
    release.set()
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive()
    assert failures == []


@pytest.mark.parametrize(
    "failure",
    (
        ValueError("private value"),
        RuntimeError("private\r\ntrace"),
        ObservabilityRequestError(),
        ObservabilityResourceError(),
        ObservabilityIntegrationError(),
    ),
)
def test_sink_ordinary_exceptions_translate_to_fresh_context_free_error(
    failure: Exception,
) -> None:
    class FailingSink:
        def __init__(self) -> None:
            self.calls = 0
            self.failure: Exception | None = failure

        def emit_event(self, event: ObservabilityEvent | BoundaryErrorEvent, /) -> None:
            del event
            self.calls += 1
            if self.failure is not None:
                raise self.failure

    sink = FailingSink()
    service, _, _ = _service(event_sink=sink)
    with pytest.raises(ObservabilityIntegrationError) as raised:
        service.emit_event(_event())
    _assert_fixed_integration_error(raised.value)
    assert raised.value is not failure
    assert "private" not in str(raised.value)
    assert "private" not in repr(raised.value)
    assert failure not in raised.value.args
    assert sink.calls == 1

    sink.failure = None
    assert service.emit_event(_event()) is None
    assert sink.calls == 2


@pytest.mark.parametrize("wrong_return", (False, 0, "", object(), _Hostile()))
def test_non_none_sink_return_is_one_integration_failure_without_retry(
    wrong_return: object,
) -> None:
    class WrongReturnSink:
        def __init__(self) -> None:
            self.calls = 0
            self.return_value: object | None = wrong_return

        def increment_counter(self, metric: CounterMetricSnapshot, /) -> object:
            del metric
            self.calls += 1
            return self.return_value

        def observe_duration(self, metric: DurationMetricSnapshot, /) -> None:
            del metric

    sink = WrongReturnSink()
    service, _, _ = _service(metric_sink=sink)
    with pytest.raises(ObservabilityIntegrationError) as raised:
        service.increment_counter(MetricKind.SCORE_COUNT)
    _assert_fixed_integration_error(raised.value)
    assert sink.calls == 1
    sink.return_value = None
    assert service.increment_counter(MetricKind.SCORE_COUNT) is None
    assert sink.calls == 2


def test_missing_noncallable_and_incompatible_sink_methods_translate() -> None:
    class Missing:
        pass

    class NonCallable:
        increment_counter = None

    class Incompatible:
        def increment_counter(self) -> None:
            pass

    for sink in (Missing(), NonCallable(), Incompatible()):
        service, _, _ = _service(metric_sink=sink)
        with pytest.raises(ObservabilityIntegrationError) as raised:
            service.increment_counter(MetricKind.REJECT_COUNT)
        _assert_fixed_integration_error(raised.value)


def test_hostile_sink_descriptor_translates_without_constructor_inspection() -> None:
    accesses = 0

    class Descriptor:
        def __get__(self, instance: object, owner: type[object]) -> object:
            nonlocal accesses
            del instance, owner
            accesses += 1
            raise RuntimeError("private descriptor payload")

    class Sink:
        observe_duration = Descriptor()

    service, _, _ = _service(metric_sink=Sink())
    assert accesses == 0
    with pytest.raises(ObservabilityIntegrationError) as raised:
        service.observe_duration(DurationStage.SUBMIT, 1)
    _assert_fixed_integration_error(raised.value)
    assert accesses == 1


@pytest.mark.parametrize(
    "failure", (KeyboardInterrupt(), SystemExit(7), GeneratorExit())
)
def test_non_exception_baseexceptions_propagate_unchanged_and_release_capacity(
    failure: BaseException,
) -> None:
    class BaseFailureSink:
        def __init__(self) -> None:
            self.failure: BaseException | None = failure
            self.calls = 0

        def emit_event(self, event: ObservabilityEvent | BoundaryErrorEvent, /) -> None:
            del event
            self.calls += 1
            if self.failure is not None:
                raise self.failure

    sink = BaseFailureSink()
    service, _, _ = _service(event_sink=sink)
    with pytest.raises(type(failure)) as raised:
        service.emit_event(_event())
    assert raised.value is failure
    sink.failure = None
    assert service.emit_event(_event()) is None
    assert sink.calls == 2


def test_a11_created_errors_clear_ambient_caller_exception_context() -> None:
    def under_ambient_exception(
        operation: Callable[[], object],
        expected_type: type[ObservabilityError],
    ) -> ObservabilityError:
        try:
            raise RuntimeError("ambient private caller exception")
        except RuntimeError:
            try:
                operation()
            except expected_type as error:
                assert BaseException.__getattribute__(error, "__cause__") is None
                assert BaseException.__getattribute__(error, "__context__") is None
                return error
        raise AssertionError("operation did not raise its exact A11 error")

    request_service, _, _ = _service()
    request_error = under_ambient_exception(
        lambda: request_service.emit_event(_Hostile()),  # type: ignore[arg-type]
        ObservabilityRequestError,
    )
    assert type(request_error) is ObservabilityRequestError

    class FailingMetricSink:
        def increment_counter(self, metric: CounterMetricSnapshot, /) -> None:
            del metric
            raise ValueError("private sink failure")

        def observe_duration(self, metric: DurationMetricSnapshot, /) -> None:
            del metric

    integration_service, _, _ = _service(metric_sink=FailingMetricSink())
    integration_error = under_ambient_exception(
        lambda: integration_service.increment_counter(MetricKind.SUBMIT_COUNT),
        ObservabilityIntegrationError,
    )
    assert type(integration_error) is ObservabilityIntegrationError

    class ReentrantSink:
        def __init__(self) -> None:
            self.service: ObservabilityService | None = None
            self.error: ObservabilityError | None = None

        def emit_event(self, event: ObservabilityEvent | BoundaryErrorEvent, /) -> None:
            del event
            assert self.service is not None
            self.error = under_ambient_exception(
                lambda: self.service.increment_counter(MetricKind.SUBMIT_COUNT),
                ObservabilityResourceError,
            )

    reentrant_sink = ReentrantSink()
    resource_service, _, _ = _service(event_sink=reentrant_sink, capacity=2)
    reentrant_sink.service = resource_service
    assert resource_service.emit_event(_event()) is None
    assert type(reentrant_sink.error) is ObservabilityResourceError


def test_shared_capacity_rejects_before_sink_access_and_validation_precedes_capacity() -> (
    None
):
    entered = threading.Event()
    release = threading.Event()

    class BlockingEventSink:
        def __init__(self) -> None:
            self.calls = 0

        def emit_event(self, event: ObservabilityEvent | BoundaryErrorEvent, /) -> None:
            del event
            self.calls += 1
            entered.set()
            assert release.wait(5)

    metric_accesses = 0

    class MetricDescriptor:
        def __get__(self, instance: object, owner: type[object]) -> object:
            nonlocal metric_accesses
            del instance, owner
            metric_accesses += 1
            raise AssertionError("metric sink was accessed at capacity")

    class UntouchedMetricSink:
        increment_counter = MetricDescriptor()

    event_sink = BlockingEventSink()
    service, _, _ = _service(
        event_sink=event_sink,
        metric_sink=UntouchedMetricSink(),
        capacity=1,
    )
    failures: list[BaseException] = []

    def occupy() -> None:
        try:
            service.emit_event(_event())
        except BaseException as error:  # noqa: BLE001 - record thread failures
            failures.append(error)

    thread = threading.Thread(target=occupy)
    thread.start()
    assert entered.wait(5)

    with pytest.raises(ObservabilityRequestError):
        service.increment_counter(_Hostile())  # type: ignore[arg-type]
    with pytest.raises(ObservabilityResourceError) as raised:
        service.increment_counter(MetricKind.SUBMIT_COUNT)
    assert raised.value.__cause__ is None and raised.value.__context__ is None
    assert metric_accesses == 0
    assert event_sink.calls == 1

    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert failures == []
    assert service.emit_event(_event()) is None
    assert event_sink.calls == 2


def test_capacity_two_allows_simultaneous_sink_entry_without_an_ordinary_mutex() -> (
    None
):
    entered = threading.Barrier(3)
    release = threading.Event()

    class ConcurrentEventSink:
        def __init__(self) -> None:
            self.calls = 0
            self.lock = threading.Lock()

        def emit_event(self, event: ObservabilityEvent | BoundaryErrorEvent, /) -> None:
            del event
            with self.lock:
                self.calls += 1
            entered.wait(5)
            assert release.wait(5)

    event_sink = ConcurrentEventSink()
    metric_sink = _RecordingMetricSink()
    service = ObservabilityService(
        event_sink,
        metric_sink,
        ObservabilityResourceLimits(2),
    )
    failures: list[BaseException] = []

    def occupy() -> None:
        try:
            service.emit_event(_event())
        except BaseException as error:  # noqa: BLE001 - record thread failures
            failures.append(error)

    threads = (threading.Thread(target=occupy), threading.Thread(target=occupy))
    for thread in threads:
        thread.start()
    entered.wait(5)
    assert event_sink.calls == 2
    with pytest.raises(ObservabilityResourceError):
        service.observe_duration(DurationStage.SCORE, 1)
    assert metric_sink.durations == []

    release.set()
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive()
    assert failures == []
    assert service.observe_duration(DurationStage.SCORE, 1) is None
    assert [(metric.stage, metric.duration_ns) for metric in metric_sink.durations] == [
        ("SCORE", 1)
    ]


def test_same_service_reentrancy_rejects_before_a_second_sink_call() -> None:
    first_metric_sink = _RecordingMetricSink()
    second_metric_sink = _RecordingMetricSink()
    second_service = ObservabilityService(
        _RecordingEventSink(),
        second_metric_sink,
        ObservabilityResourceLimits(1),
    )

    class ReentrantEventSink:
        def __init__(self) -> None:
            self.first_service: ObservabilityService | None = None
            self.calls = 0
            self.inner_error: ObservabilityResourceError | None = None

        def emit_event(self, event: ObservabilityEvent | BoundaryErrorEvent, /) -> None:
            del event
            self.calls += 1
            assert self.first_service is not None
            try:
                self.first_service.increment_counter(MetricKind.SUBMIT_COUNT)
            except ObservabilityResourceError as error:
                self.inner_error = error
            assert second_service.increment_counter(MetricKind.SCORE_COUNT) is None

    event_sink = ReentrantEventSink()
    first_service = ObservabilityService(
        event_sink,
        first_metric_sink,
        ObservabilityResourceLimits(2),
    )
    event_sink.first_service = first_service
    assert first_service.emit_event(_event()) is None
    assert event_sink.calls == 1
    assert type(event_sink.inner_error) is ObservabilityResourceError
    assert first_metric_sink.counters == []
    assert [metric.metric_name for metric in second_metric_sink.counters] == [
        "SCORE_COUNT"
    ]
    assert first_service.increment_counter(MetricKind.SUBMIT_COUNT) is None
    assert [metric.metric_name for metric in first_metric_sink.counters] == [
        "SUBMIT_COUNT"
    ]


@dataclass(frozen=True, slots=True)
class _DeterminedDomainResult:
    scientific_status: str
    lifecycle_state: str
    publication_sequence: int
    economic_effect: int


def test_composition_preserves_determined_domain_result_when_telemetry_fails() -> None:
    class FailingMetricSink:
        def __init__(self) -> None:
            self.calls = 0

        def increment_counter(self, metric: CounterMetricSnapshot, /) -> None:
            del metric
            self.calls += 1
            raise RuntimeError("private backend failure")

        def observe_duration(self, metric: DurationMetricSnapshot, /) -> None:
            del metric

    result = _DeterminedDomainResult("SCORED", "SCORED", 7, 0)
    sink = FailingMetricSink()
    service, _, _ = _service(metric_sink=sink)

    def compose(determined: _DeterminedDomainResult) -> _DeterminedDomainResult:
        try:
            service.increment_counter(MetricKind.SCORE_COUNT)
        except ObservabilityError:
            pass
        return determined

    before = dataclasses.astuple(result)
    returned = compose(result)
    assert returned is result
    assert dataclasses.astuple(result) == before
    assert sink.calls == 1


def _attribute_path(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while type(current) is ast.Attribute:
        parts.append(current.attr)
        current = current.value
    if type(current) is not ast.Name:
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def test_dependency_graph_and_runtime_escape_policy_are_exact() -> None:
    files = tuple(sorted(OBSERVABILITY_ROOT.glob("*.py")))
    allowed_relative = {
        "__init__.py": {"model", "providers", "service"},
        "model.py": set(),
        "providers.py": {"model"},
        "service.py": {"model", "providers"},
    }
    expected_owner_imports = {
        ("carbon.fees", frozenset({"SubmissionId", "SubmissionState"})),
        ("carbon.scoring", frozenset({"ScoreStatus"})),
    }
    forbidden_modules = {
        "aiohttp",
        "bittensor",
        "copy",
        "dataclasses",
        "datetime",
        "flask",
        "http",
        "importlib",
        "json",
        "logging",
        "marshal",
        "numpy",
        "opentelemetry",
        "os",
        "pathlib",
        "pickle",
        "prometheus_client",
        "queue",
        "requests",
        "shelve",
        "socket",
        "sqlite3",
        "statsd",
        "tempfile",
        "time",
        "urllib",
    }
    forbidden_runtime_names = {
        "__import__",
        "asdict",
        "astuple",
        "compile",
        "dataclass",
        "deepcopy",
        "dumps",
        "eval",
        "exec",
        "field",
        "fields",
        "getattr",
        "globals",
        "import_module",
        "isinstance",
        "is_dataclass",
        "issubclass",
        "loads",
        "locals",
        "make_dataclass",
        "repr",
        "replace",
        "runtime_checkable",
        "sleep",
        "vars",
    }
    found_owner_imports: set[tuple[str, frozenset[str]]] = set()
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if type(node) is ast.Import:
                for alias in node.names:
                    root = alias.name.partition(".")[0]
                    assert root in sys.stdlib_module_names
                    assert root not in forbidden_modules
                    assert alias.asname is None
            elif type(node) is ast.ImportFrom:
                assert all(
                    alias.name != "*" and alias.asname is None for alias in node.names
                )
                if node.level:
                    assert node.level == 1
                    if node.module is None:
                        assert {alias.name for alias in node.names} <= allowed_relative[
                            path.name
                        ]
                    else:
                        assert node.module in allowed_relative[path.name]
                elif node.module in {"carbon.fees", "carbon.scoring"}:
                    assert path.name == "model.py"
                    found_owner_imports.add(
                        (node.module, frozenset(alias.name for alias in node.names))
                    )
                else:
                    assert node.module is not None
                    root = node.module.partition(".")[0]
                    assert root in sys.stdlib_module_names
                    assert root not in forbidden_modules
            elif type(node) is ast.Name:
                assert node.id not in forbidden_runtime_names
            elif type(node) is ast.Attribute:
                assert node.attr not in {
                    "__dict__",
                    "asdict",
                    "astuple",
                    "dataclass",
                    "dumps",
                    "field",
                    "fields",
                    "is_dataclass",
                    "loads",
                    "make_dataclass",
                    "replace",
                    "to_dict",
                }
            elif type(node) is ast.ExceptHandler and node.type is not None:
                caught = (
                    {node.type.id}
                    if type(node.type) is ast.Name
                    else (
                        {
                            element.id
                            for element in node.type.elts
                            if type(element) is ast.Name
                        }
                        if type(node.type) is ast.Tuple
                        else set()
                    )
                )
                assert "BaseException" not in caught
            elif type(node) is ast.Call:
                path_name = _attribute_path(node.func)
                assert path_name != "str"
                assert path_name not in {
                    "threading.Lock",
                    "threading.RLock",
                    "threading.Thread",
                }
    assert found_owner_imports == expected_owner_imports


def test_source_has_no_private_owner_or_deferred_authority_dependency() -> None:
    nodes = [
        node
        for path in sorted(OBSERVABILITY_ROOT.glob("*.py"))
        for node in ast.walk(
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        )
    ]
    used_names = {node.id for node in nodes if type(node) is ast.Name} | {
        node.attr for node in nodes if type(node) is ast.Attribute
    }
    prohibited = {
        "AttemptEventKind",
        "Bittensor",
        "CardStore",
        "ChallengeKey",
        "EvaluationCard",
        "Evidence",
        "FixtureLeaderboardService",
        "FrontierAdvanceEvent",
        "FrontierRecord",
        "InformationBudget",
        "InternalResult",
        "Landscape",
        "McpService",
        "ProductQualification",
        "Receipt",
        "PublishedPrior",
        "PublishedScaffold",
        "RequesterIdentity",
        "ScoreEngine",
        "SubmissionService",
        "SubmissionStatusView",
        "Settlement",
        "TrainEval",
        "Treasury",
        "ValidationResult",
        "Weight",
    }
    assert used_names.isdisjoint(prohibited)

    forbidden_carbon_prefixes = (
        "carbon.audit",
        "carbon.cards",
        "carbon.chain",
        "carbon.emission",
        "carbon.evaluation",
        "carbon.landscape",
        "carbon.leaderboard",
        "carbon.logging_utils",
        "carbon.mcp",
        "carbon.miner",
        "carbon.qualification",
        "carbon.traineval",
        "carbon.validator",
    )
    for path in sorted(OBSERVABILITY_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if type(node) is ast.Import
            for alias in node.names
        } | {
            node.module
            for node in ast.walk(tree)
            if type(node) is ast.ImportFrom
            and node.module is not None
            and not node.level
        }
        assert not any(
            module == prefix or module.startswith(prefix + ".")
            for module in imported_modules
            for prefix in forbidden_carbon_prefixes
        )


def test_providers_module_contains_protocols_only_and_service_has_no_authority_api() -> (
    None
):
    providers_path = OBSERVABILITY_ROOT / "providers.py"
    tree = ast.parse(
        providers_path.read_text(encoding="utf-8"), filename=str(providers_path)
    )
    assert tuple(node.name for node in tree.body if type(node) is ast.ClassDef) == (
        "StructuredEventSink",
        "MetricSink",
    )
    assert not any(
        type(node) in (ast.FunctionDef, ast.AsyncFunctionDef) for node in tree.body
    )
    assert not any(type(node) is ast.AsyncFunctionDef for node in ast.walk(tree))

    service, _, _ = _service()
    assert not hasattr(service, "__dict__")
    slots = tuple(type(service).__slots__)
    assert not any(
        token in slot
        for slot in slots
        for token in (
            "audit",
            "cache",
            "challenge",
            "database",
            "evidence",
            "exporter",
            "frontier",
            "history",
            "logger",
            "publication",
            "queue",
            "receipt",
            "result",
            "retry",
            "score",
            "settlement",
            "store",
            "timestamp",
            "treasury",
            "weight",
        )
    )


def test_a5_through_a10_owners_do_not_import_observability() -> None:
    owner_roots = tuple(
        REPOSITORY_ROOT / "carbon" / name
        for name in ("scoring", "cards", "fees", "traineval", "mcp", "leaderboard")
    )
    for owner_root in owner_roots:
        for path in owner_root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "carbon.observability" not in source
            assert "from ..observability" not in source
            assert "from .observability" not in source
    assert "observability" not in (
        REPOSITORY_ROOT / "carbon" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "observability" not in (
        REPOSITORY_ROOT / "carbon" / "logging_utils" / "__init__.py"
    ).read_text(encoding="utf-8")


def test_enum_member_tampering_is_rejected_in_an_isolated_process(
    tmp_path: Path,
) -> None:
    script = f"""
import sys
sys.path.insert(0, {str(REPOSITORY_ROOT)!r})

from carbon.fees import SubmissionId, SubmissionState
from carbon.observability import (
    BoundaryErrorEvent, BoundaryErrorKind, DurationStage, EventKind, MetricKind,
    ObservabilityEvent, ObservabilityRequestError, ObservabilityResourceLimits,
    ObservabilityService,
)
from carbon.scoring import ScoreStatus

identifier = SubmissionId({SUBMISSION_ID_TEXT!r})

class EventSink:
    def emit_event(self, event, /):
        raise AssertionError('tampered event reached sink')

class MetricSink:
    def increment_counter(self, metric, /):
        raise AssertionError('tampered metric reached sink')
    def observe_duration(self, metric, /):
        raise AssertionError('tampered duration reached sink')

service = ObservabilityService(EventSink(), MetricSink(), ObservabilityResourceLimits(1))

def rejected(member, attribute, replacement, operation):
    original = object.__getattribute__(member, attribute)
    object.__setattr__(member, attribute, replacement)
    try:
        try:
            operation()
        except ObservabilityRequestError:
            pass
        else:
            raise AssertionError('tampered canonical enum member was accepted')
    finally:
        object.__setattr__(member, attribute, original)

rejected(
    EventKind.SUBMIT, '_value_', 'ALTERED',
    lambda: ObservabilityEvent(
        EventKind.SUBMIT, identifier, SubmissionState.RECEIVED, None
    ),
)
rejected(
    EventKind.SUBMIT, '_name_', 'ALTERED',
    lambda: ObservabilityEvent(
        EventKind.SUBMIT, identifier, SubmissionState.RECEIVED, None
    ),
)
rejected(
    SubmissionState.RECEIVED, '_value_', 'ALTERED',
    lambda: ObservabilityEvent(
        EventKind.SUBMIT, identifier, SubmissionState.RECEIVED, None
    ),
)
rejected(
    ScoreStatus.SCORED, '_name_', 'ALTERED',
    lambda: ObservabilityEvent(
        EventKind.SCORE, identifier, SubmissionState.SCORED, ScoreStatus.SCORED
    ),
)
rejected(
    BoundaryErrorKind.MCP_REQUEST, '_value_', 'ALTERED',
    lambda: BoundaryErrorEvent(BoundaryErrorKind.MCP_REQUEST),
)
rejected(
    MetricKind.SUBMIT_COUNT, '_name_', 'ALTERED',
    lambda: service.increment_counter(MetricKind.SUBMIT_COUNT),
)
rejected(
    DurationStage.SUBMIT, '_value_', 'ALTERED',
    lambda: service.observe_duration(DurationStage.SUBMIT, 0),
)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_import_with_optional_and_later_dependencies_blocked(tmp_path: Path) -> None:
    script = f"""
import dataclasses
import importlib
import importlib.abc
import sys

sys.path.insert(0, {str(REPOSITORY_ROOT)!r})
stdlib_dataclass_apis = (
    dataclasses.is_dataclass,
    dataclasses.asdict,
    dataclasses.astuple,
    dataclasses.replace,
)

blocked_roots = {{
    'aiohttp', 'bittensor', 'docker', 'fastapi', 'flask', 'jax', 'neuralop',
    'numpy', 'opentelemetry', 'pandas', 'physicsnemo', 'prometheus_client',
    'pydantic', 'requests', 'scipy', 'sklearn', 'statsd', 'torch', 'yaml',
}}
blocked_carbon = (
    'carbon.audit', 'carbon.chain', 'carbon.emission', 'carbon.evaluation',
    'carbon.landscape', 'carbon.leaderboard', 'carbon.logging_utils',
    'carbon.mcp', 'carbon.miner', 'carbon.qualification', 'carbon.traineval',
    'carbon.validator',
)
attempted = []

class DependencyBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        del path, target
        root = fullname.partition('.')[0]
        if root in blocked_roots or any(
            fullname == prefix or fullname.startswith(prefix + '.')
            for prefix in blocked_carbon
        ):
            attempted.append(fullname)
            raise ModuleNotFoundError(
                f'blocked dependency: {{fullname}}', name=fullname
            )
        return None

sys.meta_path.insert(0, DependencyBlocker())
module = importlib.import_module('carbon.observability')
assert all(
    current is original
    for current, original in zip(
        (
            dataclasses.is_dataclass,
            dataclasses.asdict,
            dataclasses.astuple,
            dataclasses.replace,
        ),
        stdlib_dataclass_apis,
        strict=True,
    )
)
assert module.__all__ == {PUBLIC_EXPORTS!r}
assert tuple(getattr(module, name).__name__ for name in module.__all__) == module.__all__
assert attempted == []
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_fresh_zero_dependency_wheel_imports_exact_surface_outside_tree(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(REPOSITORY_ROOT / "pyproject.toml", source / "pyproject.toml")
    shutil.copy2(REPOSITORY_ROOT / "README.md", source / "README.md")
    shutil.copytree(
        REPOSITORY_ROOT / "carbon",
        source / "carbon",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    builder = None
    checked: set[str] = set()
    for candidate in (sys.executable, getattr(sys, "_base_executable", None)):
        if type(candidate) is not str or candidate in checked:
            continue
        checked.add(candidate)
        probe = subprocess.run(
            [candidate, "-I", "-c", "import setuptools, wheel"],
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            builder = candidate
            break
    assert builder is not None
    environment_values = os.environ.copy()
    environment_values.update(
        {
            "PIP_CACHE_DIR": str(tmp_path / "pip-cache"),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    build = subprocess.run(
        [
            builder,
            "-m",
            "pip",
            "wheel",
            "--no-cache-dir",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
            str(source),
        ],
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    wheel = next(wheelhouse.glob("carbon-0.9.0-*.whl"))
    wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert wheel.name.startswith("carbon-0.9.0-")
    assert wheel.name.endswith(".whl")
    assert len(wheel_sha256) == 64
    assert all(character in "0123456789abcdef" for character in wheel_sha256)
    print(f"fresh A11 wheel {wheel.name} sha256:{wheel_sha256}")
    environment = tmp_path / "venv"
    create = subprocess.run(
        [sys.executable, "-m", "venv", str(environment)],
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert create.returncode == 0, create.stderr
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    install = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == wheel_sha256
    outside = tmp_path / "outside"
    outside.mkdir()
    script = f"""
import copy
import dataclasses
import importlib
import importlib.abc
import importlib.metadata
import pathlib
import pickle
import sys

stdlib_dataclass_apis = (
    dataclasses.is_dataclass,
    dataclasses.asdict,
    dataclasses.astuple,
    dataclasses.replace,
)

blocked_roots = {{
    'aiohttp', 'bittensor', 'docker', 'fastapi', 'flask', 'jax', 'neuralop',
    'numpy', 'opentelemetry', 'pandas', 'physicsnemo', 'prometheus_client',
    'pydantic', 'requests', 'scipy', 'sklearn', 'statsd', 'torch', 'yaml',
}}
blocked_carbon = (
    'carbon.audit', 'carbon.chain', 'carbon.emission', 'carbon.evaluation',
    'carbon.landscape', 'carbon.leaderboard', 'carbon.logging_utils',
    'carbon.mcp', 'carbon.miner', 'carbon.qualification', 'carbon.traineval',
    'carbon.validator',
)
attempted = []

class DependencyBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        del path, target
        root = fullname.partition('.')[0]
        if root in blocked_roots or any(
            fullname == prefix or fullname.startswith(prefix + '.')
            for prefix in blocked_carbon
        ):
            attempted.append(fullname)
            raise ModuleNotFoundError(
                f'blocked dependency: {{fullname}}', name=fullname
            )
        return None

sys.meta_path.insert(0, DependencyBlocker())
module = importlib.import_module('carbon.observability')
from carbon.fees import SubmissionId, SubmissionState

assert all(
    current is original
    for current, original in zip(
        (
            dataclasses.is_dataclass,
            dataclasses.asdict,
            dataclasses.astuple,
            dataclasses.replace,
        ),
        stdlib_dataclass_apis,
        strict=True,
    )
)

def assert_dataclass_apis_blocked(value, forbidden_text=None):
    assert dataclasses.is_dataclass(value) is False
    assert dataclasses.is_dataclass(type(value)) is False
    for operation in (
        dataclasses.asdict,
        dataclasses.astuple,
        dataclasses.replace,
    ):
        sentinel = object()
        result = sentinel
        try:
            result = operation(value)
        except TypeError as error:
            if forbidden_text is not None:
                assert forbidden_text not in str(error)
                assert forbidden_text not in repr(error)
                assert forbidden_text not in error.args
        else:
            raise AssertionError('generic dataclass operation returned an A11 value')
        assert result is sentinel

assert importlib.metadata.version('carbon') == '0.9.0'
requirements = importlib.metadata.requires('carbon') or ()
assert all('extra ==' in requirement.lower() for requirement in requirements)
assert module.__all__ == {PUBLIC_EXPORTS!r}
assert tuple(getattr(module, name).__name__ for name in module.__all__) == module.__all__
assert {str(source)!r} not in str(pathlib.Path(module.__file__).resolve())
assert attempted == []
assert not any(
    name.partition('.')[0] in blocked_roots
    or any(name == prefix or name.startswith(prefix + '.') for prefix in blocked_carbon)
    for name in sys.modules
)

class EventSink:
    def __init__(self):
        self.events = []
    def emit_event(self, event, /):
        self.events.append(event)

class MetricSink:
    def __init__(self):
        self.counters = []
        self.durations = []
    def increment_counter(self, metric, /):
        self.counters.append(metric)
    def observe_duration(self, metric, /):
        self.durations.append(metric)

event_sink = EventSink()
metric_sink = MetricSink()
limits = module.ObservabilityResourceLimits(1)
service = module.ObservabilityService(
    event_sink, metric_sink, limits
)
submission_text = {SUBMISSION_ID_TEXT!r}
event = module.ObservabilityEvent(
    module.EventKind.SUBMIT,
    SubmissionId(submission_text),
    SubmissionState.RECEIVED,
    None,
)
boundary = module.BoundaryErrorEvent(module.BoundaryErrorKind.MCP_REQUEST)
assert_dataclass_apis_blocked(event, submission_text)
assert_dataclass_apis_blocked(boundary)
assert_dataclass_apis_blocked(limits)
assert service.emit_event(event) is None
assert service.emit_event(boundary) is None
assert service.increment_counter(module.MetricKind.SUBMIT_COUNT) is None
assert service.observe_duration(module.DurationStage.SUBMIT, 0) is None
assert len(event_sink.events) == 2
assert event_sink.events[0] is not event
assert event_sink.events[1] is not boundary
assert type(event_sink.events[0]) is module.SubmissionEventSnapshot
assert type(event_sink.events[1]) is module.BoundaryErrorSnapshot
assert event_sink.events[0].kind == 'SUBMIT'
assert event_sink.events[0].submission_id == submission_text
assert event_sink.events[0].submission_state == 'RECEIVED'
assert event_sink.events[0].score_status is None
assert event_sink.events[1].error_code == 'mcp.request.invalid'
assert_dataclass_apis_blocked(event_sink.events[0], submission_text)
assert_dataclass_apis_blocked(event_sink.events[1])
owned_limits = object.__getattribute__(service, '_limits')
assert type(owned_limits) is module.ObservabilityResourceLimits
assert owned_limits is not limits
assert_dataclass_apis_blocked(owned_limits)
assert len(metric_sink.counters) == 1
assert type(metric_sink.counters[0]) is module.CounterMetricSnapshot
assert metric_sink.counters[0].metric_name == 'SUBMIT_COUNT'
assert len(metric_sink.durations) == 1
assert type(metric_sink.durations[0]) is module.DurationMetricSnapshot
assert metric_sink.durations[0].stage == 'SUBMIT'
assert metric_sink.durations[0].duration_ns == 0

snapshots = (
    module.SubmissionEventSnapshot('SUBMIT', submission_text, 'RECEIVED', None),
    module.BoundaryErrorSnapshot('mcp.request.invalid'),
    module.CounterMetricSnapshot('SUBMIT_COUNT'),
    module.DurationMetricSnapshot('SUBMIT', 0),
)
for snapshot in snapshots:
    assert_dataclass_apis_blocked(snapshot, submission_text)
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        try:
            operation(snapshot)
        except TypeError:
            pass
        else:
            raise AssertionError('snapshot generic copy or pickle succeeded')

for operation in (
    lambda: module.SubmissionEventSnapshot('SUBMIT', 'invalid', 'RECEIVED', None),
    lambda: module.BoundaryErrorSnapshot('unknown'),
    lambda: module.CounterMetricSnapshot('STAGE_DURATION_NS'),
    lambda: module.DurationMetricSnapshot('SUBMIT', -1),
):
    try:
        operation()
    except module.ObservabilityRequestError:
        pass
    else:
        raise AssertionError('invalid snapshot constructor succeeded')

failed_initialization_cases = (
    (
        module.SubmissionEventSnapshot,
        ('SUBMIT', submission_text, 'RECEIVED', None),
        ('INVALID', submission_text, 'RECEIVED', None),
    ),
    (
        module.BoundaryErrorSnapshot,
        ('mcp.request.invalid',),
        ('invalid',),
    ),
    (
        module.CounterMetricSnapshot,
        ('SUBMIT_COUNT',),
        ('INVALID',),
    ),
    (
        module.DurationMetricSnapshot,
        ('SUBMIT', 0),
        ('INVALID_STAGE', 0),
    ),
)
for snapshot_type, valid_args, invalid_args in failed_initialization_cases:
    snapshot = snapshot_type.__new__(snapshot_type, *valid_args)
    try:
        snapshot_type.__init__(snapshot, *invalid_args)
    except module.ObservabilityRequestError:
        pass
    else:
        raise AssertionError('invalid retained snapshot initialization succeeded')
    try:
        snapshot_type.__init__(snapshot, *valid_args)
    except module.ObservabilityRequestError:
        pass
    else:
        raise AssertionError('failed snapshot initialization allowed re-entry')

first = event_sink.events[0]
object.__setattr__(first, 'kind', 'REJECT')
assert service.emit_event(event) is None
assert event_sink.events[-1] is not first
assert event_sink.events[-1].kind == 'SUBMIT'
"""
    imported = subprocess.run(
        [str(python), "-I", "-c", script],
        cwd=outside,
        env=environment_values,
        check=False,
        capture_output=True,
        text=True,
    )
    assert imported.returncode == 0, imported.stderr
