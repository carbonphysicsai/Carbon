"""Closed immutable values for bounded in-process operational observability."""

from __future__ import annotations

from enum import Enum
from threading import Lock
from typing import NoReturn, Self
from weakref import ReferenceType, ref

from carbon.fees import SubmissionId, SubmissionState
from carbon.scoring import ScoreStatus

_UINT64_MAX = (1 << 64) - 1
_OBSERVABILITY_EVENT_FIELDS = (
    "kind",
    "submission_id",
    "submission_state",
    "score_status",
)
_BOUNDARY_ERROR_EVENT_FIELDS = ("error_kind",)
_RESOURCE_LIMIT_FIELDS = ("max_concurrent_calls",)
_SUBMISSION_EVENT_SNAPSHOT_FIELDS = (
    "kind",
    "submission_id",
    "submission_state",
    "score_status",
)
_BOUNDARY_ERROR_SNAPSHOT_FIELDS = ("error_code",)
_COUNTER_METRIC_SNAPSHOT_FIELDS = ("metric_name",)
_DURATION_METRIC_SNAPSHOT_FIELDS = ("stage", "duration_ns")
_SNAPSHOT_ALLOCATION_ELIGIBILITY: dict[int, ReferenceType[object]] = {}
_SNAPSHOT_ALLOCATION_LOCK = Lock()


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

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("Observability values are immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("Observability values are immutable")

    __getstate__ = _reject_state
    __reduce__ = _reject_state
    __reduce_ex__ = _reject_reduce
    __copy__ = _reject_copy
    __deepcopy__ = _reject_deepcopy


class _SnapshotNoSerialization(_NoSerialization):
    __slots__ = ("__weakref__",)


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


def _require_uninitialized(value: object, field_names: tuple[str, ...]) -> None:
    """Reject reinitialization or partially forged nominal values."""

    for field_name in field_names:
        try:
            object.__getattribute__(value, field_name)
        except AttributeError:
            continue
        except Exception:  # noqa: BLE001 - normalize damaged slot descriptors
            _raise_request_error()
        _raise_request_error()


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
_BOUNDARY_ERROR_LITERALS = tuple(
    literal for _, _, literal in _BOUNDARY_ERROR_KIND_MEMBERS
)
_COUNTER_METRIC_LITERALS = tuple(literal for _, _, literal in _METRIC_KIND_MEMBERS[:4])
_DURATION_STAGE_LITERALS = tuple(literal for _, _, literal in _DURATION_STAGE_MEMBERS)


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


def _allocate_snapshot(
    snapshot_type: type[object],
    expected_type: type[object],
) -> object:
    """Allocate one direct-construction snapshot with no caller token."""

    if snapshot_type is not expected_type:
        _raise_request_error()
    value = object.__new__(snapshot_type)
    identity = id(value)

    def clear_eligibility(reference: ReferenceType[object]) -> None:
        with _SNAPSHOT_ALLOCATION_LOCK:
            if _SNAPSHOT_ALLOCATION_ELIGIBILITY.get(identity) is reference:
                _SNAPSHOT_ALLOCATION_ELIGIBILITY.pop(identity, None)

    reference = ref(value, clear_eligibility)
    with _SNAPSHOT_ALLOCATION_LOCK:
        _SNAPSHOT_ALLOCATION_ELIGIBILITY[identity] = reference
    return value


def _require_snapshot_initialization(
    value: object,
    field_names: tuple[str, ...],
) -> None:
    """Consume private allocation eligibility before validating any fields."""

    with _SNAPSHOT_ALLOCATION_LOCK:
        reference = _SNAPSHOT_ALLOCATION_ELIGIBILITY.pop(id(value), None)
    if reference is None or reference() is not value:
        _raise_request_error()
    for field_name in field_names:
        try:
            object.__getattribute__(value, field_name)
        except AttributeError:
            continue
        except Exception:  # noqa: BLE001 - normalize damaged slot descriptors
            _raise_request_error()
        _raise_request_error()


def _validated_submission_id_text(value: object) -> str:
    """Reconstruct one canonical UUIDv4 through A7 and return only its text."""

    if type(value) is not str or str.__len__(value) != 36 or not str.isascii(value):
        _raise_request_error()
    invalid = False
    owned: SubmissionId | None = None
    try:
        owned = SubmissionId(value)
    except Exception:  # noqa: BLE001 - normalize public A7 constructor rejection
        invalid = True
    copied_value: object = None
    if not invalid and type(owned) is SubmissionId:
        try:
            copied_value = object.__getattribute__(owned, "value")
        except Exception:  # noqa: BLE001 - reject a damaged owner result
            invalid = True
    else:
        invalid = True
    if (
        invalid
        or type(copied_value) is not str
        or copied_value != value
        or str.__len__(copied_value) != 36
        or not str.isascii(copied_value)
    ):
        _raise_request_error()
    return copied_value


def _snapshot_event_matrix_accepts(
    kind: str,
    submission_state: str,
    score_status: str | None,
) -> bool:
    if kind == "SUBMIT":
        return submission_state == "RECEIVED" and score_status is None
    if kind == "SCORE":
        return submission_state == "SCORED" and (
            score_status == "SCORED" or score_status == "MANDATORY_GATE_FAILED"
        )
    if kind == "REJECT":
        return submission_state == "REJECTED" and score_status is None
    if kind == "FAILED_STRATEGY":
        return submission_state == "FAILED_STRATEGY" and score_status is None
    if kind == "FAILED_INFRA":
        return submission_state == "FAILED_INFRA" and score_status is None
    return False


class SubmissionEventSnapshot(_SnapshotNoSerialization):
    """Primitive-only sink snapshot for one validated submission event."""

    __slots__ = _SUBMISSION_EVENT_SNAPSHOT_FIELDS

    kind: str
    submission_id: str
    submission_state: str
    score_status: str | None

    def __new__(
        cls,
        kind: str,
        submission_id: str,
        submission_state: str,
        score_status: str | None,
    ) -> Self:
        del kind, submission_id, submission_state, score_status
        return _allocate_snapshot(  # type: ignore[return-value]
            cls,
            SubmissionEventSnapshot,
        )

    def __init__(
        self,
        kind: str,
        submission_id: str,
        submission_state: str,
        score_status: str | None,
    ) -> None:
        if type(self) is not SubmissionEventSnapshot:
            _raise_request_error()
        _require_snapshot_initialization(
            self,
            _SUBMISSION_EVENT_SNAPSHOT_FIELDS,
        )
        if (
            type(kind) is not str
            or type(submission_state) is not str
            or (score_status is not None and type(score_status) is not str)
            or not _snapshot_event_matrix_accepts(
                kind,
                submission_state,
                score_status,
            )
        ):
            _raise_request_error()
        owned_submission_id = _validated_submission_id_text(submission_id)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "submission_id", owned_submission_id)
        object.__setattr__(self, "submission_state", submission_state)
        object.__setattr__(self, "score_status", score_status)

    def __repr__(self) -> str:
        return "SubmissionEventSnapshot(<private>)"


class BoundaryErrorSnapshot(_SnapshotNoSerialization):
    """Primitive-only sink snapshot for one validated boundary error kind."""

    __slots__ = _BOUNDARY_ERROR_SNAPSHOT_FIELDS

    error_code: str

    def __new__(cls, error_code: str) -> Self:
        del error_code
        return _allocate_snapshot(  # type: ignore[return-value]
            cls,
            BoundaryErrorSnapshot,
        )

    def __init__(self, error_code: str) -> None:
        if type(self) is not BoundaryErrorSnapshot:
            _raise_request_error()
        _require_snapshot_initialization(
            self,
            _BOUNDARY_ERROR_SNAPSHOT_FIELDS,
        )
        if type(error_code) is not str or not any(
            error_code == literal for literal in _BOUNDARY_ERROR_LITERALS
        ):
            _raise_request_error()
        object.__setattr__(self, "error_code", error_code)

    def __repr__(self) -> str:
        return "BoundaryErrorSnapshot(<private>)"


class CounterMetricSnapshot(_SnapshotNoSerialization):
    """Primitive-only sink snapshot for one closed counter increment."""

    __slots__ = _COUNTER_METRIC_SNAPSHOT_FIELDS

    metric_name: str

    def __new__(cls, metric_name: str) -> Self:
        del metric_name
        return _allocate_snapshot(  # type: ignore[return-value]
            cls,
            CounterMetricSnapshot,
        )

    def __init__(self, metric_name: str) -> None:
        if type(self) is not CounterMetricSnapshot:
            _raise_request_error()
        _require_snapshot_initialization(
            self,
            _COUNTER_METRIC_SNAPSHOT_FIELDS,
        )
        if type(metric_name) is not str or not any(
            metric_name == literal for literal in _COUNTER_METRIC_LITERALS
        ):
            _raise_request_error()
        object.__setattr__(self, "metric_name", metric_name)

    def __repr__(self) -> str:
        return "CounterMetricSnapshot(<private>)"


class DurationMetricSnapshot(_SnapshotNoSerialization):
    """Primitive-only sink snapshot for one caller-supplied duration."""

    __slots__ = _DURATION_METRIC_SNAPSHOT_FIELDS

    stage: str
    duration_ns: int

    def __new__(cls, stage: str, duration_ns: int) -> Self:
        del stage, duration_ns
        return _allocate_snapshot(  # type: ignore[return-value]
            cls,
            DurationMetricSnapshot,
        )

    def __init__(self, stage: str, duration_ns: int) -> None:
        if type(self) is not DurationMetricSnapshot:
            _raise_request_error()
        _require_snapshot_initialization(
            self,
            _DURATION_METRIC_SNAPSHOT_FIELDS,
        )
        if type(stage) is not str or not any(
            stage == literal for literal in _DURATION_STAGE_LITERALS
        ):
            _raise_request_error()
        owned_duration_ns = _require_duration_ns(duration_ns)
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "duration_ns", owned_duration_ns)

    def __repr__(self) -> str:
        return "DurationMetricSnapshot(<private>)"


class ObservabilityEvent(_NoSerialization):
    """Owner-shaped request that makes no record or provenance claim."""

    __slots__ = _OBSERVABILITY_EVENT_FIELDS

    kind: EventKind
    submission_id: SubmissionId
    submission_state: SubmissionState
    score_status: ScoreStatus | None

    def __init__(
        self,
        kind: EventKind,
        submission_id: SubmissionId,
        submission_state: SubmissionState,
        score_status: ScoreStatus | None,
    ) -> None:
        if type(self) is not ObservabilityEvent:
            _raise_request_error()
        _require_uninitialized(self, _OBSERVABILITY_EVENT_FIELDS)

        owned_kind = _copy_event_kind(kind)
        owned_submission_id = _copy_submission_id(submission_id)
        owned_submission_state = _copy_submission_state(submission_state)
        owned_score_status = (
            None if score_status is None else _copy_score_status(score_status)
        )
        if not _event_matrix_accepts(
            owned_kind,
            owned_submission_state,
            owned_score_status,
        ):
            _raise_request_error()

        object.__setattr__(self, "kind", owned_kind)
        object.__setattr__(self, "submission_id", owned_submission_id)
        object.__setattr__(self, "submission_state", owned_submission_state)
        object.__setattr__(self, "score_status", owned_score_status)

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


def _literal_for_member(
    member: Enum,
    expected: tuple[tuple[Enum, str, str], ...],
) -> str:
    """Map one already-validated canonical member through fixed A11 literals."""

    for canonical, _, literal in expected:
        if member is canonical:
            return literal
    _raise_request_error()


def _submission_event_snapshot(value: object) -> SubmissionEventSnapshot:
    """Construct one fresh primitive-only snapshot from an exact request."""

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
    owned_kind = _copy_event_kind(captured[0])
    owned_submission_id = _copy_submission_id(captured[1])
    owned_submission_state = _copy_submission_state(captured[2])
    owned_score_status = (
        None if captured[3] is None else _copy_score_status(captured[3])
    )
    if not _event_matrix_accepts(
        owned_kind,
        owned_submission_state,
        owned_score_status,
    ):
        _raise_request_error()
    submission_id_text: object = None
    try:
        submission_id_text = object.__getattribute__(owned_submission_id, "value")
    except Exception:  # noqa: BLE001 - reject damaged owner reconstruction
        invalid = True
    if invalid or type(submission_id_text) is not str:
        _raise_request_error()
    return SubmissionEventSnapshot(
        _literal_for_member(owned_kind, _EVENT_KIND_MEMBERS),
        submission_id_text,
        _literal_for_member(owned_submission_state, _SUBMISSION_STATE_MEMBERS),
        (
            None
            if owned_score_status is None
            else _literal_for_member(owned_score_status, _SCORE_STATUS_MEMBERS)
        ),
    )


class BoundaryErrorEvent(_NoSerialization):
    """Closed observation of an already-translated A9 or A10 failure."""

    __slots__ = _BOUNDARY_ERROR_EVENT_FIELDS

    error_kind: BoundaryErrorKind

    def __init__(self, error_kind: BoundaryErrorKind) -> None:
        if type(self) is not BoundaryErrorEvent:
            _raise_request_error()
        _require_uninitialized(self, _BOUNDARY_ERROR_EVENT_FIELDS)
        owned_error_kind = _copy_boundary_error_kind(error_kind)
        object.__setattr__(self, "error_kind", owned_error_kind)

    def __repr__(self) -> str:
        return "BoundaryErrorEvent(<private>)"


def _boundary_error_snapshot(value: object) -> BoundaryErrorSnapshot:
    """Construct one fresh primitive-only snapshot from an exact request."""

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
    error_kind = _copy_boundary_error_kind(error_kind_value)
    return BoundaryErrorSnapshot(
        _literal_for_member(error_kind, _BOUNDARY_ERROR_KIND_MEMBERS)
    )


class ObservabilityResourceLimits(_NoSerialization):
    """Mandatory finite per-service call-capacity policy."""

    __slots__ = _RESOURCE_LIMIT_FIELDS

    max_concurrent_calls: int

    def __init__(self, max_concurrent_calls: int) -> None:
        if type(self) is not ObservabilityResourceLimits:
            _raise_request_error()
        _require_uninitialized(self, _RESOURCE_LIMIT_FIELDS)
        owned_max_concurrent_calls = _require_positive_u64(max_concurrent_calls)
        object.__setattr__(
            self,
            "max_concurrent_calls",
            owned_max_concurrent_calls,
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


def _counter_metric_snapshot(value: object) -> CounterMetricSnapshot:
    """Construct one fresh primitive-only snapshot for a closed counter."""

    metric = _copy_local_enum_member(value, MetricKind, _METRIC_KIND_MEMBERS)
    if not any(metric is member for member, _, _ in _METRIC_KIND_MEMBERS[:4]):
        _raise_request_error()
    return CounterMetricSnapshot(_literal_for_member(metric, _METRIC_KIND_MEMBERS[:4]))


def _copy_duration_stage(value: object) -> DurationStage:
    """Validate one exact descriptive duration stage."""

    return _copy_local_enum_member(  # type: ignore[return-value]
        value, DurationStage, _DURATION_STAGE_MEMBERS
    )


def _duration_metric_snapshot(
    stage: object,
    duration_ns: object,
) -> DurationMetricSnapshot:
    """Construct one fresh primitive-only snapshot for a closed duration."""

    owned_stage = _copy_duration_stage(stage)
    owned_duration_ns = _require_duration_ns(duration_ns)
    return DurationMetricSnapshot(
        _literal_for_member(owned_stage, _DURATION_STAGE_MEMBERS),
        owned_duration_ns,
    )
