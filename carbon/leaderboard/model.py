"""Immutable values for the bounded fixture-only leaderboard projection."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from carbon.fees import SubmissionId
from carbon.registry import ChallengeKey, is_sha256_digest, validate_version
from carbon.scoring import ScoreStatus

_UINT64_MAX = (1 << 64) - 1
_SCHEMA_VERSION = "1.0"
_BOARD_KIND = "fixture_leaderboard"
_CURSOR_FIELDS = (
    "schema_version",
    "board_kind",
    "challenge_id",
    "challenge_version",
    "scoring_pack_hash",
    "snapshot_sequence",
    "next_offset",
)


def _reject_state(value: object) -> None:
    raise TypeError(f"{type(value).__name__} does not support generic serialization")


def _reject_reduce(value: object, protocol: int) -> object:
    del protocol
    raise TypeError(f"{type(value).__name__} does not support generic serialization")


def _reject_copy(value: object) -> object:
    raise TypeError(f"{type(value).__name__} does not support generic copying")


def _reject_deepcopy(value: object, memo: object) -> object:
    del memo
    raise TypeError(f"{type(value).__name__} does not support generic copying")


class _NoSerialization:
    __slots__ = ()

    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce
    __copy__ = _reject_copy
    __deepcopy__ = _reject_deepcopy


class _FixedLiteral:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def __get__(self, instance: object, owner: type[object]) -> str:
        del instance, owner
        return self._value

    def __set__(self, instance: object, value: object) -> None:
        del instance, value
        raise AttributeError("Leaderboard error payload is read-only")


def _set_error_attribute(value: BaseException, name: str, item: object) -> None:
    if name in {
        "__cause__",
        "__context__",
        "__suppress_context__",
        "__traceback__",
    }:
        BaseException.__setattr__(value, name, item)
        return
    raise AttributeError("Leaderboard error payload is read-only")


class LeaderboardError(Exception):
    """Common fixed, non-diagnostic A10 failure boundary."""

    __slots__ = ()

    def __init__(self) -> None:
        Exception.__init__(self)

    __setattr__ = _set_error_attribute
    __getstate__ = _reject_state
    __reduce_ex__ = _reject_reduce
    __copy__ = _reject_copy
    __deepcopy__ = _reject_deepcopy


class LeaderboardRequestError(LeaderboardError):
    """Stable failure for an invalid public leaderboard request."""

    __slots__ = ()
    code = _FixedLiteral("leaderboard.request.invalid")
    message = _FixedLiteral("Leaderboard request is invalid.")

    def __init__(self) -> None:
        Exception.__init__(self, self.message)


class LeaderboardResourceError(LeaderboardError):
    """Stable failure for an exceeded leaderboard resource limit."""

    __slots__ = ()
    code = _FixedLiteral("leaderboard.resource.exhausted")
    message = _FixedLiteral("Leaderboard resource limit was exceeded.")

    def __init__(self) -> None:
        Exception.__init__(self, self.message)


class LeaderboardUnavailableError(LeaderboardError):
    """Stable failure for unavailable retained fixture publication state."""

    __slots__ = ()
    code = _FixedLiteral("leaderboard.fixture.unavailable")
    message = _FixedLiteral("Fixture leaderboard is unavailable.")

    def __init__(self) -> None:
        Exception.__init__(self, self.message)


class LeaderboardIntegrationError(LeaderboardError):
    """Stable failure for malformed fixture-provider integration data."""

    __slots__ = ()
    code = _FixedLiteral("leaderboard.integration.failed")
    message = _FixedLiteral("Leaderboard provider response is invalid.")

    def __init__(self) -> None:
        Exception.__init__(self, self.message)


def _require_exact_u64(value: object, *, positive: bool) -> int:
    lower_bound = 1 if positive else 0
    if type(value) is not int or not lower_bound <= value <= _UINT64_MAX:
        raise LeaderboardRequestError()
    return value


def _require_exact_bool(value: object) -> bool:
    if type(value) is not bool:
        raise LeaderboardRequestError()
    return value


def _copy_challenge_key(value: object) -> ChallengeKey:
    if type(value) is not ChallengeKey:
        raise LeaderboardRequestError()

    invalid = False
    challenge_id: object = None
    version: object = None
    try:
        challenge_id = object.__getattribute__(value, "challenge_id")
        version = object.__getattribute__(value, "version")
    except Exception:  # noqa: BLE001 - capture a hostile exact owner nominal
        invalid = True
    if invalid or type(challenge_id) is not str or type(version) is not str:
        raise LeaderboardRequestError()

    owned: ChallengeKey | None = None
    try:
        owned = ChallengeKey(challenge_id, version)
    except Exception:  # noqa: BLE001 - normalize owner-constructor rejection
        invalid = True
    if invalid or type(owned) is not ChallengeKey:
        raise LeaderboardRequestError()
    return owned


def _copy_submission_id(value: object) -> SubmissionId:
    if type(value) is not SubmissionId:
        raise LeaderboardRequestError()

    invalid = False
    raw_value: object = None
    try:
        raw_value = object.__getattribute__(value, "value")
    except Exception:  # noqa: BLE001 - capture a hostile exact owner nominal
        invalid = True
    if invalid or type(raw_value) is not str:
        raise LeaderboardRequestError()

    owned: SubmissionId | None = None
    try:
        owned = SubmissionId(raw_value)
    except Exception:  # noqa: BLE001 - normalize owner-constructor rejection
        invalid = True
    if invalid or type(owned) is not SubmissionId:
        raise LeaderboardRequestError()
    return owned


def _validated_result_id(value: object) -> str:
    if type(value) is not str:
        raise LeaderboardRequestError()

    invalid = False
    validated: object = None
    try:
        validated = validate_version(value)
    except Exception:  # noqa: BLE001 - normalize owner-validator rejection
        invalid = True
    if invalid or type(validated) is not str or validated != value:
        raise LeaderboardRequestError()
    return value


def _validated_scoring_pack_hash(value: object) -> str:
    if type(value) is not str:
        raise LeaderboardRequestError()

    invalid = False
    valid: object = False
    try:
        valid = is_sha256_digest(value)
    except Exception:  # noqa: BLE001 - normalize owner-validator rejection
        invalid = True
    if invalid or valid is not True:
        raise LeaderboardRequestError()
    return value


def _copy_score_status(value: object) -> ScoreStatus:
    expected = (
        (ScoreStatus.SCORED, "SCORED", "SCORED"),
        (
            ScoreStatus.MANDATORY_GATE_FAILED,
            "MANDATORY_GATE_FAILED",
            "MANDATORY_GATE_FAILED",
        ),
        (ScoreStatus.PACK_NOT_READY, "PACK_NOT_READY", "PACK_NOT_READY"),
    )
    if type(value) is not ScoreStatus:
        raise LeaderboardRequestError()

    invalid = False
    for member, expected_name, expected_value in expected:
        if value is not member:
            continue
        current_name: object = None
        current_value: object = None
        try:
            current_name = object.__getattribute__(member, "name")
            current_value = object.__getattribute__(member, "value")
        except Exception:  # noqa: BLE001 - reject hostile enum descriptor state
            invalid = True
        if (
            not invalid
            and type(current_name) is str
            and current_name == expected_name
            and type(current_value) is str
            and current_value == expected_value
        ):
            return member
        break
    raise LeaderboardRequestError()


@dataclass(frozen=True, slots=True)
class PublicationSequence(_NoSerialization):
    """Provider-owned sequence within one fixture publication stream."""

    value: int

    def __post_init__(self) -> None:
        if type(self) is not PublicationSequence:
            raise LeaderboardRequestError()
        object.__setattr__(
            self, "value", _require_exact_u64(self.value, positive=False)
        )


def _copy_publication_sequence(value: object) -> PublicationSequence:
    if type(value) is not PublicationSequence:
        raise LeaderboardRequestError()

    invalid = False
    raw_value: object = None
    try:
        raw_value = object.__getattribute__(value, "value")
    except Exception:  # noqa: BLE001 - capture a hostile exact A10 nominal
        invalid = True
    if invalid:
        raise LeaderboardRequestError()
    return PublicationSequence(_require_exact_u64(raw_value, positive=False))


@dataclass(frozen=True, slots=True)
class LeaderboardSnapshotSequence(_NoSerialization):
    """Provider-owned identity of one retained fixture snapshot."""

    value: int

    def __post_init__(self) -> None:
        if type(self) is not LeaderboardSnapshotSequence:
            raise LeaderboardRequestError()
        object.__setattr__(
            self, "value", _require_exact_u64(self.value, positive=False)
        )


def _copy_snapshot_sequence(value: object) -> LeaderboardSnapshotSequence:
    if type(value) is not LeaderboardSnapshotSequence:
        raise LeaderboardRequestError()

    invalid = False
    raw_value: object = None
    try:
        raw_value = object.__getattribute__(value, "value")
    except Exception:  # noqa: BLE001 - capture a hostile exact A10 nominal
        invalid = True
    if invalid:
        raise LeaderboardRequestError()
    return LeaderboardSnapshotSequence(_require_exact_u64(raw_value, positive=False))


@dataclass(frozen=True, slots=True, repr=False)
class LeaderboardCursor(_NoSerialization):
    """Opaque canonical ASCII continuation value."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not LeaderboardCursor
            or type(self.value) is not str
            or not self.value.isascii()
        ):
            raise LeaderboardRequestError()

    def __repr__(self) -> str:
        return "LeaderboardCursor(<opaque>)"


def _copy_cursor(value: object) -> LeaderboardCursor:
    if type(value) is not LeaderboardCursor:
        raise LeaderboardRequestError()

    invalid = False
    raw_value: object = None
    try:
        raw_value = object.__getattribute__(value, "value")
    except Exception:  # noqa: BLE001 - capture a hostile exact A10 nominal
        invalid = True
    if invalid or type(raw_value) is not str or not raw_value.isascii():
        raise LeaderboardRequestError()
    return LeaderboardCursor(raw_value)


@dataclass(frozen=True, slots=True)
class ListFixtureLeaderboardRequest(_NoSerialization):
    """One bounded fixture-board page request."""

    challenge_key: ChallengeKey
    page_size: int
    cursor: LeaderboardCursor | None

    def __post_init__(self) -> None:
        if type(self) is not ListFixtureLeaderboardRequest:
            raise LeaderboardRequestError()
        challenge_key = _copy_challenge_key(self.challenge_key)
        page_size = _require_exact_u64(self.page_size, positive=True)
        cursor = None if self.cursor is None else _copy_cursor(self.cursor)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "page_size", page_size)
        object.__setattr__(self, "cursor", cursor)


def _copy_request(value: object) -> ListFixtureLeaderboardRequest:
    if type(value) is not ListFixtureLeaderboardRequest:
        raise LeaderboardRequestError()

    invalid = False
    challenge_key: object = None
    page_size: object = None
    cursor: object = None
    try:
        challenge_key = object.__getattribute__(value, "challenge_key")
        page_size = object.__getattribute__(value, "page_size")
        cursor = object.__getattribute__(value, "cursor")
    except Exception:  # noqa: BLE001 - capture a hostile exact A10 request
        invalid = True
    if invalid:
        raise LeaderboardRequestError()
    return ListFixtureLeaderboardRequest(
        challenge_key=challenge_key,  # type: ignore[arg-type]
        page_size=page_size,  # type: ignore[arg-type]
        cursor=cursor,  # type: ignore[arg-type]
    )


@dataclass(frozen=True, slots=True, repr=False)
class FixtureLeaderboardResourceLimits(_NoSerialization):
    """Mandatory finite resource policy for one fixture-board service."""

    max_page_size: int
    max_snapshot_rows: int
    max_cursor_utf8_bytes: int
    max_string_utf8_bytes: int
    max_response_utf8_bytes: int
    max_concurrent_calls: int

    def __post_init__(self) -> None:
        if type(self) is not FixtureLeaderboardResourceLimits:
            raise LeaderboardRequestError()
        for field_name in (
            "max_page_size",
            "max_snapshot_rows",
            "max_cursor_utf8_bytes",
            "max_string_utf8_bytes",
            "max_response_utf8_bytes",
            "max_concurrent_calls",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_exact_u64(
                    object.__getattribute__(self, field_name),
                    positive=True,
                ),
            )

    def __repr__(self) -> str:
        return "FixtureLeaderboardResourceLimits(<private>)"


def _copy_resource_limits(value: object) -> FixtureLeaderboardResourceLimits:
    if type(value) is not FixtureLeaderboardResourceLimits:
        raise LeaderboardRequestError()

    invalid = False
    captured: list[object] = []
    try:
        captured = [
            object.__getattribute__(value, "max_page_size"),
            object.__getattribute__(value, "max_snapshot_rows"),
            object.__getattribute__(value, "max_cursor_utf8_bytes"),
            object.__getattribute__(value, "max_string_utf8_bytes"),
            object.__getattribute__(value, "max_response_utf8_bytes"),
            object.__getattribute__(value, "max_concurrent_calls"),
        ]
    except Exception:  # noqa: BLE001 - capture hostile exact resource policy
        invalid = True
    if invalid:
        raise LeaderboardRequestError()
    return FixtureLeaderboardResourceLimits(*captured)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True, repr=False)
class FixtureLeaderboardCandidate(_NoSerialization):
    """Provider-integration projection, never a public leaderboard row."""

    submission_id: SubmissionId = field(repr=False)
    result_id: str = field(repr=False)
    challenge_key: ChallengeKey
    scoring_pack_hash: str
    score_status: ScoreStatus
    overall_score: float
    mandatory_gates_passed: bool
    fixture_origin: bool
    eligible_for_emission: bool
    publication_sequence: PublicationSequence

    def __post_init__(self) -> None:
        if type(self) is not FixtureLeaderboardCandidate:
            raise LeaderboardRequestError()
        submission_id = _copy_submission_id(self.submission_id)
        result_id = _validated_result_id(self.result_id)
        challenge_key = _copy_challenge_key(self.challenge_key)
        scoring_pack_hash = _validated_scoring_pack_hash(self.scoring_pack_hash)
        score_status = _copy_score_status(self.score_status)
        if type(self.overall_score) is not float or not math.isfinite(
            self.overall_score
        ):
            raise LeaderboardRequestError()
        mandatory_gates_passed = _require_exact_bool(self.mandatory_gates_passed)
        fixture_origin = _require_exact_bool(self.fixture_origin)
        eligible_for_emission = _require_exact_bool(self.eligible_for_emission)
        publication_sequence = _copy_publication_sequence(self.publication_sequence)
        object.__setattr__(self, "submission_id", submission_id)
        object.__setattr__(self, "result_id", result_id)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "scoring_pack_hash", scoring_pack_hash)
        object.__setattr__(self, "score_status", score_status)
        object.__setattr__(self, "mandatory_gates_passed", mandatory_gates_passed)
        object.__setattr__(self, "fixture_origin", fixture_origin)
        object.__setattr__(self, "eligible_for_emission", eligible_for_emission)
        object.__setattr__(self, "publication_sequence", publication_sequence)

    def __repr__(self) -> str:
        return "FixtureLeaderboardCandidate(<private>)"


def _copy_candidate(value: object) -> FixtureLeaderboardCandidate:
    if type(value) is not FixtureLeaderboardCandidate:
        raise LeaderboardRequestError()

    invalid = False
    captured: list[object] = []
    try:
        captured = [
            object.__getattribute__(value, "submission_id"),
            object.__getattribute__(value, "result_id"),
            object.__getattribute__(value, "challenge_key"),
            object.__getattribute__(value, "scoring_pack_hash"),
            object.__getattribute__(value, "score_status"),
            object.__getattribute__(value, "overall_score"),
            object.__getattribute__(value, "mandatory_gates_passed"),
            object.__getattribute__(value, "fixture_origin"),
            object.__getattribute__(value, "eligible_for_emission"),
            object.__getattribute__(value, "publication_sequence"),
        ]
    except Exception:  # noqa: BLE001 - capture a hostile exact candidate
        invalid = True
    if invalid:
        raise LeaderboardRequestError()
    return FixtureLeaderboardCandidate(*captured)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True, repr=False)
class FixtureLeaderboardCandidateSnapshot(_NoSerialization):
    """One immutable provider-owned fixture publication snapshot."""

    challenge_key: ChallengeKey
    scoring_pack_hash: str
    snapshot_sequence: LeaderboardSnapshotSequence
    candidates: tuple[FixtureLeaderboardCandidate, ...]

    def __post_init__(self) -> None:
        if type(self) is not FixtureLeaderboardCandidateSnapshot:
            raise LeaderboardRequestError()
        challenge_key = _copy_challenge_key(self.challenge_key)
        scoring_pack_hash = _validated_scoring_pack_hash(self.scoring_pack_hash)
        snapshot_sequence = _copy_snapshot_sequence(self.snapshot_sequence)
        if type(self.candidates) is not tuple:
            raise LeaderboardRequestError()
        candidates = tuple(_copy_candidate(value) for value in self.candidates)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "scoring_pack_hash", scoring_pack_hash)
        object.__setattr__(self, "snapshot_sequence", snapshot_sequence)
        object.__setattr__(self, "candidates", candidates)

    def __repr__(self) -> str:
        return "FixtureLeaderboardCandidateSnapshot(<private>)"


@dataclass(frozen=True, slots=True)
class FixtureLeaderboardRow(_NoSerialization):
    """Exact public projection of one eligible fixture publication."""

    rank: int
    challenge_key: ChallengeKey
    scoring_pack_hash: str
    overall_score: float
    mandatory_gates_passed: bool
    publication_sequence: PublicationSequence
    fixture_origin: bool
    eligible_for_emission: bool

    def __post_init__(self) -> None:
        if type(self) is not FixtureLeaderboardRow:
            raise LeaderboardRequestError()
        rank = _require_exact_u64(self.rank, positive=True)
        challenge_key = _copy_challenge_key(self.challenge_key)
        scoring_pack_hash = _validated_scoring_pack_hash(self.scoring_pack_hash)
        if (
            type(self.overall_score) is not float
            or not math.isfinite(self.overall_score)
            or not 0.0 <= self.overall_score <= 1.0
            or (
                self.overall_score == 0.0
                and math.copysign(1.0, self.overall_score) != 1.0
            )
        ):
            raise LeaderboardRequestError()
        if self.mandatory_gates_passed is not True:
            raise LeaderboardRequestError()
        publication_sequence = _copy_publication_sequence(self.publication_sequence)
        if self.fixture_origin is not True or self.eligible_for_emission is not False:
            raise LeaderboardRequestError()
        object.__setattr__(self, "rank", rank)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "scoring_pack_hash", scoring_pack_hash)
        object.__setattr__(self, "publication_sequence", publication_sequence)


def _copy_row(value: object) -> FixtureLeaderboardRow:
    if type(value) is not FixtureLeaderboardRow:
        raise LeaderboardRequestError()

    invalid = False
    captured: list[object] = []
    try:
        captured = [
            object.__getattribute__(value, "rank"),
            object.__getattribute__(value, "challenge_key"),
            object.__getattribute__(value, "scoring_pack_hash"),
            object.__getattribute__(value, "overall_score"),
            object.__getattribute__(value, "mandatory_gates_passed"),
            object.__getattribute__(value, "publication_sequence"),
            object.__getattribute__(value, "fixture_origin"),
            object.__getattribute__(value, "eligible_for_emission"),
        ]
    except Exception:  # noqa: BLE001 - capture a hostile exact public row
        invalid = True
    if invalid:
        raise LeaderboardRequestError()
    return FixtureLeaderboardRow(*captured)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class FixtureLeaderboardPage(_NoSerialization):
    """One fully metered public fixture leaderboard page."""

    schema_version: str
    challenge_key: ChallengeKey
    scoring_pack_hash: str
    snapshot_sequence: LeaderboardSnapshotSequence
    rows: tuple[FixtureLeaderboardRow, ...]
    next_cursor: LeaderboardCursor | None
    fixture_origin: bool
    eligible_for_emission: bool

    def __post_init__(self) -> None:
        if type(self) is not FixtureLeaderboardPage:
            raise LeaderboardRequestError()
        if (
            type(self.schema_version) is not str
            or self.schema_version != _SCHEMA_VERSION
        ):
            raise LeaderboardRequestError()
        challenge_key = _copy_challenge_key(self.challenge_key)
        scoring_pack_hash = _validated_scoring_pack_hash(self.scoring_pack_hash)
        snapshot_sequence = _copy_snapshot_sequence(self.snapshot_sequence)
        if type(self.rows) is not tuple:
            raise LeaderboardRequestError()
        rows = tuple(_copy_row(value) for value in self.rows)
        next_cursor = (
            None if self.next_cursor is None else _copy_cursor(self.next_cursor)
        )
        if self.fixture_origin is not True or self.eligible_for_emission is not False:
            raise LeaderboardRequestError()
        object.__setattr__(self, "schema_version", _SCHEMA_VERSION)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "scoring_pack_hash", scoring_pack_hash)
        object.__setattr__(self, "snapshot_sequence", snapshot_sequence)
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "next_cursor", next_cursor)


def _encode_cursor_field(field_name: str, value: str) -> str:
    return f"{field_name}={len(value)}:{value}"


def _encode_cursor(
    challenge_key: ChallengeKey,
    scoring_pack_hash: str,
    snapshot_sequence: LeaderboardSnapshotSequence,
    next_offset: int,
) -> LeaderboardCursor:
    owned_challenge_key = _copy_challenge_key(challenge_key)
    owned_hash = _validated_scoring_pack_hash(scoring_pack_hash)
    owned_snapshot_sequence = _copy_snapshot_sequence(snapshot_sequence)
    owned_offset = _require_exact_u64(next_offset, positive=False)
    values = (
        _SCHEMA_VERSION,
        _BOARD_KIND,
        owned_challenge_key.challenge_id,
        owned_challenge_key.version,
        owned_hash,
        str(owned_snapshot_sequence.value),
        str(owned_offset),
    )
    encoded = "|".join(
        _encode_cursor_field(field_name, value)
        for field_name, value in zip(_CURSOR_FIELDS, values, strict=True)
    )
    return LeaderboardCursor(encoded)


def _parse_canonical_u64(value: str) -> int | None:
    if value == "0":
        return 0
    if not value or value[0] == "0":
        return None
    parsed = 0
    for character in value:
        if character < "0" or character > "9":
            return None
        parsed = (parsed * 10) + (ord(character) - ord("0"))
        if parsed > _UINT64_MAX:
            return None
    return parsed


def _parse_cursor_fields(value: str) -> tuple[str, ...] | None:
    position = 0
    parsed: list[str] = []
    for index, field_name in enumerate(_CURSOR_FIELDS):
        prefix = f"{field_name}="
        if not value.startswith(prefix, position):
            return None
        position += len(prefix)
        length_start = position
        while position < len(value) and "0" <= value[position] <= "9":
            position += 1
        if position == length_start or position >= len(value) or value[position] != ":":
            return None
        length_text = value[length_start:position]
        field_length = _parse_canonical_u64(length_text)
        if field_length is None:
            return None
        position += 1
        field_end = position + field_length
        if field_end > len(value):
            return None
        parsed.append(value[position:field_end])
        position = field_end
        if index < len(_CURSOR_FIELDS) - 1:
            if position >= len(value) or value[position] != "|":
                return None
            position += 1
    if position != len(value):
        return None
    return tuple(parsed)


def _decode_cursor(
    cursor: LeaderboardCursor,
) -> tuple[ChallengeKey, str, LeaderboardSnapshotSequence, int]:
    owned_cursor = _copy_cursor(cursor)
    parsed = _parse_cursor_fields(owned_cursor.value)
    if parsed is None:
        raise LeaderboardRequestError()
    (
        schema_version,
        board_kind,
        challenge_id,
        challenge_version,
        scoring_pack_hash,
        snapshot_sequence_text,
        next_offset_text,
    ) = parsed
    if schema_version != _SCHEMA_VERSION or board_kind != _BOARD_KIND:
        raise LeaderboardRequestError()

    invalid = False
    challenge_key: ChallengeKey | None = None
    try:
        challenge_key = ChallengeKey(challenge_id, challenge_version)
    except Exception:  # noqa: BLE001 - normalize cursor owner construction
        invalid = True
    if invalid or type(challenge_key) is not ChallengeKey:
        raise LeaderboardRequestError()
    scoring_pack_hash = _validated_scoring_pack_hash(scoring_pack_hash)
    snapshot_sequence_value = _parse_canonical_u64(snapshot_sequence_text)
    next_offset = _parse_canonical_u64(next_offset_text)
    if snapshot_sequence_value is None or next_offset is None:
        raise LeaderboardRequestError()
    snapshot_sequence = LeaderboardSnapshotSequence(snapshot_sequence_value)
    canonical = _encode_cursor(
        challenge_key,
        scoring_pack_hash,
        snapshot_sequence,
        next_offset,
    )
    if canonical.value != owned_cursor.value:
        raise LeaderboardRequestError()
    return (
        _copy_challenge_key(challenge_key),
        scoring_pack_hash,
        _copy_snapshot_sequence(snapshot_sequence),
        next_offset,
    )
