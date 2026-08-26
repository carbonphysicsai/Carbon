"""Bounded fixture-only leaderboard projection service."""

from __future__ import annotations

import math
import threading

from carbon.fees import SubmissionId
from carbon.registry import ChallengeKey, is_sha256_digest, validate_version
from carbon.scoring import ScoreStatus

from .model import (
    FixtureLeaderboardCandidate,
    FixtureLeaderboardCandidateSnapshot,
    FixtureLeaderboardPage,
    FixtureLeaderboardResourceLimits,
    FixtureLeaderboardRow,
    LeaderboardCursor,
    LeaderboardError,
    LeaderboardIntegrationError,
    LeaderboardRequestError,
    LeaderboardResourceError,
    LeaderboardSnapshotSequence,
    LeaderboardUnavailableError,
    ListFixtureLeaderboardRequest,
    PublicationSequence,
    _decode_cursor,
    _encode_cursor,
)
from .providers import FixtureLeaderboardProvider

_UINT64_MAX = (1 << 64) - 1
_PUBLIC_ERRORS = (
    LeaderboardRequestError,
    LeaderboardResourceError,
    LeaderboardUnavailableError,
    LeaderboardIntegrationError,
)


def _request_field(value: object, name: str) -> object:
    failed = False
    try:
        result = object.__getattribute__(value, name)
    except Exception:  # noqa: BLE001 - hostile public nominal capture
        failed = True
    else:
        return result
    if failed:
        raise LeaderboardRequestError()
    raise AssertionError


def _provider_field(value: object, name: str) -> object:
    failed = False
    try:
        result = object.__getattribute__(value, name)
    except Exception:  # noqa: BLE001 - the ratified provider exception seam
        failed = True
    else:
        return result
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _require_utf8_capacity(value: str, maximum: int) -> None:
    if len(value) > maximum:
        raise LeaderboardResourceError()
    width = 0
    for character in value:
        code_point = ord(character)
        if code_point <= 0x7F:
            width += 1
        elif code_point <= 0x7FF:
            width += 2
        elif 0xD800 <= code_point <= 0xDFFF:
            return
        elif code_point <= 0xFFFF:
            width += 3
        else:
            width += 4
        if width > maximum:
            raise LeaderboardResourceError()


def _require_string_capacity(
    value: str, limits: FixtureLeaderboardResourceLimits
) -> None:
    _require_utf8_capacity(value, limits.max_string_utf8_bytes)


def _copy_limits(value: object) -> FixtureLeaderboardResourceLimits:
    if type(value) is not FixtureLeaderboardResourceLimits:
        raise LeaderboardRequestError()
    max_page_size = _request_field(value, "max_page_size")
    max_snapshot_rows = _request_field(value, "max_snapshot_rows")
    max_cursor_utf8_bytes = _request_field(value, "max_cursor_utf8_bytes")
    max_string_utf8_bytes = _request_field(value, "max_string_utf8_bytes")
    max_response_utf8_bytes = _request_field(value, "max_response_utf8_bytes")
    max_concurrent_calls = _request_field(value, "max_concurrent_calls")
    values = (
        max_page_size,
        max_snapshot_rows,
        max_cursor_utf8_bytes,
        max_string_utf8_bytes,
        max_response_utf8_bytes,
        max_concurrent_calls,
    )
    if not all(type(item) is int and 0 < item <= _UINT64_MAX for item in values):
        raise LeaderboardRequestError()
    failed = False
    try:
        owned = FixtureLeaderboardResourceLimits(
            max_page_size,
            max_snapshot_rows,
            max_cursor_utf8_bytes,
            max_string_utf8_bytes,
            max_response_utf8_bytes,
            max_concurrent_calls,
        )
    except Exception:  # noqa: BLE001 - normalize invalid constructor state
        failed = True
    else:
        return owned
    if failed:
        raise LeaderboardRequestError()
    raise AssertionError


def _copy_request_challenge(
    value: object, limits: FixtureLeaderboardResourceLimits
) -> ChallengeKey:
    if type(value) is not ChallengeKey:
        raise LeaderboardRequestError()
    challenge_id = _request_field(value, "challenge_id")
    version = _request_field(value, "version")
    if type(challenge_id) is not str or type(version) is not str:
        raise LeaderboardRequestError()
    _require_string_capacity(challenge_id, limits)
    _require_string_capacity(version, limits)
    if not challenge_id.isascii() or not version.isascii():
        raise LeaderboardRequestError()
    failed = False
    try:
        owned = ChallengeKey(challenge_id, version)
    except Exception:  # noqa: BLE001 - normalize invalid owner nominal state
        failed = True
    else:
        return owned
    if failed:
        raise LeaderboardRequestError()
    raise AssertionError


def _copy_provider_challenge(
    value: object, limits: FixtureLeaderboardResourceLimits
) -> ChallengeKey:
    if type(value) is not ChallengeKey:
        raise LeaderboardIntegrationError()
    challenge_id = _provider_field(value, "challenge_id")
    version = _provider_field(value, "version")
    if type(challenge_id) is not str or type(version) is not str:
        raise LeaderboardIntegrationError()
    _require_string_capacity(challenge_id, limits)
    _require_string_capacity(version, limits)
    if not challenge_id.isascii() or not version.isascii():
        raise LeaderboardIntegrationError()
    failed = False
    try:
        owned = ChallengeKey(challenge_id, version)
    except Exception:  # noqa: BLE001 - provider graph invalidity collapses
        failed = True
    else:
        return owned
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _same_challenge(left: ChallengeKey, right: ChallengeKey) -> bool:
    return object.__getattribute__(left, "challenge_id") == object.__getattribute__(
        right, "challenge_id"
    ) and object.__getattribute__(left, "version") == object.__getattribute__(
        right, "version"
    )


def _copy_request_hash(value: object, limits: FixtureLeaderboardResourceLimits) -> str:
    if type(value) is not str or not is_sha256_digest(value):
        raise LeaderboardRequestError()
    _require_string_capacity(value, limits)
    return value


def _copy_provider_hash(value: object, limits: FixtureLeaderboardResourceLimits) -> str:
    if type(value) is not str:
        raise LeaderboardIntegrationError()
    _require_string_capacity(value, limits)
    if not is_sha256_digest(value):
        raise LeaderboardIntegrationError()
    return value


def _copy_request_snapshot_sequence(value: object) -> LeaderboardSnapshotSequence:
    if type(value) is not LeaderboardSnapshotSequence:
        raise LeaderboardRequestError()
    raw = _request_field(value, "value")
    if type(raw) is not int or not 0 <= raw <= _UINT64_MAX:
        raise LeaderboardRequestError()
    failed = False
    try:
        owned = LeaderboardSnapshotSequence(raw)
    except Exception:  # noqa: BLE001 - normalize invalid public nominal state
        failed = True
    else:
        return owned
    if failed:
        raise LeaderboardRequestError()
    raise AssertionError


def _copy_provider_snapshot_sequence(value: object) -> LeaderboardSnapshotSequence:
    if type(value) is not LeaderboardSnapshotSequence:
        raise LeaderboardIntegrationError()
    raw = _provider_field(value, "value")
    if type(raw) is not int or not 0 <= raw <= _UINT64_MAX:
        raise LeaderboardIntegrationError()
    failed = False
    try:
        owned = LeaderboardSnapshotSequence(raw)
    except Exception:  # noqa: BLE001 - provider graph invalidity collapses
        failed = True
    else:
        return owned
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _copy_publication_sequence(value: object) -> PublicationSequence:
    if type(value) is not PublicationSequence:
        raise LeaderboardIntegrationError()
    raw = _provider_field(value, "value")
    if type(raw) is not int or not 0 <= raw <= _UINT64_MAX:
        raise LeaderboardIntegrationError()
    failed = False
    try:
        owned = PublicationSequence(raw)
    except Exception:  # noqa: BLE001 - provider graph invalidity collapses
        failed = True
    else:
        return owned
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _copy_submission_id(
    value: object, limits: FixtureLeaderboardResourceLimits
) -> SubmissionId:
    if type(value) is not SubmissionId:
        raise LeaderboardIntegrationError()
    raw = _provider_field(value, "value")
    if type(raw) is not str:
        raise LeaderboardIntegrationError()
    _require_string_capacity(raw, limits)
    if not raw.isascii():
        raise LeaderboardIntegrationError()
    failed = False
    try:
        owned = SubmissionId(raw)
    except Exception:  # noqa: BLE001 - provider graph invalidity collapses
        failed = True
    else:
        return owned
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _copy_result_id(value: object, limits: FixtureLeaderboardResourceLimits) -> str:
    if type(value) is not str:
        raise LeaderboardIntegrationError()
    _require_string_capacity(value, limits)
    if not value.isascii():
        raise LeaderboardIntegrationError()
    failed = False
    try:
        owned = validate_version(value)
    except Exception:  # noqa: BLE001 - provider graph invalidity collapses
        failed = True
    else:
        if type(owned) is not str or owned != value:
            raise LeaderboardIntegrationError()
        return value
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _copy_score_status(
    value: object, limits: FixtureLeaderboardResourceLimits
) -> ScoreStatus:
    if type(value) is not ScoreStatus or value is not ScoreStatus.SCORED:
        raise LeaderboardIntegrationError()
    name = _provider_field(value, "name")
    literal = _provider_field(value, "value")
    if (
        type(name) is not str
        or name != "SCORED"
        or type(literal) is not str
        or literal != "SCORED"
    ):
        raise LeaderboardIntegrationError()
    _require_string_capacity(name, limits)
    _require_string_capacity(literal, limits)
    return ScoreStatus.SCORED


def _copy_request_cursor(
    value: object,
    request_challenge: ChallengeKey,
    limits: FixtureLeaderboardResourceLimits,
) -> tuple[
    LeaderboardCursor,
    LeaderboardSnapshotSequence,
    str,
    int,
]:
    if type(value) is not LeaderboardCursor:
        raise LeaderboardRequestError()
    raw = _request_field(value, "value")
    if type(raw) is not str:
        raise LeaderboardRequestError()
    _require_utf8_capacity(raw, limits.max_cursor_utf8_bytes)
    _require_utf8_capacity(raw, limits.max_string_utf8_bytes)
    if not raw.isascii():
        raise LeaderboardRequestError()
    failed = False
    try:
        owned_cursor = LeaderboardCursor(raw)
        decoded = _decode_cursor(owned_cursor)
    except Exception:  # noqa: BLE001 - malformed caller cursor is one request error
        failed = True
    else:
        if type(decoded) is not tuple or tuple.__len__(decoded) != 4:
            raise LeaderboardRequestError()
        decoded_challenge = tuple.__getitem__(decoded, 0)
        decoded_hash = tuple.__getitem__(decoded, 1)
        decoded_sequence = tuple.__getitem__(decoded, 2)
        decoded_offset = tuple.__getitem__(decoded, 3)
        owned_challenge = _copy_request_challenge(decoded_challenge, limits)
        owned_hash = _copy_request_hash(decoded_hash, limits)
        owned_sequence = _copy_request_snapshot_sequence(decoded_sequence)
        if (
            type(decoded_offset) is not int
            or not 0 <= decoded_offset <= _UINT64_MAX
            or not _same_challenge(owned_challenge, request_challenge)
        ):
            raise LeaderboardRequestError()
        return owned_cursor, owned_sequence, owned_hash, decoded_offset
    if failed:
        raise LeaderboardRequestError()
    raise AssertionError


def _copy_request(
    value: ListFixtureLeaderboardRequest,
    limits: FixtureLeaderboardResourceLimits,
) -> tuple[ChallengeKey, int, LeaderboardSnapshotSequence | None, str | None, int]:
    challenge_value = _request_field(value, "challenge_key")
    page_size = _request_field(value, "page_size")
    cursor_value = _request_field(value, "cursor")
    challenge = _copy_request_challenge(challenge_value, limits)
    if type(page_size) is not int or not 1 <= page_size <= _UINT64_MAX:
        raise LeaderboardRequestError()
    if page_size > limits.max_page_size:
        raise LeaderboardResourceError()
    if cursor_value is None:
        cursor = None
        snapshot_sequence = None
        scoring_pack_hash = None
        next_offset = 0
    else:
        cursor, snapshot_sequence, scoring_pack_hash, next_offset = (
            _copy_request_cursor(cursor_value, challenge, limits)
        )
    failed = False
    try:
        ListFixtureLeaderboardRequest(challenge, page_size, cursor)
    except Exception:  # noqa: BLE001 - normalize invalid public nominal state
        failed = True
    else:
        return (
            challenge,
            page_size,
            snapshot_sequence,
            scoring_pack_hash,
            next_offset,
        )
    if failed:
        raise LeaderboardRequestError()
    raise AssertionError


def _invoke_provider(
    provider: FixtureLeaderboardProvider,
    challenge_key: ChallengeKey,
    snapshot_sequence: LeaderboardSnapshotSequence | None,
) -> object:
    failed = False
    try:
        method = provider.get_snapshot
        result = method(challenge_key, snapshot_sequence)
    except Exception:  # noqa: BLE001 - the exact ordinary-provider seam
        failed = True
    else:
        return result
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _construct_candidate(
    submission_id: SubmissionId,
    result_id: str,
    challenge_key: ChallengeKey,
    scoring_pack_hash: str,
    score_status: ScoreStatus,
    overall_score: float,
    mandatory_gates_passed: bool,
    fixture_origin: bool,
    eligible_for_emission: bool,
    publication_sequence: PublicationSequence,
) -> FixtureLeaderboardCandidate:
    failed = False
    try:
        owned = FixtureLeaderboardCandidate(
            submission_id,
            result_id,
            challenge_key,
            scoring_pack_hash,
            score_status,
            overall_score,
            mandatory_gates_passed,
            fixture_origin,
            eligible_for_emission,
            publication_sequence,
        )
    except Exception:  # noqa: BLE001 - provider graph invalidity collapses
        failed = True
    else:
        return owned
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _copy_candidate(
    value: object,
    snapshot_challenge: ChallengeKey,
    scoring_pack_hash: str,
    limits: FixtureLeaderboardResourceLimits,
) -> tuple[FixtureLeaderboardCandidate, str, str, int]:
    if type(value) is not FixtureLeaderboardCandidate:
        raise LeaderboardIntegrationError()
    submission_value = _provider_field(value, "submission_id")
    result_value = _provider_field(value, "result_id")
    challenge_value = _provider_field(value, "challenge_key")
    hash_value = _provider_field(value, "scoring_pack_hash")
    status_value = _provider_field(value, "score_status")
    score_value = _provider_field(value, "overall_score")
    mandatory_value = _provider_field(value, "mandatory_gates_passed")
    fixture_value = _provider_field(value, "fixture_origin")
    emission_value = _provider_field(value, "eligible_for_emission")
    publication_value = _provider_field(value, "publication_sequence")

    submission_id = _copy_submission_id(submission_value, limits)
    result_id = _copy_result_id(result_value, limits)
    challenge_key = _copy_provider_challenge(challenge_value, limits)
    candidate_hash = _copy_provider_hash(hash_value, limits)
    score_status = _copy_score_status(status_value, limits)
    publication_sequence = _copy_publication_sequence(publication_value)
    if (
        type(score_value) is not float
        or not math.isfinite(score_value)
        or not 0.0 <= score_value <= 1.0
        or (score_value == 0.0 and math.copysign(1.0, score_value) != 1.0)
        or type(mandatory_value) is not bool
        or mandatory_value is not True
        or type(fixture_value) is not bool
        or fixture_value is not True
        or type(emission_value) is not bool
        or emission_value is not False
        or not _same_challenge(challenge_key, snapshot_challenge)
        or candidate_hash != scoring_pack_hash
    ):
        raise LeaderboardIntegrationError()
    owned = _construct_candidate(
        submission_id,
        result_id,
        challenge_key,
        candidate_hash,
        score_status,
        score_value,
        True,
        True,
        False,
        publication_sequence,
    )
    return (
        owned,
        object.__getattribute__(submission_id, "value"),
        result_id,
        object.__getattribute__(publication_sequence, "value"),
    )


def _construct_snapshot(
    challenge_key: ChallengeKey,
    scoring_pack_hash: str,
    snapshot_sequence: LeaderboardSnapshotSequence,
    candidates: tuple[FixtureLeaderboardCandidate, ...],
) -> FixtureLeaderboardCandidateSnapshot:
    failed = False
    try:
        owned = FixtureLeaderboardCandidateSnapshot(
            challenge_key,
            scoring_pack_hash,
            snapshot_sequence,
            candidates,
        )
    except Exception:  # noqa: BLE001 - provider graph invalidity collapses
        failed = True
    else:
        return owned
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _copy_snapshot(
    value: object,
    request_challenge: ChallengeKey,
    cursor_hash: str | None,
    cursor_sequence: LeaderboardSnapshotSequence | None,
    limits: FixtureLeaderboardResourceLimits,
) -> FixtureLeaderboardCandidateSnapshot:
    if type(value) is not FixtureLeaderboardCandidateSnapshot:
        raise LeaderboardIntegrationError()
    challenge_value = _provider_field(value, "challenge_key")
    hash_value = _provider_field(value, "scoring_pack_hash")
    sequence_value = _provider_field(value, "snapshot_sequence")
    candidates_value = _provider_field(value, "candidates")
    challenge_key = _copy_provider_challenge(challenge_value, limits)
    scoring_pack_hash = _copy_provider_hash(hash_value, limits)
    snapshot_sequence = _copy_provider_snapshot_sequence(sequence_value)
    if type(candidates_value) is not tuple:
        raise LeaderboardIntegrationError()
    candidate_count = tuple.__len__(candidates_value)
    if candidate_count > limits.max_snapshot_rows:
        raise LeaderboardResourceError()
    if not _same_challenge(challenge_key, request_challenge):
        raise LeaderboardIntegrationError()
    if cursor_hash is not None:
        if cursor_sequence is None:
            raise LeaderboardIntegrationError()
        if scoring_pack_hash != cursor_hash or object.__getattribute__(
            snapshot_sequence, "value"
        ) != object.__getattribute__(cursor_sequence, "value"):
            raise LeaderboardIntegrationError()

    owned_candidates: list[FixtureLeaderboardCandidate] = []
    submission_ids: set[str] = set()
    result_ids: set[str] = set()
    publication_sequences: set[int] = set()
    for index in range(candidate_count):
        candidate_value = tuple.__getitem__(candidates_value, index)
        candidate, submission_id, result_id, publication_sequence = _copy_candidate(
            candidate_value,
            challenge_key,
            scoring_pack_hash,
            limits,
        )
        if (
            submission_id in submission_ids
            or result_id in result_ids
            or publication_sequence in publication_sequences
        ):
            raise LeaderboardIntegrationError()
        submission_ids.add(submission_id)
        result_ids.add(result_id)
        publication_sequences.add(publication_sequence)
        owned_candidates.append(candidate)
    return _construct_snapshot(
        challenge_key,
        scoring_pack_hash,
        snapshot_sequence,
        tuple(owned_candidates),
    )


def _sort_key(candidate: FixtureLeaderboardCandidate) -> tuple[float, int]:
    score = object.__getattribute__(candidate, "overall_score")
    sequence = object.__getattribute__(candidate, "publication_sequence")
    return (-score, object.__getattribute__(sequence, "value"))


def _rank_snapshot(
    snapshot: FixtureLeaderboardCandidateSnapshot,
) -> list[tuple[FixtureLeaderboardCandidate, int]]:
    candidates = object.__getattribute__(snapshot, "candidates")
    ordered = list(candidates)
    ordered.sort(key=_sort_key)
    ranked: list[tuple[FixtureLeaderboardCandidate, int]] = []
    previous_score: float | None = None
    current_rank = 0
    for index, candidate in enumerate(ordered):
        score = object.__getattribute__(candidate, "overall_score")
        if index == 0 or score != previous_score:
            current_rank = index + 1
        ranked.append((candidate, current_rank))
        previous_score = score
    return ranked


def _new_row(
    candidate: FixtureLeaderboardCandidate,
    rank: int,
    limits: FixtureLeaderboardResourceLimits,
) -> FixtureLeaderboardRow:
    challenge = _copy_provider_challenge(
        object.__getattribute__(candidate, "challenge_key"), limits
    )
    scoring_pack_hash = _copy_provider_hash(
        object.__getattribute__(candidate, "scoring_pack_hash"), limits
    )
    publication_sequence = _copy_publication_sequence(
        object.__getattribute__(candidate, "publication_sequence")
    )
    overall_score = object.__getattribute__(candidate, "overall_score")
    failed = False
    try:
        row = FixtureLeaderboardRow(
            rank,
            challenge,
            scoring_pack_hash,
            overall_score,
            True,
            publication_sequence,
            True,
            False,
        )
    except Exception:  # noqa: BLE001 - fail closed on projection construction
        failed = True
    else:
        return row
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _new_cursor(
    challenge_key: ChallengeKey,
    scoring_pack_hash: str,
    snapshot_sequence: LeaderboardSnapshotSequence,
    next_offset: int,
    limits: FixtureLeaderboardResourceLimits,
) -> LeaderboardCursor:
    failed = False
    try:
        cursor = _encode_cursor(
            challenge_key,
            scoring_pack_hash,
            snapshot_sequence,
            next_offset,
        )
    except Exception:  # noqa: BLE001 - fail closed on internal cursor construction
        failed = True
    else:
        if type(cursor) is not LeaderboardCursor:
            raise LeaderboardIntegrationError()
        raw = object.__getattribute__(cursor, "value")
        if type(raw) is not str or not raw.isascii():
            raise LeaderboardIntegrationError()
        if (
            len(raw) > limits.max_cursor_utf8_bytes
            or len(raw) > limits.max_string_utf8_bytes
        ):
            raise LeaderboardResourceError()
        return cursor
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _new_page(
    snapshot: FixtureLeaderboardCandidateSnapshot,
    rows: tuple[FixtureLeaderboardRow, ...],
    next_cursor: LeaderboardCursor | None,
    limits: FixtureLeaderboardResourceLimits,
) -> FixtureLeaderboardPage:
    challenge_key = _copy_provider_challenge(
        object.__getattribute__(snapshot, "challenge_key"), limits
    )
    scoring_pack_hash = _copy_provider_hash(
        object.__getattribute__(snapshot, "scoring_pack_hash"), limits
    )
    snapshot_sequence = _copy_provider_snapshot_sequence(
        object.__getattribute__(snapshot, "snapshot_sequence")
    )
    failed = False
    try:
        page = FixtureLeaderboardPage(
            "1.0",
            challenge_key,
            scoring_pack_hash,
            snapshot_sequence,
            rows,
            next_cursor,
            True,
            False,
        )
    except Exception:  # noqa: BLE001 - fail closed on projection construction
        failed = True
    else:
        return page
    if failed:
        raise LeaderboardIntegrationError()
    raise AssertionError


def _charge_response_text(
    total: int,
    value: object,
    limits: FixtureLeaderboardResourceLimits,
) -> int:
    if type(value) is not str or not value.isascii():
        raise LeaderboardIntegrationError()
    width = len(value)
    if width > limits.max_string_utf8_bytes:
        raise LeaderboardResourceError()
    if width > limits.max_response_utf8_bytes - total:
        raise LeaderboardResourceError()
    return total + width


def _response_utf8_bytes(
    page: FixtureLeaderboardPage,
    limits: FixtureLeaderboardResourceLimits,
) -> int:
    if type(page) is not FixtureLeaderboardPage:
        raise LeaderboardIntegrationError()
    total = _charge_response_text(0, page.schema_version, limits)
    if type(page.challenge_key) is not ChallengeKey:
        raise LeaderboardIntegrationError()
    total = _charge_response_text(total, page.challenge_key.challenge_id, limits)
    total = _charge_response_text(total, page.challenge_key.version, limits)
    total = _charge_response_text(total, page.scoring_pack_hash, limits)
    if type(page.rows) is not tuple:
        raise LeaderboardIntegrationError()
    for row in page.rows:
        if type(row) is not FixtureLeaderboardRow:
            raise LeaderboardIntegrationError()
        if type(row.challenge_key) is not ChallengeKey:
            raise LeaderboardIntegrationError()
        total = _charge_response_text(total, row.challenge_key.challenge_id, limits)
        total = _charge_response_text(total, row.challenge_key.version, limits)
        total = _charge_response_text(total, row.scoring_pack_hash, limits)
    if page.next_cursor is not None:
        if type(page.next_cursor) is not LeaderboardCursor:
            raise LeaderboardIntegrationError()
        cursor_value = page.next_cursor.value
        if type(cursor_value) is not str or not cursor_value.isascii():
            raise LeaderboardIntegrationError()
        if len(cursor_value) > limits.max_cursor_utf8_bytes:
            raise LeaderboardResourceError()
        total = _charge_response_text(total, cursor_value, limits)
    return total


class FixtureLeaderboardService:
    """The sole bounded in-process fixture leaderboard service."""

    __slots__ = (
        "_active_calls",
        "_admission_lock",
        "_limits",
        "_provider",
    )

    def __init__(
        self,
        provider: FixtureLeaderboardProvider,
        resource_limits: FixtureLeaderboardResourceLimits,
    ) -> None:
        if type(self) is not FixtureLeaderboardService or provider is None:
            raise LeaderboardRequestError()
        limits = _copy_limits(resource_limits)
        self._provider = provider
        self._limits = limits
        self._admission_lock = threading.Lock()
        self._active_calls = 0

    def _admit(self) -> bool:
        if not self._admission_lock.acquire(blocking=False):
            return False
        try:
            if self._active_calls >= self._limits.max_concurrent_calls:
                return False
            self._active_calls += 1
            return True
        finally:
            self._admission_lock.release()

    def _release(self) -> None:
        with self._admission_lock:
            self._active_calls -= 1

    def list_entries(
        self, request: ListFixtureLeaderboardRequest
    ) -> FixtureLeaderboardPage:
        if type(request) is not ListFixtureLeaderboardRequest:
            raise LeaderboardRequestError()
        if not self._admit():
            raise LeaderboardResourceError()
        result: FixtureLeaderboardPage | None = None
        public_error: LeaderboardError | None = None
        integration_failure = False
        try:
            try:
                result = self._list_admitted(request)
                if type(result) is not FixtureLeaderboardPage:
                    integration_failure = True
            except _PUBLIC_ERRORS as error:
                if type(error) in _PUBLIC_ERRORS:
                    public_error = error
                else:
                    integration_failure = True
            except Exception:  # noqa: BLE001 - fixed public boundary collapse
                integration_failure = True
            if integration_failure:
                public_error = LeaderboardIntegrationError()
        finally:
            self._release()
        if public_error is not None:
            raise public_error
        if result is None:
            raise LeaderboardIntegrationError()
        return result

    def _list_admitted(
        self, request: ListFixtureLeaderboardRequest
    ) -> FixtureLeaderboardPage:
        (
            challenge_key,
            page_size,
            cursor_sequence,
            cursor_hash,
            offset,
        ) = _copy_request(request, self._limits)
        provider_challenge_key = _copy_request_challenge(challenge_key, self._limits)
        provider_snapshot_sequence = (
            None
            if cursor_sequence is None
            else _copy_request_snapshot_sequence(cursor_sequence)
        )
        raw_snapshot = _invoke_provider(
            self._provider,
            provider_challenge_key,
            provider_snapshot_sequence,
        )
        if raw_snapshot is None:
            raise LeaderboardUnavailableError()
        snapshot = _copy_snapshot(
            raw_snapshot,
            challenge_key,
            cursor_hash,
            cursor_sequence,
            self._limits,
        )
        ranked = _rank_snapshot(snapshot)
        row_count = len(ranked)
        if offset > row_count:
            raise LeaderboardRequestError()
        end = min(offset + page_size, row_count)
        rows: list[FixtureLeaderboardRow] = []
        for candidate, rank in ranked[offset:end]:
            rows.append(_new_row(candidate, rank, self._limits))
        snapshot_challenge = object.__getattribute__(snapshot, "challenge_key")
        snapshot_hash = object.__getattribute__(snapshot, "scoring_pack_hash")
        snapshot_sequence = object.__getattribute__(snapshot, "snapshot_sequence")
        next_cursor = None
        if end < row_count:
            next_cursor = _new_cursor(
                snapshot_challenge,
                snapshot_hash,
                snapshot_sequence,
                end,
                self._limits,
            )
        page = _new_page(snapshot, tuple(rows), next_cursor, self._limits)
        _response_utf8_bytes(page, self._limits)
        return page
