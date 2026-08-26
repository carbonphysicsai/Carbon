"""Closed immutable values for bounded in-process operational observability."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import NoReturn

from carbon.fees import SubmissionId, SubmissionState
from carbon.scoring import ScoreStatus

_UINT64_MAX = (1 << 64) - 1


def _reject_state(value: object) -> None:
    del value
    raise TypeError("Observability values do not support generic serialization")


def _reject_reduce(value: object, protocol: int) -> object:
    del value, protocol
    raise TypeError("Observability values do not support generic serialization")


def _reject_copy(value: object) -> object:
    del value
    raise TypeError("Observability values do not support generic copying")


def _reject_deepcopy(value: object, memo: object) -> object:
    del value, memo
    raise TypeError("Observability values do not support generic copying")


class _NoSerialization:
    __slots__ = ()

    __getstate__ = _reject_state
    __reduce__ = _reject_state
    __reduce_ex__ = _reject_reduce
    __copy__ = _reject_copy
    __deepcopy__ = _reject_deepcopy


class _FixedLiteral:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        object.__setattr__(self, "_value", value)

    def __get__(self, instance: object, owner: type[object]) -> str:
        del instance, owner
        return object.__getattribute__(self, "_value")

    def __set__(self, instance: object, value: object) -> None:
        del instance, value
        raise AttributeError("Observability error payload is read-only")

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("Observability error payload is read-only")


def _get_error_attribute(value: BaseException, name: str) -> object:
    if name == "__dict__":
        raise AttributeError("Observability errors have no public instance dictionary")
    return BaseException.__getattribute__(value, name)


def _set_error_attribute(value: BaseException, name: str, item: object) -> None:
    if name in {
        "__cause__",
        "__context__",
        "__suppress_context__",
        "__traceback__",
    }:
        BaseException.__setattr__(value, name, item)
        return
    raise AttributeError("Observability error payload is read-only")


def _delete_error_attribute(value: BaseException, name: str) -> None:
    del value, name
    raise AttributeError("Observability error payload is read-only")


class ObservabilityError(Exception):
    """Common fixed, non-diagnostic A11 failure boundary."""

    __slots__ = ()

    @property
    def __dict__(self) -> object:
        raise AttributeError("Observability errors have no public instance dictionary")

    def __init__(self) -> None:
        Exception.__init__(self)

    def add_note(self, note: str) -> None:
        del note
        raise AttributeError("Observability error payload is read-only")

    __getattribute__ = _get_error_attribute
    __setattr__ = _set_error_attribute
    __delattr__ = _delete_error_attribute
    __getstate__ = _reject_state
    __reduce__ = _reject_state
    __reduce_ex__ = _reject_reduce
    __copy__ = _reject_copy
    __deepcopy__ = _reject_deepcopy


class ObservabilityRequestError(ObservabilityError):
    """Stable failure for an invalid observability request."""

    __slots__ = ()
    code = _FixedLiteral("observability.request.invalid")
    message = _FixedLiteral("Observability request is invalid.")

    def __init__(self) -> None:
        Exception.__init__(self, self.message)


class ObservabilityResourceError(ObservabilityError):
    """Stable failure for exceeded observability call capacity."""

    __slots__ = ()
    code = _FixedLiteral("observability.resource.exhausted")
    message = _FixedLiteral("Observability resource limit was exceeded.")

    def __init__(self) -> None:
        Exception.__init__(self, self.message)


class ObservabilityIntegrationError(ObservabilityError):
    """Stable failure for an invalid or failed observability sink."""

    __slots__ = ()
    code = _FixedLiteral("observability.integration.failed")
    message = _FixedLiteral("Observability sink failed.")

    def __init__(self) -> None:
        Exception.__init__(self, self.message)


def _raise_clean(error: ObservabilityError) -> NoReturn:
    """Raise a fresh fixed error without retaining ambient exception state."""

    try:
        raise error
    except ObservabilityError:
        BaseException.__setattr__(error, "__cause__", None)
        BaseException.__setattr__(error, "__context__", None)
        BaseException.__setattr__(error, "__suppress_context__", True)
        raise


def _raise_request_error() -> NoReturn:
    _raise_clean(ObservabilityRequestError())


def _raise_resource_error() -> NoReturn:
    _raise_clean(ObservabilityResourceError())


def _raise_integration_error() -> NoReturn:
    _raise_clean(ObservabilityIntegrationError())


class EventKind(str, Enum):
    """Closed submission-event vocabulary."""

    SUBMIT = "SUBMIT"
    SCORE = "SCORE"
    REJECT = "REJECT"
    FAILED_STRATEGY = "FAILED_STRATEGY"
    FAILED_INFRA = "FAILED_INFRA"


class MetricKind(str, Enum):
    """Closed metric vocabulary."""

    SUBMIT_COUNT = "SUBMIT_COUNT"
    SCORE_COUNT = "SCORE_COUNT"
    REJECT_COUNT = "REJECT_COUNT"
    FAILED_INFRA_COUNT = "FAILED_INFRA_COUNT"
    STAGE_DURATION_NS = "STAGE_DURATION_NS"


class DurationStage(str, Enum):
    """Closed duration-stage vocabulary."""

    SUBMIT = "SUBMIT"
    SCORE = "SCORE"


class BoundaryErrorKind(str, Enum):
    """Closed projection of already-translated A9 and A10 boundary failures."""

    MCP_REQUEST = "mcp.request.invalid"
    MCP_RESOURCE = "mcp.resource_limit_exceeded"
    MCP_TOOL_UNAVAILABLE = "mcp.tool_unavailable"
    MCP_CHALLENGE_UNAVAILABLE = "mcp.challenge_unavailable"
    MCP_SUBMISSION_UNAVAILABLE = "mcp.submission_unavailable"
    MCP_QUERY_BUDGET = "mcp.query_budget_exceeded"
    MCP_INTEGRATION = "mcp.integration_failure"
    LEADERBOARD_REQUEST = "leaderboard.request.invalid"
    LEADERBOARD_RESOURCE = "leaderboard.resource.exhausted"
    LEADERBOARD_UNAVAILABLE = "leaderboard.fixture.unavailable"
    LEADERBOARD_INTEGRATION = "leaderboard.integration.failed"


_EVENT_KIND_MEMBERS = (
    (EventKind.SUBMIT, "SUBMIT", "SUBMIT"),
    (EventKind.SCORE, "SCORE", "SCORE"),
    (EventKind.REJECT, "REJECT", "REJECT"),
    (EventKind.FAILED_STRATEGY, "FAILED_STRATEGY", "FAILED_STRATEGY"),
    (EventKind.FAILED_INFRA, "FAILED_INFRA", "FAILED_INFRA"),
)
_METRIC_KIND_MEMBERS = (
    (MetricKind.SUBMIT_COUNT, "SUBMIT_COUNT", "SUBMIT_COUNT"),
    (MetricKind.SCORE_COUNT, "SCORE_COUNT", "SCORE_COUNT"),
    (MetricKind.REJECT_COUNT, "REJECT_COUNT", "REJECT_COUNT"),
    (
        MetricKind.FAILED_INFRA_COUNT,
        "FAILED_INFRA_COUNT",
        "FAILED_INFRA_COUNT",
    ),
    (
        MetricKind.STAGE_DURATION_NS,
        "STAGE_DURATION_NS",
        "STAGE_DURATION_NS",
    ),
)
_DURATION_STAGE_MEMBERS = (
    (DurationStage.SUBMIT, "SUBMIT", "SUBMIT"),
    (DurationStage.SCORE, "SCORE", "SCORE"),
)
_BOUNDARY_ERROR_KIND_MEMBERS = (
    (BoundaryErrorKind.MCP_REQUEST, "MCP_REQUEST", "mcp.request.invalid"),
    (
        BoundaryErrorKind.MCP_RESOURCE,
        "MCP_RESOURCE",
        "mcp.resource_limit_exceeded",
    ),
    (
        BoundaryErrorKind.MCP_TOOL_UNAVAILABLE,
        "MCP_TOOL_UNAVAILABLE",
        "mcp.tool_unavailable",
    ),
    (
        BoundaryErrorKind.MCP_CHALLENGE_UNAVAILABLE,
        "MCP_CHALLENGE_UNAVAILABLE",
        "mcp.challenge_unavailable",
    ),
    (
        BoundaryErrorKind.MCP_SUBMISSION_UNAVAILABLE,
        "MCP_SUBMISSION_UNAVAILABLE",
        "mcp.submission_unavailable",
    ),
    (
        BoundaryErrorKind.MCP_QUERY_BUDGET,
        "MCP_QUERY_BUDGET",
        "mcp.query_budget_exceeded",
    ),
    (
        BoundaryErrorKind.MCP_INTEGRATION,
        "MCP_INTEGRATION",
        "mcp.integration_failure",
    ),
    (
        BoundaryErrorKind.LEADERBOARD_REQUEST,
        "LEADERBOARD_REQUEST",
        "leaderboard.request.invalid",
    ),
    (
        BoundaryErrorKind.LEADERBOARD_RESOURCE,
        "LEADERBOARD_RESOURCE",
        "leaderboard.resource.exhausted",
    ),
    (
        BoundaryErrorKind.LEADERBOARD_UNAVAILABLE,
        "LEADERBOARD_UNAVAILABLE",
        "leaderboard.fixture.unavailable",
    ),
    (
        BoundaryErrorKind.LEADERBOARD_INTEGRATION,
        "LEADERBOARD_INTEGRATION",
        "leaderboard.integration.failed",
    ),
)
_SUBMISSION_STATE_MEMBERS = (
    (SubmissionState.RECEIVED, "RECEIVED", "RECEIVED"),
    (SubmissionState.VALIDATED, "VALIDATED", "VALIDATED"),
    (SubmissionState.QUEUED, "QUEUED", "QUEUED"),
    (SubmissionState.RUNNING, "RUNNING", "RUNNING"),
    (SubmissionState.SCORED, "SCORED", "SCORED"),
    (SubmissionState.PUBLISHED, "PUBLISHED", "PUBLISHED"),
    (SubmissionState.REJECTED, "REJECTED", "REJECTED"),
    (SubmissionState.FAILED_INFRA, "FAILED_INFRA", "FAILED_INFRA"),
    (SubmissionState.FAILED_STRATEGY, "FAILED_STRATEGY", "FAILED_STRATEGY"),
    (SubmissionState.CANCELLED, "CANCELLED", "CANCELLED"),
)
_SCORE_STATUS_MEMBERS = (
    (ScoreStatus.SCORED, "SCORED", "SCORED"),
    (
        ScoreStatus.MANDATORY_GATE_FAILED,
        "MANDATORY_GATE_FAILED",
        "MANDATORY_GATE_FAILED",
    ),
    (ScoreStatus.PACK_NOT_READY, "PACK_NOT_READY", "PACK_NOT_READY"),
)


def _enum_definition_is_exact(
    enum_type: type[Enum],
    expected: tuple[tuple[Enum, str, str], ...],
) -> bool:
    invalid = False
    bases: tuple[type[object], ...] = ()
    items: tuple[tuple[object, object], ...] = ()
    iterated: tuple[object, ...] = ()
    resolved: tuple[object, ...] = ()
    try:
        bases = type.__getattribute__(enum_type, "__bases__")
        items = tuple(enum_type.__members__.items())
        iterated = tuple(enum_type)
        resolved = tuple(enum_type(literal) for _, _, literal in expected)
    except Exception:  # noqa: BLE001 - fail closed on damaged local enum state
        invalid = True
    if (
        invalid
        or len(bases) != 2
        or bases[0] is not str
        or bases[1] is not Enum
        or len(items) != len(expected)
        or len(iterated) != len(expected)
        or len(resolved) != len(expected)
    ):
        return False
    for (
        (actual_name, actual_member),
        iterated_member,
        resolved_member,
        (
            member,
            name,
            literal,
        ),
    ) in zip(
        items,
        iterated,
        resolved,
        expected,
        strict=True,
    ):
        current_name: object = None
        current_value: object = None
        try:
            current_name = object.__getattribute__(member, "name")
            current_value = object.__getattribute__(member, "value")
        except Exception:  # noqa: BLE001 - reject damaged canonical members
            invalid = True
        if (
            invalid
            or type(actual_name) is not str
            or actual_name != name
            or actual_member is not member
            or iterated_member is not member
            or resolved_member is not member
            or type(current_name) is not str
            or current_name != name
            or type(current_value) is not str
            or current_value != literal
        ):
            return False
    return True


def _copy_owned_enum_member(
    value: object,
    enum_type: type[Enum],
    expected: tuple[tuple[Enum, str, str], ...],
) -> Enum:
    if type(value) is not enum_type:
        _raise_request_error()
    for member, name, literal in expected:
        if value is not member:
            continue
        invalid = False
        current_name: object = None
        current_value: object = None
        try:
            current_name = object.__getattribute__(member, "name")
            current_value = object.__getattribute__(member, "value")
        except Exception:  # noqa: BLE001 - reject damaged owner enum state
            invalid = True
        if (
            not invalid
            and type(current_name) is str
            and current_name == name
            and type(current_value) is str
            and current_value == literal
        ):
            return member
        break
    _raise_request_error()


def _copy_local_enum_member(
    value: object,
    enum_type: type[Enum],
    expected: tuple[tuple[Enum, str, str], ...],
) -> Enum:
    if not _enum_definition_is_exact(enum_type, expected):
        _raise_request_error()
    return _copy_owned_enum_member(value, enum_type, expected)


def _copy_event_kind(value: object) -> EventKind:
    return _copy_local_enum_member(  # type: ignore[return-value]
        value, EventKind, _EVENT_KIND_MEMBERS
    )


def _copy_submission_state(value: object) -> SubmissionState:
    return _copy_owned_enum_member(  # type: ignore[return-value]
        value, SubmissionState, _SUBMISSION_STATE_MEMBERS
    )


def _copy_score_status(value: object) -> ScoreStatus:
    return _copy_owned_enum_member(  # type: ignore[return-value]
        value, ScoreStatus, _SCORE_STATUS_MEMBERS
    )


def _copy_boundary_error_kind(value: object) -> BoundaryErrorKind:
    return _copy_local_enum_member(  # type: ignore[return-value]
        value, BoundaryErrorKind, _BOUNDARY_ERROR_KIND_MEMBERS
    )


def _copy_submission_id(value: object) -> SubmissionId:
    if type(value) is not SubmissionId:
        _raise_request_error()

    invalid = False
    raw_value: object = None
    try:
        raw_value = object.__getattribute__(value, "value")
    except Exception:  # noqa: BLE001 - normalize a damaged exact owner nominal
        invalid = True
    if invalid or type(raw_value) is not str:
        _raise_request_error()

    owned: SubmissionId | None = None
    try:
        owned = SubmissionId(raw_value)
    except Exception:  # noqa: BLE001 - normalize owner-constructor rejection
        invalid = True
    if invalid or type(owned) is not SubmissionId or owned is value:
        _raise_request_error()

    copied_value: object = None
    try:
        copied_value = object.__getattribute__(owned, "value")
    except Exception:  # noqa: BLE001 - reject a damaged owner constructor result
        invalid = True
    if invalid or type(copied_value) is not str or copied_value != raw_value:
        _raise_request_error()
    return owned


def _require_positive_u64(value: object) -> int:
    if type(value) is not int or not 1 <= value <= _UINT64_MAX:
        _raise_request_error()
    return value


def _require_duration_ns(value: object) -> int:
    """Validate one caller-supplied descriptive duration."""

    if type(value) is not int or not 0 <= value <= _UINT64_MAX:
        _raise_request_error()
    return value


@dataclass(frozen=True, slots=True, repr=False)
class ObservabilityEvent(_NoSerialization):
    """Owner-shaped request that makes no record or provenance claim."""

    kind: EventKind
    submission_id: SubmissionId = field(repr=False)
    submission_state: SubmissionState
    score_status: ScoreStatus | None

    def __post_init__(self) -> None:
        if type(self) is not ObservabilityEvent:
            _raise_request_error()

        invalid = False
        kind_value: object = None
        submission_id_value: object = None
        submission_state_value: object = None
        score_status_value: object = None
        try:
            kind_value = object.__getattribute__(self, "kind")
            submission_id_value = object.__getattribute__(self, "submission_id")
            submission_state_value = object.__getattribute__(self, "submission_state")
            score_status_value = object.__getattribute__(self, "score_status")
        except Exception:  # noqa: BLE001 - normalize a damaged exact A11 nominal
            invalid = True
        if invalid:
            _raise_request_error()

        kind = _copy_event_kind(kind_value)
        submission_id = _copy_submission_id(submission_id_value)
        submission_state = _copy_submission_state(submission_state_value)
        score_status = (
            None
            if score_status_value is None
            else _copy_score_status(score_status_value)
        )
        if not _event_matrix_accepts(kind, submission_state, score_status):
            _raise_request_error()

        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "submission_id", submission_id)
        object.__setattr__(self, "submission_state", submission_state)
        object.__setattr__(self, "score_status", score_status)

    def __repr__(self) -> str:
        return "ObservabilityEvent(<private>)"


def _event_matrix_accepts(
    kind: EventKind,
    submission_state: SubmissionState,
    score_status: ScoreStatus | None,
) -> bool:
    if kind is _EVENT_KIND_MEMBERS[0][0]:
        return (
            submission_state is _SUBMISSION_STATE_MEMBERS[0][0] and score_status is None
        )
    if kind is _EVENT_KIND_MEMBERS[1][0]:
        return submission_state is _SUBMISSION_STATE_MEMBERS[4][0] and (
            score_status is _SCORE_STATUS_MEMBERS[0][0]
            or score_status is _SCORE_STATUS_MEMBERS[1][0]
        )
    if kind is _EVENT_KIND_MEMBERS[2][0]:
        return (
            submission_state is _SUBMISSION_STATE_MEMBERS[6][0] and score_status is None
        )
    if kind is _EVENT_KIND_MEMBERS[3][0]:
        return (
            submission_state is _SUBMISSION_STATE_MEMBERS[8][0] and score_status is None
        )
    if kind is _EVENT_KIND_MEMBERS[4][0]:
        return (
            submission_state is _SUBMISSION_STATE_MEMBERS[7][0] and score_status is None
        )
    return False


def _copy_observability_event(value: object) -> ObservabilityEvent:
    """Positively reconstruct one exact sink-safe submission event."""

    if type(value) is not ObservabilityEvent:
        _raise_request_error()
    invalid = False
    captured: list[object] = []
    try:
        captured = [
            object.__getattribute__(value, "kind"),
            object.__getattribute__(value, "submission_id"),
            object.__getattribute__(value, "submission_state"),
            object.__getattribute__(value, "score_status"),
        ]
    except Exception:  # noqa: BLE001 - normalize a damaged exact A11 nominal
        invalid = True
    if invalid:
        _raise_request_error()
    return ObservabilityEvent(*captured)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True, repr=False)
class BoundaryErrorEvent(_NoSerialization):
    """Closed observation of an already-translated A9 or A10 failure."""

    error_kind: BoundaryErrorKind

    def __post_init__(self) -> None:
        if type(self) is not BoundaryErrorEvent:
            _raise_request_error()
        invalid = False
        error_kind_value: object = None
        try:
            error_kind_value = object.__getattribute__(self, "error_kind")
        except Exception:  # noqa: BLE001 - normalize a damaged exact A11 nominal
            invalid = True
        if invalid:
            _raise_request_error()
        object.__setattr__(
            self, "error_kind", _copy_boundary_error_kind(error_kind_value)
        )

    def __repr__(self) -> str:
        return "BoundaryErrorEvent(<private>)"


def _copy_boundary_error_event(value: object) -> BoundaryErrorEvent:
    """Positively reconstruct one exact sink-safe boundary-error event."""

    if type(value) is not BoundaryErrorEvent:
        _raise_request_error()
    invalid = False
    error_kind_value: object = None
    try:
        error_kind_value = object.__getattribute__(value, "error_kind")
    except Exception:  # noqa: BLE001 - normalize a damaged exact A11 nominal
        invalid = True
    if invalid:
        _raise_request_error()
    return BoundaryErrorEvent(error_kind_value)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True, repr=False)
class ObservabilityResourceLimits(_NoSerialization):
    """Mandatory finite per-service call-capacity policy."""

    max_concurrent_calls: int

    def __post_init__(self) -> None:
        if type(self) is not ObservabilityResourceLimits:
            _raise_request_error()
        invalid = False
        max_concurrent_calls_value: object = None
        try:
            max_concurrent_calls_value = object.__getattribute__(
                self, "max_concurrent_calls"
            )
        except Exception:  # noqa: BLE001 - normalize a damaged exact A11 nominal
            invalid = True
        if invalid:
            _raise_request_error()
        object.__setattr__(
            self,
            "max_concurrent_calls",
            _require_positive_u64(max_concurrent_calls_value),
        )

    def __repr__(self) -> str:
        return "ObservabilityResourceLimits(<private>)"


def _copy_resource_limits(value: object) -> ObservabilityResourceLimits:
    """Positively reconstruct one exact service resource policy."""

    if type(value) is not ObservabilityResourceLimits:
        _raise_request_error()
    invalid = False
    max_concurrent_calls_value: object = None
    try:
        max_concurrent_calls_value = object.__getattribute__(
            value, "max_concurrent_calls"
        )
    except Exception:  # noqa: BLE001 - normalize a damaged exact A11 nominal
        invalid = True
    if invalid:
        _raise_request_error()
    return ObservabilityResourceLimits(  # type: ignore[arg-type]
        max_concurrent_calls_value
    )


def _copy_counter_metric(value: object) -> MetricKind:
    """Validate one of the exact four counter members."""

    metric = _copy_local_enum_member(value, MetricKind, _METRIC_KIND_MEMBERS)
    if not any(metric is member for member, _, _ in _METRIC_KIND_MEMBERS[:4]):
        _raise_request_error()
    return metric  # type: ignore[return-value]


def _copy_duration_stage(value: object) -> DurationStage:
    """Validate one exact descriptive duration stage."""

    return _copy_local_enum_member(  # type: ignore[return-value]
        value, DurationStage, _DURATION_STAGE_MEMBERS
    )
